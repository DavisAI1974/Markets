"""The ONE stage-boundary sequence every workflow piece hands off through (Greg, 2026-10-08: "we can probably carry this
exact sequence from handoff to handoff between workflow pieces"; "Just have the build agent do this now between all
pieces"; "I won't be saying resume. We need to make trigger for teacher to start when root does last task"; "Root
should stay stopped though"; "we put CPUs on validate in root before we move onto next step after we clean and move
root data"; "when he saves is then when he starts cleaning and zipping"; "we only do 1 pass. Eliminate the 2nd pass").

At a stage's boundary (its step receipt finished: done or reused), boundary() runs, in this order and only once per
(stage, key):
  1. VALIDATE  every artifact the stage's receipts pin ({path, bytes, sha256[, count]}; the ROOT's six documents through
               frankie_box_root_validate.collect_pins, every other stage through collect_generic over the receipt
               files named in STAGES) is read EXACTLY ONCE on the held lane's CPUs (frankie_box_root_validate, lane_pin
               placement, largest first; exit 75 = the day's own save, honoured by the caller's check_save). A mismatch
               FAILS the day at this boundary: the successor never starts on unvalidated data.
  2. SAVE      the one line: the day's OWN save marker is requested (the exact marker ACTION=save writes, through
               frankie_box_frankie_queue.request_save; the Run's bound marker when the day has no queue entry), so the
               worker stops at this boundary (exit 75: entry saved, booking and CPUs retained, the stage's process ends
               and stays stopped; nothing restarts it).
  3. CLEAN     a DETACHED unit (systemd-run, KillMode=mixed, pinned to the retained lane) waits for the queue to record
               the day saved, then frankie_box_root_move.clean on the stage's output directories: pinned files of
               1 GiB or more outside every guarded prefix move behind a symlink, directories of 1 GiB or more with no
               pin inside become one tar -v | zstd -T0 archive each, sha256 on the write stream, the listing at
               creation, no read-back; the moved-manifest written.
  4. TRIGGER   the unit's FINAL step, the stage's last task: ACTION=resume RUN DAY then ACTION=kick LINE=root
               SCOPE=RUN:DAY through frankie_box_frankie_queue.sh with CODE_ROOT and MARKETS_SHA of the checkout that
               LAUNCHED the unit (a clean launched from a restaged checkout resumes on that tip, never on the old one);
               the resumed day reuses its finished stages (their receipts) and goes on to the successor. Guards:
               exactly once (trigger.fired beside the receipt, create-only), never while the day is not in state saved,
               never while a successor process or unit for that run/day already exists. A clean that FAILS (a missing
               stream hash, a refused move, a dead zstd) leaves the day SAVED: no resume, the failure named in the
               trigger receipt and beside the day's marker (<marker>.clean.json, shown by ACTION=status); an operator
               resumes by hand, and the boundary then goes on to the successor without a second clean.
The switch: FRANKIE_CLEAN_ON_SAVE=on (default) = validate -> save -> clean -> auto resume -> successor; off = validate
-> successor directly (no save, no clean). One switch for every stage, recorded on every receipt. Receipts under
<run>/handoff/<key>/<stage>/: handoff.json (FRANKIE_STAGE_HANDOFF_V1), validate.json (the validator's), clean/
clean-receipt.json + moved-manifest.json, trigger.json (FRANKIE_ROOT_CLEAN_TRIGGER_V1, with the stage name).

Adopting the sequence for a stage = one STAGES entry (which receipt fields name its output roots, which receipt files
inside them to walk, which prefixes a safe_path reader of the next stage guards, the successor) and one boundary()
call after its step record in frankie_box_frankie_queue._finish_steps / class_day. Nothing in the stage's own files
changes; no byte of its outputs or receipt fields changes (the handoff writes only its own files).
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

SWITCH = 'FRANKIE_CLEAN_ON_SAVE'
SCHEMA = 'FRANKIE_STAGE_HANDOFF_V1'
TRIGGER_SCHEMA = 'FRANKIE_ROOT_CLEAN_TRIGGER_V1'
FINISHED_WITH_OUTPUTS = ('done', 'reused')
WAIT_SAVED_SECONDS = 1800
WAIT_POLL_SECONDS = 10
VENV_PYTHON = '/opt/frankie-box/venv/bin/python'


def native_complete(stage, roots):
    """The ROOT's native stage is complete (work/native-stage.json present): the resumed sink's append segments and the
    pre-save ledger copy are then redundant (frankie_box_root_move.redundant_ledger_segments)."""
    return bool(STAGES.get(stage, {}).get('collector') == 'root' and roots and (Path(roots[0]) / 'work' / 'native-stage.json').is_file())


def _fake_transport(log_path):
    """The toy's transport (FRANKIE_ARCHIVE_S3_FAKE=<log>): no boto3; every upload call appended to the log."""
    class Fake:
        @staticmethod
        def upload(path, bucket, key, *, region, sha256=None, extra_args=None, storage_class=None, **_):
            r = dict(schema='FRANKIE_S3_TRANSPORT_V1', op='upload', path=str(path), bucket=bucket, key=key, region=region,
                     bytes=os.path.getsize(path), sha256=sha256, storage_class=storage_class, status='uploaded',
                     transport='fake', extra_args=extra_args)
            with open(log_path, 'a') as handle:
                handle.write(json.dumps(r, sort_keys=True) + '\n')
            return r
    return Fake


def floor_bytes():
    """The clean's floor (frankie_box_root_move.FLOOR_BYTES, 1 GiB); FRANKIE_CLEAN_FLOOR_BYTES overrides it (toy tests)."""
    import frankie_box_root_move as M
    try:
        return int(os.environ.get('FRANKIE_CLEAN_FLOOR_BYTES') or M.FLOOR_BYTES)
    except ValueError:
        return M.FLOOR_BYTES

# Per stage: roots = step-receipt fields naming an output directory (or a file inside it); inner = receipt files under
# each root to collect pins from (besides the Run's own step receipt); guarded = prefixes (relative to each root) that
# a safe_path reader of the next stage opens (a symlink there would be refused: those files stay); successor = the
# stage the trigger's resume reaches next (informational; the queue's own order decides).
def _teacher_rows_dirs(record):
    # frankie_box_experiment_teacher.py:179-184 writes <TEACHER_ROWS>/<day>/receipt.json; the Run's teacher step receipt
    # (experiment.py:4187) names the days, not the directories
    try:
        import frankie_box_experiment as X
        base = Path(X.TEACHER_ROWS)
    except ImportError:
        base = Path('/opt/frankie-box/work/experiment-teacher-rows')
    dirs = [base / d for d in (record.get('days') or []) if isinstance(d, str)]
    # the step receipt also names the rows directories per day under inspection.outputs.rows (experiment.py 4232)
    rows = ((record.get('inspection') or {}).get('outputs') or {}).get('rows') or {}
    for value in (rows.values() if isinstance(rows, dict) else []):
        if isinstance(value, str) and value.startswith('/') and Path(value) not in dirs:
            dirs.append(Path(value))
    return dirs


def _report_dirs(record):
    # frankie_box_experiment_day_reports.py:407 writes receipt.json beside the report files the step record lists
    return [Path(item['file']).parent for item in (record.get('reports') or []) if isinstance(item, dict) and item.get('file')]


STAGES = {
    'root': dict(roots=('calculations',), inner=('calculations-receipt.json', 'work/derive.json'), collector='root',
                 guarded=('work/derived/.rows/', 'work/bedrock/', 'work/derived/.projection-v2/'), successor='teacher'),
    'teacher': dict(roots=(), roots_from=_teacher_rows_dirs, inner=('receipt.json',), successor='classroom (arm day) / data'),
    'classroom': dict(roots=('classroom',), inner=('completion.json', 'receipt.json'), successor='data'),
    'data': dict(roots=('target',), inner=('MANIFEST.json',), successor='search'),
    'search': dict(roots=('target',), inner=('MANIFEST.json',), successor='lessons (batch) / frankie_lessons'),
    'accumulated_lessons': dict(roots=(), inner=(), successor='lessons (batch)'),
    'lessons': dict(roots=(), inner=(), successor='survivors (batch) / exchange'),
    'survivors': dict(roots=(), inner=(), successor='exchange'),
    'frankie_lessons': dict(roots=(), inner=(), successor='exchange'),
    'exchange': dict(roots=('exchange',), inner=('receipt.json',), successor='voice'),
    'voice': dict(roots=(), inner=(), successor='school'),
    'school': dict(roots=('file',), inner=(), successor='reports'),       # its receipt is the child's last log line (experiment.py:3565), no file
    'reports': dict(roots=(), roots_from=_report_dirs, inner=('receipt.json',), successor='jev / close'),
    'jev': dict(roots=(), inner=(), successor='reports revision / close'),
}


def on():
    return os.environ.get(SWITCH, 'on') != 'off'


def _load(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def _write(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(body, indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    os.replace(pending, path)
    return body


def handoff_dir(run_dir, key, stage):
    return Path(run_dir) / 'handoff' / key / stage


def output_roots(stage, record):
    """The stage's output directories from its step receipt fields (a file field names its directory)."""
    roots = []
    for field in STAGES.get(stage, {}).get('roots', ()):
        value = record.get(field)
        if isinstance(value, dict):
            value = value.get('path')
        if isinstance(value, str) and value.startswith('/'):
            path = Path(value)
            root = path if path.is_dir() else path.parent
            if root not in roots and root.is_dir():
                roots.append(root)
    derive = STAGES.get(stage, {}).get('roots_from')
    if derive is not None:
        for root in derive(record):
            root = Path(root)
            if root not in roots and root.is_dir():
                roots.append(root)
    return roots


def receipt_files(stage, step_receipt, roots):
    files = [Path(step_receipt)] if step_receipt and Path(step_receipt).is_file() else []
    for root in roots:
        for name in STAGES.get(stage, {}).get('inner', ()):
            path = Path(root) / name
            if path.is_file() and path not in files:
                files.append(path)
    return files


def collect(stage, step_receipt, roots):
    """The stage's Pins: the ROOT's own collector over its attempt directory, every other stage the generic walk."""
    import frankie_box_root_validate as V
    if STAGES.get(stage, {}).get('collector') == 'root' and roots:
        pins = V.collect_pins(roots[0])
        if step_receipt and Path(step_receipt).is_file():
            # the Run's own root step receipt: its {path,bytes,sha256} objects (receipt_sha256 is a bare string: measured)
            V._walk_pins(pins, Path(step_receipt).name, _load(step_receipt), '')
        return pins
    return V.collect_generic([str(f) for f in receipt_files(stage, step_receipt, roots)],
                             root=roots[0] if roots else None, only_under=roots)


def lane_of(run):
    """The day's held lane for the children: the owner's CPU set, else the slot booking's ledger, else the environment."""
    owner = getattr(run, 'owner', None) or {}
    if owner.get('cpus'):
        cpus = owner['cpus']
        return ','.join(str(c) for c in cpus) if isinstance(cpus, (list, tuple)) else str(cpus)
    booking = getattr(run, 'slot_booking', None)
    if booking:
        try:
            doc = _load(Path(run.cores.LEDGER) / (booking + '.json'))
            if doc and doc.get('cpu_list'):
                return str(doc['cpu_list'])
        except (AttributeError, TypeError):
            pass
    return os.environ.get('FRANKIE_LANE_CPUS') or os.environ.get('FRANKIE_BOOKED_CPUS') or ''


def _python():
    forced = os.environ.get('FRANKIE_HANDOFF_PYTHON')
    if forced:
        return forced
    return VENV_PYTHON if Path(VENV_PYTHON).is_file() else sys.executable


def run_validate(run, stage, key, out_dir, pins_args, lane, log):
    """The validator as a child on the lane (taskset of the held CPUs; FRANKIE_LANE_CPUS for lane_pin; the day's own
    stop marker as FRANKIE_LANE_STOP_FILE so a save stops it with exit 75). Returns (exit code, receipt or None)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / 'validate.json'
    log_path = Path(run.dir) / 'logs' / ('%s-%s-validate.log' % (key, stage))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [_python(), '-B', str(HERE / 'frankie_box_root_validate.py'), '--out', str(receipt_path), '--stage', stage] + pins_args
    if lane:
        command = (['taskset', '-c', lane] if shutil.which('taskset') else []) + command
    env = dict(os.environ, PYTHONPATH=str(getattr(run, 'code_root', HERE.parents[2])), PYTHONDONTWRITEBYTECODE='1')
    if lane:
        env['FRANKIE_LANE_CPUS'] = lane
        env['FRANKIE_BOOKED_CPUS'] = lane
    env.pop('FRANKIE_LANE_STOP_FILE', None)
    if getattr(run, 'stop_marker', None):
        env['FRANKIE_LANE_STOP_FILE'] = str(run.stop_marker)
    env['FRANKIE_ROOT_VALIDATE_DIR'] = str(out_dir / ('%s-validate' % stage))
    with open(log_path, 'ab') as out:
        out.write(('\n### %s %s validate at %s\n' % (stage, key, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))).encode())
        out.flush()
        code = subprocess.call(command, env=env, stdout=out, stderr=subprocess.STDOUT)
    log('%s %s: validate exit %d (%s)' % (stage, key, code, log_path))
    return code, _load(receipt_path), str(log_path)


def request_own_save(run, e, by):
    """The day's own save marker: the queue's request_save when the day has a ROOT-line entry (the entry's save_request
    and event recorded as ACTION=save would), else the marker body written create-only at the Run's bound marker."""
    try:
        import frankie_box_frankie_queue as Q
        try:
            out = Q.request_save(run.plan['run'], e['day'], by)
            return dict(how='queue request_save', marker=out.get('marker'), standing=True)
        except (SystemExit, OSError, RuntimeError, ValueError, KeyError) as refusal:
            why = '%s: %s' % (type(refusal).__name__, refusal)
            if 'stands already' in why:
                return dict(how='queue request_save', marker=str(Q.marker_of(run.plan['run'], e['day'])), standing=True,
                            note='a save request stood already')
    except ImportError:
        why = 'queue module unavailable'
    marker = getattr(run, 'stop_marker', None)
    if not marker:
        return dict(how='none', marker=None, standing=False, reason='no queue entry (%s) and no bound marker' % why)
    body = dict(schema='FRANKIE_QUEUE_SAVE_REQUEST_V1', run=run.plan['run'], day=e['day'],
                attempt=(getattr(run, 'owner', None) or {}).get('attempt'), booking=getattr(run, 'slot_booking', None),
                cpus=(getattr(run, 'owner', None) or {}).get('cpus'), requested_at=time.time(),
                requested_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), by=by)
    try:
        Path(marker).parent.mkdir(parents=True, exist_ok=True)
        with open(marker, 'x', encoding='utf-8') as handle:
            handle.write(json.dumps(body, indent=1, sort_keys=True) + '\n')
        return dict(how='bound marker written (no queue entry: %s)' % why, marker=str(marker), standing=True)
    except FileExistsError:
        return dict(how='bound marker stood already', marker=str(marker), standing=True)


def start_clean_unit(run, e, stage, key, out_dir, roots, receipts, lane, code_root, commit, log):
    """The detached clean unit on the retained lane (systemd-run, KillMode=mixed; a new session without systemd)."""
    out_dir = Path(out_dir)
    log_path = Path(run.dir) / 'logs' / ('%s-%s-clean.log' % (key, stage))
    argv = [_python(), '-B', str(Path(code_root) / 'deploy/aws/box/frankie_box_stage_handoff.py'), '--action', 'clean',
            '--run', run.plan['run'], '--day', e['day'], '--stage', stage, '--key', key, '--handoff-dir', str(out_dir),
            '--run-dir', str(run.dir), '--code-root', str(code_root), '--commit', commit]
    for root in roots:
        argv += ['--root', str(root)]
    for receipt in receipts:
        argv += ['--receipt', str(receipt)]
    if lane:
        argv += ['--cpus', lane]
    env = dict(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONPATH=str(code_root), HOME=os.environ.get('HOME') or '/root',
               MARKETS_SHA=commit, CODE_ROOT=str(code_root))
    for name in ('FRANKIE_QUEUE_DIR', 'FRANKIE_QUEUE_SH', 'FRANKIE_HANDOFF_PYTHON', 'FRANKIE_ZSTD', 'FRANKIE_ARCHIVE_ROOT',
                 'FRANKIE_BOX_ROOT', 'FRANKIE_HANDOFF_NO_KEEP_RUNNING', 'FRANKIE_HANDOFF_WAIT_SAVED_SECONDS',
                 'FRANKIE_HANDOFF_DETACH', 'FRANKIE_CLEAN_FLOOR_BYTES', 'FRANKIE_ARCHIVE_S3', 'FRANKIE_ARCHIVE_BUCKET',
                 'FRANKIE_ARCHIVE_PREFIX', 'FRANKIE_ARCHIVE_REGION', 'FRANKIE_ARCHIVE_S3_FAKE', 'FRANKIE_MOUNT_CMD',
                 'FRANKIE_FSTAB', SWITCH):
        if os.environ.get(name):
            env[name] = os.environ[name]
    pinned = (['taskset', '-c', lane] if lane and shutil.which('taskset') else [])
    how = None
    if shutil.which('systemd-run') and os.environ.get('FRANKIE_HANDOFF_DETACH', 'systemd') != 'session':
        unit = 'frankie-clean-%s-%s-%s-%d' % (stage, run.plan['run'], e['day'], int(time.time()))
        cmd = ['systemd-run', '--unit', unit, '--collect', '-p', 'StandardOutput=append:%s' % log_path,
               '-p', 'StandardError=append:%s' % log_path, '-p', 'KillMode=mixed'] + \
              [x for k, v in sorted(env.items()) for x in ('-E', '%s=%s' % (k, v))] + pinned + argv
        code = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
        how = dict(method='systemd-run', unit=unit, exit_code=code)
    if how is None or how['exit_code'] != 0:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, 'ab') as out:
            proc = subprocess.Popen(pinned + argv, env=dict(os.environ, **env), stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        how = dict(method='new session', pid=proc.pid, systemd_run=how)
    log('%s %s: clean unit started (%s)' % (stage, key, json.dumps(how, sort_keys=True)))
    return dict(how, argv=argv, log=str(log_path))


def boundary(run, e, stage, key, record, *, code_root, commit, log=print):
    """The sequence at one stage boundary; returns the handoff receipt (status: off | nothing_to_hand_off |
    validate_saved | failed | saved | already | ...). The caller calls run.check_save() right after (the save requested
    here is honoured there: exit 75)."""
    out_dir = handoff_dir(run.dir, key, stage)
    switch = 'on' if on() else 'off'
    base = dict(schema=SCHEMA, run=run.plan['run'], day=e['day'], stage=stage, key=key, switch=switch, at=time.time(),
                successor=STAGES.get(stage, {}).get('successor'), commit=commit, code_root=str(code_root))
    if not record or record.get('status') not in FINISHED_WITH_OUTPUTS:
        return dict(base, status='nothing_to_hand_off', reason='the step is %s' % ((record or {}).get('status')))
    existing = _load(out_dir / 'handoff.json')
    clean = _load(out_dir / 'clean' / 'clean-receipt.json')
    trigger = _load(out_dir / 'trigger.json')
    trigger_done = (trigger or {}).get('status') == 'done'
    clean_again = None
    if existing and existing.get('status') == 'failed':
        # review 2026-10-08 finding 1 (Patch A): a FAILED validation is never "handed off before". The queue retries a
        # failed finish once per worker start; that retry validates AGAIN (partial.json reuses every file whose stat is
        # unchanged, so only changed files are re-read); the failed receipt is kept aside, never read as a pass
        os.replace(out_dir / 'handoff.json', out_dir / ('handoff.failed-%d.json' % int(existing.get('at') or time.time())))
        existing = None
    if existing and (existing.get('status') == 'validated' or (existing.get('status') == 'saved' and trigger_done)):
        # once per (stage, key): a resumed day passes this boundary again after a DONE trigger (or a validated-only pass)
        return dict(existing, status='already', earlier_status=existing['status'],
                    clean_status=(clean or {}).get('status'), trigger_status=(trigger or {}).get('status'),
                    reason='this boundary was handed off before (%s); the clean %s; the trigger %s; the day goes on to %s'
                           % (existing['status'], (clean or {}).get('status') or 'left no receipt',
                              (trigger or {}).get('status') or 'left no receipt', base['successor']))
    if existing and existing.get('status') == 'saved' and not trigger_done:
        # review finding 2 (Patch B): the clean never triggered (a box reboot, a failed item, a hand resume): validate
        # again (unchanged stat = no read), then go on WITHOUT a second clean; the earlier receipts stay beside this one
        os.replace(out_dir / 'handoff.json', out_dir / ('handoff.unfinished-%d.json' % int(time.time())))
        base['earlier'] = dict(status='saved', trigger=(trigger or {}).get('status'), clean=(clean or {}).get('status'))
        clean_again = False
        existing = None
    roots = output_roots(stage, record)
    step_receipt = run.receipt_path(stage, key)
    receipts = receipt_files(stage, step_receipt, roots)
    lane = lane_of(run)
    if STAGES.get(stage, {}).get('collector') == 'root' and roots:
        pins_args = ['--root', str(roots[0]), '--run-dir', str(run.dir)] + [a for r in receipts for a in ('--receipt', str(r))]
    else:
        pins_args = [a for r in receipts for a in ('--receipt', str(r))] + [a for r in roots for a in ('--dir', str(r))] + \
                    [a for r in roots for a in ('--only-under', str(r))]
    _write(out_dir / 'handoff.json', dict(base, status='validating', roots=[str(r) for r in roots],
                                          receipts=[str(r) for r in receipts], lane=lane))
    code, validation, vlog = run_validate(run, stage, key, out_dir, pins_args, lane, log)
    totals = (validation or {}).get('totals') or {}
    base.update(roots=[str(r) for r in roots], receipts=[str(r) for r in receipts], lane=lane,
                validate=dict(exit_code=code, log=vlog, totals=totals, mismatches=(validation or {}).get('mismatches'),
                              reader_refusals=(validation or {}).get('reader_refusals'),
                              seconds=(validation or {}).get('seconds'), receipt=str(out_dir / 'validate.json')))
    if code == 75:
        return _write(out_dir / 'handoff.json', dict(base, status='validate_saved',
                                                     reason='the validator stopped on the day\'s standing save (exit 75); '
                                                            'it resumes from its partial results on the next start'))
    if code != 0:
        mismatches = (validation or {}).get('mismatches') or []
        if mismatches:
            why = 'validation exit %d: %s' % (code, '; '.join('%s: %s' % (m['path'], ', '.join(m['problems'])) for m in mismatches))
        elif code == 4:
            why = 'validation exit 4: verified but not readable by the next stage: %s' % json.dumps(
                (validation or {}).get('reader_refusals'))
        elif (validation or {}).get('document_problems'):
            why = 'validation exit %d: %s' % (code, '; '.join((validation or {}).get('document_problems')))
        else:
            why = 'validation exit %d: no validator receipt or an unlisted refusal (see %s)' % (code, vlog)
        return _write(out_dir / 'handoff.json', dict(base, status='failed', reason=why))
    if clean_again is False:
        return _write(out_dir / 'handoff.json', dict(base, status='validated',
                                                     reason='re-validated after an unfinished clean (trigger %s, clean %s): '
                                                            'no second clean; straight on to %s' % (
                                                                base['earlier'].get('trigger') or 'absent',
                                                                base['earlier'].get('clean') or 'absent', base['successor'])))
    if switch == 'off':
        return _write(out_dir / 'handoff.json', dict(base, status='validated',
                                                     reason='%s=off: validated; no save, no clean; straight on to %s'
                                                            % (SWITCH, base['successor'])))
    # a save is requested only when the clean has work: the plan (JSON and stat only, nothing read) must name at least
    # one move or archive; a stage whose outputs are all under the floor goes straight on to its successor
    import frankie_box_root_move as M
    try:
        pins = collect(stage, step_receipt, roots)
        items = M.plan(roots, {real: job['expected'] for real, job in pins.jobs.items()},
                       guarded=STAGES.get(stage, {}).get('guarded', ()), floor=floor_bytes(),
                       native_complete=native_complete(stage, roots),
                       archive_root=Path(os.environ.get('FRANKIE_ARCHIVE_ROOT') or M.ARCHIVE_ROOT),
                       box_root=Path(os.environ.get('FRANKIE_BOX_ROOT') or M.BOX_ROOT))
    except ValueError as error:
        items = []
        base['plan_error'] = str(error)
    work = [i for i in items if i['kind'] in ('move', 'archive')]
    base['clean_plan'] = dict(items=len(items), work=len(work), bytes=sum(i['bytes'] for i in work),
                              kinds={k: sum(1 for i in work if i['kind'] == k) for k in ('move', 'archive')})
    if not work:
        return _write(out_dir / 'handoff.json', dict(base, status='validated',
                                                     reason='validated; nothing to clean (%d items, none above the floor or '
                                                            'all guarded/receipts): no save; straight on to %s'
                                                            % (len(items), base['successor'])))
    # THE ONE LINE'S WORK: the day's own save marker (the worker stops at this boundary; the stage stays stopped)
    saved = request_own_save(run, e, by='%s boundary: validated; stop after validation, clean on save (Greg 2026-10-08)' % stage)
    unit = start_clean_unit(run, e, stage, key, out_dir, roots, receipts, lane, code_root, commit, log)
    return _write(out_dir / 'handoff.json', dict(base, status='saved', save=saved, clean_unit=unit,
                                                 reason='validated (%d pinned, %d ok); the day\'s save marker requested; the '
                                                        'clean unit will run on the retained lane and trigger the resume'
                                                        % (totals.get('pinned', 0), totals.get('ok', 0))))


# -------------------------------------------------------------------------------------------- the detached unit

def queue_dir():
    forced = os.environ.get('FRANKIE_QUEUE_DIR')
    if forced:
        return Path(forced)
    try:
        import frankie_box_frankie_queue as Q
        return Q.QUEUE
    except ImportError:
        return Path('/opt/frankie-box/work/frankie-queue')


def day_state(run, day):
    """(state, finish state, marker path) of the day's ROOT-line entry; (None, None, None) without one."""
    doc = _load(queue_dir() / 'root.json')
    for entry in (doc or {}).get('entries') or []:
        if entry.get('run') == run and entry.get('day') == day:
            return entry.get('state'), (entry.get('finish') or {}).get('state'), (entry.get('owner') or {}).get('marker')
    return None, None, None


def is_saved(run, day):
    state, finish, _ = day_state(run, day)
    return state == 'saved' or (state == 'done' and finish == 'saved')


def wait_saved(run, day, bound, say=print):
    deadline = time.monotonic() + bound
    while True:
        if is_saved(run, day):
            return True
        if time.monotonic() >= deadline:
            return False
        say('waiting for %s %s to be recorded saved (%s)' % (run, day, day_state(run, day)))
        time.sleep(WAIT_POLL_SECONDS)


def successor_running(run, day, own_unit=None):
    """Processes or workers already working this run/day (the successor must not be started twice). Review 2026-10-08
    finding 7 (Patch G): a ROOT-line worker's argv is `frankie_box_frankie_queue.py --action worker ... --scope RUN:DAYS`
    and its unit is frankie-queue-<line>-<epoch>, so the match is on the worker's --scope (and the line's lock through
    frankie_box_frankie_queue.worker_state), besides the stage children (frankie_box_experiment*) naming run and day."""
    found = []
    try:
        out = subprocess.run(['pgrep', '-af', 'frankie_box_experiment|frankie_box_frankie_queue.py --action worker'],
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            pid = line.split(' ', 1)[0]
            if pid == str(os.getpid()) or 'stage_handoff' in line:
                continue
            if '--action worker' in line:
                scope = line.split('--scope', 1)[1].split()[0] if '--scope' in line else ''
                if scope.startswith(run + ':') and day in scope.split(':', 1)[1].split(','):
                    found.append(line[:200])
            elif run in line and day in line:
                found.append(line[:200])
    except (OSError, IndexError):
        pass
    try:
        import frankie_box_frankie_queue as Q
        for line_name in Q.LINES:
            status, held = Q.worker_state(line_name)
            scope = (status or {}).get('scope') or ''
            if held and scope.startswith(run + ':') and day in scope.split(':', 1)[1].split(','):
                found.append('%s line worker holds its lock (pid %s, scope %s)' % (line_name, (status or {}).get('pid'), scope))
    except Exception:  # noqa: BLE001 - no queue on this host (toys): the process check above stands
        pass
    return found


def queue_sh(code_root):
    return os.environ.get('FRANKIE_QUEUE_SH') or str(Path(code_root) / 'deploy/aws/box/frankie_box_frankie_queue.sh')


def trigger(out_dir, run, day, stage, code_root, commit, say=print):
    """The stage's last task: resume + kick on the LAUNCHING checkout, exactly once, only while the day is saved."""
    out_dir = Path(out_dir)
    receipt_path = out_dir / 'trigger.json'
    base = dict(schema=TRIGGER_SCHEMA, run=run, day=day, stage=stage, code_root=str(code_root), commit=commit, at=time.time(),
                queue_sh=queue_sh(code_root))
    try:
        with open(out_dir / 'trigger.fired', 'x') as handle:
            handle.write('%s %s %s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), run, day, stage))
    except FileExistsError:
        earlier = _load(receipt_path)
        return dict(base, status='already_fired', earlier=earlier,
                    reason='the trigger fired before for this boundary (trigger.fired stands); nothing done')
    if not is_saved(run, day):
        return _write(receipt_path, dict(base, status='refused', reason='the day is not in state saved (%s); no resume'
                                                                        % (day_state(run, day),)))
    busy = successor_running(run, day)
    if busy:
        return _write(receipt_path, dict(base, status='refused', reason='a process or unit for %s %s already exists: %s'
                                                                        % (run, day, busy)))
    env = dict(os.environ, CODE_ROOT=str(code_root), MARKETS_SHA=commit, RUN=run, DAY=day)
    steps = []
    for action, extra in (('resume', {}), ('kick', dict(LINE='root', SCOPE='%s:%s' % (run, day)))):
        result = subprocess.run([queue_sh(code_root)], env=dict(env, ACTION=action, **extra), capture_output=True, text=True)
        steps.append(dict(action=action, exit_code=result.returncode, stdout=result.stdout[-4000:], stderr=result.stderr[-2000:]))
        say('%s %s %s: %s exit %d' % (stage, run, day, action, result.returncode))
        if result.returncode != 0:
            return _write(receipt_path, dict(base, status='failed', steps=steps,
                                             reason='%s exited %d; the day stays as it is (an operator resumes by hand)'
                                                    % (action, result.returncode)))
    return _write(receipt_path, dict(base, status='done', steps=steps,
                                     reason='resumed and kicked on %s (%s); the queue re-admits the day on its retained CPUs '
                                            'and its root step reuses the finished stages' % (code_root, commit[:12])))


def _note_beside_marker(marker, body):
    if marker:
        try:
            _write(str(marker) + '.clean.json', body)
        except OSError:
            pass


def clean_action(args):
    """The detached unit: keep the box, wait for the saved state, clean, trigger. Exit 0 done, 3 failed."""
    import frankie_box_root_move as M
    out_dir = Path(args.handoff_dir)
    clean_dir = out_dir / 'clean'
    clean_dir.mkdir(parents=True, exist_ok=True)
    say = lambda t: print('%s %s' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), t), flush=True)
    bound = float(os.environ.get('FRANKIE_HANDOFF_WAIT_SAVED_SECONDS') or WAIT_SAVED_SECONDS)
    _, _, marker = day_state(args.run, args.day)
    base = dict(schema=TRIGGER_SCHEMA, run=args.run, day=args.day, stage=args.stage, code_root=args.code_root,
                commit=args.commit, at=time.time())
    # in progress, beside the day's marker: frankie_box_experiment.box_in_use counts it (and this unit's process) as
    # the box in use, so the worker ending saved never clears KeepRunning mid-clean; the tag itself is re-set true at
    # the end only when a successor was triggered (the resumed day then owns it)
    _note_beside_marker(marker, dict(base, status='running', pid=os.getpid(), reason='the clean unit is running'))
    if not wait_saved(args.run, args.day, bound, say):
        body = dict(base, status='failed', reason='the day was not recorded saved within %d s (%s); nothing cleaned, no resume'
                                                   % (bound, (day_state(args.run, args.day),)))
        _write(out_dir / 'trigger.json', body)
        _note_beside_marker(marker, body)
        return 3
    import frankie_box_root_validate as V
    roots = [Path(r) for r in args.root]
    if STAGES.get(args.stage, {}).get('collector') == 'root' and roots:
        pins = V.collect_pins(roots[0], args.run_dir)
    else:
        pins = V.collect_generic(args.receipt, root=roots[0] if roots else None, only_under=roots) if args.receipt else V.Pins('/')
    expected = {real: job['expected'] for real, job in pins.jobs.items()}
    cpus = sorted(V._parse_cpus(args.cpus)) if args.cpus else None
    archive_root = Path(os.environ.get('FRANKIE_ARCHIVE_ROOT') or M.ARCHIVE_ROOT)
    box_root = Path(os.environ.get('FRANKIE_BOX_ROOT') or M.BOX_ROOT)
    os.environ['FRANKIE_CLEAN_LABEL'] = 'run=%s day=%s stage=%s' % (args.run, args.day, args.stage)   # the fstab line's tag
    receipt = M.clean(roots, expected, out_dir=clean_dir, cpus=cpus, guarded=STAGES.get(args.stage, {}).get('guarded', ()),
                      floor=floor_bytes(), archive_root=archive_root, box_root=box_root, say=say,
                      native_complete=native_complete(args.stage, roots))
    receipt.update(stage=args.stage, run=args.run, day=args.day, key=args.key, switch='on' if on() else 'off')
    _write(clean_dir / 'clean-receipt.json', receipt)
    say('clean %s %s %s: %s, %d moved, %d failed, %d bytes freed' % (
        args.stage, args.run, args.day, receipt['status'], receipt.get('moved', 0), len(receipt.get('failed') or []),
        receipt.get('bytes_freed', 0)))
    if receipt['status'] != 'done':
        body = dict(base, status='failed', clean=dict(receipt=str(clean_dir / 'clean-receipt.json'), failed=receipt.get('failed')),
                    reason='the clean failed (%s); the day stays saved; no resume; an operator resumes by hand'
                           % '; '.join('%s: %s' % (f['old_path'], f['reason']) for f in receipt.get('failed') or []))
        _write(out_dir / 'trigger.json', body)
        _note_beside_marker(marker, body)
        return 3
    result = trigger(out_dir, args.run, args.day, args.stage, args.code_root, args.commit, say)
    result['clean'] = dict(receipt=str(clean_dir / 'clean-receipt.json'), manifest=receipt.get('manifest'),
                           moved=receipt.get('moved'), bytes_freed=receipt.get('bytes_freed'),
                           archives=[dict(old_path=i['old_path'], new_path=i['new_path'], bytes=i.get('bytes_archived', i.get('bytes_copied')),
                                          sha256=i.get('sha256') or ('per file: %d files in the moved-manifest' % len(i.get('files') or [])),
                                          kind=i['kind']) for i in receipt['items']
                                     if i['kind'] in ('move', 'archive', 'bind_mount') and i.get('status') == 'done'])
    _write(out_dir / 'trigger.json', result)
    _note_beside_marker(marker, dict(result, note='the clean unit\'s outcome beside the day\'s marker'))
    # the S3 Glacier second copy (call (f): both), AFTER the trigger so the day's chain never waits for it, in its OWN
    # detached unit with no lane pin, under nice -n 19 ionice -c 3 (review finding 9, Patch I: the resumed day owns the
    # retained lane and reads the same volume); its receipt lands beside the clean receipt; a refusal (switch off, no
    # bucket, above the cap) is recorded there, never a failure
    try:
        started = start_upload_unit(args, clean_dir, say)
        say('s3 second copy: unit started (%s)' % json.dumps(started, sort_keys=True, default=str))
    except Exception as error:  # noqa: BLE001 - never the clean's outcome
        say('s3 second copy: unit not started (%s: %s)' % (type(error).__name__, error))
    if result['status'] == 'done' and not os.environ.get('FRANKIE_HANDOFF_NO_KEEP_RUNNING'):
        try:
            import frankie_box_experiment as X
            X.keep_running(args.run, True, '%s clean of %s done; the day resumed and kicked on %s (it owns the box now)'
                           % (args.stage, args.day, args.commit[:12]), 'frankie_box_stage_handoff.py clean', log=say)
        except Exception as error:  # noqa: BLE001 - a cost guard, never the clean's outcome
            say('keep-running: not set (%s: %s)' % (type(error).__name__, error))
    return 0 if result['status'] == 'done' else 3


def start_upload_unit(args, clean_dir, say=print):
    """The Glacier second copy as its own detached unit: unpinned (no taskset), nice -n 19 ionice -c 3, the launching
    checkout's module with --action upload; recorded in <clean dir>/s3-upload-unit.json."""
    clean_dir = Path(clean_dir)
    log_path = clean_dir / 's3-upload.log'
    argv = [_python(), '-B', str(Path(args.code_root) / 'deploy/aws/box/frankie_box_stage_handoff.py'), '--action', 'upload',
            '--run', args.run, '--day', args.day, '--stage', args.stage, '--handoff-dir', str(args.handoff_dir),
            '--code-root', str(args.code_root), '--commit', args.commit]
    env = dict(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1', PYTHONPATH=str(args.code_root), HOME=os.environ.get('HOME') or '/root')
    for name in ('FRANKIE_ARCHIVE_S3', 'FRANKIE_ARCHIVE_BUCKET', 'FRANKIE_ARCHIVE_PREFIX', 'FRANKIE_ARCHIVE_REGION',
                 'FRANKIE_ARCHIVE_S3_FAKE', 'FRANKIE_ARCHIVE_S3_MAX_BYTES', 'FRANKIE_ARCHIVE_ROOT', 'FRANKIE_HANDOFF_PYTHON',
                 'FRANKIE_HANDOFF_DETACH'):
        if os.environ.get(name):
            env[name] = os.environ[name]
    gentle = (['nice', '-n', '19'] if shutil.which('nice') else []) + (['ionice', '-c', '3'] if shutil.which('ionice') else [])
    how = None
    if shutil.which('systemd-run') and os.environ.get('FRANKIE_HANDOFF_DETACH', 'systemd') != 'session':
        unit = 'frankie-upload-%s-%s-%s-%d' % (args.stage, args.run, args.day, int(time.time()))
        cmd = ['systemd-run', '--unit', unit, '--collect', '-p', 'StandardOutput=append:%s' % log_path,
               '-p', 'StandardError=append:%s' % log_path, '-p', 'KillMode=mixed', '-p', 'Nice=19', '-p', 'IOSchedulingClass=idle'] + \
              [x for k, v in sorted(env.items()) for x in ('-E', '%s=%s' % (k, v))] + argv
        code = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
        how = dict(method='systemd-run', unit=unit, exit_code=code, nice=19, ioclass='idle')
    if how is None or how['exit_code'] != 0:
        with open(log_path, 'ab') as out:
            proc = subprocess.Popen(gentle + argv, env=dict(os.environ, **env), stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        how = dict(method='new session', pid=proc.pid, prefix=gentle, systemd_run=how)
    _write(clean_dir / 's3-upload-unit.json', dict(schema='FRANKIE_ROOT_MOVE_S3_UNIT_V1', at=time.time(), how=how, argv=argv,
                                                  rule='unpinned, nice 19 / idle I/O class, after the trigger; the chain never waits'))
    return how


def upload_action(args):
    """The upload unit's body: the clean receipt's items -> frankie_box_root_move.upload_archives (Glacier second copy)."""
    import frankie_box_root_move as M
    clean_dir = Path(args.handoff_dir) / 'clean'
    receipt = _load(clean_dir / 'clean-receipt.json')
    if not receipt:
        print('no clean receipt under %s; nothing to upload' % clean_dir, flush=True)
        return 3
    archive_root = Path(os.environ.get('FRANKIE_ARCHIVE_ROOT') or M.ARCHIVE_ROOT)
    fake = os.environ.get('FRANKIE_ARCHIVE_S3_FAKE')
    s3 = M.upload_archives(receipt['items'], out_dir=clean_dir, archive_root=archive_root,
                           transport=_fake_transport(fake) if fake else None,
                           say=lambda t: print('%s %s' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), t), flush=True))
    print('s3 second copy: %s (%s objects; %s)' % (s3.get('status'), s3.get('uploaded', 0), s3.get('reason') or s3.get('bucket')), flush=True)
    return 0 if s3.get('status') in ('done', 'refused') else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    parser.add_argument('--action', required=True, choices=('clean', 'trigger', 'upload'))
    parser.add_argument('--run', required=True)
    parser.add_argument('--day', required=True)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--key')
    parser.add_argument('--handoff-dir', required=True)
    parser.add_argument('--run-dir')
    parser.add_argument('--code-root', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--root', action='append', default=[])
    parser.add_argument('--receipt', action='append', default=[])
    parser.add_argument('--cpus')
    args = parser.parse_args(argv)
    if args.action == 'upload':
        return upload_action(args)
    if args.action == 'trigger':
        result = trigger(args.handoff_dir, args.run, args.day, args.stage, args.code_root, args.commit)
        print(json.dumps(result, indent=1, sort_keys=True, default=str))
        return 0 if result['status'] in ('done', 'already_fired') else 3
    return clean_action(args)


if __name__ == '__main__':
    sys.exit(main())
