import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import solar_calendar  # noqa: E402


class SolarCalendarEnrichmentTests(unittest.TestCase):
    def test_legacy_fields_are_preserved(self):
        row = solar_calendar._day_row("2026-03-18")
        self.assertIn("gw_day_length_h", row)
        self.assertIn("sunset_et_earliest", row)
        self.assertIn("sunset_et_latest", row)
        nyc = row["metros"]["NYC"]
        for field in (
            "sunrise_local", "sunset_local", "sunset_et", "day_length_h", "grid"
        ):
            self.assertIn(field, nyc)

    def test_weighted_event_order_is_strict(self):
        for day in ("2025-12-21", "2026-03-18", "2026-06-21"):
            row = solar_calendar._day_row(day)
            events = [
                dt.datetime.fromisoformat(row["weighted_events_utc"][name])
                for name in (
                    "civil_dawn", "sunrise", "effective_start",
                    "effective_end", "sunset", "civil_dusk",
                )
            ]
            self.assertEqual(events, sorted(events))
            self.assertEqual(len(events), len(set(events)))

    def test_summer_geometry_exceeds_winter_without_false_threshold(self):
        summer = solar_calendar._day_row("2026-06-21")
        winter = solar_calendar._day_row("2025-12-21")
        summer_peak = max(summer["clear_sky_solar_geometry"])
        winter_peak = max(winter["clear_sky_solar_geometry"])
        self.assertGreater(winter_peak, 0.0)
        self.assertGreater(summer_peak, winter_peak)

    def test_calendar_regimes_separate_seasons(self):
        self.assertEqual(
            solar_calendar._day_row("2026-06-21")["calendar_curve_regime"],
            "summer_long_day",
        )
        self.assertEqual(
            solar_calendar._day_row("2025-12-21")["calendar_curve_regime"],
            "winter_long_dark",
        )
        self.assertEqual(
            solar_calendar._day_row("2026-03-20")["calendar_curve_regime"],
            "shoulder_transition",
        )

    def test_hourly_geometry_is_bounded_and_complete(self):
        row = solar_calendar._day_row("2026-03-18")
        self.assertEqual(row["hourly_utc"], list(range(24)))
        for field in (
            "clear_sky_solar_geometry", "artificial_lighting_geometry"
        ):
            values = row[field]
            self.assertEqual(len(values), 24)
            self.assertTrue(all(0.0 <= value <= 1.0 for value in values))
        self.assertEqual(max(row["artificial_lighting_geometry"]), 1.0)

    def test_native_load_and_evening_windows_are_ordered(self):
        row = solar_calendar._day_row("2026-07-15")
        sunrise_window = row["sunrise_native_load_window_et"]
        evening_window = row["evening_net_load_ramp_window_et"]
        self.assertLess(sunrise_window["start"], sunrise_window["end"])
        self.assertLess(evening_window["start"], evening_window["end"])

    def test_per_metro_effective_solar_fields_exist(self):
        row = solar_calendar._day_row("2026-01-20")
        for metro in row["metros"].values():
            self.assertIn("civil_dawn_local", metro)
            self.assertIn("effective_solar_start_local", metro)
            self.assertIn("effective_solar_end_local", metro)
            self.assertIn("civil_dusk_local", metro)
            self.assertGreater(metro["effective_solar_hours"], 0.0)

    def test_on_demand_path_matches_authority_when_store_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "missing.json")
            with patch.object(solar_calendar, "STORE", missing):
                row = solar_calendar.solar_asof("20260318")
        self.assertIsNotNone(row)
        self.assertEqual(row["date"], "2026-03-18")
        self.assertIsNotNone(row["gw_day_length_chg_7d"])

    def test_outside_span_returns_none(self):
        self.assertIsNone(solar_calendar.solar_asof("2025-08-31"))
        self.assertIsNone(solar_calendar.solar_asof("2027-01-01"))
        self.assertIsNone(solar_calendar.solar_asof("not-a-date"))

    def test_daylight_change_signs_are_seasonally_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "missing.json")
            with patch.object(solar_calendar, "STORE", missing):
                january = solar_calendar.solar_asof("2026-01-30")
                december = solar_calendar.solar_asof("2026-12-15")
        self.assertGreater(january["gw_day_length_chg_7d"], 0.0)
        self.assertLess(december["gw_day_length_chg_7d"], 0.0)

    def test_geometry_has_no_signal_or_execution_authority(self):
        row = solar_calendar._day_row("2026-03-18")
        self.assertEqual(
            row["authority"], "EXISTING_SOLAR_DECISION_STATE_ENRICHMENT"
        )
        self.assertFalse(row["execution_authority"])
        self.assertFalse(row["may_call_direction"])
        self.assertFalse(row["may_update_ng_brain"])
        self.assertIn("BTM capacity", row["methodology"]["scope"])


if __name__ == "__main__":
    unittest.main()
