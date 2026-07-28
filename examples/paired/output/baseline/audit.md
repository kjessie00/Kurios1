# AI Media Pipeline Economics Audit — `synthetic-baseline`

**Status:** `PASS`
**Evidence confidence:** `high`
**Source digest:** `7b4c76c606b145da2dcfc70bf7e672fc3b1e2d440dc9c70799135817d5c6a6ba`

## Executive scorecard

| Metric | Value |
|---|---:|
| Model/agent calls | 6 |
| Accepted artifacts | 2 |
| Artifact acceptance rate | 100.0% |
| Exact cost | 1.420000 USD |
| Estimated cost (kept separate) | 0.000000 USD |
| Calls with unknown cost | 0 |
| Exact cost coverage | 100.0% |
| Exact token coverage | 100.0% |
| Cost / accepted artifact | 0.710000 USD |
| Retry exact-cost ratio | 19.7% |
| Failed exact-cost ratio | 15.5% |
| Duplicate exact cost | 0.000000 USD |
| Exact non-cached input tokens | 52,500 |
| Known cache hit rate | 50.0% |

> Exact, estimated, and unknown measurements are intentionally not merged into a single total.

## Cost and token breakdown

### By stage

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `planning` | 1 | 1 | 0.200000 | 0.000000 | 0 | 6,000 |
| `qa` | 1 | 1 | 0.170000 | 0.000000 | 0 | 6,000 |
| `research` | 1 | 1 | 0.300000 | 0.000000 | 0 | 12,000 |
| `visual` | 1 | 1 | 0.250000 | 0.000000 | 0 | 8,000 |
| `writing` | 2 | 1 | 0.500000 | 0.000000 | 0 | 20,500 |

### By provider

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `openai` | 6 | 5 | 1.420000 | 0.000000 | 0 | 52,500 |

### By model

| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |
|---|---:|---:|---:|---:|---:|---:|
| `gpt-5.6-mini` | 1 | 1 | 0.170000 | 0.000000 | 0 | 6,000 |
| `gpt-5.6-pro` | 5 | 4 | 1.250000 | 0.000000 | 0 | 46,500 |

## Findings

No policy findings.

## Accepted artifacts

| Artifact | Kind | Gate | Quality score | SHA-256 |
|---|---|---|---:|---|
| `script-package` | `script` | `synthetic-quality-v1` | 0.910 | `fcea73e5d9eca008286f6178a9f875af32be8c82ee2c96f6da2c7dddc1cec629` |
| `visual-package` | `visual-plan` | `synthetic-quality-v1` | 0.900 | `098d6fe969830c009991b73fe6f6f3c282e6ad892368237371671a18ae2b9d29` |

## Interpretation boundary

This report audits supplied receipts and policy declarations. It does not infer provider prices, inspect prompts, or prove creative quality beyond the supplied quality-gate receipts.
