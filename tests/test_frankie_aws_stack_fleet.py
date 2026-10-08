"""Toys for the fleet steps of frankie_aws_stack (session 8): the launch-template data shape, the fleet-launch quota
refusal and plan, and the golden-ami stopped-instance gate. A fake account answers the reads with canned responses and
records writes without performing them (apply=False), so nothing touches AWS. Run:
python -m unittest tests.test_frankie_aws_stack_fleet"""
import base64
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'deploy' / 'aws'))
import frankie_aws_stack as S  # noqa: E402


class NoSuchEntityException(Exception):
    pass


class FakeAccount(S.Account):
    """apply=False (writes are recorded, never performed); reads come from a canned table keyed by operation. An op not
    in the table raises a NoSuchEntity-shaped error (so 'absent' IAM resources read as missing); a canned value that is
    an Exception is raised; a callable is called with the params."""

    def __init__(self, canned):
        super().__init__(apply=False, say=lambda *a: None)
        self.canned = canned

    def read(self, service, region, operation, **params):
        if operation not in self.canned:
            raise NoSuchEntityException('NoSuchEntity: %s' % operation)
        value = self.canned[operation]
        if isinstance(value, Exception):
            raise value
        return value(params) if callable(value) else value


def args_for(argv):
    return S.build_parser().parse_args(argv)


class TestLaunchTemplateData(unittest.TestCase):
    def test_fleet_spec(self):
        data = S.launch_template_data(args_for(['--commit', 'a' * 40, '--run', 'e2e-a']))
        self.assertEqual(data['InstanceType'], 'r7i.16xlarge')
        self.assertEqual(data['InstanceInitiatedShutdownBehavior'], 'terminate')
        self.assertEqual(data['MetadataOptions']['HttpTokens'], 'required')
        self.assertEqual(data['MetadataOptions']['InstanceMetadataTags'], 'enabled')
        root = data['BlockDeviceMappings'][0]['Ebs']
        self.assertEqual(root['VolumeSize'], 3072)
        self.assertEqual(root['Iops'], 16000)
        self.assertEqual(root['Throughput'], 1000)
        self.assertEqual(root['KmsKeyId'], S.CMK_ARN)
        tags = {t['Key']: t['Value'] for t in data['TagSpecifications'][0]['Tags']}
        self.assertEqual(tags['Project'], 'frankie')
        self.assertEqual(tags['Role'], 'day-box')
        self.assertIn('Day', tags)       # placeholder the per-box launch fills

    def test_user_data_is_explicit(self):
        data = S.launch_template_data(args_for(['--commit', 'a' * 40, '--run', 'e2e-a', '--day-cpus', '32']))
        ud = base64.b64decode(data['UserData']).decode()
        self.assertIn('FRANKIE_FLEET_DAY_LIST', ud)          # fleet mode on for every box
        self.assertIn('DAY_CPUS=32', ud)                      # explicit
        self.assertIn('frankie_box_experiment.sh', ud)        # the existing run entrypoint
        self.assertIn('frankie_box_fleet.py', ud)             # the per-day claim
        self.assertIn('meta-data/tags/instance/Day', ud)      # reads its two days from its tags
        self.assertIn('rev-parse HEAD', ud)                   # decision 1: verify the checkout is the pinned commit
        self.assertIn('FRANKIE_FLEET_STAGE_V1', ud)           # decision 1: writes a staging receipt
        self.assertIn('stage-receipt.json', ud)


class TestFleetLaunch(unittest.TestCase):
    def canned(self, quota=256.0, running=()):
        return {'get_service_quota': {'Quota': {'Value': quota}},
                'describe_instances': {'Reservations': [{'Instances': list(running)}]}}

    def test_refuses_missing_run(self):
        acct = FakeAccount(self.canned())
        args = args_for(['--count', '2', '--days', '20231018,20231019', '--image-id', 'ami-1', '--commit', 'a' * 40])
        rec = S.step_fleet_launch(acct, args)   # no --run
        self.assertEqual(rec['status'], 'needs_input')
        self.assertIn('run', rec['reason'])
        self.assertEqual(len(rec['actions']), 0)

    def test_quota_refusal(self):
        acct = FakeAccount(self.canned(quota=256.0))
        args = args_for(['--run', 'e2e-a', '--count', '8', '--days', ','.join('2023101%d' % i for i in range(8)),
                         '--image-id', 'ami-1', '--commit', 'a' * 40])
        rec = S.step_fleet_launch(acct, args)
        self.assertEqual(rec['status'], 'refused')
        self.assertIn('512', rec['reason'])      # 8 x 64
        self.assertEqual(rec['checked']['headroom_vcpus'], 256)
        self.assertEqual(len(rec['actions']), 0)  # nothing launched

    def test_quota_counts_running_usage(self):
        running = [{'CpuOptions': {'CoreCount': 32, 'ThreadsPerCore': 2}}]  # a 64-vCPU box already running (on-demand)
        acct = FakeAccount(self.canned(quota=256.0, running=running))
        # 2 boxes need 128 vCPUs; headroom is 256 - 64 = 192, so it fits; a 3rd box (192) would exactly fill it, a 4th
        # (256) would exceed. Here 2 boxes plan.
        args = args_for(['--run', 'e2e-a', '--count', '2', '--days', '20231018,20231019,20231020,20231021',
                         '--image-id', 'ami-1', '--commit', 'a' * 40])
        rec = S.step_fleet_launch(acct, args)
        self.assertEqual(rec['checked']['used_vcpus'], 64)
        self.assertEqual(rec['checked']['headroom_vcpus'], 192)   # 256 - 64
        self.assertEqual(rec['status'], 'planned')
        self.assertEqual(len(rec['actions']), 2)

    def test_quota_refuses_when_running_usage_leaves_too_little(self):
        running = [{'CpuOptions': {'CoreCount': 32, 'ThreadsPerCore': 2}}]  # 64 vCPUs in use
        acct = FakeAccount(self.canned(quota=256.0, running=running))
        args = args_for(['--run', 'e2e-a', '--count', '4', '--days', ','.join('2023101%d' % i for i in range(8)),
                         '--image-id', 'ami-1', '--commit', 'a' * 40])
        rec = S.step_fleet_launch(acct, args)   # 4 x 64 = 256 > headroom 192
        self.assertEqual(rec['status'], 'refused')
        self.assertEqual(len(rec['actions']), 0)

    def test_plan_within_quota(self):
        acct = FakeAccount(self.canned(quota=640.0))
        days = ['20231018', '20231019', '20231020', '20231021']
        args = args_for(['--count', '2', '--days', ','.join(days), '--image-id', 'ami-1', '--commit', 'b' * 40,
                         '--run', 'e2e-a'])
        rec = S.step_fleet_launch(acct, args)
        self.assertEqual(rec['status'], 'planned')
        self.assertEqual(len(rec['actions']), 2)                  # one RunInstances per box
        plan = rec['checked']['plan']
        self.assertEqual(plan[0]['days'], ['20231018', '20231019'])
        self.assertEqual(plan[1]['days'], ['20231020', '20231021'])
        # per-box Day tag stamped
        first = rec['actions'][0]['params']['TagSpecifications'][0]['Tags']
        self.assertIn({'Key': 'Day', 'Value': '20231018,20231019'}, first)

    def test_spot_refused_for_day_boxes_by_default(self):
        acct = FakeAccount(self.canned())
        args = args_for(['--run', 'e2e-a', '--count', '2', '--days', '20231018,20231019,20231020,20231021',
                         '--image-id', 'ami-1', '--commit', 'c' * 40, '--spot'])   # no --allow-spot-days
        rec = S.step_fleet_launch(acct, args)
        self.assertEqual(rec['status'], 'refused')
        self.assertIn('Spot', rec['reason'])
        self.assertEqual(len(rec['actions']), 0)

    def test_spot_with_allow_uses_spot_quota_and_tags(self):
        canned = {'get_service_quota': lambda p: {'Quota': {'Value': 256.0 if p['QuotaCode'] == S.QUOTA_SPOT else 9.0}},
                  'describe_instances': {'Reservations': []}}
        acct = FakeAccount(canned)
        args = args_for(['--run', 'e2e-a', '--count', '2', '--days', '20231018,20231019,20231020,20231021',
                         '--image-id', 'ami-1', '--commit', 'c' * 40, '--spot', '--allow-spot-days'])
        rec = S.step_fleet_launch(acct, args)
        self.assertEqual(rec['checked']['quota_code'], S.QUOTA_SPOT)   # read the SPOT quota, not On-Demand
        self.assertEqual(rec['status'], 'planned')
        self.assertEqual(rec['actions'][0]['params']['InstanceMarketOptions']['MarketType'], 'spot')
        tags = {t['Key']: t['Value'] for t in rec['actions'][0]['params']['TagSpecifications'][0]['Tags']}
        self.assertEqual(tags['ClassroomEligible'], 'false')           # Spot box: ROOT stage only


class TestDayBoxRole(unittest.TestCase):
    def test_policy_builds_and_validates(self):
        policy = S.day_box_role_policy()
        self.assertEqual(policy['Version'], '2012-10-17')
        self.assertEqual(len(policy['Statement']), 13)
        for stmt in policy['Statement']:
            self.assertEqual(stmt['Effect'], 'Allow')
            res = stmt['Resource'] if isinstance(stmt['Resource'], list) else [stmt['Resource']]
            for arn in res:
                self.assertTrue(arn == '*' or arn.startswith('arn:aws:'), 'bad Resource %r in %s' % (arn, stmt['Sid']))
        tag = next(s for s in policy['Statement'] if s['Sid'] == 'Ec2SelfTag')
        self.assertEqual(tag['Condition']['StringEquals']['aws:ResourceTag/Project'], 'frankie')
        params = next(s for s in policy['Statement'] if s['Sid'] == 'SsmGetParameter')
        self.assertEqual(len(params['Resource']), 4)         # the four SSM parameters

    def test_creates_when_absent(self):
        acct = FakeAccount({})   # every IAM read is NoSuchEntity -> everything absent
        rec = S.step_day_box_role(acct, args_for([]))
        ops = [a['operation'] for a in rec['actions']]
        self.assertEqual(ops, ['create_role', 'attach_role_policy', 'put_role_policy', 'create_instance_profile',
                               'add_role_to_instance_profile'])
        put = next(a for a in rec['actions'] if a['operation'] == 'put_role_policy')
        self.assertEqual(put['params']['PolicyName'], S.IAM_INLINE_POLICY)

    def test_present_when_all_exist(self):
        acct = FakeAccount({
            'get_role': {'Role': {'RoleName': S.IAM_ROLE}},
            'list_attached_role_policies': {'AttachedPolicies': [{'PolicyArn': S.SSM_MANAGED_ARN}]},
            'get_role_policy': {'PolicyDocument': S.day_box_role_policy()},
            'get_instance_profile': {'InstanceProfile': {'Roles': [{'RoleName': S.IAM_ROLE}]}},
        })
        rec = S.step_day_box_role(acct, args_for([]))
        self.assertEqual(rec['status'], 'present')
        self.assertEqual(len(rec['actions']), 0)             # idempotent, never widens
        self.assertTrue(rec['checked']['inline_matches'])


class TestLaunchTemplateStep(unittest.TestCase):
    def test_needs_day_list_location(self):
        from frankie_aws_stack import Account
        acct = Account(apply=False, say=lambda *a: None)
        rec = S.step_launch_template(acct, args_for(['--image-id', 'ami-1']))   # no --run, no --fleet-day-list
        self.assertEqual(rec['status'], 'needs_input')
        self.assertIn('day-list', rec['reason'])
        self.assertEqual(len(rec['actions']), 0)

    def test_refuses_absent_instance_profile(self):
        acct = FakeAccount({})   # get_instance_profile -> NoSuchEntity
        rec = S.step_launch_template(acct, args_for(['--image-id', 'ami-1', '--run', 'e2e-a']))
        self.assertEqual(rec['status'], 'refused')
        self.assertIn('day-box-role', rec['reason'])
        self.assertEqual(len(rec['actions']), 0)


class TestGoldenAmi(unittest.TestCase):
    def test_refuses_a_running_instance(self):
        acct = FakeAccount({'describe_instances': {'Reservations': [{'Instances': [{'State': {'Name': 'running'}}]}]}})
        rec = S.step_golden_ami(acct, args_for(['--commit', 'a' * 40]))
        self.assertEqual(rec['status'], 'refused')
        self.assertIn('running', rec['reason'])

    def test_plans_image_of_a_stopped_instance(self):
        acct = FakeAccount({'describe_instances': {'Reservations': [{'Instances': [{'State': {'Name': 'stopped'}}]}]}})
        rec = S.step_golden_ami(acct, args_for(['--commit', 'deadbeef' * 5]))
        self.assertIn(rec['status'], ('planned',))
        self.assertEqual(rec['actions'][0]['operation'], 'create_image')
        self.assertTrue(rec['actions'][0]['params']['NoReboot'])
        self.assertTrue(rec['actions'][0]['params']['Name'].startswith('frankie-day-box-deadbeefde'))

    def test_needs_commit(self):
        acct = FakeAccount({})
        rec = S.step_golden_ami(acct, args_for([]))
        self.assertEqual(rec['status'], 'needs_input')


if __name__ == '__main__':
    unittest.main()
