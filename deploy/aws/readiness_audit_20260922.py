"""Read retained evidence after the authorized stop; no checkout, replay or model."""
from pathlib import Path
import time
import boto3

INSTANCE = 'i-035994afa8bdf66a5'
CANCELLED_COMMAND = 'eea87d2f-a1d7-428e-ab57-3fdab2980eb6'


def main():
    ssm = boto3.client('ssm', region_name='us-east-1')
    prior = ssm.get_command_invocation(CommandId=CANCELLED_COMMAND, InstanceId=INSTANCE)
    if prior['Status'] not in ('Success', 'Failed', 'Cancelled', 'TimedOut'):
        raise SystemExit('Prior ingest command is still active; read-only audit not sent')
    # Exactly one ACTION=status call, followed by a read-only audit in the same SSM command.
    status = Path('deploy/aws/box/frankie_box_ingest_block.sh').read_text()
    audit = Path('deploy/aws/box/frankie_box_readiness_audit.py').read_text()
    script = "ACTION='status'\nMARKETS_SHA='2ae4da204b0d2a12f605e765f281b505ff51491a'\n" + status + "\n/opt/frankie-box/venv/bin/python - <<'READINESS_AUDIT_PY'\n" + audit + "\nREADINESS_AUDIT_PY\n"
    command = ssm.send_command(InstanceIds=[INSTANCE], DocumentName='AWS-RunShellScript',
        Parameters={'commands': [script], 'executionTimeout': ['240']}, TimeoutSeconds=300,
        Comment='Greg requested read-only packing, process, brain and Friday-anchor audit')['Command']['CommandId']
    print('SSM audit command:', command, flush=True)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        time.sleep(3)
        try:
            value = ssm.get_command_invocation(CommandId=command, InstanceId=INSTANCE)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if value['Status'] in ('Success', 'Failed', 'Cancelled', 'TimedOut'):
            print('SSM audit status:', value['Status'], flush=True)
            print(value.get('StandardOutputContent', ''), flush=True)
            print(value.get('StandardErrorContent', ''), flush=True)
            if value['Status'] != 'Success':
                raise SystemExit(1)
            return
    raise SystemExit('Read-only audit has not completed')


if __name__ == '__main__':
    main()
