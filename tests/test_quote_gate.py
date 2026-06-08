"""Tests for backend/quote_gate.py (Phase 1, QUOTE_SERVICE_PLAN.md §3).

Runnable two ways:
    python -m pytest tests/test_quote_gate.py
    python tests/test_quote_gate.py        # standalone, no pytest needed

The standalone runner exists because the host test harness isn't stood up
yet (§1.5 backend not deployed); this lets the gate be verified locally
with only the stdlib.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from quote_gate import (  # noqa: E402
    EQUILIBRIUM,
    VENUE_BASE_SPREAD_BPS,
    evaluate,
)


def _baseline(**overrides):
    """A benign EQUILIBRIUM call that should quote at base spread, size 1.0."""
    kw = dict(asset="BTC", venue="BYBIT", regime=EQUILIBRIUM)
    kw.update(overrides)
    return evaluate(**kw)


def test_baseline_quotes_at_base_spread():
    d = _baseline()
    assert d.should_quote is True
    assert d.pull_reason is None
    assert d.spread_bps == VENUE_BASE_SPREAD_BPS["BYBIT"]
    assert d.size_mult == 1.0
    assert d.notes  # always traced


def test_non_equilibrium_blocks():
    d = _baseline(regime="WHALE_UP")
    assert d.should_quote is False
    assert d.pull_reason == "regime_not_equilibrium"
    assert d.spread_bps == 0.0 and d.size_mult == 0.0


def test_liq_burst_blocks():
    d = _baseline(liq_state="LIQ_BURST_DOWN")
    assert d.should_quote is False
    assert d.pull_reason == "liq_burst"


def test_basis_divergent_blocks():
    assert _baseline(basis_state="BASIS_DIVERGENT_HOT").should_quote is False
    assert _baseline(basis_state="BASIS_DIVERGENT_COLD").should_quote is False
    # CLEARED is benign
    assert _baseline(basis_state="BASIS_DIVERGENT_CLEARED").should_quote is True


def test_recent_decoupling_blocks():
    d = _baseline(recent_decoupling=True)
    assert d.should_quote is False
    assert d.pull_reason == "decoupling_recent"


def test_event_risk_blocks():
    assert _baseline(event_multiplier=0.69).should_quote is False
    assert _baseline(event_multiplier=0.70).should_quote is True  # boundary


def test_vpin_toxicity():
    # above calibrated p90 -> block
    assert _baseline(vpin=0.9, vpin_p90=0.8).should_quote is False
    # below p90 -> fine
    assert _baseline(vpin=0.7, vpin_p90=0.8).should_quote is True
    # no calibration available -> hard stop disabled (graceful degrade)
    assert _baseline(vpin=0.99, vpin_p90=None).should_quote is True


def test_oi_building_widens():
    base = VENUE_BASE_SPREAD_BPS["BYBIT"]
    assert _baseline(oi_state="OI_BUILDING_LONG").spread_bps == base + 2.0
    assert _baseline(oi_state="OI_BUILDING_SHORT").spread_bps == base + 2.0
    # benign OI states do not widen
    assert _baseline(oi_state="OI_CLEARED").spread_bps == base


def test_cb_premium_widens():
    base = VENUE_BASE_SPREAD_BPS["BYBIT"]
    assert _baseline(cb_premium_state="CB_PREMIUM_HOT").spread_bps == base + 1.0


def test_hawkes_elevated_widens():
    base = VENUE_BASE_SPREAD_BPS["BYBIT"]
    assert _baseline(hawkes_multiplier=0.8).spread_bps == base + 1.0
    assert _baseline(hawkes_multiplier=1.0).spread_bps == base  # boundary


def test_cross_venue_disagreement_widens():
    base = VENUE_BASE_SPREAD_BPS["BYBIT"]
    assert _baseline(cross_venue_multiplier=0.5).spread_bps == base + 2.0


def test_decaying_self_trend_widens_and_shrinks():
    base = VENUE_BASE_SPREAD_BPS["BYBIT"]
    d = _baseline(edge_intraday_self_trend="DECAYING")
    assert d.spread_bps == base + 1.0   # widened
    assert d.size_mult == 0.75          # and downsized


def test_flipping_self_trend_widens_only():
    base = VENUE_BASE_SPREAD_BPS["BYBIT"]
    d = _baseline(edge_intraday_self_trend="FLIPPING")
    assert d.spread_bps == base + 1.0
    assert d.size_mult == 1.0           # FLIPPING widens but does not downsize


def test_weak_edge_downsizes():
    assert _baseline(edge_intraday_strength="WEAK").size_mult == 0.75
    assert _baseline(edge_intraday_strength="NEW").size_mult == 0.75


def test_strong_strengthening_upsizes():
    d = _baseline(edge_intraday_strength="STRONG",
                  edge_intraday_self_trend="STRENGTHENING")
    assert d.size_mult == 1.25


def test_leadlag_only_btc_kr():
    # CB-leads-KR penalty applies to BTC on KR only
    d = evaluate(asset="BTC", venue="KR", regime=EQUILIBRIUM,
                 leadlag_z_cb_leads_kr=5.0)
    assert d.size_mult == 0.5
    # not on Bybit, not on ETH, not when z<=3, not when absent
    assert _baseline(leadlag_z_cb_leads_kr=5.0).size_mult == 1.0  # BYBIT
    assert evaluate(asset="ETH", venue="KR", regime=EQUILIBRIUM,
                    leadlag_z_cb_leads_kr=5.0).size_mult == 1.0
    assert evaluate(asset="BTC", venue="KR", regime=EQUILIBRIUM,
                    leadlag_z_cb_leads_kr=2.0).size_mult == 1.0
    assert evaluate(asset="BTC", venue="KR", regime=EQUILIBRIUM,
                    leadlag_z_cb_leads_kr=None).size_mult == 1.0


def test_venue_base_spreads_distinct():
    assert _baseline(venue="KR").spread_bps == VENUE_BASE_SPREAD_BPS["KR"]
    assert _baseline(venue="CB").spread_bps == VENUE_BASE_SPREAD_BPS["CB"]
    assert _baseline(venue="BYBIT").spread_bps == VENUE_BASE_SPREAD_BPS["BYBIT"]


def test_net_capture_note_is_honest():
    # Bybit perp: 6 base - 4 round-trip = +2 bps (the math can close)
    note = "\n".join(_baseline(venue="BYBIT").notes)
    assert "net spread capture @ maker: +2.0 bps" in note
    # Kraken spot: 12 base - 50 round-trip = -38 bps (structurally negative)
    note_kr = "\n".join(_baseline(venue="KR").notes)
    assert "net spread capture @ maker: -38.0 bps" in note_kr


def test_graceful_degradation_no_od_inputs():
    # With no OD/monitor/calibration inputs at all, a benign EQ chunk still
    # quotes cleanly — no path requires the OD layer to exist.
    d = evaluate(asset="ETH", venue="BYBIT", regime=EQUILIBRIUM)
    assert d.should_quote is True
    assert d.pull_reason is None


def test_multiple_hard_stops_report_primary_but_trace_all():
    d = _baseline(regime="WHALE_UP", liq_state="LIQ_BURST_UP",
                  recent_decoupling=True)
    assert d.should_quote is False
    assert d.pull_reason == "regime_not_equilibrium"  # most fundamental first
    joined = "\n".join(d.notes)
    assert "liquidation burst" in joined
    assert "decoupling" in joined


# --- standalone runner (no pytest) -----------------------------------------
if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
