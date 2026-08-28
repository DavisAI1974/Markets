from __future__ import annotations

import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.kalshi.frankie_raw_mbo_benchmark import (
    a_clean_forecaster_resume_20260828 as resume,
)
from research.kalshi.frankie_raw_mbo_benchmark.benchmark_checkpoint import (
    build_checkpoint,
    write_checkpoint_atomic,
)


SHA = "a" * 64


class LatestForecasterCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temporary.name)
        (self.runtime / "checkpoints").mkdir()

        initial = build_checkpoint(
            run_id="frankie-test",
            controller="A_CHATGPT",
            memory_mode="CLEAN",
            sequence=0,
            source_manifest_hash=SHA,
            completed_mbo_records=0,
            total_mbo_records=10,
            event_group_open=False,
            adapter_state_hash="b" * 64,
            controller_state_hash=None,
            previous_checkpoint_hash=None,
            phase="PREPARED",
            locked=False,
        )
        self.adapter = {"state_hash": "c" * 64}
        self.continuation = {
            "schema": "TEST_CONTINUATION",
            "completed_native_mbo_records": 5,
            "continuation_hash": "",
        }
        self.continuation["continuation_hash"] = resume.base.value_hash(
            self.continuation, "continuation_hash"
        )
        latest = build_checkpoint(
            run_id="frankie-test",
            controller="A_CHATGPT",
            memory_mode="CLEAN",
            sequence=1,
            source_manifest_hash=SHA,
            completed_mbo_records=5,
            total_mbo_records=10,
            event_group_open=False,
            adapter_state_hash=self.adapter["state_hash"],
            controller_state_hash=self.continuation["continuation_hash"],
            previous_checkpoint_hash=initial["checkpoint_hash"],
            phase="FORECASTER_NATIVE_REPLAY",
            locked=False,
        )
        write_checkpoint_atomic(
            self.runtime / "checkpoints" / "checkpoint-000000.json", initial
        )
        write_checkpoint_atomic(
            self.runtime / "checkpoints" / "checkpoint-000001.json", latest
        )
        with gzip.open(
            self.runtime / "checkpoints" / "adapter-state-000001.json.gz",
            "wt",
            encoding="utf-8",
        ) as handle:
            json.dump(self.adapter, handle)
        (self.runtime / "checkpoints" / "continuation-000001.json").write_text(
            json.dumps(self.continuation), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_loads_latest_complete_chain_and_siblings(self) -> None:
        with patch.object(resume, "OUT", self.runtime):
            checkpoints, adapters, continuations = resume.load_runtime_chain()
        self.assertEqual([row["sequence"] for row in checkpoints], [0, 1])
        self.assertEqual(adapters[1], self.adapter)
        self.assertEqual(continuations[1], self.continuation)

    def test_rejects_adapter_sibling_drift(self) -> None:
        path = self.runtime / "checkpoints" / "adapter-state-000001.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump({"state_hash": "d" * 64}, handle)
        with patch.object(resume, "OUT", self.runtime):
            with self.assertRaisesRegex(RuntimeError, "adapter-state hash mismatch"):
                resume.load_runtime_chain()

    def test_rejects_continuation_sibling_drift(self) -> None:
        path = self.runtime / "checkpoints" / "continuation-000001.json"
        value = dict(self.continuation)
        value["completed_native_mbo_records"] = 6
        path.write_text(json.dumps(value), encoding="utf-8")
        with patch.object(resume, "OUT", self.runtime):
            with self.assertRaisesRegex(RuntimeError, "continuation hash mismatch"):
                resume.load_runtime_chain()


if __name__ == "__main__":
    unittest.main()
