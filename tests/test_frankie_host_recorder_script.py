"""The recorder fix and its delivery: stage_admission_inputs copies the admission inputs into the candidate, and the
host script carries the recorder source verbatim (the host tools checkout is not moved mid-run)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORDER = ROOT / 'research' / 'kalshi' / 'frankie_boss' / 'operations' / 'record_actual_frankie_response.py'
SCRIPT = ROOT / 'deploy' / 'aws' / 'host' / 'frankie_host_record_principal_response.ps1'


def load_recorder():
    spec = importlib.util.spec_from_file_location('record_actual_frankie_response_under_test', RECORDER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_candidate_answers_the_admission_record_with_the_principal_directory_and_everything_else_with_its_own(tmp_path):
    m = load_recorder()

    class Adapter:
        def __init__(self, directory):
            self.directory = Path(directory)

        def _admission_record(self):
            return dict(sealed_absence=dict(path=str((self.directory / 'sealed-proof.json').resolve())))

        def where(self):
            return str(self.directory)
    principal = tmp_path / 'principal'
    principal.mkdir()
    real = Adapter(principal)
    cand = m.candidate_of(real, principal / 'response-check-x')
    assert cand.directory == principal / 'response-check-x' and cand.where() == str(principal / 'response-check-x')
    assert cand._admission_record() == real._admission_record()               # the principal's record, its own path
    assert real.directory == principal and not hasattr(Adapter, 'x')          # the real adapter untouched


def test_live_classroom_puts_the_live_block_in_the_attachment_only_when_json_equal():
    import json
    m = load_recorder()
    json_form = lambda v: json.loads(json.dumps(v))
    live = {'binding': {'mode': 'TEACH', 'pairs': ('a', 'b')}, 'model_visible_hash': 'h' * 64}
    request = {'attachment': {'dipole_classroom': json_form(live)}}
    assert m.live_classroom(request, {'pkg': 1}, lambda pkg: live, json_form) == 'live'
    assert request['attachment']['dipole_classroom'] is live                       # the live object, tuples and all
    other = {'attachment': {'dipole_classroom': {'binding': {'mode': 'OTHER'}}}}
    assert m.live_classroom(other, {}, lambda pkg: live, json_form) == 'unchanged' and other['attachment']['dipole_classroom'] == {'binding': {'mode': 'OTHER'}}
    assert m.live_classroom({'attachment': {}}, {}, lambda pkg: live, json_form) == 'unchanged'


def test_the_host_script_carries_the_recorder_source_verbatim():
    text = SCRIPT.read_text(encoding='utf-8')
    start = text.index("$recorderSource = @'\n") + len("$recorderSource = @'\n")
    end = text.index("'@\n$shippedTool", start)
    assert text[start:end] == RECORDER.read_text(encoding='utf-8')
    assert "'@" not in RECORDER.read_text(encoding='utf-8')       # a here-string terminator inside the source would truncate it


def test_the_recorder_refusal_carries_its_message():
    assert "error=str(error)[:800]" in RECORDER.read_text(encoding='utf-8')
