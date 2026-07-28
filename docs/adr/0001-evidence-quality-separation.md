# ADR 0001: Separate exact, estimated, unknown, and not-applicable evidence

- Status: Accepted
- Date: 2026-07-28

## Context

A single numeric field makes missing usage look like zero and lets estimates appear provider-verified.

## Decision

Token and cost quality are independent enums. Exact values require receipt identity, estimates require an estimator source, unknown remains null, and not-applicable carries no measurement.

## Consequences

Definitive totals are smaller but trustworthy. Reports must show coverage, and incomplete exact coverage blocks savings claims.
