# ADR 0003: Keep the kernel deterministic, offline, and provider-neutral

- Status: Accepted
- Date: 2026-07-28

## Context

Live price tables, model calls, timestamps, and hosted dependencies make audits hard to reproduce and quickly stale.

## Decision

The runtime uses the Python standard library, performs no network calls, embeds no provider prices, emits no generated timestamps, and writes canonical JSON plus SHA-256 manifests.

## Consequences

Adapters and currency conversion remain outside the kernel. The same input and version produce byte-identical artifacts.
