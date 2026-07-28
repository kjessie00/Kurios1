# Threat Model

## Assets protected

- production prompts, scripts, transcripts, and media content
- provider credentials and account routing
- customer, channel, and profile identifiers
- integrity of cost, token, cache, retry, and quality claims
- reproducibility of published audit artifacts

## Adversaries and failures

### Accidental sensitive-data ingestion

An adapter may attach a raw request, URL, filesystem path, environment, or credential. The recursive validator rejects forbidden keys, secret-like strings, URLs, and private paths before aggregation.

### Evidence inflation

A caller may label an estimate as exact or claim a cache hit from timing alone. Exact usage requires a receipt source and SHA-256 identity; cache hit/miss requires explicit evidence and receipt identity.

### Hidden or duplicate work

A pipeline may dispatch unplanned fallbacks, reuse work IDs incorrectly, or complete the same task more than once. Policy inventory and `dedupe_key` grouping surface these cases.

### Retry undercounting

A retry may overwrite the first attempt. The contract requires a new event ID and parent lineage for attempts after one.

### False quality economics

A pipeline may divide cost by every generated file, including rejected outputs. Only explicit artifact events accepted by a named gate count toward unit economics.

### Report tampering

A report file may be edited after generation. The SHA-256 manifest detects byte changes. The manifest is an integrity check, not a digital signature; trusted distribution should sign the manifest externally.

## Out of scope

- compromise of the host running the audit
- malicious or forged provider receipts that already satisfy the local shape
- correctness of external exchange-rate conversion
- quality or fairness of an external acceptance gate
- denial of service from unbounded file size in an untrusted multi-tenant service

## Recommended integration controls

- sign host receipts and verify them before creating public-kernel events
- enforce input-size and event-count limits at the service boundary
- isolate receipt collection credentials from the audit process
- version gate IDs and policy files
- retain immutable raw receipts in private storage; export only sanitized projections
- sign generated manifests for cross-system or external audit use
