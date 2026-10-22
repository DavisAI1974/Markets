import pathlib
import unittest
from family_guarded_recovery import guarded_source, validate_capture
from family_completion_hook import coordinator_source


class GuardedRecoveryTests(unittest.TestCase):
    def test_completion_hook_pins_the_isolated_recovery_source(self):
        self.assertEqual(coordinator_source(dict(base='/base',coordinator_source='/guarded/resume_multibox_candidate.py')),
                         pathlib.Path('/guarded/resume_multibox_candidate.py'))
        self.assertEqual(coordinator_source(dict(base='/base')),
                         pathlib.Path('/base/full-context-audit/scripts/resume_multibox_candidate.py'))

    def test_only_dispatch_pacing_and_host_headroom_change(self):
        import resume_multibox_candidate
        original=pathlib.Path(resume_multibox_candidate.__file__).read_text()
        guarded=guarded_source(original)
        self.assertNotIn("if args.worker_id!='A' and time.monotonic()-last_dispatch < 3:",guarded)
        self.assertIn('if time.monotonic()-last_dispatch < 3:',guarded)
        self.assertIn('Budget(total, 192*GIB',guarded)
        restored=guarded.replace('if time.monotonic()-last_dispatch < 3:',"if args.worker_id!='A' and time.monotonic()-last_dispatch < 3:").replace('Budget(total, 192*GIB','Budget(total, 64*GIB').replace('memory_reserve_gib=192','memory_reserve_gib=64')
        self.assertEqual(restored,original)
        compile(guarded,'guarded-coordinator','exec')

    def test_capture_rejects_duplicate_task_cpu_and_unowned_work(self):
        jobs=[dict(pid=1,token='t',kind='core',cohort=['o','1','2'],model='m',cpu=0)]
        owned={('o','1','2')}
        validate_capture(jobs,owned,{2:dict(parent=1)})
        with self.assertRaises(ValueError):validate_capture(jobs*2,owned,{})
        with self.assertRaises(ValueError):validate_capture(jobs,set(),{})
        with self.assertRaises(ValueError):validate_capture(jobs,owned,{2:dict(parent=99)})


if __name__=='__main__':unittest.main()
