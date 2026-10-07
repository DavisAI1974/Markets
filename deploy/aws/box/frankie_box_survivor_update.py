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

The confirmation clock (Greg, 2026-10-07; registry entry clock_prospective_discovery_confirmation). The pinned native
producer records discovery only; the experiment's confirmation is this boundary's survivor_scoped event. Every held test
row of a survivor_scoped candidate on a day other than day_made gets one FRANKIE_DISCOVERY_CONFIRMATION_CLOCK_V1 record
inside the candidate (candidates[i].confirmations[j]): the claim, its discovery (day; an observed instant only when a
producer wrote one, else absent with the reason), the confirming test row (lessons sha256, result index, part, row
ordinal, raw-line sha256), the confirming day with its search and market pins (frozen with the selection), the boundary
and the brain entry it is committed in. A record first stamped at an earlier boundary is carried as previously stamped
(never new again); an earlier stamp no longer reproduced is listed withdrawn, never relabelled. contradicted_scoped and
open candidates get no record and are listed with status (document confirmation_clock; receipt confirmation_clock).
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
# The confirmation clock (Greg, 2026-10-07): the registry entry clock_prospective_discovery_confirmation. The pinned native
# producer (native_recognition.record_call) records the discovery instant only and computes no confirmation time; in the
# experiment confirmation is a defined event, this boundary marking a candidate survivor_scoped because it held on a day
# other than its own. One record per (candidate, held test row on another day): every confirming day individually, never
# pooled; one confirming day counts (R06). contradicted_scoped and open candidates get no record and are listed with status.
CLOCK_SCHEMA = 'FRANKIE_DISCOVERY_CONFIRMATION_CLOCK_V1'
CLOCK_LAYER = 'clock_prospective_discovery_confirmation'
# claim/source fields that would carry an observed discovery instant when a producer wrote one (read, never inferred)
DISCOVERY_CLOCK_FIELDS = ('discovery_clock', 'recognized_recv_ns', 'available_second', 'as_of_ts_recv_ns', 'through_cursor',
                          'known_at')
DISCOVERY_ABSENT = {
    'frankie': 'a Dipole novel finding carries schema, finding_id, premise, why_novel, evidence_refs and '
               'future_outcome_claimed only (dipole_classroom_final_review); no instant: discovery is the classroom of '
               'day_made, day level',
    'jev': 'the JEV_CLAIMS_V1 claim names its day and the file stamp, no per-claim instant: discovery is day level',
    'search': 'the discovery row is a whole-day coupling count (origin search manifest, part, row, raw-line sha256): it '
              'has no instant inside the day; discovery is day level',
    'historical': 'a catalog claim made before the experiment (no market day): discovery day and instant absent',
}
NATIVE_DISCOVERY_NOTE = ('native_recognition.record_call stamps recognized_recv_ns on the ROOT native lifecycle episode rows '
                         'of native candidate episodes; no experiment claim carries a binding to an episode, so that clock '
                         'is not linked to this claim (never matched by time, pair or similarity)')
CONFIRMATION_RULE = ('the confirmation clock is the stage-10 batch-boundary event (Greg, 2026-10-07): stamped when this '
                     'boundary finds a held test row of the candidate on a market day other than day_made; every confirming '
                     'row and day its own record, never pooled or averaged; one confirming day counts (R06); own-day, '
                     'origin and duplicate rows never confirm; contradicted_scoped and open candidates get no record; a '
                     'record first stamped at an earlier boundary is carried as previously stamped, never restamped as new; '
                     'nothing is backfilled to the discovery day or to the confirming day\'s instant')
CONFIRMATION_CONSUMERS = (
    'committed at this boundary in the brain entry <brain>/<boundary day>-survivors (survivors.json, inline); read through '
    'frankie_box_lane_state.learner_knowledge by every stage that runs AFTER the entry is written: the classroom '
    '(frankie_box_experiment_classroom_v2, stage classroom), the exchange (frankie_box_experiment_exchange and '
    'frankie_box_teacher_knowledge, stage exchange) and the meeting voice (frankie_box_granite_meeting, stage voice), of any '
    'day other than the boundary day (all days share completed knowledge regardless of market date, Greg 2026-10-06); the '
    'boundary day\'s own classroom, exchange and voice never see it (DAY_KINDS survivors 50 > classroom 0, exchange/voice '
    '40); the next survivor update reads it as previously stamped. The day reports read the receipt only (inspection, '
    'not knowledge).')


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


def confirmation_id(candidate, test):
    w = test.get('where') or {}
    return digest([candidate, test.get('day'), w.get('part_sha256'), w.get('row'), w.get('row_sha256')])[:16]


def discovery_of(author, claim, day_made):
    """The candidate's discovery as recorded: its own day and, when a producer wrote one, an observed discovery instant
    read from the claim, its source claim or its origin (field and address named); otherwise the instant is listed
    absent with the reason. Nothing is inferred or backfilled."""
    claim = claim if isinstance(claim, dict) else {}
    found = []
    for address, value in (('claim', claim), ('claim.source_claim', claim.get('source_claim')), ('claim.origin', claim.get('origin'))):
        if isinstance(value, dict):
            for field in DISCOVERY_CLOCK_FIELDS:
                if value.get(field) is not None:
                    found.append(dict(address=address, field=field, value=value.get(field)))
    origin = claim.get('origin') if isinstance(claim.get('origin'), dict) else None
    return dict(day=day_made, day_status='present' if day_made is not None else 'absent',
                day_reason=None if day_made is not None else DISCOVERY_ABSENT.get(author, 'no day_made recorded on the claim'),
                instant=dict(status='present', values=found) if found else
                dict(status='absent', reason=DISCOVERY_ABSENT.get(author, 'the claim carries no discovery instant field')),
                origin_row=({k: origin.get(k) for k in ('day', 'search_manifest_sha256', 'part', 'part_sha256', 'row', 'row_sha256')}
                            if origin else None),
                native_record=NATIVE_DISCOVERY_NOTE)


def search_markets(documents):
    """The confirming days' market reads, keyed by search manifest sha256: for every search a selected lessons file
    names (day, cycle, dir, manifest_sha256), its MANIFEST.json read and verified against that pin; recorded are the
    axis (F_LAST group closes), the frames spool pin and the export manifest pin. Frozen with the selection, so a restart
    computes on the same reads. An unreadable manifest is listed unavailable; bytes that differ from the lessons' pin are
    an integrity failure, listed apart; neither blocks anything but its own record field."""
    wanted = {}
    for document in documents:
        docs, _ = lessons_in(document)
        for doc, _where in docs:
            if doc.get('schema') not in LESSONS:
                continue
            for s in doc.get('searches') or []:
                if isinstance(s, dict) and s.get('manifest_sha256'):
                    wanted.setdefault(s['manifest_sha256'], dict(day=s.get('day'), cycle=s.get('cycle'), dir=s.get('dir')))
    out = {}
    for sha, s in sorted(wanted.items()):
        path = Path(str(s.get('dir') or '')) / 'MANIFEST.json'
        base = dict(search=dict(s, manifest_sha256=sha, path=str(path)))
        try:
            raw = path.read_bytes()
        except OSError as error:
            out[sha] = dict(base, status='unavailable', reason='the search manifest could not be read (%s): the confirming '
                                                               'day\'s market pin is unknown, the record stays' % error)
            continue
        if sha256_bytes(raw) != sha:
            out[sha] = dict(base, status='integrity_failure', found_sha256=sha256_bytes(raw),
                            reason='the search manifest bytes differ from the lessons file\'s pin: a separate visible '
                                   'failure, never read as the confirming day\'s market')
            continue
        try:
            manifest = json.loads(raw)
        except ValueError as error:
            out[sha] = dict(base, status='integrity_failure', reason='unreadable search manifest JSON: %s' % error)
            continue
        frames = next((x for x in manifest.get('sources') or [] if isinstance(x, dict) and x.get('source') == 'frames'), None)
        axis = next((n for n in manifest.get('notes') or [] if isinstance(n, dict) and 'axis' in n), None)
        rows = frames.get('rows') if frames else None
        out[sha] = dict(base, status='read', day=manifest.get('day'), cycle=manifest.get('cycle'), day_role=manifest.get('day_role'),
                        data_manifest_sha256=manifest.get('data_manifest_sha256'),
                        frames=({k: frames.get(k) for k in ('path', 'bytes', 'sha256', 'rows')} if frames else None),
                        axis=axis,
                        through_group_close_ordinal=(rows - 1 if isinstance(rows, int) and rows > 0 else None),
                        last_receive_clock_ns=None,
                        last_receive_clock_reason='the search manifest records the axis group count and the frames spool '
                                                  'pin, not the axis end clock; a coupling row counts over the whole '
                                                  'searched day, so its evidence is complete only through the day\'s last '
                                                  'searched group close (through_group_close_ordinal)')
    return out


def confirmations(candidates, lesson_searches, markets, previously_stamped, boundary_day, batch_days, sequence):
    """FRANKIE_DISCOVERY_CONFIRMATION_CLOCK_V1 records, inside each survivor_scoped candidate ('confirmations'), one per
    held test row on another day; every candidate gets 'confirmation_clock' (stamped_at_boundary or discovery only); the
    returned index lists every candidate with its status and every earlier stamp no longer reproduced."""
    stamped, not_stamped, current_ids = [], [], set()
    new = carried = 0
    for c in candidates:
        records = []
        if c['status'] == 'survivor_scoped':
            for t in c['tests']:
                if t.get('mark') != 'held':
                    continue
                cid = confirmation_id(c['candidate'], t)
                current_ids.add(cid)
                w = t.get('where') or {}
                search = (lesson_searches.get(t.get('lesson_sha256')) or {}).get(t.get('day'))
                market = markets.get((search or {}).get('manifest_sha256')) if search else None
                prior = previously_stamped.get(cid) or []
                first = sorted(prior, key=lambda p: (str(p.get('boundary')), str(p.get('survivors_sha256'))))[0] if prior else None
                new += 0 if prior else 1
                carried += 1 if prior else 0
                records.append(dict(
                    schema=CLOCK_SCHEMA, layer=CLOCK_LAYER, confirmation_id=cid,
                    claim=dict(candidate=c['candidate'], claim_id=c['claim_id'], author=c['author'], day_made=c['day_made'],
                               statement_sha256=sha256_bytes(str(c.get('statement') or '').encode())),
                    discovery=c['discovery'],
                    confirming_test=dict(lesson_sha256=t.get('lesson_sha256'), lesson_path=t.get('lesson_path'),
                                         result_index=t.get('result_index'), part=w.get('part'),
                                         part_sha256=w.get('part_sha256'), row=w.get('row'), row_sha256=w.get('row_sha256'),
                                         mark='held', x=t.get('x'), y=t.get('y'), cell=t.get('cell'),
                                         cell_value=t.get('cell_value'), lag=t.get('lag'), x_transform=t.get('x_transform'),
                                         y_transform=t.get('y_transform'), counts=t.get('counts'),
                                         chance_check=t.get('chance_check')),
                    confirming_day=dict(
                        day=t.get('day'),
                        # all days share completed knowledge regardless of market date (Greg, 2026-10-06): a confirming
                        # day may precede the discovery day in market time; said explicitly, never passed as prospective
                        market_order=('later_market_date' if c['day_made'] and str(t.get('day')) > str(c['day_made']) else
                                      'earlier_market_date' if c['day_made'] and str(t.get('day')) < str(c['day_made']) else
                                      'unknown: no discovery day recorded'),
                        search=search if search else None,
                        search_reason=None if search else 'the lessons file does not name a search for this day',
                        market=({k: v for k, v in market.items() if k != 'search'} if market else
                                dict(status='unavailable', reason='no search manifest pin for this day in the lessons file'
                                     if not search else 'the search manifest was not captured in the frozen selection'))),
                    boundary=dict(day=boundary_day, batch_days=list(batch_days), sequence=sequence),
                    committed_in=dict(entry='<brain>/%s-survivors' % boundary_day, stage='survivors', file='survivors.json',
                                      pin='the survivors.json pin and the brain entry manifest are on this update\'s receipt '
                                          '(survivors, publication); a document cannot carry its own sha256'),
                    clock=dict(event='stage10_batch_boundary', stamped_at_boundary=boundary_day,
                               new_at_this_boundary=not prior,
                               first_stamped=(dict(boundary=first.get('boundary'), survivors_sha256=first.get('survivors_sha256'))
                                              if first else dict(boundary=boundary_day, survivors_sha256=None)),
                               previously_stamped=prior,
                               knowable_from='the first classroom, exchange or voice that reads the brain after this entry '
                                             'is written, of a day other than the boundary day; never the same day'),
                    rule=CONFIRMATION_RULE))
            c['confirmations'] = records
            c['confirmation_clock'] = dict(status='stamped_at_boundary', records=len(records),
                                           confirming_days=sorted({r['confirming_day']['day'] for r in records}),
                                           new_at_this_boundary=sum(1 for r in records if r['clock']['new_at_this_boundary']))
            stamped.append(dict(candidate=c['candidate'], claim_id=c['claim_id'], author=c['author'],
                                confirmation_ids=[r['confirmation_id'] for r in records],
                                confirming_days=c['confirmation_clock']['confirming_days']))
        else:
            c['confirmations'] = []
            c['confirmation_clock'] = dict(status='discovery_only_no_confirmation', records=0,
                                           reason='status %s: no held test row on a day other than day_made' % c['status'])
            not_stamped.append(dict(candidate=c['candidate'], claim_id=c['claim_id'], author=c['author'], status=c['status'],
                                    reason=c['confirmation_clock']['reason']))
    withdrawn = [dict(confirmation_id=cid, previously_stamped=prior,
                      reason='stamped at an earlier boundary and no longer a held test row in the current lessons (a checked '
                             'correction or successor changed it): the earlier stamp stays in its own survivors entry, '
                             'visible, never relabelled or restamped')
                 for cid, prior in sorted(previously_stamped.items()) if cid not in current_ids]
    records_total = sum(len(s['confirmation_ids']) for s in stamped)
    return dict(schema=CLOCK_SCHEMA, layer=CLOCK_LAYER,
                status='stamped_at_boundary' if records_total else 'discovery_only_no_confirmation',
                reason=None if records_total else 'no survivor_scoped candidate at this boundary: discovery only, no confirmation yet',
                stamped=stamped, not_stamped=not_stamped, withdrawn_since_previous=withdrawn,
                counts=dict(records=records_total, new_at_this_boundary=new, previously_stamped=carried,
                            candidates_stamped=len(stamped), candidates_not_stamped=len(not_stamped),
                            withdrawn_since_previous=len(withdrawn)),
                consumers=CONFIRMATION_CONSUMERS, rule=CONFIRMATION_RULE,
                records_at='candidates[i].confirmations[j] of this document')


def build(selection, boundary_day, batch_days, run):
    """The candidates and their tests from the frozen selection; previous updates read for previously_known."""
    candidates, previous_docs, untested_sources, listed = {}, [], [], []
    test_keys_seen = {}
    lesson_searches = {}      # lessons sha256 -> {day: the search it names for that day (day, cycle, dir, manifest_sha256)}
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
            lesson_searches.setdefault(where['sha256'], {}).update(
                {s.get('day'): dict(day=s.get('day'), cycle=s.get('cycle'), dir=s.get('dir'), manifest_sha256=s.get('manifest_sha256'))
                 for s in doc.get('searches') or [] if isinstance(s, dict)})
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
                    untested=[], cannot_test_yet=[], challenges=[], lessons=[], dispositions_given={},
                    discovery=discovery_of(author, claim, r.get('day_made'))))
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
    previous_known, previously_stamped = {}, {}
    for prev in previous_docs:
        for c in prev['content'].get('candidates') or []:
            for record in c.get('confirmations') or []:
                if isinstance(record, dict) and record.get('confirmation_id'):
                    previously_stamped.setdefault(record['confirmation_id'], []).append(dict(
                        boundary=(prev['content'].get('boundary') or {}).get('day'), survivors_sha256=prev['sha256']))
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
                untested_candidate_sources=untested_sources, listed=listed, lesson_searches=lesson_searches,
                previously_stamped=previously_stamped)


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
        if 'search_markets' not in selection:
            # a selection frozen before the confirmation clock existed: the confirming days' market reads are taken now,
            # each still verified against its lessons pin, and said so (never presented as frozen)
            selection['search_markets'] = search_markets(selection['documents'])
            selection['search_markets_captured'] = 'after_freeze: the frozen selection predates the confirmation clock'
    else:
        selection = select(brain, boundary_day)
        selection['search_markets'] = search_markets(selection['documents'])
        selection['search_markets_captured'] = 'with_selection'
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
    clock_index = confirmations(built['candidates'], built['lesson_searches'], selection.get('search_markets') or {},
                                built['previously_stamped'], boundary_day, batch_days, built['counts']['previous_updates'] + 1)
    clock_index['search_markets_captured'] = selection.get('search_markets_captured')
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
                    confirmation_clock=clock_index,
                    rules=dict(status=STATUS_RULE, confirmation_clock=CONFIRMATION_RULE, consumption='later classrooms only, through the brain entry <boundary day>-survivors; '
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
    # the confirmation clock as committed: stamped only when the brain entry holds this document (published or reused);
    # a declined publication leaves the records on survivors.json only, visible, never presented as committed
    committed = publication.get('status') in ('published', 'reused')
    clock_summary = dict(layer=CLOCK_LAYER, schema=CLOCK_SCHEMA,
                         status=(clock_index['status'] if committed or clock_index['status'] != 'stamped_at_boundary'
                                 else 'stamped_not_committed'),
                         reason=(clock_index['reason'] if committed or clock_index['status'] != 'stamped_at_boundary' else
                                 'the brain entry %s holds another survivors document (%s): the records are on survivors.json '
                                 'only and no later classroom reads them' % (publication.get('entry'), publication.get('status'))),
                         committed=committed, entry=publication.get('entry'), survivors=doc_pin,
                         entry_manifest=publication.get('manifest_entries'), counts=clock_index['counts'],
                         stamped=clock_index['stamped'], not_stamped=clock_index['not_stamped'],
                         withdrawn_since_previous=clock_index['withdrawn_since_previous'],
                         search_markets_captured=clock_index.get('search_markets_captured'),
                         records_at='survivors.json candidates[i].confirmations[j]', consumers=CONFIRMATION_CONSUMERS)
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
                     candidates_by_status={k: built['counts'][k] for k in ('survivor_scoped', 'contradicted_scoped', 'open')},
                     confirmation_clock=clock_summary),
        seconds=round(time.time() - started, 3), model_calls=0)
    receipt = dict(schema=RECEIPT_SCHEMA, run=run, boundary_day=boundary_day, batch_days=list(batch_days), status='complete',
                   survivors=doc_pin, reused=reused, inputs=inputs_pin, counts=built['counts'], publication=publication,
                   listed=len(document['listed']), integrity_failures=len(document['integrity_failures']),
                   late_knowledge=len(late), all99_coverage=document['all99_coverage'], confirmation_clock=clock_summary,
                   workflow_report=report,
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
