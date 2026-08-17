import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "research"))
import ng_exhaustion_s3_stage as s

ART = Path(os.environ.get("NG_EXHAUSTION_BLIND_ARTIFACT", "/mnt/data/ng_exhaustion_blind_input_artifact.zip"))
CLF = ROOT / "research" / "FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json"


@unittest.skipUnless(ART.exists(), "frozen blind artifact not materialized")
class NGExhaustionS3StageTests(unittest.TestCase):
    def test_stage_exact_frozen_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "stage"
            m = s.stage(ART, CLF, out)
            self.assertEqual(m["partition_totals"]["records"], 1711)
            self.assertEqual({d: p["records"] for d, p in m["partitions"].items()}, s.EXPECTED_DAY_COUNTS)
            self.assertEqual(
                {d: p["compressed_sha256"] for d, p in m["partitions"].items()},
                s.EXPECTED_PARTITION_SHA256,
            )
            self.assertEqual(s.sha256_file(out / m["canonical_source"]["path"]), s.EXPECTED_ARTIFACT_SHA256)
            self.assertTrue((out / "content_manifest.json").exists())
            for info in m["partitions"].values():
                gz = (out / info["path"]).read_bytes()
                self.assertEqual(gz[:3], b"\x1f\x8b\x08")
                self.assertEqual(gz[9], 255)

    def test_artifact_sha_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.zip"
            data = bytearray(ART.read_bytes())
            data[-1] ^= 1
            bad.write_bytes(data)
            with self.assertRaises(s.StageError):
                s.validate_source(bad, CLF)

    def test_partitions_are_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a"
            b = Path(td) / "b"
            ma = s.stage(ART, CLF, a)
            mb = s.stage(ART, CLF, b)
            self.assertEqual(
                {d: p["compressed_sha256"] for d, p in ma["partitions"].items()},
                {d: p["compressed_sha256"] for d, p in mb["partitions"].items()},
            )
            self.assertEqual(
                {d: p["compressed_sha256"] for d, p in ma["partitions"].items()},
                s.EXPECTED_PARTITION_SHA256,
            )


if __name__ == "__main__":
    unittest.main()
