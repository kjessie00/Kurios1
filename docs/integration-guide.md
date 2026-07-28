# Integration Guide

## 1. Define operation inventory first

List every logical model or agent operation, its stage, attempt budget, exact-cost budget, and allowed routes. Do not generate the policy from the observed calls after the run; that would turn a control into a description.

## 2. Emit one event per attempt

Create a call event before dispatch and finalize it from a provider or verified-host receipt. A retry gets a new `event_id`, increments `attempt`, and points to `parent_event_id`.

Use a stable SHA-256 `dedupe_key` derived from safe work fingerprints such as:

```text
schema version + operation ID + normalized input hash + policy version
```

Do not hash a mutable approval flag into a reusable creative-work key. Authorization should be checked live at dispatch.

## 3. Normalize receipts

Provider adapters should map official usage to the public event contract. When a field is unavailable, label it `unknown`; do not estimate silently. If estimating is useful, use `source=estimator` and keep it outside exact totals.

The public event's `receipt_sha256` identifies the private receipt after normalization. Keep the actual receipt in access-controlled storage.

## 4. Emit artifact decisions

After the external QA process finishes, emit an artifact event with:

- stable artifact ID and kind
- versioned gate ID
- accepted/rejected decision
- artifact SHA-256
- producer call IDs
- optional normalized quality score

## 5. Run the audit

```bash
media-economics-audit validate run.jsonl --policy policy.json
media-economics-audit audit run.jsonl --policy policy.json --out audit-output
media-economics-audit verify audit-output/manifest.sha256
```

Default automation fails with exit code 2 on high or critical findings. Use `--fail-on never` for exploratory reporting only.

## 6. Compare controlled runs

Use the same artifact IDs, artifact kinds, and gate IDs across baseline and candidate runs. Keep the test set and quality process stable.

```bash
media-economics-audit compare   baseline/audit.json   candidate/audit.json   --out comparison   --name provider-route-canary   --fail-on-regression
```

## 7. Store and publish safely

Private systems may retain signed raw receipts, prompts, and source artifacts. This kernel should receive only the sanitized public projection. Publish the generated bundle only after the security scan and manifest verification pass.

## Adapter checklist

- [ ] official usage fields mapped without reinterpretation
- [ ] exact receipt hash recorded
- [ ] cache evidence is explicit
- [ ] unknown values remain null/unknown
- [ ] no raw request or response body exported
- [ ] no account, profile, channel, or customer ID exported
- [ ] event and operation IDs are stable and non-sensitive
- [ ] retry lineage and dedupe key are deterministic
