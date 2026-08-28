"""Deterministic typed BOSS state serialization for controlled reasoner experiments.

This module is intentionally model-neutral. It serializes only a declared
point-in-time state snapshot; it does not invoke Granite, BOSS, Frankie, Step-1,
or any provider. The canonical artifact is JSON text with an explicit float
policy and no unrestricted passthrough field.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
import hashlib
import json
import math
from typing import Mapping

try:
    from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY
except ImportError:  # Direct execution from the package directory.
    from qsv_registry import QSV_FEATURE_REGISTRY

SCHEMA_VERSION = "boss_state_serialization/1"
FLOAT_SIGNIFICAND = 12
FLOAT_POLICY = "decimal-significand-12/1"


class ValueState(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    ABLATED = "ablated"


@dataclass(frozen=True, slots=True)
class NumericField:
    name: str
    unit: str
    state: ValueState
    value: float | int | None

    def __post_init__(self) -> None:
        if self.state is not ValueState.PRESENT and self.value is not None:
            raise ValueError(
                f"{self.name}: {self.state.value} field must not carry a numeric payload"
            )


@dataclass(frozen=True, slots=True)
class CategoricalField:
    name: str
    state: ValueState
    value: str | int | None

    def __post_init__(self) -> None:
        if self.state is not ValueState.PRESENT and self.value is not None:
            raise ValueError(
                f"{self.name}: {self.state.value} field must not carry a categorical payload"
            )


@dataclass(frozen=True, slots=True)
class SequenceRow:
    index: int
    event_time_ns: int
    ingest_time_ns: int
    numeric: tuple[NumericField, ...]
    categorical: tuple[CategoricalField, ...]
    venue: str
    instrument: str


@dataclass(frozen=True, slots=True)
class GraphNode:
    index: int
    parent: int | None


@dataclass(frozen=True, slots=True)
class QSVState:
    registry_id: str
    names: tuple[str, ...]
    values: tuple[float | int | None, ...]
    states: tuple[ValueState, ...]


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    source_packet_hash: str
    entity: str
    as_of_ns: int
    source_versions: Mapping[str, str]
    defects: tuple[str, ...]
    rows: tuple[SequenceRow, ...]
    graph: tuple[GraphNode, ...]
    qsv: QSVState | None
    ablation_policy_version: str


@dataclass(frozen=True, slots=True)
class SerializedState:
    schema_version: str
    text: str

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _canon_float(value: float | int) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("present numeric value must be int or float")
    x = float(value)
    if not math.isfinite(x):
        raise ValueError("present numeric value must be finite")
    if x == 0.0:
        return "0E+0"
    d = Decimal(repr(x))
    exp = d.adjusted()
    quant = Decimal(1).scaleb(exp - (FLOAT_SIGNIFICAND - 1))
    return f"{d.quantize(quant).normalize():E}"


def _validate_field_names(fields, kind: str) -> None:
    names = [field.name for field in fields]
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError(f"{kind} field names must be non-empty strings")
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate {kind} field name")


def _validate_snapshot(snapshot: StateSnapshot) -> None:
    if not isinstance(snapshot, StateSnapshot):
        raise TypeError("serialize_state requires StateSnapshot")
    if (
        not isinstance(snapshot.source_packet_hash, str)
        or len(snapshot.source_packet_hash) != 64
        or any(
            char not in "0123456789abcdefABCDEF"
            for char in snapshot.source_packet_hash
        )
    ):
        raise ValueError(
            "source_packet_hash must be a 64-character hexadecimal SHA-256"
        )
    if not isinstance(snapshot.entity, str) or not snapshot.entity:
        raise ValueError("entity must be a non-empty string")
    if isinstance(snapshot.as_of_ns, bool) or not isinstance(snapshot.as_of_ns, int):
        raise ValueError("as_of_ns must be an integer")
    if (
        not isinstance(snapshot.ablation_policy_version, str)
        or not snapshot.ablation_policy_version
    ):
        raise ValueError("ablation_policy_version must be non-empty")
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in snapshot.source_versions.items()
    ):
        raise ValueError("source_versions must map strings to strings")
    if any(not isinstance(defect, str) for defect in snapshot.defects):
        raise ValueError("defects must contain strings")

    row_indices = [row.index for row in snapshot.rows]
    if row_indices != list(range(len(snapshot.rows))):
        raise ValueError("row indices must be contiguous and ordered from zero")
    for row in snapshot.rows:
        if isinstance(row.event_time_ns, bool) or not isinstance(row.event_time_ns, int):
            raise ValueError("event_time_ns must be integer")
        if isinstance(row.ingest_time_ns, bool) or not isinstance(row.ingest_time_ns, int):
            raise ValueError("ingest_time_ns must be integer")
        if row.ingest_time_ns < row.event_time_ns:
            raise ValueError(
                "ingest_time_ns cannot precede event_time_ns in a trusted snapshot"
            )
        if not row.venue or not row.instrument:
            raise ValueError("venue and instrument must be non-empty")
        _validate_field_names(row.numeric, "numeric")
        _validate_field_names(row.categorical, "categorical")
        for field in row.numeric:
            if field.state is ValueState.PRESENT:
                _canon_float(field.value)
            elif field.value is not None:
                raise ValueError(
                    f"{field.name}: non-present numeric field must not carry value"
                )
        for field in row.categorical:
            if field.state is ValueState.PRESENT:
                if isinstance(field.value, bool) or not isinstance(
                    field.value, (str, int)
                ):
                    raise ValueError(
                        f"{field.name}: present categorical value must be str or int"
                    )
            elif field.value is not None:
                raise ValueError(
                    f"{field.name}: non-present categorical field must not carry value"
                )

    if len(snapshot.graph) != len(snapshot.rows):
        raise ValueError("graph width must equal row count")
    graph_indices = [node.index for node in snapshot.graph]
    if graph_indices != row_indices:
        raise ValueError("graph node indices must match row indices in order")
    valid_indices = set(graph_indices)
    for node in snapshot.graph:
        if node.parent is None:
            continue
        if isinstance(node.parent, bool) or not isinstance(node.parent, int):
            raise ValueError("parent must be an integer index or root")
        if node.parent not in valid_indices:
            raise ValueError(f"parent {node.parent} is absent from graph")
        if node.parent >= node.index:
            raise ValueError("parent must refer to an earlier causal row")

    if snapshot.qsv is not None:
        qsv = snapshot.qsv
        expected_names = tuple(QSV_FEATURE_REGISTRY)
        if tuple(qsv.names) != expected_names:
            raise ValueError("QSV names/order must equal QSV_FEATURE_REGISTRY")
        if len(qsv.values) != len(qsv.names) or len(qsv.states) != len(qsv.names):
            raise ValueError("QSV width mismatch between names, values, and states")
        if not qsv.registry_id:
            raise ValueError("QSV registry_id must be non-empty")
        for name, value, state in zip(qsv.names, qsv.values, qsv.states):
            if state is ValueState.PRESENT:
                _canon_float(value)
            elif value is not None:
                raise ValueError(
                    f"{name}: non-present QSV value must not carry payload"
                )


def _numeric_dict(field: NumericField) -> dict:
    return {
        "name": field.name,
        "unit": field.unit,
        "state": field.state.value,
        "value": (
            _canon_float(field.value)
            if field.state is ValueState.PRESENT
            else None
        ),
    }


def _categorical_dict(field: CategoricalField) -> dict:
    return {
        "name": field.name,
        "state": field.state.value,
        "value": field.value if field.state is ValueState.PRESENT else None,
    }


def _body(snapshot: StateSnapshot, schema_version: str) -> dict:
    qsv = None
    if snapshot.qsv is not None:
        qsv = {
            "registry_id": snapshot.qsv.registry_id,
            "names": list(snapshot.qsv.names),
            "states": [state.value for state in snapshot.qsv.states],
            "mask": [
                1 if state is ValueState.PRESENT else 0
                for state in snapshot.qsv.states
            ],
            "values": [
                _canon_float(value) if state is ValueState.PRESENT else None
                for value, state in zip(snapshot.qsv.values, snapshot.qsv.states)
            ],
        }
    return {
        "schema_version": schema_version,
        "float_policy": FLOAT_POLICY,
        "source_packet_hash": snapshot.source_packet_hash,
        "entity": snapshot.entity,
        "as_of_ns": snapshot.as_of_ns,
        "source_versions": dict(sorted(snapshot.source_versions.items())),
        "defects": list(snapshot.defects),
        "ablation_policy_version": snapshot.ablation_policy_version,
        "rows": [
            {
                "index": row.index,
                "event_time_ns": row.event_time_ns,
                "ingest_time_ns": row.ingest_time_ns,
                "numeric": [_numeric_dict(field) for field in row.numeric],
                "categorical": [
                    _categorical_dict(field) for field in row.categorical
                ],
                "venue": row.venue,
                "instrument": row.instrument,
            }
            for row in snapshot.rows
        ],
        "graph": [
            {"index": node.index, "parent": node.parent}
            for node in snapshot.graph
        ],
        "qsv": qsv,
    }


def serialize_state(
    snapshot: StateSnapshot,
    *,
    schema_version: str = SCHEMA_VERSION,
) -> SerializedState:
    if not isinstance(schema_version, str) or not schema_version:
        raise ValueError("schema_version must be non-empty")
    _validate_snapshot(snapshot)
    text = json.dumps(
        _body(snapshot, schema_version),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return SerializedState(schema_version=schema_version, text=text)


def _parse_numeric(raw: dict) -> NumericField:
    state = ValueState(raw["state"])
    value = float(raw["value"]) if state is ValueState.PRESENT else None
    return NumericField(raw["name"], raw["unit"], state, value)


def _parse_categorical(raw: dict) -> CategoricalField:
    state = ValueState(raw["state"])
    return CategoricalField(
        raw["name"],
        state,
        raw["value"] if state is ValueState.PRESENT else None,
    )


def parse_serialized_state(text: str) -> StateSnapshot:
    raw = json.loads(text)
    expected_top = {
        "schema_version",
        "float_policy",
        "source_packet_hash",
        "entity",
        "as_of_ns",
        "source_versions",
        "defects",
        "ablation_policy_version",
        "rows",
        "graph",
        "qsv",
    }
    if set(raw) != expected_top:
        raise ValueError(
            "serialized state contains unknown or missing top-level fields"
        )
    if raw["float_policy"] != FLOAT_POLICY:
        raise ValueError("unsupported float_policy")

    rows = tuple(
        SequenceRow(
            index=row["index"],
            event_time_ns=row["event_time_ns"],
            ingest_time_ns=row["ingest_time_ns"],
            numeric=tuple(_parse_numeric(field) for field in row["numeric"]),
            categorical=tuple(
                _parse_categorical(field) for field in row["categorical"]
            ),
            venue=row["venue"],
            instrument=row["instrument"],
        )
        for row in raw["rows"]
    )
    graph = tuple(
        GraphNode(node["index"], node["parent"])
        for node in raw["graph"]
    )

    qsv_raw = raw["qsv"]
    qsv = None
    if qsv_raw is not None:
        states = tuple(ValueState(state) for state in qsv_raw["states"])
        expected_mask = [
            1 if state is ValueState.PRESENT else 0 for state in states
        ]
        if qsv_raw["mask"] != expected_mask:
            raise ValueError("QSV mask does not agree with value states")
        qsv = QSVState(
            registry_id=qsv_raw["registry_id"],
            names=tuple(qsv_raw["names"]),
            values=tuple(
                float(value) if state is ValueState.PRESENT else None
                for value, state in zip(qsv_raw["values"], states)
            ),
            states=states,
        )

    snapshot = StateSnapshot(
        source_packet_hash=raw["source_packet_hash"],
        entity=raw["entity"],
        as_of_ns=raw["as_of_ns"],
        source_versions=dict(raw["source_versions"]),
        defects=tuple(raw["defects"]),
        rows=rows,
        graph=graph,
        qsv=qsv,
        ablation_policy_version=raw["ablation_policy_version"],
    )
    _validate_snapshot(snapshot)
    return snapshot


def ablate_market_fields(
    snapshot: StateSnapshot,
    *,
    numeric_fields: frozenset[str] = frozenset(),
    qsv_fields: frozenset[str] = frozenset(),
    policy_version: str,
) -> StateSnapshot:
    if not policy_version:
        raise ValueError("policy_version must be non-empty")

    known_numeric = {
        field.name for row in snapshot.rows for field in row.numeric
    }
    unknown_numeric = set(numeric_fields) - known_numeric
    if unknown_numeric:
        raise ValueError(
            f"unknown numeric fields for ablation: {sorted(unknown_numeric)}"
        )

    known_qsv = set(snapshot.qsv.names) if snapshot.qsv is not None else set()
    unknown_qsv = set(qsv_fields) - known_qsv
    if unknown_qsv:
        raise ValueError(
            f"unknown QSV fields for ablation: {sorted(unknown_qsv)}"
        )

    rows = tuple(
        replace(
            row,
            numeric=tuple(
                replace(field, state=ValueState.ABLATED, value=None)
                if field.name in numeric_fields
                and field.state is ValueState.PRESENT
                else field
                for field in row.numeric
            ),
        )
        for row in snapshot.rows
    )

    qsv = snapshot.qsv
    if qsv is not None and qsv_fields:
        values = list(qsv.values)
        states = list(qsv.states)
        for index, name in enumerate(qsv.names):
            if name in qsv_fields and states[index] is ValueState.PRESENT:
                states[index] = ValueState.ABLATED
                values[index] = None
        qsv = replace(qsv, values=tuple(values), states=tuple(states))

    return replace(
        snapshot,
        rows=rows,
        qsv=qsv,
        ablation_policy_version=policy_version,
    )
