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
SOCRATIC and VERIFY use the learner-owned sealed-journal reading plus the causal day file. Missing independent
evidence refuses; no host key fallback. Source-built, runtime unverified.
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
MODES_ANSWERED = ('TEACH', 'GUIDED', 'SOCRATIC', 'VERIFY')
NOT_SUPPLIED = 'DIPOLE_OBSERVATIONS_NOT_SUPPLIED_TO_THIS_SEAT'


class ModeNotAnswerable(ValueError):
    """The mode asks for independent claims the code has no source for (refused with the reason)."""


INDEPENDENT_ROUTE_GAP = (
    'the independent day-file reader needs the learner-owned Dipole snapshot for row alignment and every pair; '
    'the runner supplies that separate sealed-journal reading in SOCRATIC/VERIFY, never the host snapshot')


def _pre(visible):
    pre = visible['pre_message']
    if pre['mode'] not in MODES_ANSWERED:
        raise ModeNotAnswerable(f'classroom mode {pre["mode"]} withholds the external evidence and asks for Frankie\'s '
                                f'independent claims; not answered from the host key. Independent route: {INDEPENDENT_ROUTE_GAP}')
    return pre


def independent_day_file_evidence(pre, snapshot=None):
    """The external evidence Frankie's seat can read on its own in any mode: the day file named by the pre-message's
    descriptor (path + sha256, checked), read through the existing as-of reader at the classroom cutoff. The same
    reading half build_external_key uses, without the teacher's rows: per series its known values and facts (with the
    table's not-yet-known count from the file), per point its tables' known / not-yet-known row counts, its series and
    its missing entries, the absent series and the unassigned missing entries. Without a learner snapshot, missing
    per-row alignment and pairs are listed. With one, the existing math computes those from the learner's own rows.
    Nothing here reads the host key or host rows."""
    EXT = _external_math()
    descriptor = pre['day_file']
    dx, reader, witness = EXT.open_day_external(descriptor['path'], descriptor['sha256'], int(pre['cutoff_ns']),
                                                trading_day=pre['trading_day'])
    body, open_ns, cutoff = reader.body, int(pre['open_ns']), int(pre['cutoff_ns'])
    entries, absent = EXT.read_series(dx, reader)
    series = []
    for entry in entries:
        series.append(dict(name=entry['name'],
                           point_ids=[p['point_id'] for p in EXT.POINTS if EXT._matches(entry['name'], p['series'])],
                           table=entry['table'], column=entry['column'], where=entry['where'],
                           absent_reason=entry['absent_reason'], facts=EXT._facts(entry, open_ns),
                           known_values=[dict(published_ns=k['published_ns'], state=k['state'], value=k['value'],
                                              raw_value=k['raw_value'], reason=k['reason'], row=k['row'])
                                         for k in entry['known']]))
    names = [s['name'] for s in series]
    tables = {}
    for tname in body['points']:
        if tname in EXT.DEFERRED['tables']:
            continue
        view = reader.until(tname, cutoff)
        tables[tname] = dict(name=tname, rows_known=len(view['rows']), not_yet_known=view['not_yet_known'])
    missing = list(body.get('missing') or ())
    assigned = {id(m) for m in missing if EXT._matches(str(m.get('point')), EXT.DEFERRED['missing'])}
    points = []
    for p in EXT.POINTS:
        mine = [m for m in missing if EXT._matches(str(m.get('point')), p['missing'])]
        assigned.update(id(m) for m in mine)
        points.append(dict(point_id=p['point_id'], name=p['name'],
                           series=[n for n in names if EXT._matches(n, p['series'])],
                           tables=[tables.get(t, dict(name=t, absent=True, reason='not in the day file (see missing)'))
                                   for t in p['tables']],
                           missing=mine))
    result = dict(schema='FRANKIE_BOX_INDEPENDENT_DAY_FILE_EVIDENCE_V1', author=AUTHOR, day_file=witness,
                cutoff_ns=cutoff, open_ns=open_ns, series=series, series_absent=absent, points=points,
                missing_not_assigned=[m for m in missing if id(m) not in assigned],
                not_supplied=['alignment (state counts, terminal state, direction, runs per series): needs the Dipole '
                              'rows\' timestamps', 'relationship pairs (series x Dipole, series x series): need the '
                              'Dipole ledgers and the row alignment'],
                rule='read from the day file at the cutoff, never from the teacher\'s key or rows (R09/R10); what is not '
                     'readable here is listed, not filled in (R04)')
    if snapshot is None:
        return result
    # The caller supplies ONLY Frankie's newly calculated snapshot. Align the same
    # day-file entries with its own row times, using the original scientific functions.
    np = EXT._np()
    dip = EXT.dipole_arrays(snapshot)
    if (snapshot['as_of'] != cutoff or dip['n'] != pre['rows'] or
            int(dip['cursors'][0]) != pre['first_cursor'] or int(dip['cursors'][-1]) != pre['last_cursor'] or
            names != [s['name'] for s in pre['series']]):
        raise ValueError('learner external reading does not span the requested source window/series')
    ledgers = {}
    for entry, shaped in zip(entries, series):
        idx = EXT._align(np, entry, dip)
        codes, values = EXT._ledger(np, entry, idx)
        direction = EXT._direction(np, codes, values)
        ledgers[entry['name']] = (codes, values, direction)
        segments = EXT._segments(np, entry, idx, dip)
        nonpresent = {}
        for seg in segments:
            if seg['state'] != 'PRESENT':
                reason = seg['state'] + '|' + str(seg['reason'])
                nonpresent[reason] = nonpresent.get(reason, 0) + seg['rows']
        last = segments[-1]
        shaped['alignment'] = dict(rows=dip['n'],
            state_counts={state: int(np.sum(codes == i)) for i, state in enumerate(EXT.STATES)},
            nonpresent_rows_by_reason=dict(sorted(nonpresent.items())), segments=segments,
            terminal_state=last['state'], terminal_value=last['value'], terminal_reason=last['reason'],
            first_to_last_present_direction=direction)
    dipole = {c: (dip['codes'][c], dip['values'][c], EXT._direction(np, dip['codes'][c], dip['values'][c]))
              for c in pre['dipole_columns']}
    review = [EXT._pair(np, name, c, 'EXTERNAL_DIPOLE', ledgers[name], dipole[c])
              for name in names for c in pre['dipole_columns']]
    review += [EXT._pair(np, a, b, 'EXTERNAL_EXTERNAL', ledgers[a], ledgers[b])
               for i, a in enumerate(names) for b in names[i + 1:]]
    if [[p['left'], p['right']] for p in review] != pre['relationship_pairs']:
        raise ValueError('learner external pair roster differs from the request')
    result.update(relationship_review=review, learner_source_snapshot_hash=snapshot['source_snapshot_hash'],
                  teacher_message_hash=pre['teacher_message_hash'], not_supplied=[])
    return result


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


def _section(visible, dipole_visible, independent_evidence=None):
    """(series in the TEACH shape, the pair review, the attribution text, the questions this evidence leaves)."""
    pre = _pre(visible)
    if pre['mode'] == 'TEACH':
        return (list(pre['series']), list(pre['relationship_review']), 'the teacher\'s relation', [],
                [dict(p, day=pre['trading_day']) for p in pre['points']],
                'not in the day file')
    if pre['mode'] in ('SOCRATIC', 'VERIFY'):
        own = (dipole_visible or {}).get('learner_evidence')
        if independent_evidence is None or own is None:
            raise ModeNotAnswerable('independent external answers require the learner-owned journal/day-file reading')
        if (independent_evidence['teacher_message_hash'] != pre['teacher_message_hash'] or
                independent_evidence['learner_source_snapshot_hash'] != own['witness']['source_snapshot_hash']):
            raise ValueError('independent external evidence belongs to another learner reading/request')
        return (independent_evidence['series'], independent_evidence['relationship_review'],
                'computed from the learner-owned journal reading and the causal day file', [],
                [dict(p, day=pre['trading_day']) for p in independent_evidence['points']], 'not in the day file')
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


def answers(visible, *, dipole_visible=None, learner_context=None, independent_evidence=None,
            knowledge=(), school=()):
    """All four external ledgers: TEACH transcribed from the shown evidence; GUIDED computed from the visible known
    values, row runs and (when supplied) the V1 classroom's Dipole observations. `learner_context` (the classroom's
    legal-knowledge and school reproductions) stays separate from current facts. External prior findings use the same
    recognition calculation against this section's lawful current pairs and enter their interpretations."""
    pre = _pre(visible)
    series, review, basis, mode_questions, points, absent_text = _section(visible, dipole_visible, independent_evidence)
    import frankie_box_classroom_code as K
    sources, external_listed = list(knowledge), []
    # Earlier school files already retain complete external answers. Project just their findings;
    # do not rebuild the school or treat its other-day observations as today's evidence.
    for row, doc in school:
        for item in (doc.get('sections', {}).get('frankie_classwork') or {}).get('items') or []:
            if item.get('name') == 'external_answers' and not item.get('inline'):
                external_listed.append(dict(day=row['day'], source=item, school_sha256=row['sha256'],
                    reason='external school answers are a retained pointer; finding bytes are not supplied here'))
            content = item.get('content')
            if item.get('inline') and isinstance(content, dict) and content.get('schema') == SCHEMA:
                findings = (content.get('ledgers') or {}).get('external_novel_findings') or []
                sources.append(dict(label='school external findings', day=row['day'], kind='school',
                                    path=item.get('path') or row.get('file'), sha256=item['sha256'],
                                    content=dict(findings=findings, school_sha256=row['sha256'])))
    external_knowledge = K.stage_knowledge_reproduction(None, sources,
        evidence=dict(components=[], relationship_review=review), relationship_kind='EXTERNAL_RELATIONSHIP')
    external_knowledge['listed'].extend(external_listed)
    prior_checks = K._knowledge_notes({'external': external_knowledge})
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
    correlation_review += (' External accumulated-finding checks, each with its source and retained scope: '
                           + json.dumps(dict(external_knowledge, checks=prior_checks), sort_keys=True, default=str)
                           + '. These are current pattern comparisons, not new independent scientific confirmations.')
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
    for pair in scan:
        checks = [c for c in prior_checks if set(c.get('pair') or []) == {pair['left'], pair['right']}]
        if checks:
            pair['correlation_interpretation'] += (' Prior findings applied to this pair: '
                                                   + json.dumps(checks, sort_keys=True, default=str))
    return dict(external_teachback=teachback, external_value_review=[_values(s) for s in series],
                external_relationship_scan=scan, external_novel_findings=findings)
