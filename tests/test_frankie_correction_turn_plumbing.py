"""The correction turn's plumbing (2026-09-21, the Dipole classroom exchange, spec SPEC_CLASSROOM_EXCHANGE_20260921.md):
the export workflow and host script export the retained correction request, the box session fetches and answers it,
the pusher and the fetch workflow deliver the three correction files, the record workflow records them. Shape checks
on the committed scripts and workflows (syntax, the turn routes, the file names), not a run."""
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / '.github' / 'workflows'
CORRECTION_FILES = ('correction-response.json', 'host-correction-record.json', 'host-correction-attestation.json')


def test_shell_scripts_parse_and_route_the_turn():
    for name in ('frankie_box_push_response.sh', 'frankie_box_session.sh'):
        subprocess.run(['bash', '-n', str(ROOT / 'deploy' / 'aws' / 'box' / name)], check=True)
    push = (ROOT / 'deploy/aws/box/frankie_box_push_response.sh').read_text()
    assert 'TURN="${TURN:-initial}"' in push and all(f in push for f in CORRECTION_FILES)
    assert 'classroom-correction-request.json' in push and 'adapter digest of the whole correction request' in push
    session = (ROOT / 'deploy/aws/box/frankie_box_session.sh').read_text()
    assert 'fetch_correction) fetch_correction ;;' in session and 'correction) correction ;;' in session
    assert '--stage correction' in session and 'frankie-correction-$CYCLE' in session and 'not overwritten' in session


def test_workflows_load_and_carry_the_turn_input():
    for name in ('frankie_box_fetch_response.yml', 'frankie_host_export_principal_request.yml', 'frankie_host_record_principal_response.yml'):
        doc = yaml.safe_load((WF / name).read_text())
        turn = doc[True]['workflow_dispatch']['inputs']['turn']            # yaml reads the `on` key as True
        assert turn['options'] == ['initial', 'correction'] and turn['default'] == 'initial'
    fetch = (WF / 'frankie_box_fetch_response.yml').read_text()
    assert '--set "TURN=$TURN"' in fetch and all(f in fetch for f in CORRECTION_FILES) and "'/correction'" in fetch
    assert 'dipole_teachback' in fetch and '171' in fetch
    export = (WF / 'frankie_host_export_principal_request.yml').read_text()
    assert '--set "Turn=$TURN"' in export and "('classroom-correction-request.json',)" in export
    record = (WF / 'frankie_host_record_principal_response.yml').read_text()
    assert '--set "Turn=$TURN"' in record


def test_export_host_script_exports_the_correction_request_alone_on_the_correction_turn():
    text = (ROOT / 'deploy/aws/host/frankie_host_export_principal_request.ps1').read_text()
    assert "$files['classroom-correction-request.json'] = $RequestUrl" in text
    assert "@('Day', 'RunRoot', 'CycleIndex', 'RequestUrl') }" in text and "turn        = $Turn" in text


def test_the_correction_unit_waits_for_a_running_cycle_session():
    text = (ROOT / 'deploy' / 'aws' / 'box' / 'frankie_box_session.sh').read_text()
    assert 'if systemctl is-active --quiet "frankie-session-$CYCLE.service"; then echo "frankie-session-$CYCLE is running: the correction waits' in text
    assert 'trap' in text and "doc.get('original_request_sha256') != answered" in text


def test_the_fetch_workflow_hex_validates_the_sha_it_exports():
    text = (ROOT / '.github' / 'workflows' / 'frankie_box_fetch_response.yml').read_text()
    assert text.count("re.fullmatch(r'[0-9a-f]{64}', str(r['request_sha256']))") == 2
    assert text.count("out.write(f\"request_sha256={r['request_sha256']}\\n\")") == 2


def test_the_push_receipt_files_are_a_json_array():
    text = (ROOT / 'deploy' / 'aws' / 'box' / 'frankie_box_push_response.sh').read_text()
    assert '"files":%s}' in text and 'files_json=$(printf' in text
