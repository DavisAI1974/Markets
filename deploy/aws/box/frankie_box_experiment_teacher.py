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
            _box_module('frankie_box_filehash').witness(Path(receipt_path).parent / rc['journal_file'])
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


def teach(day, receipt_path, receipt_sha256, workers, day_external=None, day_external_sha256=None,
          *, calculations=None, shared_market_policy=None):
    # Keep the cooperative handler through publication too: an orderly stop must not
    # leave a completed attachment without its rows/external section/completion receipt.
    import signal
    requested = [False]
    def request_save(*_):
        requested[0] = True
    def save_requested():
        stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')
        return requested[0] or bool(stop_file and Path(stop_file).exists())
    previous_signal = signal.signal(signal.SIGTERM, request_save)
    try:
        return _teach(day, receipt_path, receipt_sha256, workers, day_external,
                      day_external_sha256, save_requested=save_requested, calculations=calculations,
                      shared_market_policy=shared_market_policy)
    finally:
        signal.signal(signal.SIGTERM, previous_signal)


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
    market = None
    if calculations is not None or shared_market_policy is not None:
        from frankie_box_market_timeline import SCHEMA, SharedMarketTimeline
        if calculations is None or shared_market_policy != SCHEMA:
            raise ValueError('shared teacher requires calculations and its exact versioned policy together')
        # The witness just measured is handed to the shared reader so the sealed journal (tens of GB on a big day)
        # is not hashed a second time in this process; the reader re-reads it itself if the witness differs.
        # bound to THE file measured (review N1): its path, device and inode travel with the bytes and sha256; the reader
        # accepts the measurement only for the very file its pin names, else hashes the file itself
        market = SharedMarketTimeline(calculations, day=day, workers=workers,
                                      input_witness=dict(journal_witness, path=str(journal), dev=journal_stat.st_dev,
                                                         ino=journal_stat.st_ino))
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
        from research.kalshi.frankie_boss import c15_journal as J
        pictures = market.iter_applied()
        expected = 0
        pre = None
        try:
            pre = PT.EvidencePrecompute(raw_cpus if cpu_pinning['outcome'] == 'waiting' else None, PJ.CONTEXT_FIELDS)
            precompute.update(outcome='used', workers=pre.workers)
        except Exception as error:  # noqa: BLE001 - speed only: without it every row is encoded here, as before
            precompute.update(outcome='not_used', reason='the pool could not start (%s: %s)' % (type(error).__name__, error))
        limit = 2 * pre.workers * PT.EVIDENCE_BATCH if pre is not None else 1
        ahead, batch, slots, done, last, failed = deque(), [], [], [False], [None], [None]
        whole = tuple(entity) if entity is not None else None
        # a resumed raw pass (parallel_teacher.RESUME_SKIP, set by row_pass before it starts this generator) skips the
        # rows its save already holds: their payloads are read (the reader has no start-at-cursor) but not encoded
        present_seen = [0]

        def flush():
            if batch:
                handle = pre.submit(list(batch))
                for entry in slots:
                    entry[1] = handle
                batch.clear()
                slots.clear()

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
                entry = [item, None, None]
                e = item['evidence']
                skip = False
                if item['arithmetic']['status'] == 'present':
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
            if done[0] and pre is not None:
                flush()

        def register(entry):
            # the previous payload has been hashed by now (the pinned loop hashes a row before asking for the next);
            # anything of it left (a resume's skipped prefix) is dropped, never kept alive
            if last[0] is not None:
                PJ._CANONICAL.pop(last[0][0], None)
                if last[0][1] is not None:
                    PJ._SUBSETS.pop(last[0][1], None)
                last[0] = None
            if entry[2] is None:
                return
            if entry[1] is None:
                flush()
            values = pre.values(entry[1])
            if values is None:
                return
            body, subset = values[entry[2]]
            e = entry[0]['evidence']
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
            while True:
                if len(ahead) * 2 <= limit:
                    fill()
                if not ahead:
                    if failed[0] is not None:
                        raise failed[0]
                    break
                entry = ahead.popleft()
                item = entry[0]
                if cpu_pinning['outcome'] == 'waiting':
                    started_streams = LP.generators_started(getattr(market, 'streams', None) or ())
                    if started_streams is None:
                        cpu_pinning.update(outcome='not_pinned', reason='cannot tell whether the reader sized its pools')
                    elif started_streams:
                        cpu_pinning.update(LP.pin_core(cpu_pinning['consumer_mask']), at_instant=equation['rows'] + len(
                            equation['absent']) + 1)
                at = item['picture']['at']
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
                yield item['evidence']
        finally:
            try:
                if pre is not None:
                    pre.close()
                    precompute.update(record=dict(PT.PRECOMPUTE_RECORD))
                ahead.clear()
                pictures.close()
                PT._save_raw_state(market_state, dict(market.report, equation=dict(equation)))
            finally:
                if cpu_pinning['outcome'] in ('pinned', 'fallback') and 'restored' not in cpu_pinning:
                    cpu_pinning['restored'] = LP.restore_mask(cpu_pinning['original_mask'])
    try:
        evidence = shared_evidence() if market else PJ.parallel_journal_prefix(builder, through, None)
        rows, processed, hashes = PT.row_pass(teacher, evidence, as_of=bound, source_manifest_hash=rc['manifest_hash'],
            recovery_path=out / 'teacher-raw-state.pkl',
            recovery_identity=dict(receipt_sha256=receipt_sha256, journal_sha256=rc['journal_sha256'],
                                   journal_count=rc['journal_count'], journal_hash=rc['journal_hash'], through=through,
                                   **({'learner_binding': learner_binding} if learner_binding is not None else {}),
                                   **({'shared_market_identity': market.identity} if market is not None else {})),
            save_requested=save_requested, retain_dstate=True)
        if cpu_pinning['outcome'] in ('pinned', 'fallback') and 'restored' not in cpu_pinning:
            cpu_pinning['restored'] = LP.restore_mask(cpu_pinning['original_mask'])     # before finish sizes its pool
        if market is not None:
            # A completed raw recovery may reuse its saved read. Never describe an
            # unstarted current iterator as a fresh complete evidence delivery.
            shared_read = PT._load_raw_state(market_state) if market_state.exists() else None
            if not shared_read or not shared_read.get('complete') or not _identity_matches(
                    shared_read.get('identity'), market.identity, out, 'saved shared read identity'):
                raise ValueError('completed teacher raw state lacks its matching complete shared read; preserved')
        if save_requested():
            raise PT.TeacherSaved('teacher raw pass saved; attachment assembly has not started')
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
    if attachment_path.exists():
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
    cpu_pinning['attachment_writer'] = attachment_writer['record'] if attachment_writer else dict(
        outcome='not_started', reason='a retained attachment stands (resume); it is hashed on a thread instead')
    hash_on_thread('rows', out / ROWS_FILE)
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
