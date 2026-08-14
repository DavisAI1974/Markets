from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_s118_redo as mod  # noqa: E402


def full_view() -> dict:
    plays = {f"play-{i:02d}": {"id": f"play-{i:02d}"} for i in range(90)}
    return {
        "plays": plays,
        "play_index": {"play-00": {"status": "ARMED"}},
        "_frankie_serving": {
            "canonical_plays_total": 90,
            "full_plays_served": 90,
        },
    }


def causal_slice(day: str = "20260427") -> dict:
    return {
        "_information_clock": {"mode": "point_in_time"},
        "20260424": {"storage": {"level": 1}, "weather": {"hdd": 2}},
        day: {
            "storage": {"level": 3},
            "weather_forecast": {"hdd": 4},
            "weather_forcing_forecast": {"wind": {"proxy": 5}, "solar": {"proxy": 6}},
        },
    }


class SpecialistSharedContextTests(unittest.TestCase):
    def test_all_five_specialists_get_same_full_current_frankie_contract(self):
        view = full_view()
        slice_ = causal_slice()
        common = None
        for spec in "ABCDE":
            roles = {"shared": "canonical shared role", "specialist": f"canonical role {spec}"}
            got = mod.specialist_shared_context(
                spec=spec,
                gid="g18",
                day="20260427",
                causal_slice=slice_,
                view=view,
                role_files=roles,
            )
            self.assertEqual(got["coordinator"], "Frankie")
            self.assertFalse(got["specialist_role_rewritten"])
            self.assertTrue(got["complete_served_causal_slice"])
            self.assertFalse(got["future_day_blocks_present"])
            self.assertTrue(got["full_brain_available"])
            self.assertEqual(got["canonical_play_bodies"], 90)
            self.assertTrue(got["play_index_consultation_only"])
            self.assertFalse(got["frankie_settings_mutable"])
            self.assertFalse(got["frankie_schema_mutable"])
            self.assertFalse(got["frankie_inputs_mutable"])
            self.assertFalse(got["historical_memory_attached"])
            self.assertIn("weather_forcing_forecast", got["decision_day_top_level_blocks"])
            self.assertEqual(set(got["toolbox_catalogue"]), set(mod.current_frankie.TOOLBOX))
            stable = dict(got)
            stable.pop("specialist")
            stable.pop("role_file_sha256")
            if common is None:
                common = stable
            else:
                self.assertEqual(stable, common)

    def test_future_day_block_hard_fails(self):
        slice_ = causal_slice()
        slice_["20260428"] = {"tape_conditions": {"future": True}}
        with self.assertRaisesRegex(mod.ForecastStop, "crossed causal wall"):
            mod.specialist_shared_context(
                spec="B",
                gid="g18",
                day="20260427",
                causal_slice=slice_,
                view=full_view(),
                role_files={"shared": "shared", "specialist": "B"},
            )

    def test_reduced_brain_hard_fails(self):
        view = full_view()
        view["plays"].pop("play-89")
        with self.assertRaisesRegex(mod.ForecastStop, "reduced specialist brain refused"):
            mod.specialist_shared_context(
                spec="C",
                gid="g18",
                day="20260427",
                causal_slice=causal_slice(),
                view=view,
                role_files={"shared": "shared", "specialist": "C"},
            )

    def test_unknown_specialist_hard_fails(self):
        with self.assertRaisesRegex(mod.ForecastStop, "unknown specialist"):
            mod.specialist_shared_context(
                spec="F",
                gid="g18",
                day="20260427",
                causal_slice=causal_slice(),
                view=full_view(),
                role_files={"shared": "shared", "specialist": "F"},
            )

    def test_install_adds_shared_contract_without_repointing_role_files(self):
        role_shared = mod.base.ROLE_SHARED
        role_spec = dict(mod.base.ROLE_SPEC)
        output_fields = mod.CANARY_ADAPTER_FIELDS
        mod.install()
        self.assertEqual(mod.base.ROLE_SHARED, role_shared)
        self.assertEqual(mod.base.ROLE_SPEC, role_spec)
        self.assertEqual(mod.CANARY_ADAPTER_FIELDS, output_fields)
        self.assertIn("CURRENT FRANKIE SPECIALIST SHARED CONTRACT", mod.base.MODEL_INSTRUCTIONS)
        self.assertIn("lens defines your ownership", mod.base.MODEL_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
