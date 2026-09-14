"""Synthetic single-session manifest and frozen native forecast tests."""
from dataclasses import replace
import pytest
import torch
from forecast_heads import KnotPolicy
from forecast_session import ForecastSession, PriceObservation
from forecast_artifact import freeze_forecast, NativeForecastArtifact
from test_forecast_heads import decoder

H = 'a' * 64


def session(**changes):
    base = ForecastSession('SYN', 'session', 1000, 2000, 500, 500,
                           2., .01, H, H, H, KnotPolicy(1, 8),
                           prior_close=PriceObservation(400, 401, 100., H))
    return replace(base, **changes)


def stopped_decoder():
    m = decoder()
    with torch.no_grad():
        m.time_decoder[-1].weight.zero_()
        m.time_decoder[-1].bias[:] = torch.tensor([0., 1.])
    return m


def freeze(m=None, s=None):
    return freeze_forecast(m or stopped_decoder(), torch.ones(4, dtype=torch.float64),
                           s or session(), native_model_hash=H, input_hash=H, arm_hash=H)


def test_frozen_artifact_queries_survive_weight_changes_and_preserve_rng():
    m = stopped_decoder(); state = torch.get_rng_state().clone()
    f = freeze(m); before = f.query(1371)
    assert torch.equal(state, torch.get_rng_state())
    assert f.points[0].p50 == 0 and f.points[0].time_ns == 1000
    assert f.net_usd == f.gap_quantiles[1] + f.points[-1].p50
    assert f.points[-1].time_ns == 2000
    with torch.no_grad(): m.path_median[-1].weight.add_(10)
    assert f.query(1371) == before
    assert freeze(m).digest != f.digest
    assert torch.equal(state, torch.get_rng_state())


def test_observed_gap_and_current_mark_are_causal_and_never_graded_as_forecasts():
    prior = PriceObservation(900, 901, 101., H)
    opening = PriceObservation(1000, 1001, 99., H)
    current = PriceObservation(1400, 1400, 102., H)
    s = session(event_cutoff_ns=1400, receive_cutoff_ns=1400,
                prior_close=prior, opening=opening, known_marks=(current,))
    f = freeze(s=s)
    assert f.gap_quantiles == (-4., -4., -4.) and f.gap_observed
    assert [(p.time_ns, p.p50, p.observed) for p in f.points[:2]] == [(1000, 0., True), (1400, 6., True)]
    assert f.query(1400) == (6., 6., 6.)
    assert not f.points[-1].observed
    with pytest.raises(ValueError, match='observed'): f.query(1200)
    with pytest.raises(ValueError): replace(s, opening=replace(opening, receive_ns=1401))


@pytest.mark.parametrize('changes', [dict(usd_per_price_unit=0), dict(tick_size=float('nan')),
    dict(close_ns=999), dict(event_cutoff_ns=2000, receive_cutoff_ns=2000),
    dict(event_cutoff_ns=501), dict(source_hash='x'), dict(open_ns=True),
    dict(event_cutoff_ns=1200, receive_cutoff_ns=1200), dict(known_marks=[])])
def test_invalid_or_unavailable_session_rejects(changes):
    with pytest.raises(ValueError): session(**changes)


def test_preopen_does_not_accept_future_observations_and_queries_stay_in_session():
    with pytest.raises(ValueError):
        session(opening=PriceObservation(1000, 1001, 99., H))
    for time in (999, 2001, 1000.5, True):
        with pytest.raises(ValueError): freeze().query(time)


def test_frozen_payload_has_content_identity_and_no_confidence_category():
    f = freeze()
    assert type(f.payload) is bytes and len(f.digest) == 64
    assert b'confidence' not in f.payload
    assert replace(f, input_hash='b'*64).digest != f.digest
    with pytest.raises(ValueError): replace(f, net_usd=f.net_usd + 1)


def test_verified_roundtrip_and_tampered_point_rejection():
    f = freeze()
    restored = NativeForecastArtifact.from_payload(f.payload, expected_digest=f.digest)
    assert restored == f and restored.query(1371) == f.query(1371)
    with pytest.raises(ValueError, match='trusted'):
        NativeForecastArtifact.from_payload(f.payload, expected_digest='b'*64)
    point = replace(f.points[-1], quantiles=(0., 0., 0.))
    changed = replace(f, points=(f.points[0], point), net_usd=f.gap_quantiles[1])
    with pytest.raises(ValueError): changed.verify_reproduction()
    with pytest.raises(ValueError):
        NativeForecastArtifact.from_payload(changed.payload, expected_digest=f.digest)


def test_distinct_session_horizons_condition_native_values():
    first = freeze()
    later = freeze(s=session(open_ns=3000, close_ns=4000))
    assert first.gap_quantiles != later.gap_quantiles
    assert first.query(1700) != later.query(3700)


def test_snapshot_rejects_unversioned_architecture_or_forward_override():
    m = stopped_decoder(); m.path_median[1] = torch.nn.Identity().eval()
    with pytest.raises(ValueError, match='architecture'): freeze(m)


def test_changed_denormal_arithmetic_rejects_frozen_query():
    from forecast_artifact import runtime_hash
    # This CPU fixture restores gradual underflow after its bounded fault injection.
    torch.set_flush_denormal(False)
    try:
        f = freeze(); before = runtime_hash()
        if torch.set_flush_denormal(True):
            assert runtime_hash() != before
            with pytest.raises(ValueError, match='runtime'): f.query(1371)
    finally:
        torch.set_flush_denormal(False)
    m = stopped_decoder(); m.gap = lambda z: torch.zeros(3)
    with pytest.raises(ValueError, match='architecture'): freeze(m)
