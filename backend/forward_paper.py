"""
forward_paper.py — auto paper-trade emitter for the candidate cells under
out-of-sample evaluation (per HANDOFF_PHASE1_5_RESULTS.md fifth pass).

Cells currently wired (chunk-level, runs in the same poll loop):
  - eth_kr_nascent_up_momo : ETH KR WHALE_NASCENT_UP -> long-momentum
  - eth_kr_herd_up_volq3_fade : ETH KR HERD_UP with volume-z >= 0.67
                               (proxy for vol-Q3) -> short-fade

Cells deferred (not wired here):
  - btc_perp_lead : BN-perp 1-min imbalance leads KR-spot. Lives on the
    per-second perp stream, not the chunk-level path; needs a separate
    minute-level evaluator before we can paper-trade it.

Each opened trade is appended to backend_practice_trades.jsonl with
auto=True and a cell_id tag so the existing /api/practice-trades
endpoint surfaces them alongside manual trades, and they show up in
aggregate win-rate / realized-pnl stats. Closure runs as a sweep at the
top of every poll cycle: anything with status='open' AND auto=True AND
elapsed >= hold_minutes gets exit_price stamped at the current bid/ask
and realized P&L computed (same fee math as the manual-close path).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class CellSpec:
    cell_id: str
    asset: str
    venue: str
    side: str               # "buy" (long-momentum) or "sell" (short-fade)
    notional_usd: float     # fixed notional per opened trade. Vol-target
                            # sizing (Tier 3.2) scales by VOL_TARGET /
                            # realized_vol at open time, clipped to
                            # [0.5x, 2.0x].
    hold_minutes: float     # auto-close after this many minutes. TODO:
                            # empirically calibrate per cell once
                            # backend_practice_trades.jsonl accumulates
                            # ~50+ closed auto trades per cell. Method:
                            # for each cell, sweep horizons (1, 5, 10,
                            # 30, 60 min) on the closed-trades realized
                            # P&L; pick the horizon maximizing adjusted
                            # IC. Until then, 10 min is a chunk-aligned
                            # default that matches the existing 30-bar
                            # chunk window on 1-min bars.
    note: str
    # Predicate: returns True iff the cell should fire on this chunk.
    # Args: regime (str), feat (MarketFeatures-like), chunk (MarketChunk-like).
    predicate: Callable[[str, object, object], bool]
    kind: str = "directional"  # "directional" (default; aggressive marketable
                               # entry/exit) or "mm_passive" (passive quoting:
                               # entry on the resting side of the book, exit
                               # on the opposite side, earning spread minus
                               # round-trip fees instead of paying it).


def _is_eth_kr_nascent_up(regime: str, feat: object, chunk: object) -> bool:
    return regime == "WHALE_NASCENT_UP"


def _is_eth_kr_herd_up_volq3(regime: str, feat: object, chunk: object) -> bool:
    if regime != "HERD_UP":
        return False
    vz = getattr(feat, "volume_zscore", 0.0)
    # ~Q3 cut on a standard-normal corpus z-score; matches the
    # sub-window finding (recent_pass5: r=-0.20 within vol-Q3 for ETH
    # KR HERD_UP at n=168, p=0.008).
    return vz is not None and float(vz) >= 0.67


def _is_eth_kr_whale_up(regime: str, feat: object, chunk: object) -> bool:
    return regime == "WHALE_UP"


def _is_equilibrium(regime: str, feat: object, chunk: object) -> bool:
    """MM cells fire on the modal regime — chunks where there's no
    directional edge but the spread is alive. Pass-6 confirms this is
    61-78% of all chunks across both assets and venues."""
    return regime == "EQUILIBRIUM_TWO_SIDED"


CELLS: list[CellSpec] = [
    CellSpec(
        cell_id="eth_kr_nascent_up_momo",
        asset="ETH", venue="KR",
        side="buy",
        notional_usd=1000.0,
        hold_minutes=10.0,
        note="forward paper: ETH KR WHALE_NASCENT_UP momentum (cell pass 5: "
             "r=+0.21 over 30d, r=+0.58 in recent 9d)",
        predicate=_is_eth_kr_nascent_up,
    ),
    CellSpec(
        cell_id="eth_kr_herd_up_volq3_fade",
        asset="ETH", venue="KR",
        side="sell",
        notional_usd=1000.0,
        hold_minutes=10.0,
        note="forward paper: ETH KR HERD_UP fade within vol-Q3 (cell pass 5: "
             "r=-0.20 at n=168, p=0.008)",
        predicate=_is_eth_kr_herd_up_volq3,
    ),
    # Pass-8 finding: KR-ETH WHALE_UP n=65 r=-0.309 BH q=0.029. First
    # BH-significant cell since Pass-3. Plain WHALE_UP fade — short
    # against the upward whale pressure, exit at next chunk close.
    # Hold tight because the WHALE regime can flip quickly; the
    # multi-horizon edge tracker will also fire its own edge_eth_kr_
    # whale_up_*_fade trades on top of this cell as supplementary
    # confirmation.
    CellSpec(
        cell_id="eth_kr_whale_up_fade",
        asset="ETH", venue="KR",
        side="sell",
        notional_usd=1000.0,
        hold_minutes=10.0,
        note="forward paper: ETH KR WHALE_UP fade (Pass-8: r=-0.309 n=65 "
             "BH q=0.029; first BH-significant cell since Pass-3)",
        predicate=_is_eth_kr_whale_up,
    ),
    # Tier 3.1 EQUILIBRIUM market-making cells. One per (asset, venue) so
    # each cell's realized P&L tracks the captured-spread minus
    # round-trip-fees on its own venue. Hold short (5 min) so the cell
    # exits before the regime drifts off EQUILIBRIUM; the actual real-
    # money equivalent would also exit on regime flip via SSE rather
    # than time-out.
    CellSpec(
        cell_id="eth_kr_eq_mm_passive",
        asset="ETH", venue="KR", side="buy", kind="mm_passive",
        notional_usd=1000.0, hold_minutes=5.0,
        note="forward paper: ETH KR EQUILIBRIUM passive-quote MM. "
             "Entry rests on bid; exit rests on ask; earns spread "
             "minus 2 fee legs while regime persists.",
        predicate=_is_equilibrium,
    ),
    CellSpec(
        cell_id="eth_cb_eq_mm_passive",
        asset="ETH", venue="CB", side="buy", kind="mm_passive",
        notional_usd=1000.0, hold_minutes=5.0,
        note="forward paper: ETH CB EQUILIBRIUM passive-quote MM.",
        predicate=_is_equilibrium,
    ),
    CellSpec(
        cell_id="btc_kr_eq_mm_passive",
        asset="BTC", venue="KR", side="buy", kind="mm_passive",
        notional_usd=1000.0, hold_minutes=5.0,
        note="forward paper: BTC KR EQUILIBRIUM passive-quote MM.",
        predicate=_is_equilibrium,
    ),
    CellSpec(
        cell_id="btc_cb_eq_mm_passive",
        asset="BTC", venue="CB", side="buy", kind="mm_passive",
        notional_usd=1000.0, hold_minutes=5.0,
        note="forward paper: BTC CB EQUILIBRIUM passive-quote MM.",
        predicate=_is_equilibrium,
    ),
]


_PRACTICE_FEE_BPS = 25.0


# ---------------------------------------------------------------------------
# Tier 3.3 — funding-rate carry / basis-arb paper trades.
#
# Triggered by funding-monitor alerts (NOT regime classification), so
# the surface differs from CellSpec: open on FUNDING_OVERLEVERED_{LONG,
# SHORT} (one trade per asset, per perp venue, deduped), close on
# FUNDING_CLEARED for that key OR when max_hold_minutes elapses.
#
# Trade represents the perp leg of an assumed delta-neutral pair. We
# don't simulate the spot hedge; we just credit funding income at
# close (= |rate_at_open| × notional × elapsed_hours / 8) and ignore
# the perp price-drift P&L on the assumption that the spot leg
# cancels it perfectly. That's optimistic — real basis variance eats
# into P&L — but adequate for forward paper accounting until we wire
# multi-leg infrastructure.
# ---------------------------------------------------------------------------


@dataclass
class CarryCellSpec:
    cell_id: str
    asset: str
    perp_venue: str          # "Binance" or "Bybit"
    notional_usd: float = 1000.0
    max_hold_minutes: float = 480.0   # one funding cycle


CARRY_CELLS: list[CarryCellSpec] = [
    CarryCellSpec(cell_id="btc_carry_bn",  asset="BTC", perp_venue="Binance"),
    CarryCellSpec(cell_id="btc_carry_bb",  asset="BTC", perp_venue="Bybit"),
    CarryCellSpec(cell_id="eth_carry_bn",  asset="ETH", perp_venue="Binance"),
    CarryCellSpec(cell_id="eth_carry_bb",  asset="ETH", perp_venue="Bybit"),
]


def find_carry_spec(asset: str, perp_venue: str) -> Optional[CarryCellSpec]:
    for c in CARRY_CELLS:
        if c.asset == asset and c.perp_venue == perp_venue:
            return c
    return None


def open_carry_trade(spec: CarryCellSpec, funding_rate_at_open: float,
                       perp_price: float) -> dict:
    """Open a paper carry trade. Side determined by funding rate sign:
       rate > 0  -> short perp (longs pay shorts; we receive funding)
       rate < 0  -> long perp  (shorts pay longs; we receive funding)
    Trade represents the perp leg of an assumed delta-neutral pair."""
    side = "sell" if funding_rate_at_open > 0 else "buy"
    qty = spec.notional_usd / perp_price if perp_price > 0 else 0.0
    notional = perp_price * qty
    fee_usd = notional * (_PRACTICE_FEE_BPS / 10000.0)
    return {
        "intent_id": str(uuid.uuid4())[:12],
        "asset": spec.asset, "venue": spec.perp_venue,
        "side": side,
        "kind": "carry_perp_leg",
        "price": float(perp_price),
        "qty": float(qty),
        "notional": float(notional),
        "note": (f"forward paper: {spec.asset} {spec.perp_venue} carry "
                 f"({side} perp leg, funding="
                 f"{funding_rate_at_open*1e4:+.2f}bps/8h)"),
        "ts_utc": time.time(),
        "practice": True, "auto": True,
        "cell_id": spec.cell_id,
        "kind_short": "carry",
        "status": "open",
        "fill_price": float(perp_price),
        "fees_usd": float(fee_usd),
        "fee_bps": _PRACTICE_FEE_BPS,
        "exit_price": 0.0,
        "exit_ts_utc": 0.0,
        "realized_pnl_usd": 0.0,
        "hold_minutes": float(spec.max_hold_minutes),
        "funding_rate_at_open": float(funding_rate_at_open),
        "base_notional_usd": float(spec.notional_usd),
    }


def close_carry_trade(trade: dict, perp_price_now: float,
                        close_reason: str = "funding_cleared") -> None:
    """Close the perp leg. Funding income accrues at the rate captured
    at open, scaled by elapsed hours / 8. Delta-neutral assumption
    cancels the perp price-drift P&L against the (un-modeled) spot leg.
    Realized P&L = funding_income - 2 × fees."""
    qty = float(trade.get("qty", 0.0))
    rate_at_open = float(trade.get("funding_rate_at_open", 0.0))
    elapsed_s = max(0.0, time.time() - float(trade.get("ts_utc", 0.0)))
    elapsed_hours = elapsed_s / 3600.0
    notional_out = perp_price_now * qty
    exit_fee = notional_out * (_PRACTICE_FEE_BPS / 10000.0)
    notional_at_open = float(trade.get("notional", 0.0))
    # Funding income = |rate| × avg notional × n_funding_cycles_elapsed.
    # Average leg notional approximates avg(open, exit) to soak up some
    # price drift; conservative.
    avg_notional = 0.5 * (notional_at_open + notional_out)
    n_cycles = elapsed_hours / 8.0
    funding_income = abs(rate_at_open) * avg_notional * n_cycles
    realized = funding_income - float(trade.get("fees_usd", 0.0)) - exit_fee
    trade["status"] = "closed"
    trade["exit_price"] = float(perp_price_now)
    trade["exit_ts_utc"] = time.time()
    trade["fees_usd"] = float(trade.get("fees_usd", 0.0)) + float(exit_fee)
    trade["realized_pnl_usd"] = float(realized)
    trade["funding_income_usd"] = float(funding_income)
    trade["elapsed_hours"] = float(elapsed_hours)
    trade["close_reason"] = str(close_reason)


def is_carry_trade(trade: dict) -> bool:
    return (trade.get("status") == "open"
              and trade.get("kind_short") == "carry")

# Vol-target sizing (Tier 3.2). Chunk realized_vol is the std of bar
# log-returns over the chunk window. The "target" is the realized_vol
# value at which the multiplier returns 1.0 — set per-(asset, venue)
# from vol_target_calibration.json (output of calibrate_vol_target.py
# = median realized_vol over the corpus). Falls back to a global
# default when the calibration entry is missing.
#
# TODO recalibration: re-run `python calibrate_vol_target.py` any
# time the corpus grows ≥2× (currently anchored on the 30d Pass-6
# corpus). See TODO.md "Recalibrations to re-run as the corpus grows".
VOL_TARGET = 0.0004
VOL_MULT_MIN = 0.5
VOL_MULT_MAX = 2.0

_VOL_TARGET_CALIB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "vol_target_calibration.json")
_vol_target_table: dict[str, float] = {}
_vol_target_loaded: bool = False


_VENUE_LABEL_MAP = {
    "CB": "Coinbase",
    "KR": "Kraken",
    "BN": "Binance",
    "BB": "Bybit",
}


def _load_vol_target_calibration() -> None:
    """Read vol_target_calibration.json into _vol_target_table once.
    Resolved keys are 'ETH/Coinbase'-style (matching the calibrator)
    AND short-form 'ETH/CB' (matching CellSpec.venue). Errors are
    non-fatal."""
    global _vol_target_loaded, _vol_target_table
    if _vol_target_loaded:
        return
    _vol_target_loaded = True
    if not os.path.exists(_VOL_TARGET_CALIB_PATH):
        return
    try:
        with open(_VOL_TARGET_CALIB_PATH) as f:
            payload = json.load(f)
        for label, entry in (payload.get("calibration") or {}).items():
            tgt = float(entry.get("vol_target", VOL_TARGET))
            _vol_target_table[label] = tgt
            try:
                asset, full_venue = label.split("/", 1)
                short_venue = next((k for k, v in _VENUE_LABEL_MAP.items()
                                     if v == full_venue), full_venue)
                _vol_target_table[f"{asset}/{short_venue}"] = tgt
            except ValueError:
                pass
    except Exception as e:
        print(f"[vol-target] could not parse {_VOL_TARGET_CALIB_PATH}: "
              f"{e}; using global default {VOL_TARGET}", flush=True)


def _target_for(asset: Optional[str], venue: Optional[str]) -> float:
    _load_vol_target_calibration()
    if asset and venue:
        key = f"{asset}/{venue}"
        if key in _vol_target_table:
            return _vol_target_table[key]
    return VOL_TARGET


def vol_target_multiplier(realized_vol: float,
                            asset: Optional[str] = None,
                            venue: Optional[str] = None,
                            target: Optional[float] = None,
                            lo: float = VOL_MULT_MIN,
                            hi: float = VOL_MULT_MAX) -> float:
    """Inverse-vol sizing: notional ∝ target / realized_vol, clipped.
    A chunk at exactly `target` returns 1.0; quieter chunks size up
    (capped at `hi`); louder chunks size down (floored at `lo`).

    Pass (asset, venue) to use the per-cell calibrated target from
    vol_target_calibration.json. Pass `target` directly to override.
    Falls back to the global VOL_TARGET default when neither is
    available."""
    if realized_vol is None or realized_vol <= 1e-9:
        return 1.0
    if target is None:
        target = _target_for(asset, venue)
    raw = float(target) / float(realized_vol)
    return max(float(lo), min(float(hi), raw))


def find_matching_cells(asset: str, venue: str, regime: str,
                          feat: object, chunk: object) -> list[CellSpec]:
    out = []
    for cell in CELLS:
        if cell.asset != asset or cell.venue != venue:
            continue
        try:
            if cell.predicate(regime, feat, chunk):
                out.append(cell)
        except Exception:
            # Predicate failure shouldn't kill the poll loop.
            continue
    return out


def entry_price_for_cell(cell: CellSpec, bid: float, ask: float, mid: float
                            ) -> float:
    """Return the simulated fill price for opening this cell's position.
    Directional cells cross the spread (buy fills at ask, sell at bid);
    mm_passive cells rest on the resting side (buy fills at bid, sell
    at ask) — they would actually be filled when a counterparty crosses.
    Falls back to mid if the appropriate side isn't quoted."""
    if cell.kind == "mm_passive":
        target = bid if cell.side == "buy" else ask
    else:
        target = ask if cell.side == "buy" else bid
    if target and target > 0:
        return float(target)
    return float(mid)


def open_paper_trade(cell: CellSpec, fill_price: float,
                       vol_multiplier: float = 1.0) -> dict:
    """Build the open-trade dict matching backend_practice_trades.jsonl
    schema (same shape as the manual practice path in api_server.py).
    Caller persists via _persist_practice_trade().

    vol_multiplier: pass a value from `vol_target_multiplier(feat.realized_vol)`
    to scale notional inversely with chunk volatility. Defaults to 1.0
    (no scaling) so callers that haven't been migrated still get the
    fixed-notional behavior."""
    scaled_notional = float(cell.notional_usd) * float(vol_multiplier)
    qty = scaled_notional / fill_price if fill_price > 0 else 0.0
    notional = fill_price * qty
    fee_usd = notional * (_PRACTICE_FEE_BPS / 10000.0)
    return {
        "intent_id": str(uuid.uuid4())[:12],
        "asset": cell.asset,
        "venue": cell.venue,
        "side": cell.side,
        "price": float(fill_price),
        "qty": float(qty),
        "notional": float(notional),
        "note": cell.note,
        "ts_utc": time.time(),
        "practice": True,
        "auto": True,
        "cell_id": cell.cell_id,
        "kind": "practice",
        "status": "open",
        "fill_price": float(fill_price),
        "fees_usd": float(fee_usd),
        "fee_bps": _PRACTICE_FEE_BPS,
        "exit_price": 0.0,
        "exit_ts_utc": 0.0,
        "realized_pnl_usd": 0.0,
        "hold_minutes": float(cell.hold_minutes),
        "vol_multiplier": float(vol_multiplier),
        "base_notional_usd": float(cell.notional_usd),
        "kind": str(cell.kind),
    }


# ---------------------------------------------------------------------------
# F11 edge-driven paper trades. When the multi-horizon edge tracker tags a
# cell as STRONG on any horizon, this opens a paper trade in the implied
# direction with a hold-time scaled to the horizon. Distinct from the
# CellSpec-driven cells above — those are static hand-picked predicates;
# these are dynamic, fired only when empirical edge appears.
# ---------------------------------------------------------------------------

# Hold-time per horizon. Hardcoded as policy this session — intraday
# fires hold for half a chunk because the edge can flip within minutes;
# daily/weekly/longterm scale up.
EDGE_DRIVEN_HOLD_MIN_INTRADAY = 15.0   # half a chunk
EDGE_DRIVEN_HOLD_MIN_DAILY = 30.0      # one chunk
EDGE_DRIVEN_HOLD_MIN_WEEKLY = 120.0    # 4 chunks
EDGE_DRIVEN_HOLD_MIN_LONGTERM = 240.0  # 8 chunks

# Notional sizing per horizon. Intraday + daily get the smallest because
# they're most ephemeral; longterm gets the largest. Vol-target scaling
# still applies on top.
EDGE_DRIVEN_NOTIONAL_INTRADAY = 250.0
EDGE_DRIVEN_NOTIONAL_DAILY = 500.0
EDGE_DRIVEN_NOTIONAL_WEEKLY = 1000.0
EDGE_DRIVEN_NOTIONAL_LONGTERM = 1500.0


def _regime_is_directional(regime: str) -> bool:
    return (regime.startswith("WHALE_") or regime.startswith("HERD_")
             or regime.startswith("WHALE_NASCENT_"))


def _side_for_edge(regime: str, direction: str) -> str | None:
    """Map (regime UP/DOWN, edge direction fade/momentum) -> 'buy'/'sell'.

    Returns None when the regime isn't directional or edge direction is empty.
    """
    if not _regime_is_directional(regime) or not direction:
        return None
    is_up = regime.endswith("_UP")
    if direction == "momentum":
        return "buy" if is_up else "sell"
    if direction == "fade":
        return "sell" if is_up else "buy"
    return None


def try_open_edge_driven_trade(
    asset: str,
    venue: str,
    regime: str,
    edge_tags,        # edge_tracker.CellTags
    bid: float,
    ask: float,
    mid: float,
    vol_multiplier: float = 1.0,
) -> dict | None:
    """Return a paper-trade dict to open, or None if no horizon qualifies.

    Priority: intraday > daily > weekly > longterm. The first horizon
    with strength==STRONG and a non-empty direction (and a directional
    regime) wins. Intraday-first because the user wants tradeable-NOW
    signals acted on immediately — even if longer horizons don't yet
    confirm. Caller is responsible for dedup (one trade per chunk per
    cell) and for persisting the returned dict.
    """
    if not _regime_is_directional(regime):
        return None

    horizons = (
        ("intraday", edge_tags.intraday, EDGE_DRIVEN_HOLD_MIN_INTRADAY,
            EDGE_DRIVEN_NOTIONAL_INTRADAY),
        ("daily", edge_tags.daily, EDGE_DRIVEN_HOLD_MIN_DAILY,
            EDGE_DRIVEN_NOTIONAL_DAILY),
        ("weekly", edge_tags.weekly, EDGE_DRIVEN_HOLD_MIN_WEEKLY,
            EDGE_DRIVEN_NOTIONAL_WEEKLY),
        ("longterm", edge_tags.longterm, EDGE_DRIVEN_HOLD_MIN_LONGTERM,
            EDGE_DRIVEN_NOTIONAL_LONGTERM),
    )

    for horizon_name, hstat, hold_min, notional in horizons:
        if hstat.strength != "STRONG":
            continue
        side = _side_for_edge(regime, hstat.direction)
        if side is None:
            continue
        # Directional fill: buy crosses ask, sell crosses bid.
        fill_price = float(ask if side == "buy" else bid)
        if fill_price <= 0:
            continue
        scaled_notional = float(notional) * float(vol_multiplier)
        qty = scaled_notional / fill_price if fill_price > 0 else 0.0
        cell_id = (f"edge_{asset.lower()}_{venue.lower()}_{regime.lower()}"
                    f"_{horizon_name}_{hstat.direction}")
        note = (f"edge-driven {horizon_name} {hstat.strength.lower()} "
                f"{hstat.direction} on {asset}/{venue}/{regime} "
                f"(r={hstat.r:+.2f} n={hstat.n} self_trend={hstat.self_trend})")
        fee_usd = scaled_notional * (_PRACTICE_FEE_BPS / 10000.0)
        return {
            "intent_id": str(uuid.uuid4())[:12],
            "asset": asset,
            "venue": venue,
            "side": side,
            "price": float(fill_price),
            "qty": float(qty),
            "notional": float(scaled_notional),
            "note": note,
            "ts_utc": time.time(),
            "practice": True,
            "auto": True,
            "cell_id": cell_id,
            "kind": "practice",
            "status": "open",
            "fill_price": float(fill_price),
            "fees_usd": float(fee_usd),
            "fee_bps": _PRACTICE_FEE_BPS,
            "exit_price": 0.0,
            "exit_ts_utc": 0.0,
            "realized_pnl_usd": 0.0,
            "hold_minutes": float(hold_min),
            "vol_multiplier": float(vol_multiplier),
            "base_notional_usd": float(notional),
            # Extra fields specific to edge-driven trades
            "edge_horizon": horizon_name,
            "edge_strength": hstat.strength,
            "edge_direction": hstat.direction,
            "edge_self_trend": hstat.self_trend,
            "edge_r": float(hstat.r) if hstat.r is not None else 0.0,
            "edge_n": int(hstat.n),
            "regime_at_open": regime,
        }
    return None


def is_expired(trade: dict, now_utc: float) -> bool:
    if trade.get("status") != "open":
        return False
    if not trade.get("auto"):
        return False
    hold = float(trade.get("hold_minutes") or 0.0)
    if hold <= 0:
        return False
    return (now_utc - float(trade.get("ts_utc", 0.0))) / 60.0 >= hold


def close_paper_trade(trade: dict, bid: float, ask: float, mid: float) -> None:
    """Mutates `trade` in place to closed status with exit_price + realized P&L.
    Mirrors the math of /api/practice-trade/close in api_server.py.

    For directional cells (kind=='directional' or unset) a buy closes at
    bid, a sell at ask — same as a market-order exit that crosses the
    spread. For mm_passive cells the exit also rests on the book
    (buy closes at ask, sell at bid), so the round trip captures
    full bid-ask spread minus fees instead of paying it."""
    side = trade.get("side")
    kind = trade.get("kind", "directional")
    if kind == "mm_passive":
        exit_price = ask if side == "buy" else bid
    else:
        exit_price = bid if side == "buy" else ask
    if exit_price <= 0:
        exit_price = mid
    if exit_price <= 0:
        # Can't close without a quote; leave open.
        return
    fill_price = float(trade.get("fill_price", 0.0))
    qty = float(trade.get("qty", 0.0))
    signed = +1 if side == "buy" else -1
    gross_pnl = signed * (exit_price - fill_price) * qty
    notional_out = exit_price * qty
    exit_fee = notional_out * (_PRACTICE_FEE_BPS / 10000.0)
    realized = gross_pnl - float(trade.get("fees_usd", 0.0)) - exit_fee
    trade["status"] = "closed"
    trade["exit_price"] = float(exit_price)
    trade["exit_ts_utc"] = time.time()
    trade["fees_usd"] = float(trade.get("fees_usd", 0.0)) + float(exit_fee)
    trade["realized_pnl_usd"] = float(realized)
    trade["close_reason"] = "auto_hold_elapsed"
