"""Frankie's brain: the calculation findings of every prior cycle, carried into the next cycle's reading (Greg, 2026-09-21
chat 6: "cycle 0 and 1 calc findings should be in the brain without a doubt; other generated docs case by case").

The latest entry remains under <brain>/cycle-<NN>/ for compatibility; every replaced version is preserved in history with a move receipt. Requests pin all accumulated entries, including earlier runs of the same cycle number, through capture_base. Each entry holds: the derivation digest (every layer of the pin, what the calculations
found), the accounting entry and the ten output ledgers (from response.json's lessons), the analysis, each with its
bytes and sha256 in MANIFEST.json. The next cycle's session loads every entry of an EARLIER cycle whose manifest says
include: true and whose bytes still match, and appends it to the reading corpus as members, so Frankie reads and
notes his own prior findings before deriving again. Case by case = the manifest: set "include": false on an entry to
keep it out of the corpus, or add a file with "include": true to bring another document in. Durable on the box; the
pusher publishes each cycle's entry under runs/<day>/root/brain/cycle-<NN>/. Nothing here is a summary, nothing is
deleted; a changed manifest changes the corpus identity, so the corpus is rebuilt.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_BRAIN_ENTRY_V1'
# Entries are keyed by DAY and cycle (Greg, 2026-09-29: "Sun and Monday cycles should be separate even though Sunday's
# hours were included in Monday run"): <brain>/<YYYYMMDD>-cycle-<NN>/. The older key <brain>/cycle-<NN>/ (no day; the
# 20211003 Sunday entry on the box) is still read, labelled day unknown. A cycle reads EVERY entry written so far, from
# every day and every cycle, except its own day+cycle (Greg: the cycles replay the day and restart earlier, so his
# reasoning may carry later data; only the actual run data ahead of time is walled, and that is the cycle being run).
ENTRY_GLOBS = ('cycle-*', '[0-9]' * 8 + '-cycle-*', '[0-9]' * 8 + '-ingest', '[0-9]' * 8 + '-day-file',
               '[0-9]' * 8 + '-root', '[0-9]' * 8 + '-teacher', '[0-9]' * 8 + '-search',
               '[0-9]' * 8 + '-lessons', '[0-9]' * 8 + '-jev-tested', '[0-9]' * 8 + '-exchange',
               '[0-9]' * 8 + '-meeting', '[0-9]' * 8 + '-meeting-*',
               '[0-9]' * 8 + '-survivors', '[0-9]' * 8 + '-confirmation')
# Non-cycle knowledge entries, ordered inside one day. They become readable as soon as each stage writes them.
DAY_KINDS = {'ingest': -40, 'day-file': -30, 'root': -20, 'teacher': -10,
             'search': 10, 'lessons': 20, 'jev-tested': 30, 'exchange': 40,
             'meeting': 45, 'survivors': 50, 'confirmation': 60}


def entry_name(day, cycle):
    """<YYYYMMDD>-cycle-<NN> with a day, the older cycle-<NN> without one."""
    if day is None:
        return f'cycle-{cycle}'
    if not re.fullmatch('[0-9]{8}', str(day)):
        raise ValueError('brain entry day must be YYYYMMDD')
    return f'{day}-cycle-{cycle}'


def parse_entry_name(name):
    """(day or None, cycle) of an entry directory name, or None when the name is not an entry. A day's lessons entry
    (<day>-lessons: the scientific teacher's test results on Frankie's claims) parses as (day, 'lessons'); a day's
    exchange entry (<day>-exchange: the three-way exchange of the two teachers and Frankie) as (day, 'exchange')."""
    kind = re.fullmatch(r'([0-9]{8})-(ingest|day-file|root|teacher|search|lessons|jev-tested|exchange|meeting|survivors|confirmation)', name)
    if kind:
        return kind.group(1), kind.group(2)
    meeting = re.fullmatch(r'([0-9]{8})-meeting-([0-9a-f]{64})', name)
    if meeting:
        return meeting.group(1), 'meeting'
    match = re.fullmatch(r'(?:([0-9]{8})-)?cycle-([0-9]+)', name)
    return (match.group(1), match.group(2)) if match else None


def write_stage_entry(brain, day, stage, sources, summary=None, inline_limit=2 * 1024 * 1024):
    """Commit one knowledge-producing stage to Frankie's brain immediately.

    The brain entry is <brain>/<day>-<stage>/stage-knowledge.json. Small JSON/text sources are carried inline; large
    evidence stays at its retained path and is represented by exact bytes + sha256 + path, so no giant duplicate is
    created and nothing is silently dropped. A repeat with identical bytes reuses the entry; different bytes decline.
    """
    allowed = {'ingest', 'day-file', 'root', 'teacher', 'search', 'jev-tested', 'survivors', 'confirmation'}
    if stage not in allowed:
        raise ValueError('stage knowledge must be one of %s' % sorted(allowed))
    if not re.fullmatch('[0-9]{8}', str(day)):
        raise ValueError('stage knowledge day must be YYYYMMDD')
    brain = Path(brain)
    records, bases = [], []
    for item in sources:
        p = Path(item)
        if not p.is_file():
            raise FileNotFoundError('stage knowledge source missing: %s' % p)
        # session 9 (Greg: one pass over the data, never two): a source's FRANKIE_FILE_CLAIM row when it still holds
        # (stat + filesystem + last 64 KiB), else read whole; a large source read whole leaves its claim row behind.
        # The basis is NOT part of stage-knowledge.json (the entry's bytes stay the same whichever way the sha256 came,
        # so a repeat reuses the entry); it rides on the manifest of a first write and on the returned manifest.
        pin, basis = stage_source_witness(p)
        bases.append(dict(path=str(p), **basis))
        rec = dict(path=str(p), **pin, inline=False)
        if pin['bytes'] <= inline_limit and p.suffix.lower() in ('.json', '.md', '.txt'):
            raw = p.read_bytes()
            if len(raw) != pin['bytes'] or sha256_bytes(raw) != pin['sha256']:
                raise ValueError('stage source changed while preparing its inline content')
            try:
                rec['content'] = json.loads(raw) if p.suffix.lower() == '.json' else raw.decode('utf-8')
                rec['inline'] = True
            except Exception:
                rec['inline'] = False
        records.append(rec)
    body = dict(schema='FRANKIE_STAGE_KNOWLEDGE_V1', day=str(day), stage=stage,
                summary=summary or {}, sources=records,
                rule='knowledge is filed immediately when legally available; large evidence remains exact by path/bytes/sha256')
    raw = (json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')
    entry_dir = brain / ('%s-%s' % (day, stage))
    manifest_path = entry_dir / 'MANIFEST.json'
    knowledge_path = entry_dir / 'stage-knowledge.json'
    digest = sha256_bytes(raw)
    if manifest_path.is_file() and knowledge_path.is_file():
        have = knowledge_path.read_bytes()
        if sha256_bytes(have) == digest:
            return dict(json.loads(manifest_path.read_bytes()), source_witness=bases), True
        # session 9 (a2: the ROOT's entry is filed before the digest is rendered beside the teacher; a later record of
        # the same ROOT lists the digest too): the ONLY difference allowed is the digest ADDED as a source (every earlier
        # source record identical, the summary differing only in its `digest` field). Then the new knowledge is filed
        # beside the original as stage-knowledge-attached-<sha16>.json (the original stays byte for byte) and the
        # manifest names it: 'digest attached later'. Anything else declines as before (R16).
        attached = _attach_digest_later(entry_dir, manifest_path, have, body, raw, digest, records, bases)
        if attached is not None:
            return attached
        raise ValueError('%s already holds different stage knowledge; duplicate data declines (R16)' % entry_dir)
    if entry_dir.exists():
        if (any(p.name not in ('stage-knowledge.json', 'stage-knowledge.json.pending', 'MANIFEST.json.pending')
                for p in entry_dir.iterdir())
                or knowledge_path.exists() and knowledge_path.read_bytes() != raw):
            raise ValueError('%s holds different incomplete stage knowledge; never overwritten' % entry_dir)
    else:
        entry_dir.mkdir(parents=True)
    if not knowledge_path.exists():
        pending_knowledge = entry_dir / 'stage-knowledge.json.pending'
        with pending_knowledge.open('wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending_knowledge, knowledge_path)
    manifest = dict(schema=SCHEMA, cycle=stage, day=str(day), entry_kind='stage_knowledge', entries=[
        dict(name='stage-knowledge.json', bytes=len(raw), sha256=digest, source='; '.join(r['path'] for r in records),
             include=True, kind='immediate %s knowledge' % stage)
    ], unavailable=[], knowledge_status='available_immediately', source_witness=bases,
       note='stage knowledge committed before the workflow advances; exact large sources remain at the digest-bound paths')
    pending = entry_dir / 'MANIFEST.json.pending'
    with pending.open('w', encoding='utf-8') as handle:
        handle.write(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(pending, manifest_path)
    directory = os.open(entry_dir, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return manifest, False


ATTACHED_LATER = 'digest attached later'
DIGEST_SOURCE_NAME = 'derivation-digest-full.md'


def _attach_digest_later(entry_dir, manifest_path, have, body, raw, digest, records, bases):
    """(manifest, reused) when the new stage knowledge is the filed one plus the digest only, else None (the caller
    declines). Reused when this exact knowledge is already attached. A second, different attachment is not made (None)."""
    manifest = json.loads(manifest_path.read_bytes())
    for entry in manifest.get('entries') or []:
        if entry.get('sha256') == digest and entry.get('attached_later') == ATTACHED_LATER:
            return dict(manifest, source_witness=bases, current_knowledge=entry['name'], attachment=ATTACHED_LATER), True
    try:
        old = json.loads(have)
    except ValueError:
        return None
    if any(e.get('attached_later') for e in manifest.get('entries') or []):
        return None                                  # one attachment per entry; a different one is different knowledge
    if {k: old.get(k) for k in ('schema', 'day', 'stage', 'rule')} != {k: body.get(k) for k in ('schema', 'day', 'stage', 'rule')}:
        return None
    previous = old.get('sources') or []
    added = [r for r in records if r not in previous]
    if not added or [r for r in records if r in previous] != previous \
            or any(Path(r['path']).name != DIGEST_SOURCE_NAME for r in added):
        return None
    before, after = dict(old.get('summary') or {}), dict(body.get('summary') or {})
    before.pop('digest', None)
    after.pop('digest', None)
    if before != after:
        return None
    name = 'stage-knowledge-attached-%s.json' % digest[:16]
    target = entry_dir / name
    if target.exists() and target.read_bytes() != raw:
        return None
    if not target.exists():
        pending = entry_dir / (name + '.pending')
        with pending.open('wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, target)
    witnessed = {b['path']: b for b in bases}
    manifest['entries'].append(dict(
        name=name, bytes=len(raw), sha256=digest, include=True, attached_later=ATTACHED_LATER,
        attaches_to=dict(name='stage-knowledge.json', sha256=sha256_bytes(have)),
        added_sources=[dict(path=r['path'], bytes=r['bytes'], sha256=r['sha256'],
                            basis=(witnessed.get(r['path']) or {}).get('basis')) for r in added],
        source='; '.join(r['path'] for r in records),
        kind='the %s knowledge again with the digest added (rendered after the entry was filed); the original '
             'stage-knowledge.json is kept byte for byte' % body.get('stage')))
    manifest['attached_later'] = (manifest.get('attached_later') or []) + [dict(name=name, sha256=digest, at=time.time())]
    pending = entry_dir / 'MANIFEST.json.pending'
    with pending.open('w', encoding='utf-8') as handle:
        handle.write(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(pending, manifest_path)
    directory = os.open(entry_dir, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return dict(manifest, source_witness=bases, current_knowledge=name, attachment=ATTACHED_LATER), False


def write_lessons_entry(brain, day, lessons_path):
    """The scientific teacher's lessons on Frankie or historical claims (written by
    frankie_box_scientific_teacher.py) as the brain entry <brain>/<day>-lessons/ (Greg, 2026-09-29: "his lessons from
    the teacher while he's learning"). Read by every later cycle like any entry. Test results computed from the data,
    never a grade or an answer key (R10). A second lessons file for the same day is added beside the first (the manifest
    lists both); the same bytes twice decline."""
    brain, source = Path(brain), Path(lessons_path)
    data = source.read_bytes()
    value = json.loads(data)
    author = value.get('author')
    schemas = {'frankie': 'FRANKIE_LESSONS_V1', 'historical': 'HISTORICAL_LESSONS_V1', 'jev': 'JEV_LESSONS_V1',
               'search': 'SEARCH_CANDIDATE_LESSONS_V1'}
    if author not in schemas or value.get('schema') != schemas[author]:
        raise ValueError(f'{source} is not scientific-teacher lessons of a known claim author')
    if author == 'jev' and (not value.get('knowledge_retest') or value.get('written_by') != 'scientific_teacher'):
        raise ValueError('only already-tested accumulated Jev claims use the additional lessons entry')
    if author == 'search' and (not value.get('knowledge_retest') or value.get('written_by') != 'scientific_teacher'):
        raise ValueError('only completed owner-local candidate checks use the additional lessons entry')
    days = [str(value.get('day'))] if author in ('frankie', 'jev') else [str(x.get('day')) for x in value.get('searches', [])]
    if str(day) not in days:
        raise ValueError('lesson entry day is not bound by the scientific-teacher source')
    entry_dir = brain / f'{day}-lessons'
    manifest_path = entry_dir / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_bytes()) if manifest_path.is_file() else dict(
        schema=SCHEMA, cycle='lessons', day=str(day), entry_kind='teacher_lessons', entries=[], unavailable=[],
        note="the scientific teacher's test results, original claim authors and per-day counts retained (R14)")
    digest = sha256_bytes(data)
    if any(e.get('sha256') == digest for e in manifest['entries']):
        raise ValueError(f'these lessons are already in {entry_dir} (duplicate data declines)')
    name = f'teacher-lessons-{digest[:16]}.json'
    entry_dir.mkdir(parents=True, exist_ok=True)
    (entry_dir / name).write_bytes(data)
    manifest['entries'].append(dict(name=name, bytes=len(data), sha256=digest, source=str(source), include=True,
                                    kind="the scientific teacher's lessons on %s claims (counts, challenges, untested)" % author))
    manifest['at'] = time.time()
    tmp = entry_dir / 'MANIFEST.json.tmp'
    tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, manifest_path)
    return manifest


def write_exchange_entry(brain, day, exchange_path):
    """The three-way exchange of one classroom-arm day (FRANKIE_EXPERIMENT_EXCHANGE_V1, Frankie's view, written by
    frankie_box_experiment_exchange.py) as the brain entry <brain>/<day>-exchange/ (SPEC-scientific-teacher.md step 5:
    "Frankie is taught from the exchange"). Read by every later cycle like any entry. Only the view built for Frankie is
    accepted (Jev's claims withheld, the lessons wall); each turn is labelled with its author (R11). The same bytes twice
    decline; a second exchange of the same day is added beside the first (the manifest lists both)."""
    brain, source = Path(brain), Path(exchange_path)
    data = source.read_bytes()
    value = json.loads(data)
    if value.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1' or value.get('view') != 'frankie' or str(value.get('day')) != str(day):
        raise ValueError(f'{source} is not the Frankie view of the FRANKIE_EXPERIMENT_EXCHANGE_V1 of {day}')
    entry_dir = brain / f'{day}-exchange'
    manifest_path = entry_dir / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_bytes()) if manifest_path.is_file() else dict(
        schema=SCHEMA, cycle='exchange', day=str(day), entry_kind='teacher_exchange', entries=[], unavailable=[],
        note="the three-way exchange (the BOSS teacher, the scientific teacher, Frankie's code), each turn labelled with "
             "its author; counts per day are the finding (R14); the teachers' own findings scoped with their days named")
    digest = sha256_bytes(data)
    if any(e.get('sha256') == digest for e in manifest['entries']):
        raise ValueError(f'this exchange is already in {entry_dir} (duplicate data declines)')
    name = f'teacher-exchange-{digest[:16]}.json'
    entry_dir.mkdir(parents=True, exist_ok=True)
    (entry_dir / name).write_bytes(data)
    manifest['entries'].append(dict(name=name, bytes=len(data), sha256=digest, source=str(source), include=True,
                                    kind="the three-way exchange: the BOSS teacher's turn, the scientific teacher's reply, "
                                         "Frankie's reply, and the teachers' own findings"))
    manifest['at'] = time.time()
    tmp = entry_dir / 'MANIFEST.json.tmp'
    tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, manifest_path)
    return manifest


def read_meeting_record(record_path, *, exchange_path, expected_sha256=None, complete=True):
    """Bind a discussion to the original Frankie exchange, not the runner's local paths."""
    raw = Path(record_path).read_bytes()
    if expected_sha256 is not None and sha256_bytes(raw) != expected_sha256:
        raise ValueError('meeting record differs from its receipt')
    record = json.loads(raw)
    source_raw = Path(exchange_path).read_bytes()
    source = json.loads(source_raw)
    exchange = record.get('exchange') or {}
    if (source.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1' or source.get('view') != 'frankie'
            or not re.fullmatch(r'[0-9]{8}', str(source.get('day')))
            or not source.get('run') or not source.get('exchange_hash')
            or record.get('schema') != 'FRANKIE_GRANITE_MEETING_V1'
            or record.get('day') != source['day'] or record.get('run') != source['run']
            or exchange.get('sha256') != sha256_bytes(source_raw)
            or exchange.get('exchange_hash') != source['exchange_hash']):
        raise ValueError('meeting does not bind this run/day/Frankie exchange')
    if record.get('status') not in (('complete',) if complete else ('complete', 'refused', 'inputs_only')):
        raise ValueError('meeting has no accepted completion or refusal status')
    if record['status'] == 'complete':
        if not isinstance(record.get('items'), list) or not isinstance(record.get('not_discussed'), list):
            raise ValueError('complete meeting must retain discussed and unreached items')
        expected = [i['item_id'] for i in source.get('items') or []]
        actual = [i.get('item_id') for i in record['items'] + record['not_discussed']]
        if len(set(actual)) != len(actual) or len(set(expected)) != len(expected) or set(actual) != set(expected):
            raise ValueError('meeting discussed/unreached items do not cover the exchange exactly once')
        if any(not isinstance(i.get('open_items'), list) for i in record['not_discussed']):
            raise ValueError('unreached meeting items must retain their open items')
        for item in record['items']:
            if not isinstance(item, dict) or any(not isinstance(item.get(k), list) for k in
                    ('seat_statements', 'coordinator_turns', 'code_seat_answers', 'open_items', 'requested_tests')):
                raise ValueError('meeting must retain the four attributed categories')
            if any(t.get('evidentiary_weight') != 0 for t in item['coordinator_turns']):
                raise ValueError('coordinator turns must have zero evidentiary weight')
            if any(t.get('status') != 'requested_not_run' for t in item['requested_tests']):
                raise ValueError('a meeting cannot report requested tests as executed')
    return record


def meeting_directory(exchange_path, *, owner_dir=None):
    """Resolve only an exact owner/day exchange route, including receipt-bound successors."""
    import frankie_box_experiment_review as REVIEW
    exchange_path = Path(exchange_path)
    if any(p.is_symlink() for p in (exchange_path, *exchange_path.parents)):
        raise ValueError('meeting exchange path traverses a symbolic link')
    raw = exchange_path.read_bytes()
    source = json.loads(raw)
    day, run = str(source.get('day')), source.get('run')
    if (source.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1' or source.get('view') != 'frankie'
            or not re.fullmatch(r'[0-9]{8}', day) or not isinstance(run, str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', run)):
        raise ValueError('meeting lookup requires an owner-bound Frankie exchange')
    candidates = [Path(owner_dir)] if owner_dir is not None else [p for p in exchange_path.parents if p.name == run]
    owners = []
    for candidate in candidates:
        if candidate.name != run or not exchange_path.is_relative_to(candidate):
            continue
        parts = exchange_path.relative_to(candidate).parts
        regular = parts == ('exchange', day, 'exchange-frankie.json')
        successor = (len(parts) == 7 and parts[:3] == ('successors', day, 'work')
                     and parts[4] == 'exchange' and parts[6] == 'exchange-frankie.json'
                     and all(re.fullmatch(r'[0-9a-f]{64}', parts[i]) for i in (3, 5)))
        if regular or successor:
            owners.append((candidate, successor))
    if len(owners) != 1:
        raise ValueError('exchange path does not name one exact owning experiment')
    owner, successor = owners[0]
    directory = owner / 'meeting' / day
    if successor:
        receipt = json.loads((exchange_path.parent / 'receipt.json').read_bytes())
        selected = receipt.get('frankie_view') or {}
        if (receipt.get('schema') != 'FRANKIE_EXCHANGE_SUCCESSOR_RECEIPT_V1'
                or receipt.get('status') != 'complete' or receipt.get('day') != day or receipt.get('run') != run
                or receipt.get('operation_sha256') != exchange_path.parent.name
                or REVIEW.digest(REVIEW.canonical(receipt.get('operation'))) != receipt['operation_sha256']
                or selected != dict(path=str(exchange_path), bytes=len(raw), sha256=sha256_bytes(raw))):
            raise ValueError('successor meeting exchange differs from its completed owner receipt')
        REVIEW._read_pin(receipt['replacement_inputs'])
        directory = directory / 'successors' / selected['sha256']
    return directory


def read_meeting_for_exchange(exchange_path, *, owner_dir=None):
    """Read the owning experiment's receipt-bound meeting; never guess from an unrelated file."""
    exchange_path = Path(exchange_path)
    source_raw = exchange_path.read_bytes()
    source = json.loads(source_raw)
    day = str(source.get('day'))
    if (not re.fullmatch(r'[0-9]{8}', day) or source.get('view') != 'frankie'
            or source.get('schema') != 'FRANKIE_EXPERIMENT_EXCHANGE_V1'
            or not source.get('run') or not source.get('exchange_hash')):
        raise ValueError('meeting lookup requires a dated Frankie exchange view')
    directory = meeting_directory(exchange_path, owner_dir=owner_dir)
    path, receipt_path = directory / 'meeting.json', directory / 'receipt.json'
    if not receipt_path.is_file():
        return dict(status='missing', record=None, path=None, receipt=None,
                    reason='no published meeting receipt for this exchange')
    receipt = json.loads(receipt_path.read_bytes())
    if receipt.get('status') == 'runtime_failed':
        # Startup failed before a meeting record existed. Bind the refusal to the
        # exact exchange and retained inputs, rather than inventing a discussion.
        binding_pin, input_pin = receipt.get('binding') or {}, receipt.get('inputs') or {}
        values = []
        for name, selected in (('meeting-binding.json', binding_pin), ('meeting-input.json', input_pin)):
            raw = (directory / name).read_bytes()
            if selected.get('bytes') != len(raw) or selected.get('sha256') != sha256_bytes(raw):
                raise ValueError('failed meeting receipt differs from retained ' + name)
            values.append(json.loads(raw))
        binding, _ = values
        exchange = binding.get('exchange') or {}
        if (receipt.get('schema') != 'FRANKIE_GRANITE_MEETING_RECEIPT_V1'
                or str(receipt.get('day')) != day or not receipt.get('refused_to_run')
                or binding.get('schema') != 'FRANKIE_GRANITE_MEETING_BINDING_V1'
                or binding.get('day') != source.get('day') or binding.get('run') != source.get('run')
                or exchange.get('sha256') != sha256_bytes(source_raw)
                or exchange.get('exchange_hash') != source.get('exchange_hash')
                or any((binding.get('input') or {}).get(k) != input_pin.get(k) for k in ('bytes', 'sha256'))):
            raise ValueError('failed meeting receipt does not bind this run/day/Frankie exchange')
        return dict(status='runtime_failed', record=None, path=None, receipt=receipt,
                    reason='; '.join(receipt['refused_to_run']))
    pin = receipt.get('record') or {}
    raw = path.read_bytes()
    if (receipt.get('schema') != 'FRANKIE_GRANITE_MEETING_RECEIPT_V1'
            or str(receipt.get('day')) != day or pin.get('bytes') != len(raw)
            or pin.get('sha256') != sha256_bytes(raw)):
        raise ValueError('meeting receipt identity, bytes or hash differs')
    record = read_meeting_record(path, exchange_path=exchange_path, expected_sha256=pin['sha256'], complete=False)
    if receipt.get('status') != record['status']:
        raise ValueError('meeting receipt status differs from the retained record')
    return dict(status=record['status'], record=record, path=str(path), receipt=receipt,
                reason='; '.join(record.get('refused_to_run') or []) or
                       ('inputs only; no coordinator model was called' if record['status'] == 'inputs_only' else None))


def write_meeting_entry(brain, day, record_path, *, exchange_path):
    """Immediately publish one immutable discussion; identical retries repair interrupted publication."""
    import fcntl
    from frankie_box_durable import write_bytes, write_json, sync_directory
    source = Path(record_path)
    raw = source.read_bytes()
    digest = sha256_bytes(raw)
    record = read_meeting_record(source, exchange_path=exchange_path, expected_sha256=digest)
    if str(record['day']) != str(day):
        raise ValueError('meeting brain entry day differs')
    import frankie_box_experiment_review as REVIEW
    records = REVIEW.corrections([brain])
    REVIEW.require_current([dict(path=str(source), bytes=len(raw), sha256=digest, content=record)], records)
    successors = [r for r in records.values() if r['replacement']['sha256'] == record['exchange']['sha256']
                  and r['body'].get('exchange_transition')]
    brain = Path(brain)
    if any(p.is_symlink() for p in (brain, *brain.parents)):
        raise ValueError('meeting brain path contains a symbolic link')
    brain.mkdir(parents=True, exist_ok=True)
    sync_directory(brain.parent)
    entry_name = '%s-meeting' % day
    if successors:
        entry_name += '-' + record['exchange']['sha256']
    entry = brain / entry_name
    target, manifest_path = entry / 'meeting.json', entry / 'MANIFEST.json'
    manifest = dict(schema=SCHEMA, cycle='meeting', day=str(day), entry_kind='meeting', entries=[
        dict(name='meeting.json', bytes=len(raw), sha256=digest, include=True,
             kind='post-class discussion; coordinator turns have zero evidentiary weight')], unavailable=[],
        knowledge_status='available_immediately',
        note='seat statements, coordinator turns, code-seat answers and open items/requested tests remain distinct')
    if successors:
        manifest.update(entry_name=entry_name, exchange_corrections=[r['record'] for r in successors])
    lock_path = brain / '.meeting.lock'
    if lock_path.is_symlink():
        raise ValueError('meeting brain lock is a symbolic link')
    with open(lock_path, 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if target.is_symlink() or manifest_path.is_symlink() or entry.is_symlink():
            raise ValueError('meeting entry contains a symbolic link')
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('different retained meeting bytes; never overwritten')
        if manifest_path.exists() and json.loads(manifest_path.read_bytes()) != manifest:
            raise ValueError('different retained meeting manifest; never overwritten')
        reused = target.is_file() and manifest_path.is_file()
        if not target.exists():
            write_bytes(target, raw)
        if not manifest_path.exists():
            write_json(manifest_path, manifest)
        sync_directory(entry)
    return manifest, reused


# Frankie's SCHOOL KNOWLEDGE BASE (Greg, 2026-09-29): one JSON file per classroom-arm day, <brain>/school/<day>.json
# (FRANKIE_SCHOOL_KNOWLEDGE_V1, written by frankie_box_school_knowledge.py), and the append-only <brain>/school/index.json
# (one row per day: day, file, sha256, bytes, report number N). A day file is never overwritten; a day already in the index
# with other bytes declines (duplicate data, R16). The loader reads every EARLIER day's school file (the day's own and
# later days never), each checked against its index row; an item whose bytes the corpus already carries (the same
# lessons or exchange file read as a brain entry) is carried once, as a reference.
SCHOOL_DIR = 'school'
SCHOOL_SCHEMA = 'FRANKIE_SCHOOL_KNOWLEDGE_V1'
SCHOOL_INDEX_SCHEMA = 'FRANKIE_SCHOOL_INDEX_V1'


def _school_index(brain):
    path = Path(brain) / SCHOOL_DIR / 'index.json'
    if not path.is_file():
        return dict(schema=SCHOOL_INDEX_SCHEMA, rows=[])
    index = json.loads(path.read_bytes())
    if index.get('schema') != SCHOOL_INDEX_SCHEMA or not isinstance(index.get('rows'), list):
        raise ValueError(f'{path} is not a {SCHOOL_INDEX_SCHEMA}')
    return index


def write_school_day(brain, day, data, report_number, run, school_day=None):
    """<brain>/school/<day>.json (written once, 'xb') and its row appended to <brain>/school/index.json under an exclusive
    lock. Returns (row, reused): the same bytes again reuse the row; other bytes for a day already there decline.
    school_day: the day's position in Frankie's class line (frankie_box_frankie_queue.py; equal to report_number), kept in
    the row when given."""
    import fcntl
    if not re.fullmatch('[0-9]{8}', str(day)):
        raise ValueError('school day must be YYYYMMDD')
    value = json.loads(data)
    if value.get('schema') != SCHOOL_SCHEMA or str(value.get('day')) != str(day):
        raise ValueError(f'not a {SCHOOL_SCHEMA} of {day}')
    school = Path(brain) / SCHOOL_DIR
    school.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(data)
    with open(school / '.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        index = _school_index(brain)
        mine = [r for r in index['rows'] if r.get('day') == str(day)]
        if mine:
            if mine[-1].get('sha256') != digest:
                raise ValueError(f'the school already holds day {day} with other bytes (sha256 {mine[-1].get("sha256")}): '
                                 'duplicate data declines (R16)')
            return mine[-1], True
        path = school / f'{day}.json'
        if path.exists() and sha256_bytes(path.read_bytes()) != digest:
            raise ValueError(f'{path} exists with other bytes and no index row: never overwritten (move it aside with a receipt)')
        if not path.exists():
            with path.open('xb') as f:
                f.write(data)
        row = dict(day=str(day), file=f'{day}.json', sha256=digest, bytes=len(data), report_number=report_number,
                   run=run, include=True, at=time.time())
        if school_day is not None:
            row['school_day'] = school_day
        index['rows'].append(row)
        tmp = school / 'index.json.tmp'
        tmp.write_text(json.dumps(index, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, school / 'index.json')
    return row, False


def school_rows(brain, before_day=None, pinned=None):
    """Read completed school records whole, hash-bound to their index rows, regardless of market-date order.

    before_day is the legacy caller's current-day argument: exclude only that day's own school answers.
    Greg's 2026-10-06 experiment has no chronological knowledge barrier. A captured base still supplies its
    exact pinned rows instead of the live index; this does not widen a saved input selection on resume.
    """
    loaded, listed = [], []
    try:
        rows = list(pinned) if pinned is not None else _school_index(brain)['rows']
    except (OSError, ValueError) as error:
        return loaded, [dict(row=None, reason=f'the school index could not be read ({type(error).__name__}: {error})')]
    for row in sorted(rows, key=lambda r: str(r.get('day'))):
        day = str(row.get('day'))
        if before_day is not None and day == str(before_day):
            listed.append(dict(row=row, reason='this classroom cannot consume its own school answers'))
            continue
        if not row.get('include', True):
            listed.append(dict(row=row, reason='excluded by its index row (include false)'))
            continue
        path = Path(brain) / SCHOOL_DIR / str(row.get('file'))
        if not path.is_file():
            listed.append(dict(row=row, reason=f'{path} is missing'))
            continue
        data = path.read_bytes()
        if sha256_bytes(data) != row.get('sha256'):
            listed.append(dict(row=row, reason=f'{path} differs from its index row'))
            continue
        loaded.append((row, json.loads(data)))
    return loaded, listed
ACCOUNTING_NAME = 'accounting-and-ledgers.md'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_files(paths):
    """sha256_bytes(path.read_bytes()) for each path, in order, streamed (derived layers run to many GB) and hashed on
    threads (hashlib releases the GIL): pinned threads over the booked lane, as many as files up to the lane's width
    (frankie_box_lane_pin.executor; endings pass 2026-10-08: sized from the lane, never a constant), else a plain pool
    of the same width."""
    from concurrent.futures import ThreadPoolExecutor
    def one(path):
        # once per unchanged file per run (frankie_box_filehash.py): brain_ready, identity() and load() check the same
        # prior entries, earlier cycles' GB digests among them (Greg, 2026-09-28)
        try:
            import frankie_box_filehash as F
        except ImportError:
            from deploy.aws.box import frankie_box_filehash as F
        return F.sha256_file(path)
    paths = list(paths)
    if len(paths) < 2:
        return [one(p) for p in paths]
    try:
        import frankie_box_lane_pin as LP
        lane = LP.lane_cpus()
        pool = LP.executor('thread', max(1, min(len(paths), len(lane))), lane)
    except Exception:  # noqa: BLE001 - placement only; the values are the same on an unpinned pool
        pool = ThreadPoolExecutor(min(14, len(paths)))
    with pool:
        return list(pool.map(one, paths))


FILE_CLAIMS_NAME = 'file-claims.jsonl'
CLAIM_TAIL_BYTES = 64 << 10


def file_claims(directory):
    """{(inode, size, mtime_ns): claim row} from <directory>/file-claims.jsonl: FRANKIE_FILE_CLAIM_V1 or V2 rows
    (research/kalshi/frankie_boss/operations/ingest_block_sources.file_claim; the ROOT's rows under <root>/work/, dedupe
    pass request R1) for files a stage measured whole on its write stream. Session 8 (2026-10-08): keyed without the
    device number (it renumbers across a reboot); a V2 row's filesystem identity is checked at the take
    (ingest_block_sources.claim_still_holds). A missing or unreadable file, or a row without the full identity, yields
    nothing (the caller hashes); never raises."""
    claims = {}
    path = Path(directory) / FILE_CLAIMS_NAME
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import claim_identity
        lines = path.read_bytes().splitlines() if path.is_file() else []
    except (OSError, ImportError):
        return claims
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        identity = claim_identity(row)
        if (identity is None or type(row.get('bytes')) is not int or not row.get('sha256') or not row.get('tail_sha256')
                or identity[1] != row['bytes']):
            continue
        claims[identity] = dict(row, claim_file=str(path))
    return claims


def _tail_sha256(path, size):
    with open(path, 'rb') as handle:
        handle.seek(max(0, size - CLAIM_TAIL_BYTES))
        return hashlib.sha256(handle.read()).hexdigest()


def file_witnesses(paths, claims):
    """[(sha256, basis)] for `paths` in order. A file whose (inode, size, mtime_ns), filesystem (a V2 row) AND the
    sha256 of its last 64 KiB equal a claim row's takes the claim's sha256 (basis 'claim', the export's exact rule, `_pins_progress`); every
    other file is hashed from byte 0 here on sha256_files (basis 'hashed'). Nothing is taken on stat alone (Greg's open
    call (c) untouched); the basis is recorded by the caller. Endings pass 2026-10-08: on a2 the classroom's brain entry
    hashed ROOT's 472 GB inline layer from byte 0 (one sequential sha256, ~7 min at the volume's 1.1 GB/s) to write
    derived-files.md; with ROOT's claim row that is one 64 KiB read."""
    paths = list(paths)
    taken, to_hash = {}, []
    for index, path in enumerate(paths):
        row, held = None, None
        if claims:
            try:
                from research.kalshi.frankie_boss.operations.ingest_block_sources import claim_still_holds
                s = os.stat(path)
                row = claims.get((s.st_ino, s.st_size, s.st_mtime_ns))
                held = claim_still_holds(row, path) if row is not None else None
            except (OSError, ImportError):
                held = None
        if held is not None:
            taken[index] = (row['sha256'], dict(basis='claim', claimed_by=row.get('claimed_by'), claim_file=row.get('claim_file'),
                                                claim_schema=held['basis'],
                                                rule='inode, size, mtime_ns, the filesystem identity (a V2 row) and the last '
                                                     '64 KiB checked; any difference hashes from byte 0'))
        else:
            to_hash.append(index)
    hashed = sha256_files([paths[i] for i in to_hash])
    for index, digest in zip(to_hash, hashed):
        taken[index] = (digest, dict(basis='hashed'))
    return [taken[i] for i in range(len(paths))]


STAGE_CLAIM_THRESHOLD = 256 << 20     # a source at or over this many bytes, read whole for want of a claim, gets one


def _claims_work_of(path):
    """<D>/work for the nearest ancestor D of `path` holding work/file-claims.jsonl (the attempt the source belongs to:
    a ROOT attempt's calculations-receipt.json, derive.json, digest, layers and spools all sit under it), else None.
    One pass (2026-10-09): the source's own directory comes first when it holds file-claims.jsonl (the ingest writes
    its journal claim beside its receipt; the teacher-only step writes its rows file's claim in its rows directory)."""
    own = Path(path).resolve().parent
    if (own / FILE_CLAIMS_NAME).is_file() and _claim_row_of(own, path) is not None:
        return own
    for parent in Path(path).resolve().parents:
        if (parent / 'work' / FILE_CLAIMS_NAME).is_file():
            return parent / 'work'
    return None


def _claim_row_of(work, path):
    """The last FRANKIE_FILE_CLAIM_V1/V2 row of <work>/file-claims.jsonl naming `path` (resolved), else None."""
    want, found = str(Path(path).resolve()), None
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import FILE_CLAIM_SCHEMAS
        lines = (Path(work) / FILE_CLAIMS_NAME).read_bytes().splitlines()
    except (OSError, ImportError):
        return None
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get('schema') in FILE_CLAIM_SCHEMAS and str(row.get('path')) == want:
            found = row
    return found


def append_file_claim(work, row):
    """Append one FRANKIE_FILE_CLAIM_V2 row to <work>/file-claims.jsonl: every existing line byte for byte, the row
    after them, one atomic rewrite (ingest_block_sources._write_claims_atomic) under an flock on the <work> directory
    itself (no lock file is added to the attempt); a row already there for the same path, sha256 and stat is not added
    twice. Returns the note dict; never raises (a claim is a hint: without it the next reader reads whole)."""
    import fcntl
    work = Path(work)
    target = work / FILE_CLAIMS_NAME
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import _write_claims_atomic
        directory = os.open(work, os.O_RDONLY)
        try:
            fcntl.flock(directory, fcntl.LOCK_EX)
            text = target.read_text(encoding='utf-8') if target.is_file() else ''
            for line in text.splitlines():
                try:
                    have = json.loads(line)
                except ValueError:
                    continue
                if isinstance(have, dict) and all(have.get(k) == row.get(k) for k in ('path', 'sha256', 'stat')):
                    return dict(file=str(target), status='present', added=0)
            if text and not text.endswith('\n'):
                text += '\n'
            _write_claims_atomic(target, (text + json.dumps(row, sort_keys=True) + '\n').encode())
        finally:
            os.close(directory)              # closing the descriptor releases the lock
        return dict(file=str(target), status='written', added=1)
    except Exception as error:  # noqa: BLE001 - a claim is a hint, never a stage's outcome
        return dict(file=str(target), status='not_written', added=0, reason='%s: %s' % (type(error).__name__, error))


def stage_source_witness(path, threshold=None):
    """({bytes, sha256}, basis) of one stage-entry source with at most ONE whole read (session 9, Greg: "one pass over
    the data, never two"). The rule:
      - a claim row for the source under its attempt (<D>/work/file-claims.jsonl, D the nearest such ancestor) whose
        bytes equal the file's size and which still holds (inode, size, mtime_ns, the filesystem of a V2 row and the
        sha256 of the last 64 KiB: ingest_block_sources.claim_still_holds, the rule of
        frankie_box_boss_session._claim_still_holds) gives the sha256 (basis 'by claim'; a V1 row taken this way is
        rewritten as V2 there); one 64 KiB read;
      - else the file is hashed whole (frankie_box_filehash.witness: once per unchanged file per process), basis
        'read whole'; at or over `threshold` bytes (STAGE_CLAIM_THRESHOLD, 256 MiB; FRANKIE_BRAIN_CLAIM_THRESHOLD
        overrides) the claim row is then written beside the attempt's others (file_claim on the stat the hash ran
        on) so the next stage takes it: basis 'read whole once, claim written'. With no claims file above the source
        nothing is written and the basis says so."""
    from frankie_box_filehash import witness, remember
    p = Path(path)
    if threshold is None:
        threshold = int(os.environ.get('FRANKIE_BRAIN_CLAIM_THRESHOLD') or STAGE_CLAIM_THRESHOLD)
    work = _claims_work_of(p)
    before = os.stat(p)
    if work is not None:
        row = _claim_row_of(work, p)
        if row is not None and row.get('bytes') == before.st_size and row.get('sha256'):
            try:
                from research.kalshi.frankie_boss.operations.ingest_block_sources import (claim_still_holds,
                                                                                           refresh_file_claims)
                held = claim_still_holds(row, p)
                if held is not None and held['refreshed'] is not None:
                    refresh_file_claims(work, {held['refreshed']['path']: held['refreshed']})
            except ImportError:
                held = None
            if held is not None:
                pin = dict(bytes=int(row['bytes']), sha256=str(row['sha256']))
                remember(p, pin)              # a later witness() of the unchanged file in this process reads nothing
                return pin, dict(basis='by claim', claim_file=str(work / FILE_CLAIMS_NAME), claim_schema=held['basis'],
                                 claimed_by=row.get('claimed_by'))
    pin = witness(p)
    if pin['bytes'] < threshold:
        return pin, dict(basis='read whole')
    if work is None:
        return pin, dict(basis='read whole once, no claim written: no work/%s above the source' % FILE_CLAIMS_NAME)
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import file_claim
        row = file_claim(p, pin['bytes'], pin['sha256'],
                         'brain stage entry (frankie_box_brain.write_stage_entry): read whole once at %s'
                         % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    except (OSError, ValueError, ImportError) as error:
        return pin, dict(basis='read whole once, no claim written: %s: %s' % (type(error).__name__, error))
    if row['stat'] != [before.st_ino, before.st_size, before.st_mtime_ns]:
        return pin, dict(basis='read whole once, no claim written: the file changed identity after its hash')
    note = append_file_claim(work, row)
    if note['status'] == 'not_written':
        return pin, dict(basis='read whole once, no claim written: ' + note.get('reason', ''), claim_file=note['file'])
    return pin, dict(basis='read whole once, claim written', claim_file=note['file'])


def _lessons_doc(response):
    """The accounting entry and the output ledgers (every JSON lesson of the response) as one Markdown document."""
    lessons = response.get('lessons') or []
    blocks = []
    for entry in lessons:
        if isinstance(entry, dict):
            title = entry.get('ledger') or entry.get('name') or 'entry'
            blocks.append(f'## {title}\n\n```json\n' + json.dumps(entry, indent=1, sort_keys=True, ensure_ascii=False) + '\n```\n')
    if not blocks:
        return None
    return f'# Accounting entry and output ledgers ({len(blocks)} JSON lessons of the response)\n\n' + '\n'.join(blocks)


def _archive_entry(brain, entry_dir):
    """Preserve the previous version with a receipt for its move."""
    import uuid
    brain, entry_dir = Path(brain).resolve(), Path(entry_dir)
    if not entry_dir.exists():
        return None
    if entry_dir.is_symlink() or entry_dir.resolve().parent != brain:
        raise ValueError('brain entry must be an immediate real directory')
    history = _require_real_path(brain / 'history')
    history.mkdir(exist_ok=True)
    stamp = str(time.time_ns()) + '-' + uuid.uuid4().hex
    target = history / (entry_dir.name + '-' + stamp)
    manifest = entry_dir / 'MANIFEST.json'
    value = dict(schema='FRANKIE_BRAIN_PRESERVATION_RECEIPT_V1', source=str(entry_dir),
                 destination=str(target), manifest_sha256=sha256_bytes(manifest.read_bytes()) if manifest.is_file() else None,
                 reason='new run adds knowledge; previous entry retained whole')
    entry_dir.rename(target)
    with (history / ('move-' + stamp + '.json')).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
    return target


def _require_real_path(path):
    path = Path(path)
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('knowledge path contains a symbolic link')
    return path


def _checked_tree(directory):
    directory = _require_real_path(directory)
    for path in directory.rglob('*'):
        _require_real_path(path)
        if not (path.is_file() or path.is_dir()):
            raise ValueError('knowledge tree contains a nonregular member')


def _checked_entry(directory, expected_hash=None):
    directory = Path(directory)
    _checked_tree(directory)
    raw = (directory / 'MANIFEST.json').read_bytes()
    if expected_hash is not None and sha256_bytes(raw) != expected_hash:
        raise ValueError('knowledge manifest differs from pinned base')
    manifest = json.loads(raw)
    included = []
    for entry in manifest.get('entries', []):
        if not entry.get('include'):
            continue
        name = entry.get('name', '')
        path = directory / name
        if (not name or Path(name).name != name or path.is_symlink() or not path.is_file()
                or path.stat().st_size != entry.get('bytes')):
            raise ValueError('included historical knowledge missing or changed: ' + name)
        included.append((entry, path))
    # one pass (Greg, 2026-10-09): a file with a holding claim row in the entry's own file-claims.jsonl (the digest:
    # hard-linked from the ROOT's work at write_entry, its sha256 from the digest writer's claim; identity, filesystem
    # and last 64 KiB checked) takes the claim's sha256; every other included file is streamed and hashed on threads
    for (entry, path), (digest, _) in zip(included, file_witnesses([p for _, p in included], file_claims(directory))):
        if digest != entry.get('sha256'):
            raise ValueError('included historical knowledge missing or changed: ' + entry.get('name', ''))
    return manifest, sha256_bytes(raw)


def _link_or_copy(source, destination):
    """os.link (same filesystem: no bytes written), else shutil.copy2. Entries are immutable once written."""
    import shutil
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    return destination


def _linked_claim(source):
    """(bytes, sha256, basis) of `source` from a holding claim row in its own directory's file-claims.jsonl or the
    nearest <D>/work/file-claims.jsonl above it (the ROOT's work: the digest writer appends the digest's row there),
    else None. Never raises."""
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import claim_still_holds
        work = _claims_work_of(source)
        row = _claim_row_of(work, source) if work is not None else None
        if row is None or row.get('bytes') != os.stat(source).st_size or not row.get('sha256'):
            return None
        held = claim_still_holds(row, source)
        if held is None:
            return None
        return int(row['bytes']), str(row['sha256']), dict(basis='by claim', claim_file=str(work / FILE_CLAIMS_NAME),
                                                           claim_schema=held['basis'], claimed_by=row.get('claimed_by'))
    except Exception:  # noqa: BLE001 - a claim is a hint
        return None


def capture_base(brain, request_identity):
    """Pin all accumulated prior-run knowledge, including cycle zero, for this request."""
    import re
    import shutil
    if not re.fullmatch('[0-9a-f]{64}', request_identity):
        raise ValueError('full request identity required for knowledge base')
    brain = Path(brain)
    snapshot = _require_real_path(brain / 'bases' / request_identity / 'MANIFEST.json')
    if snapshot.is_file():
        list(snapshot_entries(brain, snapshot))
        return snapshot
    history = _require_real_path(brain / 'history')
    history.mkdir(parents=True, exist_ok=True)
    candidates = [m for pattern in ENTRY_GLOBS for m in brain.glob(pattern + '/MANIFEST.json')] + list(history.glob('*/MANIFEST.json'))
    frozen = brain / FROZEN_DIR / 'MANIFEST.json'
    if frozen.is_file():
        candidates.append(frozen)
    import frankie_box_experiment_review as REVIEW
    records = REVIEW.corrections([brain])
    entries, withheld_meetings = {}, []
    for path in sorted(candidates):
        manifest, digest = _checked_entry(path.parent)
        replaced = _stale_meeting_sources(manifest, path.parent, records)
        if replaced:
            withheld_meetings.append(dict(path=str(path), sha256=digest, corrections=replaced,
                                          reason='meeting discussed an explicitly replaced exchange'))
            continue
        if digest in entries:
            continue
        destination = history / ('entry-' + digest)
        if not destination.exists():
            # one pass (2026-10-09): hard links (no second write of a many-GB digest; the claim rows still hold on
            # the shared inode), a copy only where a link fails
            shutil.copytree(path.parent, destination, copy_function=_link_or_copy)
        _checked_entry(destination, digest)
        entries[digest] = dict(path=str(destination.relative_to(brain)), sha256=digest,
                               cycle=manifest.get('cycle'), day=manifest.get('day'), source_schema=manifest.get('schema'))
    value = dict(schema='FRANKIE_ACCUMULATED_KNOWLEDGE_BASE_V1', request_identity=request_identity,
                 entries=list(entries.values()), rule='all previously stored intact knowledge; immutable for this request')
    value['corrections'] = sorted(r['record']['sha256'] for r in records.values())
    if withheld_meetings:
        value['withheld_meetings'] = withheld_meetings
    school = _school_index(brain)['rows'] if (brain / SCHOOL_DIR / 'index.json').is_file() else []
    if school:          # the school days written so far, pinned by their index rows (the files are never overwritten)
        value['school'] = [{k: r.get(k) for k in ('day', 'file', 'sha256', 'bytes', 'report_number', 'include')} for r in school]
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    with snapshot.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
    return snapshot


def snapshot_entries(brain, snapshot):
    brain = Path(brain).resolve()
    value = json.loads(Path(snapshot).read_bytes())
    if value.get('schema') != 'FRANKIE_ACCUMULATED_KNOWLEDGE_BASE_V1':
        raise ValueError('accumulated knowledge base schema differs')
    for entry in value['entries']:
        path = (brain / entry['path']).resolve()
        if not path.is_relative_to(brain / 'history'):
            raise ValueError('knowledge base entry is outside retained history')
        manifest, digest = _checked_entry(path, entry['sha256'])
        day = entry.get('day') or manifest.get('day')
        yield ('prior-run-' + digest[:16] + ('-' + str(day) if day else '') + '-cycle-' + str(entry.get('cycle')), manifest, path)


def pin_session_base(brain, request_identity, receipt_path):
    """Pin one request's base once; refuse changed or unreceipted reused bases."""
    if not re.fullmatch('[0-9a-f]{64}', request_identity):
        raise ValueError('full request identity required for knowledge base')
    brain = _require_real_path(Path(brain)).resolve()
    snapshot = _require_real_path(brain / 'bases' / request_identity / 'MANIFEST.json')
    receipt_path = _require_real_path(Path(receipt_path))
    schema = 'FRANKIE_SESSION_KNOWLEDGE_BASE_RECEIPT_V1'
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_bytes())
        raw = snapshot.read_bytes()
        base = json.loads(raw)
        if (receipt.get('schema') != schema
                or receipt.get('request_identity') != request_identity
                or receipt.get('path') != str(snapshot)
                or receipt.get('sha256') != sha256_bytes(raw)
                or receipt.get('bytes') != len(raw)
                or base.get('request_identity') != request_identity
                or receipt.get('entries') != len(base.get('entries', []))):
            raise ValueError('request knowledge base differs from its retained receipt')
        list(snapshot_entries(brain, snapshot))
        return snapshot
    if snapshot.exists():
        raise ValueError('existing request knowledge base has no retained receipt')
    snapshot = capture_base(brain, request_identity)
    raw = snapshot.read_bytes()
    base = json.loads(raw)
    if base.get('request_identity') != request_identity:
        raise ValueError('knowledge base request identity differs')
    list(snapshot_entries(brain, snapshot))
    receipt = dict(schema=schema, request_identity=request_identity,
        path=str(snapshot), entries=len(base['entries']), bytes=len(raw), sha256=sha256_bytes(raw))
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open('x', encoding='utf-8') as handle:
        json.dump(receipt, handle, indent=1, sort_keys=True)
    return snapshot


def write_entry(work, out, brain, cycle, include_analysis=True, principal_directory=None, calcs_only=False, day=None):
    """Write <brain>/cycle-<cycle>/ from the session's work and out directories. Returns the manifest.

    calcs_only (Greg, 2026-09-29: the Monday calculations never reached the brain because no principal finished): the
    entry takes ONLY the calculation findings of work/ (derivation digest, derivation receipt, comparison, bedrock
    receipt, derived-file witness). Everything a principal writes (response ledgers, analysis, classroom teach-back,
    priming, session documents, final classroom exchange) is listed under "unavailable" with the reason, never taken
    from whatever an earlier run left in the directories. A later full entry for the same cycle archives this one with
    a move receipt (nothing deleted).
    Every entry lists what it did not find under "unavailable" (unknown or incomplete data is listed, never dropped)."""
    if calcs_only and principal_directory is not None:
        raise ValueError('a calculations-only entry takes no principal directory')
    work, out, entry_dir = Path(work), Path(out), Path(brain) / entry_name(day, cycle)
    if not (work / 'derivation-digest-full.md').is_file():
        raise FileNotFoundError('the brain entry needs the calculation findings')
    final_files = {}
    if principal_directory is not None:
        from research.kalshi.frankie_boss.frankie_principal_adapter import digest, file_witness
        from research.kalshi.frankie_boss.c15_journal import unpack
        principal = Path(principal_directory).resolve()
        request = json.loads((principal / 'session-request.json').read_bytes())
        initial = json.loads((principal / 'session-response.json').read_bytes())
        correction = json.loads((principal / 'classroom-correction-response.json').read_bytes())
        completion = json.loads((principal / 'dipole-classroom-completion.json').read_bytes())
        receipt = json.loads((principal / 'dipole-classroom-receipt.json').read_bytes())
        pending_path = principal.parent / 'pending-feedback.c15.json'
        pending = unpack(json.loads(pending_path.read_bytes()))
        if (request['attachment']['feedback_contract'].get('feedback_status') != 'pending_target_outcomes'
                or pending.get('status') != 'pending_target_outcomes'
                or pending.get('request_id') != request['request_id']
                or pending.get('classroom_complete') is not True
                or pending.get('native_learning_performed') is not False
                or pending.get('cycle_complete') is not False
                or pending['principal_receipt']['request_sha256'] != digest(request)
                or pending['principal_receipt']['response_sha256'] != digest(initial['response'])
                or initial['response'] != json.loads((out / 'response.json').read_bytes())
                or correction['response'] != json.loads((out / 'correction-response.json').read_bytes())
                or receipt.get('teacher_complete') is not True
                or receipt['completion_hash'] != completion['completion_hash']
                or receipt['initial_session_id'] != receipt['correction_session_id']
                or receipt['initial_session_id'] != initial['response']['session_id']
                or receipt['transcript'] != file_witness(principal / 'dipole-classroom-transcript.md')):
            raise ValueError('final knowledge requires this session corrected and graded by the host')
        for name in ('session-request.json', 'session-response.json', 'classroom-correction-request.json',
                     'classroom-correction-response.json', 'dipole-classroom-acknowledgement.json',
                     'dipole-classroom-completion.json', 'dipole-classroom-receipt.json',
                     'dipole-classroom-transcript.md'):
            path = principal / name
            final_files['final-' + name] = (path.read_bytes(), path)
        grade = principal.parent / 'classroom-audit' / 'dipole-classroom-post-grade.json'
        final_files['final-host-grade.json'] = (grade.read_bytes(), grade)
        final_files['pending-target-outcomes.c15.json'] = (pending_path.read_bytes(), pending_path)
        for name in ('host-session-record.json', 'host-attestation.json',
                     'host-correction-record.json', 'host-correction-attestation.json'):
            path = out / name
            final_files['final-' + name] = (path.read_bytes(), path)
    _archive_entry(brain, entry_dir)
    entry_dir.mkdir(parents=True, exist_ok=False)
    entries = []
    unavailable = []
    CALCS_ONLY_REASON = 'calculations-only entry: written from the calculations before any principal finished'

    def absent(name, source, reason='not written by the session'):
        unavailable.append(dict(name=name, source=str(source), reason=CALCS_ONLY_REASON if calcs_only else reason))

    def put(name, data, source, kind, include=True):
        (entry_dir / name).write_bytes(data)
        entries.append(dict(name=name, bytes=len(data), sha256=sha256_bytes(data), source=str(source), kind=kind, include=include))

    claim_rows = []

    def put_file(name, source, kind, include=True):
        # one pass (Greg, 2026-10-09): hard-link the file into the entry (same filesystem: no copy) and take its sha256
        # from the source's claim row (the digest writer's write-stream sha256); a link with no holding claim is hashed
        # once; where a link fails, a streamed copy and hash in one pass as before. The entry's own file-claims.jsonl
        # gets the file's claim row so _checked_entry takes it instead of hashing the file again.
        target = entry_dir / name
        try:
            os.link(source, target)
            linked = True
        except OSError:
            linked = False
        if linked:
            claimed = _linked_claim(source)
            if claimed is not None:
                size, sha256, basis = claimed
            else:
                try:
                    import frankie_box_filehash as F
                except ImportError:
                    from deploy.aws.box import frankie_box_filehash as F
                seen = F.witness(target)
                size, sha256, basis = seen['bytes'], seen['sha256'], dict(basis='linked; hashed once here')
            if os.stat(target).st_size != size:
                raise ValueError('linked brain entry file changed size while linked: ' + str(source))
            basis['placed'] = 'hard link'
        else:
            hashed, size = hashlib.sha256(), 0
            with Path(source).open('rb') as reader, target.open('xb') as writer:
                while block := reader.read(64 * 1024 * 1024):
                    writer.write(block)
                    hashed.update(block)
                    size += len(block)
            sha256, basis = hashed.hexdigest(), dict(basis='copied and hashed in one pass', placed='copy')
        entries.append(dict(name=name, bytes=size, sha256=sha256, source=str(source), kind=kind, include=include,
                            sha256_basis=basis))
        try:
            from research.kalshi.frankie_boss.operations.ingest_block_sources import file_claim
            claim_rows.append(file_claim(target, size, sha256, 'brain entry (frankie_box_brain.write_entry) at %s'
                                         % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())))
        except Exception:  # noqa: BLE001 - a claim is a hint: without it the reader hashes
            pass

    digest = work / 'derivation-digest-full.md'
    if not digest.is_file():
        raise FileNotFoundError(f'no derivation digest at {digest}; the brain entry needs the calculation findings')
    put_file('derivation-digest-full.md', digest, 'calculation findings: the derivation digest, every layer of the pin')
    response = out / 'response.json'
    if response.is_file() and not calcs_only:
        doc = _lessons_doc(json.loads(response.read_bytes()))
        if doc:
            put(ACCOUNTING_NAME, doc.encode('utf-8'), response, 'calculation findings: the accounting entry and the output ledgers')
        else:
            absent(ACCOUNTING_NAME, response, 'the response carries no lessons')
    else:
        absent(ACCOUNTING_NAME, response)
    analysis = out / 'analysis.md'
    if analysis.is_file() and not calcs_only:
        put('analysis.md', analysis.read_bytes(), analysis, 'the run analysis', include_analysis)
    else:
        absent('analysis.md', analysis)
    derive = work / 'derive.json'
    if derive.is_file():
        try:
            doc = '# Derivation receipt (derive.json: every layer of the pin with its status, producer and sha256)\n\n```json\n' + \
                json.dumps(json.loads(derive.read_bytes()), indent=1, sort_keys=True, ensure_ascii=False) + '\n```\n'
            put('derive.md', doc.encode('utf-8'), derive, 'calculation findings: the derivation receipt (layer statuses, producers, digests)')
        except Exception:
            pass
    comparison = work / 'comparison.md'
    if comparison.is_file():
        put('comparison.md', comparison.read_bytes(), comparison, 'calculation findings: the comparison packet (derived layers beside the frozen learned-structure files)')
    classroom = work / 'classroom' / 'classroom.md'
    if calcs_only or not classroom.is_file():
        absent('classroom.md', classroom)
    else:
        put('classroom.md', classroom.read_bytes(), classroom, "the Dipole classroom: Frankie's own teach-back of the 19-dimension surface for this cycle (case by case: set include false to keep it out)")
    # Small priming describes shared evidence/knowledge; full scientific evidence has separate owner-local consumers.
    # It embeds no giant rendered table and is not proof that every required consumer is connected.
    priming = work / 'teach' / 'priming.md'
    if calcs_only or not priming.is_file():
        absent('priming.md', priming)
    else:
        put('priming.md', priming.read_bytes(), priming, 'small code priming and frozen-source references; exact contents retained, no giant rendered table')
    bedrock = work / 'bedrock' / 'receipt.json'
    if bedrock.is_file():
        try:
            doc = '# The bedrock traversal receipt (bedrock/receipt.json: the pinned producers\' own driver on this cycle\'s rows; identity, arguments, ledgers, reconciliation, sections fed)\n\n```json\n' + \
                json.dumps(json.loads(bedrock.read_bytes()), indent=1, sort_keys=True, ensure_ascii=False) + '\n```\n'
            put('bedrock.md', doc.encode('utf-8'), bedrock, 'calculation findings: the bedrock traversal receipt (the twenty bedrock layers\' provenance)')
        except Exception as error:
            entries.append(dict(name='bedrock.md', error=f'{type(error).__name__}: {error}', source=str(bedrock), include=False))
    derived = work / 'derived'
    if derived.is_dir():
        paths = [f for f in sorted(derived.iterdir()) if f.is_file()]
        # the witness of each derived file: the writing stage's FRANKIE_FILE_CLAIM_V1 claim when stat and the last 64 KiB
        # still match (<work>/file-claims.jsonl), else hashed here (file_witnesses); the document's bytes are the same
        # either way, the basis per file is on the manifest entry (additive, endings pass 2026-10-08)
        witnessed = file_witnesses(paths, file_claims(work))
        files = [dict(name=f.name, bytes=f.stat().st_size, sha256=digest) for f, (digest, _) in zip(paths, witnessed)]
        doc = ('# Derived files of this cycle (witnessed by name, bytes, sha256; the derivation digest renders their content losslessly)\n\n'
               '| file | bytes | sha256 |\n|---|---:|---|\n' + '\n'.join(f"| {f['name']} | {f['bytes']} | {f['sha256']} |" for f in files) + '\n')
        put('derived-files.md', doc.encode('utf-8'), derived, 'witness of the derived files (their content is in the digest)', False)
        entries[-1]['witness_basis'] = {f.name: basis for f, (_, basis) in zip(paths, witnessed)}
    docs = out / 'docs'
    if calcs_only:
        absent('session-doc-*.md', docs)
    elif docs.is_dir():
        for path in sorted(docs.glob('*.md')):
            put('session-doc-' + path.name, path.read_bytes(), path,
                'session document: retained whole for subsequent runs')
    for name, (data, source) in final_files.items():
        if name == 'final-host-grade.json':
            # rule R10 (CLASSROOM_RULES_V1, confirmed): graded outcomes stay out of the lesson material; the next cycle
            # carries WHERE Frankie was corrected (the teacher's correction request, kept included), never the answer
            # key or the exhaustive grade. Kept whole in the entry on record, out of his next reading.
            put(name, data, source, 'host grade: on record only, never read by Frankie (rule R10)', include=False)
        else:
            put(name, data, source, 'host-recorded final correction and retained exchange; target outcomes remain pending')
    if principal_directory is None:
        absent('final classroom exchange (request, answers, correction, receipt, transcript, grade)', 'principal directory',
               'no principal directory given: the classroom has not been corrected and graded for this cycle')
    manifest = dict(schema=SCHEMA, cycle=cycle, day=day, at=time.time(), entries=entries, unavailable=unavailable,
                    entry_kind='calculations_only' if calcs_only else 'session',
                    knowledge_status=('classroom_final_pending_target_outcomes' if final_files else 'session_findings'),
                    native_learning_performed=False if final_files else None,
                    cycle_complete=False if final_files else None,
                    note='Greg, 2026-09-21: the calculation findings of cycles 0 and 1 are in the brain without a doubt; other documents '
                         'case by case: set include to false to keep an entry out of the next corpus, add a file with include true to bring one in.')
    if claim_rows:
        try:
            from research.kalshi.frankie_boss.operations.ingest_block_sources import write_file_claims
            write_file_claims(entry_dir, claim_rows)
        except Exception:  # noqa: BLE001 - a claim is a hint
            pass
    (entry_dir / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


EXPERIMENT_ROOT = Path('/opt/frankie-box/work/experiment-calcs')
EXPERIMENT_SCHEMA = 'FRANKIE_EXPERIMENT_CALCULATIONS_V1'


def export_calculations(work, day, cycle, root=EXPERIMENT_ROOT):
    """The second copy of this cycle's calculations, for the experiments (Greg, 2026-09-29: "make sure json is gen after
    each cycle and one goes to frankie knowledge and one could go to wherever we need it to do the experiment").

    The brain entry keeps the calculations as Frankie reads them (the derivation digest). This copy keeps the SAME
    calculations as the machine-readable JSON layer files the derive stage wrote (work/derived/*.json) plus derive.json,
    hard-linked (no second write, no extra disk; a link survives any later cleanup of the run directory), each with its
    bytes and sha256 in MANIFEST.json. The bedrock layers are not exported (Greg: the experiment does not need the
    bedrock). Nothing is recalculated, averaged or reduced. Idempotent: an existing complete export is returned."""
    work = Path(work)
    target = Path(root) / str(day) / f'cycle-{cycle}'
    manifest_path = target / 'MANIFEST.json'
    if manifest_path.is_file():
        return json.loads(manifest_path.read_bytes())
    derive_path = work / 'derive.json'
    derive = json.loads(derive_path.read_bytes())
    bedrock = set((derive.get('bedrock') or {}).get('layers') or [])
    sources = [('derive.json', derive_path)]
    skipped = []
    for name, entry in sorted((derive.get('layers') or {}).items()):
        path = Path(entry['path']) if entry.get('path') else work / 'derived' / f'{name}.json'
        if name in bedrock or entry.get('bedrock'):
            # the 44 projection layers are listed in derive.bedrock.layers; the two section files
            # (bedrock_section_4_2 / 4_4) carry bedrock=True on their own entry only, and leaked through before
            skipped.append(dict(layer=name, reason='bedrock layer (not exported for the experiments)'))
        elif not path.is_file():
            skipped.append(dict(layer=name, reason=f'no layer file ({entry.get("status")}: {entry.get("reason")})'))
        else:
            sources.append((path.name, path))
    staging = target.with_name(target.name + '.partial')
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for name, path in sources:
        try:
            os.link(path, staging / name)
        except OSError:
            shutil.copy2(path, staging / name)          # another filesystem: a whole copy, same bytes
    digests = sha256_files([staging / name for name, _ in sources])
    files = [dict(name=name, source=str(path), bytes=(staging / name).stat().st_size, sha256=digest)
             for (name, path), digest in zip(sources, digests)]
    manifest = dict(schema=EXPERIMENT_SCHEMA, day=str(day), cycle=str(cycle), at=time.time(), files=files, not_exported=skipped,
                    note='the calculations of this cycle as their JSON layer files, hard-linked from the derive stage; the brain '
                         'entry carries the same calculations as the derivation digest')
    (staging / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(staging, target)
    return manifest


def check(brain, cycle, day=None):
    """The earlier cycles of this day WITHOUT a usable brain entry (no manifest, or the digest missing or not matching).
    Empty = ready. Looks for <day>-cycle-<NN> first, then the older cycle-<NN>."""
    brain = Path(brain)
    missing = []
    for n in range(int(cycle)):
        cyc = f'{n:02d}'
        d = brain / entry_name(day, cyc)
        if day is not None and not (d / 'MANIFEST.json').is_file():
            d = brain / f'cycle-{cyc}'
        m = d / 'MANIFEST.json'
        ok = False
        if m.is_file():
            try:
                manifest = json.loads(m.read_bytes())
                digest = next((e for e in manifest.get('entries', []) if e.get('name') == 'derivation-digest-full.md'), None)
                ok = bool(digest) and (d / 'derivation-digest-full.md').is_file() and \
                    _file_sha256(d / 'derivation-digest-full.md') == digest.get('sha256')
            except Exception:
                ok = False
        if not ok:
            missing.append(cyc)
    return missing


def _file_sha256(path):
    return sha256_files([path])[0]      # streamed, once per unchanged file per run


def _restore_offloaded(pointer, entry, directory):
    """A staged copy (a path under directory) of a file the pusher offloaded, taken from its box path or from S3, or
    None; the bytes must match both the pointer and the manifest entry."""
    if (pointer.get('schema') != 'FRANKIE_OFFLOADED_FILE_V1' or pointer.get('sha256') != entry.get('sha256')
            or (entry.get('bytes') is not None and pointer.get('bytes') != entry.get('bytes'))):
        return None
    staged = Path(directory) / ('.restore-' + entry['name'])
    staged.unlink(missing_ok=True)
    box = pointer.get('box_path')
    try:
        if box and Path(box).is_file() and Path(box).stat().st_size == pointer['bytes']:
            shutil.copyfile(box, staged)
        elif pointer.get('uploaded') and pointer.get('key'):
            import boto3
            boto3.client('s3', region_name=pointer.get('region', 'us-east-1')).download_file(pointer['bucket'], pointer['key'], str(staged))
        else:
            return None
        if staged.stat().st_size != pointer['bytes'] or _file_sha256(staged) != pointer['sha256']:
            staged.unlink(missing_ok=True)
            return None
    except Exception:
        staged.unlink(missing_ok=True)
        return None
    return staged


def restore_from_git(brain, cycles, repo, day, remote='origin', branch_format='root/cycle-{cycle}-response'):
    """Restore the named cycles' entries from their published branches (a fetch into FETCH_HEAD; the checkout is never
    moved). Returns {cycle: 'restored' | reason}. Files land under <brain>/<day>-cycle-<NN>/ only when the manifest and every
    listed file arrive and match their sha256."""
    import subprocess
    brain, repo = Path(brain), Path(repo)
    result = {}
    for cyc in cycles:
        branch = branch_format.format(cycle=cyc)
        prefix = f'research/kalshi/frankie_boss/runs/{day}/root/brain/cycle-{cyc}'
        fetch = subprocess.run(['git', '-C', str(repo), 'fetch', '-q', '--depth', '1', remote, branch], capture_output=True, text=True)
        if fetch.returncode:
            result[cyc] = f'branch {branch} not fetchable: {fetch.stderr.strip()[:200]}'
            continue
        show = subprocess.run(['git', '-C', str(repo), 'show', f'FETCH_HEAD:{prefix}/MANIFEST.json'], capture_output=True)
        if show.returncode:
            result[cyc] = f'no brain entry on {branch} ({prefix}/MANIFEST.json)'
            continue
        try:
            manifest = json.loads(show.stdout)
        except Exception:
            result[cyc] = f'unreadable manifest on {branch}'
            continue
        staged = {}
        bad = None
        d = brain / entry_name(day, cyc)
        d.mkdir(parents=True, exist_ok=True)
        for e in manifest.get('entries', []):
            got = subprocess.run(['git', '-C', str(repo), 'show', f'FETCH_HEAD:{prefix}/{e["name"]}'], capture_output=True)
            if got.returncode:
                # the pusher commits a file of 90 MB or more as <name>.gz; the plain bytes must still match the manifest
                zipped = subprocess.run(['git', '-C', str(repo), 'show', f'FETCH_HEAD:{prefix}/{e["name"]}.gz'], capture_output=True)
                if not zipped.returncode:
                    import gzip
                    got = subprocess.CompletedProcess(zipped.args, 0, gzip.decompress(zipped.stdout), b'')
            if got.returncode:
                # a file too large for git is committed as <name>.s3.json (frankie_box_offload.py): the box copy or S3
                pointer = subprocess.run(['git', '-C', str(repo), 'show', f'FETCH_HEAD:{prefix}/{e["name"]}.s3.json'], capture_output=True)
                if not pointer.returncode:
                    staged_path = _restore_offloaded(json.loads(pointer.stdout), e, d)
                    if staged_path is not None:
                        staged[e['name']] = staged_path
                        continue
            if got.returncode or sha256_bytes(got.stdout) != e.get('sha256'):
                bad = e['name']
                break
            staged[e['name']] = got.stdout
        if bad:
            for value in staged.values():
                if isinstance(value, Path):
                    value.unlink(missing_ok=True)
            result[cyc] = f'{bad} missing or not matching its sha256 on {branch}'
            continue
        for name, data in staged.items():
            if isinstance(data, Path):
                os.replace(data, d / name)
            else:
                (d / name).write_bytes(data)
        (d / 'MANIFEST.json').write_bytes(show.stdout)
        result[cyc] = 'restored'
    return result


FROZEN_DIR = 'frozen-learned-structure'
FROZEN_ROW = re.compile(r'^\|\s*`([^`]+)`\s*\|\s*frozen_learned_structure\s*\|')
FILE_REF = re.compile(r'`([^`]+)`\s+`([0-9a-f]{12})`')


def frozen_files_from_prompt(historical_prompt_text):
    """{(path, sha256 prefix): [layers]} for every file the request's knowledge table names under frozen_learned_structure."""
    found = {}
    for line in historical_prompt_text.splitlines():
        m = FROZEN_ROW.match(line)
        if not m:
            continue
        layer = m.group(1)
        for path, prefix in FILE_REF.findall(line):
            found.setdefault((path, prefix), []).append(layer)
    return found


def write_frozen_entry(historical_prompt, repo, brain):
    """Greg, 2026-09-21 ("unfreeze the structure content"): the frozen learned-structure layers are delivered BY PATH
    only (the request names the files and 12-char digests; Frankie saw only that table in cycle 0). This writes
    <brain>/frozen-learned-structure/ from the box's own checkout: every named file whose bytes match the delivered
    digest prefix, flattened by path, with a manifest (include true); a file whose bytes differ, or is absent, is
    listed with include false and the reason (case by case: flip include to carry the checkout's version anyway).
    Deterministic and idempotent; rebuilt at every session start."""
    repo, entry_dir = Path(repo), Path(brain) / FROZEN_DIR
    text = Path(historical_prompt).read_text(encoding='utf-8', errors='replace')
    files = frozen_files_from_prompt(text)
    repo_root = Path(repo).resolve()
    for (path, _prefix) in list(files):
        # containment: a path the delivered prompt names is data; it must resolve inside the checkout (never .. or absolute)
        if Path(path).is_absolute() or '..' in Path(path).parts or not (repo_root / path).resolve().is_relative_to(repo_root):
            raise ValueError(f'the delivered prompt names a frozen file outside the checkout: {path!r}')
    entries = []
    for (path, prefix), layers in sorted(files.items()):
        src = repo / path
        name = path.replace('/', '__')
        if not src.is_file():
            entries.append(dict(name=name, source=path, layers=layers, include=False, reason='file absent from the checkout', delivered_prefix=prefix))
            continue
        data = src.read_bytes()
        digest = sha256_bytes(data)
        e = dict(name=name, source=path, bytes=len(data), sha256=digest, layers=layers, delivered_prefix=prefix,
                 kind='frozen learned structure: a file the request names for these layers, from the checkout')
        if digest.startswith(prefix):
            e['include'] = True
        else:
            e['include'] = False
            e['reason'] = 'the checkout bytes do not match the delivered digest prefix; excluded unless include is set true'
        entries.append(e)
    manifest = dict(schema='FRANKIE_BOX_BRAIN_FROZEN_ENTRY_V1', at=time.time(), historical_prompt=str(historical_prompt),
                    layers=sorted({l for ls in files.values() for l in ls}), entries=entries,
                    note='the frozen learned-structure content, so the comparison step can run; rebuilt from the checkout at every session start')
    if (entry_dir / 'MANIFEST.json').is_file():
        previous, _ = _checked_entry(entry_dir)
        stable = lambda value: {k: v for k, v in value.items() if k != 'at'}
        if stable(previous) == stable(manifest):
            return previous
    _archive_entry(brain, entry_dir)
    entry_dir.mkdir(parents=True, exist_ok=False)
    for entry in entries:
        if 'sha256' not in entry:
            continue
        data = (repo / entry['source']).read_bytes()
        if sha256_bytes(data) != entry['sha256'] or len(data) != entry['bytes']:
            raise ValueError('frozen source changed while preserving knowledge')
        (entry_dir / entry['name']).write_bytes(data)
    (entry_dir / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def frozen_entry(brain):
    """(manifest, entry_dir) of the standing frozen entry, or (None, None)."""
    d = Path(brain) / FROZEN_DIR
    m = d / 'MANIFEST.json'
    if not m.is_file():
        return None, None
    try:
        return json.loads(m.read_bytes()), d
    except Exception:
        return None, None


def _stale_meeting_sources(manifest, directory, records):
    """Selection-only exclusion of a discussion of an explicitly replaced exchange."""
    if manifest.get('entry_kind') != 'meeting' or not records:
        return []
    replacements = []
    for item in manifest.get('entries', []):
        if not item.get('include'):
            continue
        if Path(item['name']).name != item['name']:
            raise ValueError('meeting member leaves its retained entry')
        raw = (Path(directory) / item['name']).read_bytes()
        if len(raw) != item['bytes'] or sha256_bytes(raw) != item['sha256']:
            raise ValueError('retained meeting member differs from its manifest')
        meeting = json.loads(raw)
        if meeting.get('schema') != 'FRANKIE_GRANITE_MEETING_V1':
            raise ValueError('meeting entry contains another artifact schema')
        old = (meeting.get('exchange') or {}).get('sha256')
        if old in records:
            replacements.append(records[old]['record'])
    return replacements


def entries_before(brain, cycle, day=None):
    """(label, manifest, entry_dir) for every entry written so far, from every day and every cycle, EXCEPT this run's own
    day+cycle (Greg, 2026-09-29: the cycles replay the day and restart earlier, so his reasoning may carry later data;
    only the actual run data ahead of time is walled, and that is the cycle being run). Sorted by day (older key first,
    day unknown) then cycle. Without a day (an older caller) the older rule's own-slot exclusion applies to cycle-<NN>."""
    brain = Path(brain)
    found = []
    if not brain.is_dir():
        return found
    import frankie_box_experiment_review as REVIEW
    records = REVIEW.corrections([brain])
    own = entry_name(day, cycle)
    for d in sorted({p for pattern in ENTRY_GLOBS for p in brain.glob(pattern) if p.is_dir()}):
        parsed = parse_entry_name(d.name)
        m = d / 'MANIFEST.json'
        if parsed is None or not m.is_file() or d.name == own:
            continue
        try:
            manifest = json.loads(m.read_bytes())
        except Exception:
            continue
        replaced = _stale_meeting_sources(manifest, d, records)
        if replaced:
            # Return a reader projection only. Original bytes, manifest and pinned bases stay immutable.
            manifest = dict(manifest, entries=[dict(item, include=False,
                reason='meeting discussed an explicitly replaced exchange') for item in manifest.get('entries', [])],
                unavailable=list(manifest.get('unavailable') or []) + [dict(
                    reason='meeting discussed an explicitly replaced exchange', corrections=replaced)])
        entry_day, cyc = parsed
        label = (f'{entry_day}-{cyc}' if cyc in DAY_KINDS else
                 f'{entry_day}-cycle-{cyc}' if entry_day else f'cycle-{cyc} (day not recorded)')
        found.append(((entry_day or '', DAY_KINDS[cyc] if cyc in DAY_KINDS else int(cyc)), label, manifest, d))
    return [(label, manifest, d) for _, label, manifest, d in sorted(found, key=lambda x: x[0])]


def _correction_records(brain, snapshot=None):
    import frankie_box_experiment_review as REVIEW
    records = REVIEW.corrections([brain])
    if snapshot:
        pinned = set(json.loads(Path(snapshot).read_bytes()).get('corrections') or [])
        if not pinned.issubset({r['record']['sha256'] for r in records.values()}):
            raise ValueError('pinned request correction records are missing or changed')
    return records


def _corrected_knowledge(brain, pin, *, day, records, snapshot=None):
    """A true complete-source successor; a pinned request may not silently acquire later corrections."""
    import frankie_box_experiment_review as REVIEW
    raw = Path(pin['path']).read_bytes()
    if sha256_bytes(raw) != pin['sha256'] or ('bytes' in pin and len(raw) != pin['bytes']):
        raise ValueError('included knowledge differs from its selected pin: ' + str(pin['path']))
    delivered = REVIEW.current_document(dict(pin, content=json.loads(raw)), records, brain, day=day, stage='root')
    if snapshot:
        pinned = set(json.loads(Path(snapshot).read_bytes()).get('corrections') or [])
        if any(r['sha256'] not in pinned for r in delivered.get('corrections_applied') or []):
            raise ValueError('pending request knowledge has a later correction; an explicit successor request is required')
    return delivered, Path(delivered['path']).read_bytes()


def identity(brain, cycle, *, snapshot=None, day=None):
    """A short digest of every included prior entry (name + sha256): part of the corpus identity."""
    h = hashlib.sha256()
    records = _correction_records(brain, snapshot)
    fm, _ = (None, None) if snapshot else frozen_entry(brain)
    for e in (fm or {}).get('entries', []):
        if e.get('include'):
            if records and e['name'].endswith('.json'):
                e, _ = _corrected_knowledge(brain, dict(e, path=str(Path(brain) / FROZEN_DIR / e['name'])),
                                            day=day, records=records, snapshot=snapshot)
            h.update(f'frozen/{e["name"]}/{e["sha256"]}\n'.encode())
    for cyc, manifest, d in (snapshot_entries(brain, snapshot) if snapshot else entries_before(brain, cycle, day)):
        for e in manifest.get('entries', []):
            if e.get('include'):
                if records and e['name'].endswith('.json'):
                    e, _ = _corrected_knowledge(brain, dict(e, path=str(d / e['name'])),
                                                day=day, records=records, snapshot=snapshot)
                h.update(f'{cyc}/{e["name"]}/{e["sha256"]}\n'.encode())
    for row, _ in _school_for(brain, snapshot, day, records=records)[0]:
        h.update(f'school/{row["day"]}/{row["sha256"]}\n'.encode())
    return h.hexdigest()[:16]


SCHOOL_SECTIONS = ('frankie_classwork', 'boss_teacher', 'scientific_teacher', 'exchange', 'day_file')


def _school_for(brain, snapshot, day, *, records=None):
    """All completed other-day school records, regardless of trading date, or the exact captured selection.
    A base captured before school existed pins none. Without a day nothing is read (own-answer exclusion needs it).
    """
    if day is None:
        return [], []
    if snapshot:
        loaded, listed = school_rows(brain, day, pinned=json.loads(Path(snapshot).read_bytes()).get('school') or [])
    else:
        loaded, listed = school_rows(brain, day)
    if records:
        corrected = []
        for row, doc in loaded:
            delivered, _ = _corrected_knowledge(brain, dict(path=str(Path(brain) / SCHOOL_DIR / row['file']),
                sha256=row['sha256']), day=day, records=records, snapshot=snapshot)
            corrected.append((dict(row, sha256=delivered['sha256'], path=delivered['path']), delivered['content']))
        loaded = corrected
    return loaded, listed


def load(brain, cycle, *, snapshot=None, carried=None, day=None):
    """(text, members): the included, digest-verified entries of every earlier cycle as corpus text plus member records.
    carried: {sha256: where} of content the corpus already holds (the current cycle's digest). An entry whose manifest
    sha256 is already carried, or equal to an earlier entry's, is written once: later copies are a one-line reference
    to the first (Greg, 2026-09-28: dedupe; identical bytes are read by the model once) and are not re-read from disk."""
    parts, members = [], []
    carried = dict(carried or {})
    records = _correction_records(brain, snapshot)

    def reference(label, e):
        """A one-line pointer for bytes already in the corpus, or None when the bytes are new."""
        where = carried.get(e.get('sha256'))
        if where is None:
            return None
        parts.append(f"\n\n## Frankie's brain: {label}: the same bytes as {where} (sha256 {e['sha256'][:16]}, {e.get('bytes')} bytes); "
                     'carried once, not repeated\n')
        members.append(dict(name=label, bytes=e.get('bytes'), sha256=e['sha256'], treatment=f'brain: same bytes as {where}; carried once (dedupe by sha256)'))
        return where
    fm, fd = (None, None) if snapshot else frozen_entry(brain)
    if fm:
        parts.append("\n\n## Frankie's brain: the frozen learned structure, the files the request's knowledge layers name (delivered by path; "
                     "their content here from the checkout, each verified against the delivered digest). Compare this cycle's derivations "
                     "with them, layer by layer.\n")
        for e in fm.get('entries', []):
            name = e.get('name', '')
            p = fd / name
            if not e.get('include'):
                members.append(dict(name=f'brain-frozen-{name}', bytes=e.get('bytes'), treatment=f'frozen file excluded: {e.get("reason", "include false")}'))
                continue
            if records and name.endswith('.json'):
                e, _ = _corrected_knowledge(brain, dict(e, path=str(p)), day=day, records=records, snapshot=snapshot)
                p = Path(e['path'])
            if reference(f'brain-frozen-{name}', e):
                continue
            data = p.read_bytes() if p.is_file() else None
            if data is None or sha256_bytes(data) != e.get('sha256'):
                members.append(dict(name=f'brain-frozen-{name}', treatment='frozen file missing or changed since its manifest; not in the corpus'))
                continue
            parts.append(f"\n### {e['source']} (layers: {', '.join(e.get('layers', []))}; sha256 {e['sha256'][:16]})\n\n" + data.decode('utf-8', errors='replace') + '\n')
            members.append(dict(name=f'brain-frozen-{name}', bytes=len(data), sha256=e['sha256'], treatment='brain: frozen learned-structure file, whole'))
            carried[e['sha256']] = f'the frozen file {e["source"]}'
    for cyc, manifest, d in (snapshot_entries(brain, snapshot) if snapshot else entries_before(brain, cycle, day)):
        for e in manifest.get('entries', []):
            name = e.get('name', '')
            p = d / name
            if not e.get('include'):
                members.append(dict(name=f'brain-cycle-{cyc}-{name}', bytes=e.get('bytes'), sha256=e.get('sha256'), treatment='brain entry excluded by its manifest (include false); not in the corpus'))
                continue
            if records and name.endswith('.json'):
                e, _ = _corrected_knowledge(brain, dict(e, path=str(p)), day=day, records=records, snapshot=snapshot)
                p = Path(e['path'])
            if reference(f'brain-cycle-{cyc}-{name}', e):
                continue
            if not p.is_file():
                members.append(dict(name=f'brain-cycle-{cyc}-{name}', treatment='brain entry file missing; not in the corpus'))
                continue
            if name == 'derivation-digest-full.md':
                # Greg, 2026-09-28 ("Do what we did on Sunday night to the full Monday"): a carried digest is read as the 6-hour
                # run read one: up to its bedrock heading, whole (frankie_box_digest_read); sha256 of the whole file checked
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                import frankie_box_digest_read as DR
                text, stats = DR.legacy_read(p)
                if stats['digest_sha256'] != e.get('sha256'):
                    members.append(dict(name=f'brain-cycle-{cyc}-{name}', bytes=stats['digest_bytes'], treatment='brain entry bytes differ from its manifest; not in the corpus'))
                    continue
                kept = ', bedrock retained on the box' if stats['bedrock_at'] is not None else ''
                parts.append(f"\n\n## Frankie's brain: cycle {cyc}, {name} ({e.get('kind', 'document')}; carried forward: header, layer statuses "
                             f"and legacy tables whole{kept}; sha256 {e['sha256'][:16]})\n\n" + text + '\n')
                members.append(dict(name=f'brain-cycle-{cyc}-{name}', bytes=stats['digest_bytes'], sha256=e['sha256'],
                                    treatment='brain: prior cycle digest, header, layer statuses and legacy tables whole' + kept, read=stats))
                carried[e['sha256']] = f'brain cycle {cyc} {name}'
                continue
            data = p.read_bytes()
            if sha256_bytes(data) != e.get('sha256'):
                members.append(dict(name=f'brain-cycle-{cyc}-{name}', bytes=len(data), treatment='brain entry bytes differ from its manifest; not in the corpus'))
                continue
            parts.append(f"\n\n## Frankie's brain: cycle {cyc}, {name} ({e.get('kind', 'document')}; carried forward whole, sha256 {e['sha256'][:16]})\n\n"
                         + data.decode('utf-8', errors='replace') + '\n')
            members.append(dict(name=f'brain-cycle-{cyc}-{name}', bytes=len(data), sha256=e['sha256'], treatment='brain: prior cycle calculation findings, whole'))
            carried[e['sha256']] = f'brain cycle {cyc} {name}'
    # Frankie's school knowledge base: every earlier classroom day's school file, section by section, each labelled with
    # its author (R11). An inline item whose source bytes are already carried (the same lessons or exchange file read as
    # a brain entry above) is a one-line reference; a pointer item (a large file) is named, never read here.
    loaded, listed = _school_for(brain, snapshot, day, records=records)
    if loaded:
        parts.append("\n\n## Frankie's school: the school knowledge of every earlier classroom day (FRANKIE_SCHOOL_KNOWLEDGE_V1), "
                     'each section labelled with its author; counts per day, never pooled\n')
    for row, doc in loaded:
        sections = doc.get('sections') or {}
        for section in [x for x in SCHOOL_SECTIONS if x in sections] + sorted(set(sections) - set(SCHOOL_SECTIONS)):
            body = sections[section] or {}
            for item in body.get('items') or []:
                label = f'school-{row["day"]}-{section}-{item.get("name")}'
                if item.get('inline') and 'content' in item:
                    if item.get('sha256') and reference(label, item):
                        continue
                    text = json.dumps(item['content'], indent=1, sort_keys=True, default=str)
                    parts.append(f"\n### School day {row['day']} (report #{row.get('report_number')}), {section} by "
                                 f"{item.get('author') or body.get('author')}: {item.get('name')} (source {item.get('path')}, "
                                 f"sha256 {str(item.get('sha256'))[:16]})\n\n" + text + '\n')
                    members.append(dict(name=label, bytes=len(text), sha256=item.get('sha256'),
                                        treatment=f'school: {section} ({item.get("author") or body.get("author")}), inline'))
                    if item.get('sha256'):
                        carried[item['sha256']] = f'school day {row["day"]} {section} {item.get("name")}'
                else:
                    why = item.get('pointer_reason') or 'a pointer'
                    parts.append(f"\n### School day {row['day']}, {section} by {item.get('author') or body.get('author')}: "
                                 f"{item.get('name')}: a pointer, not read here ({why}); path {item.get('path')}, "
                                 f"sha256 {item.get('sha256')}, bytes {item.get('bytes')}\n")
                    members.append(dict(name=label, bytes=item.get('bytes'), sha256=item.get('sha256'),
                                        treatment=f'school pointer; not in the corpus ({why})'))
        for m in doc.get('missing') or []:
            parts.append(f"- School day {row['day']}: {m.get('section')} / {m.get('item')} missing: {m.get('reason')}\n")
    for x in listed:
        members.append(dict(name=f'school-{(x.get("row") or {}).get("day")}', treatment='school day not read: ' + x['reason']))
    return ''.join(parts), members


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--work', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--brain', required=True)
    p.add_argument('--cycle', required=True)
    p.add_argument('--principal-directory')
    p.add_argument('--calcs-only', action='store_true', help='only the calculation findings (no principal has finished)')
    p.add_argument('--day', default=None, help='YYYYMMDD: key the entry <day>-cycle-<NN> (days never share a slot)')
    a = p.parse_args()
    m = write_entry(a.work, a.out, a.brain, a.cycle, principal_directory=a.principal_directory, calcs_only=a.calcs_only,
                    day=a.day)
    print(f"brain entry day {a.day} cycle {a.cycle}: {len(m['entries'])} documents in {Path(a.brain) / entry_name(a.day, a.cycle)}")
    for e in m['entries']:
        print(f"  {e['name']}: {e.get('bytes')} bytes, include {e['include']}")
    for u in m['unavailable']:
        print(f"  UNAVAILABLE {u['name']}: {u['reason']}")


if __name__ == '__main__':
    main()
