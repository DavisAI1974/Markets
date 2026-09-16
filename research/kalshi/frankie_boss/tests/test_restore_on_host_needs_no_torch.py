"""The on-host restore runs under the stock host interpreter: it must never import torch or Frankie.

The third host restore (2026-09-16) got through 18 GB of bulk, six archives and 170 package files,
then died in its audit step on `ModuleNotFoundError: torch`, because the audit modules were imported
through the package whose __init__ imports torch. This test runs the restore script's module loader
in a subprocess with torch and the Frankie package blocked, and loads both audit modules that way.
"""
import subprocess
import sys
import unittest
from pathlib import Path

OPERATIONS = Path(__file__).resolve().parent.parent / 'operations'
SCRIPT = OPERATIONS / 'restore_sunday_set_on_host.py'

PROBE = r'''
import sys
sys.modules['torch'] = None                      # any `import torch` now raises ImportError
sys.modules['research.kalshi.frankie_boss'] = None
import importlib.util
spec = importlib.util.spec_from_file_location('restore_on_host', sys.argv[1])
restore = importlib.util.module_from_spec(spec); spec.loader.exec_module(restore)
operations = sys.argv[2]
A = restore.load_module_by_path('audit_sunday_restoration_manifest', operations + '/audit_sunday_restoration_manifest.py')
R = restore.load_module_by_path('restore_sunday_working_tree_identity', operations + '/restore_sunday_working_tree_identity.py')
print('ok', callable(A.audit), callable(R.audit_working_tree))
'''


class RestoreNeedsNoTorch(unittest.TestCase):
    def test_loads_with_torch_and_package_blocked(self):
        proc = subprocess.run([sys.executable, '-c', PROBE, str(SCRIPT), str(OPERATIONS)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), 'ok True True')

    def test_script_has_no_package_import(self):
        source = SCRIPT.read_text(encoding='utf-8')
        self.assertNotIn('from research.kalshi.frankie_boss', source)
        self.assertNotIn('import torch', source)


if __name__ == '__main__':
    unittest.main()
