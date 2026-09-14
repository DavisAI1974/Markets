"""Claude R3/R4/O5: asynchronous anchors, explicit gap references and tick grid."""
from dataclasses import replace
import pytest
from forecast_session import PriceObservation
from test_forecast_session import session, freeze, H


def postopen(**changes):
    values = dict(event_cutoff_ns=1500, receive_cutoff_ns=1501,
        prior_close=PriceObservation(900, 901, 101., H),
        opening=PriceObservation(1000, 1001, 99., H),
        known_marks=(PriceObservation(1300, 1301, 102., H),))
    return session(**{**values, **changes})


def test_stale_anchor_is_separate_from_global_cutoff_and_never_interpolated():
    s = postopen(); f = freeze(s=s)
    assert s.anchor_ns == 1300 and s.event_cutoff_ns == 1500
    assert f.query(1300) == (6., 6., 6.)
    with pytest.raises(ValueError, match='certified|observed'): f.query(1400)
    assert all(p.time_ns > 1500 for p in f.points if not p.observed)
    assert f.query(1600)[0] <= f.query(1600)[1] <= f.query(1600)[2]


def test_opening_is_valid_anchor_until_next_certified_mark():
    s = postopen(known_marks=()); f = freeze(s=s)
    assert s.anchor_ns == 1000
    assert f.points[0].observed and not f.points[-1].observed
    with pytest.raises(ValueError, match='certified|observed'): f.query(1100)


def test_anchor_age_is_an_explicit_decoder_coordinate():
    first = postopen()
    second = replace(first, event_cutoff_ns=1490)
    assert len(first.features) == 5
    assert first.features[:-1] == second.features[:-1]
    assert first.features[-1] == 200/86_400_000_000_000
    assert first.features[-1] != second.features[-1]


def test_global_cutoff_accepts_different_instrument_observation_times():
    a = postopen()
    b = replace(a, instrument='OTHER', known_marks=(PriceObservation(1400, 1401, 103., H),))
    assert a.event_cutoff_ns == b.event_cutoff_ns
    assert freeze(s=a).session.anchor_ns != freeze(s=b).session.anchor_ns


def test_cutoff_need_not_coincide_with_output_quantum():
    from forecast_heads import KnotPolicy
    s = postopen(event_cutoff_ns=1503, receive_cutoff_ns=1504, knot_policy=KnotPolicy(10, 8))
    f = freeze(s=s)
    assert f.points[-1].time_ns == s.close_ns
    assert all((p.time_ns-s.open_ns) % 10 == 0 for p in f.points if not p.observed)


def test_new_preopen_forecast_requires_causal_prior_close():
    with pytest.raises(ValueError, match='reference|prior close'):
        freeze(s=session(prior_close=None))
    valid = session(prior_close=PriceObservation(400, 401, 100., H))
    f = freeze(s=valid)
    assert f.session.prior_close.price == 100.
    assert freeze(s=replace(valid, prior_close=replace(valid.prior_close, price=101.))).digest != f.digest


@pytest.mark.parametrize('name', ['prior_close', 'opening', 'known_marks'])
def test_new_forecasts_reject_off_grid_certified_prices(name):
    s = postopen()
    change = (replace(s.known_marks[0], price=102.015),) if name == 'known_marks' else replace(getattr(s, name), price=100.015)
    with pytest.raises(ValueError, match='tick'):
        freeze(s=replace(s, **{name: change}))


def test_new_forecasts_accept_negative_prices_on_declared_grid():
    s = session(prior_close=PriceObservation(400, 401, -.01, H))
    assert freeze(s=s).session.prior_close.price == -.01


def test_hundred_second_stale_anchor_is_accepted():
    s = postopen()
    def scaled(mark):
        return replace(mark, event_ns=mark.event_ns*10**9, receive_ns=mark.receive_ns*10**9)
    s = replace(s, open_ns=s.open_ns*10**9, close_ns=s.close_ns*10**9,
        event_cutoff_ns=1400*10**9, receive_cutoff_ns=1501*10**9,
        prior_close=scaled(s.prior_close), opening=scaled(s.opening),
        known_marks=tuple(scaled(m) for m in s.known_marks))
    f = freeze(s=s)
    assert s.event_cutoff_ns-s.anchor_ns == 100*10**9
    assert all(p.observed or p.time_ns > s.event_cutoff_ns for p in f.points)


def test_native_rolling_refresh_accepts_postopen_stale_anchor(tmp_path):
    from test_native_forecast_refresh import build_refresh, update
    from forecast_artifact import NativeForecastArtifact
    bridge, sessions = build_refresh(tmp_path)
    t, s = sessions[0]
    sessions = ((t, replace(s, event_cutoff_ns=1500, receive_cutoff_ns=1501,
        opening=PriceObservation(1000, 1001, 99., H),
        known_marks=(PriceObservation(1300, 1301, 102., H),))),
        *((t, replace(s, event_cutoff_ns=1500, receive_cutoff_ns=1501)) for t, s in sessions[1:]))
    publications = update(bridge, sessions)
    assert len(publications) == len(sessions)
    p = publications[0].selected
    f = NativeForecastArtifact.from_payload(p.forecast_artifact, expected_digest=p.candidate_id)
    assert f.session.anchor_ns == 1300 and f.session.event_cutoff_ns == 1500


def test_anchor_age_reaches_gap_path_and_time_heads():
    import torch
    from test_forecast_heads import decoder
    m = decoder(); z = torch.ones(4, dtype=torch.float64)
    fresh = m.condition(z, (0., 1., 2., .01, 0.))
    stale = m.condition(z, (0., 1., 2., .01, .125))
    assert not torch.equal(m.gap(fresh), m.gap(stale))
    assert not torch.equal(m.path(fresh, .7), m.path(stale, .7))
    assert not torch.equal(m.next_time(fresh, .2, .1), m.next_time(stale, .2, .1))
