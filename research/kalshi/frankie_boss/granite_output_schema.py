"""C23's closed, model-neutral evidence schema; never a BLD-1 response.

This validates shape only. Snapshot identity and reference resolution belong to
the single runtime/training scorer in ``granite_parser``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

SCHEMA_VERSION = "BOSS_GRANITE_OUTPUT_SCHEMA_V1"
REQUIRED_KEYS = frozenset({
    "schema_version", "snapshot_hash", "evidence_refs", "contradictions",
    "missing_evidence", "hypotheses", "disposition",
})
DISPOSITIONS = frozenset({"CONSISTENT", "CONFLICTED", "INSUFFICIENT"})


def _keys(value: object, keys: set[str] | frozenset[str]) -> bool:
    return type(value) is dict and value.keys() == keys


def _text(value: object, limit: int) -> bool:
    return type(value) is str and len(value) <= limit


def _ref(value: object) -> bool:
    return (_keys(value, {"row", "field"})
            and type(value["row"]) is int and type(value["field"]) is str)


def _refs(value: object) -> bool:
    return type(value) is list and all(_ref(ref) for ref in value)


def validate_schema(value: object) -> bool:
    """Check exact keys, JSON types, caps and enums, without trusting references.

The plan caps evidence_refs at 16, but specifies no separate support/against
cap. No additional limit is silently imposed on those hypothesis lists.
"""
    if not _keys(value, REQUIRED_KEYS):
        return False
    if value["schema_version"] != SCHEMA_VERSION:
        return False
    digest = value["snapshot_hash"]
    if type(digest) is not str or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
        return False
    if not _refs(value["evidence_refs"]) or len(value["evidence_refs"]) > 16:
        return False
    contradictions = value["contradictions"]
    if type(contradictions) is not list or len(contradictions) > 8:
        return False
    if not all(_keys(item, {"a", "b", "note"})
               and _ref(item["a"]) and _ref(item["b"])
               and _text(item["note"], 200) for item in contradictions):
        return False
    missing = value["missing_evidence"]
    if type(missing) is not list or len(missing) > 8:
        return False
    if not all(_text(item, 120) for item in missing):
        return False
    hypotheses = value["hypotheses"]
    if type(hypotheses) is not list or not 1 <= len(hypotheses) <= 4:
        return False
    if not all(_keys(item, {"label", "support", "against"})
               and _text(item["label"], 40)
               and _refs(item["support"]) and _refs(item["against"])
               for item in hypotheses):
        return False
    return type(value["disposition"]) is str and value["disposition"] in DISPOSITIONS


def iter_refs(value: dict) -> Iterator[dict]:
    """Yield every reference in a previously schema-validated object."""
    yield from value["evidence_refs"]
    for item in value["contradictions"]:
        yield item["a"]
        yield item["b"]
    for item in value["hypotheses"]:
        yield from item["support"]
        yield from item["against"]
