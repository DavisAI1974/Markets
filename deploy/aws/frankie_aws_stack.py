#!/usr/bin/env python3
"""Frankie AWS account stack: idempotent steps, dry-run by default, one JSON receipt per step.

SOURCE-BUILT / RUNTIME-UNVERIFIED (2026-10-08). Nothing here has run against the account. Research and the per-step
costs: research/kalshi/frankie_boss/AWS_TOOLS_STACK_20261008.md. How to run: deploy/aws/FRANKIE_AWS_STACK_README.md.

Contract
- `python3 frankie_aws_stack.py [--steps a,b] [options]` plans every selected step and prints the receipts; no call
  that changes the account is made (Describe*/Get*/List* only).
- `--apply --confirm GREG_GO_AWS_STACK` performs the planned actions. Every step checks presence first, so a second
  apply is a no-op ("present"). A step that needs an input it does not have returns "needs_input" and names it.
- Receipt (one dict per step, schema FRANKIE_AWS_STACK_V1): step, status (planned | present | applied | needs_input |
  refused), actions (the exact API calls, with parameters), cost (a sentence with numbers), reason (on refused /
  needs_input), checked (what the presence check saw). Receipts are written to --receipt-dir as <step>.json.
- Steps never touch the fenced box modules; they only call the AWS APIs.

Steps (in run order): ebs-status, s3-gateway-endpoint, s3-lifecycle, cw-agent, cw-alarms, detailed-monitoring,
scheduler-stop, golden-ami, launch-template, fleet-launch, compute-optimizer, snapshot-archive.

The fleet steps (session 8, Greg's plan: up to 15 x 64-vCPU boxes, two days per box, ROOT in parallel, then the
classroom one day at a time across the fleet): golden-ami images a STOPPED staged box; launch-template builds
`frankie-day-box` (r7i.16xlarge, IMDSv2, Ssm, terminate-on-shutdown, the account CMK, user-data that stages a commit
then runs the box's two assigned days); fleet-launch runs N boxes from it, refusing when N x 64 exceeds the live
service-quota (On-Demand L-1216C47A or, with --spot, Spot L-34B43A08). All dry-run by default; --apply --confirm is
NEVER run by the build role.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time

SCHEMA = 'FRANKIE_AWS_STACK_V1'
CONFIRM = 'GREG_GO_AWS_STACK'
ACCOUNT = '568968024170'
REGION_BOX = 'us-east-1'
REGION_DATA = 'us-east-2'
BOX = 'i-035994afa8bdf66a5'
VPC = 'vpc-0be74ac7faf7e965e'
ROUTE_TABLE = 'rtb-095aab35cdfc7ec27'
ARCHIVE_VOLUME = 'vol-004b68c077be09cc9'
BUCKET_DATA = 'bento-568968024170-us-east-2-an'
BUCKET_GRANITE = 'frankie-granite42-568968024170-us-east-1'
AGENT_PARAMETER = 'AmazonCloudWatch-frankie-box'
LAUNCH_TEMPLATE = 'frankie-day-box'
ALARM_PREFIX = 'frankie-box-'
# The fleet (session 8). The CMK is the account key the clones and the box root already use; EBS takes its ARN.
CMK_KEY_ID = '77551067-fa8c-412c-87a5-490d85ae2e79'
CMK_ARN = 'arn:aws:kms:%s:%s:key/%s' % (REGION_BOX, ACCOUNT, CMK_KEY_ID)
QUOTA_ONDEMAND = 'L-1216C47A'           # Running On-Demand Standard (A,C,D,H,I,M,R,T,Z) instances, us-east-1
QUOTA_SPOT = 'L-34B43A08'               # All Standard Spot Instance Requests, us-east-1
REPO = 'DavisAI1974/Markets'
GITHUB_TOKEN_PARAM = '/markets/frankie/github-token'   # SSM SecureString in us-east-2 the box reads (workflow line 43)
FLEET_INSTANCE_TYPE = 'r7i.16xlarge'    # 64 vCPU, 512 GiB (Greg's fleet box)
FLEET_RUN_DEFAULT = 'e2e-20231018-a2'   # the run name the days run under (the first box resumes a2)
STEP_ORDER = ['ebs-status', 's3-gateway-endpoint', 's3-lifecycle', 'cw-agent', 'cw-alarms', 'detailed-monitoring',
              'scheduler-stop', 'golden-ami', 'launch-template', 'fleet-launch', 'compute-optimizer',
              'snapshot-archive']

# CloudWatch agent configuration: disk/mem/diskio with stable alarm dimensions [InstanceId, path] / [InstanceId].
# Source: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-Configuration-File-Details.html
AGENT_CONFIG = {
    'agent': {'metrics_collection_interval': 60, 'run_as_user': 'root'},
    'metrics': {
        'namespace': 'CWAgent',
        'append_dimensions': {'InstanceId': '${aws:InstanceId}'},
        'aggregation_dimensions': [['InstanceId'], ['InstanceId', 'path']],
        'metrics_collected': {
            'disk': {'measurement': ['used_percent', 'free'], 'resources': ['/', '/mnt/archive'],
                     'ignore_file_system_types': ['sysfs', 'devtmpfs', 'tmpfs', 'squashfs', 'overlay']},
            'mem': {'measurement': ['used_percent', 'available']},
            'diskio': {'measurement': ['read_bytes', 'write_bytes', 'io_time'], 'resources': ['*']},
            'cpu': {'measurement': ['usage_idle', 'usage_iowait'], 'totalcpu': True},
        },
    },
}

# Optional scratch preamble: stripe any extra gp3/NVMe into /mnt/scratch (only when --scratch-volumes > 0; r7i has no
# NVMe, so the fleet box normally has none). Source: https://docs.aws.amazon.com/ebs/latest/userguide/raid-config.html
SCRATCH_SNIPPET = r'''ROOT_DEV=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)")
mapfile -t DEVS < <(lsblk -dno NAME,TYPE | awk '$2=="disk"{print "/dev/"$1}' | grep -v "/dev/${ROOT_DEV}")
if [ "${#DEVS[@]}" -gt 0 ]; then
  mkdir -p /mnt/scratch
  if [ "${#DEVS[@]}" -eq 1 ]; then
    mkfs.ext4 -F -E lazy_itable_init=0,lazy_journal_init=0 "${DEVS[0]}"
    mount -o noatime,lazytime "${DEVS[0]}" /mnt/scratch
  else
    mdadm --create /dev/md0 --level=0 --chunk=256 --raid-devices="${#DEVS[@]}" "${DEVS[@]}"
    mkfs.ext4 -F -E lazy_itable_init=0,lazy_journal_init=0 /dev/md0
    mount -o noatime,lazytime /dev/md0 /mnt/scratch
  fi
  for d in "${DEVS[@]}"; do echo 4096 > "/sys/block/$(basename "$d")/queue/read_ahead_kb" || true; done
  chmod 1777 /mnt/scratch
fi
'''

# The fleet box's user-data (session 8). INSTALLS NOTHING NEW (git, awscli and the venv are baked into the golden AMI):
# it reads its two assigned days + the commit from its own instance tags (IMDSv2, InstanceMetadataTags=enabled),
# obtains the code at that commit under the required /opt/frankie-box/code/<commit> checkout (the box's own stage path),
# turns fleet mode ON (FRANKIE_FLEET_DAY_LIST, so the classroom is serialised across the fleet by the S3 lease), claims
# each day (the per-day conditional write), then starts each day on the root line with DAY_CPUS explicit. The handoff
# chain carries each day to its successor; the classroom gate waits in line for the global lease. Every value is
# explicit: the commit, the two days, DAY_CPUS, the run, the fleet location and region all come from tags/placeholders
# the launch-template or fleet-launch fills. RUNTIME-UNVERIFIED (nothing has booted from this).
FLEET_USER_DATA_TMPL = r'''#!/bin/bash
set -euo pipefail
exec >>/var/log/frankie-fleet-userdata.log 2>&1
echo "frankie fleet user-data start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
__SCRATCH__
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
md() {{ curl -s -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/$1"; }}
IID=$(md meta-data/instance-id)
REGION=$(md meta-data/placement/region)
COMMIT=$(md "meta-data/tags/instance/Commit")
DAYS=$(md "meta-data/tags/instance/Day")           # the two assigned days, comma-separated
RUN=$(md "meta-data/tags/instance/Run")
case "$COMMIT" in *[!0-9a-f]*) echo "frankie: bad Commit tag"; exit 2;; esac
[ "${{#COMMIT}}" -eq 40 ] || {{ echo "frankie: Commit tag must be a full 40-hex commit"; exit 2; }}
export FRANKIE_FLEET_INSTANCE="$IID"
export FRANKIE_FLEET_DAY_LIST="{day_list}"         # same for every box -> fleet mode ON (the classroom is serialised)
export FRANKIE_FLEET_REGION="{fleet_region}"
export MARKETS_SHA="$COMMIT"
CODE_ROOT="/opt/frankie-box/code/$COMMIT"           # the box's required staged-checkout location
BOX_DIR="/opt/frankie-box/box/$COMMIT"
# the stage for this commit: the reviewed code at the pinned commit under CODE_ROOT (the self-driving fleet box stages
# from git rather than the SSM reviewed-helper dispatch; see FLEET_SOURCE_STATUS for the open choice)
if [ ! -d "$CODE_ROOT/.git" ]; then
  GH=$(aws ssm get-parameter --with-decryption --name "{github_token_param}" --region "{token_region}" \
        --query Parameter.Value --output text)
  git clone "https://x-access-token:$GH@github.com/{repo}" "$CODE_ROOT"
  unset GH
fi
git -C "$CODE_ROOT" fetch --depth 1 origin "$COMMIT"
git -C "$CODE_ROOT" checkout -q "$COMMIT"
export CODE_ROOT
mkdir -p "$BOX_DIR"
# run each assigned day on the root line, DAY_CPUS explicit; the handoff chain carries it on, the classroom lease
# serialises the classroom across the fleet; the second day waits for CPUs/the first day's classroom (Greg's plan)
IFS=',' read -ra DAY_ARR <<< "$DAYS"
for D in "${{DAY_ARR[@]}}"; do
  case "$D" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "frankie: bad Day '$D'"; continue;; esac
  python3 -I -S -B "$CODE_ROOT/deploy/aws/box/frankie_box_fleet.py" claim-day \
    --run "$RUN" --day "$D" --stage root --commit "$COMMIT" || echo "frankie: day $D already claimed; skipping"
  CODE_ROOT="$CODE_ROOT" MARKETS_SHA="$COMMIT" RUN="$RUN" DAYS="$D" DAY_CPUS={day_cpus} DETACH=on \
    bash "$CODE_ROOT/deploy/aws/box/frankie_box_experiment.sh" ACTION=start || echo "frankie: day $D start returned $?"
done
echo "frankie fleet user-data done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
'''


def fleet_user_data(args):
    """Fill the fleet user-data template from the stack args (every value explicit)."""
    bucket, prefix = _fleet_day_list_location(args)
    day_list = '%s/%s' % (bucket, prefix) if bucket != BUCKET_GRANITE else prefix
    scratch = SCRATCH_SNIPPET if args.scratch_volumes > 0 else 'true  # no scratch volumes on this box\n'
    return FLEET_USER_DATA_TMPL.replace('__SCRATCH__', scratch).format(
        day_list=day_list, fleet_region=args.fleet_region, github_token_param=args.github_token_param,
        token_region=REGION_DATA, repo=REPO, day_cpus=args.day_cpus)


def _fleet_day_list_location(args):
    """(bucket, prefix) of the fleet day list from --fleet-day-list (default: a run-named prefix under the granite
    bucket). Mirrors frankie_box_fleet.location so the box and the launcher agree."""
    raw = (args.fleet_day_list or '').strip().removeprefix('s3://').strip('/')
    import re
    if '/' in raw and re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', raw.split('/', 1)[0]) and \
            ('-' in raw.split('/', 1)[0] or '.' in raw.split('/', 1)[0]):
        return raw.split('/', 1)
    return BUCKET_GRANITE, raw or ('fleet/%s' % args.run)


def receipt(step, **fields):
    base = dict(schema=SCHEMA, step=step, at=round(time.time(), 3), status='planned', actions=[], checked={},
                cost=None, reason=None)
    base.update(fields)
    return base


def _error_text(error):
    return '%s: %s' % (type(error).__name__, str(error)[:240])


class Account:
    """Thin boto3 wrapper: reads always run; writes run only when apply is confirmed, and are always recorded."""

    def __init__(self, apply, say=print):
        self.apply, self.say = apply, say
        self._clients = {}

    def client(self, service, region):
        key = (service, region)
        if key not in self._clients:
            import boto3  # imported here so --help and the toy test work without boto3
            self._clients[key] = boto3.client(service, region_name=region)
        return self._clients[key]

    def read(self, service, region, operation, **params):
        return getattr(self.client(service, region), operation)(**params)

    def write(self, rec, service, region, operation, **params):
        """Record the call on the receipt; perform it only under apply. Returns the response or None."""
        rec['actions'].append(dict(service=service, region=region, operation=operation, params=params))
        if not self.apply:
            return None
        return getattr(self.client(service, region), operation)(**params)


def _finish(rec, account, applied_status='applied'):
    if rec['status'] == 'planned' and account.apply and rec['actions']:
        rec['status'] = applied_status
    return rec


# ----------------------------------------------------------------------------------------------- steps

def step_ebs_status(account, args):
    """Read-only: volumes on the box and their modification state (the 4-per-24h / 6 h rule)."""
    rec = receipt('ebs-status', cost='$0 (read-only).')
    try:
        vols = account.read('ec2', REGION_BOX, 'describe_volumes',
                            Filters=[{'Name': 'attachment.instance-id', 'Values': [args.instance_id]}])['Volumes']
        ids = [v['VolumeId'] for v in vols]
        mods = account.read('ec2', REGION_BOX, 'describe_volumes_modifications', VolumeIds=ids).get(
            'VolumesModifications', []) if ids else []
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    rec['checked'] = {
        'volumes': [dict(id=v['VolumeId'], type=v['VolumeType'], gib=v['Size'], iops=v.get('Iops'),
                         throughput=v.get('Throughput'), encrypted=v['Encrypted'],
                         delete_on_termination=[a.get('DeleteOnTermination') for a in v.get('Attachments', [])])
                    for v in vols],
        'modifications': [dict(id=m['VolumeId'], state=m.get('ModificationState'), progress=m.get('Progress'),
                               start=str(m.get('StartTime')), end=str(m.get('EndTime')))
                          for m in mods],
        'rule': 'up to 4 modifications per rolling 24 h per volume; wait for ModificationState completed; '
                '~6 h per fully used TiB.',
    }
    rec['status'] = 'present'
    return rec


def step_s3_gateway_endpoint(account, args):
    """A free S3 gateway endpoint in the box's VPC (same-Region only; the bento bucket is cross-Region)."""
    service = 'com.amazonaws.%s.s3' % REGION_BOX
    rec = receipt('s3-gateway-endpoint', cost='$0 (gateway endpoints are free; same-Region traffic only).')
    try:
        found = account.read('ec2', REGION_BOX, 'describe_vpc_endpoints', Filters=[
            {'Name': 'vpc-id', 'Values': [args.vpc_id]}, {'Name': 'service-name', 'Values': [service]},
            {'Name': 'vpc-endpoint-type', 'Values': ['Gateway']}])['VpcEndpoints']
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    rec['checked'] = {'existing': [dict(id=e['VpcEndpointId'], state=e['State'], route_tables=e.get('RouteTableIds'))
                                   for e in found]}
    if found:
        rec['status'] = 'present'
        return rec
    account.write(rec, 'ec2', REGION_BOX, 'create_vpc_endpoint', VpcEndpointType='Gateway', VpcId=args.vpc_id,
                  ServiceName=service, RouteTableIds=[args.route_table_id],
                  TagSpecifications=[{'ResourceType': 'vpc-endpoint',
                                      'Tags': [{'Key': 'Project', 'Value': 'Frankie'}]}])
    return _finish(rec, account)


def lifecycle_rules(prefix, storage_class, after_days, abort_days):
    """The two rules: abort dead multipart uploads bucket-wide; transition big archive objects by prefix."""
    rules = [{
        'ID': 'frankie-abort-incomplete-mpu',
        'Status': 'Enabled',
        'Filter': {'Prefix': ''},
        'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': abort_days},
    }]
    if prefix and storage_class:
        rules.append({
            'ID': 'frankie-archive-%s-%dd' % (storage_class.lower().replace('_', '-'), after_days),
            'Status': 'Enabled',
            'Filter': {'And': {'Prefix': prefix, 'ObjectSizeGreaterThan': 131072}},
            'Transitions': [{'Days': after_days, 'StorageClass': storage_class}],
        })
    return rules


def step_s3_lifecycle(account, args):
    """Abort-incomplete-MPU (7 d) + a prefix transition to the archive class; existing rules are kept, by ID."""
    bucket = args.bucket
    region = REGION_DATA if bucket == BUCKET_DATA else REGION_BOX
    rec = receipt('s3-lifecycle', cost='$0 to set; Glacier transition requests $0.05 per 1,000 objects; Glacier '
                                       'Flexible $0.0036/GB-mo, Deep Archive $0.00099/GB-mo, GIR $0.004/GB-mo (Ohio).')
    try:
        current = account.read('s3', region, 'get_bucket_lifecycle_configuration', Bucket=bucket).get('Rules', [])
    except Exception as error:  # noqa: BLE001
        if 'NoSuchLifecycleConfiguration' in str(error):
            current = []
        else:
            rec.update(status='refused', reason=_error_text(error))
            return rec
    wanted = lifecycle_rules(args.archive_prefix, args.archive_class, args.archive_after_days, args.abort_mpu_days)
    have = {r.get('ID') for r in current}
    missing = [r for r in wanted if r['ID'] not in have]
    rec['checked'] = {'bucket': bucket, 'region': region, 'existing_rule_ids': sorted(i for i in have if i),
                      'missing_rule_ids': [r['ID'] for r in missing]}
    if not missing:
        rec['status'] = 'present'
        return rec
    account.write(rec, 's3', region, 'put_bucket_lifecycle_configuration', Bucket=bucket,
                  LifecycleConfiguration={'Rules': current + missing})
    return _finish(rec, account)


def step_cw_agent(account, args):
    """CloudWatch agent config in Parameter Store + a State Manager association that installs/configures it."""
    rec = receipt('cw-agent', cost='State Manager and the parameter are free; 8 custom metrics at 1-min: first 10 '
                                   'metrics free, PutMetricData ~$0.35/mo.')
    try:
        try:
            param = account.read('ssm', REGION_BOX, 'get_parameter', Name=args.agent_parameter)['Parameter']['Value']
        except Exception as error:  # noqa: BLE001
            if 'ParameterNotFound' not in str(error):
                raise
            param = None
        assocs = account.read('ssm', REGION_BOX, 'list_associations', AssociationFilterList=[
            {'key': 'Name', 'value': 'AmazonCloudWatch-ManageAgent'}]).get('Associations', [])
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    wanted = json.dumps(AGENT_CONFIG, sort_keys=True)
    ours = [a for a in assocs if any(t.get('Key') == 'InstanceIds' and args.instance_id in t.get('Values', [])
                                     for t in a.get('Targets', []))]
    rec['checked'] = {'parameter_present': param is not None, 'parameter_matches': param == wanted,
                      'associations_for_box': [a.get('AssociationId') for a in ours]}
    if param != wanted:
        account.write(rec, 'ssm', REGION_BOX, 'put_parameter', Name=args.agent_parameter, Type='String',
                      Value=wanted, Overwrite=True, Description='Frankie box CloudWatch agent config')
    if not ours:
        account.write(rec, 'ssm', REGION_BOX, 'create_association', Name='AmazonCloudWatch-ManageAgent',
                      AssociationName='frankie-box-cloudwatch-agent',
                      Targets=[{'Key': 'InstanceIds', 'Values': [args.instance_id]}],
                      Parameters={'action': ['configure'], 'mode': ['ec2'], 'optionalConfigurationSource': ['ssm'],
                                  'optionalConfigurationLocation': [args.agent_parameter],
                                  'optionalRestart': ['yes']},
                      ScheduleExpression='rate(1 day)')
    if not rec['actions']:
        rec['status'] = 'present'
    return _finish(rec, account)


def alarm_definitions(args):
    """Alarms for the box. Plain metric alarms only: EC2 actions are not allowed on metric-math or composite alarms.
    Source: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/UsingAlarmActions.html"""
    box = args.instance_id
    notify = [args.sns_topic_arn] if args.sns_topic_arn else []
    disk = lambda name, path: dict(  # noqa: E731
        AlarmName=ALARM_PREFIX + name, Namespace='CWAgent', MetricName='disk_used_percent',
        Dimensions=[{'Name': 'InstanceId', 'Value': box}, {'Name': 'path', 'Value': path}],
        Statistic='Maximum', Period=300, EvaluationPeriods=2, DatapointsToAlarm=2, Threshold=85.0,
        ComparisonOperator='GreaterThanOrEqualToThreshold', TreatMissingData='breaching',
        AlarmActions=notify, AlarmDescription='Frankie box %s at or above 85%% used' % path)
    alarms = [
        disk('root-disk-85', '/'),
        disk('archive-disk-85', '/mnt/archive'),
        dict(AlarmName=ALARM_PREFIX + 'mem-95', Namespace='CWAgent', MetricName='mem_used_percent',
             Dimensions=[{'Name': 'InstanceId', 'Value': box}], Statistic='Maximum', Period=300,
             EvaluationPeriods=2, DatapointsToAlarm=2, Threshold=95.0,
             ComparisonOperator='GreaterThanOrEqualToThreshold', TreatMissingData='missing',
             AlarmActions=notify, AlarmDescription='Frankie box memory at or above 95% used'),
        dict(AlarmName=ALARM_PREFIX + 'system-recover', Namespace='AWS/EC2', MetricName='StatusCheckFailed_System',
             Dimensions=[{'Name': 'InstanceId', 'Value': box}], Statistic='Maximum', Period=60,
             EvaluationPeriods=2, DatapointsToAlarm=2, Threshold=1.0,
             ComparisonOperator='GreaterThanOrEqualToThreshold', TreatMissingData='missing',
             AlarmActions=['arn:aws:automate:%s:ec2:recover' % REGION_BOX] + notify,
             AlarmDescription='Frankie box underlying host failure: recover (same instance id, volumes kept)'),
    ]
    if args.idle_stop:
        alarms.append(dict(
            AlarmName=ALARM_PREFIX + 'cpu-idle-stop', Namespace='AWS/EC2', MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': box}], Statistic='Average', Period=300,
            EvaluationPeriods=args.idle_minutes // 5, DatapointsToAlarm=args.idle_minutes // 5,
            Threshold=args.idle_cpu_percent, ComparisonOperator='LessThanThreshold', TreatMissingData='notBreaching',
            AlarmActions=['arn:aws:automate:%s:ec2:stop' % REGION_BOX] + notify,
            AlarmDescription='Frankie box idle (CPU < %s%% for %d min): stop. The queue HOLD and KeepRunning=true '
                             'must DisableAlarmActions on this alarm first.' % (args.idle_cpu_percent,
                                                                                args.idle_minutes)))
    return alarms


def step_cw_alarms(account, args):
    """Disk/memory/system-recover alarms, plus the opt-in idle-stop alarm."""
    rec = receipt('cw-alarms', cost='$0.10 per standard alarm-month: 4 alarms $0.40/mo, 5 with --idle-stop $0.50/mo.')
    wanted = alarm_definitions(args)
    try:
        existing = account.read('cloudwatch', REGION_BOX, 'describe_alarms', AlarmNamePrefix=ALARM_PREFIX).get(
            'MetricAlarms', [])
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    have = {a['AlarmName']: a for a in existing}
    rec['checked'] = {'existing': sorted(have), 'wanted': [a['AlarmName'] for a in wanted]}
    for alarm in wanted:
        current = have.get(alarm['AlarmName'])
        same = current is not None and all(current.get(k) == v for k, v in alarm.items()
                                           if k not in ('AlarmDescription',))
        if same:
            continue
        account.write(rec, 'cloudwatch', REGION_BOX, 'put_metric_alarm', **alarm)
    if not rec['actions']:
        rec['status'] = 'present'
    return _finish(rec, account)


def step_detailed_monitoring(account, args):
    """1-minute EC2 metrics (needed for a 1-h idle alarm with 12 points)."""
    rec = receipt('detailed-monitoring', cost='$2.10 per instance-month (7 metrics at $0.30).')
    try:
        inst = account.read('ec2', REGION_BOX, 'describe_instances', InstanceIds=[args.instance_id])
        state = inst['Reservations'][0]['Instances'][0]['Monitoring']['State']
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    rec['checked'] = {'monitoring': state}
    if state == 'enabled':
        rec['status'] = 'present'
        return rec
    account.write(rec, 'ec2', REGION_BOX, 'monitor_instances', InstanceIds=[args.instance_id])
    return _finish(rec, account)


def step_scheduler_stop(account, args):
    """An EventBridge Scheduler schedule that stops the box at a fixed cron (opt-in; honors nothing by itself)."""
    rec = receipt('scheduler-stop', cost='$0 (14M Scheduler invocations/month free).')
    if not args.stop_cron:
        rec.update(status='needs_input', reason='--stop-cron not given (e.g. "cron(0 6 * * ? *)"); no schedule planned')
        return rec
    if not args.scheduler_role_arn:
        rec.update(status='needs_input', reason='--scheduler-role-arn not given: a role trusting scheduler.amazonaws.com '
                                                'with ec2:StopInstances on the box is required')
        return rec
    name = 'frankie-box-stop'
    try:
        account.read('scheduler', REGION_BOX, 'get_schedule', Name=name)
        present = True
    except Exception as error:  # noqa: BLE001
        if 'ResourceNotFound' not in str(error):
            rec.update(status='refused', reason=_error_text(error))
            return rec
        present = False
    rec['checked'] = {'schedule_present': present, 'conflict': 'KeepRunning=true and the queue HOLD are not read by '
                                                                'the scheduler; disable it during long runs.'}
    if present:
        rec['status'] = 'present'
        return rec
    account.write(rec, 'scheduler', REGION_BOX, 'create_schedule', Name=name, ScheduleExpression=args.stop_cron,
                  FlexibleTimeWindow={'Mode': 'OFF'},
                  Target={'Arn': 'arn:aws:scheduler:::aws-sdk:ec2:stopInstances', 'RoleArn': args.scheduler_role_arn,
                          'Input': json.dumps({'InstanceIds': [args.instance_id]})},
                  Description='Frankie box fixed stop time')
    return _finish(rec, account)


def launch_template_data(args):
    """The fleet day-box template `frankie-day-box` (r7i.16xlarge, two days per box, resumable; session 8). IMDSv2
    required, instance tags readable from metadata (the user-data reads Day/Commit/Run), detailed monitoring on,
    terminate-on-shutdown, the account CMK on every encrypted volume, Project=frankie + Role/Name/Day tags on the
    instance AND its volumes. Source: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-templates.html"""
    root_ebs = {'VolumeType': 'gp3', 'VolumeSize': args.root_gib, 'Iops': args.root_iops,
                'Throughput': args.root_throughput, 'DeleteOnTermination': True, 'Encrypted': True,
                'KmsKeyId': args.kms_key_id}
    block_devices = [{'DeviceName': '/dev/sda1', 'Ebs': root_ebs}]
    for i in range(args.scratch_volumes):
        block_devices.append({'DeviceName': '/dev/sd%s' % chr(ord('f') + i),
                              'Ebs': {'VolumeType': 'gp3', 'VolumeSize': args.scratch_gib, 'Iops': args.scratch_iops,
                                      'Throughput': args.scratch_throughput, 'DeleteOnTermination': True,
                                      'Encrypted': True, 'KmsKeyId': args.kms_key_id}})
    # Day/Commit/Run are stamped per box by fleet-launch; the template carries empty placeholders so the keys exist
    tags = [{'Key': 'Project', 'Value': 'frankie'}, {'Key': 'Role', 'Value': 'day-box'},
            {'Key': 'Name', 'Value': args.launch_template}, {'Key': 'KeepRunning', 'Value': 'false'},
            {'Key': 'Day', 'Value': ''}, {'Key': 'Commit', 'Value': ''}, {'Key': 'Run', 'Value': args.run}]
    return {
        'ImageId': args.image_id,
        'InstanceType': args.instance_type,
        'IamInstanceProfile': {'Name': args.instance_profile},
        'MetadataOptions': {'HttpTokens': 'required', 'HttpPutResponseHopLimit': 2, 'HttpEndpoint': 'enabled',
                            'InstanceMetadataTags': 'enabled'},
        'Monitoring': {'Enabled': True},
        'InstanceInitiatedShutdownBehavior': 'terminate',
        'EbsOptimized': True,
        'BlockDeviceMappings': block_devices,
        'UserData': base64.b64encode(fleet_user_data(args).encode()).decode(),
        'TagSpecifications': [{'ResourceType': 'instance', 'Tags': tags}, {'ResourceType': 'volume', 'Tags': tags}],
    }


def step_launch_template(account, args):
    """Create the `frankie-day-box` launch template (a new version when it exists and the data differs)."""
    rec = receipt('launch-template', cost='$0 for the template; instances launched from it cost the type price '
                                          '(r7i.16xlarge $4.233600/h on-demand, ~$1.27-1.70/h Spot).')
    if not args.image_id:
        rec.update(status='needs_input', reason='--image-id not given (the golden AMI from the golden-ami step; the '
                                                'box AMI ami-025d99823a4caad37 is a 2 TB root, not the lean fleet image)')
        return rec
    data = launch_template_data(args)
    try:
        found = account.read('ec2', REGION_BOX, 'describe_launch_templates', Filters=[
            {'Name': 'launch-template-name', 'Values': [args.launch_template]}])['LaunchTemplates']
    except Exception as error:  # noqa: BLE001
        if 'NotFoundException' in str(error):
            found = []
        else:
            rec.update(status='refused', reason=_error_text(error))
            return rec
    rec['checked'] = {'present': bool(found), 'latest_version': found[0].get('LatestVersionNumber') if found else None,
                      'data_summary': dict(image=data['ImageId'], type=data['InstanceType'],
                                           volumes=len(data['BlockDeviceMappings']))}
    if found:
        latest = account.read('ec2', REGION_BOX, 'describe_launch_template_versions',
                              LaunchTemplateName=args.launch_template, Versions=['$Latest'])['LaunchTemplateVersions'][0]
        if latest.get('LaunchTemplateData') == data:
            rec['status'] = 'present'
            return rec
        account.write(rec, 'ec2', REGION_BOX, 'create_launch_template_version',
                      LaunchTemplateName=args.launch_template, LaunchTemplateData=data,
                      VersionDescription='frankie_aws_stack %s' % time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    else:
        account.write(rec, 'ec2', REGION_BOX, 'create_launch_template', LaunchTemplateName=args.launch_template,
                      LaunchTemplateData=data, VersionDescription='frankie_aws_stack initial',
                      TagSpecifications=[{'ResourceType': 'launch-template',
                                          'Tags': [{'Key': 'Project', 'Value': 'Frankie'}]}])
    return _finish(rec, account)


def step_golden_ami(account, args):
    """Image a STOPPED staged box into a lean golden AMI the launch template boots from. NoReboot (the box is stopped);
    the AMI name carries the staged commit. Source: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-an-ami-ebs.html"""
    rec = receipt('golden-ami', cost='$0 to create; the AMI snapshots cost $0.05/GB-mo on changed blocks (a lean ~100 '
                                     'GB root ~ $5/mo).')
    if not args.commit:
        rec.update(status='needs_input', reason='--commit not given (the staged commit the AMI name carries)')
        return rec
    try:
        inst = account.read('ec2', REGION_BOX, 'describe_instances', InstanceIds=[args.source_instance_id])
        state = inst['Reservations'][0]['Instances'][0]['State']['Name']
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    name = 'frankie-day-box-%s-%s' % (args.commit[:12], time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    rec['checked'] = {'source_instance': args.source_instance_id, 'state': state, 'ami_name': name}
    if state != 'stopped':
        rec.update(status='refused', reason='the source instance is %s; image a STOPPED instance for a consistent root '
                                            '(stop it first, or use NoReboot knowingly)' % state)
        return rec
    account.write(rec, 'ec2', REGION_BOX, 'create_image', InstanceId=args.source_instance_id, Name=name, NoReboot=True,
                  Description='Frankie fleet day-box golden image, staged commit %s' % args.commit,
                  TagSpecifications=[{'ResourceType': rt, 'Tags': [{'Key': 'Project', 'Value': 'frankie'},
                                                                   {'Key': 'Role', 'Value': 'day-box-ami'},
                                                                   {'Key': 'Commit', 'Value': args.commit}]}
                                     for rt in ('image', 'snapshot')])
    return _finish(rec, account)


def _vcpus_of(instance):
    """vCPUs of a running instance from its CpuOptions (CoreCount x ThreadsPerCore)."""
    cpu = instance.get('CpuOptions') or {}
    if cpu.get('CoreCount') and cpu.get('ThreadsPerCore'):
        return int(cpu['CoreCount']) * int(cpu['ThreadsPerCore'])
    return 0


def _day_pairs(days, count):
    """Split the day list into `count` boxes of up to two days each; returns [[d1,d2], [d3,d4], ...] (the last box may
    carry one). Refuses when there are more boxes than day-pairs would fill or days do not cover the boxes."""
    pairs = [days[i:i + 2] for i in range(0, len(days), 2)]
    return pairs[:count]


def step_fleet_launch(account, args):
    """Launch N day-boxes from the template, two days each from the day list, refusing when N x 64 vCPUs exceeds the
    LIVE service-quota (On-Demand L-1216C47A, or Spot L-34B43A08 with --spot). Spot is lawful for ROOT only (resumable
    from the save marker; the classroom must stay On-Demand), so --spot boxes are tagged ROOT-stage. Dry run prints the
    exact per-box plan. Source: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/launch-instance-from-launch-template.html"""
    rec = receipt('fleet-launch', cost='r7i.16xlarge $4.233600/h on-demand (~$1.27-1.70/h Spot) per box; template, '
                                       'tags and the quota read are $0.')
    if args.count <= 0:
        rec.update(status='needs_input', reason='--count N (the number of boxes) required')
        return rec
    days = [d for d in (args.days or '').split(',') if d]
    if not days:
        rec.update(status='needs_input', reason='--days d1,d2,... (the day list, two per box) required')
        return rec
    if any(len(d) != 8 or not d.isdigit() for d in days):
        rec.update(status='refused', reason='every --days value must be an 8-digit YYYYMMDD')
        return rec
    if len(days) < args.count:
        rec.update(status='refused', reason='%d days cannot fill %d boxes (need up to two per box, at least one each)'
                                            % (len(days), args.count))
        return rec
    quota_code = QUOTA_SPOT if args.spot else QUOTA_ONDEMAND
    market = 'Spot' if args.spot else 'On-Demand'
    try:
        quota = account.read('service-quotas', REGION_BOX, 'get_service_quota', ServiceCode='ec2',
                             QuotaCode=quota_code)['Quota']['Value']
        running = account.read('ec2', REGION_BOX, 'describe_instances',
                               Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])['Reservations']
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    used = 0
    for res in running:
        for inst in res.get('Instances', []):
            is_spot = inst.get('InstanceLifecycle') == 'spot'
            if is_spot == bool(args.spot):          # count only the instances that draw on THIS market's quota
                used += _vcpus_of(inst)
    need = args.count * 64
    headroom = int(quota) - used
    rec['checked'] = {'market': market, 'quota_code': quota_code, 'quota_vcpus': int(quota), 'used_vcpus': used,
                      'headroom_vcpus': headroom, 'requested_vcpus': need, 'boxes': args.count}
    if need > headroom:
        rec.update(status='refused', reason='%d boxes need %d vCPUs; the live %s quota (%s) is %d with %d in use, '
                                            'leaving %d. Reduce --count or raise the quota first.'
                                            % (args.count, need, market, quota_code, int(quota), used, headroom))
        return rec
    pairs = _day_pairs(days, args.count)
    if not args.image_id:
        rec.update(status='needs_input', reason='--image-id (the golden AMI) required to launch; the plan above is '
                                                'otherwise sound')
        return rec
    if not args.commit:
        rec.update(status='needs_input', reason='--commit (the staged commit the boxes stage and run) required')
        return rec
    plan = []
    for i, box_days in enumerate(pairs):
        name = 'frankie-day-%s-%s' % (args.commit[:8], '-'.join(box_days))
        tags = [{'Key': 'Project', 'Value': 'frankie'}, {'Key': 'Role', 'Value': 'day-box%s' % ('-root-spot' if args.spot else '')},
                {'Key': 'Name', 'Value': name}, {'Key': 'Day', 'Value': ','.join(box_days)},
                {'Key': 'Commit', 'Value': args.commit}, {'Key': 'Run', 'Value': args.run},
                {'Key': 'ClassroomEligible', 'Value': 'false' if args.spot else 'true'}]
        run_params = dict(LaunchTemplate={'LaunchTemplateName': args.launch_template, 'Version': '$Latest'},
                          MinCount=1, MaxCount=1,
                          TagSpecifications=[{'ResourceType': 'instance', 'Tags': tags},
                                             {'ResourceType': 'volume', 'Tags': tags}])
        if args.spot:
            run_params['InstanceMarketOptions'] = {'MarketType': 'spot',
                                                   'SpotOptions': {'SpotInstanceType': 'one-time'}}
        plan.append(dict(box=i + 1, name=name, days=box_days, market=market))
        account.write(rec, 'ec2', REGION_BOX, 'run_instances', **run_params)
    rec['checked']['plan'] = plan
    if args.spot:
        rec['checked']['note'] = ('Spot boxes run ROOT only (resumable); their days\' classrooms must run on an '
                                  'On-Demand box. The S3 classroom lease serialises classrooms fleet-wide; a Spot box '
                                  'reaching the gate still waits in line. Runtime policy, named for Greg.')
    return _finish(rec, account)


def step_compute_optimizer(account, args):
    """Enroll Compute Optimizer and Cost Optimization Hub (both free)."""
    rec = receipt('compute-optimizer', cost='$0 (both services are free; findings after ~30 h of metrics).')
    try:
        co = account.read('compute-optimizer', REGION_BOX, 'get_enrollment_status')
        co_status = co.get('status')
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    try:
        coh = account.read('cost-optimization-hub', REGION_BOX, 'list_enrollment_statuses', IncludeOrganizationInfo=False)
        coh_status = (coh.get('items') or [{}])[0].get('status')
    except Exception as error:  # noqa: BLE001
        coh_status = 'unreadable (%s)' % _error_text(error)
    rec['checked'] = {'compute_optimizer': co_status, 'cost_optimization_hub': coh_status}
    if co_status != 'Active':
        account.write(rec, 'compute-optimizer', REGION_BOX, 'update_enrollment_status', status='Active')
    if coh_status != 'Active':
        account.write(rec, 'cost-optimization-hub', REGION_BOX, 'update_enrollment_status', status='Active')
    if not rec['actions']:
        rec['status'] = 'present'
    return _finish(rec, account)


def step_snapshot_archive(account, args):
    """Snapshot the archive volume; on a later run, once the snapshot is completed, move it to the Archive tier."""
    rec = receipt('snapshot-archive', cost='Snapshot $0.05/GB-mo (changed blocks only); Archive tier $0.0125/GB-mo as '
                                           'a FULL copy, 90-day minimum, 24-72 h restore, $0.03/GB on restore.')
    try:
        snaps = account.read('ec2', REGION_BOX, 'describe_snapshots', OwnerIds=['self'], Filters=[
            {'Name': 'volume-id', 'Values': [args.volume_id]},
            {'Name': 'tag:FrankieArchive', 'Values': ['true']}])['Snapshots']
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    rec['checked'] = {'volume': args.volume_id,
                      'snapshots': [dict(id=s['SnapshotId'], state=s['State'], tier=s.get('StorageTier'),
                                         start=str(s.get('StartTime'))) for s in snaps]}
    pending = [s for s in snaps if s['State'] == 'pending']
    standard_done = [s for s in snaps if s['State'] == 'completed' and s.get('StorageTier', 'standard') == 'standard']
    if pending:
        rec.update(status='present', reason='snapshot %s still pending; rerun when completed' % pending[0]['SnapshotId'])
        return rec
    if standard_done and args.archive_tier:
        newest = sorted(standard_done, key=lambda s: str(s.get('StartTime')))[-1]
        account.write(rec, 'ec2', REGION_BOX, 'modify_snapshot_tier', SnapshotId=newest['SnapshotId'],
                      StorageTier='archive')
        return _finish(rec, account)
    if standard_done and not args.archive_tier:
        rec.update(status='present', reason='a completed standard snapshot exists; pass --archive-tier to move it')
        return rec
    account.write(rec, 'ec2', REGION_BOX, 'create_snapshot', VolumeId=args.volume_id,
                  Description='Frankie archive volume %s' % time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()),
                  TagSpecifications=[{'ResourceType': 'snapshot', 'Tags': [
                      {'Key': 'Project', 'Value': 'Frankie'}, {'Key': 'FrankieArchive', 'Value': 'true'}]}])
    return _finish(rec, account)


STEPS = {
    'ebs-status': step_ebs_status,
    's3-gateway-endpoint': step_s3_gateway_endpoint,
    's3-lifecycle': step_s3_lifecycle,
    'cw-agent': step_cw_agent,
    'cw-alarms': step_cw_alarms,
    'detailed-monitoring': step_detailed_monitoring,
    'scheduler-stop': step_scheduler_stop,
    'golden-ami': step_golden_ami,
    'launch-template': step_launch_template,
    'fleet-launch': step_fleet_launch,
    'compute-optimizer': step_compute_optimizer,
    'snapshot-archive': step_snapshot_archive,
}


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--steps', default=','.join(STEP_ORDER), help='comma-separated step names (default: all, in order)')
    p.add_argument('--apply', action='store_true', help='perform the planned writes (needs --confirm %s)' % CONFIRM)
    p.add_argument('--confirm', default='', help='the confirm token for --apply')
    p.add_argument('--receipt-dir', default='aws_stack_receipts', help='where <step>.json receipts are written')
    p.add_argument('--instance-id', default=BOX)
    p.add_argument('--vpc-id', default=VPC)
    p.add_argument('--route-table-id', default=ROUTE_TABLE)
    # s3-lifecycle
    p.add_argument('--bucket', default=BUCKET_DATA)
    p.add_argument('--archive-prefix', default='frankie/ingest/')
    p.add_argument('--archive-class', default='', choices=['', 'STANDARD_IA', 'ONEZONE_IA', 'GLACIER_IR', 'GLACIER',
                                                           'DEEP_ARCHIVE'],
                   help='empty = abort-MPU rule only (the class is Greg\'s call f)')
    p.add_argument('--archive-after-days', type=int, default=30)
    p.add_argument('--abort-mpu-days', type=int, default=7)
    # cw-agent / cw-alarms
    p.add_argument('--agent-parameter', default=AGENT_PARAMETER)
    p.add_argument('--sns-topic-arn', default='')
    p.add_argument('--idle-stop', action='store_true', help='add the CPU-idle stop alarm (opt-in; see README)')
    p.add_argument('--idle-minutes', type=int, default=60)
    p.add_argument('--idle-cpu-percent', type=float, default=2.0)
    # scheduler-stop
    p.add_argument('--stop-cron', default='')
    p.add_argument('--scheduler-role-arn', default='')
    # launch-template (the fleet day-box) + golden-ami + fleet-launch
    p.add_argument('--launch-template', default=LAUNCH_TEMPLATE)
    p.add_argument('--image-id', default='')
    p.add_argument('--instance-type', default=FLEET_INSTANCE_TYPE)
    p.add_argument('--instance-profile', default='Ssm')
    p.add_argument('--kms-key-id', default=CMK_ARN, help='the account CMK ARN for EBS encryption (the box root/clones use it)')
    p.add_argument('--root-gib', type=int, default=3072, help='fleet root gp3 size (a day\'s ~1.4 TB x2, or clean-after-save)')
    p.add_argument('--root-iops', type=int, default=16000)
    p.add_argument('--root-throughput', type=int, default=1000)
    p.add_argument('--day-cpus', type=int, default=32, choices=[16, 32, 64], help='CPUs a day-run books (verified: 32)')
    p.add_argument('--run', default=FLEET_RUN_DEFAULT, help='the run name the days run under')
    p.add_argument('--commit', default='', help='the staged commit the golden AMI/boxes carry and run')
    p.add_argument('--github-token-param', default=GITHUB_TOKEN_PARAM, help='SSM SecureString (us-east-2) the box clones with')
    p.add_argument('--fleet-day-list', default='', help='the S3 day list location (bucket/prefix); default a run-named '
                                                        'prefix under the granite bucket')
    p.add_argument('--source-instance-id', default=BOX, help='golden-ami: the STOPPED staged box to image')
    p.add_argument('--fleet-region', default=REGION_BOX)
    p.add_argument('--count', type=int, default=0, help='fleet-launch: number of boxes')
    p.add_argument('--days', default='', help='fleet-launch: comma list of YYYYMMDD days (two per box)')
    p.add_argument('--spot', action='store_true', help='fleet-launch: Spot market (ROOT-stage boxes only; classroom On-Demand)')
    p.add_argument('--scratch-volumes', type=int, default=0, help='extra gp3 volumes striped by user-data (0 = none; r7i has no NVMe)')
    p.add_argument('--scratch-gib', type=int, default=2048)
    p.add_argument('--scratch-iops', type=int, default=16000)
    p.add_argument('--scratch-throughput', type=int, default=1000)
    # snapshot-archive
    p.add_argument('--volume-id', default=ARCHIVE_VOLUME)
    p.add_argument('--archive-tier', action='store_true', help='move the completed standard snapshot to the Archive tier')
    return p


def run(args, account=None, say=print):
    names = [s.strip() for s in args.steps.split(',') if s.strip()]
    unknown = [n for n in names if n not in STEPS]
    if unknown:
        raise SystemExit('unknown step(s): %s; known: %s' % (', '.join(unknown), ', '.join(STEP_ORDER)))
    if args.apply and args.confirm != CONFIRM:
        raise SystemExit('--apply needs --confirm %s' % CONFIRM)
    account = account or Account(apply=args.apply, say=say)
    os.makedirs(args.receipt_dir, exist_ok=True)
    receipts = []
    for name in sorted(names, key=STEP_ORDER.index):
        rec = STEPS[name](account, args)
        rec['mode'] = 'apply' if args.apply else 'dry-run'
        receipts.append(rec)
        with open(os.path.join(args.receipt_dir, name + '.json'), 'w') as f:
            json.dump(rec, f, indent=2, default=str)
        say('%-22s %-12s actions=%d %s' % (name, rec['status'], len(rec['actions']), rec.get('reason') or ''))
    return receipts


def main(argv=None):
    args = build_parser().parse_args(argv)
    receipts = run(args)
    print(json.dumps(receipts, indent=2, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
