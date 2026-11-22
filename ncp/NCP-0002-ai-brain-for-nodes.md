# NCP-0002: AI Brain for Nodes

| Field | Value |
| :--- | :--- |
| **Status** | Draft. Not yet proposed for consensus. |
| **Author** | Krittidet Chanthake |
| **Created** | 2026-11-22 |
| **Kind** | 3a: node-console feature (no protocol change). 3b and 3c: protocol changes (NCP process, GOVERNANCE.md §5.2) |
| **Depends on** | NCP-0001 (mini AI agent and verified learning); peer-to-peer transport (for 3b) |
| **License** | CC BY-SA 4.0 |

---

## 1. Motivation

People who run a node console should be able to **ask general questions and get help writing code** from an AI that:
- runs on their own computer,
- needs no company or subscription,
- keeps their questions private by default.

Today the protocol's agents are tiny, verifiable rules or models (NCP-0001). They cannot hold a conversation or write code. Large language models (LLMs) can, but usually only from a few central providers. That is exactly the dependency the Nano-Commons charter exists to avoid.

This proposal adds an **AI brain** to each node, using open-weight language models. It follows the same principles as the rest of the protocol:

1. **Start tiny and grow with demand.** A small model runs by default on an ordinary CPU. Larger models are optional, on machines that can afford them.
2. **Local first.** Questions and code stay on the user's machine unless the user chooses otherwise.
3. **Verify, don't trust.** When answers are shared or relied on, they are checked. Code is checked by tests run in a sandbox, and answers by canary questions with known answers.
4. **Improve only through verified updates.** A model update is adopted only if it does no worse on a held-out benchmark, as in NCP-0001.
5. **Humans decide.** The AI may propose changes to the project, but never merges, deploys or runs them by itself.

---

## 2. Scope

| Part | What | Protocol change? | Needs P2P? |
| :--- | :--- | :--- | :--- |
| **3a: Local brain** | The node console connects to a local LLM runtime and offers "Ask" and "Code" | No; console feature only | No |
| **3b: Verified answers** | Work is sent to several nodes; code is verified by sandboxed tests, answers by canaries | Yes | Yes |
| **3c: Verified self-improvement** | Opt-in feedback produces candidate model adapters, adopted only after verified evaluation | Yes | Partly |

---

## 3. Specification

### 3.1 The brain ladder

```text
User question or coding request
  │
  ▼
Tier 1: tiny local model (default)       fast, free, private
  │  escalate if: the user asks for it, the task is classified "hard",
  │               the output fails a local check, or tier 1 is overloaded
  ▼
Tier 2: larger local model (optional)    on capable machines only
  │  escalate if: the user requests verification (3b)
  ▼
Tier 3: verified by several nodes        code: sandboxed tests; answers: canary-scored brains
```

Escalation rules are local, deterministic and visible to the user. An answer **always shows which tier produced it** and whether it was verified.

### 3.2 Runtime connection (3a)

- The node console talks to an **OpenAI-compatible chat endpoint** provided by a separately installed runtime, such as llama.cpp's server or Ollama. Nano-Commons does not bundle model weights or inference code, so the project stays lightweight and its dependencies unchanged.
- The configuration is per node:
  - **endpoint URL**, which must be loopback by default; anything else requires an explicit flag and a warning
  - **model identifier**
  - **SHA-256 of the model file**
  - maximum tokens, timeout and concurrency limits
- **Model eligibility for the commons default.** The model's weights must be under an open license that allows free use and redistribution (for example Apache-2.0 or MIT). The exact list is kept in a reviewed allowlist (§3.6), and each entry is verified by hash.
- **External providers.** A node operator *may* configure a commercial API with their own key. It is off by default, it is clearly labelled **"external, not part of the commons"** in every answer, and it is never used for verification (3b) or for training data (3c).

### 3.3 Interfaces (3a)

| Surface | Addition |
| :--- | :--- |
| HTTP API | `POST /api/brain/ask` and `POST /api/brain/code` (operator token required), plus `GET /api/brain/status` (model, tier, hash and limits; never prompts) |
| CLI | `nano-commons ask "..."` and `nano-commons code "..." [--lang python]` |
| Web page | A plain "Ask" panel with the tier and verification status shown on each answer |
| Python client | Matching `ask()` and `code()` methods |

**Defaults**
- Prompts and answers are **not logged**.
- Generated code is **returned as text only** and is **never executed** by the console.
- Requests are subject to the existing body limit, the operator token and loopback binding.

### 3.4 Verified answers (3b)

| Task type | How it is verified |
| :--- | :--- |
| **Code with tests** | The request carries a test suite (by hash). Brain nodes propose candidate code. Verifier nodes run each candidate's tests in the sandbox (no network; CPU, memory and time caps) and vote on **pass or fail for a specific candidate hash**. A candidate is accepted only by the usual weighted, zone-capped quorum. |
| **Structured answers** (multiple choice, numeric, labels) | Votes are compared directly, as with any protocol task. Canary questions with known answers score each brain node's reputation. |
| **Free-text answers** | Not put to consensus. Shown with the producing tier and the brain node's canary accuracy, and labelled "unverified text". |

For consensus over structured answers, nodes must declare the **same model hash and decoding settings** (for example greedy decoding). Results across different hardware may still differ, which is why free text is never put to consensus.

### 3.5 Verified self-improvement (3c)

1. **Opt-in feedback only.** Users may mark answers as good or bad, or give a corrected answer. Feedback is stored **locally**. It leaves the device only if the user explicitly contributes it to a public dataset, after local removal of personal data, and under an open license.
2. **Candidate adapters.** Machines with enough capacity train small adapters (for example LoRA) for an allowlisted base model. Each adapter is identified by its hash and signed by its producer.
3. **Verified evaluation.** Several nodes run a fixed held-out benchmark in the sandbox: canary questions with known answers, and coding tasks with tests. They vote on the scores. A candidate is adopted **only if it does no worse than the current adapter on every benchmark category**. The benchmark items are never used for training.
4. **History and rollback.** Adopted adapters are versioned and hash-chained per base model, as with policies in NCP-0001, and can be rolled back.
5. **No self-modifying protocol.** AI output may be submitted as a pull request by a human, but changes to the project's code or rules follow GOVERNANCE.md, consensus of humans, without exception.

### 3.6 Model allowlist

- **Contents.** A reviewed file, `brains/allowlist.json`, lists each eligible base model: its name, license, file hash, size, recommended tier and known limits.
- **Changes.** Adding a model is a routine change if its license is clearly open and the hash is verified. Changing the **default** model is an NCP-level change.

---

## 4. Security and collusion impact

| Risk | Mitigation |
| :--- | :--- |
| **Prompt injection** (instructions hidden in user content or documents) | The brain has **no tools and no authority**. It cannot call node APIs, sign packets, change settings or run code, so its output is only text returned to the user. |
| **Malicious or backdoored model weights** | Hash-pinned allowlist; open weights only; models are never downloaded automatically from unlisted sources. |
| **Executing harmful generated code** | Never executed by the console. In 3b, it runs only in a sandbox with no network, a read-only filesystem and hard resource caps. |
| **Poisoned training (3c)** | Opt-in data; held-out benchmark; quorum of independent evaluators; reject anything that scores worse; rollback; zone caps against single-region capture. |
| **Benchmark gaming** | Benchmark items stay private to the verifiers until each evaluation is completed; a share of items is rotated; the same principles as for canaries (NCP-0001). |
| **Privacy (PDPA and similar laws)** | Local by default; no logging; explicit opt-in to share; local removal of personal data before any contribution. |
| **Resource exhaustion** | Concurrency, token and time limits; loopback binding; escalation only when capacity exists. |
| **Dependence on companies** | External APIs are opt-in, labelled, and excluded from verification and training. |
| **Model licence violations** | Allowlist with a licence review for every entry. |
| **Over-trust in AI answers** | Every answer shows its tier, its verification status and an "AI can be wrong" notice. Free text is always marked unverified. |

---

## 5. Compatibility and migration

- **3a is additive.** Consoles without a configured runtime behave exactly as today. No packet format changes.
- **3b and 3c add new task kinds and artefact types**, so they need protocol changes and will be specified in detail in follow-up NCPs once peer-to-peer transport exists.
- No changes to existing checkpoints, canaries or reputation rules.

---

## 6. Verification plan

- **3a**
  - Unit tests with a fake local endpoint: request shape, limits, timeouts, the external-provider label, and that no prompt is logged.
  - Tests that generated code is never executed.
  - Tests that a non-loopback endpoint is refused without the explicit flag.
- **3b**
  - Sandbox escape tests.
  - Code candidates that fail tests are rejected by consensus.
  - Brain nodes are scored with canary questions.
- **3c**
  - A worse adapter is rejected.
  - A poisoned adapter is rejected.
  - The held-out benchmark is never used in training.
  - Rollback restores the previous adapter.

---

## 7. Open questions

1. Which open model should be the default tier-1 brain? The candidates must be confirmed against the allowlist criteria, for licence, size and Thai-language quality.
2. Thai-language support: which small open models handle Thai well enough, and how should Thai be measured in the benchmark?
3. Sandbox technology for 3b: WebAssembly (WASI) runtimes, containers, or OS-level isolation. The choice affects which programming languages can be tested.
4. Who maintains the benchmark, and how is its secrecy protected in a commons (several independent verifiers, threshold disclosure)?

---

*This proposal follows GOVERNANCE.md. Under the bootstrap rule (§5.3), the protocol parts (3b and 3c) cannot be finalised until the project has at least 3 stewards from at least 2 unrelated organisations. Part 3a is a console feature and can be developed in the meantime.*
