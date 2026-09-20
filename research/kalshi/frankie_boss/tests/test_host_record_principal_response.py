"""The host script that records Root's actual Frankie response, checked as text (no PowerShell here).

Built 2026-09-20 20:55Z when Root's recorder had run on his own machine: the record must be made on
the host. Contract: every variable refused when absent (three sha256/bytes triples validated), no
path literal and no credential, the presigned URLs never printed, each delivered file verified by
sha256 and bytes before use, the attestation's host_record.path must equal the record's place beside
the request (derived from the configuration's run directory), an existing session-response.json is
left alone, an existing record with different bytes refuses, nothing deleted or moved, the recorder
runs from the tools checkout and its status line is required, one receipt; the workflow fetches the
three files from a git ref, checks them, stages them with SigV4 presigns, masks the URLs, and passes
every variable by --set.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_record_principal_response.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_record_principal_response.yml'
TEXT = SCRIPT.read_text()
CODE = '\n'.join(line for line in TEXT.splitlines() if not line.lstrip().startswith('#'))
REQUIRED = ('Day', 'RunRoot', 'ToolsRoot', 'Python', 'CycleIndex', 'SourceRef', 'ResponseUrl', 'ResponseSha256',
            'ResponseBytes', 'AttestationUrl', 'AttestationSha256', 'AttestationBytes', 'RecordUrl', 'RecordSha256',
            'RecordBytes')


def test_refuses_unsupplied_or_malformed_variables():
    block = CODE.split('foreach ($required in', 1)[1].split(') {', 1)[0]
    for name in REQUIRED:
        assert f"'{name}'" in block, name
    assert "$value -like 'HOST_*'" in CODE
    assert "if ($CycleIndex -notmatch '^\\d{2}$')" in CODE
    assert "-notmatch '^[0-9a-f]{64}$'" in CODE and "-notmatch '^\\d+$'" in CODE


def test_no_path_literal_no_credential_nothing_deleted_urls_never_printed():
    assert not re.search(r"['\"][A-Za-z]:[\\/]", CODE), 'a host path literal travels in the script'
    for forbidden in ('Get-SSMParameter', 'ssm get-parameter', 'SecretString', 'Remove-Item', 'Move-Item', 'Rename-Item'):
        assert forbidden not in CODE, forbidden
    for line in CODE.splitlines():
        if 'Write-Output' in line or 'throw' in line:
            for url in ('$ResponseUrl', '$AttestationUrl', '$RecordUrl', '$url'):
                assert url not in line, 'a presigned URL would be printed'
    assert 'Invoke-WebRequest -Uri $url -OutFile $target -UseBasicParsing' in CODE


def test_every_delivered_file_is_verified_and_the_attestation_binds_the_record_on_this_host():
    assert "Fetch $ResponseUrl $responseFile $ResponseSha256 $ResponseBytes 'response'" in CODE
    assert "Fetch $AttestationUrl $attestationFile $AttestationSha256 $AttestationBytes 'host attestation'" in CODE
    assert "Fetch $RecordUrl $recordFile $RecordSha256 $RecordBytes 'host session record'" in CODE
    assert 'if ($got.Length -ne [int64]$expectedBytes -or $gotDigest -ne $expectedSha)' in CODE
    assert "$recordTarget = Join-Path $principal 'host-session-record.json'" in CODE
    assert 'if ((Normal $pinned.path) -ne (Normal $recordTarget))' in CODE
    assert 'if ($pinned.sha256 -ne $RecordSha256 -or [int64]$pinned.bytes -ne [int64]$RecordBytes)' in CODE
    assert "$principal = Join-Path (Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)) 'principal'" in CODE


def test_nothing_written_over():
    assert 'ALREADY_RECORDED' in CODE and 'exit 0' in CODE.split('ALREADY_RECORDED', 1)[1].split('\n', 2)[1]
    assert 'refusing: a different host-session-record.json is present' in CODE
    assert 'if (Test-Path $incoming) { throw' in CODE
    writes = [line for line in CODE.splitlines() if 'Set-Content' in line or 'Copy-Item' in line or 'Tee-Object' in line]
    assert len(writes) == 3  # the record placement, the recorder log tee, the receipt


def test_recorder_runs_from_the_tools_checkout_and_its_status_is_required():
    assert "$tool = Join-Path $ToolsRoot 'research\\kalshi\\frankie_boss\\operations\\record_actual_frankie_response.py'" in CODE
    assert '--configuration $cfgPath --configuration-sha256 $cfgSha --cycle-index ([int]$CycleIndex)' in CODE
    assert '--response $responseFile --response-sha256 $ResponseSha256' in CODE
    assert '--host-attestation $attestationFile --host-attestation-sha256 $AttestationSha256' in CODE
    assert "$output -notmatch 'actual_principal_response_recorded'" in CODE
    assert "if (-not (Test-Path $responsePath)) { throw 'the recorder reported success but session-response.json is absent' }" in CODE
    assert "'FRANKIE_PRINCIPAL_RESPONSE_RECORDED_V1'" in CODE and "Write-Output ('RECEIPT '" in CODE
    assert '$env:PYTHONPATH = $ToolsRoot' in CODE and 'Push-Location $ToolsRoot' in CODE


def test_workflow_fetches_checks_stages_masks_and_passes_every_variable():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert {'source_ref', 'response_path', 'attestation_path', 'record_path'} <= set(inputs)
    assert all(inputs[k]['required'] for k in ('source_ref', 'response_path', 'attestation_path', 'record_path'))
    steps = workflow['jobs']['record']['steps']
    fetch = next(s for s in steps if s.get('id') == 'files')['run']
    assert 'git fetch --depth 1 origin "$SOURCE_REF"' in fetch and 'git show "FETCH_HEAD:$RESPONSE_PATH"' in fetch
    for check in ("len(r['sections']) != 18", "rec['sha256'] != rsha", "h.get('host_authority')", "a.get(k) != r.get(k)"):
        assert check in fetch
    stage = next(s for s in steps if 'generate_presigned_url' in s.get('run', ''))['run']
    assert "Config(signature_version='s3v4')" in stage and "print('::add-mask::' + url)" in stage and "'get_object'" in stage
    ssm = next(s for s in steps if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--script deploy/aws/host/frankie_host_record_principal_response.ps1' in ssm and '--tail 0' in ssm
    for name in REQUIRED:
        assert f'--set "{name}=' in ssm, name
    assert 'echo' not in ssm.replace('--comment', '')
    assert workflow['permissions'] == {'contents': 'read'}
