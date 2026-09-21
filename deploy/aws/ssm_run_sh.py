"""Send a bash script file to a Linux EC2 instance over SSM and wait for it.

The Linux twin of ssm_run_ps1.py (Frankie's box i-035994afa8bdf66a5 is Ubuntu). Reads the script bytes
verbatim (only --set prepends assignments), sends AWS-RunShellScript, polls until it finishes, prints
stdout and stderr, and exits nonzero unless SSM reports Success.

    python deploy/aws/ssm_run_sh.py --instance i-... --region us-east-1 --script path.sh [--timeout 1800]
        [--set DAY=20211003 --set WORK=/opt/frankie ...]
Credentials come from the environment or, if --env-file is given, from lines of NAME=value.

--set is the ONLY substitution: each NAME=VALUE is prepended to the script as a bash single-quoted
assignment, which is literal (no expansion, no command substitution). A name that is not a bare
identifier, or a value carrying a single quote or a newline, is refused rather than escaped, so there
is still no quoting logic anywhere in this file. The script runs as root under /bin/sh -c via the
document; scripts that need bash start with a bash shebang re-exec or use only POSIX sh.
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
    """NAME=VALUE pairs as literal shell assignments above the script body."""
    lines = []
    for item in variables:
        name, sep, value = item.partition('=')
        if not sep or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or "'" in value or '\n' in value:
            raise SystemExit('--set expects NAME=VALUE with a bare name and no quote or newline in the value')
        lines.append("%s='%s'" % (name, value))
    return ''.join(line + '\n' for line in lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--script', required=True)
    parser.add_argument('--timeout', type=int, default=1800,
                        help='seconds the command may run on the box (SSM executionTimeout, 1..172800)')
    parser.add_argument('--env-file')
    parser.add_argument('--comment', default='')
    parser.add_argument('--set', dest='variables', action='append', default=[], metavar='NAME=VALUE',
                        help="prepend NAME='VALUE' above the script body")
    parser.add_argument('--tail', type=int, default=0,
                        help='print only this many trailing characters of the box stdout; 0 (the default) prints '
                             'everything the SSM API returned (the API keeps about 24,000 characters; longer '
                             'output must travel by file)')
    args = parser.parse_args()
    if not re.fullmatch(r'i-[0-9a-f]{8,17}', args.instance) or not re.fullmatch(r'[a-z]{2}-[a-z]+-\d', args.region):
        raise SystemExit('instance must look like i-<hex> and region like us-east-1')
    if not 1 <= args.timeout <= 172800:
        raise SystemExit('timeout must be within 1..172800 seconds')
    if args.env_file:
        load_env_file(args.env_file)
    import boto3
    ssm = boto3.client('ssm', region_name=args.region)
    script = preamble(args.variables) + open(args.script, encoding='utf-8').read()
    command = ssm.send_command(InstanceIds=[args.instance], DocumentName='AWS-RunShellScript',
                               Parameters={'commands': [script], 'executionTimeout': [str(args.timeout)]},
                               TimeoutSeconds=min(max(args.timeout, 30), 2592000),
                               Comment=args.comment[:100])['Command']['CommandId']
    print('SSM command:', command)
    deadline = time.time() + args.timeout + 120
    status = 'Pending'
    inv = {}
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
        print('STDERR:', err[-4000:])
    return 0 if status == 'Success' else 1


if __name__ == '__main__':
    sys.exit(main())
