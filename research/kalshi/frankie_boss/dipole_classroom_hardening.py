"""Leak-resistant operational hardening for the Dipole classroom.

This module leaves the governed Dipole teacher mathematics and lawful Sunday host
untouched. It narrows only the classroom transport/control seam:

- Pearson is exposed only at a declared minimum of eight overlapping PRESENT values.
- Classroom taper regresses one level after a non-mastered/unfinished cycle.
- Prior-cycle feedback is reduced to correction locations, never the prior answer key.
- Same-session correction carries only the mistakes that require correction, not the
  exhaustive 19-dimension / 171-pair post-grade.
- The duplicate teacher-key audit is not written into the principal directory.

The host-owned cycle package still retains the complete teacher key for audit.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from . import dipole_classroom as classroom
from .c15_journal import evidence_hash
from .c15_normalizer import COLUMNS
from .dipole_classroom_render import render_transcript
from .dipole_classroom_resolution import validate_correction_resolutions
from .dipole_classroom_session import (
    CORRECTION_REQUEST_SCHEMA,
    finish,
    grade_initial_response,
    validate_correction_response,
)
from .frankie_dipole_classroom_adapter import DipoleClassroomPrincipalAdapter
from .frankie_principal_adapter import (
    FrankiePrincipalAdapter,
    PrincipalPending,
    digest,
    file_witness,
    _write,
)

# Both are declared once in the core module; re-exported here for existing importers.
MIN_PEARSON_PRESENT_OVERLAP = classroom.MIN_PEARSON_PRESENT_OVERLAP
PRIOR_CORRECTION_SCHEMA = classroom.PRIOR_CORRECTION_SCHEMA
prior_correction_summary = classroom.prior_correction_summary

_PREVIOUS_MODE = {
    classroom.ClassroomMode.TEACH.value: classroom.ClassroomMode.TEACH.value,
    classroom.ClassroomMode.GUIDED.value: classroom.ClassroomMode.TEACH.value,
    classroom.ClassroomMode.SOCRATIC.value: classroom.ClassroomMode.GUIDED.value,
    classroom.ClassroomMode.VERIFY.value: classroom.ClassroomMode.SOCRATIC.value,
}


def select_hardened_mode(history: Sequence[Mapping[str, Any]]) -> str:
    """Advance on demonstrated mastery; regress one level after degradation."""
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


def _harden_teacher_key_correlations(key: Mapping[str, Any]) -> dict:
    """Re-apply the declared Pearson floor to a key from any builder; no governed observation changes.

    The core builder already applies MIN_PEARSON_PRESENT_OVERLAP, so on a core-built key this is
    an identity that re-pins the hash; it exists so a key assembled elsewhere cannot carry a
    sub-floor coefficient into the classroom.
    """
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
                "reason": f"FEWER_THAN_{MIN_PEARSON_PRESENT_OVERLAP}_OVERLAPPING_PRESENT_VALUES",
            }
        item["correlation"] = correlation
        relationships.append(item)
    body = {k: v for k, v in key.items() if k != "teacher_key_hash"}
    body["relationship_scan"] = tuple(relationships)
    body["teacher_key_hash"] = evidence_hash(body)
    return body


def prepare_hardened_cycle(
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
    """Build the ordinary package, then harden only transport-visible classroom state."""
    snapshot = classroom.snapshot_teacher_attachment(
        teacher,
        request_id=request_id,
        cycle_index=cycle_index,
        cycle_count=cycle_count,
        source_hash=source_hash,
        as_of=as_of,
        through_cursor=through_cursor,
    )
    key = _harden_teacher_key_correlations(
        classroom.build_teacher_key(snapshot, previous_snapshot)
    )
    mode = select_hardened_mode(history)
    # The core builder now emits the prior-correction SUMMARY and the Pearson-floor text itself.
    message = classroom.build_pre_message(key, mode=mode, prior_grade=prior_grade)
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


def _component_grade(grade: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    for item in grade.get("component_grades", ()):
        if item.get("name") == name:
            return item
    return None


def _observation_grade(grade: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    audit = grade.get("exhaustive_audit", {})
    for item in audit.get("observation_grades", ()):
        if item.get("name") == name:
            return item
    return None


def _relationship_grade(
    grade: Mapping[str, Any], left: str, right: str
) -> Mapping[str, Any] | None:
    audit = grade.get("exhaustive_audit", {})
    for item in audit.get("relationship_grades", ()):
        if item.get("left") == left and item.get("right") == right:
            return item
    return None


def correction_items(grade: Mapping[str, Any]) -> tuple[dict, ...]:
    """Return only correction-local teaching facts, never the exhaustive grade."""
    if grade.get("schema") != classroom.GRADE_SCHEMA:
        raise ValueError("complete Dipole post-grade required")
    correction_ids = tuple(grade.get("correction_ids", ()))
    items = []
    for correction_id in correction_ids:
        if correction_id.startswith("component:"):
            name = correction_id.split(":", 1)[1]
            item = _component_grade(grade, name)
            if item is None:
                raise ValueError("component correction lacks host grade evidence")
            wrong_fields = []
            if item.get("state_counts_correct") is not True:
                wrong_fields.append("STATE_COUNTS")
            if item.get("state_correct") is not True:
                wrong_fields.append("TERMINAL_STATE")
            if item.get("direction_correct") is not True:
                wrong_fields.append("FIRST_TO_LAST_PRESENT_DIRECTION")
            items.append(
                {
                    "correction_id": correction_id,
                    "kind": "COMPONENT",
                    "subject": name,
                    "wrong_fields": tuple(wrong_fields),
                    "explanation": item["explanation"],
                }
            )
            continue
        if correction_id.startswith("observation-set:"):
            name = correction_id.split(":", 1)[1]
            item = _observation_grade(grade, name)
            if item is None:
                raise ValueError("observation-set correction lacks host audit evidence")
            items.append(
                {
                    "correction_id": correction_id,
                    "kind": "OBSERVATION_SET",
                    "subject": name,
                    "expected_count": item["expected_count"],
                    "claimed_count": item["claimed_count"],
                    "explanation": "Reconcile the retained cursor set before resolving this correction.",
                }
            )
            continue
        if correction_id.startswith("observation-extra:"):
            name = correction_id.split(":", 1)[1]
            item = _observation_grade(grade, name)
            if item is None:
                raise ValueError("extra-observation correction lacks host audit evidence")
            items.append(
                {
                    "correction_id": correction_id,
                    "kind": "OBSERVATION_EXTRA",
                    "subject": name,
                    "extra_cursors": tuple(item["extra_cursors"]),
                    "explanation": "Remove observations that are not members of the retained causal cursor set.",
                }
            )
            continue
        if correction_id.startswith("observation:"):
            _, name, cursor_text = correction_id.split(":", 2)
            item = _observation_grade(grade, name)
            if item is None:
                raise ValueError("observation correction lacks host audit evidence")
            cursor = int(cursor_text)
            point = next((value for value in item["grades"] if value["cursor"] == cursor), None)
            if point is None:
                raise ValueError("observation correction cursor lacks host audit evidence")
            items.append(
                {
                    "correction_id": correction_id,
                    "kind": "OBSERVATION",
                    "subject": name,
                    "cursor": cursor,
                    "actual_state": point["state"],
                    "actual_value": point["value"],
                    "explanation": point["explanation"],
                }
            )
            continue
        if correction_id.startswith("relationship:"):
            _, left, right = correction_id.split(":", 2)
            item = _relationship_grade(grade, left, right)
            if item is None:
                raise ValueError("relationship correction lacks host audit evidence")
            items.append(
                {
                    "correction_id": correction_id,
                    "kind": "RELATIONSHIP",
                    "left": left,
                    "right": right,
                    "claimed": item["claimed"],
                    "actual": item["actual"],
                    "explanation": item["explanation"],
                }
            )
            continue
        items.append(
            {
                "correction_id": correction_id,
                "kind": "OTHER",
                "explanation": (
                    "Re-evaluate the named prior claim against the same causal evidence "
                    "and state the corrected understanding explicitly."
                ),
            }
        )
    return tuple(items)


def build_hardened_correction_request(
    *,
    original_request_sha256: str,
    response: Mapping[str, Any],
    grade: Mapping[str, Any],
) -> dict:
    """Return only the mistakes Frankie must correct, not the exhaustive post-grade."""
    if type(original_request_sha256) is not str or len(original_request_sha256) != 64:
        raise ValueError("original principal request sha256 required")
    if (
        type(response) is not dict
        or not isinstance(response.get("session_id"), str)
        or not response["session_id"].strip()
    ):
        raise ValueError("initial Frankie session identity required")
    if (
        grade.get("schema") != classroom.GRADE_SCHEMA
        or grade.get("exhaustive_audit", {}).get("coverage_proven") is not True
    ):
        raise ValueError("complete Dipole post-grade required")
    ids = tuple(grade.get("correction_ids", ()))
    items = correction_items(grade)
    if tuple(item["correction_id"] for item in items) != ids:
        raise ValueError("learner correction item order differs from host grade")
    body = {
        "schema": CORRECTION_REQUEST_SCHEMA,
        "original_request_sha256": original_request_sha256,
        "session_id": response["session_id"],
        "model_identity_as_reported_by_session": response[
            "model_identity_as_reported_by_session"
        ],
        "post_grade_hash": grade["post_grade_hash"],
        "correction_ids": ids,
        "correction_items": items,
        "instruction": (
            "Dipole is returning only the mistakes that require correction, not the "
            "exhaustive teacher key or the complete post-grade. Stay in this exact "
            "session. Resolve every correction_id from the same causal evidence, state "
            "your corrected understanding in your own words, state any remaining "
            "disagreement explicitly, and do not treat an omitted item as an answer key."
        ),
    }
    body["request_sha256"] = evidence_hash(body)
    return body


def bind_hardened_resolution_requirement(correction: Mapping[str, Any]) -> dict:
    """Require a corrected-understanding record for every exposed correction item."""
    if (
        type(correction) is not dict
        or correction.get("schema") != CORRECTION_REQUEST_SCHEMA
    ):
        raise ValueError("Dipole correction request required")
    body = {k: v for k, v in correction.items() if k != "request_sha256"}
    body["instruction"] += (
        " Your dipole_acknowledgement must include correction_resolutions: one "
        "ordered object {correction_id, corrected_understanding} for every correction_id "
        "in correction_items. If there are no correction_ids, correction_resolutions "
        "must be an empty list. A bare ID echo is not sufficient."
    )
    body["request_sha256"] = evidence_hash(body)
    return body


class HardenedDipoleClassroomPrincipalAdapter(DipoleClassroomPrincipalAdapter):
    """Existing principal protocol with the answer-key prompt leak removed.

    prepare() is inherited: the base classroom adapter retains the source snapshot and the
    teacher key in the host-owned audit directory, not the principal directory.
    """

    def _recover_with_classroom(
        self, request_id, attachment, *, dispatch_followup
    ):
        # Call the ordinary principal recovery directly. Calling super().recover()
        # would re-enter DipoleClassroomPrincipalAdapter.recover() and recurse into
        # this override.
        envelope = FrankiePrincipalAdapter.recover(self, request_id, attachment)
        request = json.loads((self.directory / "session-request.json").read_bytes())
        retained = json.loads((self.directory / "session-response.json").read_bytes())
        initial_response = retained["response"]
        teachback, grade = grade_initial_response(
            self.classroom_package, initial_response
        )
        self._retain("dipole-classroom-teachback.json", teachback)
        self._retain_audit("dipole-classroom-post-grade.json", grade)

        correction = bind_hardened_resolution_requirement(
            build_hardened_correction_request(
                original_request_sha256=digest(request),
                response=initial_response,
                grade=grade,
            )
        )
        correction_path = self.directory / "classroom-correction-request.json"
        created = False
        if correction_path.exists():
            if json.loads(correction_path.read_bytes()) != correction:
                raise ValueError("retained Dipole classroom correction request changed")
        else:
            _write(correction_path, correction)
            created = True

        response_path = self.directory / "classroom-correction-response.json"
        if not response_path.exists():
            if not created or not dispatch_followup or self.session_executor is None:
                raise PrincipalPending(
                    "same Frankie session must consume Dipole classroom correction"
                )
            dispatched = self.session_executor(correction)
            self._record_correction_response(correction, dispatched)
        correction_envelope = json.loads(response_path.read_bytes())
        self._attest_host(
            correction_envelope["response"],
            correction_envelope["host_attestation"],
            correction,
        )
        base_acknowledgement = validate_correction_response(
            correction=correction,
            response=correction_envelope["response"],
            initial_response=initial_response,
            grade=grade,
        )
        acknowledgement = validate_correction_resolutions(
            correction_envelope["response"].get("dipole_acknowledgement"),
            grade,
            base_acknowledgement,
        )
        self._retain("dipole-classroom-acknowledgement.json", acknowledgement)
        completion = finish(
            self.classroom_package,
            teachback=teachback,
            grade=grade,
            acknowledgement=acknowledgement,
        )
        self._retain("dipole-classroom-completion.json", completion)
        transcript = render_transcript(
            self.classroom_package["pre_message"],
            teachback,
            grade,
            acknowledgement,
        )
        transcript_path = self._retain_text(
            "dipole-classroom-transcript.md", transcript
        )
        self._retain(
            "dipole-classroom-receipt.json",
            {
                "schema": "FRANKIE_DIPOLE_CLASSROOM_RECEIPT_V1",
                "classroom_binding_hash": self.classroom_package["binding"][
                    "classroom_binding_hash"
                ],
                "teacher_key_hash": self.classroom_package["teacher_key"][
                    "teacher_key_hash"
                ],
                "completion_hash": completion["completion_hash"],
                "exhaustive_audit_hash": completion["exhaustive_audit_hash"],
                "observation_claims_reviewed": completion[
                    "observation_claims_reviewed"
                ],
                "relationship_pairs_explicitly_reviewed": completion[
                    "relationship_pairs_explicitly_reviewed"
                ],
                "correction_resolutions": len(
                    acknowledgement["correction_resolutions"]
                ),
                "transcript": file_witness(transcript_path),
                "initial_session_id": initial_response["session_id"],
                "correction_session_id": correction_envelope["response"][
                    "session_id"
                ],
                "teacher_complete": completion["teacher_complete"],
            },
        )
        return envelope
