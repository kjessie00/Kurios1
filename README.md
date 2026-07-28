# AI Media Pipeline Economics Audit

**Know what each accepted media artifact really costs — without storing prompts, responses, credentials, or customer content.**

AI media pipelines often report model spend, token counts, cache rates, retries, and quality in separate systems. That makes a cheap but rejected artifact look efficient, lets unknown costs appear as zero, and hides duplicate successful calls. This project turns provider or verified-host receipts into a deterministic audit bundle centered on one business metric:

> **Exact cost per quality-accepted artifact**

The repository is an independently authored public kernel. It is not a copy of a production media factory and contains no channel-specific prompts, upload logic, browser sessions, customer data, or provider credentials.

[한국어 안내](README.ko.md)

## What it proves

- Exact, estimated, unknown, and not-applicable evidence remain separate.
- Cache hit/miss claims require evidence and a receipt SHA-256.
- Each retry is an immutable attempt linked to its parent.
- Stable `dedupe_key` values expose duplicate successful work without storing prompts.
- Declared operations have provider, model, attempt, and exact-cost budgets.
- Artifacts count toward unit economics only after a named quality gate accepts them.
- JSON, Markdown, and SHA-256 manifests are byte-reproducible.

## Five-minute demo

No API key or network call is required.

```bash
git clone https://github.com/kjessie00/Kurios1.git ai-media-pipeline-economics-audit
cd ai-media-pipeline-economics-audit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

media-economics-audit audit \
  examples/paired/baseline.jsonl \
  --policy examples/paired/baseline-policy.json \
  --out build/baseline \
  --fail-on never

media-economics-audit audit \
  examples/paired/optimized.jsonl \
  --policy examples/paired/optimized-policy.json \
  --out build/optimized \
  --fail-on never

media-economics-audit compare \
  build/baseline/audit.json \
  build/optimized/audit.json \
  --out build/comparison \
  --name local-demo

media-economics-audit verify build/comparison/comparison-manifest.sha256
```

The bundled **synthetic** paired fixture produces:

| Metric | Baseline | Candidate | Change |
|---|---:|---:|---:|
| Exact cost | 1.420000 USD | 0.790000 USD | −44.4% |
| Accepted artifacts | 2 | 2 | unchanged |
| Cost / accepted artifact | 0.710000 USD | 0.395000 USD | −44.4% |
| Non-cached input tokens | 52,500 | 17,500 | −35,000 |
| Retry exact-cost ratio | 19.7% | 0.0% | −19.7 percentage points |

This is a test fixture, **not a production savings claim**. A real claim requires complete exact-cost receipts and preserved quality-gate contracts on both sides.

See the tracked, reproducible output:

- [`examples/paired/output/comparison/comparison.md`](examples/paired/output/comparison/comparison.md)
- [`examples/paired/output/baseline/audit.md`](examples/paired/output/baseline/audit.md)
- [`examples/paired/output/optimized/audit.md`](examples/paired/output/optimized/audit.md)
- [`examples/paired/output/problematic/audit.md`](examples/paired/output/problematic/audit.md)

## Commands

```text
media-economics-audit validate EVENTS.jsonl [--policy POLICY.json]
media-economics-audit audit EVENTS.jsonl --policy POLICY.json --out OUTPUT_DIR
media-economics-audit compare BASELINE_AUDIT.json CANDIDATE_AUDIT.json --out OUTPUT_DIR
media-economics-audit verify MANIFEST.sha256
```

Exit codes:

| Code | Meaning |
|---:|---|
| 0 | Valid command; no configured failure threshold reached |
| 2 | Audit threshold reached, comparison regressed/inconclusive, or manifest failed |
| 3 | Unsafe or invalid input |

## Evidence contract at a glance

A call receipt contains fingerprints and measurements, never raw payloads:

```json
{
  "schema_version": "media-economics-event.v1",
  "event_type": "call",
  "event_id": "call-001",
  "run_id": "run-001",
  "operation_id": "script-draft",
  "stage": "writing",
  "status": "succeeded",
  "provider": "provider-a",
  "model": "model-a",
  "started_at": "2026-07-28T00:00:00Z",
  "finished_at": "2026-07-28T00:00:05Z",
  "attempt": 1,
  "parent_event_id": null,
  "dedupe_key": "<sha256>",
  "input_sha256": "<sha256>",
  "output_sha256": "<sha256>",
  "usage": {
    "token_quality": "exact",
    "cost_quality": "exact",
    "source": "provider_receipt",
    "input_tokens": 1000,
    "cached_input_tokens": 800,
    "output_tokens": 100,
    "reasoning_tokens": 20,
    "cost_amount": "0.020000",
    "currency": "USD",
    "receipt_sha256": "<sha256>"
  },
  "cache": {
    "status": "hit",
    "evidence_source": "provider_receipt",
    "key_sha256": "<sha256>",
    "receipt_sha256": "<sha256>"
  },
  "tags": {"lane": "production"}
}
```

The validator rejects raw prompts, responses, scripts, transcripts, URLs, private paths, credentials, cookies, and account/customer identifiers. Read the full [event contract](docs/event-contract.md).

## What the audit catches

- unknown costs presented as zero
- evidence-free cache claims
- incomplete call attempts
- unplanned or hidden model operations
- undeclared provider/model fallback
- attempt and per-operation budget overruns
- duplicate successful work sharing one `dedupe_key`
- artifacts referencing missing or unsuccessful producer calls
- pipelines with spend but no accepted artifact
- low exact-cost or exact-token coverage
- excessive retry and failed-call cost ratios

## Design boundaries

This project deliberately does **not**:

- embed provider price tables
- estimate exchange rates
- store prompts or responses
- judge creative quality by itself
- call model or media APIs
- upload or publish media
- provide a hosted dashboard

Those decisions keep the kernel portable, auditable, and safe to embed in private production systems. See [public/private boundary](docs/public-private-boundary.md).

## Development

```bash
make check
```

`make check` performs compile checks, adversarial/unit tests, byte-reproducibility verification, and a public-boundary secret/private-path scan.

The runtime package has no third-party dependency. CI tests Python 3.11, 3.12, and 3.13.

## Documentation

- [Architecture](docs/architecture.md)
- [Event and policy contract](docs/event-contract.md)
- [Audit methodology](docs/methodology.md)
- [Threat model](docs/threat-model.md)
- [Integration guide](docs/integration-guide.md)
- [Public/private boundary](docs/public-private-boundary.md)
- [Roadmap](docs/roadmap.md)
- [ADRs](docs/adr/)

## Status

`v0.1.0` is an alpha public kernel. The contract is intentionally small and strict. Backward-incompatible schema changes will use a new schema version rather than silently changing the meaning of old receipts.

## License

Apache License 2.0. See [LICENSE](LICENSE).
