#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile

from media_economics_audit.engine import audit_files, compare_audit_files

ROOT = Path(__file__).resolve().parents[1]
PAIRED = ROOT / "examples" / "paired"
PROBLEMATIC = ROOT / "examples" / "problematic"
TRACKED_OUTPUT = PAIRED / "output"


def build(output: Path) -> None:
    baseline = output / "baseline"
    optimized = output / "optimized"
    comparison = output / "comparison"
    problematic = output / "problematic"
    audit_files(PAIRED / "baseline.jsonl", PAIRED / "baseline-policy.json", output_dir=baseline)
    audit_files(PAIRED / "optimized.jsonl", PAIRED / "optimized-policy.json", output_dir=optimized)
    compare_audit_files(
        baseline / "audit.json",
        optimized / "audit.json",
        output_dir=comparison,
        comparison_name="synthetic-baseline-vs-optimized",
    )
    audit_files(PROBLEMATIC / "events.jsonl", PROBLEMATIC / "policy.json", output_dir=problematic)


def file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if tracked outputs are not reproducible")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="media-economics-example-") as temp:
            generated = Path(temp) / "output"
            build(generated)
            expected_files = file_map(TRACKED_OUTPUT)
            generated_files = file_map(generated)
            if expected_files != generated_files:
                missing = sorted(set(expected_files) - set(generated_files))
                extra = sorted(set(generated_files) - set(expected_files))
                changed = sorted(
                    key
                    for key in set(expected_files) & set(generated_files)
                    if expected_files[key] != generated_files[key]
                )
                print(f"example drift: missing={missing} extra={extra} changed={changed}")
                return 1
        print("examples are byte-reproducible")
        return 0

    shutil.rmtree(TRACKED_OUTPUT, ignore_errors=True)
    TRACKED_OUTPUT.mkdir(parents=True, exist_ok=True)
    build(TRACKED_OUTPUT)
    print(f"rebuilt {TRACKED_OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
