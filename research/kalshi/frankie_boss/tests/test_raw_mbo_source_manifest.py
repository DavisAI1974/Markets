from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "raw_mbo_source_manifest.py"
SPEC = importlib.util.spec_from_file_location("raw_mbo_source_manifest_under_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load source manifest module from {MODULE_PATH}")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

ManifestError = module.ManifestError
build_source_manifest = module.build_source_manifest
manifest_hash = module.manifest_hash
progress_snapshot = module.progress_snapshot


class RawMboSourceManifestTests(unittest.TestCase):
    def make_files(self, root: Path):
        paths = []
        for date, size in (("20211001", 11), ("20211003", 13), ("20211004", 17), ("20211005", 19)):
            path = root / f"glbx-mdp3-{date}.mbo.dbn.zst"
            path.write_bytes((date.encode("ascii") + b"x" * size))
            paths.append(path)
        return paths

    def counter(self, path: Path) -> int:
        return {
            "20211001": 100,
            "20211003": 20,
            "20211004": 200,
            "20211005": 300,
        }[path.name.split("-")[2].split(".")[0]]

    def test_manifest_accepts_only_exact_native_four_file_roster(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_files(Path(tmp))
            manifest = build_source_manifest(paths, count_records=self.counter)
        self.assertEqual(manifest["source_kind"], "NATIVE_DBN_MBO")
        self.assertEqual(manifest["causal_clock"], "ts_recv_ns")
        self.assertEqual([row["date"] for row in manifest["sources"]], ["20211001", "20211003", "20211004", "20211005"])
        self.assertEqual([row["role"] for row in manifest["sources"]], ["WARMUP_DEVELOPMENT", "WARMUP_DEVELOPMENT", "HELD_OUT_BLIND", "HELD_OUT_BLIND"])
        self.assertEqual(manifest["total_mbo_records"], 620)
        self.assertEqual(manifest["held_out_mbo_records"], 500)
        self.assertEqual(manifest["manifest_hash"], manifest_hash(manifest))

    def test_reduced_or_derived_surface_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.make_files(root)
            paths[-1] = root / "V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz"
            paths[-1].write_bytes(b"derived")
            with self.assertRaises(ManifestError):
                build_source_manifest(paths, count_records=self.counter)

    def test_missing_extra_duplicate_or_wrong_date_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.make_files(root)
            with self.assertRaises(ManifestError):
                build_source_manifest(paths[:-1], count_records=self.counter)
            with self.assertRaises(ManifestError):
                build_source_manifest(paths + [paths[0]], count_records=self.counter)
            wrong = root / "glbx-mdp3-20211006.mbo.dbn.zst"
            wrong.write_bytes(b"wrong")
            with self.assertRaises(ManifestError):
                build_source_manifest(paths[:-1] + [wrong], count_records=lambda _: 1)

    def test_progress_uses_actual_raw_record_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_source_manifest(self.make_files(Path(tmp)), count_records=self.counter)
        p = progress_snapshot(manifest, completed_mbo_records=310, phase="RAW_MBO_REPLAY")
        self.assertEqual(p["completed_mbo_records"], 310)
        self.assertEqual(p["total_mbo_records"], 620)
        self.assertEqual(p["percent_complete"], 50.0)
        self.assertEqual(p["denominator"], "HASH_BOUND_NATIVE_MBO_RECORD_COUNT")
        with self.assertRaises(ManifestError):
            progress_snapshot(manifest, completed_mbo_records=621, phase="RAW_MBO_REPLAY")

    def test_manifest_hash_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_source_manifest(self.make_files(Path(tmp)), count_records=self.counter)
        poisoned = dict(manifest)
        poisoned["total_mbo_records"] = 999
        with self.assertRaisesRegex(ManifestError, "hash|reconcile"):
            progress_snapshot(poisoned, completed_mbo_records=1, phase="RAW_MBO_REPLAY")

    def test_zero_or_noninteger_record_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_files(Path(tmp))
            with self.assertRaises(ManifestError):
                build_source_manifest(paths, count_records=lambda _: 0)
            with self.assertRaises(ManifestError):
                build_source_manifest(paths, count_records=lambda _: 1.5)


if __name__ == "__main__":
    unittest.main()
