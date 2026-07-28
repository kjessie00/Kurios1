# Security Policy

## Supported versions

Security fixes are applied to the latest released minor version. During the `0.x` phase, only the current `main` branch and newest tagged release are supported.

## Reporting a vulnerability

Do not open a public issue containing credentials, private receipts, customer data, exploit payloads, or a reproducible secret-leak path.

Use GitHub's **Security → Report a vulnerability** flow when it is available. If private vulnerability reporting is unavailable, contact the maintainer through the GitHub profile and disclose only enough information to establish a private channel.

A useful report contains:

- affected version or commit
- threat scenario and impact
- minimal reproduction using synthetic data
- whether the issue can expose raw payloads, credentials, private paths, or falsified evidence
- a proposed mitigation, when known

## Security invariants

A change is security-sensitive when it can:

- admit a raw prompt, response, transcript, script, credential, URL, or private path
- label estimated or unknown usage as exact
- accept a cache hit/miss without receipt-backed evidence
- allow a manifest to verify after a tracked file changes
- let an artifact count as accepted without a successful producer call
- weaken operation allowlists, attempt budgets, or evidence-quality rules

Security fixes should add an adversarial regression test before release.
