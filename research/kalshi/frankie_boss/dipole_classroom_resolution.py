"""Require Frankie to restate corrected understanding for every Dipole correction.

A bare acknowledgement or list of correction IDs is not sufficient evidence that
Frankie understood Dipole's post-answer correction. The same-session response
must include one nonempty corrected-understanding statement per correction ID.
"""
from __future__ import annotations

from typing import Any, Mapping

from .c15_journal import evidence_hash
from .dipole_classroom_session import CORRECTION_REQUEST_SCHEMA


def bind_resolution_requirement(correction: Mapping[str, Any]) -> dict:
    """Add the explicit resolution schema to Dipole's same-session correction turn."""
    if type(correction) is not dict or correction.get("schema")!=CORRECTION_REQUEST_SCHEMA:
        raise ValueError("Dipole correction request required")
    body={k:v for k,v in correction.items() if k!="request_sha256"}
    body["instruction"] += (
        " Your dipole_acknowledgement must also include correction_resolutions: one ordered object "
        "{correction_id, corrected_understanding} for every correction_id in post_grade, with your corrected "
        "understanding stated in your own words. If there are no correction_ids, correction_resolutions must be an "
        "empty list. A bare ID echo is not sufficient."
    )
    body["request_sha256"]=evidence_hash(body)
    return body


def validate_correction_resolutions(raw_ack: Mapping[str, Any], grade: Mapping[str, Any], base_ack: Mapping[str, Any]) -> dict:
    if type(raw_ack) is not dict or type(grade) is not dict or type(base_ack) is not dict:
        raise ValueError("Dipole correction resolution records required")
    expected=tuple(grade.get("correction_ids",()))
    records=raw_ack.get("correction_resolutions")
    if type(records) is not list or len(records)!=len(expected):
        raise ValueError("one corrected-understanding record is required for every Dipole correction")
    seen=set();checked=[]
    for item in records:
        if type(item) is not dict or set(item)!={"correction_id","corrected_understanding"}:
            raise ValueError("Dipole correction resolution fields differ")
        correction_id=item["correction_id"]
        understanding=item["corrected_understanding"]
        if correction_id not in expected or correction_id in seen:
            raise ValueError("Dipole correction resolution ID is unknown or duplicate")
        if type(understanding) is not str or not understanding.strip():
            raise ValueError("corrected Dipole understanding must be explicit nonempty text")
        seen.add(correction_id);checked.append(dict(item))
    if set(seen)!=set(expected):
        raise ValueError("every Dipole correction must have a corrected-understanding record")
    if set(base_ack.get("resolved_correction_ids",()))!=set(expected):
        raise ValueError("base Dipole acknowledgement correction set differs")
    result={k:v for k,v in base_ack.items() if k!="ack_hash"}
    result["correction_resolutions"]=checked
    result["ack_hash"]=evidence_hash(result)
    return result
