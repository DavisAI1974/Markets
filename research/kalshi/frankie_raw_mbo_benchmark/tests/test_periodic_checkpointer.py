"""Tests for periodic save points on long native raw-MBO runs."""
from __future__ import annotations

import gzip
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from research.kalshi.frankie_raw_mbo_benchmark import a_memory_rt_resume_20260828 as base
from research.kalshi.frankie_raw_mbo_benchmark.periodic_checkpointer import (
    PeriodicCheckpointer,
    PeriodicCheckpointError,
    adapter_state_path,
    canonical_hash,
    checkpoint_path,
    controller_state_path,
    load_chain,
    resume_from_latest,
)
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import V4MboAdapter

TOTAL = 1_000_000
MANIFEST_HASH = "a" * 64


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class PeriodicCheckpointerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "checkpoints"
        self.clock = FakeClock()
        self.synced: list[tuple[Path, ...]] = []
        self.adapter = V4MboAdapter()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make(self, **kwargs) -> PeriodicCheckpointer:
        defaults = dict(
            run_id="run-test-1",
            controller="A_CHATGPT",
            memory_mode="CLEAN",
            source_manifest_hash=MANIFEST_HASH,
            total_mbo_records=TOTAL,
            checkpoint_dir=self.dir,
            phase="REPLAY",
            every_records=100,
            every_seconds=60.0,
            durable_sync=lambda paths: self.synced.append(tuple(paths)),
            monotonic=self.clock,
        )
        defaults.update(kwargs)
        return PeriodicCheckpointer(**defaults)

    # --- interval behavior -------------------------------------------------

    def test_seal_start_writes_sequence_zero_and_syncs(self) -> None:
        cp = self.make()
        checkpoint = cp.seal_start(self.adapter)
        self.assertEqual(checkpoint["sequence"], 0)
        self.assertIsNone(checkpoint["previous_checkpoint_hash"])
        self.assertEqual(checkpoint["completed_mbo_records"], 0)
        self.assertTrue(checkpoint_path(self.dir, 0).exists())
        self.assertTrue(adapter_state_path(self.dir, 0).exists())
        self.assertEqual(len(self.synced), 1)

    def test_saves_on_record_interval(self) -> None:
        cp = self.make()
        cp.seal_start(self.adapter)
        self.assertIsNone(cp.maybe_save(self.adapter, completed_mbo_records=99))
        saved = cp.maybe_save(self.adapter, completed_mbo_records=100)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["sequence"], 1)
        self.assertEqual(saved["completed_mbo_records"], 100)

    def test_saves_on_wall_clock_interval_when_records_are_slow(self) -> None:
        """A phase that produces few records must still create save points."""
        cp = self.make()
        cp.seal_start(self.adapter)
        self.assertIsNone(cp.maybe_save(self.adapter, completed_mbo_records=5))
        self.clock.advance(60.0)
        saved = cp.maybe_save(self.adapter, completed_mbo_records=5)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["completed_mbo_records"], 5)

    def test_interval_resets_after_each_save(self) -> None:
        cp = self.make()
        cp.seal_start(self.adapter)
        cp.maybe_save(self.adapter, completed_mbo_records=100)
        self.assertIsNone(cp.maybe_save(self.adapter, completed_mbo_records=150))
        self.assertIsNotNone(cp.maybe_save(self.adapter, completed_mbo_records=200))

    def test_refuses_to_save_inside_an_open_event_group(self) -> None:
        """An F_LAST-closed boundary is the only lawful resume point."""
        cp = self.make()
        cp.seal_start(self.adapter)
        self.assertIsNone(
            cp.maybe_save(self.adapter, completed_mbo_records=500, event_group_open=True)
        )
        self.assertEqual(cp.sequence, 0)
        self.assertIsNotNone(
            cp.maybe_save(self.adapter, completed_mbo_records=500, event_group_open=False)
        )

    def test_interval_save_before_seal_start_is_refused(self) -> None:
        cp = self.make()
        with self.assertRaises(PeriodicCheckpointError):
            cp.maybe_save(self.adapter, completed_mbo_records=100)

    def test_double_seal_start_is_refused(self) -> None:
        cp = self.make()
        cp.seal_start(self.adapter)
        with self.assertRaises(PeriodicCheckpointError):
            cp.seal_start(self.adapter)

    def test_nonpositive_intervals_are_refused(self) -> None:
        with self.assertRaises(PeriodicCheckpointError):
            self.make(every_records=0)
        with self.assertRaises(PeriodicCheckpointError):
            self.make(every_seconds=0)

    # --- chain integrity ---------------------------------------------------

    def test_chain_is_contiguous_and_hash_linked(self) -> None:
        cp = self.make()
        cp.seal_start(self.adapter)
        for cursor in (100, 200, 300):
            cp.maybe_save(self.adapter, completed_mbo_records=cursor)
        chain = load_chain(self.dir)
        self.assertEqual([c["sequence"] for c in chain], [0, 1, 2, 3])
        for previous, current in zip(chain, chain[1:]):
            self.assertEqual(current["previous_checkpoint_hash"], previous["checkpoint_hash"])

    def test_final_seal_locks_and_requires_full_denominator(self) -> None:
        cp = self.make()
        cp.seal_start(self.adapter)
        with self.assertRaises(PeriodicCheckpointError):
            cp.seal_final(self.adapter, completed_mbo_records=TOTAL - 1)
        final = cp.seal_final(self.adapter, completed_mbo_records=TOTAL)
        self.assertTrue(final["locked"])
        self.assertEqual(final["progress_percent"], 100.0)

    def test_load_chain_on_empty_directory_is_refused(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(PeriodicCheckpointError):
            load_chain(self.dir)

    # --- controller state --------------------------------------------------

    def test_controller_state_hash_matches_existing_convention(self) -> None:
        """Save points must stay verifiable by the already-written resume path."""
        cp = self.make()
        controller = {"cursor": 0, "families": ["a", "b"]}
        checkpoint = cp.seal_start(self.adapter, controller_state=controller)
        self.assertEqual(checkpoint["controller_state_hash"], base.canonical_hash(controller))
        written = json.loads(controller_state_path(self.dir, 0).read_text(encoding="utf-8"))
        self.assertEqual(canonical_hash(written), checkpoint["controller_state_hash"])

    def test_controller_state_is_optional(self) -> None:
        cp = self.make()
        checkpoint = cp.seal_start(self.adapter)
        self.assertIsNone(checkpoint["controller_state_hash"])
        self.assertFalse(controller_state_path(self.dir, 0).exists())

    # --- resume ------------------------------------------------------------

    def test_resume_restores_the_newest_save_point(self) -> None:
        cp = self.make()
        cp.seal_start(self.adapter)
        cp.maybe_save(self.adapter, completed_mbo_records=100)
        latest = cp.maybe_save(self.adapter, completed_mbo_records=200)
        resumed, adapter = resume_from_latest(self.dir)
        self.assertEqual(resumed["checkpoint_hash"], latest["checkpoint_hash"])
        self.assertEqual(resumed["completed_mbo_records"], 200)
        self.assertIsInstance(adapter, V4MboAdapter)

    def test_resume_rejects_a_tampered_adapter_state(self) -> None:
        """A truncated or partially synced state file must fail here, not mid-run."""
        cp = self.make()
        cp.seal_start(self.adapter)
        cp.maybe_save(self.adapter, completed_mbo_records=100)
        target = adapter_state_path(self.dir, 1)
        with gzip.open(target, "rb") as handle:
            state = json.loads(handle.read().decode("utf-8"))
        state["record_count"] = int(state["record_count"]) + 1
        with gzip.open(target, "wb") as handle:
            handle.write(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        with self.assertRaises(PeriodicCheckpointError):
            resume_from_latest(self.dir)

    def test_resume_refuses_a_completed_run(self) -> None:
        cp = self.make()
        cp.seal_start(self.adapter)
        cp.seal_final(self.adapter, completed_mbo_records=TOTAL)
        with self.assertRaises(PeriodicCheckpointError):
            resume_from_latest(self.dir)

    # --- durable sync ------------------------------------------------------

    def test_every_save_point_is_pushed_to_durable_storage(self) -> None:
        cp = self.make()
        cp.seal_start(self.adapter, controller_state={"cursor": 0})
        cp.maybe_save(self.adapter, completed_mbo_records=100, controller_state={"cursor": 100})
        self.assertEqual(len(self.synced), 2)
        for paths in self.synced:
            self.assertEqual(len(paths), 3)
            for path in paths:
                self.assertTrue(path.exists())

    def test_a_failed_push_surfaces_at_its_own_save_point(self) -> None:
        def explode(_paths):
            raise OSError("network down")

        cp = self.make(durable_sync=explode)
        with self.assertRaises(OSError):
            cp.seal_start(self.adapter)


if __name__ == "__main__":
    unittest.main()
