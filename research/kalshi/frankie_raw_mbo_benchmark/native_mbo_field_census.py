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

_SCALAR_TYPES = frozenset({str, int, float, bool, type(None)})
_NUMERIC_TYPES = frozenset({int, float})
_LIST_TYPES = frozenset({list})
_NONE_TYPE_SET = frozenset({type(None)})

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

    def observe_column(self, column: list, column_types: set | None = None) -> None:
        """Fold a whole column of SCALARS at once, identically to observing each in turn.

        Every element of a list shares one field path, so a 300-level ladder folds 300
        values into one `_Field`. Doing that with C builtins - len, count, map, min, max -
        removes 300 Python frames per list per row.

        The distinct set is still filled ONE AT A TIME on purpose: `capped` latches the
        moment the set reaches DISTINCT_CAP and nothing is added after, so a bulk update
        would report the column's true cardinality where the loop reports exactly the cap.
        That difference is visible in `distinct_values`, so the loop stays.
        """
        self.observations += len(column)
        nulls = column.count(None)
        self.null += nulls
        if nulls == len(column):
            return
        if column_types is None:
            column_types = set(map(type, column))
        self.types |= column_types - _NONE_TYPE_SET
        # The column's type set already says whether a second pass is needed: an all-numeric
        # column IS its own numeric subset, so the filtering comprehension is skipped
        # entirely on the shape that dominates a ladder.
        numeric_types = column_types - _NONE_TYPE_SET
        if numeric_types and numeric_types <= _NUMERIC_TYPES:
            numeric = column if nulls == 0 else [v for v in column if v is not None]
        elif numeric_types & _NUMERIC_TYPES:
            numeric = [v for v in column if type(v) is int or type(v) is float]
        else:
            numeric = ()
        if numeric:
            low = min(numeric)
            high = max(numeric)
            self.minimum = low if self.minimum is None else min(self.minimum, low)
            self.maximum = high if self.maximum is None else max(self.maximum, high)
        if not self.capped:
            distinct = self.distinct
            for value in column:
                if value is None:
                    continue
                try:
                    distinct.add(value)
                except TypeError:
                    distinct.add(repr(value))
                if len(distinct) >= DISTINCT_CAP:
                    self.capped = True
                    break

    def observe(self, value: Any) -> None:
        self.observations += 1
        if value is None:
            self.null += 1
            return
        tv = type(value)
        # The TYPE OBJECT, not its name: an attribute lookup per observation over 61.6M
        # observations buys nothing a report-time lookup cannot. Names are rendered in `_row`.
        self.types.add(tv)
        # bool is a subclass of int, so `isinstance(v, int)` is true for True/False and a
        # min/max over them is noise rather than a range. `type(v) is int` excludes bool by
        # construction, which is both faster than two isinstance calls and says what it means.
        if tv is int or tv is float or (
            tv is not bool and isinstance(value, (int, float)) and not isinstance(value, bool)
        ):
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
        if type(node) is dict or isinstance(node, Mapping):
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                self._observe_at(path, value, touched)
        elif isinstance(node, (list, tuple)):
            # One path for every element: a ladder position is not a field. Because the path
            # is the same for all of them, the field lookup and the `touched` add are
            # per-LIST facts and are hoisted out of the element loop.
            path = f"{prefix}{LIST_MARKER}"
            fields = self._fields
            stat = fields.get(path)
            if stat is None:
                stat = fields[path] = _Field()
            touched.add(path)
            # An all-scalar column is folded in one call with C builtins. A list of
            # containers - a ladder of level dicts - still walks, because each element
            # carries its own child paths.
            column_types = set(map(type, node))
            if column_types <= _SCALAR_TYPES:
                stat.observe_column(
                    node if type(node) is list else list(node), column_types
                )
                return
            # A LIST OF DICTS is the dominant shape: a ladder is hundreds of sibling level
            # dicts with the same keys, and every one of them folds to the same handful of
            # child paths. Transposing it - one column per key across all the dicts - turns
            # hundreds of per-element walks into one fold per key.
            if node and all(type(v) is dict for v in node):
                stat.observations += len(node)
                stat.types.add(dict)
                # A ladder's level dicts all carry the same keys, so the union is the first
                # element's key list unless some element disagrees. Checking that is a length
                # compare plus a membership test, against building a union dict per row.
                first = node[0]
                keys: Any = first
                for element in node:
                    if len(element) != len(first) or element.keys() != first.keys():
                        keys = {}
                        for other in node:
                            keys.update(dict.fromkeys(other))
                        break
                for key in keys:
                    child = f"{path}.{key}"
                    column = [e[key] for e in node if key in e]
                    child_stat = fields.get(child)
                    if child_stat is None:
                        child_stat = fields[child] = _Field()
                    touched.add(child)
                    column_types = set(map(type, column))
                    if column_types <= _SCALAR_TYPES:
                        child_stat.observe_column(column, column_types)
                    elif column_types <= _LIST_TYPES:
                        # Every value in this column is a list, and every one of them
                        # contributes to the SAME `[]` child path. So they are walked once
                        # concatenated rather than once each: a ladder's hundreds of
                        # per-level `orders` lists become one walk instead of hundreds.
                        # Concatenation preserves element order, which matters because the
                        # distinct set latches at the cap and order decides which values
                        # reach it first.
                        child_stat.observations += len(column)
                        child_stat.types |= column_types
                        merged: list = []
                        for element in column:
                            merged.extend(element)
                        if merged:
                            self._walk(merged, child, touched)
                    else:
                        for value in column:
                            tv = type(value)
                            if tv is dict or tv is list or tv is tuple or (
                                tv not in _SCALAR_TYPES
                                and isinstance(value, (Mapping, list, tuple))
                            ):
                                child_stat.observations += 1
                                child_stat.types.add(tv)
                                self._walk(value, child, touched)
                            else:
                                child_stat.observe(value)
                return
            observe = stat.observe
            for value in node:
                tv = type(value)
                if tv is dict or tv is list or tv is tuple or (
                    tv not in _SCALAR_TYPES and isinstance(value, (Mapping, list, tuple))
                ):
                    stat.observations += 1
                    stat.types.add(tv)
                    self._walk(value, path, touched)
                else:
                    observe(value)

    def _observe_at(self, path: str, value: Any, touched: set[str]) -> None:
        # The field lookup is inlined rather than wrapped in a helper: it runs once per leaf,
        # tens of millions of times per run, and a method call around a dict lookup is pure
        # overhead at that count.
        fields = self._fields
        stat = fields.get(path)
        if stat is None:
            stat = fields[path] = _Field()
        touched.add(path)
        tv = type(value)
        if tv is dict or tv is list or tv is tuple or (
            tv not in _SCALAR_TYPES and isinstance(value, (Mapping, list, tuple))
        ):
            # The container itself is "present" with its type recorded; its leaves are
            # counted under their own paths. Its distinct/range are meaningless and are not
            # accumulated, so a container never reads as degenerate or always-null.
            stat.observations += 1
            stat.types.add(tv)
            self._walk(value, path, touched)
        else:
            stat.observe(value)

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
            "types": sorted(t.__name__ for t in stat.types),
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
