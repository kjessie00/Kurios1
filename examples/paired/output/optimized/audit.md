# AI Media Pipeline Economics Audit — `synthetic-optimized`

**Status:** `PASS`
**Evidence confidence:** `high`
**Source digest:** `8d2cd99f24cfd6690a77b49ccb292735389dec335fe75badb7c62fb6d225669e`

## Executive scorecard

| Metric | Value |
|---|---:|
| Model/agent calls | 5 |
| Accepted artifacts | 2 |
| Artifact acceptance rate | 100.0% |
| Exact cost | 0.790000 USD |
| Estimated cost (kept separate) | 0.000000 USD |
| Calls with unknown cost | 0 |
| Exact cost coverage | 100.0% |
| Exact token coverage | 100.0% |
| Cost / accepted artifact | 0.395000 USD |
| Retry exact-cost ratio | 0.0% |
| Failed exact-cost ratio | 0.0% |
| Duplicate exact cost | 0.000000 USD |
| Exact non-cached input tokens | 17,500 |
| Known cache hit rate | 100.0% |

> Exact, estimated, and unknown measurements are intentionally not merged into a single total.

## Cost and token breakdown

### By stage

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `planning` | 1 | 1 | 0.120000 | 0.000000 | 0 | 3,000 |
| `qa` | 1 | 1 | 0.100000 | 0.000000 | 0 | 2,000 |
| `research` | 1 | 1 | 0.180000 | 0.000000 | 0 | 4,000 |
| `visual` | 1 | 1 | 0.150000 | 0.000000 | 0 | 3,500 |
| `writing` | 1 | 1 | 0.240000 | 0.000000 | 0 | 5,000 |

### By provider

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `openai` | 5 | 5 | 0.790000 | 0.000000 | 0 | 17,500 |

### By model

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `gpt-5.6-mini` | 3 | 3 | 0.370000 | 0.000000 | 0 | 8,500 |
| `gpt-5.6-pro` | 2 | 2 | 0.420000 | 0.000000 | 0 | 9,000 |

## Findings

No policy findings.

## Accepted artifacts

| Artifact | Kind | Gate | Quality score | SHA-256 |
|---|---|---|---:|---|
| `script-package` | `script` | `synthetic-quality-v1` | 0.920 | `a6ac9066e8279f898c958da4c13848af40c018fa48f2d816209a1ab99bd0b4fa` |
| `visual-package` | `visual-plan` | `synthetic-quality-v1` | 0.910 | `4193422a200547c9df0ac6ec52432a3689a70a28544cc203a35b4ffd5faadaa0` |

## Interpretation boundary

This report audits supplied receipts and policy declarations. It does not infer provider prices, inspect prompts, or prove creative quality beyond the supplied quality-gate receipts.
