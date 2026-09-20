"""The read-only binding-diff host probe, checked as text (there is no PowerShell here).

Built on 2026-09-20 when the declared identity supersede was still refused: it rebuilds the cycle
binding from what is on disk and prints only the differing key paths, so the next fix is measured
rather than guessed (it found controller.arm_hash). The contract: variables refused when absent, no
path literal and no credential, the only write is the embedded Python to $env:TEMP, the cycle store
is opened read-only, the embedded Python parses, the configuration is read with utf-8-sig (the host
writes a BOM), and the workflow passes every variable by --set.
"""
import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_binding_diff.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_binding_diff.yml'
REQUIRED_VARIABLES = ('Day', 'RunRoot', 'ToolsRoot', 'Python')
TEXT = SCRIPT.read_text()
EMBEDDED_PYTHON = TEXT.split("$code = @'\n", 1)[1].split("\n'@", 1)[0]
SHELL = TEXT.replace(EMBEDDED_PYTHON, '')
CODE = '\n'.join(line for line in SHELL.splitlines() if not line.lstrip().startswith('#'))


def test_refuses_unsupplied_variables():
    for name in REQUIRED_VARIABLES:
        assert f"'{name}'" in CODE.split('foreach ($required in', 1)[1].split(')', 1)[0]
    assert "$value -like 'HOST_*'" in CODE and "$CycleIndex = '00'" in CODE


def test_reads_only_no_path_literal_no_credential():
    assert not re.search(r"['\"][A-Za-z]:[\\/]", CODE), 'a host path literal travels in the script'
    for forbidden in ('Get-SSMParameter', 'ssm get-parameter', 'SecretString', 'Remove-Item', 'Move-Item',
                      'Rename-Item', 'Out-File', 'New-Item'):
        assert forbidden not in CODE, forbidden
    writes = [line for line in CODE.splitlines() if 'Set-Content' in line]
    assert writes == ['Set-Content -Path $probe -Value $code -Encoding ASCII']
    assert "$probe = Join-Path $env:TEMP 'frankie_binding_diff.py'" in CODE
    assert "sqlite3.connect((run/'cycles.sqlite').as_uri()+'?mode=ro', uri=True)" in EMBEDDED_PYTHON
    for forbidden in ('INSERT', 'UPDATE', 'DELETE', 'write_bytes', 'write_text', 'unlink', 'rename'):
        assert forbidden not in EMBEDDED_PYTHON, forbidden


def test_embedded_python_parses_and_reads_the_configuration_with_the_bom():
    ast.parse(EMBEDDED_PYTHON)
    assert "read_text(encoding='utf-8-sig')" in EMBEDDED_PYTHON
    assert "print('differences saved -> rebuilt:')" in EMBEDDED_PYTHON and "DIFF {path}" in EMBEDDED_PYTHON
    assert '& $Python $probe $cfg.run_directory $requestId $CycleIndex $cfgPath' in CODE
    assert '$env:PYTHONPATH = $ToolsRoot' in CODE


def test_workflow_passes_every_variable_by_set():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert set(inputs) == {'instance', 'day', 'run_root', 'tools_root', 'python', 'cycle_index'}
    run = workflow['jobs']['diff']['steps'][-1]['run']
    assert '--script deploy/aws/host/frankie_host_binding_diff.ps1' in run
    for name, env in (('Day', 'DAY'), ('RunRoot', 'RUN_ROOT'), ('ToolsRoot', 'TOOLS_ROOT'), ('Python', 'HOST_PYTHON'),
                      ('CycleIndex', 'CYCLE_INDEX')):
        assert f'--set "{name}=${env}"' in run, name
    assert workflow['permissions'] == {'contents': 'read'}
