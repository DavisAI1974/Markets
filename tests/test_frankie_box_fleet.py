"""Toys for frankie_box_fleet (the fleet day list + cross-box classroom claim, session 8). Standard library only; the
file-backed fake store (FRANKIE_FLEET_S3_FAKE) gives the real conditional-write semantics (O_EXCL), so two racers hit
the real put_if_absent. No boto3, no S3, nothing runs on a box. Run: python -m unittest tests.test_frankie_box_fleet"""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'deploy' / 'aws' / 'box'))
import frankie_box_fleet as F  # noqa: E402


class FleetBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = dict(os.environ)
        os.environ['FRANKIE_FLEET_DAY_LIST'] = 'fleet/run-20231018'   # prefix under the default granite bucket
        os.environ['FRANKIE_FLEET_S3_FAKE'] = self.tmp
        os.environ['FRANKIE_FLEET_INSTANCE'] = 'i-aaaa'
        os.environ.pop('FRANKIE_FLEET_BUCKET', None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)

    def store_for(self, instance):
        os.environ['FRANKIE_FLEET_INSTANCE'] = instance
        return F.store()


class TestConfig(FleetBase):
    def test_enabled_and_location(self):
        self.assertTrue(F.enabled())
        bucket, prefix, region = F.location()
        self.assertEqual(bucket, F.DEFAULT_BUCKET)
        self.assertEqual(prefix, 'fleet/run-20231018')
        self.assertEqual(region, 'us-east-1')

    def test_location_bucket_in_value(self):
        os.environ['FRANKIE_FLEET_DAY_LIST'] = 'frankie-granite42-568968024170-us-east-1/fleet/x'
        bucket, prefix, _ = F.location()
        self.assertEqual(bucket, 'frankie-granite42-568968024170-us-east-1')
        self.assertEqual(prefix, 'fleet/x')

    def test_disabled_when_unset(self):
        os.environ.pop('FRANKIE_FLEET_DAY_LIST')
        self.assertFalse(F.enabled())


class TestClaimRace(FleetBase):
    def test_two_writers_race_one_wins(self):
        """The core guarantee: two boxes claiming the same day; exactly one wins the conditional write."""
        results, barrier = {}, threading.Barrier(2)

        def claim(instance):
            st = F.FakeStore(*F.location()[:2], self.tmp)   # each thread its own store on the same backing dir
            barrier.wait()
            results[instance] = F.claim_day('e2e-a', '20231018', 'root', 'c0ffee', st=st, instance=instance)

        threads = [threading.Thread(target=claim, args=(i,)) for i in ('i-box1', 'i-box2')]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        winners = [i for i, r in results.items() if r['won']]
        self.assertEqual(len(winners), 1, 'exactly one box wins the claim; got %s' % results)
        losers = [i for i, r in results.items() if not r['won']]
        self.assertEqual(results[losers[0]]['holder'], winners[0])

    def test_reclaim_by_same_box_is_a_win(self):
        st = self.store_for('i-box1')
        self.assertTrue(F.claim_day('e2e-a', '20231018', 'root', 'c0ffee', st=st)['won'])
        again = F.claim_day('e2e-a', '20231018', 'root', 'c0ffee', st=st)
        self.assertTrue(again['won'])        # idempotent for the same holder
        self.assertEqual(again['holder'], 'i-box1')


class TestLease(FleetBase):
    def test_acquire_then_another_box_waits(self):
        st1 = self.store_for('i-box1')
        F.record_root_finished('e2e-a', '20231018', st=st1, instance='i-box1', epoch=100)
        got1 = F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st1, instance='i-box1')
        self.assertTrue(got1['acquired'])

        st2 = self.store_for('i-box2')
        F.record_root_finished('e2e-a', '20231019', st=st2, instance='i-box2', epoch=200)
        got2 = F.acquire_classroom_lease('e2e-a', '20231019', 'c0ffee', st=st2, instance='i-box2')
        self.assertFalse(got2['acquired'])       # one global lease: box2 waits
        self.assertEqual(got2['holder'], 'i-box1')

    def test_release_lets_the_next_box_in(self):
        st1 = self.store_for('i-box1')
        F.record_root_finished('e2e-a', '20231018', st=st1, instance='i-box1', epoch=100)
        F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st1, instance='i-box1')
        rel = F.release_classroom_lease('e2e-a', '20231018', st=st1, instance='i-box1')
        self.assertEqual(rel['status'], 'released')
        self.assertIsNone(F.lease_holder(st=st1))   # lease gone; box1's waiting marker dropped

        st2 = self.store_for('i-box2')
        F.record_root_finished('e2e-a', '20231019', st=st2, instance='i-box2', epoch=200)
        got2 = F.acquire_classroom_lease('e2e-a', '20231019', 'c0ffee', st=st2, instance='i-box2')
        self.assertTrue(got2['acquired'])

    def test_release_by_non_holder_is_refused(self):
        st1 = self.store_for('i-box1')
        F.record_root_finished('e2e-a', '20231018', st=st1, instance='i-box1', epoch=100)
        F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st1, instance='i-box1')
        st2 = self.store_for('i-box2')
        rel = F.release_classroom_lease('e2e-a', '20231018', st=st2, instance='i-box2')
        self.assertEqual(rel['status'], 'not_held')
        self.assertIsNotNone(F.lease_holder(st=st2))   # box1 still holds it

    def test_fairness_first_to_finish_first(self):
        """The later-finishing box yields to the earlier one while the earlier marker is live."""
        st_late = self.store_for('i-late')
        F.record_root_finished('e2e-a', '20231020', st=st_late, instance='i-late', epoch=500)
        st_early = self.store_for('i-early')
        F.record_root_finished('e2e-a', '20231018', st=st_early, instance='i-early', epoch=100)
        # i-late tries first but a strictly earlier LIVE waiter (i-early) exists -> it yields
        late = F.acquire_classroom_lease('e2e-a', '20231020', 'c0ffee', st=st_late, instance='i-late',
                                         fair_wait=10_000)
        self.assertFalse(late['acquired'])
        self.assertIn('yielding', late['reason'])
        # i-early (earliest) acquires
        early = F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st_early, instance='i-early')
        self.assertTrue(early['acquired'])

    def test_cpu_not_ready_blocks_the_lease(self):
        # B4: the box cannot give the classroom its CPUs -> do NOT take the global lease (never hold it while blocked)
        os.environ['FRANKIE_FLEET_CPU_READY'] = 'no'
        st = self.store_for('i-box1')
        F.record_root_finished('e2e-a', '20231018', st=st, instance='i-box1', epoch=100)
        got = F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st, instance='i-box1')
        self.assertFalse(got['acquired'])
        self.assertIn('CPUs', got['reason'])
        self.assertIsNone(F.lease_holder(st=st))        # the lease was NOT taken
        os.environ.pop('FRANKIE_FLEET_CPU_READY')

    def test_cpu_ready_allows_the_lease(self):
        os.environ['FRANKIE_FLEET_CPU_READY'] = 'yes'
        st = self.store_for('i-box1')
        F.record_root_finished('e2e-a', '20231018', st=st, instance='i-box1', epoch=100)
        got = F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st, instance='i-box1')
        self.assertTrue(got['acquired'])
        os.environ.pop('FRANKIE_FLEET_CPU_READY')

    def test_heartbeat_waiting_refreshes_liveness_not_order(self):
        st = self.store_for('i-box1')
        F.record_root_finished('e2e-a', '20231018', st=st, instance='i-box1', epoch=100.0)
        before = F.store().get(F.waiting_key('e2e-a', '20231018'))
        F.heartbeat_waiting('e2e-a', '20231018', st=st, instance='i-box1')
        after = F.store().get(F.waiting_key('e2e-a', '20231018'))
        self.assertEqual(after['root_finish_epoch'], 100.0)                 # ORDER is unchanged
        self.assertGreaterEqual(after['heartbeat_epoch'], before['heartbeat_epoch'])   # liveness refreshed

    def test_dead_earlier_waiter_does_not_deadlock(self):
        os.environ['FRANKIE_FLEET_CPU_READY'] = 'yes'
        # an earlier finisher whose heartbeat is ancient (crashed); a later LIVE box must not yield to it forever
        st_dead = self.store_for('i-dead')
        F.record_root_finished('e2e-a', '20231018', st=st_dead, instance='i-dead', epoch=100)
        marker = st_dead.get(F.waiting_key('e2e-a', '20231018'))
        marker['heartbeat_epoch'] = 1.0                  # ancient: the dead box stopped polling
        st_dead.put(F.waiting_key('e2e-a', '20231018'), marker)
        st_late = self.store_for('i-late')
        F.record_root_finished('e2e-a', '20231020', st=st_late, instance='i-late', epoch=500)
        got = F.acquire_classroom_lease('e2e-a', '20231020', 'c0ffee', st=st_late, instance='i-late', fair_wait=300)
        self.assertTrue(got['acquired'])                 # the stale earlier waiter did not block the line
        os.environ.pop('FRANKIE_FLEET_CPU_READY')

    def test_takeover_requires_force(self):
        st1 = self.store_for('i-box1')
        F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st1, instance='i-box1')
        st2 = self.store_for('i-box2')
        soft = F.takeover_classroom_lease('e2e-a', '20231018', 'c0ffee', 'greg', force=False, st=st2, instance='i-box2')
        self.assertEqual(soft['status'], 'refused')          # never automatic
        hard = F.takeover_classroom_lease('e2e-a', '20231018', 'c0ffee', 'greg', force=True, st=st2, instance='i-box2')
        self.assertEqual(hard['status'], 'taken_over')
        self.assertEqual(F.lease_holder(st=st2)['holder_instance'], 'i-box2')
        self.assertEqual(hard['prior']['holder_instance'], 'i-box1')   # old holder recorded in the audit


class TestDayList(FleetBase):
    def test_seed_is_idempotent(self):
        st = self.store_for('i-op')
        a = [{'day': '20231018', 'box': 'i-box1'}, {'day': '20231019', 'box': 'i-box1', 'spot': True}]
        first = F.seed_day_list('e2e-a', a, 'c0ffee', st=st)
        self.assertEqual(first['status'], 'seeded')
        self.assertEqual(first['days'], 2)
        again = F.seed_day_list('e2e-a', a, 'c0ffee', st=st)
        self.assertEqual(again['status'], 'exists')       # create-only: two seeders safe

    def test_stage_state_advisory(self):
        st = self.store_for('i-op')
        F.seed_day_list('e2e-a', [{'day': '20231018', 'box': 'i-box1'}], 'c0ffee', st=st)
        F.set_day_stage_state('e2e-a', '20231018', 'root', 'done', st=st)
        doc = F.read_day_list(st=st)
        self.assertEqual(doc['days'][0]['stages']['root']['state'], 'done')


class TestDriverSupport(FleetBase):
    def test_box_saved_days(self):
        import json as J
        qdir = Path(self.tmp) / 'q'
        qdir.mkdir()
        (qdir / 'root.json').write_text(J.dumps({'entries': [
            {'run': 'e2e-a', 'day': '20231018', 'state': 'saved'},
            {'run': 'e2e-a', 'day': '20231019', 'state': 'running'},
            {'run': 'e2e-a', 'day': '20231020', 'state': 'done', 'finish': {'state': 'saved'}},
            {'run': 'other', 'day': '20231021', 'state': 'saved'},
        ]}))
        got = F.box_saved_days('e2e-a', queue_dir=qdir)
        self.assertEqual(sorted(got), ['20231018', '20231020'])   # saved, or done+finish saved, this run only

    def test_claim_day_off_is_error_exit_2(self):
        import subprocess
        box = str(HERE.parent / 'deploy' / 'aws' / 'box' / 'frankie_box_fleet.py')
        env = {k: v for k, v in os.environ.items() if k not in ('FRANKIE_FLEET_DAY_LIST', 'FRANKIE_FLEET_CONFIG')}
        env['FRANKIE_FLEET_CONFIG'] = str(Path(self.tmp) / 'no-such-config.json')   # fleet mode OFF
        out = subprocess.run([sys.executable, box, 'claim-day', '--run', 'e2e-a', '--day', '20231018',
                              '--commit', 'c0ffee'], env=env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)       # B3: OFF is an error for claim-day, never a silent win (0)


class TestConfigFile(FleetBase):
    def test_box_config_turns_fleet_on(self):
        import json as J
        cfg = Path(self.tmp) / 'fleet.json'
        cfg.write_text(J.dumps({'day_list': 'fleet/run-cfg', 'region': 'us-east-1', 'instance': 'i-cfg'}))
        env = {k: v for k, v in os.environ.items()
               if k not in ('FRANKIE_FLEET_DAY_LIST', 'FRANKIE_FLEET_INSTANCE')}   # env wins; drop it to test config
        saved = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(env)
            os.environ['FRANKIE_FLEET_CONFIG'] = str(cfg)
            self.assertTrue(F.enabled())                      # env unset, config names a day list -> on
            self.assertEqual(F.location()[1], 'fleet/run-cfg')
            self.assertEqual(F.instance_id(), 'i-cfg')
        finally:
            os.environ.clear()
            os.environ.update(saved)


class TestCLI(FleetBase):
    def test_claim_day_cli(self):
        import subprocess
        box = str(HERE.parent / 'deploy' / 'aws' / 'box' / 'frankie_box_fleet.py')
        env = dict(os.environ, FRANKIE_FLEET_DAY_LIST='fleet/run-x', FRANKIE_FLEET_S3_FAKE=self.tmp,
                   FRANKIE_FLEET_INSTANCE='i-cli')
        argv = [sys.executable, box, 'claim-day', '--run', 'e2e-a', '--day', '20231018', '--commit', 'c0ffee']
        first = subprocess.run(argv, env=env, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)       # the claim won
        second = subprocess.run(argv, env=dict(env, FRANKIE_FLEET_INSTANCE='i-other'), capture_output=True, text=True)
        self.assertEqual(second.returncode, 1)                    # a second box loses -> exit 1 (user-data skips it)


class TestGate(FleetBase):
    def test_gate_proceeds_when_lease_free(self):
        out = Path(self.tmp) / 'handoff' / 'day' / 'teacher'
        st = self.store_for('i-box1')
        rec = F.classroom_gate('e2e-a', '20231018', 'teacher', out, '/code', 'c0ffee', st=st, start_wait=False)
        self.assertEqual(rec['decision'], 'proceed')
        self.assertEqual(F.lease_holder(st=st)['holder_instance'], 'i-box1')
        self.assertTrue((out / 'fleet-gate.json').is_file())

    def test_gate_ineligible_box_refused_the_lease(self):
        # a Spot / ClassroomEligible=false box is refused the lease and does NOT acquire or wait (decision 2)
        os.environ['FRANKIE_FLEET_CLASSROOM_ELIGIBLE'] = 'false'
        out = Path(self.tmp) / 'handoff' / 'spotday' / 'teacher'
        st = self.store_for('i-spot')
        rec = F.classroom_gate('e2e-a', '20231018', 'teacher', out, '/code', 'c0ffee', st=st, start_wait=False)
        self.assertEqual(rec['decision'], 'ineligible')
        self.assertIsNone(F.lease_holder(st=st))      # it never took the lease
        os.environ.pop('FRANKIE_FLEET_CLASSROOM_ELIGIBLE')

    def test_gate_waits_when_lease_held(self):
        # box1 holds the lease for its day
        st1 = self.store_for('i-box1')
        F.record_root_finished('e2e-a', '20231018', st=st1, instance='i-box1', epoch=100)
        F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st1, instance='i-box1')
        # box2 reaches the gate for a different day; the single lease is held -> WAIT (no wait unit started in the toy)
        out = Path(self.tmp) / 'handoff' / 'day19' / 'teacher'
        st2 = self.store_for('i-box2')
        rec = F.classroom_gate('e2e-a', '20231019', 'teacher', out, '/code', 'c0ffee', st=st2, start_wait=False)
        self.assertEqual(rec['decision'], 'waiting')
        self.assertEqual(rec['holder'], 'i-box1')
        self.assertIsNotNone(rec['position'])


if __name__ == '__main__':
    unittest.main()
