from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from .errors import AuditInputError, safe_path_label


def _pct(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.1%}"


def _money(value: Any, currency: str) -> str:
    return "N/A" if value is None else f"{value} {currency}"


def render_audit_markdown(audit: Mapping[str, Any]) -> str:
    summary = audit["summary"]
    currency = audit["currency"]
    lines = [
        f"# AI Media Pipeline Economics Audit — `{audit['audit_name']}`",
        "",
        f"**Status:** `{audit['status']}`",
        f"**Evidence confidence:** `{audit['confidence']}`",
        f"**Source digest:** `{audit['source_digest_sha256']}`",
        "",
        "## Executive scorecard",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Model/agent calls | {summary['call_count']} |",
        f"| Accepted artifacts | {summary['accepted_artifact_count']} |",
        f"| Artifact acceptance rate | {_pct(summary['artifact_acceptance_rate'])} |",
        f"| Exact cost | {_money(summary['exact_cost'], currency)} |",
        f"| Estimated cost (kept separate) | {_money(summary['estimated_cost'], currency)} |",
        f"| Calls with unknown cost | {summary['unknown_cost_call_count']} |",
        f"| Exact cost coverage | {_pct(summary['exact_cost_coverage'])} |",
        f"| Exact token coverage | {_pct(summary['exact_token_coverage'])} |",
        f"| Cost / accepted artifact | {_money(summary['cost_per_accepted_artifact'], currency)} |",
        f"| Retry exact-cost ratio | {_pct(summary['retry_exact_cost_ratio'])} |",
        f"| Failed exact-cost ratio | {_pct(summary['failed_exact_cost_ratio'])} |",
        f"| Duplicate exact cost | {_money(summary['duplicate_exact_cost'], currency)} |",
        f"| Exact non-cached input tokens | {summary['exact_non_cached_input_tokens']:,} |",
        f"| Known cache hit rate | {_pct(summary['cache_hit_rate_known'])} |",
        "",
        "> Exact, estimated, and unknown measurements are intentionally not merged into a single total.",
        "",
        "## Cost and token breakdown",
        "",
    ]
    for heading, key in (
        ("By stage", "by_stage"),
        ("By provider", "by_provider"),
        ("By model", "by_model"),
    ):
        lines.extend(
            [
                f"### {heading}",
                "",
                "| Name | Calls | Succeeded | Exact cost | Estimated cost | Unknown-cost calls | Non-cached input tokens |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for name, row in audit["breakdown"][key].items():
            lines.append(
                f"| `{name}` | {row['calls']} | {row['succeeded']} | {row['exact_cost']} | "
                f"{row['estimated_cost']} | {row['unknown_cost_calls']} | "
                f"{row['exact_non_cached_input_tokens']:,} |"
            )
        lines.append("")

    lines.extend(["## Findings", ""])
    if not audit["findings"]:
        lines.append("No policy findings.")
        lines.append("")
    else:
        for finding in audit["findings"]:
            lines.extend(
                [
                    f"### [{finding['severity'].upper()}] {finding['code']}",
                    "",
                    f"**{finding['title']}**",
                    "",
                    finding["detail"],
                    "",
                    f"**Evidence:** {', '.join(f'`{item}`' for item in finding['evidence']) or 'none'}",
                    "",
                    f"**Remediation:** {finding['remediation']}",
                    "",
                ]
            )

    lines.extend(
        [
            "## Accepted artifacts",
            "",
            "| Artifact | Kind | Gate | Quality score | SHA-256 |",
            "|---|---|---|---:|---|",
        ]
    )
    for artifact in audit["accepted_artifacts"]:
        score = "N/A" if artifact["quality_score"] is None else f"{float(artifact['quality_score']):.3f}"
        lines.append(
            f"| `{artifact['artifact_id']}` | `{artifact['artifact_kind']}` | `{artifact['gate_id']}` | "
            f"{score} | `{artifact['artifact_sha256']}` |"
        )
    if not audit["accepted_artifacts"]:
        lines.append("| _none_ | | | | |")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This report audits supplied receipts and policy declarations. It does not infer provider prices, "
            "inspect prompts, or prove creative quality beyond the supplied quality-gate receipts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_comparison_markdown(comparison: Mapping[str, Any]) -> str:
    delta = comparison["delta"]
    currency = comparison["currency"]
    lines = [
        f"# AI Media Pipeline Economics Comparison — `{comparison['comparison_name']}`",
        "",
        f"**Conclusion:** `{comparison['conclusion']}`",
        f"**Confidence:** `{comparison['confidence']}`",
        f"**Quality floor preserved:** `{str(comparison['quality_floor_preserved']).lower()}`",
        "",
        "## Paired result",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
        f"| Exact cost | {comparison['baseline']['exact_cost']} {currency} | "
        f"{comparison['candidate']['exact_cost']} {currency} | {delta['exact_cost']} {currency} |",
        f"| Exact cost reduction | — | — | {_pct(delta['exact_cost_reduction_ratio'])} |",
        f"| Cost / accepted artifact | {_money(comparison['baseline']['cost_per_accepted_artifact'], currency)} | "
        f"{_money(comparison['candidate']['cost_per_accepted_artifact'], currency)} | "
        f"{_money(delta['cost_per_accepted_artifact'], currency)} |",
        f"| Accepted artifacts | {comparison['baseline']['accepted_artifact_count']} | "
        f"{comparison['candidate']['accepted_artifact_count']} | {delta['accepted_artifact_count']} |",
        f"| Non-cached input tokens | {comparison['baseline']['exact_non_cached_input_tokens']:,} | "
        f"{comparison['candidate']['exact_non_cached_input_tokens']:,} | "
        f"{delta['exact_non_cached_input_tokens']:,} |",
        f"| Retry exact-cost ratio | {_pct(comparison['baseline']['retry_exact_cost_ratio'])} | "
        f"{_pct(comparison['candidate']['retry_exact_cost_ratio'])} | "
        f"{_pct(delta['retry_exact_cost_ratio'])} |",
        "",
        "## Decision rule",
        "",
        comparison["decision_rule"],
        "",
        "## Surviving cautions",
        "",
    ]
    for caution in comparison["cautions"]:
        lines.append(f"- {caution}")
    if not comparison["cautions"]:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        handle.write(data)
        handle.flush()
    temp.replace(path)


def _manifest_lines(files: list[Path], root: Path) -> str:
    rows = []
    for path in sorted(files, key=lambda item: item.name):
        digest = sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  {path.relative_to(root).as_posix()}")
    return "\n".join(rows) + "\n"


def write_audit_bundle(audit: Mapping[str, Any], output_dir: str | Path) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "audit.json"
    markdown_path = output / "audit.md"
    _write_atomic(json_path, json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    _write_atomic(markdown_path, render_audit_markdown(audit).encode("utf-8"))
    manifest_path = output / "manifest.sha256"
    _write_atomic(manifest_path, _manifest_lines([json_path, markdown_path], output).encode("utf-8"))
    return [json_path, markdown_path, manifest_path]


def write_comparison_bundle(comparison: Mapping[str, Any], output_dir: str | Path) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "comparison.json"
    markdown_path = output / "comparison.md"
    _write_atomic(
        json_path,
        json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    _write_atomic(markdown_path, render_comparison_markdown(comparison).encode("utf-8"))
    manifest_path = output / "comparison-manifest.sha256"
    _write_atomic(manifest_path, _manifest_lines([json_path, markdown_path], output).encode("utf-8"))
    return [json_path, markdown_path, manifest_path]


def verify_manifest(path: str | Path) -> list[str]:
    manifest = Path(path)
    if not manifest.is_file():
        raise AuditInputError("MANIFEST_NOT_FOUND", "manifest does not exist", location=safe_path_label(manifest))
    failures: list[str] = []
    seen_paths: set[str] = set()
    for line_number, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise AuditInputError("MANIFEST_INVALID", "expected '<sha256>  <path>'", location=f"{safe_path_label(manifest)}:{line_number}")
        expected, relative = parts
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise AuditInputError(
                "MANIFEST_INVALID",
                "digest must be lowercase SHA-256 hex",
                location=f"{safe_path_label(manifest)}:{line_number}",
            )
        if relative in seen_paths:
            raise AuditInputError(
                "MANIFEST_DUPLICATE_PATH",
                f"duplicate path {relative}",
                location=f"{safe_path_label(manifest)}:{line_number}",
            )
        seen_paths.add(relative)
        target = (manifest.parent / relative).resolve()
        try:
            target.relative_to(manifest.parent.resolve())
        except ValueError as exc:
            raise AuditInputError("MANIFEST_PATH_ESCAPE", "manifest path escapes its directory", location=safe_path_label(manifest)) from exc
        if not target.is_file():
            failures.append(f"missing:{relative}")
            continue
        actual = sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            failures.append(f"hash_mismatch:{relative}")
    return failures
