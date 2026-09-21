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


def test_stage_admission_inputs_copies_prompt_proof_and_witness_when_present(tmp_path):
    m = load_recorder()
    src, cand = tmp_path / 'principal', tmp_path / 'candidate'
    src.mkdir(); cand.mkdir()
    (src / 'prompt.md').write_bytes(b'# composed prompt\n')
    (src / 'sealed-proof.json').write_bytes(b'{"schema": "FRANKIE_SEALED_ABSENCE_PROOF_V1"}')
    (src / 'session-request.json').write_bytes(b'{}')
    (src / 'memory-a-witness.json').write_bytes(b'{"schema": "FRANKIE_BOSS_MEMORY_A_WITNESS_V1"}')
    staged = m.stage_admission_inputs(src, cand)
    assert staged == {'prompt.md': 'linked', 'sealed-proof.json': 'linked', 'memory-a-witness.json': 'copied'}
    assert (cand / 'prompt.md').is_symlink() and (cand / 'prompt.md').resolve() == (src / 'prompt.md').resolve()
    assert (cand / 'sealed-proof.json').resolve() == (src / 'sealed-proof.json').resolve()     # the admission record's path is the principal's
    assert (cand / 'prompt.md').read_bytes() == b'# composed prompt\n' and not (cand / 'memory-a-witness.json').is_symlink()
    assert not (cand / 'session-request.json').exists()
    assert m.stage_admission_inputs(tmp_path / 'empty', cand / 'other') == {} if (cand / 'other').mkdir() is None else False


def test_the_host_script_carries_the_recorder_source_verbatim():
    text = SCRIPT.read_text(encoding='utf-8')
    start = text.index("$recorderSource = @'\n") + len("$recorderSource = @'\n")
    end = text.index("'@\n$shippedTool", start)
    assert text[start:end] == RECORDER.read_text(encoding='utf-8')
    assert "'@" not in RECORDER.read_text(encoding='utf-8')       # a here-string terminator inside the source would truncate it


def test_the_recorder_refusal_carries_its_message():
    assert "error=str(error)[:800]" in RECORDER.read_text(encoding='utf-8')
