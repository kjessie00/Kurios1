from __future__ import annotations

from pathlib import Path


def safe_path_label(value: str | Path) -> str:
    """Return a basename-only diagnostic label that cannot expose a host path."""
    name = Path(value).name
    return name or "<input>"


class AuditInputError(ValueError):
    """Raised when an input event, policy, report, or manifest is unsafe or invalid."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        location: str | None = None,
    ) -> None:
        self.code = code
        self.location = location
        prefix = f"{location}: " if location else ""
        super().__init__(f"{code}: {prefix}{message}")
