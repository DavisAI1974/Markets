"""quote_gate.py — pure quote-decision gate for the mm_passive cells.

Phase 1 of QUOTE_SERVICE_PLAN.md. The single entry point is

    evaluate(...) -> QuoteDecision

which decides, for one (asset, venue) on the latest classified chunk:

  - should_quote : may we post resting two-sided quotes right now?
  - spread_bps   : how wide to quote (base venue spread + risk wideners)
  - size_mult    : multiplier on the vol-target notional (cell-strength
                   driven; the caller multiplies this into the vol-target
                   multiplier, which is clipped to [0.5x, 2.0x] downstream)
  - pull_reason  : if quoting is blocked / an open quote must be pulled, why
  - notes        : human-readable trace of every path taken

DESIGN (plan §2) — OD signals are GATES + spread adjusters, NOT entry
signals. At 1s resolution venues are synchronous (cc=0.656 z=580), so
directional OD signals lose net-of-cost. The decision to quote rests on
regime + microstructure safety; the OD layer only widens spreads or pulls
quotes. The edge is maker-tier spread capture on EQUILIBRIUM, nothing else.

PURITY — no I/O, no global mutation, deterministic. Every OD-layer input
(recent_decoupling, leadlag_z_cb_leads_kr) is OPTIONAL: when the OD
snapshot is absent (odcore not merged, or realbins/ absent on the host)
the gate degrades gracefully and those paths simply never fire. Likewise
vpin_p90 None disables the VPIN hard stop rather than blocking on it.

FEE REALITY (verified 2026-06-08) — maker fees at the retail tier are:
Kraken 25 bps/leg, Coinbase 60 bps/leg, Bybit USDT-perp 2 bps/leg. A quote
only nets positive when the captured spread exceeds the round-trip (2-leg)
maker cost. On spot majors that gap is 10-50x — passive MM there is a
learning/comparison baseline, not a live profit candidate. Bybit USDT-perp
(4 bps round-trip) is the only venue where the math can close. Every
should_quote decision carries a `net spread capture @ maker` note so the
fee truth is visible in the decision itself, not buried downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --- regime / monitor / edge string literals (verified against source) -----
EQUILIBRIUM = "EQUILIBRIUM_TWO_SIDED"

_OI_BUILDING = {"OI_BUILDING_LONG", "OI_BUILDING_SHORT"}
_CB_PREMIUM_ACTIVE = {"CB_PREMIUM_HOT", "CB_PREMIUM_COLD"}
_BASIS_DIVERGENT = {"BASIS_DIVERGENT_HOT", "BASIS_DIVERGENT_COLD"}
_LIQ_BURST_PREFIX = "LIQ_BURST"  # LIQ_BURST_UP / LIQ_BURST_DOWN

_EDGE_WEAK = {"WEAK", "NEW"}
_SELF_TREND_FRAGILE = {"DECAYING", "FLIPPING"}

# --- venue policy (plan §2: "policy until calibrated by calibrate_spread.py")
# Base quoted spread (bps) per venue. MUST exceed the round-trip maker cost
# to have any chance of net-positive capture.
# Venue codes match the codebase convention: CB=Coinbase spot, KR=Kraken
# spot, BB=Bybit USDT-perp.
VENUE_BASE_SPREAD_BPS: dict[str, float] = {
    "KR": 12.0,      # Kraken spot — plan policy; does NOT cover 50 bps
    "CB": 15.0,      # Coinbase spot — plan policy; does NOT cover 120 bps
    "BB": 6.0,       # Bybit USDT-perp — clears the 4 bps round-trip + ~2 bps
}
_DEFAULT_BASE_SPREAD_BPS = 12.0

# Round-trip (2-leg) maker cost per venue, retail tier (bps). Used only to
# annotate the honest net-capture figure on each decision.
VENUE_ROUNDTRIP_MAKER_BPS: dict[str, float] = {
    "KR": 50.0,      # 25 bps/leg x 2
    "CB": 120.0,     # 60 bps/leg x 2
    "BB": 4.0,       # 2 bps/leg x 2
}


@dataclass
class QuoteDecision:
    """Outcome of one gate evaluation. See module docstring for fields."""
    should_quote: bool
    spread_bps: float
    size_mult: float
    pull_reason: Optional[str]
    notes: list[str] = field(default_factory=list)


def evaluate(
    *,
    asset: str,
    venue: str,
    regime: str,
    # --- microstructure / regime features (from ClassificationResult) ------
    vpin: float = 0.0,
    vpin_p90: Optional[float] = None,
    hawkes_multiplier: float = 1.0,
    event_multiplier: float = 1.0,
    cross_venue_multiplier: float = 1.0,
    # --- monitor states (from *_monitor.current_state_for(); may be None) --
    oi_state: Optional[str] = None,
    cb_premium_state: Optional[str] = None,
    basis_state: Optional[str] = None,
    liq_state: Optional[str] = None,
    # --- edge tracker (cell strength) --------------------------------------
    edge_intraday_strength: Optional[str] = None,
    edge_intraday_self_trend: Optional[str] = None,
    # --- OD layer (optional; absent => graceful degrade, no pull) ----------
    recent_decoupling: bool = False,
    leadlag_z_cb_leads_kr: Optional[float] = None,
) -> QuoteDecision:
    """Decide whether/how to quote mm_passive on (asset, venue) right now.

    Pure function. Every branch appends a note. See plan §2 for the rule
    table this implements.
    """
    notes: list[str] = []

    # ----- HARD STOPS: should_quote = False -------------------------------
    # Collected so the trace shows everything wrong, but the primary
    # pull_reason is the first (most fundamental) trigger.
    stops: list[str] = []

    if regime != EQUILIBRIUM:
        stops.append("regime_not_equilibrium")
        notes.append(f"hard-stop: regime {regime!r} != {EQUILIBRIUM}")
    if liq_state and liq_state.startswith(_LIQ_BURST_PREFIX):
        stops.append("liq_burst")
        notes.append(f"hard-stop: liquidation burst ({liq_state})")
    if basis_state in _BASIS_DIVERGENT:
        stops.append("basis_divergent")
        notes.append(f"hard-stop: spot-perp basis dislocated ({basis_state})")
    if recent_decoupling:
        stops.append("decoupling_recent")
        notes.append("hard-stop: recent (<=10min) structural decoupling for "
                     "this venue-pair")
    if event_multiplier < 0.7:
        stops.append("event_risk")
        notes.append(f"hard-stop: scheduled-event risk "
                     f"(event_multiplier={event_multiplier:.2f} < 0.70)")
    if vpin_p90 is not None and vpin > vpin_p90:
        stops.append("vpin_toxic")
        notes.append(f"hard-stop: order-flow toxicity "
                     f"(vpin={vpin:.3f} > p90={vpin_p90:.3f})")

    if stops:
        return QuoteDecision(
            should_quote=False,
            spread_bps=0.0,
            size_mult=0.0,
            pull_reason=stops[0],
            notes=notes,
        )

    # ----- We are in EQUILIBRIUM and microstructure is safe: QUOTE --------
    base = VENUE_BASE_SPREAD_BPS.get(venue, _DEFAULT_BASE_SPREAD_BPS)
    spread = base
    notes.append(f"quote: {venue} base spread {base:.1f} bps")

    # ----- Spread wideners (+bps) -----------------------------------------
    if oi_state in _OI_BUILDING:
        spread += 2.0
        notes.append(f"+2.0 bps: open-interest building ({oi_state})")
    if cb_premium_state in _CB_PREMIUM_ACTIVE:
        spread += 1.0
        notes.append(f"+1.0 bps: Coinbase premium active ({cb_premium_state})")
    if hawkes_multiplier < 1.0:
        spread += 1.0
        notes.append(f"+1.0 bps: Hawkes elevated "
                     f"(mult={hawkes_multiplier:.2f}<1.0) — quiet may break")
    if edge_intraday_self_trend in _SELF_TREND_FRAGILE:
        spread += 1.0
        notes.append(f"+1.0 bps: intraday edge {edge_intraday_self_trend}")
    if cross_venue_multiplier < 1.0:
        spread += 2.0
        notes.append(f"+2.0 bps: cross-venue disagreement "
                     f"(mult={cross_venue_multiplier:.2f}<1.0)")

    # ----- Size multipliers (cell strength, Adaptive-Markets framing) -----
    size_mult = 1.0
    if edge_intraday_strength in _EDGE_WEAK:
        size_mult *= 0.75
        notes.append(f"x0.75 size: intraday edge {edge_intraday_strength}")
    if edge_intraday_self_trend == "DECAYING":
        size_mult *= 0.75
        notes.append("x0.75 size: intraday self-trend DECAYING")
    # CB leads KR on BTC: resting passive on the lagging venue (KR) is
    # information-disadvantaged. OD bias only — multi-min hold, never timing.
    if (asset == "BTC" and venue == "KR"
            and leadlag_z_cb_leads_kr is not None
            and leadlag_z_cb_leads_kr > 3.0):
        size_mult *= 0.5
        notes.append(f"x0.50 size: CB leads KR-BTC (z={leadlag_z_cb_leads_kr:.1f}"
                     ">3) — passive on lagging venue")
    if (edge_intraday_strength == "STRONG"
            and edge_intraday_self_trend == "STRENGTHENING"):
        size_mult *= 1.25
        notes.append("x1.25 size: intraday edge STRONG + STRENGTHENING")

    # ----- Honest net-of-fee annotation -----------------------------------
    roundtrip = VENUE_ROUNDTRIP_MAKER_BPS.get(venue)
    if roundtrip is not None:
        net = spread - roundtrip
        notes.append(
            f"net spread capture @ maker: {net:+.1f} bps "
            f"(spread {spread:.1f} - round-trip fees {roundtrip:.1f})"
        )

    return QuoteDecision(
        should_quote=True,
        spread_bps=spread,
        size_mult=size_mult,
        pull_reason=None,
        notes=notes,
    )
