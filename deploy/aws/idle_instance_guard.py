"""Stop EC2 instances that have been idle, so an unattended box can never bill for weeks again.

Written 2026-09-16 after i-08cee7171c0a76a04 (r6i.2xlarge) ran idle at 0.6% CPU from September 2 to
September 16, about $184 at list price, with nobody watching it.

Rules, in order:
1. Every running instance in every listed region is inspected.
2. An instance tagged KeepRunning=true is never stopped; it is reported so the tag is a visible,
   deliberate choice (the 19-cycle Sunday run must carry this tag for its whole duration).
3. Otherwise, if its average CPU over the last --idle-hours is below --cpu-percent on every
   hourly datapoint, it is stopped. A stop keeps the volumes; nothing is terminated or deleted.
4. Instances younger than --idle-hours are left alone (their CloudWatch history is incomplete).
5. Unattached volumes are reported (they bill too) but never touched.

Dry run by default; --stop makes it act. Exit code is nonzero when something was stopped or
would be, so a scheduled run is visible in the workflow history.

    python deploy/aws/idle_instance_guard.py --regions us-east-1 us-east-2 --idle-hours 6 --cpu-percent 5 --stop
"""
import argparse
import datetime as dt
import json
import sys


def instances_in(ec2):
    for reservation in ec2.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])['Reservations']:
        for instance in reservation['Instances']:
            tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
            yield instance, tags


def idle_by_cpu(cloudwatch, instance_id, hours, threshold, now):
    points = cloudwatch.get_metric_statistics(
        Namespace='AWS/EC2', MetricName='CPUUtilization',
        Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
        StartTime=now - dt.timedelta(hours=hours), EndTime=now, Period=3600, Statistics=['Average'])['Datapoints']
    if len(points) < max(1, hours - 1):
        return None, points  # not enough history to judge
    return all(p['Average'] < threshold for p in points), points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regions', nargs='+', default=['us-east-1', 'us-east-2'])
    parser.add_argument('--idle-hours', type=int, default=6)
    parser.add_argument('--cpu-percent', type=float, default=5.0)
    parser.add_argument('--stop', action='store_true', help='actually stop idle instances (default: report only)')
    args = parser.parse_args()
    import boto3
    now = dt.datetime.now(dt.timezone.utc)
    report = dict(schema='AWS_IDLE_INSTANCE_GUARD_V1', checked_at=now.isoformat(), idle_hours=args.idle_hours,
                  cpu_percent=args.cpu_percent, acted=args.stop, instances=[], unattached_volumes=[])
    would_stop = stopped = 0
    for region in args.regions:
        ec2 = boto3.client('ec2', region_name=region)
        cloudwatch = boto3.client('cloudwatch', region_name=region)
        for instance, tags in instances_in(ec2):
            instance_id = instance['InstanceId']
            age_hours = (now - instance['LaunchTime']).total_seconds() / 3600
            row = dict(region=region, instance_id=instance_id, type=instance['InstanceType'], name=tags.get('Name'),
                       keep_running=tags.get('KeepRunning', '').lower() == 'true', age_hours=round(age_hours, 1))
            if row['keep_running']:
                row['decision'] = 'kept: KeepRunning=true'
            elif age_hours < args.idle_hours:
                row['decision'] = 'kept: younger than the idle window'
            else:
                idle, points = idle_by_cpu(cloudwatch, instance_id, args.idle_hours, args.cpu_percent, now)
                row['cpu_hourly_avg'] = [round(p['Average'], 2) for p in sorted(points, key=lambda p: p['Timestamp'])]
                if idle is None:
                    row['decision'] = 'kept: insufficient CloudWatch history'
                elif not idle:
                    row['decision'] = 'kept: busy'
                elif args.stop:
                    ec2.stop_instances(InstanceIds=[instance_id])
                    row['decision'] = 'STOPPED: idle'; stopped += 1
                else:
                    row['decision'] = 'WOULD STOP: idle (dry run)'; would_stop += 1
            report['instances'].append(row)
        for volume in ec2.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])['Volumes']:
            report['unattached_volumes'].append(dict(region=region, volume_id=volume['VolumeId'], size_gb=volume['Size'],
                                                     type=volume['VolumeType'], created=volume['CreateTime'].isoformat()))
    report['stopped'] = stopped; report['would_stop'] = would_stop
    print(json.dumps(report, indent=1, default=str))
    return 2 if (stopped or would_stop) else 0


if __name__ == '__main__':
    sys.exit(main())
