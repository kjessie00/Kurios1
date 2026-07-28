from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from media_economics_audit.engine import audit_files, compare_audits
from media_economics_audit.errors import AuditInputError
from media_economics_audit.metrics import build_audit
from media_economics_audit.report import verify_manifest, write_audit_bundle
from media_economics_audit.schema import load_events, load_policy, validate_event

ROOT = Path(__file__).resolve().parents[1]
PAIRED = ROOT / "examples" / "paired"
PROBLEMATIC = ROOT / "examples" / "problematic"


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def sample_call() -> dict:
    return {
        "schema_version": "media-economics-event.v1",
        "event_type": "call",
        "event_id": "call-1",
        "run_id": "run-1",
        "operation_id": "research",
        "stage": "research",
        "status": "succeeded",
        "provider": "openai",
        "model": "gpt-5.6-pro",
        "started_at": "2026-07-28T00:00:00Z",
        "finished_at": "2026-07-28T00:00:01Z",
        "attempt": 1,
        "parent_event_id": None,
        "dedupe_key": sha("dedupe"),
        "input_sha256": sha("input"),
        "output_sha256": sha("output"),
        "usage": {
            "token_quality": "exact",
            "cost_quality": "exact",
            "source": "provider_receipt",
            "input_tokens": 100,
            "cached_input_tokens": 20,
            "output_tokens": 10,
            "reasoning_tokens": 2,
            "cost_amount": "0.100000",
            "currency": "USD",
            "receipt_sha256": sha("receipt"),
        },
        "cache": {
            "status": "hit",
            "evidence_source": "provider_receipt",
            "key_sha256": sha("cache-key"),
            "receipt_sha256": sha("cache-receipt"),
        },
        "tags": {"fixture": "unit"},
    }


def sample_artifact(produced_by: list[str] | None = None) -> dict:
    return {
        "schema_version": "media-economics-event.v1",
        "event_type": "artifact",
        "event_id": "artifact-event-1",
        "run_id": "run-1",
        "artifact_id": "artifact-1",
        "artifact_kind": "script",
        "accepted": True,
        "gate_id": "qa-v1",
        "completed_at": "2026-07-28T00:00:02Z",
        "artifact_sha256": sha("artifact"),
        "produced_by": produced_by or ["call-1"],
        "quality_score": 0.9,
        "tags": {"fixture": "unit"},
    }


def sample_policy() -> dict:
    return {
        "schema_version": "media-economics-policy.v1",
        "audit_name": "unit-audit",
        "currency": "USD",
        "minimum_exact_cost_coverage": 1.0,
        "minimum_exact_token_coverage": 1.0,
        "maximum_retry_cost_ratio": 0.2,
        "maximum_failed_cost_ratio": 0.2,
        "require_accepted_artifact": True,
        "operations": {
            "research": {
                "stage": "research",
                "required": True,
                "max_attempts": 2,
                "max_exact_cost": "1.000000",
                "allowed_providers": ["openai"],
                "allowed_models": ["gpt-5.6-pro"],
            }
        },
    }


class PairedExampleTests(unittest.TestCase):
    def test_baseline_audit_exact_metrics(self) -> None:
        report = audit_files(PAIRED / "baseline.jsonl", PAIRED / "baseline-policy.json")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["summary"]["exact_cost"], "1.420000")
        self.assertEqual(report["summary"]["accepted_artifact_count"], 2)
        self.assertEqual(report["summary"]["cost_per_accepted_artifact"], "0.710000")
        self.assertEqual(report["summary"]["retry_call_count"], 1)
        self.assertEqual(report["summary"]["exact_cost_coverage"], 1.0)

    def test_optimized_audit_exact_metrics(self) -> None:
        report = audit_files(PAIRED / "optimized.jsonl", PAIRED / "optimized-policy.json")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["summary"]["exact_cost"], "0.790000")
        self.assertEqual(report["summary"]["accepted_artifact_count"], 2)
        self.assertEqual(report["summary"]["cost_per_accepted_artifact"], "0.395000")
        self.assertEqual(report["summary"]["retry_call_count"], 0)

    def test_comparison_requires_quality_and_exact_coverage(self) -> None:
        baseline = audit_files(PAIRED / "baseline.jsonl", PAIRED / "baseline-policy.json")
        optimized = audit_files(PAIRED / "optimized.jsonl", PAIRED / "optimized-policy.json")
        comparison = compare_audits(baseline, optimized, comparison_name="paired")
        self.assertEqual(comparison["conclusion"], "IMPROVED")
        self.assertTrue(comparison["quality_floor_preserved"])
        self.assertEqual(comparison["delta"]["exact_cost"], "-0.630000")
        self.assertAlmostEqual(comparison["delta"]["exact_cost_reduction_ratio"], 0.443662)

    def test_problematic_fixture_surfaces_adversarial_findings(self) -> None:
        report = audit_files(PROBLEMATIC / "events.jsonl", PROBLEMATIC / "policy.json")
        codes = {finding["code"] for finding in report["findings"]}
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("DUPLICATE_SUCCESSFUL_WORK", codes)
        self.assertIn("UNPLANNED_OPERATION", codes)
        self.assertIn("EXACT_COST_COVERAGE_LOW", codes)
        self.assertIn("REQUIRED_OPERATION_MISSING", codes)
        self.assertEqual(report["summary"]["exact_cost"], "0.000000")
        self.assertEqual(report["summary"]["unknown_cost_call_count"], 3)
        self.assertIsNone(report["summary"]["cost_per_accepted_artifact"])


class SchemaSafetyTests(unittest.TestCase):
    def test_cache_claim_requires_evidence(self) -> None:
        event = sample_call()
        event["cache"]["evidence_source"] = "none"
        with self.assertRaisesRegex(AuditInputError, "CACHE_CLAIM_REQUIRES_EVIDENCE"):
            validate_event(event, location="fixture")

    def test_raw_prompt_field_is_rejected(self) -> None:
        event = sample_call()
        event["prompt"] = "do not store me"
        with self.assertRaisesRegex(AuditInputError, "PRIVATE_FIELD_FORBIDDEN"):
            validate_event(event, location="fixture")

    def test_absolute_path_is_rejected(self) -> None:
        event = sample_call()
        event["tags"]["source"] = "/" + "Users/alice/private.txt"
        with self.assertRaisesRegex(AuditInputError, "PRIVATE_LOCATION_FORBIDDEN"):
            validate_event(event, location="fixture")

    def test_retry_requires_parent(self) -> None:
        event = sample_call()
        event["attempt"] = 2
        with self.assertRaisesRegex(AuditInputError, "RETRY_PARENT_REQUIRED"):
            validate_event(event, location="fixture")

    def test_exact_usage_requires_receipt(self) -> None:
        event = sample_call()
        event["usage"]["receipt_sha256"] = None
        with self.assertRaisesRegex(AuditInputError, "FIELD_REQUIRED"):
            validate_event(event, location="fixture")

    def test_estimate_requires_estimator_source(self) -> None:
        event = sample_call()
        event["usage"]["token_quality"] = "estimated"
        event["usage"]["cost_quality"] = "estimated"
        with self.assertRaisesRegex(AuditInputError, "ESTIMATE_REQUIRES_ESTIMATOR"):
            validate_event(event, location="fixture")

    def test_duplicate_event_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            raw = json.dumps(sample_call())
            path.write_text(raw + "\n" + raw + "\n")
            with self.assertRaisesRegex(AuditInputError, "DUPLICATE_EVENT_ID"):
                load_events(path)

    def test_first_attempt_cannot_have_parent(self) -> None:
        event = sample_call()
        event["parent_event_id"] = "call-0"
        with self.assertRaisesRegex(AuditInputError, "FIRST_ATTEMPT_HAS_PARENT"):
            validate_event(event, location="fixture")

    def test_sensitive_tag_key_is_rejected(self) -> None:
        event = sample_call()
        event["tags"]["customer_identifier"] = "opaque-1"
        with self.assertRaisesRegex(AuditInputError, "PRIVATE_FIELD_FORBIDDEN"):
            validate_event(event, location="fixture")


class AuditPolicyTests(unittest.TestCase):
    def test_missing_artifact_call_reference_is_high(self) -> None:
        report = build_audit([sample_call(), sample_artifact(["missing-call"])], sample_policy())
        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("ARTIFACT_CALL_REFERENCE_MISSING", codes)
        self.assertEqual(report["status"], "FAIL")

    def test_duplicate_successful_work_is_detected(self) -> None:
        first = sample_call()
        second = deepcopy(first)
        second["event_id"] = "call-2"
        second["started_at"] = "2026-07-28T00:00:02Z"
        second["finished_at"] = "2026-07-28T00:00:03Z"
        second["output_sha256"] = sha("output-2")
        second["usage"]["receipt_sha256"] = sha("receipt-2")
        second["cache"]["receipt_sha256"] = sha("cache-receipt-2")
        report = build_audit([first, second, sample_artifact(["call-2"])], sample_policy())
        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("DUPLICATE_SUCCESSFUL_WORK", codes)
        self.assertEqual(report["summary"]["duplicate_exact_cost"], "0.100000")

    def test_unplanned_operation_is_detected(self) -> None:
        event = sample_call()
        event["operation_id"] = "hidden-call"
        report = build_audit([event, sample_artifact()], sample_policy())
        self.assertIn("UNPLANNED_OPERATION", {item["code"] for item in report["findings"]})

    def test_no_accepted_artifact_is_not_unit_economics(self) -> None:
        artifact = sample_artifact()
        artifact["accepted"] = False
        report = build_audit([sample_call(), artifact], sample_policy())
        self.assertIn("NO_ACCEPTED_ARTIFACT", {item["code"] for item in report["findings"]})
        self.assertIsNone(report["summary"]["cost_per_accepted_artifact"])

    def test_incomplete_exact_coverage_makes_comparison_inconclusive(self) -> None:
        baseline = build_audit([sample_call(), sample_artifact()], sample_policy())
        candidate_event = sample_call()
        candidate_event["usage"] = {
            "token_quality": "unknown",
            "cost_quality": "unknown",
            "source": "none",
            "input_tokens": None,
            "cached_input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "cost_amount": None,
            "currency": None,
            "receipt_sha256": None,
        }
        candidate = build_audit([candidate_event, sample_artifact()], sample_policy())
        comparison = compare_audits(baseline, candidate)
        self.assertEqual(comparison["conclusion"], "INCONCLUSIVE")
        self.assertEqual(comparison["confidence"], "low")

    def test_retry_parent_reference_and_scope_are_audited(self) -> None:
        retry = sample_call()
        retry["event_id"] = "call-2"
        retry["attempt"] = 2
        retry["parent_event_id"] = "missing-parent"
        retry["usage"]["receipt_sha256"] = sha("receipt-2")
        retry["cache"]["receipt_sha256"] = sha("cache-receipt-2")
        report = build_audit([retry, sample_artifact(["call-2"])], sample_policy())
        self.assertIn("RETRY_PARENT_REFERENCE_MISSING", {item["code"] for item in report["findings"]})

    def test_multiple_runs_and_cross_run_artifact_are_rejected(self) -> None:
        other = sample_call()
        other["event_id"] = "call-other"
        other["run_id"] = "run-2"
        other["usage"]["receipt_sha256"] = sha("receipt-other")
        other["cache"]["receipt_sha256"] = sha("cache-other")
        artifact = sample_artifact(["call-other"])
        report = build_audit([sample_call(), other, artifact], sample_policy())
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("MULTIPLE_RUN_IDS", codes)
        self.assertIn("ARTIFACT_RUN_MISMATCH", codes)
        self.assertEqual(report["status"], "FAIL")

    def test_duplicate_artifact_identity_is_detected(self) -> None:
        second = sample_artifact()
        second["event_id"] = "artifact-event-2"
        second["artifact_sha256"] = sha("artifact-2")
        report = build_audit([sample_call(), sample_artifact(), second], sample_policy())
        self.assertIn("DUPLICATE_ARTIFACT_ID", {item["code"] for item in report["findings"]})

    def test_duplicate_usage_receipt_is_detected(self) -> None:
        second = deepcopy(sample_call())
        second["event_id"] = "call-2"
        second["dedupe_key"] = sha("dedupe-2")
        second["output_sha256"] = sha("output-2")
        second["cache"]["receipt_sha256"] = sha("cache-2")
        report = build_audit([sample_call(), second, sample_artifact(["call-2"])], sample_policy())
        self.assertIn("DUPLICATE_USAGE_RECEIPT", {item["code"] for item in report["findings"]})

    def test_currency_mismatch_is_critical_even_for_unplanned_call(self) -> None:
        event = sample_call()
        event["operation_id"] = "hidden-call"
        event["usage"]["currency"] = "EUR"
        report = build_audit([event, sample_artifact()], sample_policy())
        finding = next(item for item in report["findings"] if item["code"] == "CURRENCY_MISMATCH")
        self.assertEqual(finding["severity"], "critical")

    def test_dedupe_scope_collision_is_detected(self) -> None:
        second = deepcopy(sample_call())
        second["event_id"] = "call-2"
        second["operation_id"] = "hidden-call"
        second["usage"]["receipt_sha256"] = sha("receipt-2")
        second["cache"]["receipt_sha256"] = sha("cache-2")
        report = build_audit([sample_call(), second, sample_artifact()], sample_policy())
        self.assertIn("DEDUPE_SCOPE_COLLISION", {item["code"] for item in report["findings"]})

    def test_comparison_preserves_na_unit_cost(self) -> None:
        artifact = sample_artifact()
        artifact["accepted"] = False
        baseline = build_audit([sample_call(), artifact], sample_policy())
        candidate = deepcopy(baseline)
        candidate["source_digest_sha256"] = sha("candidate-audit")
        comparison = compare_audits(baseline, candidate)
        self.assertIsNone(comparison["baseline"]["cost_per_accepted_artifact"])
        self.assertIsNone(comparison["candidate"]["cost_per_accepted_artifact"])
        self.assertIsNone(comparison["delta"]["cost_per_accepted_artifact"])


class ArtifactBundleTests(unittest.TestCase):
    def test_bundle_is_deterministic_and_manifest_verifies(self) -> None:
        report = audit_files(PAIRED / "baseline.jsonl", PAIRED / "baseline-policy.json")
        with tempfile.TemporaryDirectory() as left_temp, tempfile.TemporaryDirectory() as right_temp:
            left = Path(left_temp)
            right = Path(right_temp)
            write_audit_bundle(report, left)
            write_audit_bundle(report, right)
            left_files = {path.name: path.read_bytes() for path in left.iterdir()}
            right_files = {path.name: path.read_bytes() for path in right.iterdir()}
            self.assertEqual(left_files, right_files)
            self.assertEqual(verify_manifest(left / "manifest.sha256"), [])

    def test_manifest_detects_tampering(self) -> None:
        report = audit_files(PAIRED / "baseline.jsonl", PAIRED / "baseline-policy.json")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            write_audit_bundle(report, output)
            (output / "audit.md").write_text("tampered\n")
            self.assertEqual(verify_manifest(output / "manifest.sha256"), ["hash_mismatch:audit.md"])

    def test_manifest_rejects_non_hex_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / "audit.json").write_text("{}\n")
            (output / "manifest.sha256").write_text("z" * 64 + "  audit.json\n")
            with self.assertRaisesRegex(AuditInputError, "MANIFEST_INVALID"):
                verify_manifest(output / "manifest.sha256")

    def test_manifest_rejects_duplicate_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            target = output / "audit.json"
            target.write_text("{}\n")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            (output / "manifest.sha256").write_text(
                f"{digest}  audit.json\n{digest}  audit.json\n"
            )
            with self.assertRaisesRegex(AuditInputError, "MANIFEST_DUPLICATE_PATH"):
                verify_manifest(output / "manifest.sha256")


if __name__ == "__main__":
    unittest.main()
