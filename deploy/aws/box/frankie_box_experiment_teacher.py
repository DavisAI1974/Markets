"""The teacher-only step: the Dipole teacher's rows for ONE day, without a launch (research/kalshi/frankie_boss/
TEACHER_ONLY_CALL_MAP_20260929.md; SPEC-experiment-orchestrator.md "The teacher's Dipole rows: 1 day in 5"; Greg,
2026-09-29: the classroom arm runs on days 1 and 2 and needs these rows the same night).

The same calls the launch makes, in the pattern concurrent_teacher._run already uses (a teacher-only process): the day's
sealed journal read in place (its bytes and sha256 checked against its ingestion receipt), the parallel journal prefix,
JournalTeacherR3 with the teacher changes (all levels, the whole day, unknown trades carried), row_pass, finish with the
whole day as the context, then dipole_classroom.snapshot_teacher_attachment and sunday_execution._save. No model, no Pod,
no Granite. Greg authorized save/restore-only teacher hooks on 2026-10-06; calculation definitions remain unchanged.
The entity is the day's own instrument (the first INPUT record's publisher and instrument; the launch hard-coded the
2021-10 front month 111313), with the NG tick 0.001 = 1,000,000 raw. The walk cache is a per-day scratch directory, never
inside the sealed ingest.
Writes /opt/frankie-box/work/experiment-teacher-rows/<day>/: host-dipole-classroom-source.c15.json (the rows the search
and the classroom read), teacher-attachment.pkl (the attachment the classroom package is built from), receipt.json.
A day whose rows exist declines (duplicate data). Caveat kept from the call map: with the whole day as the context the
exact-row check in finish compares the rows with themselves.

Frankie's historical data points (Greg, 2026-09-29; research/kalshi/frankie_boss/dipole_classroom_external.py): the day
file (FRANKIE_DAY_EXTERNAL_V1) is read the same way every reader of the ingest reads it: given as --day-external +
--day-external-sha256 (checked BEFORE the walk; a mismatch is refused), or taken from beside the sealed ingest (its
day-external-receipt.json sha256 must match the bytes). After the rows, the BOSS teacher's external section is built once
into <out>/external-section/ (the rows' as-of alignment, the facts of every point, the pairs in the classroom's shapes)
through operations/frankie_day_external.AsOfReader at the rows' cutoff. No day file beside the ingest: listed in the
receipt, the rows stand (the classroom V2 builds the section when the file is there). A file beside the ingest that
differs from its receipt, or a section that fails, is listed in the receipt; the rows stand and the step exits 4.

Missing coverage (Greg, 2026-10-07): a missing operand blocks only the equation that needs it, never the day. A journal
without the full-book observation, or a day on which no original APPLIED operand reaches the pinned equation, publishes a
receipt with status equation_not_run (exit 5) and no rows file; the export and the search list the Dipole rows missing
and the day goes on. Nothing is invented. Every receipt carries the piece's workflow_report (inputs / use / outputs)
for the one-day inspection reporter (frankie_box_workflow_inspection.py).
"""
import argparse
import hashlib
import json
import os
import pickle
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = Path('/opt/frankie-box/work/experiment-teacher-rows')
ROWS_FILE = 'host-dipole-classroom-source.c15.json'
NG_TICK_RAW = 1_000_000            # NG tick 0.001 in the DBN fixed-point price (1e-9)
SECOND_SET_FILE = 'teacher-second-set.pkl'



def directive_witness():
    """The experiment's directive (Greg, 2026-09-29), named in this step's record: what the run is shooting for.
    research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json, whole text in the receipt."""
    path = Path(__file__).resolve().parents[3] / 'research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'
    data = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), directive=json.loads(data))

def _box_module(name):
    """A deploy/aws/box module by name (the box directory is this script's own; imported as a package otherwise)."""
    import importlib
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.append(here)
    try:
        return importlib.import_module(name)
    except ImportError:
        return importlib.import_module('deploy.aws.box.' + name)


def _journal_prefetch(receipt_path):
    """Start the sealed journal's sha256 (tens of GB on a big day) on a thread while the cheap checks run (Greg,
    2026-10-07: overlap the serial hash with other preparation). It fills the process's file-hash cache
    (frankie_box_filehash.witness: keyed on path/device/inode/size/mtime/ctime, a file that changes while hashed is
    refused); the walk then reads the same value at its original place, after joining. Any error here is ignored: the
    original place measures again and raises in the original order."""
    import threading
    def measure():
        began = time.monotonic()
        try:
            rc = json.loads(Path(receipt_path).read_bytes())
            journal = Path(receipt_path).parent / rc['journal_file']
            # one pass (Greg, 2026-10-09): the ingest's FRANKIE_FILE_CLAIM_V2 row beside the receipt, naming the
            # receipt's journal bytes and sha256 and still holding (stat, filesystem, last 64 KiB), is the witness:
            # it goes into the process cache (frankie_box_filehash.remember) and the journal is not read whole
            pin = dict(bytes=rc['journal_bytes'], sha256=rc['journal_sha256'])
            claim = _box_module('frankie_box_experiment_journal')._holding_claim(journal, pin, [journal.parent])
            if claim is not None and _box_module('frankie_box_filehash').remember(journal, pin):
                PREFETCH.update(outcome='by claim', claim=claim, seconds=round(time.monotonic() - began, 3))
                return
            _box_module('frankie_box_filehash').witness(journal)
            PREFETCH.update(outcome='measured', seconds=round(time.monotonic() - began, 3))
        except Exception as error:  # noqa: BLE001 - re-measured and raised at the original place
            PREFETCH.update(outcome='error', seconds=round(time.monotonic() - began, 3),
                            reason='%s: %s; the original place measured again' % (type(error).__name__, error))
    PREFETCH.clear()
    PREFETCH.update(outcome='started')
    thread = threading.Thread(target=measure, name='teacher-journal-sha256', daemon=True)
    thread.start()
    return thread


# What the overlapped journal measurement did (receipt and workflow_report only; never an identity or a gate).
PREFETCH = {}
# The defaults this process took when started from the command line (main): the worker count when --workers is not
# given and the thread caps for the spawn workers; listed on the receipt and in the workflow report (Day-1 visibility).
RUN_DEFAULTS = {}
THREAD_CAPS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def _work_probe(out, rc):
    """The walk's unit progress (FRANKIE_WORK_PROBE_V1 progress.json in the day's output directory, read by
    frankie_box_progress.sh DIRECTORY=<out>, and the stage heartbeat's phase file through report_phase): a function for
    parallel_teacher.PROGRESS. Report-only; None when the probe module is not importable."""
    try:
        probe = _box_module('frankie_box_progress').Probe(out, request_sha256=rc.get('journal_sha256'), phase='teacher')
    except Exception:  # noqa: BLE001 - the stage runs without its own probe file; the heartbeat still samples /proc
        probe = None
    totals = dict(teacher_raw_rows=int(rc['record_count']))
    units = dict(teacher_raw_rows='APPLIED rows (total = the day\'s INPUT records, an upper bound)',
                 teacher_attachment_chunks='attachment chunks')

    def report(stage, completed, total):
        total = total if total is not None else totals.get(stage)
        if probe is not None:
            probe.update(stage, int(completed), int(total) if total is not None and total >= completed else None,
                         force=True)
        try:
            import frankie_box_stage_progress as _SP
            _SP.report_phase('teacher: %s' % stage, units_done=int(completed), units_total=total, unit=units.get(stage))
        except Exception:  # noqa: BLE001
            pass
    return report


# Checkout moves accepted on retained teacher documents in this process (receipt field identity_rebinds).
IDENTITY_REBINDS = []


def _identity_matches(saved, built, out, what):
    """Identity is content, not location (ROOT's rule, frankie_box_experiment_root.content_rebinds): True when the retained
    identity equals the one this checkout builds, or differs ONLY by checkout-prefix moves of file witnesses with equal
    bytes and sha256 (recorded under <out>/checkout-rebinds/<ns>.json and in IDENTITY_REBINDS); False otherwise (the
    caller refuses as before). Nothing retained is rewritten."""
    if saved == built:
        return True
    if not (isinstance(saved, dict) and isinstance(built, dict)):
        return False
    try:
        moves = _box_module('frankie_box_experiment_root').content_rebinds(saved, built)
    except Exception as error:  # noqa: BLE001 - no rebind helper here: the plain comparison stands (refused)
        IDENTITY_REBINDS.append(dict(what=what, accepted=False, reason='content_rebinds unavailable (%s: %s)'
                                                                       % (type(error).__name__, error)))
        return False
    if not moves:
        return False
    where = Path(out) / 'checkout-rebinds'
    where.mkdir(parents=True, exist_ok=True)
    note = where / ('%d.json' % time.time_ns())
    note.write_text(json.dumps(dict(schema='FRANKIE_TEACHER_CHECKOUT_REBINDS_V1', what=what, moves=moves,
                                    rule='checkout-prefix moves with equal bytes and sha256 only; nothing retained is '
                                         'rewritten'), indent=1, sort_keys=True, default=str))
    IDENTITY_REBINDS.append(dict(what=what, accepted=True, moves=len(moves), file=str(note)))
    return True


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(64 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class _HashingWriter:
    """A file wrapper for pickle.dump: every byte written to the file is also fed to sha256, so the digest is that of
    exactly the bytes in the file (no second read pass). pickle sees only write(); the bytes are unchanged."""

    def __init__(self, handle):
        self.handle, self.sha256 = handle, hashlib.sha256()

    def write(self, data):
        self.sha256.update(data)
        return self.handle.write(data)


def _write_attachment(attachment_path, body):
    """pickle.dump(body) to <attachment>.pending hashed as written, then published; the sha256 of the bytes written."""
    temporary = attachment_path.with_name(attachment_path.name + '.pending')
    with temporary.open('wb') as f:
        writer = _HashingWriter(f)
        pickle.dump(body, writer, protocol=pickle.HIGHEST_PROTOCOL)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, attachment_path)
    return writer.sha256.hexdigest()


def _attachment_writer_main(attachment_path, body, cpu, sidecar):
    """The side process: on its lane CPU, write the attachment, leave the digest in the sidecar (whole, then renamed)."""
    import signal
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    pin = 'pinned'
    if cpu is not None:
        try:
            os.sched_setaffinity(0, {cpu})
        except OSError as error:                     # listed; the write goes on with the inherited mask
            pin = 'fallback: the OS refused (%s); the inherited mask was kept' % error
    digest = _write_attachment(attachment_path, body)
    pending = Path(str(sidecar) + '.%d.pending' % os.getpid())
    pending.write_text(json.dumps(dict(sha256=digest, pin=pin)), encoding='utf-8')
    os.replace(pending, sidecar)


def _start_attachment_writer(attachment_path, body, lane):
    """Fork the attachment writer when no attachment stands and this process runs one thread; else None (the caller
    writes in order). {'process', 'sidecar', 'record'}: the record goes on the receipt (cpu_pinning.attachment_writer)."""
    import multiprocessing
    import threading
    if attachment_path.exists():
        return None
    record = dict(outcome='not_started')
    if not sys.platform.startswith('linux'):
        record['reason'] = 'not Linux (no fork)'
        return dict(process=None, sidecar=None, record=record)
    if threading.active_count() > 1:
        record['reason'] = 'live threads: %s (a fork beside a live thread can inherit a held lock); written in order' % sorted(
            t.name for t in threading.enumerate() if t is not threading.current_thread())
        return dict(process=None, sidecar=None, record=record)
    cpu = None
    try:
        if lane and len(lane) > 1:
            cpu = LP.placement(1, list(lane))[1][0]
    except Exception as error:  # noqa: BLE001 - placement only
        record['placement'] = 'no CPU chosen (%s: %s); the child keeps the inherited mask' % (type(error).__name__, error)
    sidecar = attachment_path.with_name(attachment_path.name + '.sha256')
    for stale in [sidecar] + list(sidecar.parent.glob(sidecar.name + '.*.pending')):
        try:
            stale.unlink()
        except OSError:
            pass
    process = multiprocessing.get_context('fork').Process(
        target=_attachment_writer_main, args=(attachment_path, body, cpu, sidecar), name='teacher-attachment-writer')
    process.start()
    record.update(outcome='running', pid=process.pid, cpu=cpu, started_at=round(time.time(), 3))
    return dict(process=process, sidecar=sidecar, record=record, started=time.monotonic())


def _finish_attachment_writer(writer, attachment_path, body):
    """Join the side writer and take its digest; a writer that was not started, died or left no digest is redone here
    (the same bytes). The sha256 of the published attachment."""
    if writer is None or writer['process'] is None:
        digest = _write_attachment(attachment_path, body)
        if writer is not None:
            writer['record'].update(outcome='written_in_order')
        return digest
    process, sidecar, record = writer['process'], writer['sidecar'], writer['record']
    clock = time.monotonic()
    process.join()
    record.update(parent_waited_s=round(time.monotonic() - clock, 3), side_seconds=round(time.monotonic() - writer['started'], 3),
                  exitcode=process.exitcode)
    digest = None
    if process.exitcode == 0 and sidecar.is_file() and attachment_path.is_file():
        try:
            note = json.loads(sidecar.read_text(encoding='utf-8'))
            digest, record['pin'] = note['sha256'], note.get('pin')
        except (OSError, ValueError, KeyError) as error:
            record['sidecar_error'] = '%s: %s' % (type(error).__name__, error)
    try:
        sidecar.unlink()
    except OSError:
        pass
    if digest is not None:
        record['outcome'] = 'side_process'
        return digest
    record.update(outcome='redone_in_order', reason='side process exit %s, no digest' % process.exitcode)
    for stale in attachment_path.parent.glob(attachment_path.name + '.pending'):
        try:
            stale.unlink()
        except OSError:
            pass
    return _write_attachment(attachment_path, body)


CARRY_FILE = 'classroom-carry.pkl'
WALK_POSITION_SCHEMA = 'FRANKIE_TEACHER_WALK_POSITION_V1'     # a raw save's reader_position (teacher resume, 2026-10-09)


class _WalkCollector:
    """Value-neutral collector settings for the shared raw walk (2026-10-09, a2/20231018: a parent heap of 100+ GB of
    live decoded rows, pictures and teacher rows, where every full collection walks all of it; the native traversal's
    _CollectorPolicy, frankie_box_native_parallel, is the precedent). The state built before the walk is frozen
    (gc.freeze: never walked again), the youngest generation collects every YOUNG container allocations and a full
    collection waits for OLD collections of the middle one. Reference counting frees every acyclic object at once
    either way; only WHEN cyclic garbage is reclaimed changes, never a value, an order or an identity. Restored when the
    row pass ends (thresholds; unfreeze). enter() returns the record for the receipt."""
    YOUNG, OLD = 100_000, 100

    def __init__(self):
        self.saved = None

    def enter(self):
        import gc
        if self.saved is not None:
            return None
        self.saved = gc.get_threshold()
        gc.collect()
        gc.freeze()
        young, middle, old = self.saved
        gc.set_threshold(max(young, self.YOUNG), middle, max(old, self.OLD))
        return dict(schema='FRANKIE_TEACHER_WALK_COLLECTOR_V1', previous_thresholds=list(self.saved),
                    thresholds=list(gc.get_threshold()), frozen=gc.get_freeze_count(),
                    basis='value-neutral: only when cyclic garbage is reclaimed changes; restored after the row pass')

    def exit(self):
        import gc
        if self.saved is None:
            return
        gc.set_threshold(*self.saved)
        gc.unfreeze()
        self.saved = None


def walked_now(carry):
    """Whether this attempt's walk fed the carry at least one picture."""
    value = carry.get('value')
    return value is not None and getattr(value, 'pictures', 0) > 0


def _keep_cutoff_context(AM, market, cutoff_walk, out, *, day, rc, as_of, through, exhausted):
    """<out>/AM.TEACHER_CONTEXT_NAME from this walk's CutoffTracker (the exchange/Jev contract, 2026-10-09): scope,
    walk_context, retain_context; {path, bytes, sha256} or the reason nothing was written. None without a shared walk."""
    if market is None:
        return None
    tracker = cutoff_walk.get('tracker')
    if AM is None or tracker is None or cutoff_walk.get('pictures', 0) == 0 or not exhausted:
        return dict(status='not_written', reason=cutoff_walk.get('error') or (
            'this attempt did not walk the source (a completed saved walk was reused): no tracker'
            if not cutoff_walk.get('pictures') else 'the shared read did not reach the end of the source'))
    try:
        scope = AM.cutoff_scope(market.identity, day=day, source_hash=rc['source_prefix_hash'], as_of=as_of,
                                through_cursor=through)
        context = AM.walk_context(market, scope, tracker)
        kept = AM.retain_context(out / AM.TEACHER_CONTEXT_NAME, context)
    except Exception as error:  # noqa: BLE001 - ValueError/OSError by contract; nothing else may stop the teacher
        return dict(status='not_written', reason='%s: %s' % (type(error).__name__, error))
    return dict(kept, status='written', tracker_continued=cutoff_walk.get('continued', False))


def _body_identity(body):
    """The attachment body's identity fields (everything but the attachment object), as JSON-safe values."""
    return json.loads(json.dumps({k: v for k, v in body.items() if k != 'attachment'}, sort_keys=True, default=str))


def _write_teacher_claims(out, items):
    """out/file-claims.jsonl: one FRANKIE_FILE_CLAIM_V2 row per (path, sha256, body identity) whose sha256 this step
    took on the write stream or one read; a hint for later stages, never the step's outcome. Returns the note."""
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import file_claim, write_file_claims
        rows = []
        for path, sha256, identity in items:
            if not sha256 or not Path(path).is_file():
                continue
            row = file_claim(path, Path(path).stat().st_size, sha256,
                             'teacher-only step (frankie_box_experiment_teacher) at %s'
                             % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
            if identity is not None:
                row['body_identity'] = identity
            rows.append(row)
        return write_file_claims(out, rows)
    except Exception as error:  # noqa: BLE001 - a claim is a hint
        return dict(status='not_written', reason='%s: %s' % (type(error).__name__, error))


def _attachment_claim(out, attachment_path, body):
    """The retained attachment's claim row when it names this body's identity and still holds (claim_still_holds),
    else None (the retained attachment is unpickled, compared and hashed as before). Never raises."""
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import claim_still_holds, FILE_CLAIMS_NAME
        want = str(Path(attachment_path).resolve())
        for line in (Path(out) / FILE_CLAIMS_NAME).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if (isinstance(row, dict) and row.get('path') == want and row.get('body_identity') == _body_identity(body)
                    and claim_still_holds(row, attachment_path) is not None):
                return row
    except Exception:  # noqa: BLE001 - without a holding claim the attachment is read as before
        return None
    return None


def _publish(out, result):
    """The step's receipt, complete or not at all; then the directory entry is durable."""
    temporary = out / 'receipt.json.pending'
    with temporary.open('w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, out / 'receipt.json')
    directory_fd = os.open(out, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def workflow_report(result, *, receipt_path, rc, external, market, equation, workers, exit_code):
    """The piece's inputs / use / outputs record for the one-day review (Greg, 2026-10-07; schema shared with the
    adviser pieces so frankie_box_workflow_inspection projects it). Inputs: the sealed journal and its receipt, the
    day file, the shared ROOT identity. Use: which operands entered the pinned R3 equation (the original APPLIED
    payloads of the contiguous adapter-cursor prefix), every instant listed without that operand, the external section
    state, the whole-day context. Outputs: the rows file, the attachment, this receipt, the exit code. A row in the
    rows file is the teacher's measured output; it is not proof that the classroom or the search consumed it."""
    identity = result.get('shared_market_identity')
    read = result.get('shared_market_read') or {}
    return dict(schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='teacher',
                inputs=dict(day=result['day'],
                            ingestion_receipt=dict(path=str(receipt_path), sha256=result['ingestion_receipt']['sha256']),
                            journal=dict(path=str(Path(receipt_path).parent / rc['journal_file']), bytes=rc['journal_bytes'],
                                         sha256=rc['journal_sha256'], journal_count=rc['journal_count'],
                                         record_count=rc['record_count'], observation_mode=rc.get('observation_mode'),
                                         source_binding='BOSS_BLOCK_INGESTION_RECEIPT_V1 of this trading day, bytes and '
                                                        'sha256 checked before the walk'),
                            day_file={k: external.get(k) for k in ('path', 'sha256', 'found', 'status', 'reason') if k in external},
                            entity=result.get('entity'),
                            calculations=(identity or {}).get('calculations'),
                            shared_market_picture=(None if identity is None else dict(
                                identity=identity, read_complete=read.get('complete'),
                                coverage=read.get('coverage'), basis='SharedMarketTimeline.iter_applied over the same '
                                                                    'sealed journal; complete means source exhaustion only')),
                            shared_market_dispositions=(None if identity is None else dict(
                                arithmetic=read.get('arithmetic'), journal=read.get('journal'),
                                integrity_failure=read.get('integrity_failure'), stopped=read.get('stopped'))),
                            experiment_directive=(result.get('experiment_directive') or {}).get('sha256'),
                            workers=workers),
                use=dict(equation='the pinned JournalTeacherR3 row pass (c15_teacher_r3 + teacher_changes), unchanged: '
                                  'original APPLIED payloads with every adapter cursor from zero, the whole day as context',
                         operands_entered=(dict(rows=equation['rows'], through_applied_cursor=equation['through_applied_cursor'])
                                           if equation is not None else dict(rows=result.get('rows'), basis='parallel journal prefix')),
                         instants_without_operand=(dict(count=len(equation['absent']), ended_at=equation['ended_at'],
                                                        listed_in='shared_market_arithmetic.absent')
                                                   if equation is not None else None),
                         thinner_picture=(dict(absent_layers=(read.get('coverage') or {}).get('absent_layers'),
                                               rule=read.get('completeness')) if read else None),
                         external_section=external.get('status'),
                         through_cursor=result.get('through_cursor'), as_of=result.get('as_of'),
                         skipped=result.get('equation_not_run'),
                         walk_seconds=result.get('walk_seconds'), phase_timings=result.get('phase_timings'),
                         sealed_journal_verification=dict(
                             teacher='bytes and sha256 measured here against the ingestion receipt (phase verify_sealed_journal)',
                             shared_reader=read.get('input_verification') if read else None,
                             rule='one full hash per process; the compact reader still verifies the chained head hash on read'),
                         all99_coverage=_all99_use(result.get('all99_coverage')),
                         stacks=stack_events(result),
                         model_calls=0),
                outputs=dict(status=result.get('status', 'rows_published'), exit_code=exit_code,
                             all99_coverage='receipt.json all99_coverage (FRANKIE_ALL99_COVERAGE_V1, piece teacher)',
                             rows_file=result.get('rows_file'), attachment_file=result.get('attachment_file'),
                             rows=result.get('rows'), entity_rows=result.get('entity_rows'),
                             external_section=external, receipt='receipt.json in the same directory',
                             brain='filed by the orchestrator beside this receipt (teacher-knowledge.json -> <brain>/<day>-teacher) '
                                   'before the classroom; recorded there, not here',
                             waits=[]),
                rule='recorded inputs, use and outputs of this piece for the one-day review; a measured row is not proof '
                     'of downstream consumption; missing evidence means unknown, never zero')


def stack_events(result):
    """Day-1 visibility of the speed stacks (Greg, 2026-10-07: every skip, wait, refusal, fallback, cap, retry and default
    taken lands on the receipt AND in the inspection markdown): the CPU placement outcome, every pool's workers,
    rebuilds after a dead worker, bounded stops, batches not registered (computed the original way), the periodic and
    resumed saves, the journal prefetch, the defaults taken. A projection of fields already on the receipt; [] events
    means nothing of the kind happened, a missing field means the step did not reach that part (unknown, never zero)."""
    pin = result.get('cpu_pinning') or {}
    events = []

    def add(kind, where, reason, **detail):
        events.append(dict(kind=kind, where=where, reason=reason, **detail))
    if pin and pin.get('outcome') not in ('pinned', None):
        add('placement', 'serial raw loop', '%s: %s' % (pin.get('outcome'), pin.get('reason') or pin.get('read_back')))
    for name in ('raw_pool', 'finish_pool'):
        record = pin.get(name) or {}
        for rebuild in record.get('rebuilds') or []:
            add('retry', name, 'dead worker: pool rebuilt with %s worker(s); %s redone' % (
                rebuild.get('workers'), rebuild.get('batches_again', rebuild.get('chunks_again'))), error=rebuild.get('error'))
        for stop in record.get('stops') or []:
            add('bounded_stop', name, stop.get('reason') or 'shutdown error', **{k: v for k, v in stop.items() if k != 'reason'})
    precompute = pin.get('evidence_precompute') or {}
    if precompute.get('outcome') == 'not_used':
        add('fallback', 'evidence precompute', precompute.get('reason'))
    record = precompute.get('record') or {}
    for why in record.get('not_registered_batches') or []:
        add('fallback', 'evidence precompute', 'batch not registered (rows encoded the original way): %s' % why)
    for rebuild in record.get('rebuilds') or []:
        add('retry', 'evidence precompute', 'dead worker: pool rebuilt with %s worker(s); %s batch(es) again' % (
            rebuild.get('workers'), rebuild.get('batches_again')), error=rebuild.get('error'))
    for stop in record.get('stops') or []:
        add('bounded_stop', 'evidence precompute', stop.get('reason') or 'shutdown error')
    if precompute.get('resume_skipped_rows'):
        add('skip', 'evidence precompute', 'resumed raw pass: %d saved row(s) read again but not encoded'
            % precompute['resume_skipped_rows'])
    saves = result.get('raw_saves') or {}
    if saves.get('resumed_from'):
        add('resume', 'raw pass', 'resumed from a saved raw pass at %s row(s) (complete %s)' % (
            saves['resumed_from'].get('processed'), saves['resumed_from'].get('complete')))
    for save in saves.get('saves') or []:
        add('save', 'raw pass', 'periodic exact save at cursor %s (%s s)' % (save.get('cursor'), save.get('seconds')))
    if saves.get('every_seconds') is None and saves:
        add('default', 'raw pass', 'periodic save off (%s)' % saves.get('basis'))
    if saves.get('progress_errors'):
        add('swallowed', 'unit probe', '%d probe write(s) failed (report-only)' % saves['progress_errors'])
    prefetch = result.get('journal_prefetch') or {}
    if prefetch.get('outcome') not in ('measured', None):
        add('fallback', 'journal prefetch', prefetch.get('reason') or prefetch.get('outcome'))
    for rebind in result.get('identity_rebinds') or []:
        add('rebind' if rebind.get('accepted') else 'refusal', rebind.get('what'),
            ('checkout moves accepted (%s), recorded in %s' % (rebind.get('moves'), rebind.get('file'))
             if rebind.get('accepted') else rebind.get('reason')))
    for name, value in sorted((result.get('run_defaults') or {}).items()):
        add('default', 'run setting', '%s = %s' % (name, value))
    return dict(schema='FRANKIE_TEACHER_STACK_EVENTS_V1', events=events,
                placement=dict(outcome=pin.get('outcome'), lane=pin.get('lane'), consumer_mask=pin.get('consumer_mask'),
                               raw_workers=(pin.get('raw_pool') or {}).get('workers'),
                               precompute_workers=record.get('workers'),
                               finish_workers=(pin.get('finish_pool') or {}).get('workers')) if pin else None,
                rule='projection of the receipt; nothing here is an identity, a gate or a value')


# The 99 through the teacher (Greg, 2026-10-07: the 99 layers combined for Frankie FIRST). The teacher's own computed
# forms of registry entries (the columns the search's plane table names as these entries' partial teacher form) and the
# raw entries whose original APPLIED payload is the pinned equation's operand.
# TEACHER_FORMS: the one shared table frankie_box_all99_coverage.TEACHER_FORMS (entry -> (Dipole columns, text)), the
# same the search's plane rows name, so the teacher's list and the search cannot drift (main_recovery, 2026-10-07).
OPERAND_ENTRIES = ('canonical_sep_nov_2021_dbn_mbo_objects', 'october_first_source_window', 'native_acmrtfn_messages',
                   'snapshot_bootstrap_reset_messages', 'raw_source_identity_provenance_clocks_integrity',
                   'clock_event_time', 'clock_receive_time')
EXPOSED = 'teacher.market_picture: both raw teachers see the picture at every computed row; the pinned equations read original APPLIED fields only'


EXTERNAL_POINTS_SCHEMA = 'FRANKIE_TEACHER_EXTERNAL_POINTS_V1'


def external_points_summary(key, status=None, reason=None):
    """Per day-file point (the day file's own point ids, dipole_classroom_external.POINTS / DEFERRED), from the external
    section key this step built or reused (never recomputed): the series of the point present in the section, the Dipole
    rows at which a PRESENT value was used (state_counts PRESENT per series, aligned at or before each row's own time),
    the rows its tables had known by the cutoff and not yet known, and every missing entry with its reason. Without a key:
    status and reason only (never zeros). Read by the day reports' 99-layer join (its per-point table)."""
    if not isinstance(key, dict):
        return dict(schema=EXTERNAL_POINTS_SCHEMA, status=status or 'not_built',
                    reason=reason or 'no external section key was built or reused by this step', points=[])
    by_name = {s.get('name'): s for s in key.get('series') or [] if isinstance(s, dict)}
    points = []
    for p in key.get('points') or []:
        if not isinstance(p, dict):
            continue
        series = []
        for name in p.get('series') or []:
            counts = ((by_name.get(name) or {}).get('alignment') or {}).get('state_counts') or {}
            series.append(dict(series=name, present_rows=int(counts.get('PRESENT') or 0), state_counts=counts))
        used = sum(x['present_rows'] for x in series)
        tables = [dict(table=t.get('name'), rows_known=t.get('rows_known'), not_yet_known=t.get('not_yet_known'),
                       absent=t.get('absent'), reason=t.get('reason')) for t in p.get('tables') or [] if isinstance(t, dict)]
        missing = [dict(point=m.get('point'), reason=m.get('reason'), detail={k: v for k, v in m.items()
                                                                              if k not in ('point', 'reason')})
                   for m in p.get('missing') or [] if isinstance(m, dict)]
        if used:
            use, why = 'used', ('%d Dipole row(s) took a PRESENT value of its series (aligned at or before each row\'s own '
                                'time) in the external section' % used)
        elif series:
            use, why = 'missing', 'its series are in the section, but no value was published at or before any Dipole row'
        else:
            use, why = 'missing', ('none of its series is in the day file read at the cutoff%s' % (
                ': ' + '; '.join(str(m['reason']) for m in missing) if missing else ''))
        points.append(dict(point_id=p.get('point_id'), name=p.get('name'), use=use, reason=why, rows_used=used,
                           series=series, tables=tables, missing=missing))
    counts = {}
    for p in points:
        counts[p['use']] = counts.get(p['use'], 0) + 1
    return dict(schema=EXTERNAL_POINTS_SCHEMA, status=status or 'built', reason=reason,
                external_key_hash=key.get('external_key_hash'), cutoff_ns=key.get('cutoff_ns'), rows=key.get('rows'),
                points=points, counts=counts,
                rule='per point as the external section key records it: used = a PRESENT value of its series reached a '
                     'Dipole row; missing = none did (or the section does not read the point\'s table), with the reason; '
                     'never a zero filled in')


def all99_field(result, market_report, *, day):
    """The teacher's FRANKIE_ALL99_COVERAGE_V1: the shared reader's per-day field (what each carrier yielded) with this
    piece's own rows: the APPLIED operands that entered the pinned R3 equation, the teacher's computed forms, the
    picture entries exposed but not read by the equation, the cutoff it stamps and the pins it writes. Without a shared
    market policy the base is absent and every picture entry says so. Nothing here is a new scientific mapping."""
    import frankie_box_all99_coverage as ALL99
    TEACHER_FORMS = {name: text for name, (_, text) in ALL99.TEACHER_FORMS.items()}
    base = (market_report or {}).get('all99_coverage')
    base_rows = {e['entry']: e for e in (base or {}).get('entries') or []}
    rows_computed = result.get('rows') or 0
    not_run = result.get('equation_not_run')
    equation = result.get('shared_market_arithmetic') or {}
    updates = {}
    through = equation.get('through_applied_cursor')
    absent_count = len(equation.get('absent') or []) if equation else None
    operand_reason = ('original APPLIED payloads of the contiguous adapter-cursor prefix entered the pinned equation (%d rows%s)'
                      % (rows_computed, '' if through is None else ' through adapter cursor %s' % through)
                      + ('; %d instant(s) listed without that operand in shared_market_arithmetic' % absent_count
                         if absent_count is not None else '; no shared reader on this ROOT (the parallel journal prefix)'))
    for layer in ALL99.entries():
        name, role = layer['entry'], layer['role']
        prior = base_rows.get(name)
        if name in OPERAND_ENTRIES:
            if rows_computed:
                row = dict(disposition='operand', consumer='JournalTeacherR3 row pass (pinned R3 equation, teacher_changes)',
                           reason=operand_reason)
            else:
                row = dict(disposition='thin', consumer=None,
                           reason='the sealed journal was read; the equation had no operand on this day: %s' % (
                               (not_run or {}).get('reason') or 'no rows'))
        elif name in TEACHER_FORMS:
            if rows_computed:
                row = dict(disposition='computed_here', canonical='thin',
                           consumer='the teacher rows file (%s)' % ROWS_FILE,
                           reason='the teacher form: %s; the registry layer itself through the shared reader: %s' % (
                               TEACHER_FORMS[name], (prior or {}).get('disposition') or 'no shared reader'))
            else:
                row = dict(disposition='absent', reason='the equation did not run on this day: %s' % (
                    (not_run or {}).get('reason') or 'no rows'))
        elif name == 'clock_lock_time':
            row = dict(disposition='stamped', consumer='the teacher attachment snapshot (as_of / through_cursor)',
                       reason='as_of %s, through_cursor %s (the whole sealed day)' % (result.get('as_of'), result.get('through_cursor')))
        elif name == 'output_source_state_manifest_code_model_run_hashes' and result.get('rows_file'):
            row = dict(disposition='output_analogue', consumer='receipt.json',
                       reason='the receipt pins the ingestion receipt, the rows file and the attachment (sha256)')
        elif prior is None:
            row = dict(disposition='absent' if role in ('raw', 'calculation', 'clock') else 'not_read_by_this_piece',
                       reason=('no shared market policy on this ROOT: the teacher read the sealed journal directly and no '
                               'picture carried this entry' if role in ('raw', 'calculation', 'clock') else
                               'not an input of the teacher-only step (the sealed journal, its ingestion receipt and the day file)'))
        elif prior.get('piece_disposition') == 'yielded_no_rows':
            row = dict(disposition='thin', consumer=EXPOSED,
                       reason='%s; nothing of it was in the picture on this day' % prior['reason'])
        elif (prior.get('piece_disposition') or prior['disposition']) in ('yielded', 'carrier_present'):
            row = dict(disposition='exposed_not_used', consumer=EXPOSED,
                       reason='%s; exposed in the picture, not an operand of the pinned equation' % prior['reason'])
        elif prior['disposition'] == 'thin':
            row = dict(disposition='thin', consumer=EXPOSED, reason=prior['reason'])
        elif (prior.get('piece_disposition') or prior['disposition']) == 'not_a_core_layer':
            row = dict(disposition='not_read_by_this_piece',
                       reason=('the experiment directive is witnessed in the receipt (experiment_directive), not an input to '
                               'the equation' if name == 'controlling_rt_mission' else
                               'not an input of the teacher-only step: %s' % prior['reason']))
        else:
            row = dict(disposition=prior.get('piece_disposition') or prior['disposition'], canonical=prior['disposition'],
                       reason=prior['reason'], consumer=prior.get('consumer'))
        updates[name] = row
    return ALL99.derive_field(base, 'teacher', updates, day=day, stage='teacher',
                              basis='the teacher receipt: rows %s, equation %s; the shared reader field as its base' % (
                                  rows_computed, 'not run' if not_run else 'ran'))


def _all99_use(field):
    """The inspection projection of the teacher's all-99 field: the shared counts, the integrity findings, and every
    native-only entry (Greg, 2026-10-07: the 18 reach both teachers) with its word, reason and consumer."""
    if not isinstance(field, dict):
        return None
    import frankie_box_all99_coverage as ALL99
    native = {e['entry']: dict(disposition=e['disposition'], piece_disposition=e.get('piece_disposition'),
                               reason=e['reason'], consumer=e.get('consumer'))
              for e in field.get('entries') or [] if e.get('entry') in ALL99.NATIVE_SERIES}
    return dict(counts=field.get('counts'), by_role=field.get('by_role'), integrity=field.get('integrity'),
                listed=field.get('listed'), native_entries=native,
                rule='the native entries are in teacher.market_picture at their GROUP_CLOSE emission (exposed to both raw '
                     'teachers within the teacher\'s role and walls); the pinned equations read original APPLIED fields only')


PREFIX_PROGRESS_ROWS = 1024        # the prefix merge offers its row count to the stage heartbeat every this many rows


def _second_set_prefix(open_market, needed, SS, book_needed=0, changes=True, label_needed=0, on_row=None):
    """For the rows the walk of THIS process did not read (a resume from a save written before the second set or the
    book read): read the same pictures again from a fresh shared reader of the same ROOT, in order, with the walk's
    equation filter (present APPLIED payloads, adapter cursors contiguous from zero). The first `needed` rows get their
    join records (nothing computed); the first `book_needed` rows get the book read beside the pinned functions,
    exactly as the walk's workers read it: the R3 stream's own row builder (T._history_row), its group boundaries
    (the receipt), the previous group's closing book, teacher_book_read.book_group on those very rows, and each window
    the pinned R3 calls on a group (its own anchor function, T._anchor, on the same groups; no pinned column is
    computed); the first `label_needed` rows get the state labels their picture carries (joins recorded before the
    labels were). Returns (records, book) with book = {groups, windows, cursor_group, labels}. on_row(index, records,
    book): called after each row is merged, in cursor order (the sealed blocks, 2026-10-09: a block seals the moment
    its rows are merged)."""
    from collections import deque
    from research.kalshi.frankie_boss import c15_teacher_r3 as T, teacher_book_read as TBR, parallel_teacher as PT
    # the frames rows by reference (frankie_box_market_timeline.RowRef): the join names them by (source, source_ordinal)
    # and nothing here reads a frames value; every line is still decoded and checked on the decode workers
    reader = open_market(frame_values='reference')
    pictures = reader.iter_applied()
    records, expected = [], 0
    upto = max(needed, book_needed, label_needed)
    book = dict(groups={}, windows={}, cursor_group={}, labels={})
    open_rows, last_closing, ordinals, history = {}, {}, {}, {}
    try:
        for item in pictures:
            if expected >= upto:
                break
            if item['arithmetic']['status'] != 'present':
                continue
            e = item['evidence']
            if e.get('cursor') != expected:
                break                       # the equation prefix ends here (the rows hold more: refused by the caller)
            if expected < needed:
                records.append(SS.join_record(e, item['picture']))
            elif expected < label_needed:
                book['labels'][expected] = SS.state_labels(item['picture'])
            if expected < book_needed:
                m = e['normalized']
                key = (m['publisher_id'], m['instrument_id'])
                made = T._history_row(e)
                open_rows.setdefault(key, []).append(made)
                if e['receipt'] is not None:
                    group = open_rows.pop(key)
                    ordinal = ordinals.get(key, 0)
                    ordinals[key] = ordinal + 1
                    previous, last_closing[key] = last_closing.get(key), group[-1]
                    book['cursor_group'][e['cursor']] = (key, ordinal)
                    book['groups'][(key, ordinal)] = TBR.book_group(previous, group)
                    held = history.setdefault(key, deque(maxlen=65 if changes else 1025))
                    held.append(group)
                    groups = list(held)
                    side, missing = T._anchor(groups)
                    if changes:
                        if missing is None:
                            book['windows'][e['cursor']] = dict(short=(key, ordinal, len(groups[-64:]) if len(groups) > 64
                                                                       else len(groups) - 1, side))
                    else:
                        obs = e['observation']
                        if missing is None and (any(obs['integrity'].values()) or (
                                obs['levels']['A'] and obs['levels']['B']
                                and obs['levels']['B'][0]['price_raw'] >= obs['levels']['A'][0]['price_raw'])):
                            missing = 'LEVEL_INTEGRITY'
                        if missing is None:
                            slots = {slot: (key, ordinal, horizon, side)
                                     for slot, horizon in (('short', 64), ('long', 1024)) if len(groups) > horizon}
                            if slots:
                                book['windows'][e['cursor']] = slots
            if on_row is not None:
                on_row(expected, records, book)
            expected += 1
            if expected % PREFIX_PROGRESS_ROWS == 0:
                # the stage heartbeat (PT.PROGRESS: progress.json and the phase file): rows merged of the prefix
                PT._progress('teacher_second_set_prefix', expected, upto)
        PT._progress('teacher_second_set_prefix', expected, upto, force=True)
    finally:
        close = getattr(pictures, 'close', None)
        if close is not None:
            close()
    return records, book


def _second_set(out, open_market, market, second, rows, SS, feed=None):  # noqa: C901
    """The teacher's second set for every row, written beside the rows (teacher-second-set.pkl, hash-bound) and
    summarized for the receipt. The rows the walk read carry their join from the walk; rows read by an earlier process
    whose save holds no join are joined here from a fresh reader of the same ROOT (merged at publication). A row left
    without its join refuses the publication (the reason listed); a join whose picture identity or clocks differ from
    the row's own is listed with both values, never aligned."""
    import frankie_box_all99_coverage as ALL99
    from research.kalshi.frankie_boss import parallel_teacher as PT, teacher_book_read as TBR
    needed = len(rows) - len(second['records'])
    if needed < 0:
        raise ValueError('the teacher second set holds %d joins for %d rows; the rows do not leave the teacher'
                         % (len(second['records']), len(rows)))
    walked = PT.ROW_PASS_BOOK[0] or dict(groups={}, windows={}, cursor_group={}, changes=True, read_before=len(rows))
    book_needed = min(len(rows), walked.get('read_before') or 0)
    # joins recorded before the state labels were (a save of the code before them): their labels are read with the prefix
    label_needed = 0
    for record in second['records']:
        if 'state_labels' in record:
            break
        label_needed += 1
    label_needed = needed + label_needed if label_needed else 0
    on_row = None
    if feed is not None:
        # the sealed blocks (2026-10-09): every row is fed in cursor order as its parts exist (the merged prefix first,
        # as the merge proceeds, then the rows the walk joined), so block n seals the moment its rows are there
        on_row = feed.merge_view(rows, second['records'], needed, walked)
    prefix, read = (_second_set_prefix(open_market, needed, SS, book_needed, bool(walked.get('changes')), label_needed,
                                       on_row=on_row)
                    if needed or book_needed or label_needed else
                    ([], dict(groups={}, windows={}, cursor_group={}, labels={})))
    if feed is not None:
        feed.merged_rest(prefix, read)
    records = prefix + second['records']
    for cursor, (labels, origin) in read['labels'].items():
        records[cursor]['state_labels'], records[cursor]['state_label_origin'] = labels, origin
    unlabelled = [index for index, record in enumerate(records) if 'state_labels' not in record]
    if unlabelled:
        raise ValueError('%d row(s) of the second set carry no state labels (first %s); the rows do not leave the teacher'
                         % (len(unlabelled), unlabelled[:10]))
    check = SS.check_rows(records, rows)
    if check['rows_without_record'] or len(records) != len(rows):
        raise ValueError('the teacher second set holds %d joins for %d rows (the shared reader yielded %d of the %d rows '
                         'before the walk\'s own joins); a row without its joined planes does not leave the teacher'
                         % (len(records), len(rows), len(prefix), needed))
    groups = {**read['groups'], **walked['groups']}
    windows = {**read['windows'], **walked['windows']}
    cursor_group = {**read['cursor_group'], **walked['cursor_group']}
    group_labels = _group_labels(rows, records, cursor_group)
    reads = TBR.assemble(rows, cursor_group, groups, windows, whole_day=bool(walked.get('changes')),
                         group_labels=group_labels)
    day_split = _day_state_split(groups, group_labels, TBR)
    unread = [row[6] for row, entry in zip(rows, reads) if entry.get('status') == 'GROUP_NOT_READ']
    if unread:
        raise ValueError('the teacher book read lacks %d group(s) (first rows %s); a row without its book read does not '
                         'leave the teacher' % (len(unread), unread[:10]))
    for record, entry in zip(records, reads):
        record['book'] = entry
    carried, not_carried = _carriers()
    lock = max(row[4] for row in rows)
    header = dict(schema=SS.SCHEMA, format=SS.FORMAT, key_fields=SS.KEY_FIELDS, clock_fields=SS.CLOCK_FIELDS,
                  plane_reference=SS.PLANE_REFERENCE, state_reference=SS.STATE_REFERENCE,
                  key_rule='record i is teacher row i: key.adapter_cursor == the row cursor, its picture the one the '
                           'walk read that row with (picture.original_applied is the row\'s payload)',
                  clock_lock_time=dict(label=SS.LOCK_LABEL, teacher_as_of=lock,
                                       basis='the teacher\'s as_of (the latest receive clock of its rows), stamped once: '
                                             'not a picture element and never Frankie\'s lock'),
                  streams={stream.name: dict(pin=dict(stream.pin), kind=stream.kind) for stream in market.streams},
                  plane_values='by reference: (source, source_ordinal) names the row of that stream\'s pinned file the '
                               'picture handed over; the values are the ROOT\'s receipted rows, not copied',
                  carriers=market.layer_entries(), entries_carried=carried, entries_not_carried=not_carried,
                  rows_total=len(rows), rows_matched=check['rows_matched'], rows_mismatched=check['rows_mismatched'],
                  mismatches=check['mismatches'], clocks_compared=check['clocks_compared'],
                  joined_in_walk=len(second['records']) - second['restored'], restored_from_save=second['restored'],
                  merged_at_publication=len(prefix),
                  state_split=dict(format=TBR.SPLIT_FORMAT, unknown_bucket=TBR.STATE_UNKNOWN,
                                   label_fields=SS.STATE_LABEL_FIELDS, generic_rule='a lifecycle section not in '
                                   'label_fields: every top-level text or true/false field except %s' % (
                                       list(SS.GENERIC_EXCLUDED),),
                                   dipole='teacher.dstate|... : the teacher row\'s own DState (status, '
                                          'state.anchor_dir, state.armed, state.broken); derived_roll20_and_dipole_state '
                                          'is the teacher\'s Dipole state rows, not a picture plane',
                                   per_row='each R3 short window (64 groups) on its side: every label field\'s '
                                           'buckets with the event and book parts, sums_back per field, pinned_check '
                                           'against the row\'s pinned columns',
                                   day=day_split['summary'], day_file=STATE_SPLIT_FILE,
                                   rows_all_sum_back=sum(1 for entry in reads for read in (entry.get('windows') or {})
                                                         .values() if read.get('state_split', {}).get('all_sum_back')),
                                   rows_pinned_equal=sum(1 for entry in reads if ((entry.get('windows') or {}).get(
                                       'short') or {}).get('state_split', {}).get('pinned_check', {}).get('all_equal')),
                                   rows_pinned_not_equal=[row[6] for row, entry in zip(rows, reads) if (
                                       ((entry.get('windows') or {}).get('short') or {}).get('state_split', {})
                                       .get('pinned_check', {}).get('status') == 'compared'
                                       and not entry['windows']['short']['state_split']['pinned_check']['all_equal'])]),
                  book_read=dict(schema=TBR.SCHEMA, format=TBR.FORMAT, groups=len(groups),
                                 groups_read_in_walk=len(walked['groups']), groups_read_at_publication=len(read['groups']),
                                 rows_read_at_publication=book_needed, windows=sum(len(v) for v in windows.values()),
                                 whole_day=bool(walked.get('changes')),
                                 rule='beside the pinned functions on the same full rows (teacher_book_read); the '
                                      'rows before a resume whose save held no book read are read at publication from '
                                      'the same reader with the same functions'))
    from research.kalshi.frankie_boss import parallel_teacher as PT
    with (out / (STATE_SPLIT_FILE + '.pending')).open('w') as handle:
        json.dump(day_split, handle, sort_keys=True)
    os.replace(out / (STATE_SPLIT_FILE + '.pending'), out / STATE_SPLIT_FILE)
    header['state_split']['day_file_sha256'] = _sha256(out / STATE_SPLIT_FILE)
    path = out / SECOND_SET_FILE
    PT._save_raw_state(path, dict(header, records=records))
    mismatches = _write_list(out / MISMATCHES_FILE, header['mismatches'])
    header['mismatches_file'] = mismatches
    summary = dict({k: v for k, v in header.items() if k not in ('carriers', 'entries_carried', 'mismatches', 'streams')},
                file=SECOND_SET_FILE, sha256=_sha256(path), mismatches=mismatches,
                streams={name: value['pin'] for name, value in header['streams'].items()},
                entries_not_carried=[item['entry'] for item in not_carried],
                file_format='64 hex digits of the sha256 of the bytes after them, then the pickle of the header with '
                            '`records` (parallel_teacher._load_raw_state reads it)')
    return summary, records, header


def _carriers():
    """(entries carried by the picture {entry: {carrier, thinner}}, entries not carried [{entry, group, role, reason}])."""
    import frankie_box_all99_coverage as ALL99
    carried = {name: dict(carrier=first, thinner=thin) for name, (first, thin) in ALL99.MARKET_CARRIERS.items()}
    not_carried = [dict(entry=layer['entry'], group=layer['group'], role=layer['role'],
                        reason=ALL99.NOT_MARKET_CARRIED.get(layer['entry']) or (
                            'withheld by role (R09/R10: no teacher reads an answer key or a sealed target)'
                            if layer['role'] in ('answer', 'target') else
                            'not market evidence: the registry role %s is not carried by the picture' % layer['role']))
                   for layer in ALL99.entries() if layer['entry'] not in carried]
    return carried, not_carried


STATE_SPLIT_FILE = 'teacher-state-split.json'
MISMATCHES_FILE = 'teacher-second-set-mismatches.jsonl'
DIFFERENCES_FILE = 'teacher-book-event-differences.jsonl'


def _write_list(path, items):
    """A whole list as JSON lines beside the receipt (every item, never cut): {file, count, sha256}."""
    import hashlib
    digest, count = hashlib.sha256(), 0
    pending = Path(str(path) + '.pending')
    with pending.open('wb') as handle:
        for item in items:
            data = (json.dumps(item, sort_keys=True, default=repr) + '\n').encode()
            digest.update(data)
            handle.write(data)
            count += 1
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(pending, path)
    return dict(file=Path(path).name, count=count, sha256=digest.hexdigest(), format='one JSON value per line')


# ---- the classroom carry's anchors fed by the walk (frankie_box_classroom_code.TeacherPassCarry.enable_anchors /
# note_row, 2026-10-09: the classroom does not re-walk the market timeline to its last anchor). Each roster row's
# components are built as dipole_classroom._target_row builds them: the teacher's normalizer (identity: observe on a
# group-closing row, the raw value otherwise), the target's float32, TargetState names, a value only when PRESENT.
# Fed once per row, in row order, as soon as the row's worker results are in it (parallel_teacher.ROW_DONE). Only the
# identity normalizer is stateless enough to do this in the walk; any other leaves the anchors off (recorded).
def _enable_anchors(carry, teacher):
    value = carry['value']
    if not hasattr(value, 'enable_anchors'):
        carry['anchor_feed'] = dict(status='off', reason='this TeacherPassCarry has no anchors')
        return
    if type(teacher.normalizer).__name__ != 'IdentityNormalizerR3':
        carry['anchor_feed'] = dict(status='off', reason='the normalizer is not the identity: the target values exist only '
                                                         'after the attachment, so the walk cannot feed them')
        return
    value.enable_anchors()
    carry['anchor_feed'] = dict(status='on', basis='fed by the walk once per roster row (ROW_DONE)')


def _restored_anchors(carry):
    """A carry unpickled from a save: one written before the anchors existed holds none; it stays without them (the
    rows before the save were never fed), listed."""
    value = carry['value']
    if value is None or hasattr(value, 'anchor_on'):
        return
    value.anchor_on, value.anchor_pending, value.anchor = False, {}, {}
    value.anchor_pictures, value.anchor_rows, value.anchor_unvalued = {}, 0, []
    carry['anchor_feed'] = dict(status='off', reason='the carry was restored from a save written before the anchors: '
                                                     'its rows before the save were not fed')


def _anchor_feed(carry, teacher, T):
    import struct
    from research.kalshi.frankie_boss.c15_normalizer import NormalizedValue, State
    from research.kalshi.frankie_boss.dipole_target import TargetState
    normalizer, columns = teacher.normalizer, tuple(T.CONTROL_COLUMNS)

    def feed(index, row):
        value = carry['value']
        if value is None or not value.anchor_on or row[6] not in value.anchor_pending:
            return
        _, has_receipt, iid, combined = row[:4]
        normalized = ([normalizer.observe(iid, c, v['value'], State(v['state'])) for c, v in zip(columns, combined)]
                      if has_receipt else [NormalizedValue(v['value'], State(v['state'])) for v in combined])
        components = []
        for name, item in zip(columns, normalized):
            state = TargetState(int(item.state)).name
            stored = struct.unpack('<f', struct.pack('<f', item.value))[0]
            components.append((name, state, float(stored) if state == TargetState.PRESENT.name else None))
        value.note_row(row[6], components)
    return feed


def _anchor_record(carry, source):
    """carry anchors: n, and each anchor's value checked against the published snapshot row (the classroom reads both)."""
    value = carry.get('value')
    record = dict(carry.get('anchor_feed') or dict(status='off', reason='no carry'))
    if value is None or not getattr(value, 'anchor_on', False):
        return record
    rows = {row['cursor']: {c['name']: c for c in row['components']} for row in source['rows']}
    checked = differ = 0
    first = []
    for name, slot in value.anchor.items():
        for which, (cursor, number) in slot.items():
            component = (rows.get(cursor) or {}).get(name)
            checked += 1
            if component is None or component['state'] != 'PRESENT' or component['value'] != number:
                differ += 1
                first.append(dict(component=name, anchor=which, cursor=cursor, fed=number,
                                  published=None if component is None else component['value']))
    record.update(anchors=len(value.anchor_pictures), components=len(value.anchor), rows_valued=value.anchor_rows,
                  rows_without_values=len(value.anchor_unvalued) + len(value.anchor_pending),
                  checked_against_snapshot=checked, differ=differ, differing=first)
    return record


def _group_labels(rows, records, cursor_group):
    """(key, ordinal) -> the state labels of the instant that closes that group: the planes' labels from its joined
    picture and the teacher row's own DState (teacher.dstate|...)."""
    out = {}
    for index, row in enumerate(rows):
        group = cursor_group.get(row[6])
        if group is None:
            continue
        labels = dict(records[index].get('state_labels') or {})
        if len(row) > 8 and isinstance(row[8], dict):
            dstate = row[8]
            labels['teacher.dstate|status'] = dstate.get('status')
            state = dstate.get('state') if isinstance(dstate.get('state'), dict) else {}
            for name in ('anchor_dir', 'armed', 'broken'):
                if name in state:
                    labels['teacher.dstate|state.%s' % name] = state[name]
        out[group] = labels
    return out


def _day_state_split(groups, group_labels, TBR):
    """The whole day's split, per side: for every label field, every bucket's parts and its share of the day's
    totals (written to STATE_SPLIT_FILE; a summary of the field and bucket counts goes on the receipt)."""
    ordered = sorted(groups)
    results = [groups[key] for key in ordered]
    labels = [group_labels.get(key) for key in ordered]
    sides = {}
    for side in TBR.SIDES:
        split = TBR.state_split(results, labels, side)
        totals = split['totals']['events']
        for field in split['fields'].values():
            for bucket in field['buckets'].values():
                bucket['share_of_day'] = {k: (bucket['events'].get(k, 0) / v if v else None) for k, v in totals.items()}
        sides[side] = split
    summary = dict(groups=len(ordered), fields=len(sides[TBR.SIDES[0]]['fields']) if ordered else 0,
                   buckets={side: sum(len(f['buckets']) for f in value['fields'].values()) for side, value in sides.items()},
                   unknown_groups={side: {name: f['unknown_groups'] for name, f in value['fields'].items()
                                          if f['unknown_groups']} for side, value in sides.items()},
                   all_sum_back={side: value['all_sum_back'] for side, value in sides.items()})
    return dict(schema='FRANKIE_TEACHER_STATE_SPLIT_DAY_V1', format=TBR.SPLIT_FORMAT, sides=sides, summary=summary)


ROWS_SIDECAR = 'host-dipole-classroom-source.c15.rows.jsonl'
SIDECAR_ROW_KEYS = ('key', 'clocks', 'clocks_absent', 'planes', 'planes_state', 'planes_absent', 'invalidated',
                    'coverage', 'match', 'book_columns', 'state_split', 'state_labels', 'state_label_origin')


def _sidecar_planes(record, carried):
    """{99 entry: [[source, source_ordinal, input_cursor, instrument_id, known_at_ns]...]} of one row (every entry the
    picture carries; the entries carried by the row itself or the picture's own fields name that element), and
    {entry: reason} for an entry with no plane row at this instant."""
    placed = {}
    for source, ordinal, cursor, instrument, known, entries in record['planes']:
        for entry in entries:
            placed.setdefault(entry, []).append([source, ordinal, cursor, instrument, known])
    planes, absent = {}, {}
    for entry, how in carried.items():
        carrier = how['carrier']
        if carrier in ('input', 'clock', 'availability', 'opening'):
            planes[entry] = dict(carrier=carrier, element=('the row itself (its APPLIED payload, key and clocks)'
                                                           if carrier != 'opening' else 'picture.opening_state'))
        elif carrier == 'completed':
            planes[entry] = []
            absent[entry] = ('completed-only: a post-stream aggregate (report.completed_sources), never a value in a '
                             'live picture')
        elif entry in placed:
            planes[entry] = placed[entry]
        else:
            planes[entry] = []
            absent[entry] = 'no %s row was placed at this instant' % carrier
    return planes, absent


def _sidecar_split(book):
    """The row's state split (each window's, keyed by its slot), its own row role in the sidecar."""
    return {slot: read['state_split'] for slot, read in (book.get('windows') or {}).items() if 'state_split' in read}


def _sidecar_book(book):
    """The book read of a row as JSON values: each side's depth decoded to [price, size, count] per level; the state
    split goes to its own role (state_split)."""
    from research.kalshi.frankie_boss import teacher_book_read as TBR
    if book.get('windows'):
        book = dict(book, windows={slot: {k: v for k, v in read.items() if k != 'state_split'}
                                   for slot, read in book['windows'].items()})
    group = book.get('group')
    if group is None:
        return book
    return dict(book, group=dict(group, depth={side: (None if depth is None else [list(level) for level in
                                                                                   TBR.depth_levels(depth)])
                                               for side, depth in group['depth'].items()}))


def _refuse_json(value):
    raise TypeError('row value of type %s is not JSON' % type(value).__name__)


def _sidecar_document(row, record, book, carried, lock, SS):
    """One sidecar line's document: the snapshot row with its second set (SIDECAR_ROW_KEYS), the lock stamped."""
    planes, absent = _sidecar_planes(record, carried)
    clocks = dict(record['clocks'], clock_lock_time=dict(label=SS.LOCK_LABEL, teacher_as_of=lock))
    return dict(row, key=record['key'], clocks=clocks, clocks_absent=record['clocks_absent'],
                planes=planes, planes_state=record['state'], planes_absent=absent,
                invalidated=record['invalidated'], coverage=record['coverage'], match=record['match'],
                state_labels=record['state_labels'], state_label_origin=record['state_label_origin'],
                book_columns=_sidecar_book(book), state_split=_sidecar_split(book))


def _sidecar_line(row, record, book, carried, lock, SS):
    return (json.dumps(_sidecar_document(row, record, book, carried, lock, SS), default=_refuse_json, allow_nan=False)
            + '\n').encode()


def _write_rows_sidecar(out, source, records, header, SS):
    """The rows as JSON lines beside the rows file (one row per line, streamed and hashed on the stream): line 1 the
    header (schema, FORMAT, the row keys, the key and clock fields, the stream pins), then every snapshot row with its
    second set (SIDECAR_ROW_KEYS), joined by the row cursor. Values are written whole (json; floats round-trip)."""
    import hashlib
    by_cursor = {record['key']['adapter_cursor']: record for record in records}
    carried = header['entries_carried']
    path, temporary = out / ROWS_SIDECAR, out / (ROWS_SIDECAR + '.pending')
    digest, lines, unjoined = hashlib.sha256(), 0, []
    lock = header['clock_lock_time']['teacher_as_of']

    with temporary.open('wb') as handle:
        def write(document):
            data = (json.dumps(document, default=_refuse_json, allow_nan=False) + '\n').encode()
            digest.update(data)
            handle.write(data)
        write(dict(schema='FRANKIE_TEACHER_ROWS_SIDECAR_V1', format=SS.FORMAT, rows_file=ROWS_FILE,
                   source_snapshot_hash=source.get('source_snapshot_hash'), rows=len(source['rows']),
                   row_keys=SIDECAR_ROW_KEYS, key_fields=SS.KEY_FIELDS, clock_fields=SS.CLOCK_FIELDS,
                   plane_reference=list(SS.PLANE_REFERENCE[:5]), state_reference=list(SS.STATE_REFERENCE),
                   clock_lock_time=header['clock_lock_time'], plane_values=header['plane_values'],
                   streams={name: value['pin'] for name, value in header['streams'].items()},
                   entries_not_carried=header['entries_not_carried']))
        for row in source['rows']:
            record = by_cursor.get(row['cursor'])
            if record is None:
                unjoined.append(row['cursor'])
                continue
            write(_sidecar_document(row, record, record['book'], carried, lock, SS))
            lines += 1
        handle.flush()
        os.fsync(handle.fileno())
    if unjoined:
        temporary.unlink()
        raise ValueError('%d snapshot row(s) have no second-set record (first cursors %s); the rows do not leave the '
                         'teacher' % (len(unjoined), unjoined[:10]))
    os.replace(temporary, path)
    return dict(file=ROWS_SIDECAR, sha256=digest.hexdigest(), rows=lines, format=SS.FORMAT,
                schema='FRANKIE_TEACHER_ROWS_SIDECAR_V1', row_keys=list(SIDECAR_ROW_KEYS),
                basis='line 1 the header, then one snapshot row per line with its second set; sha256 of the bytes '
                      'as written')


# ---- the sealed blocks (Greg, 2026-10-09: "Can we start sending data out as it's coming in?"; frankie_box_teacher_blocks)
# The rows sidecar is appended block by block on the receive clock (FRANKIE_BLOCK_SCHEDULE_MINUTES, default "5,30": the
# five-minute canary, then thirty-minute blocks; "0" turns it off) while the rows are produced: in the walk (each row fed
# as the row pass reports it complete, parallel_teacher.ROW_DONE; a block seals once the book reads of its groups are in)
# and in the publication's merge of the rows a resumed walk did not join (_second_set_prefix on_row: a block seals the
# moment its rows are merged). Each line is built by the same _sidecar_line as the whole-day writer; the lock stamped on a
# block's lines is the block's teacher as_of (the latest receive clock of the rows through it), declared in the header.
# Every stateful measure crosses the boundary by carry: the book read's whole-day running window
# (teacher_book_read.assemble running=), the group labels of every closed group, the R3 windows (the book groups kept by
# reference), the cutter's running receive clock. The final publication re-builds every line from the whole-day result
# and compares each block's bytes (a difference refuses the publication, named); the sidecar is then the sealed file.
PLANE_VALUES = ('by reference: (source, source_ordinal) names the row of that stream\'s pinned file the picture handed '
                'over; the values are the ROOT\'s receipted rows, not copied')
SIDECAR_SCHEMA = 'FRANKIE_TEACHER_ROWS_SIDECAR_V1'
BLOCK_FEED = [None]
SECOND_RECORDS = [None]            # the walk's `second` (its 'records': the walk feed's joins, by reference)
BLOCK_TARGET_CHUNK = 4096          # snapshot rows built per target call inside a block (memory only; no value depends on it)


def _row_done(anchors, feed):
    """parallel_teacher.ROW_DONE: the anchors' feed (its error stops the reports, as before), then the block feed (never
    raises)."""
    if anchors is None and feed is None:
        return None

    def report(index, row):
        try:
            if anchors is not None:
                anchors(index, row)
        finally:
            if feed is not None:
                feed.on_walk_row(index, row)
    return report


def _block_feed(out, *, day, market, teacher, rc, SS):
    """The block feed of this teacher process, or (None, record) when blocks are off (FRANKIE_BLOCK_SCHEDULE_MINUTES=0)
    and no manifest stands. A manifest left by an earlier process is continued whatever the setting says."""
    B = _box_module('frankie_box_teacher_blocks')
    minutes, setting = B.schedule_setting()
    standing = B.read_manifest(out)
    if minutes is None and standing is None:
        return None, setting
    if minutes is None:
        minutes = tuple(standing['schedule']['minutes'])
        setting = dict(setting, outcome='continued', reason='a manifest of sealed blocks stands: they continue')
    return _BlockFeed(out, day=day, market=market, teacher=teacher, rc=rc, SS=SS, minutes=minutes, setting=setting), setting


class _BlockFeed:
    def __init__(self, out, *, day, market, teacher, rc, SS, minutes, setting):
        from collections import deque
        from research.kalshi.frankie_boss import teacher_book_read as TBR, parallel_teacher as PT
        from research.kalshi.frankie_boss import dipole_classroom as DC
        self.B, self.TBR, self.PT, self.DC, self.SS = _box_module('frankie_box_teacher_blocks'), TBR, PT, DC, SS
        self.out, self.day, self.teacher, self.rc = Path(out), day, teacher, rc
        self.carried, not_carried = _carriers()
        origin, basis = self.B.trading_day_open_ns(day)
        header = dict(schema=SIDECAR_SCHEMA, format=SS.FORMAT, rows_file=ROWS_FILE, source_snapshot_hash=None, rows=None,
                      row_keys=SIDECAR_ROW_KEYS, key_fields=SS.KEY_FIELDS, clock_fields=SS.CLOCK_FIELDS,
                      plane_reference=list(SS.PLANE_REFERENCE[:5]), state_reference=list(SS.STATE_REFERENCE),
                      clock_lock_time=dict(label=SS.LOCK_LABEL, teacher_as_of=None, per_block=True,
                                           basis='sealed blocks: each row\'s clocks.clock_lock_time.teacher_as_of is its '
                                                 'block\'s teacher as_of (the latest receive clock of the rows through '
                                                 'that block); the whole day\'s is on the receipt and in %s'
                                                 % self.B.MANIFEST_FILE),
                      plane_values=PLANE_VALUES, streams={stream.name: dict(stream.pin) for stream in market.streams},
                      entries_not_carried=not_carried,
                      blocks=dict(manifest=self.B.MANIFEST_FILE, rule='this file is this header followed by every sealed '
                                  'block\'s bytes in order (blocks/<n>.json: its byte range and sha256)'))
        try:
            wake = _box_module('frankie_box_frankie_queue').wake_dir()
        except Exception:  # noqa: BLE001 - the manifest's rename still wakes a waiter on the rows directory
            wake = None
        self.sealer = self.B.BlockSealer(self.out, day=day, schedule=self.B.Schedule(minutes), origin_ns=origin,
                                         origin_basis=basis if origin is not None else '%s; the first row\'s receive '
                                         'clock instead' % basis, header=header, sidecar_name=ROWS_SIDECAR,
                                         log=lambda text: print(text, flush=True), wake_dir=wake, setting=setting)
        self.changes = PT._changes_applied()
        self.mode = 'off' if self.sealer.complete else 'pending'     # pending -> walk | merge
        self.error = None
        self.pending = deque()
        self.entity = None
        self._reset()

    def _reset(self):
        self.fed, self.cutter, self.running, self.group_labels = 0, None, {}, {}
        self.pending.clear()
        self.rows = self.records = self.cg = self.groups = self.windows = None
        self.book_size = -1

    # -- the row parts (references; nothing copied)
    def _label(self, index, row):
        group = self.cg.get(row[6])
        if group is not None:
            self.group_labels.update(_group_labels([row], [self.records(index)], {row[6]: group}))

    def _feed(self, index):
        row = self.rows[index]
        self._label(index, row)
        if index < self.sealer.next_cursor:          # sealed by an earlier process: only the carry is replayed
            if self.changes:
                self.TBR.advance_running(self.running, [row], self.cg, self.groups, self.windows)
            return
        if self.cutter is None:
            if self.sealer.manifest['schedule'].get('origin_ns') is None:
                self.sealer.manifest['schedule']['origin_ns'] = row[4]
            self.cutter = self.sealer.cutter(row[4])
        for block in self.cutter.offer(index, row[4]):
            self.pending.append(block)

    def _ready(self, block):
        if self.mode != 'walk':
            return True
        if 'unresolved' not in block:
            a, b = block['cursor_range']
            block['unresolved'] = {self.cg[c] for c in range(a, b) if self.rows[c][1] and c in self.cg}
        block['unresolved'] = {g for g in block['unresolved'] if self.groups.get(g) is None}
        return not block['unresolved']

    def _drain(self):
        while self.pending and self._ready(self.pending[0]):
            block = self.pending.popleft()
            block.pop('unresolved', None)
            self._seal(block)

    def _state_after(self, block):
        index = block['index'] + 1
        start = block['clock_range'][1]
        return dict(origin_ns=self.cutter.origin, index=index, start_cursor=block['cursor_range'][1], start_ns=start,
                    end_ns=start + self.sealer.schedule.length(index), known_by=block['known_by'],
                    lock=block['teacher_as_of'])

    def _lines(self, block, extra):
        import math
        a, b = block['cursor_range']
        span = self.rows[a:b]
        entries = self.TBR.assemble(span, self.cg, self.groups, self.windows, whole_day=self.changes,
                                    group_labels=self.group_labels, running=self.running)
        wanted = [k for k, row in enumerate(span) if row[6] in self.entity]
        sums, lock, columns = {}, block['teacher_as_of'], self.DC.COLUMNS
        for start in range(0, len(wanted), BLOCK_TARGET_CHUNK):
            part = wanted[start:start + BLOCK_TARGET_CHUNK]
            made = self.PT.block_targets(self.teacher, [span[k] for k in part], self.rc['manifest_hash'])
            for k, (target, receipt) in zip(part, made):
                row = span[k]
                snap = self.DC._target_row(target, row[3], receipt, row[6])
                if len(row) > 8:
                    state = row[8]
                    if (state.get('schema') != 'FRANKIE_TEACHER_DSTATE_ROWS_V1'
                            or any(state.get(key) != snap[key] for key in ('cursor', 'source_prefix_hash', 'ts_recv_ns'))
                            or state.get('status') not in ('GROUP_STATE', 'NOT_F_LAST')
                            or (state['status'] == 'GROUP_STATE') != isinstance(state.get('state'), dict)):
                        raise ValueError('teacher DState differs from its exact target source row (cursor %d)' % row[6])
                    snap['dstate'] = state
                snap['raw_components'] = {name: dict(value) for name, value in zip(columns, row[3])}
                for component in snap['components']:
                    slot = sums.setdefault(component['name'], dict(present=0, values=[], states={}))
                    slot['states'][component['state']] = slot['states'].get(component['state'], 0) + 1
                    if component['value'] is not None:
                        slot['present'] += 1
                        slot['values'].append(component['value'])
                yield _sidecar_line(snap, self.records(row[6]), entries[k], self.carried, lock, self.SS)
        extra['pinned_sums'] = {name: dict(present=slot['present'], sum=math.fsum(slot['values']), states=slot['states'])
                                for name, slot in sums.items()}
        extra['snapshot_rows'] = len(wanted)

    def _seal(self, block):
        a, b = block['cursor_range']
        extra = dict(mode=self.mode,
                     second_set=dict(records=[a, b], file=SECOND_SET_FILE,
                                     carried_in='this block\'s sidecar lines: each row\'s key, clocks, plane references, '
                                                'book columns, state split and labels (teacher-second-set.pkl records '
                                                '[a, b) at the final publication)'),
                     carried_state=dict(
                         book_running={str(k): v['upto'] for k, v in self.running.items()},
                         group_labels=len(self.group_labels),
                         r3_windows='the short (64-group) and long (1024-group) R3 windows of later rows reach back into '
                                    'this block\'s book groups (held by reference)',
                         receive_clock_known_by=block['known_by'], teacher_as_of=block['teacher_as_of'],
                         walk='the classroom carry, cutoff tracker and the row pass continuation continue on the walk '
                              '(saved with its position)',
                         normalizer='identity (stateless)'))
        self.sealer.seal(block, self._lines(block, extra), extra, cutter_state=self._state_after(block),
                         walk_cursor=self.fed)

    # -- the walk (parallel_teacher.ROW_DONE)
    def on_walk_row(self, index, row):
        if self.mode in ('off', 'merge', 'failed'):
            return
        try:
            if self.mode == 'pending':
                live = self.PT.ROW_PASS_LIVE[0]
                records = SECOND_RECORDS[0]['records'] if SECOND_RECORDS[0] is not None else None
                why = None
                if live is None or records is None:
                    why = 'no live row pass state'
                elif (live.get('book_before') or 0) > self.sealer.next_cursor:
                    why = 'the save holds no book read for rows before %d' % live['book_before']
                elif len(records) < index:
                    why = 'the save holds %d joins for %d rows' % (len(records), index)
                elif any('state_labels' not in r for r in records[self.sealer.next_cursor:index]):
                    why = 'joins before the state labels in the save'
                if why is not None:
                    self.mode = 'merge'
                    self.sealer.manifest.setdefault('notes', []).append(
                        'walk sealing not taken (%s): blocks seal in the publication merge' % why)
                    return
                streams = live['streams']
                self.rows, self.records = live['rows'], records.__getitem__
                self.cg, self.groups, self.windows = streams.cursor_group, streams.book_groups, streams.windows
                self.entity = live['entity_hashes']
                self.mode = 'walk'
                while self.fed < index:                 # the saved rows first (their parts are in the save)
                    self._feed(self.fed)
                    self.fed += 1
            self._feed(index)
            self.fed = index + 1
            if self.pending and len(self.groups) != self.book_size:
                self.book_size = len(self.groups)
                self._drain()
        except Exception as error:  # noqa: BLE001 - never stops the walk: the publication merge seals from the manifest
            self.error = 'walk: %s: %s' % (type(error).__name__, error)
            self.mode = 'merge'
            self.sealer.manifest.setdefault('notes', []).append('walk sealing stopped (%s); continued in the merge'
                                                                % self.error)

    # -- the publication merge (_second_set)
    def merge_view(self, rows, walk_records, needed, walked):
        from collections import ChainMap
        if self.mode in ('off', 'failed'):
            return None
        walking = self.mode == 'walk' and self.error is None
        if not walking:
            self._reset()
        self.mode = 'walk' if walking else 'merge'
        self.rows = rows
        view = dict(prefix=[], book=None)

        def record(index):
            rec = view['prefix'][index] if index < needed else walk_records[index - needed]
            label = view['book']['labels'].get(index)
            if label is not None and 'state_labels' not in rec:
                rec = dict(rec, state_labels=label[0], state_label_origin=label[1])
            return rec

        def bind(book):
            view['book'] = book
            self.cg = ChainMap(book['cursor_group'], walked['cursor_group'])
            self.groups = ChainMap(book['groups'], walked['groups'])
            self.windows = ChainMap(book['windows'], walked['windows'])
        self.view, self.bind = view, bind
        if walking:
            return None                                # every row was fed in the walk; the rest closes in merged_rest
        self.records = record
        bind(dict(groups={}, windows={}, cursor_group={}, labels={}))

        def on_row(index, records, book):
            if self.mode != 'merge':
                return
            try:
                if view['book'] is not book:
                    bind(book)
                view['prefix'] = records
                while self.fed <= index:
                    self._feed(self.fed)
                    self.fed += 1
                self._drain()
            except Exception as error:  # noqa: BLE001 - never stops the merge; listed and the blocks end here
                self._fail('merge: %s: %s' % (type(error).__name__, error))
        return on_row

    def merged_rest(self, prefix, read):
        if self.mode not in ('walk', 'merge'):
            return
        try:
            if self.mode == 'merge':
                self.view['prefix'] = prefix
                self.bind(read)
            while self.fed < len(self.rows):
                self._feed(self.fed)
                self.fed += 1
            if self.cutter is None:
                raise ValueError('no row was fed')
            self.pending.append(self.cutter.close())
            self.mode = 'merge'                        # every row's parts are there now: nothing waits on a book read
            self._drain()
        except Exception as error:  # noqa: BLE001
            self._fail('merge end: %s: %s' % (type(error).__name__, error))

    def _fail(self, reason):
        self.error, self.mode = reason, 'failed'
        try:
            self.sealer.finish('failed', complete=False, reason=reason)
        except Exception:  # noqa: BLE001
            pass
        print('TEACHER_BLOCKS failed: %s' % reason, flush=True)

    # -- the final publication
    def verify(self, source, records):
        """Every sealed block's bytes against the lines built from the whole-day result (record['book'], the snapshot
        rows): equal, or ValueError naming each differing block. Returns the rows_sidecar pin."""
        manifest = self.sealer.manifest
        side = self.out / ROWS_SIDECAR
        with side.open('rb') as handle:
            head = handle.read(manifest['header']['bytes'][1])
        if hashlib.sha256(head).hexdigest() != manifest['header']['sha256']:
            raise ValueError('the rows sidecar header differs from its manifest pin')
        digest = hashlib.sha256(head)
        by_cursor = {record['key']['adapter_cursor']: record for record in records}
        rows, at, differ, lines = source['rows'], 0, [], 0
        for entry in manifest['blocks']:
            a, b = entry['cursor_range']
            block_digest, count = hashlib.sha256(), 0
            while at < len(rows) and rows[at]['cursor'] < b:
                row = rows[at]
                if row['cursor'] < a:
                    raise ValueError('snapshot row %d lies before block %d' % (row['cursor'], entry['index']))
                record = by_cursor[row['cursor']]
                data = _sidecar_line(row, record, record['book'], self.carried, entry['teacher_as_of'], self.SS)
                block_digest.update(data)
                digest.update(data)
                count += 1
                at += 1
            lines += count
            if block_digest.hexdigest() != entry['sidecar_sha256'] or count != entry['lines']:
                differ.append(dict(index=entry['index'], lines=[entry['lines'], count],
                                   sha256=[entry['sidecar_sha256'], block_digest.hexdigest()]))
        if at != len(rows):
            differ.append(dict(unsealed_snapshot_rows=len(rows) - at, first_cursor=rows[at]['cursor']))
        if side.stat().st_size != manifest['sealed_bytes']:
            differ.append(dict(sidecar_bytes=side.stat().st_size, sealed_bytes=manifest['sealed_bytes']))
        if differ:
            raise ValueError('the sealed blocks differ from the whole-day rows (%d): %s; the rows do not leave the '
                             'teacher' % (len(differ), json.dumps(differ[:10])))
        return dict(file=ROWS_SIDECAR, sha256=digest.hexdigest(), rows=lines, format=self.SS.FORMAT, schema=SIDECAR_SCHEMA,
                    row_keys=list(SIDECAR_ROW_KEYS), blocks=self.sealer.sealed_pin(),
                    basis='line 1 the header, then every sealed block\'s rows (each row\'s lock its block\'s teacher '
                          'as_of); every block re-built from the whole-day result and equal; sha256 of the bytes')

    def complete(self, receipt_path, result):
        self.sealer.finish('complete', complete=True, receipt=dict(file='receipt.json', sha256=_sha256(receipt_path)),
                           pins=dict(rows_file=result.get('rows_file'),
                                     rows_sidecar=(result.get('rows_sidecar') or {}).get('sha256'),
                                     second_set=(result.get('teacher_second_set') or {}).get('sha256'),
                                     attachment=result.get('attachment_file')), walk_cursor=self.fed)


ACCOUNT_FORMAT = 1


def _teacher_account(rows, records, header, *, raw_saves, cpu_pinning, phases, walked, processed, out):
    """The facts the teacher's own account is written from (Greg, 2026-10-09: which data it saw together, what it lacks,
    what it would want, what would give better outputs, beside its findings). Every number is counted from this run's
    rows, second set, pools and clocks; nothing is estimated. FORMAT ACCOUNT_FORMAT. The day reports render it."""
    from collections import Counter
    import resource
    from research.kalshi.frankie_boss import parallel_teacher as PT, teacher_book_read as TBR
    from research.kalshi.frankie_boss.c15_teacher_r3 import CONTROL_COLUMNS
    account = dict(schema='FRANKIE_TEACHER_ACCOUNT_V1', format=ACCOUNT_FORMAT,
                   basis='counted from this run (rows, second set, pools, clocks); nothing estimated')
    # (e) the pinned columns' coverage: per column, the states and reasons over every row
    pinned = {}
    for index, name in enumerate(CONTROL_COLUMNS):
        states, reasons = Counter(), Counter()
        for row in rows:
            value = row[3][index]
            states[value.get('state')] += 1
            if value.get('reason'):
                reasons[value['reason']] += 1
        pinned[name] = dict(states={str(k): v for k, v in sorted(states.items(), key=str)},
                            reasons=dict(sorted(reasons.items())))
    science = dict(pinned_columns=pinned)
    if records is None:
        account.update(read_together=dict(status='no second set', reason='no shared market reader on this ROOT'),
                       science=science)
        return account
    # (a) what was read together per row
    carried = header['entries_carried']
    present, absent_reasons = Counter(), {}
    clocks_present = Counter()
    for record in records:
        seen = set()
        for _, _, _, _, _, entries in record['planes']:
            seen.update(entries)
        for entry, how in carried.items():
            if how['carrier'] in ('input', 'clock', 'availability', 'opening') or entry in seen:
                present[entry] += 1
            else:
                reason = ('completed-only: a post-stream aggregate, never a value in a live picture'
                          if how['carrier'] == 'completed' else 'no %s row was placed at this instant' % how['carrier'])
                absent_reasons.setdefault(entry, Counter())[reason] += 1
        for clock in _clocks_carried(record):
            clocks_present[clock] += 1
    total = len(records)
    planes = {entry: dict(carrier=how['carrier'], rows_present=present[entry], rows_absent=total - present[entry],
                          absent_reasons=dict(absent_reasons.get(entry, {})))
              for entry, how in carried.items()}
    account['read_together'] = dict(
        rows=total, planes=planes, clocks=dict(carried_rows=dict(clocks_present), fields=list(header['clock_fields'])),
        book_columns=['book_balance', 'book_absorption', 'counts', 'event_incomplete', 'reconciliation', 'group.depth',
                      'group.touches', 'group.sides'],
        state_split=dict(status='built', planes=sorted({name.split('|')[0] for record in records
                                                        for name in record.get('state_labels') or ()}),
                         label_fields=sorted({name for record in records for name in record.get('state_labels') or ()}),
                         dipole='teacher.dstate (the teacher row\'s own DState)'))
    # (b) missing or thin
    reconciliation, examples = Counter(), []
    for record in records:
        group = (record.get('book') or {}).get('group')
        if not group:
            continue
        for side, part in group['sides'].items():
            for measure, found in part['differs'].items():
                for reason in found['reasons']:
                    reconciliation['%s:%s' % (measure, reason)] += 1
                examples.append((abs(found['book'] - found['events']), record['key']['adapter_cursor'], side, measure,
                                 found['book'], found['events'], found['reasons']))
    examples.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    differences = _write_list(out / DIFFERENCES_FILE, [
        dict(cursor=c, side=sd, measure=m, book=b, events=e, difference=d, reasons=r)
        for d, c, sd, m, b, e, r in examples])
    guard = (cpu_pinning.get('raw_pool') or {}).get('guard') or {}
    account['missing_or_thin'] = dict(
        planes_never_carried=header['entries_not_carried'],
        planes_partial={entry: value for entry, value in planes.items() if value['rows_absent']},
        clock_mismatches=dict(rows=header['rows_mismatched'], all=header.get('mismatches_file')),
        rows_read_in_walk=header['joined_in_walk'], rows_restored_from_save=header['restored_from_save'],
        rows_merged_at_publication=header['merged_at_publication'],
        book_read=header.get('book_read'),
        state_unknown_groups=((header.get('state_split') or {}).get('day') or {}).get('unknown_groups'),
        reconciliation=dict(differences=sum(reconciliation.values()), by_measure_reason=dict(sorted(reconciliation.items())),
                            all=differences, order='largest absolute difference first, then cursor, side, measure'),
        guard=dict(guard))
    # (c) wants, derived from (b)
    wants = [dict(want=entry['entry'] if isinstance(entry, dict) else entry, reason='never carried by the picture on '
                  'this day') for entry in header['entries_not_carried']]
    wants += [dict(want=entry, reason='absent on %d of %d rows: %s' % (value['rows_absent'], total, value['absent_reasons']))
              for entry, value in planes.items() if value['rows_absent']]
    questions = [dict(question='why do book and event %s differ (%s)?' % tuple(name.split(':', 1)), rows=count)
                 for name, count in sorted(reconciliation.items())]
    for side, fields in (((header.get('state_split') or {}).get('day') or {}).get('unknown_groups') or {}).items():
        for name, count in sorted(fields.items()):
            wants.append(dict(want=name, reason='side %s: %d group(s) with no row of that plane at their closing '
                                                'instant (state unknown)' % (side, count)))
    account['wants'] = dict(wants=wants, questions=questions,
                            rule='every plane absent or partial is a want; every reconciliation class a question')
    # (d) runtime facts
    shipped = (cpu_pinning.get('raw_pool') or {}).get('shipped') or {}
    account['runtime'] = dict(
        rows=processed, walk_seconds=round(walked, 1), rows_per_second=round(processed / walked, 2) if walked else None,
        phase_seconds=dict(phases), raw_batches=dict(shipped), evidence_precompute=cpu_pinning.get('evidence_precompute'),
        saves=raw_saves, memory_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        one_pass=dict(rows_joined_in_walk=header['joined_in_walk'],
                      rows_read_again_at_publication=header['merged_at_publication'],
                      reader_seek=raw_saves.get('reader_seek') if isinstance(raw_saves, dict) else None))
    # (e) findings
    sides = {side: dict(book=Counter(), events=Counter()) for side in TBR.SIDES}
    for record in records:
        group = (record.get('book') or {}).get('group')
        if group:
            for side, part in group['sides'].items():
                sides[side]['book'].update(part['book'])
                sides[side]['events'].update(part['events'])
    science.update(book_vs_events={side: dict(book=dict(value['book']), events=dict(value['events']))
                                   for side, value in sides.items()},
                   state_split=dict(header.get('state_split') or {}, status='built',
                                    findings='per label field and bucket, both sides, with each bucket\'s share of the '
                                             'day\'s totals: %s' % STATE_SPLIT_FILE))
    account['science'] = science
    return account


def _clocks_carried(record):
    """The clock names this row carries a value for (clocks_absent lists the others with their reason)."""
    return [name for name in record['clocks'] if name not in record.get('clocks_absent', {})]


def teach(day, receipt_path, receipt_sha256, workers, day_external=None, day_external_sha256=None,
          *, calculations=None, shared_market_policy=None):
    # Keep the cooperative handler through publication too: an orderly stop must not
    # leave a completed attachment without its rows/external section/completion receipt.
    import signal
    requested = [False]
    def request_save(*_):
        requested[0] = True
    # The row pass asks at every row (a2/20231018 py-spy: a Path.exists per row on the parent). The lane stop file is
    # watched by the box's event latch (frankie_box_wake.FileLatch: inotify + SIGIO, armed before the first check, a
    # read costs no syscall), as the classroom does; a stat per ask only when the latch cannot be armed here.
    stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')
    latch = None
    if stop_file:
        try:
            latch = _box_module('frankie_box_wake').FileLatch(stop_file)
        except Exception:  # noqa: BLE001 - no latch: the stop file is checked with a stat per ask, as before
            latch = None
    def save_requested():
        if requested[0]:
            return True
        if not stop_file:
            return False
        return latch.set if latch is not None else Path(stop_file).exists()
    previous_signal = signal.signal(signal.SIGTERM, request_save)
    try:
        return _teach(day, receipt_path, receipt_sha256, workers, day_external,
                      day_external_sha256, save_requested=save_requested, calculations=calculations,
                      shared_market_policy=shared_market_policy)
    finally:
        signal.signal(signal.SIGTERM, previous_signal)
        if latch is not None:
            latch.close()


def _teach(day, receipt_path, receipt_sha256, workers, day_external=None, day_external_sha256=None,
           *, save_requested, learner_binding=None, learner_directory=None,
           calculations=None, shared_market_policy=None):
    receipt_path = Path(receipt_path)
    IDENTITY_REBINDS.clear()
    # Where the time goes (Greg, 2026-10-07: keep the instrumentation that shows it): seconds per phase of this
    # step, recorded in the receipt as phase_timings. Diagnostic only; never an identity, never a gate.
    phases, phase_started = {}, [time.time()]
    def phase(name):
        now = time.time()
        phases[name] = round(phases.get(name, 0.0) + now - phase_started[0], 3)
        phase_started[0] = now
        try:                                     # the stage heartbeat (frankie_box_stage_progress); never changes the stage
            import frankie_box_stage_progress as _SP
            _SP.report_phase('teacher: %s done' % name, units_done=len(phases), unit='phases')
        except Exception:  # noqa: BLE001
            pass
    if _sha256(receipt_path) != receipt_sha256:
        raise SystemExit('the ingestion receipt differs from the sha256 given')
    journal_prefetch = _journal_prefetch(receipt_path)
    phase('verify_ingestion_receipt')
    from research.kalshi.frankie_boss import dipole_classroom_external as EXT
    try:
        day_file, day_sha, day_source = EXT.resolve_day_file(day_external, day_external_sha256, receipt_path)
    except EXT.DayExternalRefused as error:
        if day_external is not None:
            raise SystemExit('the day file of the historical data points: %s' % error)
        day_file = None
        external = dict(status='absent', reason=str(error),
                        listed='no external section built here; the classroom V2 builds it when the day file is there')
    if day_file is not None:
        if _sha256(day_file) != day_sha:
            if day_external is not None:
                raise SystemExit('the day file %s differs from the sha256 %s given; refused' % (day_file, day_sha))
            external = dict(status='refused', path=str(day_file), sha256_expected=day_sha,
                            reason='the day file beside the ingest differs from its day-external-receipt.json sha256')
        else:
            external = dict(path=str(day_file), sha256=day_sha, found=day_source)
    rc = json.loads(receipt_path.read_bytes())
    if rc.get('schema') != 'BOSS_BLOCK_INGESTION_RECEIPT_V1' or rc.get('writer') != 'compact' or rc.get('trading_day') != day:
        raise SystemExit('a compact BOSS_BLOCK_INGESTION_RECEIPT_V1 of trading day %s is required' % day)
    # A journal written without the full-book observation (observation none) carries no operand for this equation;
    # the day is not refused: the step publishes an equation_not_run receipt below, after the retained-receipt checks.
    journal = receipt_path.parent / rc['journal_file']
    journal_stat = journal.stat()
    journal_prefetch.join()        # the overlapped measurement (same bytes, same sha256; a changed file is re-measured)
    journal_witness = dict(bytes=journal_stat.st_size, sha256=_box_module('frankie_box_filehash').witness(journal)['sha256'])
    if journal_witness != dict(bytes=rc['journal_bytes'], sha256=rc['journal_sha256']):
        raise SystemExit('the sealed journal differs from its ingestion receipt')
    phase('verify_sealed_journal')
    market = open_market = None
    if calculations is not None or shared_market_policy is not None:
        from frankie_box_market_timeline import SCHEMA, SharedMarketTimeline
        if calculations is None or shared_market_policy != SCHEMA:
            raise ValueError('shared teacher requires calculations and its exact versioned policy together')
        # The witness just measured is handed to the shared reader so the sealed journal (tens of GB on a big day)
        # is not hashed a second time in this process; the reader re-reads it itself if the witness differs.
        # bound to THE file measured (review N1): its path, device and inode travel with the bytes and sha256; the reader
        # accepts the measurement only for the very file its pin names, else hashes the file itself
        def open_market(**options):
            return SharedMarketTimeline(calculations, day=day, workers=workers, **options,
                                        input_witness=dict(journal_witness, path=str(journal), dev=journal_stat.st_dev,
                                                           ino=journal_stat.st_ino,
                                                           **(dict(basis='claim', claim=PREFETCH.get('claim'))
                                                              if PREFETCH.get('outcome') == 'by claim' else {})))
        market = open_market()
        phase('open_shared_picture')
        if (market.source['ingestion_receipt']['sha256'] != receipt_sha256
                or market.input_pin['sha256'] != rc['journal_sha256']):
            raise ValueError('teacher and shared picture have different sealed evidence')
        shared_external = market.source.get('external') or {}
        if ((shared_external.get('sha256') if shared_external.get('status') == 'attached' else None)
                != external.get('sha256')):
            raise ValueError('teacher and shared picture have different external publications')
    out = OUT / day
    if learner_binding is not None:
        # The learner owns a separate calculation and recovery namespace. It may reuse the
        # measurement functions, never the host's completed measurements or walk state.
        if learner_directory is None or Path(learner_directory).resolve() == out.resolve():
            raise ValueError('learner reading requires its own output directory')
        if (learner_binding['through_cursor'] != rc['record_count'] - 1 or
                learner_binding['source_hash'] != rc['source_prefix_hash']):
            raise ValueError('learner binding does not name this complete sealed day')
        out = Path(learner_directory)
    retained_receipt_path = out / 'receipt.json'
    retained_receipt = (json.loads(retained_receipt_path.read_bytes())
                        if retained_receipt_path.exists() else None)
    if retained_receipt is not None:
        if (retained_receipt.get('schema') != 'FRANKIE_EXPERIMENT_TEACHER_ROWS_V1' or
                retained_receipt.get('day') != day or
                retained_receipt.get('learner_binding') != learner_binding or
                not _identity_matches(retained_receipt.get('shared_market_identity'),
                                      market.identity if market else None, out, 'retained receipt shared_market_identity') or
                retained_receipt.get('ingestion_receipt', {}).get('sha256') != receipt_sha256):
            raise ValueError('retained teacher receipt belongs to another day or ingestion; preserved')
        old_external = retained_receipt.get('external_section', {})
        old_sha = old_external.get('sha256') or old_external.get('sha256_expected')
        current_sha = external.get('sha256') or external.get('sha256_expected')
        if old_sha is not None and old_sha != current_sha:
            raise ValueError('retained teacher external input identity changed; preserved')
    # A retained equation_not_run receipt (no rows file) is not a duplicate publication: the walk is attempted
    # again below; the same source gives the same explicit result, a repaired source may now carry the operand.
    if (out / ROWS_FILE).exists():
        status = (retained_receipt or {}).get('external_section', {}).get('status')
        retry_publication = retained_receipt is None or status in ('failed', 'refused')
        if not retry_publication:
            raise SystemExit('%s already holds the Dipole rows of %s (duplicate data declines)' % (out, day))
        if not ((out / 'teacher-raw-state.pkl').is_file() and
                (out / 'teacher-attachment-state.pkl').is_file()):
            raise ValueError('teacher publication is incomplete without its saved calculation state; preserved')
    out.mkdir(parents=True, exist_ok=True)
    phase('retained_receipt_checks')
    if rc.get('observation_mode') == 'none':
        # Greg, 2026-10-07: a missing operand blocks only the equation that needs it, never the day. The teacher
        # reads the full-book observation; this journal has none, so the Dipole rows are not computed and the day
        # goes on without them (the export and the search list them missing). Nothing is invented.
        reason = ('this journal was written without the full-book observation (observation none); the teacher reads the '
                  'observation, so its equation has no operand on this day; observation_replay would have to be wired '
                  'into the walk first (listed, not run)')
        result = dict(schema='FRANKIE_EXPERIMENT_TEACHER_ROWS_V1', day=day, status='equation_not_run',
                      equation_not_run=dict(reason=reason, operand='full-book observation', rows=0),
                      ingestion_receipt=dict(path=str(receipt_path), sha256=receipt_sha256), rows=0, processed=0,
                      entity_rows=0, through_cursor=rc['record_count'] - 1, model_calls=0, phase_timings=phases,
                      external_section=dict(external, listed='no external section built: the rows it aligns to were not computed'),
                      external_points=external_points_summary(None, status='not_built', reason='no external section built: the rows it aligns to were not computed'),
                      experiment_directive=directive_witness(),
                      shared_market_identity=market.identity if market is not None else None,
                      shared_market_read=None,
                      shared_market_use=('not read here: the walk that consumes the shared picture did not run; every other '
                                         'consumer opens the same ROOT with its own reader') if market is not None else None)
        if learner_binding is not None:
            result.update(learner_binding=learner_binding, evidence_seat='frankie', independent_scientific_verification=False)
        result['all99_coverage'] = all99_field(result, market.report if market is not None else None, day=day)
        result['workflow_report'] = workflow_report(result, receipt_path=receipt_path, rc=rc, external=external, market=market,
                                                    equation=None, workers=workers, exit_code=5)
        _publish(out, result)
        print(json.dumps(result, sort_keys=True), flush=True)
        return 5
    os.environ['FRANKIE_WALK_CACHE'] = str(out / 'walk-cache')       # never inside the sealed ingest directory
    os.environ.setdefault('FRANKIE_TEACHER_CHANGES', '1')

    from research.kalshi.frankie_boss import parallel_journal as PJ, context_session as CS, c15_teacher_r3 as T
    from research.kalshi.frankie_boss import parallel_teacher as PT, teacher_changes as TC, dipole_classroom as DC
    from research.kalshi.frankie_boss import sunday_execution as SE
    from research.kalshi.frankie_boss import teacher_second_set as SS
    from research.kalshi.frankie_boss.c15_normalizer_r3 import IdentityNormalizerR3
    from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
    from research.kalshi.frankie_boss.compact_journal import CompactReader
    from research.kalshi.frankie_boss.c15_journal import unpack

    # the day's own entity: the first INPUT record's (publisher, instrument)
    entity = None
    with CompactReader(journal, expected_count=rc['journal_count'], expected_head_hash=rc['journal_hash']) as first_reader:
        for ordinal, kind, body, digest in first_reader.rows():
            if kind == 'INPUT':
                record = unpack(json.loads(body))['payload']['record']
                entity = (int(record['publisher_id']), int(record['instrument_id']))
                break
    if entity is None:
        raise SystemExit('the journal holds no INPUT record')
    phase('first_input_entity')
    started = time.time()
    TC.install_binding()
    teacher = T.JournalTeacherR3({entity[1]: NG_TICK_RAW}, normalizer=IdentityNormalizerR3((entity[1],)))
    reader = FrankieCompactReader(journal, expected_count=rc['journal_count'], expected_head_hash=rc['journal_hash'],
                                  workers=workers)
    builder = SimpleNamespace(journal=reader, _failed=False, chain=SimpleNamespace(next_cursor=rc['record_count']))
    through = rc['record_count'] - 1
    bound = (learner_binding['as_of'] if learner_binding is not None else int(time.time() * 1e9))
    PJ._SERIAL = CS.journal_prefix
    PJ._ENTITY[0] = entity
    h0 = T.evidence_hash
    T.evidence_hash = PJ._chain_hash_factory(h0)
    TC.apply()
    evidence = None
    shared_read = None
    market_state = out / 'shared-market-state.pkl'
    saved_market_state = {}          # one pass (2026-10-09): the shared read saved in this process, kept in memory
    # One pass (2026-10-09, the exchange/Jev contract): the adviser cutoff context is kept from THIS walk, so the
    # exchange and Jev load it (<out>/AM.TEACHER_CONTEXT_NAME) instead of a third walk of the source. The tracker sees
    # every picture the walk consumes; it is saved beside the walk's state on every stop (cutoff-tracker.pkl, with the
    # next INPUT cursor) and continued only by a walk that resumes exactly there; a walk that begins later than the
    # first INPUT without that saved tracker writes no context.
    cutoff_walk = dict(tracker=None, first_input_cursor=None, next_input_cursor=None, continued=False, pictures=0)
    tracker_path = out / 'cutoff-tracker.pkl'
    AM = None
    # One pass (Greg, 2026-10-09, item 3): the classroom's whole-source work (all-99 arrivals, source status counts, the
    # six native entries' pass) made on THIS walk (frankie_box_classroom_code.TeacherPassCarry), saved beside the
    # receipt (classroom-carry.pkl); the classroom then reads the shared source only to its last anchor picture.
    carry = dict(value=None, first_input_cursor=None, error=None)
    # The second set (Greg, 2026-10-09: the teacher reads all of Frankie's 99 planes pinned together with the event flow
    # and builds a second set): every row the walk yields is joined, in the same step, to the picture it was read with
    # (teacher_second_set.join_record: the row key, the seven causal clocks and every plane row the picture placed or
    # carried, as references to the ROOT's receipted rows). The records travel with the walk's save position; rows a
    # resumed walk did not read itself (a save written before this) are joined at publication from the same reader.
    second = dict(records=[], read_in_walk=0, restored=0)
    second_set = second_records = second_header = None
    carry_path = out / CARRY_FILE
    # the sealed blocks (2026-10-09): the rows sidecar appended per block of the receive clock as the rows are made
    feed, block_setting = None, None
    if market is not None and learner_binding is None:
        try:
            feed, block_setting = _block_feed(out, day=day, market=market, teacher=teacher, rc=rc, SS=SS)
        except Exception as error:  # noqa: BLE001 - listed; the whole-day publication stands as before
            feed, block_setting = None, dict(outcome='failed', reason='%s: %s' % (type(error).__name__, error))
            print('TEACHER_BLOCKS not started: %s' % block_setting['reason'], flush=True)
    BLOCK_FEED[0] = feed
    SECOND_RECORDS[0] = second
    if market is not None:
        try:
            K = _box_module('frankie_box_classroom_code')
            carry['value'] = K.TeacherPassCarry(market, K.native_cutoff_limits(os.environ))
            _enable_anchors(carry, teacher)
        except Exception as error:  # noqa: BLE001 - the classroom then makes its own whole pass
            carry['error'] = 'not started: %s: %s' % (type(error).__name__, error)
    if market is not None:
        try:
            AM = _box_module('frankie_box_adviser_market')
            cutoff_walk['tracker'] = AM.CutoffTracker(rc['record_count'] - 1, rc['record_count'], strict=False)
        except Exception as error:  # noqa: BLE001 - the context is an addition; the walk never stops for it
            cutoff_walk['error'] = '%s: %s' % (type(error).__name__, error)
    # The pinned R3 equation's operands are the original APPLIED payloads with every adapter
    # cursor from zero (c15_teacher_r3.iter_raw). It runs on exactly that prefix. An instant
    # without its operand (failed, unpaired, unreadable, or past a cursor gap) is listed here
    # with its ordinal; it is not skipped silently, not given an invented row, and it never
    # removes the instant from the shared picture other consumers read.
    equation = dict(rows=0, through_applied_cursor=None, absent=[], ended_at=None,
                    rule='existing equation on its original contiguous operands only; no derived substitute')
    # CPU placement of the walk (Greg, 2026-10-07 night: every process/pool/thread pinned to its share of the lane,
    # physical cores first). The serial raw loop (this thread) goes on a whole core: lane[0], the CPU the journal
    # reader and the shared timeline's decode leave free (they take lane[1:]), plus its sibling threads, which the
    # raw-batch workers leave out (the pool's manager and feeder threads, started after the pin, land there). The
    # raw-batch spawn workers take every other CPU, one each, physical cores first (parallel_teacher.RAW_WORKER_CPUS).
    # The timeline sizes its decode pools from THIS thread's affinity when each stream starts, so the pin waits until
    # every stream generator has started and is undone when the walk's evidence ends, before finish sizes its pool.
    # Shared path only; the legacy no-policy walk is unchanged. Placement only: no row, hash or identity depends on it.
    LP = _box_module('frankie_box_lane_pin')
    PT.FINISH_POOL_RECORD.clear()
    PT.PROGRESS = _work_probe(out, rc)          # unit progress of the raw pass and the finish (report-only)
    PT.PROGRESS_ERRORS[0] = 0
    cpu_pinning = dict(schema='FRANKIE_TEACHER_CPU_PINNING_V1', outcome='not_pinned',
                       reason='legacy no-policy walk: placement unchanged' if market is None else None)
    if market is not None:
        lane = sorted(os.sched_getaffinity(0))          # this walk's own slice (teacher.sh taskset, or the classroom lane)
        consumer, siblings, topology_basis = LP.consumer_core(lane)
        raw_cpus = [c for c in LP.core_order(lane)[0] if c != consumer and c not in siblings]
        cpu_pinning.update(lane=lane, consumer=consumer, consumer_mask=sorted({consumer, *siblings}) if consumer is not None
                           else None, raw_worker_cpus=raw_cpus, topology=topology_basis, original_mask=LP.current_mask())
        if consumer is not None and raw_cpus:
            PT.RAW_WORKER_CPUS = tuple(raw_cpus)
            cpu_pinning.update(outcome='waiting', reason=None)
        else:
            cpu_pinning.update(reason='a lane of %d CPU(s) on one core: nothing to separate; placement unchanged' % len(lane))
    # The per-row canonical bytes of the shared path across the CPUs (parallel_teacher.EvidencePrecompute: the legacy
    # walk's fast path, the same values registered right before each payload is yielded; a row not registered is
    # computed the original way by the consumer). Its spawn workers take the raw-batch workers' CPUs, one each.
    precompute = dict(outcome='not_used', reason='legacy no-policy walk: its reader workers already compute these bytes'
                      if market is None else None)

    def shared_evidence():
        from collections import deque
        import pickle
        from research.kalshi.frankie_boss import c15_journal as J
        # One pass on a resume (2026-10-09, the seek protocol of parallel_teacher.RESUME_POSITION): a raw save carries
        # this walk's position (position() below: the shared read's position after the last picture it handed to this
        # walk, the pictures this walk had read ahead but not consumed, and this walk's own state: the equation, the
        # adapter cursor expected next, the present pictures counted, the cutoff tracker and the classroom carry, each
        # as of the last picture consumed). A resume whose saved position holds exactly the saved rows continues there:
        # nothing before it is read again, and the context and the carry are written after the resumed walk as after a
        # whole one. Anything else reads from the start and skips the saved rows (the earlier behaviour), listed.
        seek, seek_record = None, None
        saved = PT.RESUME_POSITION[0]
        if saved is not None:
            problem = None
            if not isinstance(saved, dict) or saved.get('schema') != WALK_POSITION_SCHEMA:
                problem = 'the saved reader position is not this walk\'s'
            elif (saved.get('teacher') or {}).get('rows') != PT.RESUME_SKIP[0]:
                problem = 'the saved position holds %r rows; the save holds %d' % (
                    (saved.get('teacher') or {}).get('rows'), PT.RESUME_SKIP[0])
            else:
                problem = market.seek_problem(saved['market'])
            if problem is None:
                seek = saved
            seek_record = dict(outcome='seeked' if seek is not None else 'read_from_start', reason=problem)
            PT.SAVE_RECORD['reader_seek'] = seek_record
        pictures = market.iter_applied(start=seek['market'] if seek is not None else None)
        expected = 0
        pre = None
        # The read-ahead (2026-10-09, a2/20231018): it was 2 batches per CPU of the plan (2 x 62 x 256 = 31,744 whole
        # pictures, each with its full-book APPLIED payload and its decoded layer rows, held in the parent and pickled
        # whole into every raw save). PT.EVIDENCE_AHEAD_BATCHES batches keep that many encodings in flight (refilled at
        # half), so the precompute pool is that many workers, on the plan's last CPUs (the raw-batch workers take it
        # from the front). Same pictures, same order, same registered bytes (the guard is unchanged).
        planned = raw_cpus if cpu_pinning['outcome'] == 'waiting' else None
        pre_workers = min(len(planned) if planned else PT._cpus(), PT.EVIDENCE_AHEAD_BATCHES)
        try:
            pre = PT.EvidencePrecompute(planned[-pre_workers:] if planned else None, PJ.CONTEXT_FIELDS,
                                        workers=pre_workers)
            precompute.update(outcome='used', workers=pre.workers)
        except Exception as error:  # noqa: BLE001 - speed only: without it every row is encoded here, as before
            precompute.update(outcome='not_used', reason='the pool could not start (%s: %s)' % (type(error).__name__, error))
        limit = min(2 * pre.workers, PT.EVIDENCE_AHEAD_BATCHES) * PT.EVIDENCE_BATCH if pre is not None else 1
        precompute.update(read_ahead_pictures=limit)
        ahead, batch, slots, done, last, failed = deque(), [], [], [False], [None], [None]
        whole = tuple(entity) if entity is not None else None
        # a resumed raw pass (parallel_teacher.RESUME_SKIP, set by row_pass before it starts this generator) skips the
        # rows its save already holds: without a seek their payloads are read again but not encoded; after a seek the
        # count continues from the saved position (restored below), so nothing past it is skipped
        present_seen = [0]

        def flush():
            if batch:
                handle = pre.submit(list(batch))
                for entry in slots:
                    entry[1] = handle
                batch.clear()
                slots.clear()

        def admit(item, counted=True):
            entry = [item, None, None]
            e = item['evidence']
            skip = False
            if counted and item['arithmetic']['status'] == 'present':
                present_seen[0] += 1
                skip = present_seen[0] <= PT.RESUME_SKIP[0]
                if skip:
                    precompute['resume_skipped_rows'] = present_seen[0]
            if pre is not None and not skip and item['arithmetic']['status'] == 'present' and type(e) is dict:
                m = e.get('normalized')
                entity_row = whole is None or (type(m) is dict and (m.get('publisher_id'), m.get('instrument_id')) == whole)
                entry[2] = len(batch)
                batch.append((e, entity_row))
                slots.append(entry)
                if len(batch) >= PT.EVIDENCE_BATCH:
                    flush()
            ahead.append(entry)

        def fill():
            # read ahead in source order (the timeline's own order; nothing is reordered or dropped) so the workers
            # encode upcoming payloads while the consumer runs the pinned loop
            while not done[0] and len(ahead) < limit:
                try:
                    item = next(pictures, None)
                except Exception as error:  # noqa: BLE001 - raised in order, after every earlier instant is consumed
                    failed[0], done[0] = error, True
                    break
                if item is None:
                    done[0] = True
                    break
                admit(item)
            if done[0] and pre is not None:
                flush()

        def position():
            """This walk's position after the last picture it consumed (parallel_teacher.RESUME_POSITION_SOURCE): the
            shared read after the last picture it handed here, the pictures read ahead but not consumed (yielded again
            first on a resume), and the walk's own state. The tracker and the carry are pickled here (each restored or
            listed on its own on a resume); the rest is pickled by the save that asks for it, before the walk goes on."""
            def packed(value):
                return None if value is None else pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
            return dict(schema=WALK_POSITION_SCHEMA, market=market.position(), ahead=[entry[0] for entry in ahead],
                        teacher=dict(rows=equation['rows'], expected=expected, present_seen=present_seen[0],
                                     equation=equation,
                                     cutoff_walk=dict({k: v for k, v in cutoff_walk.items() if k != 'tracker'},
                                                      tracker=packed(cutoff_walk['tracker'])),
                                     carry=dict(value=packed(carry['value']), first_input_cursor=carry['first_input_cursor'],
                                                error=carry['error']),
                                     second_set=dict(format=SS.FORMAT, records=second['records'])))
        PT.RESUME_POSITION_SOURCE[0] = position

        def register(entry):
            # the previous payload has been hashed by now (the pinned loop hashes a row before asking for the next);
            # anything of it left (a resume's skipped prefix) is dropped, never kept alive
            if last[0] is not None:
                PJ._CANONICAL.pop(last[0][0], None)
                if last[0][1] is not None:
                    PJ._SUBSETS.pop(last[0][1], None)
                last[0] = None
            PT.ROW_BYTES.clear()
            if entry[2] is None:
                return
            if entry[1] is None:
                flush()
            values = pre.values(entry[1])
            e = entry[0]['evidence']
            payload = pre.payload(entry[1], entry[2])
            if payload is not None:
                # the payload's one pickle, handed on to the raw streams (parallel_teacher.ROW_BYTES): its rows reach
                # the raw-batch workers whole without the payload being pickled again
                PT.ROW_BYTES[id(e)] = (e, payload)
            if values is None:
                return
            body, subset = values[entry[2]]
            if entry[2] == 0:
                # guard: the first row of every batch is encoded the original way here and must be equal
                PT.PRECOMPUTE_RECORD['guard_checked'] += 1
                if body != J.canonical_bytes(J.pack(e)) or (
                        subset is not None and subset != h0({k: e[k] for k in PJ.CONTEXT_FIELDS})):
                    raise ValueError('parallel teacher evidence bytes differ from the original encoding; run stopped')
            PJ._CANONICAL[id(e)] = (e, body)
            key = None
            if subset is not None:
                key = ('teacher', e['cursor'])
                PJ._SUBSETS[key] = (subset, id(e['raw_record']))
            last[0] = (id(e), key)
        try:
            if seek is not None:
                # this walk's state as of the last picture consumed before the save; the pictures read ahead then come first
                mine = seek['teacher']
                expected, present_seen[0] = mine['expected'], mine['present_seen']
                equation.clear()
                equation.update(mine['equation'])
                walked = dict(mine['cutoff_walk'])
                try:
                    walked['tracker'] = pickle.loads(walked['tracker']) if walked['tracker'] is not None else None
                except Exception as error:  # noqa: BLE001 - no tracker: no context from this walk (listed)
                    walked.update(tracker=None, error='the saved cutoff tracker could not be restored (%s: %s)'
                                                      % (type(error).__name__, error))
                cutoff_walk.clear()
                cutoff_walk.update(walked, continued=True)
                kept = mine['carry']
                try:
                    value = pickle.loads(kept['value']) if kept['value'] is not None else None
                    carry.update(value=value, first_input_cursor=kept['first_input_cursor'], error=kept['error'])
                    _restored_anchors(carry)
                except Exception as error:  # noqa: BLE001 - no carry: the classroom makes its own whole pass (listed)
                    carry.update(value=None, first_input_cursor=kept['first_input_cursor'],
                                 error='the saved classroom carry could not be restored (%s: %s)' % (type(error).__name__, error))
                for item in seek['ahead']:
                    admit(item, counted=False)
                seek_record.update(pictures=seek['market'].get('pictures'), ahead=len(seek['ahead']), rows=mine['rows'],
                                   market_exhausted=bool(seek['market'].get('exhausted')))
                PT.RESUME_SEEKED[0] = mine['rows']
                kept = mine.get('second_set')
                if isinstance(kept, dict) and len(kept.get('records') or ()) == mine['rows']:
                    second['records'] = list(kept['records'])
                    second['restored'] = len(second['records'])
                # else (a save written before the second set): the rows before the seek are joined at publication
            while True:
                if len(ahead) * 2 <= limit:
                    fill()
                if not ahead:
                    if failed[0] is not None:
                        raise failed[0]
                    break
                entry = ahead.popleft()
                item = entry[0]
                if cutoff_walk['tracker'] is not None:
                    at_input = item['picture']['at'].get('input_cursor')
                    if cutoff_walk['first_input_cursor'] is None:
                        cutoff_walk['first_input_cursor'] = at_input
                        if type(at_input) is int and at_input > 0:
                            # a walk resumed past the source start: continue the tracker saved at exactly this cursor
                            try:
                                saved = PT._load_raw_state(tracker_path) if tracker_path.is_file() else None
                            except Exception:  # noqa: BLE001 - no usable tracker: no context is written
                                saved = None
                            if saved and saved.get('next_input_cursor') == at_input:
                                cutoff_walk.update(tracker=saved['tracker'], continued=True)
                            else:
                                cutoff_walk.update(tracker=None, error='the walk began at INPUT cursor %s with no tracker '
                                                   'saved there: no context from this walk' % at_input)
                    if cutoff_walk['tracker'] is not None:
                        cutoff_walk['tracker'].see(item['picture'])        # the return value is ignored by contract
                        cutoff_walk['pictures'] += 1
                        if type(at_input) is int:
                            cutoff_walk['next_input_cursor'] = at_input + 1
                if cpu_pinning['outcome'] == 'waiting':
                    started_streams = LP.generators_started(getattr(market, 'streams', None) or ())
                    if started_streams is None:
                        cpu_pinning.update(outcome='not_pinned', reason='cannot tell whether the reader sized its pools')
                    elif started_streams:
                        cpu_pinning.update(LP.pin_core(cpu_pinning['consumer_mask']), at_instant=equation['rows'] + len(
                            equation['absent']) + 1)
                at = item['picture']['at']
                if carry['value'] is not None:
                    if carry['first_input_cursor'] is None:
                        carry['first_input_cursor'] = at.get('input_cursor')
                        if type(at.get('input_cursor')) is int and at['input_cursor'] > 0:
                            carry.update(value=None, error='the walk began at INPUT cursor %s, not the source start'
                                                           % at['input_cursor'])
                if carry['value'] is not None:
                    # the classroom's Dipole roster: the entity's rows of this walk's contiguous equation prefix
                    # (row_pass hashes exactly those; PT.finish selects them as the context cursors)
                    row_cursor = None
                    if (item['arithmetic']['status'] == 'present' and equation['ended_at'] is None
                            and item['evidence'].get('cursor') == expected):
                        m = item['evidence'].get('normalized') or {}
                        if whole is None or (m.get('publisher_id'), m.get('instrument_id')) == whole:
                            row_cursor = item['evidence']['cursor']
                    carry['value'].note(item, row_cursor)
                if item['arithmetic']['status'] != 'present':
                    equation['absent'].append(dict(input_journal_ordinal=at['input_journal_ordinal'],
                                                   adapter_cursor=at['adapter_cursor'], input_cursor=at['input_cursor'],
                                                   reason=item['arithmetic']['reason']))
                    continue
                if equation['ended_at'] is not None:
                    equation['absent'].append(dict(input_journal_ordinal=at['input_journal_ordinal'],
                                                   adapter_cursor=at['adapter_cursor'], input_cursor=at['input_cursor'],
                                                   reason='after_equation_prefix_end'))
                    continue
                if item['evidence'].get('cursor') != expected:
                    # The pinned equation would refuse here ('complete prefix requires every cursor
                    # from zero'). Its prefix ends; the reader keeps presenting every later instant.
                    equation['ended_at'] = dict(input_journal_ordinal=at['input_journal_ordinal'],
                                                adapter_cursor=at['adapter_cursor'], expected_adapter_cursor=expected,
                                                reason='adapter cursor gap before this APPLIED; the equation needs every cursor from zero')
                    equation['absent'].append(dict(input_journal_ordinal=at['input_journal_ordinal'],
                                                   adapter_cursor=at['adapter_cursor'], input_cursor=at['input_cursor'],
                                                   reason='after_equation_prefix_end'))
                    continue
                expected += 1
                equation['rows'] += 1
                equation['through_applied_cursor'] = item['evidence']['cursor']
                # Both existing equations see the identical richer current input.
                # Their raw argument/hash and numerical formulas remain unchanged.
                teacher.market_picture = item['picture']
                teacher.control.market_picture = item['picture']
                teacher.raw_teacher.market_picture = item['picture']
                register(entry)
                second['records'].append(SS.join_record(item['evidence'], item['picture']))
                second['read_in_walk'] += 1
                yield item['evidence']
        finally:
            try:
                if pre is not None:
                    pre.close()
                    precompute.update(record=dict(PT.PRECOMPUTE_RECORD))
                ahead.clear()
                pictures.close()
                state = dict(market.report, equation=dict(equation))
                PT._save_raw_state(market_state, state)
                saved_market_state['value'] = state
                if carry['value'] is not None and market.report.get('complete'):
                    if PT.ROW_DONE[0] is not None:
                        # the anchors are fed as rows resolve; the last rows resolve after the evidence ends: the carry
                        # is saved by the caller once the row pass has fed every row
                        carry['save_after_rows'] = market.identity
                    else:
                        try:
                            PT._save_raw_state(carry_path, carry['value'].state(market.identity))
                            carry['saved'] = True
                        except Exception as error:  # noqa: BLE001 - the classroom then makes its own whole pass
                            carry['error'] = 'not saved: %s: %s' % (type(error).__name__, error)
                if cutoff_walk['tracker'] is not None and cutoff_walk['next_input_cursor'] is not None:
                    try:          # the tracker with the walk's save point (plain picklable data)
                        PT._save_raw_state(tracker_path, dict(tracker=cutoff_walk['tracker'],
                                                              next_input_cursor=cutoff_walk['next_input_cursor']))
                    except Exception as error:  # noqa: BLE001 - listed; the walk's own save stands
                        cutoff_walk['save_error'] = '%s: %s' % (type(error).__name__, error)
            finally:
                PT.RESUME_POSITION_SOURCE[0] = None
                PT.ROW_BYTES.clear()
                if cpu_pinning['outcome'] in ('pinned', 'fallback') and 'restored' not in cpu_pinning:
                    cpu_pinning['restored'] = LP.restore_mask(cpu_pinning['original_mask'])
    collector = _WalkCollector()
    anchors = (_anchor_feed(carry, teacher, T) if market is not None and carry['value'] is not None
               and getattr(carry['value'], 'anchor_on', False) else None)
    PT.ROW_DONE[0] = _row_done(anchors, feed)
    try:
        if market is not None:
            cpu_pinning['collector'] = collector.enter()
        evidence = shared_evidence() if market else PJ.parallel_journal_prefix(builder, through, None)
        rows, processed, hashes = PT.row_pass(teacher, evidence, as_of=bound, source_manifest_hash=rc['manifest_hash'],
            recovery_path=out / 'teacher-raw-state.pkl',
            recovery_identity=dict(receipt_sha256=receipt_sha256, journal_sha256=rc['journal_sha256'],
                                   journal_count=rc['journal_count'], journal_hash=rc['journal_hash'], through=through,
                                   **({'learner_binding': learner_binding} if learner_binding is not None else {}),
                                   **({'shared_market_identity': market.identity} if market is not None else {})),
            save_requested=save_requested, retain_dstate=True)
        if carry.get('save_after_rows') is not None and carry['value'] is not None:
            try:                 # every row fed (the row pass drained its streams): the carry with its anchors
                PT._save_raw_state(carry_path, carry['value'].state(carry.pop('save_after_rows')))
                carry['saved'] = True
            except Exception as error:  # noqa: BLE001 - the classroom then makes its own whole pass
                carry['error'] = 'not saved: %s: %s' % (type(error).__name__, error)
        if cpu_pinning['outcome'] in ('pinned', 'fallback') and 'restored' not in cpu_pinning:
            cpu_pinning['restored'] = LP.restore_mask(cpu_pinning['original_mask'])     # before finish sizes its pool
        if market is not None:
            # A completed raw recovery may reuse its saved read. Never describe an
            # unstarted current iterator as a fresh complete evidence delivery.
            # one pass (2026-10-09): the read this process just saved is the dict in memory (the file holds its
            # pickle); only a resume that did not walk loads the saved file (hash-checked, once)
            shared_read = (saved_market_state['value'] if 'value' in saved_market_state else
                           PT._load_raw_state(market_state) if market_state.exists() else None)
            if not shared_read or not shared_read.get('complete') or not _identity_matches(
                    shared_read.get('identity'), market.identity, out, 'saved shared read identity'):
                raise ValueError('completed teacher raw state lacks its matching complete shared read; preserved')
        if save_requested():
            raise PT.TeacherSaved('teacher raw pass saved; attachment assembly has not started')
        if market is not None and rows:
            # the merge runs under the walk's collector settings (frozen heap, rare full collections): restored after it
            if feed is not None:
                feed.entity = hashes
            second_set, second_records, second_header = _second_set(out, open_market, market, second, rows, SS,
                                                                    feed=feed)
            phase('second_set')
        collector.exit()
        walked = time.time() - started
        phase('raw_pass_rows')
        if not rows:
            # No original APPLIED operand reached the equation on the whole day (every INPUT failed, unpaired or
            # unreadable, or the adapter-cursor prefix ended at zero). The pinned PT.finish requires a nonempty
            # complete prefix; that is the equation's refusal, not the day's. The shared read, with every instant
            # listed, is retained in shared-market-state.pkl; the receipt below says so and the day goes on.
            equation_not_run = dict(reason='no original APPLIED operand on the whole day; the pinned equation (PT.finish) '
                                           'requires a nonempty complete prefix, so no Dipole row is computed or invented',
                                    operand='original APPLIED payload (contiguous adapter-cursor prefix)', rows=0,
                                    processed=processed)
        else:
            equation_not_run = None
            as_of = max(r[4] for r in rows)
            if learner_binding is not None and as_of != bound:
                raise ValueError('learner reading does not end at its requested whole-day cutoff')
            spec = [(cursor, True, h) for cursor, h in sorted(hashes.items())]
            if market is not None and len(cpu_pinning.get('lane') or ()) > 1:
                # the attachment pool on every CPU of the lane but the coordinator's (it joins the chunks in order
                # while they run): one spawn worker per CPU, physical cores first, the coordinator's sibling last
                coordinator, finish_cpus, finish_basis = LP.placement(len(cpu_pinning['lane']) - 1, cpu_pinning['lane'])
                PT.FINISH_WORKER_CPUS = tuple(finish_cpus)
                cpu_pinning['finish_plan'] = dict(coordinator=coordinator, worker_cpus=list(finish_cpus), basis=finish_basis)
            attachment = PT.finish(teacher, rows, processed, hashes, spec, source_manifest_hash=rc['manifest_hash'],
                                   recovery_path=out / 'teacher-attachment-state.pkl',
                                   save_requested=save_requested)
            phase('finish_attachment')
    finally:
        try:
            # Closing a paused walk drains already submitted block workers and their
            # existing durable caches before the journal reader/process is released.
            if evidence is not None:
                evidence.close()
        finally:
            PT.RAW_WORKER_CPUS = None
            PT.FINISH_WORKER_CPUS = None
            PT.PROGRESS = None
            PT.ROW_DONE[0] = None
            PT.ROW_PASS_LIVE[0] = None
            carry['anchor_feed'] = dict(PT.ROW_DONE_RECORD, **(carry.get('anchor_feed') or {}))
            raw_saves = dict(PT.SAVE_RECORD, progress_errors=PT.PROGRESS_ERRORS[0])
            cpu_pinning['finish_pool'] = dict(PT.FINISH_POOL_RECORD) if PT.FINISH_POOL_RECORD else None
            cpu_pinning['evidence_precompute'] = dict(precompute)
            if cpu_pinning['outcome'] in ('pinned', 'fallback') and 'restored' not in cpu_pinning:
                cpu_pinning['restored'] = LP.restore_mask(cpu_pinning['original_mask'])
            cpu_pinning['raw_pool'] = dict(PT.RAW_POOL_RECORD)
            if cpu_pinning.get('original_mask') is not None:
                cpu_pinning['original_mask'] = sorted(cpu_pinning['original_mask'])
            if cpu_pinning['outcome'] == 'waiting':
                cpu_pinning.update(outcome='not_pinned', reason='the reader streams never all started in this walk')
            collector.exit()
            TC.restore()
            T.evidence_hash = h0
            PJ._ENTITY[0] = None
            PJ._CANONICAL.clear()
            PJ._SUBSETS.clear()
            reader.close()
            phase('close_walk')
    if equation_not_run is not None:
        result = dict(schema='FRANKIE_EXPERIMENT_TEACHER_ROWS_V1', day=day, status='equation_not_run',
                      equation_not_run=equation_not_run, entity=list(entity),
                      ingestion_receipt=dict(path=str(receipt_path), sha256=receipt_sha256), rows=0, processed=processed,
                      entity_rows=0, through_cursor=through, walk_seconds=round(walked, 1),
                      seconds=round(time.time() - started, 1), model_calls=0, experiment_directive=directive_witness(),
                      phase_timings=phases,
                      external_section=dict(external, listed='no external section built: the rows it aligns to were not computed'),
                      external_points=external_points_summary(None, status='not_built', reason='no external section built: the rows it aligns to were not computed'),
                      cpu_pinning=cpu_pinning, raw_saves=raw_saves, journal_prefetch=dict(PREFETCH),
                      run_defaults=dict(RUN_DEFAULTS), identity_rebinds=list(IDENTITY_REBINDS))
        if market is not None:
            result.update(shared_market_identity=market.identity, shared_market_read=shared_read,
                          shared_market_arithmetic=shared_read.get('equation'),
                          shared_market_use='full picture read and every instant listed (shared_market_arithmetic); the '
                                            'existing equation had no operand, so no row was computed or invented')
        if learner_binding is not None:
            result.update(learner_binding=learner_binding, evidence_seat='frankie', independent_scientific_verification=False)
        result['all99_coverage'] = all99_field(result, shared_read, day=day)
        result['workflow_report'] = workflow_report(result, receipt_path=receipt_path, rc=rc, external=external, market=market,
                                                    equation=(shared_read or {}).get('equation') if market is not None else None,
                                                    workers=workers, exit_code=5)
        _publish(out, result)
        if feed is not None and feed.mode != 'failed':
            feed.sealer.finish('equation_not_run', complete=True, reason=equation_not_run['reason'])
        print(json.dumps(result, sort_keys=True), flush=True)
        return 5
    request_id = 'experiment-%s-cycle-00' % day
    attachment_path = out / 'teacher-attachment.pkl'
    body = dict(attachment=attachment, request_id=request_id, source_hash=rc['source_prefix_hash'], as_of=as_of,
                through_cursor=through, entity=entity)
    # Endings pass (2026-10-08; Greg: CPUs in every step of the ending): the attachment pickle (pure Python, GIL-bound)
    # is written by a forked side process pinned to one lane CPU while this process builds the snapshot (DC.snapshot_
    # teacher_attachment reads the attachment and builds new rows; it never mutates it) and writes the rows file; the
    # child hashes the bytes as it writes them (the same _HashingWriter, the same pickle of the same objects at the same
    # addresses: the same bytes) and leaves the digest in a sidecar. Taken only when this process runs one thread (a fork
    # beside a live thread can inherit a held lock); a child that could not start, died or left no digest is redone
    # here, in order, exactly as before. Recorded on cpu_pinning.attachment_writer.
    attachment_writer = _start_attachment_writer(attachment_path, body, cpu_pinning.get('lane'))
    source = DC.snapshot_teacher_attachment(attachment, request_id=request_id, cycle_index=0, cycle_count=1,
                                            source_hash=rc['source_prefix_hash'], as_of=as_of, through_cursor=through)
    # The publication tail (stacks pass): the attachment is hashed as it is written (the same bytes pickle hands to the
    # file; no read-back pass), the rows file is hashed on a thread while the external section is built, and a retained
    # attachment is hashed on a thread too. hashlib releases the GIL on these buffers; the values are the files' sha256.
    attachment_sha = [None]
    hashers = {}

    def hash_on_thread(name, path):
        import threading
        box = dict(sha256=None, error=None)

        def run():
            try:
                box['sha256'] = _sha256(path)
            except BaseException as error:  # noqa: BLE001 - raised at the join, in the original order
                box['error'] = error
        thread = threading.Thread(target=run, name='teacher-%s-sha256' % name, daemon=True)
        thread.start()
        hashers[name] = (thread, box)

    def hashed(name):
        thread, box = hashers.pop(name)
        thread.join()
        if box['error'] is not None:
            raise box['error']
        return box['sha256']
    retained_claim = _attachment_claim(out, attachment_path, body) if attachment_path.exists() else None
    if retained_claim is not None:
        # one pass (2026-10-09): this code wrote the attachment and its FRANKIE_FILE_CLAIM_V2 row with the same body
        # identity; stat, filesystem and last 64 KiB unchanged: not unpickled, re-snapshotted or hashed again
        attachment_sha[0] = retained_claim['sha256']
        SE._save(out / ROWS_FILE, source)
    elif attachment_path.exists():
        with attachment_path.open('rb') as f:
            retained = pickle.load(f)
        if any(retained[key] != body[key] for key in body if key != 'attachment') or \
                DC.snapshot_teacher_attachment(retained['attachment'], request_id=request_id, cycle_index=0,
                    cycle_count=1, source_hash=rc['source_prefix_hash'], as_of=as_of, through_cursor=through) != source:
            raise ValueError('retained teacher attachment differs; publication preserved for recovery')
        hash_on_thread('attachment', attachment_path)
        SE._save(out / ROWS_FILE, source)
    else:
        SE._save(out / ROWS_FILE, source)               # beside the side process writing the attachment
        attachment_sha[0] = _finish_attachment_writer(attachment_writer, attachment_path, body)
    teacher_context = _keep_cutoff_context(AM, market, cutoff_walk, out, day=day, rc=rc, as_of=as_of, through=through,
                                           exhausted=bool(shared_read and shared_read.get('complete')))
    cpu_pinning['attachment_writer'] = attachment_writer['record'] if attachment_writer else dict(
        outcome='not_started', reason=('a retained attachment stands (resume); its claim row holds, not read again'
                                       if retained_claim is not None else
                                       'a retained attachment stands (resume); it is hashed on a thread instead'))
    hash_on_thread('rows', out / ROWS_FILE)
    if second_records is not None and feed is not None and feed.mode != 'failed':
        rows_sidecar = feed.verify(source, second_records)      # the sealed blocks are the sidecar (each block checked)
    else:
        rows_sidecar = (_write_rows_sidecar(out, source, second_records, second_header, SS)
                        if second_records is not None else None)
    phase('snapshot_rows_attachment')
    result = dict(schema='FRANKIE_EXPERIMENT_TEACHER_ROWS_V1', day=day, request_id=request_id, entity=list(entity),
                  ingestion_receipt=dict(path=str(receipt_path), sha256=receipt_sha256), rows=len(rows), processed=processed,
                  entity_rows=len(hashes), as_of=as_of, through_cursor=through, walk_seconds=round(walked, 1),
                  seconds=round(time.time() - started, 1), rows_file=dict(file=ROWS_FILE, sha256=None),
                  attachment_file=dict(file='teacher-attachment.pkl', sha256=attachment_sha[0]),
                  model_calls=0, caveat='whole-day context: the exact-row check in finish compares the rows with themselves',
                  experiment_directive=directive_witness(), phase_timings=phases, cpu_pinning=cpu_pinning,
                  raw_saves=raw_saves, journal_prefetch=dict(PREFETCH), run_defaults=dict(RUN_DEFAULTS),
                  identity_rebinds=list(IDENTITY_REBINDS))
    if teacher_context is not None:
        result['shared_market_context'] = teacher_context
    # the second set (teacher_second_set FORMAT): every row joined to its picture of the 99 planes on the same clocks
    result['teacher_second_set'] = second_set if second_set is not None else dict(
        status='not_built', format=None,
        reason='no shared market reader on this ROOT (the legacy journal walk): no picture to join the rows to')
    result['rows_sidecar'] = rows_sidecar or dict(status='not_written', reason='no second set on this day')
    result['blocks'] = (dict(status='sealed', setting=block_setting, mode=feed.mode, error=feed.error,
                             pin=(rows_sidecar or {}).get('blocks'))
                        if feed is not None and feed.mode != 'failed' else
                        dict(status='failed' if feed is not None else 'off', setting=block_setting,
                             error=feed.error if feed is not None else None,
                             rule='the whole-day sidecar written at publication'))
    result['account'] = _teacher_account(rows, second_records, second_header, raw_saves=raw_saves,
                                         cpu_pinning=cpu_pinning, phases=phases, walked=walked, processed=processed,
                                         out=out)
    if market is not None:
        # the classroom loads the file and checks its identity and roster itself; a missing or other carry makes the
        # classroom's own whole pass, so an older teacher (no field) never blocks it
        result['classroom_carry'] = (
            dict(file=CARRY_FILE, status='written', schema='FRANKIE_CLASSROOM_TEACHER_CARRY_V1') if carry.get('saved') else
            dict(file=CARRY_FILE, status='retained', reason='a completed saved walk was reused; the carry its walk saved')
            if carry_path.is_file() and not walked_now(carry) else
            dict(file=CARRY_FILE, status='not_written', reason=carry.get('error') or 'the walk did not reach the source end'))
        result['classroom_carry']['anchors'] = _anchor_record(carry, source)
    if market is not None:
        result.update(shared_market_identity=market.identity, shared_market_read=shared_read,
                      shared_market_arithmetic=shared_read.get('equation'),
                      shared_market_use='full current picture exposed to both raw teachers at every computed row; existing '
                                        'equations use original APPLIED fields on their contiguous prefix; instants without '
                                        'that operand are listed in shared_market_arithmetic, never invented or dropped '
                                        'from the shared picture; shared_market_read.complete means source exhaustion only')
    if learner_binding is not None:
        result.update(learner_binding=learner_binding, evidence_seat='frankie',
                      independent_scientific_verification=False)
    code = 4 if external.get('status') == 'refused' else 0
    external_key = None
    if learner_binding is None and external.get('status') not in ('absent', 'refused'):
        try:
            key, section = EXT.ensure_external_section(out, source, external['path'], external['sha256'], trading_day=day,
                                                       built_by='teacher-only step')
            external.update(status='built' if not section['reused'] else 'reused', section=section)
            external_key = key
        except Exception as error:                 # listed; the rows stand; the classroom V2 refuses with the same error
            external.update(status='failed', error='%s: %s' % (type(error).__name__, error))
            code = 4
        phase('external_section')
    result['rows_file']['sha256'] = hashed('rows')
    if 'attachment' in hashers:
        result['attachment_file']['sha256'] = hashed('attachment')
    # one pass (Greg, 2026-10-09): FRANKIE_FILE_CLAIM_V2 rows for the rows file and the attachment in this directory
    # (out/file-claims.jsonl), so the data export and the brain take them instead of hashing them again, and a
    # resume takes the attachment's (with its body identity) instead of unpickling it
    result['file_claims'] = _write_teacher_claims(out, [(out / ROWS_FILE, result['rows_file']['sha256'], None),
                                                        (attachment_path, result['attachment_file']['sha256'],
                                                         _body_identity(body))])
    phase('hash_publications')
    result['external_section'] = external
    # the per-point summary of the 13 points (the day reports' 99-layer join reads it): from the key above only
    result['external_points'] = (external_points_summary(external_key) if external_key is not None else
                                 external_points_summary(None, status='not_built', reason=(
                                     'the external section is %s%s' % (external.get('status'),
                                                                     (': ' + str(external.get('reason') or external.get('error')))
                                                                     if (external.get('reason') or external.get('error')) else '')
                                     if learner_binding is None else
                                     'a learner-bound teacher step builds no external section (the classroom builds it)')))
    result['status'] = 'rows_published'
    result['all99_coverage'] = all99_field(result, shared_read, day=day)
    result['workflow_report'] = workflow_report(result, receipt_path=receipt_path, rc=rc, external=external, market=market,
                                                equation=(shared_read or {}).get('equation') if market is not None else None,
                                                workers=workers, exit_code=code)
    _publish(out, result)
    if feed is not None and feed.mode != 'failed':
        feed.complete(out / 'receipt.json', result)
    print(json.dumps(result, sort_keys=True), flush=True)
    return code


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--day', required=True)
    p.add_argument('--ingestion-receipt', required=True)
    p.add_argument('--ingestion-receipt-sha256', required=True)
    p.add_argument('--workers', type=int, default=None,
                   help='reader workers (default: the lane minus one, from FRANKIE_LANE_CPUS / the booking / affinity)')
    p.add_argument('--day-external', help='the day file (FRANKIE_DAY_EXTERNAL_V1); default: beside the sealed ingest')
    p.add_argument('--day-external-sha256', help='its sha256 (given together with --day-external; a mismatch is refused)')
    p.add_argument('--calculations', help='owner-local ROOT of the same sealed source')
    p.add_argument('--shared-market-policy', choices=['FRANKIE_SHARED_MARKET_TIMELINE_V1'])
    a = p.parse_args()
    if (a.day_external is None) != (a.day_external_sha256 is None):
        p.error('--day-external and --day-external-sha256 are given together')
    RUN_DEFAULTS.clear()
    # One BLAS/OpenMP thread per process (the spawn workers are pinned one per CPU; torch only builds tensors here, no
    # reduction, so the cap cannot change a value). Set before anything imports torch/numpy; an operator value stands.
    for name in THREAD_CAPS:
        if os.environ.get(name) is None:
            os.environ[name] = '1'
            RUN_DEFAULTS[name] = '1 (default taken)'
    if a.workers is None:
        lane = _box_module('frankie_box_lane_pin').lane_cpus()
        a.workers = max(1, len(lane) - 1)
        RUN_DEFAULTS['workers'] = '%d (default taken: lane of %d CPU(s) minus the consumer)' % (a.workers, len(lane))
    if os.environ.get('FRANKIE_TEACHER_CHANGES') is None:
        RUN_DEFAULTS['FRANKIE_TEACHER_CHANGES'] = '1 (default taken)'
    return teach(a.day, a.ingestion_receipt, a.ingestion_receipt_sha256, a.workers, a.day_external, a.day_external_sha256,
                 calculations=a.calculations, shared_market_policy=a.shared_market_policy)


if __name__ == '__main__':
    sys.exit(main())
