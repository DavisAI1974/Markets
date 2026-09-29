"""The external section of the Dipole classroom answered by Frankie's code (beside frankie_box_classroom_code.py, which
answers the 19 components and 171 pairs and is not changed). No model call (Greg: "Granite has absolutely nothing to do
with classroom anymore"); knowledge/CLASSROOM_RULES_V1.json governs it the same way.

Every answer is computed from the model-visible external section (research/kalshi/frankie_boss/dipole_classroom_external
.py) and returned in the shapes its validator takes: per series the state counts, terminal state and direction the rows
saw, the series' facts (counts, the value in force at the open, first/last, lowest/highest with their times, the
publication times in the day) transcribed from the TEACH evidence, six narratives that each say what they are; every
known value with its publication time; every external pair with its relation, the teacher's coefficient and co-movement
counts quoted as the teacher's; the point review; hypotheses only where a computation surfaces one (a pair whose
first-to-last relation and its step counts point different ways). Counts and per-pair values only, nothing averaged
(rules R04, R05). GUIDED, SOCRATIC and VERIFY withhold the evidence and ask for independent claims the code has no source
for: refused with the reason, never answered from the host key.
"""
from __future__ import annotations

import json

SCHEMA = 'FRANKIE_BOX_CLASSROOM_EXTERNAL_CODE_V1'
AUTHOR = 'Frankie\'s code (computed; no model)'
TEACHBACK_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_TEACHBACK_V1'
NOVEL_SCHEMA = 'FRANKIE_DIPOLE_EXTERNAL_NOVEL_FINDING_V1'


class ModeNotAnswerable(ValueError):
    """The mode asks for independent claims the code has no source for (refused with the reason)."""


def _pre(visible):
    pre = visible['pre_message']
    if pre['mode'] != 'TEACH':
        raise ModeNotAnswerable(f'classroom mode {pre["mode"]} withholds the external evidence and asks for Frankie\'s '
                                'independent claims; Frankie\'s code has no independent source for them yet (not built), and '
                                'it never answers from the host key')
    return pre


def _v(point):
    if point is None:
        return 'none'
    return f'{point["state"]} {point["value"]!r} published at {point["published_ns"]}'


def _component(s):
    f, a = s['facts'], s['alignment']
    table = f'{s["table"]}.{s["column"]}' + (f' where {json.dumps(s["where"], sort_keys=True)}' if s['where'] else '')
    reasons = '; '.join(f'{n} rows {k}' for k, n in a['nonpresent_rows_by_reason'].items()) or 'none'
    segments = len(a['segments'])
    return dict(
        name=s['name'], state_counts=dict(a['state_counts']), terminal_state=a['terminal_state'],
        direction=a['first_to_last_present_direction'], facts={k: f[k] for k in f},
        explanation=(f'{AUTHOR}: {s["name"]} ({table}); {f["values_known"]} values known at the cutoff '
                     f'({f["known_before_open"]} published before the open, {f["published_in_day"]} in the day, '
                     f'{f["not_yet_known_in_table"]} rows of the table not yet known); in force at the open {_v(f["in_force_at_open"])}; '
                     f'first in the day {_v(f["first_in_day"])}, last {_v(f["last_in_day"])}; lowest {_v(f["lowest_in_day"])}, '
                     f'highest {_v(f["highest_in_day"])}; over the {a["rows"]} Dipole rows: states '
                     f'{json.dumps(a["state_counts"], sort_keys=True)} in {segments} runs of one value, terminal '
                     f'{a["terminal_state"]}, first-to-last PRESENT direction {a["first_to_last_present_direction"]}.'),
        why=(f'The day file\'s own description of this series\' table, quoted (not a claim of Frankie\'s): {s["table"]} '
             f'column {s["column"]}. Frankie\'s code adds no interpretation of its own (rule R01).'),
        market_behavior=('Not interpreted by Frankie\'s code: what this value means for the market is interpretation, left '
                         'open (rule R01). What was measured is in the explanation and the value review.'),
        fifo_full_book_order_link=('Not computed by Frankie\'s code: this is an outside series, not a book quantity; its '
                                   'relation to the book is only what the pair counts show (rule R04).'),
        evidence=(f'every one of the {f["values_known"]} known values is listed in external_value_review with its '
                  f'publication time; the {segments} runs name the first and last cursor that saw each value.'),
        uncertainty=(f'Rows without a usable value: {reasons}. Absent from the day file: {s["absent_reason"] or "no"}. '
                     f'Values published after the cutoff are not read ({f["not_yet_known_in_table"]} rows of the table). '
                     'No outcome after the cutoff is known or claimed (rule R02).'))


def _values(s):
    out = []
    for k in s['known_values']:
        why = (f'published at {k["published_ns"]}; ' + (f'value {k["value"]!r}' if k['state'] == 'PRESENT'
                                                          else f'{k["state"]}: {k["reason"]} (raw {k["raw_value"]!r})'))
        out.append(dict(published_ns=k['published_ns'], state=k['state'], value=k['value'], explanation=f'{AUTHOR}: {why}'))
    return dict(name=s['name'], values=out)


def _pair_text(p):
    corr = p['correlation']
    coefficient = (f'Pearson {corr["pearson"]!r} over {corr["present_overlap"]} rows where both are PRESENT'
                   if corr['pearson'] is not None else
                   f'Pearson not reported ({corr["reason"]}; {corr["present_overlap"]} rows where both are PRESENT)')
    m = p['co_movement']
    moves = (f'co-movement over {m["steps_between_consecutive_both_present"]} consecutive both-PRESENT steps: '
             f'{json.dumps(m["steps"], sort_keys=True)}; state pairings {json.dumps(m["state_pairs"], sort_keys=True)}')
    return (f'{AUTHOR}: the teacher\'s relation {p["direction_relation"]}; {coefficient}; {moves}. Descriptive for this '
            'pair and window only; no causation or outcome claimed (rules R01, R02, R05).')


def _disagreement(p):
    steps = p['co_movement']['steps']
    same, opposite = steps['same_direction'], steps['opposite_direction']
    if p['direction_relation'] == 'SAME_DIRECTION' and opposite > same:
        return same, opposite
    if p['direction_relation'] == 'OPPOSITE_DIRECTION' and same > opposite:
        return same, opposite
    return None


def _point(p):
    tables = [dict(name=t['name'], rows_known=t.get('rows_known'), not_yet_known=t.get('not_yet_known')) for t in p['tables']]
    parts = [f'{t["name"]}: {t["rows_known"]} rows known, {t["not_yet_known"]} not yet known' if t['rows_known'] is not None
             else f'{t["name"]}: not in the day file' for t in tables]
    missing = '; '.join(f'{m.get("point")}: {m.get("reason")}' for m in p['missing']) or 'none listed'
    named = ', '.join(p['series']) or 'none (no numeric series in the day file)'
    return dict(point_id=p['point_id'], name=p['name'], series=list(p['series']), tables=tables, missing_count=len(p['missing']),
                review=(f'{AUTHOR}: point {p["point_id"]} {p["name"]}: series {named}; tables {"; ".join(parts)}; '
                        f'missing (day {p.get("day", "")}): {missing}.'))


def answers(visible):
    """All four external ledgers, from the TEACH evidence."""
    pre = _pre(visible)
    series = list(pre['series'])
    review = list(pre['relationship_review'])
    by_relation, reported, not_reported = {}, 0, {}
    for p in review:
        by_relation[p['direction_relation']] = by_relation.get(p['direction_relation'], 0) + 1
        if p['correlation']['pearson'] is not None:
            reported += 1
        else:
            reason = str(p['correlation']['reason'])
            not_reported[reason] = not_reported.get(reason, 0) + 1
    disagreements = [(p, d) for p in review for d in [_disagreement(p)] if d is not None]
    by_direction = {}
    for s in series:
        by_direction.setdefault(s['alignment']['first_to_last_present_direction'], []).append(s['name'])
    questions = [f'{s["name"]}: absent from the day file ({s["absent_reason"]}); nothing to read for it this day.'
                 for s in series if s['absent_reason']]
    questions += [f'{s["name"]}: no value known at any row of the window.' for s in series
                  if not s['absent_reason'] and s['alignment']['state_counts']['PRESENT'] == 0]
    questions += [f'{m.get("point")}: {m.get("reason")} (day file missing list; not assigned to a point)'
                  for m in pre['missing_not_assigned']]
    deferred = pre.get('deferred') or {}
    findings = [dict(schema=NOVEL_SCHEMA, finding_id=f'steps-vs-endpoints:{p["left"]}:{p["right"]}',
                     premise=(f'HYPOTHESIS: {p["left"]} and {p["right"]} end this window {p["direction_relation"]} first-to-last, '
                              f'while their consecutive both-PRESENT steps moved the same way {same} times and the opposite '
                              f'way {opposite} times.'),
                     why_novel=('Computed by Frankie\'s code from the pair\'s co-movement counts; the key grades the '
                                'first-to-last relation only. One window; kept as a hypothesis for later windows (rule R06).'),
                     evidence_refs=[dict(kind='EXTERNAL_RELATIONSHIP', left=p['left'], right=p['right'],
                                         steps=p['co_movement']['steps'])],
                     future_outcome_claimed=False) for p, (same, opposite) in disagreements]
    teachback = dict(
        schema=TEACHBACK_SCHEMA, teacher_message_hash=pre['teacher_message_hash'],
        components=[_component(s) for s in series],
        point_review=[_point(dict(p, day=pre['trading_day'])) for p in pre['points']],
        cycle_summary=(f'{AUTHOR}: {len(series)} series of {len(pre["points"])} points over {pre["rows"]} Dipole rows '
                       f'(cursors {pre["first_cursor"]}..{pre["last_cursor"]}), day file {pre["day_file"]["sha256"]} read at '
                       f'cutoff {pre["cutoff_ns"]}. First-to-last PRESENT direction: '
                       + '; '.join(f'{k} {len(v)}' for k, v in sorted(by_direction.items()))
                       + f'. Series absent from the day file: {len(pre["series_absent"])}. Deferred by Greg: '
                       f'{", ".join(d["name"] for d in deferred.get("points", [])) or "none"}.'),
        correlation_review=(f'{AUTHOR}: {len(review)} external pairs. Relation: {json.dumps(by_relation, sort_keys=True)}. '
                            f'Pearson reported on {reported}; not reported on {len(review) - reported} '
                            f'({json.dumps(not_reported, sort_keys=True)}). {len(disagreements)} pairs whose first-to-last '
                            'relation and step counts point different ways (filed as hypotheses). Per pair and per window, '
                            'never pooled or averaged (rule R05).'),
        unresolved_questions=questions, relationship_pairs_considered=len(review), future_outcome_claimed=False)
    scan = [dict(left=p['left'], right=p['right'], direction_relation=p['direction_relation'],
                 correlation_interpretation=_pair_text(p), developing_structure=None) for p in review]
    return dict(external_teachback=teachback, external_value_review=[_values(s) for s in series],
                external_relationship_scan=scan, external_novel_findings=findings)
