"""Send a PowerShell script file to a Windows EC2 instance over SSM and wait for it.

Reads the script bytes verbatim (no shell quoting anywhere), sends AWS-RunPowerShellScript, polls
until it finishes, prints stdout and stderr, and exits nonzero unless SSM reports Success.

    python deploy/aws/ssm_run_ps1.py --instance i-... --region us-east-2 --script path.ps1 [--timeout 1800]
Credentials come from the environment or, if --env-file is given, from lines of NAME=value.
"""
import argparse
import os
import re
import sys
import time


def load_env_file(path):
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*(?:export\s+)?([A-Z_]+)\s*=\s*"?([^"\n]+)"?', line)
        if m and m.group(1).startswith('AWS_'):
            os.environ[m.group(1)] = m.group(2).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--region', default='us-east-2')
    parser.add_argument('--script', required=True)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--env-file')
    parser.add_argument('--comment', default='')
    args = parser.parse_args()
    if args.env_file:
        load_env_file(args.env_file)
    import boto3
    ssm = boto3.client('ssm', region_name=args.region)
    script = open(args.script, encoding='utf-8').read()
    command = ssm.send_command(InstanceIds=[args.instance], DocumentName='AWS-RunPowerShellScript',
                               Parameters={'commands': [script]}, TimeoutSeconds=args.timeout,
                               Comment=args.comment[:100])['Command']['CommandId']
    deadline = time.time() + args.timeout + 120
    status = 'Pending'
    while time.time() < deadline:
        time.sleep(10)
        try:
            inv = ssm.get_command_invocation(CommandId=command, InstanceId=args.instance)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        status = inv['Status']
        if status in ('Success', 'Failed', 'Cancelled', 'TimedOut'):
            break
    print('SSM status:', status)
    print(inv.get('StandardOutputContent', '')[-6000:])
    err = inv.get('StandardErrorContent', '')
    if err.strip():
        print('STDERR:', err[-2000:])
    return 0 if status == 'Success' else 1


if __name__ == '__main__':
    sys.exit(main())
