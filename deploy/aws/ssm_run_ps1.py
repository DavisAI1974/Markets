"""Send a PowerShell script file to a Windows EC2 instance over SSM and wait for it.

Reads the script bytes verbatim (only --set prepends assignments), sends AWS-RunPowerShellScript, polls
until it finishes, prints stdout and stderr, and exits nonzero unless SSM reports Success.

    python deploy/aws/ssm_run_ps1.py --instance i-... --region us-east-2 --script path.ps1 [--timeout 1800]
        [--set Day=20211004 --set ToolsRoot=C:\\tools\\Markets ...]
Credentials come from the environment or, if --env-file is given, from lines of NAME=value.

--set is the ONLY substitution: each NAME=VALUE is prepended to the script as a PowerShell
single-quoted assignment, which is literal (no interpolation, no subexpression). A name that is
not a bare identifier, or a value carrying a single quote or a newline, is refused rather than
escaped, so there is still no quoting logic anywhere in this file.
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


def preamble(variables):
    """NAME=VALUE pairs as literal PowerShell assignments above the script body."""
    lines = []
    for item in variables:
        name, sep, value = item.partition('=')
        if not sep or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or "'" in value or '\n' in value:
            raise SystemExit('--set expects NAME=VALUE with a bare name and no quote or newline in the value')
        lines.append("$%s = '%s'" % (name, value))
    return ''.join(line + '\n' for line in lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--region', default='us-east-2')
    parser.add_argument('--script', required=True)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--env-file')
    parser.add_argument('--comment', default='')
    parser.add_argument('--set', dest='variables', action='append', default=[], metavar='NAME=VALUE',
                        help='prepend $NAME = ' + "'VALUE'" + ' above the script body')
    parser.add_argument('--tail', type=int, default=0,
                        help='print only this many trailing characters of the host stdout; 0 (the default) prints '
                             'everything the SSM API returned (the API itself keeps about 24,000 characters; a '
                             'longer output must travel by file, as the cycle report does)')
    args = parser.parse_args()
    if args.env_file:
        load_env_file(args.env_file)
    import boto3
    ssm = boto3.client('ssm', region_name=args.region)
    script = preamble(args.variables) + open(args.script, encoding='utf-8').read()
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
    output = inv.get('StandardOutputContent', '')
    print(output[-args.tail:] if args.tail > 0 else output)
    err = inv.get('StandardErrorContent', '')
    if err.strip():
        print('STDERR:', err[-2000:])
    return 0 if status == 'Success' else 1


if __name__ == '__main__':
    sys.exit(main())
