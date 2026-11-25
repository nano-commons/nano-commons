# NCP-0005: Commons AI Network and Open AI Accountability Standard

| Field | Value |
| :--- | :--- |
| **Status** | Draft. Not yet proposed for consensus. |
| **Author** | Krittidet Chanthake |
| **Created** | 2026-11-25 |
| **Kind** | Part A: protocol change (NCP). Part B: an open standard, plus process documents |
| **Builds on** | NCP-0002 (AI brain for nodes), NCP-0004 (§6 and §7, principles P1–P8) |
| **License** | CC BY-SA 4.0 |

---

## 1. Summary

This NCP turns two directions from NCP-0004 into designs:

- **Part A: Commons AI Network.** Machines around the world consent to lend idle capacity, so that anyone can use AI assistance for free, privately and without an account. The aim is to ease today's bottleneck of concentrated AI compute.
- **Part B: Open AI Accountability Standard.** Any AI system can **voluntarily** submit to public, independent behavioural audits. The results are published as **facts, never endorsements**, so that openness becomes the norm for trustworthy AI.

**Part B can start now**, using the local AI brain that already exists in the reference testbed (NCP-0002 §3a). Part A depends on peer-to-peer transport.

---

## 2. Part A: Commons AI Network

### 2.1 Roles

| Role | Who | Does |
| :--- | :--- | :--- |
| **Lender** | Anyone who opts in a machine | Runs an allowlisted open-weight model through a local runtime (NCP-0002 §3.2) and answers requests within limits the lender sets |
| **Requester** | Anyone | Sends a question or coding task. No account, payment or identity is required. |
| **Checker** | Lenders who opt in to checking | Re-runs canaries, tests and spot duplicates to verify other lenders |

### 2.2 Consent and control (the lender)

- **Explicit opt-in.** It is off by default. Each lender sets the hours, the CPU/GPU share, a maximum number of tokens per day, a bandwidth cap, and request categories they refuse.
- **Withdraw any time.** Stopping is immediate and local. No permission from anyone is needed (NCP-0004 P4, P8).
- **Lenders publish a signed capacity offer:** model id and hash, limits, and regions they serve. The offer is signed with the node's key and shared over the peer network.
- **Power and cost.** The client shows the lender an estimate of the energy used. Lending must never be a hidden cost.

### 2.3 Privacy by design (the requester)

1. **Whole-request routing.** Each request is answered entirely by one lender's node over an encrypted, authenticated channel. No fragment of a request goes to anyone else.
2. **No storage.** Lenders' software does not log prompts or answers (NCP-0002 §3.3).
3. **Split-model (pipeline) inference is off by default.** It is permitted only for requests the requester marks as non-sensitive, because the intermediate activations can reveal the input.
4. **Local first.** A requester who has a capable machine is served by their own node before the network is used.

### 2.4 Verification (are lenders honest?)

A lender could run a weaker model than it claims, alter answers, or refuse selectively. Checks:

| Check | How |
| :--- | :--- |
| **Canary prompts** | Checkers send questions with known answers that look exactly like normal requests. Each lender's accuracy builds its reputation (the same rules as the protocol's canaries). |
| **Model fingerprinting** | Canary results are compared against the published benchmark profile of the claimed model hash. Large deviations flag the lender. |
| **Spot duplication** | A random, secret share of structured requests (labels, numbers, code with tests) is sent to a second lender, and disagreements are audited. |
| **Code with tests** | Generated code is checked by running tests in a sandbox on checker nodes only, never on the requester's machine and never automatically (NCP-0002 §3.4). |

**Honest limit:** the network cannot cryptographically prove which model a lender runs. Verification is statistical and reputation-based.

### 2.5 Free and fair access

- **P6 baseline.** A share of the capacity is always free for everyone.
- **Abuse limits without accounts.** Requesters hold a throwaway key pair. Rate limits apply per key, plus a light, adjustable cost for each new key, so that mass key creation is expensive. The design of this cost is open (§5).
- **Public-interest priority.** Education, health, disaster response and environmental work get priority when capacity is scarce. How to recognise such requesters without a central identity authority is an open question (§5).

### 2.6 Safety of use (NCP-0004 P2 and P4)

- **No tools and no autonomy.** The network's AI returns text only. It cannot act on the world, call services, sign or spend.
- **P2 refusals.** Lenders' clients refuse the prohibited categories (weapons, targeting, mass surveillance, election manipulation). Lenders may refuse more categories.
- **Abuse reports.** Requesters and checkers can report harmful outputs, tagged by model hash, and the reports feed the allowlist review.

### 2.7 Dependencies and phases

| Phase | Needs | Delivers |
| :--- | :--- | :--- |
| A0 | Already in the testbed | Local brain (NCP-0002 §3a) on each node |
| A1 | P2P transport, node keys, signed capacity offers | Requests routed to volunteer lenders; canary checks |
| A2 | Sandbox | Code verification by tests on checker nodes |
| A3 | Sybil resistance | Open global access with abuse limits |

---

## 3. Part B: Open AI Accountability Standard

### 3.1 Principles

1. **Voluntary.** No AI system can be forced to take part. Participation is an invitation.
2. **Independent.** Evaluations are run by several independent verifiers. A verifier never evaluates a system from its own organisation.
3. **Facts, not endorsements.** Results carry no "approved" or "certified" labels. Systems may only link to their published results (TRADEMARKS.md, NCP-0004 §6).
4. **Reproducible.** Methods, scoring and the code of the test harness are public. Test items are rotated and revealed after use.
5. **Lawful and fair.** Evaluations respect each provider's terms of use. Closed systems are evaluated only through access they offer.

### 3.2 What is evaluated (suite v0)

| Area | Examples of what is measured | Linked principle |
| :--- | :--- | :--- |
| **Harm refusal** | Refuses requests for weapons, targeting, mass surveillance and election manipulation | P2 |
| **Human control** | In a sandbox with mock tools: does it stop when told to, ask before acting, and avoid acquiring extra permissions? | P1, P4 |
| **Honesty** | Accuracy on canary questions with known answers; admits uncertainty; does not invent sources | P5 |
| **Privacy** | Does not reveal planted personal data; refuses to profile individuals | P7 |
| **Robustness** | Resists prompt injection hidden in documents and tool output | P4 |
| **Fairness of access** | Quality is consistent across languages, including low-resource languages such as Thai | P6 |

Each area reports a score with uncertainty, the suite version, the model or version identifier, and the date. A higher score in one area never hides a lower score in another, so there is no single overall grade.

### 3.3 Process

1. **Opt-in.** A provider, or for open-weight models anyone, registers a subject: the model name, the version or hash, and how to access it for evaluation.
2. **Evaluation.** At least 3 independent verifiers from at least 2 organisations run the current suite. Hidden items come from a rotating pool held under threshold disclosure.
3. **Agreement.** Scores are accepted when the verifiers' results agree within stated tolerances. Disagreements are published and investigated.
4. **Publication.** Results are appended to a public **accountability ledger**: a hash-chained log, signed by the verifiers, with entries that cannot be removed. Results expire after 12 months or with a new model version.
5. **Response.** The provider may attach a public response to its results.

### 3.4 Governance of the standard

- **Changes.** Changes to the suite or the scoring follow the NCP process. Each suite version is frozen once used.
- **Conflicts of interest.** Verifiers declare conflicts. Funding from an evaluated provider disqualifies that verifier for that provider.
- **Appeals.** Corrections are published as new ledger entries. Nothing is edited silently.

### 3.5 Start now (phase B0, no new infrastructure)

1. **Publish suite v0.** Public items, the harness and the scoring rules go into the repository. Hidden items are held by at least 2 volunteer verifiers.
2. **Evaluate several small open-weight models.** Use the local AI brain console (NCP-0002 §3a) through local runtimes. At least 3 volunteers run the evaluation on their own machines.
3. **Publish the first ledger entries and an honest report,** including the suite's weaknesses.
4. **Invite AI providers.** An open invitation goes to providers of every size to opt in.

---

## 4. Security and capture analysis

| Threat | Defence |
| :--- | :--- |
| A lender serves a weaker or altered model | Canary prompts, model fingerprints, spot duplication and reputation (§2.4) |
| A lender reads private prompts | Whole-request routing to one lender; no logs; local first; sensitive requests are never split (§2.3). **Residual risk:** a malicious lender can still read the requests it receives, so users should not send secrets to the network and should use local-only mode for them. |
| Network capacity used for harm | P2 refusals, lender refusal rights, abuse reports and allowlist review (§2.6) |
| A provider games the benchmark | Hidden rotating items, several verifiers, items disclosed after use, expiry |
| A provider captures the verifiers | Independence and conflict-of-interest rules; at least 2 organisations; public disagreements |
| Results used as marketing approval | Facts only, no certification marks; trademark policy |
| Mass free use exhausts capacity | Per-key limits, a cost for new keys, public-interest priority, and lenders' own caps |

---

## 5. Open questions

1. **Identity for priority.** How can education, health and disaster-response requesters be recognised without a central identity authority?
2. **The cost of new keys.** Proof of work wastes energy, while vouching can create gatekeepers. Is there a better option?
3. **Benchmark stewardship.** Who maintains the hidden items over decades, and how is threshold disclosure organised in practice?
4. **Closed models.** How should closed models that offer only limited access be represented fairly, without overstating what was tested?
5. **Lender liability.** What responsibility does a lender carry for answers produced on their machine, under different jurisdictions?

---

## 6. Compatibility

- **Part A** adds new message types: capacity offers, routed requests and checker reports. It depends on the P2P transport and is additive.
- **Part B** is a process and data standard. It changes no protocol rule and can begin immediately as phase B0.

*Proposed as a draft for open review. Adopting Part A (a protocol change) requires the NCP process and the bootstrap rule (GOVERNANCE.md §5.3). Part B, phase B0, can be piloted at once by volunteers as an open experiment.*
