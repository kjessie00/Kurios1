from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .errors import AuditInputError, safe_path_label
from .metrics import build_audit
from .report import write_audit_bundle, write_comparison_bundle
from .schema import (
    AUDIT_SCHEMA_VERSION,
    COMPARE_SCHEMA_VERSION,
    canonical_json_bytes,
    load_events,
    load_policy,
)


def audit_files(
    events_path: str | Path,
    policy_path: str | Path,
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    events = load_events(events_path)
    policy = load_policy(policy_path)
    audit = build_audit(events, policy)
    if output_dir is not None:
        write_audit_bundle(audit, output_dir)
    return audit


def _load_audit(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise AuditInputError("AUDIT_FILE_NOT_FOUND", "audit JSON does not exist", location=safe_path_label(source))
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditInputError("JSON_INVALID", exc.msg, location=safe_path_label(source)) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise AuditInputError("AUDIT_SCHEMA_INVALID", f"expected {AUDIT_SCHEMA_VERSION}", location=safe_path_label(source))
    return payload


def _decimal(value: Any, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise AuditInputError("AUDIT_VALUE_INVALID", f"{field} is not a decimal") from exc
    if not result.is_finite():
        raise AuditInputError("AUDIT_VALUE_INVALID", f"{field} is not finite")
    return result


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001")), "f")


def _ratio(value: Decimal, denominator: Decimal) -> float | None:
    if denominator == 0:
        return None
    return round(float(value / denominator), 6)


def compare_audits(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    comparison_name: str | None = None,
) -> dict[str, Any]:
    if baseline.get("schema_version") != AUDIT_SCHEMA_VERSION or candidate.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise AuditInputError("AUDIT_SCHEMA_INVALID", "both reports must be media-economics-audit.v1")
    if baseline["currency"] != candidate["currency"]:
        raise AuditInputError("COMPARISON_CURRENCY_MISMATCH", "audits must use the same currency")

    base_summary = baseline["summary"]
    cand_summary = candidate["summary"]
    base_cost = _decimal(base_summary["exact_cost"], field="baseline exact_cost")
    cand_cost = _decimal(cand_summary["exact_cost"], field="candidate exact_cost")
    base_unit_raw = base_summary["cost_per_accepted_artifact"]
    cand_unit_raw = cand_summary["cost_per_accepted_artifact"]
    base_unit = _decimal(base_unit_raw, field="baseline unit cost") if base_unit_raw is not None else None
    cand_unit = _decimal(cand_unit_raw, field="candidate unit cost") if cand_unit_raw is not None else None
    cost_delta = cand_cost - base_cost
    unit_delta = cand_unit - base_unit if base_unit is not None and cand_unit is not None else None
    accepted_delta = int(cand_summary["accepted_artifact_count"]) - int(base_summary["accepted_artifact_count"])
    tokens_delta = int(cand_summary["exact_non_cached_input_tokens"]) - int(
        base_summary["exact_non_cached_input_tokens"]
    )
    retry_delta = float(cand_summary["retry_exact_cost_ratio"]) - float(base_summary["retry_exact_cost_ratio"])

    exact_coverage_complete = (
        float(base_summary["exact_cost_coverage"]) == 1.0
        and float(cand_summary["exact_cost_coverage"]) == 1.0
    )
    baseline_artifacts = {
        (item["artifact_id"], item["artifact_kind"], item["gate_id"]): item
        for item in baseline["accepted_artifacts"]
    }
    candidate_artifacts = {
        (item["artifact_id"], item["artifact_kind"], item["gate_id"]): item
        for item in candidate["accepted_artifacts"]
    }
    artifact_contract_preserved = set(baseline_artifacts).issubset(candidate_artifacts)
    artifact_scores_preserved = all(
        baseline_artifacts[key].get("quality_score") is None
        or (
            candidate_artifacts.get(key, {}).get("quality_score") is not None
            and float(candidate_artifacts[key]["quality_score"])
            >= float(baseline_artifacts[key]["quality_score"])
        )
        for key in baseline_artifacts
    )
    quality_floor_preserved = (
        artifact_contract_preserved
        and artifact_scores_preserved
        and int(cand_summary["accepted_artifact_count"]) >= int(base_summary["accepted_artifact_count"])
        and (cand_summary["artifact_acceptance_rate"] or 0) >= (base_summary["artifact_acceptance_rate"] or 0)
        and candidate["finding_counts"].get("critical", 0) <= baseline["finding_counts"].get("critical", 0)
        and candidate["finding_counts"].get("high", 0) <= baseline["finding_counts"].get("high", 0)
    )

    if not exact_coverage_complete:
        conclusion = "INCONCLUSIVE"
        confidence = "low"
    elif quality_floor_preserved and cand_cost < base_cost:
        conclusion = "IMPROVED"
        confidence = "high"
    elif cand_cost > base_cost or not quality_floor_preserved:
        conclusion = "REGRESSED"
        confidence = "high" if exact_coverage_complete else "low"
    else:
        conclusion = "NO_MATERIAL_CHANGE"
        confidence = "high"

    cautions: list[str] = []
    if not exact_coverage_complete:
        cautions.append("At least one audit has incomplete exact-cost coverage; no definitive savings claim is allowed.")
    if not artifact_contract_preserved:
        cautions.append("The candidate is missing at least one baseline artifact ID/kind/gate contract.")
    if not artifact_scores_preserved:
        cautions.append("At least one candidate artifact quality score is below its baseline score.")
    if not quality_floor_preserved:
        cautions.append("The candidate did not preserve the baseline quality floor or finding severity profile.")
    if baseline["source_digest_sha256"] == candidate["source_digest_sha256"]:
        cautions.append("Both audits use the same source digest; confirm that this is an intentional repeatability check.")
    if not baseline["accepted_artifacts"] or not candidate["accepted_artifacts"]:
        cautions.append("One side has no accepted artifact, so unit economics are not decision-ready.")

    comparison = {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "comparison_name": comparison_name or f"{baseline['audit_name']}-vs-{candidate['audit_name']}",
        "currency": baseline["currency"],
        "baseline_digest_sha256": baseline["source_digest_sha256"],
        "candidate_digest_sha256": candidate["source_digest_sha256"],
        "comparison_digest_sha256": hashlib.sha256(
            canonical_json_bytes(
                {
                    "baseline": baseline["source_digest_sha256"],
                    "candidate": candidate["source_digest_sha256"],
                }
            )
        ).hexdigest(),
        "conclusion": conclusion,
        "confidence": confidence,
        "quality_floor_preserved": quality_floor_preserved,
        "decision_rule": (
            "A candidate is labeled IMPROVED only when both sides have 100% exact-cost coverage, "
            "the accepted-output floor and severity profile are preserved, and candidate exact cost is lower."
        ),
        "baseline": {
            "audit_name": baseline["audit_name"],
            "exact_cost": _money(base_cost),
            "cost_per_accepted_artifact": _money(base_unit) if base_unit is not None else None,
            "accepted_artifact_count": base_summary["accepted_artifact_count"],
            "artifact_acceptance_rate": base_summary["artifact_acceptance_rate"],
            "exact_non_cached_input_tokens": base_summary["exact_non_cached_input_tokens"],
            "retry_exact_cost_ratio": base_summary["retry_exact_cost_ratio"],
            "exact_cost_coverage": base_summary["exact_cost_coverage"],
            "status": baseline["status"],
        },
        "candidate": {
            "audit_name": candidate["audit_name"],
            "exact_cost": _money(cand_cost),
            "cost_per_accepted_artifact": _money(cand_unit) if cand_unit is not None else None,
            "accepted_artifact_count": cand_summary["accepted_artifact_count"],
            "artifact_acceptance_rate": cand_summary["artifact_acceptance_rate"],
            "exact_non_cached_input_tokens": cand_summary["exact_non_cached_input_tokens"],
            "retry_exact_cost_ratio": cand_summary["retry_exact_cost_ratio"],
            "exact_cost_coverage": cand_summary["exact_cost_coverage"],
            "status": candidate["status"],
        },
        "delta": {
            "exact_cost": _money(cost_delta),
            "exact_cost_reduction_ratio": _ratio(base_cost - cand_cost, base_cost),
            "cost_per_accepted_artifact": _money(unit_delta) if unit_delta is not None else None,
            "accepted_artifact_count": accepted_delta,
            "exact_non_cached_input_tokens": tokens_delta,
            "retry_exact_cost_ratio": round(retry_delta, 6),
        },
        "cautions": cautions,
    }
    return comparison


def compare_audit_files(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    comparison_name: str | None = None,
) -> dict[str, Any]:
    baseline = _load_audit(baseline_path)
    candidate = _load_audit(candidate_path)
    comparison = compare_audits(baseline, candidate, comparison_name=comparison_name)
    if output_dir is not None:
        write_comparison_bundle(comparison, output_dir)
    return comparison
