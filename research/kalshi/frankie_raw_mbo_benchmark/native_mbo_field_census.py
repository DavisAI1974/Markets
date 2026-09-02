"""Per-field census of the retained raw MBO, so the drop question can be answered at all.

Mission section 9a asks the principal to classify each retained field as LOAD_BEARING,
RETAINED_UNREAD, DEGENERATE_ON_THIS_SLICE, REDUNDANT or CANNOT_JUDGE. Until this module
nothing measured the fields themselves: the member ledger stayed on the box, the result
carried a row COUNT, and "which fields are degenerate on this slice" had no evidence behind
it either way. A judgement made without that measurement is a guess, and a guess in either
direction is what D60 exists to stop.

This walks every member row the runner's sink receives and reports, per field path: how
many observations, in how many rows, how many null, how many distinct values (capped), the
types seen, the numeric range, and whether the field is degenerate (one value throughout)
or always null. It is READ-ONLY on its input and it is a MEASUREMENT: it never drops,
never recommends, and its summary says so in its own `basis`.

List positions are collapsed: `book_full.bid_levels_full[].size` is one field, not one per
ladder position, because a position in a ladder is not a field and a census keyed by
position would grow with book depth instead of with the schema. Rows-with-field is counted
separately from observations so a list of 300 elements in one row is not mistaken for 300
rows carrying the field.
"""
from __future__ import annotations

from typing import Any, Mapping

DISTINCT_CAP = 64
LIST_MARKER = "[]"


class _Field:
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
        # bool is a subclass of int; a min/max over True/False is noise, not a range.
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


class MboFieldCensus:
    """Observe rows; report what each field path carried. Read-only on its input."""

    def __init__(self) -> None:
        self.rows_observed = 0
        self._fields: dict[str, _Field] = {}

    # -- walking ------------------------------------------------------------------------

    def observe(self, row: Mapping[str, Any]) -> None:
        self.rows_observed += 1
        touched: set[str] = set()
        self._walk(row, "", touched)
        for path in touched:
            self._fields[path].rows_with_field += 1

    def _walk(self, node: Any, prefix: str, touched: set[str]) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                self._observe_at(path, value, touched)
        elif isinstance(node, (list, tuple)):
            # One path for every element: a ladder position is not a field.
            path = f"{prefix}{LIST_MARKER}"
            for value in node:
                self._observe_at(path, value, touched)

    def _observe_at(self, path: str, value: Any, touched: set[str]) -> None:
        stat = self._touch(path)
        touched.add(path)
        if isinstance(value, (Mapping, list, tuple)):
            # The container itself is "present" with its type recorded; its leaves are
            # counted under their own paths. Its distinct/range are meaningless and are not
            # accumulated, so a container never reads as degenerate or always-null.
            stat.observations += 1
            stat.types.add(type(value).__name__)
            self._walk(value, path, touched)
        else:
            stat.observe(value)

    def _touch(self, path: str) -> _Field:
        stat = self._fields.get(path)
        if stat is None:
            stat = self._fields[path] = _Field()
        return stat

    # -- reporting ----------------------------------------------------------------------

    def field(self, path: str) -> dict[str, Any]:
        stat = self._fields[path]
        return self._row(path, stat)

    def paths(self) -> list[str]:
        return sorted(self._fields)

    def _row(self, path: str, stat: _Field) -> dict[str, Any]:
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

    def summary(self) -> dict[str, Any]:
        fields = [self._row(p, s) for p, s in sorted(self._fields.items())]
        return {
            "rows_observed": self.rows_observed,
            "field_count": len(fields),
            "fields": fields,
            "degenerate_fields": [
                {
                    "field": f["field"],
                    "only_value": f["only_value"],
                    "rows_with_field": f["rows_with_field"],
                }
                for f in fields if f["degenerate"]
            ],
            "always_null_fields": [f["field"] for f in fields if f["always_null"]],
            "distinct_cap": DISTINCT_CAP,
            "list_positions_collapsed": True,
            "basis": (
                "measurement only, and not a recommendation to drop anything. A degenerate "
                "field (one value throughout this slice) or an always-null field is a candidate "
                "for DISCUSSION under D60; whether it holds on other days is unknown from one "
                "slice; keep-everything is a first-class answer under D76. Absent and "
                "present-but-null are counted separately because collapsing them is how a "
                "dropped input comes to look like a measured absence. `[]` marks a list whose "
                "every element is counted under one path, because a position in a ladder is "
                "not a field; `rows_with_field` counts rows, `observations` counts elements."
            ),
        }
