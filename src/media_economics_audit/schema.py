from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .errors import AuditInputError, safe_path_label

EVENT_SCHEMA_VERSION = "media-economics-event.v1"
POLICY_SCHEMA_VERSION = "media-economics-policy.v1"
AUDIT_SCHEMA_VERSION = "media-economics-audit.v1"
COMPARE_SCHEMA_VERSION = "media-economics-comparison.v1"

EVENT_TYPES = frozenset({"call", "artifact"})
CALL_STATUSES = frozenset({"started", "succeeded", "failed", "timed_out", "cancelled"})
EVIDENCE_QUALITIES = frozenset({"exact", "estimated", "unknown", "not_applicable"})
USAGE_SOURCES = frozenset({"provider_receipt", "verified_host", "estimator", "none"})
CACHE_STATUSES = frozenset({"hit", "miss", "bypass", "unknown", "not_applicable"})
CACHE_EVIDENCE = frozenset({"provider_receipt", "verified_host", "application_lookup", "none"})

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"api[_-]?key\s*[:=]|password\s*[:=]|client[_-]?secret\s*[:=])"
)

_FORBIDDEN_KEYS = frozenset(
    {
        "prompt",
        "raw_prompt",
        "response",
        "raw_response",
        "script",
        "transcript",
        "url",
        "uri",
        "path",
        "absolute_path",
        "command",
        "environment",
        "env",
        "secret",
        "secrets",
        "token",
        "cookie",
        "cookies",
        "authorization",
        "password",
        "email",
        "account_id",
        "profile_id",
        "channel_id",
        "customer_id",
    }
)

_SAFE_DERIVED_KEYS = frozenset(
    {
        "token_quality",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "minimum_exact_token_coverage",
        "receipt_sha256",
        "input_sha256",
        "output_sha256",
    }
)
_SENSITIVE_KEY_PARTS = frozenset(
    {
        "prompt",
        "response",
        "script",
        "transcript",
        "url",
        "uri",
        "path",
        "command",
        "environment",
        "secret",
        "cookie",
        "authorization",
        "password",
        "email",
        "account",
        "profile",
        "channel",
        "customer",
    }
)

_CALL_KEYS = frozenset(
    {
        "schema_version",
        "event_type",
        "event_id",
        "run_id",
        "operation_id",
        "stage",
        "status",
        "provider",
        "model",
        "started_at",
        "finished_at",
        "attempt",
        "parent_event_id",
        "dedupe_key",
        "input_sha256",
        "output_sha256",
        "usage",
        "cache",
        "tags",
    }
)
_ARTIFACT_KEYS = frozenset(
    {
        "schema_version",
        "event_type",
        "event_id",
        "run_id",
        "artifact_id",
        "artifact_kind",
        "accepted",
        "gate_id",
        "completed_at",
        "artifact_sha256",
        "produced_by",
        "quality_score",
        "tags",
    }
)
_USAGE_KEYS = frozenset(
    {
        "token_quality",
        "cost_quality",
        "source",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cost_amount",
        "currency",
        "receipt_sha256",
    }
)
_CACHE_KEYS = frozenset({"status", "evidence_source", "key_sha256", "receipt_sha256"})
_POLICY_KEYS = frozenset(
    {
        "schema_version",
        "audit_name",
        "currency",
        "minimum_exact_cost_coverage",
        "minimum_exact_token_coverage",
        "maximum_retry_cost_ratio",
        "maximum_failed_cost_ratio",
        "require_accepted_artifact",
        "operations",
    }
)
_OPERATION_POLICY_KEYS = frozenset(
    {
        "stage",
        "required",
        "max_attempts",
        "max_exact_cost",
        "allowed_providers",
        "allowed_models",
    }
)


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_sha256(name: str, value: Any, *, required: bool = False, location: str | None = None) -> None:
    if value is None:
        if required:
            raise AuditInputError("FIELD_REQUIRED", f"{name} is required", location=location)
        return
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise AuditInputError("SHA256_INVALID", f"{name} must be a lowercase SHA-256 hex digest", location=location)


def validate_id(name: str, value: Any, *, required: bool = True, location: str | None = None) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise AuditInputError("ID_INVALID", f"{name} must match {_ID_RE.pattern}", location=location)


def parse_timestamp(name: str, value: Any, *, location: str | None = None) -> datetime:
    if not isinstance(value, str):
        raise AuditInputError("TIMESTAMP_INVALID", f"{name} must be an RFC3339 string", location=location)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditInputError("TIMESTAMP_INVALID", f"{name} is not RFC3339", location=location) from exc
    if parsed.tzinfo is None:
        raise AuditInputError("TIMESTAMP_TZ_REQUIRED", f"{name} must include a timezone", location=location)
    return parsed


def decimal_value(name: str, value: Any, *, location: str | None = None) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise AuditInputError("DECIMAL_INVALID", f"{name} must be a non-negative decimal", location=location)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AuditInputError("DECIMAL_INVALID", f"{name} must be a decimal", location=location) from exc
    if not result.is_finite() or result < 0:
        raise AuditInputError("DECIMAL_INVALID", f"{name} must be finite and non-negative", location=location)
    return result


def _reject_unknown_keys(payload: Mapping[str, Any], allowed: frozenset[str], *, location: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise AuditInputError("UNKNOWN_FIELD", f"unsupported fields: {', '.join(unknown)}", location=location)


def _reject_private_data(value: Any, *, location: str, key: str | None = None) -> None:
    if key is not None and key.lower() in _FORBIDDEN_KEYS:
        raise AuditInputError("PRIVATE_FIELD_FORBIDDEN", f"field {key!r} is forbidden", location=location)
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            _reject_private_data(child_value, location=location, key=str(child_key))
        return
    if isinstance(value, list):
        for child in value:
            _reject_private_data(child, location=location, key=key)
        return
    if not isinstance(value, str):
        return
    lowered = value.lower()
    if _SECRET_VALUE_RE.search(value):
        raise AuditInputError("SECRET_LIKE_VALUE", "secret-like value is forbidden", location=location)
    if (
        value.startswith(("/", "~", "\\"))
        or re.match(r"^[A-Za-z]:[\\/]", value)
        or lowered.startswith(("http://", "https://", "file://"))
        or "/users/" in lowered
        or "$home" in lowered
    ):
        raise AuditInputError("PRIVATE_LOCATION_FORBIDDEN", "URLs and absolute/private paths are forbidden", location=location)


def _validate_tags(value: Any, *, location: str) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping) or len(value) > 20:
        raise AuditInputError("TAGS_INVALID", "tags must be an object with at most 20 entries", location=location)
    for key, item in value.items():
        validate_id("tag key", key, location=location)
        lowered_key = str(key).lower()
        normalized_key = re.sub(r"[^a-z0-9]", "", lowered_key)
        token_key = bool(re.search(r"(?:^|[_-])token(?:$|[_-])", lowered_key))
        if lowered_key not in _SAFE_DERIVED_KEYS and (
            token_key or any(part in normalized_key for part in _SENSITIVE_KEY_PARTS)
        ):
            raise AuditInputError("PRIVATE_FIELD_FORBIDDEN", f"tag field {key!r} is forbidden", location=location)
        if not isinstance(item, (str, int, float, bool)) or isinstance(item, (dict, list)):
            raise AuditInputError("TAGS_INVALID", "tag values must be scalar", location=location)
        _reject_private_data(item, location=location, key=str(key))


def _validate_nonnegative_int(name: str, value: Any, *, required: bool, location: str) -> int | None:
    if value is None and not required:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AuditInputError("INTEGER_INVALID", f"{name} must be a non-negative integer", location=location)
    return value


def _validate_usage(value: Any, *, location: str) -> None:
    if not isinstance(value, Mapping):
        raise AuditInputError("USAGE_INVALID", "usage must be an object", location=location)
    _reject_unknown_keys(value, _USAGE_KEYS, location=f"{location}.usage")
    token_quality = value.get("token_quality")
    cost_quality = value.get("cost_quality")
    source = value.get("source")
    if token_quality not in EVIDENCE_QUALITIES:
        raise AuditInputError("TOKEN_QUALITY_INVALID", "invalid token_quality", location=location)
    if cost_quality not in EVIDENCE_QUALITIES:
        raise AuditInputError("COST_QUALITY_INVALID", "invalid cost_quality", location=location)
    if source not in USAGE_SOURCES:
        raise AuditInputError("USAGE_SOURCE_INVALID", "invalid usage source", location=location)

    input_tokens = _validate_nonnegative_int(
        "input_tokens", value.get("input_tokens"), required=token_quality in {"exact", "estimated"}, location=location
    )
    cached_tokens = _validate_nonnegative_int(
        "cached_input_tokens", value.get("cached_input_tokens"), required=False, location=location
    )
    _validate_nonnegative_int(
        "output_tokens", value.get("output_tokens"), required=token_quality in {"exact", "estimated"}, location=location
    )
    _validate_nonnegative_int("reasoning_tokens", value.get("reasoning_tokens"), required=False, location=location)
    if cached_tokens is not None and input_tokens is not None and cached_tokens > input_tokens:
        raise AuditInputError("CACHED_TOKENS_INVALID", "cached_input_tokens cannot exceed input_tokens", location=location)

    cost_amount = value.get("cost_amount")
    currency = value.get("currency")
    if cost_quality in {"exact", "estimated"}:
        decimal_value("cost_amount", cost_amount, location=location)
        if not isinstance(currency, str) or not _CURRENCY_RE.fullmatch(currency):
            raise AuditInputError("CURRENCY_INVALID", "currency must be ISO-4217 style uppercase", location=location)
    elif cost_amount is not None or currency is not None:
        raise AuditInputError(
            "UNSUPPORTED_EVIDENCE_VALUE",
            "unknown/not_applicable cost quality cannot carry cost values",
            location=location,
        )

    receipt = value.get("receipt_sha256")
    if token_quality == "exact" or cost_quality == "exact":
        if source not in {"provider_receipt", "verified_host"}:
            raise AuditInputError("EXACT_REQUIRES_VERIFIED_SOURCE", "exact evidence needs a verified source", location=location)
        validate_sha256("receipt_sha256", receipt, required=True, location=location)
    elif source in {"provider_receipt", "verified_host"}:
        validate_sha256("receipt_sha256", receipt, required=True, location=location)
    elif receipt is not None:
        validate_sha256("receipt_sha256", receipt, required=True, location=location)

    if token_quality == "estimated" or cost_quality == "estimated":
        if source != "estimator":
            raise AuditInputError("ESTIMATE_REQUIRES_ESTIMATOR", "estimated evidence requires source=estimator", location=location)
    if token_quality in {"unknown", "not_applicable"} and any(
        value.get(k) is not None for k in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")
    ):
        raise AuditInputError("UNKNOWN_TOKEN_VALUES", "unknown/not_applicable token quality cannot carry token values", location=location)


def _validate_cache(value: Any, *, location: str) -> None:
    if not isinstance(value, Mapping):
        raise AuditInputError("CACHE_INVALID", "cache must be an object", location=location)
    _reject_unknown_keys(value, _CACHE_KEYS, location=f"{location}.cache")
    status = value.get("status")
    evidence = value.get("evidence_source")
    if status not in CACHE_STATUSES:
        raise AuditInputError("CACHE_STATUS_INVALID", "invalid cache status", location=location)
    if evidence not in CACHE_EVIDENCE:
        raise AuditInputError("CACHE_EVIDENCE_INVALID", "invalid cache evidence source", location=location)
    validate_sha256("key_sha256", value.get("key_sha256"), required=False, location=location)
    validate_sha256("receipt_sha256", value.get("receipt_sha256"), required=False, location=location)
    if status in {"hit", "miss"}:
        if evidence == "none":
            raise AuditInputError("CACHE_CLAIM_REQUIRES_EVIDENCE", "hit/miss needs evidence", location=location)
        validate_sha256("receipt_sha256", value.get("receipt_sha256"), required=True, location=location)
    if status in {"unknown", "not_applicable"} and (
        evidence != "none" or value.get("key_sha256") is not None or value.get("receipt_sha256") is not None
    ):
        raise AuditInputError("CACHE_EVIDENCE_CONFLICT", "unknown/not_applicable cache state cannot carry evidence", location=location)


def validate_event(event: Any, *, location: str) -> dict[str, Any]:
    if not isinstance(event, Mapping):
        raise AuditInputError("EVENT_INVALID", "event must be an object", location=location)
    _reject_private_data(event, location=location)
    if event.get("schema_version") != EVENT_SCHEMA_VERSION:
        raise AuditInputError("SCHEMA_VERSION_INVALID", f"expected {EVENT_SCHEMA_VERSION}", location=location)
    event_type = event.get("event_type")
    if event_type not in EVENT_TYPES:
        raise AuditInputError("EVENT_TYPE_INVALID", "event_type must be call or artifact", location=location)
    _reject_unknown_keys(event, _CALL_KEYS if event_type == "call" else _ARTIFACT_KEYS, location=location)
    validate_id("event_id", event.get("event_id"), location=location)
    validate_id("run_id", event.get("run_id"), location=location)
    _validate_tags(event.get("tags"), location=location)

    if event_type == "call":
        validate_id("operation_id", event.get("operation_id"), location=location)
        validate_id("stage", event.get("stage"), location=location)
        validate_id("provider", event.get("provider"), location=location)
        validate_id("model", event.get("model"), location=location)
        status = event.get("status")
        if status not in CALL_STATUSES:
            raise AuditInputError("CALL_STATUS_INVALID", "invalid call status", location=location)
        started = parse_timestamp("started_at", event.get("started_at"), location=location)
        finished_raw = event.get("finished_at")
        if status == "started":
            if finished_raw is not None:
                raise AuditInputError("STARTED_HAS_FINISH", "started call cannot have finished_at", location=location)
        else:
            finished = parse_timestamp("finished_at", finished_raw, location=location)
            if finished < started:
                raise AuditInputError("NEGATIVE_LATENCY", "finished_at precedes started_at", location=location)
        attempt = _validate_nonnegative_int("attempt", event.get("attempt"), required=True, location=location)
        if attempt is None or attempt < 1:
            raise AuditInputError("ATTEMPT_INVALID", "attempt must be at least 1", location=location)
        validate_id("parent_event_id", event.get("parent_event_id"), required=False, location=location)
        if attempt == 1 and event.get("parent_event_id") is not None:
            raise AuditInputError("FIRST_ATTEMPT_HAS_PARENT", "first attempt cannot have parent_event_id", location=location)
        if attempt > 1 and not event.get("parent_event_id"):
            raise AuditInputError("RETRY_PARENT_REQUIRED", "retry attempt requires parent_event_id", location=location)
        validate_sha256("dedupe_key", event.get("dedupe_key"), required=True, location=location)
        validate_sha256("input_sha256", event.get("input_sha256"), required=False, location=location)
        validate_sha256("output_sha256", event.get("output_sha256"), required=False, location=location)
        _validate_usage(event.get("usage"), location=location)
        _validate_cache(event.get("cache"), location=location)
    else:
        validate_id("artifact_id", event.get("artifact_id"), location=location)
        validate_id("artifact_kind", event.get("artifact_kind"), location=location)
        if not isinstance(event.get("accepted"), bool):
            raise AuditInputError("ACCEPTED_INVALID", "accepted must be boolean", location=location)
        validate_id("gate_id", event.get("gate_id"), location=location)
        parse_timestamp("completed_at", event.get("completed_at"), location=location)
        validate_sha256("artifact_sha256", event.get("artifact_sha256"), required=True, location=location)
        produced_by = event.get("produced_by")
        if not isinstance(produced_by, list) or not produced_by:
            raise AuditInputError("PRODUCED_BY_INVALID", "produced_by must be a non-empty list", location=location)
        for item in produced_by:
            validate_id("produced_by item", item, location=location)
        score = event.get("quality_score")
        if score is not None and (
            isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= float(score) <= 1
        ):
            raise AuditInputError("QUALITY_SCORE_INVALID", "quality_score must be between 0 and 1", location=location)
    return dict(event)


def load_events(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    source_label = safe_path_label(source)
    if not source.is_file():
        raise AuditInputError("EVENT_FILE_NOT_FOUND", "event JSONL file does not exist", location=source_label)
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        location = f"{source_label}:{line_number}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AuditInputError("JSON_INVALID", exc.msg, location=location) from exc
        event = validate_event(payload, location=location)
        event_id = event["event_id"]
        if event_id in seen:
            raise AuditInputError("DUPLICATE_EVENT_ID", f"duplicate event_id {event_id}", location=location)
        seen.add(event_id)
        events.append(event)
    if not events:
        raise AuditInputError("EVENT_FILE_EMPTY", "no events found", location=source_label)
    return events


def _ratio(name: str, value: Any, *, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
        raise AuditInputError("RATIO_INVALID", f"{name} must be between 0 and 1", location=location)
    return float(value)


def load_policy(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    source_label = safe_path_label(source)
    if not source.is_file():
        raise AuditInputError("POLICY_FILE_NOT_FOUND", "policy file does not exist", location=source_label)
    try:
        policy = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditInputError("JSON_INVALID", exc.msg, location=source_label) from exc
    if not isinstance(policy, Mapping):
        raise AuditInputError("POLICY_INVALID", "policy must be an object", location=source_label)
    _reject_private_data(policy, location=source_label)
    _reject_unknown_keys(policy, _POLICY_KEYS, location=source_label)
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise AuditInputError("SCHEMA_VERSION_INVALID", f"expected {POLICY_SCHEMA_VERSION}", location=source_label)
    validate_id("audit_name", policy.get("audit_name"), location=source_label)
    currency = policy.get("currency")
    if not isinstance(currency, str) or not _CURRENCY_RE.fullmatch(currency):
        raise AuditInputError("CURRENCY_INVALID", "policy currency must be uppercase ISO style", location=source_label)
    for field in (
        "minimum_exact_cost_coverage",
        "minimum_exact_token_coverage",
        "maximum_retry_cost_ratio",
        "maximum_failed_cost_ratio",
    ):
        _ratio(field, policy.get(field), location=source_label)
    if not isinstance(policy.get("require_accepted_artifact"), bool):
        raise AuditInputError("POLICY_INVALID", "require_accepted_artifact must be boolean", location=source_label)
    operations = policy.get("operations")
    if not isinstance(operations, Mapping) or not operations:
        raise AuditInputError("POLICY_INVALID", "operations must be a non-empty object", location=source_label)
    normalized_operations: dict[str, dict[str, Any]] = {}
    for operation_id, value in operations.items():
        op_location = f"{source_label}:operations.{operation_id}"
        validate_id("operation_id", operation_id, location=op_location)
        if not isinstance(value, Mapping):
            raise AuditInputError("POLICY_OPERATION_INVALID", "operation policy must be an object", location=op_location)
        _reject_unknown_keys(value, _OPERATION_POLICY_KEYS, location=op_location)
        validate_id("stage", value.get("stage"), location=op_location)
        if not isinstance(value.get("required"), bool):
            raise AuditInputError("POLICY_OPERATION_INVALID", "required must be boolean", location=op_location)
        max_attempts = _validate_nonnegative_int(
            "max_attempts", value.get("max_attempts"), required=True, location=op_location
        )
        if max_attempts is None or max_attempts < 1:
            raise AuditInputError("POLICY_OPERATION_INVALID", "max_attempts must be at least 1", location=op_location)
        max_cost = decimal_value("max_exact_cost", value.get("max_exact_cost"), location=op_location)
        for list_field in ("allowed_providers", "allowed_models"):
            items = value.get(list_field)
            if not isinstance(items, list) or not items:
                raise AuditInputError("POLICY_OPERATION_INVALID", f"{list_field} must be non-empty", location=op_location)
            for item in items:
                validate_id(list_field, item, location=op_location)
        normalized = dict(value)
        normalized["max_exact_cost"] = format(max_cost, "f")
        normalized_operations[operation_id] = normalized
    normalized_policy = dict(policy)
    normalized_policy["operations"] = normalized_operations
    return normalized_policy


def input_digest(events: Iterable[Mapping[str, Any]], policy: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes({"events": list(events), "policy": policy}))
