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
BUCKET_ARCHIVE = 'frankie-archive-568968024170-us-east-1'   # the us-east-1 archive bucket (parent 85ce2827)
IAM_ROLE = 'frankie-day-box'            # the fleet boxes' OWN role (never widen the main box's Ssm role)
IAM_PROFILE = 'frankie-day-box'
IAM_INLINE_POLICY = 'FrankieDayBox-20261008'
# The four SSM parameters the Ssm role names (CONFIRMED against the Ssm role's inline policy by the parent's read-only
# audit, 2026-10-08: exact matches). The self-driving stage needs github-token.
SSM_PARAM_ARNS = [
    'arn:aws:ssm:us-east-2:%s:parameter/markets/frankie/github-token' % ACCOUNT,
    'arn:aws:ssm:us-east-2:%s:parameter/markets/frankie/granite-service' % ACCOUNT,
    'arn:aws:ssm:us-east-2:%s:parameter/markets/frankie/runpod-serverless' % ACCOUNT,
    'arn:aws:ssm:us-east-1:%s:parameter/markets/DATABENTO_API_KEY' % ACCOUNT,
]
FLEET_INSTANCE_TYPE = 'r7i.16xlarge'    # 64 vCPU, 512 GiB (Greg's fleet box)
# --run has NO default (Greg decision 5): a missing run is refused so no fleet reuses the one-box a2 run e2e-20231018-a2.
STEP_ORDER = ['ebs-status', 's3-gateway-endpoint', 's3-lifecycle', 'cw-agent', 'cw-alarms', 'detailed-monitoring',
              'scheduler-stop', 'day-box-role', 'golden-ami', 'launch-template', 'fleet-launch', 'compute-optimizer',
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

# The fleet box's user-data (session 8, rewritten in slice f for review findings B1/B2/B3/B5/B6/S9/S13). INSTALLS
# NOTHING NEW (git, awscli and the venv are on the golden AMI). It PREPARES the box and sets up reboot-resume; it does
# NOT start a day from scratch (B1): a self-driving box has no lawful route to its partitions, so a FRESH day-start is
# driven per instance by frankie_box_run.yml (ACTION=stage then ACTION=start with the FULL dispatch set + the presign),
# with fleet mode on via /opt/frankie-box/fleet.json. Preparation: read its tags (IMDSv2, with retry and -f so a 404
# body is never read as a value, S13); refuse LOUDLY to a boot-failed marker on a bad tag (never a silent idle box);
# wipe box-local run state on the FIRST boot only (B5, guarded so a reboot keeps progress); stage the pinned commit
# WITHOUT persisting the token on disk (S9); verify rev-parse HEAD and write the staging receipt (decision 1); write
# the box-local fleet config so every process sees fleet mode; install a systemd unit that runs the committed day
# driver on EVERY boot (B6: reboot-resume, not once). RUNTIME-UNVERIFIED (nothing has booted from this).
FLEET_USER_DATA_TMPL = r'''#!/bin/bash
set -euo pipefail
exec >>/var/log/frankie-fleet-userdata.log 2>&1
echo "frankie fleet user-data start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
__SCRATCH__
mkdir -p /opt/frankie-box/box
fail() {{ printf '{{"schema":"FRANKIE_FLEET_BOOT_FAILED_V1","reason":"%s","instance":"%s","at_utc":"%s"}}\n' "$1" "${{IID:-}}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /opt/frankie-box/box/fleet-boot-failed.json; echo "frankie: BOOT FAILED: $1"; exit 2; }}
IID=""; COMMIT=""; RUN=""; DAYS=""; REGION="{fleet_region}"
for i in $(seq 1 30); do   # S13: tags lag IMDS by seconds after launch; retry ~60s with -f
  TOKEN=$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 600" || true)
  [ -n "$TOKEN" ] || {{ sleep 2; continue; }}
  H="X-aws-ec2-metadata-token: $TOKEN"
  IID=$(curl -fsS -H "$H" "http://169.254.169.254/latest/meta-data/instance-id" || true)
  COMMIT=$(curl -fsS -H "$H" "http://169.254.169.254/latest/meta-data/tags/instance/Commit" || true)
  RUN=$(curl -fsS -H "$H" "http://169.254.169.254/latest/meta-data/tags/instance/Run" || true)
  DAYS=$(curl -fsS -H "$H" "http://169.254.169.254/latest/meta-data/tags/instance/Day" || true)
  DAYLIST=$(curl -fsS -H "$H" "http://169.254.169.254/latest/meta-data/tags/instance/DayList" || true)  # S8: per box
  R=$(curl -fsS -H "$H" "http://169.254.169.254/latest/meta-data/placement/region" || true)
  [ -n "$R" ] && REGION="$R"
  [ -n "$IID" ] && [ -n "$COMMIT" ] && [ -n "$RUN" ] && break
  sleep 2
done
case "$COMMIT" in *[!0-9a-f]*) fail "Commit tag is not hex";; esac
[ "${{#COMMIT}}" -eq 40 ] || fail "Commit tag must be a full 40-hex commit (got '${{COMMIT}}')"
[ -n "$RUN" ] || fail "Run tag empty"
[ -n "$IID" ] || fail "instance-id unreadable from IMDS"
[ -n "$DAYLIST" ] || DAYLIST="{day_list}"   # S8: prefer the per-box DayList tag; fall back to the template's baked value
CODE_ROOT="/opt/frankie-box/code/$COMMIT"
BOX_DIR="/opt/frankie-box/box/$COMMIT"
mkdir -p "$BOX_DIR"
# B5: FIRST boot only, clear any box-local run state (belt-and-suspenders; golden-ami refuses a dirty source). The
# marker guard means a REBOOT never wipes a day's progress.
if [ ! -f /opt/frankie-box/.fleet-prepared ]; then
  echo "frankie: first boot; clearing box-local run state"
  rm -rf /opt/frankie-box/work/frankie-queue /opt/frankie-box/work/cpu-bookings /opt/frankie-box/cpu-bookings \
         /opt/frankie-box/work/experiment /opt/frankie-box/work/logs 2>/dev/null || true
fi
# S9: stage the pinned commit with an auth header for the fetch only; the token is NEVER written to .git/config
GH=$(aws ssm get-parameter --with-decryption --name "{github_token_param}" --region "{token_region}" --query Parameter.Value --output text)
AUTH="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH" | base64 -w0)"
unset GH
[ -d "$CODE_ROOT/.git" ] || git -c http.extraheader="$AUTH" clone --depth 1 "https://github.com/{repo}" "$CODE_ROOT"
git -C "$CODE_ROOT" -c http.extraheader="$AUTH" fetch --depth 1 origin "$COMMIT"
git -C "$CODE_ROOT" checkout -q "$COMMIT"
git -C "$CODE_ROOT" remote set-url origin "https://github.com/{repo}"   # S9: no token left on disk
GOT=$(git -C "$CODE_ROOT" rev-parse HEAD)
[ "$GOT" = "$COMMIT" ] || fail "rev-parse HEAD ($GOT) != pinned commit ($COMMIT)"
TREE=$(git -C "$CODE_ROOT" rev-parse "HEAD^{{tree}}")
FILES=$(git -C "$CODE_ROOT" ls-files | wc -l | tr -d ' ')
# decision 1: the staging receipt so every fleet box names the identical commit/tree
python3 -I -S -c "import json,sys,time; json.dump({{'schema':'FRANKIE_FLEET_STAGE_V1','status':'staged','commit':sys.argv[1],'tree_sha':sys.argv[2],'file_count':int(sys.argv[3]),'instance':sys.argv[4],'code_root':sys.argv[5],'staged_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}}, open(sys.argv[6],'w'), indent=1, sort_keys=True)" "$COMMIT" "$TREE" "$FILES" "$IID" "$CODE_ROOT" "$BOX_DIR/stage-receipt.json"
# the box-local fleet config: EVERY process on the box (including run.yml-dispatched starts) sees fleet mode from it
python3 -I -S -c "import json,sys; json.dump({{'schema':'FRANKIE_FLEET_CONFIG_V1','day_list':sys.argv[1],'region':sys.argv[2],'instance':sys.argv[3],'run':sys.argv[4],'commit':sys.argv[5],'code_root':sys.argv[6]}}, open('/opt/frankie-box/fleet.json','w'), indent=1, sort_keys=True)" "$DAYLIST" "$REGION" "$IID" "$RUN" "$COMMIT" "$CODE_ROOT"
# B6: run the committed day driver on EVERY boot (reboot-resume), via a systemd unit, not once
cat > /etc/systemd/system/frankie-fleet-day.service <<UNIT
[Unit]
Description=Frankie fleet day driver (reboot-resume)
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/bin/bash $CODE_ROOT/deploy/aws/box/frankie_fleet_day.sh
[Install]
WantedBy=multi-user.target
UNIT
touch /opt/frankie-box/.fleet-prepared
systemctl daemon-reload
systemctl enable --now frankie-fleet-day.service || true
echo "frankie fleet user-data done (prepared; day-start is driven by run.yml; reboot-resume via the unit) $(date -u +%Y-%m-%dT%H:%M:%SZ)"
'''


def fleet_user_data(args):
    """Fill the fleet user-data template from the stack args (every value explicit)."""
    bucket, prefix = _fleet_day_list_location(args)
    day_list = '%s/%s' % (bucket, prefix) if bucket != BUCKET_GRANITE else prefix
    scratch = SCRATCH_SNIPPET if args.scratch_volumes > 0 else 'true  # no scratch volumes on this box\n'
    return FLEET_USER_DATA_TMPL.replace('__SCRATCH__', scratch).format(
        day_list=day_list, fleet_region=args.fleet_region, github_token_param=args.github_token_param,
        token_region=REGION_DATA, repo=REPO)


def _bad_fleet_prefix(args):
    """S11: the module's keys all live under <prefix> on the day-list bucket; the day-box role grants only `fleet/*` on
    the granite bucket. A location outside that escapes the grant -> every control write is AccessDenied -> the gate
    treats it as a silent WAIT. Refuse it at launch unless --allow-any-prefix names a widened role. Returns a refusal
    reason or None."""
    if getattr(args, 'allow_any_prefix', False):
        return None
    bucket, prefix = _fleet_day_list_location(args)
    if bucket != BUCKET_GRANITE or not (prefix + '/').startswith('fleet/'):
        return ('the fleet day-list location %s/%s is outside fleet/ on the granite bucket, which the day-box role '
                'grants (fleet/*). A box there gets AccessDenied -> a silent classroom WAIT. Use fleet/<run>, or pass '
                '--allow-any-prefix after widening the role.' % (bucket, prefix))
    return None


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
    # Day/Commit/Run are stamped per box by fleet-launch; the template carries empty placeholders so the keys exist.
    # KeepRunning=true at launch (B6): the idle guard stops only boxes with KeepRunning != true, so a fleet box is
    # protected while its day runs; the run clears it (keep_running(false)) at the day's end as today, after which the
    # box is idle-stop eligible. The day-box role (slice e) grants the box ec2:CreateTags on Project=frankie so its
    # own keep_running succeeds (the main-box-only grant was the gap the review named).
    tags = [{'Key': 'Project', 'Value': 'frankie'}, {'Key': 'Role', 'Value': 'day-box'},
            {'Key': 'Name', 'Value': args.launch_template}, {'Key': 'KeepRunning', 'Value': 'true'},
            {'Key': 'Day', 'Value': ''}, {'Key': 'Commit', 'Value': ''}, {'Key': 'Run', 'Value': args.run}]
    return {
        'ImageId': args.image_id,
        'InstanceType': args.instance_type,
        'IamInstanceProfile': {'Name': args.instance_profile},
        'MetadataOptions': {'HttpTokens': 'required', 'HttpPutResponseHopLimit': 2, 'HttpEndpoint': 'enabled',
                            'InstanceMetadataTags': 'enabled'},
        'Monitoring': {'Enabled': True},
        'InstanceInitiatedShutdownBehavior': args.shutdown_behavior,   # S7: terminate (Greg) or stop (safer; a day's
        #                                                                un-archived data is not lost to a stray shutdown)
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
    if not args.run and not args.fleet_day_list:
        rec.update(status='needs_input', reason='the user-data needs the fleet day-list location: pass --fleet-day-list '
                                                'bucket/prefix, or --run (the location defaults to fleet/<run>; --run '
                                                'has no default, Greg decision 5)')
        return rec
    bad = _bad_fleet_prefix(args)   # S11
    if bad:
        rec.update(status='refused', reason=bad)
        return rec
    # the instance profile must exist (read-only GetInstanceProfile): a template naming an absent profile launches boxes
    # with no role. NoSuchEntity -> refuse (run day-box-role first); a credentials/other error is noted, not fatal (an
    # offline dry run still prints the plan)
    try:
        account.read('iam', REGION_BOX, 'get_instance_profile', InstanceProfileName=args.instance_profile)
        rec['checked'] = dict(rec.get('checked') or {}, instance_profile=args.instance_profile, profile_present=True)
    except Exception as error:  # noqa: BLE001
        if 'NoSuchEntity' in str(error) or 'NoSuchEntity' in type(error).__name__:
            rec.update(status='refused', reason='instance profile %s does not exist: run the day-box-role step first '
                                                '(python3 frankie_aws_stack.py --steps day-box-role)' % args.instance_profile)
            return rec
        rec['checked'] = dict(rec.get('checked') or {}, instance_profile=args.instance_profile,
                              profile_check='unverified (%s)' % _error_text(error))
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


def day_box_role_policy():
    """The ONE inline policy FrankieDayBox-20261008 for the fleet boxes' role, exactly as the IAM-gap audit lists
    (DROP_IN_CLAUDE_20261008_SESSION8.md): the granite day-list/claims/lease + the Ssm role's pod-root/box-runs/
    host-deliveries S3, read of the bento ingest/day_external prefixes, the archive bucket (if boxes upload directly),
    Bedrock in us-east-1 (the Granite voice meeting), self DescribeInstances/CreateTags scoped to Project=frankie, the
    four SSM parameters, SSM command/info reads, and GetCallerIdentity. Never broader than this."""
    g = 'arn:aws:s3:::%s' % BUCKET_GRANITE
    d = 'arn:aws:s3:::%s' % BUCKET_DATA
    a = 'arn:aws:s3:::%s' % BUCKET_ARCHIVE
    return {
        'Version': '2012-10-17',
        'Statement': [
            {'Sid': 'GraniteList', 'Effect': 'Allow', 'Action': 's3:ListBucket', 'Resource': g},
            {'Sid': 'GraniteObjects', 'Effect': 'Allow',
             'Action': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
             'Resource': [g + '/fleet/*', g + '/pod-root/*', g + '/box-runs/*']},
            {'Sid': 'GraniteHostDeliveries', 'Effect': 'Allow',
             'Action': ['s3:GetObject', 's3:PutObject', 's3:AbortMultipartUpload'], 'Resource': g + '/host-deliveries/*'},
            {'Sid': 'BentoList', 'Effect': 'Allow', 'Action': 's3:ListBucket', 'Resource': d,
             'Condition': {'StringLike': {'s3:prefix': ['frankie/ingest/*', 'frankie/day_external/*']}}},
            {'Sid': 'BentoGet', 'Effect': 'Allow', 'Action': 's3:GetObject',
             'Resource': [d + '/frankie/ingest/*', d + '/frankie/day_external/*']},
            {'Sid': 'ArchiveList', 'Effect': 'Allow', 'Action': 's3:ListBucket', 'Resource': a},
            {'Sid': 'ArchiveObjects', 'Effect': 'Allow',
             'Action': ['s3:GetObject', 's3:PutObject', 's3:AbortMultipartUpload'], 'Resource': a + '/*'},
            {'Sid': 'BedrockInvoke', 'Effect': 'Allow',
             'Action': ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
             'Resource': ['arn:aws:bedrock:us-east-1::foundation-model/*',
                          'arn:aws:bedrock:us-east-1:%s:inference-profile/*' % ACCOUNT]},
            {'Sid': 'Ec2Describe', 'Effect': 'Allow', 'Action': 'ec2:DescribeInstances', 'Resource': '*'},
            {'Sid': 'Ec2SelfTag', 'Effect': 'Allow', 'Action': 'ec2:CreateTags',
             'Resource': 'arn:aws:ec2:us-east-1:%s:instance/*' % ACCOUNT,
             'Condition': {'StringEquals': {'aws:ResourceTag/Project': 'frankie'}}},
            {'Sid': 'SsmGetParameter', 'Effect': 'Allow', 'Action': 'ssm:GetParameter', 'Resource': SSM_PARAM_ARNS},
            {'Sid': 'SsmCommandInfo', 'Effect': 'Allow',
             'Action': ['ssm:GetCommandInvocation', 'ssm:DescribeInstanceInformation'], 'Resource': '*'},
            {'Sid': 'StsWhoAmI', 'Effect': 'Allow', 'Action': 'sts:GetCallerIdentity', 'Resource': '*'},
        ],
    }


DAY_BOX_TRUST = {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow',
                 'Principal': {'Service': 'ec2.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]}
SSM_MANAGED_ARN = 'arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore'


def step_day_box_role(account, args):
    """Create the fleet boxes' role frankie-day-box (trust ec2), attach AmazonSSMManagedInstanceCore, put the ONE inline
    policy FrankieDayBox-20261008, create the instance profile frankie-day-box and add the role; tag both
    Project=frankie. Idempotent: if a piece exists it is verified and reported, never widened. The dry run prints the
    full policy JSON. IAM is a NEW role, never a change to the main box's Ssm role."""
    rec = receipt('day-box-role', cost='$0 (IAM role, inline policy and instance profile are free).')
    policy = day_box_role_policy()
    rec['checked'] = {'role': IAM_ROLE, 'instance_profile': IAM_PROFILE, 'inline_policy': IAM_INLINE_POLICY,
                      'statements': len(policy['Statement']), 'policy': policy, 'managed': SSM_MANAGED_ARN}

    def read(op, **kw):
        try:
            return account.read('iam', REGION_BOX, op, **kw)
        except Exception as error:  # noqa: BLE001
            if 'NoSuchEntity' in str(error) or 'NoSuchEntity' in type(error).__name__:
                return None
            raise
    try:
        role = read('get_role', RoleName=IAM_ROLE)
        attached = read('list_attached_role_policies', RoleName=IAM_ROLE) if role else None
        inline = read('get_role_policy', RoleName=IAM_ROLE, PolicyName=IAM_INLINE_POLICY) if role else None
        profile = read('get_instance_profile', InstanceProfileName=IAM_PROFILE)
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    tags = [{'Key': 'Project', 'Value': 'frankie'}]
    if not role:
        account.write(rec, 'iam', REGION_BOX, 'create_role', RoleName=IAM_ROLE,
                      AssumeRolePolicyDocument=json.dumps(DAY_BOX_TRUST), Tags=tags,
                      Description='Frankie fleet day-box: SSM + fleet S3 + Bedrock + self-tag (never the main box role)')
        account.write(rec, 'iam', REGION_BOX, 'attach_role_policy', RoleName=IAM_ROLE, PolicyArn=SSM_MANAGED_ARN)
        account.write(rec, 'iam', REGION_BOX, 'put_role_policy', RoleName=IAM_ROLE, PolicyName=IAM_INLINE_POLICY,
                      PolicyDocument=json.dumps(policy))
    else:
        have_managed = any(p.get('PolicyArn') == SSM_MANAGED_ARN for p in (attached or {}).get('AttachedPolicies', []))
        if not have_managed:
            account.write(rec, 'iam', REGION_BOX, 'attach_role_policy', RoleName=IAM_ROLE, PolicyArn=SSM_MANAGED_ARN)
        if not inline:
            account.write(rec, 'iam', REGION_BOX, 'put_role_policy', RoleName=IAM_ROLE, PolicyName=IAM_INLINE_POLICY,
                          PolicyDocument=json.dumps(policy))
        else:
            # never widen an existing inline policy: verify and report only
            rec['checked']['inline_matches'] = (inline.get('PolicyDocument') == policy)
    if not profile:
        account.write(rec, 'iam', REGION_BOX, 'create_instance_profile', InstanceProfileName=IAM_PROFILE, Tags=tags)
        account.write(rec, 'iam', REGION_BOX, 'add_role_to_instance_profile', InstanceProfileName=IAM_PROFILE,
                      RoleName=IAM_ROLE)
    else:
        roles = [r.get('RoleName') for r in (profile or {}).get('InstanceProfile', {}).get('Roles', [])]
        rec['checked']['profile_has_role'] = IAM_ROLE in roles
        if IAM_ROLE not in roles:
            account.write(rec, 'iam', REGION_BOX, 'add_role_to_instance_profile', InstanceProfileName=IAM_PROFILE,
                          RoleName=IAM_ROLE)
    if not rec['actions']:
        rec['status'] = 'present'
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
        inst = account.read('ec2', REGION_BOX, 'describe_instances', InstanceIds=[args.source_instance_id])['Reservations'][0]['Instances'][0]
        state = inst['State']['Name']
        root_name = inst.get('RootDeviceName')
        root_vol = next((m['Ebs']['VolumeId'] for m in inst.get('BlockDeviceMappings', [])
                         if m.get('DeviceName') == root_name and m.get('Ebs')), None)
        root_gib = None
        if root_vol:
            vols = account.read('ec2', REGION_BOX, 'describe_volumes', VolumeIds=[root_vol])['Volumes']
            root_gib = vols[0]['Size'] if vols else None
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    name = 'frankie-day-box-%s-%s' % (args.commit[:12], time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    rec['checked'] = {'source_instance': args.source_instance_id, 'state': state, 'ami_name': name,
                      'root_volume': root_vol, 'root_gib': root_gib, 'max_root_gib': args.max_root_gib}
    if state != 'stopped':
        rec.update(status='refused', reason='the source instance is %s; image a STOPPED instance for a consistent root '
                                            '(stop it first, or use NoReboot knowingly)' % state)
        return rec
    # B5: refuse a NON-LEAN source (the main box's 2 TB root carries a2's queue, retained bookings and ~1.4 TB of day
    # data; 15 boxes would each boot with a foreign saved day). Image a clean staged box. The root-size check is the
    # review's offered simple proxy for "no box-local run state"; --max-root-gib sets the lean bound.
    if root_gib is not None and root_gib > args.max_root_gib:
        rec.update(status='refused', reason='the source root volume is %d GiB, over the lean bound --max-root-gib %d: '
                                            'image a CLEAN staged box, not the main box (its queue/bookings/day data '
                                            'would ship in the AMI). Raise --max-root-gib only for a knowingly-lean '
                                            'large root.' % (root_gib, args.max_root_gib))
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


def _vcpus_for_type(instance_type):
    """vCPUs for an EC2 instance type from its size suffix (S6: `need` must use --instance-type, not a hard 64).
    r7i.16xlarge = 64. Unknown -> 64 (the fleet default) so the quota check is never silently too small."""
    sizes = {'medium': 1, 'large': 2, 'xlarge': 4, '2xlarge': 8, '4xlarge': 16, '8xlarge': 32, '12xlarge': 48,
             '16xlarge': 64, '24xlarge': 96, '32xlarge': 128, '48xlarge': 192}
    size = (instance_type or '').split('.', 1)[-1]
    return sizes.get(size, 64)


def _day_pairs(days, count):
    """Split the day list into `count` boxes of up to two days each; returns [[d1,d2], [d3,d4], ...] (the last box may
    carry one)."""
    pairs = [days[i:i + 2] for i in range(0, len(days), 2)]
    return pairs[:count]


def step_fleet_launch(account, args):
    """Launch N day-boxes from the template, two days each from the day list, refusing when N x 64 vCPUs exceeds the
    LIVE service-quota (On-Demand L-1216C47A, or Spot L-34B43A08 with --spot). Spot is lawful for ROOT only (resumable
    from the save marker; the classroom must stay On-Demand), so --spot boxes are tagged ROOT-stage. Dry run prints the
    exact per-box plan. Source: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/launch-instance-from-launch-template.html"""
    rec = receipt('fleet-launch', cost='r7i.16xlarge $4.233600/h on-demand (~$1.27-1.70/h Spot) per box; template, '
                                       'tags and the quota read are $0.')
    if not args.run:
        rec.update(status='needs_input', reason='--run (the run name) required and has NO default: a missing run is '
                                                'refused so no fleet reuses the one-box a2 run e2e-20231018-a2 '
                                                '(Greg, decision 5)')
        return rec
    if args.spot and not args.allow_spot_days:
        rec.update(status='refused', reason='--spot for DAY boxes is refused by default (Greg, decision 2): a reclaimed '
                                            'classroom loses a day of the serial chain and the day\'s data sits on the '
                                            'reclaimed box. Spot is for stateless burst work (the digest render), not '
                                            'day boxes. Pass --allow-spot-days to override knowingly (the boxes are '
                                            'tagged ClassroomEligible=false and the gate refuses them the classroom).')
        return rec
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
    bad = _bad_fleet_prefix(args)   # S11
    if bad:
        rec.update(status='refused', reason=bad)
        return rec
    if len(days) < args.count:
        rec.update(status='refused', reason='%d days cannot fill %d boxes (need up to two per box, at least one each)'
                                            % (len(days), args.count))
        return rec
    if len(days) > 2 * args.count:
        # S6: do not SILENTLY drop days -- refuse and name the ones that would not be assigned
        rec.update(status='refused', reason='%d days exceed the %d boxes x 2/day = %d capacity; the %d unassigned days '
                                            'would be dropped silently. Raise --count or shorten --days. Unassigned: %s'
                                            % (len(days), args.count, 2 * args.count, len(days) - 2 * args.count,
                                               ','.join(days[2 * args.count:])))
        return rec
    quota_code = QUOTA_SPOT if args.spot else QUOTA_ONDEMAND
    market = 'Spot' if args.spot else 'On-Demand'
    try:
        quota = account.read('service-quotas', REGION_BOX, 'get_service_quota', ServiceCode='ec2',
                             QuotaCode=quota_code)['Quota']['Value']
        # S6: pending counts against the quota too, not only running
        running = account.read('ec2', REGION_BOX, 'describe_instances',
                               Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'pending']}])['Reservations']
    except Exception as error:  # noqa: BLE001
        rec.update(status='refused', reason=_error_text(error))
        return rec
    used = 0
    for res in running:
        for inst in res.get('Instances', []):
            is_spot = inst.get('InstanceLifecycle') == 'spot'
            if is_spot == bool(args.spot):          # count only the instances that draw on THIS market's quota
                used += _vcpus_of(inst)
    per_box = _vcpus_for_type(args.instance_type)   # S6: need uses the actual instance type
    need = args.count * per_box
    headroom = int(quota) - used
    rec['checked'] = {'market': market, 'quota_code': quota_code, 'quota_vcpus': int(quota), 'used_vcpus': used,
                      'headroom_vcpus': headroom, 'requested_vcpus': need, 'boxes': args.count,
                      'instance_type': args.instance_type, 'vcpus_per_box': per_box}
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
    # S8: pin the template VERSION NUMBER (not the loose $Latest, which a later fleet-launch --run could move under a
    # day list baked for another run) and record it; verify it exists.
    version = '$Latest'
    try:
        v = account.read('ec2', REGION_BOX, 'describe_launch_template_versions',
                         LaunchTemplateName=args.launch_template, Versions=['$Latest'])['LaunchTemplateVersions'][0]
        version = str(v['VersionNumber'])
    except Exception as error:  # noqa: BLE001
        if 'NotFound' in str(error):
            rec.update(status='refused', reason='launch template %s not found; run the launch-template step first'
                                                % args.launch_template)
            return rec
        rec['checked']['version_pin'] = 'unverified (%s); using $Latest' % _error_text(error)
    rec['checked']['template_version'] = version
    day_list_loc = '%s/%s' % _fleet_day_list_location(args) if _fleet_day_list_location(args)[0] != BUCKET_GRANITE \
        else _fleet_day_list_location(args)[1]
    plan, launched, failed = [], [], []
    for i, box_days in enumerate(pairs):
        name = 'frankie-day-%s-%s' % (args.commit[:8], '-'.join(box_days))
        tags = [{'Key': 'Project', 'Value': 'frankie'}, {'Key': 'Role', 'Value': 'day-box%s' % ('-root-spot' if args.spot else '')},
                {'Key': 'Name', 'Value': name}, {'Key': 'Day', 'Value': ','.join(box_days)},
                {'Key': 'Commit', 'Value': args.commit}, {'Key': 'Run', 'Value': args.run},
                {'Key': 'DayList', 'Value': day_list_loc},   # S8: the day-list location per box, so a reused template never mismatches
                {'Key': 'KeepRunning', 'Value': 'true'},   # B6: protected from the idle guard while its day runs
                {'Key': 'ClassroomEligible', 'Value': 'false' if args.spot else 'true'}]
        run_params = dict(LaunchTemplate={'LaunchTemplateName': args.launch_template, 'Version': version},
                          MinCount=1, MaxCount=1,
                          TagSpecifications=[{'ResourceType': 'instance', 'Tags': tags},
                                             {'ResourceType': 'volume', 'Tags': tags}])
        if args.spot:
            run_params['InstanceMarketOptions'] = {'MarketType': 'spot',
                                                   'SpotOptions': {'SpotInstanceType': 'one-time'}}
        entry = dict(box=i + 1, name=name, days=box_days, market=market)
        # S6: per-box try/except so a mid-loop RunInstances error (VcpuLimitExceeded between the quota read and here,
        # InsufficientInstanceCapacity) records the boxes already launched and returns 'partial', never losing them.
        try:
            resp = account.write(rec, 'ec2', REGION_BOX, 'run_instances', **run_params)
            if resp:   # apply mode: record the real InstanceId(s) (S5)
                ids = [inst['InstanceId'] for inst in resp.get('Instances', [])]
                entry['instance_ids'] = ids
                launched.extend((iid, box_days) for iid in ids)
        except Exception as error:  # noqa: BLE001
            entry['error'] = _error_text(error)
            failed.append(entry)
            plan.append(entry)
            rec.update(status='partial', reason='launched %d of %d boxes; box %d (%s) failed: %s. The launched ids are '
                                                'on the receipt.' % (i, len(pairs), i + 1, ','.join(box_days), entry['error']))
            rec['checked'].update(plan=plan, launched=[dict(instance=iid, days=d) for iid, d in launched], failed=failed)
            return rec
        plan.append(entry)
    rec['checked'].update(plan=plan, launched=[dict(instance=iid, days=d) for iid, d in launched])
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
    'day-box-role': step_day_box_role,
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
    p.add_argument('--instance-profile', default=IAM_PROFILE, help='the fleet boxes\' instance profile (default '
                                                                   'frankie-day-box from the day-box-role step)')
    p.add_argument('--kms-key-id', default=CMK_ARN, help='the account CMK ARN for EBS encryption (the box root/clones use it)')
    p.add_argument('--root-gib', type=int, default=3072, help='fleet root gp3 size (a day\'s ~1.4 TB x2, or clean-after-save)')
    p.add_argument('--root-iops', type=int, default=16000)
    p.add_argument('--root-throughput', type=int, default=1000)
    p.add_argument('--day-cpus', type=int, default=32, choices=[16, 32, 64], help='CPUs a day-run books (verified: 32)')
    p.add_argument('--run', default='', help='the run name the days run under (NO default; a missing run is refused so '
                                             'no fleet reuses the one-box a2 run, Greg decision 5)')
    p.add_argument('--allow-spot-days', action='store_true', help='fleet-launch: allow --spot for DAY boxes (refused by '
                                                                  'default; a reclaimed classroom loses a day, so Spot '
                                                                  'is for stateless burst work, not day boxes)')
    p.add_argument('--commit', default='', help='the staged commit the golden AMI/boxes carry and run')
    p.add_argument('--github-token-param', default=GITHUB_TOKEN_PARAM, help='SSM SecureString (us-east-2) the box clones with')
    p.add_argument('--fleet-day-list', default='', help='the S3 day list location (bucket/prefix); default a run-named '
                                                        'prefix under the granite bucket')
    p.add_argument('--allow-any-prefix', action='store_true', help='allow a day-list location outside fleet/ on the '
                                                                   'granite bucket (needs a widened day-box role; S11)')
    p.add_argument('--source-instance-id', default=BOX, help='golden-ami: the STOPPED staged box to image')
    p.add_argument('--max-root-gib', type=int, default=300, help='golden-ami: refuse a source root volume larger than '
                                                                 'this (a non-lean box carries foreign run state/data)')
    p.add_argument('--shutdown-behavior', default='terminate', choices=['terminate', 'stop'],
                   help='launch-template InstanceInitiatedShutdownBehavior (Greg chose terminate; stop is safer against '
                        'a stray shutdown deleting a day, see review S7)')
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
