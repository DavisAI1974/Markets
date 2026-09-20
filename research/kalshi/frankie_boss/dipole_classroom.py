"""Auditable Dipole -> Frankie classroom protocol over governed C15 targets.

Objective (audit 2026-09-20, Greg Davis: the exhaustion research is the objective and must be
stated wherever Frankie is taught): the 19 C15 Dipole dimensions taught here are the opposing-
pressure surface of the EXHAUSTION research (calculation contract section 4.12, "Dipole and
opposing-pressure runway"); the classroom exists so Frankie reads dipole state as part of
exhaustion formation, runway, chains and D-depth, pre-birth and the causal clocks, never as a
subject of its own.

Core rule: complete Dipole coverage is invariant; only who does the explaining
changes.  Early cycles are full TEACH cycles.  Dipole may back away only after
Frankie demonstrates mastery and acknowledges corrections.  The governed
mathematical teacher remains authoritative; this module does not derive a new
market label, alter a DipoleTarget, run a model, or cross the causal cutoff.

The durable exchange is:

    complete audit-only teacher key
      -> model-visible Dipole pre-message
      -> Frankie's structured teach-back
      -> deterministic factual/correlation grade and correction
      -> same-session Frankie correction acknowledgement
      -> teacher-complete gate

Every cycle accounts for all 19 C15 Dipole dimensions, every target state/value
available in the teacher attachment, every prior-cycle comparison when one exists,
and the full 171-pair intra-Dipole relationship scan.  Later Socratic modes can
withhold the answer key, but never reduce the required coverage.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Mapping, Sequence

try:
    from .c15_journal import evidence_hash
    from .c15_normalizer import COLUMNS
    from .dipole_target import DipoleTarget, TargetState
except ImportError:
    from c15_journal import evidence_hash
    from c15_normalizer import COLUMNS
    from dipole_target import DipoleTarget, TargetState

SOURCE_SCHEMA = "DIPOLE_CLASSROOM_SOURCE_V1"
KEY_SCHEMA = "DIPOLE_CLASSROOM_TEACHER_KEY_V1"
MESSAGE_SCHEMA = "DIPOLE_CLASSROOM_PRE_MESSAGE_V1"
TEACHBACK_SCHEMA = "DIPOLE_CLASSROOM_TEACHBACK_V1"
GRADE_SCHEMA = "DIPOLE_CLASSROOM_POST_GRADE_V1"
ACK_SCHEMA = "DIPOLE_CLASSROOM_CORRECTION_ACK_V1"
COMPLETION_SCHEMA = "DIPOLE_CLASSROOM_COMPLETION_V1"
PRIOR_CORRECTION_SCHEMA = "DIPOLE_CLASSROOM_PRIOR_CORRECTION_SUMMARY_V1"

_HEX = frozenset("0123456789abcdef")
_STATE_NAMES = tuple(state.name for state in TargetState)
_DIRECTIONS = ("RISE", "FALL", "FLAT", "INSUFFICIENT")
_RELATIONS = ("SAME_DIRECTION", "OPPOSITE_DIRECTION", "UNRESOLVED", "HYPOTHESIS")
PAIR_COUNT = len(COLUMNS) * (len(COLUMNS) - 1) // 2
# Pearson over fewer overlapping PRESENT points than this is noise; below it only the overlap
# count is reported. Declared once here; every layer and message text reads this constant.
MIN_PEARSON_PRESENT_OVERLAP = 8


class ClassroomMode(str, Enum):
    TEACH = "TEACH"
    GUIDED = "GUIDED"
    SOCRATIC = "SOCRATIC"
    VERIFY = "VERIFY"


_MODES = tuple(mode.value for mode in ClassroomMode)
_NEXT_MODE = {
    ClassroomMode.TEACH.value: ClassroomMode.GUIDED.value,
    ClassroomMode.GUIDED.value: ClassroomMode.SOCRATIC.value,
    ClassroomMode.SOCRATIC.value: ClassroomMode.VERIFY.value,
    ClassroomMode.VERIFY.value: ClassroomMode.VERIFY.value,
}

# Curriculum descriptions of equations already implemented by c15_teacher,
# c15_teacher_r3 and c15_dstate.  These are explanatory metadata, not features.
ROLE_DEFINITIONS = {
    "far_front_age_log": "Age of the front resting order in the selected far-side top-three cohort.",
    "far_queue_age_p90_log": "Age threshold accounting for 90 percent of selected far-side top-three cohort size.",
    "far_size_hhi": "Herfindahl concentration of displayed size across the selected far-side top-three cohort.",
    "far_replenish_log1p_64": "64-group far-side top-three net addition-versus-removal geometry.",
    "far_replenish_log1p_1024": "1024-group far-side top-three net addition-versus-removal geometry.",
    "far_priority_loss_rate_64": "Share of 64-group far-side top-three modifications that lose queue priority.",
    "far_priority_loss_rate_1024": "Share of 1024-group far-side top-three modifications that lose queue priority.",
    "far_absorption_share_64": "64-group share of reconciled far-side removals attributable to fills.",
    "far_absorption_share_1024": "1024-group share of reconciled far-side removals attributable to fills.",
    "far_identity_survival_64": "Fraction of the original 64-group far-side cohort whose order identities survive.",
    "far_identity_survival_1024": "Fraction of the original 1024-group far-side cohort whose order identities survive.",
    "far_size_retention_64": "Fraction of original 64-group cohort quantity retained by those same orders.",
    "far_size_retention_1024": "Fraction of original 1024-group cohort quantity retained by those same orders.",
    "unresolved_age_groups_log": "D-chain age of the current unresolved far-side extreme in instrument groups.",
    "extension_count_log": "D-chain count of completed far-side extensions in the current chain.",
    "step_ratio_log": "Log ratio of latest completed extension magnitude to the previous completed extension magnitude.",
    "pullback_ticks_last_log": "Log pullback depth in ticks associated with the latest completed far-side extension.",
    "step_duration_groups_log": "Log duration in instrument groups of the latest completed far-side step.",
    "pullback_ticks_prev_log": "Log pullback depth in ticks associated with the previous completed far-side extension.",
}

BEHAVIOR_BASIS = {
    "far_front_age_log": "FIFO/resting-order persistence at the visible far-side queue front.",
    "far_queue_age_p90_log": "Full-book order-age structure behind most displayed far-side size.",
    "far_size_hhi": "Full-book concentration versus dispersion of visible far-side resting size.",
    "far_replenish_log1p_64": "Short-horizon add/remove behavior in the full far-side order cohort.",
    "far_replenish_log1p_1024": "Long-horizon add/remove persistence in the full far-side order cohort.",
    "far_priority_loss_rate_64": "Short-horizon FIFO deterioration caused by modifications that surrender priority.",
    "far_priority_loss_rate_1024": "Long-horizon FIFO deterioration caused by modifications that surrender priority.",
    "far_absorption_share_64": "Short-horizon executed absorption separated from other disappearing displayed size.",
    "far_absorption_share_1024": "Long-horizon executed absorption separated from other disappearing displayed size.",
    "far_identity_survival_64": "Short-horizon order-identity persistence rather than anonymous aggregate depth.",
    "far_identity_survival_1024": "Long-horizon order-identity persistence rather than anonymous aggregate depth.",
    "far_size_retention_64": "Short-horizon retained quantity on the same identified resting orders.",
    "far_size_retention_1024": "Long-horizon retained quantity on the same identified resting orders.",
    "unresolved_age_groups_log": "Persistence of the current far-side geometric state across instrument groups.",
    "extension_count_log": "Repeated far-side pullback/extension structure in D-chain geometry.",
    "step_ratio_log": "Change in extension magnitude from one completed D-chain step to the next.",
    "pullback_ticks_last_log": "Depth of the pullback that preceded the latest completed far-side extension.",
    "step_duration_groups_log": "Time-in-groups required to complete the latest far-side extension step.",
    "pullback_ticks_prev_log": "Prior pullback depth retained for comparison with the latest completed step.",
}

if tuple(ROLE_DEFINITIONS) != tuple(COLUMNS) or tuple(BEHAVIOR_BASIS) != tuple(COLUMNS):
    raise RuntimeError("Dipole classroom curriculum must cover C15 columns exactly and in order")


def _hex(value: Any, name: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in _HEX for c in value):
        raise ValueError(f"{name} must be a sha256 hex digest")
    return value


def _nonempty(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def _state_name(raw: int) -> str:
    try:
        return TargetState(int(raw)).name
    except (TypeError, ValueError) as exc:
        raise ValueError("teacher state outside TargetState") from exc


def _target_row(target: DipoleTarget, raw_row: Sequence[Mapping[str, Any]], receipt: Mapping[str, Any], cursor: int) -> dict:
    if not isinstance(target, DipoleTarget):
        raise ValueError("governed DipoleTarget required")
    target.check_integrity()
    if tuple(target.spec.target_names) != tuple(COLUMNS):
        raise ValueError("teacher target columns differ from governed C15 classroom surface")
    if tuple(target.values.shape) != (1, 1, len(COLUMNS)) or tuple(target.states.shape) != target.values.shape:
        raise ValueError("one governed 19-column target row required per context cursor")
    if tuple(target.ts_recv_ns.shape) != (1, 1):
        raise ValueError("target timestamp must be one causal timestamp")
    if len(raw_row) != len(COLUMNS):
        raise ValueError("raw teacher row must retain every governed column")
    if receipt.get("cursor") != cursor or receipt.get("target_hash") != target.target_hash:
        raise ValueError("teacher step receipt differs from target/cursor")
    if receipt.get("source_prefix_hash") != target.source_prefix_hash:
        raise ValueError("teacher step receipt source prefix differs from target")
    values = target.values.detach().cpu()[0, 0].tolist()
    states = target.states.detach().cpu()[0, 0].tolist()
    ts_recv_ns = int(target.ts_recv_ns.detach().cpu()[0, 0].item())
    components = []
    for index, name in enumerate(COLUMNS):
        raw = raw_row[index]
        state = _state_name(states[index])
        reason = raw.get("reason", "")
        if type(reason) is not str:
            raise ValueError("teacher reason must be text")
        components.append({
            "name": name,
            "unit": target.spec.target_units[index],
            "value": float(values[index]) if state == TargetState.PRESENT.name else None,
            "state": state,
            "raw_reason": reason,
        })
    return {
        "cursor": cursor,
        "target_hash": target.target_hash,
        "source_manifest_hash": target.source_manifest_hash,
        "source_prefix_hash": target.source_prefix_hash,
        "as_of_ts_recv_ns": target.as_of_ts_recv_ns,
        "ts_recv_ns": ts_recv_ns,
        "components": components,
        "step_receipt_hash": evidence_hash(receipt),
    }


def snapshot_teacher_attachment(teacher: Mapping[str, Any], *, request_id: str, cycle_index: int, cycle_count: int,
                                source_hash: str, as_of: int, through_cursor: int) -> dict:
    """Losslessly snapshot every context Dipole target row for this causal cycle.

    cycle_count is the run's curriculum length, owned by the retained runtime schedule (the
    host derives it from the schedule steps). It is not a classroom constant: the 19 Sunday
    cycles and the 19 Dipole columns are unrelated numbers.
    """
    _nonempty(request_id, "request_id")
    if type(cycle_count) is not int or cycle_count <= 0:
        raise ValueError("positive curriculum cycle count required")
    if type(cycle_index) is not int or not 0 <= cycle_index < cycle_count:
        raise ValueError("cycle_index must be inside the retained runtime schedule")
    _hex(source_hash, "source_hash")
    if type(as_of) is not int or as_of <= 0 or type(through_cursor) is not int or through_cursor < 0:
        raise ValueError("positive causal cutoff and nonnegative cursor required")
    if type(teacher) is not dict:
        raise ValueError("governed teacher attachment required")
    required = {"targets", "raw", "processed_records", "context_cursors", "step_receipts",
                "attachment_hash", "candidate_digest"}
    if not required.issubset(teacher):
        raise ValueError("teacher attachment missing governed fields")
    targets = tuple(teacher["targets"]);raw_rows = tuple(teacher["raw"])
    cursors = tuple(teacher["context_cursors"]);receipts = tuple(teacher["step_receipts"])
    if not targets or not (len(targets) == len(raw_rows) == len(cursors) == len(receipts)):
        raise ValueError("teacher target/raw/cursor/receipt cardinality differs")
    if tuple(sorted(set(cursors))) != cursors or any(type(c) is not int or not 0 <= c <= through_cursor for c in cursors):
        raise ValueError("teacher context cursors must be ordered unique members of causal prefix")
    rows = tuple(_target_row(t, r, s, c) for t, r, s, c in zip(targets, raw_rows, receipts, cursors))
    if any(row["as_of_ts_recv_ns"] > as_of or row["ts_recv_ns"] > as_of for row in rows):
        raise ValueError("classroom target exceeds causal cutoff")
    if any(row["source_manifest_hash"] != rows[0]["source_manifest_hash"] for row in rows):
        raise ValueError("teacher targets cross source manifests")
    body = {
        "schema": SOURCE_SCHEMA,"request_id": request_id,"cycle_index": cycle_index,"cycle_count": cycle_count,
        "source_hash": source_hash,"as_of": as_of,"through_cursor": through_cursor,
        "teacher_attachment_hash": _hex(teacher["attachment_hash"], "teacher attachment hash"),
        "candidate_digest": _hex(teacher["candidate_digest"], "candidate digest"),
        "processed_records": teacher["processed_records"],"context_cursors": cursors,"rows": rows,
        "coverage_columns": tuple(COLUMNS),"coverage_count": len(COLUMNS),
    }
    body["source_snapshot_hash"] = evidence_hash(body)
    return body


def _dimension_ledger(snapshot: Mapping[str, Any], index: int) -> tuple[dict, ...]:
    name = COLUMNS[index];result = []
    for row in snapshot["rows"]:
        component = row["components"][index]
        if component["name"] != name:raise ValueError("teacher row column order changed")
        result.append({"cursor": row["cursor"],"ts_recv_ns": row["ts_recv_ns"],"target_hash": row["target_hash"],
            "state": component["state"],"value": component["value"],"raw_reason": component["raw_reason"]})
    return tuple(result)


def _first_last_present(ledger: Sequence[Mapping[str, Any]]):
    present = [point for point in ledger if point["state"] == TargetState.PRESENT.name]
    return (present[0], present[-1]) if present else (None, None)


def _direction(ledger: Sequence[Mapping[str, Any]]) -> str:
    first,last = _first_last_present(ledger)
    if first is None or last is None or first["cursor"] == last["cursor"]:return "INSUFFICIENT"
    if last["value"] > first["value"]:return "RISE"
    if last["value"] < first["value"]:return "FALL"
    return "FLAT"


def _state_counts(ledger: Sequence[Mapping[str, Any]]) -> dict:
    return {name: sum(point["state"] == name for point in ledger) for name in _STATE_NAMES}


def _change(previous: Mapping[str, Any] | None, current_ledger: Sequence[Mapping[str, Any]]) -> dict | None:
    if previous is None:return None
    current = current_ledger[-1];prior = previous["terminal"]
    delta = None
    if current["state"] == prior["state"] == TargetState.PRESENT.name:
        delta = current["value"] - prior["value"]
    return {"previous_terminal": prior,"current_terminal": current,
        "terminal_state_changed": prior["state"] != current["state"],"present_value_delta": delta,
        "previous_direction": previous["direction"],"current_direction": _direction(current_ledger)}


def _pearson(left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]]) -> dict:
    pairs = [(a["value"],b["value"]) for a,b in zip(left,right)
        if a["cursor"] == b["cursor"] and a["state"] == b["state"] == TargetState.PRESENT.name]
    n=len(pairs)
    if n<MIN_PEARSON_PRESENT_OVERLAP:
        return {"present_overlap":n,"pearson":None,"reason":f"FEWER_THAN_{MIN_PEARSON_PRESENT_OVERLAP}_OVERLAPPING_PRESENT_VALUES"}
    xs=[a for a,_ in pairs];ys=[b for _,b in pairs];mx=sum(xs)/n;my=sum(ys)/n
    vx=sum((x-mx)**2 for x in xs);vy=sum((y-my)**2 for y in ys)
    if vx==0 or vy==0:return {"present_overlap":n,"pearson":None,"reason":"ZERO_VARIANCE"}
    value=sum((x-mx)*(y-my) for x,y in pairs)/math.sqrt(vx*vy)
    return {"present_overlap":n,"pearson":float(value),"reason":None}


def _direction_relation(left: str,right: str) -> str:
    if left in ("RISE","FALL") and right in ("RISE","FALL"):
        return "SAME_DIRECTION" if left==right else "OPPOSITE_DIRECTION"
    return "UNRESOLVED"


def build_teacher_key(snapshot: Mapping[str, Any], previous_snapshot: Mapping[str, Any] | None = None) -> dict:
    """Complete audit key, including all values/states and all 171 pair scans."""
    if snapshot.get("schema") != SOURCE_SCHEMA or snapshot.get("coverage_columns") != tuple(COLUMNS):
        raise ValueError("complete Dipole classroom source snapshot required")
    if evidence_hash({k:v for k,v in snapshot.items() if k!="source_snapshot_hash"}) != snapshot.get("source_snapshot_hash"):
        raise ValueError("classroom source snapshot changed")
    if snapshot["cycle_index"] and previous_snapshot is None:
        raise ValueError("every cycle after zero requires the preceding classroom source snapshot")
    previous = {}
    if previous_snapshot is not None:
        if previous_snapshot.get("schema") != SOURCE_SCHEMA or previous_snapshot["cycle_index"] != snapshot["cycle_index"]-1:
            raise ValueError("previous classroom snapshot must be the immediately preceding cycle")
        for index,name in enumerate(COLUMNS):
            ledger=_dimension_ledger(previous_snapshot,index)
            previous[name]={"terminal":ledger[-1],"direction":_direction(ledger),"state_counts":_state_counts(ledger)}
    dimensions=[];ledgers={};directions={}
    for index,name in enumerate(COLUMNS):
        ledger=_dimension_ledger(snapshot,index);ledgers[name]=ledger;direction=_direction(ledger);directions[name]=direction
        nonpresent=tuple({"cursor":p["cursor"],"state":p["state"],"reason":p["raw_reason"]} for p in ledger
            if p["state"] != TargetState.PRESENT.name)
        dimensions.append({"name":name,"role":ROLE_DEFINITIONS[name],"behavior_basis":BEHAVIOR_BASIS[name],
            "unit":snapshot["rows"][0]["components"][index]["unit"],"observations":ledger,
            "state_counts":_state_counts(ledger),"nonpresent_explanations":nonpresent,
            "terminal_state":ledger[-1]["state"],"terminal_value":ledger[-1]["value"],
            "terminal_reason":ledger[-1]["raw_reason"],"first_to_last_present_direction":direction,
            "previous_cycle":previous.get(name),"change_from_previous":_change(previous.get(name),ledger)})
    relationships=[]
    for i,left in enumerate(COLUMNS):
        for right in COLUMNS[i+1:]:
            corr=_pearson(ledgers[left],ledgers[right])
            relationships.append({"left":left,"right":right,
                "direction_relation":_direction_relation(directions[left],directions[right]),
                "correlation":corr,
                "interpretation_limit":"DESCRIPTIVE_WITHIN_CAUSAL_WINDOW_NOT_CAUSATION_OR_FUTURE_PREDICTION"})
    if len(relationships)!=PAIR_COUNT:raise ValueError("complete pairwise Dipole scan required")
    body={"schema":KEY_SCHEMA,"request_id":snapshot["request_id"],"cycle_index":snapshot["cycle_index"],
        "source_snapshot_hash":snapshot["source_snapshot_hash"],"teacher_attachment_hash":snapshot["teacher_attachment_hash"],
        "coverage_columns":tuple(COLUMNS),"coverage_count":len(COLUMNS),"dimensions":tuple(dimensions),
        "relationship_scan":tuple(relationships),"relationship_pairs_scanned":PAIR_COUNT,
        "causality_rule":"OBSERVATION_INTERPRETATION_HYPOTHESIS_MUST_REMAIN_DISTINCT; NO FUTURE_OUTCOME CLAIM"}
    body["teacher_key_hash"]=evidence_hash(body);return body


def select_mode(history: Sequence[Mapping[str, Any]]) -> str:
    """Dipole earns the right to back away only after two mastered acknowledged cycles."""
    if not history:return ClassroomMode.TEACH.value
    for item in history:
        if item.get("schema")!=COMPLETION_SCHEMA or item.get("mode") not in _MODES or item.get("teacher_complete") is not True:
            raise ValueError("classroom history contains an invalid completion")
    current=history[-1]["mode"];tail=[]
    for item in reversed(history):
        if item["mode"]!=current:break
        tail.append(item)
    if len(tail)>=2 and all(item["mastered"] and item["acknowledged"] for item in tail[:2]):
        return _NEXT_MODE[current]
    return current


def _observation_text(d: Mapping[str, Any]) -> str:
    c=d["state_counts"]
    return (f"This component has {c['PRESENT']} PRESENT, {c['MISSING']} MISSING, {c['INVALID']} INVALID, "
        f"and {c['ABLATED']} ABLATED observations in the retained classroom window. Its terminal state is "
        f"{d['terminal_state']} and its first-to-last PRESENT direction is {d['first_to_last_present_direction']}.")


def _teacher_component(d: Mapping[str, Any],mode:str)->dict:
    base={"name":d["name"],"role":d["role"],"behavior_basis":d["behavior_basis"],"unit":d["unit"],
        "required_review":"Account for every state/value available for this component, its prior-cycle change, why it matters, its FIFO/full-book/order relation where applicable, relationships to other Dipole components, and uncertainty."}
    if mode==ClassroomMode.TEACH.value:
        return {**base,"teacher_explanation":"I am teaching this component exhaustively before you answer. Nothing in its retained Dipole evidence may be skipped.",
            "what_happened":_observation_text(d),"why_it_matters":d["role"]+" "+d["behavior_basis"],
            "observation_interpretation_boundary":"The target states/values below are observations. Their market meaning is interpretation. They do not establish a later outcome.",
            "observations":d["observations"],"state_counts":d["state_counts"],"nonpresent_explanations":d["nonpresent_explanations"],
            "terminal_state":d["terminal_state"],"terminal_value":d["terminal_value"],"terminal_reason":d["terminal_reason"],
            "first_to_last_present_direction":d["first_to_last_present_direction"],"previous_cycle":d["previous_cycle"],
            "change_from_previous":d["change_from_previous"]}
    if mode==ClassroomMode.GUIDED.value:
        return {**base,"teacher_explanation":"We still review the complete evidence together, but you must do more of the interpretation.",
            "observations":d["observations"],"state_counts":d["state_counts"],"nonpresent_explanations":d["nonpresent_explanations"],
            "previous_cycle":d["previous_cycle"],"change_from_previous":d["change_from_previous"]}
    return {**base,"teacher_explanation":"You now lead. Analyze the complete Dipole surface from the causal evidence and account for this component explicitly; I will reveal my factual key only after your answer."}


def prior_correction_summary(grade:Mapping[str,Any]|None)->dict|None:
    """What the next cycle may carry from the previous grade: WHERE Frankie was corrected, never the key.

    The full post-grade holds every actual observation and all 171 actual relations; consecutive
    context windows overlap, so embedding it would hand the next cycle most of its answers one
    turn late. Only the correction identifiers, their count and the mastery flag travel.
    """
    if grade is None:return None
    if grade.get("schema")!=GRADE_SCHEMA:raise ValueError("prior correction must be a classroom post-grade")
    correction_ids=tuple(grade.get("correction_ids",()))
    if any(type(value) is not str or not value for value in correction_ids):raise ValueError("prior correction ids must be nonempty strings")
    return {"schema":PRIOR_CORRECTION_SCHEMA,"post_grade_hash":grade.get("post_grade_hash"),"correction_ids":correction_ids,
        "correction_count":len(correction_ids),"prior_cycle_mastered":grade.get("mastered") is True,
        "guidance":("These identifiers mark prior-cycle misunderstandings only. Recompute the current causal window "
            "from its own evidence; no prior actual value, state, direction, pair answer, or exhaustive audit is carried forward.")}


def build_pre_message(key:Mapping[str,Any],*,mode:str,prior_grade:Mapping[str,Any]|None=None)->dict:
    if key.get("schema")!=KEY_SCHEMA or key.get("coverage_columns")!=tuple(COLUMNS) or key.get("relationship_pairs_scanned")!=PAIR_COUNT:
        raise ValueError("complete classroom teacher key required")
    if mode not in _MODES:raise ValueError("known classroom mode required")
    prior_summary=prior_correction_summary(prior_grade)
    components=tuple(_teacher_component(d,mode) for d in key["dimensions"])
    if tuple(x["name"] for x in components)!=tuple(COLUMNS):raise ValueError("pre-message lost Dipole coverage")
    relationship_review=key["relationship_scan"] if mode==ClassroomMode.TEACH.value else None
    body={"schema":MESSAGE_SCHEMA,"request_id":key["request_id"],"cycle_index":key["cycle_index"],"mode":mode,
        "teacher_key_hash":key["teacher_key_hash"],"coverage_columns":tuple(COLUMNS),"coverage_count":len(COLUMNS),
        "relationship_pairs_required":PAIR_COUNT,"prior_cycle_correction":prior_summary,
        "teacher_opening":"Complete Dipole coverage is mandatory. We will account for all 19 components, all PRESENT values, every MISSING/INVALID/ABLATED state and reason, prior-cycle changes, full-book/FIFO/order behavior where justified, and the full intra-Dipole relationship surface. Observation, interpretation, hypothesis, and unknowable future outcome must remain separate.",
        "components":components,"relationship_review":relationship_review,
        "relationship_instruction":f"Consider all {PAIR_COUNT} Dipole pairs. Pearson is reported only with at least {MIN_PEARSON_PRESENT_OVERLAP} overlapping PRESENT values and nonzero variance; below that threshold only the overlap count is retained. It is descriptive, not proof of causation or future outcome. Label unsupported developing structures HYPOTHESIS.",
        "teachback_instruction":"In your own words, cover all 19 dimensions without omission: what happened, what changed or stayed stable, what the states/values mean, why, FIFO/full-book/order behavior where appropriate, every relevant relationship/correlation, what may be a developing structure, and what cannot yet be known.",
        "future_wall":"DO_NOT_CLAIM_OR_USE_ANY_OUTCOME_NOT_CAUSALLY_AVAILABLE_AT_THIS_CUTOFF"}
    body["teacher_message_hash"]=evidence_hash(body);return body


def prepare_cycle(teacher:Mapping[str,Any],*,request_id:str,cycle_index:int,cycle_count:int,source_hash:str,as_of:int,through_cursor:int,
                  previous_snapshot:Mapping[str,Any]|None=None,history:Sequence[Mapping[str,Any]]=(),prior_grade:Mapping[str,Any]|None=None)->dict:
    snapshot=snapshot_teacher_attachment(teacher,request_id=request_id,cycle_index=cycle_index,cycle_count=cycle_count,source_hash=source_hash,as_of=as_of,through_cursor=through_cursor)
    key=build_teacher_key(snapshot,previous_snapshot);mode=select_mode(history);message=build_pre_message(key,mode=mode,prior_grade=prior_grade)
    binding={"request_id":request_id,"cycle_index":cycle_index,"cycle_count":cycle_count,"source_hash":source_hash,"as_of":as_of,"through_cursor":through_cursor,
        "source_snapshot_hash":snapshot["source_snapshot_hash"],"teacher_key_hash":key["teacher_key_hash"],
        "teacher_message_hash":message["teacher_message_hash"],"teacher_attachment_hash":snapshot["teacher_attachment_hash"],
        "mode":mode,"coverage_count":len(COLUMNS),"relationship_pairs_required":PAIR_COUNT}
    binding["classroom_binding_hash"]=evidence_hash(binding)
    return {"source":snapshot,"teacher_key":key,"pre_message":message,"binding":binding}


def _components_by_name(items:Any,*,label:str)->dict[str,Mapping[str,Any]]:
    if type(items) is not list or len(items)!=len(COLUMNS):raise ValueError(f"{label} must contain exactly {len(COLUMNS)} Dipole components")
    result={}
    for item in items:
        if type(item) is not dict:raise ValueError(f"{label} components must be objects")
        name=item.get("name")
        if name not in COLUMNS or name in result:raise ValueError(f"{label} contains unknown or duplicate Dipole component")
        result[name]=item
    if tuple(result)!=tuple(COLUMNS):raise ValueError(f"{label} must preserve governed Dipole column order")
    return result


def _checked_state_counts(value:Any)->dict:
    if type(value) is not dict or set(value)!=set(_STATE_NAMES) or any(type(value[n]) is not int or value[n]<0 for n in _STATE_NAMES):
        raise ValueError("teach-back state_counts must explicitly account for PRESENT/MISSING/INVALID/ABLATED")
    if sum(value.values())<=0:raise ValueError("teach-back state_counts cannot be empty")
    return dict(value)


def validate_teachback(value:Mapping[str,Any],pre_message:Mapping[str,Any])->dict:
    """Frankie must explicitly account for all 19 components and the full pair scan."""
    if type(value) is not dict or value.get("schema")!=TEACHBACK_SCHEMA:raise ValueError("structured Dipole classroom teach-back required")
    if value.get("teacher_message_hash")!=pre_message.get("teacher_message_hash"):raise ValueError("teach-back belongs to a different teacher message")
    if value.get("future_outcome_claimed") is not False:raise ValueError("same-cycle teach-back may not claim a future outcome")
    if value.get("relationship_pairs_considered")!=PAIR_COUNT:raise ValueError("Frankie must consider the full intra-Dipole relationship surface")
    components=_components_by_name(value.get("components"),label="teach-back");normalized=[]
    for name in COLUMNS:
        item=components[name]
        allowed={"name","state_counts","terminal_state","direction","explanation","why","market_behavior","fifo_full_book_order_link","evidence","uncertainty","relationships"}
        if set(item)!=allowed:raise ValueError("teach-back component fields differ from classroom contract")
        if item["terminal_state"] not in _STATE_NAMES or item["direction"] not in _DIRECTIONS:raise ValueError("teach-back state/direction outside governed vocabulary")
        counts=_checked_state_counts(item["state_counts"])
        for field in ("explanation","why","market_behavior","fifo_full_book_order_link","evidence","uncertainty"):_nonempty(item[field],f"teach-back {name} {field}")
        rels=item["relationships"]
        if type(rels) is not list:raise ValueError("teach-back relationships must be a list")
        seen=set();checked=[]
        for relation in rels:
            if type(relation) is not dict or set(relation)!={"with","relation","explanation"}:raise ValueError("teach-back relationship fields differ")
            other=relation["with"]
            if other not in COLUMNS or other==name or other in seen:raise ValueError("teach-back relationship target invalid or duplicate")
            if relation["relation"] not in _RELATIONS:raise ValueError("teach-back relationship vocabulary differs")
            _nonempty(relation["explanation"],"relationship explanation");seen.add(other);checked.append(dict(relation))
        normalized.append({**item,"state_counts":counts,"relationships":checked})
    _nonempty(value.get("cycle_summary"),"cycle_summary");_nonempty(value.get("correlation_review"),"correlation_review")
    unresolved=value.get("unresolved_questions")
    if type(unresolved) is not list or any(type(x) is not str or not x.strip() for x in unresolved):raise ValueError("unresolved_questions must be explicit text entries")
    result={"schema":TEACHBACK_SCHEMA,"teacher_message_hash":pre_message["teacher_message_hash"],"components":normalized,
        "cycle_summary":value["cycle_summary"],"correlation_review":value["correlation_review"],
        "relationship_pairs_considered":PAIR_COUNT,"unresolved_questions":list(unresolved),"future_outcome_claimed":False}
    result["teachback_hash"]=evidence_hash(result);return result


def _key_dimensions(key):
    if key.get("schema")!=KEY_SCHEMA:raise ValueError("teacher key required")
    result={x["name"]:x for x in key["dimensions"]}
    if tuple(result)!=tuple(COLUMNS):raise ValueError("teacher key coverage changed")
    return result


def _pair_key(key):
    result={}
    for item in key["relationship_scan"]:result[(item["left"],item["right"])]=item
    if len(result)!=PAIR_COUNT:raise ValueError("teacher key relationship scan incomplete")
    return result


def grade_teachback(key:Mapping[str,Any],teachback:Mapping[str,Any])->dict:
    """Point-by-point factual grade; prose is retained but never fake-scored."""
    dimensions=_key_dimensions(key);items=_components_by_name(teachback.get("components"),label="teach-back");pairs=_pair_key(key)
    component_grades=[];corrections=[];factual_ok=True;relationship_ok=True
    for name in COLUMNS:
        actual=dimensions[name];claimed=items[name]
        counts_ok=claimed["state_counts"]==actual["state_counts"]
        state_ok=claimed["terminal_state"]==actual["terminal_state"]
        direction_ok=claimed["direction"]==actual["first_to_last_present_direction"]
        factual_ok=factual_ok and counts_ok and state_ok and direction_ok
        problems=[]
        if not counts_ok:problems.append(f"state counts are {actual['state_counts']}, not {claimed['state_counts']}")
        if not state_ok:problems.append(f"terminal state is {actual['terminal_state']}, not {claimed['terminal_state']}")
        if not direction_ok:problems.append(f"first-to-last PRESENT direction is {actual['first_to_last_present_direction']}, not {claimed['direction']}")
        if problems:
            cid="component:"+name;corrections.append(cid)
            explanation=("Correction: "+"; ".join(problems)+". Why it matters: "+actual["role"]+" "+actual["behavior_basis"])
        else:
            explanation=(f"Correct: {name} accounts for all target states, ends {actual['terminal_state']}, and has "
                f"{actual['first_to_last_present_direction']} first-to-last PRESENT direction. Why: {actual['role']} {actual['behavior_basis']}")
        relgrades=[]
        for relation in claimed["relationships"]:
            other=relation["with"]
            if relation["relation"]=="HYPOTHESIS":
                relgrades.append({"with":other,"claimed":"HYPOTHESIS","status":"HYPOTHESIS_RETAINED",
                    "explanation":"Retained as a hypothesis, not promoted to correlation or causation."});continue
            left,right=sorted((name,other),key=lambda n:COLUMNS.index(n));actual_relation=pairs[(left,right)]["direction_relation"]
            ok=relation["relation"]==actual_relation;relationship_ok=relationship_ok and ok
            if not ok:
                cid=f"relationship:{left}:{right}";corrections.append(cid)
            relgrades.append({"with":other,"claimed":relation["relation"],"actual":actual_relation,
                "status":"CORRECT" if ok else "CORRECTION",
                "correlation":pairs[(left,right)]["correlation"],
                "explanation":("The directional claim matches the exact causal-window comparison."
                    if ok else f"The exact directional comparison is {actual_relation}, not {relation['relation']}. Pearson, when present, remains descriptive only.")})
        component_grades.append({"name":name,"state_counts_correct":counts_ok,"state_correct":state_ok,"direction_correct":direction_ok,
            "explanation":explanation,"relationship_grades":relgrades})
    corrections=tuple(dict.fromkeys(corrections));mastered=factual_ok and relationship_ok and not corrections
    body={"schema":GRADE_SCHEMA,"request_id":key["request_id"],"cycle_index":key["cycle_index"],"teacher_key_hash":key["teacher_key_hash"],
        "teachback_hash":teachback["teachback_hash"],"coverage_columns":tuple(COLUMNS),"coverage_count":len(COLUMNS),
        "relationship_pairs_checked":PAIR_COUNT,"component_grades":tuple(component_grades),"correction_ids":corrections,
        "factual_components_correct":factual_ok,"directional_relationship_claims_correct":relationship_ok,"mastered":mastered,
        "unresolved_questions_reported":tuple(teachback["unresolved_questions"]),
        "teacher_closing":"I checked every Dipole component and the complete relationship scan. The corrections above identify each factual misunderstanding and explain why. Observed state/value, interpretation, hypothesis, and future outcome remain distinct. A cycle is not teacher-complete until you acknowledge and resolve every correction; later outcome correctness is unavailable here."}
    body["post_grade_hash"]=evidence_hash(body);return body


def validate_acknowledgement(value:Mapping[str,Any],grade:Mapping[str,Any],*,session_id:str)->dict:
    if type(value) is not dict or value.get("schema")!=ACK_SCHEMA:raise ValueError("Frankie classroom correction acknowledgement required")
    if value.get("post_grade_hash")!=grade.get("post_grade_hash"):raise ValueError("acknowledgement belongs to different post-grade")
    if value.get("session_id")!=session_id:raise ValueError("correction must be acknowledged by same Frankie session")
    if value.get("acknowledged") is not True:raise ValueError("Frankie must explicitly acknowledge Dipole correction")
    _nonempty(value.get("what_i_will_change"),"what_i_will_change")
    resolved=value.get("resolved_correction_ids");remaining=value.get("remaining_disagreements")
    if type(resolved) is not list or len(resolved)!=len(set(resolved)) or any(type(x) is not str for x in resolved):raise ValueError("resolved_correction_ids must be unique strings")
    if set(resolved)!=set(grade["correction_ids"]):raise ValueError("every Dipole correction must be explicitly resolved")
    if type(remaining) is not list or any(type(x) is not str or not x.strip() for x in remaining):raise ValueError("remaining_disagreements must be explicit text entries")
    result={"schema":ACK_SCHEMA,"post_grade_hash":grade["post_grade_hash"],"session_id":session_id,"acknowledged":True,
        "resolved_correction_ids":resolved,"remaining_disagreements":remaining,"what_i_will_change":value["what_i_will_change"]}
    result["ack_hash"]=evidence_hash(result);return result


def audit_teacher_complete(*,binding:Mapping[str,Any],key:Mapping[str,Any],pre_message:Mapping[str,Any],teachback:Mapping[str,Any],grade:Mapping[str,Any],acknowledgement:Mapping[str,Any])->dict:
    """Actual completion gate for Greg's invariant classroom contract."""
    if binding.get("coverage_count")!=len(COLUMNS) or binding.get("relationship_pairs_required")!=PAIR_COUNT:raise ValueError("binding lost complete Dipole coverage")
    if key.get("coverage_count")!=len(COLUMNS) or key.get("relationship_pairs_scanned")!=PAIR_COUNT:raise ValueError("teacher key did not cover full Dipole surface")
    if tuple(d["name"] for d in key["dimensions"])!=tuple(COLUMNS):raise ValueError("teacher key missing Dipole dimension")
    for d in key["dimensions"]:
        if sum(d["state_counts"].values())!=len(d["observations"]):raise ValueError("teacher state accounting incomplete")
        nonpresent=sum(d["state_counts"][s] for s in ("MISSING","INVALID","ABLATED"))
        if len(d["nonpresent_explanations"])!=nonpresent:raise ValueError("missing/invalid/ablated observations were silently omitted")
        if key["cycle_index"] and d["change_from_previous"] is None:raise ValueError("prior-cycle Dipole change was not reviewed")
    if pre_message.get("coverage_count")!=len(COLUMNS) or pre_message.get("relationship_pairs_required")!=PAIR_COUNT:raise ValueError("Dipole pre-message incomplete")
    if tuple(c["name"] for c in pre_message["components"])!=tuple(COLUMNS):raise ValueError("Dipole did not address every component")
    if pre_message["mode"]==ClassroomMode.TEACH.value:
        if pre_message.get("relationship_review") is None or len(pre_message["relationship_review"])!=PAIR_COUNT:raise ValueError("TEACH cycle must explicitly teach full relationship scan")
        for component,dimension in zip(pre_message["components"],key["dimensions"]):
            if component.get("observations")!=dimension["observations"] or component.get("state_counts")!=dimension["state_counts"]:
                raise ValueError("TEACH cycle must explicitly teach every retained state/value")
    if teachback.get("relationship_pairs_considered")!=PAIR_COUNT or len(teachback.get("components",()))!=len(COLUMNS):raise ValueError("Frankie did not explain full Dipole surface")
    if grade.get("coverage_count")!=len(COLUMNS) or grade.get("relationship_pairs_checked")!=PAIR_COUNT:raise ValueError("Dipole did not grade full Dipole surface")
    if acknowledgement.get("acknowledged") is not True or set(acknowledgement.get("resolved_correction_ids",()))!=set(grade["correction_ids"]):raise ValueError("Dipole corrections were not fully acknowledged")
    if acknowledgement.get("remaining_disagreements"):
        raise ValueError("cycle cannot be teacher-complete with unresolved Dipole disagreement")
    # prior_cycle_change_reviewed is established by the raise inside the dimension loop above
    # (every cycle after zero must carry change_from_previous); reaching here means it held.
    return {"every_dimension_covered":True,"every_state_value_accounted":True,"prior_cycle_change_reviewed":True,
        "relationship_pairs_reviewed":PAIR_COUNT,"frankie_teachback_complete":True,"dipole_correction_complete":True,
        "unresolved_disagreements":0,"teacher_complete":True}


def complete_cycle(*,binding:Mapping[str,Any],key:Mapping[str,Any],pre_message:Mapping[str,Any],teachback:Mapping[str,Any],grade:Mapping[str,Any],acknowledgement:Mapping[str,Any])->dict:
    audit=audit_teacher_complete(binding=binding,key=key,pre_message=pre_message,teachback=teachback,grade=grade,acknowledgement=acknowledgement)
    body={"schema":COMPLETION_SCHEMA,"request_id":binding["request_id"],"cycle_index":binding["cycle_index"],"mode":binding["mode"],
        "classroom_binding_hash":binding["classroom_binding_hash"],"post_grade_hash":grade["post_grade_hash"],"ack_hash":acknowledgement["ack_hash"],
        "mastered":grade["mastered"],"acknowledged":acknowledgement["acknowledged"],"coverage_count":len(COLUMNS),
        # What a mastered cycle in this mode measures: comprehension of instruction (TEACH/GUIDED)
        # or independent recognition (SOCRATIC/VERIFY). Carried so the curriculum record never
        # reads a TEACH pass as a discovery.
        "learning_measurement":binding.get("learning_measurement"),
        "relationship_pairs_reviewed":PAIR_COUNT,"teacher_complete":audit["teacher_complete"],"audit":audit}
    body["completion_hash"]=evidence_hash(body);return body
