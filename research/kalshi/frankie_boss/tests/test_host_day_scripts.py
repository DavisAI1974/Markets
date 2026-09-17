"""The host scripts the day pipeline sends, checked as text.

There is no PowerShell in the test container and the host is under HOLD, so these scripts are
never executed here. What can be checked without running them is the contract day_pipeline.py
depends on: the variables the sender prepends, the single receipt line, the gate field names in
it, and that no path or credential is baked into a file that is sent verbatim to a live host.
"""
import json
import re
import sys
from pathlib import Path

import pytest

from research.kalshi.frankie_boss.operations import day_pipeline as dp

ROOT = Path(__file__).resolve().parents[4]
CONFIGURATION = json.loads((ROOT / 'research/kalshi/frankie_boss/operations/day_pipeline.configuration.json').read_bytes())
STAGE_OF = {'schedule_prefixes': 'schedule-prefixes', 'cycles': 'cycles'}
REQUIRED_VARIABLES = ('Day', 'ToolsRoot', 'Python', 'RunRoot')
SENT = [(key, ROOT / path) for key, path in CONFIGURATION['host_scripts'].items() if path]


def test_every_declared_host_script_is_present_and_ingest_is_deliberately_absent():
    assert [key for key, _ in SENT] == ['schedule_prefixes', 'cycles']
    assert CONFIGURATION['host_scripts']['ingest'] is None
    # Greg, 2026-09-17: ingestion stays the journal-stack job already on git. A future session that
    # wants a host ingest script has to change this test and say why.
    assert 'journal-stack job already on git' in CONFIGURATION['_host_scripts']
    for _, path in SENT:
        assert path.is_file(), path


@pytest.mark.parametrize('key', [key for key, _ in SENT])
def test_the_script_refuses_a_variable_the_sender_did_not_supply(key):
    text = dict(SENT)[key].read_text()
    for name in REQUIRED_VARIABLES:
        assert f"'{name}'" in text, f'{key} never names {name}'
    assert "-like 'HOST_*'" in text        # an unfilled placeholder is refused, never used as a path
    assert 'throw' in text


@pytest.mark.parametrize('key', [key for key, _ in SENT])
def test_one_receipt_line_last_carrying_exactly_its_stage_gate_fields(key):
    lines = [line for line in dict(SENT)[key].read_text().splitlines() if line.strip()]
    emitting = [line for line in lines if dp.MARKER in line]
    assert len(emitting) == 1 and emitting[0] is lines[-1]
    body = '\n'.join(lines)
    receipt = body.split('$receipt = [ordered]@{', 1)[1].split('}', 1)[0]
    declared = set(re.findall(r'^\s*([a-z0-9_]+)\s*=', receipt, re.M))
    assert set(dp.GATES[STAGE_OF[key]]) <= declared, (key, declared)


@pytest.mark.parametrize('key', [key for key, _ in SENT])
def test_no_path_literal_and_no_credential_travels_in_a_verbatim_script(key):
    text = dict(SENT)[key].read_text()
    assert not re.search(r'[A-Za-z]:\\', text), 'a drive-letter path is baked into a sent script (D34)'
    for word in ('secret', 'api_key', 'password', 'AWS_ACCESS', 'bearer '):
        assert word.lower() not in text.lower()


def test_the_sender_renders_the_variables_these_scripts_require():
    sys.path.insert(0, str(ROOT / 'deploy/aws'))
    import ssm_run_ps1

    variables = dict(CONFIGURATION['host_variables'], Day='20211004')
    rendered = ssm_run_ps1.preamble([f'{name}={value}' for name, value in variables.items()])
    for name in REQUIRED_VARIABLES:
        assert f'${name} = ' in rendered
    assert rendered.count('\n') == len(variables)
    with pytest.raises(SystemExit):                     # no quoting logic: a quote is refused
        ssm_run_ps1.preamble(["RunRoot=D:\\it's"])
