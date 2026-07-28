#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "build", "dist", "__pycache__"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".toml", ".yml", ".yaml", ".txt", ".cff"}
PATTERNS = {
    "openai_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "github_classic_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "github_fine_grained_token": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "mac_private_path": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    "windows_private_path": re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\"),
}


def main() -> int:
    findings: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"LICENSE", "Makefile", ".gitignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}:{name}")
    if findings:
        print("public-boundary scan failed")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("public-boundary scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
