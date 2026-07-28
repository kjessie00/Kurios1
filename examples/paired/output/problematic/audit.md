# AI Media Pipeline Economics Audit — `synthetic-problematic`

**Status:** `FAIL`
**Evidence confidence:** `low`
**Source digest:** `7d4189ffda1a714d4d3858e29d2759eb118a282aa38b498ab1e13e247e10e498`

## Executive scorecard

| Metric | Value |
|---|---:|
| Model/agent calls | 3 |
| Accepted artifacts | 1 |
| Artifact acceptance rate | 100.0% |
| Exact cost | 0.000000 USD |
| Estimated cost (kept separate) | 0.000000 USD |
| Calls with unknown cost | 3 |
| Exact cost coverage | 0.0% |
| Exact token coverage | 0.0% |
| Cost / accepted artifact | N/A |
| Retry exact-cost ratio | 0.0% |
| Failed exact-cost ratio | 0.0% |
| Duplicate exact cost | 0.000000 USD |
| Exact non-cached input tokens | 0 |
| Known cache hit rate | N/A |

> Exact, estimated, and unknown measurements are intentionally not merged into a single total.

## Cost and token breakdown

### By stage

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `research` | 3 | 3 | 0.000000 | 0.000000 | 3 | 0 |

### By provider

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `openai` | 3 | 3 | 0.000000 | 0.000000 | 3 | 0 |

### By model

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `gpt-5.6-pro` | 3 | 3 | 0.000000 | 0.000000 | 3 | 0 |

## Findings

### [HIGH] ATTEMPT_BUDGET_EXCEEDED

**Operation exceeded its attempt budget**

Operation research used 2 attempts; budget is 1.

**Evidence:** `p-call-1`, `p-call-2`

**Remediation:** Add a stop-loss or require a fresh approval before further retries.

### [HIGH] DUPLICATE_SUCCESSFUL_WORK

**The same logical work succeeded more than once**

Dedupe key 81f358c07625… has 2 successful calls; recorded extra exact cost is 0.000000 USD. 1 duplicate call(s) lack exact cost, so total duplicate cost is not proven.

**Evidence:** `p-call-1`, `p-call-2`

**Remediation:** Acquire an idempotency lease before dispatch and bind completion to the dedupe key.

### [HIGH] EXACT_COST_COVERAGE_LOW

**Too few calls have exact cost receipts**

Coverage is 0.0%; policy requires 100.0%.

**Evidence:** `p-call-1`, `p-call-2`, `p-call-3`

**Remediation:** Ingest provider or verified-host receipts; do not relabel estimates as exact.

### [HIGH] EXACT_TOKEN_COVERAGE_LOW

**Too few calls have exact token receipts**

Coverage is 0.0%; policy requires 100.0%.

**Evidence:** `p-call-1`, `p-call-2`, `p-call-3`

**Remediation:** Capture provider usage fields or label the measurement as estimated/unknown.

### [HIGH] REQUIRED_OPERATION_MISSING

**Required operation did not produce a call receipt**

Required operation qa-review is absent from the event ledger.

**Evidence:** `qa-review`

**Remediation:** Ingest the missing receipt or fail the pipeline before claiming completion.

### [HIGH] UNPLANNED_OPERATION

**Model call was not declared in the policy**

Operation hidden-review executed 1 call(s) without a declared budget.

**Evidence:** `p-call-3`

**Remediation:** Declare the operation and budget before dispatch, or remove the hidden call.

## Accepted artifacts

| Artifact | Kind | Gate | Quality score | SHA-256 |
|---|---|---|---:|---|
| `weak-output` | `script` | `synthetic-quality-v1` | 0.700 | `44a105f55690dfcc5db932231dda1899a0d28cb4e915141cd64b32709839d229` |

## Interpretation boundary

This report audits supplied receipts and policy declarations. It does not infer provider prices, inspect prompts, or prove creative quality beyond the supplied quality-gate receipts.
