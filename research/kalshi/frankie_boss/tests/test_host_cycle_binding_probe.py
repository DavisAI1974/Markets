"""The read-only cycles-binding probe, checked as text (there is no PowerShell here).

The probe is sent verbatim to the live native host under HOLD, so what matters is the contract it
promises and cannot be allowed to drift: it names the variables the sender prepends, it carries no
path literal and no credential, it never calls anything in run_actual_sunday.py that writes
(retained_instance_id mints an instance id; retained_ready_signal writes a witness; save routes to
sunday_execution._save), its only file writes are its own scratch files under TEMP, the workflow
supplies exactly the variables it requires, and its embedded Python compiles. The c15 shape test
pins the fact that broke the probe's first run: a .c15.json is a pack() payload, a tagged list.
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_cycle_binding_probe.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_cycle_binding_probe.yml'
REQUIRED_VARIABLES = ('Day', 'RunRoot', 'ToolsRoot', 'Python')
TEXT = SCRIPT.read_text()
HERE_STRING = TEXT.split('$probe = @"\n', 1)[1].split('\n"@', 1)[0]
OUTSIDE = TEXT.replace(HERE_STRING, '')


def _c15_journal():
    # The package __init__ imports torch. c15_journal and causal_packet are stdlib only and
    # c15_journal already falls back to a flat import, so use that path rather than the package.
    sys.path.insert(0, str(ROOT / 'research/kalshi/frankie_boss'))
    return importlib.import_module('c15_journal')


def test_the_script_refuses_a_variable_the_sender_did_not_supply():
    for name in REQUIRED_VARIABLES:
        assert f"'{name}'" in TEXT, f'probe never names {name}'
    assert "-like 'HOST_*'" in TEXT
    assert 'throw' in TEXT


def test_no_path_literal_and_no_credential_travels_in_the_sent_script():
    assert not re.search(r'[A-Za-z]:[\\/]', TEXT), 'a drive-letter path is baked into a sent script'
    for word in ('secret', 'api_key', 'password', 'AWS_ACCESS', 'bearer '):
        assert word.lower() not in TEXT.lower()


def test_the_probe_never_reaches_a_writer_in_run_actual_sunday():
    for writer in ('retained_instance_id(', 'retained_ready_signal(', 'read_execution_trigger(',
                   '_save(', '.save(', 'ActualHost('):
        assert writer not in HERE_STRING, f'probe calls {writer}; that writes or mints on the host'
    assert 'unpack(' in HERE_STRING, 'c15 payloads must be read through unpack'


def test_the_only_file_writes_are_its_own_scratch_files_under_temp():
    for verb in ('Out-File', 'New-Item', 'Add-Content', 'Copy-Item', 'Move-Item', 'Rename-Item'):
        assert verb not in OUTSIDE, f'{verb} writes outside TEMP'
    writes = [line for line in OUTSIDE.splitlines() if 'Set-Content' in line]
    assert writes, 'the probe stages its Python through Set-Content'
    for line in writes:
        assert '-Path $tmp' in line, line
    assert re.search(r"^\$tmp = Join-Path \$env:TEMP '", OUTSIDE, re.M)
    assert re.search(r"^\$out = Join-Path \$env:TEMP '", OUTSIDE, re.M)
    assert 'Remove-Item $tmp, $out' in OUTSIDE
    # The Python side writes only to the file PowerShell handed it.
    opens = re.findall(r"open\(([^)]*)\)", HERE_STRING)
    assert opens == ["r'$out', 'a', encoding='ascii', errors='replace'"], opens


def test_the_embedded_python_compiles_once_powershell_interpolates_its_variables():
    rendered = (HERE_STRING.replace('$out', '/scratch/probe.out').replace('$cfgPath', '/day/config.json')
                .replace('$ToolsRoot', '/tools').replace('$CycleIndex', '00'))
    assert '$' not in rendered, [line for line in rendered.splitlines() if '$' in line]
    compile(rendered, str(SCRIPT), 'exec')


def test_the_workflow_supplies_exactly_the_variables_the_script_requires():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    steps = workflow['jobs']['probe']['steps']
    run = next(step['run'] for step in steps if 'frankie_host_cycle_binding_probe.ps1' in step.get('run', ''))
    supplied = set(re.findall(r'--set "([A-Za-z]+)=', run))
    assert set(REQUIRED_VARIABLES) <= supplied, supplied
    assert supplied == set(REQUIRED_VARIABLES) | {'CycleIndex'}
    assert workflow['permissions'] == {'contents': 'read'}
    assert workflow[True] == {'workflow_dispatch': {'inputs': workflow[True]['workflow_dispatch']['inputs']}}


def test_a_c15_json_is_a_tagged_list_not_an_object():
    journal = _c15_journal()
    record = dict(schema='FRANKIE_ACTUAL_HOST_INSTANCE_V1', run_id='r', instance_id='0' * 32)
    packed = journal.pack(record)
    assert isinstance(packed, list) and packed[0] == 'dict'
    with pytest.raises(TypeError):
        packed['instance_id']
    assert journal.unpack(packed) == record
    raw = journal.canonical_bytes(packed)
    assert journal.canonical_bytes(journal.pack(journal.unpack(packed))) == raw
    assert journal.canonical_bytes(journal.pack(dict(record, run_id='other'))) != raw
