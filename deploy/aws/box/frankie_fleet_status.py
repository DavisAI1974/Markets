"""Read-only fleet status (session 8): one line per Project=frankie fleet instance -- instance id, state, assigned
days, current stage, booking, receipt present, and the global classroom-lease holder -- from the S3 day list and EC2
DescribeInstances. Starts, stops and changes NOTHING. Used by the `status` action of frankie_fleet.yml.

Two sources, joined on instance id:
  - the day list (frankie_box_fleet: bucket + prefix from FRANKIE_FLEET_DAY_LIST, or a local file via --day-list) gives
    each day's assigned box, current stage and done/stage state, plus the classroom lease holder;
  - EC2 DescribeInstances (Filter tag:Project=frankie, state running|stopped|...) gives the live instance state, type,
    and the Day/Run/Commit tags each box carries.
boto3 is imported inside the call that uses it, so --day-list <path> runs with no boto3 and no AWS (the toy): it reads a
local day-list JSON and renders what the list knows, EC2 columns shown as '-'.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

SCHEMA = 'FRANKIE_FLEET_STATUS_V1'
PROJECT_TAG = 'frankie'


def _day_list_from_file(path):
    return json.loads(Path(path).read_bytes())


def _ec2_fleet_instances(region):
    """Live Project=frankie instances with their tags and state (read-only DescribeInstances)."""
    import boto3
    ec2 = boto3.client('ec2', region_name=region)
    out, token = [], None
    while True:
        kw = dict(Filters=[{'Name': 'tag:Project', 'Values': [PROJECT_TAG]}])
        if token:
            kw['NextToken'] = token
        resp = ec2.describe_instances(**kw)
        for res in resp.get('Reservations', []):
            for inst in res.get('Instances', []):
                tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
                out.append(dict(instance=inst['InstanceId'], state=inst['State']['Name'],
                                type=inst.get('InstanceType'), role=tags.get('Role'), day_tag=tags.get('Day'),
                                run_tag=tags.get('Run'), commit_tag=tags.get('Commit')))
        token = resp.get('NextToken')
        if not token:
            return out


def _days_by_box(day_list):
    """instance id -> [its day entries] from the day list (box = the assigned instance)."""
    by = {}
    for entry in (day_list or {}).get('days', []):
        by.setdefault(entry.get('box'), []).append(entry)
    return by


def _day_line(entry, lease_holder):
    day = entry.get('day')
    stage = entry.get('current_stage') or '-'
    done = 'done' if entry.get('done_utc') else stage
    classroom = (entry.get('stages', {}).get('classroom') or {}).get('state')
    in_classroom = classroom == 'lease_held' and not entry.get('done_utc')
    holder = ' CLASSROOM-LEASE' if in_classroom else ''
    return dict(day=day, current_stage=stage, status=done, classroom=classroom, holds_lease=in_classroom,
                lease_holder=lease_holder)


def collect(*, day_list, lease, ec2_instances, region):
    """Join the day list and EC2 into one status, one row per fleet instance (plus day rows). Pure: the caller fetches
    day_list/lease/ec2_instances (from S3+EC2, or a local file)."""
    by_box = _days_by_box(day_list)
    lease_holder = (lease or {}).get('holder_instance')
    rows = []
    seen = set()
    for inst in ec2_instances or []:
        iid = inst['instance']
        seen.add(iid)
        days = [_day_line(e, lease_holder) for e in by_box.get(iid, [])]
        rows.append(dict(inst, days=days, assigned_days=[d['day'] for d in days]))
    # day-list boxes with no live instance (stopped-and-terminated, or not yet launched)
    for box, entries in by_box.items():
        if box and box not in seen:
            rows.append(dict(instance=box, state='(not in DescribeInstances)', type=None, role=None,
                             days=[_day_line(e, lease_holder) for e in entries],
                             assigned_days=[e.get('day') for e in entries]))
    return dict(schema=SCHEMA, region=region, classroom_lease=lease, instances=rows,
                total_days=len((day_list or {}).get('days', [])))


def render(status):
    lines = ['fleet status (region %s): %d day(s); classroom lease: %s' % (
        status['region'], status['total_days'],
        (status['classroom_lease'] or {}).get('holder_instance') or 'free')]
    for row in status['instances']:
        days = ', '.join('%s@%s%s' % (d['day'], d['status'], ' [classroom]' if d['holds_lease'] else '')
                         for d in row['days']) or '-'
        lines.append('  %-20s %-14s %-14s days=[%s]' % (row['instance'], row.get('state') or '-',
                                                        row.get('type') or '-', days))
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    parser.add_argument('--day-list', help='a LOCAL day-list JSON (the toy / offline): reads it, no boto3, EC2 shown as -')
    parser.add_argument('--region', default=os.environ.get('FRANKIE_FLEET_REGION', 'us-east-1'))
    parser.add_argument('--json', action='store_true', help='print the status JSON instead of the rendered lines')
    args = parser.parse_args(argv)
    if args.day_list:
        day_list = _day_list_from_file(args.day_list)
        lease = (day_list.get('_lease') if isinstance(day_list, dict) else None)   # optional, for the offline toy
        ec2 = []
    else:
        import frankie_box_fleet as FL
        if not FL.enabled():
            print('fleet mode is OFF (FRANKIE_FLEET_DAY_LIST unset): no fleet to report')
            return 0
        st = FL.store()
        day_list = FL.read_day_list(st=st)
        lease = FL.lease_holder(st=st)
        ec2 = _ec2_fleet_instances(args.region)
    status = collect(day_list=day_list, lease=lease, ec2_instances=ec2, region=args.region)
    print(json.dumps(status, indent=1, default=str) if args.json else render(status))
    return 0


if __name__ == '__main__':
    sys.exit(main())
