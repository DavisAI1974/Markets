"""Toy for frankie_box_cores' resolver (lane_for), core map (core_map) and grow (session 8, the 64-vCPU main box).
Standard library only; a fake /sys tree (siblings N/N+32 like an r7i.16xlarge) and fake bookings; the ledger paths are
redirected to a temporary directory. Run: python -m unittest tests.test_frankie_box_cpu_plan"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'deploy' / 'aws' / 'box'))
import frankie_box_cores as C  # noqa: E402


def fake_sys(root, nproc=64, threads=2, broken=()):
    """cpuN/topology/thread_siblings_list for a box of nproc CPUs, siblings N and N + nproc/threads; `broken` CPUs get
    no topology (unreadable)."""
    root = Path(root)
    (root / 'online').write_text('0-%d\n' % (nproc - 1))
    per = nproc // threads
    for cpu in range(nproc):
        if cpu in broken:
            continue
        t = root / ('cpu%d' % cpu) / 'topology'
        t.mkdir(parents=True)
        sibs = sorted({cpu % per + k * per for k in range(threads)})
        (t / 'thread_siblings_list').write_text(','.join(map(str, sibs)) + '\n')
        (t / 'core_id').write_text('%d\n' % (cpu % per))
        (t / 'physical_package_id').write_text('0\n')


def R(text):
    """The CPU set a comma list / range text names (the ledger's cpu_list is the comma form; taskset reads both)."""
    return sorted(C.parse_list(text))


def booking(bid, cpus, run='e2e-20231018-a2', day='20231018', retained=True, alive=False, kind='day-run', grown=None):
    b = dict(schema=C.SCHEMA, booking=bid, kind=kind, run=run, day=day, cpus=sorted(cpus), cpu_list=C.cpu_list(cpus),
             parent_cpu=min(cpus), worker_cpus=sorted(cpus)[1:], size=len(cpus), pids=[], stage='day-slot-root',
             commit='abc', _alive=alive, _retained=retained)
    if retained:
        b['retained'] = dict(run=run, day=day, attempt='%s-%s-a1' % (run, day))
    if grown:
        b['grown'] = grown
    return b


class CoreMap(unittest.TestCase):
    def test_16xlarge_siblings_read_not_assumed(self):
        with tempfile.TemporaryDirectory() as d:
            fake_sys(d)
            m = C.core_map(sys_root=d)
        self.assertEqual(m['nproc'], 64)
        self.assertEqual(m['physical_cores'], 32)
        self.assertEqual(m['threads_per_core'], 2)
        self.assertEqual(m['cores'][0], [0, 32])
        self.assertEqual(m['siblings'][5], [37])
        self.assertIn('thread_siblings_list', m['basis'])

    def test_unreadable_topology_is_said(self):
        with tempfile.TemporaryDirectory() as d:
            fake_sys(d, nproc=8, broken=(3,))
            m = C.core_map(sys_root=d)
        self.assertIn('unreadable', m['basis'])
        self.assertEqual(m['siblings'][3], [])

    def test_whole_cores_first(self):
        with tempfile.TemporaryDirectory() as d:
            fake_sys(d)
            m = C.core_map(sys_root=d)
        order = C.whole_cores_first(range(32, 64), m)
        self.assertEqual(order, list(range(32, 64)))          # 32-63 are 32 distinct cores' second threads
        order = C.whole_cores_first([0, 32, 1, 33], m)
        self.assertEqual(order, [0, 1, 32, 33])


class Resolver(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        fake_sys(self.d.name)
        self.m = C.core_map(sys_root=self.d.name)
        self.a2 = booking('day-run-20231018-day_slot_root-1791402822-3111', range(32))

    def tearDown(self):
        self.d.cleanup()

    def lane(self, step, **kw):
        kw.setdefault('cmap', self.m)
        kw.setdefault('environ', {})
        kw.setdefault('run', 'e2e-20231018-a2')
        kw.setdefault('day', '20231018')
        return C.lane_for(step, **kw)

    def test_day_slot_needs_the_plan_size(self):
        with self.assertRaises(C.PlanRefused) as cm:
            self.lane('day-slot', bookings=[])
        self.assertIn('missing', str(cm.exception))
        with self.assertRaises(C.PlanRefused):
            self.lane('day-slot', plan_size=48, bookings=[])

    def test_day_slot_idle_box_whole_cores_first(self):
        out = self.lane('day-slot', plan_size=32, bookings=[])
        self.assertEqual(R(out['cpu_list']), R('0-15,32-47'))       # 16 whole cores, both threads (decision 5)
        self.assertEqual(out['physical_cores'], 16)
        self.assertFalse(out['fallback'])
        self.assertEqual(out['shares_cores_with'], [])
        out = self.lane('day-slot', plan_size=64, bookings=[])
        self.assertEqual(R(out['cpu_list']), R('0-63'))
        out = self.lane('day-slot', plan_size=16, bookings=[])
        self.assertEqual(R(out['cpu_list']), R('0-7,32-39'))

    def test_second_day_slot_takes_whole_cores_before_siblings(self):
        a = booking('day-a', R('0-15,32-47'), run='fleet', day='20231019', retained=False, alive=True)
        out = self.lane('day-slot', plan_size=32, run='fleet', day='20231020', bookings=[a])
        self.assertEqual(R(out['cpu_list']), R('16-31,48-63'))
        self.assertFalse(out['fallback'])
        self.assertEqual(out['shares_cores_with'], [])

    def test_day_slot_fallback_when_no_whole_cores_free(self):
        # a2 retained on 0-31 (one thread of every core): only siblings are free -> the old lowest-first rule, said so
        out = self.lane('day-slot', plan_size=32, run='fleet', day='20231020', bookings=[self.a2])
        self.assertEqual(R(out['cpu_list']), R('32-63'))
        self.assertTrue(out['fallback'])
        self.assertTrue(any('FALLBACK' in n for n in out['notes']))
        self.assertEqual(out['shares_cores_with'], list(range(32, 64)))
        # a mix: 8 whole cores free (24-31 with 56-63) and 24 single threads (0-23): 16 from whole cores, 16 lowest-first
        held = booking('ingest-x', R('32-55'), run='r', day='d', kind='ingest', retained=False, alive=True)
        out = self.lane('day-slot', plan_size=32, run='fleet', day='20231020', bookings=[held])
        self.assertEqual(R(out['cpu_list']), R('0-15,24-31,56-63'))
        self.assertTrue(out['fallback'])

    def test_allocate_day_slot_pure(self):
        cpus, how, fallback = C.allocate_day_slot(range(64), 32, self.m)
        self.assertEqual(cpus, sorted(R('0-15,32-47')))
        self.assertIn('16 whole core', how)
        self.assertFalse(fallback)
        cpus, how, fallback = C.allocate_day_slot(range(32), 16, self.m)
        self.assertEqual(cpus, list(range(16)))
        self.assertTrue(fallback)
        self.assertIn('FALLBACK', how)

    def test_day_slot_retained_exactly(self):
        out = self.lane('day-slot', plan_size=32, bookings=[self.a2])
        self.assertEqual(R(out['cpu_list']), R('0-31'))
        self.assertTrue(out['retained'])
        self.assertEqual(out['booking'], self.a2['booking'])

    def test_day_slot_plan_64_against_retained_32_is_refused_loudly(self):
        with self.assertRaises(C.PlanRefused) as cm:
            self.lane('day-slot', plan_size=64, bookings=[self.a2])
        text = str(cm.exception)
        self.assertIn('asks 64', text)
        self.assertIn('holds 32', text)
        self.assertIn('grow', text)

    def test_day_slot_grown_booking_is_accepted(self):
        grown = booking(self.a2['booking'], range(64), grown=[dict(from_size=32, to_size=64, reason='classroom day gets all 64')])
        out = self.lane('day-slot', plan_size=32, bookings=[grown])
        self.assertEqual(R(out['cpu_list']), R('0-63'))
        self.assertTrue(any('grown' in line for line in out['basis']))

    def test_day_slot_waits_never_shrinks(self):
        with self.assertRaises(C.PlanRefused) as cm:
            self.lane('day-slot', plan_size=64, run='other', day='20231019', bookings=[self.a2])
        self.assertIn('32 free of 64', str(cm.exception))

    def test_digest_render_outside_every_booking(self):
        out = self.lane('digest-render', bookings=[self.a2])
        self.assertEqual(R(out['cpu_list']), R('32-63'))
        self.assertEqual(out['shares_cores_with'], list(range(32, 64)))   # the siblings of a2's lane: said, not hidden
        self.assertTrue(any('DURING the teacher' in n for n in out['notes']))   # decision 2, on the plan
        with self.assertRaises(C.PlanRefused) as cm:
            self.lane('digest-render', bookings=[self.a2], environ={'FRANKIE_LANE_CPUS': '16-31'})
        self.assertIn('overlaps', str(cm.exception))
        out = self.lane('digest-render', bookings=[self.a2], environ={'FRANKIE_LANE_CPUS': '40-47'})
        self.assertEqual(R(out['cpu_list']), R('40-47'))
        with self.assertRaises(C.PlanRefused):
            self.lane('digest-render', bookings=[booking('x', range(64))])
        with self.assertRaises(C.PlanRefused):
            self.lane('digest-render', bookings=[self.a2], environ={'FRANKIE_LANE_CPUS': '60-70'})

    def test_classroom_day_all_grows_the_held_booking(self):
        out = self.lane('classroom-day', bookings=[self.a2], environ={'FRANKIE_CLASSROOM_CPUS': 'all'})
        self.assertEqual(out['grow_to'], 64)
        self.assertEqual(out['grow_cpus'], list(range(32, 64)))
        self.assertEqual(out['waits_for'], 0)
        self.assertEqual(R(out['cpu_list']), R('0-63'))
        other = booking('ingest-x', range(40, 48), run='r2', day='20231019', kind='ingest', retained=False, alive=True)
        out = self.lane('classroom-day', bookings=[self.a2, other], environ={'FRANKIE_CLASSROOM_CPUS': 'all'})
        self.assertEqual(out['waits_for'], 8)
        self.assertTrue(any('WAITS' in line for line in out['basis']))
        # decision 1: unset = ALL by default when the box has more CPUs than the held booking; recorded as the default
        out = self.lane('classroom-day', bookings=[self.a2], environ={})
        self.assertEqual(out['grow_to'], 64)
        self.assertEqual(out['setting'], 'all')
        self.assertIn('default', out['setting_source'])
        self.assertTrue(any('default all' in line for line in out['basis']))
        # a user-set value still wins
        out = self.lane('classroom-day', bookings=[self.a2], environ={'FRANKIE_CLASSROOM_CPUS': 'held'})
        self.assertIsNone(out['grow_to'])
        self.assertEqual(R(out['cpu_list']), R('0-31'))
        self.assertEqual(out['setting_source'], 'given')
        # a booking that already holds the whole box: unset = held, nothing to grow
        whole = booking('day-64', range(64), run='r64', day='20231021')
        out = self.lane('classroom-day', run='r64', day='20231021', bookings=[whole], environ={})
        self.assertIsNone(out['grow_to'])
        self.assertEqual(out['setting'], 'held')
        with self.assertRaises(C.PlanRefused):
            self.lane('classroom-day', bookings=[self.a2], environ={'FRANKIE_CLASSROOM_CPUS': '16'})
        with self.assertRaises(C.PlanRefused):
            self.lane('classroom-day', bookings=[self.a2], environ={'FRANKIE_CLASSROOM_CPUS': 'most'})
        with self.assertRaises(C.PlanRefused):
            self.lane('classroom-day', bookings=[], environ={'FRANKIE_CLASSROOM_CPUS': 'all'})

    def test_teacher_lanes_every_cpu_used(self):
        out = self.lane('teacher-lanes', bookings=[self.a2], days=['a', 'b', 'c'])
        self.assertEqual([len(lane) for lane in out['lanes']], [11, 11, 10])
        self.assertEqual(sorted(c for lane in out['lanes'] for c in lane), list(range(32)))
        out = self.lane('teacher-lanes', bookings=[self.a2], days=['a'])
        self.assertEqual([R(x) for x in out['lane_lists']], [list(range(32))])

    def test_step_inside_and_jev_need_the_held_booking(self):
        with self.assertRaises(C.PlanRefused):
            self.lane('step-inside', bookings=[])
        out = self.lane('jev', bookings=[self.a2])
        self.assertEqual(R(out['cpu_list']), R('0-31'))
        if out['threads'] is not None:
            self.assertEqual(out['threads'], 32)                      # the lane size (JEV_THREADS None)
        whole = booking('day-64', range(64), run='r64', day='20231021')
        out = self.lane('jev', run='r64', day='20231021', bookings=[whole])
        if out['threads'] is not None:
            self.assertEqual(out['threads'], 64)                      # decision 3: 64 on a 64 lane

    def test_unknown_step(self):
        with self.assertRaises(C.PlanRefused):
            self.lane('render', bookings=[])


class Grow(unittest.TestCase):
    """grow through the ledger itself: a temporary ledger, 64 online CPUs, no live Frankie processes."""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        fake_sys(self.d.name)
        self.saved = (C.LEDGER, C.RELEASED, C.WAITING, C.SYS_CPU, C.online_cpus, C.usage)
        C.LEDGER = Path(self.d.name) / 'cpu-bookings'
        C.RELEASED = C.LEDGER / 'released'
        C.WAITING = C.LEDGER / 'waiting'
        C.LEDGER.mkdir()
        C.online_cpus = lambda sys_root=None: list(range(64))
        C.usage = lambda window, exclude=(): ({}, [], {}, [b for b in C.live_bookings() if b['_alive'] or b['_retained']])
        self.saved_core_map = C.core_map
        self.m = C.core_map(sys_root=self.d.name)                  # the fake 16xlarge map, read once before the stub
        C.core_map = lambda sys_root=None, online=None: self.m
        self.a2 = booking('day-run-20231018-day_slot_root-1791402822-3111', range(32))
        self.write(self.a2)

    def tearDown(self):
        C.LEDGER, C.RELEASED, C.WAITING, C.SYS_CPU, C.online_cpus, C.usage = self.saved
        C.core_map = self.saved_core_map
        self.d.cleanup()

    def test_ledger_books_whole_cores_first(self):
        meta = dict(run='fleet', day='20231019', stage='day-slot-root', commit='c', size=32)
        b, out = C.book('day-run', os.getpid(), meta, 0.1)
        self.assertEqual(out['status'], 'booked')
        self.assertEqual(R(out['cpus']), R('32-63'))               # a2 holds 0-31: only siblings are free -> the fallback
        again = json.loads((C.LEDGER / (b['booking'] + '.json')).read_bytes())
        self.assertTrue(again['placement']['fallback'])
        self.assertIn('whole cores first', again['placement']['rule'])

    def write(self, b):
        body = {k: v for k, v in b.items() if not k.startswith('_')}
        (C.LEDGER / (b['booking'] + '.json')).write_text(json.dumps(body))

    def test_grow_retained_to_64(self):
        b, out = C.grow(self.a2['booking'], 64, 'classroom day gets all 64')
        self.assertEqual(out['status'], 'grown')
        self.assertEqual(R(out['added']), R('32-63'))
        again = json.loads((C.LEDGER / (self.a2['booking'] + '.json')).read_bytes())
        self.assertEqual(R(again['cpu_list']), R('0-63'))
        self.assertEqual(again['size'], 64)
        self.assertEqual(again['grown'][0]['reason'], 'classroom day gets all 64')
        self.assertTrue(again.get('retained'))               # still retained by its owner; grow does not resume

    def test_grow_never_shrinks_and_only_lawful_sizes(self):
        _, out = C.grow(self.a2['booking'], 16, 'x')
        self.assertEqual(out['status'], 'refused')
        _, out = C.grow(self.a2['booking'], 48, 'x')
        self.assertEqual(out['status'], 'refused')
        _, out = C.grow('nope', 64, 'x')
        self.assertEqual(out['status'], 'refused')

    def test_grow_waits_for_booked_cpus(self):
        self.write(booking('ingest-x', range(40, 48), run='r2', day='d', kind='ingest', retained=True))
        _, out = C.grow(self.a2['booking'], 64, 'x')
        self.assertEqual(out['status'], 'waiting')
        self.assertIn('24 free of the 32 more', out['reason'])

    def test_takeover_refuses_a_differing_plan_unless_grown(self):
        meta = dict(run='e2e-20231018-a2', day='20231018', cpus=list(range(32)), stage='day-slot-root', commit='c')
        b, out = C.book('day-run', os.getpid(), dict(meta, size=64), 0.1)
        self.assertEqual(out['status'], 'refused')
        self.assertIn('asks 64', out['reason'])
        self.assertIn('holds 32', out['reason'])
        b, out = C.book('day-run', os.getpid(), dict(meta, size=32), 0.1)
        self.assertEqual(out['status'], 'booked')
        self.assertEqual(out['resumed_from'], self.a2['booking'])

    def test_takeover_of_a_grown_booking(self):
        C.grow(self.a2['booking'], 64, 'grown before the classroom')
        meta = dict(run='e2e-20231018-a2', day='20231018', cpus=list(range(64)), stage='day-slot-classroom', commit='c', size=32)
        b, out = C.book('day-run', os.getpid(), meta, 0.1)
        self.assertEqual(out['status'], 'booked')
        self.assertEqual(R(out['cpus']), R('0-63'))


if __name__ == '__main__':
    unittest.main()
