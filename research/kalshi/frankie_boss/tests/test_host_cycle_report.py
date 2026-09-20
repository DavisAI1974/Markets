"""The read-only cycle-report host script, checked as text (there is no PowerShell here).

Built on 2026-09-20 to answer "how did the cycle run and what did Frankie find". Greg, 20:35Z: no
limit, let him say as much as he needs to. So the contract is: every section is printed WHOLE (no
slice, no budget, no short()), the whole report is teed to a file under the day's run directory
(created with 'x', never written over), the file rides a presigned PUT the workflow signs and masks
(the URL is never printed on either side), the SSM sender is told --tail 0, and the workflow
downloads the file and prints it entire. Otherwise the script reads only: variables refused when
absent, no path literal, no credential, the cycle stores opened read-only, nothing deleted or moved.
"""
import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_cycle_report.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_cycle_report.yml'
SENDER = ROOT / 'deploy/aws/ssm_run_ps1.py'
REQUIRED_VARIABLES = ('Day', 'RunRoot', 'ToolsRoot', 'Python')
TEXT = SCRIPT.read_text()
EMBEDDED_PYTHON = TEXT.split("$code = @'\n", 1)[1].split("\n'@", 1)[0]
SHELL = TEXT.replace(EMBEDDED_PYTHON, '')
CODE = '\n'.join(line for line in SHELL.splitlines() if not line.lstrip().startswith('#'))
PYTHON_CODE = '\n'.join(line for line in EMBEDDED_PYTHON.splitlines() if not line.lstrip().startswith('#'))


def test_refuses_unsupplied_variables_and_defaults_the_optional_ones():
    for name in REQUIRED_VARIABLES:
        assert f"'{name}'" in CODE.split('foreach ($required in', 1)[1].split(')', 1)[0]
    assert "$value -like 'HOST_*'" in CODE and "$CycleIndex = '00'" in CODE and "$Url = ''" in CODE


def test_reads_only_no_path_literal_no_credential_nothing_moved():
    assert not re.search(r"['\"][A-Za-z]:[\\/]", CODE), 'a host path literal travels in the script'
    for forbidden in ('Get-SSMParameter', 'ssm get-parameter', 'SecretString', 'Remove-Item', 'Move-Item',
                      'Rename-Item', 'Out-File', 'New-Item'):
        assert forbidden not in CODE, forbidden
    writes = [line for line in CODE.splitlines() if 'Set-Content' in line]
    assert writes == ['Set-Content -Path $probe -Value $code -Encoding ASCII']
    assert "sqlite3.connect(Path(db_path).as_uri()+'?mode=ro', uri=True)" in PYTHON_CODE
    assert "sqlite3.connect(lessons.as_uri()+'?mode=ro', uri=True)" in PYTHON_CODE
    for forbidden in ('INSERT', 'UPDATE', 'DELETE', 'write_bytes', 'write_text', 'unlink', 'rename', 'shutil'):
        assert forbidden not in PYTHON_CODE, forbidden


def test_the_only_file_written_is_the_report_and_it_is_never_written_over():
    # the report file is created exclusively ('x'): an existing file refuses rather than being replaced
    opens = [line for line in PYTHON_CODE.splitlines() if '.open(' in line]
    assert opens == ["report_handle = report_path.open('x', encoding='utf-8', newline='\\n')"]
    assert "if report_path.exists(): raise SystemExit(" in PYTHON_CODE
    assert "report_path = Path(sys.argv[4])" in PYTHON_CODE and 'sys.stdout = Tee(sys.stdout, report_handle)' in PYTHON_CODE
    assert "$report = Join-Path (Join-Path $dayDirectory 'reports')" in CODE
    assert '& $Python $probe $cfg.run_directory $CycleIndex $cfg.run_id $report' in CODE
    assert 'REPORT_FILE ' in CODE and 'Get-FileHash -Path $report -Algorithm SHA256' in CODE


def test_no_display_cut_anywhere():
    # Greg: no limit. No slice of a printed value, no budget, no short() helper, no "first N chars".
    assert 'def short' not in PYTHON_CODE and 'budget' not in PYTHON_CODE
    assert not re.search(r"\[:\d+\]", PYTHON_CODE), 'a printed value is sliced'
    assert not re.search(r"\)\[:\d+\]", PYTHON_CODE)
    assert "first 6000 chars" not in PYTHON_CODE and "output budget" not in PYTHON_CODE
    assert "print(text)" in PYTHON_CODE  # the critique and every lesson, whole
    assert "for rec in records:" in PYTHON_CODE and "for s in fb.get('sessions', ()):" in PYTHON_CODE


def test_upload_is_optional_and_the_url_is_never_printed():
    assert 'Invoke-WebRequest -Uri $Url -Method Put -InFile $report' in CODE
    assert 'REPORT_UPLOADED' in CODE and 'REPORT_NOT_UPLOADED' in CODE and 'REPORT_UPLOAD_REFUSED' in CODE
    assert "-replace '<RequestId>.*?</RequestId>', ''" in CODE  # the refusal is named without its ids
    for line in CODE.splitlines():
        if 'Write-Output' in line or 'Write-Host' in line or 'throw' in line:
            assert '$Url' not in line, 'the presigned URL would be printed'
    assert '$Url' not in EMBEDDED_PYTHON


def test_embedded_python_parses_and_the_sender_prints_everything_by_default():
    ast.parse(EMBEDDED_PYTHON)
    assert '$env:PYTHONPATH = $ToolsRoot' in CODE and "$env:PYTHONIOENCODING = 'utf-8'" in CODE
    sender = SENDER.read_text()
    assert "parser.add_argument('--tail', type=int, default=0," in sender
    assert "print(output[-args.tail:] if args.tail > 0 else output)" in sender


def test_workflow_passes_every_variable_by_set_signs_a_masked_put_and_prints_the_file_entire():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    inputs = workflow[True]['workflow_dispatch']['inputs']
    assert set(inputs) == {'instance', 'day', 'run_root', 'tools_root', 'python', 'cycle_index', 'bucket'}
    steps = workflow['jobs']['report']['steps']
    sign = next(s for s in steps if s.get('id') == 'sign')['run']
    assert "'put_object'" in sign and "print('::add-mask::' + url)" in sign and 'ExpiresIn=3600' in sign
    assert "region_name='us-east-1'" in sign and inputs['bucket']['default'] == 'frankie-granite42-568968024170-us-east-1'
    ssm = next(s for s in steps if 'python deploy/aws/ssm_run_ps1.py' in s.get('run', ''))['run']
    assert '--script deploy/aws/host/frankie_host_cycle_report.ps1' in ssm and '--tail 0' in ssm
    for name, env in (('Day', 'DAY'), ('RunRoot', 'RUN_ROOT'), ('ToolsRoot', 'TOOLS_ROOT'), ('Python', 'HOST_PYTHON'),
                      ('CycleIndex', 'CYCLE_INDEX')):
        assert f'--set "{name}=${env}"' in ssm
    assert '--set "Url=$(cat "$RUNNER_TEMP/presigned-put.txt")"' in ssm
    assert 'echo' not in ssm.replace('--comment', '')  # the URL never reaches the log
    download = next(s for s in steps if 'get_object' in s.get('run', ''))['run']
    assert "print(body.decode('utf-8', 'replace'))" in download and 'hashlib.sha256(body).hexdigest()' in download
    artifact = next(s for s in steps if 'upload-artifact' in s.get('uses', ''))
    assert artifact['with']['if-no-files-found'] == 'error'
    assert workflow['permissions'] == {'contents': 'read'}
