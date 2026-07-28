# Event and Policy Contract

The runtime validator is authoritative. Examples in this document are explanatory and do not override code.

## Call event

Every provider or verified-host attempt gets a unique call event. A retry never reuses an event ID.

Required top-level fields:

| Field | Meaning |
|---|---|
| `schema_version` | `media-economics-event.v1` |
| `event_type` | `call` |
| `event_id` | unique immutable attempt ID |
| `run_id` | bounded audit run |
| `operation_id` | logical work declared in policy |
| `stage` | pipeline stage declared in policy |
| `status` | `started`, `succeeded`, `failed`, `timed_out`, or `cancelled` |
| `provider`, `model` | safe identifiers, not account routes |
| `started_at`, `finished_at` | RFC3339; `finished_at` is null only while started |
| `attempt` | positive integer |
| `parent_event_id` | required when `attempt > 1` |
| `dedupe_key` | SHA-256 of stable logical work identity |
| `input_sha256`, `output_sha256` | optional content fingerprints |
| `usage` | token and cost evidence |
| `cache` | cache evidence |
| `tags` | at most 20 safe scalar labels |

### Usage evidence

`token_quality` and `cost_quality` are independent:

- `exact`: provider or verified-host receipt with SHA-256 identity
- `estimated`: an explicit estimator, never mixed into exact totals
- `unknown`: unavailable and never treated as zero
- `not_applicable`: measurement does not apply

Allowed `source` values are `provider_receipt`, `verified_host`, `estimator`, and `none`.

Exact or estimated token evidence requires non-negative input/output counts. Cached input cannot exceed total input. Exact cost requires a three-letter currency and non-negative decimal amount. Exact evidence requires `receipt_sha256`.

### Cache evidence

Allowed states: `hit`, `miss`, `bypass`, `unknown`, `not_applicable`.

A hit or miss needs an evidence source and receipt hash. Unknown and not-applicable states cannot carry evidence. Fast latency or empty usage is not cache evidence.

## Artifact event

An artifact event represents an external quality decision. This project does not perform that creative or media-quality judgment.

| Field | Meaning |
|---|---|
| `event_type` | `artifact` |
| `artifact_id` | stable output identity used in comparisons |
| `artifact_kind` | e.g. `script`, `audio`, `video` |
| `accepted` | result of the named gate |
| `gate_id` | versioned quality contract |
| `completed_at` | RFC3339 completion time |
| `artifact_sha256` | output fingerprint |
| `produced_by` | one or more call event IDs |
| `quality_score` | optional normalized score in `[0, 1]` |

An accepted artifact without a successful producer call is a high-severity finding.

## Policy

A policy declares the audit currency and operation inventory before economics are interpreted.

```json
{
  "schema_version": "media-economics-policy.v1",
  "audit_name": "shorts-canary",
  "currency": "USD",
  "minimum_exact_cost_coverage": 1.0,
  "minimum_exact_token_coverage": 1.0,
  "maximum_retry_cost_ratio": 0.2,
  "maximum_failed_cost_ratio": 0.1,
  "require_accepted_artifact": true,
  "operations": {
    "script-draft": {
      "stage": "writing",
      "required": true,
      "max_attempts": 2,
      "max_exact_cost": "1.000000",
      "allowed_providers": ["provider-a"],
      "allowed_models": ["model-a"]
    }
  }
}
```

The kernel does not infer missing policy. An undeclared call is a high-severity `UNPLANNED_OPERATION` finding.

## Forbidden content

Inputs fail closed when they contain raw prompts, responses, scripts, transcripts, URLs, absolute/private paths, commands, environments, credentials, cookies, authentication material, or account/customer/channel identifiers.

Use safe IDs, counts, normalized labels, and SHA-256 fingerprints instead.
