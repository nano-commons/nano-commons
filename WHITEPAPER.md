# The Nano-Commons Protocol

### Small minds, verified together, owned by everyone.

**Whitepaper v0.2 · November 2026**
**Initiator and Genesis Author: Krittidet Chanthake**
**Status:** Specification and Python reference implementation (local testbed)
**License:** This document is licensed under CC BY-SA 4.0. Reference code is AGPLv3 or later.

---

## Abstract

Artificial intelligence is becoming infrastructure. Infrastructure that only a few can build, own and switch off is a risk to everyone who comes to depend on it.

The Nano-Commons Protocol proposes a different foundation. Very small autonomous agents, from bytes to a few kilobytes, run on computers that volunteers donate. They do bounded, useful work and report results that the network does not take on trust. Every result is signed, checked by several independent nodes, weighted by earned reputation, and limited so that no single region can decide it alone. The network then tests its own consensus against tasks whose answers are already known.

That last step is the core of this paper. Most open networks assume that agreement means truth. It does not: a coordinated group can agree on a lie. Nano-Commons treats the majority as a claim to be audited. **Canary tasks** look exactly like real work but carry an answer held only by the verifier. Each node is scored on whether it was right, not on whether it agreed. Every checkpoint of shared knowledge records who produced it, so that once a canary exposes a coalition, everything that coalition produced is flagged and can be rolled back.

The protocol has no owner, no token and no master key. It belongs to the commons.

---

## 1. Why this has to exist

Three trends point in the same direction.

1. **Compute is concentrating.** The most capable AI systems need capital and data-center capacity that only a handful of organisations hold. Access, pricing and permitted use are set by those who own the machines.
2. **Communities are left with two bad choices.** A rural clinic, a farming cooperative or a city monitoring its air can rent intelligence from a distant provider and hand over its data, or it can go without.
3. **Trust is assumed instead of shown.** Users rarely see how an answer was produced, who checked it, or whether it can be corrected once it turns out to be wrong.

Meanwhile, hundreds of millions of capable computers sit idle most of the day. Volunteer computing has shown for over two decades that people will donate that capacity to science when the purpose is clear and the software is safe. What has been missing is a way to make donated capacity **trustworthy enough to rely on** without putting a company in the middle.

Nano-Commons is an attempt to build that missing layer.

---

## 2. The thesis

> Many small agents, each bounded and verifiable, can produce knowledge that a community can rely on. This works only if the network checks itself against reality, not just against itself, and only if no one can own the result.

The thesis has three claims, and the protocol is built to test each of them:

| Claim | What would prove it wrong | How the protocol answers |
| :--- | :--- | :--- |
| Small agents can do useful work | Tasks too complex for bounded agents | Start with well-defined missions: anomaly detection, sensor validation, classification |
| Untrusted nodes can produce trusted results | A coalition that captures consensus | Signed packets, weighted K-node voting, zone caps, and canary audits against known answers |
| The result can remain a commons | Capture by a company, a token market or the founder | No token, non-transferable credits, copyleft code, public-domain specifications, no master key |

---

## 3. Design principles

1. **Small by design.** An agent should fit where intelligence is needed: on a laptop, a phone or a sensor gateway. Small agents are cheap to verify, cheap to replicate and cheap to stop.
2. **Bounded by default.** Every agent carries its own limits: time to live, energy budget and freshness. A host refuses anything that asks for more than the host allows. Nothing replicates forever.
3. **Verified, not trusted.** No single node's answer counts as a fact. Answers are signed, cross-checked, weighted and recorded with their provenance.
4. **Truth over majority.** Agreement is evidence, not proof. The network audits its own consensus against known answers and acts when consensus fails.
5. **Correctable memory.** Shared knowledge is a hash-linked chain of checkpoints that records who produced each one. Bad knowledge can be found, flagged and rolled back.
6. **Owned by no one.** No company, foundation, token holder or founder can switch the network off or enclose what it learns.

---

## 4. Architecture

| Layer | Responsibility | Reference implementation (v0.2) |
| :--- | :--- | :--- |
| **1. Nano-Agent** | A signed packet carrying goal, policy, short memory and bounds; runs an Observe → Think → Act → Reflect loop | Implemented |
| **2. Host gate** | Checks schema, network, TTL, energy, freshness, signature and input before anything runs | Implemented |
| **3. Consensus and trust** | K-node weighted voting, per-zone caps, reputation, quarantine, fault log | Implemented |
| **4. Canary audit** | Ground-truth tasks, checkpoint audit, network alarm, held results | Implemented |
| **5. Knowledge chain** | Hash-linked checkpoints with producer records, rollback, CRDT state merging | Implemented |
| **6. P2P mesh** | Gossip, shard leases, routing between real machines | Leases modelled; networking planned |
| **7. Sandbox runtime** | WebAssembly isolation with hard CPU, memory and network limits | Planned |
| **8. Node console** | Each operator's own control surface: a plain web page, a command line and a local HTTP API | Implemented (testbed) |

Layers 1 to 5 and the node console exist today as a Python reference implementation, run in a single-process testbed. Layers 6 and 7 are the next engineering milestones (see Section 11).

### 4.1 Everyone runs their own node

A protocol that anyone can join must also be one that anyone can use. Every participant therefore gets a **node console**: a quiet web page for people who do not program, a command line for operators, and an HTTP API with a Python client for developers. Each console runs on its owner's machine and controls only that machine, in the same way a full node's local RPC controls only that node.

**There is no official Nano-Commons server, and there never should be.**
- No one needs anyone else's console to take part.
- A mission owner creates keys and signs work on their own computer, and the private key never leaves it.
- A console offered to the public as "the" service would concentrate keys, canary answers and control in one operator's hands. The Governance Charter forbids exactly that.

When peer-to-peer networking arrives, the console becomes the local control panel of each participant's node daemon, one among many and never above any other.

---

## 5. The Nano-Agent

An agent travels as a signed packet:

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
  "parent_checkpoint_hash": "sha256:…",
  "payload": {
    "bias": 0.0,
    "memory_window": [],
    "crdt_clock": {},
    "observation_hash": "sha256:…",
    "assigned_workers": ["node-a", "node-b", "node-c"]
  },
  "signature": "ed25519:…"
}
```

**Signed as a whole.** The mission owner signs the canonical JSON of every field except the signature itself, using Ed25519. Changing any field breaks the signature, even by a single bit of a floating-point value. That includes the budget, the policy, the parent checkpoint and the hash of the input data.

**Bound to its input and its judges.** `observation_hash` commits the packet to the exact data it is meant to judge. A relay cannot swap the input after signing, and a probe cannot learn anything by feeding the packet fake inputs. `assigned_workers` can also commit the packet to the nodes that must judge it, so whoever carries the packet cannot pick friendlier judges.

**Bounded in life.**
- Each hop lowers `ttl` by one and takes a fixed cost from `energy_budget`.
- `freshness` decays, so stale knowledge loses influence unless it is re-validated.
- A host refuses packets whose TTL exceeds its own maximum, whose energy cannot cover the next hop, or whose knowledge is staler than it accepts.

**Simple in mind.** Inside a sandbox, the agent observes its input, applies its policy, decides, and records a bounded memory window and a conflict-free counter of who has run it.

---

## 6. Trust without trust

A volunteer network must assume that any node can be buggy, offline, compromised or hostile. Nano-Commons therefore earns trust through a pipeline of checks, each cheap and each explicit.

### 6.1 The host gate

Before any work runs, a node checks the packet in a fixed order: well-formed schema and payload types, matching `network_id`, TTL within bounds, energy sufficient for the hop, freshness above the minimum, a registered mission key, a valid signature, the input matching its committed hash, the workers matching any bound worker set, a parent equal to the current head of the knowledge chain, and a packet not seen before. A packet that fails any check is refused with a named reason.

### 6.2 Weighted K-node consensus

Each task goes to K independent workers (at least three non-quarantined nodes). Each vote is weighted by the worker's reputation `R ∈ [0, 1]`, and two rules stop concentration of power:

- **Zone cap.** No zone (a region, operator or network segment) can hold more than a set share of the vote, 50% by default. The cap is applied by water-filling: excess weight flows to other zones, and the cap still holds after redistribution. With a quorum of 65%, no single zone can approve anything on its own, whatever its reputation.
- **Quorum above one half.** The quorum must be strictly above 50%, so a split vote is never accepted.

### 6.3 Reputation that is earned and lost

| Event | Effect |
| :--- | :--- |
| Vote matches an accepted result or a canary's known answer | R +0.04, plus Compute Credits |
| First wrong vote | R −0.06 and a hashed entry in the fault log |
| Each later wrong vote | R −0.18, treated as confirmed poisoning |
| Vote splits without quorum | No change, so an attacker cannot force honest nodes into quarantine by splitting the vote |
| R below 0.10 | Quarantine: zero voting weight, no credits, but the node can recover by answering correctly |

The network sets penalties only from what it can observe. It never relies on a node's own claim about itself.

---

## 7. Truth over majority: canary tasks

Consensus has a blind spot. If a coordinated group holds enough weight, it decides what counts as correct. It is then rewarded for lying and honest nodes are punished for telling the truth. Every reputation system built only on agreement shares this weakness.

Nano-Commons closes the gap with **canary tasks**.

### 7.1 How a canary works

1. A verifier prepares an ordinary signed packet for a case whose correct answer is already known. The packet has no marker of any kind.
2. The verifier registers the expected answer privately with the network's audit layer.
3. Workers process the packet like any other task.
4. Each worker is scored against **the truth**, not the majority. A correct minority is rewarded. A wrong majority is penalised.

### 7.2 Auditing the knowledge chain

Every checkpoint records the workers that produced it and their weights at that moment. When a canary runs, it audits every checkpoint whose producers all took part:

- If that coalition, at the weights it held then, would have got the canary wrong, the checkpoint is **tainted**.
- Otherwise, a checkpoint not yet verified becomes **vouched**.

A taint is sticky. Once found out, a coalition cannot clean its record by behaving well later, because the audit uses the weight it held when it produced the checkpoint. Only rollback or an explicit, recorded operator review removes a taint, and later canaries never overturn an operator's review.

### 7.3 The alarm

If most of a canary's own vote weight answers wrong, the network raises an **alarm**:

- Ordinary tasks keep reaching workers, so the work stream does not reveal which tasks are canaries. Their results are **held**: no rewards, no penalties, no new checkpoints.
- Canaries continue, draining the reputation of nodes that keep failing them.
- The alarm clears only when **the nodes that failed**, judged among themselves at their current weight, answer a later canary correctly. An unrelated honest subset cannot clear the alarm, and neither can honest nodes padded in to dilute the coalition.
- The last fully vouched checkpoint marks a safe point to roll back to.

### 7.4 A worked example

In the reference testbed, two colluding nodes in different zones start with 70% of the vote weight, against two honest nodes. All numbers below come from running the reference implementation.

| Step | Event | Honest R | Colluder R | Alarm |
| :--- | :--- | ---: | ---: | :---: |
| 1 | Ordinary task: colluders win with the wrong answer (70%) | 0.24 | 0.74 | – |
| 2 | Canary: 76% of the weight is wrong; checkpoint 1 is tainted | 0.28 | 0.68 | raised |
| 3 | Ordinary task: runs, result held | 0.28 | 0.68 | on |
| 4 | Canary: 71% wrong | 0.32 | 0.50 | on |
| 5 | Canary: 61% wrong | 0.36 | 0.32 | on |
| 6 | Canary: 47% wrong, majority now correct | 0.40 | 0.14 | cleared |
| 7 | Tainted checkpoint 1 rolled back to the last trusted point | 0.40 | 0.14 | – |
| 8 | Ordinary task: the honest answer wins (74%) | 0.44 | 0.00 | – |

**Outcome.** Four canaries were enough to detect the coalition, contain it and remove it. The honest nodes ended with all the canary credit, the colluders were quarantined, and the false knowledge they wrote was removed from the chain.

---

## 8. Memory that can be corrected

- **Checkpoints.** Each accepted result is anchored in a SHA-256 hash chain. Each link names its predecessor, the packet it came from, the verdict, the producers and an audit status.
- **Rollback.** The chain can be cut back to any checkpoint. Packets that point at a superseded head are refused, and canaries prepared for it are dropped.
- **CRDT state.** Agent counters merge as grow-only counters (element-wise maximum), which give the same result in any order. Regions that worked apart converge when they reconnect.
- **Freshness.** Knowledge decays unless it is re-validated, so yesterday's assumptions lose their hold on today.

---

## 9. Economics: a commons, not a market

- **No token. No coin. No equity.** The protocol issues nothing that can be traded. Any project that offers a "Nano-Commons token" is not this project.
- **Compute and Priority Credits.** Contributors earn non-transferable credits for verified accuracy, never for volume. Credits buy priority on the network and nothing else.
- **Universal Basic Compute.** A fixed share of capacity is reserved, free, for individuals, schools, clinics, researchers and public-interest missions, including people who run no node at all.

The incentive is simple: help the network be right, and the network helps you.

---

## 10. Governance: owned by no one

The Nano-Commons Protocol was initiated by **Krittidet Chanthake** in November 2026 and dedicated from the start to the global public commons.

- **No master key.** The founder holds no veto, no kill switch and no special vote. The genesis author is credited for history and takes part on equal terms with every steward.
- **No central server.** The software gives each operator control of their own node only. No hosted service, foundation server or founder's machine stands between participants and the network.
- **Change by consensus only.** No change is adopted by vote, by majority or by anyone's say, the founder's included. Protocol changes are proposed as public Nano-Commons Proposals (NCPs). Each one goes through an open review window, a security and collusion impact assessment, and review by every active steward, and it is adopted only when no reasoned objection remains. A timelock then runs before it takes effect.
- **Everyone owns it.** Every contributor keeps the copyright in their own work under the same open licenses. There is no copyright assignment, so no one can ever take the commons private. On first publication, the initiator renounces every special right and keeps only what every contributor keeps.
- **Forkable by right.** Code is AGPLv3, so network services built on it stay open. Documents are CC BY-SA 4.0, so anyone may adapt them, crediting the initiator and contributors and sharing alike. Forks must use their own name and `network_id`, so that they never collide with or impersonate the commons network.
- **Harm refused at the protocol level.** Missions for cyberattack, unauthorised surveillance, data exfiltration or harm to people are rejected by network rules.
- **Local law respected.** Raw personal data stays where it was collected whenever possible. Each operator remains responsible under the law of their jurisdiction.

---

## 11. What is still open

A protocol that asks for trust must be candid about where it has not earned it yet. These problems are open, and they are where contributors are most needed.

| Open problem | Why it matters | Direction |
| :--- | :--- | :--- |
| **Sybil resistance** | One actor running thousands of nodes | Graduated reputation exists; latency and topology triangulation and web-of-trust vouching are next |
| **Adaptive attackers** | A coalition that answers canaries honestly while poisoning real work | Canaries drawn from the same distribution as real tasks, a secret canary rate, audit state hidden from workers |
| **Retroactive vouching** | A coalition that poisons a checkpoint and then answers canaries honestly can have that checkpoint vouched later | Re-validate checkpoint verdicts directly by replaying their tasks to fresh worker sets |
| **Worker assignment** | Unless packets bind their workers, a submitter chooses who judges | Bind `assigned_workers` on every packet, then move to mesh-assigned random workers |
| **Independent verifiers** | The answer key must not sit with one party | Canary issuance split across independent verifiers with threshold disclosure |
| **Per-hop signatures** | Forwarded copies are not re-signed today | Signed hop receipts that chain to the origin signature |
| **Real networking and sandboxing** | The testbed runs in one process | P2P gossip transport and a WebAssembly runtime with hard resource caps |
| **Penalty calibration** | An honest node that is wrong twice is treated like a poisoner | Calibration from real error rates during public testnets |

---

## 12. Roadmap

| Phase | Goal | Status |
| :--- | :--- | :--- |
| **0. Genesis** | Specification, packet format, verification rules | Complete |
| **1. Reference testbed** | Signed agents, host gate, weighted consensus, zone caps, reputation, canary audit, checkpoints, rollback, node console (web, CLI, API) | Python reference implementation complete; networking and sandboxing in progress |
| **2. First public mission** | Distributed environmental and disaster anomaly monitoring with real sensor feeds and public canary statistics | Next |
| **3. Commons federation** | Open participation for developers, institutions and volunteer nodes under NCP governance | Future |

---

## 13. An invitation

Intelligence does not have to be something people rent. It can be something they hold in common: small enough to run anywhere, careful enough to check itself, honest enough to admit what it does not yet know, and open enough that no one can take it away.

The reference implementation is open, and so are the specifications. Anyone can start a node console on their own machine in a minute. The remaining problems are listed above. If you can write code, run a node, design a canary, audit a protocol or bring a mission that matters to your community, there is a place for you here.

> *"I started this protocol, but I do not own it. No one will. That is the point."*
> **Krittidet Chanthake**, Initiator and Genesis Author, November 2026

---

*© 2026 Krittidet Chanthake and the Nano-Commons contributors. Licensed under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0). Published from Thailand.*
