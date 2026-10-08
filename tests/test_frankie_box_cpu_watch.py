"""Toy for frankie_box_cpu_watch (session 8): a fake process tree, fake affinities, a fake sibling map and fake bookings
through the pure audit; the wall-clock resize decision; the resize state machine with recorded fake actions (a resumable
ROOT step and a non-resizable teacher step). Standard library only. Run: python -m unittest tests.test_frankie_box_cpu_watch"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'deploy' / 'aws' / 'box'))
import frankie_box_cores as C  # noqa: E402
import frankie_box_cpu_watch as W  # noqa: E402


def cmap64():
    cores = [[n, n + 32] for n in range(32)]
    siblings = {}
    for a, b in cores:
        siblings[a], siblings[b] = [b], [a]
    return dict(online=list(range(64)), cores=cores, siblings=siblings, threads_per_core=2, basis='fake', nproc=64, physical_cores=32)


def booking(bid, cpus, pids, run='e2e', day='20231018', kind='day-run', retained=False):
    return dict(schema=C.SCHEMA, booking=bid, kind=kind, run=run, day=day, cpus=sorted(cpus), cpu_list=C.cpu_list(cpus),
                pids=pids, _alive=any(p.get('alive', True) for p in pids), _retained=retained)


class Fake:
    """A fake process tree: procs {pid: info}, threads {pid: [tid]}, affinity {tid: set}; C.alive is answered by `alive`."""

    def __init__(self):
        self.procs, self.threads, self.aff = {}, {}, {}

    def proc(self, pid, ppid, cmd, aff, tids=None, frankie=True):
        self.procs[pid] = dict(pid=pid, ppid=ppid, cmdline=cmd, cwd='/opt/frankie-box/work' if frankie else '/home',
                               exe='/opt/frankie-box/venv/bin/python' if frankie else '/usr/bin/python3')
        tids = tids or [pid]
        self.threads[pid] = tids
        for t in tids:
            self.aff[t] = set(aff)
        return pid

    def affinity_of(self, tid):
        return self.aff.get(tid)

    def threads_of(self, pid):
        return self.threads.get(pid, [])

    def setaffinity(self, tid, cpus):
        self.aff[tid] = set(cpus)


class Audit(unittest.TestCase):
    def setUp(self):
        self.f = Fake()
        self.saved = (C.alive, C.is_frankie)
        C.alive = lambda entry: entry.get('pid') in self.f.procs
        C.is_frankie = lambda info: info.get('exe', '').startswith('/opt/frankie-box')
        self.m = cmap64()

    def tearDown(self):
        C.alive, C.is_frankie = self.saved

    def run_audit(self, bookings, **kw):
        return W.audit(bookings, self.f.procs, self.f.affinity_of, self.f.threads_of, self.m, self.m['online'], **kw)

    def test_clean_tree_has_no_findings(self):
        f = self.f
        f.proc(100, 1, 'python frankie_box_experiment.py', range(32))                 # the holder on the whole lane
        f.proc(200, 100, 'python frankie_box_experiment_root.py', range(32))           # the step root on the lane
        for i in range(1, 32):
            f.proc(300 + i, 200, 'python worker', [i])                                 # workers pinned one CPU each
        b = booking('b1', range(32), [dict(pid=100, role='booking holder'), dict(pid=200, role='step root (under taskset)')])
        out = self.run_audit([b])
        self.assertEqual(out['findings'], [])
        self.assertEqual(out['bookings'][0]['stage'], 'root')
        self.assertEqual(out['bookings'][0]['processes'], 33)

    def test_outside_narrower_unreachable_and_unbooked(self):
        f = self.f
        f.proc(100, 1, 'python frankie_box_experiment.py', range(32))
        f.proc(200, 100, 'python frankie_box_experiment_root.py', range(16))          # the step root narrower than its lane
        f.proc(301, 200, 'python worker', [40])                                        # a worker OUTSIDE the booking
        f.proc(302, 200, 'python worker', [3, 50])                                     # partly outside
        f.proc(900, 1, 'python frankie_box_render_digest.py', range(32, 64))           # an unbooked Frankie process
        f.proc(901, 1, 'python3 something', range(64), frankie=False)                  # not Frankie: ignored
        b = booking('b1', range(32), [dict(pid=100, role='booking holder'), dict(pid=200, role='step root (x)')])
        out = self.run_audit([b])
        kinds = sorted(x['kind'] for x in out['findings'])
        # the holder (pid 100) reaches the whole lane, so no lane CPU is unreachable here
        self.assertEqual(kinds, ['narrower_than_lane', 'outside_booking', 'outside_booking', 'unbooked'])
        outside = [x for x in out['findings'] if x['kind'] == 'outside_booking']
        self.assertEqual(sorted(x['pid'] for x in outside), [301, 302])
        self.assertEqual(next(x for x in outside if x['pid'] == 301)['correction']['set_to'], C.cpu_list(range(32)))
        self.assertEqual(next(x for x in outside if x['pid'] == 302)['correction']['set_to'], '3')
        narrow = next(x for x in out['findings'] if x['kind'] == 'narrower_than_lane')
        self.assertEqual(narrow['pid'], 200)
        self.assertEqual(out['unbooked'][0]['pid'], 900)
        # CORRECT=on: re-pin applies to the three affinity findings only, never to the unbooked process
        done = W.apply_repins(out['findings'], self.f.setaffinity)
        self.assertEqual(sorted(d['pid'] for d in done), [200, 301, 302])
        self.assertEqual(self.f.aff[301], set(range(32)))
        self.assertEqual(self.f.aff[302], {3})
        self.assertEqual(self.f.aff[200], set(range(32)))
        self.assertEqual(self.f.aff[900], set(range(32, 64)))

    def test_unreachable_counts_a_pool_sized_small(self):
        f = self.f
        f.proc(200, 1, 'python frankie_box_experiment_root.py', [0])                   # the root pinned to its CPU
        for i in range(1, 16):
            f.proc(300 + i, 200, 'python worker', [i])                                 # 15 workers on a 32 lane
        b = booking('b1', range(32), [dict(pid=200, role='step root (x)')])
        out = self.run_audit([b])
        kinds = [x['kind'] for x in out['findings']]
        self.assertIn('lane_cpus_unreachable', kinds)
        unreachable = next(x for x in out['findings'] if x['kind'] == 'lane_cpus_unreachable')
        self.assertEqual(unreachable['count'], 16)
        self.assertIn(W.REPIN_LIMIT, unreachable['note'])
        # the step root is pinned to ONE CPU (its lane is 32): narrower_than_lane names it, re-pin widens it, the pool stays 15
        self.assertIn('narrower_than_lane', kinds)

    def test_plan_wider_than_lane_carries_the_decision(self):
        f = self.f
        f.proc(200, 1, 'python frankie_box_experiment_root.py', range(32))
        b = booking('b1', range(32), [dict(pid=200, role='step root (x)')])
        out = self.run_audit([b], plans={'b1': list(range(64))}, remaining={'b1': 3600.0})
        wider = next(x for x in out['findings'] if x['kind'] == 'plan_wider_than_lane')
        self.assertEqual(wider['decision']['choice'], 'resize')
        self.assertEqual(wider['decision']['ratio'], 2.0)
        self.assertIn('wall-clock', wider['decision']['basis'])
        self.assertEqual(wider['mechanism'], W.RESUMABLE['root'])
        f.proc(201, 1, 'python frankie_box_experiment_teacher.py', range(32))
        t = booking('b2', range(32), [dict(pid=201, role='step teacher (x)')], day='20231019')
        out = self.run_audit([t], plans={'b2': list(range(64))}, remaining={'b2': 3600.0})
        wider = next(x for x in out['findings'] if x['kind'] == 'plan_wider_than_lane')
        self.assertEqual(wider['decision']['choice'], 'not_resizable')
        self.assertIsNone(wider['mechanism'])


class Decision(unittest.TestCase):
    def test_wall_clock_only(self):
        d = W.resize_decision('root', range(64), range(32), True, remaining_seconds=4.5 * 3600, redo_seconds=600, restart_seconds=300)
        self.assertEqual(d['choice'], 'resize')                 # 4.5 h on 32 vs ~2.5 h on 64: the faster path
        self.assertEqual(d['remaining_on_planned'], round(4.5 * 3600 / 2 + 900, 1))
        d = W.resize_decision('root', range(64), range(32), True, remaining_seconds=600, redo_seconds=600, restart_seconds=300)
        self.assertEqual(d['choice'], 'keep_faster')            # 10 min left: the stop costs more than it saves
        d = W.resize_decision('root', range(64), range(32), True, remaining_seconds=None)
        self.assertEqual(d['choice'], 'resize')                 # unknown remaining: the plan is the full lane (Greg)
        d = W.resize_decision('teacher', range(64), range(32), False, remaining_seconds=None)
        self.assertEqual(d['choice'], 'not_resizable')
        d = W.resize_decision('root', range(40), range(32), True)
        self.assertEqual(d['choice'], 'keep')                   # 1.25x: under the 1.5x bar
        d = W.resize_decision('root', range(32), range(32), True)
        self.assertEqual(d['choice'], 'repin')
        self.assertNotIn('cost', json.dumps(d).lower().replace('cost is not an input', ''))


class ResizeMachine(unittest.TestCase):
    """The state machine with fake actions: a resumable ROOT step goes request -> saved -> grow -> resume -> kick; a
    non-resizable step is listed and nothing is called; a render waits for its pass boundary, then restarts."""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.calls = []
        self.state = dict(owner='running', render_alive=True)

        def rec(name, result=None):
            def f(*a):
                self.calls.append((name,) + tuple(a))
                return result(*a) if callable(result) else result
            return f
        self.actions = dict(request_save=rec('request_save', 'marker written'),
                            owner_state=rec('owner_state', lambda run, day: self.state['owner']),
                            grow=rec('grow', dict(status='grown', cpus='0-63')),
                            resume=rec('resume', 'resumed'), kick=rec('kick', 'kicked'),
                            stop_render=rec('stop_render', '/x/render-stop-request.json'),
                            render_stopped=rec('render_stopped', lambda pid: not self.state['render_alive']),
                            restart_render=rec('restart_render', 'restarted'))

    def tearDown(self):
        self.d.cleanup()

    def finding(self, stage, booking='b1'):
        decision = W.resize_decision(stage, range(64), range(32), stage in W.RESUMABLE or stage == 'digest-render')
        return dict(kind='plan_wider_than_lane', booking=booking, stage=stage, planned=C.cpu_list(range(64)),
                    running=C.cpu_list(range(32)), decision=decision, run='e2e', day='20231018', step_pid=4242)

    def test_root_resize_across_passes(self):
        f = self.finding('root')
        record = dict(resize=[])
        W.drive_resize(f, self.d.name, record, self.actions)            # pass 1: the marker
        self.assertEqual([c[0] for c in self.calls], ['request_save'])
        req = json.loads((Path(self.d.name) / 'resize-b1.json').read_bytes())
        self.assertEqual(req['state'], 'requested')
        W.drive_resize(f, self.d.name, record, self.actions)            # pass 2: still running
        self.assertEqual([c[0] for c in self.calls][-1], 'owner_state')
        self.state['owner'] = 'saved'
        W.drive_resize(f, self.d.name, record, self.actions)            # pass 3: saved -> grow -> resume -> kick
        self.assertEqual([c[0] for c in self.calls][-4:], ['owner_state', 'grow', 'resume', 'kick'])
        self.assertEqual(self.calls[-3], ('grow', 'b1', 64))
        req = json.loads((Path(self.d.name) / 'resize-b1.json').read_bytes())
        self.assertEqual(req['state'], 'done')
        self.assertEqual([x['did'] for x in req['log']], ['request_save', 'owner_state', 'owner_state', 'grow', 'resume', 'kick'])
        W.drive_resize(f, self.d.name, record, self.actions)            # pass 4: nothing more
        self.assertEqual([c[0] for c in self.calls][-1], 'kick')
        self.assertEqual(record['resize'][-1]['state'], 'done')

    def test_non_resizable_step_calls_nothing(self):
        f = self.finding('teacher')
        self.assertEqual(f['decision']['choice'], 'not_resizable')
        record = dict(resize=[])
        W.drive_resize(f, self.d.name, record, self.actions)
        self.assertEqual(self.calls, [])
        req = json.loads((Path(self.d.name) / 'resize-b1.json').read_bytes())
        self.assertEqual(req['state'], 'not_resizable')

    def test_render_waits_for_its_pass_boundary(self):
        f = self.finding('digest-render', booking='render-4242')
        record = dict(resize=[])
        W.drive_resize(f, self.d.name, record, self.actions)
        self.assertEqual([c[0] for c in self.calls], ['stop_render'])
        W.drive_resize(f, self.d.name, record, self.actions)
        self.assertEqual([c[0] for c in self.calls][-1], 'render_stopped')
        self.assertEqual(json.loads((Path(self.d.name) / 'resize-render-4242.json').read_bytes())['log'][-1]['did'], 'wait')
        self.state['render_alive'] = False
        W.drive_resize(f, self.d.name, record, self.actions)
        self.assertEqual([c[0] for c in self.calls][-1], 'restart_render')
        self.assertEqual(json.loads((Path(self.d.name) / 'resize-render-4242.json').read_bytes())['state'], 'done')

    def test_failed_request_is_recorded_not_retried(self):
        def boom(*a):
            raise RuntimeError('queue refused')
        self.actions['request_save'] = boom
        f = self.finding('root')
        record = dict(resize=[])
        W.drive_resize(f, self.d.name, record, self.actions)
        req = json.loads((Path(self.d.name) / 'resize-b1.json').read_bytes())
        self.assertEqual(req['state'], 'request_failed')
        self.assertIn('queue refused', req['log'][0]['error'])
        W.drive_resize(f, self.d.name, record, self.actions)
        self.assertEqual(record['resize'][-1]['state'], 'request_failed')


class StepOf(unittest.TestCase):
    def test_step_from_roles(self):
        saved = C.alive
        C.alive = lambda entry: True
        try:
            self.assertEqual(W.step_of(dict(pids=[dict(pid=1, role='booking holder'), dict(pid=2, role='step classroom (under taskset)')])),
                             ('classroom', 2))
            self.assertEqual(W.step_of(dict(pids=[dict(pid=1, role='booking holder')])), (None, 1))
        finally:
            C.alive = saved


if __name__ == '__main__':
    unittest.main()
