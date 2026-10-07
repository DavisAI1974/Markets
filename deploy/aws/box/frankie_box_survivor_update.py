"""Stage 10: the survivor/candidate update at a cross-day batch boundary (SPEC-experiment-orchestrator section 0, step 9;
Greg, 2026-10-07: cross-day batch boundary; consumption only by LATER classrooms; no averaging, no pooling; immediate
brain commit; provenance to the exact claims, pictures and days; missing coverage thins the picture, never rejects a day;
day-quantity agnostic: a boundary of one day is lawful).

What it is. Every claim the scientific teacher has tested so far (Frankie's novel findings, Jev's sealed claims, the
historical crosswalk claims, the search's own candidates) is ONE candidate, kept individually. For each candidate the
update lists every test the lessons files hold for it, one row per (day, search part, row): the mark the scientific
teacher gave it on that day (held / shown_otherwise / unresolved / counts_only), the counts, the cell, the lag, the
transforms and the exact provenance (lessons file sha256, result index, part sha256, row ordinal, raw-line sha256).
Nothing is averaged: the finding is the days named per mark.

Status words (orientation only, R14; the days are the finding):
  survivor_scoped      held beyond chance, the claimed way, on at least one day OTHER than the day the claim was made
                       (a single checked occurrence counts: R06, equal treatment); scoped to the cells/lags it held on
                       ("works on {X}"); days shown otherwise are kept beside it ("not {Y}": both accounts, R13)
  contradicted_scoped  no held day, at least one shown_otherwise day (the challenge stands; not dropped: D52)
  open                 neither: unresolved, counts_only, untested or not yet tested on another day
No threshold, rarity gate, minimum occurrence, acceptance rule or freeze is added here (step 13 freezes once, separately).
The claim's own day (day_made) and the search candidate's origin day are listed as own-day / origin evidence and never
counted toward survivor scoping: a second reading of the evidence a claim came from is not another occurrence.

Where it runs. At a batch boundary of the orchestrator (after Run.lessons of the batch; CCode's caller, named in the
return), on the owner lane, keyed by the boundary day (the batch's last day in plan order; a batch of ONE day is a
boundary). The update is CUMULATIVE over every lessons entry in the brain at the boundary: a lesson that arrives after
the boundary froze its selection is LISTED (late_knowledge) and consumed at the next boundary; nothing waits.

Consumption. The document is filed as the brain stage entry <brain>/<boundary day>-survivors (frankie_box_brain.
write_stage_entry, stage 'survivors'); frankie_box_lane_state.learner_knowledge delivers it to every LATER classroom
(DAY_KINDS: survivors 50 > classroom 0 excludes the boundary day's own classroom; no same-day circular promotion). Each
candidate carries claim_id, x, y, scope.pair and its days so the classroom's existing learner check
(frankie_box_classroom_code.stage_knowledge_reproduction) binds it as a prior hypothesis, never as today's observation.

Provenance and identity. inputs.json freezes the selection (every lessons/jev-tested/search/survivors entry read, by
pin; the previous updates; the searches' manifests; the readers' sha256) and the document binds it (selection_sha256).
A restart reads the frozen selection and reproduces the same bytes (no clock in the document). A previously known
status is carried per candidate (previously_known) beside what is new since the previous update (new_tests): a known
value stays distinguishable from a new observation. Integrity failures (a brain entry whose bytes differ from its
manifest, an unreadable file, a lesson needing a checked successor) are listed under integrity_failures / listed and
block only what they carry, never the boundary. Code only; no model call; no scientific test is run here.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

BOX = Path(__file__).resolve().parent
sys.path.insert(0, str(BOX))
SCHEMA = 'FRANKIE_SURVIVOR_UPDATE_V1'
INPUTS_SCHEMA = 'FRANKIE_SURVIVOR_UPDATE_INPUTS_V1'
RECEIPT_SCHEMA = 'FRANKIE_SURVIVOR_UPDATE_RECEIPT_V1'
ROOT = Path('/opt/frankie-box/work/experiment-survivors')
SEARCH = Path('/opt/frankie-box/work/experiment-search')
CYCLE = '00'
LESSONS = {'FRANKIE_LESSONS_V1': 'frankie', 'JEV_LESSONS_V1': 'jev', 'HISTORICAL_LESSONS_V1': 'historical',
           'SEARCH_CANDIDATE_LESSONS_V1': 'search'}
MARKS = ('held', 'shown_otherwise', 'unresolved', 'counts_only')
STATUS_RULE = ('orientation only (R14): survivor_scoped = held beyond chance the claimed way on at least one day other than '
               'the day the claim was made (R06: one checked occurrence counts); contradicted_scoped = no held day and at '
               'least one shown_otherwise day; open = neither. Days shown otherwise stay beside days held (both accounts, '
               'R13). No threshold, rarity gate, pooling, averaging or freeze (step 13 freezes once, separately).')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()


def digest(value):
    return sha256_bytes(canonical(value))


# ------------------------------------------------------------------------------------------------ selection (frozen)
def select(brain, boundary_day):
    """Every brain entry the update may read, with per-entry integrity capture (an entry that cannot be read or
    verified is listed and the rest continues: a missing operand blocks only its own equation)."""
    import frankie_box_brain as BR
    import frankie_box_experiment_review as REVIEW
    import frankie_box_lane_state as LS
    roots = LS.knowledge_roots(brain)
    records = REVIEW.corrections(roots)
    documents, listed, integrity, seen = [], [], [], set()
    for root in roots:
        root = Path(root)
        readable = {d.name for _, _, d in BR.entries_before(root, CYCLE, day=boundary_day)}
        # entries_before skips an unreadable manifest silently; name every entry directory it left out
        for pattern in BR.ENTRY_GLOBS:
            for d in sorted(p for p in root.glob(pattern) if p.is_dir()):
                parsed = BR.parse_entry_name(d.name)
                if parsed is None or d.name in readable or d.name == BR.entry_name(boundary_day, CYCLE):
                    continue
                if parsed[1] in ('lessons', 'jev-tested', 'search', 'survivors'):
                    integrity.append(dict(root=str(root), entry=d.name, kind='manifest_unreadable_or_absent',
                                          reason='entries_before could not read this entry\'s MANIFEST.json; not consumed, listed'))
        for label, manifest, d in BR.entries_before(root, CYCLE, day=boundary_day):
            eday, kind = BR.parse_entry_name(d.name)
            if kind not in ('lessons', 'jev-tested', 'search', 'survivors'):
                listed.append(dict(label=label, entry=d.name, kind=kind, reason='not a claim-test, candidate or survivor entry; not read here'))
                continue
            if kind == 'survivors' and eday == boundary_day:
                listed.append(dict(label=label, entry=d.name, kind=kind,
                                   reason='this boundary\'s own earlier survivors entry: never its own previous update or late knowledge'))
                continue
            for e in manifest.get('entries', []):
                name = e.get('name', '')
                p = d / name
                if not e.get('include'):
                    listed.append(dict(label=label, name=name, reason='excluded by the source manifest'))
                    continue
                if not name.endswith('.json'):
                    listed.append(dict(label=label, name=name, reason='retained text evidence; no structured claim content'))
                    continue
                if not p.is_file():
                    integrity.append(dict(label=label, path=str(p), kind='included_file_missing',
                                          reason='the manifest includes a file that is not there; not consumed'))
                    continue
                raw = p.read_bytes()
                if len(raw) != e.get('bytes') or sha256_bytes(raw) != e.get('sha256'):
                    integrity.append(dict(label=label, path=str(p), kind='bytes_differ_from_manifest',
                                          expected=dict(bytes=e.get('bytes'), sha256=e.get('sha256')),
                                          found=dict(bytes=len(raw), sha256=sha256_bytes(raw)),
                                          reason='altered pinned bytes: a separate visible failure, not missing coverage; not consumed'))
                    continue
                try:
                    content = json.loads(raw)
                except ValueError as error:
                    integrity.append(dict(label=label, path=str(p), kind='unreadable_json', reason=str(error)))
                    continue
                try:
                    delivered = REVIEW.current_document(dict(label=label, day=eday, kind=kind, path=str(p), bytes=len(raw),
                                                             sha256=e['sha256'], content=content),
                                                        records, brain, day=boundary_day, stage='survivors')
                except ValueError as error:
                    listed.append(dict(label=label, path=str(p), sha256=e['sha256'], kind=kind,
                                       reason='needs a checked successor before it can be consumed: %s' % error))
                    continue
                if delivered['sha256'] in seen:
                    listed.append(dict(label=label, path=delivered['path'], sha256=delivered['sha256'],
                                       reason='identical delivered bytes already selected'))
                    continue
                seen.add(delivered['sha256'])
                documents.append(dict(label=label, day=eday, kind=kind, path=delivered['path'], bytes=delivered.get('bytes'),
                                      sha256=delivered['sha256'], corrections_applied=delivered.get('corrections_applied') or [],
                                      content=delivered['content']))
    return dict(documents=documents, listed=listed, integrity_failures=integrity, roots=[str(r) for r in roots],
                corrections_known=len(records))


def lessons_in(document):
    """(lesson docs, listed) inside one selected document: a lessons file is itself a lesson; a stage-knowledge entry
    (jev-tested, search, survivors) carries its sources inline."""
    content, out, listed = document['content'], [], []
    schema = content.get('schema') if isinstance(content, dict) else None
    if schema in LESSONS:
        out.append((content, dict(path=document['path'], sha256=document['sha256'])))
    elif schema == 'FRANKIE_STAGE_KNOWLEDGE_V1':
        for i, member in enumerate(content.get('sources') or []):
            inner = member.get('content') if member.get('inline') else None
            if isinstance(inner, dict) and inner.get('schema') in LESSONS:
                out.append((inner, dict(path=member.get('path'), sha256=member.get('sha256'), container_sha256=document['sha256'],
                                        address=['sources', i, 'content'])))
            elif isinstance(inner, dict) and inner.get('schema') in ('FRANKIE_SEARCH_FINDINGS_V1', SCHEMA):
                out.append((inner, dict(path=member.get('path'), sha256=member.get('sha256'), container_sha256=document['sha256'],
                                        address=['sources', i, 'content'])))
            else:
                listed.append(dict(path=member.get('path'), sha256=member.get('sha256'),
                                   reason='stage source without inline structured claim content (a pointer or another schema)'))
    else:
        listed.append(dict(path=document['path'], sha256=document['sha256'], schema=schema, reason='not a lessons, candidate or survivor document'))
    return out, listed


def candidate_key(author, claim_id, day_made, statement):
    return digest([author, claim_id, day_made, statement])[:16]


def build(selection, boundary_day, batch_days, run):
    """The candidates and their tests from the frozen selection; previous updates read for previously_known."""
    candidates, previous_docs, untested_sources, listed = {}, [], [], []
    test_keys_seen = {}
    for document in selection['documents']:
        docs, inner_listed = lessons_in(document)
        listed.extend(inner_listed)
        for doc, where in docs:
            schema = doc.get('schema')
            if schema == SCHEMA:
                previous_docs.append(dict(where, boundary=doc.get('boundary'), candidates=len(doc.get('candidates') or []),
                                          content=doc))
                continue
            if schema == 'FRANKIE_SEARCH_FINDINGS_V1':
                untested_sources.append(dict(where, day=doc.get('day'), findings=len(doc.get('findings') or []),
                                             manifest_sha256=doc.get('manifest_sha256'),
                                             reason='search candidates listed by source and count; each becomes a candidate '
                                                    'here only once a lessons file has tested it (origin evidence alone is not a test)'))
                continue
            author = LESSONS[schema]
            if doc.get('written_by') != 'scientific_teacher' or not isinstance(doc.get('results'), list):
                listed.append(dict(where, reason='lesson without scientific_teacher results; not consumed'))
                continue
            claims = {c['id']: c for c in ((doc.get('claim_inputs') or {}).get('claims') or [])}
            for index, r in enumerate(doc['results']):
                claim = claims.get(r.get('claim_id')) or {}
                key = candidate_key(author, r.get('claim_id'), r.get('day_made'), r.get('statement'))
                series = list(claim.get('series') or sorted(({t.get('x') for t in r.get('tests') or []} |
                                                              {t.get('y') for t in r.get('tests') or []}) - {None}))
                slot = candidates.setdefault(key, dict(
                    candidate=key, claim_id=r.get('claim_id'), author=author, day_made=r.get('day_made'),
                    statement=r.get('statement'), series=series, x=series[0] if len(series) > 0 else None,
                    y=series[1] if len(series) > 1 else None, scope=dict(pair=series[:2]),
                    claimed=dict(direction=claim.get('direction'), lag=claim.get('lag'), cells=claim.get('cells'),
                                 x_transform=claim.get('x_transform'), y_transform=claim.get('y_transform'),
                                 condition=claim.get('condition')),
                    origin=claim.get('origin'), tests=[], own_day_evidence=[], origin_evidence=[], duplicates=[],
                    untested=[], cannot_test_yet=[], challenges=[], lessons=[], dispositions_given={}))
                slot['lessons'].append(dict(where, result_index=index, day=doc.get('day'), stamp=doc.get('stamp'),
                                            claims_sha256=doc.get('claims_sha256'),
                                            searches=[s.get('day') for s in doc.get('searches') or []],
                                            disposition=r.get('disposition')))
                word = r.get('disposition')
                slot['dispositions_given'][word] = slot['dispositions_given'].get(word, 0) + 1
                for note in r.get('untested') or []:
                    if note not in slot['untested']:
                        slot['untested'].append(note)
                for note in r.get('cannot_test_yet') or []:
                    if note not in slot['cannot_test_yet']:
                        slot['cannot_test_yet'].append(note)
                for note in r.get('challenge') or []:
                    if note not in slot['challenges']:
                        slot['challenges'].append(note)
                for t in r.get('origin_evidence') or []:
                    slot['origin_evidence'].append(dict(day=t.get('day'), x=t.get('x'), y=t.get('y'), cell=t.get('cell'),
                                                        cell_value=t.get('cell_value'), lag=t.get('lag'), counts=t.get('counts'),
                                                        beyond_chance=t.get('beyond_chance'), where=t.get('where'),
                                                        lesson_sha256=where['sha256'], result_index=index,
                                                        reason='origin day: evidence the candidate was read from; never a test'))
                for t in r.get('tests') or []:
                    w = t.get('where') or {}
                    tkey = (t.get('day'), w.get('part_sha256'), w.get('row'))
                    row = dict(day=t.get('day'), x=t.get('x'), y=t.get('y'), cell=t.get('cell'), cell_value=t.get('cell_value'),
                               lag=t.get('lag'), x_transform=t.get('x_transform'), y_transform=t.get('y_transform'),
                               steps=t.get('steps'), counts=t.get('counts'), chance_check=t.get('chance_check'),
                               mark=t.get('mark'), scope_not_tested=t.get('scope_not_tested'), where=w,
                               lesson_sha256=where['sha256'], lesson_path=where.get('path'), result_index=index)
                    if tkey in test_keys_seen and test_keys_seen[tkey] == key:
                        slot['duplicates'].append(dict(row, reason='the same row already counted from another lessons file: '
                                                                   'a second use of the same evidence is not another occurrence'))
                        continue
                    test_keys_seen[tkey] = key
                    if r.get('day_made') is not None and t.get('day') == r.get('day_made'):
                        slot['own_day_evidence'].append(dict(row, reason='the day the claim was made: the same market day\'s '
                                                                         'evidence, listed beside, never a second occurrence'))
                        continue
                    slot['tests'].append(row)
    previous_known = {}
    for prev in previous_docs:
        for c in prev['content'].get('candidates') or []:
            previous_known.setdefault(c.get('candidate'), []).append(dict(
                boundary=(prev['content'].get('boundary') or {}).get('day'), status=c.get('status'),
                survivors_sha256=prev['sha256'], test_keys=[(t.get('day'), (t.get('where') or {}).get('part_sha256'),
                                                               (t.get('where') or {}).get('row')) for t in c.get('tests') or []]))
    out = []
    for key in sorted(candidates):
        slot = candidates[key]
        days = {m: sorted({t['day'] for t in slot['tests'] if t['mark'] == m}) for m in MARKS}
        held_on = [dict(day=t['day'], cell=t['cell'], cell_value=t['cell_value'], lag=t['lag'], x=t['x'], y=t['y'],
                        x_transform=t['x_transform'], y_transform=t['y_transform'], counts=t['counts'])
                   for t in slot['tests'] if t['mark'] == 'held']
        shown_on = [dict(day=t['day'], cell=t['cell'], cell_value=t['cell_value'], lag=t['lag'], x=t['x'], y=t['y'],
                         counts=t['counts']) for t in slot['tests'] if t['mark'] == 'shown_otherwise']
        status = ('survivor_scoped' if days['held'] else 'contradicted_scoped' if days['shown_otherwise'] else 'open')
        known = previous_known.get(key) or []
        known_keys = {k for item in known for k in item['test_keys']}
        new_tests = [t for t in slot['tests'] if (t['day'], (t['where'] or {}).get('part_sha256'), (t['where'] or {}).get('row')) not in known_keys]
        slot.update(status=status, status_rule=STATUS_RULE,
                    days=dict(held=days['held'], shown_otherwise=days['shown_otherwise'], unresolved=days['unresolved'],
                              counts_only=days['counts_only'], own_day=sorted({t['day'] for t in slot['own_day_evidence']}),
                              origin=sorted({t['day'] for t in slot['origin_evidence']}),
                              tested=sorted({t['day'] for t in slot['tests']})),
                    counts=dict(tests=len(slot['tests']), held=len(held_on), shown_otherwise=len(shown_on),
                                unresolved=sum(1 for t in slot['tests'] if t['mark'] == 'unresolved'),
                                counts_only=sum(1 for t in slot['tests'] if t['mark'] == 'counts_only'),
                                own_day_evidence=len(slot['own_day_evidence']), origin_evidence=len(slot['origin_evidence']),
                                duplicates=len(slot['duplicates'])),
                    works_on=held_on, not_on=shown_on,
                    previously_known=[dict(boundary=k['boundary'], status=k['status'], survivors_sha256=k['survivors_sha256']) for k in known],
                    new_tests=[dict(day=t['day'], where=t['where'], mark=t['mark']) for t in new_tests],
                    new_since_previous=bool(new_tests) if known else None,
                    evidence_refs=[dict(kind='SEARCH_PAIR', left=slot['x'], right=slot['y'])] if slot['y'] else [],
                    rule='one candidate, every test listed with its exact provenance; days named per mark; the claim\'s own '
                         'day and origin day are listed, never counted; a previously known status is carried beside what is '
                         'new (new_tests); nothing pooled, averaged, dropped or frozen here')
        out.append(slot)
    # candidates resting on the same series pair (another author's claim, a search candidate of another day): cross-
    # referenced so a reader sees that their evidence on a shared day is the same market day read twice, never two
    # occurrences; each stays its own candidate with its own counts (no pooling)
    by_pair = {}
    for c in out:
        by_pair.setdefault(tuple(sorted(x for x in (c['x'], c['y']) if x)), []).append(c['candidate'])
    for c in out:
        siblings = [k for k in by_pair.get(tuple(sorted(x for x in (c['x'], c['y']) if x)), []) if k != c['candidate']]
        c['same_pair_candidates'] = siblings
    counts = dict(candidates=len(out), survivor_scoped=sum(1 for c in out if c['status'] == 'survivor_scoped'),
                  contradicted_scoped=sum(1 for c in out if c['status'] == 'contradicted_scoped'),
                  open=sum(1 for c in out if c['status'] == 'open'),
                  by_author={a: sum(1 for c in out if c['author'] == a) for a in sorted({c['author'] for c in out})},
                  tests=sum(c['counts']['tests'] for c in out), duplicates=sum(c['counts']['duplicates'] for c in out),
                  previous_updates=len(previous_docs), untested_candidate_sources=len(untested_sources),
                  untested_candidates_listed=sum(u['findings'] for u in untested_sources))
    return dict(candidates=out, counts=counts, previous=[{k: v for k, v in p.items() if k != 'content'} for p in previous_docs],
                untested_candidate_sources=untested_sources, listed=listed)


# ----------------------------------------------------------------------------------------------------- all-99 coverage
def coverage(batch_days, candidates, out_dir, searches=None, brain_documents=None):
    """The all-99 list of every searched day of the batch, from the candidates' tests on that day (frankie_box_all99_coverage);
    a day whose search is not complete is listed, never a refusal."""
    import frankie_box_all99_coverage as A99
    import frankie_box_scientific_teacher as ST
    by_day, listed = {}, []
    historical = [c for c in candidates if c.get('author') == 'historical']
    knowledge_inputs = dict(brain_documents=brain_documents,
                            historical=(dict(mapped_claims=len(historical), not_testable=None, catalog_sha256=None) if historical else None),
                            frankie=any(c.get('author') == 'frankie' for c in candidates),
                            jev=any(c.get('author') == 'jev' for c in candidates),
                            search_candidates=any(c.get('author') == 'search' for c in candidates))
    for day in batch_days:
        directory = Path((searches or {}).get(day) or (SEARCH / day / ('cycle-' + CYCLE) / 'discovery'))
        if not (directory / 'MANIFEST.json').is_file():
            listed.append(dict(day=day, reason='no completed search MANIFEST at %s: the day\'s all-99 list waits for its search; '
                                               'its lessons, if any, are consumed above regardless' % directory))
            continue
        try:
            loaded = ST.load_searches([directory])[0]
        except (OSError, ValueError, SystemExit) as error:
            listed.append(dict(day=day, reason='the search of the day could not be loaded (%s); listed, the boundary continues' % error))
            continue
        tests = [t for c in candidates for t in c['tests'] + c['own_day_evidence'] + c['origin_evidence'] if t.get('day') == day]
        cov = A99.day_coverage(day, manifest_sha256=loaded['manifest_sha256'], planes=loaded.get('planes'),
                               sources=loaded.get('sources'), tests=tests, knowledge_inputs=knowledge_inputs,
                               outputs={}, stage='survivor_update', code_root=os.environ.get('CODE_ROOT'),
                               shared_market=loaded.get('shared_market'))
        by_day[day] = dict(A99.retain(cov, out_dir), full=cov)
    boundary = A99.boundary([pin['full'] for pin in by_day.values()]) if by_day else None
    return dict(by_day={d: {k: v for k, v in pin.items() if k != 'full'} for d, pin in by_day.items()},
                boundary=boundary, listed=listed, rule=A99.RULE)


# ---------------------------------------------------------------------------------------------------------- operation
def update(run, boundary_day, batch_days, brain, out_root, *, searches=None, log=print):
    import frankie_box_brain as BR
    from frankie_box_durable import write_json, witness
    started = time.time()
    out = Path(out_root) / run / boundary_day
    inputs_path = out / 'inputs.json'
    timings = {}
    t0 = time.time()
    if inputs_path.is_file():
        inputs = json.loads(inputs_path.read_bytes())
        if inputs.get('schema') != INPUTS_SCHEMA or inputs.get('selection_sha256') != digest(inputs['selection']):
            raise ValueError('retained survivor update inputs differ from their binding: ' + str(inputs_path))
        if inputs['identity'].get('run') != run or inputs['identity'].get('boundary_day') != boundary_day:
            raise ValueError('retained survivor update belongs to another run/boundary')
        selection = inputs['selection']
        frozen = True
        current = select(brain, boundary_day)
        seen = {d['sha256'] for d in selection['documents']}
        late = [dict(label=d['label'], path=d['path'], sha256=d['sha256'], kind=d['kind'], day=d['day'],
                     reason='published after this boundary froze its selection; consumed at the next boundary')
                for d in current['documents'] if d['sha256'] not in seen]
        # the frozen documents are re-read by pin so the restart computes on the same bytes
        import frankie_box_experiment_review as REVIEW
        for d in selection['documents']:
            d['content'] = json.loads(REVIEW._read_pin(dict(path=d['path'], bytes=d['bytes'], sha256=d['sha256'])))
    else:
        selection = select(brain, boundary_day)
        frozen, late = False, []
        identity = dict(run=run, boundary_day=boundary_day, batch_days=list(batch_days), brain=str(Path(brain).resolve()),
                        producer=witness(__file__), readers={m: witness(BOX / (m + '.py'))['sha256']
                                                              for m in ('frankie_box_all99_coverage', 'frankie_box_scientific_teacher',
                                                                        'frankie_box_experiment_review', 'frankie_box_brain')})
        stored = dict(selection, documents=[{k: v for k, v in d.items() if k != 'content'} for d in selection['documents']])
        inputs = dict(schema=INPUTS_SCHEMA, identity=identity, selection=stored, selection_sha256=digest(stored))
        write_json(inputs_path, inputs)
    timings['select'] = round(time.time() - t0, 3)
    inputs_pin = dict(path=str(inputs_path), **witness(inputs_path))
    t0 = time.time()
    built = build(selection, boundary_day, batch_days, run)
    timings['build'] = round(time.time() - t0, 3)
    t0 = time.time()
    cov = coverage(batch_days, built['candidates'], out, searches, brain_documents=len(selection['documents']))
    timings['coverage'] = round(time.time() - t0, 3)
    document = dict(schema=SCHEMA, run=run,
                    boundary=dict(day=boundary_day, batch_days=list(batch_days), sequence=built['counts']['previous_updates'] + 1,
                                  rule='a cross-day batch boundary keyed by its last day; a batch of one day is a boundary; '
                                       'consumed only by LATER classrooms (the boundary day\'s own classroom never sees it)'),
                    inputs=inputs_pin, selection_sha256=inputs['selection_sha256'],
                    candidates=built['candidates'], counts=built['counts'], previous=built['previous'],
                    untested_candidate_sources=built['untested_candidate_sources'],
                    listed=built['listed'] + list(selection.get('listed') or []) + cov['listed'],
                    integrity_failures=list(selection.get('integrity_failures') or []),
                    late_knowledge=dict(frozen=frozen, listed=late),
                    all99_coverage=dict(by_day=cov['by_day'], boundary=cov['boundary'], rule=cov['rule']),
                    rules=dict(status=STATUS_RULE, consumption='later classrooms only, through the brain entry <boundary day>-survivors; '
                                                               'never the boundary day\'s own classroom (no same-day circular promotion)',
                               missing_coverage='a day without a search or lessons is listed and the boundary continues; an unreadable or '
                                                'altered entry is an integrity failure listed apart; nothing waits for all days or all layers',
                               provenance='every test names its lessons file sha256, result index, part sha256, row ordinal and raw-line sha256; '
                                          'every candidate names its claim id, author, day made and statement'),
                    model_calls=0)
    data = (json.dumps(document, indent=1, sort_keys=True, default=str) + '\n').encode()
    doc_path = out / 'survivors.json'
    if doc_path.exists():
        if doc_path.read_bytes() != data:
            raise ValueError('%s exists with different bytes: the frozen selection must reproduce the same update' % doc_path)
        reused = True
    else:
        from frankie_box_durable import write_bytes
        write_bytes(doc_path, data)
        reused = False
    doc_pin = dict(path=str(doc_path), bytes=len(data), sha256=sha256_bytes(data))
    t0 = time.time()
    try:
        manifest, entry_reused = BR.write_stage_entry(brain, boundary_day, 'survivors', [doc_path],
                                                      summary=dict(run=run, boundary_day=boundary_day, counts=built['counts']),
                                                      inline_limit=max(len(data), 2 * 1024 * 1024))
        publication = dict(status='reused' if entry_reused else 'published', entry=str(Path(brain) / ('%s-survivors' % boundary_day)),
                           manifest_entries=[dict(name=e.get('name'), sha256=e.get('sha256'), bytes=e.get('bytes')) for e in manifest.get('entries') or []])
    except ValueError as error:
        # the brain holds another survivors document for this boundary day (an earlier update whose selection differed):
        # visible on the receipt, never overwritten; the next boundary carries everything this one found
        publication = dict(status='declined_existing_entry_differs', reason=str(error),
                           entry=str(Path(brain) / ('%s-survivors' % boundary_day)))
    timings['publish'] = round(time.time() - t0, 3)
    report = dict(
        schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='candidates',
        inputs=dict(run=run, boundary_day=boundary_day, batch_days=list(batch_days), brain=str(brain), frozen_selection=frozen,
                    operation_inputs=inputs_pin, roots=selection.get('roots'),
                    documents=[dict(label=d['label'], day=d['day'], kind=d['kind'], path=d['path'], sha256=d['sha256'],
                                    corrections_applied=len(d.get('corrections_applied') or [])) for d in selection['documents']],
                    searches=list(cov['by_day'])),
        use=dict(counts=built['counts'], listed=document['listed'], integrity_failures=document['integrity_failures'],
                 late_knowledge=document['late_knowledge'], previous_updates=built['previous'],
                 all99_coverage={d: pin.get('summary') for d, pin in cov['by_day'].items()}, all99_boundary=cov['boundary'],
                 phase_timings=timings, rules=document['rules']),
        outputs=dict(survivors=doc_pin, reused=reused, publication=publication,
                     all99_coverage_files={d: {k: v for k, v in pin.items() if k != 'summary'} for d, pin in cov['by_day'].items()},
                     candidates_by_status={k: built['counts'][k] for k in ('survivor_scoped', 'contradicted_scoped', 'open')}),
        seconds=round(time.time() - started, 3), model_calls=0)
    receipt = dict(schema=RECEIPT_SCHEMA, run=run, boundary_day=boundary_day, batch_days=list(batch_days), status='complete',
                   survivors=doc_pin, reused=reused, inputs=inputs_pin, counts=built['counts'], publication=publication,
                   listed=len(document['listed']), integrity_failures=len(document['integrity_failures']),
                   late_knowledge=len(late), all99_coverage=document['all99_coverage'], workflow_report=report,
                   model_calls=0, at=time.time())
    write_json(out / 'receipt.json', receipt)
    receipt['receipt'] = dict(path=str(out / 'receipt.json'), **witness(out / 'receipt.json'))
    log(json.dumps(receipt, sort_keys=True, default=str))
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--run', required=True)
    p.add_argument('--boundary-day', required=True, help='the batch boundary day (YYYYMMDD; the batch\'s last day in plan order)')
    p.add_argument('--days', required=True, help='comma list of the batch\'s days (one or more; the boundary day included)')
    p.add_argument('--brain', default='/opt/frankie-box/brain')
    p.add_argument('--out-dir', default=str(ROOT))
    p.add_argument('--search', action='append', default=[], metavar='DAY=DIR',
                   help='a completed search directory of a batch day (default <experiment-search>/<day>/cycle-00/discovery)')
    a = p.parse_args()
    if not re.fullmatch('[0-9]{8}', a.boundary_day) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run):
        p.error('--boundary-day YYYYMMDD and --run of letters, digits, _ and - required')
    days = [d for d in a.days.split(',') if d]
    if not days or any(not re.fullmatch('[0-9]{8}', d) for d in days) or len(set(days)) != len(days):
        p.error('--days needs one or more distinct YYYYMMDD days')
    if a.boundary_day not in days:
        p.error('the boundary day must be one of the batch days')
    searches = {}
    for item in a.search:
        day, sep, directory = item.partition('=')
        if not sep or day not in days or not Path(directory).is_absolute():
            p.error('--search needs DAY=ABSOLUTE_DIR for a batch day')
        searches[day] = directory
    update(a.run, a.boundary_day, days, a.brain, a.out_dir, searches=searches)
    return 0


if __name__ == '__main__':
    sys.exit(main())
