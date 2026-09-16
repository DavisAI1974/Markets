"""Auditable Dipole -> Frankie classroom protocol over governed C15 teacher targets.

The mathematical teacher remains authoritative.  This module does not derive a new
market label, alter a DipoleTarget, run a model, or look beyond the current causal
cutoff.  It turns the exact governed teacher attachment into a classroom record:

    teacher key (complete, audit-only) -> model-visible pre-message ->
    Frankie teach-back -> deterministic factual grade -> Frankie correction ack.

Every cycle covers every governed C15 Dipole dimension.  Coverage never tapers.
Only how much of the answer the pre-message reveals can taper after demonstrated
mastery.  The full target ledger is retained in the teacher key even when a later
Socratic pre-message withholds target values from Frankie.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

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

_HEX = frozenset("0123456789abcdef")
_STATE_NAMES = tuple(state.name for state in TargetState)
_DIRECTIONS = ("RISE", "FALL", "FLAT", "INSUFFICIENT")
_RELATIONS = ("SAME_DIRECTION", "OPPOSITE_DIRECTION", "UNRESOLVED", "HYPOTHESIS")


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

# These descriptions explain the equations already implemented by c15_teacher,
# c15_teacher_r3 and c15_dstate.  They are curriculum text, not new features.
ROLE_DEFINITIONS = {
    "far_front_age_log": (
        "Age of the front resting order in the selected far-side top-three cohort. "
        "It teaches whether the queue front is newly formed or has persisted."
    ),
    "far_queue_age_p90_log": (
        "Age threshold that accounts for 90 percent of the selected far-side top-three "
        "cohort size. It teaches the age structure behind the visible queue, not only its front."
    ),
    "far_size_hhi": (
        "Herfindahl concentration of size across the selected far-side top-three cohort. "
        "It teaches whether displayed size is diffuse or concentrated in fewer resting orders."
    ),
    "far_replenish_log1p_64": (
        "Short-horizon (64-group) far-side top-three net addition versus removal geometry, "
        "computed from the teacher's reconciled order dynamics."
    ),
    "far_replenish_log1p_1024": (
        "Long-horizon (1024-group) far-side top-three net addition versus removal geometry, "
        "the long-run companion to the 64-group replenishment view."
    ),
    "far_priority_loss_rate_64": (
        "Share of short-horizon far-side top-three modifications that lose queue priority. "
        "It teaches whether apparent liquidity is preserving or surrendering FIFO position."
    ),
    "far_priority_loss_rate_1024": (
        "Share of long-horizon far-side top-three modifications that lose queue priority, "
        "providing the 1024-group persistence view of FIFO deterioration."
    ),
    "far_absorption_share_64": (
        "Short-horizon share of reconciled far-side removals attributable to fills. "
        "It teaches absorption rather than treating all disappearing size as equivalent."
    ),
    "far_absorption_share_1024": (
        "Long-horizon share of reconciled far-side removals attributable to fills, "
        "the 1024-group persistence view of absorption."
    ),
    "far_identity_survival_64": (
        "Fraction of the original short-horizon far-side top-three order cohort whose "
        "identities remain alive after the 64-group horizon."
    ),
    "far_identity_survival_1024": (
        "Fraction of the original long-horizon far-side top-three order cohort whose "
        "identities remain alive after the 1024-group horizon."
    ),
    "far_size_retention_64": (
        "Fraction of the original short-horizon cohort quantity still retained by those "
        "same orders, separating identity survival from retained size."
    ),
    "far_size_retention_1024": (
        "Fraction of the original long-horizon cohort quantity still retained by those "
        "same orders over 1024 groups."
    ),
    "unresolved_age_groups_log": (
        "D-chain age of the current unresolved far-side extreme in instrument groups. "
        "It teaches how long the present geometry has persisted without a new extension."
    ),
    "extension_count_log": (
        "D-chain count of completed far-side extensions in the current chain. "
        "It teaches how many pullback-and-extension steps have accumulated."
    ),
    "step_ratio_log": (
        "Log ratio of the latest completed extension magnitude to the previous completed "
        "extension magnitude; unavailable until two valid extensions exist."
    ),
    "pullback_ticks_last_log": (
        "Log pullback depth, in ticks, associated with the most recently completed far-side extension."
    ),
    "step_duration_groups_log": (
        "Log duration, in instrument groups, of the most recently completed far-side step."
    ),
    "pullback_ticks_prev_log": (
        "Log pullback depth, in ticks, associated with the previous completed far-side extension."
    ),
}

if tuple(ROLE_DEFINITIONS) != tuple(COLUMNS):
    raise RuntimeError("Dipole classroom role definitions must cover C15 columns exactly and in order")


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


def _tensor_scalar(tensor, name: str):
    if tuple(tensor.shape) != (1, 1):
        raise ValueError(f"{name} must have exactly one causal timestamp")
    return tensor.detach().cpu().item()


def _target_row(target: DipoleTarget, raw_row: Sequence[Mapping[str, Any]], receipt: Mapping[str, Any], cursor: int) -> dict:
    if not isinstance(target, DipoleTarget):
        raise ValueError("governed DipoleTarget required")
    target.check_integrity()
    if tuple(target.spec.target_names) != tuple(COLUMNS):
        raise ValueError("teacher target columns differ from governed C15 classroom surface")
    if tuple(target.values.shape) != (1, 1, len(COLUMNS)) or tuple(target.states.shape) != target.values.shape:
        raise ValueError("one governed 19-column target row required per context cursor")
    if len(raw_row) != len(COLUMNS):
        raise ValueError("raw teacher row must retain every governed column")
    if receipt.get("cursor") != cursor or receipt.get("target_hash") != target.target_hash:
        raise ValueError("teacher step receipt differs from target/cursor")
    if receipt.get("source_prefix_hash") != target.source_prefix_hash:
        raise ValueError("teacher step receipt source prefix differs from target")
    values = target.values.detach().cpu()[0, 0].tolist()
    states = target.states.detach().cpu()[0, 0].tolist()
    ts_recv_ns = int(_tensor_scalar(target.ts_recv_ns, "target ts_recv_ns"))
    components = []
    for index, name in enumerate(COLUMNS):
        raw = raw_row[index]
        state = _state_name(states[index])
        raw_state = _state_name(raw.get("state"))
        if raw_state != state and target.spec.target_units[index] != "z_score":
            raise ValueError("identity-normalized target state differs from raw teacher state")
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


def snapshot_teacher_attachment(teacher: Mapping[str, Any], *, request_id: str, cycle_index: int,
                                source_hash: str, as_of: int, through_cursor: int) -> dict:
    """Losslessly snapshot every model-context Dipole target row for this cycle."""
    _nonempty(request_id, "request_id")
    if type(cycle_index) is not int or not 0 <= cycle_index < 19:
        raise ValueError("cycle_index must be 0..18")
    _hex(source_hash, "source_hash")
    if type(as_of) is not int or as_of <= 0 or type(through_cursor) is not int or through_cursor < 0:
        raise ValueError("positive causal cutoff and nonnegative cursor required")
    if type(teacher) is not dict:
        raise ValueError("governed teacher attachment required")
    required = {"targets", "raw", "processed_records", "context_cursors", "step_receipts",
                "attachment_hash", "candidate_digest"}
    if not required.issubset(teacher):
        raise ValueError("teacher attachment missing governed fields")
    targets = tuple(teacher["targets"])
    raw_rows = tuple(teacher["raw"])
    cursors = tuple(teacher["context_cursors"])
    receipts = tuple(teacher["step_receipts"])
    if not targets or not (len(targets) == len(raw_rows) == len(cursors) == len(receipts)):
        raise ValueError("teacher target/raw/cursor/receipt cardinality differs")
    if tuple(sorted(set(cursors))) != cursors or any(type(c) is not int or not 0 <= c <= through_cursor for c in cursors):
        raise ValueError("teacher context cursors must be ordered unique members of causal prefix")
    rows = tuple(_target_row(t, r, s, c) for t, r, s, c in zip(targets, raw_rows, receipts, cursors))
    if rows[-1]["as_of_ts_recv_ns"] > as_of or any(row["ts_recv_ns"] > as_of for row in rows):
        raise ValueError("classroom target exceeds causal cutoff")
    if any(row["source_manifest_hash"] != rows[0]["source_manifest_hash"] for row in rows):
        raise ValueError("teacher targets cross source manifests")
    body = {
        "schema": SOURCE_SCHEMA,
        "request_id": request_id,
        "cycle_index": cycle_index,
        "source_hash": source_hash,
        "as_of": as_of,
        "through_cursor": through_cursor,
        "teacher_attachment_hash": _hex(teacher["attachment_hash"], "teacher attachment hash"),
        "candidate_digest": _hex(teacher["candidate_digest"], "candidate digest"),
        "processed_records": teacher["processed_records"],
        "context_cursors": cursors,
        "rows": rows,
        "coverage_columns": tuple(COLUMNS),
        "coverage_count": len(COLUMNS),
    }
    body["source_snapshot_hash"] = evidence_hash(body)
    return body


def _dimension_ledger(snapshot: Mapping[str, Any], index: int) -> tuple[dict, ...]:
    name = COLUMNS[index]
    result = []
    for row in snapshot["rows"]:
        component = row["components"][index]
        if component["name"] != name:
            raise ValueError("teacher row column order changed")
        result.append({
            "cursor": row["cursor"],
            "ts_recv_ns": row["ts_recv_ns"],
            "target_hash": row["target_hash"],
            "state": component["state"],
            "value": component["value"],
            "raw_reason": component["raw_reason"],
        })
    return tuple(result)


def _first_last_present(ledger: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    present = [point for point in ledger if point["state"] == TargetState.PRESENT.name]
    return (present[0], present[-1]) if present else (None, None)


def _direction(ledger: Sequence[Mapping[str, Any]]) -> str:
    first, last = _first_last_present(ledger)
    if first is None or last is None or first["cursor"] == last["cursor"]:
        return "INSUFFICIENT"
    if last["value"] > first["value"]:
        return "RISE"
    if last["value"] < first["value"]:
        return "FALL"
    return "FLAT"


def _relation(left: str, right: str) -> str:
    if left in ("RISE", "FALL") and right in ("RISE", "FALL"):
        return "SAME_DIRECTION" if left == right else "OPPOSITE_DIRECTION"
    return "UNRESOLVED"


def build_teacher_key(snapshot: Mapping[str, Any], previous_snapshot: Mapping[str, Any] | None = None) -> dict:
    """Complete audit key.  This is never required to be model-visible in later modes."""
    if snapshot.get("schema") != SOURCE_SCHEMA or snapshot.get("coverage_columns") != tuple(COLUMNS):
        raise ValueError("complete Dipole classroom source snapshot required")
    if evidence_hash({k: v for k, v in snapshot.items() if k != "source_snapshot_hash"}) != snapshot.get("source_snapshot_hash"):
        raise ValueError("classroom source snapshot changed")
    previous_by_name = {}
    if previous_snapshot is not None:
        if previous_snapshot.get("schema") != SOURCE_SCHEMA:
            raise ValueError("previous classroom source snapshot schema differs")
        if previous_snapshot["cycle_index"] >= snapshot["cycle_index"]:
            raise ValueError("previous classroom snapshot must precede current cycle")
        for index, name in enumerate(COLUMNS):
            ledger = _dimension_ledger(previous_snapshot, index)
            first, last = _first_last_present(ledger)
            previous_by_name[name] = {
                "terminal_state": ledger[-1]["state"],
                "terminal_value": ledger[-1]["value"],
                "first_present": first,
                "last_present": last,
                "direction": _direction(ledger),
            }
    dimensions = []
    direction_by_name = {}
    for index, name in enumerate(COLUMNS):
        ledger = _dimension_ledger(snapshot, index)
        first, last = _first_last_present(ledger)
        direction = _direction(ledger)
        direction_by_name[name] = direction
        dimensions.append({
            "name": name,
            "role": ROLE_DEFINITIONS[name],
            "unit": snapshot["rows"][0]["components"][index]["unit"],
            "observations": ledger,
            "terminal_state": ledger[-1]["state"],
            "terminal_value": ledger[-1]["value"],
            "terminal_reason": ledger[-1]["raw_reason"],
            "first_present": first,
            "last_present": last,
            "first_to_last_present_direction": direction,
            "previous_cycle": previous_by_name.get(name),
        })
    relationships = []
    for left_index, left in enumerate(COLUMNS):
        for right in COLUMNS[left_index + 1:]:
            relationships.append({
                "left": left,
                "right": right,
                "relation": _relation(direction_by_name[left], direction_by_name[right]),
                "basis": "FIRST_TO_LAST_PRESENT_DIRECTION_ONLY_NOT_STATISTICAL_CORRELATION",
            })
    body = {
        "schema": KEY_SCHEMA,
        "request_id": snapshot["request_id"],
        "cycle_index": snapshot["cycle_index"],
        "source_snapshot_hash": snapshot["source_snapshot_hash"],
        "teacher_attachment_hash": snapshot["teacher_attachment_hash"],
        "coverage_columns": tuple(COLUMNS),
        "coverage_count": len(COLUMNS),
        "dimensions": tuple(dimensions),
        "directional_relationship_scan": tuple(relationships),
        "relationship_pairs_scanned": len(relationships),
        "causality_rule": "NO_EVIDENCE_AFTER_CURRENT_AS_OF; FUTURE_OUTCOME_CORRECTNESS_IS_NOT_GRADED_HERE",
    }
    body["teacher_key_hash"] = evidence_hash(body)
    return body


def select_mode(history: Sequence[Mapping[str, Any]]) -> str:
    """Back away only after two consecutive mastered+acknowledged cycles at a mode."""
    if not history:
        return ClassroomMode.TEACH.value
    for item in history:
        if item.get("schema") != COMPLETION_SCHEMA or item.get("mode") not in _MODES:
            raise ValueError("classroom history contains an invalid completion")
    current = history[-1]["mode"]
    same_mode_tail = []
    for item in reversed(history):
        if item["mode"] != current:
            break
        same_mode_tail.append(item)
    if len(same_mode_tail) >= 2 and all(item.get("mastered") is True and item.get("acknowledged") is True
                                        for item in same_mode_tail[:2]):
        return _NEXT_MODE[current]
    return current


def _teacher_component(dimension: Mapping[str, Any], mode: str) -> dict:
    base = {
        "name": dimension["name"],
        "role": dimension["role"],
        "unit": dimension["unit"],
        "required_review": (
            "Explain this dimension's state, movement, role in this cycle, relationships to other "
            "Dipole dimensions, supporting evidence, and uncertainty. Do not infer a future outcome."
        ),
    }
    if mode == ClassroomMode.TEACH.value:
        return {**base,
            "teacher_explanation": (
                "I am teaching this component explicitly. Review every retained observation below, "
                "then explain back what changed and why this geometry matters."
            ),
            "observations": dimension["observations"],
            "terminal_state": dimension["terminal_state"],
            "terminal_value": dimension["terminal_value"],
            "terminal_reason": dimension["terminal_reason"],
            "first_to_last_present_direction": dimension["first_to_last_present_direction"],
            "previous_cycle": dimension["previous_cycle"],
        }
    if mode == ClassroomMode.GUIDED.value:
        return {**base,
            "teacher_explanation": (
                "I am still supplying the exact Dipole evidence, but you must perform more of the "
                "interpretation. Compare the observations and tell me the relationship you see."
            ),
            "observations": dimension["observations"],
            "previous_cycle": dimension["previous_cycle"],
        }
    return {**base,
        "teacher_explanation": (
            "You now lead. Derive this component from the causal evidence you were given and tell me "
            "what you saw. I am withholding my target state/value/direction until after your answer."
        )}


def build_pre_message(key: Mapping[str, Any], *, mode: str, prior_grade: Mapping[str, Any] | None = None) -> dict:
    if key.get("schema") != KEY_SCHEMA or key.get("coverage_columns") != tuple(COLUMNS):
        raise ValueError("complete classroom teacher key required")
    if mode not in _MODES:
        raise ValueError("known classroom mode required")
    if prior_grade is not None and prior_grade.get("schema") != GRADE_SCHEMA:
        raise ValueError("prior correction must be a classroom post-grade")
    components = tuple(_teacher_component(dimension, mode) for dimension in key["dimensions"])
    if tuple(item["name"] for item in components) != tuple(COLUMNS):
        raise ValueError("pre-message did not cover every Dipole component")
    body = {
        "schema": MESSAGE_SCHEMA,
        "request_id": key["request_id"],
        "cycle_index": key["cycle_index"],
        "mode": mode,
        "teacher_key_hash": key["teacher_key_hash"],
        "coverage_columns": tuple(COLUMNS),
        "coverage_count": len(COLUMNS),
        "prior_cycle_correction": prior_grade,
        "teacher_opening": (
            "We will cover every Dipole component in this cycle. Nothing Dipole-related may be silently "
            "skipped. I will distinguish what the current causal evidence shows from hypotheses and from "
            "future outcomes that are not available yet. Your teach-back must cover all 19 components."
        ),
        "components": components,
        "relationship_instruction": (
            "Review relationships across the full Dipole surface. A same/opposite first-to-last direction "
            "is only a directional relationship, not a statistical correlation or proof of causation. "
            "If a relationship is only a hypothesis, label it HYPOTHESIS."
        ),
        "future_wall": "DO_NOT_CLAIM_OR_USE_ANY_OUTCOME_NOT_CAUSALLY_AVAILABLE_AT_THIS_CUTOFF",
    }
    body["teacher_message_hash"] = evidence_hash(body)
    return body


def prepare_cycle(teacher: Mapping[str, Any], *, request_id: str, cycle_index: int, source_hash: str,
                  as_of: int, through_cursor: int, previous_snapshot: Mapping[str, Any] | None = None,
                  history: Sequence[Mapping[str, Any]] = (), prior_grade: Mapping[str, Any] | None = None) -> dict:
    snapshot = snapshot_teacher_attachment(teacher, request_id=request_id, cycle_index=cycle_index,
        source_hash=source_hash, as_of=as_of, through_cursor=through_cursor)
    key = build_teacher_key(snapshot, previous_snapshot)
    mode = select_mode(history)
    message = build_pre_message(key, mode=mode, prior_grade=prior_grade)
    binding = {
        "request_id": request_id,
        "cycle_index": cycle_index,
        "source_hash": source_hash,
        "as_of": as_of,
        "through_cursor": through_cursor,
        "source_snapshot_hash": snapshot["source_snapshot_hash"],
        "teacher_key_hash": key["teacher_key_hash"],
        "teacher_message_hash": message["teacher_message_hash"],
        "teacher_attachment_hash": snapshot["teacher_attachment_hash"],
        "mode": mode,
        "coverage_count": len(COLUMNS),
    }
    binding["classroom_binding_hash"] = evidence_hash(binding)
    return {"source": snapshot, "teacher_key": key, "pre_message": message, "binding": binding}


def _components_by_name(items: Any, *, label: str) -> dict[str, Mapping[str, Any]]:
    if type(items) is not list or len(items) != len(COLUMNS):
        raise ValueError(f"{label} must contain exactly {len(COLUMNS)} Dipole components")
    result = {}
    for item in items:
        if type(item) is not dict:
            raise ValueError(f"{label} components must be objects")
        name = item.get("name")
        if name not in COLUMNS or name in result:
            raise ValueError(f"{label} contains unknown or duplicate Dipole component")
        result[name] = item
    if tuple(result) != tuple(COLUMNS):
        raise ValueError(f"{label} must preserve governed Dipole column order")
    return result


def validate_teachback(value: Mapping[str, Any], pre_message: Mapping[str, Any]) -> dict:
    """Require Frankie to explicitly account for all 19 components before grading."""
    if type(value) is not dict or value.get("schema") != TEACHBACK_SCHEMA:
        raise ValueError("structured Dipole classroom teach-back required")
    if value.get("teacher_message_hash") != pre_message.get("teacher_message_hash"):
        raise ValueError("teach-back belongs to a different teacher message")
    if value.get("future_outcome_claimed") is not False:
        raise ValueError("same-cycle teach-back may not claim a future outcome")
    components = _components_by_name(value.get("components"), label="teach-back")
    normalized = []
    for name in COLUMNS:
        item = components[name]
        allowed = {"name", "terminal_state", "direction", "explanation", "role_in_cycle",
                   "evidence", "uncertainty", "relationships"}
        if set(item) != allowed:
            raise ValueError("teach-back component fields differ from classroom contract")
        if item["terminal_state"] not in _STATE_NAMES or item["direction"] not in _DIRECTIONS:
            raise ValueError("teach-back state/direction outside governed vocabulary")
        for field in ("explanation", "role_in_cycle", "evidence", "uncertainty"):
            _nonempty(item[field], f"teach-back {name} {field}")
        relationships = item["relationships"]
        if type(relationships) is not list:
            raise ValueError("teach-back relationships must be a list")
        seen = set()
        checked = []
        for relation in relationships:
            if type(relation) is not dict or set(relation) != {"with", "relation", "explanation"}:
                raise ValueError("teach-back relationship fields differ")
            other = relation["with"]
            if other not in COLUMNS or other == name or other in seen:
                raise ValueError("teach-back relationship target is invalid or duplicate")
            if relation["relation"] not in _RELATIONS:
                raise ValueError("teach-back relationship vocabulary differs")
            _nonempty(relation["explanation"], "relationship explanation")
            seen.add(other); checked.append(dict(relation))
        normalized.append({**item, "relationships": checked})
    _nonempty(value.get("cycle_summary"), "cycle_summary")
    _nonempty(value.get("correlation_review"), "correlation_review")
    result = {
        "schema": TEACHBACK_SCHEMA,
        "teacher_message_hash": pre_message["teacher_message_hash"],
        "components": normalized,
        "cycle_summary": value["cycle_summary"],
        "correlation_review": value["correlation_review"],
        "future_outcome_claimed": False,
    }
    result["teachback_hash"] = evidence_hash(result)
    return result


def _key_dimensions(key: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if key.get("schema") != KEY_SCHEMA:
        raise ValueError("teacher key required")
    result = {item["name"]: item for item in key["dimensions"]}
    if tuple(result) != tuple(COLUMNS):
        raise ValueError("teacher key coverage changed")
    return result


def _pair_key(key: Mapping[str, Any]) -> dict[tuple[str, str], str]:
    result = {}
    for item in key["directional_relationship_scan"]:
        result[(item["left"], item["right"])] = item["relation"]
    expected = len(COLUMNS) * (len(COLUMNS) - 1) // 2
    if len(result) != expected:
        raise ValueError("teacher key relationship scan is incomplete")
    return result


def grade_teachback(key: Mapping[str, Any], teachback: Mapping[str, Any]) -> dict:
    """Grade factual state/direction and structured directional claims only.

    Free-text interpretation is retained verbatim for audit; this deterministic
    grader does not pretend to know whether prose is insightful.  It explains
    factual corrections from the governed target rows and labels hypotheses as
    hypotheses rather than silently promoting them to correlations.
    """
    dimensions = _key_dimensions(key)
    items = _components_by_name(teachback.get("components"), label="teach-back")
    pairs = _pair_key(key)
    component_grades = []
    factual_ok = True
    relationship_ok = True
    for name in COLUMNS:
        actual = dimensions[name]
        claimed = items[name]
        state_ok = claimed["terminal_state"] == actual["terminal_state"]
        direction_ok = claimed["direction"] == actual["first_to_last_present_direction"]
        factual_ok = factual_ok and state_ok and direction_ok
        first, last = actual["first_present"], actual["last_present"]
        if state_ok and direction_ok:
            explanation = (
                f"Correct: {name} ended {actual['terminal_state']} and its first-to-last PRESENT "
                f"direction was {actual['first_to_last_present_direction']}."
            )
        else:
            ends = ("no two PRESENT observations were available"
                    if first is None or last is None or first["cursor"] == last["cursor"] else
                    f"first PRESENT {first['value']} at cursor {first['cursor']} and last PRESENT "
                    f"{last['value']} at cursor {last['cursor']}")
            explanation = (
                f"Correction: {name} actually ended {actual['terminal_state']} and its first-to-last "
                f"PRESENT direction was {actual['first_to_last_present_direction']}; {ends}. "
                f"Its classroom role is: {actual['role']}"
            )
        relation_grades = []
        for relation in claimed["relationships"]:
            other = relation["with"]
            if relation["relation"] == "HYPOTHESIS":
                relation_grades.append({"with": other, "claimed": "HYPOTHESIS", "status": "HYPOTHESIS_RETAINED",
                    "explanation": "Retained as a hypothesis; the classroom does not promote it to a factual correlation."})
                continue
            left, right = sorted((name, other), key=lambda n: COLUMNS.index(n))
            actual_relation = pairs[(left, right)]
            ok = relation["relation"] == actual_relation
            relationship_ok = relationship_ok and ok
            relation_grades.append({"with": other, "claimed": relation["relation"], "actual": actual_relation,
                "status": "CORRECT" if ok else "CORRECTION",
                "explanation": ("The claim matches the exact first-to-last PRESENT direction comparison."
                    if ok else f"The exact directional comparison is {actual_relation}, not {relation['relation']}. "
                    "This is still not a statistical correlation or causation claim.")})
        component_grades.append({
            "name": name,
            "state_correct": state_ok,
            "direction_correct": direction_ok,
            "explanation": explanation,
            "relationship_grades": relation_grades,
        })
    mastered = factual_ok and relationship_ok
    body = {
        "schema": GRADE_SCHEMA,
        "request_id": key["request_id"],
        "cycle_index": key["cycle_index"],
        "teacher_key_hash": key["teacher_key_hash"],
        "teachback_hash": teachback["teachback_hash"],
        "coverage_columns": tuple(COLUMNS),
        "coverage_count": len(COLUMNS),
        "component_grades": tuple(component_grades),
        "factual_components_correct": factual_ok,
        "directional_relationship_claims_correct": relationship_ok,
        "mastered": mastered,
        "teacher_closing": (
            "I checked every Dipole component. The corrections above explain what you got right and "
            "what you got wrong from the current causal target only. Future outcome correctness remains "
            "unknown here and must be reviewed later, after it becomes causally available."
        ),
    }
    body["post_grade_hash"] = evidence_hash(body)
    return body


def validate_acknowledgement(value: Mapping[str, Any], grade: Mapping[str, Any], *, session_id: str) -> dict:
    if type(value) is not dict or value.get("schema") != ACK_SCHEMA:
        raise ValueError("Frankie classroom correction acknowledgement required")
    if value.get("post_grade_hash") != grade.get("post_grade_hash"):
        raise ValueError("correction acknowledgement belongs to a different post-grade")
    if value.get("session_id") != session_id:
        raise ValueError("correction must be acknowledged by the same Frankie session")
    if value.get("acknowledged") is not True:
        raise ValueError("Frankie must explicitly acknowledge the Dipole correction")
    _nonempty(value.get("what_i_will_change"), "what_i_will_change")
    result = {
        "schema": ACK_SCHEMA,
        "post_grade_hash": grade["post_grade_hash"],
        "session_id": session_id,
        "acknowledged": True,
        "what_i_will_change": value["what_i_will_change"],
    }
    result["ack_hash"] = evidence_hash(result)
    return result


def complete_cycle(*, binding: Mapping[str, Any], grade: Mapping[str, Any], acknowledgement: Mapping[str, Any]) -> dict:
    if binding.get("coverage_count") != len(COLUMNS) or grade.get("coverage_count") != len(COLUMNS):
        raise ValueError("classroom completion requires full Dipole coverage")
    if acknowledgement.get("post_grade_hash") != grade.get("post_grade_hash"):
        raise ValueError("classroom acknowledgement/grade binding differs")
    body = {
        "schema": COMPLETION_SCHEMA,
        "request_id": binding["request_id"],
        "cycle_index": binding["cycle_index"],
        "mode": binding["mode"],
        "classroom_binding_hash": binding["classroom_binding_hash"],
        "post_grade_hash": grade["post_grade_hash"],
        "ack_hash": acknowledgement["ack_hash"],
        "mastered": grade["mastered"],
        "acknowledged": acknowledgement["acknowledged"],
        "coverage_count": len(COLUMNS),
    }
    body["completion_hash"] = evidence_hash(body)
    return body
