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
    """Write `raw` durably (unchanged bytes are left as they are) and return its witness {bytes, sha256}: the write
    stream's (frankie_box_durable.write_chunks, remembered in frankie_box_filehash), or of the equal bytes already on
    disk (hashed from memory, remembered the same way): no read-back either way (endings pass, 2026-10-08)."""
    path = Path(path)
    if path.exists() and path.read_bytes() == raw:
        value = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        try:
            from frankie_box_filehash import remember
            remember(path, value)
        except ImportError:
            pass
        return value
    from frankie_box_durable import write_bytes
    return write_bytes(path, raw)


def _text(path, text):
    return _bytes(path, text.encode('utf-8'))


def _dump(path, body):
    return _text(path, json.dumps(body, indent=1, sort_keys=True, default=str))


# Function-level identities of the code the classroom invokes from other files (drop-in session 5, open item 5; the
# native identities' pattern in eac32a0: frankie_box_bedrock.code_identity of declared definitions, each hashed as its
# syntax tree without positions). A saved classroom then survives unrelated edits of those files (a comment, another
# function, a move) and still refuses any change to the code its saved values came from. The lists are the transitive
# closure, inside each file, of what the classroom calls: frankie_box_classroom_code.exhaustion_d_facts calls
# frankie_box_teach.facts and frankie_box_bedrock.producers_commit / load_producers (and _sections_of calls
# crosswalk_records); the native entry arithmetic reuses frankie_box_joined_teacher._flatten and CATEGORY_LIMIT. A new
# definition those call is added here. Not covered (as before): frankie_box_digest_sources._JSON, which teach._stream_layer
# imports, and the pinned producers checkout, whose commit the facts check themselves.
EXHAUSTION_D_CODE = (
    ('frankie_box_teach.py', ('FACTS_SCHEMA', 'FROZEN_LAYERS', 'FROZEN_DIR', 'CLOCK_RULE', 'sha256_bytes', '_load',
                              '_stream_layer', 'lineage_vocabulary', '_sections_rows', '_each_member', '_job_sections',
                              '_job_clock', '_job_evaluated', '_job_families', '_job_actions', '_streams', 'facts')),
    ('frankie_box_bedrock.py', ('PIN_COMMIT', 'V4_ADAPTER', 'V4_ADAPTER_MODULE', 'sha256_file', 'witness',
                                'producers_commit', 'loaded_modules', 'load_producers', 'crosswalk_records')))
NATIVE_ENTRY_CODE = (('frankie_box_joined_teacher.py', ('CATEGORY_LIMIT', '_flatten')),)


def _code_identities(declared):
    """{file: FRANKIE_NATIVE_CODE_IDENTITY_V1 of its declared definitions} (frankie_box_bedrock.code_identity; a missing
    name raises: never computed from less)."""
    from frankie_box_bedrock import code_identity
    return {name: code_identity(BOX / name, names) for name, names in declared}


def _whole_file_identities(declared):
    """The earlier form, {file: sha256 of its whole bytes} (saves made before the function-level identities)."""
    return {name: _sha256(BOX / name) for name, _ in declared}


def identity_acceptance(saved, current):
    """Why a saved classroom identity is accepted for `current`, or None (refused). 'code': equal. The compatibility rule
    (as the native identities, eac32a0): a save whose exhaustion_d_code / native_entry_code are the earlier whole-file
    sha256 values is accepted only while those whole files are byte-identical now and every other field is equal
    ('whole_file_unchanged'); the saved identity then stays the identity, so its saved phases load unchanged."""
    if saved == current:
        return 'code'
    whole = dict(current, exhaustion_d_code=_whole_file_identities(EXHAUSTION_D_CODE),
                 native_entry_code=_whole_file_identities(NATIVE_ENTRY_CODE))
    if saved == whole:
        return 'whole_file_unchanged'
    return None


def checkout_rebinds(saved, current):
    """Identity is content, not location (frankie_box_experiment_root.content_rebinds, ROOT's rule): the checkout moves
    under which `saved` equals `current` (or its whole-file form), or None. Only file witnesses whose bytes, sha256 and
    every other key are equal and whose paths name the same file inside a checkout may differ."""
    import frankie_box_experiment_root as XR
    for form, built in (('code', current), ('whole_file_unchanged', dict(
            current, exhaustion_d_code=_whole_file_identities(EXHAUSTION_D_CODE),
            native_entry_code=_whole_file_identities(NATIVE_ENTRY_CODE)))):
        moves = XR.content_rebinds(saved, built)
        if moves:
            return form, moves
    return None


def _record_rebinds(directory, moves, rule):
    """<classroom>/checkout-rebinds/<ns>-<sha8>.json (as ROOT's <attempt>/checkout-rebinds/); nothing saved is rewritten."""
    raw = json.dumps(dict(schema='FRANKIE_CLASSROOM_CHECKOUT_REBIND_V1', rule=rule, moves=moves, at=time.time()),
                     indent=1, sort_keys=True).encode()
    path = Path(directory) / 'checkout-rebinds' / ('%d-%s.json' % (time.time_ns(), hashlib.sha256(raw).hexdigest()[:8]))
    path.parent.mkdir(parents=True, exist_ok=True)
    _bytes(path, raw)
    return str(path)


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


PIN_RECORD = {}
JOURNAL_WITNESS_SCHEMA = 'FRANKIE_CLASSROOM_JOURNAL_WITNESS_V1'
JOURNAL_TAIL_BYTES = 1 << 20


def _file_tail(path, size):
    """The last MiB of a file (offset, sha256): the line-free form of frankie_box_boss_session._line_ending_at."""
    offset = max(0, size - JOURNAL_TAIL_BYTES)
    with open(path, 'rb') as handle:
        handle.seek(offset)
        return dict(offset=offset, sha256=hashlib.sha256(handle.read(size - offset)).hexdigest())


def _journal_witness_record(path, value):
    """The saved claim of a full journal measure, with the additive resume block (frankie_box_boss_session.
    _saved_spool_position's rule: device, inode, mtime, size and the tail)."""
    observed = os.stat(path)
    return dict(schema=JOURNAL_WITNESS_SCHEMA, path=str(path), bytes=value['bytes'], sha256=value['sha256'],
                resume=dict(device=observed.st_dev, inode=observed.st_ino, mtime_ns=observed.st_mtime_ns,
                            size=observed.st_size, tail=_file_tail(path, observed.st_size)), measured_at=time.time())


def _saved_journal_witness(directory, path, pin):
    """(value, file, why): the claim saved by an earlier attempt when it names this same unchanged file (the ROOT rule of
    frankie_box_boss_session._resume_row_spool for a file without lines: size, device, inode and mtime equal and the
    last MiB equal; no full read), else (None, None, why) and the caller makes one full pass. The claim must equal the
    pin (one pass, 2026-10-09: no seal re-read follows)."""
    record_path = Path(directory) / 'journal-witness.json'
    if not record_path.is_file():
        return None, None, 'the save recorded no journal witness (a first attempt or an older save)'
    try:
        saved = json.loads(record_path.read_bytes())
    except ValueError as error:
        return None, None, 'journal-witness.json unreadable (%s)' % error
    fast = saved.get('resume') or {}
    try:
        observed = os.stat(path)
    except OSError as error:
        return None, None, 'the journal cannot be stated (%s)' % error
    if saved.get('schema') != JOURNAL_WITNESS_SCHEMA or saved.get('path') != str(path):
        why = 'the saved witness names another schema or path'
    elif {k: saved.get(k) for k in ('bytes', 'sha256')} != {k: pin.get(k) for k in ('bytes', 'sha256')}:
        why = 'the saved witness differs from the pin'
    elif (fast.get('size'), fast.get('device'), fast.get('inode'), fast.get('mtime_ns')) != (
            observed.st_size, observed.st_dev, observed.st_ino, observed.st_mtime_ns):
        why = 'the file is not the one saved (size, device, inode or mtime differ)'
    elif _file_tail(path, observed.st_size) != fast.get('tail'):
        why = 'its last MiB differs from the saved one'
    else:
        return dict(bytes=saved['bytes'], sha256=saved['sha256']), dict(dev=observed.st_dev, ino=observed.st_ino), None
    return None, None, why


def _pin_outputs(directory, names):
    """{name: pin} for the produced files on disk, and the names that are not (listed, never pinned). The files are
    hashed side by side on pinned threads over the booked lane (frankie_box_lane_pin.executor; hashlib releases the GIL
    on each 16 MB block), each by the same streamed frankie_box_filehash.witness as before, and placed in `names` order:
    the same pins in the same order. A file is still hashed whole each time (no stat-only skip: Greg's open call (c))."""
    on_disk, listed = [], []
    for name in names:
        path = Path(directory) / name
        if path.is_file():
            on_disk.append((name, path))
        else:
            listed.append(dict(name=name, reason='not on disk after the classroom wrote its files'))
    started = time.monotonic()
    shas, how = None, None
    if len(on_disk) > 1:
        try:
            import frankie_box_lane_pin as LP
            lane = LP.lane_cpus()
            workers = max(1, min(len(on_disk), len(lane)))
            with LP.executor('thread', workers, lane) as pool:
                shas = list(pool.map(lambda item: _sha256(item[1]), on_disk))
            how = dict(LP.record(workers, lane, what='classroom output pins (sha256 threads)'))
        except Exception as error:  # noqa: BLE001 - hashed one after another below, the reason recorded
            shas, how = None, dict(where='this thread, one after another',
                                   why='%s: %s' % (type(error).__name__, error))
    if shas is None:
        shas = [_sha256(path) for _, path in on_disk]
        how = how or dict(where='this thread', why='one file or none')
    pinned = {name: dict(path=str(path), bytes=path.stat().st_size, sha256=sha)
              for (name, path), sha in zip(on_disk, shas)}
    PIN_RECORD.update(how, files=len(on_disk), seconds=round(time.monotonic() - started, 3))
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


def _side_main(function, path, cpus):
    """A side task's process: on its CPUs, compute, write the value whole (pickle, then rename), exit. SIGTERM ends it
    (the classroom's own handler, inherited by the fork, only marks a save request)."""
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    pin = 'no CPU list: the classroom\'s mask'
    if cpus:
        try:
            os.sched_setaffinity(0, set(cpus))
            pin = 'pinned'
        except OSError as error:            # listed (side record), the computation goes on with the inherited mask
            pin = 'fallback: the OS refused (%s); the inherited mask was kept' % error
    try:
        Path(str(path) + '.pin').write_text(pin, encoding='utf-8')
    except OSError:
        pass
    value = function()
    pending = Path(str(path) + '.%d.pending' % os.getpid())
    with pending.open('wb') as stream:
        pickle.dump(value, stream, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(pending, path)


class _SideTask:
    """One independent classroom operation on its own forked process beside the shared market read (Greg, 2026-10-07
    night; the September 29 pattern item 4: independent pieces side by side). The parent's phase() still saves, times
    and orders it exactly as before; result() hands it the side process's value, or computes it here (the same call)
    when the side process could not be started, died or failed: a dead side process never stops or hangs the stage.
    The side process is stopped when the classroom exits first (a stop, a refusal, a failure)."""

    def __init__(self, name, function, directory, cpus):
        self.name, self.function, self.cpus = name, function, list(cpus)
        self.path = Path(directory) / ('side-%s.pkl' % hashlib.sha256(name.encode()).hexdigest()[:16])
        self.process, self.started = None, None
        self.record = dict(operation=name, cpus=self.cpus, outcome='not_started')

    def start(self, ready):
        import atexit
        import multiprocessing
        forkable, waited, why = ready
        self.record.update(waited_for_threads_s=waited)
        if not forkable:
            self.record.update(outcome='computed_in_order', reason='no fork: %s' % why)
            return self
        for stale in [self.path, Path(str(self.path) + '.pin')] + list(self.path.parent.glob(self.path.name + '.*.pending')):
            try:
                stale.unlink()                        # a value left by an earlier, stopped attempt is never read
            except OSError:
                pass
        self.process = multiprocessing.get_context('fork').Process(
            target=_side_main, args=(self.function, self.path, self.cpus), name='classroom-side-' + self.name)
        self.started = time.monotonic()
        self.process.start()
        atexit.register(self.cancel)                  # registered after multiprocessing's own exit hook: runs first
        self.record.update(outcome='running', pid=self.process.pid, started_at=round(time.time(), 3))
        return self

    def result(self):
        if self.process is None:
            return self.function()
        clock = time.monotonic()
        self.process.join()
        self.record.update(parent_waited_s=round(time.monotonic() - clock, 3),
                           side_seconds=round(time.monotonic() - self.started, 3), exitcode=self.process.exitcode)
        pin_path = Path(str(self.path) + '.pin')
        try:
            self.record['pin'] = pin_path.read_text(encoding='utf-8')
            pin_path.unlink()
        except OSError:
            self.record['pin'] = 'not recorded (the side process wrote no pin note)'
        value, error = None, None
        if self.process.exitcode == 0 and self.path.is_file():
            try:
                with self.path.open('rb') as stream:
                    value = pickle.load(stream)
            except Exception as failure:  # noqa: BLE001 - redone here below, recorded
                error = '%s: %s' % (type(failure).__name__, failure)
        else:
            error = 'side process exit %s' % self.process.exitcode
        try:
            self.path.unlink()
        except OSError:
            pass
        if error is None:
            self.record['outcome'] = 'side_process'
            return value
        self.record.update(outcome='redone_in_order', reason=error)
        return self.function()

    def cancel(self):
        process = self.process
        if process is not None and process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
            self.record['outcome'] = 'stopped_with_the_classroom'


class _ThreadTask:
    """One independent computation on a thread of this process, beside work that releases the GIL (the external
    section's numpy Pearson beside the forked component-answer pool; endings pass 2026-10-08). No fork: the same
    process, the same OpenBLAS reduction setting (dipole_classroom_external.blas_reduction), so the same bits. result()
    joins and hands the value to the same phase() as before, or re-raises the exception the computation raised (the same
    object: a ModeNotAnswerable still reaches the runner's refusal path); when the thread was never started the value is
    computed here, in order."""

    def __init__(self, name, function):
        self.name, self.function, self.thread = name, function, None
        self.box = {}
        self.record = dict(operation=name, outcome='not_started')

    def start(self):
        import threading
        def body():
            try:
                self.box['value'] = self.function()
            except BaseException as error:  # noqa: BLE001 - re-raised by result()
                self.box['error'] = error
        self.thread = threading.Thread(target=body, name='classroom-thread-' + self.name, daemon=True)
        self.started = time.monotonic()
        self.thread.start()
        self.record.update(outcome='running', started_at=round(time.time(), 3))
        return self

    def result(self):
        if self.thread is None:
            self.record.update(outcome='computed_in_order', reason='thread not started')
            return self.function()
        clock = time.monotonic()
        self.thread.join()
        self.record.update(parent_waited_s=round(time.monotonic() - clock, 3),
                           thread_seconds=round(time.monotonic() - self.started, 3))
        if 'error' in self.box:
            self.record.update(outcome='raised', error='%s: %s' % (type(self.box['error']).__name__, self.box['error']))
            raise self.box['error']
        self.record['outcome'] = 'thread'
        return self.box['value']


def _side_writes(items, directory, cpus, ready):
    """Write the classroom's large output files side by side (endings pass, 2026-10-08): each item (name, function) runs
    its own `_dump`/`_text` calls on a forked side process pinned to one lane CPU (frankie_box_lane_pin.placement over
    `cpus`, one CPU per writer, physical cores first) while the runner goes on with the host's grade chain; the function
    returns {file name: witness} and collect() hands every witness to frankie_box_filehash.remember, so the output pins
    (_pin_outputs) stay cache hits and no file written here is read back. The bytes are the same: the same json.dumps,
    the same durable write, in another process. A writer that could not be forked, died or failed is redone here in
    order (_SideTask.result), as every side task is. Returns (tasks, placement record)."""
    tasks, how = [], None
    try:
        import frankie_box_lane_pin as LP
        _, worker_cpus, basis = LP.placement(len(items), cpus)
        how = dict(LP.record(len(items), cpus, what='classroom output writers (one side process per file group)'))
    except Exception as error:  # noqa: BLE001 - placement only; the writers then take the whole CPU list
        worker_cpus, how = [list(cpus)] * len(items), dict(where='side processes on the whole off-consumer list',
                                                          why='%s: %s' % (type(error).__name__, error))
    for (name, function), cpu in zip(items, worker_cpus):
        tasks.append(_SideTask('write:' + name, function, directory, [cpu] if isinstance(cpu, int) else cpu).start(ready))
    return tasks, how


def _collect_side_writes(tasks):
    """Join the side writers; remember every witness; {name: record} for the receipt."""
    records = {}
    for task in tasks:
        witnesses = task.result()
        try:
            from frankie_box_filehash import remember
            for path, value in (witnesses or {}).items():
                remember(path, value)
        except ImportError:
            pass
        records[task.name] = dict(task.record, files=sorted(str(p) for p in (witnesses or {})))
    return records


def _owner_sigterm(requested, owner):
    """The classroom's SIGTERM handler, bound to the process that installed it (Greg, 2026-10-07 night: never stop, never
    hang). In the classroom process itself a SIGTERM only marks a save request, exactly as before. A process FORKED from
    it (a side task, a frankie_box_lane_pin.ordered_map pool worker, the 171-pair ProcessPoolExecutor) inherits this
    handler; there it restores the default action and re-raises the signal on itself, so a pool's terminate() ends the
    worker. Without this a forked worker caught terminate() as a save mark and kept running, and the pool's unbounded
    join() after terminate() waited forever: the shard exit hang a2's ROOT hit at its 22:32Z save (LegacyFrameShards._stop,
    E2E_ONE_DAY_20231018.md session 4). No value, order or byte depends on it."""
    def handler(signum, frame):
        if os.getpid() == owner:
            requested[0] = True
            return
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
    return handler


def run(day, calculations, teacher_rows, previous, brain, day_external, day_external_sha256):
    requested = [False]
    previous_handler = signal.signal(signal.SIGTERM, _owner_sigterm(requested, os.getpid()))
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
    # Save/restore as ROOT (frankie_box_boss_session._resume_row_spool): a resume on the SAME unchanged journal takes
    # the claim its first attempt saved (no full read now); anything else is one full pass, the reason recorded. The
    # ingest's own claim row comes first (below); nothing re-reads the journal at the seal (one pass, 2026-10-09).
    journal_resume = dict(how='first measure in this directory')
    ingest_claim = None
    if journal_pin.get('path') and type(journal_pin.get('bytes')) is int and journal_pin.get('sha256'):
        # one pass (Greg, 2026-10-09): the ingest's FRANKIE_FILE_CLAIM_V2 row for the sealed journal
        # (<ingest>/file-claims.jsonl, written by ingest_block_sources beside its receipt) naming the pin's bytes and
        # sha256 and still holding (stat, filesystem, last 64 KiB) is the witness: the journal is not read whole
        from frankie_box_experiment_journal import _holding_claim
        ingest_claim = _holding_claim(
            journal_pin['path'], {k: journal_pin[k] for k in ('bytes', 'sha256')}, [Path(journal_pin['path']).parent])
    if ingest_claim is not None:
        observed = os.stat(journal_pin['path'])
        measured_witness.update(value={k: journal_pin[k] for k in ('bytes', 'sha256')},
                                file=dict(dev=observed.st_dev, ino=observed.st_ino))
        # a later witness() of the unchanged journal in this process (the learner walk, the full reader) is this value
        from frankie_box_filehash import remember
        remember(journal_pin['path'], measured_witness['value'])
        journal_resume = dict(how='the ingest\'s file claim (%s, %s): no full read' % (ingest_claim['claim_file'],
                                                                                      ingest_claim['basis']))
    elif journal_pin.get('path'):
        saved_value, saved_file, why = _saved_journal_witness(d, journal_pin['path'], journal_pin)
        if saved_value is not None:
            measured_witness.update(value=saved_value, file=saved_file)
            journal_resume = dict(how='unchanged file: size, device, inode, mtime and the last MiB checked, no full read')
        elif (d / 'journal-witness.json').is_file():
            journal_resume = dict(how='one full pass: ' + why)
    if journal_pin.get('path') and 'value' not in measured_witness:
        import threading
        from frankie_box_filehash import witness as measured
        def measure():
            try:
                measured_witness['value'] = measured(journal_pin['path'])
                stat = os.stat(journal_pin['path'])         # the measured file's identity, bound on the witness (N1)
                measured_witness['file'] = dict(dev=stat.st_dev, ino=stat.st_ino)
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
    # Read ONCE (the September 29 pattern: every file read and hashed once and shared across sub-steps): the attachment's
    # bytes are hashed in memory, checked against the teacher receipt, and the same bytes are unpickled below (the
    # former code streamed the file for its sha256 and then read it whole again). Same check, same bytes, same object.
    attachment_raw = (teacher_rows / 'teacher-attachment.pkl').read_bytes()
    attachment_sha = hashlib.sha256(attachment_raw).hexdigest()
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
    journal_witness, market, journal_claim = None, None, None
    if witness_thread is not None or 'value' in measured_witness:
        if witness_thread is not None:
            witness_thread.join()
            if 'error' in measured_witness:
                raise measured_witness['error']
            # the claim a resume takes without a full read (written below once the directory exists)
            journal_claim = _journal_witness_record(journal_pin['path'], measured_witness['value'])
        journal_witness = dict(path=journal_pin['path'], **measured_witness['value'], resume=journal_resume,
                               basis=('frankie_box_filehash.witness: streamed sha256 in this process, cached per unchanged file'
                                      if witness_thread is not None else
                                      'the ingest\'s FRANKIE_FILE_CLAIM_V2 row (claim_still_holds)' if ingest_claim else
                                      'the claim journal-witness.json saved by the first attempt (resume rule above)'),
                               seconds=round(time.monotonic() - witness_clock, 3),
                               overlapped_with=['teacher receipt and attachment hash', 'day file resolution and hash'],
                               equals_pin=({k: measured_witness['value'].get(k) for k in ('bytes', 'sha256')}
                                           == {k: journal_pin.get(k) for k in ('bytes', 'sha256')}))
    if shared_policy:
        market = _box('frankie_box_market_timeline').SharedMarketTimeline(
            calculations, day=day, workers=K.lane_workers(),
            # review N1: the witness names the file it measured (path, device, inode); the core accepts it only when that
            # is THE pinned file of the same size, else it hashes the journal itself (never a weaker check)
            input_witness=(dict({k: journal_witness[k] for k in ('bytes', 'sha256')}, path=journal_witness['path'],
                                **(measured_witness.get('file') or {}),
                                **(dict(basis='claim', claim=ingest_claim) if ingest_claim else {}))
                           if journal_witness else None))
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
    if journal_claim is not None and journal_witness.get('equals_pin'):
        _dump(d / 'journal-witness.json', journal_claim)      # the resume point of the journal measure (additive)
    p = pickle.loads(attachment_raw)          # the bytes hashed and checked above (no second read)
    attachment_bytes = len(attachment_raw)
    del attachment_raw
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
                    learner_reading_producers=KR.producer_hashes(),
                    # the existing exhaustion/D computation this classroom now invokes, and its producers loader:
                    # function-level (EXHAUSTION_D_CODE; a whole-file save is accepted while byte-identical)
                    exhaustion_d_code=_code_identities(EXHAUSTION_D_CODE),
                    # the leaf rule the native entry arithmetic reuses (frankie_box_joined_teacher._flatten / CATEGORY_LIMIT)
                    native_entry_code=_code_identities(NATIVE_ENTRY_CODE))
    if market is not None:
        identity['shared_market'] = market.identity
    # Inspection (Greg, 2026-10-07): every input this piece received, with path, bytes, sha256, the whole-day
    # binding (as_of / through_cursor / source hash) and the source binding, recorded in the receipt itself so
    # the reporter shows them from receipt.json alone. Recorded, not re-verified here; the checks above are the
    # verification and they refuse on a mismatch.
    cpus = sorted(os.sched_getaffinity(0))
    received = dict(
        # the lane (same day, same lane: the Run books it; recorded here, refused only by the learner walk)
        lane=dict(cpus=cpus, count=len(cpus), booked=K.lane_cpus(), expected=len(K.lane_cpus()),
                  note=('held booking of %d CPUs (the day\'s 32 or a 16-CPU lane)' % len(cpus)
                        if cpus == K.lane_cpus() else
                        'affinity differs from the booked CPU list: recorded, not refused here (the SOCRATIC/VERIFY '
                        'learner walk refuses)')),
        journal_witness=journal_witness, shared_market_disposition=shared_market_disposition,
        teacher_shared_read=teacher_shared_read,
        stop_polling=dict(signal='SIGTERM immediate', stop_file=os.environ.get('FRANKIE_LANE_STOP_FILE'),
                          poll_seconds=STOP_POLL_SECONDS,
                          forked_children=('SIGTERM ends a process forked from the classroom (side tasks, pinned pool '
                                           'workers): a pool terminate() is never caught as a save mark, so no join '
                                           'after terminate() can wait forever (_owner_sigterm)')),
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
                                bytes=attachment_bytes, read='once: hashed in memory and unpickled from the same bytes'),
        binding=dict(request_id=p.get('request_id'), source_hash=p.get('source_hash'), as_of=p.get('as_of'),
                     through_cursor=p.get('through_cursor'), cycle_index=0, cycle_count=1,
                     note='through_cursor = record_count - 1 names the sealed day and its whole-day causal cutoff; '
                          'it is an identity, not a claim that every input applied or every layer exists'),
        day_file=dict(path=str(day_file), sha256=day_sha, bytes=Path(day_file).stat().st_size, found=day_source),
        previous=carried, previous_external=external_carried,
        directive=dict(path=str(DIRECTIVE_PATH), sha256=identity['directive']), rules=rules_witness,
        producers=identity['producers'], learner_reading_producers=identity['learner_reading_producers'],
        # the files' whole bytes as before (the receipt field keeps its meaning); the identity binds the function-level
        # form beside it (received.identity_acceptance.current_code)
        exhaustion_d_code=_whole_file_identities(EXHAUSTION_D_CODE), native_entry_code=_whole_file_identities(NATIVE_ENTRY_CODE),
        shared_market_identity=market.identity if market is not None else None,
        shared_market_external=shared_external,
        teacher_shared_market_arithmetic=teacher_receipt.get('shared_market_arithmetic'))
    state = _load_raw_state(state_path) if state_path.exists() else dict(identity=identity, started=time.time(), phases={})
    phase_directory = d / 'saved-phases'
    phase_directory.mkdir(exist_ok=True)
    acceptance, rebinds = identity_acceptance(state['identity'], identity), None
    if acceptance is None:
        found = checkout_rebinds(state['identity'], identity)
        if found is not None:
            acceptance = 'checkout_rebind (%s)' % found[0]
            rebinds = dict(moves=found[1], record=_record_rebinds(d, found[1], found[0]))
    if acceptance is None:
        raise ValueError('saved classroom source, previous class, directive or destination changed')
    # recorded on the receipt (received.identity_acceptance): 'code' (equal), or 'whole_file_unchanged' (a save made
    # before the function-level code identities, accepted while those files are byte-identical; its identity is kept)
    received['identity_acceptance'] = dict(rule=acceptance, checkout_rebinds=rebinds, current_code=dict(
        exhaustion_d_code=identity['exhaustion_d_code'], native_entry_code=identity['native_entry_code']))
    identity = state['identity']
    # Periodic exact saves inside the long sub-steps (the 171 pairs, the native series, the anchor picture texts):
    # frankie_box_classroom_code._Segments, bound to this identity, honouring the same save request.
    K.SEGMENT_SAVES.update(directory=str(d), identity=hashlib.sha256(json.dumps(
        identity, sort_keys=True, default=str).encode()).hexdigest(), save_requested=save_requested,
        every_s=float(os.environ.get('FRANKIE_CLASSROOM_SAVE_EVERY_SECONDS') or K.SEGMENT_EVERY_SECONDS))
    received['segment_saves'] = K.SEGMENT_RECORD
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
    def phase_path(name):
        return phase_directory / (hashlib.sha256(name.encode()).hexdigest() + '.pkl')
    def phase(name, operation):
        stop()
        # the stage heartbeat (frankie_box_stage_progress); never changes the stage; a probe import failure is listed on
        # the receipt (received.probe_errors), not swallowed
        K.heartbeat('classroom: %s' % name, len(state['phases']), unit='saved operations')
        path = phase_path(name)
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
    all99, exhaustion_d, consumers, market_reading, native_entries = None, None, None, None, None
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
            # one pass (Greg, 2026-10-09): the learner reading takes the host teacher's completed walk of this day
            # under the learner binding when it is the same walk (KR._teacher_walk), instead of walking the day again
            snapshot, learner_reading = phase('learner_reading', lambda: KR.read_day(
                day, calculations, visible['binding'], day_file=day_file, day_sha256=day_sha,
                save_requested=save_requested, teacher_rows=teacher_rows, teacher_body=p))
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
        # how the 171 Dipole pairs were computed in this process (fork pool on the lane, or serial with the reason); empty
        # when the evidence came from a saved phase or from TEACH (transcribed)
        received['dipole_pairs_pool'] = dict(K.PAIR_POOL_RECORD) or dict(
            basis='not computed in this process (TEACH transcribes; or restored from a saved phase)')
        shared_market = None
        market_reading = None
        native_entries = dict(schema=K.NATIVE_ENTRY_SCHEMA, status='unavailable',
                              reason='no shared market policy on this ROOT: no picture was read, so no native value was placed')
        # The cutoff of the native entry arithmetic (Greg, 2026-10-07 night, binding for the one-day run): wall time and
        # resident memory, from the environment the plan sets for this step, else the defaults (60 min, 48 GB); recorded
        # here whether or not it is reached. A reached cutoff keeps what was computed and lists the rest; the rest of
        # the classroom is not affected.
        native_limits = K.native_cutoff_limits(os.environ)
        received['native_cutoff'] = native_limits
        # Side by side (Greg, 2026-10-07 night: the September 29 pattern for every piece): the exhaustion/D facts read
        # the ROOT's bedrock files only, never the shared pictures, so they run on their own process beside the full
        # ordered read (off the read's consumer core) and the phase below takes their value; computed in order here
        # when the read is already saved, the facts are saved, or no fork can be taken.
        # The two learner checks (stage knowledge, school) read only the visible classroom and the knowledge/school
        # documents already retained in the learner_inputs phase, never the shared pictures, so they run side by side
        # with the read too (the September 29 pattern item 1: independent pieces side by side). Each value comes back
        # through the same pickle its saved phase uses; a resume already hands every later consumer that unpickled
        # value, so the answers are the same bytes. Each is computed in order here when its phase is saved, the read
        # is saved, or no fork can be taken; a dead side process is redone in order (_SideTask.result).
        side = {}
        if market is not None and not phase_path('shared_market_context').exists():
            lane = K.lane_cpus()
            consumer, siblings, _ = K._lane_pin().consumer_core(lane)
            off_consumer = [c for c in lane if c != consumer and c not in siblings] or lane
            ready = K._fork_ready(wait=2.0)
            for name, function in (('exhaustion_d_facts', lambda: K.exhaustion_d_facts(calculations, brain)),
                                   ('knowledge_reproduction', lambda: K.stage_knowledge_reproduction(visible, knowledge)),
                                   ('school_reproduction', lambda: K.school_reproduction(visible, school))):
                if not phase_path(name).exists():
                    side[name] = _SideTask(name, function, d, off_consumer).start(ready)
            received['side_by_side'] = {name: task.record for name, task in side.items()}
        if side:
            received['side_by_side'] = {name: task.record for name, task in side.items()}
        side_exhaustion = side.get('exhaustion_d_facts')
        if market is not None:
            market_reading = phase('shared_market_context', lambda: K.market_context(
                visible, market, save_requested=save_requested, native_limits=native_limits))
            if market_reading['identity'] != market.identity:
                raise ValueError('retained classroom market reading differs from its original source')
            shared_market = K.ClassroomMarketContext(calculations, day, market_reading)
            # 18 of 18 (Greg, 2026-10-07 night): the six native entries that were context are operands of the native entry
            # arithmetic computed on the same pass (each series against every Dipole component). Whole in its own pinned
            # file; the receipt, the all-99 list and the answers carry the compact view and the pin.
            native_whole = shared_market.native_entries()
            native_entries = shared_market.native_entries_status()
            if native_whole is not None:
                native_path = d / 'native-entry-arithmetic.json'
                _dump(native_path, native_whole)
                shared_market.native_file = dict(name=native_path.name, path=str(native_path),
                                                 bytes=native_path.stat().st_size, sha256=_sha256(native_path))
                native_entries = dict(native_entries, file=shared_market.native_file)
        received['native_entries'] = native_entries
        # Where this process's classroom work ran (Greg, 2026-10-07: every pool and thread pinned to the booked lane,
        # physical cores first): the pass consumer, the native series threads and the 171-pair processes, per pool its
        # plan, outcomes and fallbacks; empty pools were restored from saved phases (not computed in this process).
        # The math libraries' thread caps the runner was started with (frankie_box_experiment_classroom_v2.sh).
        received['cpu_pinning'] = dict(K.pinning_record(), thread_caps={
            name: os.environ.get(name) for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')},
            basis=('recorded where it ran; a pool absent here was restored from a saved phase or not reached'))
        # The 99 INGESTED, not only seen (Greg, 2026-10-07): the existing exhaustion/D classroom computation
        # (frankie_box_teach.facts, code only, no model; built 2026-09-21, not invoked on the experiment path until now)
        # runs on the ROOT's completed whole-day bedrock layers. A ROOT without a native pass, a missing input or a
        # refusal leaves only these facts unavailable, named with the reason; the Dipole classroom and the day go on.
        exhaustion_d = phase('exhaustion_d_facts', side_exhaustion.result if side_exhaustion is not None else
                             lambda: K.exhaustion_d_facts(calculations, brain))
        if exhaustion_d.get('status') == 'computed':
            facts_path = d / 'exhaustion-d-facts.json'
            _dump(facts_path, exhaustion_d['facts'])
            exhaustion_d = dict(exhaustion_d, file=dict(name=facts_path.name, path=str(facts_path),
                                                        bytes=facts_path.stat().st_size, sha256=_sha256(facts_path)))
        received['exhaustion_d'] = K._exhaustion_d_receipt(exhaustion_d)
        # These inputs and their checks are retained before any answer. A resume uses this exact selection,
        # never a later peer knowledge version or a newly completed school day partway through the classroom.
        knowledge_reproduction = phase('knowledge_reproduction', side['knowledge_reproduction'].result
                                       if 'knowledge_reproduction' in side else
                                       lambda: K.stage_knowledge_reproduction(visible, knowledge))
        reproduction = phase('school_reproduction', side['school_reproduction'].result if 'school_reproduction' in side
                             else lambda: K.school_reproduction(visible, school))
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
            binding=received['binding'], mode=mode, dipole_components=len(names),
            # what the Dipole arithmetic takes per component today, and what the exhaustion/D facts took per entry
            dipole_operands=K.dipole_operands(visible), exhaustion_d=exhaustion_d,
            # the six native entries' arithmetic (None when no shared market was read: each reads absent with the reason)
            native_entries=native_entries)
        # The anchor pictures enter every component answer whole (the published guarantee); each is encoded ONCE on
        # the lane (K.picture_texts: a pinned fork pool) and spliced into each answer that names it: the same bytes.
        # Only when a component answer is still to be computed; released after the summary.
        pending_names = [n for n in names if not phase_path('component:' + n).exists()]
        if shared_market is not None and pending_names:
            shared_market.prepare_picture_texts()        # placement: received.cpu_pinning.picture_texts
        # Endings pass (2026-10-08; Greg: CPUs in every step of the ending): the component answers still to be computed
        # run side by side on a pinned fork pool over the lane (K.component_answers_side_by_side, ordered_map) and
        # arrive in name order; each is saved by the same phase() as before (the same value, the same pickle bytes),
        # a saved one is restored as before. The external section (numpy Pearson, releases the GIL) runs on a thread
        # of this process started once the pool is forked, and its phase takes that value in the same place.
        external = _ThreadTask('external_answers', lambda: KX.answers(
            ext_visible, dipole_visible=visible, learner_context=learner_context,
            independent_evidence=independent_external, knowledge=knowledge, school=school))
        start_external = external.start if not phase_path('external_answers').exists() else None
        answers = K.component_answers_side_by_side(
            visible, pending_names, {n: C.component(visible, n) for n in pending_names},
            {n: [q['right'] for q in C.pairs_of(visible, n)] for n in pending_names},
            learner_context=learner_context, shared_market=shared_market, exhaustion_d=exhaustion_d,
            on_start=start_external) if pending_names else None
        def next_answer(expected):
            name, value = next(answers)
            if name != expected:
                raise ValueError('component answers arrived out of order: %s before %s' % (name, expected))
            return value
        outputs = {}
        try:
            for n in names:
                outputs[n] = phase('component:' + n, (lambda n=n: next_answer(n)) if n in pending_names else
                                   lambda n=n: K.component_answer(
                                       visible, C.component(visible, n), [q['right'] for q in C.pairs_of(visible, n)],
                                       learner_context=learner_context, shared_market=shared_market, exhaustion_d=exhaustion_d))
        finally:
            if answers is not None:
                answers.close()                          # the pool is ended (bounded) before any later fork
        received['side_by_side'] = dict(received.get('side_by_side') or {}, external_answers=external.record)
        summary = phase('summary', lambda: K.summary_answer(visible, outputs, learner_context=learner_context,
                                                          shared_market=shared_market, exhaustion_d=exhaustion_d))
        if shared_market is not None:
            shared_market.release_picture_texts()
        ext_ledgers = phase('external_answers', external.result)
        # The 13 external points (Greg via Frankie, 2026-10-07): per point how the classroom used it (computed / context /
        # absent), the series that entered the external section arithmetic (each value at or after its reader stamp), the
        # 99 entries the day file declares it feeds with the mapping basis (exact / closest) and the placement note, and
        # any row whose reader stamp precedes its declared event time or 14:00 ET placement (an integrity finding listed
        # beside the use, review R-B), and the day file's stamp shape (reader stamp, or a superseded publication stamp).
        consumers['external_points'] = phase('external_points', lambda: K.external_points_use(
            ext_ledgers, day_file, day_sha, cutoff_ns=(ext_visible.get('pre_message') or {}).get('cutoff_ns')))
        # the all-99 list after every answer: it accounts for what entered the Dipole, exhaustion/D and external arithmetic
        all99 = phase('all99_coverage', lambda: K.all99_coverage(market_reading, consumers, repo_root=ROOT))
    except (K.ModeNotAnswerable, KX.ModeNotAnswerable) as error:
        pinned, listed = _pin_outputs(d, ['package.external.pre_message.json', 'package.external.binding.json']
                                      + [f'package.{part}.c15.json' for part in ('source', 'teacher_key', 'pre_message', 'binding')])
        if all99 is None and consumers is not None:
            # refused before the list: it still accounts for what was read (no external answers, said so in the list)
            all99 = K.all99_coverage(market_reading, consumers, repo_root=ROOT)
        received['all99'] = all99
        received['probe_errors'] = dict(K.PROBE_ERRORS)
        refusal = dict(schema=SCHEMA, day=day, status='refused', mode=mode, reason=str(error),
                       listed='SOCRATIC/VERIFY require the learner-owned sealed-journal/day-file reader; '
                              'missing evidence never falls back to the host key',
                       teacher_rows=str(teacher_rows), shared_market_external=shared_external,
                       shared_market=shared_market.summary() if shared_market is not None else None,
                       shared_market_use=shared_market.use() if shared_market is not None else None,
                       all99_coverage=all99, exhaustion_d=K._exhaustion_d_receipt(exhaustion_d),
                       native_entries=native_entries,
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
    # Endings pass (2026-10-08): the large answer files (the picture texts sit in the outputs, the ledgers and the
    # rendered markdown) are encoded and written on side processes, one lane CPU each, beside the host's grade chain
    # below; the same json.dumps and the same durable write (the same bytes), their write-stream witnesses remembered
    # here so the output pins read nothing back. Collected before the grade-chain files are written.
    def write_code_answers():
        return {str(d / 'code-answers.json'): _dump(d / 'code-answers.json', dict(
            schema=K.SCHEMA, rules=rules_witness, outputs=outputs, summary=summary,
            school=reproduction, stage_knowledge=knowledge_reproduction,
            learner_reading=learner_reading, model_calls=0,
            shared_market=shared_market.summary() if shared_market is not None else None,
            shared_market_external=shared_external, all99_coverage=all99,
            exhaustion_d=K._exhaustion_d_receipt(exhaustion_d),
            native_entries=native_entries))}
    def write_learner_knowledge():
        return {str(d / 'learner-knowledge.json'): _dump(d / 'learner-knowledge.json', dict(
            day=day, stage='classroom', documents=knowledge,
            versions=knowledge_input['versions'], listed=knowledge_input['listed'],
            school_documents=school, school_listed=school_listed,
            school_sources=reproduction['school_days_read'],
            learner_reading=learner_reading,
            applied_to=['component_answer', 'summary_answer', 'external_answers']))}
    def write_ledgers():
        return {str(d / 'ledgers.json'): _dump(d / 'ledgers.json', built['ledgers'])}
    def write_classroom_md():
        return {str(d / 'classroom.md'): _text(d / 'classroom.md', C.render_markdown(built['ledgers'], built['dropped_findings']))}
    def write_external():
        first = _dump(d / 'external-code-answers.json', dict(schema=KX.SCHEMA, rules=rules_witness, ledgers=ext_ledgers, model_calls=0))
        second = _dump(d / 'external-novel-findings.json', dict(schema='FRANKIE_EXTERNAL_FINDINGS_V1', day=day,
                       findings=ext_ledgers['external_novel_findings'],
                       source=dict(path=str(d / 'external-code-answers.json'), sha256=first['sha256'])))
        return {str(d / 'external-code-answers.json'): first, str(d / 'external-novel-findings.json'): second}
    writer_lane = K.lane_cpus()
    writer_consumer, writer_siblings, _ = K._lane_pin().consumer_core(writer_lane)
    writers, writers_placement = _side_writes(
        [('code-answers', write_code_answers), ('learner-knowledge', write_learner_knowledge), ('ledgers', write_ledgers),
         ('classroom-md', write_classroom_md), ('external', write_external)],
        d, [c for c in writer_lane if c != writer_consumer and c not in writer_siblings] or writer_lane,
        K._fork_ready(wait=2.0))

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

    # the side writers of the answer files (started above, beside the two grade chains): joined here, witnesses remembered
    received['side_by_side'] = dict(received.get('side_by_side') or {}, output_writers=dict(
        placement=writers_placement, tasks=_collect_side_writes(writers)))

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
                       'package.external.pre_message.json', 'package.external.binding.json',
                       # the whole exhaustion/D facts (listed, not pinned, on a day they were not computed)
                       'exhaustion-d-facts.json',
                       # the six native entries' whole arithmetic (listed when no shared market was read)
                       'native-entry-arithmetic.json']
                      + [f'package.{part}.c15.json' for part in ('source', 'teacher_key', 'pre_message', 'binding')]
                      + [f'{name}.json' for name in files])
    outputs_pinned, outputs_listed = _pin_outputs(d, produced_names)
    # the all-99 output analogues get their pins now that the files exist (receipt.json cannot pin itself)
    for item in (all99 or {}).get('entries') or []:
        if item.get('outputs'):
            item['output_pins'] = {name: (outputs_pinned.get(name) or ('this receipt' if name == 'receipt.json' else 'not on disk'))
                                   for name in item['outputs']}
    received['all99'] = all99
    # every pool that ran in this process, including those after the market read (the anchor picture texts)
    received['cpu_pinning'] = dict(received.get('cpu_pinning') or {}, **K.pinning_record())
    # a heartbeat that could not be written (the probe module failed to import), counted per error; {} = none
    received['probe_errors'] = dict(K.PROBE_ERRORS)
    received['output_pins'] = dict(PIN_RECORD)              # where the output sha256s ran and how long
    # one pass (Greg, 2026-10-09): no seal re-read of the journal; the witness basis is on journal_witness
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
                  # The exhaustion/D facts (frankie_box_teach.facts on the completed bedrock rows): status, inputs, the
                  # per-entry attribution and the pinned whole facts file (exhaustion-d-facts.json); the facts themselves
                  # stay in that file. Also under received.exhaustion_d.
                  exhaustion_d=K._exhaustion_d_receipt(exhaustion_d),
                  # The six native entries that were context, now operands of the native entry arithmetic (Greg,
                  # 2026-10-07 night: 18 of 18): per entry use / form / series / pairs / relation counts / unavailable
                  # carriers, and the pin of native-entry-arithmetic.json (every series, pair and cell whole). Also
                  # under received.native_entries.
                  native_entries=native_entries,
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
