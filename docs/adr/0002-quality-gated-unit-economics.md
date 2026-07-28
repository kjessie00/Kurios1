# ADR 0002: Count only quality-accepted artifacts in unit economics

- Status: Accepted
- Date: 2026-07-28

## Context

Dividing spend by every generated file rewards low-quality volume and hides rejection cost.

## Decision

An external, versioned gate emits an artifact receipt. Only `accepted=true` artifacts count in the denominator. Accepted artifacts must reference at least one successful producer call.

## Consequences

The kernel does not claim to judge creativity. Integrators must keep gate contracts stable for comparisons.
