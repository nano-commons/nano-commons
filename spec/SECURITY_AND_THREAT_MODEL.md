# Security, Privacy & Threat Model Specification

**Document:** `spec/SECURITY_AND_THREAT_MODEL.md` (revision 0.2)
**Protocol:** The Nano-Commons Protocol (wire version `0.1`)
**Initiator / Genesis Author:** Krittidet Chanthake
**Date:** November 2026

Mitigation status:
- **[implemented]**: present in the reference implementation (`nano_commons/`)
- **[planned]**: specified but not yet built
- **[operational]**: depends on how a deployment is run, not on protocol code

Section numbers such as §3 refer to [`PROTOCOL_AND_CONSENSUS.md`](PROTOCOL_AND_CONSENSUS.md).

---

## 1. Threat model overview

The Nano-Commons Protocol invites anyone to contribute compute, so it uses a **zero-trust, verifiable-commons** model. It assumes:

- **Nodes:** any node may be buggy, intermittently offline, resource-constrained, malicious, or colluding with other nodes, including coalitions that hold a majority of the vote weight.
- **Packets:** packets may be replayed, tampered with in transit, re-submitted with altered inputs or worker sets, or built to replicate excessively.
- **Submitters:** whoever submits a packet is not trusted. Only the mission owner's signature is.
- **Shared knowledge:** pooled results must resist poisoning and long-term drift while raw data stays local.

---

## 2. Threats and mitigations

### 2.1 Packet tampering and forgery

**Threat:** A packet is changed in transit, or forged by someone who does not hold the mission key.

**Mitigations:**
- **[implemented]** An Ed25519 signature covers every field except the signature itself. The verifying key is registered per `mission_id`.
- **[implemented]** The canonical encoding gives each packet exactly one byte form (§2.2): string keys only, finite numbers only, no rounding before signing.
- **[implemented]** Broken signatures, bad base64 and unknown missions are refused without raising errors.
- **[planned]** Signed hop receipts, so that forwarded copies can be checked against the origin signature.

### 2.2 Input substitution and canary probing

**Threat:** A relay feeds a valid packet a different input, or feeds it fake inputs to see whether the network treats it as a canary.

**Mitigations:**
- **[implemented]** `payload.observation_hash` is signed, so any other input is refused with `observation_mismatch`. Canaries and real tasks get the same response, and neither is consumed.
- **[implemented]** Inputs that are not valid observations (non-finite or non-numeric `value`/`threshold`) are refused with `malformed_observation`.
- **[implemented]** All of these checks run after signature verification, so unsigned traffic learns nothing about audit state.

### 2.3 Replay and stale-chain injection

**Threat:** A valid packet is submitted again to collect rewards twice or to inflict penalties twice, or a packet built on an old chain head is injected.

**Mitigations:**
- **[implemented]** Each packet digest is processed at most once (`replayed_packet`).
- **[implemented]** `parent_checkpoint_hash` must equal the current head (`stale_parent_checkpoint`).
- **[planned]** A replay set that persists and is shared across meshes. Today it lives in memory.

### 2.4 Captured consensus (collusion)

**Threat:** A coordinated group holding enough vote weight agrees on false answers. It is rewarded, honest nodes are penalised, and the false results are written into shared knowledge.

**Mitigations:**
- **[implemented]** **Zone cap.** No zone can hold more than `zone_weight_cap` (default 50%) of the weight, and water-filling keeps the cap in place after redistribution (§4.2). The quorum must be above 50%, so a tie is never accepted.
- **[implemented]** **No penalty on split votes.** An attacker who prevents quorum cannot push honest nodes into quarantine.
- **[implemented]** **Canary tasks.** Workers are scored against known answers, not the majority (§5).
- **[implemented]** **Checkpoint audit.** Every checkpoint records its producers and their weights. When those producers, at those weights, fail a canary, the checkpoint is tainted. The taint is sticky and is not undone by later good behaviour.
- **[implemented]** **Alarm with held results.**
  - If most of the weight fails a canary, ordinary results are held: no scoring, no checkpoints.
  - The alarm clears only when the failing nodes, weighted among themselves, pass a canary. Padding the canary with honest nodes therefore does not dilute them below the threshold.
- **[implemented]** **Rollback** to the last trusted checkpoint (§6).

### 2.5 Worker-set manipulation

**Threat:** A submitter picks friendly workers, for example by running a canary on an honest-only set before the verifier does, so the colluders are never tested.

**Mitigations:**
- **[implemented]** `payload.assigned_workers` lets the signer bind the worker set. Any other set is refused with `worker_set_mismatch`.
- **[operational]** Missions SHOULD bind the worker set on **every** packet, so that canaries stay indistinguishable from real work.
- **[planned]** The mesh assigns workers at random from the healthy pool.

### 2.6 Sybil attacks and botnet dominance

**Threat:** An adversary runs many virtual nodes to dominate voting, collect credits or inject poisoned updates.

**Mitigations:**
- **[implemented]** New nodes start with low reputation (`R = 0.15`), and reputation can only be earned through correct votes.
- **[implemented]** The zone cap limits how much weight any one zone holds.
- **[planned]** Latency and topology triangulation to detect many nodes hosted on one machine, and web-of-trust vouching.

### 2.7 Runaway replication and resource exhaustion

**Threat:** A bug or a malicious change makes an agent clone itself without end, or makes it consume a host's resources.

**Mitigations:**
- **[implemented]** Every hop lowers `ttl` and `energy_budget`. A packet whose TTL is outside `1..host_max_ttl`, or whose energy cannot cover the next hop, is refused.
- **[implemented]** `freshness` decays at each hop, and hosts may set `min_freshness`.
- **[planned]** A WebAssembly sandbox with hard CPU, memory, bandwidth and concurrency caps that agent code cannot override.

### 2.8 Split-brain, knowledge drift and catastrophic forgetting

**Threat:** Regional updates conflict when merged, knowledge goes stale, or new updates overwrite good knowledge.

**Mitigations:**
- **[implemented]** G-Counter merging, which gives the same result in any order (§6.3).
- **[implemented]** A hash-linked checkpoint chain with producer records and rollback.
- **[implemented]** Canaries double as drift probes: a falling `consensus_accuracy` signals that the network is drifting from ground truth.
- **[planned]** Causal knowledge deltas, PN-Counters for fault tallies, and scheduled recalibration.

### 2.9 Data privacy and cross-border jurisdiction

**Threat:** Sensitive local data (health, farm, personal or community telemetry) is exposed to untrusted nodes or is handled against local law.

**Mitigations:**
- **[implemented]** Packets carry only a hash of the input (`observation_hash`), never the raw records. The audit trail stores digests and verdicts, not data.
- **[operational]** Raw personal data stays on the local, trusted source wherever possible, and only bounded summaries are shared.
- **[operational]** Each node operator follows the law of its own jurisdiction (for example data-protection statutes).
- **[planned]** A host policy gate that refuses missions unsuitable for the host's jurisdiction.

### 2.10 Impersonation, release tampering and token scams

**Threat:** Bad actors impersonate the project to distribute malware, or launch fake tokens that claim to be affiliated with it.

**Mitigations:**
- **[operational]** Official releases and proposals carry GPG or Sigstore signatures and published SHA-256 checksums.
- **[operational]** Documentation and client banners state that no token or financial investment exists under this project.

---

## 3. Verification and scoring rules (summary)

| Rule | Value |
| :--- | :--- |
| Minimum workers | 3 non-quarantined, distinct, registered nodes |
| Quorum | Winning weight ≥ `quorum_threshold` (default 0.65, must be > 0.5) |
| Correct vote | `R +0.04`, `+10` credits (only if vote weight > 0) |
| First fault / repeat fault | `R −0.06` / `R −0.18`, recorded in a hashed fault log |
| No quorum | No reward or penalty, and no checkpoint |
| Quarantine | `R < 0.10`: weight 0 and no credits; the node can recover |
| Canary | Scored against the known answer; audits checkpoints; can raise or clear the alarm |

Exact definitions are in [`PROTOCOL_AND_CONSENSUS.md`](PROTOCOL_AND_CONSENSUS.md).

---

## 4. Known residual risks

| Risk | Detail | Direction |
| :--- | :--- | :--- |
| **Adaptive colluders** | A worker that can see the chain head or the alarm state can infer when an alarm is active and switch to honest answers until it clears. Recognisable canary inputs can be learned. | Keep audit state away from workers; draw canaries from the real input distribution; keep the canary rate secret |
| **Retroactive vouching** | The audit assumes nodes behave consistently. Colluders who poison a checkpoint and then answer canaries honestly can have that checkpoint vouched later. | Re-validate checkpoint verdicts by replaying their tasks to fresh, randomly assigned workers |
| **Single answer key** | In the reference code, one mesh object holds the canary answers. | Independent verifiers with threshold disclosure |
| **Unbound worker sets** | Without `assigned_workers`, the submitter chooses the judges. | Bind every packet; move to mesh-assigned workers |
| **Penalty calibration** | An honest node that is wrong twice is treated like a poisoner. | Calibrate on public-testnet error rates |
| **Unrevoked gains** | Rollback does not undo reputation or credits earned before an alarm. | Credit clawback for producers of tainted checkpoints |
| **No network or sandbox yet** | The reference implementation runs in one process. | P2P transport and a WebAssembly runtime (roadmap Phase 1) |
