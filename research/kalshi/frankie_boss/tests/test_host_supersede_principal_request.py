"""The host script that moves a cycle's rendered principal request aside, checked as text.

Built 2026-09-20 21:55Z (Greg: the run-findings ledger enters cycle 0's prompt; cycle 0 is rendered
again). Contract: variables refused when absent, no path literal and no credential, MOVES only (never
Remove-Item), refuses when a session-response.json exists or a runner is alive, moves exactly the
rendered request files (prompt.md, session-request.json, run-findings-witness.json, response-check-*),
names what it keeps, one receipt with sha256 per moved file; the workflow passes every variable by --set.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_supersede_principal_request.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_supersede_principal_request.yml'
DECLARE_SCRIPT = ROOT / 'deploy/aws/host/frankie_host_declare_identity_supersede.ps1'
DECLARE_WORKFLOW = ROOT / '.github/workflows/frankie_host_declare_identity_supersede.yml'
TEXT = SCRIPT.read_text()
CODE = '\n'.join(line for line in TEXT.splitlines() if not line.lstrip().startswith('#'))


def test_refuses_unsupplied_variables():
    block = CODE.split('foreach ($required in', 1)[1].split(') {', 1)[0]
    for name in ('Day', 'RunRoot', 'CycleIndex', 'Reason'):
        assert f"'{name}'" in block, name
    assert "$value -like 'HOST_*'" in CODE and "if ($CycleIndex -notmatch '^\\d{2}$')" in CODE


def test_moves_never_deletes_and_refuses_when_a_response_or_runner_exists():
    assert not re.search(r"['\"][A-Za-z]:[\\/]", CODE), 'a host path literal travels in the script'
    for forbidden in ('Remove-Item', 'Get-SSMParameter', 'ssm get-parameter', 'SecretString'):
        assert forbidden not in CODE, forbidden
    assert "if (Test-Path (Join-Path $principal 'session-response.json')) { throw" in CODE
    assert "CommandLine -like '*run_actual_sunday*'" in CODE and 'refusing: a runner process is alive' in CODE
    assert "$names = @('prompt.md', 'session-request.json', 'run-findings-witness.json')" in CODE
    assert "-Filter 'response-check-*'" in CODE
    assert "NOTHING_RENDERED" in CODE
    assert "'-principal-cycle-' + $CycleIndex" in CODE and 'Move-Item -LiteralPath $source -Destination (Join-Path $target $name)' in CODE
    assert "$record.sha256 = Digest $source" in CODE
    assert "kept            = @('historical-prompt.md', 'receiver'" in CODE
    assert "'FRANKIE_PRINCIPAL_REQUEST_SUPERSEDED_V1'" in CODE and "Write-Output ('RECEIPT '" in CODE


def test_workflow_passes_every_variable_by_set():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert inputs['reason']['required'] is True
    ssm = next(s for s in workflow['jobs']['supersede']['steps'] if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--script deploy/aws/host/frankie_host_supersede_principal_request.ps1' in ssm
    for name, env in (('Day', 'DAY'), ('RunRoot', 'RUN_ROOT'), ('CycleIndex', 'CYCLE_INDEX'), ('Reason', 'REASON')):
        assert f'--set "{name}=${env}"' in ssm
    assert workflow['permissions'] == {'contents': 'read'}


def test_declaration_script_and_workflow_carry_the_principal_option():
    code = '\n'.join(line for line in DECLARE_SCRIPT.read_text().splitlines() if not line.lstrip().startswith('#'))
    assert "$SupersedePrincipal = 'false'" in code and "@('--supersede-principal')" in code
    assert "if ($SupersedePrincipal -notin @('true', 'false')) { throw" in code
    assert '--receipt-directory $dayDirectory @principalArgs' in code
    workflow = yaml.safe_load(DECLARE_WORKFLOW.read_text())
    assert workflow[True]['workflow_dispatch']['inputs']['supersede_principal']['default'] == 'false'
    ssm = next(s for s in workflow['jobs']['declare']['steps'] if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--set "SupersedePrincipal=$SUPERSEDE_PRINCIPAL"' in ssm
