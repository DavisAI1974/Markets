"""Production integration seam for the reviewed Dipole classroom.

The earlier ``dipole_classroom_hardening`` module remains in the repository as reviewed
history/test compatibility, but it is not on the production adapter MRO or curriculum
builder path after integration.  This module owns the two hardening policies that remain
live (mastery-based taper/regression and the Pearson overlap re-pin) and composes the
reviewed final classroom behavior directly onto the base mandatory classroom adapter.

No governed Dipole teacher mathematics, Frankie inputs, calculations, planes, replay,
Memory A, loss, optimizer, causal cutoff, or source evidence is changed here.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import dipole_classroom as classroom
from .c15_journal import evidence_hash
from .c15_normalizer import COLUMNS
from .dipole_classroom_final_review import (
    FinalDipoleClassroomPrincipalAdapter as _ReviewedFinalAdapter,
    _independent_discovery_eligible,
    _learning_measurement,
)
from .frankie_dipole_classroom_adapter import DipoleClassroomPrincipalAdapter

MIN_PEARSON_PRESENT_OVERLAP = classroom.MIN_PEARSON_PRESENT_OVERLAP

_PREVIOUS_MODE = {
    classroom.ClassroomMode.TEACH.value: classroom.ClassroomMode.TEACH.value,
    classroom.ClassroomMode.GUIDED.value: classroom.ClassroomMode.TEACH.value,
    classroom.ClassroomMode.SOCRATIC.value: classroom.ClassroomMode.GUIDED.value,
    classroom.ClassroomMode.VERIFY.value: classroom.ClassroomMode.SOCRATIC.value,
}


def select_integrated_mode(history: Sequence[Mapping[str, Any]]) -> str:
    """Advance after two mastered cycles at one level; regress one level on degradation."""
    if not history:
        return classroom.ClassroomMode.TEACH.value
    for item in history:
        if (
            item.get("schema") != classroom.COMPLETION_SCHEMA
            or item.get("mode") not in classroom._MODES
            or item.get("teacher_complete") is not True
        ):
            raise ValueError("classroom history contains an invalid completion")
    current = history[-1]["mode"]
    latest = history[-1]
    if latest.get("mastered") is not True or latest.get("acknowledged") is not True:
        return _PREVIOUS_MODE[current]
    tail = []
    for item in reversed(history):
        if item["mode"] != current:
            break
        tail.append(item)
    if len(tail) >= 2 and all(
        item.get("mastered") is True and item.get("acknowledged") is True
        for item in tail[:2]
    ):
        return classroom._NEXT_MODE[current]
    return current


def _repin_teacher_key_correlations(key: Mapping[str, Any]) -> dict:
    """Fail closed on malformed keys and suppress sub-floor Pearson coefficients."""
    if (
        key.get("schema") != classroom.KEY_SCHEMA
        or key.get("relationship_pairs_scanned") != classroom.PAIR_COUNT
        or len(key.get("relationship_scan", ())) != classroom.PAIR_COUNT
    ):
        raise ValueError("complete classroom teacher key required")
    relationships = []
    for relation in key["relationship_scan"]:
        item = dict(relation)
        correlation = dict(item["correlation"])
        overlap = correlation.get("present_overlap")
        if type(overlap) is not int or overlap < 0:
            raise ValueError("Dipole Pearson overlap must be a nonnegative integer")
        if overlap < MIN_PEARSON_PRESENT_OVERLAP:
            correlation = {
                "present_overlap": overlap,
                "pearson": None,
                "reason": (
                    f"FEWER_THAN_{MIN_PEARSON_PRESENT_OVERLAP}_OVERLAPPING_PRESENT_VALUES"
                ),
            }
        item["correlation"] = correlation
        relationships.append(item)
    body = {k: v for k, v in key.items() if k != "teacher_key_hash"}
    body["relationship_scan"] = tuple(relationships)
    body["teacher_key_hash"] = evidence_hash(body)
    return body


def prepare_integrated_cycle(
    teacher: Mapping[str, Any],
    *,
    request_id: str,
    cycle_index: int,
    cycle_count: int,
    source_hash: str,
    as_of: int,
    through_cursor: int,
    previous_snapshot: Mapping[str, Any] | None = None,
    history: Sequence[Mapping[str, Any]] = (),
    prior_grade: Mapping[str, Any] | None = None,
) -> dict:
    """Build the final reviewed classroom package without the intermediate hardening layer."""
    snapshot = classroom.snapshot_teacher_attachment(
        teacher,
        request_id=request_id,
        cycle_index=cycle_index,
        cycle_count=cycle_count,
        source_hash=source_hash,
        as_of=as_of,
        through_cursor=through_cursor,
    )
    key = _repin_teacher_key_correlations(
        classroom.build_teacher_key(snapshot, previous_snapshot)
    )
    mode = select_integrated_mode(history)
    message = classroom.build_pre_message(key, mode=mode, prior_grade=prior_grade)
    message = {k: v for k, v in message.items() if k != "teacher_message_hash"}
    message["direction_definition"] = (
        "Graded direction means the first PRESENT observation versus the last PRESENT "
        "observation in this retained cycle window. Intrawindow rises, falls, reversals, "
        "and excursions may still exist even when that endpoint direction is FLAT."
    )
    message["novelty_invitation"] = (
        "After completing the required Dipole curriculum, report any relationship, structure, "
        "mechanism, or hypothesis you believe is new or not explicitly taught. A new idea is "
        "not a classroom error merely because Dipole did not teach it. Cite the causal evidence "
        "that led you to it and keep future outcomes outside the wall."
    )
    message["teacher_message_hash"] = evidence_hash(message)
    binding = {
        "request_id": request_id,
        "cycle_index": cycle_index,
        "cycle_count": cycle_count,
        "source_hash": source_hash,
        "as_of": as_of,
        "through_cursor": through_cursor,
        "source_snapshot_hash": snapshot["source_snapshot_hash"],
        "teacher_key_hash": key["teacher_key_hash"],
        "teacher_message_hash": message["teacher_message_hash"],
        "teacher_attachment_hash": snapshot["teacher_attachment_hash"],
        "mode": mode,
        "learning_measurement": _learning_measurement(mode),
        "independent_discovery_eligible": _independent_discovery_eligible(mode),
        "coverage_count": len(COLUMNS),
        "relationship_pairs_required": classroom.PAIR_COUNT,
    }
    binding["classroom_binding_hash"] = evidence_hash(binding)
    return {
        "source": snapshot,
        "teacher_key": key,
        "pre_message": message,
        "binding": binding,
    }


class IntegratedDipoleClassroomPrincipalAdapter(DipoleClassroomPrincipalAdapter):
    """Reviewed final behavior directly on the base mandatory classroom protocol.

    The method implementations are the ccode-reviewed final methods; rebinding them here
    removes the superseded hardening adapter from the production MRO without rewriting the
    reviewed behavior.
    """

    prepare = _ReviewedFinalAdapter.prepare
    _request = _ReviewedFinalAdapter._request
    _recover_with_classroom = _ReviewedFinalAdapter._recover_with_classroom
