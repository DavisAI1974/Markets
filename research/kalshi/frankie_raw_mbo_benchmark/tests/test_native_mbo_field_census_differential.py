"""The optimised census against a reference walk, over inputs chosen to break it.

The census was made 9.7x faster by replacing abstract-base-class isinstance checks with
concrete-type fast paths, folding scalar columns with C builtins, transposing lists of dicts
into columns, and concatenating sibling lists that share a path. Every one of those trades a
general Python walk for a special case, and its output feeds hash-verified artifacts.

Each optimisation was verified by comparing full summaries - and one still shipped a defect.
Hoisting the field lookup out of the element loop was correct for every list except an EMPTY
one, where the original created no field at all. The differential could not catch it because
the corpus was a synthetic member row that happened to contain no empty list. A differential
is only as strong as its inputs, so the inputs are the point of this file: the reference
implementation below is the pre-optimisation walk, and the corpus is the set of shapes the
fast paths could plausibly get wrong.

Deleting the ABC fallback entirely left all 20 behavioural tests green before this file
existed. That is what it guards.
"""
from __future__ import annotations

import json
import unittest
from collections import OrderedDict, defaultdict, namedtuple
from decimal import Decimal
from enum import IntEnum
from typing import Any, Mapping

from research.kalshi.frankie_raw_mbo_benchmark.native_mbo_field_census import (
    DISTINCT_CAP,
    LIST_MARKER,
    MboFieldCensus,
)


class _RefField:
    """`_Field` as it stood before any optimisation.

    The reference MUST NOT reuse the live `_Field`. It did, and that made the differential
    blind to half of what it claimed to check: `_Field` carries two of the four
    optimisations - the `type(v) is int` numeric fast path and the removal of the dead
    `not isinstance(value, bool)` - so with the live class on both sides those cancelled and
    a defect injected into `_Field.observe` passed the differential silently.

    Differences from the optimised class, all deliberate: type NAMES rather than type
    objects, `isinstance` for the numeric test with the bool exclusion spelled out, and no
    `observe_column` at all - the reference folds nothing.
    """

    __slots__ = (
        "observations", "null", "rows_with_field", "distinct", "capped", "types",
        "minimum", "maximum",
    )

    def __init__(self) -> None:
        self.observations = 0
        self.null = 0
        self.rows_with_field = 0
        self.distinct: set = set()
        self.capped = False
        self.types: set = set()
        self.minimum: float | None = None
        self.maximum: float | None = None

    def observe(self, value: Any) -> None:
        self.observations += 1
        if value is None:
            self.null += 1
            return
        self.types.add(type(value).__name__)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            self.minimum = value if self.minimum is None else min(self.minimum, value)
            self.maximum = value if self.maximum is None else max(self.maximum, value)
        if not self.capped:
            try:
                self.distinct.add(value)
            except TypeError:
                self.distinct.add(repr(value))
            if len(self.distinct) >= DISTINCT_CAP:
                self.capped = True


class ReferenceCensus(MboFieldCensus):
    """The walk as it stood before any optimisation, reusing only the reporting SHAPE.

    Kept deliberately naive: `isinstance` against the abstract `Mapping`, one call per leaf,
    no columns and no transposition, and its own `_RefField`. It is the definition the fast
    paths must reproduce, so it shares no accumulating code with them.
    """

    def _row(self, path: str, stat: Any) -> dict[str, Any]:
        """The reporting half as it was: `types` already holds NAMES, so no rendering."""
        non_null = stat.observations - stat.null
        only_value = None
        degenerate = False
        if not stat.capped and non_null > 0 and len(stat.distinct) == 1:
            degenerate = True
            only_value = next(iter(stat.distinct))
        return {
            "field": path,
            "observations": stat.observations,
            "observations_null": stat.null,
            "rows_with_field": stat.rows_with_field,
            "rows_absent": self.rows_observed - stat.rows_with_field,
            "distinct_values": len(stat.distinct),
            "distinct_capped": stat.capped,
            "types": sorted(stat.types),
            "minimum": stat.minimum,
            "maximum": stat.maximum,
            "degenerate": degenerate,
            "only_value": only_value,
            "always_null": stat.observations > 0 and non_null == 0,
        }

    def observe(self, row: Mapping[str, Any]) -> None:
        self.rows_observed += 1
        touched: set[str] = set()
        self._ref_walk(row, "", touched)
        for path in touched:
            self._fields[path].rows_with_field += 1

    def _ref_walk(self, node: Any, prefix: str, touched: set[str]) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                self._ref_at(path, value, touched)
        elif isinstance(node, (list, tuple)):
            path = f"{prefix}{LIST_MARKER}"
            for value in node:
                self._ref_at(path, value, touched)

    def _ref_at(self, path: str, value: Any, touched: set[str]) -> None:
        stat = self._fields.get(path)
        if stat is None:
            stat = self._fields[path] = _RefField()
        touched.add(path)
        if isinstance(value, (Mapping, list, tuple)):
            stat.observations += 1
            stat.types.add(type(value).__name__)
            self._ref_walk(value, path, touched)
        else:
            stat.observe(value)


class Colour(IntEnum):
    RED = 1
    BLUE = 7


Level = namedtuple("Level", "px sz")


class MyInt(int):
    pass


class MyStr(str):
    pass


def _one() -> type:
    class Row:  # noqa: D401 - two distinct classes deliberately share a __name__
        pass
    return Row


def _two() -> type:
    class Row:
        pass
    return Row


class Unhashable:
    __hash__ = None  # type: ignore[assignment]


CORPUS: list[tuple[str, list[dict]]] = [
    ("empty list", [{"orders": []}, {"orders": []}]),
    ("empty tuple", [{"t": ()}]),
    ("empty list nested one level", [{"book": {"lv": [{"q": []}]}}]),
    ("empty list beside a full one",
     [{"levels": [{"size": 1}, {"size": 2}, {"size": 3}]}, {"levels": []}]),
    ("ordered dict walks as a container", [{"m": OrderedDict((("a", 1), ("b", 2)))}]),
    ("defaultdict walks as a container", [{"m": defaultdict(int, {"a": 1})}]),
    ("namedtuple walks as a list", [{"lv": Level(px=3.1, sz=5)}]),
    ("int enum carries a range", [{"c": Colour.RED}, {"c": Colour.BLUE}]),
    ("int subclass carries a range", [{"n": MyInt(4)}, {"n": MyInt(9)}]),
    ("str subclass carries no range", [{"s": MyStr("x")}]),
    ("decimal carries no range", [{"d": Decimal("1.5")}]),
    ("bool carries no range", [{"b": True}, {"b": False}]),
    ("two classes sharing a name", [{"a": _one()()}, {"a": _two()()}]),
    ("unhashable falls back to repr", [{"u": Unhashable()}]),
    ("heterogeneous key sets",
     [{"lv": [{"px": 1, "sz": 2}, {"px": 3, "ct": 4}, {"sz": 5}]}]),
    ("mixed scalar and dict list", [{"lv": [1, {"px": 2}, "three", [4]]}]),
    ("sibling lists concatenate",
     [{"lv": [{"orders": [{"oid": 1}, {"oid": 2}]}, {"orders": [{"oid": 3}]}]}]),
    ("nulls beside values", [{"v": None}, {"v": 1}, {"v": None}]),
    ("all null", [{"v": None}, {"v": None}]),
    ("distinct cap latches on the same value",
     [{"lv": list(range(DISTINCT_CAP * 3))}]),
    ("int and float tie", [{"n": 1}, {"n": 1.0}, {"n": 2}]),
    ("deeply nested empties", [{"a": {"b": {"c": []}}}, {"a": {"b": {"c": [{"d": []}]}}}]),
    # The three below exist for the BULK distinct update. It snapshots the set before the
    # update so it can restore and redo one at a time when the cap is reached, and the
    # snapshot only does anything when a PRIOR row already put values in the set. A
    # single-row cap crossing never exercises it.
    ("cap crosses on a later row, with the set already part full",
     [{"lv": list(range(DISTINCT_CAP - 4))}, {"lv": list(range(DISTINCT_CAP * 2))}]),
    ("cap crosses exactly on the boundary value",
     [{"lv": list(range(DISTINCT_CAP - 1))}, {"lv": [DISTINCT_CAP - 1, DISTINCT_CAP]}]),
    # An unhashable arriving AFTER the set is part full: the bulk update raises partway,
    # so the restore has to put back exactly what was there and not what the aborted
    # update left behind.
    ("unhashable after a part-full set",
     [{"u": 1}, {"u": 2}, {"u": Unhashable()}, {"u": 3}]),
]


class CensusDifferentialTest(unittest.TestCase):
    def _summaries(self, rows: list[dict]) -> tuple[str, str]:
        reference = ReferenceCensus()
        optimised = MboFieldCensus()
        for row in rows:
            reference.observe(row)
            optimised.observe(row)
        return (
            json.dumps(reference.summary(), sort_keys=True, default=repr),
            json.dumps(optimised.summary(), sort_keys=True, default=repr),
        )

    def test_every_shape_matches_the_reference_walk(self):
        for label, rows in CORPUS:
            with self.subTest(shape=label):
                expected, actual = self._summaries(rows)
                self.assertEqual(expected, actual)

    def test_the_whole_corpus_at_once_matches(self):
        """Shapes interact: one row's empty list meets another row's full one."""
        rows = [row for _label, shape in CORPUS for row in shape]
        expected, actual = self._summaries(rows)
        self.assertEqual(expected, actual)

    def test_an_empty_list_creates_no_field_and_no_row_credit(self):
        """C1, pinned by name: this is the defect the corpus was missing."""
        census = MboFieldCensus()
        census.observe({"orders": []})
        census.observe({"orders": []})
        self.assertNotIn(f"orders{LIST_MARKER}", census.paths())
        summary = census.summary()
        self.assertEqual(summary["field_count"], 1)

    def test_a_row_with_an_empty_list_is_not_credited_with_the_field(self):
        census = MboFieldCensus()
        census.observe({"levels": [{"size": 1}]})
        census.observe({"levels": []})
        row = census.field(f"levels{LIST_MARKER}")
        self.assertEqual(row["rows_with_field"], 1)
        self.assertEqual(row["rows_absent"], 1)

    def test_the_abc_fallback_is_load_bearing(self):
        """Deleting it left all 20 behavioural tests green; it must not be silently removable."""
        census = MboFieldCensus()
        census.observe({"m": OrderedDict((("a", 1),))})
        self.assertIn("m.a", census.paths())
        self.assertEqual(census.field("m.a")["observations"], 1)

    def test_two_classes_sharing_a_name_report_one_type(self):
        """R1: the pre-optimisation code deduped on the NAME, not the type object."""
        census = MboFieldCensus()
        census.observe({"a": _one()()})
        census.observe({"a": _two()()})
        self.assertEqual(census.field("a")["types"], ["Row"])


if __name__ == "__main__":
    unittest.main()
