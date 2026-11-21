# Protocol, Verification & Node Coordination Specification

**Document:** `spec/PROTOCOL_AND_CONSENSUS.md` (revision 0.2)
**Wire protocol version:** `protocol_version = "0.1"`
**Initiator / Genesis Author:** Krittidet Chanthake
**Date:** November 2026
**Reference implementation:** `nano_commons/nano_agent.py`, `nano_commons/node_runner.py`

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119. Every rule marked **[implemented]** matches the reference implementation exactly. Rules marked **[planned]** are not yet in the code.

---

## 1. Purpose

This specification defines:

1. The **agent packet** and its canonical, signed encoding
2. The **admission pipeline** that a packet passes before any work runs
3. **Weighted K-node consensus**, including zone caps and reputation
4. **Canary tasks**, which audit consensus and the knowledge chain against known answers
5. **Checkpoints, rollback and CRDT state merging**

---

## 2. Agent packet

### 2.1 Fields **[implemented]**

```json
{
  "protocol_version": "0.1",
  "network_id": "nano-commons-mainnet-v0.1",
  "agent_id": "nano-agent-0001",
  "mission_id": "public-environmental-watch-01",
  "shard_id": "shard-env-watch-001",
  "generation": 1,
  "ttl": 4,
  "energy_budget": 100,
  "freshness": 1.0,
  "freshness_decay_rate": 0.05,
  "parent_checkpoint_hash": "sha256:<64 hex>",
  "payload": {
    "bias": 0.0,
    "memory_window": [],
    "crdt_clock": {},
    "observation_hash": "sha256:<64 hex>",
    "assigned_workers": ["node-a", "node-b", "node-c"]
  },
  "signature": "ed25519:<base64>"
}
```

| Field | Type | Constraint |
| :--- | :--- | :--- |
| `protocol_version`, `network_id`, `agent_id`, `mission_id`, `shard_id`, `parent_checkpoint_hash`, `signature` | string | — |
| `generation`, `ttl`, `energy_budget` | integer | Booleans are not integers |
| `freshness`, `freshness_decay_rate` | number | Finite, in `[0.0, 1.0]` |
| `payload` | object | Canonical JSON only (§2.2) |
| `payload.bias` | number | Optional; finite |
| `payload.memory_window` | array of numbers | Optional; finite |
| `payload.crdt_clock` | object of `node_id → integer ≥ 0` | Optional (G-Counter) |
| `payload.observation_hash` | string | **Required for admission** (§3, step 9) |
| `payload.assigned_workers` | array of strings | Optional; binds the worker set (§3, step 10) |

`shard_id` SHOULD be derived deterministically, for example `hash(mission_id, shard_index, window_id)`, so that peers can deduplicate work **[planned]**.

### 2.2 Canonical encoding

- A packet's **signing bytes** are the UTF-8 JSON of every field except `signature`, with keys sorted and separators `,` and `:` (no whitespace).
- Numbers are encoded exactly as stored. `freshness` MUST NOT be rounded before signing.
- Every object key in `payload`, at any depth, MUST be a string. Every number MUST be finite, and every integer MUST lie within ±2^53, the range every JSON implementation represents exactly. The only allowed value types are string, finite number, boolean, null, array and object. This gives each payload exactly one encoding.
- The **packet digest** is `"sha256:" + hex(SHA-256(signing bytes))`.

### 2.3 Signature

- `signature = "ed25519:" + base64(Ed25519_sign(mission_private_key, signing_bytes))`.
- The verifying key is looked up by `mission_id` from keys the host registered in advance.
- An unknown mission, a malformed signature string, invalid base64 or a failed verification MUST all lead to rejection. None of them may raise an error that escapes the gate.
- Signatures cover the packet as published by the mission owner. Forwarded copies (§2.4) are not re-signed; signed hop receipts are **[planned]**.

### 2.4 Hop rules **[implemented]**

When a node clones a packet for execution or forwarding:

| Field | Child value |
| :--- | :--- |
| `generation` | `parent.generation + 1` |
| `ttl` | `parent.ttl − 1` |
| `energy_budget` | `parent.energy_budget − hop_energy_cost` (default 15) |
| `freshness` | `max(0, parent.freshness × (1 − freshness_decay_rate))` |
| `payload` | Deep copy |

A packet with `ttl ≤ 0` MUST NOT be forwarded. The gate (§3) guarantees that a child's `energy_budget` is never negative.

### 2.5 Observation digest **[implemented]**

`observation_digest(obs) = "sha256:" + hex(SHA-256(canonical JSON of obs))`, using the same canonical rules as §2.2.

- `obs` MUST be a JSON object.
- If present, `obs.value` and `obs.threshold` MUST be finite numbers. Integers MUST lie within ±2^53.
- A packet commits to its input by carrying `payload.observation_hash = observation_digest(obs)`.

### 2.6 Agent loop (Observe → Think → Act → Reflect) **[implemented]**

1. **Observe:** `reading = obs.value` (default 0); `threshold = obs.threshold` (default 50).
2. **Think:** `adjusted = reading + payload.bias`. `effective_score = adjusted × freshness` is reported for audit only.
3. **Act:** verdict is `"ANOMALY"` if `adjusted ≥ threshold`, otherwise `"NORMAL"`.
4. **Reflect:** append the reading to `memory_window` and keep the last 5 entries. Increment `crdt_clock[node_id]` by 1.

---

## 3. Admission pipeline **[implemented]**

A host MUST evaluate these checks in this order and stop at the first failure with the reason given. A rejection changes no state and does not consume the packet.

| # | Check | Reason on failure |
| :--- | :--- | :--- |
| 1 | Worker list has no duplicates | `duplicate_worker` |
| 2 | Every worker is registered | `unknown_worker` |
| 3 | At least `min_workers` (default 3) workers are not quarantined | `insufficient_workers` |
| 4 | Packet is well-formed (§2.1, §2.2) | `malformed_schema` |
| 5 | `network_id` matches the host's network | `network_id_mismatch` |
| 6 | `1 ≤ ttl ≤ host_max_ttl` (default 10) | `invalid_or_exhausted_ttl` |
| 7 | `energy_budget > 0` and `energy_budget ≥ hop_energy_cost` | `exhausted_energy_budget` |
| 8 | `freshness ≥ min_freshness` (default 0) | `stale_knowledge` |
| 9 | A key is registered for `mission_id` | `unknown_mission` |
| 10 | Signature verifies (§2.3) | `invalid_signature` |
| 11 | Observation is valid (§2.5) | `malformed_observation` |
| 12 | `payload.observation_hash = observation_digest(obs)` | `observation_mismatch` |
| 13 | If `assigned_workers` is present, it equals the worker set (order ignored) | `worker_set_mismatch` |
| 14 | `parent_checkpoint_hash` equals the current chain head | `stale_parent_checkpoint` |
| 15 | Packet digest has not been processed before | `replayed_packet` |

Checks 11–15 come after the signature check on purpose, so that unsigned traffic cannot probe chain or audit state. A packet that passes all 15 checks is **consumed**: its digest is recorded, and it is never processed again.

---

## 4. Weighted K-node consensus

### 4.1 Configuration **[implemented]**

| Parameter | Default | Constraint (violations raise an error at startup) |
| :--- | :--- | :--- |
| `quorum_threshold` | 0.65 | `0.5 < q ≤ 1`, so a 50/50 tie can never be accepted |
| `zone_weight_cap` | 0.50 | `0 < c ≤ 1` |
| `min_workers` | 3 | `≥ 1` |
| `host_max_ttl` | 10 | — |
| `min_freshness` | 0.0 | — |

### 4.2 Vote weight **[implemented]**

1. Each worker's raw weight is its reputation `R`, or 0 if it is quarantined.
2. Raw weights are summed per **zone**, and zone shares are normalised to sum to 1.
3. Zone shares are capped at `zone_weight_cap` by **water-filling**:
   - Cap every share that is above the limit.
   - Spread the remaining budget over the uncapped zones in proportion to their shares.
   - Repeat until no share exceeds the cap.
   - If every zone ends up capped, the leftover weight stays unassigned, so the total can be below 1.
4. A worker's weight is its zone's capped share multiplied by its fraction of the zone's raw weight.

As a result, no single zone can reach a quorum on its own when `zone_weight_cap < quorum_threshold`.

### 4.3 Decision **[implemented]**

- Each verdict's score is the sum of the weights of the workers that voted for it.
- The winning verdict has the highest score. Ties are broken alphabetically, which makes the result deterministic but never acceptable (§4.1).
- **Quorum** is met when `winning_score ≥ quorum_threshold`. The result is then `accepted = true` with reason `ok`, and a checkpoint is appended (§6.1). Otherwise the reason is `quorum_not_met`.

### 4.4 Reputation and credits **[implemented]**

`R ∈ [0, 1]` is rounded to 4 decimals after every update. A new node starts at `R = 0.15`.

| Outcome (quorum met, or any canary) | Effect |
| :--- | :--- |
| Correct vote | `R += 0.04`; `verified_samples += 1`; `+10` credits if the vote's weight was above 0 |
| Wrong vote, node has no prior fault | `R −= 0.06`; `fault_count += 1`; fault logged |
| Wrong vote, node has a prior fault | `R −= 0.18`; `fault_count += 1`; fault logged |
| Ordinary task without quorum | No change for anyone, and no checkpoint |

- `R < 0.10` means **quarantine**: the node's vote weight is 0 and it earns no credits. It can still raise `R` by voting correctly.
- Penalties MUST depend only on observed votes. A node's own claims about itself are never used.
- **Fault log entry:** `{node_id, shard_id, packet_digest, kind ("consensus" | "canary"), submitted, reference, fault_number}`, plus `fault_hash = "sha256:" + SHA-256(JSON of the entry with sorted keys)`.

---

## 5. Canary tasks **[implemented]**

A canary is an ordinary packet whose correct verdict the audit layer knows in advance. It carries no marker that workers could detect.

### 5.1 Registration

`register_canary(packet, expected_verdict)`:

- `expected_verdict` MUST be `"ANOMALY"` or `"NORMAL"`.
- `packet.parent_checkpoint_hash` MUST equal the current head.
- The packet digest MUST NOT already be processed or registered.
- A registration whose parent is no longer the head is dropped when a checkpoint is appended or after a rollback.
- To stay indistinguishable from real work, a canary SHOULD use the same distribution of inputs, `assigned_workers` usage and timing as real work.

### 5.2 Scoring and checkpoint audit

When an admitted packet is a registered canary:

1. Each worker is scored against `expected_verdict` with the rules of §4.4. `canary_passed` or `canary_failed` is incremented.
2. **Checkpoint audit.** For every checkpoint other than genesis whose status is not `reviewed`:
   - Let `P` be its recorded producers whose weight was above 0.
   - Skip it unless `P` is non-empty and every member of `P` voted in this canary.
   - Compute `wrong_P` = the producers' recorded weight on wrong answers divided by their total recorded weight.
   - If `wrong_P ≥ 0.5`, the status becomes **`tainted`**. Otherwise, a status of `unverified` becomes **`vouched`**.
3. A canary never creates a checkpoint. Its result has `accepted = false` and reason `canary_scored`.

### 5.3 Alarm

Let `wrong` be the canary's own wrong weight divided by its total weight. If the total weight is 0, `wrong = 1`, so the check fails closed.

- **Raise:** if `wrong ≥ 0.5` (a tie counts as wrong):
  - If no alarm is active, open one that records the raising canary, its `wrong` value and `failed_canaries = 0`.
  - Then, for every failing canary while the alarm is open: increment `failed_canaries`, add this canary's workers to `alarm.workers`, and add the hashes of newly tainted checkpoints to `alarm.tainted_checkpoint_hashes`.
- **Clear:** if `wrong < 0.5`, an active alarm clears only when both of these hold:
  - Every node in `alarm.workers` voted in this canary.
  - Those nodes, weighted **among themselves** at their current reputation (§4.2), have a wrong fraction below 0.5.
- **While an alarm is active:**
  - Ordinary packets are still admitted and executed, so the work stream does not reveal which tasks are canaries.
  - Their outcome is recorded in `held_results`, with reason `held_alarm_active`, and is not scored or checkpointed. The packet is consumed.

### 5.4 Operator review

`mark_reviewed(checkpoint_id)` sets the status to **`reviewed`**. The automatic audit never changes a reviewed checkpoint. Genesis cannot be reviewed.

---

## 6. Checkpoints, rollback and state

### 6.1 Checkpoints **[implemented]**

- Genesis: `checkpoint_id = 0`, `hash = "sha256:genesis_checkpoint_0000"`, status `vouched`.
- An ordinary task that meets quorum appends a checkpoint:
  - `hash = "sha256:" + SHA-256(JSON with sorted keys of {prev, shard_id, packet_digest, verdict, cp_index})`.
  - It records `workers` (each producer's weight at that moment) and status **`unverified`**.

| Query | Definition |
| :--- | :--- |
| Suspect checkpoints | Status not `vouched` or `reviewed` |
| Tainted checkpoints | Status `tainted` |
| Last trusted checkpoint | Highest id such that it and every earlier checkpoint are `vouched` or `reviewed` |

### 6.2 Rollback **[implemented]**

`rollback_to_checkpoint(id)` is refused with `invalid_checkpoint_id` if no checkpoint has that id. Otherwise it does three things:
- Keeps checkpoints `0..id`.
- Removes every other checkpoint hash from node-local lists.
- Drops canary registrations whose parent is not the new head.

Rollback does **not** revert reputation, credits, fault counts, the fault log, held results or an active alarm. Alarm records refer to checkpoints by hash, so they stay correct after a rollback.

### 6.3 CRDT state **[implemented]**

`crdt_clock` is a G-Counter. Clocks merge by element-wise maximum, which is commutative, associative and idempotent. A round returns the merge of the packet's clock and every worker's clock. PN-Counters for fault tallies and causal knowledge deltas are **[planned]**.

### 6.4 Shard leases

- **[implemented]** `claim_shard` grants a lease if the shard is free and is idempotent for the current holder. `release_shard` frees it, but only for the holder.
- **[planned]** Leases are not yet enforced during execution, and they are not yet gossiped between peers.

---

## 7. Summary of guarantees (reference implementation)

| Dimension | Mechanism | Effect |
| :--- | :--- | :--- |
| Safety and bounds | Canonical schema, `network_id`, Ed25519, TTL, energy, freshness, host caps | Runaway replication, tampering and cross-network mixups are refused before execution |
| Input integrity | `observation_hash`, optional `assigned_workers` | Inputs and judges cannot be swapped after signing; fake inputs reveal nothing |
| Replay and ordering | Packet digest set, parent must equal head | Each packet counts once, and only on the current chain |
| Consensus | Reputation weights, water-filled zone cap, quorum > 0.5 | No zone decides alone and ties are never accepted |
| Truth audit | Canaries, checkpoint taint and vouch, alarm with held results | A captured majority is detected, contained and drained, and its checkpoints are flagged for rollback |
| Correctable memory | Hash chain with producer records, rollback, G-Counters | Bad knowledge can be located and removed, and regions converge |

Known gaps are listed in [`SECURITY_AND_THREAT_MODEL.md`](SECURITY_AND_THREAT_MODEL.md) §4 and in the whitepaper §11.
