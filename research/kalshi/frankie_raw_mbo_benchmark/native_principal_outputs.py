"""The principal's OUTPUT ledgers: the required set is derived, never counted in advance.

Frankie receives every record of every field for the day as a causal stream in `ts_recv_ns`
order and computes every calculation-contract section himself (D81). What he writes is
produced sequentially as the stream advances and is never rewritten - the feed inventory,
section 15: *"These outputs are part of the experimental data and must remain append-only"*,
and the registry group `append_only_outputs` (`proof_mode: APPEND_ONLY_HASH_CHAIN`,
`activation_stage: SEQUENTIAL_AS_PRODUCED`). This module is the schema and the validator for
that output surface. Staging calls it; it edits nothing staging owns.

**THE REQUIRED SET IS DERIVED AT VALIDATION TIME, AND THERE IS NO FLOOR BELOW IT.** Greg
(DROP_IN_S121, ruling 4): *"don't take any historical number like that as a valid number
that we should follow"*; *"not 10 as the floor. if it's supposed to have 30, the floor is
28. 10 is how 20 get silently dropped."* So the set is:

- every layer id of the loaded registry's `append_only_outputs` group, read from the
  registry object handed in - never typed here;
- one ledger per `### 4.x` heading of the calculation contract, read from the contract TEXT
  handed in (`contract_section_<id>`, including 4.0 and 4.0b); adding a heading adds a
  required ledger with no edit here;
- the mission's section 9a raw-MBO classification (`raw_mbo_classification`); and
- the knowledge-verification record (`knowledge_verification`), one verdict per delivered
  lesson.

A bundle missing any one of them is a refused spawn. No constant in this module names a
count, and `tests/test_native_principal_outputs.py` asserts that by reading the module's
own AST.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

APPEND_ONLY_OUTPUTS_GROUP = "append_only_outputs"
SECTION_LEDGER_PREFIX = "contract_section_"
RAW_MBO_CLASSIFICATION_LEDGER = "raw_mbo_classification"
KNOWLEDGE_VERIFICATION_LEDGER = "knowledge_verification"

#: `### 4.0`, `### 4.0b`, `### 4.16` - the section id is the token after the marks.
CONTRACT_SECTION_HEADING_RE = re.compile(r"^### (4\.[0-9]+[a-z]?)\b", re.MULTILINE)


class PrincipalOutputError(ValueError):
    """An output ledger could not be written lawfully, or a bundle could not be trusted."""


def _group(registry: Mapping[str, Any], group_id: str) -> Mapping[str, Any]:
    groups = registry.get("groups") if isinstance(registry, Mapping) else None
    if not isinstance(groups, list):
        raise PrincipalOutputError("registry carries no `groups` list")
    for group in groups:
        if isinstance(group, Mapping) and group.get("group_id") == group_id:
            return group
    raise PrincipalOutputError(f"registry has no {group_id!r} group")


def _layer_ids(registry: Mapping[str, Any], group_id: str) -> tuple[str, ...]:
    entries = _group(registry, group_id).get("entries")
    if not isinstance(entries, list) or not entries:
        raise PrincipalOutputError(f"registry group {group_id!r} has no entries")
    ids = tuple(str(entry["layer_id"]) for entry in entries)
    if len(set(ids)) != len(ids):
        raise PrincipalOutputError(f"registry group {group_id!r} repeats a layer id")
    return ids


def registry_output_layer_ids(registry: Mapping[str, Any]) -> tuple[str, ...]:
    """The output layers of the LOADED registry's `append_only_outputs` group, in order."""
    return _layer_ids(registry, APPEND_ONLY_OUTPUTS_GROUP)


def contract_section_ids(contract_text: str) -> tuple[str, ...]:
    """Every `### 4.x` heading of the calculation contract, in document order.

    Read at validation time so that adding a section to the contract adds a required ledger
    with no edit here. A text with no such heading is not a calculation contract.
    """
    ids = tuple(CONTRACT_SECTION_HEADING_RE.findall(contract_text))
    if not ids:
        raise PrincipalOutputError("contract text carries no `### 4.x` section headings")
    if len(set(ids)) != len(ids):
        raise PrincipalOutputError("contract text repeats a `### 4.x` section heading")
    return ids


def section_ledger_id(section: str) -> str:
    return f"{SECTION_LEDGER_PREFIX}{section}"


def required_ledger_ids(registry: Mapping[str, Any], contract_text: str) -> tuple[str, ...]:
    """Registry outputs + one per contract section + 9a classification + knowledge verification.

    Derived from the two objects handed in. Nothing here knows how many that is.
    """
    return (
        registry_output_layer_ids(registry)
        + tuple(section_ledger_id(section) for section in contract_section_ids(contract_text))
        + (RAW_MBO_CLASSIFICATION_LEDGER, KNOWLEDGE_VERIFICATION_LEDGER)
    )
