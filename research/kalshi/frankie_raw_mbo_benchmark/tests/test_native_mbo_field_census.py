"""The field census measures the retained raw MBO; it never judges it."""
from __future__ import annotations

import json
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_mbo_field_census import (
    DISTINCT_CAP,
    MboFieldCensus,
)


def _census(rows):
    census = MboFieldCensus()
    for row in rows:
        census.observe(row)
    return census


class CountingTest(unittest.TestCase):
    def test_rows_observed_counts_every_row_once(self):
        census = _census([{"a": 1}, {"a": 2}, {"b": 3}])
        self.assertEqual(census.rows_observed, 3)

    def test_absent_and_null_are_counted_separately(self):
        """Collapsing them is how a dropped input comes to look like a measured absence."""
        census = _census([{"a": 1}, {"a": None}, {}])
        row = census.field("a")
        self.assertEqual(row["observations"], 2)
        self.assertEqual(row["observations_null"], 1)
        self.assertEqual(row["rows_with_field"], 2)
        self.assertEqual(row["rows_absent"], 1)

    def test_a_field_is_read_only_on_its_input(self):
        row = {"a": {"b": [1, 2, {"c": None}]}}
        before = json.dumps(row, sort_keys=True)
        _census([row])
        self.assertEqual(json.dumps(row, sort_keys=True), before)

    def test_an_empty_census_summarises_without_inventing_fields(self):
        summary = MboFieldCensus().summary()
        self.assertEqual(summary["rows_observed"], 0)
        self.assertEqual(summary["field_count"], 0)
        self.assertEqual(summary["fields"], [])
        self.assertEqual(summary["degenerate_fields"], [])
        self.assertEqual(summary["always_null_fields"], [])


class PathTest(unittest.TestCase):
    def test_nested_mappings_become_dotted_paths(self):
        census = _census([{"book": {"best_bid": 5, "levels": {"top": 1}}}])
        self.assertIn("book.best_bid", census.paths())
        self.assertIn("book.levels.top", census.paths())

    def test_list_positions_collapse_into_one_path_per_field(self):
        """A position in a ladder is not a field; the census grows with the schema, not with
        book depth."""
        ladder = [{"price": 100 + i, "size": 1} for i in range(300)]
        census = _census([{"bid_levels_full": ladder}])
        self.assertIn("bid_levels_full[].price", census.paths())
        self.assertIn("bid_levels_full[].size", census.paths())
        self.assertNotIn("bid_levels_full[0].price", census.paths())
        self.assertEqual(
            [p for p in census.paths() if p.startswith("bid_levels_full")],
            ["bid_levels_full", "bid_levels_full[]", "bid_levels_full[].price",
             "bid_levels_full[].size"],
            "the list, its element container and two leaf fields - not 300 positions",
        )

    def test_observations_count_elements_and_rows_with_field_counts_rows(self):
        ladder = [{"size": 1}] * 300
        census = _census([{"levels": ladder}, {"levels": []}])
        row = census.field("levels[].size")
        self.assertEqual(row["observations"], 300)
        self.assertEqual(row["rows_with_field"], 1, "one row carried the field, not 300")
        self.assertEqual(row["rows_absent"], 1)

    def test_a_list_of_scalars_is_one_path(self):
        census = _census([{"sizes": [1, 2, 3]}])
        row = census.field("sizes[]")
        self.assertEqual(row["observations"], 3)
        self.assertEqual(row["types"], ["int"])

    def test_a_container_is_present_with_its_type_and_never_degenerate(self):
        census = _census([{"book": {"x": 1}}, {"book": {"x": 1}}])
        row = census.field("book")
        self.assertEqual(row["observations"], 2)
        self.assertEqual(row["types"], ["dict"])
        self.assertFalse(row["degenerate"])
        self.assertFalse(row["always_null"])
        self.assertTrue(census.field("book.x")["degenerate"])


class DegeneracyTest(unittest.TestCase):
    def test_one_value_throughout_is_degenerate_with_the_value_named(self):
        census = _census([{"scope": "FULL"}] * 5)
        row = census.field("scope")
        self.assertTrue(row["degenerate"])
        self.assertEqual(row["only_value"], "FULL")
        self.assertEqual(census.summary()["degenerate_fields"],
                         [{"field": "scope", "only_value": "FULL", "rows_with_field": 5}])

    def test_two_values_are_not_degenerate(self):
        census = _census([{"scope": "FULL"}, {"scope": "TOP"}])
        self.assertFalse(census.field("scope")["degenerate"])
        self.assertIsNone(census.field("scope")["only_value"])

    def test_always_null_is_reported_and_is_not_degenerate(self):
        census = _census([{"a": None}, {"a": None}])
        row = census.field("a")
        self.assertTrue(row["always_null"])
        self.assertFalse(row["degenerate"])
        self.assertEqual(census.summary()["always_null_fields"], ["a"])

    def test_null_plus_one_value_is_degenerate_on_the_non_null_observations(self):
        census = _census([{"a": None}, {"a": 7}, {"a": 7}])
        row = census.field("a")
        self.assertTrue(row["degenerate"])
        self.assertEqual(row["only_value"], 7)
        self.assertFalse(row["always_null"])

    def test_distinct_values_are_capped_and_a_capped_field_is_not_judged_degenerate(self):
        census = _census([{"id": i} for i in range(DISTINCT_CAP * 3)])
        row = census.field("id")
        self.assertTrue(row["distinct_capped"])
        self.assertEqual(row["distinct_values"], DISTINCT_CAP)
        self.assertFalse(row["degenerate"])
        # The range keeps accumulating past the cap; only the distinct set stops.
        self.assertEqual(row["minimum"], 0)
        self.assertEqual(row["maximum"], DISTINCT_CAP * 3 - 1)

    def test_an_unhashable_value_is_censused_by_its_repr_not_dropped(self):
        census = _census([{"a": {1, 2}}])
        self.assertEqual(census.field("a")["distinct_values"], 1)


class RangeAndTypeTest(unittest.TestCase):
    def test_numeric_range_is_recorded(self):
        census = _census([{"px": 3.5}, {"px": -1}, {"px": 10}])
        row = census.field("px")
        self.assertEqual(row["minimum"], -1)
        self.assertEqual(row["maximum"], 10)
        self.assertEqual(row["types"], ["float", "int"])

    def test_bool_is_excluded_from_the_range(self):
        census = _census([{"flag": True}, {"flag": False}])
        row = census.field("flag")
        self.assertIsNone(row["minimum"])
        self.assertIsNone(row["maximum"])
        self.assertEqual(row["types"], ["bool"])

    def test_strings_carry_no_range(self):
        census = _census([{"s": "b"}, {"s": "a"}])
        row = census.field("s")
        self.assertIsNone(row["minimum"])
        self.assertEqual(row["distinct_values"], 2)


class SummaryTest(unittest.TestCase):
    def test_the_summary_is_json_serialisable_and_sorted_by_path(self):
        census = _census([{"z": 1, "a": {"m": [1, {"k": None}]}}])
        summary = census.summary()
        json.dumps(summary)
        self.assertEqual([f["field"] for f in summary["fields"]],
                         sorted(f["field"] for f in summary["fields"]))
        self.assertEqual(summary["field_count"], len(summary["fields"]))

    def test_the_basis_says_measurement_not_recommendation(self):
        basis = MboFieldCensus().summary()["basis"]
        self.assertIn("not a recommendation to drop anything", basis)
        self.assertIn("D60", basis)
        self.assertIn("keep-everything is a first-class answer", basis)
        self.assertTrue(MboFieldCensus().summary()["list_positions_collapsed"])


if __name__ == "__main__":
    unittest.main()
