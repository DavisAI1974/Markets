"""Two-turn principal-session protocol for the Dipole classroom.

The first Frankie response contains the full 19-dimension teach-back.  The host
then grades it from the audit-only teacher key and sends Dipole's correction back
to the *same* Frankie session.  That same session must acknowledge and resolve
every correction before the cycle can become teacher-complete.

The audit-only teacher key is never returned by model_visible_classroom().
"""
from __future__ import annotations

from typing import Any, Mapping

from .c15_journal import evidence_hash
from .c15_normalizer import COLUMNS
from .dipole_classroom import (
    ACK_SCHEMA,
    GRADE_SCHEMA,
    KEY_SCHEMA,
    MESSAGE_SCHEMA,
    PAIR_COUNT,
    SOURCE_SCHEMA,
    TEACHBACK_SCHEMA,
    complete_cycle,
    grade_teachback,
    validate_acknowledgement,
    validate_teachback,
)

CORRECTION_REQUEST_SCHEMA = "FRANKIE_DIPOLE_CLASSROOM_CORRECTION_REQUEST_V1"


def validate_package(package: Mapping[str, Any]) -> dict:
    if type(package) is not dict or set(package) != {"source", "teacher_key", "pre_message", "binding"}:
        raise ValueError("complete Dipole classroom package required")
    source = package["source"];key = package["teacher_key"];pre = package["pre_message"];binding = package["binding"]
    if source.get("schema") != SOURCE_SCHEMA or key.get("schema") != KEY_SCHEMA or pre.get("schema") != MESSAGE_SCHEMA:
        raise ValueError("Dipole classroom package schemas differ")
    if source.get("source_snapshot_hash") != binding.get("source_snapshot_hash"):
        raise ValueError("classroom source binding differs")
    if key.get("teacher_key_hash") != binding.get("teacher_key_hash") or key.get("source_snapshot_hash") != source.get("source_snapshot_hash"):
        raise ValueError("classroom teacher key binding differs")
    if pre.get("teacher_message_hash") != binding.get("teacher_message_hash") or pre.get("teacher_key_hash") != key.get("teacher_key_hash"):
        raise ValueError("classroom pre-message binding differs")
    if key.get("coverage_count") != len(COLUMNS) or pre.get("coverage_count") != len(COLUMNS):
        raise ValueError("classroom package lost 19-of-19 coverage")
    if key.get("relationship_pairs_scanned") != PAIR_COUNT or pre.get("relationship_pairs_required") != PAIR_COUNT:
        raise ValueError("classroom package lost complete relationship scan")
    return dict(package)


def model_visible_classroom(package: Mapping[str, Any]) -> dict:
    """Exactly what Frankie is allowed to see before answering; never the key."""
    package = validate_package(package)
    value = {
        "binding": package["binding"],
        "pre_message": package["pre_message"],
        "audit_key_withheld": True,
        "coverage_invariant": "ALL_19_DIPOLE_DIMENSIONS_EVERY_CYCLE",
    }
    value["model_visible_hash"] = evidence_hash(value)
    return value


def grade_initial_response(package: Mapping[str, Any], response: Mapping[str, Any]) -> tuple[dict, dict]:
    package = validate_package(package)
    if type(response) is not dict:
        raise ValueError("Frankie principal response required")
    teachback = validate_teachback(response.get("dipole_teachback"), package["pre_message"])
    grade = grade_teachback(package["teacher_key"], teachback)
    return teachback, grade


def correction_request(*, original_request_sha256: str, response: Mapping[str, Any], grade: Mapping[str, Any]) -> dict:
    if type(original_request_sha256) is not str or len(original_request_sha256) != 64:
        raise ValueError("original principal request sha256 required")
    if type(response) is not dict or not isinstance(response.get("session_id"), str) or not response["session_id"].strip():
        raise ValueError("initial Frankie session identity required")
    if grade.get("schema") != GRADE_SCHEMA:
        raise ValueError("Dipole post-grade required")
    body = {
        "schema": CORRECTION_REQUEST_SCHEMA,
        "original_request_sha256": original_request_sha256,
        "session_id": response["session_id"],
        "model_identity_as_reported_by_session": response["model_identity_as_reported_by_session"],
        "post_grade": grade,
        "post_grade_hash": grade["post_grade_hash"],
        "instruction": (
            "This is Dipole's point-by-point correction of your teach-back. Stay in this exact session. "
            "Read every component correction and relationship correction, resolve every correction_id, "
            "state any remaining disagreement explicitly, and return dipole_acknowledgement with schema "
            f"{ACK_SCHEMA}. A cycle cannot be teacher-complete while a correction is unacknowledged or "
            "a Dipole disagreement remains unresolved."
        ),
    }
    body["request_sha256"] = evidence_hash(body)
    return body


def validate_correction_response(*, correction: Mapping[str, Any], response: Mapping[str, Any],
                                 initial_response: Mapping[str, Any], grade: Mapping[str, Any]) -> dict:
    if correction.get("schema") != CORRECTION_REQUEST_SCHEMA:
        raise ValueError("Dipole classroom correction request required")
    if type(response) is not dict:
        raise ValueError("Frankie correction response required")
    if response.get("session_id") != initial_response.get("session_id"):
        raise ValueError("Dipole correction must return from the same Frankie session")
    if response.get("model_identity_as_reported_by_session") != initial_response.get("model_identity_as_reported_by_session"):
        raise ValueError("Frankie model identity changed during Dipole classroom correction")
    if response.get("request_sha256") != correction.get("request_sha256"):
        raise ValueError("Frankie correction response belongs to a different correction request")
    return validate_acknowledgement(response.get("dipole_acknowledgement"), grade,
        session_id=initial_response["session_id"])


def finish(package: Mapping[str, Any], *, teachback: Mapping[str, Any], grade: Mapping[str, Any],
           acknowledgement: Mapping[str, Any]) -> dict:
    package = validate_package(package)
    return complete_cycle(binding=package["binding"], key=package["teacher_key"],
        pre_message=package["pre_message"], teachback=teachback,
        grade=grade, acknowledgement=acknowledgement)
