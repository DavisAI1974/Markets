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
            "reasoning_steps": [
                {
                    "step_id": "S1",
                    "action": "OBSERVE",
                    "claim": "contract and clock state are present",
                    "evidence_refs": ["event:contract_identity", "event:causal_state"],
                    "depends_on": [],
                    "status": "SUPPORTED",
                },
                {
                    "step_id": "S2",
                    "action": "REASON",
                    "claim": "the synthetic candidate may proceed only in shadow",
                    "evidence_refs": ["derived:qualification"],
                    "depends_on": ["S1"],
                    "status": "SUPPORTED",
                },
            ],
            "uncertainty": {
                "level": "HIGH",
                "drivers": ["synthetic unit-test evidence"],
                "calibrated_probability": None,
            },
        }

    @staticmethod
    def outcome(result="NO_EDGE_AFTER_COSTS"):
        # Synthetic unit-test resolution deliberately far after any test decision timestamp.
        resolved = "2099-01-01T00:00:00Z"
        return {
            "resolved_at": resolved,
            "result": result,
            "metrics": {"net_edge": 0.0},
            "source_provenance": [
                {
                    "source": "unit-outcome",
                    "knowable_at": resolved,
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

    def test_event_rejects_future_source_provenance(self):
        raw = self.event().as_dict()
        raw["source_provenance"][0]["knowable_at"] = "2026-08-07T14:30:00Z"
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
                allowed_evidence_refs={
                    "event:contract_identity",
                    "event:causal_state",
                    "derived:qualification",
                },
            )

    def test_ready_paper_manifest_allows_agreed_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, decision, evidence = self.evaluated(tmp)
            self.assertEqual(decision.state, "SHADOW")
            self.assertFalse(decision.execution_enabled)
            self.assertEqual(decision.provenance["cognitive_contract_version"], "1.0")
            self.assertTrue(decision.provenance["evidence_catalog_hash"])
            self.assertTrue(decision.provenance["primary_trace_hash"])
            self.assertTrue(decision.provenance["critic_trace_hash"])
            self.assertTrue(evidence.is_file())

    def test_unknown_reasoning_evidence_ref_is_rejected(self):
        raw = self.lane()
        raw["reasoning_steps"][0]["evidence_refs"] = ["source:not-in-catalog"]
        with self.assertRaises(BackendError):
            LaneResult.from_dict(
                raw,
                lane="causal_scientist",
                backend="scripted",
                paper_ids=set(),
                allowed_evidence_refs={
                    "event:contract_identity",
                    "event:causal_state",
                    "derived:qualification",
                },
            )

    def test_reasoning_trace_cannot_request_execution(self):
        raw = self.lane()
        raw["reasoning_steps"][0]["action"] = "EXECUTE"
        with self.assertRaises(BackendError):
            LaneResult.from_dict(
                raw,
                lane="causal_scientist",
                backend="scripted",
                paper_ids=set(),
                allowed_evidence_refs={
                    "event:contract_identity",
                    "event:causal_state",
                    "derived:qualification",
                },
            )

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
