from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from research.kalshi import ng_exhaustion_october_frankie_v4_bridge_20260824 as bridge


class BlindBridgeTest(unittest.TestCase):
  def test_replays_once_suppresses_bootstrap_and_retains_negative_findings(self) -> None:
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    tmp_path = Path(temporary.name)
    manifest = json.loads(
        Path("research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json").read_text()
    )
    selected = bridge.select_blind_canary_objects(manifest)
    assert [row["date"] for row in selected] == ["20210930", "20211001"]

    sources = []
    for row in selected:
        path = tmp_path / Path(row["key"]).name
        path.touch()
        with path.open("r+b") as handle:
            handle.truncate(row["bytes"])
        sources.append(path)
    by_name = {Path(row["key"]).name: row["sha256"] for row in selected}
    hash_patch = mock.patch.object(bridge, "sha256_file", lambda path: by_name[Path(path).name])
    hash_patch.start()
    self.addCleanup(hash_patch.stop)

    replay_calls: list[list[str]] = []

    class Reference:
        def checkpoint(self):
            return {
                "book": {
                    "bid_depth_full": 7,
                    "ask_depth_full": 5,
                    "bid_order_count_full": 2,
                    "ask_order_count_full": 2,
                    "bid_price_level_count_full": 1,
                    "ask_price_level_count_full": 1,
                    "bid_levels_full": [{"fifo_queue": [{"size": 4}, {"size": 3}]}],
                    "ask_levels_full": [{"fifo_queue": [{"size": 2}, {"size": 3}]}],
                },
                "activity": {},
                "integrity": {},
            }

    def envelope(ts: float, *, snapshot: bool, marker: str):
        return {
            "compact_event_frame": {
                "instrument_id": 1,
                "raw_symbol": "NGX1",
                "ts_event_ns": int(ts * 1e9),
                "ts_recv_ns": int(ts * 1e9),
                "snapshot_bootstrap_only": snapshot,
                "raw_actions": [{"action": "R" if snapshot else "A", "size": 1, "marker": marker}],
                "book": {"best_bid": 3.0, "best_ask": 3.1, "spread": 0.1},
                "activity": {},
                "integrity": {},
            },
            "full_state": Reference(),
        }

    def fake_replay(paths, on_group, *, materialize_full_state):
        replay_calls.append(list(paths))
        assert materialize_full_state is False
        on_group(envelope(bridge.TARGET_START - 1, snapshot=False, marker="PREDECESSOR_ONLY"), [{"leak": "LEGACY_SECRET"}])
        on_group(envelope(bridge.TARGET_START + 1, snapshot=True, marker="SNAPSHOT_ONLY"), [{"leak": "LEGACY_SECRET"}])
        on_group(envelope(bridge.TARGET_START + 2, snapshot=False, marker="TARGET_NATIVE"), [{"leak": "LEGACY_SECRET"}])
        on_group(envelope(bridge.TARGET_END, snapshot=False, marker="OUTSIDE_HALF_OPEN"), [{"leak": "LEGACY_SECRET"}])
        return {"status": "V4_FULL_STATE_REPLAY_COMPLETE", "record_count": 4, "completed_event_group_count": 4}

    class Evaluator:
        def __init__(self):
            self.requests = []

        def evaluate(self, request):
            self.requests.append(request)
            return bridge.SolEvaluationResult(
                provider_request_id="resp_test",
                resolved_model="gpt-5.6-sol",
                request_sha256=request.request_sha256,
                response_sha256="b" * 64,
                usage={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
                output={
                    "global_status": "INCONCLUSIVE",
                    "structure_presence_probability": 0.25,
                    "findings": [
                        {
                            "finding_id": "weak-1",
                            "status": "NEGATIVE",
                            "title": "No stable queue pattern",
                            "claim": "The observed window does not support a stable structure.",
                            "confidence": 0.25,
                            "supporting_refs": [],
                            "counterevidence_refs": [request.evidence_ref],
                            "falsifiers": ["A later independent window reproduces the pattern."],
                        }
                    ],
                },
            )

    evaluator = Evaluator()
    receipt = bridge.run_blind_october_canary(
        bridge.BlindOctoberConfig(
            manifest_path=Path("research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json"),
            source_paths=tuple(sources),
            output_root=tmp_path / "out",
            run_id="test-run",
            window_seconds=3600,
        ),
        evaluator,
        replay=fake_replay,
    )

    self.assertEqual(replay_calls, [[str(path) for path in sources]])
    self.assertTrue(evaluator.requests)
    model_payload = json.dumps([request.payload for request in evaluator.requests], sort_keys=True)
    self.assertIn("TARGET_NATIVE", model_payload)
    self.assertNotIn("PREDECESSOR_ONLY", model_payload)
    self.assertNotIn("SNAPSHOT_ONLY", model_payload)
    self.assertNotIn("OUTSIDE_HALF_OPEN", model_payload)
    self.assertNotIn("LEGACY_SECRET", model_payload)
    self.assertEqual(receipt.status, "BLIND_OCTOBER_FRANKIE_CANARY_COMPLETE")
    findings = json.loads((tmp_path / "out" / "structure_findings.json").read_text())
    self.assertEqual(findings["evaluations"][0]["output"]["findings"][0]["status"], "NEGATIVE")
    self.assertEqual(findings["evaluations"][0]["resolved_model"], "gpt-5.6-sol")
    self.assertTrue((tmp_path / "out" / "state_movie.json").exists())
    self.assertTrue((tmp_path / "out" / "probability_movie.json").exists())
    self.assertTrue((tmp_path / "out" / "first_lock.json").exists())


if __name__ == "__main__":
    unittest.main()
