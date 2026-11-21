# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Krittidet Chanthake and the Nano-Commons contributors
"""Local node console: HTTP JSON API and web page for one in-memory Nano-Commons testbed.

This is the control surface of *your own* node or testbed, in the same way a daemon's
local RPC is. It is not a central server for the Nano-Commons network. The network has
no official server, and running this as a shared public service would make its operator
a central point of control, which the Governance Charter forbids.

All state lives in memory and is lost when the process stops. Every GET is public and
read-only. Every POST needs ``Authorization: Bearer <operator token>``; the token only
lets the machine's operator control this console. Hosted missions (the console signs for
you) are for testing only: their private keys stay inside this process and are never
returned by any endpoint. Real missions sign on the owner's machine (``keygen`` /
``submit``). The canary endpoint simulates a verifier for testbed use; on a real
network, canaries come from independent verifiers.
"""

from __future__ import annotations

import copy
import hmac
import ipaddress
import json
import math
import os
import re
import secrets
import socket
import socketserver
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .nano_agent import (
    build_packet,
    generate_keypair,
    packet_from_dict,
    public_key_from_b64,
    public_key_to_b64,
    sign_packet,
)
from .node_runner import NanoCommonsMesh, NodeState

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8700
DEFAULT_NETWORK_ID = "nano-commons-testbed"
MAX_BODY_BYTES = 64 * 1024
MAX_NAME_LENGTH = 128
MAX_WORKERS = 100
_DRAIN_LIMIT = 1 << 20          # bytes of a refused body we read so the client sees our reply
_WEB_DIR = Path(__file__).with_name("web")

_CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Mission:
    mission_id: str
    public_key: str                              # base64
    private_key: Optional[Ed25519PrivateKey] = None   # hosted missions only; never serialised

    @property
    def hosted(self) -> bool:
        return self.private_key is not None

    def to_dict(self) -> Dict[str, Any]:
        return {"mission_id": self.mission_id, "public_key": self.public_key, "hosted": self.hosted}


# --- request field validation --------------------------------------------------


def _bad(message: str) -> ApiError:
    return ApiError(400, message)


def _name(body: Dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value or len(value) > MAX_NAME_LENGTH or not value.isprintable():
        raise _bad(f"{key} must be a printable string of 1-{MAX_NAME_LENGTH} characters")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _bad(f"{label} must be a number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise _bad(f"{label} must be a finite number")
    return value


def _int(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise _bad(f"{label} must be an integer between {low} and {high}")
    return value


def _flag(body: Dict[str, Any], key: str, default: bool) -> bool:
    value = body.get(key, default)
    if not isinstance(value, bool):
        raise _bad(f"{key} must be true or false")
    return value


def _workers(body: Dict[str, Any]) -> List[str]:
    workers = body.get("workers")
    if (not isinstance(workers, list) or not workers or len(workers) > MAX_WORKERS
            or not all(isinstance(w, str) for w in workers)):
        raise _bad(f"workers must be a list of 1-{MAX_WORKERS} node id strings")
    return workers


def _hop_cost(body: Dict[str, Any]) -> int:
    return _int(body.get("hop_energy_cost", 15), "hop_energy_cost", 0, 1_000_000)


def _observation(raw: Any) -> Dict[str, Any]:
    """Task input from a client: ``value`` is required, ``threshold`` optional."""
    if not isinstance(raw, dict) or "value" not in raw:
        raise _bad("observation must be an object with a numeric 'value' (and optional 'threshold')")
    obs = {"value": _number(raw["value"], "observation.value")}
    if raw.get("threshold") is not None:
        obs["threshold"] = _number(raw["threshold"], "observation.threshold")
    return obs


def _shard_id(body: Dict[str, Any]) -> Optional[str]:
    return _name(body, "shard_id") if body.get("shard_id") is not None else None


# --- application state ---------------------------------------------------------


class NanoCommonsApp:
    """One mesh and its missions behind a single lock. Transport-free, so it is easy to test."""

    def __init__(self, network_id: str = DEFAULT_NETWORK_ID, **mesh_kwargs: Any):
        self.mesh = NanoCommonsMesh(network_id=network_id, **mesh_kwargs)
        self.missions: Dict[str, Mission] = {}
        self.lock = threading.Lock()
        self._get_routes: Dict[str, Callable[[], Any]] = {
            "/api/status": self.status,
            "/api/nodes": self.list_nodes,
            "/api/missions": self.list_missions,
            "/api/checkpoints": self.list_checkpoints,
            "/api/faults": self.faults,
            "/api/alarms": self.alarms,
            "/api/held": self.held,
        }
        self._post_routes: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "/api/nodes": self.add_node,
            "/api/missions": self.add_mission,
            "/api/tasks": self.run_task,
            "/api/canaries": self.run_canary,
            "/api/packets": self.submit_packet,
            "/api/rollback": self.rollback,
        }

    def handle(self, method: str, path: str, body: Dict[str, Any]) -> Tuple[int, Any]:
        """Dispatch one request. Raises ApiError; other errors are mapped by the caller."""
        with self.lock:
            if method == "GET":
                route = self._get_routes.get(path)
                if route is not None:
                    # Copy while the lock is held: replies must not alias live mesh state,
                    # which another request may change while this one is serialised.
                    return 200, copy.deepcopy(route())
            else:
                route = self._post_routes.get(path)
                if route is not None:
                    return 200, copy.deepcopy(route(body))
                match = re.fullmatch(r"/api/checkpoints/([^/]+)/review", path)
                if match:
                    return 200, copy.deepcopy(self.review(match.group(1)))
        raise ApiError(404, "not found")

    # --- reads

    def status(self) -> Dict[str, Any]:
        mesh = self.mesh
        head = mesh.checkpoints[-1]
        return {
            "network_id": mesh.network_id,
            "config": {
                "quorum_threshold": mesh.quorum_threshold,
                "zone_weight_cap": mesh.zone_weight_cap,
                "min_workers": mesh.min_workers,
                "host_max_ttl": mesh.host_max_ttl,
                "min_freshness": mesh.min_freshness,
            },
            "node_count": len(mesh.nodes),
            "mission_count": len(self.missions),
            "checkpoint_count": len(mesh.checkpoints) - 1,
            "head": {"checkpoint_id": head["checkpoint_id"], "hash": head["hash"]},
            "alarm_active": mesh.alarm_active,
            "canary_stats": mesh.canary_stats(),
            "last_trusted_checkpoint_id": mesh.last_trusted_checkpoint_id(),
            "suspect_checkpoint_ids": mesh.suspect_checkpoint_ids(),
            "tainted_checkpoint_ids": mesh.tainted_checkpoint_ids(),
        }

    def list_nodes(self) -> Dict[str, Any]:
        return {"nodes": [
            {
                "node_id": n.node_id,
                "zone": n.zone,
                "reputation": n.reputation,
                "compute_credits": n.compute_credits,
                "quarantined": n.quarantined,
                "verified_samples": n.verified_samples,
                "fault_count": n.fault_count,
                "canary_passed": n.canary_passed,
                "canary_failed": n.canary_failed,
                "simulated_malicious": n.is_malicious,
            }
            for n in self.mesh.nodes.values()
        ]}

    def list_missions(self) -> Dict[str, Any]:
        return {"missions": [m.to_dict() for m in self.missions.values()]}

    def list_checkpoints(self) -> Dict[str, Any]:
        return {
            "checkpoints": [
                {
                    "checkpoint_id": cp["checkpoint_id"],
                    "hash": cp["hash"],
                    "shard_id": cp.get("shard_id"),
                    "verified_verdict": cp["verified_verdict"],
                    "status": cp["status"],
                    "workers": dict(cp["workers"]),
                }
                for cp in self.mesh.checkpoints
            ],
            "last_trusted_checkpoint_id": self.mesh.last_trusted_checkpoint_id(),
        }

    def faults(self) -> Dict[str, Any]:
        return {"faults": [dict(f) for f in self.mesh.fault_log]}

    def alarms(self) -> Dict[str, Any]:
        mesh = self.mesh
        return {"active": mesh.canary_alarm, "history": mesh.alarm_history}

    def held(self) -> Dict[str, Any]:
        return {"held": list(self.mesh.held_results)}

    # --- writes

    def add_node(self, body: Dict[str, Any]) -> Dict[str, Any]:
        node_id, zone = _name(body, "node_id"), _name(body, "zone")
        reputation = _number(body.get("reputation", 0.15), "reputation")
        if not 0.0 <= reputation <= 1.0:
            raise _bad("reputation must be between 0 and 1")
        malicious = _flag(body, "simulate_malicious", False)
        if node_id in self.mesh.nodes:
            raise _bad(f"node {node_id!r} already exists")
        self.mesh.register_node(NodeState(node_id, zone, float(reputation), is_malicious=malicious))
        return {"node_id": node_id, "zone": zone, "reputation": self.mesh.nodes[node_id].reputation}

    def add_mission(self, body: Dict[str, Any]) -> Dict[str, Any]:
        mission_id = _name(body, "mission_id")
        if mission_id in self.missions:
            raise _bad(f"mission {mission_id!r} already exists")
        supplied = body.get("public_key")
        if supplied is None:
            private_key, public_key = generate_keypair()
            mission = Mission(mission_id, public_key_to_b64(public_key), private_key)
        else:
            try:
                public_key = public_key_from_b64(supplied)
            except ValueError as exc:
                raise _bad(str(exc)) from None
            mission = Mission(mission_id, public_key_to_b64(public_key))
        self.mesh.register_mission_key(mission_id, public_key)
        self.missions[mission_id] = mission
        return mission.to_dict()

    def _hosted_mission(self, body: Dict[str, Any]) -> Mission:
        mission_id = _name(body, "mission_id")
        mission = self.missions.get(mission_id)
        if mission is None:
            raise ApiError(404, f"unknown mission {mission_id!r}")
        if not mission.hosted:
            raise _bad(f"mission {mission_id!r} is external: sign the packet yourself "
                       "and send it to /api/packets")
        return mission

    def _signed_packet(self, mission: Mission, observation: Dict[str, Any], workers: List[str],
                       body: Dict[str, Any]):
        packet = build_packet(
            network_id=self.mesh.network_id,
            mission_id=mission.mission_id,
            parent_checkpoint_hash=self.mesh.checkpoints[-1]["hash"],
            observation=observation,
            shard_id=_shard_id(body),
            assigned_workers=workers if _flag(body, "bind_workers", True) else None,
        )
        return sign_packet(packet, mission.private_key)

    def run_task(self, body: Dict[str, Any]) -> Dict[str, Any]:
        mission = self._hosted_mission(body)
        observation = _observation(body.get("observation"))
        workers, cost = _workers(body), _hop_cost(body)
        packet = self._signed_packet(mission, observation, workers, body)
        return self.mesh.execute_k_node_verification(packet, observation, workers, cost)

    def run_canary(self, body: Dict[str, Any]) -> Dict[str, Any]:
        mission = self._hosted_mission(body)
        observation = _observation(body.get("observation"))
        expected = body.get("expected_verdict")
        if expected not in ("ANOMALY", "NORMAL"):
            raise _bad("expected_verdict must be ANOMALY or NORMAL")
        workers, cost = _workers(body), _hop_cost(body)
        packet = self._signed_packet(mission, observation, workers, body)
        digest = self.mesh.register_canary(packet, expected)
        try:
            return self.mesh.execute_k_node_verification(packet, observation, workers, cost)
        finally:
            # A scored canary is already consumed. If the mesh refused the packet before
            # scoring (unknown_worker, ...), drop the registration so it cannot pile up.
            self.mesh.unregister_canary(digest)

    def submit_packet(self, body: Dict[str, Any]) -> Dict[str, Any]:
        packet = packet_from_dict(body.get("packet"))
        observation = body.get("observation")
        if not isinstance(observation, dict):
            raise _bad("observation must be an object")
        return self.mesh.execute_k_node_verification(packet, observation, _workers(body), _hop_cost(body))

    def rollback(self, body: Dict[str, Any]) -> Dict[str, Any]:
        checkpoint_id = _int(body.get("checkpoint_id"), "checkpoint_id", 0, 10 ** 9)
        result = self.mesh.rollback_to_checkpoint(checkpoint_id)
        if not result["rolled_back"]:
            raise _bad(f"no checkpoint with id {checkpoint_id}")
        return {"rolled_back": True, "head_checkpoint_id": self.mesh.checkpoints[-1]["checkpoint_id"],
                "head_hash": self.mesh.checkpoints[-1]["hash"]}

    def review(self, raw_id: str) -> Dict[str, Any]:
        if not re.fullmatch(r"[0-9]{1,9}", raw_id):
            raise _bad("checkpoint id must be a non-negative integer")
        checkpoint_id = int(raw_id)
        if not self.mesh.mark_reviewed(checkpoint_id):
            raise ApiError(404, f"checkpoint {checkpoint_id} not found or not reviewable")
        return {"checkpoint_id": checkpoint_id, "status": self.mesh.checkpoints[checkpoint_id]["status"]}


# --- HTTP layer ----------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    server_version = "NanoCommons/0.2"
    _responded = False
    timeout = 15   # per-recv stall limit; a client trickling bytes can still hold a thread longer

    def log_message(self, format: str, *args: Any) -> None:   # noqa: A002 - stdlib signature
        pass  # quiet by default; the request line can carry ?token=

    # -- helpers

    def _send(self, status: int, payload: Any = None, *, body: Optional[bytes] = None,
              content_type: str = "application/json; charset=utf-8") -> None:
        if body is None:
            body = json.dumps(payload).encode("utf-8")
        self._responded = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", _CSP)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        if self._responded:   # headers already went out; a second response would corrupt the stream
            return
        self._send(status, {"error": message})

    def _authorized(self) -> bool:
        scheme, _, supplied = self.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not supplied.strip():
            return False
        return hmac.compare_digest(supplied.strip().encode("utf-8"), self.server.token.encode("utf-8"))

    def _declared_length(self) -> Optional[int]:
        """Content-Length as an int (ASCII digits only), 0 if absent, None if invalid."""
        raw = self.headers.get("Content-Length", "0").strip()
        return int(raw) if re.fullmatch(r"[0-9]{1,12}", raw) else None

    def _drain(self, length: int) -> None:
        """Read (a bounded amount of) a body we are refusing, so the client can read our reply."""
        try:
            self.connection.settimeout(1.0)
            remaining = min(length, _DRAIN_LIMIT)
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass

    def _read_body(self) -> Optional[Dict[str, Any]]:
        """Parsed JSON object body (empty body = {}), or None after an error reply was sent."""
        length = self._declared_length()
        if length is None:
            self._error(400, "invalid Content-Length")
            return None
        if length > MAX_BODY_BYTES:
            self._drain(length)
            self._error(413, f"request body too large (limit {MAX_BODY_BYTES} bytes)")
            return None
        data = self.rfile.read(length) if length else b""
        if not data.strip():
            return {}
        try:
            body = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            self._error(400, "body is not valid JSON")
            return None
        if not isinstance(body, dict):
            self._error(400, "body must be a JSON object")
            return None
        return body

    def _dispatch(self, method: str) -> None:
        path = urlsplit(self.path).path
        self._responded = False
        try:
            if method == "GET" or method == "HEAD":
                if path in ("/", "/index.html"):
                    return self._serve_page()
                if path == "/favicon.ico":
                    return self._send(204, body=b"")
                status, payload = self.server.app.handle("GET", path, {})
            else:
                if not self._authorized():
                    self._drain(self._declared_length() or 0)
                    return self._error(401, "missing or invalid operator token "
                                            "(send 'Authorization: Bearer <token>')")
                body = self._read_body()
                if body is None:
                    return
                status, payload = self.server.app.handle("POST", path, body)
            self._send(status, payload)
        except ApiError as exc:
            self._error(exc.status, exc.message)
        except (ConnectionError, TimeoutError):
            pass   # the client went away; nothing to answer
        except (ValueError, OverflowError, RecursionError) as exc:
            self._error(400, f"invalid input: {exc}" if isinstance(exc, ValueError) else "invalid input")
        except Exception as exc:  # never let a bad request take the server down
            print(f"nano-commons: internal error on {method} {path}: {exc!r}", file=sys.stderr)
            self._error(500, "internal server error")

    def _serve_page(self) -> None:
        try:
            page = (_WEB_DIR / "index.html").read_bytes()
        except OSError:
            return self._error(404, "web page not installed")
        self._send(200, body=page, content_type="text/html; charset=utf-8")

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_HEAD(self) -> None:
        self._dispatch("HEAD")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _method_not_allowed(self) -> None:
        self._responded = False  # per request, in case connections are ever kept alive
        self._error(405, "method not allowed")

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _method_not_allowed


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not allowed in JSON")


class NanoCommonsServer(ThreadingHTTPServer):
    daemon_threads = True
    token_generated = False

    def __init__(self, address: Tuple[str, int], app: NanoCommonsApp, token: str):
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        self.app = app
        self.token = token
        super().__init__(address, _Handler)

    def server_bind(self) -> None:
        # HTTPServer.server_bind does a reverse DNS lookup that can stall on some hosts.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    @property
    def port(self) -> int:
        return self.server_address[1]


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def bind_warning(host: str) -> Optional[str]:
    if is_loopback(host):
        return None
    return (f"WARNING: bound to {host}, which is reachable from other machines. The API is plain "
            "HTTP: the operator token and all traffic can be read on the network. Put it behind TLS "
            "(a reverse proxy) or use an SSH tunnel. This console is for your own node; do not run "
            "it as a shared public service for others, because that recreates the central point "
            "of control the protocol exists to avoid.")


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, token: Optional[str] = None,
                  network_id: str = DEFAULT_NETWORK_ID, **mesh_kwargs: Any) -> NanoCommonsServer:
    """Build (and bind) the server without starting it. ``port=0`` picks a free port."""
    configured = token or os.environ.get("NANO_TOKEN")
    app = NanoCommonsApp(network_id=network_id, **mesh_kwargs)
    server = NanoCommonsServer((host, port), app, configured or secrets.token_urlsafe(24))
    server.token_generated = not configured
    return server


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, token: Optional[str] = None,
          network_id: str = DEFAULT_NETWORK_ID, **mesh_kwargs: Any) -> None:
    """Run the server until interrupted. Prints the API URL and the page URL (with the token only if it was generated here)."""
    server = create_server(host, port, token, network_id, **mesh_kwargs)
    shown_host = {"0.0.0.0": "127.0.0.1", "": "127.0.0.1", "::": "::1"}.get(host, host).strip("[]")
    shown_host = f"[{shown_host}]" if ":" in shown_host else shown_host
    base = f"http://{shown_host}:{server.port}"
    warning = bind_warning(host)
    if warning:
        print(warning, file=sys.stderr)
    print(f"Nano-Commons local node console, network {network_id} (testbed, state is in memory only)")
    print("This console controls your own node only. There is no central Nano-Commons server.")
    print(f"API:        {base}/api/status")
    if server.token_generated:
        print(f"Open page:  {base}/?token={server.token}")
    else:
        print(f"Open page:  {base}/   (use your configured token)")
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()
