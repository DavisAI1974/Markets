"""The host script that moves a cycle's RECORDED principal response aside, checked as text.

Built 2026-09-21 (the Dipole classroom exchange, Greg: option 1): cycle 0's recorded response carried no classroom
teach-back and the runner stopped on it; the request is unchanged, so only the recorded response and what the
recorder placed beside it move aside. Contract: variables refused when absent, no path literal and no credential,
MOVES only (never Remove-Item), refuses when a runner is alive or a classroom completion exists, moves exactly the
recorded-response files (session-response.json, host-session-record.json, incoming-*, response-check-*, the classroom
turn files, the audit post-grade), names what it keeps (the request), one receipt with sha256 per moved file; the
workflow validates its inputs and passes every variable by --set.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_supersede_principal_response.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_supersede_principal_response.yml'
TEXT = SCRIPT.read_text()
CODE = '\n'.join(line for line in TEXT.splitlines() if not line.lstrip().startswith('#'))


def test_refuses_unsupplied_variables():
    block = CODE.split('foreach ($required in', 1)[1].split(') {', 1)[0]
    for name in ('Day', 'RunRoot', 'CycleIndex', 'Reason'):
        assert f"'{name}'" in block, name
    assert "$value -like 'HOST_*'" in CODE and "if ($CycleIndex -notmatch '^\\d{2}$')" in CODE


def test_moves_never_deletes_and_refuses_when_a_runner_or_a_completion_exists():
    assert not re.search(r"['\"][A-Za-z]:[\\/]", CODE), 'a host path literal travels in the script'
    for forbidden in ('Remove-Item', 'Get-SSMParameter', 'ssm get-parameter', 'SecretString', 'Set-Content -Path $cyclesDb'):
        assert forbidden not in CODE, forbidden
    assert "CommandLine -like '*run_actual_sunday*'" in CODE and 'refusing: a runner process is alive' in CODE
    assert "if (Test-Path -LiteralPath $completion) { throw" in CODE and "'dipole-classroom-completion.json'" in CODE
    assert "stage='principal_output'" in CODE and 'the runner accepted the response' in CODE
    assert "$responseNames = @('session-response.json', 'host-session-record.json', 'classroom-correction-request.json', 'classroom-correction-response.json'," in CODE
    assert "$_.Name -like 'incoming-*' -or $_.Name -like 'response-check-*'" in CODE
    assert "NOTHING_RECORDED" in CODE
    assert "'-principal-response-cycle-' + $CycleIndex" in CODE
    assert 'Move-Item -LiteralPath $source -Destination $destination' in CODE
    assert "ComputeHash($stream)" in CODE and "sha256 = $rootEntry.sha256" in CODE
    assert "'classroom-audit/dipole-classroom-post-grade.json'" in CODE
    assert "$kept = @('session-request.json', 'prompt.md', 'historical-prompt.md', 'receiver'" in CODE
    assert "'FRANKIE_PRINCIPAL_RESPONSE_SUPERSEDED_V1'" in CODE and "Write-Output ('RECEIPT '" in CODE
    assert 'Write-StateJson $intentPath $intent' in CODE and 'Complete-ScopedIntent $intentPath' in CODE
    assert CODE.index('Write-StateJson $intentPath $intent') < CODE.index('Complete-ScopedIntent $intentPath')
    assert '[IO.FileMode]::CreateNew' in CODE and '$stream.Flush($true)' in CODE
    assert '[IO.File]::Move($pending, $full)' in CODE
    assert 'principal-response-superseded-' in CODE and 'FRANKIE_PRINCIPAL_RESPONSE_INTENT_V1' in CODE
    assert 'Get-StateManifest $source' in CODE and 'Assert-StateManifest $destination $entry.manifest' in CODE
    assert "'code-bound-state.lock'" in CODE and '[IO.FileShare]::None' in CODE
    assert 'Assert-ForeignStateIntents $intentSchema' in CODE
    assert 'Get-CimInstance Win32_Process -ErrorAction Stop' in CODE
    # the principal_output gate reads the coordinator's sqlite read-only through the host python; any error refuses, never passes
    assert "?mode=ro', uri=True" in CODE and "if ($LASTEXITCODE -ne 0 -or $accepted -notmatch '^\\d+$') { throw" in CODE
    assert "Where-Object { $_.CommandLine -like '*run_actual_sunday*' }" in CODE


def test_workflow_validates_inputs_and_passes_every_variable_by_set():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert inputs['reason']['required'] is True
    steps = workflow['jobs']['supersede']['steps']
    validate = next(s for s in steps if 'shapes only' in s.get('name', ''))['run']
    assert '^[0-9]{2}$' in validate and 'apostrophes' in validate
    ssm = next(s for s in steps if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--script deploy/aws/host/frankie_host_supersede_principal_response.ps1' in ssm
    for name, env in (('Day', 'DAY'), ('RunRoot', 'RUN_ROOT'), ('CycleIndex', 'CYCLE_INDEX'), ('Reason', 'REASON'), ('Python', 'HOST_PYTHON')):
        assert f'--set "{name}=${env}"' in ssm
    assert workflow['permissions'] == {'contents': 'read'}
