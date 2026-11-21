# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Krittidet Chanthake and the Nano-Commons contributors
"""Nano-Agent packet, Ed25519 signing, safety gate and the Observe-Think-Act-Reflect loop.

Signatures cover the packet as published by the mission owner (everything except
``signature``). Nodes verify a packet when it enters the mesh; per-hop re-signing of
forwarded clones is future work and is not modelled in v0.1.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

SIGNATURE_PREFIX = "ed25519:"


@dataclass
class NanoAgentPacket:
    protocol_version: str
    network_id: str
    agent_id: str
    mission_id: str
    shard_id: str
    generation: int
    ttl: int
    energy_budget: int
    freshness: float
    freshness_decay_rate: float
    parent_checkpoint_hash: str
    payload: Dict[str, Any]
    signature: str = ""

    def signing_bytes(self) -> bytes:
        """Canonical JSON of every field except ``signature``."""
        body = {
            "protocol_version": self.protocol_version,
            "network_id": self.network_id,
            "agent_id": self.agent_id,
            "mission_id": self.mission_id,
            "shard_id": self.shard_id,
            "generation": self.generation,
            "ttl": self.ttl,
            "energy_budget": self.energy_budget,
            "freshness": self.freshness,
            "freshness_decay_rate": self.freshness_decay_rate,
            "parent_checkpoint_hash": self.parent_checkpoint_hash,
            "payload": self.payload,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.signing_bytes()).hexdigest()

    def clone_for_next_hop(self, hop_energy_cost: int = 15) -> "NanoAgentPacket":
        next_freshness = max(0.0, self.freshness * (1.0 - self.freshness_decay_rate))
        return NanoAgentPacket(
            protocol_version=self.protocol_version,
            network_id=self.network_id,
            agent_id=self.agent_id,
            mission_id=self.mission_id,
            shard_id=self.shard_id,
            generation=self.generation + 1,
            ttl=self.ttl - 1,
            energy_budget=self.energy_budget - hop_energy_cost,
            freshness=next_freshness,
            freshness_decay_rate=self.freshness_decay_rate,
            parent_checkpoint_hash=self.parent_checkpoint_hash,
            payload=json.loads(json.dumps(self.payload)),
            signature=self.signature,
        )


# --- Ed25519 signing -------------------------------------------------------


def generate_keypair() -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def sign_packet(packet: NanoAgentPacket, private_key: Ed25519PrivateKey) -> NanoAgentPacket:
    """Sign ``packet`` in place and return it."""
    raw_sig = private_key.sign(packet.signing_bytes())
    packet.signature = SIGNATURE_PREFIX + base64.b64encode(raw_sig).decode("ascii")
    return packet


def verify_packet_signature(packet: NanoAgentPacket, public_key: Optional[Ed25519PublicKey]) -> bool:
    if public_key is None or not isinstance(packet.signature, str):
        return False
    if not packet.signature.startswith(SIGNATURE_PREFIX):
        return False
    try:
        raw_sig = base64.b64decode(packet.signature[len(SIGNATURE_PREFIX):], validate=True)
        public_key.verify(raw_sig, packet.signing_bytes())
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


# --- Key serialisation -------------------------------------------------------
# Raw 32-byte Ed25519 keys, standard base64. Safe to paste into a CLI or a JSON body.


def public_key_to_b64(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def public_key_from_b64(text: str) -> Ed25519PublicKey:
    """Raises ValueError unless ``text`` is base64 of exactly 32 bytes."""
    return Ed25519PublicKey.from_public_bytes(_decode_key(text, "public key"))


def private_key_to_b64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return base64.b64encode(raw).decode("ascii")


def private_key_from_b64(text: str) -> Ed25519PrivateKey:
    """Raises ValueError unless ``text`` is base64 of exactly 32 bytes."""
    return Ed25519PrivateKey.from_private_bytes(_decode_key(text, "private key"))


def _decode_key(text: Any, what: str) -> bytes:
    if not isinstance(text, str):
        raise ValueError(f"{what} must be a base64 string")
    try:
        raw = base64.b64decode(text.strip(), validate=True)
    except ValueError:
        raise ValueError(f"{what} is not valid base64") from None
    if len(raw) != 32:
        raise ValueError(f"{what} must decode to 32 bytes")
    return raw


# --- Safety gate -------------------------------------------------------------

_INT_FIELDS = ("generation", "ttl", "energy_budget")
_FLOAT_FIELDS = ("freshness", "freshness_decay_rate")
_STR_FIELDS = (
    "protocol_version", "network_id", "agent_id", "mission_id",
    "shard_id", "parent_checkpoint_hash", "signature",
)


MAX_SAFE_INTEGER = 2 ** 53  # largest integer every JSON implementation represents exactly


def _is_number(value: Any) -> bool:
    """Finite float, or an integer within +/- 2**53 (huge ints would overflow float())."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return abs(value) <= MAX_SAFE_INTEGER
    return isinstance(value, float) and math.isfinite(value)


def _is_canonical_json(value: Any) -> bool:
    """Only values with exactly one canonical JSON encoding (str keys, finite numbers)."""
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, (int, float)):
        return _is_number(value)
    if isinstance(value, list):
        return all(_is_canonical_json(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_canonical_json(v) for k, v in value.items())
    return False


def _is_valid_payload(payload: Any) -> bool:
    if not isinstance(payload, dict) or not _is_canonical_json(payload):
        return False
    if "bias" in payload and not _is_number(payload["bias"]):
        return False
    if "observation_hash" in payload and not isinstance(payload["observation_hash"], str):
        return False
    if "assigned_workers" in payload:
        assigned = payload["assigned_workers"]
        if not isinstance(assigned, list) or not all(isinstance(w, str) for w in assigned):
            return False
    memory = payload.get("memory_window", [])
    if not isinstance(memory, list) or not all(_is_number(m) for m in memory):
        return False
    clock = payload.get("crdt_clock", {})
    if not isinstance(clock, dict):
        return False
    return all(isinstance(c, int) and not isinstance(c, bool) and c >= 0 for c in clock.values())


def _is_well_formed(packet: NanoAgentPacket) -> bool:
    for name in _INT_FIELDS:
        value = getattr(packet, name)
        if not isinstance(value, int) or isinstance(value, bool):
            return False
    if not all(_is_number(getattr(packet, name)) for name in _FLOAT_FIELDS):
        return False
    if not all(isinstance(getattr(packet, name), str) for name in _STR_FIELDS):
        return False
    if not _is_valid_payload(packet.payload):
        return False
    return 0.0 <= packet.freshness <= 1.0 and 0.0 <= packet.freshness_decay_rate <= 1.0


def can_execute_or_forward(
    packet: NanoAgentPacket,
    expected_network_id: str,
    mission_keys: Mapping[str, Ed25519PublicKey],
    host_max_ttl: int = 10,
    hop_energy_cost: int = 0,
    min_freshness: float = 0.0,
) -> Tuple[bool, str]:
    """Return (ok, reason). Cheap checks first, signature last."""
    if not _is_well_formed(packet):
        return False, "malformed_schema"
    if packet.network_id != expected_network_id:
        return False, "network_id_mismatch"
    if packet.ttl <= 0 or packet.ttl > host_max_ttl:
        return False, "invalid_or_exhausted_ttl"
    if packet.energy_budget <= 0 or packet.energy_budget < hop_energy_cost:
        return False, "exhausted_energy_budget"
    if packet.freshness < min_freshness:
        return False, "stale_knowledge"
    public_key = mission_keys.get(packet.mission_id)
    if public_key is None:
        return False, "unknown_mission"
    if not verify_packet_signature(packet, public_key):
        return False, "invalid_signature"
    return True, "ok"


def observation_digest(observation: Dict[str, Any]) -> str:
    """Hash the task input. Packets commit to it in ``payload["observation_hash"]``
    so the input cannot be swapped after signing. Raises ValueError if the
    observation has no single canonical JSON form."""
    if not isinstance(observation, dict) or not _is_canonical_json(observation):
        raise ValueError("observation must be a JSON object with str keys and finite numbers")
    for key in ("value", "threshold"):
        if key in observation and not _is_number(observation[key]):
            raise ValueError(f"observation[{key!r}] must be a finite number")
    raw = json.dumps(observation, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# --- Building and (de)serialising packets -----------------------------------


def build_packet(
    *,
    network_id: str,
    mission_id: str,
    parent_checkpoint_hash: str,
    observation: Dict[str, Any],
    shard_id: Optional[str] = None,
    assigned_workers: Optional[Sequence[str]] = None,
    agent_id: str = "nano-agent-0001",
    ttl: int = 4,
    energy_budget: int = 100,
    freshness: float = 1.0,
    freshness_decay_rate: float = 0.05,
    bias: float = 0.0,
) -> NanoAgentPacket:
    """Unsigned packet that commits to ``observation`` via ``payload["observation_hash"]``.

    Pass the current checkpoint head as ``parent_checkpoint_hash`` and sign the result
    with ``sign_packet``. ``assigned_workers`` binds the worker set under the signature.
    Raises ValueError if the observation has no canonical JSON form.
    """
    payload: Dict[str, Any] = {
        "bias": bias,
        "memory_window": [],
        "crdt_clock": {},
        "observation_hash": observation_digest(observation),
    }
    if assigned_workers is not None:
        payload["assigned_workers"] = list(assigned_workers)
    return NanoAgentPacket(
        protocol_version="0.1",
        network_id=network_id,
        agent_id=agent_id,
        mission_id=mission_id,
        shard_id=shard_id if shard_id is not None else "shard-" + uuid.uuid4().hex[:12],
        generation=1,
        ttl=ttl,
        energy_budget=energy_budget,
        freshness=freshness,
        freshness_decay_rate=freshness_decay_rate,
        parent_checkpoint_hash=parent_checkpoint_hash,
        payload=payload,
    )


def packet_to_dict(packet: NanoAgentPacket) -> Dict[str, Any]:
    """JSON-safe copy of ``packet`` (including its signature)."""
    return asdict(packet)


def packet_from_dict(data: Any) -> NanoAgentPacket:
    """Inverse of ``packet_to_dict``. Raises ValueError on missing fields or wrong types.

    Only shape is checked here; the safety gate still decides whether the packet is valid.
    """
    if not isinstance(data, Mapping):
        raise ValueError("packet must be a JSON object")
    required = _STR_FIELDS[:-1] + _INT_FIELDS + _FLOAT_FIELDS + ("payload",)
    missing = [name for name in required if name not in data]
    if missing:
        raise ValueError("packet is missing field(s): " + ", ".join(missing))
    for name in _STR_FIELDS[:-1]:
        if not isinstance(data[name], str):
            raise ValueError(f"packet field {name!r} must be a string")
    for name in _INT_FIELDS:
        if not isinstance(data[name], int) or isinstance(data[name], bool):
            raise ValueError(f"packet field {name!r} must be an integer")
    for name in _FLOAT_FIELDS:
        value = data[name]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"packet field {name!r} must be a number")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"packet field {name!r} must be a finite number")
    if not isinstance(data["payload"], dict):
        raise ValueError("packet field 'payload' must be an object")
    signature = data.get("signature", "")
    if not isinstance(signature, str):
        raise ValueError("packet field 'signature' must be a string")
    fields = {name: data[name] for name in required}
    fields["payload"] = json.loads(json.dumps(data["payload"]))  # detach from caller's dict
    return NanoAgentPacket(signature=signature, **fields)


# --- CRDT helpers ------------------------------------------------------------


def merge_g_counters(*clocks: Mapping[str, int]) -> Dict[str, int]:
    """G-Counter merge: element-wise max. Commutative, associative, idempotent."""
    merged: Dict[str, int] = {}
    for clock in clocks:
        for node_id, count in clock.items():
            merged[node_id] = max(merged.get(node_id, 0), count)
    return merged


# --- Agent loop --------------------------------------------------------------


def run_observe_think_act_reflect(
    packet: NanoAgentPacket,
    observation: Dict[str, Any],
    node_id: str,
    is_malicious: bool = False,
) -> Dict[str, Any]:
    """Run one loop on ``packet`` (mutates its payload).

    ``is_malicious`` only simulates a poisoning node's behaviour for the testbed;
    the mesh never reads it when scoring nodes.
    """
    # 1. OBSERVE: read local sensor/task input (privacy-filtered summary)
    reading = float(observation.get("value", 0.0))
    threshold = float(observation.get("threshold", 50.0))

    # 2. THINK: apply the agent's policy bias; freshness is reported for audit
    bias = float(packet.payload.get("bias", 0.0))
    adjusted = reading + bias
    effective_score = adjusted * packet.freshness

    # 3. ACT: classify anomaly (inverted if the simulated node is poisoning)
    is_anomaly = adjusted >= threshold
    if is_malicious:
        is_anomaly = not is_anomaly
    verdict = "ANOMALY" if is_anomaly else "NORMAL"

    # 4. REFLECT: update bounded memory window & G-Counter clock
    memory = list(packet.payload.get("memory_window", []))
    memory.append(round(reading, 2))
    packet.payload["memory_window"] = memory[-5:]

    clock = dict(packet.payload.get("crdt_clock", {}))
    clock[node_id] = clock.get(node_id, 0) + 1
    packet.payload["crdt_clock"] = clock

    return {
        "node_id": node_id,
        "shard_id": packet.shard_id,
        "verdict": verdict,
        "effective_score": round(effective_score, 4),
        "freshness_used": round(packet.freshness, 4),
        "ttl_remaining": packet.ttl,
        "energy_remaining": packet.energy_budget,
        "crdt_clock": clock,
    }
