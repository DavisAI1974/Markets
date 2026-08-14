from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import consensus_poll
import frankie_s128_contract_repairs as s128


class S128ContractRepairsTest(unittest.TestCase):
    def test_consensus_poll_preserves_changed_forecast_history(self):
        prev = {
            "forecast": "31B",
            "last_polled_at": "2026-08-12T22:00:00+00:00",
        }
        h = consensus_poll._forecast_history(prev, "35B", "2026-08-13T01:00:00+00:00")
        self.assertEqual(h[0]["forecast"], "31B")
        self.assertEqual(h[0]["observed_at"], prev["last_polled_at"])
        self.assertEqual(h[0]["migration"], "legacy_value_seeded_at_last_poll")
        self.assertEqual(h[-1]["forecast"], "35B")
        self.assertEqual(h[-1]["observed_at"], "2026-08-13T01:00:00+00:00")

    def test_forward_consensus_uses_latest_snapshot_strictly_before_cutoff(self):
        rows = [{
            "title": "Natural Gas Storage",
            "date": "2026-08-13T10:30:00-04:00",
            "forecast": "35B",
            "last_polled_at": "2026-08-13T01:00:00+00:00",
            "forecast_history": [
                {"forecast": "31B", "observed_at": "2026-08-12T23:00:00+00:00"},
                {"forecast": "35B", "observed_at": "2026-08-13T01:00:00+00:00"},
            ],
        }]
        # Decision day Aug 13 -> cutoff Aug 12 20:00 ET = Aug 13 00:00 UTC.
        v = s128.forward_storage_consensus("20260813", rows)
        self.assertIsNotNone(v)
        self.assertEqual(v["consensus_chg_bcf"], 31.0)
        self.assertEqual(v["consensus_pre_print_snapshot_utc"], "2026-08-12T23:00:00Z")
        self.assertNotIn("actual", v)
        self.assertNotIn("surprise", v)

    def test_legacy_forward_consensus_refuses_post_cutoff_latest_value(self):
        rows = [{
            "title": "Natural Gas Storage",
            "date": "2026-08-13T10:30:00-04:00",
            "forecast": "35B",
            "last_polled_at": "2026-08-13T01:00:00+00:00",
        }]
        self.assertIsNone(s128.forward_storage_consensus("20260813", rows))

    def test_post_roll_structure_is_machine_marked_unavailable(self):
        row = {
            "scored_leg": {
                "leg": "ng_mbo_ngu26",
                "frozen_structural_blocks_describe": "ng_mbo_ngq26",
                "side_of_seam": "post_roll",
            },
            "contract_structure": {"masked_one_shot": True, "calendar_front_symbol": "NGQ26"},
            "options_surface": {"masked_one_shot": True},
            "squeeze_watch": {"masked_one_shot": True},
            "flow_calendar": {"front_symbol_calendar": "NGU26"},
        }
        s128._mark_scored_leg_structure(row)
        status = row["scored_leg"]["current_scored_leg_price_structure"]
        self.assertEqual(status["status"], "UNAVAILABLE_ONE_SHOT_PRICE_MASK")
        self.assertFalse(status["price_fields_usable_for_scored_leg"])
        for name in ("contract_structure", "options_surface", "squeeze_watch"):
            self.assertFalse(row[name]["scored_leg_usable"])
            self.assertEqual(row[name]["describes_leg"], "ng_mbo_ngq26")
        self.assertEqual(row["flow_calendar"]["front_symbol_calendar"], "NGU26")

    def test_emission_ceiling_play_is_formally_unavailable_not_removed(self):
        view = {
            "plays": {
                "magnitude.emission_ceiling_check": {"id": "magnitude.emission_ceiling_check"},
                "direction.foo": {"id": "direction.foo"},
            },
            "_frankie_serving": {"full_plays_served": 2},
        }
        out = s128._decorate_full_brain(view)
        self.assertIn("magnitude.emission_ceiling_check", out["plays"])
        a = out["_frankie_serving"]["play_input_availability"]["magnitude.emission_ceiling_check"]
        self.assertEqual(a["status"], "UNAVAILABLE_NO_SERVED_INPUT")
        self.assertEqual(a["action"], "STAND_DOWN")

    def test_handoff_contract_separates_blind_and_realized_state(self):
        state = {"close_px": 2.9, "last_hour_signed_flow": None}
        b = s128.typed_handoff_state(state, "blind")
        bc = b["_handoff_contract"]
        self.assertEqual(bc["state_kind"], "forecast_derived_at_prior_cutoff")
        self.assertIsNotNone(bc["forecast_derived_at_prior_cutoff"])
        self.assertIsNone(bc["realized_exit_state_after_close"])

        a = s128.typed_handoff_state({"close_px": 2.91, "last_hour_signed_flow": -1}, "actual")
        ac = a["_handoff_contract"]
        self.assertEqual(ac["state_kind"], "realized_exit_state_after_close")
        self.assertIsNone(ac["forecast_derived_at_prior_cutoff"])
        self.assertIsNotNone(ac["realized_exit_state_after_close"])


if __name__ == "__main__":
    unittest.main()
