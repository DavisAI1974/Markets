import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_anchor import AnchorError  # noqa: E402
from ng_g15_pipeline import (  # noqa: E402
    PipelineError,
    daily_audit,
    run_pipeline,
    write_outputs,
)
from ng_historical_replay import NORMALIZED_SCHEMA  # noqa: E402
from ng_historical_replay_prepared import _fixture  # noqa: E402


def anchor_sources(root: Path, *, start: float = 1.0) -> list[Path]:
    identity = {
        "schema": NORMALIZED_SCHEMA,
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": 1008,
        "raw_symbol": "NGJ26",
        "definition_date": "2026-03-01",
        "session_day": "20260313",
    }
    definitions = root / "anchor_definition.jsonl"
    trades = root / "anchor_trades.jsonl"
    mbo = root / "anchor_mbo.jsonl"
    definitions.write_text(
        json.dumps(
            {
                **identity,
                "event_type": "definition",
                "ts_event_s": start,
                "source_sequence": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    trade_rows = [
        {
            **identity,
            "event_type": "trade",
            "ts_event_s": start + sequence,
            "source_sequence": sequence,
            "price": 3.0 + 0.001 * sequence,
            "size": 2,
            "side": "B" if sequence >= 4 else "A",
        }
        for sequence in range(1, 7)
    ]
    trades.write_text(
        "".join(json.dumps(row) + "\n" for row in trade_rows),
        encoding="utf-8",
    )
    mbo.write_text(
        json.dumps(
            {
                **identity,
                "event_type": "mbo",
                "ts_event_s": start + 6,
                "source_sequence": 1,
                "action": "A",
                "side": "B",
                "size": 10,
                "order_id": 1,
                "price": 3.005,
                "flags": 128,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return [definitions, trades, mbo]


class G15PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest, self.index = _fixture(self.root)
        self.blind = self.root / "grp15.json"
        self.blind.write_text(
            json.dumps({"group": 15, "days": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        self.prior = {"up": 0.4, "flat": 0.2, "down": 0.4}

    def tearDown(self):
        self.temp.cleanup()

    def run_bundle(self, *, anchor_start: float = 1.0):
        return run_pipeline(
            prepared_index=self.index,
            manifest=self.manifest,
            blind_prior=self.prior,
            blind_forecast_path=self.blind,
            anchor_inputs=anchor_sources(self.root, start=anchor_start),
        )

    def test_end_to_end_bundle_covers_all_g15_days(self):
        before = self.blind.read_bytes()
        bundle = self.run_bundle()
        self.assertEqual(bundle["schema"], "ng_g15_pipeline.v1")
        self.assertEqual(bundle["daily_audit"]["n_days"], 12)
        self.assertEqual(bundle["refine_stream"]["n_outputs"], 12)
        self.assertTrue(bundle["blind_forecast"]["byte_identical"])
        self.assertEqual(self.blind.read_bytes(), before)
        self.assertFalse(bundle["execution_authority"])
        self.assertFalse(bundle["gates"]["g16_authorized"])

    def test_outputs_are_separate_auditable_artifacts(self):
        bundle = self.run_bundle()
        paths = write_outputs(bundle, self.root / "out")
        self.assertEqual(
            set(paths),
            {
                "anchor",
                "replay",
                "refine_stream",
                "daily_audit",
                "lesson_proposals",
                "pipeline",
            },
        )
        for path in paths.values():
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertFalse(payload.get("execution_authority", False))

    def test_anchor_is_required(self):
        with self.assertRaises(PipelineError):
            run_pipeline(
                prepared_index=self.index,
                manifest=self.manifest,
                blind_prior=self.prior,
                blind_forecast_path=self.blind,
                anchor_inputs=[],
            )

    def test_anchor_cannot_occur_after_replay_states(self):
        with self.assertRaises(AnchorError):
            self.run_bundle(anchor_start=1000.0)

    def test_daily_audit_refuses_missing_session(self):
        bundle = self.run_bundle()
        outputs = list(bundle["refine_stream"]["outputs"])
        with self.assertRaises(PipelineError):
            daily_audit(
                outputs[:-1],
                blind_forecast_sha256=bundle["blind_forecast"]["sha256_before"],
                anchor_fingerprint=bundle["anchor"]["anchor_fingerprint"],
            )

    def test_lesson_proposals_cannot_mutate_brain(self):
        lessons = self.run_bundle()["lesson_proposals"]
        self.assertEqual(lessons["authority"], "LESSON_PROPOSAL_ONLY")
        self.assertFalse(lessons["may_update_ng_brain"])
        for proposal in lessons["proposals"]:
            self.assertFalse(proposal["may_update_ng_brain"])
            self.assertEqual(proposal["status"], "UNSCORED_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
