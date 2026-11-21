# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately using the repository's **"Report a vulnerability"** feature (private security advisories) on the official repository listed in [TRADEMARKS.md](TRADEMARKS.md#official-channels). If that is not available, contact any steward privately using the details in [STEWARDS.md](STEWARDS.md).

Please include:
- the affected version or commit,
- the steps to reproduce,
- the impact (for example a signature bypass, canary leakage, a consensus capture, a token or key leak, or a crash of a node console),
- any suggested fix.

## What happens next

1. **Acknowledgement:** a steward acknowledges the report within 7 days.
2. **Fix:** at least two stewards prepare and review the fix privately ([GOVERNANCE.md §5.2](GOVERNANCE.md), "Security fix").
3. **Disclosure:** the fix is released with a public advisory that credits the reporter, unless they prefer otherwise. The target is 90 days or less from the report.

## Scope

Reports are in scope if they affect the protocol rules or the reference implementation in this repository: packet signing and verification, the admission gate, consensus and reputation, canary handling, checkpoints, and the node console (web page, CLI, HTTP API).

Out of scope:
- The known limits listed in [WHITEPAPER.md §11](WHITEPAPER.md#11-what-is-still-open) and the [threat model](spec/SECURITY_AND_THREAT_MODEL.md#4-known-residual-risks), unless you show a concrete new attack.
- Problems that only occur when a console is deliberately exposed to the internet without TLS, against the documented guidance.

## No bounties, no tokens

The project has no money and issues no tokens. Reporters are credited publicly. Anyone who offers a "bounty" in a token on the project's behalf is not affiliated with it.

*This policy is licensed under CC BY-SA 4.0.*
