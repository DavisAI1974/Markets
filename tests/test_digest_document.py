"""Whole DIGEST_V6 composition against the immutable pre-streaming renderer."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import pytest
import test_frankie_box_digest_render as FX

BOX = Path(__file__).resolve().parents[1] / 'deploy/aws/box'
sys.path.insert(0, str(BOX))

def document():
    import frankie_box_digest_document
    return frankie_box_digest_document

@pytest.fixture
def reference():
    path = os.environ.get('DIGEST_REFERENCE_PATH')
    assert path, 'CI must provide the immutable renderer reference'
    spec = importlib.util.spec_from_file_location('digest_reference', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def receipt():
    return dict(rows=dict(path='p', count=8, kinds={'input':4}, head='a'*64,
                          head_is_request_source_hash=True),
                input_records=4, legacy_rows=4, f_last_groups=4, failure_count=0,
                pin_group='test', layers={})

class Once:
    def __init__(self, rows):
        self.rows, self.used = rows, False
    def __iter__(self):
        assert not self.used, 'one-pass input was replayed'
        self.used = True
        yield from self.rows

def pinned_layers(root, files):
    root.mkdir()
    out, normalized = {}, {}
    for i, (name, value) in enumerate(files.items()):
        path = root / ('layer-%d.json' % i)
        raw = (json.dumps(value, sort_keys=True, default=str) + '\n').encode()
        path.write_bytes(raw)
        out[name] = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        normalized[name] = json.loads(raw)
    return out, normalized

@pytest.mark.parametrize('layers_kind', ['none', 'layers', 'sections'])
def test_complete_document_is_byte_identical_to_pinned_reference(tmp_path, reference, layers_kind):
    mod = document()
    tables = FX._tables()
    frames, structures = tables['legacy_book_imbalance'], tables['legacy_structure_observables']
    prices = [dict(ts_recv=1633298400000000001+i, price=5.5+i/100, size=i+1) for i in range(4)]
    buys, sells = [0.0,1.0,2.0,3.0], [0.0,0.0,2.0,1.0]
    roll = [float('nan'),1.0,1.0/5.0,1.0/3.0]
    pins, layers = ({}, None) if layers_kind == 'none' else pinned_layers(
        tmp_path/'inputs', FX._section_files() if layers_kind == 'sections' else FX._bedrock_files())
    expected = reference.digest_text(receipt(), {}, prices, frames, structures, roll, 10, buys, sells, bedrock=layers)
    target = tmp_path/'digest.md'
    proof = mod.write_digest(target, receipt(), {}, Once(prices), Once(frames), Once(structures),
                             roll, 10, buys, sells, bedrock_entries=pins, scratch_directory=tmp_path/'scratch')
    assert target.read_bytes() == expected.encode()
    assert proof['verified'] is True
    assert proof['bytes'] == len(expected.encode())
    assert proof['sha256'] == hashlib.sha256(expected.encode()).hexdigest()

def test_family_ties_and_per_second_float_order_match_reference(tmp_path, reference):
    rows = [dict(action_string=v, i=i) for i,v in enumerate(['B','A','C','A','B','D'])]
    buys = [1e16, 1.0, 1.0, 0.0] * 12
    sells = [0.0, 1.0, 0.0, 0.0] * 12
    cb, cs = [0.0], [0.0]
    for b,s in zip(buys,sells):
        cb.append(cb[-1]+b); cs.append(cs[-1]+s)
    roll = []
    for t in range(len(buys)):
        lo = max(0,t-19)
        b,s = cb[t+1]-cb[lo],cs[t+1]-cs[lo]
        roll.append((b-s)/(b+s) if b+s > 0 else float('nan'))
    expected = reference.digest_text(receipt(), {}, [], [], rows, roll, 0, buys, sells)
    target = tmp_path/'digest.md'
    document().write_digest(target, receipt(), {}, iter([]), iter([]), Once(rows), roll, 0, buys,sells,
                            bedrock_entries={}, scratch_directory=tmp_path/'scratch')
    assert target.read_bytes() == expected.encode()

def test_production_document_forbids_materializing_compatibility_wrappers(tmp_path, monkeypatch):
    mod = document()
    def forbidden(*a,**k): raise AssertionError('materializing compatibility wrapper used')
    for name in ('digest_text','render_layers','bedrock_tables','per_second_rows','render_table','parse_table'):
        monkeypatch.setattr(FX.DG, name, forbidden)
    pins, _ = pinned_layers(tmp_path/'inputs', FX._section_files())
    target=tmp_path/'digest.md'
    mod.write_digest(target, receipt(), {}, iter([]), iter([]), iter([]), [], 0, [], [],
                     bedrock_entries=pins, scratch_directory=tmp_path/'scratch')
    assert target.is_file()

def test_existing_destination_is_preserved(tmp_path):
    target=tmp_path/'digest.md'; target.write_bytes(b'old evidence')
    with pytest.raises(FileExistsError):
        document().write_digest(target, receipt(), {}, [], [], [], [], 0, [], [],
                                bedrock_entries={}, scratch_directory=tmp_path/'scratch')
    assert target.read_bytes() == b'old evidence'

def test_failed_table_proof_publishes_nothing_and_retains_scratch(tmp_path, monkeypatch):
    mod = document()
    def fail(*a,**k): raise ValueError('injected inverse failure')
    monkeypatch.setattr(mod.TS, 'verify_table', fail)
    with pytest.raises(ValueError, match='inverse'):
        mod.write_digest(tmp_path/'digest.md', receipt(), {}, [], [], [], [], 0, [], [],
                         bedrock_entries={}, scratch_directory=tmp_path/'scratch')
    assert not (tmp_path/'digest.md').exists()
    assert list((tmp_path/'scratch').rglob('*'))

def test_changed_verified_block_is_refused_before_publication(tmp_path, monkeypatch):
    mod=document(); original=mod.TS.write_table
    def changed(path,*a,**k):
        proof=original(path,*a,**k)
        with Path(path).open('ab') as handle: handle.write(b'CORRUPTED\n')
        return proof
    monkeypatch.setattr(mod.TS,'write_table',changed)
    with pytest.raises(ValueError):
        mod.write_digest(tmp_path/'digest.md', receipt(), {}, [], [], [], [], 0, [], [],
                         bedrock_entries={}, scratch_directory=tmp_path/'scratch')
    assert not (tmp_path/'digest.md').exists()

def session_module():
    spec=importlib.util.spec_from_file_location('session_stream_test', BOX/'frankie_box_boss_session.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def test_session_digest_path_invokes_file_writer_without_full_layer_load(tmp_path, monkeypatch):
    session=session_module()
    obj=session.Session.__new__(session.Session); obj.work=tmp_path
    def forbidden(*a,**k): raise AssertionError('full layer load')
    monkeypatch.setattr(session,'load_json',forbidden)
    mod=document()
    pins,_=pinned_layers(tmp_path/'inputs',FX._bedrock_files())
    rec=receipt()
    rec['layers']={name:dict(entry,bedrock=True,status='derived',producer='fixture') for name,entry in pins.items()}
    obj._write_digest(rec,{},[],[],[],[],0,[],[])
    assert (tmp_path/'derivation-digest-full.md').exists()
    proof=json.loads((tmp_path/'digest-proof.json').read_bytes())
    assert proof['verified']

def test_session_witness_hashes_without_whole_file_read(tmp_path,monkeypatch):
    session=session_module(); path=tmp_path/'large'
    path.write_bytes(b'abc'*100000)
    expected=hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(Path,'read_bytes',lambda *a,**k: (_ for _ in ()).throw(AssertionError('whole read')))
    assert session.witness(path)==dict(bytes=300000,sha256=expected)
