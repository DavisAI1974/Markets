"""Journal-derived C15R2 target attachment, no training or market run."""
import math
import pytest
from test_c15_full_evidence import build, submit, row
from c15_normalizer import IdentityNormalizer, State, COLUMNS
from c15_teacher import JournalTeacher


def test_receive_regression_cannot_stamp_target_before_evidence(tmp_path):
    builder=build(tmp_path)
    submit(builder,row(1))
    submit(builder,row(0))
    evidence=list(builder.evidence_stream())
    teacher=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,)))
    with pytest.raises(ValueError,match='receive-time regression'):
        teacher.attach(evidence,evidence[-1:],as_of=102,source_manifest_hash=builder.scope.scope_id)
    assert len(evidence)==2


def test_cutoff_target_uses_complete_history_outside_model_context(tmp_path):
    builder=build(tmp_path)
    submit(builder,row(0,oid=1,size=10,side='A',price=101))
    for i in range(1,65): submit(builder,row(i,action='T',side='B',oid=0,size=1))
    evidence=list(builder.evidence_stream())
    teacher=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,)))
    out=teacher.attach(evidence,evidence[-2:],as_of=6402,source_manifest_hash=builder.scope.genesis_hash())
    assert out['processed_records']==65
    assert len(out['targets'])==2 and all(t.values.shape==(1,1,19) for t in out['targets'])
    assert out['targets'][-1].states[0,0,2].item()==State.PRESENT
    assert out['targets'][-1].values[0,0,2].item()==1.0
    assert out['raw'][1][0]['value']==pytest.approx(math.log1p((6402-2)/1e9))
    assert all(t.states[0,:,7:13].eq(State.ABLATED).all() for t in out['targets'])
    assert out['context_cursors']==(63,64)


def test_observer_ranks_come_from_authoritative_book_before_and_after(tmp_path):
    builder=build(tmp_path)
    submit(builder,row(0,oid=1,price=101))
    submit(builder,row(1,oid=2,price=102))
    changed=submit(builder,row(2,oid=2,action='M',price=100))
    assert changed.evidence['rank_before']==2
    assert changed.evidence['rank_after']==1


def test_nonterminal_target_and_snapshot_origin_are_explicit(tmp_path):
    builder=build(tmp_path)
    submit(builder,row(0,flags=128|32))
    for i in range(1,65): submit(builder,row(i,action='T',side='B',oid=0,size=1))
    submit(builder,row(65,action='N',side='N',oid=0,flags=0))
    evidence=list(builder.evidence_stream())
    out=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,))).attach(evidence,evidence[-2:],as_of=6502,source_manifest_hash=builder.scope.genesis_hash())
    assert out['raw'][0][0]['reason']=='LEFT_CENSORED'
    assert out['raw'][1][0]['reason']=='NOT_F_LAST'
    assert out['targets'][1].states[0,0,0].item()==State.MISSING


def test_teacher_continuous_and_reconstructed_journal_attachment_match(tmp_path):
    from c15_normalizer import Normalizer, NormalizerConfig
    builder=build(tmp_path)
    for i in range(4): submit(builder,row(i))
    evidence=list(builder.evidence_stream())
    teacher=JournalTeacher({1:1},normalizer=Normalizer(NormalizerConfig((1,))))
    first=teacher.attach(evidence,evidence[-2:],as_of=302,source_manifest_hash=builder.scope.genesis_hash())
    again=teacher.attach(evidence,evidence[-2:],as_of=302,source_manifest_hash=builder.scope.genesis_hash())
    assert first['attachment_hash']==again['attachment_hash']
    assert first['step_receipts']==again['step_receipts']


@pytest.mark.parametrize('last,expected', [
    (dict(action='F',oid=1,size=3), 'UNRECONCILED_FILL'),
    (dict(action='F',oid=999,size=3), 'MISSING_REFERENCE'),
    (dict(action='T',oid=0,side='N',size=1000), 'UNKNOWN_SIDE'),
])
def test_window_integrity_does_not_ignore_fill_or_unknown_trade(tmp_path,last,expected):
    builder=build(tmp_path)
    submit(builder,row(0))
    for i in range(1,64): submit(builder,row(i,action='T',side='B',oid=0,size=1))
    submit(builder,row(64,**last))
    evidence=list(builder.evidence_stream())
    out=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,))).attach(evidence,evidence[-1:],as_of=6402,source_manifest_hash=builder.scope.scope_id)
    assert out['raw'][0][3]['state']==State.INVALID
    assert out['raw'][0][3]['reason']==expected


def test_finite_price_tob_add_is_not_a_reset(tmp_path):
    builder=build(tmp_path)
    submit(builder,row(0))
    for i in range(1,64): submit(builder,row(i,action='T',side='B',oid=0,size=1))
    submit(builder,row(64,oid=2,price=102,flags=192))
    evidence=list(builder.evidence_stream())
    out=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,))).attach(evidence,evidence[-1:],as_of=6402,source_manifest_hash=builder.scope.scope_id)
    assert out['raw'][0][3]['state']==State.PRESENT


def test_each_target_artifact_binds_its_own_cutoff_and_prefix(tmp_path):
    builder=build(tmp_path)
    for i in range(3): submit(builder,row(i,oid=i+1))
    evidence=list(builder.evidence_stream())
    out=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,))).attach(evidence,evidence,as_of=202,source_manifest_hash=builder.scope.scope_id)
    for e,target,receipt in zip(evidence,out['targets'],out['step_receipts']):
        assert target.source_prefix_hash==e['terminal_prefix_hash']
        assert target.as_of_ts_recv_ns==e['normalized']['ts_recv_ns']
        assert target.values.shape==(1,1,19)
        assert receipt['cursor']==e['cursor'] and receipt['target_hash']==target.target_hash


def test_matched_fill_cancel_counts_one_economic_removal(tmp_path):
    builder=build(tmp_path); submit(builder,row(0))
    for i in range(1,64): submit(builder,row(i,action='T',side='B',oid=0,size=1))
    submit(builder,row(64,action='F',size=3,flags=0))
    submit(builder,row(65,action='C',size=3))
    evidence=list(builder.evidence_stream())
    out=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,))).attach(evidence,evidence[-1:],as_of=6502,source_manifest_hash=builder.scope.scope_id)
    assert out['raw'][0][3]['state']==State.PRESENT
    assert out['raw'][0][3]['value']==pytest.approx(-math.log1p(3))


def test_journal_derived_d_chain_matches_known_break_restart_trace(tmp_path):
    builder=build(tmp_path); submit(builder,row(0,price=10))
    for i in range(1,64): submit(builder,row(i,action='T',side='B',oid=0,size=1))
    for i,price in enumerate((11,10,12,9,13,12,14),64): submit(builder,row(i,action='M',price=price))
    evidence=list(builder.evidence_stream())
    out=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,))).attach(evidence,evidence[-1:],as_of=7002,source_manifest_hash=builder.scope.scope_id)
    raw=out['raw'][0]
    assert raw[14]['value']==pytest.approx(math.log1p(1))
    assert raw[16]['value']==pytest.approx(math.log1p(1))
    assert raw[17]['value']==pytest.approx(math.log1p(2))


def test_builder_restore_and_later_attachment_are_identical(tmp_path):
    from c15_builder import C15Builder
    builder=build(tmp_path)
    for i in range(3): submit(builder,row(i,oid=i+1))
    saved=builder.export_state()
    resumed=C15Builder.restore(builder.scope,builder.journal.path,saved,expected_hash=saved['state_hash'])
    submit(resumed,row(3,oid=4))
    restored=list(resumed.evidence_stream())
    teacher=JournalTeacher({1:1},normalizer=IdentityNormalizer((1,)))
    after=teacher.attach(restored,restored[-2:],as_of=302,source_manifest_hash=builder.scope.scope_id)
    other=tmp_path/'continuous'; other.mkdir()
    continuous=build(other)
    for i in range(4): submit(continuous,row(i,oid=i+1))
    evidence=list(continuous.evidence_stream())
    direct=teacher.attach(evidence,evidence[-2:],as_of=302,source_manifest_hash=continuous.scope.scope_id)
    assert after['attachment_hash']==direct['attachment_hash']
    assert after['raw']==direct['raw']
