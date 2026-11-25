# NCP-0003: Scoped and Rate-Limited Alarms

| Field | Value |
| :--- | :--- |
| **Status** | Draft. Not yet proposed for consensus. |
| **Author** | Krittidet Chanthake, based on a proposal from an external security review |
| **Created** | 2026-11-22 |
| **Kind** | Protocol change (GOVERNANCE.md §5.2, NCP) |
| **Addresses** | [SECURITY_AND_THREAT_MODEL.md §2.12](../spec/SECURITY_AND_THREAT_MODEL.md) "Alarm abuse (denial of service)" |
| **License** | CC BY-SA 4.0 |

---

## 1. Motivation

In v0.2, the canary alarm is **one switch for the whole mesh**. When most of a canary's own vote weight answers wrong, the alarm is raised and **every** ordinary result is held until a later canary clears it. This is deliberately fail-safe, but it opens a denial-of-service path: a group that controls enough weight in one canary's worker set can fail canaries on purpose and freeze **all** missions, including missions and zones it has nothing to do with.

The goal is to make alarms **precise rather than blunt**, without making the network blind to real attacks:
- an alarm should stop only what is actually affected,
- repeated triggering should not multiply its effect,
- stopping everything should require evidence from several places.

An analysis for this proposal also found a liveness bug. In v0.2, an alarm clears only when the workers that failed, weighted among themselves, pass a canary. If **every** one of them has since been quarantined, their total weight is zero. The check then fails closed for ever, and the alarm can never clear. This proposal fixes that as well.

### 1.1 How alarms work here

Nodes do not "send" alarms. **The mesh raises them itself from canary results.** The attack to defend against is therefore not nodes spamming alarm messages. It is a group of nodes **deliberately answering canaries wrongly**. That changes some of the original review's suggestions:

- **Rate limits** apply per scope and per worker set, not per reporting node.
- **Incentives:** no extra reward for "confirming an alarm" is needed. Canary answers are already scored against the truth (+0.04 for a correct answer; −0.06 and then −0.18 for wrong ones), so anyone who triggers false alarms pays for it in reputation.

---

## 2. Specification

### 2.1 Alarm scopes

Every alarm has a `scope_type` and a `scope_id`:

| Scope | `scope_id` | Raised when | Effect |
| :--- | :--- | :--- | :--- |
| **`mission`** (default) | the canary's `mission_id` | A canary of that mission is failed by most of its own weight | Ordinary results of **that mission only** are held, as v0.2 holds all results. Other missions continue. |
| **`zone`** | a zone name | The wrong weight of a failing canary is concentrated in one zone: that zone holds at least `zone_concentration` (default 0.66) of the wrong weight | Nodes of **that zone** get weight 0 in ordinary tasks of the affected mission while the alarm lasts. Work continues if a quorum is still reachable without them; otherwise the result is held. |
| **`global`** | `"*"` | §2.3 escalation rules | All ordinary results in the mesh are held, as in v0.2 today |

A failing canary may raise a `zone` alarm **and** a `mission` alarm together. The zone alarm limits the damage, and the mission alarm keeps the evidence.

### 2.2 Counting in canary rounds, not clock time

Every quota, window and cooldown is counted in **canary rounds**: the mesh's own sequence number of scored canaries.
- Rounds are deterministic and identical on every node, so every decision can be replayed and audited.
- Wall clocks differ between machines and can be manipulated; rounds cannot.

### 2.3 Escalation to `global`

A `global` alarm is raised only if, within the last `global_window` canary rounds (default 10), canaries were failed by most of their own weight in **at least 2 distinct zones** or **at least 2 distinct missions**. Each of those failures must also meet both of these:

- at least 3 non-quarantined workers took part (the existing minimum);
- the zone cap of 50% applied to the weights.

### 2.4 Cooldown and hysteresis

- **Cooldown.** After a scope's alarm is raised, the same scope cannot raise a *new* alarm for `cooldown_rounds` (default 5). Further failures in that scope during cooldown are **added to the open alarm as evidence**: they increment `trigger_count` and are appended to `evidence`. They never create duplicate alarms.
- **Evidence keeps escalating during cooldown.** Escalation to `zone` or `global` is still evaluated on every failure. A cooldown never hides worsening evidence.
- **Hysteresis.**
  - A scope's alarm clears only after `clear_passes` consecutive passing canaries in that scope (default 1 for `mission` and `zone`, 2 for `global`).
  - The same scope then cannot be re-raised within the next `rearm_rounds` (default 2), unless the escalation rules in §2.3 are met.

### 2.5 Quota per worker set

Let a **worker set** be the hash of its sorted worker ids. A worker set may cause at most `set_quota` new alarm raises (default 2) per `set_window` canary rounds (default 20). Above that quota:
- its canary failures are still **scored and penalised** in full,
- they are added as evidence to any open alarm,
- **they do not raise new alarms**.

### 2.6 Clearing

An alarm clears when a passing canary in its scope meets all of these:
1. It includes every alarm worker that is **not currently quarantined**. Quarantined workers have weight 0 and no say, so they are removed from the requirement. **This fixes the liveness bug in §1.**
2. Those workers, weighted **among themselves** at their current reputation, answer it correctly. This is unchanged from v0.2: padding with honest nodes cannot dilute the coalition.
3. The hysteresis count in §2.4 is satisfied.

If no non-quarantined alarm workers remain, the next passing canary in the scope that has at least 3 non-quarantined workers clears it. In that case the attackers are all quarantined, so the honest remainder decides.

### 2.7 Alarm records and audit chain

Each alarm record contains:

```json
{
  "scope_type": "mission | zone | global",
  "scope_id": "mission-01-pm25-north-th",
  "raised_round": 42,
  "trigger_count": 3,
  "cooldown_until_round": 47,
  "workers": ["..."],
  "evidence": ["sha256:<canary packet digest>", "..."],
  "tainted_checkpoint_hashes": ["sha256:..."],
  "cleared_round": null
}
```

- **Alarm log.** Every *raise*, *escalation*, *merge* (evidence added during cooldown) and *clear* is appended to an **alarm log**: a SHA-256 hash chain in which each entry contains the hash of the previous one.
- **Rollback does not affect it.** Rolling back the checkpoint chain never removes alarm-log entries. The audit trail of alarms is permanent.

### 2.8 Parameters

| Parameter | Default | Notes |
| :--- | :--- | :--- |
| `zone_concentration` | 0.66 | Share of wrong weight from one zone that makes a zone alarm |
| `global_window` | 10 rounds | Window for the multi-zone or multi-mission escalation |
| `cooldown_rounds` | 5 | Per scope |
| `clear_passes` | 1 (`global`: 2) | Hysteresis |
| `rearm_rounds` | 2 | After clearing |
| `set_quota` / `set_window` | 2 / 20 rounds | Per worker set |

All defaults are placeholders, to be calibrated on public-testnet data. Changing a default is itself an NCP-level change.

---

## 3. Security and collusion impact

| Attack | v0.2 | With NCP-0003 |
| :--- | :--- | :--- |
| A few colluders fail one mission's canaries | All missions frozen | **Only that mission** is held. If they are concentrated in one zone, only that zone is muted and work continues on the others. |
| Repeated triggering | Holds everything for as long as the colluders keep failing | Cooldown merges repeats into one alarm; the quota stops new raises; every failure still costs reputation (−0.18 per repeat) until quarantine |
| All failing workers quarantined | **Alarm never clears** (liveness bug) | Quarantined workers are removed from the clearing requirement; the honest remainder clears it |
| Stopping the whole network | One worker set is enough | Needs failures in ≥ 2 zones or ≥ 2 missions within a window, each with ≥ 3 independent workers under the zone cap. This needs broad compromise, which then justifies a global halt. |
| Hiding a real attack behind a cooldown | n/a | Evidence still accumulates, and escalation is evaluated on every failure |
| Alarm flapping | Possible | Hysteresis (`clear_passes`, `rearm_rounds`) |

**Residual risks**
- A zone alarm mutes honest nodes in that zone, so an attacker with presence in a zone can still reduce that zone's voice for a time. This is bounded by cooldown and quota, and paid for in reputation.
- The parameters need calibration. If they are set badly, alarms become either too sluggish or too easy to trigger.

---

## 4. Compatibility and migration

- **Replaces the v0.2 alarm.** The single mesh-wide alarm is replaced by scoped alarms. The v0.2 behaviour corresponds to always raising `global`.
- **API.**
  - `alarm_active` becomes a query per scope, for example `alarm_active(mission_id=..., zone=...)`.
  - Node-console `GET /api/alarms` returns a list of open alarms with their scopes, plus the alarm log.
- **No change** to packets, signatures, checkpoints or reputation rules.

---

## 5. Verification plan

The reference implementation must include deterministic tests for:

1. **Mission isolation.** Colluders in one zone fail mission A's canaries: mission A is held (or its zone is muted), while mission B's ordinary tasks are still accepted.
2. **Zone muting.** Concentrated wrong weight raises a zone alarm; work in the affected mission continues when a quorum is reachable without the muted zone.
3. **Global escalation.** It happens only after failures in 2 zones or 2 missions within `global_window`, and never from a single worker set.
4. **Cooldown merge.** Repeated failures within the cooldown increase `trigger_count` and evidence without creating new alarms, and escalation is still evaluated.
5. **Worker-set quota.** It is enforced, while penalties still apply in full.
6. **DoS simulation.** Attackers repeatedly fail canaries. Their reputation falls to quarantine, the alarm clears through the honest remainder, and unrelated missions are never held.
7. **Liveness bug.** An alarm whose workers are all quarantined still clears.
8. **Hysteresis.** No flapping under alternating pass and fail.
9. **Alarm log.** It is hash-chained, survives rollback, and can be replayed deterministically from canary rounds.

---

## 6. Acknowledgement

The scoping, rate-limit and escalation ideas come from an external security review of v0.2. This NCP adapts them to the protocol's design, in which the mesh raises alarms from canary results rather than nodes sending them, and adds the liveness fix in §1.

*Under GOVERNANCE.md §5.3 (bootstrap rule), this protocol change cannot be finalised until the project has at least 3 stewards from at least 2 unrelated organisations. It can be implemented and tested in the reference testbed in the meantime.*
