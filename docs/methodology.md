# Audit Methodology

## Measurement classes

The audit keeps four evidence classes separate:

| Class | Interpretation | Included in definitive totals? |
|---|---|---|
| exact | receipt-backed value | yes |
| estimated | explicit estimator | shown separately |
| unknown | not measured | no; never zero |
| not applicable | metric does not apply | no |

## Primary unit metric

```text
exact cost per accepted artifact = total exact call cost / accepted artifact count
```

The metric is published only when:

1. at least one artifact is accepted, and
2. exact-cost coverage is 100% for the run.

Otherwise the value is `N/A`. This avoids a partially measured run looking artificially cheap.

## Token metrics

For exact token receipts:

```text
non-cached input tokens = max(0, input tokens - cached input tokens)
```

Estimated and unknown token events are counted for coverage but not merged into exact token totals.

## Waste signals

- **retry exact cost:** exact cost of attempts numbered greater than one
- **failed exact cost:** exact cost of failed, timed-out, or cancelled calls
- **duplicate exact cost:** exact cost of successful calls after the first success for one `dedupe_key`
- **hidden work:** calls whose operation is absent from policy
- **budget drift:** attempts, provider/model route, stage, or exact cost outside policy

These are diagnostic categories and can overlap. They must not be added together as a single “waste total” without a separate de-duplication model.

## Coverage

```text
exact cost coverage = exact-cost call count / all call count
exact token coverage = exact-token call count / all call count
```

A started or otherwise incomplete call remains in the denominator. Missing evidence is part of the economic risk, not something to hide from coverage.

## Finding status

- `PASS`: no findings
- `WARN`: findings exist, but none are high or critical
- `FAIL`: at least one high or critical finding

The CLI's `--fail-on` option can apply a stricter automation threshold.

## Comparison rule

A candidate is labeled `IMPROVED` only when all conditions hold:

1. both audits have 100% exact-cost coverage
2. candidate exact cost is lower
3. every baseline accepted artifact ID, kind, and gate ID exists in the candidate
4. candidate quality scores do not fall below corresponding baseline scores
5. accepted artifact count and acceptance rate do not decrease
6. high and critical finding counts do not increase

If exact coverage is incomplete, the comparison is `INCONCLUSIVE`. If cost rises or the quality floor breaks, it is `REGRESSED`.

## What the method does not prove

The audit does not prove that a gate is well designed, that a provider receipt is cryptographically authentic, or that two artifacts are semantically equivalent beyond the supplied IDs, gate versions, hashes, and scores. Integrators own receipt signing, gate validity, and experiment design.
