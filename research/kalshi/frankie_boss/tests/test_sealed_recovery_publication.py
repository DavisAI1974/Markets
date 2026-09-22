"""Publication gates for recovered evidence."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from research.kalshi.frankie_boss import sealed_recovery_run as run

ROOT=Path(__file__).resolve().parents[4]
def boundary():
    return json.loads((ROOT/'research/kalshi/frankie_boss/blocks/MONDAY_SOURCE_BOUNDARY_VERIFIED_20260922.json').read_bytes())
def manifest():
    return json.loads((ROOT/'research/kalshi/frankie_boss/blocks/BLOCK_20211004_SOURCE_MANIFEST.json').read_bytes())
def test_independent_boundary_and_retained_wire_binding():
    b=boundary()
    run.validate_boundary(b,manifest())
    row=dict(b['last_included'],cursor=2032202)
    run.validate_retained(dict(member_boundaries={1:row}),b)
    for field in ('wire_sha256','ts_recv_ns','session_id','is_last','cursor'):
        broken=copy.deepcopy(row)
        broken[field]='wrong'
        with pytest.raises(ValueError):run.validate_retained(dict(member_boundaries={1:broken}),b)

@pytest.mark.parametrize('field,value',[
    ('verified',False),('manifest_hash','0'*64),('source_sha256','0'*64),
    ('take',1975175),('partition_mbo_records',1994357)])
def test_invalid_boundary_refuses(field,value):
    b=boundary()
    b[field]=value
    with pytest.raises(ValueError):run.validate_boundary(b,manifest())

def test_open_or_same_session_boundary_refuses():
    b=boundary()
    b['last_included']['is_last']=False
    with pytest.raises(ValueError):run.validate_boundary(b,manifest())
    b=boundary()
    b['first_excluded']['session_id']='20211004'
    with pytest.raises(ValueError):run.validate_boundary(b,manifest())

def result():
    return dict(state=dict(state_hash='state',implementation={'original':'identity'}),
        completion=dict(record_count=2032203,journal_count=4064406,journal_hash='head',
            group_count=1500000,source_prefix_hash='prefix'),
        completion_digest='completion',container={'path':run.PARENT,'sha256':run.PARENT_SHA},
        sessions=[],member_boundaries={},resources={})

def test_published_commit_marker_is_last_and_artifacts_hash_match(tmp_path,monkeypatch):
    calls=[]
    def upload(url,raw):calls.append((url,raw))
    monkeypatch.setattr(run,'put',upload)
    names=['source-boundary.json','builder-checkpoint.c15.json','completion.json','recovery-receipt.json']
    uploads={x:x for x in names}
    raw=json.dumps(boundary()).encode()
    (tmp_path/'source-boundary.json').write_bytes(raw)
    run.publish(tmp_path,uploads,result(),raw,SimpleNamespace(genesis_hash=lambda:'scope'),'commit',0)
    assert [x[0] for x in calls]==names
    receipt=json.loads(calls[-1][1])
    assert receipt['schema']=='FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1'
    assert receipt['original_ingest_status']=='Cancelled'
    for artifact in receipt['artifacts'].values():
        data=(tmp_path/artifact['file']).read_bytes()
        assert len(data)==artifact['bytes'] and hashlib.sha256(data).hexdigest()==artifact['sha256']
    assert not (tmp_path/'ingestion-receipt.json').exists()

def test_failed_artifact_upload_never_publishes_commit_marker(tmp_path,monkeypatch):
    calls=[]
    def upload(url,raw):
        calls.append(url)
        if url=='completion.json':raise RuntimeError('upload refused')
    monkeypatch.setattr(run,'put',upload)
    names=['source-boundary.json','builder-checkpoint.c15.json','completion.json','recovery-receipt.json']
    raw=json.dumps(boundary()).encode()
    (tmp_path/'source-boundary.json').write_bytes(raw)
    with pytest.raises(RuntimeError):
        run.publish(tmp_path,{x:x for x in names},result(),raw,SimpleNamespace(genesis_hash=lambda:'scope'),'commit',0)
    assert 'recovery-receipt.json' not in calls
    assert (tmp_path/'builder-checkpoint.c15.json').is_file()
    assert (tmp_path/'recovery-receipt.json').is_file()

def test_write_once_preserves_existing(tmp_path):
    path=tmp_path/'receipt'
    path.write_bytes(b'preserved')
    with pytest.raises(FileExistsError):run.write_once(path,b'replacement')
    assert path.read_bytes()==b'preserved'
