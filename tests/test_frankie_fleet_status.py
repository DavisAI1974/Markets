"""Toys for the fleet status probe (frankie_fleet_status.collect/render) and the fleet workflow's shape (session 8).
Standard library + pyyaml for the workflow parse; a local day-list JSON (no boto3, no AWS). Run:
python -m unittest tests.test_frankie_fleet_status"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'deploy' / 'aws' / 'box'))
import frankie_fleet_status as P  # noqa: E402

WORKFLOW = ROOT / '.github' / 'workflows' / 'frankie_fleet.yml'


def toy_day_list():
    return {
        'schema': 'FRANKIE_FLEET_DAY_LIST_V1', 'run': 'e2e-a',
        'days': [
            {'day': '20231018', 'box': 'i-box1', 'current_stage': 'classroom',
             'stages': {'root': {'state': 'done'}, 'teacher': {'state': 'done'},
                        'classroom': {'state': 'lease_held'}}},
            {'day': '20231019', 'box': 'i-box1', 'current_stage': 'root', 'stages': {'root': {'state': 'done'}}},
            {'day': '20231020', 'box': 'i-box2', 'current_stage': 'jev', 'done_utc': '2026-10-08T15:00:00Z',
             'stages': {'jev': {'state': 'done'}}},
        ],
        '_lease': {'holder_instance': 'i-box1', 'run': 'e2e-a', 'day': '20231018'},
    }


class TestCollect(unittest.TestCase):
    def test_join_day_list_and_ec2(self):
        dl = toy_day_list()
        ec2 = [{'instance': 'i-box1', 'state': 'running', 'type': 'r7i.16xlarge'},
               {'instance': 'i-box2', 'state': 'running', 'type': 'r7i.16xlarge'}]
        status = P.collect(day_list=dl, lease=dl['_lease'], ec2_instances=ec2, region='us-east-1')
        self.assertEqual(status['total_days'], 3)
        box1 = next(r for r in status['instances'] if r['instance'] == 'i-box1')
        self.assertEqual(sorted(box1['assigned_days']), ['20231018', '20231019'])
        d18 = next(d for d in box1['days'] if d['day'] == '20231018')
        self.assertTrue(d18['holds_lease'])             # classroom lease_held + not done -> in the classroom
        self.assertEqual(d18['lease_holder'], 'i-box1')
        box2 = next(r for r in status['instances'] if r['instance'] == 'i-box2')
        d20 = box2['days'][0]
        self.assertEqual(d20['status'], 'done')         # jev + done_utc -> done
        self.assertFalse(d20['holds_lease'])

    def test_box_with_no_live_instance(self):
        dl = toy_day_list()
        status = P.collect(day_list=dl, lease=None, ec2_instances=[], region='us-east-1')
        states = {r['instance']: r['state'] for r in status['instances']}
        self.assertIn('i-box1', states)
        self.assertEqual(states['i-box1'], '(not in DescribeInstances)')   # on the list, not launched/terminated

    def test_gate_state_and_unassigned_shown(self):
        # N8: a waiting/ineligible day shows its gate state; S5/N8: a day with no box is shown, not dropped
        dl = {'schema': 'FRANKIE_FLEET_DAY_LIST_V1', 'run': 'e2e-a', 'days': [
            {'day': '20231018', 'box': 'i-box1', 'current_stage': 'teacher',
             'stages': {'classroom': {'state': 'waiting'}}},
            {'day': '20231019', 'box': None},   # not launched / not claimed yet
            {'day': '20231020', 'box': 'i-spot', 'current_stage': 'teacher',
             'stages': {'classroom': {'state': 'ineligible'}}},
        ]}
        status = P.collect(day_list=dl, lease=None, ec2_instances=[], region='us-east-1')
        self.assertIn('20231019', status['unassigned_days'])
        text = P.render(status)
        self.assertIn('gate:waiting', text)
        self.assertIn('gate:ineligible', text)
        self.assertIn('(unassigned)', text)

    def test_store_error_shown_not_free(self):
        # S11: a store error is surfaced, not rendered as "lease: free"
        status = P.collect(day_list=None, lease=None, ec2_instances=[], region='us-east-1',
                           store_error='AccessDenied: fleet/ prefix')
        self.assertIn('STORE ERROR', P.render(status))

    def test_render_mentions_lease_and_days(self):
        dl = toy_day_list()
        status = P.collect(day_list=dl, lease=dl['_lease'], ec2_instances=[], region='us-east-1')
        text = P.render(status)
        self.assertIn('classroom lease: i-box1', text)
        self.assertIn('20231018', text)
        self.assertIn('[classroom]', text)              # the day holding the lease is flagged


class TestProbeCLI(unittest.TestCase):
    def test_local_day_list_runs_without_boto3(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as handle:
            json.dump(toy_day_list(), handle)
            path = handle.name
        out = subprocess.run([sys.executable, str(ROOT / 'deploy/aws/box/frankie_fleet_status.py'),
                              '--day-list', path], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('fleet status', out.stdout)
        self.assertIn('20231020@done', out.stdout)


class TestWorkflowShape(unittest.TestCase):
    def test_yaml_parses(self):
        import yaml
        doc = yaml.safe_load(WORKFLOW.read_text())
        # the 'on' key parses as True in YAML 1.1; accept either
        trig = doc.get('on') or doc.get(True)
        self.assertIn('workflow_dispatch', trig)
        opts = trig['workflow_dispatch']['inputs']['action']['options']
        self.assertEqual(set(opts), {'plan', 'launch', 'status', 'stop-all'})
        self.assertEqual(doc['concurrency']['cancel-in-progress'], False)   # workflow-level, like frankie_box_run.yml
        self.assertEqual(doc['jobs']['fleet']['if'], "github.repository == 'DavisAI1974/Markets'")

    def test_launch_guards_on_confirm(self):
        text = WORKFLOW.read_text()
        self.assertIn('GREG_GO_AWS_STACK', text)
        # the launch step refuses unless the confirm equals the exact token
        self.assertIn('if [ "$CONFIRM" != "GREG_GO_AWS_STACK" ]', text)
        # stop-all never terminates and protects the main boxes
        self.assertIn('stop_instances', text)
        self.assertNotIn('terminate_instances', text)
        self.assertIn('i-035994afa8bdf66a5 i-0d17573dbce871520', text)

    def test_inline_bash_snippets_parse(self):
        """Every `run: |` shell block in the workflow passes bash -n (extracted and checked)."""
        import yaml
        doc = yaml.safe_load(WORKFLOW.read_text())
        steps = doc['jobs']['fleet']['steps']
        checked = 0
        for step in steps:
            run = step.get('run')
            if not run or run.lstrip().startswith('python - <<'):   # heredoc-wrapped python is not pure bash
                continue
            res = subprocess.run(['bash', '-n'], input=run, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, 'bash -n failed for step %r: %s' % (step.get('name'), res.stderr))
            checked += 1
        self.assertGreater(checked, 0)


if __name__ == '__main__':
    unittest.main()
