import copy
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_corpus_basis_gate import CANONICAL_DATES, _fixture_rows  # noqa: E402
from ng_g15_exact_l1_recovery import (  # noqa: E402
    DATASET,
    SCHEMA,
    STYPE_IN,
    L1RecoveryError,
    acquire_exact_l1,
    build_recovery_plan,
    validate_plan,
    validate_receipt,
)


class Metadata:
    def __init__(self, cost):
        self.cost = cost
        self.calls = []

    def get_cost(self, **kwargs):
        self.calls.append(kwargs)
        return self.cost


class Batch:
    def __init__(self):
        self.submit = []
        self.downloads = []

    def submit_job(self, **kwargs):
        self.submit.append(kwargs)
        return {"id": "job-1", "state": "done"}

    def get_job_details(self, job_id):
        return {"id": job_id, "state": "done"}

    def download(self, job_id, output_dir):
        self.downloads.append((job_id, output_dir))
        root = Path(output_dir)
        (root / "part").mkdir()
        (root / "part" / "a.dbn.zst").write_bytes(b"abc")
        (root / "part" / "b.dbn.zst").write_bytes(b"defg")


class Client:
    def __init__(self, cost=0.25):
        self.metadata = Metadata(cost)
        self.batch = Batch()


class PlanTests(unittest.TestCase):
    def test_wrong_pre_roll_builds_one_exact_ngj26_request(self):
        plan = build_recovery_plan(_fixture_rows(wrong_pre_roll_l1=True))
        validate_plan(plan)
        self.assertEqual(plan["status"], "RECOVERY_PLAN_READY")
        self.assertEqual(plan["blocked_l1_days"], list(CANONICAL_DATES[:6]))
        request = plan["requests"][0]
        self.assertEqual((request["symbol"], request["expected_instrument_id"]), ("NGJ26", 1008))
        self.assertEqual((request["start"], request["end_exclusive"]), ("2026-03-13", "2026-03-20"))
        self.assertEqual((request["schema"], request["stype_in"]), (SCHEMA, STYPE_IN))
        self.assertNotIn(".v.0", request["pull_command"])

    def test_matched_inventory_needs_no_recovery(self):
        plan = build_recovery_plan(_fixture_rows(wrong_pre_roll_l1=False))
        validate_plan(plan)
        self.assertEqual(plan["status"], "NO_RECOVERY_REQUIRED")
        self.assertEqual(plan["requests"], [])

    def test_mbo_block_blocks_acquisition_plan(self):
        rows = _fixture_rows(wrong_pre_roll_l1=True)
        rows[0]["mbo_present"] = False
        plan = build_recovery_plan(rows)
        validate_plan(plan)
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["requests"], [])

    def test_two_contracts_are_never_pooled(self):
        rows = _fixture_rows(wrong_pre_roll_l1=True)
        for row in rows:
            if row["date"] >= "20260320":
                row["l1_instrument_id"] = [1008]
                row["l1_basis_correct"] = False
        plan = build_recovery_plan(rows)
        validate_plan(plan)
        self.assertEqual([request["symbol"] for request in plan["requests"]], ["NGJ26", "NGK26"])

    def test_source_inventory_is_immutable(self):
        rows = _fixture_rows(wrong_pre_roll_l1=True)
        before = copy.deepcopy(rows)
        build_recovery_plan(rows)
        self.assertEqual(rows, before)

    def test_plan_tampering_is_rejected(self):
        plan = build_recovery_plan(_fixture_rows(wrong_pre_roll_l1=True))
        plan["requests"][0]["stype_in"] = "continuous"
        with self.assertRaises(L1RecoveryError):
            validate_plan(plan)

    def test_plan_cannot_grant_paid_or_execution_authority(self):
        plan = build_recovery_plan(_fixture_rows(wrong_pre_roll_l1=True))
        self.assertFalse(plan["paid_pull_authority"])
        self.assertFalse(plan["execution_authority"])
        self.assertFalse(plan["may_update_manifest_without_observation"])


class PullTests(unittest.TestCase):
    def test_pull_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(L1RecoveryError):
                acquire_exact_l1(
                    symbol="NGJ26",
                    start="2026-03-13",
                    end="2026-03-20",
                    output_dir=Path(temp_dir) / "out",
                    max_cost=1,
                    confirm_paid_pull=False,
                    client=Client(),
                )

    def test_cost_gate_prevents_submission(self):
        client = Client(cost=2.0)
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(L1RecoveryError):
                acquire_exact_l1(
                    symbol="NGJ26",
                    start="2026-03-13",
                    end="2026-03-20",
                    output_dir=Path(temp_dir) / "out",
                    max_cost=1,
                    confirm_paid_pull=True,
                    client=client,
                )
        self.assertEqual(client.batch.submit, [])

    def test_exact_raw_contract_request_and_receipt(self):
        client = Client()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "out"
            receipt = acquire_exact_l1(
                symbol="NGJ26",
                start="2026-03-13",
                end="2026-03-20",
                output_dir=output,
                max_cost=1,
                confirm_paid_pull=True,
                client=client,
            )
            validate_receipt(receipt, verify_files=True)
            request = client.batch.submit[0]
            self.assertEqual(request["dataset"], DATASET)
            self.assertEqual(request["schema"], SCHEMA)
            self.assertEqual(request["symbols"], ["NGJ26"])
            self.assertEqual(request["stype_in"], STYPE_IN)
            self.assertEqual(receipt["identity_status"], "UNKNOWN_UNTIL_NORMALIZED_AND_INVENTORIED")
            self.assertEqual(receipt["downloaded_bytes"], 7)

    def test_invalid_or_oversized_ranges_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(L1RecoveryError):
                acquire_exact_l1(
                    symbol="NGJ26",
                    start="2026-03-20",
                    end="2026-03-13",
                    output_dir=Path(temp_dir) / "out",
                    max_cost=1,
                    confirm_paid_pull=True,
                    client=Client(),
                )
            with self.assertRaises(L1RecoveryError):
                acquire_exact_l1(
                    symbol="NGJ26",
                    start="2026-01-01",
                    end="2026-03-20",
                    output_dir=Path(temp_dir) / "out2",
                    max_cost=1,
                    confirm_paid_pull=True,
                    client=Client(),
                )

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "out"
            output.mkdir()
            with self.assertRaises(L1RecoveryError):
                acquire_exact_l1(
                    symbol="NGJ26",
                    start="2026-03-13",
                    end="2026-03-20",
                    output_dir=output,
                    max_cost=1,
                    confirm_paid_pull=True,
                    client=Client(),
                )

    def test_receipt_detects_download_tampering(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "out"
            receipt = acquire_exact_l1(
                symbol="NGJ26",
                start="2026-03-13",
                end="2026-03-20",
                output_dir=output,
                max_cost=1,
                confirm_paid_pull=True,
                client=Client(),
            )
            (output / "part" / "a.dbn.zst").write_bytes(b"changed")
            with self.assertRaises(L1RecoveryError):
                validate_receipt(receipt, verify_files=True)

    def test_receipt_fingerprint_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            receipt = acquire_exact_l1(
                symbol="NGJ26",
                start="2026-03-13",
                end="2026-03-20",
                output_dir=Path(temp_dir) / "out",
                max_cost=1,
                confirm_paid_pull=True,
                client=Client(),
            )
            receipt["identity_status"] = "VERIFIED"
            with self.assertRaises(L1RecoveryError):
                validate_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
