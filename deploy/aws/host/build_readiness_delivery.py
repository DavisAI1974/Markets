"""Build the PowerShell delivery script that places published readiness on the native host and
writes the credential-free execution trigger the cycles stage waits for.

    python deploy/aws/host/build_readiness_delivery.py --readiness <dir> --request-id <id>
        --request-sha256 <sha> --out delivery.ps1

The readiness directory is the retained-granite-ready-<run_id> artifact of
frankie_retained_granite.yml. Only the six files the native runtime verifies are delivered
(operations/run_actual_sunday.py binds service-pins.json by sha256 and re-hashes the other five).
Bytes are embedded base64 so they land byte-exact. The script refuses on the runner if the readiness
is bound to a different request, and refuses on the host if a trigger already exists (the trigger is
immutable by contract, operations/SSM_POD_CREDENTIAL.md). No credential is read, embedded or printed.
"""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

DELIVERED = ('service-pins.json', 'pod-info.json', 'startup-intent.json', 'run.json',
             'service-ready.json', 'observer.json')
SCHEMA = 'FRANKIE_ACTUAL_EXECUTE_V1'
READINESS_ROOT = 'C:/Codex/Frankie-BOSS-20260919/readiness'
HOST_CONFIGURATION = 'C:/Codex/Frankie-BOSS-20260919/days/20211003/actual-host-configuration.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--readiness', required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', args.request_id):
        raise SystemExit('request id must be a bare identifier')
    if not re.fullmatch('[0-9a-f]{64}', args.request_sha256):
        raise SystemExit('request sha256 must be 64 hex characters')
    source = Path(args.readiness)
    files = {}
    for name in DELIVERED:
        path = source/name
        if not path.is_file():
            raise SystemExit('readiness artifact lacks ' + name)
        files[name] = path.read_bytes()
    pins = json.loads(files['service-pins.json'])
    bound = pins.get('request_sha256')
    if bound != args.request_sha256 or pins.get('admission', {}).get('request_sha256') != args.request_sha256:
        raise SystemExit('readiness is bound to request %s, not %s; refusing to deliver' % (bound, args.request_sha256))
    ready = json.loads(files['service-ready.json'])
    if ready.get('inference_sent') is not False:
        raise SystemExit('service-ready.json must record inference_sent false before any trigger')
    pins_sha256 = hashlib.sha256(files['service-pins.json']).hexdigest()
    readiness_directory = READINESS_ROOT + '/' + args.request_id
    trigger = json.dumps(dict(schema=SCHEMA, readiness_directory=readiness_directory,
                              service_pins_sha256=pins_sha256), separators=(',', ':'), sort_keys=True)

    lines = ["$ErrorActionPreference = 'Stop'",
             "$ready = '%s'" % readiness_directory,
             "$cfg = Get-Content '%s' -Raw | ConvertFrom-Json" % HOST_CONFIGURATION,
             "$triggerDirectory = $cfg.host_runtime.pod_credential_ssm.trigger_directory",
             "if (-not $triggerDirectory) { throw 'host configuration declares no trigger_directory' }",
             "$triggerDir = Join-Path $triggerDirectory '%s'" % args.request_id,
             "$trigger = Join-Path $triggerDir '%s.json'" % SCHEMA,
             "if (Test-Path $trigger) { throw ('trigger already exists (immutable): ' + $trigger) }",
             "New-Item -ItemType Directory -Force -Path $ready | Out-Null",
             "$sha = [System.Security.Cryptography.SHA256]::Create()"]
    for name, raw in files.items():
        expected = hashlib.sha256(raw).hexdigest()
        lines += ["$bytes = [Convert]::FromBase64String('%s')" % base64.b64encode(raw).decode('ascii'),
                  "[IO.File]::WriteAllBytes((Join-Path $ready '%s'), $bytes)" % name,
                  "$got = ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes((Join-Path $ready '%s'))))).Replace('-','').ToLower()" % name,
                  "if ($got -ne '%s') { throw 'delivered %s differs from the published bytes' }" % (expected, name),
                  "Write-Output ('delivered %s sha256=' + $got)" % name]
    lines += ["New-Item -ItemType Directory -Force -Path $triggerDir | Out-Null",
              "[IO.File]::WriteAllText($trigger, '%s', (New-Object System.Text.UTF8Encoding $false))" % trigger.replace("'", "''"),
              "Write-Output ('trigger written: ' + $trigger)",
              "Write-Output ('RECEIPT ' + (@{schema='FRANKIE_READINESS_DELIVERY_RECEIPT_V1'; request_id='%s'; request_sha256='%s'; readiness_directory=$ready; service_pins_sha256='%s'; trigger=$trigger; at=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()} | ConvertTo-Json -Compress))"
              % (args.request_id, args.request_sha256, pins_sha256)]
    Path(args.out).write_text('\n'.join(lines) + '\n', encoding='ascii')
    print(json.dumps(dict(status='delivery_script_built', request_id=args.request_id, request_sha256=args.request_sha256,
                          readiness_directory=readiness_directory, service_pins_sha256=pins_sha256,
                          files={name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
                          script_bytes=Path(args.out).stat().st_size)))


if __name__ == '__main__':
    main()
