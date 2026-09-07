"""Journal-backed context coverage, failures and trusted resume, synthetic only."""
import copy
import pytest
import torch
from native_mbo_encoder import NativeRegistry, NativeTrunk, reconstruct
from context_session import ContextSessionRunner
from test_c15_full_evidence import build, submit, row


def model():
    torch.manual_seed(20)
    return NativeTrunk(NativeRegistry(), d_model=16, n_heads=2, n_layers=1).double().eval()


def test_context_receipt_accounts_for_every_prefix_row_and_resume(tmp_path):
    builder = build(tmp_path)
    m = model()
    session = ContextSessionRunner(m, builder, entity=(1,1), t_ctx=2)
    for i in range(4):
        session.append(row(i), source_member_index=0, session_id='s')
    output = session.run(as_of=302)
    r = output.receipt
    assert (r.prefix_rows, r.context_start, r.context_end, r.outside_context_rows) == (4,2,4,2)
    assert r.context_cursors == (2,3) and r.consumed_rows == 2
    assert output.heads['evidence_scores'].shape == (1,2)
    assert r.journal_entries == 8 and r.journal_prefix_hash == builder.journal.head_hash
    assert len(r.packet_hashes) == 2
    state = session.export()
    resumed = ContextSessionRunner.restore(m, builder, state, expected_input_hash=r.input_hash, expected_model_hash=r.model_hash)
    again = resumed.run(as_of=302)
    assert again.receipt == r
    assert all(torch.equal(output.heads[k],again.heads[k]) for k in output.heads)
    state['tokens']['numeric'][0,0,0] += 1
    with pytest.raises(ValueError,match='input'):
        ContextSessionRunner.restore(m,builder,state,expected_input_hash=r.input_hash,expected_model_hash=r.model_hash)


def test_failure_keeps_input_blocks_append_and_allows_exact_retry(tmp_path, monkeypatch):
    builder=build(tmp_path); m=model()
    session=ContextSessionRunner(m,builder,entity=(1,1),t_ctx=2)
    source=row(0)
    session.append(source,source_member_index=0,session_id='s')
    source['size']=999
    original=m.forward
    def fail(**kwargs): raise RuntimeError('synthetic forward failure')
    monkeypatch.setattr(m,'forward',fail)
    with pytest.raises(RuntimeError): session.run(as_of=2)
    with pytest.raises(ValueError,match='retry'): session.append(row(1),source_member_index=0,session_id='s')
    assert builder.adapter.record_count==1
    monkeypatch.setattr(m,'forward',original)
    out=session.run(as_of=2)
    assert out.receipt.consumed_rows==1
    assert reconstruct(session.export()['tokens'],m.registry)[0]['size']==10


def test_entity_interleaving_cutoff_and_foreign_model_are_checked(tmp_path):
    builder=build(tmp_path); m=model()
    for i in range(4): submit(builder,row(i,iid=2 if i==1 else 1))
    session=ContextSessionRunner(m,builder,entity=(1,1),t_ctx=2)
    out=session.run(as_of=302)
    assert out.receipt.prefix_rows==4 and out.receipt.entity_rows==3
    assert out.receipt.other_entity_rows==1
    assert out.receipt.context_cursors==(2,3)
    with pytest.raises(ValueError,match='future'): session.run(as_of=2)
    # Failed validation is retained; the original cutoff may be retried.
    session.run(as_of=302)
    state=session.export()
    changed=model()
    with torch.no_grad(): changed.byte_embedding.weight[0,0]+=1
    with pytest.raises(ValueError,match='model'):
        ContextSessionRunner.restore(changed,builder,state,expected_input_hash=out.receipt.input_hash,expected_model_hash=out.receipt.model_hash)


def test_b1_accepts_native_trunk_with_finite_window_and_qsv_disabled(tmp_path):
    from b1_reasoner import B1Reasoner, B1Config
    builder=build(tmp_path); submit(builder,row(0))
    boss=B1Reasoner(model(),B1Config(k_max=1,k_fixed=1)).double().eval()
    out=ContextSessionRunner(boss,builder,entity=(1,1),t_ctx=2).run(as_of=2)
    assert out.receipt.consumed_rows==1 and out.recurrence_receipt is not None


def test_teacher_attachment_and_resume_bind_every_cutoff(tmp_path):
    from c15_teacher import JournalTeacher
    from c15_normalizer import IdentityNormalizer
    builder=build(tmp_path); m=model()
    for i in range(3): submit(builder,row(i,oid=i+1))
    teacher=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,)))
    session=ContextSessionRunner(m,builder,entity=(1,1),t_ctx=2,teacher=teacher)
    out=session.run(as_of=202)
    assert out.receipt.teacher_hash==out.teacher['attachment_hash']
    assert out.teacher['processed_records']==3
    assert [r['cursor'] for r in out.teacher['step_receipts']]==[1,2]
    state=session.export()
    restored=ContextSessionRunner.restore(m,builder,state,teacher=teacher,
        expected_input_hash=out.receipt.input_hash,expected_model_hash=out.receipt.model_hash)
    assert restored.run(as_of=202).receipt==out.receipt
    with pytest.raises(ValueError,match='input'):
        ContextSessionRunner.restore(m,builder,state,expected_input_hash=out.receipt.input_hash,
            expected_model_hash=out.receipt.model_hash)


def test_earlier_cursor_receipt_is_unchanged_by_future_suffix(tmp_path):
    builder=build(tmp_path); m=model()
    submit(builder,row(0))
    session=ContextSessionRunner(m,builder,entity=(1,1),t_ctx=2)
    first=session.run(as_of=2,through_cursor=0)
    submit(builder,row(1))
    assert session.run(as_of=2,through_cursor=0).receipt==first.receipt


def test_training_mode_and_incomplete_or_unmapped_source_fail_closed(tmp_path):
    builder=build(tmp_path); m=model()
    with pytest.raises(ValueError,match='eval'):
        ContextSessionRunner(m.train(),builder,entity=(1,1))
    m.eval(); session=ContextSessionRunner(m,builder,entity=(1,1))
    session.append({**row(0),'undeclared':17},source_member_index=0,session_id='s')
    with pytest.raises(ValueError,match='unmapped'):
        session.run(as_of=2)
    assert list(builder.evidence_stream())[0]['raw_record']['undeclared']==17


def test_failed_forward_cannot_retry_with_changed_weights(tmp_path, monkeypatch):
    builder=build(tmp_path); m=model(); submit(builder,row(0))
    session=ContextSessionRunner(m,builder,entity=(1,1))
    original=m.forward
    def fail(**kwargs): raise RuntimeError('synthetic')
    monkeypatch.setattr(m,'forward',fail)
    with pytest.raises(RuntimeError): session.run(as_of=2)
    monkeypatch.setattr(m,'forward',original)
    with torch.no_grad(): m.byte_embedding.weight[0,0]+=1
    with pytest.raises(ValueError,match='retry.*model|model.*retry'): session.run(as_of=2)


def test_explicit_qsv_ablation_remains_allowed(tmp_path):
    builder=build(tmp_path); submit(builder,row(0))
    m=NativeTrunk(NativeRegistry(),d_model=16,n_heads=2,n_layers=1,use_qsv=True).double().eval()
    m.encoder.ablate_qsv()
    assert ContextSessionRunner(m,builder,entity=(1,1)).run(as_of=2).receipt.consumed_rows==1


def test_failed_forward_cannot_retry_with_changed_context(tmp_path,monkeypatch):
    builder=build(tmp_path); m=model()
    for i in range(2): submit(builder,row(i))
    session=ContextSessionRunner(m,builder,entity=(1,1),t_ctx=2)
    original=m.forward
    def fail(**kwargs): raise RuntimeError('synthetic')
    monkeypatch.setattr(m,'forward',fail)
    with pytest.raises(RuntimeError): session.run(as_of=102)
    monkeypatch.setattr(m,'forward',original)
    session.t_ctx=1
    with pytest.raises(ValueError,match='retry input'): session.run(as_of=102)
