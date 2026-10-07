"""The experiment's classroom arm V2 for one day of a run of any length (1, 2, 3 or N days are configured identically; the
run's day count is the plan's and is never assumed here): the classroom arm (frankie_box_experiment_classroom.py, unchanged) plus
Frankie's historical data points (Greg, 2026-09-29: "we should be able to unlock classroom and teachers for today. We're
the ones who made the locks"). Swap, not edit: every pinned file keeps its bytes; the V1 script stays as it was.

The same calls as the V1 arm, in the same order and with the same arguments, for the 19 components and 171 pairs: the
package (prepare_integrated_cycle, through dipole_classroom_v2.prepare_cycle_v2), Frankie's code answers
(frankie_box_classroom_code), the assembly and validation (frankie_box_classroom), the host's grade, the relationship-view
cross-check, the novel findings, the correction and its answer, the acknowledgement, the completion and the transcript.
The V1 request identity stays the digest of the V1 model-visible request, so the V1 grade, correction, acknowledgement
and completion are exactly what the V1 arm computes.

Added beside them (dipole_classroom_external.py): the BOSS teacher's external section (built once per day in the teacher
rows directory, by the teacher-only step or here), its model-visible part, Frankie's code answers for it
(frankie_box_classroom_external_code), the host's exact grade, the correction turn (Frankie's code's correction answer,
the classroom's acknowledgement and resolution validators), the external completion. The day file (FRANKIE_DAY_EXTERNAL_V1)
is given as --day-external + --day-external-sha256 (a mismatch is refused) or taken from beside the sealed ingest named in
the teacher rows receipt (its day-external-receipt.json sha256 must match the bytes).

Jev's material is the V2 model-visible classroom ({'dipole_classroom', 'dipole_external'}), written BEFORE any answer to
<calculations>/jev-material/classroom-request.json. Frankie's brain entry <day>-cycle-00 is written by frankie_box_brain
(unchanged), then carries his external teach-back (classroom-external.md, include true) and lists the day file as an
attachment (name, sha256, bytes, path, S3 key; not copied into his corpus, the same way the day-external step lists it).
Wednesday takes PREVIOUS = Tuesday's work/classroom: the V1 history and grade as the V1 arm does, and the external
history and grade the same way (only the correction ids travel, rule R10).

Recovery retains the full package, learner inputs and each completed operation in local phase files. A stop finishes
the active operation, saves its result and returns 75; resume loads it without repeating its calculations. The final
receipt is published after histories and the complete brain entry. completion.json alone is not a finished stage.

THE SCHOOL (Greg, 2026-10-06): before answers, read completed school files available at this workflow boundary,
regardless of trading-date order. Each <brain>/school/<day>.json is checked against its index row (a missing or changed
file is listed, never read), and Frankie's code checks supported hypotheses on today's lawful mode-specific evidence
(frankie_box_classroom_code.school_reproduction: his earlier novel findings and the teachers' own findings, per earlier
day, counts only). The result travels in code-answers.json ("school") and the receipt ("school_knowledge"); it is not
part of the model-visible request, so Jev's material never carries it.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import signal
import pickle
import sys
import time
from pathlib import Path

BOX = Path(__file__).resolve().parent
ROOT = BOX.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BOX))
SCHEMA = 'FRANKIE_EXPERIMENT_CLASSROOM_RECEIPT_V2'
MODEL_IDENTITY = "Frankie's code (computed; no model)"
STOP_POLL_SECONDS = 1.0   # the lane stop file is polled at most this often (SIGTERM is immediate)
BRAIN_PUBLICATION_SCHEMA = 'FRANKIE_CLASSROOM_BRAIN_PUBLICATION_V1'


def _box(name):
    spec = importlib.util.spec_from_file_location(name, BOX / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    # Reuse the existing streamed, changed-file-aware witness within this process;
    # repeated source/receipt checks need not reread unchanged owner-local bytes.
    from frankie_box_filehash import sha256_file
    return sha256_file(path)


def _bytes(path, raw):
    path = Path(path)
    if path.exists() and path.read_bytes() == raw:
        return
    from frankie_box_durable import write_bytes
    write_bytes(path, raw)


def _text(path, text):
    _bytes(path, text.encode('utf-8'))


def _dump(path, body):
    _text(path, json.dumps(body, indent=1, sort_keys=True, default=str))


DIRECTIVE_PATH = ROOT / 'research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'


def directive():
    """The experiment's directive (Greg, 2026-09-29: "make sure frankie and teachers and classroom has the directive of
    what we're shooting for with this experiment"), loaded whole, and its witness for the receipt."""
    data = DIRECTIVE_PATH.read_bytes()
    value = json.loads(data)
    if value.get('schema') != 'FRANKIE_EXPERIMENT_DIRECTIVE_V1' or not value.get('directive'):
        raise ValueError('%s is not the experiment directive' % DIRECTIVE_PATH)
    return value, dict(path=str(DIRECTIVE_PATH), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def _attach_to_brain_entry(entry_dir, classroom_external_md, day_file, day_sha, day_receipt, day):
    """His external teach-back into the entry (include true) and the day file listed as an attachment; MANIFEST rewritten."""
    manifest_path = Path(entry_dir) / 'MANIFEST.json'
    manifest = json.loads(manifest_path.read_bytes())
    data = Path(classroom_external_md).read_bytes()
    name = 'classroom-external.md'
    _bytes(Path(entry_dir) / name, data)
    manifest['entries'] = [e for e in manifest['entries'] if e['name'] != name]
    manifest['entries'].append(dict(name=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                    source=str(classroom_external_md), include=True,
                                    kind="the Dipole classroom's external section: Frankie's own teach-back of his historical "
                                         "data points beside the 19 dimensions for this cycle"))
    has_receipt = bool(day_receipt) and Path(day_receipt).is_file()
    receipt = json.loads(Path(day_receipt).read_bytes()) if has_receipt else {}
    manifest['attachments'] = [e for e in manifest.get('attachments', []) if e['name'] != 'day-external.json']
    manifest['attachments'].append(dict(
        name='day-external.json', sha256=day_sha, bytes=Path(day_file).stat().st_size, path=str(day_file),
        s3_key=receipt.get('s3_key'), brain_attachment=f'{day}-external', schema='FRANKIE_DAY_EXTERNAL_V1', included=False,
        # a missing day-external-receipt.json leaves s3_key unknown: said here, never a silent None
        s3_key_basis=('day-external-receipt.json beside the day file' if has_receipt else
                      'unknown: no day-external-receipt.json beside the day file; the S3 key was not recorded'),
        note='the day file of his historical data points, listed (not copied into his reading corpus); every reader of '
             'the ingest reads it through operations/frankie_day_external.AsOfReader at its own cutoff'))
    _dump(manifest_path, manifest)
    return manifest


def _pin_outputs(directory, names):
    """{name: pin} for the produced files on disk, and the names that are not (listed, never pinned)."""
    pinned, listed = {}, []
    for name in names:
        path = Path(directory) / name
        if path.is_file():
            pinned[name] = dict(path=str(path), bytes=path.stat().st_size, sha256=_sha256(path))
        else:
            listed.append(dict(name=name, reason='not on disk after the classroom wrote its files'))
    return pinned, listed


def _failure_receipt(attempt, day, status, error, exit_code):
    """Nothing fails silently (Greg, 2026-10-07): an uncaught refusal or failure lands on receipt.json with its
    reason and the operations that were saved, before the error propagates. A complete receipt is never
    overwritten; when the work directory is not known yet the record goes to stdout only."""
    record = dict(schema=SCHEMA, day=day, status=status, error_type=type(error).__name__, reason=str(error),
                  exit_code=exit_code, saved_phases=sorted(attempt.get('phases') or {}),
                  phase_timings=dict(attempt.get('timings') or {}), received=attempt.get('received'),
                  listed='the classroom stopped on this error; every saved operation is retained and a resume reuses it; '
                         'no answer, grade or brain entry was written by this attempt beyond the saved phases',
                  stage_reached=attempt.get('stage'))
    directory = attempt.get('directory')
    if directory is not None:
        path = Path(directory) / 'receipt.json'
        try:
            existing = json.loads(path.read_bytes()) if path.is_file() else {}
        except ValueError:
            existing = {}
        if existing.get('status') == 'complete':
            record['listed'] = 'a complete receipt already stands in this directory and is preserved; this failure is printed only'
        else:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
                _dump(path, record)
            except OSError as write_error:
                record['receipt_not_written'] = str(write_error)
    print(json.dumps(dict((k, v) for k, v in record.items() if k != 'received'), sort_keys=True, default=str), flush=True)


def run(day, calculations, teacher_rows, previous, brain, day_external, day_external_sha256):
    requested = [False]
    previous_handler = signal.signal(signal.SIGTERM, lambda *_: requested.__setitem__(0, True))
    stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')
    # Efficiency (Greg, 2026-10-07): the stop file is polled at most once per STOP_POLL_SECONDS, not once per
    # picture (one stat call per picture is millions of syscalls on a big day); SIGTERM is immediate. A stop is
    # honoured within one poll interval plus the operation in hand. Recorded on the receipt (received.stop_polling).
    polled = [float('-inf'), False]
    def save_requested():
        if requested[0]:
            return True
        if not stop_file:
            return False
        now = time.monotonic()
        if now - polled[0] >= STOP_POLL_SECONDS:
            polled[0], polled[1] = now, Path(stop_file).exists()
        return polled[1]
    attempt = dict(directory=None, received=None, timings=None, phases=None, stage='opening', progress=None)
    try:
        return _run(day, calculations, teacher_rows, previous, brain, day_external, day_external_sha256,
                    save_requested=save_requested, attempt=attempt)
    except SystemExit as error:
        if error.code == 75:
            # TeacherSaved: every completed operation and the continuation state are on disk; say so where the
            # inspection reads it (phase-progress.json last_event), then exit 75 as before.
            if attempt.get('progress') is not None:
                attempt['progress']('saved: ' + str(getattr(error, 'args', [''])[0] or 'stop requested'))
        elif error.code != 3:                     # 3 = the refusal receipt was already written by _run
            _failure_receipt(attempt, day, 'refused' if isinstance(error.code, str) else 'failed', error, error.code)
        raise
    except BaseException as error:               # every other failure: on the receipt, then propagate unchanged
        _failure_receipt(attempt, day, 'failed', error, 1)
        raise
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


def _run(day, calculations, teacher_rows, previous, brain, day_external, day_external_sha256, *, save_requested, attempt):
    from research.kalshi.frankie_boss import dipole_classroom_final_review as F
    from research.kalshi.frankie_boss import dipole_classroom_session as S, dipole_classroom_resolution as R
    from research.kalshi.frankie_boss import dipole_classroom_external as EXT, dipole_classroom_v2 as V2
    from research.kalshi.frankie_boss import sunday_execution as SE
    from research.kalshi.frankie_boss.frankie_principal_adapter import digest, json_form
    C, K, BR = _box('frankie_box_classroom'), _box('frankie_box_classroom_code'), _box('frankie_box_brain')
    KX = _box('frankie_box_classroom_external_code')
    LS = _box('frankie_box_lane_state')
    KR = _box('frankie_box_classroom_reader')

    calculations, teacher_rows = Path(calculations), Path(teacher_rows)
    work, out = calculations / 'work', calculations / 'out'
    receipt = json.loads((calculations / 'calculations-receipt.json').read_bytes())
    if receipt.get('day') != day:
        raise SystemExit('the calculations are for day %s, not %s' % (receipt.get('day'), day))
    source = json.loads((calculations / 'source-binding.json').read_bytes())
    shared_policy = source.get('shared_market_policy')
    d = work / 'classroom'
    attempt['directory'] = d
    # Efficiency (Greg, 2026-10-07; the core's retained fast path): the sealed journal (tens of GB on a big day) is
    # measured ONCE in this process by frankie_box_filehash.witness (streamed, per-process cache keyed on
    # path/device/inode/size/mtime/ctime, a file that changes while hashed is refused) on a daemon thread that
    # overlaps the cheap identity checks below, and handed to the core as input_witness so its open does not
    # re-hash the same bytes; the learner walk (SOCRATIC/VERIFY) and the full reader then hit the same cache.
    # The core still compares the witness to its pin and raises on a mismatch: pin, identity and chained head
    # hash unchanged. A daemon thread never delays a refusal that happens before the join.
    journal_pin = (source.get('container') or {}) if isinstance(shared_policy, dict) else {}
    measured_witness, witness_thread, witness_clock = {}, None, time.monotonic()
    if journal_pin.get('path'):
        import threading
        from frankie_box_filehash import witness as measured
        def measure():
            try:
                measured_witness['value'] = measured(journal_pin['path'])
            except Exception as error:       # surfaced after the join, never swallowed
                measured_witness['error'] = error
        witness_thread = threading.Thread(target=measure, name='classroom-journal-witness', daemon=True)
        witness_thread.start()
    if not (work / 'derivation-digest-full.md').is_file():
        raise SystemExit('the day\'s ROOT ran without the digest; the classroom day needs DIGEST=on (the brain entry takes it)')
    entry = Path(brain) / BR.entry_name(day, '00')
    state_path = d / 'phase-state.pkl'
    if entry.exists() and not state_path.exists():
        raise SystemExit('the brain already holds %s without this classroom continuation (duplicate data declines, R16)' % entry)

    # the day file: given (path + sha256) or beside the sealed ingest the teacher rows were walked from
    teacher_receipt = json.loads((teacher_rows / 'receipt.json').read_bytes())
    if teacher_receipt.get('day') != day:
        raise SystemExit('the teacher rows are for day %s, not %s' % (teacher_receipt.get('day'), day))
    attachment_sha = _sha256(teacher_rows / 'teacher-attachment.pkl')
    if attachment_sha != teacher_receipt['attachment_file']['sha256']:
        raise SystemExit('teacher-attachment.pkl differs from its teacher rows receipt; refused')
    try:
        day_file, day_sha, day_source = EXT.resolve_day_file(day_external, day_external_sha256,
                                                             teacher_receipt['ingestion_receipt']['path'])
    except EXT.DayExternalRefused as error:
        raise SystemExit('the day file of the historical data points: %s' % error)
    if _sha256(day_file) != day_sha:
        raise SystemExit('the day file %s differs from the sha256 %s (%s); refused' % (day_file, day_sha, day_source))
    # the shared market source, opened after the cheap checks with the journal witness measured above
    journal_witness, market = None, None
    if witness_thread is not None:
        witness_thread.join()
        if 'error' in measured_witness:
            raise measured_witness['error']
        journal_witness = dict(path=journal_pin['path'], **measured_witness['value'],
                               basis='frankie_box_filehash.witness: streamed sha256 in this process, cached per unchanged file',
                               seconds=round(time.monotonic() - witness_clock, 3),
                               overlapped_with=['teacher receipt and attachment hash', 'day file resolution and hash'],
                               equals_pin=({k: measured_witness['value'].get(k) for k in ('bytes', 'sha256')}
                                           == {k: journal_pin.get(k) for k in ('bytes', 'sha256')}))
    if shared_policy:
        market = _box('frankie_box_market_timeline').SharedMarketTimeline(
            calculations, day=day, workers=15,
            input_witness=({k: journal_witness[k] for k in ('bytes', 'sha256')} if journal_witness else None))
    shared_market_disposition = ('read: the ROOT carries the shared market policy; one full ordered read follows' if market is not None else
                                 'legacy no-policy source: source-binding.json carries no shared_market_policy; the classroom reads '
                                 'no shared picture and the external section reads the checked day file directly (listed, not refused)')
    teacher_shared_read = None
    if market is not None:
        shared_read = teacher_receipt.get('shared_market_read') or {}
        if (teacher_receipt.get('shared_market_identity') != market.identity
                or shared_read.get('identity') != market.identity
                or teacher_receipt.get('ingestion_receipt') != {
                    key: market.source['ingestion_receipt'][key] for key in ('path', 'sha256')}):
            raise ValueError('identity: shared classroom requires its exact shared teacher source, not another same-day reading')
        # Missing-coverage rule (Greg, 2026-10-07): what the teacher's read must have done is reach the
        # end of the same source. Absent layers, failed inputs or unavailable pictures in that read are
        # a thinner picture and do not refuse the classroom day; an unfinished read is not this day's reading.
        if not K.source_exhausted(shared_read, journal_count=market.source.get('journal_count'),
                                  record_count=market.source.get('record_count')):
            raise ValueError('the shared teacher reading did not reach the end of its source; an unfinished read is not '
                             'this day\'s shared reading (this is not a missing-layer or failed-input check)')
        teacher_shared_read = dict(
            exhausted=True,
            basis=('the teacher read\'s complete / source_exhausted flag' if (shared_read.get('complete') is True or
                   shared_read.get('source_exhausted') is True) else 'journal accounting equal to the sealed envelope and INPUT counts'),
            core_report_complete=shared_read.get('complete'),
            absent_layers=(shared_read.get('identity') or {}).get('absent_layers'),
            note='an exhaustion check only; absent layers or failed inputs in the teacher read thin the picture and never refuse')
    shared_external = None
    if market is not None:
        external = market.source.get('external') or {}
        if external.get('status') == 'attached':
            if external.get('sha256') != day_sha:
                raise ValueError('identity: the shared ROOT attached another external day file than the classroom\'s; irreconcilable')
            shared_external = dict(status='attached', sha256=day_sha)
        else:
            # The shared pictures carry no external publications (the ROOT ran without a day file). The
            # external section still reads its own checked day file; the day stays in, thinner.
            shared_external = dict(status=external.get('status'), disposition='external_layer_absent_in_shared_source',
                                   recorded={k: v for k, v in external.items() if k != 'rows'},
                                   listed='no external publication enters the shared market pictures of this day; the '
                                          'classroom external section reads the checked day file directly')
    day_receipt = Path(day_file).parent / 'day-external-receipt.json'

    d.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    p = pickle.loads((teacher_rows / 'teacher-attachment.pkl').read_bytes())
    history, prior_grade, carried = [], None, None
    external_history, prior_external_grade, external_carried = [], None, None
    if previous:
        prev = Path(previous)
        # Both local and imported predecessors must have the same complete, receipt-bound carry set. Grades
        # remain host inputs; prepare_cycle_v2 exposes only the governed prior correction summary (R10).
        LS.pack_classroom_carry(prev)
        history = json.loads((prev / 'history.json').read_bytes())
        prior_grade = json.loads((prev / 'post-grade.json').read_bytes())
        carried = dict(directory=str(prev), history_entries=len(history), history_sha256=_sha256(prev / 'history.json'),
                       grade_sha256=_sha256(prev / 'post-grade.json'))
        if (prev / 'external-history.json').is_file() and (prev / 'external-post-grade.json').is_file():
            external_history = json.loads((prev / 'external-history.json').read_bytes())
            prior_external_grade = json.loads((prev / 'external-post-grade.json').read_bytes())
            external_carried = dict(directory=str(prev), history_entries=len(external_history),
                                    history_sha256=_sha256(prev / 'external-history.json'),
                                    grade_sha256=_sha256(prev / 'external-post-grade.json'))
        else:
            external_carried = dict(directory=str(prev), listed='the previous classroom day has no external section '
                                    '(it ran before V2); the external section starts without a prior correction')
    from research.kalshi.frankie_boss.parallel_teacher import _load_raw_state, _save_raw_state, TeacherSaved
    rules, rules_witness = K.rules()
    identity = dict(day=day, calculations=str(calculations), brain=str(Path(brain)), runner_sha256=_sha256(__file__),
                    root_receipt=_sha256(calculations / 'calculations-receipt.json'),
                    teacher_receipt=_sha256(teacher_rows / 'receipt.json'), attachment=attachment_sha,
                    day_file=str(day_file), day_sha256=day_sha, previous=carried, previous_external=external_carried,
                    directive=_sha256(DIRECTIVE_PATH), rules=rules_witness,
                    producers={m.__name__: _sha256(m.__file__) for m in (F, S, R, EXT, V2, C, K, KX, LS, BR, KR)},
                    learner_reading_producers=KR.producer_hashes())
    if market is not None:
        identity['shared_market'] = market.identity
    # Inspection (Greg, 2026-10-07): every input this piece received, with path, bytes, sha256, the whole-day
    # binding (as_of / through_cursor / source hash) and the source binding, recorded in the receipt itself so
    # the reporter shows them from receipt.json alone. Recorded, not re-verified here; the checks above are the
    # verification and they refuse on a mismatch.
    cpus = sorted(os.sched_getaffinity(0))
    received = dict(
        # the lane (same day, same lane: the Run books it; recorded here, refused only by the learner walk)
        lane=dict(cpus=cpus, count=len(cpus), expected=16,
                  note=('held 16-CPU lane' if len(cpus) == 16 else
                        'affinity is not a 16-CPU lane: recorded, not refused here (the SOCRATIC/VERIFY learner walk refuses)')),
        journal_witness=journal_witness, shared_market_disposition=shared_market_disposition,
        teacher_shared_read=teacher_shared_read,
        stop_polling=dict(signal='SIGTERM immediate', stop_file=os.environ.get('FRANKIE_LANE_STOP_FILE'),
                          poll_seconds=STOP_POLL_SECONDS),
        schema='FRANKIE_CLASSROOM_RECEIVED_V1', day=day, calculations=str(calculations), teacher_rows=str(teacher_rows),
        brain=str(Path(brain)),
        root_receipt=dict(path=str(calculations / 'calculations-receipt.json'), sha256=identity['root_receipt']),
        source_binding=dict(path=str(calculations / 'source-binding.json'),
                            sha256=_sha256(calculations / 'source-binding.json'),
                            shared_market_policy=(shared_policy.get('schema') if isinstance(shared_policy, dict)
                                                  else shared_policy)),
        ingestion_receipt=teacher_receipt.get('ingestion_receipt'),
        teacher_receipt=dict(path=str(teacher_rows / 'receipt.json'), sha256=identity['teacher_receipt']),
        teacher_attachment=dict(path=str(teacher_rows / 'teacher-attachment.pkl'), sha256=attachment_sha,
                                bytes=(teacher_rows / 'teacher-attachment.pkl').stat().st_size),
        binding=dict(request_id=p.get('request_id'), source_hash=p.get('source_hash'), as_of=p.get('as_of'),
                     through_cursor=p.get('through_cursor'), cycle_index=0, cycle_count=1,
                     note='through_cursor = record_count - 1 names the sealed day and its whole-day causal cutoff; '
                          'it is an identity, not a claim that every input applied or every layer exists'),
        day_file=dict(path=str(day_file), sha256=day_sha, bytes=Path(day_file).stat().st_size, found=day_source),
        previous=carried, previous_external=external_carried,
        directive=dict(path=str(DIRECTIVE_PATH), sha256=identity['directive']), rules=rules_witness,
        producers=identity['producers'], learner_reading_producers=identity['learner_reading_producers'],
        shared_market_identity=market.identity if market is not None else None,
        shared_market_external=shared_external,
        teacher_shared_market_arithmetic=teacher_receipt.get('shared_market_arithmetic'))
    state = _load_raw_state(state_path) if state_path.exists() else dict(identity=identity, started=time.time(), phases={})
    phase_directory = d / 'saved-phases'
    phase_directory.mkdir(exist_ok=True)
    if state['identity'] != identity:
        raise ValueError('saved classroom source, previous class, directive or destination changed')
    # Where the classroom's time goes, per saved operation (Greg, 2026-10-07: show where a run spends its
    # time): seconds of each operation when it was computed (kept across resumes from the saved state), or
    # `restored` with no seconds when a phase file predates this field. Diagnostic only; never an input to
    # any answer.
    timings = state.setdefault('timings', {})
    attempt.update(received=received, timings=timings, phases=state['phases'], stage='phases')
    def save(event='saved_state'):
        _save_raw_state(state_path, state)
        # Inspection-readable progress beside the pickle (Greg, 2026-10-07: every piece reports what it
        # received/used/produced): which operations are saved and the last event (a save, a stop, a wait),
        # so a stop/wait is visible without unpickling.
        _dump(d / 'phase-progress.json', dict(schema='FRANKIE_CLASSROOM_PHASE_PROGRESS_V1', day=day,
                                              saved_phases=list(state['phases']), started=state['started'],
                                              saved_at=time.time(), stop_requested=bool(save_requested()),
                                              last_event=event, timings=timings))
    def progress(event):
        # the last event written beside the saved state (run() calls this on a TeacherSaved raised inside an operation)
        _dump(d / 'phase-progress.json', dict(schema='FRANKIE_CLASSROOM_PHASE_PROGRESS_V1', day=day,
                                              saved_phases=list(state['phases']), started=state['started'],
                                              saved_at=time.time(), stop_requested=True, last_event=event, timings=timings))
    attempt['progress'] = progress
    def stop():
        if save_requested():
            save('saved: stop requested; every completed operation and the continuation state retained')
            raise TeacherSaved('classroom saved every completed operation and its full continuation state')
    def phase(name, operation):
        stop()
        path = phase_directory / (hashlib.sha256(name.encode()).hexdigest() + '.pkl')
        if path.exists():
            retained = _load_raw_state(path)
            if retained['name'] != name or retained['identity'] != identity:
                raise ValueError('saved classroom operation belongs to another continuation')
            value = retained['value']
            timings.setdefault(name, dict(restored=True, seconds=None))
        else:
            if name in state['phases']:
                raise ValueError('saved classroom operation is missing; refuse recalculation')
            clock = time.monotonic()
            value = operation()
            timings[name] = dict(restored=False, seconds=round(time.monotonic() - clock, 3))
            _save_raw_state(path, dict(identity=identity, name=name, value=value))
        if name not in state['phases']:
            state['phases'][name] = path.name
            save()
        stop()
        return value
    save()
    stop()
    started = state['started']
    try:
        pkg2 = phase('package', lambda: V2.prepare_cycle_v2(p['attachment'], request_id=p['request_id'], cycle_index=0, cycle_count=1,
                                   source_hash=p['source_hash'], as_of=p['as_of'], through_cursor=p['through_cursor'],
                                   history=history, prior_grade=prior_grade, section_directory=teacher_rows,
                                   day_file=day_file, day_file_sha256=day_sha, trading_day=day,
                                   prior_external_grade=prior_external_grade, built_by='classroom V2'))
    except EXT.DayExternalRefused as error:
        raise SystemExit('the day file of the historical data points: %s' % error)
    pkg, ext = pkg2['v1'], pkg2['external']
    for part in ('source', 'teacher_key', 'pre_message', 'binding'):
        SE._save(d / f'package.{part}.c15.json', pkg[part])
    _dump(d / 'package.external.pre_message.json', ext['pre_message'])
    _dump(d / 'package.external.binding.json', ext['binding'])
    mode = pkg['binding']['mode']
    visible = F.final_model_visible_classroom(pkg)
    request = {'attachment': {'dipole_classroom': visible}}                     # the V1 request, unchanged
    ext_visible = EXT.model_visible_external(ext['binding'], ext['pre_message'])
    the_directive, directive_witness = directive()
    request_v2 = {'attachment': {'dipole_classroom': visible, 'dipole_external': ext_visible,
                                 'experiment_directive': the_directive}}
    # Jev's material: the SAME model-visible classroom Frankie answers (V2: the 19/171 and the external section), written
    # BEFORE any answer and OUTSIDE work/classroom/ (the blind wall of frankie_box_jev_relay.sh ACTION=material)
    jev_dir = calculations / 'jev-material'
    jev_dir.mkdir(exist_ok=True)
    jev_path = jev_dir / 'classroom-request.json'
    jev_raw = json.dumps(request_v2, indent=1, sort_keys=True, default=str).encode('utf-8')
    if jev_path.exists() and jev_path.read_bytes() != jev_raw:
        raise SystemExit('%s exists with other bytes; refused' % jev_path)
    if not jev_path.exists():
        _bytes(jev_path, jev_raw)
    names = [c['name'] for c in C.components(visible)]
    def learner_inputs():
        selected = LS.learner_knowledge(day, 'classroom', brain=brain, classroom_mode=mode)
        school, listed = LS.learner_school(day, brain=brain, versions=selected['versions'])
        return selected, school, listed
    knowledge_input, school, school_listed = phase('learner_inputs', learner_inputs)
    knowledge = knowledge_input['documents']
    all99 = None
    # Ordinary new knowledge waits for the next boundary, but a checked correction
    # cannot leave a known error active in a saved classroom. Keep every retained
    # input/answer intact and require an explicit successor instead of repicking.
    import frankie_box_experiment_review as REVIEW
    REVIEW.require_current(
        list(knowledge) + [dict(row, content=doc) for row, doc in school],
        REVIEW.corrections(LS.knowledge_roots(brain)))
    learner_reading, independent_external = None, None
    try:
        if mode in ('SOCRATIC', 'VERIFY'):
            snapshot, learner_reading = phase('learner_reading', lambda: KR.read_day(
                day, calculations, visible['binding'], day_file=day_file, day_sha256=day_sha,
                save_requested=save_requested))
            own_evidence = phase('independent_evidence', lambda: K.independent_evidence(visible, snapshot, learner_reading))
            # Keep request/Jev material unchanged. Only Frankie's answer consumers get his own reading.
            visible = dict(visible, learner_evidence=own_evidence)
            independent_external = phase('independent_external', lambda: KX.independent_day_file_evidence(
                ext_visible['pre_message'], snapshot))
        if mode == 'GUIDED':
            # The derived view is a completed learner calculation, not a host answer. Save it once so
            # resume can serve every remaining consumer without recalculating its 19 components/171 pairs.
            evidence = phase('guided_evidence', lambda: K._evidence(visible))
            K._EVIDENCE_CACHE[visible['pre_message']['teacher_message_hash']] = evidence
        shared_market = None
        market_reading = None
        if market is not None:
            market_reading = phase('shared_market_context', lambda: K.market_context(
                visible, market, save_requested=save_requested))
            if market_reading['identity'] != market.identity:
                raise ValueError('retained classroom market reading differs from its original source')
            shared_market = K.ClassroomMarketContext(calculations, day, market_reading)
        # These inputs and their checks are retained before any answer. A resume uses this exact selection,
        # never a later peer knowledge version or a newly completed school day partway through the classroom.
        knowledge_reproduction = phase('knowledge_reproduction', lambda: K.stage_knowledge_reproduction(visible, knowledge))
        reproduction = phase('school_reproduction', lambda: K.school_reproduction(visible, school))
        learner_context = dict(stage_knowledge=knowledge_reproduction, school=reproduction)
        # All-99 (Greg, 2026-10-07: the 99 layers combined for Frankie FIRST): every registry entry routed to the
        # picture element the component answers compute beside, or to its own consumer here, or named sealed /
        # disabled / output / retired, with this day's arrivals; on the receipt and in the inspection markdown.
        consumers = dict(
            directive=directive_witness, rules=rules_witness,
            policy=dict(shared_market_policy=(shared_policy.get('schema') if isinstance(shared_policy, dict) else shared_policy),
                        native_calculation_policy=source.get('native_calculation_policy')),
            knowledge=dict(documents=[{k: doc.get(k) for k in ('label', 'day', 'kind', 'sha256')} for doc in knowledge],
                           versions=knowledge_input['versions'], selection_listed=len(knowledge_input['listed']),
                           school_days_read=reproduction['school_days_read'], school_listed=len(school_listed),
                           stage_knowledge_checks=len(knowledge_reproduction['checks']),
                           school_checks=len(reproduction['checks'])),
            carry=dict(previous=carried, previous_external=external_carried),
            binding=received['binding'], mode=mode, dipole_components=len(names))
        all99 = phase('all99_coverage', lambda: K.all99_coverage(market_reading, consumers, repo_root=ROOT))
        outputs = {n: phase('component:' + n, lambda n=n: K.component_answer(
            visible, C.component(visible, n), [q['right'] for q in C.pairs_of(visible, n)],
            learner_context=learner_context, shared_market=shared_market)) for n in names}
        summary = phase('summary', lambda: K.summary_answer(visible, outputs, learner_context=learner_context,
                                                          shared_market=shared_market))
        ext_ledgers = phase('external_answers', lambda: KX.answers(
            ext_visible, dipole_visible=visible, learner_context=learner_context,
            independent_evidence=independent_external, knowledge=knowledge, school=school))
    except (K.ModeNotAnswerable, KX.ModeNotAnswerable) as error:
        pinned, listed = _pin_outputs(d, ['package.external.pre_message.json', 'package.external.binding.json']
                                      + [f'package.{part}.c15.json' for part in ('source', 'teacher_key', 'pre_message', 'binding')])
        received['all99'] = all99
        refusal = dict(schema=SCHEMA, day=day, status='refused', mode=mode, reason=str(error),
                       listed='SOCRATIC/VERIFY require the learner-owned sealed-journal/day-file reader; '
                              'missing evidence never falls back to the host key',
                       teacher_rows=str(teacher_rows), shared_market_external=shared_external,
                       shared_market=shared_market.summary() if shared_market is not None else None,
                       shared_market_use=shared_market.use() if shared_market is not None else None,
                       all99_coverage=all99,
                       external=dict(day_file=dict(path=str(day_file), sha256=day_sha, found=day_source)),
                       received=received, phase_timings=dict(timings), saved_phases=list(state['phases']),
                       outputs=dict(schema='FRANKIE_CLASSROOM_OUTPUTS_V1', directory=str(d), pinned=pinned, listed=listed,
                                    brain_entry=None, note='refused before any answer; the package files are the only products'),
                       jev_material=dict(
                           path=str(jev_path), sha256=hashlib.sha256(jev_raw).hexdigest(), bytes=len(jev_raw)))
        _dump(d / 'receipt.json', refusal)
        print(json.dumps(refusal), flush=True)
        return 3
    school_witness = dict(read=reproduction['school_days_read'],
                          listed=[dict(day=(x.get('row') or {}).get('day'), reason=x['reason']) for x in school_listed],
                          counts_per_earlier_day=reproduction['counts_per_earlier_day'],
                          index=str(Path(brain) / BR.SCHOOL_DIR / 'index.json'))
    built = phase('assembly', lambda: C.assemble(visible, outputs, summary))
    report = phase('answer_report', lambda: C.validate(visible, built['ledgers']))
    ext_report = phase('external_report', lambda: EXT.validate_external_ledgers(ext_ledgers, ext['pre_message']))
    _dump(d / 'code-answers.json', dict(schema=K.SCHEMA, rules=rules_witness, outputs=outputs, summary=summary,
                                        school=reproduction, stage_knowledge=knowledge_reproduction,
                                        learner_reading=learner_reading, model_calls=0,
                                        shared_market=shared_market.summary() if shared_market is not None else None,
                                        shared_market_external=shared_external, all99_coverage=all99))
    _dump(d / 'learner-knowledge.json', dict(day=day, stage='classroom', documents=knowledge,
                                           versions=knowledge_input['versions'], listed=knowledge_input['listed'],
                                           school_documents=school, school_listed=school_listed,
                                           school_sources=reproduction['school_days_read'],
                                           learner_reading=learner_reading,
                                           applied_to=['component_answer', 'summary_answer', 'external_answers']))
    _dump(d / 'ledgers.json', built['ledgers'])
    _text(d / 'classroom.md', C.render_markdown(built['ledgers'], built['dropped_findings']))
    _dump(d / 'external-code-answers.json', dict(schema=KX.SCHEMA, rules=rules_witness, ledgers=ext_ledgers, model_calls=0))
    _dump(d / 'external-novel-findings.json', dict(schema='FRANKIE_EXTERNAL_FINDINGS_V1', day=day,
          findings=ext_ledgers['external_novel_findings'],
          source=dict(path=str(d / 'external-code-answers.json'), sha256=_sha256(d / 'external-code-answers.json'))))

    # ---- the 19 components and 171 pairs: exactly the V1 arm's calls
    request_sha256 = digest(request)
    request_v2_sha256 = digest(request_v2)
    session_id = 'experiment-%s-classroom' % day
    response = dict(built['ledgers'], request_sha256=request_sha256, session_id=session_id,
                    model_identity_as_reported_by_session=MODEL_IDENTITY)
    teachback, initial_grade = phase('initial_grade', lambda: S.grade_initial_response(pkg, response))
    grade = phase('relationship_grade', lambda: F.apply_relationship_view_crosscheck(initial_grade, response))
    novel = phase('novel_findings', lambda: F.validate_novel_findings(response.get('dipole_novel_findings'), pkg['pre_message']))
    novelty = phase('novelty_investigation', lambda: F.investigate_novel_findings(pkg['teacher_key'], novel, mode=mode, learning_policy=pkg['binding'].get('learning_policy')))
    correction = phase('correction', lambda: F.bind_final_resolution_requirement(F.build_final_correction_request(
        original_request_sha256=request_sha256, response=response, grade=grade, key=pkg['teacher_key'], teachback=teachback,
        novelty_investigation=novelty)))
    parsed = phase('correction_answer', lambda: C.parse_correction(json.dumps(K.correction_answer(correction)), correction))
    reply = phase('correction_reply', lambda: C.correction_response(correction, parsed, session_id=session_id, model_identity=MODEL_IDENTITY))
    base = phase('correction_base', lambda: S.validate_correction_response(correction=correction, response=reply, initial_response=response, grade=grade))
    ack = phase('acknowledgement', lambda: R.validate_correction_resolutions(reply.get('dipole_acknowledgement'), grade, base))
    completion = phase('completion', lambda: S.finish(pkg, teachback=teachback, grade=grade, acknowledgement=ack))
    transcript = phase('transcript', lambda: F.render_final_transcript(pkg['pre_message'], teachback, novel, correction, ack,
                                           reply.get('dipole_scientific_exchange')))

    # ---- the external section: the host's exact grade and its correction turn
    ext_grade = phase('external_grade', lambda: EXT.grade_external(ext['teacher_key'], ext_ledgers))
    ext_correction = phase('external_correction', lambda: EXT.correction_request(original_request_sha256=request_v2_sha256, session_id=session_id,
                                            model_identity=MODEL_IDENTITY, grade=ext_grade))
    ext_parsed = phase('external_correction_answer', lambda: C.parse_correction(json.dumps(K.correction_answer(ext_correction)), ext_correction))
    ext_reply = phase('external_correction_reply', lambda: C.correction_response(ext_correction, ext_parsed, session_id=session_id, model_identity=MODEL_IDENTITY))
    ext_ack, ext_completion = phase('external_finish', lambda: EXT.finish_external(binding=ext['binding'], key=ext['teacher_key'], pre=ext['pre_message'],
                                                  ledgers=ext_ledgers, grade=ext_grade, correction=ext_correction,
                                                  reply=ext_reply, initial_session_id=session_id, model_identity=MODEL_IDENTITY))

    files = dict(teachback=teachback, **{'post-grade': grade}, **{'novel-findings': list(novel)},
                 **{'novelty-investigation': novelty}, **{'correction-request': correction},
                 **{'correction-response': reply}, acknowledgement=ack, completion=completion,
                 **{'external-post-grade': ext_grade}, **{'external-correction-request': ext_correction},
                 **{'external-correction-response': ext_reply}, **{'external-acknowledgement': ext_ack},
                 **{'external-completion': ext_completion})
    for name, body in files.items():
        _dump(d / f'{name}.json', json_form(body))
    _text(d / 'transcript.md', transcript)
    _text(d / 'classroom-external.md', EXT.render_markdown(ext_ledgers, ext_grade))
    _dump(d / 'history.json', json_form(list(history) + [completion]))
    _dump(d / 'external-history.json', json_form(list(external_history) + [ext_completion]))

    def publish_brain():
        from frankie_box_durable import sync_directory
        staging_brain = Path(brain) / '.classroom-publication' / day
        staging_entry = staging_brain / BR.entry_name(day, '00')
        additions = [
            ('classroom-external.md', d / 'classroom-external.md'),
            ('classroom-findings.json', d / 'novel-findings.json'),
            ('classroom-external-findings.json', d / 'external-novel-findings.json'),
            ('experiment-directive.json', DIRECTIVE_PATH)]
        rebuilt = None
        if entry.exists():
            manifest, _ = BR._checked_entry(entry)
            if manifest.get('day') != day or any((entry / name).read_bytes() != source.read_bytes()
                                                for name, source in additions):
                raise ValueError('published classroom brain entry differs from retained work')
            return dict(schema=BRAIN_PUBLICATION_SCHEMA, manifest=manifest, rebuilt=None,
                        basis='the brain already held this exact entry; reused, not rewritten')
        manifest_path = staging_entry / 'MANIFEST.json'
        if manifest_path.exists():
            try:
                manifest, _ = BR._checked_entry(staging_entry)
            except (ValueError, OSError) as error:
                # Retain an interrupted copy/manifest whole; rebuild only the publication from saved results.
                # The swallowed error is recorded (nothing silent, Greg 2026-10-07).
                rebuilt = dict(error_type=type(error).__name__, error=str(error),
                               disposition='an interrupted staging entry was found and retained whole; the publication '
                                           'was rebuilt from the saved results')
                manifest = BR.write_entry(work, out, staging_brain, '00', day=day)
        else:
            manifest = BR.write_entry(work, out, staging_brain, '00', day=day)
        manifest = _attach_to_brain_entry(staging_entry, d / 'classroom-external.md', day_file, day_sha, day_receipt, day)
        for name, source in additions[1:]:
            raw = source.read_bytes()
            _bytes(staging_entry / name, raw)
            manifest['entries'] = [e for e in manifest['entries'] if e['name'] != name]
            manifest['entries'].append(dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                source=str(source), include=True, kind=('Frankie classroom claims, source-bound; scientific checking follows'
                if name in ('classroom-findings.json', 'classroom-external-findings.json')
                else "the experiment's directive (Greg): what we are shooting for")))
        _dump(manifest_path, manifest)
        for path in staging_entry.iterdir():
            if path.is_file():
                with path.open('rb') as stream:
                    os.fsync(stream.fileno())
        sync_directory(staging_entry)
        entry.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staging_entry, entry)
        sync_directory(entry.parent)
        sync_directory(staging_brain)
        return dict(schema=BRAIN_PUBLICATION_SCHEMA, manifest=manifest, rebuilt=rebuilt, basis='published by this classroom')
    published = phase('brain_publication', publish_brain)
    if isinstance(published, dict) and published.get('schema') == BRAIN_PUBLICATION_SCHEMA:
        manifest = published['manifest']
        brain_publication = dict(basis=published.get('basis'), rebuilt_from_interrupted_staging=published.get('rebuilt'))
    else:
        # a phase file saved before this field existed holds the manifest alone
        manifest = published
        brain_publication = dict(basis='restored from a phase saved before the publication record existed',
                                 rebuilt_from_interrupted_staging='not recorded')
    if not (entry / 'MANIFEST.json').is_file() or json.loads((entry / 'MANIFEST.json').read_bytes()) != manifest:
        raise ValueError('published classroom brain manifest differs from its saved operation')
    # Inspection (Greg, 2026-10-07): what this piece produced, each file with its pin. receipt.json cannot pin
    # itself; phase-progress.json is progress, not a product. A name not on disk is listed, never pinned.
    produced_names = (['code-answers.json', 'learner-knowledge.json', 'ledgers.json', 'classroom.md',
                       'external-code-answers.json', 'external-novel-findings.json', 'transcript.md',
                       'classroom-external.md', 'history.json', 'external-history.json',
                       'package.external.pre_message.json', 'package.external.binding.json']
                      + [f'package.{part}.c15.json' for part in ('source', 'teacher_key', 'pre_message', 'binding')]
                      + [f'{name}.json' for name in files])
    outputs_pinned, outputs_listed = _pin_outputs(d, produced_names)
    # the all-99 output analogues get their pins now that the files exist (receipt.json cannot pin itself)
    for item in (all99 or {}).get('entries') or []:
        if item.get('outputs'):
            item['output_pins'] = {name: (outputs_pinned.get(name) or ('this receipt' if name == 'receipt.json' else 'not on disk'))
                                   for name in item['outputs']}
    received['all99'] = all99
    key = ext['teacher_key']
    result = dict(schema=SCHEMA, day=day, status='complete', mode=mode, components=report['components'],
                  observations=report['observations'], pairs=report['pairs'], novel_findings=len(novel),
                  dropped_findings=len(built['dropped_findings']), correction_ids=len(correction.get('correction_ids') or ()),
                  teacher_complete=completion.get('teacher_complete'), completion_hash=completion.get('completion_hash'),
                  carried_from_previous=carried, school_knowledge=school_witness, classroom_rules=rules_witness,
                  learner_reading=learner_reading,
                  shared_market=shared_market.summary() if shared_market is not None else None,
                  shared_market_external=shared_external,
                  # Inspection (Greg, 2026-10-07): what each component received from the shared picture and where
                  # it entered its answer, with partial/missing/completed-only dispositions; read by
                  # frankie_box_workflow_inspection's classroom projection.
                  shared_market_use=shared_market.use() if shared_market is not None else None,
                  # All-99 (Greg, 2026-10-07): every registry entry's route and this day's disposition (also under
                  # received.all99, which the reporter projects whole, and in code-answers.json)
                  all99_coverage=all99,
                  # The core teacher's own listing of which instants its pinned equation computed on and which it
                  # listed absent (revised core; None on a d6af990 teacher receipt). Carried, not reinterpreted.
                  teacher_shared_market_arithmetic=teacher_receipt.get('shared_market_arithmetic'),
                  novel_finding_ids=[f.get('finding_id') for f in novel],
                  external_novel_finding_ids=[f.get('finding_id') for f in ext_ledgers['external_novel_findings']],
                  stage_knowledge=dict(path=str(d / 'learner-knowledge.json'),
                                       sha256=_sha256(d / 'learner-knowledge.json'),
                                       versions=knowledge_input['versions'],
                                       selection_listed=knowledge_input['listed'],
                                       applied_to=['component_answer', 'summary_answer'],
                                       sources=knowledge_reproduction['sources'],
                                       checks=len(knowledge_reproduction['checks']), listed=knowledge_reproduction['listed']),
                  teacher_rows=str(teacher_rows),
                  experiment_directive=directive_witness, v1_unchanged=pkg2['v1_unchanged'],
                  external=dict(day_file=dict(path=str(day_file), sha256=day_sha, found=day_source,
                                              receipt=str(day_receipt) if day_receipt.is_file() else None),
                                section=ext['section_receipt'], external_key_hash=key['external_key_hash'],
                                points=[dict(point_id=q['point_id'], name=q['name'], series=len(q['series']),
                                             missing=len(q['missing'])) for q in key['points']],
                                deferred=key['deferred'], series=key['series_count'], series_absent=key['series_absent'],
                                missing_not_assigned=key['missing_not_assigned'], rows=key['rows'], cutoff_ns=key['cutoff_ns'],
                                ledgers=ext_report, correction_ids=len(ext_grade['correction_ids']),
                                mastered=ext_grade['mastered'], teacher_complete=ext_completion['teacher_complete'],
                                completion_hash=ext_completion['completion_hash'], carried_from_previous=external_carried),
                  jev_material=dict(path=str(jev_path), sha256=hashlib.sha256(jev_raw).hexdigest(), bytes=len(jev_raw),
                                    carries=['dipole_classroom', 'dipole_external', 'experiment_directive']),
                  stand_ins=dict(request_sha256=request_sha256, request_v2_sha256=request_v2_sha256, session_id=session_id,
                                 model_identity=MODEL_IDENTITY,
                                 why='the experiment has no principal request; the V1 request identity is the digest of the '
                                     'V1 model-visible request (unchanged), the external correction names the digest of the '
                                     'V2 request'),
                  brain_entry=str(entry), brain_manifest=manifest, seconds=round(time.time() - started, 1), model_calls=0,
                  # Inspection (Greg, 2026-10-07): received with pins, produced with pins, where the time went.
                  received=received,
                  outputs=dict(schema='FRANKIE_CLASSROOM_OUTPUTS_V1', directory=str(d), pinned=outputs_pinned,
                               listed=outputs_listed, brain_publication=brain_publication,
                               brain_entry=dict(path=str(entry), manifest_entries=[
                                   dict(name=e.get('name'), bytes=e.get('bytes'), sha256=e.get('sha256'), include=e.get('include'))
                                   for e in manifest.get('entries', [])])),
                  phase_timings=dict(timings))
    result = phase('receipt', lambda: result)
    _dump(d / 'receipt.json', result)
    stop()
    print(json.dumps(dict((k, v) for k, v in result.items() if k != 'brain_manifest'), sort_keys=True, default=str), flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--day', required=True)
    ap.add_argument('--calculations', required=True, help='the day\'s experiment ROOT (DIGEST=on)')
    ap.add_argument('--teacher-rows', required=True, help='experiment-teacher-rows/<day>/ (teacher-attachment.pkl)')
    ap.add_argument('--previous', help='the previous classroom day\'s work/classroom/ (its histories and grades carried in)')
    ap.add_argument('--brain', default='/opt/frankie-box/brain')
    ap.add_argument('--day-external', help='the day file (FRANKIE_DAY_EXTERNAL_V1); default: beside the sealed ingest')
    ap.add_argument('--day-external-sha256', help='its sha256 (given together with --day-external; a mismatch is refused)')
    a = ap.parse_args()
    if (a.day_external is None) != (a.day_external_sha256 is None):
        ap.error('--day-external and --day-external-sha256 are given together')
    return run(a.day, a.calculations, a.teacher_rows, a.previous, a.brain, a.day_external, a.day_external_sha256)


if __name__ == '__main__':
    sys.exit(main())
