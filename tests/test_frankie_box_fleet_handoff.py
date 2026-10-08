"""Toy for the fleet hooks inside frankie_box_stage_handoff.boundary (session 8): the ROOT->classroom gate (proceed /
wait) and the one-box default being unchanged when fleet mode is off. The heavy internals (the validator child, the
queue save) are stubbed so the toy exercises the NEW branch logic with the real fleet store (file-backed fake).
Run: python -m unittest tests.test_frankie_box_fleet_handoff"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'deploy' / 'aws' / 'box'))
import frankie_box_fleet as F  # noqa: E402
import frankie_box_stage_handoff as H  # noqa: E402


class FakeRun:
    def __init__(self, root):
        self.dir = str(root)
        self.plan = {'run': 'e2e-a'}
        self.code_root = str(HERE.parent)
        self.stop_marker = str(Path(root) / 'marker.json')
        self.owner = {'cpus': [0, 1], 'attempt': 1}
        self.slot_booking = None
        self.cores = None

    def receipt_path(self, stage, key):
        return str(Path(self.dir) / ('%s-%s-receipt.json' % (stage, key)))


class HandoffFleetBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = dict(os.environ)
        self._orig_validate = H.run_validate
        self._orig_save = H.request_own_save
        # a passing validation and a no-op save, so the toy reaches the NEW fleet branch deterministically
        H.run_validate = lambda run, stage, key, out_dir, pins_args, lane, log: (0, {'totals': {'pinned': 3, 'ok': 3}}, 'log')
        H.request_own_save = lambda run, e, by: dict(how='stub', marker=run.stop_marker, standing=True, by=by)
        os.environ['FRANKIE_FLEET_S3_FAKE'] = self.tmp
        os.environ['FRANKIE_FLEET_INSTANCE'] = 'i-box1'
        os.environ['FRANKIE_FLEET_NO_WAIT_UNIT'] = '1'   # the toy never spawns the detached poller

    def tearDown(self):
        H.run_validate = self._orig_validate
        H.request_own_save = self._orig_save
        os.environ.clear()
        os.environ.update(self.env)

    def run_boundary(self, run_dir, arm=True):
        run = FakeRun(run_dir)
        record = dict(status='done', days=['20231018'])
        return H.boundary(run, {'day': '20231018', 'classroom_arm': arm}, 'teacher', 'day', record,
                          code_root=run.code_root, commit='c0ffee' * 6 + 'cafe', log=lambda *a: None)


class TestFleetOff(HandoffFleetBase):
    def test_off_takes_no_fleet_branch(self):
        """FRANKIE_FLEET_DAY_LIST unset -> _fleet() is None -> the teacher boundary runs its normal path, not a fleet
        one (here it validates and, with no clean work, returns 'validated')."""
        os.environ.pop('FRANKIE_FLEET_DAY_LIST', None)
        self.assertIsNone(H._fleet())
        rec = self.run_boundary(Path(self.tmp) / 'off')
        self.assertNotIn(rec['status'], ('fleet_proceed', 'fleet_waiting'))
        self.assertNotIn('fleet_gate', rec)


class TestFleetGate(HandoffFleetBase):
    def setUp(self):
        super().setUp()
        os.environ['FRANKIE_FLEET_DAY_LIST'] = 'fleet/run-20231018'

    def test_proceed_when_lease_free(self):
        rec = self.run_boundary(Path(self.tmp) / 'proceed')
        self.assertEqual(rec['status'], 'fleet_proceed')
        self.assertEqual(rec['fleet_gate']['decision'], 'proceed')
        self.assertEqual(F.lease_holder(st=F.store())['holder_instance'], 'i-box1')

    def test_non_arm_day_skips_the_gate(self):
        # S3: a non-arm day runs no classroom, so it must not take the global lease
        rec = self.run_boundary(Path(self.tmp) / 'nonarm', arm=False)
        self.assertNotIn(rec['status'], ('fleet_proceed', 'fleet_waiting'))
        self.assertIsNone(F.lease_holder(st=F.store()))

    def test_wait_when_lease_held_by_another(self):
        # another box holds the single global lease for its own day
        other = F.store()
        F.acquire_classroom_lease('e2e-a', '20231099', 'c0ffee', st=other, instance='i-box2')
        rec = self.run_boundary(Path(self.tmp) / 'wait')
        self.assertEqual(rec['status'], 'fleet_waiting')
        self.assertEqual(rec['fleet_gate']['decision'], 'waiting')
        self.assertEqual(rec['fleet_gate']['holder'], 'i-box2')
        self.assertTrue(rec['save']['standing'])        # the day was saved so it stops here

    def test_release_on_failed_classroom(self):
        # S2: a classroom that FAILED must still release the global lease (before the nothing_to_hand_off return)
        st = F.store()
        F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st, instance='i-box1')
        run = FakeRun(Path(self.tmp) / 'failc')
        rec = H.boundary(run, {'day': '20231018'}, 'classroom', 'day', dict(status='failed'),
                         code_root=run.code_root, commit='c0ffee' * 6 + 'cafe', log=lambda *a: None)
        self.assertEqual(rec['status'], 'nothing_to_hand_off')         # a failed record is not handed off
        self.assertEqual(rec['fleet_release']['status'], 'released')   # but the lease was freed
        self.assertIsNone(F.lease_holder(st=F.store()))

    def test_release_at_classroom_boundary(self):
        # this box holds the lease; a classroom boundary releases it (idempotent)
        st = F.store()
        F.acquire_classroom_lease('e2e-a', '20231018', 'c0ffee', st=st, instance='i-box1')
        run = FakeRun(Path(self.tmp) / 'release')
        record = dict(status='done', classroom=str(Path(self.tmp) / 'release' / 'classroom'))
        rec = H.boundary(run, {'day': '20231018'}, 'classroom', 'day', record,
                         code_root=run.code_root, commit='c0ffee' * 6 + 'cafe', log=lambda *a: None)
        self.assertEqual(rec['fleet_release']['status'], 'released')
        self.assertIsNone(F.lease_holder(st=F.store()))


if __name__ == '__main__':
    unittest.main()
