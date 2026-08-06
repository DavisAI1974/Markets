from __future__ import annotations

import dataclasses
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_backends import ScriptedBackend  # noqa: E402
from frankie_core import (  # noqa: E402
    BackendError,
    FrankieConfig,
    FrankieEvent,
    GateStop,
    LaneResult,
    load_candidate_registry,
    qualify_event,
    verify_original_spawn,
)
from frankie_engine import evaluate_event  # noqa: E402
from frankie_improve import propose_improvement, record_outcome  # noqa: E402


class FrankieTests(unittest.TestCase):
    def setUp(self):
        self.base = FrankieConfig.from_env()
        self.registry = load_candidate_registry(self.base.novel_registry)

    @staticmethod
    def event(candidate_id="CME_KALSHI_DIGITAL_PARITY", identity="MAPPED"):
        return FrankieEvent.from_dict(
            {
                "event_id": "unit-event",
                "candidate_id": candidate_id,
                "knowable_at": "2026-08-06T14:30:00Z",
                "observed_at": "2026-08-06T14:30:01Z",
                "trigger": "unit test",
                "source_provenance": [
                    {
                        "source": "unit",
                        "knowable_at": "2026-08-06T14:30:00Z",
                        "content_hash": "unit-hash",
                    }
                ],
                "contract_identity": {"status": identity},
                "market_state": {},
                "causal_state": {"clock_status": "POINT_IN_TIME", "source_fresh": True},
                "cost_state": {"costs_known": True},
                "execution_enabled": False,
            }
        )

    @staticmethod
    def lane(balance="DELTA_NEUTRAL", state="SHADOW", citations=None):
        return {
            "verdict": "ADVANCE",
            "recommended_state": state,
            "balance_mode": balance,
            "causal_chain": ["a", "b"],
            "information_clock": "exact test clock",
            "exact_contracts": ["A", "B"],
            "missing_evidence": [],
            "falsifiers": ["no convergence"],
            "paper_citations": citations or [],
            "rationale": "test",
        }

    @staticmethod
    def outcome(result="NO_EDGE_AFTER_COSTS"):
        return {
            "resolved_at": "2026-08-07T21:00:00Z",
            "result": result,
            "metrics": {"net_edge": 0.0},
            "source_provenance": [
                {
                    "source": "unit-outcome",
                    "knowable_at": "2026-08-07T21:00:00Z",
                    "content_hash": "unit-outcome-hash",
                }
            ],
            "execution_enabled": False,
        }

    def evaluated(self, tmp):
        config = dataclasses.replace(
            self.base,
            allow_missing_papers=True,
            evidence_root=Path(tmp) / "evidence",
            s3_bucket=None,
        )
        decision, evidence = evaluate_event(
            self.event(),
            config=config,
            primary_backend=ScriptedBackend("one", self.lane()),
            critic_backend=ScriptedBackend("two", self.lane()),
            deterministic_only=False,
        )
        return config, decision, Path(evidence["local_path"])

    def test_origin_is_pinned(self):
        self.assertTrue(verify_original_spawn()["verified"])

    def test_event_cannot_enable_execution(self):
        raw = self.event().as_dict()
        raw["execution_enabled"] = True
        with self.assertRaises(GateStop):
            FrankieEvent.from_dict(raw)

    def test_payoff_neutral_requires_exact_identity(self):
        event = self.event("KALSHI_DUPLICATE_WRAPPER_PARITY", identity="MAPPED")
        q = qualify_event(event, self.registry[event.candidate_id])
        self.assertFalse(q.eligible)
        self.assertIn("PAYOFF_NEUTRAL requires exact payoff identity", q.blockers)

    def test_unknown_paper_citation_is_rejected(self):
        with self.assertRaises(BackendError):
            LaneResult.from_dict(
                self.lane(citations=["invented-paper"]),
                lane="causal_scientist",
                backend="scripted",
                paper_ids=set(),
            )

    def test_incomplete_paper_manifest_caps_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, decision, evidence = self.evaluated(tmp)
            self.assertEqual(decision.state, "WATCH_ONLY")
            self.assertFalse(decision.execution_enabled)
            self.assertTrue(evidence.is_file())

    def test_lane_disagreement_cannot_be_averaged(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = dataclasses.replace(
                self.base,
                allow_missing_papers=True,
                evidence_root=Path(tmp) / "evidence",
                s3_bucket=None,
            )
            decision, _ = evaluate_event(
                self.event(),
                config=config,
                primary_backend=ScriptedBackend("one", self.lane(balance="DELTA_NEUTRAL")),
                critic_backend=ScriptedBackend("two", self.lane(balance="WATCH_ONLY")),
                deterministic_only=False,
            )
            self.assertEqual(decision.state, "HUMAN_REVIEW")

    def test_outcome_sidecar_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, evidence = self.evaluated(tmp)
            first = record_outcome(evidence_path=evidence, outcome=self.outcome(), config=config)
            second = record_outcome(evidence_path=evidence, outcome=self.outcome(), config=config)
            self.assertEqual(first["outcome_hash"], second["outcome_hash"])
            with self.assertRaises(GateStop):
                record_outcome(
                    evidence_path=evidence,
                    outcome=self.outcome("DIFFERENT_RESULT"),
                    config=config,
                )

    def test_unresolved_evidence_cannot_improve(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, evidence = self.evaluated(tmp)
            proposer, reviewer = self.improvement_backends(evidence)
            with self.assertRaises(GateStop):
                propose_improvement(
                    evidence_paths=[evidence], proposer=proposer, critic=reviewer, config=config
                )

    def improvement_backends(self, evidence, requested_file="research/kalshi/tests/test_agent_frankie.py"):
        import json

        evidence_hash = json.loads(evidence.read_text(encoding="utf-8"))["envelope_hash"]
        proposer = ScriptedBackend(
            "proposer",
            {
                "target_component": "test_harness",
                "hypothesis": "test",
                "change_summary": "test",
                "evidence_refs": [evidence_hash],
                "requested_files": [requested_file],
                "expected_benefit": "test",
                "falsifiers": ["fails"],
                "test_plan": ["replay"],
                "untouched_forward_gate": "one forward event",
                "rollback_plan": "revert",
                "execution_enabled": False,
                "apply_allowed": False,
            },
        )
        reviewer = ScriptedBackend(
            "reviewer",
            {
                "verdict": "SANDBOX_ELIGIBLE",
                "reasons": ["test"],
                "required_tests": ["test"],
                "leakage_risks": [],
                "execution_risks": [],
            },
        )
        return proposer, reviewer

    def test_self_improvement_cannot_touch_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _, evidence = self.evaluated(tmp)
            record_outcome(evidence_path=evidence, outcome=self.outcome(), config=config)
            proposer, reviewer = self.improvement_backends(evidence, "research/kalshi/spawn.py")
            with self.assertRaises(GateStop):
                propose_improvement(
                    evidence_paths=[evidence], proposer=proposer, critic=reviewer, config=config
                )


if __name__ == "__main__":
    unittest.main()
