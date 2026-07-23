from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

KALSHI = Path(__file__).resolve().parents[1]
if str(KALSHI) not in sys.path:
    sys.path.insert(0, str(KALSHI))

import ng_corpus_inspection as inspection
import ng_corpus_materialization as target


class FakeS3:
    def __init__(self, data: dict[str, bytes], *, paginated: bool = False) -> None:
        self.data = data
        self.paginated = paginated
        self.calls: list[dict[str, Any]] = []

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        prefix = kwargs.get("Prefix", "")
        keys = sorted(key for key in self.data if key.startswith(prefix))
        token = kwargs.get("ContinuationToken")
        if self.paginated and len(keys) > 1 and not token:
            keys = keys[:1]
            truncated = True
            next_token = "next"
        elif self.paginated and token:
            keys = keys[1:]
            truncated = False
            next_token = None
        else:
            truncated = False
            next_token = None
        response: dict[str, Any] = {
            "IsTruncated": truncated,
            "Contents": [
                {
                    "Key": key,
                    "Size": len(self.data[key]),
                    "ETag": f'"etag-{index}"',
                    "LastModified": "2026-07-22T00:00:00Z",
                    "StorageClass": "STANDARD",
                }
                for index, key in enumerate(keys)
            ],
        }
        if next_token:
            response["NextContinuationToken"] = next_token
        return response

    def download_file(self, bucket: str, key: str, target_path: str) -> None:
        Path(target_path).write_bytes(self.data[key])


class BadSizeS3(FakeS3):
    def download_file(self, bucket: str, key: str, target_path: str) -> None:
        Path(target_path).write_bytes(self.data[key] + b"x")


def refingerprint(value: dict[str, Any], field: str) -> dict[str, Any]:
    value.pop(field, None)
    value[field] = target._fp(value)
    return value


class CorpusMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = {"ng/l1/a.dbn": b"abc", "ng/l1/b.dbn": b"defg"}
        self.s3 = FakeS3(self.data, paginated=True)
        self.snapshot = target.snapshot_s3(
            self.s3,
            bucket="bucket",
            prefixes=["ng/l1/"],
            observed_at="2026-07-22T00:00:00Z",
        )
        self.bindings = target.binding_template(self.snapshot)

    def definition(self) -> dict[str, Any]:
        return inspection.definition_observation(
            dataset="GLBX.MDP3",
            publisher_id=1,
            instrument_id=996,
            raw_symbol="NGK26",
            definition_date="2026-03-01",
            definition_start_s=1.0,
            definition_end_s=9999999999.0,
            observed_from="s3://bucket/definitions/ngk26.dbn",
            observed_at="2026-07-22T00:00:00Z",
            source_sha256="a" * 64,
            source_size_bytes=100,
        )

    def approve_first(self, *, day: str = "20260330") -> dict[str, Any]:
        value = copy.deepcopy(self.bindings)
        row = value["bindings"][0]
        row.update(
            {
                "review_status": "APPROVED",
                "source_id": "l1-20260330",
                "corpus_id": "l1_dense_one_year",
                "lane": "l1_trades",
                "day": day,
                "definition": self.definition(),
            }
        )
        refingerprint(row, "binding_fingerprint")
        value["bindings"][1]["review_status"] = "REJECTED"
        refingerprint(value["bindings"][1], "binding_fingerprint")
        refingerprint(value, "binding_manifest_fingerprint")
        return value

    def test_snapshot_paginates_and_asserts_no_identity(self) -> None:
        self.assertEqual(self.snapshot["object_count"], 2)
        self.assertEqual(len(self.s3.calls), 2)
        self.assertTrue(
            all(
                row["contract_identity_status"] == "UNOBSERVED"
                for row in self.snapshot["objects"]
            )
        )
        self.assertFalse(self.snapshot["identity_inferred_from_object_name"])

    def test_snapshot_deduplicates_overlapping_prefixes(self) -> None:
        value = target.snapshot_s3(
            FakeS3(self.data),
            bucket="bucket",
            prefixes=["ng/", "ng/l1/"],
            observed_at="2026-07-22T00:00:00Z",
        )
        self.assertEqual(value["object_count"], 2)

    def test_binding_template_requires_review(self) -> None:
        self.assertTrue(
            all(
                row["review_status"] == "REVIEW_REQUIRED"
                for row in self.bindings["bindings"]
            )
        )
        self.assertTrue(self.bindings["all_bindings_require_explicit_review"])

    def test_snapshot_tamper_is_rejected(self) -> None:
        value = copy.deepcopy(self.snapshot)
        value["objects"][0]["size_bytes"] += 1
        refingerprint(value, "snapshot_fingerprint")
        with self.assertRaises(target.CorpusMaterializationError):
            target.validate_snapshot(value)

    def test_approved_binding_requires_observed_definition(self) -> None:
        value = self.approve_first()
        value["bindings"][0]["definition"] = None
        refingerprint(value["bindings"][0], "binding_fingerprint")
        refingerprint(value, "binding_manifest_fingerprint")
        with self.assertRaises(target.CorpusMaterializationError):
            target.validate_bindings(
                value,
                snapshot=self.snapshot,
                require_approved=True,
            )

    def test_approved_day_must_be_inside_corpus_window(self) -> None:
        value = self.approve_first(day="20270101")
        with self.assertRaises(target.CorpusMaterializationError):
            target.validate_bindings(
                value,
                snapshot=self.snapshot,
                require_approved=True,
            )

    def test_complete_assertion_requires_complete_snapshot_scope(self) -> None:
        value = self.approve_first()
        control = value["corpora"][0]
        control.update(
            {
                "expected_days": ["20260330"],
                "expected_object_count": 1,
                "inventory_scope_verified": True,
                "inventory_complete_asserted": True,
            }
        )
        refingerprint(value, "binding_manifest_fingerprint")
        with self.assertRaises(target.CorpusMaterializationError):
            target.validate_bindings(
                value,
                snapshot=self.snapshot,
                require_approved=True,
            )

    def test_materialization_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(target.CorpusMaterializationError):
                target.materialize_approved(
                    self.s3,
                    snapshot=self.snapshot,
                    bindings=self.approve_first(),
                    output_root=Path(tmp),
                    confirm_download=False,
                    max_total_bytes=100,
                )

    def test_materialization_respects_byte_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(target.CorpusMaterializationError):
                target.materialize_approved(
                    self.s3,
                    snapshot=self.snapshot,
                    bindings=self.approve_first(),
                    output_root=Path(tmp),
                    confirm_download=True,
                    max_total_bytes=2,
                )

    def test_materialization_hashes_exact_bytes(self) -> None:
        bindings = self.approve_first()
        with tempfile.TemporaryDirectory() as tmp:
            receipt = target.materialize_approved(
                self.s3,
                snapshot=self.snapshot,
                bindings=bindings,
                output_root=Path(tmp),
                confirm_download=True,
                max_total_bytes=100,
            )
            row = receipt["objects"][0]
            self.assertEqual(Path(row["materialized_path"]).read_bytes(), b"abc")
            self.assertEqual(
                row["sha256"],
                target.hashlib.sha256(b"abc").hexdigest(),
            )
            target.validate_materialization(
                receipt,
                snapshot=self.snapshot,
                bindings=bindings,
                verify_files=True,
            )

    def test_materialization_rejects_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(target.CorpusMaterializationError):
                target.materialize_approved(
                    BadSizeS3(self.data),
                    snapshot=self.snapshot,
                    bindings=self.approve_first(),
                    output_root=Path(tmp),
                    confirm_download=True,
                    max_total_bytes=100,
                )

    def test_materialization_refuses_overwrite(self) -> None:
        bindings = self.approve_first()
        with tempfile.TemporaryDirectory() as tmp:
            target.materialize_approved(
                self.s3,
                snapshot=self.snapshot,
                bindings=bindings,
                output_root=Path(tmp),
                confirm_download=True,
                max_total_bytes=100,
            )
            with self.assertRaises(target.CorpusMaterializationError):
                target.materialize_approved(
                    self.s3,
                    snapshot=self.snapshot,
                    bindings=bindings,
                    output_root=Path(tmp),
                    confirm_download=True,
                    max_total_bytes=100,
                )

    def test_materialization_receipt_tamper_is_rejected(self) -> None:
        bindings = self.approve_first()
        with tempfile.TemporaryDirectory() as tmp:
            receipt = target.materialize_approved(
                self.s3,
                snapshot=self.snapshot,
                bindings=bindings,
                output_root=Path(tmp),
                confirm_download=True,
                max_total_bytes=100,
            )
            receipt["objects"][0]["sha256"] = "b" * 64
            refingerprint(receipt, "receipt_fingerprint")
            with self.assertRaises(target.CorpusMaterializationError):
                target.validate_materialization(
                    receipt,
                    snapshot=self.snapshot,
                    bindings=bindings,
                    verify_files=True,
                )

    def test_build_plan_links_snapshot_binding_definition_and_bytes(self) -> None:
        bindings = self.approve_first()
        snapshot_before = copy.deepcopy(self.snapshot)
        bindings_before = copy.deepcopy(bindings)
        with tempfile.TemporaryDirectory() as tmp:
            receipt = target.materialize_approved(
                self.s3,
                snapshot=self.snapshot,
                bindings=bindings,
                output_root=Path(tmp),
                confirm_download=True,
                max_total_bytes=100,
            )
            plan, bundle = target.build_inspection_plan(
                snapshot=self.snapshot,
                bindings=bindings,
                receipt=receipt,
            )
            source = plan["corpora"][0]["sources"][0]
            self.assertEqual(source["definition"]["raw_symbol"], "NGK26")
            self.assertEqual(source["day"], "20260330")
            self.assertFalse(source["identity_inferred_from_filename"])
            target.validate_bundle(
                bundle,
                snapshot=self.snapshot,
                bindings=bindings,
                receipt=receipt,
            )
        self.assertEqual(self.snapshot, snapshot_before)
        self.assertEqual(bindings, bindings_before)

    def test_bundle_tamper_and_authority_are_rejected(self) -> None:
        bindings = self.approve_first()
        with tempfile.TemporaryDirectory() as tmp:
            receipt = target.materialize_approved(
                self.s3,
                snapshot=self.snapshot,
                bindings=bindings,
                output_root=Path(tmp),
                confirm_download=True,
                max_total_bytes=100,
            )
            _, bundle = target.build_inspection_plan(
                snapshot=self.snapshot,
                bindings=bindings,
                receipt=receipt,
            )
            self.assertFalse(bundle["execution_authority"])
            self.assertFalse(bundle["may_update_ng_brain"])
            self.assertEqual(
                bundle["brokerage_contract"],
                "tastytrade_not_ibkr",
            )
            self.assertEqual(bundle["cme_event_contracts_mode"], "SHADOW")
            self.assertFalse(bundle["options_lane_started"])
            bundle["execution_authority"] = True
            refingerprint(bundle, "bundle_fingerprint")
            with self.assertRaises(target.CorpusMaterializationError):
                target.validate_bundle(
                    bundle,
                    snapshot=self.snapshot,
                    bindings=bindings,
                    receipt=receipt,
                )


if __name__ == "__main__":
    unittest.main()
