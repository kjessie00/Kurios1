from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .schema import AUDIT_SCHEMA_VERSION, decimal_value, input_digest, parse_timestamp

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001")), "f")


def _ratio(numerator: Decimal | int, denominator: Decimal | int) -> float | None:
    if denominator == 0:
        return None
    return round(float(Decimal(numerator) / Decimal(denominator)), 6)


def _finding(
    code: str,
    severity: str,
    title: str,
    detail: str,
    *,
    evidence: Iterable[str] = (),
    remediation: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "detail": detail,
        "evidence": sorted(set(evidence)),
        "remediation": remediation,
    }


def _add_breakdown(
    table: dict[str, dict[str, Any]],
    key: str,
    event: Mapping[str, Any],
    exact_cost: Decimal,
    estimated_cost: Decimal,
) -> None:
    row = table.setdefault(
        key,
        {
            "calls": 0,
            "succeeded": 0,
            "failed_or_incomplete": 0,
            "exact_cost": Decimal("0"),
            "estimated_cost": Decimal("0"),
            "unknown_cost_calls": 0,
            "exact_input_tokens": 0,
            "exact_cached_input_tokens": 0,
            "exact_output_tokens": 0,
            "exact_reasoning_tokens": 0,
        },
    )
    row["calls"] += 1
    if event["status"] == "succeeded":
        row["succeeded"] += 1
    else:
        row["failed_or_incomplete"] += 1
    row["exact_cost"] += exact_cost
    row["estimated_cost"] += estimated_cost
    usage = event["usage"]
    if usage["cost_quality"] == "unknown":
        row["unknown_cost_calls"] += 1
    if usage["token_quality"] == "exact":
        row["exact_input_tokens"] += int(usage.get("input_tokens") or 0)
        row["exact_cached_input_tokens"] += int(usage.get("cached_input_tokens") or 0)
        row["exact_output_tokens"] += int(usage.get("output_tokens") or 0)
        row["exact_reasoning_tokens"] += int(usage.get("reasoning_tokens") or 0)


def _finalize_breakdown(table: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for key in sorted(table):
        row = dict(table[key])
        row["exact_cost"] = _money(row["exact_cost"])
        row["estimated_cost"] = _money(row["estimated_cost"])
        row["exact_non_cached_input_tokens"] = max(
            0, row["exact_input_tokens"] - row["exact_cached_input_tokens"]
        )
        output[key] = row
    return output


def build_audit(events: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    calls = [event for event in events if event["event_type"] == "call"]
    artifacts = [event for event in events if event["event_type"] == "artifact"]
    call_by_id = {event["event_id"]: event for event in calls}
    findings: list[dict[str, Any]] = []

    run_ids = sorted({event["run_id"] for event in events})
    if len(run_ids) > 1:
        findings.append(
            _finding(
                "MULTIPLE_RUN_IDS",
                "critical",
                "One audit ledger contains multiple run IDs",
                f"The ledger contains {len(run_ids)} run IDs and cannot represent one bounded unit-economics run.",
                evidence=run_ids,
                remediation="Split the ledger by run_id and audit each run independently.",
            )
        )

    artifact_ids: dict[str, list[str]] = defaultdict(list)
    for artifact in artifacts:
        artifact_ids[artifact["artifact_id"]].append(artifact["event_id"])
    for artifact_id, event_ids in sorted(artifact_ids.items()):
        if len(event_ids) > 1:
            findings.append(
                _finding(
                    "DUPLICATE_ARTIFACT_ID",
                    "high",
                    "Artifact identity is not unique within the run",
                    f"Artifact ID {artifact_id} appears in {len(event_ids)} receipts.",
                    evidence=event_ids,
                    remediation="Issue one immutable artifact receipt per artifact identity and version later outputs explicitly.",
                )
            )

    exact_cost = Decimal("0")
    estimated_cost = Decimal("0")
    exact_cost_calls = 0
    estimated_cost_calls = 0
    unknown_cost_calls = 0
    exact_token_calls = 0
    estimated_token_calls = 0
    unknown_token_calls = 0
    exact_input_tokens = 0
    exact_cached_input_tokens = 0
    exact_output_tokens = 0
    exact_reasoning_tokens = 0
    retry_exact_cost = Decimal("0")
    failed_exact_cost = Decimal("0")
    duplicate_exact_cost = Decimal("0")
    cache_hits = 0
    cache_misses = 0
    cache_unknown_or_bypass = 0
    terminal_calls = 0

    by_provider: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_stage: dict[str, dict[str, Any]] = {}
    by_operation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_dedupe: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_usage_receipt: dict[str, list[str]] = defaultdict(list)

    for event in calls:
        usage = event["usage"]
        receipt_sha256 = usage.get("receipt_sha256")
        if receipt_sha256 is not None:
            by_usage_receipt[receipt_sha256].append(event["event_id"])
        call_exact_cost = Decimal("0")
        call_estimated_cost = Decimal("0")
        if usage["cost_quality"] == "exact":
            call_exact_cost = decimal_value("cost_amount", usage["cost_amount"])
            exact_cost += call_exact_cost
            exact_cost_calls += 1
        elif usage["cost_quality"] == "estimated":
            call_estimated_cost = decimal_value("cost_amount", usage["cost_amount"])
            estimated_cost += call_estimated_cost
            estimated_cost_calls += 1
        elif usage["cost_quality"] == "unknown":
            unknown_cost_calls += 1

        if usage["token_quality"] == "exact":
            exact_token_calls += 1
            exact_input_tokens += int(usage.get("input_tokens") or 0)
            exact_cached_input_tokens += int(usage.get("cached_input_tokens") or 0)
            exact_output_tokens += int(usage.get("output_tokens") or 0)
            exact_reasoning_tokens += int(usage.get("reasoning_tokens") or 0)
        elif usage["token_quality"] == "estimated":
            estimated_token_calls += 1
        elif usage["token_quality"] == "unknown":
            unknown_token_calls += 1

        if event["attempt"] > 1:
            retry_exact_cost += call_exact_cost
        if event["status"] in {"failed", "timed_out", "cancelled"}:
            failed_exact_cost += call_exact_cost
        if event["status"] != "started":
            terminal_calls += 1

        cache_status = event["cache"]["status"]
        if cache_status == "hit":
            cache_hits += 1
        elif cache_status == "miss":
            cache_misses += 1
        else:
            cache_unknown_or_bypass += 1

        _add_breakdown(by_provider, event["provider"], event, call_exact_cost, call_estimated_cost)
        _add_breakdown(by_model, event["model"], event, call_exact_cost, call_estimated_cost)
        _add_breakdown(by_stage, event["stage"], event, call_exact_cost, call_estimated_cost)
        by_operation[event["operation_id"]].append(event)
        by_dedupe[event["dedupe_key"]].append(event)

    for event in calls:
        if event["attempt"] <= 1:
            continue
        parent_id = event["parent_event_id"]
        parent = call_by_id.get(parent_id)
        if parent is None:
            findings.append(
                _finding(
                    "RETRY_PARENT_REFERENCE_MISSING",
                    "high",
                    "Retry references a missing parent attempt",
                    f"Retry {event['event_id']} references parent {parent_id}, which is absent from the ledger.",
                    evidence=[event["event_id"], parent_id],
                    remediation="Ingest the parent attempt receipt before counting or comparing the retry.",
                )
            )
            continue
        if parent["run_id"] != event["run_id"] or parent["operation_id"] != event["operation_id"]:
            findings.append(
                _finding(
                    "RETRY_PARENT_SCOPE_MISMATCH",
                    "high",
                    "Retry parent belongs to a different run or operation",
                    f"Retry {event['event_id']} is not scoped to the same run and operation as {parent_id}.",
                    evidence=[event["event_id"], parent_id],
                    remediation="Link retries only to the immediately preceding attempt of the same logical operation.",
                )
            )
        if int(parent["attempt"]) != int(event["attempt"]) - 1:
            findings.append(
                _finding(
                    "RETRY_SEQUENCE_GAP",
                    "medium",
                    "Retry attempt sequence is not contiguous",
                    f"Retry {event['event_id']} is attempt {event['attempt']} but parent {parent_id} is attempt {parent['attempt']}.",
                    evidence=[event["event_id"], parent_id],
                    remediation="Use contiguous attempt numbers and point to the immediately preceding attempt.",
                )
            )

    for receipt_sha256, event_ids in sorted(by_usage_receipt.items()):
        if len(event_ids) > 1:
            findings.append(
                _finding(
                    "DUPLICATE_USAGE_RECEIPT",
                    "high",
                    "One normalized usage receipt is counted more than once",
                    f"Usage receipt {receipt_sha256[:12]}… appears in {len(event_ids)} call events.",
                    evidence=event_ids,
                    remediation="Give each normalized call receipt a unique content hash or deduplicate before aggregation.",
                )
            )

    accepted_artifacts = [event for event in artifacts if event["accepted"]]
    rejected_artifacts = [event for event in artifacts if not event["accepted"]]

    for artifact in artifacts:
        missing = sorted(event_id for event_id in artifact["produced_by"] if event_id not in call_by_id)
        if missing:
            findings.append(
                _finding(
                    "ARTIFACT_CALL_REFERENCE_MISSING",
                    "high",
                    "Artifact references missing calls",
                    f"Artifact {artifact['artifact_id']} references call IDs absent from the event ledger.",
                    evidence=[artifact["event_id"], *missing],
                    remediation="Ingest the missing call receipts or reject the artifact receipt.",
                )
            )
        wrong_run_sources = sorted(
            event_id
            for event_id in artifact["produced_by"]
            if event_id in call_by_id and call_by_id[event_id]["run_id"] != artifact["run_id"]
        )
        if wrong_run_sources:
            findings.append(
                _finding(
                    "ARTIFACT_RUN_MISMATCH",
                    "high",
                    "Artifact references producer calls from another run",
                    f"Artifact {artifact['artifact_id']} crosses the run boundary.",
                    evidence=[artifact["event_id"], *wrong_run_sources],
                    remediation="Bind the artifact only to producer calls from its own run_id.",
                )
            )
        successful_sources = [
            call_by_id[event_id]
            for event_id in artifact["produced_by"]
            if event_id in call_by_id
            and call_by_id[event_id]["run_id"] == artifact["run_id"]
            and call_by_id[event_id]["status"] == "succeeded"
        ]
        if artifact["accepted"] and not successful_sources:
            findings.append(
                _finding(
                    "ACCEPTED_ARTIFACT_WITHOUT_SUCCESSFUL_CALL",
                    "high",
                    "Accepted artifact lacks a successful producer call",
                    f"Artifact {artifact['artifact_id']} passed {artifact['gate_id']} but has no successful producer call.",
                    evidence=[artifact["event_id"]],
                    remediation="Bind the artifact to successful call receipts before counting it as accepted output.",
                )
            )

    wrong_currency_events = [
        event
        for event in calls
        if event["usage"]["cost_quality"] in {"exact", "estimated"}
        and event["usage"]["currency"] != policy["currency"]
    ]
    if wrong_currency_events:
        currencies = sorted({event["usage"]["currency"] for event in wrong_currency_events})
        findings.append(
            _finding(
                "CURRENCY_MISMATCH",
                "critical",
                "Costs use incompatible currencies",
                f"The ledger includes {', '.join(currencies)} while the audit currency is {policy['currency']}.",
                evidence=[event["event_id"] for event in wrong_currency_events],
                remediation="Convert outside this tool using a dated exchange-rate receipt, then ingest one currency.",
            )
        )

    operations_policy = policy["operations"]
    for operation_id, events_for_operation in sorted(by_operation.items()):
        op_policy = operations_policy.get(operation_id)
        if op_policy is None:
            findings.append(
                _finding(
                    "UNPLANNED_OPERATION",
                    "high",
                    "Model call was not declared in the policy",
                    f"Operation {operation_id} executed {len(events_for_operation)} call(s) without a declared budget.",
                    evidence=[event["event_id"] for event in events_for_operation],
                    remediation="Declare the operation and budget before dispatch, or remove the hidden call.",
                )
            )
            continue
        if any(event["stage"] != op_policy["stage"] for event in events_for_operation):
            findings.append(
                _finding(
                    "OPERATION_STAGE_MISMATCH",
                    "medium",
                    "Operation ran in an unexpected stage",
                    f"Operation {operation_id} is declared for stage {op_policy['stage']}.",
                    evidence=[event["event_id"] for event in events_for_operation],
                    remediation="Correct the event stage or the reviewed policy declaration.",
                )
            )
        if len(events_for_operation) > int(op_policy["max_attempts"]):
            findings.append(
                _finding(
                    "ATTEMPT_BUDGET_EXCEEDED",
                    "high",
                    "Operation exceeded its attempt budget",
                    f"Operation {operation_id} used {len(events_for_operation)} attempts; budget is {op_policy['max_attempts']}.",
                    evidence=[event["event_id"] for event in events_for_operation],
                    remediation="Add a stop-loss or require a fresh approval before further retries.",
                )
            )
        invalid_providers = sorted(
            {event["provider"] for event in events_for_operation} - set(op_policy["allowed_providers"])
        )
        if invalid_providers:
            findings.append(
                _finding(
                    "PROVIDER_NOT_ALLOWED",
                    "high",
                    "Operation used an undeclared provider",
                    f"Operation {operation_id} used: {', '.join(invalid_providers)}.",
                    evidence=[event["event_id"] for event in events_for_operation],
                    remediation="Update the reviewed policy or block provider fallback outside the allowlist.",
                )
            )
        invalid_models = sorted({event["model"] for event in events_for_operation} - set(op_policy["allowed_models"]))
        if invalid_models:
            findings.append(
                _finding(
                    "MODEL_NOT_ALLOWED",
                    "high",
                    "Operation used an undeclared model",
                    f"Operation {operation_id} used: {', '.join(invalid_models)}.",
                    evidence=[event["event_id"] for event in events_for_operation],
                    remediation="Update the reviewed policy or block model fallback outside the allowlist.",
                )
            )
        operation_exact_cost = sum(
            (
                decimal_value("cost_amount", event["usage"]["cost_amount"])
                for event in events_for_operation
                if event["usage"]["cost_quality"] == "exact"
            ),
            Decimal("0"),
        )
        max_exact_cost = Decimal(str(op_policy["max_exact_cost"]))
        if operation_exact_cost > max_exact_cost:
            findings.append(
                _finding(
                    "OPERATION_COST_BUDGET_EXCEEDED",
                    "high",
                    "Operation exceeded its exact-cost budget",
                    f"Operation {operation_id} cost {_money(operation_exact_cost)} {policy['currency']}; budget is {_money(max_exact_cost)}.",
                    evidence=[event["event_id"] for event in events_for_operation],
                    remediation="Reduce calls, improve caching, change the reviewed model route, or raise the budget explicitly.",
                )
            )
    for operation_id, op_policy in sorted(operations_policy.items()):
        if op_policy["required"] and operation_id not in by_operation:
            findings.append(
                _finding(
                    "REQUIRED_OPERATION_MISSING",
                    "high",
                    "Required operation did not produce a call receipt",
                    f"Required operation {operation_id} is absent from the event ledger.",
                    evidence=[operation_id],
                    remediation="Ingest the missing receipt or fail the pipeline before claiming completion.",
                )
            )

    for dedupe_key, events_for_key in sorted(by_dedupe.items()):
        dedupe_scopes = sorted({(event["run_id"], event["operation_id"]) for event in events_for_key})
        if len(dedupe_scopes) > 1:
            findings.append(
                _finding(
                    "DEDUPE_SCOPE_COLLISION",
                    "high",
                    "One dedupe key spans multiple run or operation scopes",
                    f"Dedupe key {dedupe_key[:12]}… appears in {len(dedupe_scopes)} scopes.",
                    evidence=[event["event_id"] for event in events_for_key],
                    remediation="Derive dedupe keys from the run-independent work fingerprint plus operation identity, then prevent cross-operation reuse.",
                )
            )
        successes = sorted(
            (event for event in events_for_key if event["status"] == "succeeded"),
            key=lambda event: (event["finished_at"], event["event_id"]),
        )
        if len(successes) > 1:
            extra_cost = sum(
                (
                    decimal_value("cost_amount", event["usage"]["cost_amount"])
                    for event in successes[1:]
                    if event["usage"]["cost_quality"] == "exact"
                ),
                Decimal("0"),
            )
            duplicate_exact_cost += extra_cost
            unknown_duplicate_cost_calls = sum(
                1 for event in successes[1:] if event["usage"]["cost_quality"] != "exact"
            )
            unknown_suffix = (
                f" {unknown_duplicate_cost_calls} duplicate call(s) lack exact cost, so total duplicate cost is not proven."
                if unknown_duplicate_cost_calls
                else ""
            )
            findings.append(
                _finding(
                    "DUPLICATE_SUCCESSFUL_WORK",
                    "high",
                    "The same logical work succeeded more than once",
                    f"Dedupe key {dedupe_key[:12]}… has {len(successes)} successful calls; "
                    f"recorded extra exact cost is {_money(extra_cost)} {policy['currency']}.{unknown_suffix}",
                    evidence=[event["event_id"] for event in successes],
                    remediation="Acquire an idempotency lease before dispatch and bind completion to the dedupe key.",
                )
            )

    started_calls = [event for event in calls if event["status"] == "started"]
    if started_calls:
        findings.append(
            _finding(
                "INCOMPLETE_CALLS",
                "high",
                "Calls never reached a terminal state",
                f"{len(started_calls)} call(s) remain started.",
                evidence=[event["event_id"] for event in started_calls],
                remediation="Reconcile provider receipts and close each attempt without reusing its event ID.",
            )
        )

    exact_cost_coverage = _ratio(exact_cost_calls, len(calls)) or 0.0
    exact_token_coverage = _ratio(exact_token_calls, len(calls)) or 0.0
    retry_cost_ratio = _ratio(retry_exact_cost, exact_cost) or 0.0
    failed_cost_ratio = _ratio(failed_exact_cost, exact_cost) or 0.0

    if exact_cost_coverage < float(policy["minimum_exact_cost_coverage"]):
        findings.append(
            _finding(
                "EXACT_COST_COVERAGE_LOW",
                "high",
                "Too few calls have exact cost receipts",
                f"Coverage is {exact_cost_coverage:.1%}; policy requires {float(policy['minimum_exact_cost_coverage']):.1%}.",
                evidence=[event["event_id"] for event in calls if event["usage"]["cost_quality"] != "exact"],
                remediation="Ingest provider or verified-host receipts; do not relabel estimates as exact.",
            )
        )
    if exact_token_coverage < float(policy["minimum_exact_token_coverage"]):
        findings.append(
            _finding(
                "EXACT_TOKEN_COVERAGE_LOW",
                "high",
                "Too few calls have exact token receipts",
                f"Coverage is {exact_token_coverage:.1%}; policy requires {float(policy['minimum_exact_token_coverage']):.1%}.",
                evidence=[event["event_id"] for event in calls if event["usage"]["token_quality"] != "exact"],
                remediation="Capture provider usage fields or label the measurement as estimated/unknown.",
            )
        )
    if retry_cost_ratio > float(policy["maximum_retry_cost_ratio"]):
        findings.append(
            _finding(
                "RETRY_COST_RATIO_HIGH",
                "medium",
                "Retries consume too much exact cost",
                f"Retry exact-cost ratio is {retry_cost_ratio:.1%}; policy maximum is {float(policy['maximum_retry_cost_ratio']):.1%}.",
                evidence=[event["event_id"] for event in calls if event["attempt"] > 1],
                remediation="Use targeted retries, stronger preflight validation, and bounded stop-loss rules.",
            )
        )
    if failed_cost_ratio > float(policy["maximum_failed_cost_ratio"]):
        findings.append(
            _finding(
                "FAILED_COST_RATIO_HIGH",
                "medium",
                "Failed calls consume too much exact cost",
                f"Failed exact-cost ratio is {failed_cost_ratio:.1%}; policy maximum is {float(policy['maximum_failed_cost_ratio']):.1%}.",
                evidence=[event["event_id"] for event in calls if event["status"] in {"failed", "timed_out", "cancelled"}],
                remediation="Reject bad inputs before provider dispatch and stop retry cascades.",
            )
        )
    if policy["require_accepted_artifact"] and not accepted_artifacts:
        findings.append(
            _finding(
                "NO_ACCEPTED_ARTIFACT",
                "high",
                "The run has cost but no accepted output",
                "No artifact passed a quality gate.",
                evidence=[event["event_id"] for event in artifacts],
                remediation="Do not report unit economics until at least one artifact passes the declared gate.",
            )
        )

    severity_counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        severity_counts[finding["severity"]] += 1
    highest_severity = max(
        (finding["severity"] for finding in findings),
        key=lambda severity: SEVERITY_ORDER[severity],
        default="info",
    )
    status = "FAIL" if SEVERITY_ORDER[highest_severity] >= SEVERITY_ORDER["high"] else ("WARN" if findings else "PASS")
    confidence = (
        "high"
        if exact_cost_coverage == 1.0 and exact_token_coverage == 1.0
        else (
            "medium"
            if exact_cost_coverage >= float(policy["minimum_exact_cost_coverage"])
            and exact_token_coverage >= float(policy["minimum_exact_token_coverage"])
            else "low"
        )
    )

    cost_per_accepted = (
        exact_cost / len(accepted_artifacts)
        if accepted_artifacts and exact_cost_coverage == 1.0
        else None
    )
    known_cache = cache_hits + cache_misses
    completed_times = [parse_timestamp("completed_at", event["completed_at"]) for event in artifacts]
    call_start_times = [parse_timestamp("started_at", event["started_at"]) for event in calls]
    run_wall_seconds = None
    if completed_times and call_start_times:
        run_wall_seconds = round((max(completed_times) - min(call_start_times)).total_seconds(), 3)

    audit = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "audit_name": policy["audit_name"],
        "source_digest_sha256": input_digest(events, policy),
        "status": status,
        "confidence": confidence,
        "currency": policy["currency"],
        "summary": {
            "call_count": len(calls),
            "terminal_call_count": terminal_calls,
            "accepted_artifact_count": len(accepted_artifacts),
            "rejected_artifact_count": len(rejected_artifacts),
            "artifact_acceptance_rate": _ratio(len(accepted_artifacts), len(artifacts)),
            "exact_cost": _money(exact_cost),
            "estimated_cost": _money(estimated_cost),
            "unknown_cost_call_count": unknown_cost_calls,
            "exact_cost_coverage": exact_cost_coverage,
            "estimated_cost_call_count": estimated_cost_calls,
            "exact_token_coverage": exact_token_coverage,
            "estimated_token_call_count": estimated_token_calls,
            "unknown_token_call_count": unknown_token_calls,
            "cost_per_accepted_artifact": _money(cost_per_accepted) if cost_per_accepted is not None else None,
            "cost_per_accepted_artifact_confidence": "high" if cost_per_accepted is not None else "not_available",
            "retry_call_count": sum(1 for event in calls if event["attempt"] > 1),
            "retry_exact_cost": _money(retry_exact_cost),
            "retry_exact_cost_ratio": retry_cost_ratio,
            "failed_exact_cost": _money(failed_exact_cost),
            "failed_exact_cost_ratio": failed_cost_ratio,
            "duplicate_exact_cost": _money(duplicate_exact_cost),
            "exact_input_tokens": exact_input_tokens,
            "exact_cached_input_tokens": exact_cached_input_tokens,
            "exact_non_cached_input_tokens": max(0, exact_input_tokens - exact_cached_input_tokens),
            "exact_output_tokens": exact_output_tokens,
            "exact_reasoning_tokens": exact_reasoning_tokens,
            "cache_hit_count": cache_hits,
            "cache_miss_count": cache_misses,
            "cache_hit_rate_known": _ratio(cache_hits, known_cache),
            "cache_unknown_or_bypass_count": cache_unknown_or_bypass,
            "run_wall_seconds": run_wall_seconds,
            "highest_finding_severity": highest_severity,
        },
        "accepted_artifacts": [
            {
                "artifact_id": event["artifact_id"],
                "artifact_kind": event["artifact_kind"],
                "artifact_sha256": event["artifact_sha256"],
                "gate_id": event["gate_id"],
                "quality_score": event.get("quality_score"),
            }
            for event in sorted(accepted_artifacts, key=lambda item: item["artifact_id"])
        ],
        "breakdown": {
            "by_provider": _finalize_breakdown(by_provider),
            "by_model": _finalize_breakdown(by_model),
            "by_stage": _finalize_breakdown(by_stage),
        },
        "finding_counts": severity_counts,
        "findings": sorted(
            findings,
            key=lambda finding: (-SEVERITY_ORDER[finding["severity"]], finding["code"], finding["detail"]),
        ),
        "policy_snapshot": policy,
    }
    return audit
