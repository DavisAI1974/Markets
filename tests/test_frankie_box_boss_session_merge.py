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
    kept = session.Session._merge_keep(s, 'merge-0-0000', [f'n1 {H1}', f'n2 {H2}'], dict(text=f'n2 {H2}\nn1 {H1}', incomplete=False))
    assert kept == f'n2 {H2}\nn1 {H1}'
    assert (tmp_path / 'merges' / 'merge-0-0000.md').read_text().startswith('## merge-0-0000\n\nn2 ')
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

def test_retained_fourth_part_survives_original_failed_merge_chain(tmp_path):
    """Replay retained text through current guard; no provider call or new market calculation."""
    import hashlib
    import json
    root=Path(__file__).resolve().parents[1]/'research/kalshi/frankie_boss/records/chat6_scratchpad_20260921/cycle-00-docs/docs-cycle-00'
    index=json.loads((root/'docs-index.json').read_bytes())
    pins={row['name']:row for row in index['docs']}
    def read(name):
        raw=(root/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==pins[name]['sha256']
        assert len(raw)==pins[name]['bytes']
        return raw.decode()
    def outcome(name):
        text=read(name)
        # The archival extractor's Markdown title is not provider-generated output.
        assert text.startswith('## '+name[:-3]+' (extracted from ')
        return dict(text=text.split('\n\n',1)[1],incomplete=False)
    fourth=read('reading-note-0003.md');assert 'part 4/4 (bytes 527078-532065)' in fourth
    s=stub(tmp_path)
    kept=session.Session._merge_keep(s,'retained-level0',[fourth],outcome('merge-0-0001.md'))
    assert fourth in kept
    kept=session.Session._merge_keep(s,'retained-level1',[kept],outcome('merge-1-0001.md'))
    assert fourth in kept
    kept=session.Session._merge_keep(s,'retained-final',[read('merge-1-0000.md'),kept],outcome('merge-2-final.md'))
    assert fourth in kept
    assert (tmp_path/'merges/retained-final.model-output.md').is_file()
    assert all((tmp_path/f'merges/retained-{stage}.model-output.md').is_file() for stage in ('level0','level1','final'))

@pytest.mark.parametrize('output',[
    '## Notes on part 1/4\nsource '+H1,
    '## Notes on part 1/4\nsource '+H1+'\n## Notes on part 4/4',
    '## Notes on part 1/4\nsource '+H1+'\n## Notes on part 4/4\nAll four parts are preserved.'])
def test_quiet_hash_free_part_loss_retains_inputs(tmp_path,output):
    s=stub(tmp_path)
    inputs=['## Notes on part 1/4\nsource '+H1,
        '## Notes on part 4/4\n@4 ^3 -45 -45 I-870 ^3\nstructure_families: 24 rows']
    kept=session.Session._merge_keep(s,'quiet-drop',inputs,dict(text=output))
    assert kept.startswith('\n'.join(inputs))
    assert 'MERGE KEPT VERBATIM' in kept
    assert output in (tmp_path/'merges/quiet-drop.model-output.md').read_text()

def test_hash_in_intermediate_group_does_not_mask_lost_hash_free_body(tmp_path):
    s=stub(tmp_path);mixed='prior pinned source '+H1+'\npart four fact without a hash'
    kept=session.Session._merge_keep(s,'mixed-drop',[mixed,'another exact fact'],
        dict(text='prior pinned source '+H1+'\nanother exact fact'))
    assert kept.startswith(mixed+'\nanother exact fact')
    assert 'MERGE KEPT VERBATIM' in kept

def test_verbatim_lines_may_be_reordered_and_deduplicated(tmp_path):
    s=stub(tmp_path);inputs=['fact A\nshared fact','fact B\nshared fact']
    output='fact B\nshared fact\nfact A'
    assert session.Session._merge_keep(s,'covered',inputs,dict(text=output))==output
    assert not (tmp_path/'merges/covered.model-output.md').exists()

def test_nonshrinking_guarded_merge_stops_without_discarding_notes(tmp_path,monkeypatch):
    s=stub(tmp_path);calls=[]
    monkeypatch.setattr(session,'CHUNK_BYTES',4100)
    inputs=['A'*80,'B'*80]
    def reader(name,text):
        calls.append(name);return dict(text='I cannot complete this request.')
    s.reader=reader;s._merge_prompt=lambda joined,label:joined
    s._merge_keep=session.Session._merge_keep.__get__(s)
    s._fan_out=lambda label,items,work:[work(item) for item in items]
    s._merge=lambda *args:pytest.fail('a nonshrinking merge must not recurse')
    kept=session.Session._merge(s,inputs,0)
    assert all(note in kept for note in inputs) and len(calls)==2
    assert 'MERGE KEPT VERBATIM' in kept

def merge_stub(tmp_path,monkeypatch,*,budget,transform,max_calls):
    s=stub(tmp_path);calls=[]
    monkeypatch.setattr(session,'CHUNK_BYTES',4000+budget)
    s._merge_prompt=lambda joined,label:joined
    s._fan_out=lambda label,items,fn:[fn(item) for item in items]
    s._merge_keep=lambda name,inputs,outcome:session.Session._merge_keep(s,name,inputs,outcome)
    s._merge=lambda notes,level:session.Session._merge(s,notes,level)
    def reader(name,prompt):
        calls.append(name)
        if len(calls)>max_calls:pytest.fail('merge recurred without progress')
        return dict(text=transform(prompt))
    s.reader=reader
    return s,calls

@pytest.mark.parametrize('mode',['unchanged','expanded','lossy'])
def test_no_progress_merge_stops_after_first_group_pass(tmp_path,monkeypatch,mode):
    def transform(text):
        if mode=='unchanged':return text
        if mode=='expanded':return text+'\nExtra commentary.'
        return 'A pleasant short summary.'
    s,calls=merge_stub(tmp_path,monkeypatch,budget=12,transform=transform,max_calls=2)
    inputs=['alpha fact','bravo fact'];kept=session.Session._merge(s,inputs,0)
    assert all(line in kept.splitlines() for line in inputs) and len(calls)==2
    if mode=='lossy':
        assert 'MERGE KEPT VERBATIM' in kept
        assert len(list((tmp_path/'merges').glob('*.model-output.md')))==2

def test_depth_limit_preserves_oversized_groups_without_provider_call(tmp_path,monkeypatch):
    s,calls=merge_stub(tmp_path,monkeypatch,budget=12,transform=lambda text:text,max_calls=0)
    inputs=['alpha fact','bravo fact']
    assert session.Session._merge(s,inputs,8)=='\n'.join(inputs) and calls==[]

def test_real_size_reduction_can_finish_with_verbatim_deduplication(tmp_path,monkeypatch):
    s,calls=merge_stub(tmp_path,monkeypatch,budget=32,
        transform=lambda text:'\n'.join(sorted(set(text.splitlines()))),max_calls=3)
    inputs=['a\nshared\nshared']*3
    assert session.Session._merge(s,inputs,0)=='a\nshared' and len(calls)==3
    assert not list((tmp_path/'merges').glob('*.model-output.md'))
