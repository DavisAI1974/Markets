"""Frankie's SCHOOL KNOWLEDGE BASE: one JSON file per classroom-arm day, and the append-only index (Greg, 2026-09-29).

Written after the day's exchange (the orchestrator's 'school' stage), starting with the first school day (Monday
20211004 is out of scope). ONE file, FRANKIE_SCHOOL_KNOWLEDGE_V1, at <brain>/school/<day>.json, plus its row in the
append-only <brain>/school/index.json (day, file, sha256, bytes, report number N), both through
frankie_box_brain.write_school_day. The brain loader (frankie_box_brain.load) and the next classroom day
(frankie_box_experiment_classroom_v2, Frankie's code: school_reproduction) read every EARLIER day's file, checked against
its index row.

Every section is labelled with its author (R11); every item names its source path and sha256 (source_sha256). An item is
the whole JSON file inline when the step already wrote it as JSON of at most INLINE_MAX bytes (sha256 = the file's), a
stated subset of it (sha256 = the subset's own canonical bytes, source_sha256 = the file's; the subset says what it holds
and why), or a pointer (path, sha256, bytes; never read into the corpus) for anything larger or not JSON:
  frankie_classwork   (Frankie's code) his classroom code answers (the 19 components, the summary), his ledgers (the 171
                      pairs), his external-section answers, his novel findings, the corrections he received (the ids and
                      the teacher's worded messages, "the data is showing this instead": WHERE he was corrected, R10), his
                      correction answers and the validated acknowledgements, the completions and the mode;
  boss_teacher        the teacher's measurements used that day: its Dipole rows (pointer) and their receipt, the teacher
                      key's hash (its content withheld, R10), the external key's hash, its investigation of his novel
                      findings, and the targets, masks and controls it named in the exchange;
  scientific_teacher  the FRANKIE_LESSONS_V1 of the day (per claim, per day counts; the disposition word orientation only,
                      R14) and its untested / cannot-test-yet lists;
  exchange            Frankie's view of the three-way exchange (the turns, the teachers' own findings scoped with their
                      days named), and the entire receipt-verified meeting discussion inline, without a size cutoff;
                      its four categories remain separate and have no evidentiary authority;
  day_file            the 13-point day file by reference (name, sha256, bytes, path, S3 key).
Kept out, each listed under withheld with the reason: the exhaustive grades (post-grade.json, external-post-grade.json)
and the answer key's content (R10), Jev's claims (the lessons wall). Whatever is absent is listed under missing with the
reason, never dropped (R04). The document holds no clock, so a restart reproduces the same bytes; other bytes for a day
already in the index decline (R16). Counts, never averages. No model call.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BOX = Path(__file__).resolve().parent
sys.path.insert(0, str(BOX.parents[2]))
sys.path.insert(0, str(BOX))
SCHEMA = 'FRANKIE_SCHOOL_KNOWLEDGE_V1'
RECEIPT_SCHEMA = 'FRANKIE_SCHOOL_KNOWLEDGE_RECEIPT_V1'
INLINE_MAX = 8 * 1024 * 1024
MONDAY = '20211004'
FRANKIE = "Frankie's code (computed; no model)"
BOSS = "the BOSS teacher's code (JournalTeacherR3 rows, the classroom package, the teacher key; no model)"
SCIENCE = "the scientific teacher's code (the experiment's search; no model)"
EXCHANGE = 'the three-way exchange (each turn labelled with its author)'
DAY_FILE = 'the day file of the 13 historical data points (FRANKIE_DAY_EXTERNAL_V1)'
TEACHER_ROWS_FILE = 'host-dipole-classroom-source.c15.json'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')


class Section:
    def __init__(self, name, author, missing):
        self.name, self.author, self.items, self.missing = name, author, [], missing

    def whole(self, name, path, *, author=None, why=None):
        """The whole JSON file inline (at most INLINE_MAX bytes), else a pointer; absent -> missing with the reason."""
        path = Path(path) if path else None
        if path is None or not path.is_file():
            self.missing.append(dict(section=self.name, item=name, path=str(path) if path else None,
                                     reason=why or 'the file is not there (%s)' % path))
            return None
        data = path.read_bytes()
        base = dict(name=name, author=author or self.author, path=str(path), sha256=sha256_bytes(data),
                    source_sha256=sha256_bytes(data), bytes=len(data))
        if len(data) > INLINE_MAX or path.suffix != '.json':
            self.items.append(dict(base, inline=False, pointer_reason=(
                'larger than %d bytes' % INLINE_MAX if len(data) > INLINE_MAX else 'not a JSON file')))
            return None
        value = json.loads(data)
        self.items.append(dict(base, inline=True, content=value))
        return value

    def subset(self, name, path, content, holds, *, author=None):
        """A stated subset of a file the step wrote: sha256 of the subset's own bytes, source_sha256 of the file."""
        data = Path(path).read_bytes() if path and Path(path).is_file() else None
        self.items.append(dict(name=name, author=author or self.author, path=str(path) if path else None,
                               source_sha256=sha256_bytes(data) if data is not None else None,
                               sha256=sha256_bytes(canonical(content)), bytes=len(canonical(content)),
                               inline=True, holds=holds, content=content))

    def pointer(self, name, path, why, *, author=None, extra=None):
        path = Path(path) if path else None
        if path is None or not path.is_file():
            self.missing.append(dict(section=self.name, item=name, path=str(path) if path else None,
                                     reason='the file is not there (%s)' % path))
            return
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(64 * 1024 * 1024), b''):
                h.update(block)
        self.items.append(dict(name=name, author=author or self.author, path=str(path), sha256=h.hexdigest(),
                               source_sha256=h.hexdigest(), bytes=path.stat().st_size, inline=False, pointer_reason=why,
                               **(extra or {})))

    def body(self, label):
        return dict(author=self.author, author_label=label, items=self.items)


def corrections(value):
    """WHERE he was corrected (R10): the correction ids, each item's id, kind and the teacher's worded message, and the
    root-cause groups; the rest of the request (the data shown per subclaim, the post-grade hash) is named by the file's
    sha256 and not carried."""
    return dict(correction_ids=list(value.get('correction_ids') or []),
                items=[{k: i.get(k) for k in ('correction_id', 'kind', 'message')} for i in value.get('data_review_items') or []],
                root_cause_groups=list(value.get('root_cause_groups') or []))


def build(day, run, report_number, classroom, exchange_view, exchange_listed, lessons, teacher_rows, rules_witness):
    missing, withheld = [], []
    classroom = Path(classroom)
    receipt_path = classroom / 'receipt.json'
    receipt = json.loads(receipt_path.read_bytes()) if receipt_path.is_file() else {}
    status = receipt.get('status')

    # ---- Frankie's classwork
    fw = Section('frankie_classwork', 'frankie', missing)
    fw.subset('classroom_receipt', receipt_path, {k: receipt.get(k) for k in (
        'day', 'status', 'mode', 'reason', 'listed', 'components', 'observations', 'pairs', 'novel_findings',
        'dropped_findings', 'correction_ids', 'teacher_complete', 'completion_hash', 'carried_from_previous',
        'school_knowledge')}, 'the classroom receipt\'s status, mode (TEACH / GUIDED / SOCRATIC / VERIFY), counts and '
                              'the school days it read; the brain manifest and paths are not repeated')
    if status != 'complete':
        missing.append(dict(section='frankie_classwork', item='answers, corrections, completion',
                            reason='the classroom was %s on this day: %s' % (status or 'not run', receipt.get('reason'))))
    else:
        for name, file in (('code_answers', 'code-answers.json'), ('ledgers', 'ledgers.json'),
                           ('external_answers', 'external-code-answers.json'), ('novel_findings', 'novel-findings.json'),
                           ('correction_answers', 'correction-response.json'), ('acknowledgement', 'acknowledgement.json'),
                           ('external_correction_answers', 'external-correction-response.json'),
                           ('external_acknowledgement', 'external-acknowledgement.json'), ('completion', 'completion.json'),
                           ('external_completion', 'external-completion.json')):
            fw.whole(name, classroom / file)
        for name, file in (('corrections_received', 'correction-request.json'),
                           ('external_corrections_received', 'external-correction-request.json')):
            path = classroom / file
            if path.is_file():
                fw.subset(name, path, corrections(json.loads(path.read_bytes())),
                          'the correction ids, kinds and the teacher\'s worded messages ("the data is showing this instead"): '
                          'WHERE he was corrected (R10)', author='boss_teacher')
            else:
                missing.append(dict(section='frankie_classwork', item=name, path=str(path), reason='the file is not there'))
        for file in ('post-grade.json', 'external-post-grade.json'):
            withheld.append(dict(section='frankie_classwork', item=file, path=str(classroom / file),
                                 reason='the exhaustive grade: graded outcomes stay out of the lesson material (R10)'))

    # ---- the BOSS teacher
    bt = Section('boss_teacher', 'boss_teacher', missing)
    rows_dir = Path(teacher_rows) if teacher_rows else None
    bt.pointer('dipole_rows', rows_dir / TEACHER_ROWS_FILE if rows_dir else None,
               'the teacher\'s Dipole rows of the day (large; read by the teachers and the search, never copied)')
    bt.whole('teacher_rows_receipt', rows_dir / 'receipt.json' if rows_dir else None)
    key_path = classroom / 'package.teacher_key.c15.json'
    if key_path.is_file():
        from research.kalshi.frankie_boss.c15_journal import unpack
        key = unpack(json.loads(key_path.read_bytes()))
        bt.subset('teacher_key_identity', key_path, {k: key.get(k) for k in (
            'schema', 'teacher_key_hash', 'source_snapshot_hash', 'teacher_attachment_hash', 'coverage_count',
            'relationship_pairs_scanned')}, 'the teacher key by its hashes and coverage; its content (every value and '
                                            'relation) is withheld (R10: never the answer key)')
        withheld.append(dict(section='boss_teacher', item='package.teacher_key.c15.json (content)', path=str(key_path),
                             reason='the answer key: only its hash travels (R10)'))
    else:
        missing.append(dict(section='boss_teacher', item='teacher_key_identity', path=str(key_path),
                            reason='no teacher key in the classroom directory (classroom %s)' % (status or 'not run')))
    ext = receipt.get('external') or {}
    if ext:
        bt.subset('external_key_identity', receipt_path, dict(external_key_hash=ext.get('external_key_hash'),
                                                              completion_hash=ext.get('completion_hash'),
                                                              series=ext.get('series'), rows=ext.get('rows')),
                  'the external section\'s key by its hash (content withheld, R10)')
    bt.whole('novelty_investigation', classroom / 'novelty-investigation.json',
             why='no novelty investigation (classroom %s)' % (status or 'not run'))
    view = json.loads(Path(exchange_view).read_bytes()) if exchange_view and Path(exchange_view).is_file() else None
    if view is not None:
        named = [dict(item_id=i['item_id'], author=i['author'], position=t['record']['position'],
                      measured=t.get('measured'), proposals=t.get('proposals'))
                 for i in view.get('items') or [] for t in i.get('turns') or [] if t.get('seat') == 'boss_teacher']
        bt.subset('exchange_measurements', exchange_view, named,
                  'the targets, masks and controls the BOSS teacher named in the exchange (its turns, per item)')

    # ---- the scientific teacher
    sc = Section('scientific_teacher', 'scientific_teacher', missing)
    doc = sc.whole('frankie_lessons', lessons, why='no FRANKIE_LESSONS_V1 of this day (no novel findings of his were '
                                                   'tested, or the lessons step has not run for them)')
    if doc is not None:
        sc.subset('untested', lessons, [dict(claim_id=r.get('claim_id'), untested=r.get('untested') or [],
                                             cannot_test_yet=r.get('cannot_test_yet') or []) for r in doc.get('results') or []],
                  'per claim, the untested combinations and what cannot be tested yet (listed, never dropped: R13)')
    withheld.append(dict(section='scientific_teacher', item='JEV_LESSONS_V1',
                         reason='Jev\'s claims stay out of Frankie\'s brain (the lessons wall)'))

    # ---- the exchange
    ex = Section('exchange', 'the three seats', missing)
    if view is not None:
        ex.whole('exchange_frankie_view', exchange_view)
    else:
        missing.append(dict(section='exchange', item='exchange_frankie_view', path=exchange_view,
                            reason=exchange_listed or 'the day\'s exchange is not there'))
    if view is not None:
        from frankie_box_brain import read_meeting_for_exchange
        meeting = read_meeting_for_exchange(exchange_view)
    else:
        meeting = dict(status='missing', record=None, path=None, receipt=None,
                       reason=exchange_listed or "the day's Frankie exchange is not there")
    if meeting['status'] == 'complete':
        # Use the already verified record, not a second unverified file read. Keep every category and item intact.
        pin = meeting['receipt']['record']
        ex.items.append(dict(name='discussion (meeting)', author='the three code seats and Granite coordinator',
                             path=meeting['path'], source_sha256=pin['sha256'], sha256=pin['sha256'],
                             bytes=pin['bytes'], inline=True, content=meeting['record'],
                             evidentiary_authority='none; discussion only; original code-seat evidence remains authoritative',
                             category_rule='seat_statements, coordinator_turns, code_seat_answers, and '
                                           'open_items/requested_tests stay separate; requested tests are not results'))
    else:
        missing.append(dict(section='exchange', item='discussion (meeting)', status=meeting['status'],
                            path=meeting.get('path'), reason=meeting.get('reason') or
                            'meeting %s; no completed discussion' % meeting['status'],
                            refused_to_run=(meeting.get('record') or {}).get('refused_to_run') or []))

    # ---- the day file
    df = Section('day_file', 'the day file', missing)
    day_file = ext.get('day_file') or {}
    if day_file.get('path'):
        s3 = None
        if day_file.get('receipt') and Path(day_file['receipt']).is_file():
            s3 = json.loads(Path(day_file['receipt']).read_bytes()).get('s3_key')
        df.pointer('day_external', day_file['path'], 'the day file is read through its as-of reader at a cutoff, never '
                                                     'copied into the corpus', extra=dict(s3_key=s3,
                                                                                          recorded_sha256=day_file.get('sha256')))
    else:
        missing.append(dict(section='day_file', item='day_external', reason='the classroom receipt names no day file '
                                                                            '(classroom %s)' % (status or 'not run')))

    sections = dict(frankie_classwork=fw.body(FRANKIE), boss_teacher=bt.body(BOSS), scientific_teacher=sc.body(SCIENCE),
                    exchange=ex.body(EXCHANGE), day_file=df.body(DAY_FILE))
    return dict(schema=SCHEMA, day=day, run=run, report_number=report_number, classroom_status=status,
                written_by="the school step's code (no model)", rules=rules_witness, sections=sections,
                missing=missing, withheld=withheld, model_calls=0,
                rule='each section labelled with its author (R11); counts per day, never pooled or averaged (R04, R05); '
                     'only WHERE Frankie was corrected, never the answer key or the exhaustive grade (R10)')


def _successor_projection(before, records, meeting=None):
    """Only copied sources and their existing school projections may change."""
    import frankie_box_experiment_review as R
    after = json.loads(json.dumps(before))
    consumed = set()
    changed_exchange = None
    for section, body in after['sections'].items():
        for item in body['items']:
            if item['name'] == 'discussion (meeting)':
                continue
            cursor = item.get('source_sha256') or item.get('sha256')
            links = []
            while cursor in records:
                link = records[cursor]
                links.append(link)
                consumed.add(link['record']['sha256'])
                cursor = link['replacement']['sha256']
            if not links:
                continue
            pin = links[-1]['replacement']
            doc = json.loads(R._read_pin(pin))
            if not item.get('inline') and (section, item['name']) in (
                    ('scientific_teacher', 'frankie_lessons'), ('exchange', 'exchange_frankie_view')):
                if item['sha256'] != links[0]['original']['sha256']:
                    raise ValueError('school pointer differs from its checked original source')
                item.update(path=links[-1]['body']['replacement']['path'], source_sha256=pin['sha256'],
                            sha256=pin['sha256'], bytes=pin['bytes'])
                if section == 'exchange':
                    changed_exchange = (links[0]['original'], pin, doc)
                continue
            if item.get('inline') and 'holds' not in item:
                if item['sha256'] != links[0]['original']['sha256']:
                    raise ValueError('school copied source differs from its correction identity')
                if canonical(item['content']) != canonical(json.loads(R._read_pin(links[0]['original']))):
                    raise ValueError('school inline source differs from its checked original')
                content, digest, size = doc, pin['sha256'], pin['bytes']
            elif section == 'boss_teacher' and item['name'] == 'exchange_measurements':
                content = [dict(item_id=i['item_id'], author=i['author'], position=t['record']['position'],
                                measured=t.get('measured'), proposals=t.get('proposals'))
                           for i in doc.get('items') or [] for t in i.get('turns') or []
                           if t.get('seat') == 'boss_teacher']
                digest, size = sha256_bytes(canonical(content)), len(canonical(content))
            elif section == 'scientific_teacher' and item['name'] == 'untested':
                content = [dict(claim_id=r.get('claim_id'), untested=r.get('untested') or [],
                                cannot_test_yet=r.get('cannot_test_yet') or []) for r in doc.get('results') or []]
                digest, size = sha256_bytes(canonical(content)), len(canonical(content))
            else:
                raise ValueError('school source needs its specific owner projection: ' + item['name'])
            item.update(path=links[-1]['body']['replacement']['path'], source_sha256=pin['sha256'], sha256=digest, bytes=size,
                        inline=True, content=content)
            if section == 'exchange' and item['name'] == 'exchange_frankie_view':
                changed_exchange = (links[0]['original'], pin, doc)
    meetings = [i for i in after['sections']['exchange']['items'] if i['name'] == 'discussion (meeting)']
    if changed_exchange and meetings:
        original, replacement, view = changed_exchange
        if len(meetings) != 1 or meetings[0]['content']['exchange']['sha256'] != original['sha256']:
            raise ValueError('school discussion is not bound to its original exchange')
        if (meeting is None or meeting['content'].get('status') != 'complete'
                or meeting['content'].get('day') != before['day'] or meeting['content'].get('run') != before['run']
                or meeting['content']['exchange'].get('sha256') != replacement['sha256']
                or meeting['content']['exchange'].get('exchange_hash') != view['exchange_hash']):
            raise ValueError('school successor awaits the completed meeting for its corrected exchange')
        expected = dict(meetings[0])
        expected.update({k: meeting[k] for k in ('path', 'source_sha256', 'sha256', 'bytes', 'content')})
        if meeting != expected:
            raise ValueError('school successor changed meeting attribution or evidentiary authority')
        meetings[0].update(meeting)
    elif meeting is not None:
        raise ValueError('school successor supplied an unrelated replacement meeting')
    if not consumed or after == before:
        raise ValueError('school successor needs an affected checked source')
    return after, consumed


def retained_school(brain, day):
    """Return the indexed original and its explicit published successor; never rewrite on read."""
    import frankie_box_brain as BR
    import frankie_box_experiment_review as R
    import frankie_box_lane_state as LS
    rows = [r for r in BR._school_index(brain)['rows'] if r['day'] == day]
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError('school owner has ambiguous indexed originals')
    row = rows[0]
    pin = dict(path=str(Path(brain) / BR.SCHOOL_DIR / row['file']), bytes=row['bytes'], sha256=row['sha256'])
    records = R.corrections(LS.knowledge_roots(brain))
    R._read_pin(pin)
    seen = []
    while pin['sha256'] in records:
        record = records[pin['sha256']]
        if record['body'].get('school_transition') is None:
            raise ValueError('school successor is missing its owner operation')
        seen.append(record['record'])
        pin = record['replacement']
    doc = json.loads(R._read_pin(pin))
    stale = set()
    for section in doc['sections'].values():
        for item in section['items']:
            if item.get('source_sha256') in records or item.get('sha256') in records:
                stale.add(item.get('source_sha256') or item['sha256'])
            if item.get('inline'):
                stale.update((R.references(item['content']) & set(records)) - R._ancestors(item['sha256'], records))
    return dict(row=row, original=pin, content=doc, corrections=seen,
                status='requires_successor' if stale else 'complete')


def rebuild_successor(day, run, brain, *, original_school, exchange_view=None):
    """Retain an explicit school successor on its original owner, after the new meeting completes.

    Reuses the original container, rules, classroom work and author walls. Only checked source
    copies and their existing projections change. No model/scientific execution occurs here.
    """
    import fcntl
    import frankie_box_brain as BR
    import frankie_box_experiment_review as R
    import frankie_box_lane_state as LS
    from frankie_box_durable import write_json, witness
    before = json.loads(R._read_pin(original_school))
    records = R.corrections(LS.knowledge_roots(brain))
    prior = records.get(original_school['sha256'])
    if prior is not None:
        completed = prior['body'].get('school_transition') or {}
        operation = completed.get('operation') or {}
        if (completed.get('original_school') != original_school or operation.get('day') != day
                or operation.get('run') != run or operation.get('brain') != str(Path(brain).resolve())):
            raise ValueError('school retry belongs to another retained owner operation')
        path = Path(brain) / 'school' / 'successors' / day / completed['operation_sha256'] / 'receipt.json'
        if json.loads(path.read_bytes()) != completed:
            raise ValueError('school retry lost its original completed receipt')
        R._read_pin(completed['school'])
        return dict(completed, receipt=dict(path=str(path), **witness(path)), correction=prior['record'])
    retained = retained_school(brain, day)
    if (retained is None or retained['original'] != original_school or before != retained['content']
            or before.get('schema') != SCHEMA or before.get('day') != day or before.get('run') != run
            or retained['row']['run'] != run):
        raise ValueError('school successor must own the original indexed day/run/brain')
    records = R.corrections(LS.knowledge_roots(brain))
    old_meetings = [i for i in before['sections']['exchange']['items'] if i['name'] == 'discussion (meeting)']
    meeting, meeting_receipt = None, None
    if old_meetings and old_meetings[0]['content']['exchange']['sha256'] in records:
        if not exchange_view:
            raise ValueError('school successor requires the corrected owner exchange')
        found = BR.read_meeting_for_exchange(exchange_view)
        if found['status'] != 'complete':
            raise ValueError('school successor awaits the completed corrected meeting: ' + found['status'])
        meeting = dict(old_meetings[0], path=found['path'], content=found['record'],
                       source_sha256=found['receipt']['record']['sha256'],
                       sha256=found['receipt']['record']['sha256'], bytes=found['receipt']['record']['bytes'])
        path = BR.meeting_directory(exchange_view) / 'receipt.json'
        meeting_receipt = dict(path=str(path), **witness(path))
    after, consumed = _successor_projection(before, records, meeting)
    source_corrections = sorted((r['record'] for r in records.values() if r['record']['sha256'] in consumed),
                                key=lambda p: p['sha256'])
    operation = dict(schema='FRANKIE_SCHOOL_SUCCESSOR_OPERATION_V1', day=day, run=run,
                     brain=str(Path(brain).resolve()), original_school=original_school,
                     source_corrections=source_corrections, meeting_receipt=meeting_receipt,
                     producer_sha256=sha256_bytes(Path(__file__).read_bytes()))
    operation_sha = R.digest(R.canonical(operation))
    directory = Path(brain) / 'school' / 'successors' / day / operation_sha
    if any(p.is_symlink() for p in (directory, *directory.parents, directory / 'successor.lock')):
        raise ValueError('school successor directory traverses a symbolic link')
    directory.mkdir(parents=True, exist_ok=True)
    def save(path, doc):
        if path.exists():
            if json.loads(path.read_bytes()) != doc:
                raise ValueError('retained school successor artifact differs')
        else:
            write_json(path, doc)
        return dict(path=str(path), **witness(path))
    with (directory / 'successor.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        replacement = save(directory / 'school.json', after)
        receipt = dict(schema='FRANKIE_SCHOOL_SUCCESSOR_RECEIPT_V1', status='complete',
                       owner='frankie_box_school_knowledge.rebuild_successor', operation=operation,
                       operation_sha256=operation_sha, original_school=original_school, school=replacement,
                       source_corrections=source_corrections, model_calls=0, scientific_retests=0)
        receipt_pin = save(directory / 'receipt.json', receipt)
        correction = R.record_correction(brain, original=original_school, replacement=replacement,
            scopes=[[]], decision='checked_dependency_rebuild',
            reason='owner school rebuilt from checked source corrections and completed successor discussion',
            evidence=source_corrections + ([meeting_receipt] if meeting_receipt else []), publication_day=day,
            school_transition=dict(receipt=receipt_pin))
        return dict(receipt, receipt=receipt_pin, correction=correction)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--day', required=True)
    p.add_argument('--run', required=True)
    p.add_argument('--report-number', type=int, required=True)
    p.add_argument('--school-day', type=int, help='the day\'s school-day number in Frankie\'s class line (= the report number)')
    p.add_argument('--classroom', required=True, help='the day\'s <root>/work/classroom')
    p.add_argument('--exchange-view', help='the exchange\'s exchange-frankie.json')
    p.add_argument('--exchange-listed', help='why there is no exchange view (the orchestrator\'s reason)')
    p.add_argument('--lessons', help='the FRANKIE_LESSONS_V1 of the day')
    p.add_argument('--teacher-rows', help='experiment-teacher-rows/<day>/')
    p.add_argument('--brain', default='/opt/frankie-box/brain')
    a = p.parse_args()
    if not re.fullmatch('[0-9]{8}', a.day) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', a.run):
        p.error('--day YYYYMMDD and --run of letters, digits, _ and - required')
    if a.day == MONDAY:
        raise SystemExit('Monday 20211004 is out of the school (it starts with the first school day)')
    import frankie_box_brain as BR
    import frankie_box_classroom_code as K
    _, rules = K.rules()
    rules_witness = dict(file=Path(rules['path']).name, sha256=rules['sha256'], bytes=rules['bytes'], rules=rules['rules'])
    if a.school_day is not None and a.school_day != a.report_number:
        raise SystemExit('the school day and report number must match')
    retained = retained_school(a.brain, a.day)
    successor = None
    if retained is not None:
        if retained['content']['run'] != a.run or retained['row']['report_number'] != a.report_number:
            raise ValueError('school reuse belongs to another run or class position')
        if retained['status'] == 'requires_successor':
            successor = rebuild_successor(a.day, a.run, a.brain,
                original_school=retained['original'], exchange_view=a.exchange_view)
            retained = retained_school(a.brain, a.day)
        if retained['status'] != 'complete':
            raise ValueError('school successor still has a replaced dependency')
        doc, row = retained['content'], dict(retained['row'], **retained['original'])
        file, reused = retained['original']['path'], successor is None
    else:
        import frankie_box_experiment_review as R
        import frankie_box_lane_state as LS
        records = R.corrections(LS.knowledge_roots(a.brain))
        lessons = a.lessons
        if lessons and Path(lessons).is_file():
            raw = Path(lessons).read_bytes()
            delivered = R.current_document(dict(path=lessons, bytes=len(raw), sha256=sha256_bytes(raw),
                content=json.loads(raw)), records, a.brain, day=a.day, stage='school')
            lessons = delivered['path']
        doc = build(a.day, a.run, a.report_number, a.classroom, a.exchange_view, a.exchange_listed, lessons,
                    a.teacher_rows, rules_witness)
        data = (json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n').encode('utf-8')
        R.current_document(dict(path=str(Path(a.brain) / 'school' / (a.day + '.json')),
            bytes=len(data), sha256=sha256_bytes(data), content=doc), records, a.brain, day=a.day, stage='school')
        row, reused = BR.write_school_day(a.brain, a.day, data, a.report_number, a.run, school_day=a.school_day)
        file = str(Path(a.brain) / 'school' / row['file'])
    receipt = dict(schema=RECEIPT_SCHEMA, run=a.run, day=a.day, status='complete', file=file,
                   index=str(Path(a.brain) / 'school' / 'index.json'), row=row, reused=reused,
                   sections={k: len(v['items']) for k, v in doc['sections'].items()}, missing=len(doc['missing']),
                   withheld=len(doc['withheld']), model_calls=0)
    if successor is not None:
        receipt.update(successor=successor['receipt'], correction=successor['correction'])
    elif retained is not None:
        receipt['corrections'] = retained['corrections']
    print(json.dumps(receipt, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
