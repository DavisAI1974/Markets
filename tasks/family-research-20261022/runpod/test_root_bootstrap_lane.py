"""Exercise the real lane cache before a producer narrows its coordinator."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class BootstrapLaneTests(unittest.TestCase):
    def test_preserves_startup_lane_before_producer_imports(self):
        bootstrap = Path(__file__).with_name('runpod_root_bootstrap.py').resolve()
        lane = subprocess.check_output(['git', 'show',
            '6f9178b:deploy/aws/box/frankie_box_lane_pin.py'])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'frankie_box_lane_pin.py').write_bytes(lane)
            (root/'frankie_box_bedrock.py').write_text(
                'import os\ndef load_producers(path):\n    os.sched_getaffinity = lambda pid: {2}\n')
            (root/'frankie_box_parallel_evidence.py').write_text('')
            (root/'entry.py').write_text(
                'import frankie_box_lane_pin as lane\n'
                'assert lane.lane_cpus() == [2, 4, 6], lane.lane_cpus()\n')
            driver = ('import os,runpy,sys\n'
                      'os.sched_getaffinity = lambda pid: {2, 4, 6}\n'
                      'sys.argv = sys.argv[1:]\n'
                      'runpy.run_path(sys.argv[0], run_name="__main__")\n')
            (root/'driver.py').write_text(driver)
            env = {k:v for k,v in os.environ.items() if k not in ('FRANKIE_LANE_CPUS','FRANKIE_BOOKED_CPUS')}
            result = subprocess.run([sys.executable, str(root/'driver.py'), str(bootstrap), str(root/'entry.py')],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
