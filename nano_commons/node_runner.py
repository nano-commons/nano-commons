# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Krittidet Chanthake and the Nano-Commons contributors
"""Local multi-node testbed: K-node weighted consensus, canary tasks, reputation, checkpoints."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .nano_agent import (
    NanoAgentPacket,
    can_execute_or_forward,
    merge_g_counters,
    observation_digest,
    run_observe_think_act_reflect,
)

GENESIS_CHECKPOINT_HASH = "sha256:genesis_checkpoint_0000"
VERDICTS = ("ANOMALY", "NORMAL")

# Checkpoint audit status.
UNVERIFIED = "unverified"   # no canary has tested the workers that produced it yet
VOUCHED = "vouched"         # its producers, at their weights then, answered a canary correctly
TAINTED = "tainted"         # its producers, at their weights then, got a canary wrong (sticky)
REVIEWED = "reviewed"       # vouched by an operator; the automatic audit no longer touches it
TRUSTED = (VOUCHED, REVIEWED)

REWARD_REPUTATION = 0.04
REWARD_CREDITS = 10.0
FIRST_FAULT_PENALTY = 0.06    # first wrong answer (vs consensus or canary truth)
REPEAT_FAULT_PENALTY = 0.18   # repeated wrong answers: treated as confirmed poisoning
QUARANTINE_THRESHOLD = 0.10
_EPS = 1e-12


@dataclass
class NodeState:
    node_id: str
    zone: str
    reputation: float = 0.15
    compute_credits: float = 0.0
    quarantined: bool = False
    # Simulation only: makes the node poison its votes. The mesh never reads it.
    is_malicious: bool = False
    verified_samples: int = 0
    fault_count: int = 0
    canary_passed: int = 0
    canary_failed: int = 0
    local_checkpoints: List[str] = field(default_factory=list)

    def clamp_reputation(self) -> None:
        self.reputation = max(0.0, min(1.0, round(self.reputation, 4)))
        self.quarantined = self.reputation < QUARANTINE_THRESHOLD


def water_fill_shares(shares: Dict[str, float], cap: float) -> Dict[str, float]:
    """Scale ``shares`` to sum to 1 with no entry above ``cap``.

    Excess above the cap is redistributed proportionally to the remaining entries.
    If every entry hits the cap (fewer than 1/cap entries), the leftover stays
    unassigned, so the result can sum to less than 1.
    """
    result: Dict[str, float] = {key: 0.0 for key in shares}
    remaining = {key: value for key, value in shares.items() if value > 0}
    budget = 1.0
    while remaining:
        sub_total = sum(remaining.values())
        scaled = {key: value / sub_total * budget for key, value in remaining.items()}
        over = [key for key, value in scaled.items() if value > cap + _EPS]
        if not over:
            result.update(scaled)
            break
        for key in over:
            result[key] = cap
            budget -= cap
            del remaining[key]
    return result


def zone_capped_weights(nodes: Iterable[NodeState], zone_cap: float) -> Dict[str, float]:
    """Vote weight per node: reputation-proportional, each zone capped at ``zone_cap``.

    Quarantined nodes get zero weight. Weights sum to at most 1.0.
    """
    nodes = list(nodes)
    raw = {n.node_id: (0.0 if n.quarantined else n.reputation) for n in nodes}
    zone_raw: Dict[str, float] = {}
    for n in nodes:
        zone_raw[n.zone] = zone_raw.get(n.zone, 0.0) + raw[n.node_id]
    total = sum(zone_raw.values())
    if total <= 0:
        return {n.node_id: 0.0 for n in nodes}
    zone_share = water_fill_shares({z: r / total for z, r in zone_raw.items()}, zone_cap)
    weights: Dict[str, float] = {}
    for n in nodes:
        zr = zone_raw[n.zone]
        weights[n.node_id] = zone_share[n.zone] * raw[n.node_id] / zr if zr > 0 else 0.0
    return weights


def _wrong_fraction(weights: Dict[str, float], answers: Dict[str, str], expected: str) -> float:
    """Share of ``weights`` whose answer differs from ``expected``. Zero total fails closed (1.0)."""
    total = sum(weights.values())
    if total <= 0:
        return 1.0
    return sum(w for nid, w in weights.items() if answers[nid] != expected) / total


class NanoCommonsMesh:
    """In-process mesh.

    Canary tasks: a canary is an ordinary signed packet whose correct verdict the
    mesh learns in advance through ``register_canary``. Packets carry no canary
    marker, and ordinary tasks keep reaching workers during an alarm, so the
    packet stream gives workers no way to single canaries out. Each worker is
    scored against the known answer, not the majority.

    Every checkpoint records the workers that produced it and their weights. A
    canary audits each checkpoint whose producers all took part: if those
    producers, at their weights then, would have got the canary wrong, the
    checkpoint is tainted (sticky); otherwise an unverified checkpoint becomes
    vouched. A canary that most of its own weight gets wrong raises a mesh alarm.
    While it is up, ordinary results are held: no scoring, no checkpoint. The alarm
    clears only when the workers recorded in it, weighted among themselves at
    their current reputation, answer a canary correctly.

    Signers can bind the worker set with ``payload["assigned_workers"]`` so that
    whoever submits a packet cannot pick a friendlier set of workers.
    """

    def __init__(
        self,
        network_id: str = "nano-commons-mainnet-v0.1",
        quorum_threshold: float = 0.65,
        zone_weight_cap: float = 0.50,
        min_workers: int = 3,
        host_max_ttl: int = 10,
        min_freshness: float = 0.0,
    ):
        # A quorum at or below 0.5 would let a 50/50 tie be accepted.
        if not 0.5 < quorum_threshold <= 1.0:
            raise ValueError("quorum_threshold must be in (0.5, 1.0]")
        if not 0.0 < zone_weight_cap <= 1.0:
            raise ValueError("zone_weight_cap must be in (0.0, 1.0]")
        if min_workers < 1:
            raise ValueError("min_workers must be >= 1")
        self.network_id = network_id
        self.quorum_threshold = quorum_threshold
        self.zone_weight_cap = zone_weight_cap
        self.min_workers = min_workers
        self.host_max_ttl = host_max_ttl
        self.min_freshness = min_freshness
        self.nodes: Dict[str, NodeState] = {}
        self.mission_keys: Dict[str, Ed25519PublicKey] = {}
        self.active_leases: Dict[str, str] = {}
        self.fault_log: List[Dict[str, Any]] = []
        self.processed_digests: set = set()
        self.checkpoints: List[Dict[str, Any]] = [
            {"checkpoint_id": 0, "hash": GENESIS_CHECKPOINT_HASH, "verified_verdict": None,
             "workers": {}, "status": VOUCHED}
        ]
        # Canary state. The answer key is private to the mesh (the verifier side).
        self._canaries: Dict[str, Dict[str, str]] = {}   # digest -> {"expected", "parent"}
        self.canary_alarm: Optional[Dict[str, Any]] = None
        self.alarm_history: List[Dict[str, Any]] = []
        self.held_results: List[Dict[str, Any]] = []
        self.canary_rounds = 0
        self.canary_consensus_correct = 0

    # --- registration & leases ------------------------------------------------

    def register_mission_key(self, mission_id: str, public_key: Ed25519PublicKey) -> None:
        self.mission_keys[mission_id] = public_key

    def register_node(self, node: NodeState) -> None:
        node.clamp_reputation()
        self.nodes[node.node_id] = node

    def claim_shard(self, node_id: str, shard_id: str) -> bool:
        holder = self.active_leases.get(shard_id)
        if holder is None:
            self.active_leases[shard_id] = node_id
            return True
        return holder == node_id

    def release_shard(self, node_id: str, shard_id: str) -> bool:
        if self.active_leases.get(shard_id) == node_id:
            del self.active_leases[shard_id]
            return True
        return False

    # --- canaries & audit -------------------------------------------------------

    def register_canary(self, packet: NanoAgentPacket, expected_verdict: str) -> str:
        """Record the known answer for ``packet``; return its digest.

        Register before submitting. The packet must extend the current head; the
        entry is dropped automatically if the head moves before it is submitted.
        """
        if expected_verdict not in VERDICTS:
            raise ValueError(f"expected_verdict must be one of {VERDICTS}")
        if packet.parent_checkpoint_hash != self.checkpoints[-1]["hash"]:
            raise ValueError("canary must extend the current checkpoint head")
        digest = packet.digest()
        if digest in self.processed_digests or digest in self._canaries:
            raise ValueError("packet already processed or registered as a canary")
        self._canaries[digest] = {"expected": expected_verdict, "parent": packet.parent_checkpoint_hash}
        return digest

    def unregister_canary(self, digest: str) -> bool:
        """Drop a canary registration that was never scored. Returns True if one was removed."""
        return self._canaries.pop(digest, None) is not None

    def _prune_canaries(self) -> None:
        head = self.checkpoints[-1]["hash"]
        self._canaries = {d: c for d, c in self._canaries.items() if c["parent"] == head}

    @property
    def alarm_active(self) -> bool:
        return self.canary_alarm is not None

    def suspect_checkpoint_ids(self) -> List[int]:
        """Checkpoints neither vouched by a canary nor reviewed by an operator."""
        return [cp["checkpoint_id"] for cp in self.checkpoints if cp["status"] not in TRUSTED]

    def tainted_checkpoint_ids(self) -> List[int]:
        return [cp["checkpoint_id"] for cp in self.checkpoints if cp["status"] == TAINTED]

    def last_trusted_checkpoint_id(self) -> int:
        """Highest id such that it and every checkpoint before it are vouched or reviewed."""
        trusted = 0
        for cp in self.checkpoints[1:]:
            if cp["status"] not in TRUSTED:
                break
            trusted = cp["checkpoint_id"]
        return trusted

    def mark_reviewed(self, checkpoint_id: int) -> bool:
        """Operator override after manual review. Later canaries do not change it."""
        if not 0 < checkpoint_id < len(self.checkpoints):
            return False
        self.checkpoints[checkpoint_id]["status"] = REVIEWED
        return True

    def canary_stats(self) -> Dict[str, Any]:
        rounds = self.canary_rounds
        return {
            "rounds": rounds,
            "consensus_correct": self.canary_consensus_correct,
            "consensus_accuracy": round(self.canary_consensus_correct / rounds, 4) if rounds else None,
            "alarm_active": self.alarm_active,
        }

    # --- scoring helpers ------------------------------------------------------

    def _reject(self, packet: NanoAgentPacket, reason: str) -> Dict[str, Any]:
        return {"accepted": False, "reason": reason, "shard_id": packet.shard_id}

    def _reward(self, node: NodeState, weight: float) -> None:
        node.reputation += REWARD_REPUTATION
        node.verified_samples += 1
        if weight > 0:  # zero-weight (quarantined) votes earn no credits
            node.compute_credits += REWARD_CREDITS

    def _penalize(
        self, node: NodeState, packet: NanoAgentPacket, digest: str, submitted: str, reference: str, kind: str
    ) -> str:
        repeat = node.fault_count > 0
        node.fault_count += 1
        node.reputation -= REPEAT_FAULT_PENALTY if repeat else FIRST_FAULT_PENALTY
        entry = {
            "node_id": node.node_id,
            "shard_id": packet.shard_id,
            "packet_digest": digest,
            "kind": kind,              # "consensus" or "canary"
            "submitted": submitted,
            "reference": reference,    # the consensus verdict, or the canary's known answer
            "fault_number": node.fault_count,
        }
        entry["fault_hash"] = "sha256:" + hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode("utf-8")
        ).hexdigest()
        self.fault_log.append(entry)
        return entry["fault_hash"]

    # --- consensus ------------------------------------------------------------

    def execute_k_node_verification(
        self,
        packet: NanoAgentPacket,
        observation: Dict[str, Any],
        worker_ids: List[str],
        hop_energy_cost: int = 15,
    ) -> Dict[str, Any]:
        if len(set(worker_ids)) != len(worker_ids):
            return self._reject(packet, "duplicate_worker")
        if any(wid not in self.nodes for wid in worker_ids):
            return self._reject(packet, "unknown_worker")
        active = [wid for wid in worker_ids if not self.nodes[wid].quarantined]
        if len(active) < self.min_workers:
            return self._reject(packet, "insufficient_workers")

        ok, reason = can_execute_or_forward(
            packet,
            self.network_id,
            self.mission_keys,
            host_max_ttl=self.host_max_ttl,
            hop_energy_cost=hop_energy_cost,
            min_freshness=self.min_freshness,
        )
        if not ok:
            return self._reject(packet, reason)
        # Checked after the signature so unauthenticated packets cannot probe mesh state.
        try:
            obs_hash = observation_digest(observation)
        except ValueError:
            return self._reject(packet, "malformed_observation")
        if packet.payload.get("observation_hash") != obs_hash:
            return self._reject(packet, "observation_mismatch")
        # Optional binding: if the signer named the workers, nobody else may choose them.
        assigned = packet.payload.get("assigned_workers")
        if assigned is not None and sorted(assigned) != sorted(worker_ids):
            return self._reject(packet, "worker_set_mismatch")
        if packet.parent_checkpoint_hash != self.checkpoints[-1]["hash"]:
            return self._reject(packet, "stale_parent_checkpoint")
        packet_digest = packet.digest()
        if packet_digest in self.processed_digests:
            return self._reject(packet, "replayed_packet")
        self.processed_digests.add(packet_digest)
        canary = self._canaries.pop(packet_digest, None)

        workers = [self.nodes[wid] for wid in worker_ids]
        weights = zone_capped_weights(workers, self.zone_weight_cap)

        votes: List[Dict[str, Any]] = []
        for node in workers:
            hop = packet.clone_for_next_hop(hop_energy_cost=hop_energy_cost)
            vote = run_observe_think_act_reflect(
                hop, observation=observation, node_id=node.node_id, is_malicious=node.is_malicious
            )
            vote["weight"] = round(weights[node.node_id], 6)
            votes.append(vote)

        verdict_scores: Dict[str, float] = {}
        for vote in votes:
            verdict_scores[vote["verdict"]] = verdict_scores.get(vote["verdict"], 0.0) + weights[vote["node_id"]]
        # Highest score wins; ties broken alphabetically so the outcome is deterministic.
        winning_verdict, winning_share = min(verdict_scores.items(), key=lambda kv: (-kv[1], kv[0]))
        merged_clock = merge_g_counters(
            packet.payload.get("crdt_clock", {}), *(vote["crdt_clock"] for vote in votes)
        )
        common = {
            "shard_id": packet.shard_id,
            "winning_verdict": winning_verdict,
            "winning_share": round(winning_share, 4),
            "quorum_threshold": self.quorum_threshold,
            "merged_crdt_clock": merged_clock,
            "votes": votes,
        }

        if canary is not None:
            scored = self._score_canary(packet, packet_digest, canary["expected"], votes, workers, weights)
        elif self.alarm_active:
            scored = self._hold(packet_digest, winning_verdict, winning_share, worker_ids)
        else:
            scored = self._score_consensus(packet, packet_digest, winning_verdict, winning_share,
                                           votes, workers, weights)
        return {**common, **scored}

    def _hold(self, digest, winning_verdict, winning_share, worker_ids):
        # Workers did the job as usual, so an alarm does not reveal which packets are
        # canaries. The result is kept for review but not scored or checkpointed.
        self.held_results.append({
            "packet_digest": digest,
            "winning_verdict": winning_verdict,
            "winning_share": round(winning_share, 4),
            "workers": list(worker_ids),
        })
        return {
            "accepted": False,
            "reason": "held_alarm_active",
            "canary": False,
            "checkpoint_hash": None,
            "fault_hashes": {},
        }

    def _score_consensus(self, packet, digest, winning_verdict, winning_share, votes, workers, weights):
        quorum_met = winning_share + _EPS >= self.quorum_threshold
        fault_hashes: Dict[str, str] = {}
        if quorum_met:
            for vote, node in zip(votes, workers):
                if vote["verdict"] == winning_verdict:
                    self._reward(node, weights[node.node_id])
                else:
                    fault_hashes[node.node_id] = self._penalize(
                        node, packet, digest, vote["verdict"], winning_verdict, "consensus"
                    )
                node.clamp_reputation()
        # No quorum: no reward and no penalty, so an attacker splitting the vote
        # cannot push honest low-reputation nodes into quarantine.

        checkpoint_hash: Optional[str] = None
        if quorum_met:
            checkpoint_hash = self._append_checkpoint(packet, digest, winning_verdict, weights)
        return {
            "accepted": quorum_met,
            "reason": "ok" if quorum_met else "quorum_not_met",
            "canary": False,
            "checkpoint_hash": checkpoint_hash,
            "fault_hashes": fault_hashes,
        }

    def _score_canary(self, packet, digest, expected, votes, workers, weights):
        answers = {v["node_id"]: v["verdict"] for v in votes}
        fault_hashes: Dict[str, str] = {}
        for vote, node in zip(votes, workers):
            if vote["verdict"] == expected:
                self._reward(node, weights[node.node_id])
                node.canary_passed += 1
            else:
                node.canary_failed += 1
                fault_hashes[node.node_id] = self._penalize(
                    node, packet, digest, vote["verdict"], expected, "canary"
                )
            node.clamp_reputation()

        # Audit checkpoints whose producers all took part, using their weights at the time.
        newly_tainted: List[str] = []
        newly_vouched: List[int] = []
        for cp in self.checkpoints[1:]:
            if cp["status"] == REVIEWED:
                continue
            # Zero-weight (quarantined) producers had no say in the verdict.
            producers = {nid: w for nid, w in cp["workers"].items() if w > 0}
            if not producers or not set(producers) <= set(answers):
                continue
            if _wrong_fraction(producers, answers, expected) + _EPS >= 0.5:
                if cp["status"] != TAINTED:
                    cp["status"] = TAINTED
                    newly_tainted.append(cp["hash"])
            elif cp["status"] == UNVERIFIED:
                cp["status"] = VOUCHED
                newly_vouched.append(cp["checkpoint_id"])

        wrong_fraction = _wrong_fraction(weights, answers, expected)
        # A tie counts as wrong: the mesh could not tell the truth from the lie.
        majority_wrong = wrong_fraction + _EPS >= 0.5

        self.canary_rounds += 1
        alarm_raised = alarm_cleared = False
        if majority_wrong:
            if self.canary_alarm is None:
                self.canary_alarm = {
                    "raised_at_canary_round": self.canary_rounds,
                    "shard_id": packet.shard_id,
                    "packet_digest": digest,
                    "wrong_fraction": round(wrong_fraction, 4),
                    "workers": [],
                    "tainted_checkpoint_hashes": [],
                    "failed_canaries": 0,
                }
                self.alarm_history.append(self.canary_alarm)
                alarm_raised = True
            alarm = self.canary_alarm
            alarm["failed_canaries"] += 1
            alarm["workers"] = sorted(set(alarm["workers"]) | set(answers))
            alarm["tainted_checkpoint_hashes"] += newly_tainted
        else:
            self.canary_consensus_correct += 1
            # Clearing needs a canary that re-tests every worker recorded in the alarm, and
            # judges them on their own current weights, so adding honest nodes to the canary
            # cannot dilute the coalition below 50%.
            if self.canary_alarm is not None and self._alarm_workers_now_correct(answers, expected):
                self.canary_alarm["cleared_at_canary_round"] = self.canary_rounds
                self.canary_alarm = None
                alarm_cleared = True

        return {
            "accepted": False,          # canaries never create checkpoints
            "reason": "canary_scored",
            "canary": True,
            "expected_verdict": expected,
            "wrong_fraction": round(wrong_fraction, 4),
            "alarm_raised": alarm_raised,
            "alarm_cleared": alarm_cleared,
            "alarm_active": self.alarm_active,
            "tainted_checkpoint_hashes": newly_tainted,
            "vouched_checkpoint_ids": newly_vouched,
            "checkpoint_hash": None,
            "fault_hashes": fault_hashes,
        }

    def _alarm_workers_now_correct(self, answers: Dict[str, str], expected: str) -> bool:
        # Quarantined workers have zero weight and no say, so they are not required to
        # re-answer. Without this, an alarm whose failing workers were all quarantined could
        # never clear: their combined weight is 0 and the check below fails closed.
        required = [w for w in self.canary_alarm["workers"] if not self.nodes[w].quarantined]
        if not required:
            # Every failing worker is quarantined. This canary passed, and admission already
            # required at least min_workers non-quarantined workers, so the honest remainder decides.
            return True
        if not set(required) <= set(answers):
            return False
        weights = zone_capped_weights([self.nodes[w] for w in required], self.zone_weight_cap)
        return _wrong_fraction(weights, answers, expected) + _EPS < 0.5

    def _append_checkpoint(self, packet: NanoAgentPacket, digest: str, verdict: str,
                           weights: Dict[str, float]) -> str:
        cp_index = len(self.checkpoints)
        cp_payload = json.dumps(
            {
                "prev": self.checkpoints[-1]["hash"],
                "shard_id": packet.shard_id,
                "packet_digest": digest,
                "verdict": verdict,
                "cp_index": cp_index,
            },
            sort_keys=True,
        ).encode("utf-8")
        checkpoint_hash = "sha256:" + hashlib.sha256(cp_payload).hexdigest()
        self.checkpoints.append(
            {
                "checkpoint_id": cp_index,
                "hash": checkpoint_hash,
                "shard_id": packet.shard_id,
                "verified_verdict": verdict,
                "workers": dict(weights),
                "status": UNVERIFIED,
            }
        )
        for n in self.nodes.values():
            n.local_checkpoints.append(checkpoint_hash)
        self._prune_canaries()
        return checkpoint_hash

    # --- rollback -------------------------------------------------------------

    def rollback_to_checkpoint(self, checkpoint_id: int) -> Dict[str, Any]:
        if checkpoint_id < 0 or checkpoint_id >= len(self.checkpoints):
            return {"rolled_back": False, "reason": "invalid_checkpoint_id"}
        self.checkpoints = self.checkpoints[: checkpoint_id + 1]
        kept = {cp["hash"] for cp in self.checkpoints}
        for n in self.nodes.values():
            n.local_checkpoints = [h for h in n.local_checkpoints if h in kept]
        self._prune_canaries()
        return {"rolled_back": True, "active_checkpoint": self.checkpoints[-1]}
