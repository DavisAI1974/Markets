"""Human-readable rendering for the governed Dipole classroom records.

The transcript intentionally excludes the audit-only teacher key.  It contains
only what Dipole told Frankie, what Frankie answered, the correction Dipole sent
back, and Frankie's acknowledgement of that correction.
"""
from __future__ import annotations

from typing import Mapping

from .c15_normalizer import COLUMNS
from .dipole_classroom import ACK_SCHEMA, GRADE_SCHEMA, MESSAGE_SCHEMA, TEACHBACK_SCHEMA


def _line(value):
    return "null" if value is None else str(value)


def render_pre_message(message: Mapping) -> str:
    if message.get("schema") != MESSAGE_SCHEMA:
        raise ValueError("Dipole classroom pre-message required")
    parts = [
        f"# Dipole teacher — cycle {message['cycle_index']:02d}",
        "",
        f"Mode: **{message['mode']}**",
        "",
        message["teacher_opening"],
        "",
    ]
    prior = message.get("prior_cycle_correction")
    if prior is not None:
        parts += ["## Correction carried from the preceding cycle", "", prior["teacher_closing"], ""]
        for grade in prior["component_grades"]:
            parts += [f"- **{grade['name']}** — {grade['explanation']}"]
        parts.append("")
    components = message["components"]
    if tuple(item["name"] for item in components) != tuple(COLUMNS):
        raise ValueError("teacher transcript must cover all governed Dipole dimensions")
    for item in components:
        parts += [f"## {item['name']}", "", f"**Role:** {item['role']}", "",
                  f"**Dipole:** {item['teacher_explanation']}", ""]
        if "terminal_state" in item:
            parts += [f"Terminal state: `{item['terminal_state']}`",
                      f"Terminal value: `{_line(item['terminal_value'])}`",
                      f"First-to-last PRESENT direction: `{item['first_to_last_present_direction']}`",
                      f"Terminal raw reason: `{item['terminal_reason'] or 'none'}`", ""]
        observations = item.get("observations")
        if observations is not None:
            parts += ["Every retained Dipole observation for this component:", ""]
            for point in observations:
                parts.append(
                    f"- cursor `{point['cursor']}` | ts_recv_ns `{point['ts_recv_ns']}` | "
                    f"state `{point['state']}` | value `{_line(point['value'])}` | "
                    f"reason `{point['raw_reason'] or 'none'}` | target `{point['target_hash']}`"
                )
            parts.append("")
        previous = item.get("previous_cycle")
        if previous is not None:
            parts += [
                "Previous-cycle comparison:",
                f"- terminal state `{previous['terminal_state']}`",
                f"- terminal value `{_line(previous['terminal_value'])}`",
                f"- first-to-last PRESENT direction `{previous['direction']}`",
                "",
            ]
        parts += [f"**Required Frankie review:** {item['required_review']}", ""]
    parts += ["## Relationship/correlation discipline", "", message["relationship_instruction"], "",
              f"Answer wall: `{message['future_wall']}`", ""]
    return "\n".join(parts)


def render_teachback(teachback: Mapping) -> str:
    if teachback.get("schema") != TEACHBACK_SCHEMA:
        raise ValueError("Dipole classroom teach-back required")
    parts = ["# Frankie's Dipole teach-back", "", teachback["cycle_summary"], "",
             "## Correlation review", "", teachback["correlation_review"], ""]
    for item in teachback["components"]:
        parts += [f"## {item['name']}", "",
                  f"- terminal state: `{item['terminal_state']}`",
                  f"- direction: `{item['direction']}`",
                  f"- explanation: {item['explanation']}",
                  f"- role in this cycle: {item['role_in_cycle']}",
                  f"- evidence: {item['evidence']}",
                  f"- uncertainty: {item['uncertainty']}"]
        if item["relationships"]:
            parts.append("- relationships:")
            for relation in item["relationships"]:
                parts.append(f"  - with `{relation['with']}`: `{relation['relation']}` — {relation['explanation']}")
        else:
            parts.append("- relationships: none asserted")
        parts.append("")
    return "\n".join(parts)


def render_grade(grade: Mapping) -> str:
    if grade.get("schema") != GRADE_SCHEMA:
        raise ValueError("Dipole classroom post-grade required")
    parts = ["# Dipole post-answer correction", "", grade["teacher_closing"], ""]
    for item in grade["component_grades"]:
        parts += [f"## {item['name']}", "", item["explanation"], ""]
        for relation in item["relationship_grades"]:
            parts.append(f"- relationship with `{relation['with']}`: **{relation['status']}** — {relation['explanation']}")
        if item["relationship_grades"]:
            parts.append("")
    parts += [f"Full factual component check: `{grade['factual_components_correct']}`",
              f"Structured directional relationship check: `{grade['directional_relationship_claims_correct']}`",
              f"Mastery for taper decision: `{grade['mastered']}`", ""]
    return "\n".join(parts)


def render_acknowledgement(ack: Mapping) -> str:
    if ack.get("schema") != ACK_SCHEMA:
        raise ValueError("Dipole correction acknowledgement required")
    return "\n".join([
        "# Frankie acknowledges Dipole's correction",
        "",
        f"Same session: `{ack['session_id']}`",
        f"Acknowledged: `{ack['acknowledged']}`",
        f"What I will change: {ack['what_i_will_change']}",
        "",
    ])


def render_transcript(pre_message: Mapping, teachback: Mapping, grade: Mapping, acknowledgement: Mapping) -> str:
    """Exactly the classroom-visible exchange; audit-only teacher key is excluded."""
    return "\n\n---\n\n".join((
        render_pre_message(pre_message),
        render_teachback(teachback),
        render_grade(grade),
        render_acknowledgement(acknowledgement),
    )) + "\n"
