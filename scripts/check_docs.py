#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


def main() -> int:
    failures: list[str] = []
    for source in sorted(ROOT.rglob("*.md")):
        if any(part in {".git", ".venv", "build", "dist"} for part in source.parts):
            continue
        text = source.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            target = target.strip().split("#", 1)[0]
            if not target or target.startswith(SKIP_PREFIXES):
                continue
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            resolved = (source.parent / unquote(target)).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                failures.append(f"{source.relative_to(ROOT)}: path escapes repository: {target}")
                continue
            if not resolved.exists():
                failures.append(f"{source.relative_to(ROOT)}: missing link target: {target}")
    if failures:
        print("documentation link check failed")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("documentation link check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
