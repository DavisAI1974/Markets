"""Greg's explicit stop of ingest run 35694087514; no instance or runner control.

Only cancel the unique SSM command bound to the dispatched commit, ingest action,
ingest script and launch time. No send_command, filesystem deletion, EC2 call,
Pod call, runner stop or restart is performed.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import boto3

INSTANCE = 'i-035994afa8bdf66a5'
COMMIT = '2ae4da204b0d2a12f605e765f281b505ff51491a'
START = datetime(2026, 9, 22, 6, 15, tzinfo=timezone.utc)
END = datetime(2026, 9, 22, 6, 25, tzinfo=timezone.utc)
TERMINAL = {'Success', 'Failed', 'Cancelled', 'TimedOut'}


def matches(command):
    text = '\n'.join(command.get('Parameters', {}).get('commands', []))
    requested = command.get('RequestedDateTime')
    return (command.get('DocumentName') == 'AWS-RunShellScript'
            and requested is not None and START <= requested <= END
            and INSTANCE in command.get('InstanceIds', [])
            and re.search(r"(?m)^ACTION='ingest'$", text) is not None
            and ("MARKETS_SHA='" + COMMIT + "'") in text
            and 'research/kalshi/frankie_boss/operations/ingest_block_sources.py' in text)


def main():
    ssm = boto3.client('ssm', region_name='us-east-1')
    candidates, token = [], None
    while True:
        args = dict(InstanceId=INSTANCE, MaxResults=50)
        if token:
            args['NextToken'] = token
        response = ssm.list_commands(**args)
        candidates.extend(c for c in response['Commands'] if matches(c))
        token = response.get('NextToken')
        if not token:
            break
    if len(candidates) != 1:
        raise SystemExit('Refused: expected exactly one pinned ingest command; found %d' % len(candidates))
    command = candidates[0]
    command_id = command['CommandId']
    receipt = dict(schema='FRANKIE_AUTHORIZED_INGEST_STOP_V1', authorization='Greg: Stop it and we will fix',
                   github_run_id=35694087514, instance=INSTANCE, dispatched_commit=COMMIT,
                   command_id=command_id, status_before=command['Status'],
                   requested_at=command['RequestedDateTime'].isoformat(), instance_stop_requested=False,
                   native_runner_stop_requested=False, files_deleted=False, restart_requested=False)
    path = Path('monday-ingest-stop-receipt.json')
    def save():
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        print(json.dumps(receipt, sort_keys=True), flush=True)
    save()
    if command['Status'] not in TERMINAL:
        ssm.cancel_command(CommandId=command_id, InstanceIds=[INSTANCE])
        receipt['cancellation_requested_at'] = datetime.now(timezone.utc).isoformat()
        save()
    deadline = time.monotonic() + 360
    while True:
        invocation = ssm.get_command_invocation(CommandId=command_id, InstanceId=INSTANCE)
        status = invocation['Status']
        if status in TERMINAL or time.monotonic() >= deadline:
            receipt['status_after'] = status
            receipt['status_details'] = invocation.get('StatusDetails')
            receipt['verified_at'] = datetime.now(timezone.utc).isoformat()
            save()
            print('Retained SSM stdout (all returned bytes):', flush=True)
            print(invocation.get('StandardOutputContent', ''), flush=True)
            print('Retained SSM stderr (all returned bytes):', flush=True)
            print(invocation.get('StandardErrorContent', ''), flush=True)
            if status not in TERMINAL:
                raise SystemExit('Cancellation not yet terminal; do not claim the ingest stopped')
            return
        time.sleep(3)


if __name__ == '__main__':
    main()
