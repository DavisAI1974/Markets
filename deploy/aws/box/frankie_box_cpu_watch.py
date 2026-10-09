"""The CPU WATCHDOG (Greg, session 8, 2026-10-08: "Is there a generic cpu call code that we could do so if we forget a
place it just kicks in after a couple of minutes?"; "we would want to increase helpers too when possible"; the choice is
by WALL-CLOCK to reach the planned CPU set, never by dollars: "it must never pick a 4.5 h run over a 1 h run to save a
dollar").

EVENT-DRIVEN (Greg, 2026-10-09: no coded wait times; frankie_box_wake): a pass runs when the booking ledger changes
(a booking made, grown, retained, released, a step's claim or attach), when a booked process (a booking holder or a day's
step) or a watched render exits (pidfd), when the queue writes a wake file (<queue>/wake: a stage status, a queue entry's
state, a save marker) or when a kick writes one into <work dir>/wake. No interval and no lifetime cap: the watch ends when
no booking is live (no day's process runs), no render runs and no resize request is open, and the next kick starts it
again. One pass: read the bookings (frankie_box_cores.live_bookings), every Frankie process's
affinity (os.sched_getaffinity per thread over the process tree of each booking's holder and steps), the box's live core
map and the resolver's answer for the running step (frankie_box_cores.lane_for), and RECORD every process that sits
outside its booking, every step root that holds fewer CPUs than its lane, every Frankie process with no booking, every
lane CPU no thread of the tree can reach (a pool that sized itself small), and every running step whose PLANNED lane is
wider than the lane it RUNS on. The record is /opt/frankie-box/work/cpu-watch/<stamp>.json (FRANKIE_CPU_WATCH_V1) plus
one line in /opt/frankie-box/work/cpu-watch/watch.log. Read-only by default.

CORRECTIONS, in order of wall-clock cost, each ON BY DEFAULT (Greg, session 8, decision 4: off only when set to off) and each
written on the record with the estimate behind it; every kick of a queue line starts the loop (frankie_box_frankie_queue.kick
-> frankie_box_cpu_watch.sh ACTION=loop, idempotent under its own unit and lock), so it runs without anyone remembering:
  FRANKIE_CPU_WATCH_CORRECT=on   RE-PIN (instant): a thread outside its booking is set to affinity AND booking (the whole
                                 booking when nothing is left); a step root narrower than its lane is widened to the lane.
                                 Workers pinned to ONE CPU inside their lane are by design (frankie_box_lane_pin) and are
                                 never touched; an unbooked process has no planned set and is only listed.
                                 THE LIMIT, stated here and on every record: re-pinning widens affinity but cannot grow a
                                 pool that sized itself at start (its helper count is fixed), so a sizing mistake is
                                 caught only by the resolver at the step's start, or by the resize below.
  FRANKIE_CPU_WATCH_RESIZE=on    RESIZE by the step's OWN lawful stop and resume, never a kill, only when re-pin cannot
                                 reach the plan (the running pool is smaller than the planned lane by RESIZE_RATIO 1.5x or
                                 more) and the step declares a resume mechanism (RESUMABLE, named from the code):
      root           the day-bound save marker (frankie_box_frankie_queue request_save): ROOT stops at its next save
                     point with SystemExit 75, the entry reads saved, the booking is RETAINED; then grow the booking to
                     the plan (frankie_box_cores grow), resume_owner + kick on the NEWEST STAGED checkout on the box
                     (session 9: newest_staged_checkout; never the owner's older checkout; none staged = refused and
                     recorded, nothing grown or resumed; both commits on the request); the ROOT resumes at its
                     last save point and its pools size from the grown lane (FRANKIE_LANE_CPUS). Redone: the work since
                     that save point (the ROOT's own progress since its last save, read from its probe when readable).
      digest-render  FRANKIE_DIGEST_STOP_FILE (frankie_box_digest_parallel.step checks it between passes): the render
                     stops at the NEXT PASS BOUNDARY with exit 75 after its per-pass checkpoint (scratch/passes.pkl),
                     then the same render command is started again on the resolver's lane (the wrapper reads
                     plan --step digest-render) and resumes at the first unsaved pass. Redone: nothing; waited: the pass
                     in flight finishes first.
      everything else (teacher, classroom, data, search, lessons, exchange, voice, jev, survivors, validate, ingest)
                     NOT RESIZABLE here: no stop-and-resume mechanism is named for it in this audit; listed only.
    The decision is pure (resize_decision): planned lane, running lane, the ratio, the estimated remaining wall-clock on
    each (the stage heartbeat's rate when readable; unknown = "the plan is the full lane", Greg), the restart cost and
    the work redone since the last checkpoint, all on the record, so a human sees it picked the faster path. Cost in
    dollars is NOT an input anywhere here.
    A resize is a state machine across passes (a request file resize-<booking>.json): pass N writes the marker, a later
    pass sees the step stopped and triggers grow + resume + kick (ROOT) or the restart (render); every transition on
    the record; a request stays open until its step stops or exits (never dropped on a timer). An open request is
    continued from the request itself on every pass (its step has stopped by then, so the pass has no finding for it).

Standard library only (python -I -S). Its own flock (/opt/frankie-box/work/cpu-watch/.lock): two watchers never run a
pass at once. Nothing here kills, signals or re-sizes a running pool; nothing stops a process except through its own
save/stop mechanism. Placement only: no value, order, hash or identity depends on where a process runs.

CLI: frankie_box_cpu_watch.py [--once | --loop] [--max-seconds N] [--work-dir D] [--window 1.0]
     frankie_box_cpu_watch.py --kick-wake [--work-dir D]: write the kick's wake, then exit 0 when a watcher holds the
     lock (it re-checks on that wake) or 4 when none does (the caller starts one). The wake is written BEFORE the lock
     test and an ending watcher releases its lock BEFORE its last event check, so a kick never falls between them.
     exit 0 = pass done / the watch ended (findings or not; the record says), 3 = another watcher holds the lock,
     2 = refused.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import frankie_box_cores as C  # noqa: E402

SCHEMA = 'FRANKIE_CPU_WATCH_V1'
WORK_DIR = Path('/opt/frankie-box/work/cpu-watch')
QUEUE_WAKE = Path('/opt/frankie-box/work/frankie-queue/wake')   # frankie_box_frankie_queue.wake_dir()
KICK_WAKE = 'wake'                 # <work dir>/wake: a kick's wake for a running watcher
NOT_LIVE_EXIT = 4                  # --kick-wake: no watcher holds the lock
CORRECT_ENV = 'FRANKIE_CPU_WATCH_CORRECT'
RESIZE_ENV = 'FRANKIE_CPU_WATCH_RESIZE'
RESIZE_RATIO = 1.5                 # the planned lane must be at least this many times the running lane
RESTART_SECONDS = dict(root=300.0, digest_render=120.0)   # the cost of the stop + start itself (process start, reads); an
                                                          # estimate, on the record, never a measurement
REPIN_LIMIT = ('re-pinning widens affinity but cannot grow a pool that sized itself at start (its helper count is fixed): '
               'a sizing mistake is caught by the resolver at the step\'s start or by a lawful resize, never by re-pin')
# the steps with a named stop-and-resume mechanism (from the code; see the module note); every other step is NOT resizable
RESUMABLE = {
    'root': dict(mechanism='day-bound save marker (frankie_box_frankie_queue.request_save; ROOT SystemExit 75 at its next '
                           'save point; the booking is retained)',
                 resume='frankie_box_cores grow --size <plan>, then frankie_box_frankie_queue resume + kick on the newest '
                        'staged checkout (newest_staged_checkout)',
                 redo='the ROOT\'s work since its last save point'),
    'digest_render': dict(mechanism='FRANKIE_DIGEST_STOP_FILE, read by frankie_box_digest_parallel.step between passes; exit 75 '
                                    'after the per-pass checkpoint (scratch/passes.pkl)',
                          resume='the same render command again (frankie_box_render_digest.sh; the lane from plan --step '
                                 'digest-render); resumes at the first unsaved pass',
                          redo='nothing; the pass in flight finishes before the stop'),
}


# ------------------------------------------------------------------------------------------------------ pure parts

def resize_decision(step, planned, running, resumable, remaining_seconds=None, redo_seconds=0.0, restart_seconds=0.0):
    """The WALL-CLOCK decision (Greg: never dollars). planned/running = CPU lists. Returns dict(choice, reason,
    ratio, planned_lane, running_lane, remaining_on_running, remaining_on_planned, redo_seconds, restart_seconds,
    resumable). choice: 'repin' (the plan is reachable by affinity alone: same size), 'keep' (the plan is wider but
    under RESIZE_RATIO: the gain is below the bar; re-pin covers what it can), 'not_resizable' (wider by the bar, no
    named mechanism), 'resize' (wider by the bar, resumable, and faster or remaining unknown), 'keep_faster' (wider by
    the bar, resumable, but the remaining work on the running lane ends sooner than stop + redo + restart + the rest on
    the planned lane)."""
    planned, running = sorted(set(planned)), sorted(set(running))
    out = dict(step=step, planned_lane=C.cpu_list(planned), planned_size=len(planned), running_lane=C.cpu_list(running),
               running_size=len(running), resumable=bool(resumable), redo_seconds=redo_seconds, restart_seconds=restart_seconds,
               remaining_on_running=remaining_seconds, remaining_on_planned=None, basis='wall-clock only; cost is not an input')
    if not running or not planned:
        return dict(out, choice='keep', ratio=None, reason='no lane to compare')
    ratio = len(planned) / float(len(running))
    out['ratio'] = round(ratio, 3)
    if len(planned) <= len(running):
        return dict(out, choice='repin', reason='the planned lane is not wider than the running one: affinity alone reaches it')
    if ratio < RESIZE_RATIO:
        return dict(out, choice='keep', reason='planned/running %.2f is under the %.1fx bar: re-pin covers what it can, the '
                                               'pool keeps its size' % (ratio, RESIZE_RATIO))
    if not resumable:
        return dict(out, choice='not_resizable', reason='the planned lane is %.2fx the running one but %s names no stop-and-'
                                                        'resume mechanism; listed, nothing done' % (ratio, step))
    if remaining_seconds is None:
        return dict(out, choice='resize', reason='the planned lane is %.2fx the running one and the remaining work is not '
                                                 'measurable here: the plan is the full lane (Greg), resize' % ratio)
    on_planned = remaining_seconds / ratio + redo_seconds + restart_seconds
    out['remaining_on_planned'] = round(on_planned, 1)
    if on_planned < remaining_seconds:
        return dict(out, choice='resize', reason='faster on the plan: %.0f s left on %d CPUs vs %.0f s (= %.0f s / %.2f + '
                                                 '%.0f s redone + %.0f s restart) on %d CPUs'
                                                 % (remaining_seconds, len(running), on_planned, remaining_seconds, ratio,
                                                    redo_seconds, restart_seconds, len(planned)))
    return dict(out, choice='keep_faster', reason='the running lane finishes sooner: %.0f s left on %d CPUs vs %.0f s on %d '
                                                  'after the stop, %.0f s redone and %.0f s restart'
                                                  % (remaining_seconds, len(running), on_planned, len(planned), redo_seconds,
                                                     restart_seconds))


def step_of(booking):
    """(stage, pid) of the booking's live step process, from the ledger's own pid roles ('step <stage> (...)'), else
    (None, holder pid)."""
    holder = None
    for p in booking.get('pids') or []:
        if not C.alive(p):
            continue
        role = p.get('role') or ''
        if role.startswith('step '):
            return role.split(' ', 2)[1], p['pid']
        if role == 'booking holder':
            holder = p['pid']
    return None, holder


def tree_of(procs, roots):
    """The pids of `roots` and every descendant that is alive in procs."""
    roots = [r for r in roots if r in procs]
    return set(roots) | C.descendants(procs, roots)


def audit(bookings, procs, affinity_of, threads_of, cmap, online, plans=None, resumable=None, remaining=None):
    """PURE: the findings of one pass. bookings = live/retained ledger records; procs = {pid: info} (C.processes shape:
    ppid, cmdline, cwd, exe); affinity_of(tid) -> set of CPUs or None; threads_of(pid) -> [tid]; cmap = core_map();
    plans = {booking id: the resolver's planned CPU list for its running step} (None = the booking itself);
    resumable = {stage: RESUMABLE entry or None}; remaining = {booking id: seconds or None}.
    Returns dict(findings=[...], bookings=[...], unbooked=[...], repin_limit)."""
    findings, summary, claimed = [], [], set()
    plans, resumable, remaining = plans or {}, resumable if resumable is not None else RESUMABLE, remaining or {}
    for b in bookings:
        cpus = set(b.get('cpus') or [])
        roots = [p['pid'] for p in b.get('pids') or [] if C.alive(p)]
        tree = tree_of(procs, roots)
        claimed |= tree
        stage, step_pid = step_of(b)
        reach = set()
        entry = dict(booking=b['booking'], kind=b.get('kind'), run=b.get('run'), day=b.get('day'), cpus=C.cpu_list(cpus),
                     size=len(cpus), retained=bool(b.get('_retained')) and not b.get('_alive'), stage=stage, step_pid=step_pid,
                     processes=len(tree), threads=0)
        for pid in sorted(tree):
            for tid in threads_of(pid):
                aff = affinity_of(tid)
                if aff is None:
                    continue
                entry['threads'] += 1
                reach |= aff & cpus
                outside = sorted(aff - cpus)
                if outside:
                    findings.append(dict(kind='outside_booking', booking=b['booking'], pid=pid, tid=tid, affinity=C.cpu_list(aff),
                                         outside=C.cpu_list(outside), command=(procs.get(pid) or {}).get('cmdline', '')[:120],
                                         correction=dict(set_to=C.cpu_list((aff & cpus) or cpus))))
                elif pid in roots and len(aff) < len(cpus) and b.get('kind') != 'render':
                    # (a digest render pins its own coordinator thread to one CPU of its lane by design, as lane_pin
                    # workers are: never widened)
                    findings.append(dict(kind='narrower_than_lane', booking=b['booking'], pid=pid, tid=tid, affinity=C.cpu_list(aff),
                                         lane=C.cpu_list(cpus), command=(procs.get(pid) or {}).get('cmdline', '')[:120],
                                         correction=dict(set_to=C.cpu_list(cpus))))
        if tree and cpus - reach:
            findings.append(dict(kind='lane_cpus_unreachable', booking=b['booking'], cpus=C.cpu_list(cpus - reach),
                                 count=len(cpus - reach), note='no thread of the booking\'s tree can run there: a pool sized '
                                                                 'smaller than the lane, or a step between pools; ' + REPIN_LIMIT))
        planned = plans.get(b['booking'])
        if planned is not None and tree:
            planned = sorted(set(planned))
            if set(planned) != cpus:
                key = 'digest_render' if stage == 'digest-render' else (stage or '')
                mech = resumable.get(key)
                decision = resize_decision(stage or 'unknown', planned, sorted(cpus), bool(mech), remaining.get(b['booking']),
                                           restart_seconds=RESTART_SECONDS.get(key, 0.0))
                findings.append(dict(kind='plan_wider_than_lane' if len(planned) > len(cpus) else 'plan_differs', booking=b['booking'],
                                     stage=stage, planned=C.cpu_list(planned), running=C.cpu_list(cpus), decision=decision,
                                     mechanism=mech, note=REPIN_LIMIT))
        summary.append(entry)
    unbooked = []
    for pid, info in sorted(procs.items()):
        if pid in claimed or not C.is_frankie(info):
            continue
        if C.ancestors(procs, pid) & claimed:
            continue
        affs = [affinity_of(t) for t in threads_of(pid)]
        affs = [a for a in affs if a is not None]
        union = set().union(*affs) if affs else set()
        unbooked.append(dict(pid=pid, command=info.get('cmdline', '')[:120], affinity=C.cpu_list(union), threads=len(affs)))
        findings.append(dict(kind='unbooked', pid=pid, command=info.get('cmdline', '')[:120], affinity=C.cpu_list(union),
                             note='a Frankie process outside every booking: no planned set is known for it; listed only'))
    return dict(findings=findings, bookings=summary, unbooked=unbooked, repin_limit=REPIN_LIMIT,
                core_map=dict(nproc=cmap['nproc'], physical_cores=cmap['physical_cores'], threads_per_core=cmap['threads_per_core'],
                              basis=cmap['basis']))


def apply_repins(findings, setaffinity):
    """CORRECT=on: re-pin (affinity only) for every outside_booking / narrower_than_lane finding; the outcome on each."""
    done = []
    for f in findings:
        if f['kind'] not in ('outside_booking', 'narrower_than_lane'):
            continue
        target = sorted(C.parse_list(f['correction']['set_to']))
        try:
            setaffinity(f['tid'], set(target))
            f['correction']['applied'] = True
        except OSError as error:
            f['correction']['applied'] = False
            f['correction']['error'] = '%s: %s' % (type(error).__name__, error)
        done.append(dict(pid=f['pid'], tid=f['tid'], set_to=f['correction']['set_to'], applied=f['correction']['applied']))
    return done


# ------------------------------------------------------------------------------------------------------ live parts

def live_affinity(tid):
    try:
        return set(os.sched_getaffinity(tid))
    except (OSError, AttributeError):
        return None


def live_threads(pid):
    try:
        return sorted(int(t) for t in os.listdir('/proc/%d/task' % pid))
    except OSError:
        return []


def planned_lanes(bookings, cmap):
    """{booking id: the resolver's planned CPU list for its running step} (classroom: FRANKIE_CLASSROOM_CPUS may widen it;
    every other stage: the booking itself); a refusal is recorded as the plan being the booking, with the reason."""
    out, reasons = {}, {}
    for b in bookings:
        if b.get('kind') != 'day-run':
            continue
        stage, _pid = step_of(b)
        step = 'classroom-day' if stage == 'classroom' else 'step-inside'
        try:
            plan = C.lane_for(step, run=b.get('run'), day=b.get('day'), bookings=bookings, cmap=cmap, held=b)
            out[b['booking']] = plan['cpus']
        except C.PlanRefused as error:
            out[b['booking']] = sorted(b.get('cpus') or [])
            reasons[b['booking']] = str(error)
    return out, reasons


def remaining_seconds(booking):
    """The running step's estimated remaining wall-clock from its stage heartbeat (<run dir>/days/<day>/progress/<stage>.jsonl:
    units_done, units_total, rate) when readable; None otherwise (= unknown, on the record as such)."""
    stage, _ = step_of(booking)
    run, day = booking.get('run'), booking.get('day')
    if not (stage and run and day):
        return None
    path = Path('/opt/frankie-box/work/experiment') / run / 'days' / day / 'progress' / ('%s.jsonl' % stage)
    try:
        last = None
        with open(path, 'rb') as f:
            for line in f:
                if line.strip():
                    last = line
        row = json.loads(last) if last else None
    except (OSError, ValueError):
        return None
    if not row:
        return None
    done, total, rate = row.get('units_done'), row.get('units_total'), row.get('rate')
    if done is None or total is None or not rate:
        return None
    try:
        return max(0.0, (float(total) - float(done)) / float(rate))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


CODE_PARENT = Path('/opt/frankie-box/code')


def newest_staged_checkout(code_parent=CODE_PARENT):
    """The newest staged checkout on the box: dict(code_root, commit, staged_at, receipt) of the
    <code_parent>/<40-hex sha>-<run id>/markets whose staging-receipt.json says status 'staged' for that same commit and
    code_root (frankie_box_stage_code.stage writes it last), newest by the receipt's mtime (the order
    frankie_box_cleanup_code.sh keeps as 'newest'). Raises ValueError naming what was seen when none qualifies."""
    import re
    seen, best = [], None
    parent = Path(code_parent)
    for path in sorted(parent.iterdir()) if parent.is_dir() else []:
        m = re.fullmatch(r'([0-9a-f]{40})-([A-Za-z0-9_-]{1,96})', path.name)
        if not m or path.is_symlink() or not path.is_dir():
            continue
        receipt = path / 'staging-receipt.json'
        try:
            value = json.loads(receipt.read_bytes())
            at = receipt.stat().st_mtime
        except (OSError, ValueError):
            seen.append('%s: no readable staging-receipt.json' % path.name)
            continue
        code_root = path / 'markets'
        if not (value.get('status') == 'staged' and value.get('commit') == m.group(1)
                and value.get('code_root') == str(code_root) and code_root.is_dir()):
            seen.append('%s: receipt status %s commit %s' % (path.name, value.get('status'), str(value.get('commit'))[:12]))
            continue
        if best is None or at > best['staged_at']:
            best = dict(code_root=str(code_root), commit=m.group(1), staged_at=at, receipt=str(receipt))
    if best is None:
        raise ValueError('no staged checkout under %s (%s)' % (parent, '; '.join(seen) or 'nothing there'))
    return best


def resize_requests(work_dir):
    out = {}
    for path in sorted(Path(work_dir).glob('resize-*.json')):
        try:
            out[path] = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
    return out


def drive_resize(finding, work_dir, record, actions):
    """RESIZE=on: the lawful stop-and-resume for a plan_wider_than_lane finding whose decision is 'resize'. actions =
    dict(request_save(run, day) -> text, owner_state(run, day) -> 'running'|'saved'|..., grow(booking, size) -> outcome,
    resume(run, day) -> text, kick_target(run, day) -> dict (owner and newest staged commits; raises when none is staged),
    kick(run, day, target) -> text, stop_render(pid) -> path, render_stopped(pid) -> bool,
    restart_render(request) -> text); every call's outcome is appended to record['resize']. The request file carries
    the state so the next pass continues it."""
    b = finding['booking']
    path = Path(work_dir) / ('resize-%s.json' % b)
    req = resize_requests(work_dir).get(path)
    stage = finding.get('stage')
    now = time.time()
    if req is None:
        req = dict(schema='FRANKIE_CPU_WATCH_RESIZE_V1', booking=b, stage=stage, planned=finding['planned'], running=finding['running'],
                   decision=finding['decision'], requested_at=now, state='requested', log=[], run=finding.get('run'),
                   day=finding.get('day'))
        try:
            if stage == 'root':
                req['log'].append(dict(at=now, did='request_save', out=actions['request_save'](finding['run'], finding['day'])))
            elif stage == 'digest-render':
                # the stopped render's CODE_ROOT / MARKETS_SHA / OUTPUT_ROOT, read before the stop so the restart has them
                req['step_pid'] = finding.get('step_pid')
                req['environment'] = actions['render_environment'](finding['step_pid'])
                req['log'].append(dict(at=now, did='stop_render', out=str(actions['stop_render'](finding['step_pid']))))
            else:
                req['log'].append(dict(at=now, did='none', out='no mechanism for %s' % stage))
                req['state'] = 'not_resizable'
        except Exception as error:  # noqa: BLE001 - the record carries it; nothing else is tried this pass
            req['log'].append(dict(at=now, did='request', error='%s: %s' % (type(error).__name__, error)))
            req['state'] = 'request_failed'
        C.write_json(path, req)
        record['resize'].append(dict(req, step='requested'))
        return
    stage = req.get('stage') or stage      # the request's step: once it has stopped, the pass sees no step for it
    if req.get('state') in ('done', 'not_resizable', 'request_failed', 'stale'):
        record['resize'].append(dict(booking=b, state=req['state'], note='nothing more to do'))
        return
    try:
        if stage == 'root':
            state = actions['owner_state'](finding['run'], finding['day'])
            req['log'].append(dict(at=now, did='owner_state', out=state))
            if state == 'saved':
                # session 9: the kick goes at the NEWEST staged checkout (never the owner's older one); with none staged
                # the resize is refused here, recorded, and nothing is grown or resumed (the next pass tries again)
                try:
                    target = actions['kick_target'](finding['run'], finding['day'])
                except Exception as error:  # noqa: BLE001 - recorded; the request stays for the next pass
                    req['log'].append(dict(at=now, did='refused', out='no staged checkout to kick at: %s: %s'
                                                                     % (type(error).__name__, error)))
                    target = None
                if target is not None:
                    req['kick_target'] = target
                    size = len(C.parse_list(finding['planned']))
                    out = actions['grow'](b, size)
                    req['log'].append(dict(at=now, did='grow', out=out))
                    if out.get('status') == 'grown':
                        req['log'].append(dict(at=now, did='resume', out=actions['resume'](finding['run'], finding['day'])))
                        req['log'].append(dict(at=now, did='kick', out=actions['kick'](finding['run'], finding['day'], target)))
                        req['state'] = 'done'
        elif stage == 'digest-render':
            if actions['render_stopped'](req.get('step_pid') or finding.get('step_pid')):
                req['log'].append(dict(at=now, did='restart_render', out=actions['restart_render'](req)))
                req['state'] = 'done'
            else:
                req['log'].append(dict(at=now, did='wait', out='the render has not reached its pass boundary yet'))
    except Exception as error:  # noqa: BLE001
        req['log'].append(dict(at=now, did='continue', error='%s: %s' % (type(error).__name__, error)))
    C.write_json(path, req)
    record['resize'].append(dict(req, step='continued'))


def continue_open_requests(work_dir, record, actions, bookings, handled):
    """Every resize request still 'requested' that no finding of this pass drove: continued from the request itself.
    The step it asked to stop has stopped (a ROOT saved: its booking retained, its step gone; a render exited), so the
    audit has no plan_wider_than_lane finding for it any more; without this the save would never be followed by the
    grow + resume + kick (or the render's restart)."""
    for path, req in sorted(resize_requests(work_dir).items()):
        if req.get('state') != 'requested' or req.get('booking') in handled:
            continue
        b = next((x for x in bookings if x.get('booking') == req.get('booking')), {})
        finding = dict(kind='plan_wider_than_lane', booking=req['booking'], stage=req.get('stage'), planned=req['planned'],
                       running=req['running'], decision=req.get('decision'), run=req.get('run') or b.get('run'),
                       day=req.get('day') or b.get('day'), step_pid=req.get('step_pid'), from_request=path.name)
        drive_resize(finding, work_dir, record, actions)


def open_requests(work_dir):
    """The resize requests still in flight (state 'requested')."""
    return [req for req in resize_requests(work_dir).values() if req.get('state') == 'requested']


def _queue_kick_defaults(Q):
    """The (max_seconds, poll_seconds) positions of the queue's kick, filled with the queue's OWN settings (as its CLI
    kick does), never a lifetime or poll value of the watchdog's: the queue ignores the lifetime (worker_limit) and
    its workers wait on events."""
    settings = getattr(Q, 'SETTINGS', {}) or {}
    return settings.get('queue_worker_seconds', 0), settings.get('queue_poll_seconds', 0)


def live_actions():
    """The box's real stop/resume calls (ROOT through the queue's own CLI on the day's code root; the render through
    its stop file and wrapper). Each returns the text of what happened; a failure raises and lands on the record."""
    def _queue_py(run, day):
        import frankie_box_frankie_queue as Q
        status = Q.owner_status(run, day)
        owner = (status.get('owner') or {})
        return Q, status, owner

    def request_save(run, day):
        Q, _s, _o = _queue_py(run, day)
        return json.dumps(Q.request_save(run, day, by='cpu-watch resize'), sort_keys=True)[:400]

    def owner_state(run, day):
        _Q, status, _o = _queue_py(run, day)
        return ((status.get('root') or {}).get('state')) or 'unknown'

    def grow(booking, size):
        _b, out = C.grow(booking, size, 'cpu-watch resize to the planned lane')
        return out

    def resume(run, day):
        Q, _s, _o = _queue_py(run, day)
        return json.dumps(Q.resume_owner(run, day, by='cpu-watch resize'), sort_keys=True)[:400]

    def kick_target(run, day):
        # both commits on the record: the owner's (the checkout it ran on) and the newest staged one the kick uses
        _Q, _s, owner = _queue_py(run, day)
        newest = newest_staged_checkout()
        return dict(owner_commit=owner.get('commit'), owner_code_root=owner.get('code_root'),
                    kick_commit=newest['commit'], kick_code_root=newest['code_root'], kick_staged_at=newest['staged_at'],
                    kick_receipt=newest['receipt'], same_as_owner=newest['commit'] == owner.get('commit'))

    def kick(run, day, target):
        Q, _s, _owner = _queue_py(run, day)
        return json.dumps(Q.kick('root', target['kick_code_root'], target['kick_commit'], *_queue_kick_defaults(Q),
                                 'cpu-watch resize', scope='%s:%s' % (run, day)), sort_keys=True)[:400]

    def stop_render(pid):
        env = Path('/proc/%d/environ' % pid).read_bytes().split(b'\0')
        values = dict(e.split(b'=', 1) for e in env if b'=' in e)
        stop = values.get(b'FRANKIE_DIGEST_STOP_FILE')
        if not stop:
            raise ValueError('the render pid %d carries no FRANKIE_DIGEST_STOP_FILE: not stoppable lawfully' % pid)
        C.write_json(stop.decode(), dict(by='cpu-watch resize', at=time.time()))
        return stop.decode()

    def render_stopped(pid):
        return not Path('/proc/%d' % pid).exists()

    def render_environment(pid):
        env = Path('/proc/%d/environ' % pid).read_bytes().split(b'\0')
        values = dict(e.split(b'=', 1) for e in env if b'=' in e)
        out = {k: values[k.encode()].decode() for k in ('CODE_ROOT', 'MARKETS_SHA', 'OUTPUT_ROOT') if k.encode() in values}
        if len(out) != 3:
            raise ValueError('the render pid %d carries %s of CODE_ROOT/MARKETS_SHA/OUTPUT_ROOT: not restartable from here' % (pid, sorted(out)))
        return out

    def restart_render(req):
        env = req.get('environment') or {}
        if not env.get('CODE_ROOT'):
            raise ValueError('the stopped render\'s environment (CODE_ROOT, MARKETS_SHA, OUTPUT_ROOT) was not recorded')
        cmd = ['bash', str(Path(env['CODE_ROOT']) / 'deploy/aws/box/frankie_box_render_digest.sh')]
        full = dict(os.environ, **{k: env[k] for k in ('CODE_ROOT', 'MARKETS_SHA', 'OUTPUT_ROOT') if env.get(k)})
        full.pop('FRANKIE_LANE_CPUS', None)
        log = open(Path(env['OUTPUT_ROOT']) / 'work' / 'render-cpu-watch-restart.log', 'ab')
        child = subprocess.Popen(cmd, env=full, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        return 'restarted as pid %d on the resolver\'s lane' % child.pid
    return dict(request_save=request_save, owner_state=owner_state, grow=grow, resume=resume, kick=kick, kick_target=kick_target,
                stop_render=stop_render, render_stopped=render_stopped, restart_render=restart_render,
                render_environment=render_environment)


def render_processes(procs, bookings):
    """The digest renders running outside every booking (frankie_box_render_digest.py), as pseudo-bookings so the audit
    compares their lane with the resolver's digest-render answer: {booking: 'render-<pid>', cpus: the process's affinity}."""
    out = []
    claimed = {p['pid'] for b in bookings for p in b.get('pids') or []}
    for pid, info in procs.items():
        if 'frankie_box_render_digest.py' not in info.get('cmdline', '') or pid in claimed:
            continue
        aff = live_affinity(pid) or set()
        lane = None
        # session 9: a render started INSIDE a day's own booking (FRANKIE_RENDER_BOOKING) is planned on that booking,
        # never on the free set: a resize to the free set would change its part count and lose its pass save points
        try:
            env = dict(e.split(b'=', 1) for e in Path('/proc/%d/environ' % pid).read_bytes().split(b'\0') if b'=' in e)
            inside = (env.get(C.RENDER_BOOKING_SETTING.encode()) or b'').decode() or None
            # the lane the render was given (its wrapper's FRANKIE_LANE_CPUS): the digest pins its main thread to ONE
            # coordinator CPU, so the main thread's affinity alone read as a 1-CPU lane and asked a resize
            lane = sorted(C.parse_list(env[b'FRANKIE_LANE_CPUS'].decode())) if env.get(b'FRANKIE_LANE_CPUS') else None
        except (OSError, ValueError, TypeError):
            inside = None
        aff = set(lane) if lane else aff
        out.append(dict(booking='render-%d' % pid, kind='render', cpus=sorted(aff), cpu_list=C.cpu_list(aff), _alive=True, _retained=False,
                        pids=[dict(pid=pid, start=C.start_time(pid), role='step digest-render (%s)' % (
                            'inside booking ' + inside if inside else 'unbooked render'))], run=None, day=None,
                        inside_booking=inside))
    return out


def corrections_enabled(environ=None):
    """(correct, resize): ON unless the setting is exactly 'off' (Greg, session 8: the defaults are on)."""
    environ = os.environ if environ is None else environ
    return environ.get(CORRECT_ENV, 'on') != 'off', environ.get(RESIZE_ENV, 'on') != 'off'


def one_pass(work_dir=WORK_DIR, window=1.0, environ=None, now=None, trigger='once'):
    """One live pass: collect, audit, correct (when asked), record. Returns the record; its _live (what keeps a watch
    going) and _pids (the processes whose exit wakes it) are not written."""
    environ = os.environ if environ is None else environ
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(now or time.time()))
    cmap = C.core_map()
    bookings = [b for b in C.live_bookings() if b.get('_alive') or b.get('_retained')]
    procs = C.processes()
    renders = render_processes(procs, bookings)
    plans, plan_reasons = planned_lanes(bookings, cmap)
    for r in renders:
        if r.get('inside_booking'):
            held = next((b for b in bookings if b['booking'] == r['inside_booking']), None)
            if held:
                r['cpus'], r['cpu_list'] = sorted(held['cpus']), C.cpu_list(held['cpus'])
            plans[r['booking']] = sorted(r['cpus'])
            continue
        try:
            plans[r['booking']] = C.lane_for('digest-render', bookings=bookings, cmap=cmap, environ={})['cpus']
        except C.PlanRefused as error:
            plan_reasons[r['booking']] = str(error)
    remaining = {b['booking']: remaining_seconds(b) for b in bookings}
    out = audit(bookings + renders, procs, live_affinity, live_threads, cmap, cmap['online'], plans=plans, remaining=remaining)
    correct, resize = corrections_enabled(environ)
    record = dict(schema=SCHEMA, at=stamp, host=os.uname().nodename, trigger=trigger, correct=correct, resize=[],
                  resize_enabled=resize, settings={CORRECT_ENV: environ.get(CORRECT_ENV, 'unset = on'),
                                                   RESIZE_ENV: environ.get(RESIZE_ENV, 'unset = on')},
                  plan_refusals=plan_reasons, **out)
    if record['correct']:
        record['repins'] = apply_repins(record['findings'], os.sched_setaffinity)
    if record['resize_enabled']:
        actions, handled = live_actions(), set()
        for f in record['findings']:
            if f['kind'] == 'plan_wider_than_lane' and f['decision']['choice'] == 'resize':
                b = next((x for x in bookings + renders if x['booking'] == f['booking']), {})
                f.update(run=b.get('run'), day=b.get('day'), step_pid=step_of(b)[1] if b else None)
                drive_resize(f, work_dir, record, actions)
                handled.add(f['booking'])
        continue_open_requests(work_dir, record, actions, bookings, handled)
    live = [b['booking'] for b in bookings if b.get('_alive')] + [r['booking'] for r in renders]
    record['_live'] = dict(bookings=live, open_requests=[r.get('booking') for r in open_requests(work_dir)])
    record['_pids'] = sorted({(p['pid'], p.get('start')) for b in bookings + renders for p in b.get('pids') or []
                              if C.alive(p)})
    path = work_dir / ('%s.json' % stamp)
    C.write_json(path, record)
    kinds = {}
    for f in record['findings']:
        kinds[f['kind']] = kinds.get(f['kind'], 0) + 1
    line = '%s bookings %d findings %d (%s)%s%s -> %s' % (
        stamp, len(record['bookings']), len(record['findings']),
        ', '.join('%s %d' % kv for kv in sorted(kinds.items())) or 'none',
        ' repins %d' % len(record.get('repins') or []) if record['correct'] else '',
        ' resize %d' % len(record['resize']) if record['resize_enabled'] else '', path.name)
    with open(work_dir / 'watch.log', 'a') as log:
        log.write(line + '\n')
    print(line, flush=True)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--loop', action='store_true', help='a pass on every event until nothing is live (default: one pass)')
    p.add_argument('--kick-wake', action='store_true', help='write the kick wake; exit 0 when a watcher runs, %d when none'
                                                             % NOT_LIVE_EXIT)
    p.add_argument('--max-seconds', type=float, default=None, help='an optional bound on the watch (default: none)')
    p.add_argument('--work-dir', default=str(WORK_DIR))
    p.add_argument('--window', type=float, default=1.0)
    a = p.parse_args()
    work_dir = Path(a.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    if a.kick_wake:
        return kick_wake(work_dir)
    lock = open(work_dir / '.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('another cpu watcher holds %s; nothing run' % (work_dir / '.lock'), file=sys.stderr)
        return 3
    if not a.loop:
        one_pass(work_dir, a.window)
        return 0
    return watch(work_dir, lock, a.window, a.max_seconds)


def _wake():
    import frankie_box_wake as WAKE
    return WAKE


def kick_wake(work_dir):
    """A kick (frankie_box_cpu_watch.sh ACTION=loop): the wake FIRST, then the lock test. A watcher holding the lock
    re-checks on that wake (exit 0); a watcher that is ending released its lock before its last event check, so it either
    sees this wake and takes the lock back or the lock is free here (exit NOT_LIVE_EXIT: the caller starts a watcher;
    two starting at once settle on the lock, the second exits 3)."""
    _wake().notify(Path(work_dir) / KICK_WAKE, 'kick', by='cpu-watch kick')
    with open(Path(work_dir) / '.lock', 'w') as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print('a cpu watcher runs (it holds %s); it re-checks on the kick wake' % (Path(work_dir) / '.lock'))
            return 0
        fcntl.flock(probe, fcntl.LOCK_UN)
    return NOT_LIVE_EXIT


def watch(work_dir, lock, window=1.0, max_seconds=None):
    """The event-driven watch (no interval, no lifetime cap unless max_seconds is given): the waiter is armed on the
    ledger, the queue's wake directory and the kick wake BEFORE each pass, the pass runs, the booked processes' exits are
    added, then it blocks until any of them fires. When nothing is live (no booking with a running process, no render,
    no open resize request) the watch ends: the lock is released FIRST, then any event that arrived meanwhile takes it
    back (another watcher may have it: then this one ends)."""
    W = _wake()
    work_dir = Path(work_dir)
    # the kick wake directory exists before the watch is armed: a missing one would put the watch on work_dir itself,
    # where every pass writes its record (a pass waking the next)
    (work_dir / KICK_WAKE).mkdir(parents=True, exist_ok=True)
    waiter = W.Waiter([C.LEDGER, QUEUE_WAKE, work_dir / KICK_WAKE])
    deadline = None if max_seconds is None else time.time() + float(max_seconds)
    trigger, gone, starts = 'start', set(), {}
    try:
        while True:
            waiter.fired.clear()
            waiter.exited.clear()
            record = one_pass(work_dir, window, trigger=trigger)
            live = record.get('_live') or {}
            if live.get('bookings') or live.get('open_requests'):
                exited_meanwhile = []
                for pid, start in record.get('_pids') or []:
                    if (pid, start) in gone:
                        continue        # its exit already woke a pass (a zombie still reads alive to the ledger)
                    if not W.alive(pid):
                        gone.add((pid, start))
                        exited_meanwhile.append(pid)
                        continue
                    starts[pid] = start
                    waiter.watch_pid(pid)
                if exited_meanwhile:    # gone between the pass and its watch: one pass more, never a loop
                    trigger = '; '.join('exit %d (before its watch)' % p for p in exited_meanwhile)
                    continue
                remaining = None if deadline is None else deadline - time.time()
                if remaining is not None and remaining <= 0:
                    print('cpu watch: the given bound of %s s passed; ended' % max_seconds, flush=True)
                    return 0
                woke = waiter.wait(remaining)
                gone.update((pid, starts.get(pid)) for pid in waiter.exited)
                trigger = describe_trigger(waiter, woke)
                continue
            fcntl.flock(lock, fcntl.LOCK_UN)
            if not waiter.wait(0):
                print('cpu watch: no booking live, no day running, no render, no open resize: ended (the next kick '
                      'starts it again)', flush=True)
                return 0
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                print('cpu watch: an event arrived while ending and another watcher holds the lock; this one ended',
                      flush=True)
                return 0
            trigger = describe_trigger(waiter, True)
    finally:
        waiter.close()


def describe_trigger(waiter, woke):
    """What woke the watch (on the record): the directories that fired and the pids that exited."""
    if not woke:
        return 'bound'
    parts = ['dir %s' % d for d in sorted(waiter.fired)] + ['exit %d' % p for p in sorted(waiter.exited)]
    return '; '.join(parts) or 'event'



if __name__ == '__main__':
    sys.exit(main())
