"""The idle box guard (Greg, 2026-10-07: the KeepRunning tag means "keep running only when in use"; the 2026-09-15 design:
stop an idle box unless KeepRunning=true). Runs on the GitHub runner every six hours (.github/workflows/frankie_box_idle_guard.yml)
or by hand. For every Frankie box (the instances named below, plus any instance whose Name tag starts with 'frankie-') that
is RUNNING:
  KeepRunning == 'true'      -> left running (in use: a run set it at its lane claim/start; reported)
  a FRESH lane lease          -> left running whatever the tag (a controller of a run holds the Linux lane within its
                                 freshness: s3://<transfer bucket>/pod-root/<run>/controller/lease.json, not released,
                                 heartbeat younger than LEASE_FRESH_SECONDS). ANY fresh or unreadable lease protects BOTH
                                 experiment boxes: every controller, wherever it is hosted (runner or main), drives the main
                                 box over SSM (queue, claim, export, release, coordinate, prepare) as well as the worker;
                                 reported with the lease
  right before a stop          -> the instance is described again: still running, KeepRunning still not 'true' and no fresh
                                 lease now, else left running with the reason (closes the window since the snapshot)
  otherwise                   -> STOPPED (ec2 StopInstances), reported with the reason; --dry-run reports without stopping
Nothing is terminated, no volume is touched, no tag is changed. The report (every instance, what was done and why) is
printed as JSON and written to --report. Exit 0; 2 when a stop call failed (the instance is named).
Source-built 2026-10-07; not run anywhere yet."""
import argparse
import json
import sys
import time

import boto3

TRANSFER_BUCKET = 'frankie-granite42-568968024170-us-east-1'
PREFIX = 'pod-root'
LEASE_FRESH_SECONDS = 600                       # the controller's freshness (pod_root/controller.py LEASE_FRESH_SECONDS)
BOXES = {                                       # the experiment's boxes: Name tag, lane
    'i-035994afa8bdf66a5': dict(region='us-east-1', lane='main', name='frankie-ingest32-20260917'),
    'i-0d17573dbce871520': dict(region='us-east-1', lane='linux', name='frankie-linux-r7i4xl'),
}
REGIONS = ('us-east-1', 'us-east-2')
SCHEMA = 'FRANKIE_IDLE_GUARD_REPORT_V1'


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def fresh_leases():
    """Every fresh lane lease under pod-root/<run>/controller/lease.json: [{run, host, pid, controller, heartbeat_utc, age}]."""
    s3 = boto3.client('s3', region_name='us-east-1')
    runs = []
    token = None
    while True:
        kw = dict(Bucket=TRANSFER_BUCKET, Prefix=PREFIX + '/', Delimiter='/')
        if token:
            kw['ContinuationToken'] = token
        page = s3.list_objects_v2(**kw)
        runs.extend(p['Prefix'].split('/')[1] for p in page.get('CommonPrefixes', []))
        token = page.get('NextContinuationToken')
        if not token:
            break
    fresh, stale = [], []
    for run in runs:
        key = '%s/%s/controller/lease.json' % (PREFIX, run)
        try:
            lease = json.loads(s3.get_object(Bucket=TRANSFER_BUCKET, Key=key)['Body'].read())
        except s3.exceptions.NoSuchKey:
            continue
        except Exception as error:  # noqa: BLE001 - an unreadable lease is reported, and treated as FRESH (never a stop on a guess)
            fresh.append(dict(run=run, unreadable='%s: %s' % (type(error).__name__, str(error)[:200]),
                              note='an unreadable lease protects its lanes; read it by hand'))
            continue
        age = time.time() - float(lease.get('heartbeat_epoch') or 0)
        doc = dict(run=run, host=lease.get('host'), pid=lease.get('pid'), controller=lease.get('controller'),
                   heartbeat_utc=lease.get('heartbeat_utc'), age_seconds=round(age), released_utc=lease.get('released_utc'))
        (fresh if not lease.get('released_utc') and age < LEASE_FRESH_SECONDS else stale).append(doc)
    return fresh, stale


def frankie_instances():
    """Every running or stopped instance of the experiment's boxes and of any instance named frankie-*."""
    found = []
    for region in REGIONS:
        ec2 = boto3.client('ec2', region_name=region)
        for page in ec2.get_paginator('describe_instances').paginate():
            for res in page.get('Reservations', []):
                for i in res.get('Instances', []):
                    tags = {t['Key']: t['Value'] for t in i.get('Tags', [])}
                    if i['InstanceId'] in BOXES or str(tags.get('Name', '')).startswith('frankie-'):
                        found.append(dict(instance=i['InstanceId'], region=region, name=tags.get('Name'),
                                          state=i.get('State', {}).get('Name'), type=i.get('InstanceType'),
                                          keep_running=tags.get('KeepRunning'), keep_running_policy=tags.get('KeepRunningPolicy'),
                                          lane=(BOXES.get(i['InstanceId']) or {}).get('lane'), launch=str(i.get('LaunchTime'))))
    return found


def protects(lease, box):
    """A fresh (or unreadable) lease protects BOTH experiment boxes (B3b, 2026-10-07): a controller hosted on the runner
    still drives the main box over SSM (pod_root/controller.py box(..., MAIN) for queue, claim, export, release,
    coordinate, prepare), so its lease protects the main box exactly as it protects the worker. Any other frankie-* box
    is not driven by a controller and is not protected by a lease."""
    if lease.get('unreadable'):
        return True
    return box['lane'] in ('main', 'linux')


def still_idle(box):
    """(idle, why) re-read immediately before StopInstances: the instance's state and KeepRunning tag now, and the
    leases now. Any read failure is NOT idle (never a stop on a guess)."""
    try:
        r = boto3.client('ec2', region_name=box['region']).describe_instances(InstanceIds=[box['instance']])
        i = r['Reservations'][0]['Instances'][0]
        tags = {t['Key']: t['Value'] for t in i.get('Tags', [])}
        if i.get('State', {}).get('Name') != 'running':
            return False, 'state now %s' % i.get('State', {}).get('Name')
        if str(tags.get('KeepRunning')).lower() == 'true':
            return False, 'KeepRunning=true now (set since the snapshot)'
        fresh, _ = fresh_leases()
        holders = [l for l in fresh if protects(l, box)]
        if holders:
            return False, 'a fresh lane lease protects it now: %s' % [l.get('run') for l in holders]
        return True, None
    except Exception as error:  # noqa: BLE001 - a failed re-read is not idle
        return False, 're-read before the stop failed (%s: %s): left running' % (type(error).__name__, str(error)[:200])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dry-run', action='store_true', help='report what would be stopped; stop nothing')
    p.add_argument('--report', default='idle-guard-report.json')
    a = p.parse_args()
    fresh, stale = fresh_leases()
    report = dict(schema=SCHEMA, at=utc(), dry_run=a.dry_run, fresh_leases=fresh, stale_leases=stale, instances=[])
    failed = 0
    for box in frankie_instances():
        row = dict(box)
        if box['state'] != 'running':
            row.update(action='none', reason='not running (%s)' % box['state'])
        elif str(box.get('keep_running')).lower() == 'true':
            row.update(action='left_running', reason='KeepRunning=true: in use (a run set it at its lane claim/start)')
        else:
            holders = [l for l in fresh if protects(l, box)]
            if holders:
                row.update(action='left_running', reason='a fresh lane lease protects it', leases=holders)
            else:
                row.update(action='stop' if a.dry_run else 'stopped',
                           reason='running with KeepRunning=%r and no fresh lane lease: idle (Greg: keep running only when in use)'
                                  % box.get('keep_running'))
                idle, why = (True, None) if a.dry_run else still_idle(box)
                if not idle:
                    row.update(action='left_running', reason='re-checked right before the stop: ' + why)
                elif not a.dry_run:
                    try:
                        r = boto3.client('ec2', region_name=box['region']).stop_instances(InstanceIds=[box['instance']])
                        row['stop_result'] = [dict(current=s['CurrentState']['Name'], previous=s['PreviousState']['Name'])
                                              for s in r.get('StoppingInstances', [])]
                    except Exception as error:  # noqa: BLE001 - named, never hidden; the run exits nonzero
                        failed += 1
                        row.update(action='stop_failed', error='%s: %s' % (type(error).__name__, str(error)[:300]))
        report['instances'].append(row)
    report['stopped'] = [r['instance'] for r in report['instances'] if r['action'] == 'stopped']
    report['would_stop'] = [r['instance'] for r in report['instances'] if r['action'] == 'stop']
    body = json.dumps(report, indent=1, sort_keys=True, default=str)
    with open(a.report, 'w', encoding='utf-8') as f:
        f.write(body + '\n')
    print(body)
    sys.exit(2 if failed else 0)


if __name__ == '__main__':
    main()
