"""C23's closed, model-neutral evidence schema; never a BLD-1 response.

This validates shape only. Snapshot identity and reference resolution belong to
the single runtime/training scorer in ``granite_parser``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

SCHEMA_VERSION = "BOSS_GRANITE_OUTPUT_SCHEMA_V2"
REQUIRED_KEYS = frozenset({
    "schema_version", "snapshot_hash", "evidence_refs", "contradictions",
    "missing_evidence", "hypotheses", "evidence_verdict",
})
EVIDENCE_VERDICTS = frozenset({"CONSISTENT", "CONFLICTED", "INSUFFICIENT"})


def _keys(value: object, keys: set[str] | frozenset[str]) -> bool:
    return type(value) is dict and value.keys() == keys


def _text(value: object) -> bool:
    return type(value) is str


def _ref(value: object) -> bool:
    return (_keys(value, {"row", "field"})
            and type(value["row"]) is int and type(value["field"]) is str)


def _refs(value: object) -> bool:
    return type(value) is list and all(_ref(ref) for ref in value)


def validate_schema(value: object) -> bool:
    """Check exact keys, JSON types and enums; no evidence-count/text caps."""
    if not _keys(value, REQUIRED_KEYS):
        return False
    if value["schema_version"] != SCHEMA_VERSION:
        return False
    digest = value["snapshot_hash"]
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        return False
    if not _refs(value["evidence_refs"]):
        return False
    contradictions = value["contradictions"]
    if type(contradictions) is not list:
        return False
    if not all(_keys(item, {"a", "b", "note"})
               and _ref(item["a"]) and _ref(item["b"])
               and _text(item["note"]) for item in contradictions):
        return False
    missing = value["missing_evidence"]
    if type(missing) is not list:
        return False
    if not all(_text(item) for item in missing):
        return False
    hypotheses = value["hypotheses"]
    if type(hypotheses) is not list:
        return False
    if not all(_keys(item, {"label", "support", "against"})
               and _text(item["label"])
               and _refs(item["support"]) and _refs(item["against"])
               for item in hypotheses):
        return False
    return type(value["evidence_verdict"]) is str and value["evidence_verdict"] in EVIDENCE_VERDICTS


def iter_refs(value: dict) -> Iterator[dict]:
    """Yield every reference in a previously schema-validated object."""
    yield from value["evidence_refs"]
    for item in value["contradictions"]:
        yield item["a"]
        yield item["b"]
    for item in value["hypotheses"]:
        yield from item["support"]
        yield from item["against"]
