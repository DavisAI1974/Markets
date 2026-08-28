from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "benchmark_checkpoint.py"
SPEC = importlib.util.spec_from_file_location("frankie_benchmark_checkpoint_under_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load checkpoint module from {MODULE_PATH}")
checkpoint_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checkpoint_module)

CheckpointError = checkpoint_module.CheckpointError
build_checkpoint = checkpoint_module.build_checkpoint
checkpoint_hash = checkpoint_module.checkpoint_hash
load_checkpoint = checkpoint_module.load_checkpoint
progress_percent = checkpoint_module.progress_percent
verify_chain = checkpoint_module.verify_chain
write_checkpoint_atomic = checkpoint_module.write_checkpoint_atomic


H0 = "0" * 64
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64


class BenchmarkCheckpointTests(unittest.TestCase):
    def make(self, **overrides):
        values = dict(
            run_id="B2-clean",
            controller="B2_RECURRENT_GRANITE",
            memory_mode="CLEAN",
            sequence=0,
            source_manifest_hash=H1,
            completed_mbo_records=250,
            total_mbo_records=1000,
            event_group_open=False,
            adapter_state_hash=H2,
            controller_state_hash=None,
            previous_checkpoint_hash=None,
            phase="RAW_MBO_REPLAY",
            locked=False,
        )
        values.update(overrides)
        return build_checkpoint(**values)

    def test_checkpoint_core_has_no_torch_dependency(self):
        self.assertNotIn("torch", sys.modules)

    def test_progress_is_exact_record_fraction_not_elapsed_time(self):
        self.assertEqual(progress_percent(0, 1000), 0.0)
        self.assertEqual(progress_percent(250, 1000), 25.0)
        self.assertEqual(progress_percent(1000, 1000), 100.0)
        with self.assertRaises(CheckpointError):
            progress_percent(1001, 1000)
        with self.assertRaises(CheckpointError):
            progress_percent(0, 0)

    def test_hash_is_deterministic_and_bound_to_content(self):
        a = self.make()
        b = self.make()
        self.assertEqual(a, b)
        self.assertEqual(a["checkpoint_hash"], checkpoint_hash(a))
        self.assertEqual(a["checkpoint_hash"], b["checkpoint_hash"])
        moved = self.make(completed_mbo_records=251)
        self.assertNotEqual(a["checkpoint_hash"], moved["checkpoint_hash"])

    def test_mid_event_group_checkpoint_fails_closed(self):
        with self.assertRaisesRegex(CheckpointError, "F_LAST"):
            self.make(event_group_open=True)

    def test_source_hash_and_state_hashes_must_be_sha256(self):
        with self.assertRaises(CheckpointError):
            self.make(source_manifest_hash="not-a-hash")
        with self.assertRaises(CheckpointError):
            self.make(adapter_state_hash="bad")
        with self.assertRaises(CheckpointError):
            self.make(controller_state_hash="bad")

    def test_chain_requires_exact_sequence_source_and_monotonic_cursor(self):
        first = self.make(sequence=0, completed_mbo_records=100)
        second = self.make(
            sequence=1,
            completed_mbo_records=200,
            previous_checkpoint_hash=first["checkpoint_hash"],
        )
        verify_chain([first, second])

        skipped = self.make(
            sequence=2,
            completed_mbo_records=200,
            previous_checkpoint_hash=first["checkpoint_hash"],
        )
        with self.assertRaises(CheckpointError):
            verify_chain([first, skipped])

        regressed = self.make(
            sequence=1,
            completed_mbo_records=99,
            previous_checkpoint_hash=first["checkpoint_hash"],
        )
        with self.assertRaises(CheckpointError):
            verify_chain([first, regressed])

        drifted_source = self.make(
            sequence=1,
            source_manifest_hash=H3,
            completed_mbo_records=200,
            previous_checkpoint_hash=first["checkpoint_hash"],
        )
        with self.assertRaises(CheckpointError):
            verify_chain([first, drifted_source])

    def test_chain_rejects_tampering(self):
        first = self.make(sequence=0, completed_mbo_records=100)
        tampered = dict(first)
        tampered["completed_mbo_records"] = 900
        with self.assertRaisesRegex(CheckpointError, "hash"):
            verify_chain([tampered])

    def test_locked_checkpoint_is_terminal(self):
        first = self.make(sequence=0, completed_mbo_records=100)
        locked = self.make(
            sequence=1,
            completed_mbo_records=1000,
            previous_checkpoint_hash=first["checkpoint_hash"],
            phase="FINAL_LOCK",
            locked=True,
        )
        verify_chain([first, locked])
        after = self.make(
            sequence=2,
            completed_mbo_records=1000,
            previous_checkpoint_hash=locked["checkpoint_hash"],
            phase="POST_LOCK",
        )
        with self.assertRaisesRegex(CheckpointError, "locked"):
            verify_chain([first, locked, after])

    def test_controller_and_memory_mode_cannot_drift_inside_run(self):
        first = self.make(sequence=0, completed_mbo_records=100)
        changed = self.make(
            sequence=1,
            completed_mbo_records=200,
            previous_checkpoint_hash=first["checkpoint_hash"],
            memory_mode="MEMORY_ASSISTED",
        )
        with self.assertRaises(CheckpointError):
            verify_chain([first, changed])

    def test_schema_is_closed_against_answer_bearing_passthrough(self):
        checkpoint = self.make()
        forbidden = {
            "step1_answer": "x",
            "outcome": "up",
            "reveal": True,
            "self_fit": 0.9,
            "self_score": 0.8,
        }
        for key, value in forbidden.items():
            poisoned = dict(checkpoint)
            poisoned[key] = value
            poisoned["checkpoint_hash"] = checkpoint_hash(poisoned)
            with self.assertRaisesRegex(CheckpointError, "unknown"):
                verify_chain([poisoned])

    def test_atomic_write_and_load_round_trip(self):
        checkpoint = self.make()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            write_checkpoint_atomic(path, checkpoint)
            self.assertEqual(load_checkpoint(path), checkpoint)
            self.assertFalse(any(p.name.endswith(".tmp") for p in path.parent.iterdir()))

            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["completed_mbo_records"] = 999
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(CheckpointError, "hash"):
                load_checkpoint(path)


if __name__ == "__main__":
    unittest.main()
