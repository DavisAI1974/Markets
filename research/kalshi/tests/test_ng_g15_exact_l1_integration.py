import copy
import datetime as dt
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_corpus_basis_gate import _fixture_rows, evaluate_manifest  # noqa: E402
from ng_g15_exact_l1_integration import (  # noqa: E402
    ExactL1IntegrationError,
    _sha,
    build_day_map_template,
    build_integration_bundle,
    promote_bundle,
    validate_bundle,
    validate_day_map,
)
from ng_g15_exact_l1_recovery import (  # noqa: E402
    RECEIPT_SCHEMA,
    _sha as recovery_sha,
    build_recovery_plan,
)

BLOCKED_DAYS = ["20260313", "20260315", "20260316", "20260317", "20260318", "20260319"]


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_raw_files(root: Path, *, wrong_identity_day: str | None = None, outside_definition_day: str | None = None):
    files = []
    for day in BLOCKED_DAYS:
        stamp = dt.datetime(
            int(day[:4]), int(day[4:6]), int(day[6:]), 12, tzinfo=dt.timezone.utc
        ).timestamp()
        if day == outside_definition_day:
            stamp = dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc).timestamp()
        trade = {
            "action": "T",
            "ts_event_s": stamp,
            "price": 3.1,
            "size": 2,
            "side": "B",
            "instrument_id": 996 if day == wrong_identity_day else 1008,
        }
        path = root / f"GLBX-{day}.mbp-1.jsonl"
        path.write_text(
            json.dumps({"action": "A", "ts_event_s": stamp - 1}) + "\n"
            + json.dumps(trade) + "\n",
            encoding="utf-8",
        )
        files.append({
            "relative_path": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": file_sha(path),
        })
    return files


def recovery_receipt(root: Path, files: list[dict]) -> dict:
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "dataset": "GLBX.MDP3",
        "schema_requested": "mbp-1",
        "stype_in": "raw_symbol",
        "symbol_requested": "NGJ26",
        "start": "2026-03-13",
        "end_exclusive": "2026-03-20",
        "estimated_cost_usd": 1.0,
        "max_cost_usd": 2.0,
        "job_id": "fixture-job",
        "output_dir": str(root),
        "files": files,
        "downloaded_bytes": sum(row["size_bytes"] for row in files),
        "identity_status": "UNKNOWN_UNTIL_NORMALIZED_AND_INVENTORIED",
        "remote_presence_claimed_before_download": False,
        "raw_files_immutable": True,
        "may_update_manifest_without_observation": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    receipt["fingerprint"] = recovery_sha(receipt)
    return receipt


def confirmed_day_map(plan: dict, receipt: dict) -> dict:
    result = build_day_map_template(plan, receipt)
    result.pop("fingerprint")
    result["status"] = "CONFIRMED"
    for entry in result["entries"]:
        entry["confirmed"] = True
    result["fingerprint"] = _sha(result)
    return result


def definition() -> dict:
    return {
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": 1008,
        "raw_symbol": "NGJ26",
        "definition_date": "2026-03-01",
        "definition_start_s": dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc).timestamp(),
        "definition_end_s": dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc).timestamp(),
        "observed_at": "2026-07-22T00:00:00Z",
        "source": "fixture-definition",
    }


class ExactL1DayMapTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_recovery_plan(_fixture_rows(wrong_pre_roll_l1=True))

    def test_template_is_advisory_and_unconfirmed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = recovery_receipt(root, write_raw_files(root))
            result = build_day_map_template(self.plan, receipt)
            self.assertEqual(result["status"], "REVIEW_REQUIRED")
            self.assertTrue(result["filename_dates_are_non_authoritative"])
            self.assertEqual(
                sorted(row["candidate_session_day"] for row in result["entries"]),
                BLOCKED_DAYS,
            )
            self.assertTrue(all(row["confirmed"] is False for row in result["entries"]))

    def test_unconfirmed_map_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = recovery_receipt(root, write_raw_files(root))
            day_map = build_day_map_template(self.plan, receipt)
            with self.assertRaises(ExactL1IntegrationError):
                validate_day_map(day_map, plan=self.plan, receipt=receipt)

    def test_duplicate_day_ownership_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = recovery_receipt(root, write_raw_files(root))
            day_map = confirmed_day_map(self.plan, receipt)
            day_map.pop("fingerprint")
            day_map["entries"][1]["session_day"] = day_map["entries"][0]["session_day"]
            day_map["fingerprint"] = _sha(day_map)
            with self.assertRaises(ExactL1IntegrationError):
                validate_day_map(day_map, plan=self.plan, receipt=receipt)


class ExactL1IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.inventory = _fixture_rows(wrong_pre_roll_l1=True)
        self.plan = build_recovery_plan(self.inventory)

    def build(self, temp: Path, **raw_kwargs):
        raw = temp / "raw"
        raw.mkdir()
        files = write_raw_files(raw, **raw_kwargs)
        receipt = recovery_receipt(raw, files)
        day_map = confirmed_day_map(self.plan, receipt)
        bundle = temp / "bundle"
        return receipt, day_map, bundle

    def test_builds_matched_candidate_without_mutating_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root)
            inventory_before = copy.deepcopy(self.inventory)
            raw_before = {row["relative_path"]: row["sha256"] for row in receipt["files"]}
            result = build_integration_bundle(
                inventory_rows=self.inventory,
                plan=self.plan,
                receipt=receipt,
                day_map=day_map,
                definition=definition(),
                bundle_dir=bundle,
            )
            self.assertEqual(result["candidate_basis_status"], "MATCHED_L1_MBO_READY")
            self.assertEqual(self.inventory, inventory_before)
            self.assertEqual(
                {row["relative_path"]: file_sha(Path(receipt["output_dir"]) / row["relative_path"])
                 for row in receipt["files"]},
                raw_before,
            )
            validated = validate_bundle(bundle)
            self.assertEqual(validated["basis_report"]["status"], "MATCHED_L1_MBO_READY")
            self.assertFalse(validated["receipt"]["actual_outcomes_used"])
            self.assertFalse(validated["receipt"]["may_update_ng_brain"])
            self.assertFalse(validated["receipt"]["execution_authority"])

    def test_unrequested_post_roll_days_remain_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root)
            original = {row["date"]: copy.deepcopy(row) for row in self.inventory}
            build_integration_bundle(
                inventory_rows=self.inventory, plan=self.plan, receipt=receipt,
                day_map=day_map, definition=definition(), bundle_dir=bundle,
            )
            candidate = validate_bundle(bundle)["manifest"]
            by_day = {row["date"]: row for row in candidate}
            for day in ["20260320", "20260322", "20260323", "20260324", "20260325", "20260326", "20260327"]:
                self.assertEqual(by_day[day], original[day])

    def test_wrong_observed_definition_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root)
            observed = definition()
            observed["instrument_id"] = 996
            with self.assertRaises(ExactL1IntegrationError):
                build_integration_bundle(
                    inventory_rows=self.inventory, plan=self.plan, receipt=receipt,
                    day_map=day_map, definition=observed, bundle_dir=bundle,
                )
            self.assertFalse(bundle.exists())

    def test_decoded_wrong_instrument_is_rejected_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root, wrong_identity_day="20260318")
            with self.assertRaises(Exception):
                build_integration_bundle(
                    inventory_rows=self.inventory, plan=self.plan, receipt=receipt,
                    day_map=day_map, definition=definition(), bundle_dir=bundle,
                )
            self.assertFalse(bundle.exists())

    def test_event_outside_definition_period_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root, outside_definition_day="20260318")
            with self.assertRaises(ExactL1IntegrationError):
                build_integration_bundle(
                    inventory_rows=self.inventory, plan=self.plan, receipt=receipt,
                    day_map=day_map, definition=definition(), bundle_dir=bundle,
                )
            self.assertFalse(bundle.exists())

    def test_existing_bundle_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root)
            bundle.mkdir()
            with self.assertRaises(ExactL1IntegrationError):
                build_integration_bundle(
                    inventory_rows=self.inventory, plan=self.plan, receipt=receipt,
                    day_map=day_map, definition=definition(), bundle_dir=bundle,
                )

    def test_bundle_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root)
            build_integration_bundle(
                inventory_rows=self.inventory, plan=self.plan, receipt=receipt,
                day_map=day_map, definition=definition(), bundle_dir=bundle,
            )
            normalized = next((bundle / "normalized").glob("*.jsonl"))
            normalized.write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(ExactL1IntegrationError):
                validate_bundle(bundle)

    def test_promotion_requires_confirmation_and_writes_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root)
            build_integration_bundle(
                inventory_rows=self.inventory, plan=self.plan, receipt=receipt,
                day_map=day_map, definition=definition(), bundle_dir=bundle,
            )
            canonical = root / "g15_mbo_l1_manifest.json"
            canonical.write_text(json.dumps(self.inventory), encoding="utf-8")
            with self.assertRaises(ExactL1IntegrationError):
                promote_bundle(bundle_dir=bundle, canonical_inventory=canonical, confirm_promote=False)
            result = promote_bundle(bundle_dir=bundle, canonical_inventory=canonical, confirm_promote=True)
            self.assertEqual(result["status"], "PROMOTED_MATCHED_L1_MBO_READY")
            self.assertTrue(Path(result["backup"]).is_file())
            self.assertEqual(evaluate_manifest(json.loads(canonical.read_text()))["status"], "MATCHED_L1_MBO_READY")

    def test_source_inventory_drift_blocks_promotion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt, day_map, bundle = self.build(root)
            build_integration_bundle(
                inventory_rows=self.inventory, plan=self.plan, receipt=receipt,
                day_map=day_map, definition=definition(), bundle_dir=bundle,
            )
            changed = copy.deepcopy(self.inventory)
            changed[0]["operator_note"] = "changed after bundle"
            canonical = root / "g15_mbo_l1_manifest.json"
            canonical.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ExactL1IntegrationError):
                promote_bundle(bundle_dir=bundle, canonical_inventory=canonical, confirm_promote=True)


if __name__ == "__main__":
    unittest.main()
