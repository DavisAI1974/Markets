import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest

from research.kalshi.ng_exhaustion_two_day_step1_transfer_verify_20260824 import (
    verify_receipt_artifacts,
)


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = (
    ROOT
    / ".github/workflows/ng_exhaustion_two_day_step1_transfer_recovery_20260824.yml"
)


class TwoDayStep1TransferRecoveryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_is_one_shot_marker_gated_and_pinned_to_completed_run(self) -> None:
        self.assertIn("\n  push:", self.source)
        self.assertNotIn("workflow_dispatch:", self.source)
        self.assertIn(
            "research/kalshi/NG_EXHAUSTION_TWO_DAY_STEP1_TRANSFER_RECOVERY_LAUNCH_20260824.json",
            self.source,
        )
        self.assertIn(
            "TRANSFER_EXISTING_ARCHIVE_ONLY_LAST_ATTEMPT",
            self.source,
        )
        self.assertIn("ORIGINAL_RUN_ID: '32782745590'", self.source)
        self.assertIn("ORIGINAL_RUN_ATTEMPT: '1'", self.source)
        self.assertIn(
            "27cacc62681bc482e89eefcc3746f5d71958beab4e25816054e0c388a0346b33",
            self.source,
        )
        self.assertIn(
            "140c6234b8e6f4216416290aa50f4070160e200a3e7025cbca3aa08d0ef42e52",
            self.source,
        )
        self.assertIn(
            "a7611133f64064200de48cd2e7839fcea2510d51",
            self.source,
        )
        self.assertIn('test "$GITHUB_RUN_ATTEMPT" = "1"', self.source)
        self.assertIn("TRANSFER_RECOVERY_LAUNCH_NOT_CANONICAL", self.source)
        self.assertIn("TRANSFER_RECOVERY_EVENT_BASE_SHA_DRIFT", self.source)
        self.assertNotIn(
            "research/ng_exhaustion_mbo_2day_step1_finalize_20260824.py \\",
            self.source,
        )
        self.assertNotIn("--october-seconds", self.source)
        self.assertNotIn("--out-dir", self.source)

    def test_verifies_before_presigning_and_uses_one_upload_command(self) -> None:
        self.assertEqual(self.source.count("aws ssm send-command"), 2)
        verify_pass = self.source.index("TWO_DAY_ARCHIVE_IDENTITY=PASS")
        presign = self.source.index("generate_presigned_url")
        transfer_comment = self.source.index(
            "Transfer verified existing two-day Step-1 archive only"
        )
        self.assertLess(verify_pass, presign)
        self.assertLess(presign, transfer_comment)
        self.assertIn("test -f \"$archive\"", self.source)
        self.assertIn("sha256sum \"$archive\"", self.source)
        self.assertIn("test \"$actual_sha\" = \"$expected_sha\"", self.source)

    def test_uses_explicit_regional_sigv4_virtual_host_presigning(self) -> None:
        self.assertIn("https://s3.us-east-2.amazonaws.com", self.source)
        self.assertIn('signature_version="s3v4"', self.source)
        self.assertIn('s3={"addressing_style": "virtual"}', self.source)
        self.assertIn("ExpiresIn=900", self.source)
        self.assertIn("::add-mask::", self.source)
        self.assertIn('"executionTimeout": ["660"]', self.source)
        self.assertIn("--connect-timeout 10 --max-time 600", self.source)

    def test_probe_metadata_is_bound_to_exact_ready_body(self) -> None:
        probe_sha = hashlib.sha256(b"READY\n").hexdigest()
        self.assertEqual(
            probe_sha,
            "3dfa3fb239f56c778a1e9b33eb31328349edd155a95806dac4378904e88527e5",
        )
        self.assertEqual(self.source.count(probe_sha), 3)

    def test_archive_and_receipt_validation_fail_closed(self) -> None:
        self.assertIn("UNSAFE_TAR_MEMBER", self.source)
        self.assertIn("verify_receipt_artifacts", self.source)
        self.assertIn("DOWNLOADED_RECEIPT_SELF_HASH_DRIFT", self.source)
        self.assertIn("if len(verified) != 16 or set(verified)", self.source)
        self.assertIn("expected_files = {", self.source)
        for name in (
            "TWO_DAY_SECONDS.jsonl.gz",
            "LEGACY_CONTROL_EVENTS.jsonl.gz",
            "V4_NATIVE_FULL_EVENTS.jsonl.gz",
            "LEGACY_CONTROL_POPULATION.jsonl.gz",
            "V4_NATIVE_FULL_POPULATION.jsonl.gz",
            "DUAL_CENSUS_CROSSWALK.jsonl.gz",
            "TWO_DAY_SOURCE_MANIFEST.json",
            "TWO_DAY_VALIDATION_BYPASS_RECEIPT.json",
            "STEP1_DUAL_CENSUS_RECEIPT.json",
            "RESOURCE_USAGE.txt",
            "RUN.log",
        ):
            self.assertIn(name, self.source)

    def test_publishes_complete_last_without_github_artifact_retention(self) -> None:
        self.assertNotIn("actions/upload-artifact", self.source)
        verified_marker = self.source.index("FINAL_ARTIFACT_OBJECTS_VERIFIED=PASS")
        precomplete = self.source.index("PRECOMPLETE_RESULT_INVENTORY=PASS")
        complete_put = self.source.index('Key=prefix + "/COMPLETE.json"')
        self.assertLess(verified_marker, complete_put)
        self.assertLess(precomplete, complete_put)
        terminal_suffix = self.source[complete_put:]
        self.assertNotIn("head_object(", terminal_suffix)
        self.assertNotIn("list_objects_v2(", terminal_suffix)
        self.assertIn("FINAL_PUBLICATION_MARKER=PASS", self.source)
        self.assertIn("PROVIDER_LOGICAL_CALLS=0", self.source)
        self.assertIn("SSM_RUN_COMMAND_INVOCATIONS=2", self.source)

    def test_every_write_is_conditional_and_latch_precedes_ssm(self) -> None:
        latch = self.source.index('Key=prefix + "/RECOVERY_ATTEMPT.json"')
        first_ssm = self.source.index("aws ssm send-command")
        self.assertLess(latch, first_ssm)
        self.assertGreaterEqual(self.source.count('IfNoneMatch="*"'), 3)
        self.assertEqual(self.source.count("--header 'If-None-Match: *'"), 2)
        self.assertIn('retries={"total_max_attempts": 1', self.source)

    def test_actions_and_dependency_install_are_pinned_before_credentials(self) -> None:
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            self.source,
        )
        self.assertIn(
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            self.source,
        )
        install = self.source.index("--require-hashes")
        credentials = self.source.index("AWS_ACCESS_KEY_ID:")
        self.assertLess(install, credentials)


class ReceiptArtifactVerifierTests(unittest.TestCase):
    def test_verifies_json_and_deterministic_gzip_descriptor_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            json_path = root / "summary.json"
            json_path.write_text('{"ok":true}\n', encoding="utf-8")
            json_bytes = json_path.read_bytes()

            raw_jsonl = b'{"row":1}\n{"row":2}\n'
            gzip_path = root / "events.jsonl.gz"
            with gzip_path.open("wb") as raw_handle:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as handle:
                    handle.write(raw_jsonl)

            receipt = {
                "summary": {
                    "relative_path": json_path.name,
                    "bytes": len(json_bytes),
                    "sha256": hashlib.sha256(json_bytes).hexdigest(),
                },
                "events": {
                    "relative_path": gzip_path.name,
                    "rows": 2,
                    "uncompressed_jsonl_sha256": hashlib.sha256(raw_jsonl).hexdigest(),
                    "gzip_sha256": hashlib.sha256(gzip_path.read_bytes()).hexdigest(),
                },
            }

            verified = verify_receipt_artifacts(root, receipt)
            self.assertEqual(set(verified), {"summary.json", "events.jsonl.gz"})

    def test_rejects_gzip_row_count_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_jsonl = b'{"row":1}\n'
            gzip_path = root / "events.jsonl.gz"
            with gzip_path.open("wb") as raw_handle:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as handle:
                    handle.write(raw_jsonl)
            receipt = {
                "relative_path": gzip_path.name,
                "rows": 2,
                "uncompressed_jsonl_sha256": hashlib.sha256(raw_jsonl).hexdigest(),
                "gzip_sha256": hashlib.sha256(gzip_path.read_bytes()).hexdigest(),
            }
            with self.assertRaisesRegex(ValueError, "RECEIPT_ARTIFACT_ROW_COUNT_DRIFT"):
                verify_receipt_artifacts(root, receipt)

    def test_rejects_gzip_uncompressed_size_over_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_jsonl = b'{"row":1}\n'
            gzip_path = root / "events.jsonl.gz"
            with gzip_path.open("wb") as raw_handle:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as handle:
                    handle.write(raw_jsonl)
            receipt = {
                "relative_path": gzip_path.name,
                "rows": 1,
                "uncompressed_jsonl_sha256": hashlib.sha256(raw_jsonl).hexdigest(),
                "gzip_sha256": hashlib.sha256(gzip_path.read_bytes()).hexdigest(),
            }
            with self.assertRaisesRegex(ValueError, "JSONL_SIZE_CAP_EXCEEDED"):
                verify_receipt_artifacts(root, receipt, max_uncompressed_bytes=1)


if __name__ == "__main__":
    unittest.main()
