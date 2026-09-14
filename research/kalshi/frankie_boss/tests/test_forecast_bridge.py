"""Protected-interface proposal and disabled-path preservation, synthetic only."""
from dataclasses import replace
from datetime import datetime, timezone
import pytest
import torch
from forecast_bridge import prepare_frankie_forecast, route_frankie_forecast, LegacyConfidenceCompatibilityError
from forecast_session import ForecastSession
from forecast_heads import KnotPolicy
from forecast_artifact import freeze_forecast
from frankie_contract import BLD1_FIELD_NAMES, FrankieProjector, validate_bld1, ContractError
from test_forecast_heads import decoder

H = 'a'*64


def artifact(*, dst=False):
    opening = int(datetime(2026, 11, 1 if dst else 2, 0 if dst else 1, tzinfo=timezone.utc).timestamp()) * 10**9
    closing = opening + (25 if dst else 24)*3600*10**9
    s = ForecastSession('SYN', 'S', opening, closing, opening-10**9, opening-10**9,
                        2., .01, H, H, H, KnotPolicy(1000000, 4))
    m = decoder()
    with torch.no_grad():
        for p in m.time_decoder.parameters(): p.zero_()
        m.time_decoder[0].weight[0, 4] = 1
        m.time_decoder[-1].weight[1, 0] = 2
        m.time_decoder[-1].bias[:] = torch.tensor([-1.5, -.2])
    return freeze_forecast(m, torch.ones(4, dtype=torch.float64), s,
                           native_model_hash=H, input_hash=H, arm_hash=H)


def metadata():
    return dict(specialist='native', group='synthetic', date='2026-11-02', reasoning='Synthetic review fixture.',
                plays_fired=[], plays_stood_down=[], state_defects_and_gaps_reported=[], disposition='ABSTAIN')


def test_category_free_draft_retains_valid_abstain_forecast_and_stays_outside_bld1():
    f = artifact(); draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata())
    payload = draft.payload
    assert set(payload) == set(BLD1_FIELD_NAMES)
    assert payload['confidence'] is None
    assert payload['guessed_net_usd'] == f.net_usd
    assert payload['disposition'] == 'ABSTAIN' and payload['state_defects_and_gaps_reported'] == []
    assert payload['path_p50_curve'][0][1] == 0
    assert payload['path_p50_curve'][-1][1] == f.points[-1].p50
    with pytest.raises(ContractError, match='low'): validate_bld1(payload)
    with pytest.raises(LegacyConfidenceCompatibilityError) as exc:
        route_frankie_forecast(enabled=True, legacy=lambda: None, load_native=lambda: draft)
    assert exc.value.draft.payload == payload


def test_s121_clock_wrap_fractional_times_and_true_close_sentinel():
    # A normal 20:00 ET -> next-day 20:00 ET session, after DST transition.
    f = artifact()
    day = 24*3600*10**9
    start = int(datetime(2026, 11, 3, 1, tzinfo=timezone.utc).timestamp())*10**9
    s = replace(f.session, open_ns=start, close_ns=start+day,
                event_cutoff_ns=start-10**9, receive_cutoff_ns=start-10**9)
    m = f.snapshot.restore()
    f = freeze_forecast(m, torch.ones(4, dtype=torch.float64), s,
                        native_model_hash=H, input_hash=H, arm_hash=H)
    draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata={**metadata(), 'date': '2026-11-03'})
    curve = draft.payload['path_p50_curve']
    assert curve[0][0] == 20. and curve[-1][0] == '24:00'
    assert any(isinstance(t, float) and t % 1 for t, _ in curve[1:-1])


def test_dst_ambiguous_session_cannot_be_repaired_into_protected_clock():
    f = artifact(dst=True)
    with pytest.raises(ValueError, match='clock|S121'): prepare_frankie_forecast(f, expected_digest=f.digest, metadata=metadata())


def test_wrong_session_date_is_not_projected():
    f = artifact()
    with pytest.raises(ValueError, match='date'):
        prepare_frankie_forecast(f, expected_digest=f.digest, metadata={**metadata(), 'date': '2026-11-04'})


def test_existing_compact_date_is_preserved():
    f = artifact()
    draft = prepare_frankie_forecast(f, expected_digest=f.digest, metadata={**metadata(), 'date': '20261102'})
    assert draft.payload['date'] == '20261102'


def test_coarse_quantum_does_not_hide_dst_clock_mismatch():
    f = artifact(dst=True)
    s = replace(f.session, knot_policy=KnotPolicy(5*3600*10**9, 4))
    f = freeze_forecast(f.snapshot.restore(), torch.ones(4, dtype=torch.float64), s,
                        native_model_hash=H, input_hash=H, arm_hash=H)
    with pytest.raises(ValueError, match='S121|clock'):
        prepare_frankie_forecast(f, expected_digest=f.digest, metadata={**metadata(), 'date': '2026-11-01'})


def test_disabled_import_does_not_load_decoder_or_torch():
    import subprocess
    import sys
    script = "from forecast_bridge import route_frankie_forecast; import sys; assert 'torch' not in sys.modules; assert route_frankie_forecast(legacy=lambda: b'legacy', load_native=None) == b'legacy'; assert 'forecast_artifact' not in sys.modules"
    subprocess.run([sys.executable, '-c', script], check=True)


@pytest.mark.parametrize('lineage', ['v1_control', 'v2'])
def test_disabled_path_is_identity_and_does_not_load_native(lineage):
    from test_b1_reasoner import inputs
    from b1_reasoner import B1Reasoner, B1Config
    import trunk
    if lineage == 'v1_control':
        import importlib.util
        import sys
        from pathlib import Path
        path = Path(__file__).resolve().parents[4]/'tests/fixtures/boss_control_beb548b8/trunk_v1.py'
        spec = importlib.util.spec_from_file_location('_forecast_control', path)
        trunk = importlib.util.module_from_spec(spec); sys.modules[spec.name] = trunk
        spec.loader.exec_module(trunk)
    control = B1Reasoner(trunk.Trunk(trunk.TrunkConfig(d_model=8, n_heads=2, n_layers=1,
        window=3, n_numeric=3, categorical_cardinalities=(4,), use_qsv=False)), B1Config(k_max=1, k_fixed=1)).eval()
    x = inputs(b=1)
    expected = control.forward_decision(**x, packet_hash=H)
    weights = {k: v.clone() for k, v in control.state_dict().items()}
    projector = FrankieProjector('legacy', lineage)
    record = projector.abstain('2026-11-02', ['legacy fixture'], H, lineage)
    before = record.to_json(); rng = torch.get_rng_state().clone(); calls = []
    def native(): raise AssertionError('disabled native loader invoked')
    def legacy():
        calls.append(1)
        actual = control.forward_decision(**x, packet_hash=H)
        assert actual.receipt == expected.receipt
        assert all(torch.equal(actual[k], expected[k]) for k in actual)
        return record
    result = route_frankie_forecast(legacy=legacy, load_native=native)
    assert result is record and result.to_json() == before and calls == [1]
    assert torch.equal(rng, torch.get_rng_state())
    assert all(torch.equal(v, control.state_dict()[k]) for k, v in weights.items())
