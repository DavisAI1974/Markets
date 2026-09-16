"""Human-readable rendering for the governed Dipole classroom exchange.

The transcript deliberately excludes the audit-only teacher key. It records
exactly what Dipole taught, Frankie's complete observation/pair ledgers, Dipole's
point-by-point correction, and Frankie's same-session acknowledgement.
"""
from __future__ import annotations

from typing import Mapping

from .c15_normalizer import COLUMNS
from .dipole_classroom import ACK_SCHEMA, GRADE_SCHEMA, MESSAGE_SCHEMA, PAIR_COUNT, TEACHBACK_SCHEMA


def _line(value):
    return "null" if value is None else str(value)


def render_pre_message(message: Mapping) -> str:
    if message.get("schema") != MESSAGE_SCHEMA:
        raise ValueError("Dipole classroom pre-message required")
    parts = [f"# Dipole teacher — cycle {message['cycle_index']:02d}","",f"Mode: **{message['mode']}**","",message["teacher_opening"],""]
    prior=message.get("prior_cycle_correction")
    if prior is not None:
        parts += ["## Correction carried from the preceding cycle","",prior["teacher_closing"],""]
        for grade in prior["component_grades"]:parts += [f"- **{grade['name']}** — {grade['explanation']}"]
        if prior["correction_ids"]:
            parts += ["","Corrections that had to be resolved:"]+[f"- `{item}`" for item in prior["correction_ids"]]
        parts.append("")
    components=message["components"]
    if tuple(item["name"] for item in components)!=tuple(COLUMNS):raise ValueError("teacher transcript must cover all governed Dipole dimensions")
    for item in components:
        parts += [f"## {item['name']}","",f"**What Dipole measures:** {item['role']}","",
            f"**FIFO/full-book/order behavior:** {item['behavior_basis']}","",f"**Dipole:** {item['teacher_explanation']}",""]
        if "what_happened" in item:
            parts += [f"**What happened:** {item['what_happened']}","",f"**Why it matters:** {item['why_it_matters']}","",
                f"**Certainty boundary:** {item['observation_interpretation_boundary']}",""]
        if "terminal_state" in item:
            parts += [f"Terminal state: `{item['terminal_state']}`",f"Terminal value: `{_line(item['terminal_value'])}`",
                f"First-to-last PRESENT direction: `{item['first_to_last_present_direction']}`",
                f"Terminal raw reason: `{item['terminal_reason'] or 'none'}`",f"State counts: `{item['state_counts']}`",""]
        observations=item.get("observations")
        if observations is not None:
            parts += ["Every retained Dipole observation for this component:",""]
            for point in observations:
                parts.append(f"- cursor `{point['cursor']}` | ts_recv_ns `{point['ts_recv_ns']}` | state `{point['state']}` | value `{_line(point['value'])}` | reason `{point['raw_reason'] or 'none'}` | target `{point['target_hash']}`")
            parts.append("")
        nonpresent=item.get("nonpresent_explanations")
        if nonpresent:
            parts += ["Explicit non-PRESENT accounting:",""]
            for point in nonpresent:parts.append(f"- cursor `{point['cursor']}` | `{point['state']}` | reason `{point['reason'] or 'none'}`")
            parts.append("")
        previous=item.get("previous_cycle");change=item.get("change_from_previous")
        if previous is not None:
            terminal=previous["terminal"]
            parts += ["Previous-cycle comparison:",f"- prior terminal state `{terminal['state']}`",f"- prior terminal value `{_line(terminal['value'])}`",
                f"- prior first-to-last PRESENT direction `{previous['direction']}`",f"- prior state counts `{previous['state_counts']}`",f"- current change record `{change}`",""]
        parts += [f"**Required Frankie review:** {item['required_review']}",""]
    review=message.get("relationship_review")
    parts += ["## Full intra-Dipole relationship/correlation review","",message["relationship_instruction"],""]
    if review is not None:
        if len(review)!=PAIR_COUNT:raise ValueError("TEACH transcript requires the full 171-pair relationship scan")
        for pair in review:
            corr=pair["correlation"]
            parts.append(f"- `{pair['left']}` ↔ `{pair['right']}` | direction `{pair['direction_relation']}` | PRESENT overlap `{corr['present_overlap']}` | Pearson `{_line(corr['pearson'])}` | reason `{corr['reason'] or 'none'}` | limit `{pair['interpretation_limit']}`")
        parts.append("")
    parts += ["## Frankie's assignment","",message["teachback_instruction"],"",f"Answer wall: `{message['future_wall']}`",""]
    return "\n".join(parts)


def render_teachback(teachback: Mapping) -> str:
    if teachback.get("schema")!=TEACHBACK_SCHEMA:raise ValueError("Dipole classroom teach-back required")
    parts=["# Frankie's Dipole teach-back","",teachback["cycle_summary"],"",f"Relationship pairs considered: `{teachback['relationship_pairs_considered']}`","",
        "## Correlation review","",teachback["correlation_review"],""]
    for item in teachback["components"]:
        parts += [f"## {item['name']}","",f"- state counts: `{item['state_counts']}`",f"- terminal state: `{item['terminal_state']}`",
            f"- direction: `{item['direction']}`",f"- what happened: {item['explanation']}",f"- why: {item['why']}",
            f"- market behavior: {item['market_behavior']}",f"- FIFO/full-book/order link: {item['fifo_full_book_order_link']}",
            f"- evidence: {item['evidence']}",f"- uncertainty: {item['uncertainty']}"]
        if item["relationships"]:
            parts.append("- notable relationships:")
            for relation in item["relationships"]:parts.append(f"  - with `{relation['with']}`: `{relation['relation']}` — {relation['explanation']}")
        else:parts.append("- notable relationships asserted: none")
        parts.append("")
    review=teachback.get("observation_review")
    if review is None or len(review)!=len(COLUMNS):raise ValueError("transcript requires complete Frankie observation review")
    parts += ["# Frankie's explicit all-observation ledger",""]
    for component in review:
        parts += [f"## {component['name']}",""]
        for point in component["observations"]:
            parts.append(f"- cursor `{point['cursor']}` | state `{point['state']}` | value `{_line(point['value'])}` — {point['explanation']}")
        parts.append("")
    scan=teachback.get("relationship_scan")
    if scan is None or len(scan)!=PAIR_COUNT:raise ValueError("transcript requires Frankie's complete 171-pair scan")
    parts += ["# Frankie's explicit 171-pair relationship ledger",""]
    for pair in scan:
        parts.append(f"- `{pair['left']}` ↔ `{pair['right']}` | direction `{pair['direction_relation']}` | correlation interpretation: {pair['correlation_interpretation']} | developing structure: `{_line(pair['developing_structure'])}`")
    parts.append("")
    if teachback["unresolved_questions"]:
        parts += ["## Frankie's unresolved questions",""]+[f"- {q}" for q in teachback["unresolved_questions"]]+[""]
    return "\n".join(parts)


def render_grade(grade: Mapping) -> str:
    if grade.get("schema")!=GRADE_SCHEMA:raise ValueError("Dipole classroom post-grade required")
    parts=["# Dipole post-answer correction","",grade["teacher_closing"],""]
    for item in grade["component_grades"]:
        parts += [f"## {item['name']}","",item["explanation"],""]
        for relation in item["relationship_grades"]:
            corr=relation.get("correlation");corr_text="" if corr is None else f" | correlation evidence `{corr}`"
            parts.append(f"- relationship with `{relation['with']}`: **{relation['status']}** — {relation['explanation']}{corr_text}")
        if item["relationship_grades"]:parts.append("")
    audit=grade.get("exhaustive_audit")
    if type(audit) is not dict:raise ValueError("post-grade requires exhaustive classroom audit")
    parts += ["# Dipole grades Frankie's explicit observation ledger",""]
    for component in audit["observation_grades"]:
        parts += [f"## {component['name']}",f"Expected `{component['expected_count']}` / claimed `{component['claimed_count']}`",""]
        for point in component["grades"]:
            parts.append(f"- cursor `{point['cursor']}` | expected `{point['state']}` value `{_line(point['value'])}` | correct `{point['correct']}` — {point['explanation']}")
        if component["extra_cursors"]:parts.append(f"- unexpected cursors: `{component['extra_cursors']}`")
        parts.append("")
    parts += ["# Dipole grades Frankie's 171-pair ledger",""]
    if len(audit["relationship_grades"])!=PAIR_COUNT:raise ValueError("post-grade relationship audit incomplete")
    for pair in audit["relationship_grades"]:
        parts.append(f"- `{pair['left']}` ↔ `{pair['right']}` | claimed `{pair['claimed']}` | actual `{pair['actual']}` | correct `{pair['correct']}` | correlation `{pair['correlation']}` | developing structure `{_line(pair['developing_structure'])}` — {pair['explanation']}")
    parts.append("")
    if grade["correction_ids"]:
        parts += ["## Corrections Frankie must resolve before teacher completion",""]+[f"- `{item}`" for item in grade["correction_ids"]]+[""]
    else:parts += ["## Corrections","","No factual Dipole correction is required for this teach-back.",""]
    parts += [f"Full factual component check: `{grade['factual_components_correct']}`",
        f"Structured directional relationship check: `{grade['directional_relationship_claims_correct']}`",
        f"Explicit observation coverage proven: `{audit['coverage_proven']}`",
        f"Explicit observations correct on first answer: `{audit['all_observations_correct']}`",
        f"Explicit 171-pair directions correct on first answer: `{audit['all_relationship_directions_correct']}`",
        f"Mastery for taper decision: `{grade['mastered']}`",""]
    return "\n".join(parts)


def render_acknowledgement(ack: Mapping) -> str:
    if ack.get("schema")!=ACK_SCHEMA:raise ValueError("Dipole correction acknowledgement required")
    return "\n".join(["# Frankie acknowledges Dipole's correction","",f"Same session: `{ack['session_id']}`",
        f"Acknowledged: `{ack['acknowledged']}`",f"Resolved correction IDs: `{ack['resolved_correction_ids']}`",
        f"Remaining disagreements: `{ack['remaining_disagreements']}`",f"What I will change: {ack['what_i_will_change']}",""])


def render_transcript(pre_message: Mapping, teachback: Mapping, grade: Mapping, acknowledgement: Mapping) -> str:
    return "\n\n---\n\n".join((render_pre_message(pre_message),render_teachback(teachback),render_grade(grade),render_acknowledgement(acknowledgement)))+"\n"
