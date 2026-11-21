# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Krittidet Chanthake and the Nano-Commons contributors
"""Python client for the Nano-Commons HTTP API (standard library only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Union
from urllib.parse import quote, urlsplit

from .nano_agent import NanoAgentPacket, packet_to_dict
from .server import DEFAULT_HOST, DEFAULT_PORT, is_loopback

DEFAULT_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"


class NanoCommonsError(Exception):
    """The server refused a request (``status`` is the HTTP code) or could not be reached (0)."""

    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}" if status else message)
        self.status = status
        self.message = message


class NanoCommonsClient:
    def __init__(self, url: str = DEFAULT_URL, token: Optional[str] = None, timeout: float = 15.0):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        parts = urlsplit(self.url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError(f"not an http(s) URL: {url!r}")
        # A system proxy must not intercept traffic to this machine.
        handlers = [urllib.request.ProxyHandler({})] if is_loopback(parts.hostname) else []
        self._opener = urllib.request.build_opener(*handlers)

    # --- transport

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        try:
            data = json.dumps(body, allow_nan=False).encode("utf-8") if body is not None else None
        except ValueError:
            raise NanoCommonsError(0, "request contains a value JSON cannot carry "
                                      "(NaN or infinity); nothing was sent") from None
        request = urllib.request.Request(self.url + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if method == "POST" and self.token:
            # Not copied onto redirects, so a redirect to another host cannot leak the token.
            request.add_unredirected_header("Authorization", "Bearer " + self.token)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                message = _error_message(exc)
            finally:
                exc.close()
            raise NanoCommonsError(exc.code, message) from None
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise NanoCommonsError(0, f"cannot reach {self.url}: {reason}") from None
        except ValueError:
            raise NanoCommonsError(0, f"{self.url} did not return JSON; is it a Nano-Commons server?") from None

    def _post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("POST", path, body if body is not None else {})

    # --- reads

    def status(self) -> Dict[str, Any]:
        return self._request("GET", "/api/status")

    def nodes(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/api/nodes")["nodes"]

    def missions(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/api/missions")["missions"]

    def checkpoints(self) -> Dict[str, Any]:
        return self._request("GET", "/api/checkpoints")

    def faults(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/api/faults")["faults"]

    def alarms(self) -> Dict[str, Any]:
        return self._request("GET", "/api/alarms")

    def held(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/api/held")["held"]

    # --- writes (need the operator token)

    def add_node(self, node_id: str, zone: str, reputation: float = 0.15,
                 simulate_malicious: bool = False) -> Dict[str, Any]:
        return self._post("/api/nodes", {"node_id": node_id, "zone": zone, "reputation": reputation,
                                         "simulate_malicious": simulate_malicious})

    def add_mission(self, mission_id: str, public_key: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"mission_id": mission_id}
        if public_key is not None:
            body["public_key"] = public_key
        return self._post("/api/missions", body)

    def task(self, mission_id: str, value: float, workers: Sequence[str],
             threshold: Optional[float] = None, bind_workers: bool = True,
             shard_id: Optional[str] = None, hop_energy_cost: Optional[int] = None) -> Dict[str, Any]:
        body = {"mission_id": mission_id, "observation": _observation(value, threshold),
                "workers": list(workers), "bind_workers": bind_workers}
        _optional(body, shard_id=shard_id, hop_energy_cost=hop_energy_cost)
        return self._post("/api/tasks", body)

    def canary(self, mission_id: str, value: float, expected_verdict: str, workers: Sequence[str],
               threshold: Optional[float] = None, bind_workers: bool = True) -> Dict[str, Any]:
        return self._post("/api/canaries", {
            "mission_id": mission_id, "observation": _observation(value, threshold),
            "expected_verdict": expected_verdict, "workers": list(workers),
            "bind_workers": bind_workers})

    def submit_packet(self, packet: Union[NanoAgentPacket, Dict[str, Any]], observation: Dict[str, Any],
                      workers: Sequence[str], hop_energy_cost: Optional[int] = None) -> Dict[str, Any]:
        """Submit a packet that was signed elsewhere (``packet`` may be a dataclass or its dict)."""
        body = {"packet": packet_to_dict(packet) if isinstance(packet, NanoAgentPacket) else packet,
                "observation": observation, "workers": list(workers)}
        _optional(body, hop_energy_cost=hop_energy_cost)
        return self._post("/api/packets", body)

    def rollback(self, checkpoint_id: int) -> Dict[str, Any]:
        return self._post("/api/rollback", {"checkpoint_id": checkpoint_id})

    def review(self, checkpoint_id: int) -> Dict[str, Any]:
        return self._post(f"/api/checkpoints/{quote(str(checkpoint_id), safe='')}/review")


def _observation(value: float, threshold: Optional[float]) -> Dict[str, Any]:
    observation: Dict[str, Any] = {"value": value}
    if threshold is not None:
        observation["threshold"] = threshold
    return observation


def _optional(body: Dict[str, Any], **fields: Any) -> None:
    body.update({k: v for k, v in fields.items() if v is not None})


def _error_message(exc: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        return str(payload["error"])
    except (ValueError, KeyError, TypeError, OSError):
        return exc.reason or "request failed"
