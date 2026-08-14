from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_g24_run_s127 as s127  # noqa: E402


class S127G24RunnerTests(unittest.TestCase):
    def test_launcher_is_blind_only(self):
        self.assertEqual(s127.GID, "g24")
        self.assertEqual(s127.PHASES, ("preflight", "forecast"))
        self.assertNotIn("score", s127.PHASES)
        self.assertNotIn("refine", s127.PHASES)

    def test_g24_packet_corrects_only_obsolete_walked_validation_metadata(self):
        original = {
            "walked_validation_only": True,
            "realized_outcome_in_packet": False,
            "causal_slice": {"sentinel": 1},
            "brain_view_served": {"plays": {"p": {}}, "_frankie_serving": {}},
        }
        with patch.object(s127.s126, "packet", return_value=("prompt", original)):
            prompt, packet = s127._g24_packet("BLD-1", "g24", "20260720", "B", "ns")
        self.assertEqual(prompt, "prompt")
        self.assertIsNot(packet, original)
        self.assertTrue(original["walked_validation_only"])
        self.assertFalse(packet["walked_validation_only"])
        self.assertEqual(packet["causal_slice"], original["causal_slice"])
        self.assertEqual(packet["brain_view_served"], original["brain_view_served"])
        self.assertFalse(packet["realized_outcome_in_packet"])

    def test_g24_packet_rejects_other_groups(self):
        with self.assertRaisesRegex(s127.S127Stop, "g24-only"):
            s127._g24_packet("BLD-1", "g18", "20260427", "B", "ns")

    def test_runtime_requires_exact_gpt56_sol_model(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(s127.S127Stop, "FRANKIE_OPENAI_MODEL"):
                s127.require_openai_runtime()
        with patch.dict(os.environ, {"FRANKIE_OPENAI_MODEL": "gpt-5"}, clear=True):
            with self.assertRaisesRegex(s127.S127Stop, "gpt-5.6-sol"):
                s127.require_openai_runtime()
        with patch.dict(os.environ, {"FRANKIE_OPENAI_MODEL": "gpt-5.6-sol"}, clear=True):
            self.assertEqual(
                s127.require_openai_runtime(),
                {"backend": "openai", "model": "gpt-5.6-sol"},
            )

    @patch.object(s127, "install")
    @patch.object(s127, "verify_sanctioned_state")
    @patch.object(s127, "verify_original_spawn")
    @patch.object(s127.base, "preflight_group")
    def test_preflight_stays_structural_and_unrevealed(
        self, preflight_group, verify_spawn, verify_state, install
    ):
        verify_spawn.return_value = {"verified": True}
        verify_state.return_value = {"verdict": "SANCTIONED_G24_STATE"}
        preflight_group.return_value = {
            "group": "g24",
            "days": [
                {"day": day, "owner": "B", "packet_bytes": 1, "served_plays": 90}
                for day in s127.gc.GROUPS["g24"]["days"]
            ],
            "actuals_read": False,
            "verdict": "PACKETS_CAUSAL",
        }
        out = s127.preflight("ns")
        install.assert_called_once_with()
        preflight_group.assert_called_once_with("g24", "ns")
        self.assertFalse(out["backend_invoked"])
        self.assertFalse(out["actuals_read"])

    @patch.object(s127, "preflight")
    @patch.object(s127, "require_openai_runtime")
    @patch.object(s127.base, "run_group")
    def test_forecast_uses_openai_without_score_or_reveal(self, run_group, runtime, preflight):
        preflight.return_value = {"actuals_read": False}
        runtime.return_value = {"backend": "openai", "model": "gpt-5.6-sol"}
        run_group.return_value = {"group": "g24", "forecasts": [], "bridges": []}
        out = s127.forecast("ns", resume=False)
        run_group.assert_called_once_with("g24", "ns", "openai", resume=False)
        self.assertFalse(out["score_or_reveal_invoked"])


if __name__ == "__main__":
    unittest.main()
