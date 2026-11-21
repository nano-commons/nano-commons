# Governance & Commons Charter

**Version:** 0.2 (November 2026)
**Initiator / Genesis Author:** Krittidet Chanthake
**Principle:** *Owned by everyone. Controlled by no single party. Changed only by consensus.*

---

## 1. Everyone owns it; no one controls it

**The Nano-Commons Protocol** was initiated by **Krittidet Chanthake** in November 2026 and dedicated from the start as an open, non-profit public good for humanity. It has no owner, CEO, shareholder or commercial proprietor.

- **Shared ownership.** Every contributor keeps the copyright in their own contributions and licenses them under the project's licenses (§2). There is no copyright assignment and no CLA. No single person or organisation, the initiator included, can therefore ever relicense the commons as a closed product.
- **No sole control.** Neither the initiator nor any early contributor holds a veto beyond that of any other steward, a kill switch, a master key or a central server.
- **No commercial capture.** No one may enclose the protocol rules, public knowledge snapshots or governance authority behind proprietary walls or speculative financial instruments.
- **Forkable by right.** Anyone may fork under the project's licenses. A fork must use its own name and its own `network_id`, so that it never collides with or impersonates the commons network (see [TRADEMARKS.md](TRADEMARKS.md)).

### 1.1 The initiator's renunciation

When the project is first published, the initiator, Krittidet Chanthake, renounces every special right over it, effective immediately:

1. **No veto or control.** No veto, no casting vote, no reserved seat and no control over the project beyond those of any other steward.
2. **Assets handed to the commons.** No ownership of the name, domains, repositories or other project assets. Whatever the initiator holds at publication is held only as a temporary custodian under §7, until custody passes to other stewards or a non-profit body by consensus.
3. **No private benefit.** No private claim on the project's results, credits or reputation, and no private benefit from the project that is not equally open to everyone under the same rules.

**What the initiator keeps.** The initiator keeps only what every contributor keeps: the copyright in their own contributions, licensed to everyone under the same open licenses (§2), and the credit of being named as initiator. The copyright is kept, not waived, because it is what lets the open licenses be enforced, so that nobody can ever take the commons private.

Everyone may use, study, change and share the protocol fully, under the same rules as the initiator.

---

## 2. Licenses

- **Code:** GNU AGPLv3 or later, with the additional terms in [NOTICE](NOTICE) (attribution preserved; no trademark rights granted). Anyone who runs a modified version as a network service must publish its source code.
- **Specifications, whitepaper, governance and other documents:** Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0). Anyone may use, adapt and share them, including commercially, provided they credit the initiator and contributors and keep adaptations under the same license.

Details: [LICENSES.md](LICENSES.md).

---

## 3. Non-profit and anti-speculation mandate

- **No speculative assets.** The project issues no tradable tokens, equity or financial securities, and never will.
- **Utility-only credits.** Credits earned for compute or verification cannot be transferred outside the protocol. They only set compute priority and guard against abuse.
- **Public good first.** A baseline share of network capacity is permanently reserved for free public, educational, research, humanitarian and environmental use.

---

## 4. Roles in the commons

Participation is open, and standing is earned through verifiable contribution.

1. **Initiator (Genesis Author):** Krittidet Chanthake. Credited permanently as the creator of the initial specification, with equal standing to every other steward.
2. **Contributors:** anyone who submits issues, patches, tests, documentation, reviews or security reports.
3. **Node operators and verifiers:** anyone who runs a node console, executes tasks or issues and checks canaries.
4. **Stewards:** contributors entrusted with reviewing changes, coordinating releases and recording consensus. Stewards are listed in [STEWARDS.md](STEWARDS.md).

### 4.1 Becoming a steward

- Any contributor may be proposed as a steward, by themselves or by others, through a public proposal.
- Stewards are added or removed by the same consensus process as any other change (§5). Removal only covers inactivity of 6 months or more, or a breach of this charter or the Code of Conduct.

---

## 5. Decisions: consensus only

**Every change to the protocol, the code, the specifications, this charter or the project's assets is adopted only by consensus.** No change is ever adopted by voting, by majority, by seniority or by the initiator's say.

### 5.1 What consensus means

A proposal reaches consensus when **all three** of these are true:
1. It has been public for its full review window (§5.2).
2. It has been reviewed by the number of stewards required for its kind (§5.2).
3. No steward holds an **unresolved, reasoned objection** (a "block").

**Blocks**
- A block must state its reasons, grounded in this charter, in safety and security, or in evidence.
- A block must also say what change would resolve it.
- A block without reasons is void.

**Resolving a block**
- The proposer and the blocking steward work in public to resolve it.
- If they cannot, the proposal is **not adopted** and the current state stays in place.
- Anyone remains free to fork (§1).

### 5.2 Kinds of change

| Kind | Examples | Review window | Required reviewers | Timelock after consensus |
| :--- | :--- | :--- | :--- | :--- |
| **Routine** | Bug fixes, documentation, refactoring with no behaviour change | 72 hours | 1 steward other than the author | None |
| **Security fix** | A fix for a reported vulnerability | May be prepared privately (see [SECURITY.md](SECURITY.md)) | 2 stewards | Published, with full disclosure, once released |
| **Protocol change (NCP)** | Packet format, verification, scoring, canary rules, defaults | 14 days | Every active steward, or a written "no objection" | 14 days |
| **Charter change** | This document, licenses, trademark policy, steward rules | 30 days | Every active steward, or a written "no objection" | 30 days |

**NCPs (Nano-Commons Proposals)** are public documents. Each one states the motivation, the specification, a security and collusion impact assessment, and a migration plan.

### 5.3 Bootstrap rule

Until there are **at least 3 stewards from at least 2 unrelated organisations or communities**:
- **Allowed:** routine changes and security fixes.
- **Not allowed:** finalising protocol changes, charter changes, or decisions about the project's name, domains and trademarks.

This rule exists so that the initiator can never decide important matters alone, not even at the start.

### 5.4 Record keeping

- **Consensus records.** Every consensus decision is recorded publicly with the proposal, the reviewers, any blocks and how they were resolved, and the date of adoption.
- **Signed releases.** Releases are signed, and their checksums are published.

---

## 6. Security, privacy, cross-border law and accountability

- **Mandatory bounds.** All agent execution must enforce resource caps, isolation and finite time to live.
- **Privacy and jurisdiction.**
  - Raw personal or sensitive data should stay local wherever possible.
  - Each node operator and user is responsible for following the law of their own jurisdiction, including data protection, cybersecurity and export rules.
  - No central entity takes on legal liability for independent node actions.
- **Harm prevention.** Missions for cyberattack, unauthorised surveillance, data exfiltration or harm to people are refused by network rules.
- **No central server.** Project software gives each operator control of their own node only. No hosted service, foundation server or founder's machine may stand between participants and the network.
- **Public auditability.** Governance actions, consensus records, signed release hashes and verification rules stay open to public inspection.

---

## 7. Name and assets held in trust

- **Held in trust.** The project name, domains, repositories and any future trademark registrations belong to the commons. Whoever holds them does so only as a custodian for the community.
- **Organisation accounts.** Repositories live in organisation accounts with at least two owners.
- **Transfer and use.** Transfers and use policies follow §5 (charter change). Custody is to move to a non-profit body once one is agreed by consensus.

See [TRADEMARKS.md](TRADEMARKS.md).

---

## 8. Amending this charter

This charter exists to protect the public-commons nature of the Nano-Commons Protocol. It may be amended only through §5 as a **charter change**, and only when the change strengthens openness, safety and resilience for humanity.

---

*This charter is licensed under CC BY-SA 4.0. © 2026 Krittidet Chanthake and the Nano-Commons contributors.*
