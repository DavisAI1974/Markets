import asyncio
import copy
from pathlib import Path
import pytest
from research.kalshi.frankie_boss import feedback_cycle as cycle
from research.kalshi.frankie_boss.critic_knowledge import build_knowledge
from research.kalshi.frankie_boss.granite_positive_priming import MODE, load_retained_priming
from test_feedback_cycle import fixture as cycle_fixture

@pytest.fixture(scope='module')
def capsule():
    return load_retained_priming(Path(__file__).resolve().parents[4],mode=MODE)

def open_store(directory,*,priming=None,create=False):
    memory=directory/'memory-a'
    if not memory.exists():memory.write_bytes(b'frozen')
    return cycle.CycleCoordinator(directory/'cycle.sqlite',lessons_path=directory/'lessons.sqlite',
        frozen_memory_path=memory,frozen_memory_sha256=cycle.file_hash(memory),
        create=create,critic_priming=priming)

def test_capsule_owned_before_first_controller_or_training(tmp_path,capsule):
    store=open_store(tmp_path,priming=capsule,create=True)
    expected=store._lineage_value()
    assert store._load(store.LINEAGE_REQUEST,store.LINEAGE_STAGE)==expected
    assert store.db.execute("SELECT COUNT(*) FROM stages WHERE stage='binding'").fetchone()[0]==0
    store.close()
    with pytest.raises(ValueError,match='lineage'):open_store(tmp_path)
    changed=copy.deepcopy(capsule);changed['source_request_id']+='-changed'
    with pytest.raises(ValueError,match='lineage'):open_store(tmp_path,priming=changed)
    reopened=open_store(tmp_path,priming=capsule)
    assert reopened._load(reopened.LINEAGE_REQUEST,reopened.LINEAGE_STAGE)==expected
    reopened.close()

def test_existing_unprimed_run_cannot_be_reinterpreted(tmp_path,capsule):
    open_store(tmp_path,create=True).close()
    with pytest.raises(ValueError,match='lineage'):open_store(tmp_path,priming=capsule)
    reopened=open_store(tmp_path);assert reopened._lineage_value()['priming'] is None;reopened.close()

def test_lineage_is_rechecked_before_native_update(tmp_path,monkeypatch,capsule):
    store,checkpoint,args,calls=cycle_fixture(tmp_path,monkeypatch)
    initial=checkpoint.checkpoint_hash
    def changed_after_verified_feedback(phase,**kwargs):
        if phase=='native_learning':store.critic_priming=copy.deepcopy(capsule)
    store.phase_callback=changed_after_verified_feedback
    try:
        with pytest.raises(ValueError,match='lineage'):asyncio.run(store.run(**args))
        assert calls['learner']==0 and checkpoint.checkpoint_hash==initial
        assert store._load('sun','feedback') is not None
        assert store._load('sun','training') is None
    finally:store.close();checkpoint.close()

def test_primed_origin_cannot_enter_unprimed_successor(tmp_path,monkeypatch,capsule):
    store,checkpoint,args,calls=cycle_fixture(tmp_path,monkeypatch)
    try:
        asyncio.run(store.run(**args))
        origin=build_knowledge([],cutoff_ns=10,request_id='sun')
        origin.update(origins=[],priming=copy.deepcopy(capsule))
        store._save('sun','critic_knowledge',origin)
        complete=store._load('sun','complete')
        complete.update(knowledge_mode=MODE,priming_hash=cycle.evidence_hash(capsule))
        with store.db:
            store.db.execute("UPDATE stages SET payload=?,digest=? WHERE request='sun' AND stage='complete'",
                (cycle.canonical_bytes(cycle.pack(complete)),cycle.evidence_hash(complete)))
        with pytest.raises(ValueError,match='lineage'):store.critic_knowledge('next',cutoff_ns=20)
    finally:store.close();checkpoint.close()

def test_classroom_refuses_priming_before_configuration_or_io():
    from research.kalshi.frankie_boss.operations.run_actual_sunday_classroom import ClassroomActualHost
    host=ClassroomActualHost.__new__(ClassroomActualHost)
    host.config=dict(critic_priming=dict(mode=MODE,profile='retained_cycle00_20260921'))
    with pytest.raises(ValueError,match='does not support historical priming'):asyncio.run(host.run())

def test_legacy_primed_database_requires_same_capsule(tmp_path,capsule):
    store=open_store(tmp_path,priming=capsule,create=True)
    store.critic_knowledge('pending',cutoff_ns=10)
    with store.db:
        store.db.execute('DELETE FROM stages WHERE request=? AND stage=?',
            (store.LINEAGE_REQUEST,store.LINEAGE_STAGE))
    store.close()
    with pytest.raises(ValueError,match='lineage'):open_store(tmp_path)
    reopened=open_store(tmp_path,priming=capsule)
    assert reopened._load(reopened.LINEAGE_REQUEST,reopened.LINEAGE_STAGE)==reopened._lineage_value()
    reopened.close()
