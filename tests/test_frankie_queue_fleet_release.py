"""Toy for the queue half of fleet finding B4 (session 8): a day SAVED at the fleet classroom gate as fleet_waiting
RELEASES its CPU booking (request_save release_booking=True -> _end_slot releases instead of retaining), every other
save RETAINS exactly as before, and the resume of a released day re-books through the ledger under its one lock
(frankie_box_cores.rebook_for_owner: the resolver names a whole-cores-first lane, the same lane is booked and retained
for the owner) or refuses loudly when no lane is free. Real functions; the ledger, the queue store and the /sys
topology redirected to a temporary directory (a 64-vCPU box, siblings N/N+32); no live Frankie process.
Run: python -m unittest tests.test_frankie_queue_fleet_release"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'deploy' / 'aws' / 'box'))
sys.path.insert(0, str(HERE))
import frankie_box_cores as C  # noqa: E402
import frankie_box_frankie_queue as Q  # noqa: E402
from test_frankie_box_cpu_plan import fake_sys, booking, R  # noqa: E402

RUN, DAY, ATTEMPT = 'fleet-a', '20231019', 'fleet-a-20231019-a1'


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        root = Path(self.d.name)
        (root / 'sys').mkdir()
        fake_sys(root / 'sys')
        self.saved = (C.LEDGER, C.RELEASED, C.WAITING, C.online_cpus, C.usage, C.core_map, Q.QUEUE, Q.SAVE_DIR, Q._plan_of)
        C.LEDGER = root / 'cpu-bookings'
        C.RELEASED = C.LEDGER / 'released'
        C.WAITING = C.LEDGER / 'waiting'
        C.LEDGER.mkdir()
        C.online_cpus = lambda sys_root=None: list(range(64))
        C.usage = lambda window, exclude=(): ({}, [], {}, [b for b in C.live_bookings() if b['_alive'] or b['_retained']])
        cmap = C.core_map(sys_root=str(root / 'sys'))
        C.core_map = lambda sys_root=None, online=None: cmap
        Q.QUEUE = root / 'frankie-queue'
        Q.SAVE_DIR = Q.QUEUE / 'save'
        Q.SAVE_DIR.mkdir(parents=True)
        Q._plan_of = lambda run_name: {'day_cpus': 32}
        # the day's booking (its ROOT ran on 0-15,32-47: 16 whole cores), live under this process, owned by the day
        self.bid = 'day-run-20231019-day_slot_root-1791500000-%d' % os.getpid()
        b = booking(self.bid, list(range(16)) + list(range(32, 48)), run=RUN, day=DAY, retained=False, alive=True)
        b['pids'] = [dict(pid=os.getpid(), start=C.start_time(os.getpid()), role='booking holder')]
        b['owner'] = dict(run=RUN, day=DAY, attempt=ATTEMPT)
        self.write(b)
        self.marker = Q.marker_of(RUN, DAY)
        self.owner = dict(schema='FRANKIE_QUEUE_OWNER_V1', run=RUN, day=DAY, attempt=ATTEMPT, commit='c0ffee',
                          marker=str(self.marker), cpus=sorted(b['cpus']), booking=self.bid)
        self.entry = dict(seq=1, run=RUN, day=DAY, state='running', owner=dict(self.owner))

    def tearDown(self):
        C.LEDGER, C.RELEASED, C.WAITING, C.online_cpus, C.usage, C.core_map, Q.QUEUE, Q.SAVE_DIR, Q._plan_of = self.saved
        self.d.cleanup()

    def write(self, b):
        (C.LEDGER / (b['booking'] + '.json')).write_text(json.dumps({k: v for k, v in b.items() if not k.startswith('_')}))

    def ledger(self, bid=None):
        path = C.LEDGER / ((bid or self.bid) + '.json')
        return json.loads(path.read_bytes()) if path.is_file() else None

    def write_marker(self, release):
        body = dict(schema='FRANKIE_QUEUE_SAVE_REQUEST_V1', run=RUN, day=DAY, attempt=ATTEMPT, booking=self.bid,
                    cpus=self.owner['cpus'], requested_at=1.0, requested_utc='x', by='toy')
        if release:
            body.update(release_booking=True, release_reason='fleet classroom gate (toy)')
        C.write_json(self.marker, body, exclusive=True)

    def queue_doc(self, state='saved', **owner_extra):
        doc = dict(schema=Q.SCHEMA, line='root', next_seq=2, next_done_seq=1,
                   entries=[dict(seq=1, run=RUN, day=DAY, state=state, owner=dict(self.owner, **owner_extra), attempts=[{}])])
        Q.save('root', doc)
        return doc


class FleetGateSaveReleases(Base):
    def test_fleet_gate_save_releases_the_booking_and_records_the_cpu_set(self):
        """Contract (1): the marker asks release_booking -> the slot's end RELEASES the ledger booking; the holder carries
        booking_released + the released CPU set, which _note_release puts on the owner binding and the save record."""
        self.write_marker(release=True)
        holder = dict(slot=self.bid, result=('saved', 'saved on its marker', {}))
        Q._end_slot(holder, self.entry, None)
        self.assertTrue(holder['booking_released'])
        self.assertEqual(holder['released_cpus'], self.owner['cpus'])
        self.assertIsNone(self.ledger())                                     # gone from the live ledger
        rel = json.loads((C.RELEASED / (self.bid + '.json')).read_bytes())    # its release receipt, whole
        self.assertIn('fleet classroom gate', rel['release_reason'])
        self.assertNotIn('retained', holder)
        y = dict(seq=1, run=RUN, day=DAY, owner=dict(self.owner), save_request=dict(booking=self.bid))
        Q._note_release(y, holder)
        self.assertTrue(y['owner']['booking_released'])
        self.assertEqual(y['owner']['released_cpus'], self.owner['cpus'])
        self.assertEqual(y['owner']['released_booking'], self.bid)
        self.assertTrue(y['save_request']['booking_released'])
        self.assertEqual(Q._released_fields(holder)['released_cpus'], self.owner['cpus'])

    def test_unknown_end_on_a_release_marker_still_retains(self):
        """Only a SAVED end releases: an UNKNOWN end (the class child gone without its ack) retains as before, so a
        booking is never released on an outcome the save did not reach."""
        self.write_marker(release=True)
        holder = dict(slot=self.bid, result=('unknown', 'child gone', {}))
        Q._end_slot(holder, self.entry, None)
        self.assertEqual(holder.get('retained'), self.bid)
        self.assertTrue(self.ledger()['retained'])


class OrdinarySaveRetains(Base):
    def test_ordinary_save_retains_exactly_as_before(self):
        """Contract (2): a marker without the flag (the hold, the stage handoff's ordinary save, an operator save) ->
        RETAINED in the ledger for the owner; no release field anywhere on the holder."""
        self.write_marker(release=False)
        holder = dict(slot=self.bid, result=('saved', 'saved on its marker', {}))
        Q._end_slot(holder, self.entry, None)
        self.assertEqual(holder['retained'], self.bid)
        self.assertNotIn('booking_released', holder)
        self.assertEqual(Q._released_fields(holder), {})
        b = self.ledger()
        self.assertEqual((b['retained']['run'], b['retained']['day']), (RUN, DAY))
        self.assertFalse((C.RELEASED / (self.bid + '.json')).exists())

    def test_no_marker_at_all_retains(self):
        holder = dict(slot=self.bid, result=('saved', 'x', {}))
        Q._end_slot(holder, self.entry, None)
        self.assertEqual(holder['retained'], self.bid)


class ResumeRebooks(Base):
    def release_first(self):
        self.write_marker(release=True)
        holder = dict(slot=self.bid, result=('saved', 'saved', {}))
        Q._end_slot(holder, self.entry, None)
        return Q._released_fields(holder)

    def test_resume_rebooks_on_free_whole_cores_and_records_the_new_set(self):
        """Contract (3): the resume of a released day re-books through the ledger: the resolver's whole-cores-first
        lane (here the box is idle: 0-15,32-47 = 16 whole cores), booked, owned and RETAINED for the owner at once, the
        new set on the owner binding as `rebooked`; the entry is back in line with that set."""
        facts = self.release_first()
        self.queue_doc(**facts)
        out = Q.resume_owner(RUN, DAY, 'toy', rebook=True)
        owner = out['resumed']['owner']
        self.assertEqual(R(C.cpu_list(owner['cpus'])), R('0-15,32-47'))
        self.assertEqual(owner['rebooked']['previous_booking'], self.bid)
        self.assertEqual(owner['rebooked']['cpus'], owner['cpus'])
        self.assertFalse(owner['rebooked']['fallback'])
        self.assertFalse(owner['booking_released'])
        self.assertEqual(owner['released_history'][0]['rebooked_to'], owner['booking'])
        b = self.ledger(owner['booking'])
        self.assertEqual((b['retained']['run'], b['retained']['day'], b['retained']['attempt']), (RUN, DAY, ATTEMPT))
        self.assertEqual(b['owner']['attempt'], ATTEMPT)
        self.assertEqual(b['pids'], [])                                       # retained: no live holder until admission
        entry = Q.load('root')['entries'][0]
        self.assertEqual(entry['state'], 'queued')
        self.assertEqual(entry['owner']['booking'], owner['booking'])
        self.assertEqual(entry['owner_rebooks'][0]['rule'], 're-booked at resume after a fleet-gate release (B4)')

    def test_resume_rebooks_beside_the_grown_holder_on_the_fallback_when_only_siblings_are_free(self):
        """The holder grew to 48 of the 64 after the release: the resume gets the 16 remaining CPUs it can (the
        allocation says FALLBACK on the record when it had to take hyperthread siblings) -- never a 32 cut smaller."""
        facts = self.release_first()
        self.write(booking('day-run-20231018-holder', list(range(32)), run='fleet-a', day='20231018', retained=True))
        self.queue_doc(**facts)
        out = Q.resume_owner(RUN, DAY, 'toy', rebook=True)
        self.assertEqual(R(C.cpu_list(out['resumed']['owner']['cpus'])), R('32-63'))
        self.assertTrue(out['resumed']['owner']['rebooked']['fallback'])

    def test_resume_refuses_loudly_when_no_lane_is_free(self):
        """Contract (3), the refusal: the holder grew to all 64 -> no 32-CPU lane -> SystemExit naming the released
        booking, the CPUs asked and the resolver's reason; the entry stays saved, nothing re-queued, nothing booked."""
        facts = self.release_first()
        self.write(booking('day-run-20231018-holder', list(range(64)), run='fleet-a', day='20231018', retained=True))
        self.queue_doc(**facts)
        with self.assertRaises(SystemExit) as ctx:
            Q.resume_owner(RUN, DAY, 'toy', rebook=True)
        text = str(ctx.exception)
        self.assertIn(self.bid, text)
        self.assertIn('no 32-CPU lane is free', text)
        self.assertIn('0 free of 32 needed', text)
        self.assertEqual(Q.load('root')['entries'][0]['state'], 'saved')
        self.assertEqual([p.name for p in C.LEDGER.glob('*.json')], ['day-run-20231018-holder.json'])

    def test_rebook_is_one_ledger_lock_so_a_grow_cannot_take_the_lane_in_between(self):
        """Contract (4): rebook_for_owner holds the ledger lock across resolve + book + retain. Observed through the
        lock itself: a grow attempted from inside the resolver (another ledger writer at exactly that moment) finds the
        lock held (flock would block) -- here it is proven by the ledger state the grow sees afterwards: once the
        rebook returns, the holder's grow to 64 is refused the re-booked CPUs (waiting), never granted them."""
        self.release_first()
        self.write(booking('day-run-20231018-holder', list(range(16, 32)) + list(range(48, 64)),
                           run='fleet-a', day='20231018', retained=True))
        b, out = C.rebook_for_owner(RUN, DAY, ATTEMPT, 32, 'day-slot-resume', 'c0ffee', window=0.01)
        self.assertEqual(out['status'], 'rebooked')
        self.assertEqual(R(out['cpus']), R('0-15,32-47'))
        _, grow = C.grow('day-run-20231018-holder', 64, 'classroom wants all 64', window=0.01)
        self.assertEqual(grow['status'], 'waiting')                          # the re-booked lane is taken, not free
        self.assertIn('0 free of the 32 more', grow['reason'])


class OneBoxPathUnchanged(Base):
    def test_resume_without_a_release_record_never_calls_the_rebook(self):
        """Contract (5): a retained day (no fleet setting, no release) resumes on exactly its set; rebook_for_owner is
        never reached (it would raise here)."""
        self.write_marker(release=False)
        holder = dict(slot=self.bid, result=('saved', 'saved', {}))
        Q._end_slot(holder, self.entry, None)
        self.queue_doc()
        saved = C.rebook_for_owner
        C.rebook_for_owner = lambda *a, **k: (_ for _ in ()).throw(AssertionError('rebook called on the one-box path'))
        try:
            out = Q.resume_owner(RUN, DAY, 'toy')
        finally:
            C.rebook_for_owner = saved
        owner = out['resumed']['owner']
        self.assertEqual(owner['booking'], self.bid)
        self.assertEqual(owner['cpus'], self.owner['cpus'])
        self.assertNotIn('rebooked', owner)
        self.assertNotIn('booking_released', owner)

    def test_request_save_without_the_flag_writes_the_marker_as_before(self):
        """request_save(release_booking=False) adds NO key to the marker body; with the flag the two keys are added."""
        self.queue_doc(state='running')
        out = Q.request_save(RUN, DAY, 'toy')
        body = json.loads(Path(out['marker']).read_bytes())
        self.assertEqual(sorted(body), ['attempt', 'booking', 'by', 'cpus', 'day', 'requested_at', 'requested_utc', 'run', 'schema'])
        self.assertIsNone(Q._standing_release(self.entry))
        os.remove(out['marker'])
        Q.load('root')['entries'][0]['save_request'] = None
        doc = Q.load('root'); doc['entries'][0]['save_request'] = None; Q.save('root', doc)
        out = Q.request_save(RUN, DAY, 'toy', release_booking=True, release_reason='fleet gate (toy)')
        body = json.loads(Path(out['marker']).read_bytes())
        self.assertTrue(body['release_booking'])
        self.assertEqual(body['release_reason'], 'fleet gate (toy)')
        self.assertEqual(Q._standing_release(self.entry)['release_reason'], 'fleet gate (toy)')
        self.assertIn('RELEASED', out['note'])


if __name__ == '__main__':
    unittest.main()
