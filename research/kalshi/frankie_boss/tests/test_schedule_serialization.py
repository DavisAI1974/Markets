"""Focused regression for V1 sorted-JSON schedule transport; no source replay."""
import copy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest

HERE=Path(__file__).resolve().parents[1]
package=types.ModuleType('schedule_boundary')
package.__path__=[str(HERE)]
sys.modules[package.__name__]=package
fix=importlib.import_module('schedule_boundary.verified_sunday_schedule')
fixture=Path(__file__).with_name('fixtures')/'actual_sunday_schedule_v1.json'

class ScheduleOrder(unittest.TestCase):
    def test_actual_sorted_schedule_and_corruption(self):
        value=json.loads(fixture.read_bytes())
        expected='f6922f7a4b93b44394c6683e3d7c45782f27e250c81987bd54414fb124c60e42'
        verified=fix.verified_schedule(value,expected_digest=expected)
        self.assertEqual(value,verified)
        self.assertEqual(len(verified['steps']),19)
        self.assertEqual(verified['terminal_delivery']['records_delivered'],57027)
        changed=copy.deepcopy(value)
        changed['steps'][0]['as_of']+=1
        with self.assertRaises(ValueError):
            fix.verified_schedule(changed,expected_digest=expected)
        extra=copy.deepcopy(value)
        extra['steps'][0]['unexpected']=1
        with self.assertRaises(ValueError):
            fix.verified_schedule(extra,expected_digest=expected)

if __name__=='__main__':unittest.main()
