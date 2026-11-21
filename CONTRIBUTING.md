# Contributing to the Nano-Commons Protocol

Everyone is welcome, and everyone who contributes becomes one of the project's owners. These are the rules, and they are the same for everyone, the initiator included.

## The short version

1. **Read [GOVERNANCE.md](GOVERNANCE.md).** Changes are adopted **only by consensus**.
2. **Sign off every commit** under the Developer Certificate of Origin (below): `git commit -s`.
3. **Keep the copyright in your work.** There is no copyright assignment and no CLA. You license your contribution under the project's licenses: AGPLv3+ for code, CC BY-SA 4.0 for documents.
4. **Follow the [Code of Conduct](CODE_OF_CONDUCT.md).**
5. **Report security problems privately** (see [SECURITY.md](SECURITY.md)).

## Kinds of contribution

| Kind | How it is decided ([GOVERNANCE.md §5.2](GOVERNANCE.md)) |
| :--- | :--- |
| Bug fixes, documentation, refactoring | Routine: 72-hour window, 1 steward review, no reasoned objection |
| Changes to protocol behaviour or defaults | An **NCP** (Nano-Commons Proposal): 14-day window, every active steward reviews, 14-day timelock |
| Changes to the charter, licenses, names or steward rules | Charter change: 30-day window, every active steward reviews, 30-day timelock |

**An objection (a "block") must give reasons** grounded in the charter, safety or evidence, and must say what would resolve it. If a block cannot be resolved, the change is not adopted. You are always free to fork under a different name and `network_id`.

While the project has fewer than 3 stewards from at least 2 unrelated organisations, only routine changes and security fixes can be adopted ([GOVERNANCE.md §5.3](GOVERNANCE.md)).

## Writing an NCP

Open a proposal titled `NCP-<number>: <title>` that covers:
1. **Motivation:** what problem it solves, and for whom.
2. **Specification:** exact rule changes, with references to `spec/`.
3. **Security and collusion impact:** how it could be abused, and what stops that.
4. **Compatibility and migration:** what changes for existing nodes and data.
5. **Verification:** how the change was checked, in steps that reviewers can repeat.

## Development setup

```bash
pip install -e .            # editable install with the `nano-commons` command
python -m nano_commons --help
```

The repository holds the protocol and the node console only; it ships no test suite or demo scripts. With every code change, describe in the pull request how you verified it (for example, the commands you ran and what they showed) so that reviewers can repeat the check. Keep changes small and focused, and keep each commit to one logical change.

Each source file begins with:

```text
SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (C) 2026 Krittidet Chanthake and the Nano-Commons contributors
```

Add your name to the copyright line of any file you change substantially, or rely on the commit history.

## Developer Certificate of Origin (DCO)

By adding a `Signed-off-by: Your Name <your@email>` line to each commit (`git commit -s`), you certify the following:

```text
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

## What this project will never accept

- A token, coin or any tradable financial instrument.
- A central server, master key or privileged account that controls the network.
- A license change that would let anyone take the commons private.
- Telemetry, or any collection of personal data, without explicit opt-in consent.

*This guide is licensed under CC BY-SA 4.0.*
