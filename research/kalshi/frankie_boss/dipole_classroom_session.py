"""Two-turn principal-session protocol for the Dipole classroom.

The first Frankie response must contain three independent records:
- the 19-component teach-back;
- an explicit review of every retained Dipole observation/value/state;
- an explicit canonical review of all 171 intra-Dipole pairs.

The host grades all three from the audit-only teacher key, sends Dipole's full
correction back to the *same* Frankie session, and requires that same session to
resolve every correction before teacher completion.  The teacher key is never
returned by model_visible_classroom().
"""
from __future__ import annotations

import math
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
EXHAUSTIVE_AUDIT_SCHEMA = "DIPOLE_CLASSROOM_EXHAUSTIVE_AUDIT_V1"
_FACTUAL_RELATIONS = ("SAME_DIRECTION", "OPPOSITE_DIRECTION", "UNRESOLVED")
_STATES = ("PRESENT", "MISSING", "INVALID", "ABLATED")


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
        "required_response_ledgers": {
            "dipole_observation_review": "EVERY_RETAINED_OBSERVATION_FOR_ALL_19_DIMENSIONS",
            "dipole_relationship_scan": PAIR_COUNT,
        },
    }
    value["model_visible_hash"] = evidence_hash(value)
    return value


def _nonempty(value, label):
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value


def _claim_components(items, label):
    if type(items) is not list or len(items) != len(COLUMNS):
        raise ValueError(f"{label} must contain exactly {len(COLUMNS)} components")
    result=[]
    for expected, item in zip(COLUMNS, items):
        if type(item) is not dict or set(item) != {"name", "observations"} or item.get("name") != expected:
            raise ValueError(f"{label} must preserve governed Dipole component order")
        observations=item["observations"]
        if type(observations) is not list or not observations:
            raise ValueError(f"{label} observations must be nonempty lists")
        seen=set();checked=[]
        for claim in observations:
            if type(claim) is not dict or set(claim) != {"cursor", "state", "value", "explanation"}:
                raise ValueError(f"{label} observation fields differ")
            cursor=claim["cursor"]
            if type(cursor) is not int or cursor < 0 or cursor in seen:
                raise ValueError(f"{label} observation cursors must be unique nonnegative integers")
            if claim["state"] not in _STATES:
                raise ValueError(f"{label} observation state outside governed vocabulary")
            value=claim["value"]
            if claim["state"] == "PRESENT":
                if type(value) not in (int,float) or isinstance(value,bool) or not math.isfinite(float(value)):
                    raise ValueError(f"{label} PRESENT observation requires finite numeric value")
                value=float(value)
            elif value is not None:
                raise ValueError(f"{label} non-PRESENT observation value must be null")
            _nonempty(claim["explanation"],f"{label} observation explanation")
            checked.append({"cursor":cursor,"state":claim["state"],"value":value,"explanation":claim["explanation"]})
            seen.add(cursor)
        result.append({"name":expected,"observations":checked})
    return result


def _claim_relationships(items):
    if type(items) is not list or len(items) != PAIR_COUNT:
        raise ValueError(f"dipole_relationship_scan must contain exactly {PAIR_COUNT} pairs")
    expected=[]
    for i,left in enumerate(COLUMNS):
        for right in COLUMNS[i+1:]:expected.append((left,right))
    checked=[]
    for pair,item in zip(expected,items):
        if type(item) is not dict or set(item) != {"left","right","direction_relation","correlation_interpretation","developing_structure"}:
            raise ValueError("dipole_relationship_scan fields differ")
        if (item.get("left"),item.get("right")) != pair:
            raise ValueError("dipole_relationship_scan must preserve the canonical 171-pair order")
        if item["direction_relation"] not in _FACTUAL_RELATIONS:
            raise ValueError("relationship direction outside governed vocabulary")
        _nonempty(item["correlation_interpretation"],"correlation interpretation")
        developing=item["developing_structure"]
        if developing is not None:_nonempty(developing,"developing structure")
        checked.append(dict(item))
    return checked


def _teacher_dimensions(key):
    result={item["name"]:item for item in key["dimensions"]}
    if tuple(result) != tuple(COLUMNS):raise ValueError("teacher key lost governed component order")
    return result


def _teacher_pairs(key):
    result={(item["left"],item["right"]):item for item in key["relationship_scan"]}
    if len(result) != PAIR_COUNT:raise ValueError("teacher key lost complete pair scan")
    return result


def _same_value(claimed, actual):
    if actual is None:return claimed is None
    return claimed is not None and math.isclose(float(claimed),float(actual),rel_tol=1e-6,abs_tol=1e-6)


def _grade_exhaustive(key, observation_review, relationship_scan):
    dimensions=_teacher_dimensions(key);pairs=_teacher_pairs(key)
    observation_grades=[];relationship_grades=[];corrections=[];all_observations=True;all_pairs=True
    total_observations=0
    for component in observation_review:
        name=component["name"];actual=dimensions[name]["observations"];claims=component["observations"]
        total_observations+=len(actual)
        if len(claims)!=len(actual):
            all_observations=False;corrections.append("observation-set:"+name)
        by_cursor={claim["cursor"]:claim for claim in claims}
        grades=[]
        for point in actual:
            claim=by_cursor.get(point["cursor"])
            if claim is None:
                ok=False;reason="Frankie omitted this retained Dipole observation."
            else:
                state_ok=claim["state"]==point["state"]
                value_ok=_same_value(claim["value"],point["value"])
                ok=state_ok and value_ok
                reason=("Correctly accounted for this retained observation."
                    if ok else f"Expected state {point['state']} value {point['value']}; Frankie reported state {claim['state']} value {claim['value']}.")
            if not ok:
                all_observations=False;corrections.append(f"observation:{name}:{point['cursor']}")
            grades.append({"cursor":point["cursor"],"state":point["state"],"value":point["value"],"correct":ok,"explanation":reason})
        extra=sorted(set(by_cursor)-{point["cursor"] for point in actual})
        if extra:
            all_observations=False;corrections.append("observation-extra:"+name)
        observation_grades.append({"name":name,"expected_count":len(actual),"claimed_count":len(claims),"grades":grades,"extra_cursors":extra})
    for claim in relationship_scan:
        pair=(claim["left"],claim["right"]);actual=pairs[pair]
        ok=claim["direction_relation"]==actual["direction_relation"]
        if not ok:
            all_pairs=False;corrections.append(f"relationship:{pair[0]}:{pair[1]}")
        relationship_grades.append({"left":pair[0],"right":pair[1],"claimed":claim["direction_relation"],
            "actual":actual["direction_relation"],"correct":ok,"correlation":actual["correlation"],
            "developing_structure":claim["developing_structure"],
            "explanation":("Correct directional relationship for the current causal window."
                if ok else f"Dipole's exact directional relationship is {actual['direction_relation']}, not {claim['direction_relation']}.")})
    corrections=tuple(dict.fromkeys(corrections))
    audit={"schema":EXHAUSTIVE_AUDIT_SCHEMA,"components_reviewed":len(observation_review),
        "expected_components":len(COLUMNS),"observation_claims_expected":total_observations,
        "observation_claims_reviewed":sum(len(item["observations"]) for item in observation_review),
        "all_observations_correct":all_observations,"relationship_pairs_expected":PAIR_COUNT,
        "relationship_pairs_reviewed":len(relationship_scan),"all_relationship_directions_correct":all_pairs,
        "observation_grades":observation_grades,"relationship_grades":relationship_grades,
        "correction_ids":corrections,"coverage_proven":len(observation_review)==len(COLUMNS) and len(relationship_scan)==PAIR_COUNT}
    audit["audit_hash"]=evidence_hash(audit)
    return audit


def grade_initial_response(package: Mapping[str, Any], response: Mapping[str, Any]) -> tuple[dict, dict]:
    package = validate_package(package)
    if type(response) is not dict:
        raise ValueError("Frankie principal response required")
    teachback = validate_teachback(response.get("dipole_teachback"), package["pre_message"])
    observation_review=_claim_components(response.get("dipole_observation_review"),"dipole_observation_review")
    relationship_scan=_claim_relationships(response.get("dipole_relationship_scan"))
    exhaustive=_grade_exhaustive(package["teacher_key"],observation_review,relationship_scan)
    teachback=dict(teachback,observation_review=observation_review,relationship_scan=relationship_scan,
        exhaustive_audit_hash=exhaustive["audit_hash"])
    teachback["teachback_hash"]=evidence_hash({k:v for k,v in teachback.items() if k!="teachback_hash"})
    grade=grade_teachback(package["teacher_key"],teachback)
    base_corrections=tuple(grade["correction_ids"])
    grade={k:v for k,v in grade.items() if k!="post_grade_hash"}
    grade["exhaustive_audit"]=exhaustive
    grade["correction_ids"]=tuple(dict.fromkeys(base_corrections+tuple(exhaustive["correction_ids"])))
    grade["mastered"]=bool(grade["mastered"] and exhaustive["all_observations_correct"] and exhaustive["all_relationship_directions_correct"])
    grade["post_grade_hash"]=evidence_hash(grade)
    return teachback,grade


def correction_request(*, original_request_sha256: str, response: Mapping[str, Any], grade: Mapping[str, Any]) -> dict:
    if type(original_request_sha256) is not str or len(original_request_sha256) != 64:
        raise ValueError("original principal request sha256 required")
    if type(response) is not dict or not isinstance(response.get("session_id"), str) or not response["session_id"].strip():
        raise ValueError("initial Frankie session identity required")
    if grade.get("schema") != GRADE_SCHEMA or grade.get("exhaustive_audit",{}).get("coverage_proven") is not True:
        raise ValueError("complete Dipole post-grade required")
    body = {
        "schema": CORRECTION_REQUEST_SCHEMA,
        "original_request_sha256": original_request_sha256,
        "session_id": response["session_id"],
        "model_identity_as_reported_by_session": response["model_identity_as_reported_by_session"],
        "post_grade": grade,
        "post_grade_hash": grade["post_grade_hash"],
        "instruction": (
            "This is Dipole's point-by-point correction of your complete classroom record, including every "
            "retained observation and all 171 relationship pairs. Stay in this exact session. Read every "
            "component, observation, and relationship correction; resolve every correction_id; state any "
            "remaining disagreement explicitly; and return dipole_acknowledgement with schema "
            f"{ACK_SCHEMA}. A cycle cannot be teacher-complete while a correction is unacknowledged or a "
            "Dipole disagreement remains unresolved."
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
    audit=grade.get("exhaustive_audit") if type(grade) is dict else None
    if (type(audit) is not dict or audit.get("schema")!=EXHAUSTIVE_AUDIT_SCHEMA or
            audit.get("coverage_proven") is not True or audit.get("components_reviewed")!=len(COLUMNS) or
            audit.get("relationship_pairs_reviewed")!=PAIR_COUNT or
            teachback.get("exhaustive_audit_hash")!=audit.get("audit_hash")):
        raise ValueError("teacher completion requires explicit observation and 171-pair audit proof")
    completed=complete_cycle(binding=package["binding"], key=package["teacher_key"],
        pre_message=package["pre_message"], teachback=teachback,
        grade=grade, acknowledgement=acknowledgement)
    return dict(completed, exhaustive_audit_hash=audit["audit_hash"],
        observation_claims_reviewed=audit["observation_claims_reviewed"],
        relationship_pairs_explicitly_reviewed=audit["relationship_pairs_reviewed"])
