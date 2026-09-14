"""Governed external QSV artifacts reach real native/B1 computation."""
from dataclasses import replace
import pytest
import torch
from context_qsv import QSVContext, QSVRow
from context_session import ContextSessionRunner
from native_mbo_encoder import NativeRegistry, NativeTrunk
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY
from test_c15_full_evidence import build, submit, row


def make_case(tmp_path):
    builder = build(tmp_path)
    submit(builder, row(0))
    event = list(builder.evidence_stream())[0]
    torch.manual_seed(3)
    model = NativeTrunk(NativeRegistry(), d_model=16, n_heads=2,
                        n_layers=1, use_qsv=True).double().eval()
    qrow = QSVRow(0, (1, 1), 2, event['terminal_prefix_hash'],
                  tuple(0.0 for _ in QSV_FEATURE_REGISTRY),
                  tuple(True for _ in QSV_FEATURE_REGISTRY))
    artifact = QSVContext('approved-test-producer', QSV_FEATURE_REGISTRY, (qrow,))
    return builder, model, artifact


def runner(builder, model, artifact):
    return ContextSessionRunner(model, builder, entity=(1, 1),
                                qsv=artifact, expected_qsv_hash=artifact.digest)


def test_enabled_qsv_changes_real_output_and_restores(tmp_path):
    builder, model, artifact = make_case(tmp_path)
    session = runner(builder, model, artifact)
    out = session.run(as_of=2)
    changed = replace(artifact, rows=(replace(artifact.rows[0], values=(10.,)+artifact.rows[0].values[1:]),))
    other = runner(builder, model, changed).run(as_of=2)
    assert not torch.equal(out.heads['evidence_scores'], other.heads['evidence_scores'])
    assert out.receipt.input_hash != other.receipt.input_hash
    restored = ContextSessionRunner.restore(model, builder, session.export(),
        expected_input_hash=out.receipt.input_hash, expected_model_hash=out.receipt.model_hash,
        qsv=artifact, expected_qsv_hash=artifact.digest)
    assert restored.run(as_of=2).receipt == out.receipt


@pytest.mark.parametrize('change', [
    {'available_at': 3}, {'entity': (1, 2)}, {'source_prefix_hash': '0'*64},
    {'cursor': 1}, {'mask': (True,)}, {'values': (float('nan'),)*64},
])
def test_invalid_or_noncausal_artifact_rejected(tmp_path, change):
    builder, model, artifact = make_case(tmp_path)
    with pytest.raises(ValueError):
        bad = replace(artifact, rows=(replace(artifact.rows[0], **change),))
        runner(builder, model, bad).run(as_of=2)


def test_wrong_trusted_identity_and_registry_rejected(tmp_path):
    builder, model, artifact = make_case(tmp_path)
    with pytest.raises(ValueError, match='trusted'):
        ContextSessionRunner(model,builder,entity=(1,1),qsv=artifact,expected_qsv_hash='0'*64)
    with pytest.raises(ValueError, match='registry'):
        replace(artifact, names=tuple(reversed(artifact.names)))


def test_retry_rejects_changed_qsv(tmp_path,monkeypatch):
    builder, model, artifact = make_case(tmp_path)
    session=runner(builder,model,artifact)
    original=model.forward
    def fail(**kw): raise RuntimeError('synthetic forward failure')
    monkeypatch.setattr(model,'forward',fail)
    with pytest.raises(RuntimeError): session.run(as_of=2)
    monkeypatch.setattr(model,'forward',original)
    session.qsv=replace(artifact,rows=(replace(artifact.rows[0],values=(1.,)*64),))
    session.expected_qsv_hash=session.qsv.digest
    with pytest.raises(ValueError,match='retry input'):session.run(as_of=2)


def test_ablation_and_missing_are_distinct_from_present_zero(tmp_path):
    builder, model, artifact = make_case(tmp_path)
    zero=runner(builder,model,artifact).run(as_of=2)
    missing=replace(artifact,rows=(replace(artifact.rows[0],mask=(False,)*64),))
    absent=runner(builder,model,missing).run(as_of=2)
    assert not torch.equal(zero.heads['evidence_scores'],absent.heads['evidence_scores'])
    model.encoder.ablate_qsv()
    a=runner(builder,model,artifact).run(as_of=2)
    b=runner(builder,model,missing).run(as_of=2)
    assert all(torch.equal(a.heads[k],b.heads[k]) for k in a.heads)


def test_b1_consumes_qsv_and_future_artifact_suffix_does_not_change_past(tmp_path):
    from b1_reasoner import B1Reasoner, B1Config
    builder, model, artifact = make_case(tmp_path)
    boss=B1Reasoner(model,B1Config(k_max=1,k_fixed=1)).double().eval()
    first=runner(builder,boss,artifact).run(as_of=2)
    extended=replace(artifact,rows=artifact.rows+(replace(artifact.rows[0],cursor=1,available_at=102),))
    again=runner(builder,boss,extended).run(as_of=2)
    assert first.receipt==again.receipt
    assert first.recurrence_receipt is not None
    changed=replace(artifact,rows=(replace(artifact.rows[0],values=(1.,)*64),))
    other=runner(builder,boss,changed).run(as_of=2)
    assert not torch.equal(first.heads['evidence_scores'],other.heads['evidence_scores'])
    assert first.recurrence_receipt.packet_hash != other.recurrence_receipt.packet_hash
