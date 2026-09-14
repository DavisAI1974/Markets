"""Native decoder software checks; no fitting or market data."""
import pytest
import torch
from forecast_heads import NativeForecastHeads, KnotPolicy


def decoder():
    torch.manual_seed(73)
    return NativeForecastHeads(4, 8).double().eval()


def test_gap_path_and_time_each_depend_on_native_state():
    m = decoder()
    z = torch.tensor([.2, -.3, .7, .1], dtype=torch.float64, requires_grad=True)
    values = [m.gap(z)[1], m.path(z, .63)[1], *m.next_time(z, .2, .1)]
    for value in values:
        grad, = torch.autograd.grad(value, z, retain_graph=True)
        assert torch.isfinite(grad).all() and grad.abs().sum() > 0
    other = z.detach() + .05
    assert not torch.equal(m.gap(z), m.gap(other))
    assert not torch.equal(m.path(z, .63), m.path(other, .63))
    assert not torch.equal(m.next_time(z, .2, .1), m.next_time(other, .2, .1))


def test_path_is_query_native_zero_anchored_and_not_endpoint_interpolation():
    m = decoder(); z = torch.ones(4, dtype=torch.float64)
    assert torch.equal(m.path(z, 0), torch.zeros(3, dtype=torch.float64))
    assert not torch.isclose(m.path(z, .37)[1], .37 * m.path(z, 1)[1], atol=1e-10, rtol=0)
    assert m.path(z, .4, anchor=.4, anchor_usd=-17)[1] == -17
    assert m.path(z, .7, anchor=.4, anchor_usd=-17)[1] != -17


def test_quantiles_are_ordered_and_tail_gradient_cannot_fit_median():
    m = decoder(); z = torch.ones(4, dtype=torch.float64, requires_grad=True)
    for result in (m.gap(z), m.path(z, .7)):
        assert result[0] < result[1] < result[2]
        m.zero_grad(); z.grad = None
        (result[0] + result[2]).backward()
        assert all(p.grad is None or not p.grad.any() for p in m.gap_median.parameters())
        assert all(p.grad is None or not p.grad.any() for p in m.path_median.parameters())
        assert z.grad is None or not z.grad.any()


def test_tail_only_optimizer_cannot_move_frozen_medians():
    m = decoder(); z = torch.ones(4, dtype=torch.float64)
    before = (m.gap(z)[1].item(), m.path(z, .7)[1].item())
    m.freeze_medians()
    optimizer = torch.optim.AdamW(m.parameters(), lr=.01)
    loss = m.gap(z)[0] + m.path(z, .7)[2]
    loss.backward(); optimizer.step()  # One synthetic regression step, no fitted artifact.
    assert (m.gap(z)[1].item(), m.path(z, .7)[1].item()) == before


def test_known_session_metadata_conditions_each_decoder():
    m = decoder(); z = torch.ones(4, dtype=torch.float64)
    first = m.condition(z, (1., 1., 2., .01))
    later = m.condition(z, (3., 1., 2., .01))
    assert not torch.equal(m.gap(first), m.gap(later))
    assert not torch.equal(m.path(first, .7), m.path(later, .7))
    assert not torch.equal(m.next_time(first, .2, .1), m.next_time(later, .2, .1))


def scripted(m, outputs):
    iterator = iter(outputs)
    m.next_time = lambda *args: torch.tensor(next(iterator), dtype=torch.float64)


def test_endogenous_fractional_times_stop_and_true_close():
    m = decoder(); z = torch.ones(4, dtype=torch.float64)
    policy = KnotPolicy(quantum_ns=10, max_interior=4)
    # Returned delay is a positive fraction of the remaining session.
    scripted(m, [(0.125, -1), (.2, -1), (.5, 1)])
    assert m.knots(z, duration_ns=1000, start_ns=0, policy=policy) == (0, 120, 300, 1000)
    scripted(m, [(.5, 1)])
    assert m.knots(z, duration_ns=1000, start_ns=400, policy=policy) == (400, 1000)


@pytest.mark.parametrize('delay', [0, -1, 1, 1.1, float('nan'), float('inf'), .001])
def test_invalid_or_unrepresentable_time_is_rejected_without_repair(delay):
    m = decoder(); scripted(m, [(delay, -1)])
    with pytest.raises(ValueError):
        m.knots(torch.ones(4, dtype=torch.float64), duration_ns=1000,
                start_ns=0, policy=KnotPolicy(10, 3))


def test_budget_exhaustion_is_not_silent_truncation():
    m = decoder(); scripted(m, [(.2, -1), (.2, -1)])
    with pytest.raises(ValueError, match='budget'):
        m.knots(torch.ones(4, dtype=torch.float64), duration_ns=1000,
                start_ns=0, policy=KnotPolicy(1, 1))


@pytest.mark.parametrize('state', [torch.ones(4), torch.ones(1, 4, dtype=torch.float64),
                                  torch.full((4,), float('nan'), dtype=torch.float64)])
def test_bad_representation_fails(state):
    with pytest.raises(ValueError): decoder().gap(state)


@pytest.mark.parametrize('query,anchor', [(-.1, 0), (1.1, 0), (.2, .3), (float('nan'), 0)])
def test_bad_query_fails(query, anchor):
    with pytest.raises(ValueError): decoder().path(torch.ones(4, dtype=torch.float64), query, anchor=anchor)
