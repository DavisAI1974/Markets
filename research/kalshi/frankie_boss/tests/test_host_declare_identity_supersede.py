"""The declare-identity-supersede host script, checked as text (there is no PowerShell here).

Sent verbatim to the native host over SSM, it is the operator's declaration that a cycle's saved
binding may be superseded by the current code identity (2026-09-20). The contract that must not
drift: variables refused when absent (Reason included), CycleIndex two digits, no path literal and
no credential, refuses unless the tools HEAD is the configuration's boss_commit, refuses while a
runner process is alive, invokes the checked-in helper with the request id composed from the
configuration's run_id and the cycle index, sends the receipt to the DAY directory, and writes
nothing else (the helper owns the declaration file). The workflow passes every variable by --set.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_declare_identity_supersede.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_declare_identity_supersede.yml'
HELPER = 'research/kalshi/frankie_boss/operations/declare_identity_supersede.py'
REQUIRED_VARIABLES = ('Day', 'RunRoot', 'ToolsRoot', 'Python', 'Reason')
TEXT = SCRIPT.read_text()
CODE = '\n'.join(line for line in TEXT.splitlines() if not line.lstrip().startswith('#'))


def test_refuses_unsupplied_variables_and_a_malformed_cycle_index():
    for name in REQUIRED_VARIABLES:
        assert f"'{name}'" in CODE.split('foreach ($required in', 1)[1].split(')', 1)[0]
    assert "$value -like 'HOST_*'" in CODE and 'was not supplied by ssm_run_ps1.py --set' in CODE
    assert "$CycleIndex = '00'" in CODE and r"$CycleIndex -notmatch '^\d{2}$'" in CODE


def test_no_path_literal_no_credential_and_nothing_written_by_the_script_itself():
    assert not re.search(r"['\"][A-Za-z]:[\\/]", CODE), 'a host path literal travels in the script'
    for forbidden in ('Get-SSMParameter', 'ssm get-parameter', 'SecretString', 'Remove-Item', 'Move-Item',
                      'Set-Content', 'Out-File', 'New-Item'):
        assert forbidden not in CODE, forbidden


def test_refuses_a_stale_checkout_and_a_live_runner_before_declaring():
    assert '$head -ne $cfg.host_runtime.boss_commit' in CODE and 'refusing: tools HEAD' in CODE
    assert "$_.CommandLine -like '*run_actual_sunday*'" in CODE and 'refusing: a runner process is alive' in CODE
    guards = CODE.index('refusing: a runner process is alive')
    assert guards < CODE.index('& $Python $helper'), 'the helper runs before the refusals'


def test_invokes_the_checked_in_helper_with_the_composed_request_id_and_the_day_receipt_directory():
    assert f"Join-Path $ToolsRoot '{HELPER}'" in CODE
    assert "$requestId = $cfg.run_id + '-cycle-' + $CycleIndex" in CODE
    assert '$env:PYTHONPATH = $ToolsRoot' in CODE
    call = [line for line in CODE.splitlines() if line.startswith('& $Python $helper')][0]
    for argument in ('--run-directory $runDirectory', '--tools-root $ToolsRoot', '--request-id $requestId',
                     '--reason $Reason', '--receipt-directory $dayDirectory'):
        assert argument in call, argument
    assert 'if ($LASTEXITCODE -ne 0) { throw ("declaration helper exited " + $LASTEXITCODE) }' in CODE


def test_workflow_passes_every_variable_by_set_and_requires_the_reason():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert inputs['reason']['required'] is True
    assert set(inputs) == {'instance', 'day', 'run_root', 'tools_root', 'python', 'cycle_index', 'reason'}
    run = workflow['jobs']['declare']['steps'][-1]['run']
    assert '--script deploy/aws/host/frankie_host_declare_identity_supersede.ps1' in run
    for name, env in (('Day', 'DAY'), ('RunRoot', 'RUN_ROOT'), ('ToolsRoot', 'TOOLS_ROOT'), ('Python', 'HOST_PYTHON'),
                      ('CycleIndex', 'CYCLE_INDEX'), ('Reason', 'REASON')):
        assert f'--set "{name}=${env}"' in run, name
    assert workflow['permissions'] == {'contents': 'read'}
