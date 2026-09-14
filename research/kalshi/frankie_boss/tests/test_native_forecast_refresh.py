"""Same-forward native generation into the existing rolling ledger, synthetic only."""
from dataclasses import asdict, replace
import pytest
import torch
from b1_reasoner import B1Reasoner, B1Config
from c15_journal import evidence_hash
from context_session import ContextSessionRunner
from forecast_artifact import NativeForecastArtifact
from forecast_refresh import RefreshPolicy
from forecast_session import ForecastSession, PriceObservation
from forecast_heads import NativeForecastHeads, KnotPolicy
from rolling_forecast import ForecastTarget, RollingForecastBook
from native_forecast_refresh import NativeForecastRefresh, session_registry_hash
from test_context_session import model
from test_c15_full_evidence import build, submit, row

H = 'a'*64


def build_refresh(tmp_path):
    builder = build(tmp_path); submit(builder, row(0))
    boss = B1Reasoner(model(), B1Config(k_max=1, k_fixed=1)).double().eval()
    runner = ContextSessionRunner(boss, builder, entity=(1, 1))
    torch.manual_seed(8)
    decoder = NativeForecastHeads(16, 8).eval()
    with torch.no_grad():
        decoder.time_decoder[-1].weight.zero_(); decoder.time_decoder[-1].bias[:] = torch.tensor([0., 1.])
    book = RollingForecastBook(tmp_path/'forecasts.sqlite', create=True)
    sessions = tuple((ForecastTarget('SYN', str(i), 2000+i*2000),
        ForecastSession('SYN', str(i), 1000+i*2000, 2000+i*2000, 1, 2,
            2., .01, H, H, builder.chain.prefix_hash, KnotPolicy(1, 8),
            prior_close=PriceObservation(0, 0, 100., H))) for i in range(3))
    bridge = NativeForecastRefresh(runner, decoder, book, tuple(t for t, s in sessions), RefreshPolicy(((10000, 1),)))
    return bridge, sessions


def update(bridge, sessions):
    first = sessions[0][1]
    return bridge.update(sessions=sessions, expected_sessions_hash=session_registry_hash(sessions), arm_hash=H,
                         as_of=first.receive_cutoff_ns, source_as_of=first.event_cutoff_ns, source_hash=first.source_hash)


def test_second_handle_source_change_during_forward_never_publishes(tmp_path, monkeypatch):
    from c15_journal import EvidenceJournal
    bridge,sessions=build_refresh(tmp_path)
    original=bridge.context.model.forward_decision
    def changed(**kwargs):
        result=original(**kwargs)
        other=EvidenceJournal(bridge.context.builder.journal.path)
        try: other.append('foreign-audit',{})
        finally: other.close()
        return result
    monkeypatch.setattr(bridge.context.model,'forward_decision',changed)
    with pytest.raises(ValueError): update(bridge,sessions)
    assert all(bridge.book.latest(t,arm_hash=H) is None for t,_ in sessions)
    with pytest.raises(ValueError): update(bridge,sessions)


def test_each_target_uses_same_forward_state_and_preserves_native_receipt(tmp_path, monkeypatch):
    bridge, sessions = build_refresh(tmp_path)
    original = bridge.context.model.forward_decision; states = []
    def record(**kwargs):
        out = original(**kwargs); states.append(out.representation.detach().clone()); return out
    monkeypatch.setattr(bridge.context.model, 'forward_decision', record)
    output = update(bridge, sessions)
    assert len(output) == len(states) == 3
    for published, state in zip(output, states):
        payload = published.selected.forecast_artifact
        artifact = NativeForecastArtifact.from_payload(payload, expected_digest=bridge.artifact_digest(published))
        assert artifact.representation == tuple(state[0, -1].tolist())
        assert artifact.native_model_hash == bridge.context._model_hash()
        assert published.selected.score is None and published.revision == 1
    assert update(bridge, sessions) == output and len(states) == 3


def test_failure_binds_all_configuration_before_forward_and_survives_restore(tmp_path, monkeypatch):
    bridge, sessions = build_refresh(tmp_path); original = bridge.context.model.forward_decision
    def fail(**kwargs): raise RuntimeError('synthetic before output')
    monkeypatch.setattr(bridge.context.model, 'forward_decision', fail)
    with pytest.raises(RuntimeError): update(bridge, sessions)
    checkpoint = bridge.book.checkpoint()
    bridge.book.close()
    bridge.book = RollingForecastBook(tmp_path/'forecasts.sqlite', checkpoint=checkpoint)
    monkeypatch.setattr(bridge.context.model, 'forward_decision', original)
    with torch.no_grad(): bridge.decoder.gap_median[-1].bias.add_(1)
    with pytest.raises(ValueError, match='intent|changed'): update(bridge, sessions)


def test_partial_retry_finishes_only_unpublished_targets(tmp_path, monkeypatch):
    bridge, sessions = build_refresh(tmp_path); original = bridge.context.model.forward_decision; calls = []
    def fail_second(**kwargs):
        calls.append(1)
        if len(calls) == 2: raise RuntimeError('synthetic second target')
        return original(**kwargs)
    monkeypatch.setattr(bridge.context.model, 'forward_decision', fail_second)
    with pytest.raises(RuntimeError): update(bridge, sessions)
    result = update(bridge, sessions)
    assert len(result) == 3 and len(calls) == 4
    assert all(p.revision == 1 for p in result)


def test_new_data_revises_every_target_without_changing_model_identity(tmp_path):
    bridge, sessions = build_refresh(tmp_path); first = update(bridge, sessions)
    submit(bridge.context.builder, row(1))
    new = tuple((t, replace(s, event_cutoff_ns=101, receive_cutoff_ns=102,
                   source_hash=bridge.context.builder.chain.prefix_hash)) for t, s in sessions)
    second = update(bridge, new)
    assert [p.revision for p in second] == [2, 2, 2]
    assert [p.selected.target for p in second] == [p.selected.target for p in first]
    assert [p.selected.model_hash for p in second] == [p.selected.model_hash for p in first]
    assert [p.previous_hash for p in second] == [p.receipt_hash for p in first]


def test_source_or_target_semantics_mismatch_fails_before_forward(tmp_path, monkeypatch):
    bridge, sessions = build_refresh(tmp_path)
    def forbidden(**kwargs): raise AssertionError('must not forward')
    monkeypatch.setattr(bridge.context.model, 'forward_decision', forbidden)
    bad = tuple((t, replace(s, source_hash='b'*64)) for t, s in sessions)
    with pytest.raises(ValueError, match='source'): update(bridge, bad)
    bad = ((replace(sessions[0][0], target_ns=1999), sessions[0][1]), *sessions[1:])
    with pytest.raises(ValueError): update(bridge, bad)


def test_expired_target_does_not_block_later_horizons(tmp_path):
    bridge, sessions = build_refresh(tmp_path); first = update(bridge, sessions)
    submit(bridge.context.builder, row(21))
    active = tuple((t, replace(s, event_cutoff_ns=2101, receive_cutoff_ns=2102,
                    source_hash=bridge.context.builder.chain.prefix_hash)) for t, s in sessions[1:])
    result = update(bridge, active)
    assert [p.selected.target for p in result] == [p.selected.target for p in first[1:]]
    assert [p.revision for p in result] == [2, 2]
    assert bridge.book.latest(sessions[0][0], arm_hash=H) == first[0]


def test_retry_binds_effective_native_module_settings(tmp_path, monkeypatch):
    bridge, sessions = build_refresh(tmp_path); original = bridge.context.model.forward_decision
    def fail(**kwargs): raise RuntimeError('synthetic')
    monkeypatch.setattr(bridge.context.model, 'forward_decision', fail)
    with pytest.raises(RuntimeError): update(bridge, sessions)
    monkeypatch.setattr(bridge.context.model, 'forward_decision', original)
    bridge.context.model.ln_out.eps = .1
    with pytest.raises(ValueError, match='intent|changed'): update(bridge, sessions)
