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
from typing import Any, Optional


# Pass-17 cells-as-data architecture. CellSpec.predicate is a dict-tree
# matching the predicate DSL below — NOT a Python callable. Cells load
# from cells_registry.json at startup (path resolves to the repo root
# alongside the bin files and the cutoffs JSON).
#
# DSL leaves (each is a dict with exactly one of these keys):
#
#   {"regime_eq": "<regime label>"}
#     True iff the chunk's regime label equals the string.
#
#   {"feat_threshold": {"name": "<attr>", "op": ">=|>|<=|<", "value": <number>}}
#     Reads feat.<attr> via getattr, compares to value with op. Used for
#     z-score thresholds and other non-quartile gates.
#
#   {"feat_quartile":
#      {"name": "<attr>", "cell_key": "<venue_label>/<regime>",
#       "quartile_min": <int 1-4>, "quartile_max": <int 1-4>}}
#     Looks up the cell's quartile cutoffs from <asset>_cutoffs.json
#     (emitted by phase1_5_evaluator --cutoffs-out), determines which
#     quartile the live value falls in, and returns True iff
#     quartile_min <= q <= quartile_max. quartile_min defaults to 1,
#     quartile_max defaults to 4. So Q4-only = quartile_min=4, Q1-only =
#     quartile_max=1.
#
# DSL composers (each is a dict with one key, value = list of sub-preds):
#
#   {"all_of": [<pred>, ...]}   — all must be true
#   {"any_of": [<pred>, ...]}   — at least one must be true
#
# Anything else evaluates to False (fail-closed; cells with malformed
# predicates never fire).


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
    predicate: dict         # DSL predicate dict; see module docstring above.
    kind: str = "directional"  # "directional" (default; aggressive marketable
                               # entry/exit) or "mm_passive" (passive quoting:
                               # entry on the resting side of the book, exit
                               # on the opposite side, earning spread minus
                               # round-trip fees instead of paying it).
    capacity_class: str = "small"  # alpha-decay bucket consumed by
                               # signal_allocator. tiny (5/cohort, rotate),
                               # small (20/cohort, rotate),
                               # medium (50/cohort, rotate),
                               # large (broadcast to all),
                               # huge (broadcast; informational, not a
                               # trade). Per-cell setting reflects venue
                               # depth and the magnitude of edge that
                               # gets consumed per simultaneous fill.
    provenance: dict | None = None  # per-cell history: which pass/method
                                    # discovered this cell, n_chunks at
                                    # discovery, q-value, etc. Informational
                                    # only; doesn't affect trade behavior.
    runtime_status: str = "active"   # active | watch | retain | insufficient
    runtime_action: str = "active"   # active | watch | suppress
    runtime_reason: str = ""


# ---------------------------------------------------------------------------
# Registry + cutoffs loader. Both files live in the repo root; paths
# resolved relative to this file so the backend works regardless of cwd.
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_CELLS_REGISTRY_PATH = os.path.join(_REPO_ROOT, "cells_registry.json")
_CELLS_RUNTIME_CONTROLS_PATH = os.path.join(
    _REPO_ROOT, "cells_runtime_controls.json")

_cells_cache: tuple[float, float, list[CellSpec]] | None = None
_controls_cache: tuple[float, dict[str, dict]] | None = None
_cutoffs_cache: dict[str, tuple[float, dict]] = {}        # asset -> (mtime, cutoffs)

_VENUE_SHORT_ALIASES = {
    "COINBASE": "CB",
    "CB": "CB",
    "KRAKEN": "KR",
    "KR": "KR",
    "BINANCE": "BN",
    "BN": "BN",
    "BYBIT": "BB",
    "BB": "BB",
}


def _cutoffs_path(asset: str) -> str:
    return os.path.join(_REPO_ROOT, f"{asset.lower()}_cutoffs.json")


def _load_cutoffs(asset: str) -> dict:
    """Load <asset>_cutoffs.json, reloading on mtime change. Returns
    the cutoffs sub-dict keyed by venue_label/regime/feature. Missing
    file → empty dict (cells with feat_quartile predicates will then
    fail-closed)."""
    path = _cutoffs_path(asset)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    cached = _cutoffs_cache.get(asset)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[cells] cutoffs load failed for {asset} ({path}): {e}",
              flush=True)
        return {}
    cutoffs = payload.get("cutoffs", {}) or {}
    _cutoffs_cache[asset] = (mtime, cutoffs)
    return cutoffs


def _norm_venue_label(label: str | None) -> str:
    if label is None:
        return ""
    raw = str(label).strip()
    if not raw:
        return ""
    return _VENUE_SHORT_ALIASES.get(raw.upper(), raw.upper())


def _venue_matches(cell_venue: str, live_venue: str) -> bool:
    return _norm_venue_label(cell_venue) == _norm_venue_label(live_venue)


def load_cells_runtime_controls(path: str | None = None) -> dict[str, dict]:
    global _controls_cache
    actual = path or _CELLS_RUNTIME_CONTROLS_PATH
    try:
        mtime = os.path.getmtime(actual)
    except OSError:
        _controls_cache = None
        return {}
    if _controls_cache and _controls_cache[0] == mtime:
        return _controls_cache[1]
    try:
        with open(actual) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[cells] runtime controls load failed at {actual}: {e}",
              flush=True)
        return _controls_cache[1] if _controls_cache else {}
    controls = payload.get("controls") or {}
    if not isinstance(controls, dict):
        controls = {}
    _controls_cache = (mtime, controls)
    return controls


def _cellspec_from_dict(d: dict) -> CellSpec | None:
    """Build a CellSpec from a registry JSON entry. Missing required
    fields → None (caller skips with warning)."""
    try:
        return CellSpec(
            cell_id=str(d["cell_id"]),
            asset=str(d["asset"]),
            venue=str(d["venue"]),
            side=str(d["side"]),
            notional_usd=float(d.get("notional_usd", 1000.0)),
            hold_minutes=float(d.get("hold_minutes", 10.0)),
            note=str(d.get("note", "")),
            predicate=d.get("predicate") or {},
            kind=str(d.get("kind", "directional")),
            capacity_class=str(d.get("capacity_class", "small")),
            provenance=d.get("provenance"),
            runtime_status=str(d.get("runtime_status", "active")),
            runtime_action=str(d.get("runtime_action", "active")),
            runtime_reason=str(d.get("runtime_reason", "")),
        )
    except (KeyError, TypeError, ValueError) as e:
        print(f"[cells] skipping malformed registry entry: {e} "
              f"(cell_id={d.get('cell_id', '?')})", flush=True)
        return None


def load_cells_registry(path: str | None = None) -> list[CellSpec]:
    """Load cells from cells_registry.json. Caches by mtime so repeated
    calls are cheap. Returns [] if the file is missing or unreadable
    (cells_as_data system fails to all-empty rather than to legacy
    hardcoded cells — there are no legacy hardcoded cells anymore)."""
    global _cells_cache
    actual = path or _CELLS_REGISTRY_PATH
    controls = load_cells_runtime_controls()
    controls_mtime = _controls_cache[0] if _controls_cache else -1.0
    try:
        mtime = os.path.getmtime(actual)
    except OSError:
        if _cells_cache is not None:
            print(f"[cells] registry no longer at {actual}; serving "
                  f"{len(_cells_cache[2])} stale cells", flush=True)
            return _cells_cache[2]
        print(f"[cells] no registry at {actual}; no cells loaded",
              flush=True)
        return []
    if _cells_cache and _cells_cache[0] == mtime and _cells_cache[1] == controls_mtime:
        return _cells_cache[2]
    try:
        with open(actual) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[cells] registry load failed at {actual}: {e}", flush=True)
        return _cells_cache[2] if _cells_cache else []
    raw_cells = payload.get("cells") or []
    cells: list[CellSpec] = []
    for entry in raw_cells:
        spec = _cellspec_from_dict(entry)
        if spec is not None:
            ctrl = controls.get(spec.cell_id) or {}
            if isinstance(ctrl, dict):
                spec.runtime_status = str(ctrl.get("status", spec.runtime_status))
                spec.runtime_action = str(ctrl.get("action", spec.runtime_action))
                spec.runtime_reason = str(ctrl.get("reason", spec.runtime_reason))
            cells.append(spec)
    _cells_cache = (mtime, controls_mtime, cells)
    print(f"[cells] loaded {len(cells)} cells from "
          f"{os.path.basename(actual)} (schema_version="
          f"{payload.get('schema_version')})", flush=True)
    return cells


# Module-level CELLS is now a property-style function call site. Callers
# should prefer load_cells_registry() but legacy imports of CELLS keep
# working — they get the registry contents at import time.
CELLS: list[CellSpec] = load_cells_registry()


# ---------------------------------------------------------------------------
# DSL evaluator. Pure function: (predicate dict, regime, feat, chunk,
# cutoffs_for_asset) -> bool. Cutoffs are passed in (not looked up) so
# the function stays unit-testable without filesystem.
# ---------------------------------------------------------------------------


def _eval_predicate(pred: Any, regime: str, feat: object, chunk: object,
                     cutoffs: dict) -> bool:
    if not isinstance(pred, dict) or not pred:
        return False
    if "regime_eq" in pred:
        return regime == pred["regime_eq"]
    if "feat_threshold" in pred:
        spec = pred["feat_threshold"]
        v = getattr(feat, spec.get("name", ""), None)
        if v is None:
            return False
        op = spec.get("op", ">=")
        try:
            fv = float(v); thr = float(spec.get("value", 0.0))
        except (TypeError, ValueError):
            return False
        if op == ">=":  return fv >= thr
        if op == ">":   return fv > thr
        if op == "<=":  return fv <= thr
        if op == "<":   return fv < thr
        if op == "==":  return fv == thr
        return False
    if "feat_quartile" in pred:
        spec = pred["feat_quartile"]
        v = getattr(feat, spec.get("name", ""), None)
        if v is None:
            return False
        cell_key = spec.get("cell_key", "")
        venue_label, _, regime_key = cell_key.partition("/")
        feat_name = spec.get("name", "")
        try:
            entry = (cutoffs.get(venue_label, {})
                     .get(regime_key, {})
                     .get(feat_name))
        except AttributeError:
            return False
        if not isinstance(entry, dict):
            return False
        try:
            q1u = float(entry["q1_upper"])
            q2u = float(entry["q2_upper"])
            q3u = float(entry["q3_upper"])
            fv = float(v)
        except (KeyError, TypeError, ValueError):
            return False
        if fv <= q1u:    q_actual = 1
        elif fv <= q2u:  q_actual = 2
        elif fv <= q3u:  q_actual = 3
        else:            q_actual = 4
        q_min = int(spec.get("quartile_min", 1))
        q_max = int(spec.get("quartile_max", 4))
        return q_min <= q_actual <= q_max
    if "all_of" in pred:
        subs = pred.get("all_of") or []
        return all(_eval_predicate(p, regime, feat, chunk, cutoffs)
                   for p in subs)
    if "any_of" in pred:
        subs = pred.get("any_of") or []
        return any(_eval_predicate(p, regime, feat, chunk, cutoffs)
                   for p in subs)
    return False


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
    """Return all registry cells whose DSL predicate fires on this chunk.
    Reloads the registry + cutoffs on mtime change so live appends are
    picked up without a backend restart."""
    cells = load_cells_registry()
    if not cells:
        return []
    cutoffs = _load_cutoffs(asset)
    out: list[CellSpec] = []
    for cell in cells:
        if cell.asset != asset or not _venue_matches(cell.venue, venue):
            continue
        if cell.runtime_action == "suppress":
            continue
        try:
            if _eval_predicate(cell.predicate, regime, feat, chunk, cutoffs):
                out.append(cell)
        except Exception as e:
            # Predicate failure shouldn't kill the poll loop. Log + skip.
            print(f"[cells] predicate eval error for {cell.cell_id}: {e}",
                  flush=True)
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


def _predicate_feature_names(pred: Any) -> set[str]:
    if not isinstance(pred, dict) or not pred:
        return set()
    out: set[str] = set()
    if "feat_threshold" in pred:
        spec = pred.get("feat_threshold") or {}
        name = spec.get("name")
        if isinstance(name, str) and name:
            out.add(name)
    if "feat_quartile" in pred:
        spec = pred.get("feat_quartile") or {}
        name = spec.get("name")
        if isinstance(name, str) and name:
            out.add(name)
    for key in ("all_of", "any_of"):
        subs = pred.get(key) or []
        if isinstance(subs, list):
            for sub in subs:
                out |= _predicate_feature_names(sub)
    return out


def _cell_feature_names(cell: CellSpec) -> set[str]:
    prov = getattr(cell, "provenance", None) or {}
    combo_spec = prov.get("combination_spec") or []
    out: set[str] = set()
    if isinstance(combo_spec, list):
        for item in combo_spec:
            if not isinstance(item, dict):
                continue
            name = item.get("feature")
            if isinstance(name, str) and name:
                out.add(name)
    if out:
        return out
    return _predicate_feature_names(getattr(cell, "predicate", {}))


def _cell_direction_label(cell: CellSpec, regime: str) -> str:
    prov = getattr(cell, "provenance", None) or {}
    predicted = prov.get("predicted_direction")
    if predicted in ("momentum", "fade"):
        return str(predicted)
    side = getattr(cell, "side", "")
    if regime.endswith("_UP"):
        return "momentum" if side == "buy" else "fade"
    if regime.endswith("_DOWN"):
        return "momentum" if side == "sell" else "fade"
    if side == "buy":
        return "buy_bias"
    if side == "sell":
        return "sell_bias"
    return ""


def summarize_live_convergence(
    asset: str,
    venue: str,
    regime: str,
    cells: list[CellSpec],
    *,
    min_support: int = 3,
) -> dict | None:
    groups: dict[str, dict] = {}
    for cell in cells:
        if cell.runtime_action == "suppress":
            continue
        features = sorted(_cell_feature_names(cell))
        if not features:
            continue
        side = getattr(cell, "side", "")
        if side not in ("buy", "sell"):
            continue
        bucket = groups.setdefault(side, {
            "cell_ids": [],
            "features": set(),
            "directions": set(),
            "ci_lows": [],
            "edges": [],
            "tiers": set(),
        })
        bucket["cell_ids"].append(cell.cell_id)
        bucket["features"].update(features)
        bucket["directions"].add(_cell_direction_label(cell, regime))
        prov = getattr(cell, "provenance", None) or {}
        if isinstance(prov.get("score_ci_low"), (int, float)):
            bucket["ci_lows"].append(float(prov["score_ci_low"]))
        if isinstance(prov.get("edge_magnitude"), (int, float)):
            bucket["edges"].append(float(prov["edge_magnitude"]))
        tier = prov.get("tier")
        if isinstance(tier, str) and tier:
            bucket["tiers"].add(tier)

    best_side = None
    best_bucket = None
    best_key = None
    for side, bucket in groups.items():
        support_count = len(bucket["features"])
        if support_count < min_support:
            continue
        avg_ci = sum(bucket["ci_lows"]) / len(bucket["ci_lows"]) if bucket["ci_lows"] else 0.0
        score_key = (support_count, len(bucket["cell_ids"]), avg_ci)
        if best_key is None or score_key > best_key:
            best_key = score_key
            best_side = side
            best_bucket = bucket
    if best_side is None or best_bucket is None:
        return None

    support_count = len(best_bucket["features"])
    direction_labels = sorted(label for label in best_bucket["directions"] if label)
    direction_label = direction_labels[0] if len(direction_labels) == 1 else "/".join(direction_labels)
    avg_ci = (
        sum(best_bucket["ci_lows"]) / len(best_bucket["ci_lows"])
        if best_bucket["ci_lows"] else None
    )
    avg_edge = (
        sum(best_bucket["edges"]) / len(best_bucket["edges"])
        if best_bucket["edges"] else None
    )
    bonus = min(1.50, 1.0 + 0.10 * max(0, support_count - min_support + 1))
    feature_list = sorted(best_bucket["features"])
    return {
        "asset": asset,
        "venue": _norm_venue_label(venue),
        "regime": regime,
        "side": best_side,
        "direction_label": direction_label,
        "support_count": support_count,
        "cell_ids": list(best_bucket["cell_ids"]),
        "features": feature_list,
        "confidence_tier": "convergence",
        "avg_score_ci_low": avg_ci,
        "avg_edge_magnitude": avg_edge,
        "bonus_multiplier": bonus,
        "summary": (
            f"{support_count}-feature convergence on {asset}/{_norm_venue_label(venue)}/{regime}: "
            f"{best_side} via {', '.join(feature_list)}"
        ),
        "tier_labels": sorted(best_bucket["tiers"]),
    }


def open_convergence_trade(
    convergence: dict,
    fill_price: float,
    *,
    vol_multiplier: float = 1.0,
    base_notional_usd: float = 750.0,
    base_hold_minutes: float = 10.0,
) -> dict | None:
    side = str(convergence.get("side") or "")
    if side not in ("buy", "sell") or fill_price <= 0:
        return None
    support_count = int(convergence.get("support_count") or 0)
    notional_scale = max(1.0, min(2.0, support_count / 3.0))
    scaled_notional = float(base_notional_usd) * notional_scale * float(vol_multiplier)
    qty = scaled_notional / fill_price if fill_price > 0 else 0.0
    fee_usd = scaled_notional * (_PRACTICE_FEE_BPS / 10000.0)
    asset = str(convergence.get("asset") or "")
    venue = str(convergence.get("venue") or "")
    regime = str(convergence.get("regime") or "")
    features = list(convergence.get("features") or [])
    cell_id = (
        f"conv_{asset.lower()}_{venue.lower()}_{regime.lower()}_{side}_"
        f"{support_count}f"
    )
    return {
        "intent_id": str(uuid.uuid4())[:12],
        "asset": asset,
        "venue": venue,
        "side": side,
        "price": float(fill_price),
        "qty": float(qty),
        "notional": float(scaled_notional),
        "note": str(convergence.get("summary") or ""),
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
        "hold_minutes": float(base_hold_minutes),
        "vol_multiplier": float(vol_multiplier),
        "base_notional_usd": float(base_notional_usd),
        "confidence_tier": "convergence",
        "capacity_class": "medium",
        "convergence_support_count": support_count,
        "convergence_features": features,
        "convergence_bonus_multiplier": float(
            convergence.get("bonus_multiplier") or 1.0
        ),
        "regime_at_open": regime,
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


# Confidence-tier thresholds for edge-driven trades. Maps the cell's
# observed |r| at the firing horizon AND multi-horizon corroboration
# into an alert tier consumed by the UI / push notification layer.
#   high_conviction → "low-risk-trade-signal" alert
#   alertable       → "risky-trade-signal" alert
# Tier reflects detection confidence, not P&L expectation; risk is
# always 100% of stake for the paper trade itself.
#
EDGE_TIER_HIGH_CONVICTION_R = 0.20  # firing-horizon |r| floor for tier 1
EDGE_TIER_CORROBORATION_R = 0.15    # other-horizon |r| floor for corroboration


def _edge_abs_score(hstat) -> float:
    vals = []
    if getattr(hstat, "r", None) is not None:
        vals.append(abs(float(hstat.r)))
    if getattr(hstat, "rho", None) is not None:
        vals.append(abs(float(hstat.rho)))
    return max(vals) if vals else 0.0


def _edge_metric_note(hstat) -> str:
    metric = getattr(hstat, "primary_metric", "")
    if metric == "rho" and getattr(hstat, "rho", None) is not None:
        return f"rho={float(hstat.rho):+.2f}"
    if getattr(hstat, "r", None) is not None:
        return f"r={float(hstat.r):+.2f}"
    return "r=n/a"


def _edge_confidence_tier(firing_horizon: str, firing_r: float,
                            firing_direction: str,
                            edge_tags) -> str:
    """Return 'high_conviction' or 'alertable' for a STRONG firing horizon.

    Promotes to high_conviction iff |r| at the firing horizon clears
    EDGE_TIER_HIGH_CONVICTION_R AND at least one other horizon also
    has |r| >= EDGE_TIER_CORROBORATION_R with the SAME direction
    (fade ↔ fade or momentum ↔ momentum). Without that corroboration,
    the tier stays 'alertable'.

    Single-horizon STRONG fires (intraday-only, e.g.) are intentionally
    capped at alertable so they don't get pushed as the strongest tier.
    """
    others = []
    for name, stat in (("intraday", edge_tags.intraday),
                        ("daily", edge_tags.daily),
                        ("weekly", edge_tags.weekly),
                        ("longterm", edge_tags.longterm)):
        if name == firing_horizon:
            continue
        others.append(stat)
    corroborated = any(
        _edge_abs_score(s) >= EDGE_TIER_CORROBORATION_R
        and s.direction == firing_direction
        for s in others
    )
    if abs(firing_r) >= EDGE_TIER_HIGH_CONVICTION_R and corroborated:
        return "high_conviction"
    return "alertable"


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
        confidence_tier = _edge_confidence_tier(
            horizon_name, _edge_abs_score(hstat),
            hstat.direction, edge_tags)
        note = (f"edge-driven {horizon_name} {hstat.strength.lower()} "
                f"{hstat.direction} on {asset}/{venue}/{regime} "
                f"({_edge_metric_note(hstat)} n={hstat.n} "
                f"tier={confidence_tier} self_trend={hstat.self_trend})")
        fee_usd = scaled_notional * (_PRACTICE_FEE_BPS / 10000.0)
        # Edge-driven trades come from the live tracker and don't have a
        # CellSpec.capacity_class. Default capacity by horizon: intraday
        # = tiny (fastest decay), daily = small, weekly/longterm = medium.
        edge_capacity = {
            "intraday": "tiny",
            "daily": "small",
            "weekly": "medium",
            "longterm": "medium",
        }.get(horizon_name, "small")
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
            "edge_rho": float(hstat.rho) if getattr(hstat, "rho", None) is not None else 0.0,
            "edge_primary_metric": getattr(hstat, "primary_metric", ""),
            "edge_primary_value": float(
                hstat.r if getattr(hstat, "primary_metric", "") == "r" else (
                    hstat.rho if getattr(hstat, "primary_metric", "") == "rho" else 0.0
                )
            ),
            "edge_n": int(hstat.n),
            "regime_at_open": regime,
            # Tier consumed by the alert/notification layer.
            # high_conviction → push as the strongest tier; alertable →
            # push as the weaker tier. Both still book a paper trade.
            "confidence_tier": confidence_tier,
            # Capacity class for signal_allocator rotation. Edge-driven
            # trades inherit it from the firing horizon.
            "capacity_class": edge_capacity,
        }
    return None


def dispatch_signal_for_cell(cell_id: str, capacity_class: str, tier: str,
                                 payload: dict) -> dict:
    """Distribute a signal occurrence to a rotation-selected cohort.

    Pulls the current subscriber list from push.get_subs(), asks
    signal_allocator.select_cohort() which subset should receive THIS
    occurrence, sends the push to that cohort, and records the
    allocation in the fairness ledger.

    Returns the push result dict (sent / failed / pruned) augmented
    with cohort_size and tier — useful for SSE diagnostics.

    Imports are lazy because forward_paper.py is imported by the
    evaluator + the executor, neither of which need push/allocator
    machinery. Only the backend api_server path exercises this.
    """
    try:
        from backend.push import get_subs, send_to_endpoints
        from backend.signal_allocator import (
            select_cohort, record_allocation,
        )
    except ImportError as e:
        return {"sent": 0, "failed": 0,
                  "note": f"dispatch unavailable: {e}"}

    subs = get_subs()
    if not subs:
        return {"sent": 0, "failed": 0, "cohort_size": 0,
                  "note": "no subscribers"}

    all_endpoints = [s.endpoint for s in subs]
    reg_ts = {s.endpoint: float(getattr(s, "registered_utc", 0.0))
              for s in subs}
    cohort = select_cohort(
        cell_id=cell_id,
        capacity_class=capacity_class,
        tier=tier,
        all_endpoints=all_endpoints,
        registered_ts_by_endpoint=reg_ts,
    )
    if not cohort:
        return {"sent": 0, "failed": 0, "cohort_size": 0,
                  "note": "empty cohort"}

    push_payload = dict(payload)
    # Always tag the push payload with the cell + tier + cohort size so
    # the receiving client can render it sensibly.
    push_payload.setdefault("cell_id", cell_id)
    push_payload.setdefault("tier", tier)
    push_payload.setdefault("capacity_class", capacity_class)

    result = send_to_endpoints(push_payload, cohort)
    # Record allocation AFTER the push attempt. If we recorded before,
    # a failed push would still bump the cohort's fairness counters and
    # they'd be unfairly de-prioritized next round. By recording after,
    # we accept that the ledger reflects "intended delivery" rather than
    # "confirmed delivery" — the right tradeoff for fairness.
    record_allocation(cell_id=cell_id, tier=tier, endpoints=cohort)
    result["cohort_size"] = len(cohort)
    result["all_subscribers"] = len(all_endpoints)
    result["tier"] = tier
    return result


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
