"""The external section of the Dipole classroom answered by Frankie's code (beside frankie_box_classroom_code.py, which
answers the 19 components and 171 pairs). No model call (Greg: "Granite has absolutely nothing to do with classroom
anymore"); knowledge/CLASSROOM_RULES_V3.json governs it the same way.

Every answer is computed from the model-visible external section (research/kalshi/frankie_boss/dipole_classroom_external
.py) and returned in the shapes its validator takes: per series the state counts, terminal state and direction the rows
saw, the series' facts (counts, the value in force at the open, first/last, lowest/highest with their times, the
publication times in the day), six narratives that each say what they are; every known value with its publication time;
every external pair with its relation, coefficient and co-movement counts; the point review; hypotheses only where a
computation surfaces one (a pair whose first-to-last relation and its step counts point different ways). Counts and
per-pair values only, nothing averaged (rules R04, R05).

TEACH: the teacher shows all of it; the code transcribes. GUIDED (Greg, 2026-10-06: the lawful TEACH -> GUIDED
progression): the teacher shows every known value and, per series, the runs of rows that saw each value (the segments)
and the row count, but withholds the facts, the per-row alignment summary, the pair review and the points' tables. The
code COMPUTES what that evidence determines with the external module's own functions (_facts, _direction, _pair, so the
same Pearson/co-movement/relation mathematics as the key), per series and per pair, never from the key. A series x
Dipole pair needs the Dipole observations the V1 classroom shows in GUIDED: pass them as `dipole_visible`; without them
those pairs are answered UNRESOLVED and listed as not measurable. What the GUIDED evidence cannot determine (a table's
total rows known or not yet known) is answered as unknown and listed, never filled in (R04).
SOCRATIC and VERIFY withhold the evidence itself: refused with the reason, never answered from the host key.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_CLASSROOM_EXTERNAL_CODE_V1'
AUTHOR = 'Frankie\'s code (computed; no model)'
TEACHBACK_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_TEACHBACK_V1'
NOVEL_SCHEMA = 'FRANKIE_DIPOLE_EXTERNAL_NOVEL_FINDING_V1'
MODES_ANSWERED = ('TEACH', 'GUIDED')
NOT_SUPPLIED = 'DIPOLE_OBSERVATIONS_NOT_SUPPLIED_TO_THIS_SEAT'


class ModeNotAnswerable(ValueError):
    """The mode asks for independent claims the code has no source for (refused with the reason)."""


def _pre(visible):
    pre = visible['pre_message']
    if pre['mode'] not in MODES_ANSWERED:
        raise ModeNotAnswerable(f'classroom mode {pre["mode"]} withholds the external evidence and asks for Frankie\'s '
                                'independent claims; Frankie\'s code has no independent source for them yet (not built), and '
                                'it never answers from the host key')
    return pre


def _external_math():
    """dipole_classroom_external from this checkout (its own _facts / _direction / _pair: the key's mathematics), loaded
    after frankie_box_classroom.validators() registered the torch-free package namespace."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import frankie_box_classroom as C
    C.validators()
    return importlib.import_module('research.kalshi.frankie_boss.dipole_classroom_external')


def _v(point):
    if point is None:
        return 'none'
    return f'{point["state"]} {point["value"]!r} published at {point["published_ns"]}'


def _component(s, basis):
    f, a = s['facts'], s['alignment']
    table = f'{s["table"]}.{s["column"]}' + (f' where {json.dumps(s["where"], sort_keys=True)}' if s['where'] else '')
    reasons = '; '.join(f'{n} rows {k}' for k, n in a['nonpresent_rows_by_reason'].items()) or 'none'
    segments = len(a['segments'])
    not_yet = ('unknown in GUIDED (the table\'s not-yet-known count is withheld; listed, not filled in)'
               if f['not_yet_known_in_table'] is None else f'{f["not_yet_known_in_table"]} rows of the table not yet known')
    return dict(
        name=s['name'], state_counts=dict(a['state_counts']), terminal_state=a['terminal_state'],
        direction=a['first_to_last_present_direction'], facts={k: f[k] for k in f},
        explanation=(f'{AUTHOR}: {s["name"]} ({table}); {f["values_known"]} values known at the cutoff '
                     f'({f["known_before_open"]} published before the open, {f["published_in_day"]} in the day, '
                     f'{not_yet}); in force at the open {_v(f["in_force_at_open"])}; '
                     f'first in the day {_v(f["first_in_day"])}, last {_v(f["last_in_day"])}; lowest {_v(f["lowest_in_day"])}, '
                     f'highest {_v(f["highest_in_day"])}; over the {a["rows"]} Dipole rows: states '
                     f'{json.dumps(a["state_counts"], sort_keys=True)} in {segments} runs of one value, terminal '
                     f'{a["terminal_state"]}, first-to-last PRESENT direction {a["first_to_last_present_direction"]} ({basis}).'),
        why=(f'The day file\'s own description of this series\' table, quoted (not a claim of Frankie\'s): {s["table"]} '
             f'column {s["column"]}. Frankie\'s code adds no interpretation of its own (rule R01).'),
        market_behavior=('Not interpreted by Frankie\'s code: what this value means for the market is interpretation, left '
                         'open (rule R01). What was measured is in the explanation and the value review.'),
        fifo_full_book_order_link=('Not computed by Frankie\'s code: this is an outside series, not a book quantity; its '
                                   'relation to the book is only what the pair counts show (rule R04).'),
        evidence=(f'every one of the {f["values_known"]} known values is listed in external_value_review with its '
                  f'publication time; the {segments} runs name the first and last cursor that saw each value.'),
        uncertainty=(f'Rows without a usable value: {reasons}. Absent from the day file: {s["absent_reason"] or "no"}. '
                     f'Values published after the cutoff are not read ({not_yet}). '
                     'No outcome after the cutoff is known or claimed (rule R02).'))


def _values(s):
    out = []
    for k in s['known_values']:
        why = (f'published at {k["published_ns"]}; ' + (f'value {k["value"]!r}' if k['state'] == 'PRESENT'
                                                          else f'{k["state"]}: {k["reason"]} (raw {k["raw_value"]!r})'))
        out.append(dict(published_ns=k['published_ns'], state=k['state'], value=k['value'], explanation=f'{AUTHOR}: {why}'))
    return dict(name=s['name'], values=out)


def _pair_text(p, basis):
    corr = p['correlation']
    if p.get('not_measurable'):
        return (f'{AUTHOR}: not measurable by this seat: {p["not_measurable"]}; the relation is answered UNRESOLVED and '
                'listed, not filled in (rule R04). No causation or outcome claimed (rules R01, R02).')
    coefficient = (f'Pearson {corr["pearson"]!r} over {corr["present_overlap"]} rows where both are PRESENT'
                   if corr['pearson'] is not None else
                   f'Pearson not reported ({corr["reason"]}; {corr["present_overlap"]} rows where both are PRESENT)')
    m = p['co_movement']
    moves = (f'co-movement over {m["steps_between_consecutive_both_present"]} consecutive both-PRESENT steps: '
             f'{json.dumps(m["steps"], sort_keys=True)}; state pairings {json.dumps(m["state_pairs"], sort_keys=True)}')
    return (f'{AUTHOR}: {basis} {p["direction_relation"]}; {coefficient}; {moves}. Descriptive for this '
            'pair and window only; no causation or outcome claimed (rules R01, R02, R05).')


def _disagreement(p):
    if p.get('co_movement') is None:
        return None
    steps = p['co_movement']['steps']
    same, opposite = steps['same_direction'], steps['opposite_direction']
    if p['direction_relation'] == 'SAME_DIRECTION' and opposite > same:
        return same, opposite
    if p['direction_relation'] == 'OPPOSITE_DIRECTION' and same > opposite:
        return same, opposite
    return None


def _point(p, absent_text):
    tables = [dict(name=t['name'], rows_known=t.get('rows_known'), not_yet_known=t.get('not_yet_known')) for t in p['tables']]
    parts = []
    for t in tables:
        if t['rows_known'] is None:
            parts.append(f'{t["name"]}: {absent_text}')
        elif t['not_yet_known'] is None:
            parts.append(f'{t["name"]}: {t["rows_known"]} rows known, not-yet-known count unknown (listed)')
        else:
            parts.append(f'{t["name"]}: {t["rows_known"]} rows known, {t["not_yet_known"]} not yet known')
    missing = '; '.join(f'{m.get("point")}: {m.get("reason")}' for m in p['missing']) or 'none listed'
    named = ', '.join(p['series']) or 'none (no numeric series in the day file)'
    return dict(point_id=p['point_id'], name=p['name'], series=list(p['series']), tables=tables, missing_count=len(p['missing']),
                review=(f'{AUTHOR}: point {p["point_id"]} {p["name"]}: series {named}; tables {"; ".join(parts)}; '
                        f'missing (day {p.get("day", "")}): {missing}.'))


# ------------------------------------------------------------------------------------ GUIDED: computed from the evidence
def _guided_series(EXT, np, pre, s):
    """One series' facts and alignment summary recomputed from what GUIDED shows: its known values and the runs of rows
    that saw each (the segments cover every row in order). Returns the TEACH-shaped series and its row ledger."""
    n, segments = int(pre['rows']), list(s['alignment']['segments'])
    if int(s['alignment']['rows']) != n:
        raise ValueError(f'{s["name"]}: the visible alignment has another row count')
    codes = np.full(n, EXT.MISSING, dtype=np.int8)
    values = np.full(n, np.nan, dtype=np.float64)
    nonpresent, position = {}, 0
    for seg in segments:
        k = int(seg['rows'])
        if k <= 0 or position + k > n:
            raise ValueError(f'{s["name"]}: invalid visible segment row count')
        codes[position:position + k] = EXT.STATES.index(seg['state'])
        values[position:position + k] = seg['value'] if seg['value'] is not None else np.nan
        position += k
        if seg['state'] != 'PRESENT':
            key = seg['state'] + '|' + str(seg['reason'])
            nonpresent[key] = nonpresent.get(key, 0) + k
    if position != n:
        raise ValueError(f'{s["name"]}: the visible runs cover {position} of the section\'s {n} rows')
    counts = {state: int(np.sum(codes == i)) for i, state in enumerate(EXT.STATES)}
    direction = EXT._direction(np, codes, values)
    last = segments[-1]
    facts = EXT._facts(dict(known=list(s['known_values']), not_yet_known_in_table=None), int(pre['open_ns']))
    alignment = dict(rows=n, state_counts=counts, nonpresent_rows_by_reason=dict(sorted(nonpresent.items())),
                     terminal_state=last['state'], terminal_value=last['value'], terminal_reason=last['reason'],
                     first_to_last_present_direction=direction, segments=segments)
    return dict(s, facts=facts, alignment=alignment), (codes, values, direction)


def _dipole_ledgers(EXT, np, pre, dipole_visible):
    """Per Dipole column, (codes, values, direction) over this section's rows from the V1 classroom's visible
    observations (shown in TEACH and GUIDED), or (None, why) when they were not supplied or do not span the rows."""
    if dipole_visible is None:
        return None, NOT_SUPPLIED
    out, roster = {}, None
    components = dipole_visible['pre_message']['components']
    if [c['name'] for c in components] != list(pre['dipole_columns']):
        raise ValueError('the V1 and external Dipole component rosters differ')
    for comp in components:
        obs = comp['observations']
        if not obs or len(obs) != int(pre['rows']) or int(obs[0]['cursor']) != int(pre['first_cursor']) \
                or int(obs[-1]['cursor']) != int(pre['last_cursor']):
            return None, f'{comp["name"]}: the V1 observations do not span this section\'s rows'
        cursors = [int(p['cursor']) for p in obs]
        if any(a >= b for a, b in zip(cursors, cursors[1:])) or roster is not None and cursors != roster:
            raise ValueError('the V1 observations do not share one ordered cursor roster')
        roster = cursors
        codes = np.array([EXT.STATES.index(p['state']) for p in obs], dtype=np.int8)
        values = np.array([float(p['value']) if p['state'] == 'PRESENT' else np.nan for p in obs], dtype=np.float64)
        out[comp['name']] = (codes, values, EXT._direction(np, codes, values))
    for series in pre['series']:
        position = 0
        for segment in series['alignment']['segments']:
            end = position + int(segment['rows'])
            if end <= position or end > len(roster) or int(segment['first_cursor']) != roster[position] or \
                    int(segment['last_cursor']) != roster[end - 1]:
                raise ValueError('external segment boundaries differ from the visible Dipole cursor roster')
            position = end
        if position != len(roster):
            raise ValueError('external segments do not cover the visible Dipole cursor roster')
    return out, None


def _guided_point(EXT, p):
    """Table names come from public definitions; withheld totals cannot be inferred from selected series rows."""
    spec = next((x for x in EXT.POINTS if x['point_id'] == p['point_id']), None)
    tables = []
    for name in (spec['tables'] if spec else ()):
        tables.append(dict(name=name, rows_known=None, not_yet_known=None))
    return dict(p, tables=tables)


def _section(visible, dipole_visible):
    """(series in the TEACH shape, the pair review, the attribution text, the questions this evidence leaves)."""
    pre = _pre(visible)
    if pre['mode'] == 'TEACH':
        return (list(pre['series']), list(pre['relationship_review']), 'the teacher\'s relation', [],
                [dict(p, day=pre['trading_day']) for p in pre['points']],
                'not in the day file')
    EXT = _external_math()
    if dipole_visible is not None:
        binding, dipole_binding = visible['binding'], dipole_visible['binding']
        if binding['v1_source_snapshot_hash'] != dipole_binding['source_snapshot_hash'] or \
                binding['v1_classroom_binding_hash'] != dipole_binding['classroom_binding_hash']:
            raise ValueError('the external section and visible Dipole evidence belong to different classroom sources')
    np = EXT._np()
    series, ledgers = [], {}
    for s in pre['series']:
        shaped, ledgers[s['name']] = _guided_series(EXT, np, pre, s)
        series.append(shaped)
    dipole, why = _dipole_ledgers(EXT, np, pre, dipole_visible)
    columns = set(pre['dipole_columns'])
    review, questions = [], []
    for left, right in pre['relationship_pairs']:
        kind = 'EXTERNAL_DIPOLE' if right in columns else 'EXTERNAL_EXTERNAL'
        other = (dipole or {}).get(right) if kind == 'EXTERNAL_DIPOLE' else ledgers.get(right)
        if other is None:
            review.append(dict(left=left, right=right, kind=kind, direction_relation='UNRESOLVED',
                               correlation=dict(present_overlap=None, pearson=None, reason=NOT_SUPPLIED),
                               co_movement=None, not_measurable=why or f'{right} has no visible ledger'))
            continue
        review.append(EXT._pair(np, left, right, kind, ledgers[left], other))
    if dipole is None:
        questions.append(f'GUIDED: the {sum(1 for p in review if p["kind"] == "EXTERNAL_DIPOLE")} series x Dipole pairs are '
                         f'answered UNRESOLVED: {why} (pass the V1 visible classroom as dipole_visible).')
    questions.append('GUIDED: each table\'s known and not-yet-known total row counts are withheld; answered as unknown '
                     'and listed, never inferred by deduplicating visible series rows (rule R04).')
    points = [_guided_point(EXT, dict(p, day=pre['trading_day'])) for p in pre['points']]
    return (series, review, 'relation computed by Frankie\'s code from the visible rows (withheld by the teacher in GUIDED)',
            questions, points, 'table counts withheld in GUIDED (unknown; not inferred from selected series)')


def answers(visible, *, dipole_visible=None, learner_context=None):
    """All four external ledgers: TEACH transcribed from the shown evidence; GUIDED computed from the visible known
    values, row runs and (when supplied) the V1 classroom's Dipole observations. `learner_context` (the classroom's
    legal-knowledge and school reproductions) is carried into the review text, never into the ledgers' facts."""
    pre = _pre(visible)
    series, review, basis, mode_questions, points, absent_text = _section(visible, dipole_visible)
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
    questions += mode_questions
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
    correlation_review = (f'{AUTHOR}: {len(review)} external pairs ({basis}). Relation: {json.dumps(by_relation, sort_keys=True)}. '
                          f'Pearson reported on {reported}; not reported on {len(review) - reported} '
                          f'({json.dumps(not_reported, sort_keys=True)}). {len(disagreements)} pairs whose first-to-last '
                          'relation and step counts point different ways (filed as hypotheses). Per pair and per window, '
                          'never pooled or averaged (rule R05).')
    if learner_context is not None:
        checks = sum(len(r.get('checks', [])) for r in learner_context.values())
        listed = sum(len(r.get('listed', [])) for r in learner_context.values())
        correlation_review += (f' Legal learner knowledge was applied before these answers ({checks} individual checks, '
                               f'{listed} inputs listed as not evaluated by the classroom check); it is bound to the Dipole '
                               'classroom\'s pairs and components and alters no external fact here.')
    teachback = dict(
        schema=TEACHBACK_SCHEMA, teacher_message_hash=pre['teacher_message_hash'],
        components=[_component(s, basis) for s in series],
        point_review=[_point(p, absent_text) for p in points],
        cycle_summary=(f'{AUTHOR}: {len(series)} series of {len(pre["points"])} points over {pre["rows"]} Dipole rows '
                       f'(cursors {pre["first_cursor"]}..{pre["last_cursor"]}), day file {pre["day_file"]["sha256"]} read at '
                       f'cutoff {pre["cutoff_ns"]}, mode {pre["mode"]}. First-to-last PRESENT direction: '
                       + '; '.join(f'{k} {len(v)}' for k, v in sorted(by_direction.items()))
                       + f'. Series absent from the day file: {len(pre["series_absent"])}. Deferred by Greg: '
                       f'{", ".join(d["name"] for d in deferred.get("points", [])) or "none"}.'),
        correlation_review=correlation_review,
        unresolved_questions=questions, relationship_pairs_considered=len(review), future_outcome_claimed=False)
    scan = [dict(left=p['left'], right=p['right'], direction_relation=p['direction_relation'],
                 correlation_interpretation=_pair_text(p, basis), developing_structure=None) for p in review]
    return dict(external_teachback=teachback, external_value_review=[_values(s) for s in series],
                external_relationship_scan=scan, external_novel_findings=findings)
