import copy
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
from research.kalshi.frankie_boss import boss_training_checkpoint as training
from research.kalshi.frankie_boss import c15_journal as journal
from research.kalshi.frankie_boss import sunday_execution as driver
from research.kalshi.frankie_boss.granite_positive_priming import MODE,load_retained_priming
from research.kalshi.frankie_boss.operations.run_actual_sunday import ActualHost,sha_state

@pytest.fixture(scope='module')
def capsule():return load_retained_priming(Path(__file__).resolve().parents[4],mode=MODE)

class TinyCoordinator:
    def __init__(self,capsule):self.capsule=copy.deepcopy(capsule);self.checks=0
    def _knowledge_lineage_unchanged(self):self.checks+=1
    def _lineage_value(self):
        return dict(schema='FRANKIE_KNOWLEDGE_LINEAGE_V1',priming=copy.deepcopy(self.capsule),
            priming_hash=None if self.capsule is None else journal.evidence_hash(self.capsule))

def make_host(directory,capsule):
    host=ActualHost.__new__(ActualHost);host.directory=directory
    host.schedule={'model_context_rows':8};host.builder=object();host.code={'test_source':'fixed'}
    host.scope=SimpleNamespace(genesis_hash=lambda:'c'*64);host.coordinator=TinyCoordinator(capsule)
    host.saved={};host.save=lambda name,value:host.saved.__setitem__(name,copy.deepcopy(value))
    development={'schema':'TINY_TEST_DEVELOPMENT_V1','seed':1,'lr':0.1}
    def initialize(builder,*,context_rows):
        assert builder is host.builder and context_rows==8
        native=torch.nn.Linear(1,1,bias=False).double();decoder=torch.nn.Linear(1,1,bias=False).double()
        with torch.no_grad():native.weight.fill_(17);decoder.weight.fill_(29)
        optimizer=torch.optim.SGD(list(native.parameters())+list(decoder.parameters()),lr=0.1)
        return SimpleNamespace(model=native),decoder,optimizer,{'native_hash':sha_state(training,native)}
    host.api=SimpleNamespace(training=training,journal=journal,driver=driver,
        native=SimpleNamespace(DEVELOPMENT=development,initialize=initialize))
    return host

def commit_tiny_update(host):
    def update():
        with torch.no_grad():host.context.model.weight.fill_(47);host.decoder.weight.fill_(61)
        return {'updated':True}
    return host.checkpoint.apply_completed('trained',controller_result_hash='e'*64,training_cursor=0,update=update)

def test_actual_unprimed_training_preserves_ordinary_hash(tmp_path):
    host=make_host(tmp_path,None);host._training()
    try:
        assert host.checkpoint.identities['training_config_hash']==journal.evidence_hash(host.api.native.DEVELOPMENT)
        assert 'training-knowledge-lineage.c15.json' not in host.saved and host.coordinator.checks==1
        raw=host.checkpoint.db.execute('SELECT payload FROM checkpoints WHERE sequence=0').fetchone()[0]
        assert training._decode(raw)['identities']==host.checkpoint.identities
    finally:host.checkpoint.close()

def test_actual_same_capsule_restores_trained_weights(tmp_path,monkeypatch,capsule):
    first=make_host(tmp_path,capsule);first._training()
    binding=first.saved['training-knowledge-lineage.c15.json']
    assert binding['knowledge_lineage']==first.coordinator._lineage_value()
    assert binding['knowledge_mode']==MODE
    assert binding['training_config_hash']==first.checkpoint.identities['training_config_hash']
    assert binding['training_config_hash']!=journal.evidence_hash(first.api.native.DEVELOPMENT)
    try:committed=commit_tiny_update(first)
    finally:first.checkpoint.close()
    restored=[];original=training.BossTrainingCheckpoint._restore
    def observed_restore(self,state):
        restored.append(state['sequence']);return original(self,state)
    monkeypatch.setattr(training.BossTrainingCheckpoint,'_restore',observed_restore)
    second=make_host(tmp_path,copy.deepcopy(capsule));second._training()
    try:
        assert restored==[1] and second.checkpoint.checkpoint_hash==committed['checkpoint_hash']
        assert second.context.model.weight.item()==47 and second.decoder.weight.item()==61
        assert second.saved['training-knowledge-lineage.c15.json']==binding
    finally:second.checkpoint.close()

@pytest.mark.parametrize('replacement',['absent','changed'])
def test_actual_foreign_lineage_refuses_before_any_restore(tmp_path,monkeypatch,capsule,replacement):
    first=make_host(tmp_path,capsule);first._training()
    try:committed=commit_tiny_update(first)
    finally:first.checkpoint.close()
    next_capsule=None
    if replacement=='changed':
        next_capsule=copy.deepcopy(capsule);next_capsule['source_request_id']+='-different'
    restored=[]
    def forbidden_restore(self,state):
        restored.append(state['sequence']);pytest.fail('foreign replay lineage reached model restore')
    monkeypatch.setattr(training.BossTrainingCheckpoint,'_restore',forbidden_restore)
    foreign=make_host(tmp_path,next_capsule)
    with pytest.raises(ValueError,match='training checkpoint identity or chain differs'):foreign._training()
    assert restored==[] and foreign.context.model.weight.item()==17 and foreign.decoder.weight.item()==29
    import sqlite3
    db=sqlite3.connect((tmp_path/'training.sqlite').as_uri()+'?mode=ro',uri=True)
    try:assert db.execute('SELECT digest FROM checkpoints ORDER BY sequence DESC LIMIT 1').fetchone()[0]==committed['checkpoint_hash']
    finally:db.close()
