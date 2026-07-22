import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Load the adapter without requiring the full dashboard package in this isolated
# unit test. The repository import uses dashboard.adapters.paths normally.
dashboard_pkg = types.ModuleType("dashboard")
adapters_pkg = types.ModuleType("dashboard.adapters")
paths_mod = types.ModuleType("dashboard.adapters.paths")
paths_mod.KALSHI_RESEARCH = str(ROOT / "research" / "kalshi")
sys.modules.setdefault("dashboard", dashboard_pkg)
sys.modules.setdefault("dashboard.adapters", adapters_pkg)
sys.modules["dashboard.adapters.paths"] = paths_mod
spec = importlib.util.spec_from_file_location(
    "dashboard.adapters.forecast", ROOT / "dashboard" / "adapters" / "forecast.py"
)
forecast = importlib.util.module_from_spec(spec)
sys.modules["dashboard.adapters.forecast"] = forecast
assert spec.loader is not None
spec.loader.exec_module(forecast)


def blind_fixture(group=15):
    dates = forecast.G15_DATES if group == 15 else forecast.G16_DATES
    return {
        "group": group,
        "tag": f"g{group}",
        "kind": "blind_fixture",
        "brain_version": "fixture",
        "anchor": {"date": "20260313" if group == 15 else "20260327", "price": 3.0},
        "days": [
            {
                "date": day,
                "overnight_gap_usd": 0,
                "guess_curve": [
                    [hour, -10 * index]
                    for index, hour in enumerate(forecast.GRID_HOURS)
                ],
                "guessed_net_usd": -120,
            }
            for day in dates
        ],
    }


def write_json(root, relative, payload):
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


class DashboardForecastAdapterTests(unittest.TestCase):
    def test_missing_artifacts_are_visible_not_fabricated(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = forecast.summary(15, root=temporary)
        self.assertEqual(result["stage"], "BLOCKED")
        self.assertIn("blind", result["unavailable_artifacts"])
        self.assertFalse(result["actual_outcomes_loaded"])
        self.assertFalse(result["execution_authority"])

    def test_blind_only_snapshot_is_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            write_json(temporary, "forecasts/grp15.json", blind_fixture())
            result = forecast.summary(15, root=temporary)
        self.assertEqual(result["stage"], "BLIND_ONLY")
        self.assertTrue(result["artifacts"]["blind"]["available"])
        self.assertTrue(result["artifacts"]["blind"]["immutable_source"])
        self.assertEqual(result["artifacts"]["blind"]["n_days"], 12)
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["may_change_posterior"])

    def test_corrupt_posterior_blocks_the_chain(self):
        with tempfile.TemporaryDirectory() as temporary:
            write_json(temporary, "forecasts/grp15.json", blind_fixture())
            path = Path(temporary) / "renders/ng_refine_s95/g15_mbo_refine_stream.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not-json", encoding="utf-8")
            result = forecast.summary(15, root=temporary)
        self.assertEqual(result["stage"], "BLOCKED")
        self.assertEqual(result["artifacts"]["posterior"]["status"], "CORRUPT")
        self.assertIn("posterior", result["invalid_artifacts"])

    def test_invalid_refined_artifact_is_not_displayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            write_json(temporary, "forecasts/grp15.json", blind_fixture())
            write_json(temporary, "forecasts/grp15_mbo_refined.json", {"group": 15})
            result = forecast.summary(15, root=temporary)
        self.assertEqual(result["stage"], "BLOCKED")
        self.assertEqual(result["artifacts"]["refined"]["status"], "INVALID")
        self.assertFalse(result["artifacts"]["refined"]["available"])

    def test_day_snapshot_never_loads_actuals(self):
        with tempfile.TemporaryDirectory() as temporary:
            write_json(temporary, "forecasts/grp15.json", blind_fixture())
            result = forecast.day_snapshot(15, forecast.G15_DATES[0], root=temporary)
        self.assertEqual(result["blind"]["date"], forecast.G15_DATES[0])
        self.assertIsNone(result["refined"])
        self.assertEqual(result["posterior_outputs"], [])
        self.assertFalse(result["actual_outcomes_loaded"])
        self.assertFalse(result["execution_authority"])

    def test_noncanonical_day_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(forecast.ForecastAdapterError):
                forecast.day_snapshot(15, "20260321", root=temporary)

    def test_render_path_is_fixed_and_nonempty(self):
        with tempfile.TemporaryDirectory() as temporary:
            render = Path(temporary) / "renders/ng_refine_s95/g15_mbo_blind_continuous.png"
            render.parent.mkdir(parents=True, exist_ok=True)
            render.write_bytes(b"png-fixture")
            resolved = forecast.render_path(15, "blind", root=temporary)
            self.assertEqual(resolved, render.resolve())
            with self.assertRaises(forecast.ForecastAdapterError):
                forecast.render_path(15, "../../secret", root=temporary)

    def test_empty_render_is_reported_corrupt(self):
        with tempfile.TemporaryDirectory() as temporary:
            write_json(temporary, "forecasts/grp15.json", blind_fixture())
            render = Path(temporary) / "renders/ng_refine_s95/g15_mbo_refined_continuous.png"
            render.parent.mkdir(parents=True, exist_ok=True)
            render.write_bytes(b"")
            result = forecast.summary(15, root=temporary)
        self.assertEqual(result["artifacts"]["refined_render"]["status"], "CORRUPT")
        self.assertIn("refined_render", result["invalid_artifacts"])

    def test_blind_forecast_with_outcome_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            blind = blind_fixture()
            blind["actuals"] = {"leak": True}
            write_json(temporary, "forecasts/grp15.json", blind)
            result = forecast.summary(15, root=temporary)
        self.assertEqual(result["stage"], "BLOCKED")
        self.assertEqual(result["artifacts"]["blind"]["status"], "INVALID")

    def test_summary_all_keeps_groups_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            write_json(temporary, "forecasts/grp15.json", blind_fixture(15))
            write_json(temporary, "forecasts/grp16.json", blind_fixture(16))
            result = forecast.summary_all(root=temporary)
        self.assertEqual(result["groups"]["15"]["stage"], "BLIND_ONLY")
        self.assertEqual(result["groups"]["16"]["stage"], "BLIND_ONLY")
        self.assertFalse(result["execution_authority"])


if __name__ == "__main__":
    unittest.main()
