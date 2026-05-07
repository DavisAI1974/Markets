"""
carry_analyzer.py — score funding-rate carry / basis arb opportunities
across the (asset, perp venue) cells where we have live funding-rate
state.

Strategy primer:
  When funding rate > spot lending rate by enough margin to absorb the
  fee leg + the spot lending cost, a delta-neutral pair earns the
  difference:

    long-spot (cost = spot lending rate at exchange)
    short-perp (income = perp funding rate, if longs are paying)

  P&L per funding cycle (8 hours):
    gross  = funding_rate                     # per 8h
    net    = funding_rate - spot_lending_rate - fee_round_trip
    APR    = net * 3 * 365                    # 3 funding cycles per day

  When funding rate < -threshold, the pair flips: short-spot + long-perp.
  Practically harder because not every venue lends spot short cheaply.

This module does NOT execute trades; it scores opportunities given a
snapshot of FundingMonitor. The matching paper-trade cell (one extra
leg with funding-cycle accrual) is deferred until forward_paper grows
multi-leg support — see HANDOFF section "Tier 3.3 deferred work".
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass


# Conservative defaults. Real-world carry desks would feed
# venue-specific borrow rates and round-trip fee schedules. These
# defaults are intentionally pessimistic so anything flagged here
# is a real opportunity even after slippage.
DEFAULT_SPOT_LENDING_APR = 0.05         # 5% APR cost of borrowing spot
DEFAULT_FEE_ROUND_TRIP_BPS = 10.0       # 10 bps round-trip fee (open + close, both legs)
FUNDING_CYCLES_PER_DAY = 3              # 8h cadence on the venues we monitor
MIN_NET_APR_FOR_OPPORTUNITY = 0.03      # 3% net APR threshold

# Funding states that map to a carry side. Coming from
# funding_monitor: "elevated_long"/"extreme_long" means longs are
# paying shorts (positive rate); the carry play is short the perp
# and long the spot.
LONG_PAYS_STATES = {"elevated_long", "extreme_long"}
SHORT_PAYS_STATES = {"elevated_short", "extreme_short"}


@dataclass
class CarryOpportunity:
    asset: str
    venue: str
    funding_state: str
    funding_rate: float          # raw rate per 8h cycle (e.g. 0.0001 = 1bp)
    funding_apr: float           # rate * cycles_per_day * 365
    spot_lending_apr: float
    fee_round_trip_bps: float
    gross_apr: float             # signed; positive when carry direction is profitable
    net_apr: float               # gross - lending - amortized_fees
    side: str                    # "short_perp_long_spot" | "long_perp_short_spot" | "none"
    is_opportunity: bool
    note: str


def _amortized_fee_apr(fee_bps: float, expected_hold_days: float = 1.0) -> float:
    """Translate a round-trip fee into an APR penalty given an expected
    hold horizon. A 10-bp round trip held for 1 day amortizes to
    36.5% APR — i.e. carry must clear that by spreading the same fee
    over many cycles. We default to 1-day expected hold so the
    `min_net_apr` threshold sees realistic break-evens."""
    if expected_hold_days <= 0:
        return 0.0
    return (float(fee_bps) / 1e4) * (365.0 / float(expected_hold_days))


def score_carry(asset: str, venue: str, funding_state: str,
                  funding_rate: float,
                  spot_lending_apr: float = DEFAULT_SPOT_LENDING_APR,
                  fee_round_trip_bps: float = DEFAULT_FEE_ROUND_TRIP_BPS,
                  expected_hold_days: float = 1.0,
                  min_net_apr: float = MIN_NET_APR_FOR_OPPORTUNITY
                  ) -> CarryOpportunity:
    """Return a CarryOpportunity for one (asset, venue, funding_state,
    funding_rate) tuple. is_opportunity is True iff funding state
    indicates one side is paying AND net_apr exceeds min_net_apr."""
    funding_apr = float(funding_rate) * FUNDING_CYCLES_PER_DAY * 365.0
    fee_apr = _amortized_fee_apr(fee_round_trip_bps, expected_hold_days)

    if funding_state in LONG_PAYS_STATES and funding_rate > 0:
        # Longs pay shorts: short the perp, long the spot, collect rate.
        gross_apr = funding_apr
        net_apr = gross_apr - spot_lending_apr - fee_apr
        side = "short_perp_long_spot"
    elif funding_state in SHORT_PAYS_STATES and funding_rate < 0:
        # Shorts pay longs: long the perp, short the spot.
        gross_apr = -funding_apr   # rate is negative; flip sign for "income to us"
        net_apr = gross_apr - spot_lending_apr - fee_apr
        side = "long_perp_short_spot"
    else:
        gross_apr = 0.0
        net_apr = 0.0
        side = "none"

    is_opp = bool(side != "none" and net_apr >= min_net_apr)
    if is_opp:
        note = (f"{side} on {asset}/{venue}: gross {gross_apr*100:+.1f}% APR, "
                f"net {net_apr*100:+.1f}% APR after {spot_lending_apr*100:.0f}% "
                f"lending + {fee_round_trip_bps:.0f}bp/{expected_hold_days:.0f}d "
                f"fee amortization.")
    elif side != "none":
        note = (f"{side} on {asset}/{venue} below threshold: "
                f"net {net_apr*100:+.1f}% APR < min {min_net_apr*100:.0f}%.")
    else:
        note = (f"{asset}/{venue} funding state {funding_state}; no carry "
                f"side active.")

    return CarryOpportunity(
        asset=asset, venue=venue,
        funding_state=funding_state,
        funding_rate=float(funding_rate),
        funding_apr=funding_apr,
        spot_lending_apr=spot_lending_apr,
        fee_round_trip_bps=fee_round_trip_bps,
        gross_apr=gross_apr,
        net_apr=net_apr,
        side=side,
        is_opportunity=is_opp,
        note=note,
    )


def evaluate_all_carry(funding_snapshot: dict[str, dict],
                         spot_lending_apr: float = DEFAULT_SPOT_LENDING_APR,
                         fee_round_trip_bps: float = DEFAULT_FEE_ROUND_TRIP_BPS,
                         expected_hold_days: float = 1.0,
                         min_net_apr: float = MIN_NET_APR_FOR_OPPORTUNITY
                         ) -> dict:
    """Score every (asset, venue) entry in a FundingMonitor snapshot.
    Returns:
      {
        "computed_utc": ISO ts,
        "opportunities": [CarryOpportunity-as-dict, ...],   # only is_opportunity=True
        "all_evaluated": [CarryOpportunity-as-dict, ...],   # full list, for diagnostics
        "n_opportunities": int,
      }
    """
    out_all = []
    for key, entry in (funding_snapshot or {}).items():
        try:
            asset, venue = key.split("/", 1)
        except ValueError:
            continue
        funding_state = entry.get("current_state") or "normal"
        funding_rate = float(entry.get("rate", 0.0) or 0.0)
        opp = score_carry(
            asset=asset, venue=venue,
            funding_state=funding_state,
            funding_rate=funding_rate,
            spot_lending_apr=spot_lending_apr,
            fee_round_trip_bps=fee_round_trip_bps,
            expected_hold_days=expected_hold_days,
            min_net_apr=min_net_apr,
        )
        out_all.append(asdict(opp))
    opps = [d for d in out_all if d["is_opportunity"]]
    return {
        "computed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "opportunities": opps,
        "all_evaluated": out_all,
        "n_opportunities": len(opps),
    }
