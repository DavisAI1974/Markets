"""One deterministic C23 score for runtime acceptance and training reward.

Only the final JSON text enters this module. Channel extraction belongs to the
caller; Markdown fences, thinking tokens and surrounding prose are rejected.
No quality judgment, model call, BLD-1 mapping or response repair happens here.
"""

from __future__ import annotations

from enum import Enum
import json
import math

from .granite_output_schema import REQUIRED_KEYS, iter_refs, validate_schema
from .state_serialization import (
    SCHEMA_VERSION, SerializedState, parse_serialized_state, serialize_state,
)


class Verdict(Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def parse_json_object(output_text: str) -> dict | None:
    """Strict JSON object or None; safe shared decoding for offline evaluation."""
    if type(output_text) is not str:
        return None
    try:
        value = json.loads(output_text, object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant, parse_float=_finite_float)
    except (ValueError, RecursionError):
        return None
    return value if type(value) is dict else None


def score(output_text: str, snapshot: SerializedState) -> tuple[float, Verdict]:
    """Score shape, then exact prompt hash and every reference.

Malformed caller snapshots raise instead of being counted as model failures.
The existing serializer/parser remain the snapshot authority. Top-level key
errors are L1; nested key errors are L2. Missing/ablated named fields still
exist and are valid references, without claiming that their values exist.
"""
    if not isinstance(snapshot, SerializedState):
        raise TypeError("snapshot must be SerializedState")
    if snapshot.schema_version != SCHEMA_VERSION:
        raise ValueError("unsupported snapshot schema_version")
    restored = parse_serialized_state(snapshot.text)
    if serialize_state(restored).text != snapshot.text:
        raise ValueError("snapshot must use the canonical serialize_state text")
    value = parse_json_object(output_text)
    if value is None:
        return 0.0, Verdict.L0
    if value.keys() != REQUIRED_KEYS:
        return 0.2, Verdict.L1
    if not validate_schema(value):
        return 0.4, Verdict.L2
    if value["snapshot_hash"] != snapshot.hash:
        return 0.6, Verdict.L3
    # Primitive metadata and named numeric/categorical fields exist per row.
    # QSV and graph have no row/field addressing contract in this schema.
    metadata = {"index", "event_time_ns", "ingest_time_ns", "venue", "instrument"}
    fields = {row.index: metadata | {f.name for f in row.numeric + row.categorical}
              for row in restored.rows}
    if any(ref["row"] not in fields or ref["field"] not in fields[ref["row"]]
           for ref in iter_refs(value)):
        return 0.6, Verdict.L3
    return 1.0, Verdict.L4


# Both call sites import the exact same function object, including evaluation.
training_score = score
runtime_score = score


def accepts(output_text: str, snapshot: SerializedState) -> bool:
    return runtime_score(output_text, snapshot)[1] is Verdict.L4
