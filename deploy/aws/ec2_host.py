"""Status, start or stop one EC2 host, waiting for the state and for SSM to come online.

    python deploy/aws/ec2_host.py --instance i-... status|start|stop [--env-file scratchpad/aws.env]

Prints the instance state, type, KeepRunning tag, hours since launch and the approximate cost at
--hourly (default 1.80, the r7i.4xlarge Windows rate). Never prints a credential. `start` waits
until the SSM agent reports Online so a runner can follow immediately; `stop` waits until stopped.
"""
import argparse
import datetime
import os
import re
import sys
import time


def load_env_file(path):
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*(?:export\s+)?([A-Z_]+)\s*=\s*"?([^"\n]+)"?', line)
        if m and m.group(1).startswith('AWS_'):
            os.environ[m.group(1)] = m.group(2).strip()


def describe(ec2, instance):
    r = ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]
    tags = {t['Key']: t['Value'] for t in r.get('Tags', [])}
    return dict(state=r['State']['Name'], type=r['InstanceType'], launch=r['LaunchTime'],
                keep_running=tags.get('KeepRunning'), profile=r.get('IamInstanceProfile', {}).get('Arn', '').split('/')[-1])


def report(info, hourly):
    hours = (datetime.datetime.now(datetime.timezone.utc) - info['launch']).total_seconds() / 3600
    print(f"state={info['state']} type={info['type']} KeepRunning={info['keep_running']} profile={info['profile']} "
          f"since_launch={hours:.2f}h approx_cost=${hours * hourly:.2f} (at ${hourly}/h, counted only while running)")


def wait_state(ec2, instance, wanted, seconds=600):
    deadline = time.time() + seconds
    while time.time() < deadline:
        state = describe(ec2, instance)['state']
        if state == wanted:
            return state
        time.sleep(10)
    raise SystemExit(f'instance did not reach {wanted} within {seconds}s')


def wait_ssm(ssm, instance, seconds=600):
    deadline = time.time() + seconds
    while time.time() < deadline:
        info = ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds', 'Values': [instance]}])['InstanceInformationList']
        if info and info[0]['PingStatus'] == 'Online':
            return info[0].get('PlatformName', '')
        time.sleep(10)
    raise SystemExit(f'SSM agent not Online within {seconds}s')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--region', default='us-east-2')
    parser.add_argument('--env-file')
    parser.add_argument('--hourly', type=float, default=1.80)
    parser.add_argument('action', choices=('status', 'start', 'stop'))
    args = parser.parse_args()
    if args.env_file:
        load_env_file(args.env_file)
    import boto3
    ec2 = boto3.client('ec2', region_name=args.region)
    ssm = boto3.client('ssm', region_name=args.region)
    info = describe(ec2, args.instance)
    report(info, args.hourly)
    if args.action == 'start':
        if info['state'] == 'stopping':
            wait_state(ec2, args.instance, 'stopped')
        if describe(ec2, args.instance)['state'] == 'stopped':
            ec2.start_instances(InstanceIds=[args.instance])
        wait_state(ec2, args.instance, 'running')
        print('SSM Online:', wait_ssm(ssm, args.instance))
    elif args.action == 'stop':
        if info['state'] in ('running', 'pending'):
            ec2.stop_instances(InstanceIds=[args.instance])
        wait_state(ec2, args.instance, 'stopped')
        report(describe(ec2, args.instance), args.hourly)
    return 0


if __name__ == '__main__':
    sys.exit(main())
