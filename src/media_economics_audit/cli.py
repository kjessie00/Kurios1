from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .engine import audit_files, compare_audit_files
from .errors import AuditInputError
from .metrics import SEVERITY_ORDER
from .report import verify_manifest
from .schema import load_events, load_policy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="media-economics-audit",
        description="Audit AI media pipeline unit economics from evidence receipts.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate event and policy inputs without producing a report")
    validate.add_argument("events", type=Path)
    validate.add_argument("--policy", type=Path)

    audit = sub.add_parser("audit", help="Generate deterministic JSON, Markdown, and SHA-256 audit artifacts")
    audit.add_argument("events", type=Path)
    audit.add_argument("--policy", type=Path, required=True)
    audit.add_argument("--out", type=Path, required=True)
    audit.add_argument(
        "--fail-on",
        choices=["never", "low", "medium", "high", "critical"],
        default="high",
        help="Return exit code 2 when the report reaches this severity (default: high)",
    )

    compare = sub.add_parser("compare", help="Compare two generated audit.json files")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument("--out", type=Path, required=True)
    compare.add_argument("--name")
    compare.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Return exit code 2 for REGRESSED or INCONCLUSIVE comparisons",
    )

    verify = sub.add_parser("verify", help="Verify a generated SHA-256 manifest")
    verify.add_argument("manifest", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            events = load_events(args.events)
            payload = {"events": len(events), "status": "valid"}
            if args.policy:
                policy = load_policy(args.policy)
                payload["audit_name"] = policy["audit_name"]
                payload["operations"] = len(policy["operations"])
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 0

        if args.command == "audit":
            report = audit_files(args.events, args.policy, output_dir=args.out)
            print(json.dumps({"status": report["status"], "files": ["audit.json", "audit.md", "manifest.sha256"]}, sort_keys=True))
            if args.fail_on != "never":
                highest = report["summary"]["highest_finding_severity"]
                if SEVERITY_ORDER[highest] >= SEVERITY_ORDER[args.fail_on]:
                    return 2
            return 0

        if args.command == "compare":
            comparison = compare_audit_files(
                args.baseline,
                args.candidate,
                output_dir=args.out,
                comparison_name=args.name,
            )
            print(json.dumps({"conclusion": comparison["conclusion"], "files": ["comparison.json", "comparison.md", "comparison-manifest.sha256"]}, sort_keys=True))
            if args.fail_on_regression and comparison["conclusion"] in {"REGRESSED", "INCONCLUSIVE"}:
                return 2
            return 0

        if args.command == "verify":
            failures = verify_manifest(args.manifest)
            print(json.dumps({"failures": failures, "status": "valid" if not failures else "invalid"}, sort_keys=True))
            return 0 if not failures else 2
    except AuditInputError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
