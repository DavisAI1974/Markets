"""In-flight promotion: shadow -> bank attribution when winning shape emerges.

The defensive layer (wilson + protective) rejects obvious losers at entry. This
module identifies winners IN FLIGHT, after the trade has shown its shape, and
flips PnL attribution from shadow to bank for the trades that prove themselves.

Signals (from _analysis_historical_rt_trade_shapes_20260523/
HISTORICAL_RT_TRADE_SHAPE_SIGNALS.md, 67,728-trade research over the May 4-13
historic RT bins):

    hold_min_ge_runners @ 60      85.64% precision   10.3x lift   +22.0 median net bps
    reached_20bps_within_30m      67.96% precision    8.2x lift    +2.3 median net bps

Entry-time signals all sit at 1.0-1.3x lift in the same population. The signal
lives in the trade's path, not in its entry features.

Quality gate (filters weak winners from strong winners — both ramp into
hold_min_ge_runners; weak ones stall under +$3 final PnL):

    net_bps_per_min >= 0.3 at promotion check
    Strong winners observed at 0.7 bps/min and rising.
    Weak winners stall at -0.09 bps/min median.

Constants are derived from precision/lift research and economic geometry, NOT
tuned to backtest tape. Autoresearch may sweep `net_bps_per_min_floor` later as
the natural tunable; the two signal thresholds (60 min hold, 20 bps within 30 min)
are statistical breakpoints from the analysis.

Mechanism: at each per-tick check on an open trade (in close_open_for_status's
loop), call update_in_flight_tracking, then should_promote. If promotion fires
on a shadow trade, apply_promotion flips bank_allocated_notional_usd to equal
real_mock_notional_usd. At close, _pnl_bank_fraction returns 1.0 for promoted
trades, so bank_realized_pnl = realized_pnl in full.
"""

from __future__ import annotations

from typing import Any


# Signal thresholds — from HISTORICAL_RT_TRADE_SHAPE_SIGNALS.md, not tape-tuned.
HOLD_MIN_PROMOTE_THRESHOLD = 60.0       # minutes. hold_min_ge_runners @ 60 = 85.6% precision.
REACHED_NET_BPS_THRESHOLD = 20.0         # bps net. reached_20bps_within_30m = 68% precision.
REACHED_WITHIN_MINUTES = 30.0            # window for the reached signal.

# Quality floor — separates strong winners (ramping at ~0.7 bps/min) from weak
# winners (stall at ~0.1 bps/min). 0.3 is the conservative midpoint.
NET_BPS_PER_MIN_QUALITY_FLOOR = 0.3

# Fee-cover threshold (used for first_ts_fee_covered tracking, not directly for
# promotion). 0 bps net means costs are recovered.
FEE_COVER_NET_BPS_THRESHOLD = 0.0


def update_in_flight_tracking(trade: dict[str, Any], net_bps: float, ts: float) -> None:
    """Per-tick monotonic state. Call ONCE per tick on each open trade, BEFORE
    promotion check.

    Adds three monotonic fields to the trade dict (all guard against stale state
    via .get with None default — pnl-review anti-pattern: sticky flags). Because
    these fields are strictly monotonic event recorders (first-time-X), they do
    not lock out reversals.

        max_net_unrealized_bps   - running max of net_bps over the trade
        first_ts_net_bps_ge_20   - timestamp net_bps first reached +20
        first_ts_fee_covered     - timestamp net_bps first reached 0 (fees covered)
    """
    prev_max = trade.get("max_net_unrealized_bps")
    if prev_max is None or net_bps > float(prev_max):
        trade["max_net_unrealized_bps"] = float(net_bps)

    if trade.get("first_ts_net_bps_ge_20") is None and net_bps >= REACHED_NET_BPS_THRESHOLD:
        trade["first_ts_net_bps_ge_20"] = float(ts)

    if trade.get("first_ts_fee_covered") is None and net_bps >= FEE_COVER_NET_BPS_THRESHOLD:
        trade["first_ts_fee_covered"] = float(ts)


def should_promote(
    trade: dict[str, Any],
    net_bps: float,
    elapsed_min: float,
    ts: float,
) -> dict[str, Any]:
    """Decide whether to promote a shadow trade to bank attribution.

    Returns dict: {promote: bool, reason: str, signal: str | None}.

    Decision tree:
        1. Already bank (bank_allocated_notional_usd > 0) -> no-op.
        2. Quality gate: net_bps_per_min < 0.3 -> no promote.
        3. Signal A: elapsed_min >= 60 AND net_bps > 0 -> promote (hold_min_ge_runners).
        4. Signal B: first_ts_net_bps_ge_20 within 30 min of entry -> promote
           (reached_20bps_within_30m).
        5. Else no promote.

    Both signals require the quality gate to pass. Both are derived from
    precision/lift research; neither is tape-tuned.
    """
    # Already promoted (or admitted at bank from entry) -- no-op.
    if float(trade.get("bank_allocated_notional_usd") or 0.0) > 0.0:
        return {"promote": False, "reason": "already_bank_attributed", "signal": None}

    # Floor for elapsed_min so net_bps_per_min division is stable.
    if elapsed_min < 1.0:
        return {"promote": False, "reason": "elapsed_lt_1min", "signal": None}

    net_bps_per_min = float(net_bps) / float(elapsed_min)

    # Quality gate -- filters weak/stalled winners.
    if net_bps_per_min < NET_BPS_PER_MIN_QUALITY_FLOOR:
        return {
            "promote": False,
            "reason": (
                f"quality_floor_net_bps_per_min_{net_bps_per_min:.3f}"
                f"_lt_{NET_BPS_PER_MIN_QUALITY_FLOOR}"
            ),
            "signal": None,
        }

    # Signal A: hold_min >= 60 (85.6% precision, 10.3x lift, +22 bps median net).
    if elapsed_min >= HOLD_MIN_PROMOTE_THRESHOLD and net_bps > 0.0:
        return {
            "promote": True,
            "reason": (
                f"hold_min_ge_60:elapsed_{elapsed_min:.1f}min_net_{net_bps:.1f}bps"
                f"_quality_{net_bps_per_min:.2f}"
            ),
            "signal": "hold_min_ge_60",
        }

    # Signal B: reached_20bps_within_30m (68.0% precision, 8.2x lift, +2.3 bps median net).
    first_ts_20 = trade.get("first_ts_net_bps_ge_20")
    if first_ts_20 is not None:
        ts_entry = float(trade.get("ts_utc") or 0.0)
        if ts_entry > 0.0:
            mins_to_20 = (float(first_ts_20) - ts_entry) / 60.0
            if mins_to_20 <= REACHED_WITHIN_MINUTES:
                return {
                    "promote": True,
                    "reason": (
                        f"reached_20bps_within_30m:mins_to_20_{mins_to_20:.1f}"
                        f"_quality_{net_bps_per_min:.2f}"
                    ),
                    "signal": "reached_20bps_within_30m",
                }

    return {"promote": False, "reason": "no_signal_fired", "signal": None}


def apply_promotion(
    trade: dict[str, Any],
    ts: float,
    signal: str,
    reason: str,
) -> None:
    """Flip shadow -> bank attribution. Sets bank_allocated_notional_usd equal to
    real_mock_notional_usd so _pnl_bank_fraction returns 1.0 at close time and
    the full realized PnL is attributed to bank.

    Audit-trail fields capture which signal fired and when, for after-the-fact
    PnL diagnosis.
    """
    target_notional = float(trade.get("real_mock_notional_usd") or 0.0)
    if target_notional <= 0.0:
        # No actual position to attribute. (Paper-only trade or zero-size error.)
        return

    trade["bank_allocated_notional_usd"] = target_notional
    trade["pnl_accounting_role"] = "bank_allocated"
    trade["in_flight_promoted_at_ts"] = float(ts)
    trade["in_flight_promoted_signal"] = signal
    trade["in_flight_promoted_reason"] = reason


def check_and_promote_if_eligible(
    trade: dict[str, Any],
    net_bps: float,
    elapsed_min: float,
    ts: float,
) -> dict[str, Any] | None:
    """Convenience composite: update tracking, decide, apply if promote=True.

    Returns the decision dict if a promotion fired (with promote=True), or None
    if no promotion happened. Caller can log or audit when non-None.
    """
    update_in_flight_tracking(trade, net_bps, ts)
    decision = should_promote(trade, net_bps, elapsed_min, ts)
    if decision["promote"]:
        apply_promotion(trade, ts, decision["signal"], decision["reason"])
        return decision
    return None
