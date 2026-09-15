"""New integration regressions only; no model forward or retained source access."""
from types import SimpleNamespace
import struct
import pytest
import torch
from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
from research.kalshi.frankie_boss.verified_journal_reader import VerifiedJournalReader
from research.kalshi.frankie_boss.prepared_context_cache import prepare_context_cache,same_preparation


def case(tmp_path):
    path=tmp_path/'source.sqlite'
    writer=EvidenceJournal(path,create=True);writer.append('synthetic',{})
    count,head=writer.count,writer.head_hash;writer.close()
    reader=VerifiedJournalReader(path,expected_count=count,expected_head_hash=head)
    assert not hasattr(reader,'connection')
    context=SimpleNamespace(builder=SimpleNamespace(journal=reader,_failed=False,
        scope=SimpleNamespace(kind=SimpleNamespace(value='RESULT_BEARING'),scope_id='b'*64,genesis_hash=lambda:'c'*64),
        chain=SimpleNamespace(next_cursor=1)),model=torch.nn.Linear(1,1),entity=(1,1),t_ctx=1,
        teacher=None,qsv=None,expected_qsv_hash=None,_model_hash=lambda:'a'*64)
    def prepare(*args):
        return dict(numeric=torch.tensor([1.])),dict(as_of=10,t_ctx=1,teacher_binding=None,
            source_prefix_hash='d'*64,journal_prefix_hash=head,journal_entries=1,consumed_rows=1,context_cursors=(0,),teacher_hash=None),'e'*64,None,[{}]
    context._prepare=prepare
    cache=prepare_context_cache(context,as_of=10,through_cursor=0,expected_source_checkpoint=dict(count=count,head_hash=head),
        expected_model_hash='a'*64,expected_teacher_binding=None,checkpoint_hash='f'*64,current_checkpoint_hash=lambda:'f'*64)
    return context,cache


def test_cache_accepts_real_verified_reader_without_public_connection(tmp_path):
    context,cache=case(tmp_path)
    try:assert cache.prepare(10,0)[2]=='e'*64
    finally:cache.close();context.builder.journal.close()


def test_device_move_invalidates_cache_before_model_hash_or_preparation(tmp_path):
    context,cache=case(tmp_path)
    try:
        context.model.to('meta')
        context._model_hash=lambda:pytest.fail('device mismatch must reject before model hash')
        with pytest.raises(ValueError,match='identity differs'):cache.prepare(10,0)
    finally:cache.close();context.builder.journal.close()


def test_tensor_comparison_preserves_signed_zero_and_nan_payload_bits():
    def tensor(bits):return torch.frombuffer(bytearray(struct.pack('<Q',bits)),dtype=torch.float64).clone()
    assert not same_preparation(tensor(0),tensor(1<<63))
    a=tensor(0x7ff8000000000001);b=tensor(0x7ff8000000000002)
    assert same_preparation(a,a.clone())
    assert not same_preparation(a,b)
