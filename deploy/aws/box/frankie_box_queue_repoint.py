"""Re-point a ROOT-line day to a named EXISTING attempt on a RETAINED booking of a given size (session 9, 2026-10-08).

Why: the live 17:02Z resume of e2e-20231018-a2/20231018 attempt -a1 (grown to 64 CPUs) refused on data_workers 31 -> 63
(fixed in frankie_box_experiment_root.py: a run-size rebind); the queue's retry-once then minted a fresh -a2 on 32 CPUs,
killed by the parent, and the entry is failed and ownerless. Greg: "restart from exactly the same spot". This tool binds
the day back to the attempt the operator names (-a1), on a booking the ledger retains for it, so the existing
ACTION=resume (retained booking present -> queued) and ACTION=kick/handover resume THAT attempt with --resume.

Route (read from frankie_box_cores.book/book_locked): a day's admission (_book_slot) asks the plan's day_cpus with the
owner's CPU set; book() records asked_size and book_locked's take-over REFUSES a set whose size differs from the plan
unless the booking carries `grown`. So a SIZE above the plan is never booked directly: the lane is re-booked at the plan
size (rebook_for_owner: the resolver, whole cores first, booked, owned and RETAINED under one ledger lock) and then grown
to SIZE (grow: the `grown` record the take-over and lane_for accept). A retained booking of this run/day that is already
in the ledger is reused instead (grown when smaller). A waiting/refused ledger answer refuses loudly; only a booking this
tool made is released on that refusal. Nothing else is touched: the attempt directory, its saved documents, the plan.
The owner binding is minted exactly as frankie_box_frankie_queue._bind_owner mints one, plus `repointed`.
Idempotent: an entry already re-pointed to this attempt on a retained booking of SIZE prints status 'already'."""
import argparse
import json
import os
import re
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frankie_box_cores as C                     # noqa: E402
import frankie_box_frankie_queue as Q             # noqa: E402

ROOTS = Path('/opt/frankie-box/work/experiment-roots')


def _alive(pid):
    return bool(pid) and Path('/proc/%d' % int(pid)).exists()


def repoint(run, day, attempt, size, reason, by, code_root, commit):
    if not re.fullmatch(re.escape('%s-%s-a' % (run, day)) + r'[0-9]+', attempt):
        raise SystemExit('ATTEMPT %s is not an attempt name of %s %s (<RUN>-<DAY>-a<N>)' % (attempt, run, day))
    directory = ROOTS / attempt
    if directory.is_symlink() or not directory.is_dir() or not (directory / 'work' / 'derive.json').is_file():
        raise SystemExit('%s is not a retained attempt directory with work/derive.json' % directory)
    # 2026-10-09 (Greg: "use previously generated one ... we are starting this ourselves on one day at the point we want
    # it at"): a FINISHED ROOT (receipt present) whose ROOT-line entry is done but whose FINISH (teacher onward) failed or
    # stopped is re-pointed too: the owner binding is put back on the same attempt on a retained booking of SIZE, the
    # finish set 'unknown' (an owner state), so ACTION=resume ('finish' phase) and ACTION=kick resume the day at the step
    # after its ROOT (the teacher), reusing the receipted ROOT as it is. Never a new attempt, never a ROOT from scratch.
    finished = (directory / 'calculations-receipt.json').exists()
    if size not in C.DAY_RUN_SIZES:
        raise SystemExit('SIZE %s is not one of %s' % (size, C.DAY_RUN_SIZES))
    plan_size = int(Q._plan_of(run).get('day_cpus') or C.DAY_RUN_CPUS)
    if size < plan_size:
        raise SystemExit('SIZE %d is below the plan day_cpus %d: the admission would refuse it' % (size, plan_size))
    with Q.locked():
        doc = Q.load('root')
        x = next((y for y in doc['entries'] if y['run'] == run and y['day'] == day), None)
        if x is None:
            raise SystemExit('%s %s is not in the ROOT line' % (run, day))
        old = x.get('owner')
        finish = dict(x.get('finish') or {})
        owned_state = finish.get('state') if finished else x['state']
        if old and old.get('attempt') == attempt and (old.get('repointed') or {}).get('reason') and owned_state in Q.OWNER_STATES:
            path = C.LEDGER / ('%s.json' % old.get('booking'))
            b = json.loads(path.read_bytes()) if path.is_file() else {}
            if b.get('retained') and len(b.get('cpus') or []) == size:
                return dict(status='already', run=run, day=day, state=x['state'], finish=finish.get('state'), owner=old)
        if finished:
            if x['state'] != 'done' or finish.get('state') in ('running', 'finished'):
                raise SystemExit('%s %s is %s (finish %s): a finished ROOT is re-pointed only when its entry is done and its '
                                 'finish is not running or finished' % (run, day, x['state'], finish.get('state')))
        elif x['state'] not in ('failed', 'unknown', 'saved'):
            raise SystemExit('%s %s is %s: only a failed, unknown or saved entry is re-pointed' % (run, day, x['state']))
        if old and _alive(old.get('holder_pid')):
            raise SystemExit('%s %s: its owner process %s is alive' % (run, day, old.get('holder_pid')))
        ours = [b for b in C.live_bookings() if b.get('kind') == 'day-run' and b.get('run') == run and b.get('day') == day
                and (b['_alive'] or b['_retained'])]
        if any(b['_alive'] for b in ours):
            raise SystemExit('%s %s: a live booking holds the day (%s)' % (run, day, [b['booking'] for b in ours if b['_alive']]))
        made, why = None, '%s (re-point to %s by %s)' % (reason, attempt, by)
        if ours:
            b = ours[0]                                          # the retained set this day already holds: reused
            C.own(b['booking'], run, day, attempt)
            route = 'reused the retained booking %s' % b['booking']
        else:
            b, outcome = C.rebook_for_owner(run, day, attempt, plan_size, 'day-slot-repoint', commit, reason=why)
            if b is None:
                raise SystemExit('%s %s: no %d-CPU lane: %s' % (run, day, plan_size, json.dumps(outcome, sort_keys=True)))
            made = b['booking']
            route = 'rebook_for_owner at the plan size %d (%s)' % (plan_size, made)
        if len(b['cpus']) < size:
            b, outcome = C.grow(b['booking'], size, why)
            if b is None:
                if made:
                    C.release(made, 'the re-point of %s %s refused at grow: %s' % (run, day, outcome.get('reason')))
                raise SystemExit('%s %s: grow to %d refused: %s' % (run, day, size, json.dumps(outcome, sort_keys=True)))
            route += ', grown to %d (%s)' % (size, outcome.get('added'))
        elif len(b['cpus']) != size:
            raise SystemExit('%s %s: the retained booking %s holds %d CPUs, not %d (grow only widens)'
                             % (run, day, b['booking'], len(b['cpus']), size))
        if size != plan_size and not b.get('grown'):
            raise SystemExit('%s %s: the retained booking %s holds %d CPUs with no `grown` record; the admission refuses a '
                             'set above the plan day_cpus %d without it' % (run, day, b['booking'], size, plan_size))
        cpus = sorted(b['cpus'])
        history = x.get('owner_history') or []
        released = x.pop('failed_finish_bookings', None)
        owner = dict(schema='FRANKIE_QUEUE_OWNER_V1', run=run, day=day, host=socket.gethostname(), attempt=attempt,
                     commit=commit, code_root=str(Path(code_root).resolve()), marker=str(Q.marker_of(run, day)),
                     bound_utc=Q.utc(), bound_by_pid=os.getpid(), cpus=cpus, booking=b['booking'],
                     held_bookings=[dict(booking=b['booking'], cpus=cpus, bound_utc=Q.utc())],
                     repointed=dict(by=by, at_utc=Q.utc(), from_state=x['state'], reason=reason, route=route,
                                    from_owner=old or (history[-1] if history else None),
                                    cleared_failed_finish_bookings=released))
        x['owner'] = owner
        text = ('re-pointed by %s to attempt %s on the retained booking %s (%d CPUs): ACTION=resume then kick resumes it'
                % (by, attempt, b['booking'], size))
        if finished:
            # the ROOT stays done (its receipt is the day's ROOT, reused as it is); the finish becomes the owner's
            owner['repointed']['from_finish'] = finish or None
            x['finish'] = dict(finish, state='unknown', reason=text + ' at the step after its finished ROOT', repointed_utc=Q.utc())
        else:
            x.update(state='unknown', where=None, reason=text)
        Q.save('root', doc)
        Q.event('root', 'repoint', seq=x['seq'], day=day, run=run, by=by, attempt=attempt, booking=b['booking'],
                cpus=C.cpu_list(cpus), route=route, reason=reason, phase='finish' if finished else 'root')
        return dict(status='repointed', run=run, day=day, seq=x['seq'], state=x['state'],
                    finish=(x.get('finish') or {}).get('state'), phase='finish' if finished else 'root', attempt=attempt,
                    booking=b['booking'], cpus=C.cpu_list(cpus), size=len(cpus), route=route,
                    next='ACTION=resume RUN=%s DAY=%s, then ACTION=kick (or handover) LINE=root SCOPE=%s:%s' % (run, day, run, day))


def main():
    p = argparse.ArgumentParser()
    for name in ('run', 'day', 'attempt', 'reason', 'by', 'code-root', 'commit'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--size', type=int, required=True)
    a = p.parse_args()
    print(json.dumps(repoint(a.run, a.day, a.attempt, a.size, a.reason, a.by, a.code_root, a.commit), indent=1,
                     sort_keys=True, default=str))


if __name__ == '__main__':
    main()
