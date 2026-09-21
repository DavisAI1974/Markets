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
    assert "if (Test-Path (Join-Path $principal 'dipole-classroom-completion.json')) { throw" in CODE
    assert "stage='principal_output'" in CODE and 'the runner accepted the response' in CODE
    assert "$names = @('session-response.json', 'host-session-record.json', 'classroom-correction-request.json', 'classroom-correction-response.json'," in CODE
    assert "$_.Name -like 'incoming-*' -or $_.Name -like 'response-check-*'" in CODE
    assert "NOTHING_RECORDED" in CODE
    assert "'-principal-response-cycle-' + $CycleIndex" in CODE
    assert 'Move-Item -LiteralPath $source -Destination (Join-Path (Join-Path $target ' + "'principal') $name)" in CODE
    assert "$record.sha256 = Digest $source" in CODE
    assert "dipole-classroom-post-grade.json" in CODE and "'classroom-audit') 'dipole-classroom-post-grade.json'" in CODE
    assert "kept            = @('session-request.json', 'prompt.md', 'historical-prompt.md', 'receiver'" in CODE
    assert "'FRANKIE_PRINCIPAL_RESPONSE_SUPERSEDED_V1'" in CODE and "Write-Output ('RECEIPT '" in CODE
    writes = [line for line in CODE.splitlines() if 'Set-Content' in line]
    assert len(writes) == 1 and 'principal-response-superseded-' in CODE


def test_workflow_validates_inputs_and_passes_every_variable_by_set():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert inputs['reason']['required'] is True
    steps = workflow['jobs']['supersede']['steps']
    validate = next(s for s in steps if 'shapes only' in s.get('name', ''))['run']
    assert '^[0-9]{2}$' in validate and 'apostrophes' in validate
    ssm = next(s for s in steps if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--script deploy/aws/host/frankie_host_supersede_principal_response.ps1' in ssm
    for name, env in (('Day', 'DAY'), ('RunRoot', 'RUN_ROOT'), ('CycleIndex', 'CYCLE_INDEX'), ('Reason', 'REASON')):
        assert f'--set "{name}=${env}"' in ssm
    assert workflow['permissions'] == {'contents': 'read'}
