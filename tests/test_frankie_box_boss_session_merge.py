"""The session's merge guard as wired (frankie_box_boss_session._merge_keep): every merge output is kept as Markdown
under work/merges, and an output that loses a hash is replaced by the inputs verbatim (cycle-0 finding, chat 6)."""
import importlib.util
import types
from pathlib import Path

SESSION = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_boss_session.py'
spec = importlib.util.spec_from_file_location('frankie_box_boss_session_under_test', SESSION)
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)

H1, H2 = 'a' * 64, 'b' * 64


def stub(tmp_path):
    notes = []
    return types.SimpleNamespace(work=tmp_path, note=notes.append, _notes=notes)


def test_merge_keep_uses_a_complete_merge_and_writes_it_as_markdown(tmp_path):
    s = stub(tmp_path)
    kept = session.Session._merge_keep(s, 'merge-0-0000', [f'n1 {H1}', f'n2 {H2}'], dict(text=f'merged {H1} {H2}', incomplete=False))
    assert kept == f'merged {H1} {H2}'
    assert (tmp_path / 'merges' / 'merge-0-0000.md').read_text().startswith('## merge-0-0000\n\nmerged ')
    assert not (tmp_path / 'merges' / 'merge-0-0000.model-output.md').exists() and s._notes == []


def test_merge_keep_replaces_a_lossy_merge_with_the_inputs_and_keeps_the_model_output_beside_it(tmp_path):
    s = stub(tmp_path)
    inputs = [f'group A {H1}', f'I cannot complete this request {H2}']
    kept = session.Session._merge_keep(s, 'merge-1-final', inputs, dict(text=f'I will merge only the first group: {H1}', incomplete=True))
    assert kept.startswith('\n'.join(inputs)) and 'MERGE KEPT VERBATIM' in kept and H2 in kept
    model = (tmp_path / 'merges' / 'merge-1-final.model-output.md').read_text()
    assert 'NOT used' in model and '[OUTPUT INCOMPLETE]' in model
    assert s._notes == ['merge-1-final: the merge output lost 1 of 2 sha256 values; inputs kept verbatim']


def test_json_entry_rescues_a_messy_ledger_and_keeps_raw_text_when_hopeless():
    e = session.Session._json_entry(dict(text='```json\n{"status": "derived", "rows": [1,],}\n```', incomplete=False), 'output_x')
    assert e['status'] == 'derived' and e['rows'] == [1] and e['ledger'] == 'output_x'
    assert e['parse_repairs'] == ['fences stripped', 'comments and trailing commas removed']
    e = session.Session._json_entry(dict(text='{"status": "derived"}', incomplete=False), 'output_y')
    assert 'parse_repairs' not in e
    e = session.Session._json_entry(dict(text='nothing usable', incomplete=False), 'output_z')
    assert e['status'] == 'could_not' and e['boss_text'] == 'nothing usable' and 'raw text retained' in e['reason']


import pytest

@pytest.mark.parametrize('outcome', [dict(text='I cannot complete this request.'),
    dict(text='I+1 ' * 500, incomplete=True), dict(text='provider failure', error='transport'),
    dict(text='intro\n' + 'I+1\n' * 100)])
def test_unusable_hash_free_merge_keeps_all_input_notes(tmp_path, outcome):
    s = stub(tmp_path)
    inputs = ['price moved 5.544 to 5.634', 'part four structure facts']
    kept = session.Session._merge_keep(s, 'merge-safe', inputs, outcome)
    assert kept.startswith('\n'.join(inputs)) and 'MERGE KEPT VERBATIM' in kept
    assert outcome['text'] in (tmp_path / 'merges' / 'merge-safe.model-output.md').read_text()



def test_repeated_merge_name_preserves_both_previous_artifacts(tmp_path):
    import json
    s = stub(tmp_path)
    inputs = ['first input group', 'second input group']
    session.Session._merge_keep(s, 'repeat', inputs, dict(text='I cannot complete this request.'))
    old = {p.name: p.read_bytes() for p in (tmp_path / 'merges').iterdir()}
    session.Session._merge_keep(s, 'repeat', inputs, dict(text='new usable merge'))
    receipts = list(tmp_path.glob('superseded-reading-*/move-receipt.json'))
    assert receipts
    for name, raw in old.items():
        assert any((p.parent / name).read_bytes() == raw for p in receipts if (p.parent / name).exists())
    assert all(json.loads(p.read_text())['moves'] for p in receipts)
