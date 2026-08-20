from __future__ import annotations

import dataclasses
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_core import FrankieConfig, FrankieEvent  # noqa: E402
from frankie_engine import evaluate_event  # noqa: E402


class CountingBackend:
    def __init__(self, name):
        self.name = name
        self.calls = 0

    def generate(self, *, instructions, prompt):
        del instructions, prompt
        self.calls += 1
        return {
            "verdict": "ADVANCE",
            "recommended_state": "SHADOW",
            "balance_mode": "DELTA_NEUTRAL",
            "causal_chain": ["a", "b"],
            "information_clock": "exact test clock",
            "exact_contracts": ["A", "B"],
            "missing_evidence": [],
            "falsifiers": ["no convergence"],
            "paper_citations": [],
            "rationale": "test",
            "reasoning_steps": [
                {
                    "step_id": "S1",
                    "action": "OBSERVE",
                    "claim": "the contract identity is present",
                    "evidence_refs": ["event:contract_identity"],
                    "depends_on": [],
                    "status": "SUPPORTED",
                },
                {
                    "step_id": "S2",
                    "action": "REASON",
                    "claim": "the deterministic qualification is satisfied",
                    "evidence_refs": ["derived:qualification"],
                    "depends_on": ["S1"],
                    "status": "SUPPORTED",
                },
            ],
            "uncertainty": {
                "level": "HIGH",
                "drivers": ["synthetic idempotency test"],
                "calibrated_probability": None,
            },
        }


class FrankieIdempotencyTests(unittest.TestCase):
    @staticmethod
    def event():
        return FrankieEvent.from_dict(
            {
                "event_id": "idempotent-event",
                "candidate_id": "CME_KALSHI_DIGITAL_PARITY",
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
                "contract_identity": {"status": "MAPPED"},
                "market_state": {},
                "causal_state": {"clock_status": "POINT_IN_TIME", "source_fresh": True},
                "cost_state": {"costs_known": True},
                "execution_enabled": False,
            }
        )

    def test_second_delivery_reuses_first_writer_without_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = dataclasses.replace(
                FrankieConfig.from_env(),
                allow_missing_papers=True,
                evidence_root=Path(tmp) / "evidence",
                s3_bucket=None,
            )
            primary = CountingBackend("primary")
            critic = CountingBackend("critic")
            first_decision, first_evidence = evaluate_event(
                self.event(),
                config=config,
                primary_backend=primary,
                critic_backend=critic,
                deterministic_only=False,
            )
            second_decision, second_evidence = evaluate_event(
                self.event(),
                config=config,
                primary_backend=primary,
                critic_backend=critic,
                deterministic_only=False,
            )
            self.assertEqual(primary.calls, 1)
            self.assertEqual(critic.calls, 1)
            self.assertEqual(first_decision.decision_hash, second_decision.decision_hash)
            self.assertEqual(first_evidence["local_path"], second_evidence["local_path"])
            self.assertTrue(second_evidence["deduplicated"])


if __name__ == "__main__":
    unittest.main()
