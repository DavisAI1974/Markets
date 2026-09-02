"""Tests for the key-name aliaser: it must be lossless, stable and self-describing.

The measurement in FRANKIE_MEASURED_TOKEN_REDUCTION_20260902.md was made once, by hand,
and written into prose. D36 says a finding recorded somewhere nothing reads is a finding
that expires, so the measurement is a function here and these tests are what keep it
honest. The aliaser's whole claim is that it removes bytes and NOTHING else, so most of
what follows is round-trip evidence rather than saving arithmetic.
"""
from __future__ import annotations

import json
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_key_alias import (
    AliasError,
    apply_aliases,
    build_alias_table,
    expand_aliases,
    measure_key_names,
)


def survival_row(day: str, points: int) -> dict:
    """A row shaped like the real dominant cost: a Kaplan-Meier curve.

    The measurement named `at_risk`, `censored`, `events`, `survival` and `time` as the
    single biggest cost, each appearing 41,996 times in one run. The fixture is that shape
    so the test exercises what the run actually pays for.
    """
    return {
        "measure": "time_to_exit",
        "kind": "SURVIVAL",
        "stratum": {"source_day": day, "source_role": "HELD_OUT_BLIND"},
        "declaration": {"quantile_basis": "EXACT", "parallel_view": "COMPLEMENTARY"},
        "excluded_missing_members": 0,
        "value": {
            "estimator": "KAPLAN_MEIER",
            "curve": [
                {
                    "time": index,
                    "at_risk": points - index,
                    "events": 1,
                    "censored": 0,
                    "survival": 1.0 - index / points,
                }
                for index in range(points)
            ],
        },
    }


class BuildAliasTableTest(unittest.TestCase):
    def test_covers_every_key_at_every_depth(self):
        """Top-level keys alone were 7.0% of the cost; the other 42.5% is nested.

        A table built from the outer level only would miss six sevenths of what it claims
        to remove, which is the exact error the measurement warned about.
        """
        rows = [survival_row("20211003", 3)]
        table = build_alias_table(rows)
        for nested in ("time", "at_risk", "events", "censored", "survival", "estimator",
                       "curve", "source_day", "quantile_basis"):
            self.assertIn(nested, table, f"{nested} is nested and must still be aliased")

    def test_codes_are_unique(self):
        rows = [survival_row("20211003", 5), survival_row("20211004", 5)]
        table = build_alias_table(rows)
        self.assertEqual(len(set(table.values())), len(table))

    def test_a_code_never_collides_with_a_real_key_name(self):
        """An alias equal to a live key name makes the mapping ambiguous, not smaller.

        Nothing in the current vocabulary is one character, but a future estimand naming a
        field `n` or `t` would silently make two different quantities share a name, and the
        artifact would still parse.
        """
        rows = [{"a": 1, "b": 2, "c": 3, "zz": 4, "measure": "m"}]
        table = build_alias_table(rows)
        live = {"a", "b", "c", "zz", "measure"}
        for original, code in table.items():
            if code != original:
                self.assertNotIn(code, live, f"alias {code!r} collides with a real key")

    def test_table_is_deterministic(self):
        rows = [survival_row("20211003", 4)]
        self.assertEqual(build_alias_table(rows), build_alias_table(rows))

    def test_shorter_codes_go_to_the_costliest_names(self):
        """The saving is count times name length, so the ordering has to use both."""
        rows = [{"aaaaaaaaaaaaaaaaaaaa": 1, "b": 2} for _ in range(50)]
        table = build_alias_table(rows)
        self.assertLess(len(table["aaaaaaaaaaaaaaaaaaaa"]), len("aaaaaaaaaaaaaaaaaaaa"))

    def test_a_name_no_longer_than_its_code_is_left_alone(self):
        """Aliasing a one-character key spends bytes to save none."""
        rows = [{"n": 1, "verylongkeyname": 2} for _ in range(20)]
        table = build_alias_table(rows)
        self.assertNotIn("n", table)


class RoundTripTest(unittest.TestCase):
    def test_expand_undoes_apply_exactly(self):
        rows = [survival_row("20211003", 6), survival_row("20211004", 2)]
        table = build_alias_table(rows)
        restored = expand_aliases(apply_aliases(rows, table), table)
        self.assertEqual(restored, rows)

    def test_round_trip_survives_json(self):
        """The artifact is written and read as JSON, so that is the round trip that counts."""
        rows = [survival_row("20211003", 4)]
        table = build_alias_table(rows)
        wire = json.dumps({"rows": apply_aliases(rows, table), "legend": table})
        back = json.loads(wire)
        self.assertEqual(expand_aliases(back["rows"], back["legend"]), rows)

    def test_values_are_never_touched(self):
        """Only keys are renamed. A string VALUE that happens to equal a key name stays."""
        rows = [{"measure": "survival", "value": {"survival": "time"}} for _ in range(9)]
        table = build_alias_table(rows)
        applied = apply_aliases(rows, table)
        self.assertEqual(applied[0][table["measure"]], "survival")
        self.assertEqual(applied[0][table["value"]][table["survival"]], "time")

    def test_lists_of_scalars_are_preserved(self):
        rows = [{"horizons_ns": [1, 2, 3], "measure": "m"} for _ in range(9)]
        table = build_alias_table(rows)
        restored = expand_aliases(apply_aliases(rows, table), table)
        self.assertEqual(restored, rows)

    def test_empty_rows_alias_to_nothing(self):
        self.assertEqual(build_alias_table([]), {})
        self.assertEqual(apply_aliases([], {}), [])

    def test_rows_and_legend_from_different_runs_are_refused(self):
        """An aliased name appearing UNALIASED means the two are not from one run.

        This is the mismatch that is actually detectable, and it is the one that matters:
        it is what a half-applied table or a legend copied from another artifact looks
        like, and decoding it would silently produce a row with two spellings of one field.
        """
        with self.assertRaises(AliasError):
            expand_aliases([{"measure": 1}], {"measure": "a"})

    def test_a_foreign_code_is_NOT_detectable_and_that_is_why_the_legend_travels(self):
        """Recorded as a limit, not a guard, because claiming it would be false.

        A key is either a code in this legend or a name that was never aliased, and both
        are just strings - so a code from some OTHER legend is indistinguishable from a new
        plain field. Nothing in the rows can catch it. The structural answer is that the
        legend is written INTO the same layer as the rows it decodes, so the two cannot be
        separated in the first place. A test that asserted a refusal here would be
        asserting a guard that can never fire, which is the shape this branch keeps finding.
        """
        self.assertEqual(expand_aliases([{"q9": 1}], {"measure": "a"}), [{"q9": 1}])

    def test_a_legend_mapping_two_names_to_one_code_is_refused(self):
        with self.assertRaises(AliasError):
            expand_aliases([{"a": 1}], {"measure": "a", "kind": "a"})


class MeasureKeyNamesTest(unittest.TestCase):
    def test_reports_the_named_quantities(self):
        rows = [survival_row("20211003", 20)]
        report = measure_key_names(rows)
        for field in ("rows", "compact_bytes", "distinct_key_names", "key_instances",
                      "key_name_bytes", "aliased_key_name_bytes", "saved_bytes",
                      "key_name_share", "saving_share"):
            self.assertIn(field, report)

    def test_the_saving_is_the_difference_it_claims(self):
        rows = [survival_row("20211003", 30), survival_row("20211004", 30)]
        report = measure_key_names(rows)
        self.assertEqual(
            report["saved_bytes"],
            report["key_name_bytes"] - report["aliased_key_name_bytes"],
        )

    def test_the_saving_is_real_against_actual_serialized_bytes(self):
        """The report's arithmetic and the compact bytes must agree.

        A saving computed only from name lengths could drift from what the file actually
        loses; this pins it to the bytes json.dumps really writes.
        """
        rows = [survival_row("20211003", 40), survival_row("20211004", 40)]
        report = measure_key_names(rows)
        table = build_alias_table(rows)
        before = len(json.dumps(rows, separators=(",", ":"), sort_keys=True))
        after = len(json.dumps(apply_aliases(rows, table), separators=(",", ":"),
                               sort_keys=True))
        self.assertEqual(before - after, report["saved_bytes"])

    def test_a_survival_heavy_run_saves_a_large_share(self):
        """Not a threshold on the real run - a floor that would catch a no-op aliaser."""
        rows = [survival_row(f"2021100{d}", 50) for d in range(1, 6)]
        report = measure_key_names(rows)
        self.assertGreater(report["saving_share"], 0.15)


if __name__ == "__main__":
    unittest.main()
