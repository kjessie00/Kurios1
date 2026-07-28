# Architecture

## Goal

The kernel answers one bounded question:

> Given a reviewed operation policy, receipt-backed model calls, and quality-gate artifact receipts, what exact costs and waste patterns can be proven?

It does not orchestrate providers or judge creative quality. Those remain private integration responsibilities.

## Data flow

```text
provider / verified host / estimator
             |
             v
      call receipt JSONL  ---- reviewed policy JSON
             |                       |
             +----------+------------+
                        v
                 strict validator
                        |
                        v
                 deterministic audit
          +-------------+-------------+
          |             |             |
          v             v             v
      audit.json     audit.md    manifest.sha256
          |
          +--------------------+
                               v
                 baseline/candidate compare
                               |
                               v
          comparison.json / .md / manifest
```

## Components

### `schema.py`

Owns all input contracts and the public-data boundary. Unknown fields fail closed. Raw payload fields, secret-like values, URLs, and private paths are rejected recursively.

### `metrics.py`

Reduces validated events into economics and findings. It never reaches a provider, reads a pricing table, or converts currency.

### `report.py`

Produces canonical JSON, stable Markdown, and SHA-256 manifests. Generated timestamps are intentionally absent so the same input produces identical bytes.

### `engine.py`

Coordinates file loading, audit generation, and paired comparisons. A comparison is `IMPROVED` only with complete exact-cost evidence and a preserved quality floor.

### `cli.py`

Provides validation, audit, comparison, and manifest verification commands with automation-friendly exit codes.

## Trust boundaries

1. **Producer boundary:** provider adapters or verified hosts create receipts. This project does not trust narrative claims from an agent.
2. **Ingestion boundary:** the strict validator rejects unsupported or unsafe content before aggregation.
3. **Policy boundary:** allowed operations, providers, models, attempts, and cost budgets are reviewed before dispatch.
4. **Artifact boundary:** only explicit quality-gate receipts count as accepted output.
5. **Publication boundary:** outputs contain IDs, hashes, safe measurements, findings, and policy snapshots—not source media or prompts.

## Determinism

Canonical JSON uses UTF-8, sorted keys, compact separators, and one terminal newline. Manifests hash the report files by relative name. Input order is preserved in the source digest, while report collections use stable sorting where order has no semantic meaning.

## Deployment pattern

The recommended deployment is an embedded library or sidecar step after receipt collection:

```text
private pipeline -> sanitized receipts -> audit kernel -> private dashboard / CI gate
```

The kernel can run offline and needs no secret.
