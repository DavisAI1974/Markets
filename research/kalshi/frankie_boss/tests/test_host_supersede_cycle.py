"""The host script that moves an open cycle's retained state aside for a rerun from the beginning, as text.

Built 2026-09-20 22:20Z (Greg: "I wanted a full rerun from the beginning and not steps"). Contract:
variables refused when absent, no path literal and no credential, MOVES only (never Remove-Item), refuses
when a session-response.json is recorded or a runner is alive, moves the cycle's execution directory and the
coordinator's handoff directory (named by sha256 of the request id), one receipt with sha256 per moved file,
names what it keeps; the workflow passes every variable by --set; the declaration script and workflow carry
the cycle option.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_supersede_cycle.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_supersede_cycle.yml'
DECLARE_SCRIPT = ROOT / 'deploy/aws/host/frankie_host_declare_identity_supersede.ps1'
DECLARE_WORKFLOW = ROOT / '.github/workflows/frankie_host_declare_identity_supersede.yml'
TEXT = SCRIPT.read_text()
CODE = '\n'.join(line for line in TEXT.splitlines() if not line.lstrip().startswith('#'))


def test_refuses_unsupplied_variables():
    block = CODE.split('foreach ($required in', 1)[1].split(') {', 1)[0]
    for name in ('Day', 'RunRoot', 'CycleIndex', 'Reason'):
        assert f"'{name}'" in block, name
    assert "$value -like 'HOST_*'" in CODE and "if ($CycleIndex -notmatch '^\\d{2}$')" in CODE


def test_moves_the_cycle_and_handoff_never_deletes_and_refuses_on_a_response_or_runner():
    assert not re.search(r"['\"][A-Za-z]:[\\/]", CODE), 'a host path literal travels in the script'
    for forbidden in ('Remove-Item', 'Get-SSMParameter', 'ssm get-parameter', 'SecretString'):
        assert forbidden not in CODE, forbidden
    assert "'session-response.json'" in CODE and 'refusing: a session-response.json is recorded' in CODE
    assert "CommandLine -like '*run_actual_sunday*'" in CODE and 'refusing: a runner process is alive' in CODE
    assert "$requestId = $cfg.run_id + '-cycle-' + $CycleIndex" in CODE
    assert "[Text.Encoding]::UTF8.GetBytes($requestId)" in CODE and "('handoff-' + $requestSha)" in CODE
    assert "('cycle-' + $CycleIndex)" in CODE and 'NOTHING_RETAINED' in CODE
    assert "'-cycle-' + $CycleIndex" in CODE and 'Move-Item -LiteralPath $source -Destination $destination' in CODE
    assert 'Get-StateManifest $source' in CODE and 'ComputeHash($stream)' in CODE
    assert 'Assert-StateManifest $destination $entry.manifest' in CODE
    assert "$kept = @('cycles.sqlite" in CODE
    assert "'FRANKIE_CYCLE_STATE_SUPERSEDED_V1'" in CODE and "Write-Output ('RECEIPT '" in CODE
    assert 'Write-StateJson $intentPath $intent' in CODE and 'Complete-ScopedIntent $intentPath' in CODE
    assert CODE.index('Write-StateJson $intentPath $intent') < CODE.index('Complete-ScopedIntent $intentPath')
    assert '[IO.FileMode]::CreateNew' in CODE and '$stream.Flush($true)' in CODE
    assert '[IO.File]::Move($pending, $full)' in CODE
    assert "'code-bound-state.lock'" in CODE and '[IO.FileShare]::None' in CODE
    assert 'Assert-ForeignStateIntents $intentSchema' in CODE
    assert 'Get-CimInstance Win32_Process -ErrorAction Stop' in CODE
    assert "'dipole-classroom-completion.json'" in CODE and "stage='principal_output'" in CODE
    assert "?mode=ro', uri=True" in CODE and 'could not be evaluated' in CODE


def test_workflow_passes_every_variable_by_set():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert inputs['reason']['required'] is True
    ssm = next(s for s in workflow['jobs']['supersede']['steps'] if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--script deploy/aws/host/frankie_host_supersede_cycle.ps1' in ssm
    for name, env in (('Day', 'DAY'), ('RunRoot', 'RUN_ROOT'), ('CycleIndex', 'CYCLE_INDEX'), ('Reason', 'REASON'), ('Python', 'HOST_PYTHON')):
        assert f'--set "{name}=${env}"' in ssm
    assert workflow['permissions'] == {'contents': 'read'}


def test_declaration_script_and_workflow_carry_the_cycle_option():
    code = '\n'.join(line for line in DECLARE_SCRIPT.read_text().splitlines() if not line.lstrip().startswith('#'))
    assert "$SupersedeCycle = 'false'" in code and "$principalArgs += @('--supersede-cycle')" in code
    assert "if ($SupersedeCycle -notin @('true', 'false')) { throw" in code
    workflow = yaml.safe_load(DECLARE_WORKFLOW.read_text())
    assert workflow[True]['workflow_dispatch']['inputs']['supersede_cycle']['default'] == 'false'
    ssm = next(s for s in workflow['jobs']['declare']['steps'] if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--set "SupersedeCycle=$SUPERSEDE_CYCLE"' in ssm
