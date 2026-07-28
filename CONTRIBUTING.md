# Contributing

Contributions are welcome when they preserve the project's evidence semantics and public/private boundary.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
make check
```

The runtime package intentionally has no third-party dependency. A new dependency needs a written reason, license review, and evidence that the standard library cannot meet the requirement safely.

## Design rules

1. Unknown is never zero.
2. Estimated and exact values are never merged into one definitive total.
3. A cache claim needs verifiable evidence.
4. Retry attempts use new event IDs and link to a parent.
5. Unit economics require a named, accepted artifact gate.
6. Reports must be deterministic and manifest-verifiable.
7. Public inputs and outputs must not contain raw media content, prompts, credentials, URLs, or private paths.
8. A schema meaning never changes silently; introduce a new schema version.

## Pull requests

Keep changes focused and include:

- the problem and failure mode
- the contract or invariant affected
- tests for valid and adversarial inputs
- `make check` output
- regenerated example artifacts when report output changes
- migration notes for schema or CLI changes

Do not commit real provider receipts, customer traces, API keys, browser state, or production prompts. Use deterministic synthetic fixtures.

## Issue reports

Include the command, sanitized input shape, expected result, actual result, and version. Use `SECURITY.md` instead of a public issue for anything sensitive.
