"""The host script that exports one cycle's principal request materials for Root, checked as text.

Built 2026-09-20 21:40Z: Root's Frankie session runs off the host and never had the durable request.
Contract: variables refused when absent, no path literal and no credential, the presigned URLs never
printed, exactly the three retained files uploaded unchanged (each printed with bytes and sha256),
nothing deleted, moved or written over on the host (one receipt), and the workflow signs SigV4 presigns,
masks them, passes every variable by --set, and verifies each upload against the host's hashes.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_export_principal_request.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_export_principal_request.yml'
TEXT = SCRIPT.read_text()
CODE = '\n'.join(line for line in TEXT.splitlines() if not line.lstrip().startswith('#'))
REQUIRED = ('Day', 'RunRoot', 'CycleIndex', 'RequestUrl', 'PromptUrl', 'HistoricalUrl')


def test_refuses_unsupplied_variables():
    block = CODE.split('foreach ($required in', 1)[1].split(') {', 1)[0]
    for name in REQUIRED:
        assert f"'{name}'" in block, name
    assert "$value -like 'HOST_*'" in CODE and "if ($CycleIndex -notmatch '^\\d{2}$')" in CODE


def test_no_path_literal_no_credential_nothing_deleted_urls_never_printed():
    assert not re.search(r"['\"][A-Za-z]:[\\/]", CODE), 'a host path literal travels in the script'
    for forbidden in ('Get-SSMParameter', 'ssm get-parameter', 'SecretString', 'Remove-Item', 'Move-Item', 'Rename-Item', 'Copy-Item'):
        assert forbidden not in CODE, forbidden
    for line in CODE.splitlines():
        if 'Write-Output' in line or 'throw' in line:
            for url in ('$RequestUrl', '$PromptUrl', '$HistoricalUrl', '$files[$name]'):
                assert url not in line, 'a presigned URL would be printed'
    writes = [line for line in CODE.splitlines() if 'Set-Content' in line]
    assert len(writes) == 1 and 'principal-request-exported-' in CODE  # the one receipt


def test_exactly_the_three_retained_files_unchanged():
    assert "'session-request.json' = $RequestUrl" in CODE and "'prompt.md'            = $PromptUrl" in CODE
    assert "'historical-prompt.md' = $HistoricalUrl" in CODE
    assert 'Invoke-WebRequest -Uri $files[$name] -Method Put -InFile $path -UseBasicParsing' in CODE
    assert 'Write-Output ("EXPORTED " + $name + " bytes=" + $bytes + " sha256=" + $digest)' in CODE
    assert "$principal = Join-Path (Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)) 'principal'" in CODE
    assert "'FRANKIE_PRINCIPAL_REQUEST_EXPORTED_V1'" in CODE


def test_workflow_signs_masks_passes_every_variable_and_verifies():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    steps = workflow['jobs']['export']['steps']
    sign = next(s for s in steps if s.get('id') == 'sign')['run']
    assert "Config(signature_version='s3v4')" in sign and "print('::add-mask::' + url)" in sign and "'put_object'" in sign
    ssm = next(s for s in steps if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--script deploy/aws/host/frankie_host_export_principal_request.ps1' in ssm and '--tail 0' in ssm
    for name in REQUIRED:
        assert f'--set "{name}=' in ssm, name
    verify = next(s for s in steps if 'VERIFIED' in s.get('run', ''))['run']
    assert "hashlib.sha256(body).hexdigest()" in verify and "EXPORTED (\\S+) bytes=(\\d+) sha256=([0-9a-f]{64})" in verify
    assert workflow['permissions'] == {'contents': 'read'}
