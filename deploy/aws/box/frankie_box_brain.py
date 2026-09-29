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
ENTRY_GLOBS = ('cycle-*', '[0-9]' * 8 + '-cycle-*')


def entry_name(day, cycle):
    """<YYYYMMDD>-cycle-<NN> with a day, the older cycle-<NN> without one."""
    if day is None:
        return f'cycle-{cycle}'
    if not re.fullmatch('[0-9]{8}', str(day)):
        raise ValueError('brain entry day must be YYYYMMDD')
    return f'{day}-cycle-{cycle}'


def parse_entry_name(name):
    """(day or None, cycle) of an entry directory name, or None when the name is not an entry."""
    match = re.fullmatch(r'(?:([0-9]{8})-)?cycle-([0-9]+)', name)
    return (match.group(1), match.group(2)) if match else None
ACCOUNTING_NAME = 'accounting-and-ledgers.md'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_files(paths):
    """sha256_bytes(path.read_bytes()) for each path, in order, streamed (derived layers run to many GB) and hashed on
    threads (hashlib releases the GIL)."""
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
    with ThreadPoolExecutor(min(14, len(paths))) as pool:
        return list(pool.map(one, paths))


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
    # streamed and hashed on threads (a digest runs to many GB); same check as before
    for (entry, path), digest in zip(included, sha256_files([p for _, p in included])):
        if digest != entry.get('sha256'):
            raise ValueError('included historical knowledge missing or changed: ' + entry.get('name', ''))
    return manifest, sha256_bytes(raw)


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
    entries = {}
    for path in sorted(candidates):
        manifest, digest = _checked_entry(path.parent)
        if digest in entries:
            continue
        destination = history / ('entry-' + digest)
        if not destination.exists():
            shutil.copytree(path.parent, destination)
        _checked_entry(destination, digest)
        entries[digest] = dict(path=str(destination.relative_to(brain)), sha256=digest,
                               cycle=manifest.get('cycle'), day=manifest.get('day'), source_schema=manifest.get('schema'))
    value = dict(schema='FRANKIE_ACCUMULATED_KNOWLEDGE_BASE_V1', request_identity=request_identity,
                 entries=list(entries.values()), rule='all previously stored intact knowledge; immutable for this request')
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

    def put_file(name, source, kind, include=True):
        # streamed copy and hash in one pass (the digest runs to many GB; same bytes and entry as put)
        hashed, size = hashlib.sha256(), 0
        with Path(source).open('rb') as reader, (entry_dir / name).open('xb') as writer:
            while block := reader.read(64 * 1024 * 1024):
                writer.write(block)
                hashed.update(block)
                size += len(block)
        entries.append(dict(name=name, bytes=size, sha256=hashed.hexdigest(), source=str(source), kind=kind, include=include))

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
    # The bedrock-built exhaustion/D priming is gone (the bedrock is the teachers' logic helper, never Frankie's knowledge
    # base; Greg, 2026-09-29). The brain carries only the small code priming (no bedrock in it).
    priming = work / 'teach' / 'priming.md'
    if calcs_only or not priming.is_file():
        absent('priming.md', priming)
    else:
        put('priming.md', priming.read_bytes(), priming, 'the small priming: where exhaustion and D are learned (the classroom) and the frozen files for them, by name and digest; no bedrock; code only')
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
        files = [dict(name=f.name, bytes=f.stat().st_size, sha256=digest) for f, digest in zip(paths, sha256_files(paths))]
        doc = ('# Derived files of this cycle (witnessed by name, bytes, sha256; the derivation digest renders their content losslessly)\n\n'
               '| file | bytes | sha256 |\n|---|---:|---|\n' + '\n'.join(f"| {f['name']} | {f['bytes']} | {f['sha256']} |" for f in files) + '\n')
        put('derived-files.md', doc.encode('utf-8'), derived, 'witness of the derived files (their content is in the digest)', False)
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
        if name in bedrock:
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


def entries_before(brain, cycle, day=None):
    """(label, manifest, entry_dir) for every entry written so far, from every day and every cycle, EXCEPT this run's own
    day+cycle (Greg, 2026-09-29: the cycles replay the day and restart earlier, so his reasoning may carry later data;
    only the actual run data ahead of time is walled, and that is the cycle being run). Sorted by day (older key first,
    day unknown) then cycle. Without a day (an older caller) the older rule's own-slot exclusion applies to cycle-<NN>."""
    brain = Path(brain)
    found = []
    if not brain.is_dir():
        return found
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
        entry_day, cyc = parsed
        label = f'{entry_day}-cycle-{cyc}' if entry_day else f'cycle-{cyc} (day not recorded)'
        found.append(((entry_day or '', int(cyc)), label, manifest, d))
    return [(label, manifest, d) for _, label, manifest, d in sorted(found, key=lambda x: x[0])]


def identity(brain, cycle, *, snapshot=None, day=None):
    """A short digest of every included prior entry (name + sha256): part of the corpus identity."""
    h = hashlib.sha256()
    fm, _ = (None, None) if snapshot else frozen_entry(brain)
    for e in (fm or {}).get('entries', []):
        if e.get('include'):
            h.update(f'frozen/{e["name"]}/{e["sha256"]}\n'.encode())
    for cyc, manifest, d in (snapshot_entries(brain, snapshot) if snapshot else entries_before(brain, cycle, day)):
        for e in manifest.get('entries', []):
            if e.get('include'):
                h.update(f'{cyc}/{e["name"]}/{e["sha256"]}\n'.encode())
    return h.hexdigest()[:16]


def load(brain, cycle, *, snapshot=None, carried=None, day=None):
    """(text, members): the included, digest-verified entries of every earlier cycle as corpus text plus member records.
    carried: {sha256: where} of content the corpus already holds (the current cycle's digest). An entry whose manifest
    sha256 is already carried, or equal to an earlier entry's, is written once: later copies are a one-line reference
    to the first (Greg, 2026-09-28: dedupe; identical bytes are read by the model once) and are not re-read from disk."""
    parts, members = [], []
    carried = dict(carried or {})

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
