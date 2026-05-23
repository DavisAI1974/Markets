"""
api_server.py — FastAPI backend for the markets-watch UI.

Exposes:
  GET  /api/health            - liveness probe
  GET  /api/status            - current regime for each (asset, venue)
  GET  /api/signals           - recent signal events (last N entries)
  GET  /api/signal/{id}       - full detail for a specific signal
  GET  /api/stream            - Server-Sent Events stream of new signal events
  GET  /api/chart/{asset}/{venue} - chart data (dipole + price over time)

Data flow:
  - SignalStore polls the bins JSON files written by collectors every 30s
  - On each poll, runs the regime classifier on the latest chunks
  - Regime changes are emitted as signal events
  - State is exposed via REST + streamed via SSE

Run: uvicorn backend.api_server:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any

# Allow imports from the parent Markets directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from markets_adapter import (
    MarketBar, MarketChunker, MarketChunkEncoder,
    _vpin_bucket_volume_from_corpus,
)
from regime_classifier import (
    Regime, classify_regime, baselines_from_corpus,
    apply_cross_venue_multiplier, _session_phase_of,
    apply_herd_persistence, detect_whale_to_herd_cascades,
    detect_cross_venue_whale_herd_simultaneity,
    apply_cross_asset_multiplier_uniform, _direction,
    apply_event_multiplier,
)
from event_calendar import EventCalendar
from daily_news_context import adjust_present_score_with_news, load_daily_news_context, news_adjusted_trade_option
from strategy_switcher import (
    DISABLED_STRATEGIES,
    NO_TRADE,
    apply_strategy_to_option,
    classify_strategy,
)
from strategy_family_evolution import record_trade_attempt_open_json
import trade_exit_strategy
from high_conviction_ticket import build_high_conviction_ticket
from edge_tracker import MultiHorizonEdgeTracker, CellTags
from backend.auth import verify_token, ACCESS_TOKEN
from backend.push import (
    PushSubscription, add_sub, remove_sub, get_subs, send_to_all, VAPID_PUBLIC,
)
from playbook_generator import get_playbook as get_dynamic_playbook
from playbook_generator import get_drift_status
from backend.forward_paper import (
    close_carry_trade as _fp_close_carry,
    entry_price_for_cell as _fp_entry_price,
    find_carry_spec as _fp_find_carry_spec,
    find_matching_cells as _fp_find_cells,
    is_carry_trade as _fp_is_carry,
    open_carry_trade as _fp_open_carry,
    open_convergence_trade as _fp_open_convergence_trade,
    open_paper_trade as _fp_open_trade,
    load_cells_runtime_controls as _fp_load_cell_controls,
    summarize_live_convergence as _fp_summarize_convergence,
    vol_target_multiplier as _fp_vol_mult,
    is_expired as _fp_is_expired,
    close_paper_trade as _fp_close_trade,
)
from backend.basis_monitor import BasisMonitor
from backend.carry_analyzer import evaluate_all_carry
from backend.cb_premium_monitor import CoinbasePremiumMonitor
from backend.funding_monitor import FundingMonitor
from backend.oi_monitor import OIMonitor
from backend.liq_monitor import LiqMonitor
from cells_decay_monitor import (
    DEFAULT_CONTROLS_OUTPUT_PATH,
    refresh_runtime_controls,
)
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration: which (asset, venue) pairs to track and where their bins live
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_AUTO_TRADE_SETTINGS_PATH = os.path.join(REPO_ROOT, "backend_auto_trade_settings.json")
_MOCK_TRADE_SETTINGS_PATH = os.path.join(REPO_ROOT, "backend_mock_trade_settings.json")
_DEFAULT_MOCK_EXIT_PARAMS_PATH = os.path.join(
    REPO_ROOT,
    "research",
    "strategy_evolution",
    "exit_params_h0_h168_v2_promoted_min5.json",
)
_LIVE_MOCK_OPPORTUNITIES_PATH = os.path.join(
    REPO_ROOT,
    "research",
    "strategy_evolution",
    "_live_mock_opportunities.jsonl",
)
_LIVE_HINDSIGHT_AUDIT_PATH = os.path.join(
    REPO_ROOT,
    "research",
    "strategy_evolution",
    "live_mock_replay",
    "live_hindsight_missed_winner_audit.json",
)
_EVOLVE_REQUESTS_PATH = os.path.join(REPO_ROOT, "backend_evolve_requests.jsonl")
_DAILY_NEWS_CONTEXT_PATH = os.environ.get(
    "MARKETS_WATCH_DAILY_NEWS_CONTEXT",
    os.path.join(REPO_ROOT, "daily_news_context.json"),
)

LIVE_MODE = os.environ.get("MARKETS_WATCH_LIVE", "0").lower() in ("1", "true", "yes")
LIVE_DATA_DIR = os.path.abspath(os.environ.get(
    "MARKETS_WATCH_LIVE_DATA_DIR",
    os.path.join(REPO_ROOT, "live_data"),
))

def _source_path(filename: str) -> str:
    return os.path.join(LIVE_DATA_DIR if LIVE_MODE else REPO_ROOT, filename)

DATA_SOURCES = [
    # (asset, venue, bins_path)
    ("BTC", "Coinbase", _source_path("btc_coinbase_bins.json")),
    ("BTC", "Kraken",   _source_path("btc_kraken_bins.json")),
    ("BTC", "Bybit",    _source_path("btc_bybit_perp_bins.json")),
    ("ETH", "Coinbase", _source_path("eth_coinbase_bins.json")),
    ("ETH", "Kraken",   _source_path("eth_kraken_bins.json")),
    ("ETH", "Bybit",    _source_path("eth_bybit_perp_bins.json")),
]


def _source_freshness() -> list[dict[str, Any]]:
    out = []
    now = time.time()
    for asset, venue, path in DATA_SOURCES:
        exists = os.path.exists(path)
        mtime = os.path.getmtime(path) if exists else 0.0
        age = (now - mtime) if mtime else None
        out.append({
            "asset": asset,
            "venue": venue,
            "path": path,
            "exists": exists,
            "age_seconds": round(age, 1) if age is not None else None,
            "fresh": bool(age is not None and age <= max(15.0, POLL_INTERVAL_S * 3)),
        })
    return out


def _live_bucket_session(ts: float | None = None) -> str:
    """Match live mock trades to the historical first6h/remaining18h buckets."""
    basis_ts = time.time() if ts is None else float(ts)
    hour = datetime.utcfromtimestamp(basis_ts).hour
    return "first6h" if hour < 6 else "remaining18h"

# Spot/perp paths for the basis_monitor. Per-asset; we pick whichever
# spot venue is deepest (KR for both ETH/BTC at present) and whichever
# perp source exists locally. Bybit is the live public perp feed; Binance
# files are only used when a historical backfill is present.
BASIS_SPOT_PATHS = {
    "BTC": os.path.join(REPO_ROOT, "kraken_bins.json"),
    "ETH": os.path.join(REPO_ROOT, "eth_kraken_bins.json"),
}

def _first_existing_path(*paths: str) -> str:
    for path in paths:
        if os.path.exists(path):
            return path
    return paths[0]

BASIS_PERP_PATHS = {
    "BTC": _first_existing_path(
        os.path.join(REPO_ROOT, "btc_bybit_perp_bins.json"),
        os.path.join(REPO_ROOT, "btc_binance_perp_bins.json"),
    ),
    "ETH": _first_existing_path(
        os.path.join(REPO_ROOT, "eth_bybit_perp_bins.json"),
        os.path.join(REPO_ROOT, "eth_binance_perp_bins.json"),
    ),
}

POLL_INTERVAL_S = float(os.environ.get("MARKETS_WATCH_POLL_INTERVAL_S", "30.0"))
RECENT_SIGNALS_CAP = 200
CHUNK_MAX_SIZE = 30
CHUNK_MIN_SEGMENT = int(os.environ.get("MARKETS_WATCH_CHUNK_MIN_SEGMENT", "10"))
ALLOW_LIVE_AUTO_TRADE = os.environ.get(
    "MARKETS_WATCH_ALLOW_LIVE_AUTO_TRADE", "0").lower() in ("1", "true", "yes")


def _default_auto_trade_settings() -> dict[str, Any]:
    return {
        "enabled": False,
        "practice": True,
        "tolerance": "balanced",
        "profiles": ["early_probe", "confirmed_follow"],
        "min_readiness": 65,
        "max_open_trades": 3,
        "base_notional_usd": 1000.0,
    }


AUTO_TRADE_TOLERANCE_PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "profiles": ["confirmed_follow"],
        "min_readiness": 75,
        "max_open_trades": 1,
        "base_notional_usd": 750.0,
    },
    "balanced": {
        "profiles": ["early_probe", "confirmed_follow"],
        "min_readiness": 65,
        "max_open_trades": 3,
        "base_notional_usd": 1000.0,
    },
    "aggressive": {
        "profiles": ["early_probe", "confirmed_follow"],
        "min_readiness": 55,
        "max_open_trades": 6,
        "base_notional_usd": 1500.0,
    },
}


def _load_auto_trade_settings() -> dict[str, Any]:
    settings = _default_auto_trade_settings()
    if os.path.exists(_AUTO_TRADE_SETTINGS_PATH):
        try:
            with open(_AUTO_TRADE_SETTINGS_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                settings.update(raw)
        except Exception as e:
            print(f"[auto-trade] settings load error: {e}", flush=True)
    settings["enabled"] = bool(settings.get("enabled"))
    settings["practice"] = bool(settings.get("practice", True))
    tolerance = str(settings.get("tolerance") or "balanced")
    if tolerance not in AUTO_TRADE_TOLERANCE_PRESETS:
        tolerance = "balanced"
    settings["tolerance"] = tolerance
    preset = AUTO_TRADE_TOLERANCE_PRESETS[tolerance]
    for key, value in preset.items():
        settings.setdefault(key, value)
    if not settings["practice"] and not ALLOW_LIVE_AUTO_TRADE:
        settings["practice"] = True
        settings["live_blocked_reason"] = "live auto disabled by server policy"
    settings["profiles"] = [
        str(p) for p in (settings.get("profiles") or ["early_probe"])
        if str(p) in ("early_probe", "confirmed_follow")
    ] or ["early_probe"]
    settings["min_readiness"] = int(settings.get("min_readiness") or 55)
    settings["max_open_trades"] = int(settings.get("max_open_trades") or 3)
    settings["base_notional_usd"] = float(settings.get("base_notional_usd") or 1000.0)
    settings["allow_live_auto"] = ALLOW_LIVE_AUTO_TRADE
    settings.pop("apply_preset", None)
    return settings


def _save_auto_trade_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = _default_auto_trade_settings()
    merged.update(settings)
    tolerance = str(merged.get("tolerance") or "balanced")
    if tolerance not in AUTO_TRADE_TOLERANCE_PRESETS:
        tolerance = "balanced"
    merged["tolerance"] = tolerance
    if bool(settings.get("apply_preset", False)):
        merged.update(AUTO_TRADE_TOLERANCE_PRESETS[tolerance])
    if not bool(merged.get("practice", True)) and not ALLOW_LIVE_AUTO_TRADE:
        merged["practice"] = True
        merged["live_blocked_reason"] = "live auto disabled by server policy"
    merged.pop("apply_preset", None)
    tmp = _AUTO_TRADE_SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    os.replace(tmp, _AUTO_TRADE_SETTINGS_PATH)
    return _load_auto_trade_settings()


def _default_mock_trade_settings() -> dict[str, Any]:
    scenarios = [
        {
            "id": "route_evidence",
            "base_scenario_id": "route_evidence",
            "label": "Route Evidence",
            "min_present_score": 0,
            "max_present_score": 100,
            "notional_pct_bank": 1.00,
            "cooldown_minutes": 0,
            "stop_loss_bps": 10.0,
            "take_profit_bps": 18.0,
            "exit_score_drop": 12,
            "allowed_stages": ["onset", "early_follow", "mature"],
            "allowed_trade_states": ["watch", "early_probe", "confirmed"],
            "allowed_pressure_states": ["internal", "forming", "high_priority", "confirmed"],
            "hold_minutes": 10,
            "rotation_enabled": False,
            "enabled": True,
            "enforce_bucket_health": True,
            "enforce_daily_limits": True,
            "rotation_min_score_advantage": 0,
            "rotation_min_underperform_bps": 0.0,
            "rotation_require_degrading": False,
        }
    ]
    return {
        "enabled": False,
        "initial_bank_usd": 10000.0,
        "tier_high_bank_threshold_usd": 20000.0,
        "tier_high_exposure_cap_usd": 1000000.0,
        "tier_mid_bank_threshold_usd": 10000.0,
        "tier_mid_exposure_pct": 1.00,
        "tier_low_bank_threshold_usd": 5000.0,
        "tier_low_exposure_cap_usd": 1000000.0,
        "mock_fee_bps": 5.0,
        "min_trade_notional_usd": 25.0,
        "exit_params_path": _DEFAULT_MOCK_EXIT_PARAMS_PATH,
        "scenarios": scenarios,
    }


def _resolve_mock_exit_params_path(path: Any) -> str:
    raw = str(path or "").strip()
    if not raw:
        raw = _DEFAULT_MOCK_EXIT_PARAMS_PATH
    if not os.path.isabs(raw):
        raw = os.path.join(REPO_ROOT, raw)
    return os.path.abspath(raw)


def _load_mock_exit_params(settings: dict[str, Any]) -> tuple[dict[str, Any], str]:
    path = _resolve_mock_exit_params_path(settings.get("exit_params_path"))
    params = trade_exit_strategy.load_exit_params(path)
    return params, path


def _load_mock_trade_settings(load_exit_params: bool = False) -> dict[str, Any]:
    settings = _default_mock_trade_settings()
    if os.path.exists(_MOCK_TRADE_SETTINGS_PATH):
        try:
            with open(_MOCK_TRADE_SETTINGS_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                settings.update(raw)
        except Exception as e:
            print(f"[mock-trade] settings load error: {e}", flush=True)
    settings["enabled"] = bool(settings.get("enabled"))
    settings["backend_controller_enabled"] = bool(settings.get("backend_controller_enabled", settings["enabled"]))
    settings["initial_bank_usd"] = max(0.0, float(settings.get("initial_bank_usd") or 10000.0))
    settings["tier_high_bank_threshold_usd"] = max(0.0, float(settings.get("tier_high_bank_threshold_usd") or 20000.0))
    settings["tier_high_exposure_cap_usd"] = max(0.0, float(settings.get("tier_high_exposure_cap_usd") or 10000.0))
    settings["tier_mid_bank_threshold_usd"] = max(0.0, float(settings.get("tier_mid_bank_threshold_usd") or 10000.0))
    settings["tier_mid_exposure_pct"] = max(0.0, min(1.0, float(settings.get("tier_mid_exposure_pct") or 0.5)))
    settings["tier_low_bank_threshold_usd"] = max(0.0, float(settings.get("tier_low_bank_threshold_usd") or 5000.0))
    settings["tier_low_exposure_cap_usd"] = max(0.0, float(settings.get("tier_low_exposure_cap_usd") or 5000.0))
    settings["mock_fee_bps"] = max(0.0, float(settings.get("mock_fee_bps") or 5.0))
    settings["min_trade_notional_usd"] = max(1.0, float(settings.get("min_trade_notional_usd") or 25.0))
    exit_params_map, exit_params_path = _load_mock_exit_params(settings)
    settings["exit_params_path"] = exit_params_path
    settings["exit_params_loaded"] = bool(exit_params_map)
    if load_exit_params and exit_params_map:
        settings["exit_params_map"] = exit_params_map
    defaults_by_id = {s["id"]: s for s in _default_mock_trade_settings()["scenarios"]}
    legacy_scenario_ids = {
        "pressure_scout",
        "pressure_scout_rotation_off",
        "pressure_scout_rotation_on",
        "early_low_band",
        "early_low_band_rotation_off",
        "early_low_band_rotation_on",
        "next_tier_low_band",
        "next_tier_low_band_rotation_off",
        "next_tier_low_band_rotation_on",
        "almost_sure_thing",
        "almost_sure_thing_rotation_off",
        "almost_sure_thing_rotation_on",
    }
    scenarios = []
    for raw in settings.get("scenarios") or []:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("id") or "")
        base_id = str(raw.get("base_scenario_id") or sid)
        if sid in legacy_scenario_ids or base_id in legacy_scenario_ids:
            continue
        base = dict(defaults_by_id.get(sid, {}))
        base.update(raw)
        if not base.get("id"):
            continue
        if str(base.get("id") or "") == "route_evidence":
            base["notional_pct_bank"] = 1.0
            base["cooldown_minutes"] = 0
        base["enabled"] = bool(base.get("enabled", True))
        base["min_present_score"] = int(max(0, min(100, int(base.get("min_present_score") or 0))))
        base["max_present_score"] = int(max(base["min_present_score"], min(100, int(base.get("max_present_score") or 100))))
        base["notional_pct_bank"] = max(0.0, float(base.get("notional_pct_bank") or 0.0))
        base["hold_minutes"] = max(1.0, float(base.get("hold_minutes") or 10.0))
        base["cooldown_minutes"] = max(0.0, float(base.get("cooldown_minutes") or 0.0))
        base["stop_loss_bps"] = max(0.0, float(base.get("stop_loss_bps") or 0.0))
        base["take_profit_bps"] = max(0.0, float(base.get("take_profit_bps") or 0.0))
        base["exit_score_drop"] = int(max(0, int(base.get("exit_score_drop") or 0)))
        base["rotation_enabled"] = bool(base.get("rotation_enabled", False))
        base["rotation_min_score_advantage"] = int(max(0, int(base.get("rotation_min_score_advantage") or 10)))
        base["rotation_min_underperform_bps"] = float(base.get("rotation_min_underperform_bps", -5.0))
        base["rotation_require_degrading"] = bool(base.get("rotation_require_degrading", True))
        scenarios.append(base)
    if not scenarios:
        scenarios = list(defaults_by_id.values())
    settings["scenarios"] = scenarios
    return settings


def _save_mock_trade_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = _default_mock_trade_settings()
    merged.update(settings)
    merged.pop("exit_params_map", None)
    merged.pop("exit_params_loaded", None)
    tmp = _MOCK_TRADE_SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    os.replace(tmp, _MOCK_TRADE_SETTINGS_PATH)
    return _load_mock_trade_settings()

# ---------------------------------------------------------------------------
# DEMO MODE — emits synthetic signals for empty-state UI demonstration
#
# XXX TODO: revert to False before Tier 1 launch. Tracked in /TODO.md
#
# When True, _poll_one also emits a signal event when an EQUILIBRIUM chunk
# has |mean_dipole| > 0.3 AND |volume_zscore| > 0.5 (the autoresearch-
# derived mean-reversion condition). This populates the signal feed for
# UI demos before real WHALE/HERD/WASH transitions accumulate from the
# multi-day GHA data collection.
#
# Production semantics (DEMO_MODE = False): only emit on regime transitions
# to actionable states (WHALE_*, HERD_*, WASH_PAIRED). EQUILIBRIUM is the
# baseline and shouldn't spam the feed.
# ---------------------------------------------------------------------------
DEMO_MODE_EMIT_EQUILIBRIUM_EXTREMES = os.environ.get(
    "MARKETS_WATCH_DEMO_MODE", "1"
) == "1"
DEMO_DIPOLE_THRESHOLD = 0.3
DEMO_VOL_Z_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# VPIN calibration: per-(asset, venue) thresholds + bucket sizes loaded
# from vpin_calibration.json (produced by calibrate_vpin.py). Fallback
# to literature defaults when the file is missing or an entry is absent.
# ---------------------------------------------------------------------------

_VPIN_CALIBRATION_PATH = os.path.join(REPO_ROOT, "vpin_calibration.json")
_VPIN_DEFAULT_ELEVATED = 0.30
_VPIN_DEFAULT_DIFFUSE = 0.08


def _load_vpin_calibration() -> dict:
    """Read vpin_calibration.json once at module load. Returns the
    per-(asset, venue) calibration dict, or {} if the file is missing
    or malformed. Errors are non-fatal — the classifier will use
    hardcoded defaults."""
    if not os.path.exists(_VPIN_CALIBRATION_PATH):
        print(f"[vpin] no calibration file at {_VPIN_CALIBRATION_PATH}; "
              f"using defaults (elevated={_VPIN_DEFAULT_ELEVATED}, "
              f"diffuse={_VPIN_DEFAULT_DIFFUSE})", flush=True)
        return {}
    try:
        with open(_VPIN_CALIBRATION_PATH) as f:
            payload = json.load(f)
        cal = payload.get("calibration", {}) or {}
        print(f"[vpin] loaded calibration for {len(cal)} (asset, venue) "
              f"entries from {_VPIN_CALIBRATION_PATH}", flush=True)
        return cal
    except Exception as e:
        print(f"[vpin] could not parse calibration: {e}; using defaults",
              flush=True)
        return {}


_VPIN_CAL = _load_vpin_calibration()


# ---------------------------------------------------------------------------
# F10 Hawkes-η calibration loader. Mirrors VPIN structure. Calibration is
# computed over directional regimes only (Pass-7 finding: η is regime-
# dependent — venue-wide thresholds would always rank WHALE as "high η"
# and EQUILIBRIUM as "low η", giving no information).
# ---------------------------------------------------------------------------

_HAWKES_CALIBRATION_PATH = os.path.join(REPO_ROOT, "hawkes_eta_calibration.json")
_HAWKES_DEFAULT_ELEVATED = 0.45
_HAWKES_DEFAULT_DIFFUSE = 0.20


def _load_hawkes_calibration() -> dict:
    if not os.path.exists(_HAWKES_CALIBRATION_PATH):
        print(f"[hawkes] no calibration at {_HAWKES_CALIBRATION_PATH}; "
              f"using defaults (elevated={_HAWKES_DEFAULT_ELEVATED}, "
              f"diffuse={_HAWKES_DEFAULT_DIFFUSE})", flush=True)
        return {}
    try:
        with open(_HAWKES_CALIBRATION_PATH) as f:
            payload = json.load(f)
        cal = payload.get("calibration", {}) or {}
        print(f"[hawkes] loaded calibration for {len(cal)} (asset, venue) "
              f"entries from {_HAWKES_CALIBRATION_PATH}", flush=True)
        return cal
    except Exception as e:
        print(f"[hawkes] could not parse calibration: {e}; using defaults",
              flush=True)
        return {}


_HAWKES_CAL = _load_hawkes_calibration()


def _hawkes_thresholds_for(asset: str, venue: str) -> tuple[float, float]:
    entry = _HAWKES_CAL.get(f"{asset}/{venue}") or {}
    elevated = entry.get("elevated")
    diffuse = entry.get("diffuse")
    return (
        float(elevated) if elevated is not None else _HAWKES_DEFAULT_ELEVATED,
        float(diffuse) if diffuse is not None else _HAWKES_DEFAULT_DIFFUSE,
    )


def _vpin_thresholds_for(asset: str, venue: str) -> tuple[float, float]:
    """Return (elevated, diffuse) thresholds for this (asset, venue).
    Falls back to defaults when the entry isn't in the calibration."""
    entry = _VPIN_CAL.get(f"{asset}/{venue}") or {}
    elevated = float(entry.get("elevated", _VPIN_DEFAULT_ELEVATED))
    diffuse = float(entry.get("diffuse", _VPIN_DEFAULT_DIFFUSE))
    return elevated, diffuse


def _vpin_bucket_volume_for(asset: str, venue: str) -> float:
    """Return bucket_volume from calibration; 0 means caller falls back
    to per-chunk dynamic sizing (degraded but functional)."""
    entry = _VPIN_CAL.get(f"{asset}/{venue}") or {}
    return float(entry.get("bucket_volume", 0.0))


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

@dataclass
class RegimeStatus:
    asset: str
    venue: str
    regime: str
    confidence: float
    cross_venue_multiplier: float
    adjusted_confidence: float
    notes: list[str]
    mean_dipole: float
    realized_vol: float
    chunk_window: tuple[int, int]
    last_update_utc: float
    # Consumer-facing fields (added 1.5e): user-readable summary of what's
    # happening on this chunk, with no math jargon. The classifier's
    # internal features (mean_dipole, realized_vol) are not surfaced in
    # the UI; these derived fields are.
    current_price: float = 0.0
    current_bid: float = 0.0
    current_ask: float = 0.0
    last_aggressor: str = ""             # "buy" | "sell" | "" — UI flashes the side that was hit
    chunk_buy_volume: float = 0.0
    chunk_sell_volume: float = 0.0
    chunk_n_trades: int = 0
    # Microstructure toxicity (VPIN). High = informed flow concentrated;
    # surfaces alongside the regime so PWA/Discord can flag "informed
    # cascade" vs "retail flutter" without a separate signal type.
    vpin: float = 0.0
    vpin_multiplier: float = 1.0
    # F7 cross-asset directional confirmation (BTC <-> ETH).
    cross_asset_multiplier: float = 1.0
    # F8 scheduled-event / weekend confidence dampener (<=1.0).
    event_multiplier: float = 1.0
    # F9 Hurst exponent (DFA) + label. Orthogonal trending/reverting axis.
    hurst: float = 0.5
    hurst_label: str = ""
    # F10 Hawkes branching-ratio multiplier on directional regimes.
    hawkes_multiplier: float = 1.0
    # F11 multi-horizon edge tags (intraday / daily / weekly / long-term).
    # Surface on /api/status so PWA + Discord can show the four-track read.
    edge_summary: str = ""                # one-liner for display
    edge_intraday_strength: str = "NEW"   # STRONG | MODERATE | WEAK | NEW
    edge_daily_strength: str = "NEW"
    edge_weekly_strength: str = "NEW"
    edge_longterm_strength: str = "NEW"
    edge_intraday_self_trend: str = "NEW"  # STRENGTHENING | DECAYING | FLIPPING | STABLE | NEW
    edge_daily_self_trend: str = "NEW"
    edge_weekly_self_trend: str = "NEW"
    edge_longterm_self_trend: str = "NEW"
    convergence_support_count: int = 0
    convergence_direction: str = ""
    convergence_side: str = ""
    convergence_cell_ids: list[str] = field(default_factory=list)
    convergence_features: list[str] = field(default_factory=list)
    convergence_tier: str = ""
    convergence_bonus: float = 1.0
    convergence_summary: str = ""
    # Internal pressure-watch layer. Built from dipole-derived features but
    # exposed only in trader-native language. This is an amber state, not an
    # actionable signal by itself.
    pressure_watch_state: str = ""       # "" | internal | forming | transition_risk | high_priority | confirmed
    pressure_watch_label: str = ""       # e.g. Buy pressure forming
    pressure_watch_direction: str = ""   # buy | sell
    pressure_watch_intensity: str = ""   # weak | moderate | high
    pressure_watch_priority: int = 0     # 0-3
    pressure_watch_reasons: list[str] = field(default_factory=list)
    # Optional trade setup guidance. This is a decision aid for practice/live
    # intent flow, not automatic execution.
    trade_option_state: str = ""         # "" | watch | early_probe | confirmed
    trade_option_label: str = ""
    trade_option_side: str = ""          # buy | sell
    trade_option_readiness: int = 0      # 0-100
    trade_option_profile: str = ""       # early_probe | confirmed_follow | late_no_trade
    trade_option_size_hint: str = ""
    trade_option_notional_scale: float = 0.0
    trade_option_hold_minutes: int = 0
    trade_stage: str = ""                # onset | early_follow | mature | late
    trade_age_chunks: int = 0
    trade_present_score: int = 0
    trade_score_band: str = ""
    trade_from_onset_bps: float = 0.0
    trade_current_chunk_bps: float = 0.0
    trade_recent_2chunk_bps: float = 0.0
    trade_option_entry_reasons: list[str] = field(default_factory=list)
    trade_option_exit_rules: list[str] = field(default_factory=list)
    trade_option_blockers: list[str] = field(default_factory=list)
    trade_strategy_id: str = ""
    trade_strategy_label: str = ""
    trade_strategy_confidence: float = 0.0
    trade_strategy_side_override: str = ""
    trade_strategy_reasons: list[str] = field(default_factory=list)
    trade_strategy_blockers: list[str] = field(default_factory=list)
    trade_strategy_stop_loss_bps: float = 0.0
    trade_strategy_take_profit_bps: float = 0.0
    trade_strategy_exit_score_drop: int = 0
    trade_strategy_forced: bool = False
    trade_strategy_variant_id: str = ""
    trade_strategy_risk_tags: list[str] = field(default_factory=list)
    trade_strategy_handoff_hint: str = ""
    trade_strategy_source_queue_action: str = ""
    high_conviction_ticket: dict[str, Any] = field(default_factory=dict)
    daily_news_context: dict[str, Any] = field(default_factory=dict)
    daily_news_status: dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalEvent:
    signal_id: str
    asset: str
    venue: str
    regime: str
    confidence: float
    cross_venue_multiplier: float
    adjusted_confidence: float
    mean_dipole: float
    realized_vol: float
    chunk_volume: float
    notes: list[str]
    playbook: str
    timestamp_utc: float
    chunk_window: tuple[int, int]
    # Phase 1.5b: outcome tracking
    entry_price: float = 0.0
    expected_direction: int = 0          # +1 long bias, -1 short bias, 0 unclear
    outcome_status: str = "pending"      # pending | resolved | abandoned
    outcome_exit_price: float = 0.0
    outcome_resolved_utc: float = 0.0
    outcome_realized_bps: float = 0.0    # signed return in bps after fees
    # Phase 1.5c: cascade flagging — set when a HERD signal arrives directly
    # from a WHALE chunk in the same direction with no equilibrium gap
    # (single-venue) or when the other venue is concurrently in the
    # opposite-kind regime (cross-venue WHALE+HERD simultaneity).
    cascade_event: str = ""              # "" | "WHALE_TO_HERD_UP" | "WHALE_TO_HERD_DOWN" | "CROSS_VENUE_WHALE_HERD"
    cascade_detail: str = ""             # human-readable
    # Buy/sell side breakdown so the UI / Discord post can show absolute
    # buy_vol vs sell_vol on this chunk (the regime label already encodes
    # net direction; this is the magnitude).
    chunk_buy_volume: float = 0.0
    chunk_sell_volume: float = 0.0
    chunk_n_trades: int = 0              # total individual trades on this chunk
    current_price: float = 0.0           # latest close on this chunk
    current_bid: float = 0.0             # latest top-of-book bid
    current_ask: float = 0.0             # latest top-of-book ask
    last_aggressor: str = ""             # "buy" | "sell" | "" — UI flashes the side that was hit
    event_label: str = ""                # plain-language event description e.g. "Big buyer detected"
    drift_status: str = ""               # "" | "recently_flipped" | "unstable" | "decaying" — surfaced in UI as a warning badge when the cell's edge is in flux
    # Microstructure toxicity (VPIN). Carried on signal so consumers can
    # filter (e.g., paper-trade only when vpin >= 0.30).
    vpin: float = 0.0
    vpin_multiplier: float = 1.0
    # F7 cross-asset directional confirmation (BTC <-> ETH).
    cross_asset_multiplier: float = 1.0
    # F8 scheduled-event / weekend confidence dampener (<=1.0).
    event_multiplier: float = 1.0
    # F9 Hurst exponent + label (orthogonal trending/reverting axis).
    hurst: float = 0.5
    hurst_label: str = ""
    # F10 Hawkes branching-ratio multiplier on directional regimes.
    hawkes_multiplier: float = 1.0
    # F11 multi-horizon edge tags (long-term / weekly / daily).
    edge_summary: str = ""
    edge_daily_strength: str = "NEW"
    edge_weekly_strength: str = "NEW"
    edge_longterm_strength: str = "NEW"
    edge_daily_self_trend: str = "NEW"
    edge_weekly_self_trend: str = "NEW"
    edge_longterm_self_trend: str = "NEW"
    signal_tier: str = "actionable"
    convergence_support_count: int = 0
    convergence_direction: str = ""
    convergence_side: str = ""
    convergence_cell_ids: list[str] = field(default_factory=list)
    convergence_features: list[str] = field(default_factory=list)
    convergence_tier: str = ""
    convergence_bonus: float = 1.0
    convergence_summary: str = ""
    # Pressure-watch context present when this signal fired. Derived from
    # internal dipole features, surfaced only as trader-safe copy.
    pressure_watch_state: str = ""
    pressure_watch_label: str = ""
    pressure_watch_direction: str = ""
    pressure_watch_intensity: str = ""
    pressure_watch_priority: int = 0
    pressure_watch_reasons: list[str] = field(default_factory=list)
    trade_option_state: str = ""
    trade_option_label: str = ""
    trade_option_side: str = ""
    trade_option_readiness: int = 0
    trade_option_profile: str = ""
    trade_option_size_hint: str = ""
    trade_option_notional_scale: float = 0.0
    trade_option_hold_minutes: int = 0
    trade_option_entry_reasons: list[str] = field(default_factory=list)
    trade_option_exit_rules: list[str] = field(default_factory=list)
    trade_option_blockers: list[str] = field(default_factory=list)
    trade_strategy_id: str = ""
    trade_strategy_label: str = ""
    trade_strategy_confidence: float = 0.0
    trade_strategy_side_override: str = ""
    trade_strategy_reasons: list[str] = field(default_factory=list)
    trade_strategy_blockers: list[str] = field(default_factory=list)
    trade_strategy_stop_loss_bps: float = 0.0
    trade_strategy_take_profit_bps: float = 0.0
    trade_strategy_exit_score_drop: int = 0
    trade_strategy_forced: bool = False
    trade_strategy_variant_id: str = ""
    trade_strategy_risk_tags: list[str] = field(default_factory=list)
    trade_strategy_handoff_hint: str = ""
    trade_strategy_source_queue_action: str = ""
    high_conviction_ticket: dict[str, Any] = field(default_factory=dict)
    daily_news_context: dict[str, Any] = field(default_factory=dict)
    daily_news_status: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Playbook strings per regime (the actionable text users see)
# ---------------------------------------------------------------------------

PLAYBOOKS: dict[str, str] = {
    "EQUILIBRIUM_TWO_SIDED": "Healthy two-sided market. No edge. Sit out unless flow becomes extremely one-sided.",
    "WHALE_UP": "One big buyer dominating. Piggyback if early; get out of the way if late. Watch for the buyer's order to finish.",
    "WHALE_DOWN": "One big seller dominating. Piggyback short if early; sit out if late. Watch for capitulation bottom.",
    "WHALE_NASCENT_UP": "Buy pressure building, not yet sustained. Working hypothesis: trend continues until full WHALE classification kicks in.",
    "WHALE_NASCENT_DOWN": "Sell pressure building, not yet sustained. Working hypothesis: trend continues until full WHALE classification kicks in.",
    "HERD_UP": "FOMO / panic buy — many actors aligned on the buy side. Follow with tight stops; fade after overshoot.",
    "HERD_DOWN": "Panic sell / capitulation — many actors aligned on the sell side. Fade after the worst is over; do NOT catch the falling knife.",
    "WASH_PAIRED": "Wash-trade signature: paired self-trades, no real price discovery. Do not trade.",
    "WASH_HAWKES": "Hawkes wash signature: both buy and sell flows cluster simultaneously with balanced volume. Likely wash / self-trade activity at bar resolution. Do not trade — no real price discovery to ride.",
    "DEPLETED": "Market is asleep (lunch / off-hours). Sit out — there's no flow to ride.",
    "UNKNOWN": "Pattern doesn't match a known regime. Skip until classifier resolves.",
}

# Plain-language event labels for user-facing surfaces (Discord title, push
# notification title, phone-app card). Deliberately free of math jargon —
# no "dipole", no "realized vol", no "autocorrelation". Whatever happens,
# the user sees a human sentence.
EVENT_LABELS: dict[str, str] = {
    "WHALE_UP":    "Big buyer detected",
    "WHALE_DOWN":  "Big seller detected",
    "HERD_UP":     "Buying cascade detected",
    "HERD_DOWN":   "Selling cascade detected",
    "WASH_PAIRED": "Wash-trade pattern detected — skip",
    "WASH_HAWKES": "Hawkes wash signature detected — skip",
    "DEPLETED":    "Market quiet — no activity",
    "EQUILIBRIUM_TWO_SIDED": "Healthy two-sided trading",
    "UNKNOWN":     "Unclassified pattern",
}


STRONG_PRESSURE_REGIMES = {
    "WHALE_UP", "WHALE_DOWN", "HERD_UP", "HERD_DOWN",
}


def _pressure_direction(sign: int) -> str:
    return "buy" if sign > 0 else "sell" if sign < 0 else ""


def _pressure_label(direction: str, state: str) -> str:
    side = "Buy" if direction == "buy" else "Sell" if direction == "sell" else ""
    if state == "high_priority":
        return f"{side} pressure across venues".strip()
    if state == "transition_risk":
        return f"{side} pressure transition risk".strip()
    if state == "confirmed":
        return f"{side} pressure confirmed".strip()
    if state == "forming":
        return f"{side} pressure forming".strip()
    if state == "internal":
        return f"{side} pressure watch".strip()
    return ""


def _pressure_watch_from_features(
    *,
    regime: str,
    mean_dipole: float,
    volume_zscore: float,
    dipole_acl1: float,
    prev_mean_dipole: float | None,
) -> dict[str, Any]:
    """Return trader-safe pressure-watch metadata.

    Dipole stays internal; output is the reusable platform primitive. The
    states intentionally describe watch quality, not trade instructions.
    """
    sign = 1 if mean_dipole > 0 else -1 if mean_dipole < 0 else 0
    if sign == 0:
        return {}
    abs_d = abs(float(mean_dipole))
    direction = _pressure_direction(sign)
    prev_abs = abs(float(prev_mean_dipole)) if prev_mean_dipole is not None else 0.0
    prev_sign = (
        1 if (prev_mean_dipole or 0.0) > 0
        else -1 if (prev_mean_dipole or 0.0) < 0
        else 0
    )
    persistent = prev_sign == sign and prev_abs >= 0.15
    weak = 0.15 <= abs_d < 0.25
    moderate = abs_d >= 0.30
    volume_confirmed = moderate and volume_zscore >= 0.0
    autocorr_confirmed = moderate and dipole_acl1 >= 0.0

    if regime in STRONG_PRESSURE_REGIMES:
        state = "confirmed"
        priority = 3
        intensity = "high"
        reasons = ["Whale/Herd confirmation is active"]
    elif regime.startswith("WHALE_NASCENT"):
        state = "forming"
        priority = 2
        intensity = "moderate"
        reasons = ["Early Whale pressure is already visible"]
    elif volume_confirmed:
        state = "forming"
        priority = 2
        intensity = "moderate"
        reasons = ["Directional pressure with elevated volume"]
    elif autocorr_confirmed:
        state = "transition_risk"
        priority = 2
        intensity = "moderate"
        reasons = ["Sustained pressure pattern can precede a regime change"]
    elif weak and persistent:
        state = "forming"
        priority = 1
        intensity = "weak"
        reasons = ["Pressure persisted across consecutive chunks"]
    elif weak:
        state = "internal"
        priority = 1
        intensity = "weak"
        reasons = ["Early imbalance watch"]
    else:
        return {}

    return {
        "pressure_watch_state": state,
        "pressure_watch_label": _pressure_label(direction, state),
        "pressure_watch_direction": direction,
        "pressure_watch_intensity": intensity,
        "pressure_watch_priority": priority,
        "pressure_watch_reasons": reasons,
    }


def _apply_pressure_fields(target: Any, watch: dict[str, Any]) -> None:
    target.pressure_watch_state = str(watch.get("pressure_watch_state") or "")
    target.pressure_watch_label = str(watch.get("pressure_watch_label") or "")
    target.pressure_watch_direction = str(watch.get("pressure_watch_direction") or "")
    target.pressure_watch_intensity = str(watch.get("pressure_watch_intensity") or "")
    target.pressure_watch_priority = int(watch.get("pressure_watch_priority") or 0)
    target.pressure_watch_reasons = list(watch.get("pressure_watch_reasons") or [])


def _trade_stage_from_age(age_chunks: int) -> str:
    if age_chunks <= 1:
        return "onset"
    if age_chunks <= 3:
        return "early_follow"
    if age_chunks <= 8:
        return "mature"
    return "late"


def _trade_score_band(score: int) -> str:
    if score >= 85:
        return "85_100"
    if score >= 70:
        return "70_84"
    if score >= 55:
        return "55_69"
    if score >= 40:
        return "40_54"
    return "0_39"


def _signed_bps(entry: float, exit_price: float, side: str) -> float:
    if entry <= 0 or exit_price <= 0:
        return 0.0
    sign = 1 if side == "buy" else -1 if side == "sell" else 0
    if sign == 0:
        return 0.0
    return sign * math.log(max(exit_price, 1e-12) / max(entry, 1e-12)) * 10000.0


def _present_trade_score(status: RegimeStatus, inputs: dict[str, Any]) -> int:
    score = min(35.0, float(status.adjusted_confidence or status.confidence or 0.0) * 35.0)
    pressure_state = status.pressure_watch_state
    if status.regime in STRONG_PRESSURE_REGIMES:
        score += 25.0
    elif status.regime.startswith("WHALE_NASCENT"):
        score += 18.0
    elif pressure_state in ("forming", "high_priority"):
        score += 12.0
    elif pressure_state == "internal":
        score += 6.0

    abs_d = abs(float(inputs.get("mean_dipole") or status.mean_dipole or 0.0))
    if abs_d >= 0.50:
        score += 15.0
    elif abs_d >= 0.30:
        score += 10.0
    elif abs_d >= 0.15:
        score += 5.0

    volume_zscore = float(inputs.get("volume_zscore") or 0.0)
    if volume_zscore >= 1.0:
        score += 10.0
    elif volume_zscore >= 0.0:
        score += 6.0

    score += min(10.0, max(-12.0, float(inputs.get("trade_from_onset_bps") or 0.0) / 2.5))
    score += min(8.0, max(-12.0, float(inputs.get("trade_current_chunk_bps") or 0.0) / 2.0))

    age = int(inputs.get("trade_age_chunks") or 0)
    if age >= 9:
        score -= 14.0
    elif age >= 4:
        score -= 6.0

    if (float(inputs.get("trade_from_onset_bps") or 0.0) > 12.0
            and float(inputs.get("trade_recent_2chunk_bps") or 0.0) <= 0.0):
        score -= 8.0
    if float(inputs.get("trade_from_onset_bps") or 0.0) < -8.0:
        score -= 12.0

    return int(max(0, min(100, round(score))))


def _trade_option_from_status(status: RegimeStatus, inputs: dict[str, Any]) -> dict[str, Any]:
    direction = status.pressure_watch_direction
    if direction not in ("buy", "sell"):
        decision = classify_strategy(status, inputs)
        if decision.side_override not in ("buy", "sell"):
            return {}
        option = {
            "trade_option_state": "watch",
            "trade_option_label": f"{decision.side_override.title()} oracle-distilled watch",
            "trade_option_side": "",
            "trade_option_readiness": int(max(35, round(decision.confidence * 100))),
            "trade_option_profile": "oracle_distilled_context",
            "trade_option_size_hint": "practice learning size",
            "trade_option_notional_scale": 0.0,
            "trade_option_hold_minutes": 0,
            "trade_stage": str(inputs.get("trade_stage") or ""),
            "trade_age_chunks": int(inputs.get("trade_age_chunks") or 0),
            "trade_present_score": int(inputs.get("trade_present_score") or 0),
            "trade_score_band": str(inputs.get("trade_score_band") or ""),
            "trade_from_onset_bps": float(inputs.get("trade_from_onset_bps") or 0.0),
            "trade_current_chunk_bps": float(inputs.get("trade_current_chunk_bps") or 0.0),
            "trade_recent_2chunk_bps": float(inputs.get("trade_recent_2chunk_bps") or 0.0),
            "trade_option_entry_reasons": [],
            "trade_option_exit_rules": [],
            "trade_option_blockers": [],
            "trade_strategy_mode": str(inputs.get("strategy_mode") or "product"),
        }
        return apply_strategy_to_option(option, decision)
    side = direction
    blockers: list[str] = []
    reasons: list[str] = []
    exits = [
        "Exit if pressure flips the other way",
        "Exit if Whale/Herd does not confirm within the hold window",
        "Exit if price rejects the entry side",
    ]

    spread_bps = float(inputs.get("spread_bps") or 0.0)
    signed_move_bps = float(inputs.get("signed_move_bps") or 0.0)
    volume_zscore = float(inputs.get("volume_zscore") or 0.0)
    realized_vol_bps = float(inputs.get("realized_vol_bps") or 0.0)
    chunk_volume = float(inputs.get("chunk_total_volume") or 0.0)
    stage = str(inputs.get("trade_stage") or "onset")
    age_chunks = int(inputs.get("trade_age_chunks") or 0)
    news_context = load_daily_news_context(_DAILY_NEWS_CONTEXT_PATH)
    asset_news = news_context.for_asset(status.asset)
    base_present_score = int(inputs.get("trade_present_score") or _present_trade_score(status, inputs))
    present_score = base_present_score
    if news_context.status == "ok" and not news_context.stale:
        present_score = adjust_present_score_with_news(
            base_present_score,
            side,
            asset_news,
            news_dipole_value=asset_news.news_dipole,
        )
        inputs["trade_present_score"] = present_score
    score_band = _trade_score_band(present_score)
    from_onset_bps = float(inputs.get("trade_from_onset_bps") or 0.0)
    current_chunk_bps = float(inputs.get("trade_current_chunk_bps") or signed_move_bps)
    recent_2chunk_bps = float(inputs.get("trade_recent_2chunk_bps") or current_chunk_bps)

    if spread_bps <= 0:
        blockers.append("No usable bid/ask spread")
    elif spread_bps > 8.0:
        blockers.append(f"Spread too wide ({spread_bps:.1f} bps)")
    else:
        reasons.append(f"Spread acceptable ({spread_bps:.1f} bps)")

    extension_limit = max(12.0, realized_vol_bps * 1.25)
    if signed_move_bps > extension_limit:
        blockers.append(f"Move already extended ({signed_move_bps:.1f} bps)")
    else:
        reasons.append("Entry is not chasing an extended move")

    if chunk_volume <= 0:
        blockers.append("No traded volume in the current chunk")

    pressure_state = status.pressure_watch_state
    pressure_priority = int(status.pressure_watch_priority or 0)
    if pressure_state in ("forming", "high_priority"):
        reasons.append(status.pressure_watch_label or "Pressure forming")
    elif pressure_state == "transition_risk":
        blockers.append("Transition risk without clean directional edge")
    elif pressure_state == "confirmed":
        reasons.append("Whale/Herd pressure already confirmed")
    else:
        blockers.append("Pressure is not visible enough for an early trade")

    if status.regime in ("EQUILIBRIUM_TWO_SIDED", "DEPLETED", "UNKNOWN", "WASH_PAIRED", "WASH_HAWKES"):
        maturity = "early"
    elif status.regime.startswith("WHALE_NASCENT"):
        maturity = "early"
        reasons.append("Early Whale read is visible")
    elif status.regime in STRONG_PRESSURE_REGIMES:
        maturity = "confirmed"
    else:
        maturity = "watch"

    readiness = present_score
    legacy_readiness = int(round(float(status.adjusted_confidence or status.confidence or 0.0) * 45))
    legacy_readiness += min(25, pressure_priority * 8)
    if pressure_state == "high_priority":
        legacy_readiness += 12
    if volume_zscore >= 0:
        legacy_readiness += 8
    if spread_bps and spread_bps <= 4:
        legacy_readiness += 5
    if signed_move_bps <= 0:
        legacy_readiness += 5
    readiness = max(readiness, int(round(legacy_readiness * 0.75)))
    readiness = max(0, min(100, readiness))

    if present_score != base_present_score:
        reasons.append(f"News-adjusted present score {present_score}/100 from {base_present_score}/100")
    reasons.append(f"Present score {present_score}/100 ({stage.replace('_', ' ')}, age {age_chunks} chunks)")
    if from_onset_bps > 0:
        reasons.append(f"Move has worked {from_onset_bps:.1f} bps from setup onset")

    if stage == "late":
        blockers.append("Setup is late-stage; wait for a fresh onset or manual override")
    if present_score < 55:
        blockers.append(f"Present score below trade threshold ({present_score}/100)")
    hot_onset_limit = max(25.0, realized_vol_bps * 1.5)
    if stage == "onset" and present_score >= 85 and current_chunk_bps > hot_onset_limit:
        blockers.append(f"Very hot onset ({current_chunk_bps:.1f} bps); avoid chasing")
    if stage in ("mature", "late") and recent_2chunk_bps <= 0 and present_score >= 70:
        blockers.append("Setup is strong but no longer advancing over the recent window")

    if maturity == "confirmed" and stage in ("onset", "early_follow") and readiness >= 70 and not blockers:
        state = "confirmed"
        profile = "confirmed_follow"
        label = f"{side.title()} confirmed setup"
        size_hint = "normal size if risk gates pass"
        scale = 1.0
        hold = 15
    elif readiness >= 55 and not blockers:
        state = "early_probe"
        profile = "early_probe"
        label = (
            f"{side.title()} continuation probe"
            if stage == "mature" else f"{side.title()} early probe"
        )
        size_hint = "probe size, about 35% normal" if stage == "mature" else "probe size, about 25% normal"
        scale = 0.35 if stage == "mature" else 0.25
        hold = 10
    else:
        state = "watch"
        profile = "early_watch"
        label = f"{side.title()} watch only"
        size_hint = "no position yet"
        scale = 0.0
        hold = 0

    option = {
        "trade_option_state": state,
        "trade_option_label": label,
        "trade_option_side": side,
        "trade_option_readiness": readiness,
        "trade_option_profile": profile,
        "trade_option_size_hint": size_hint,
        "trade_option_notional_scale": scale,
        "trade_option_hold_minutes": hold,
        "trade_stage": stage,
        "trade_age_chunks": age_chunks,
        "trade_present_score": present_score,
        "trade_score_band": score_band,
        "trade_from_onset_bps": from_onset_bps,
        "trade_current_chunk_bps": current_chunk_bps,
        "trade_recent_2chunk_bps": recent_2chunk_bps,
        "trade_option_entry_reasons": reasons[:5],
        "trade_option_exit_rules": exits,
        "trade_option_blockers": blockers[:5],
        "trade_strategy_mode": str(inputs.get("strategy_mode") or "product"),
    }
    option = apply_strategy_to_option(option, classify_strategy(status, inputs, asset_news))
    return news_adjusted_trade_option(option, news_context, status.asset, side)


def _apply_trade_option_fields(target: Any, option: dict[str, Any]) -> None:
    target.trade_option_state = str(option.get("trade_option_state") or "")
    target.trade_option_label = str(option.get("trade_option_label") or "")
    target.trade_option_side = str(option.get("trade_option_side") or "")
    target.trade_option_readiness = int(option.get("trade_option_readiness") or 0)
    target.trade_option_profile = str(option.get("trade_option_profile") or "")
    target.trade_option_size_hint = str(option.get("trade_option_size_hint") or "")
    target.trade_option_notional_scale = float(option.get("trade_option_notional_scale") or 0.0)
    target.trade_option_hold_minutes = int(option.get("trade_option_hold_minutes") or 0)
    target.trade_stage = str(option.get("trade_stage") or "")
    target.trade_age_chunks = int(option.get("trade_age_chunks") or 0)
    target.trade_present_score = int(option.get("trade_present_score") or 0)
    target.trade_score_band = str(option.get("trade_score_band") or "")
    target.trade_from_onset_bps = float(option.get("trade_from_onset_bps") or 0.0)
    target.trade_current_chunk_bps = float(option.get("trade_current_chunk_bps") or 0.0)
    target.trade_recent_2chunk_bps = float(option.get("trade_recent_2chunk_bps") or 0.0)
    target.trade_option_entry_reasons = list(option.get("trade_option_entry_reasons") or [])
    target.trade_option_exit_rules = list(option.get("trade_option_exit_rules") or [])
    target.trade_option_blockers = list(option.get("trade_option_blockers") or [])
    target.trade_strategy_id = str(option.get("trade_strategy_id") or "")
    target.trade_strategy_label = str(option.get("trade_strategy_label") or "")
    target.trade_strategy_confidence = float(option.get("trade_strategy_confidence") or 0.0)
    target.trade_strategy_side_override = str(option.get("trade_strategy_side_override") or "")
    target.trade_strategy_reasons = list(option.get("trade_strategy_reasons") or [])
    target.trade_strategy_blockers = list(option.get("trade_strategy_blockers") or [])
    target.trade_strategy_stop_loss_bps = float(option.get("trade_strategy_stop_loss_bps") or 0.0)
    target.trade_strategy_take_profit_bps = float(option.get("trade_strategy_take_profit_bps") or 0.0)
    target.trade_strategy_exit_score_drop = int(option.get("trade_strategy_exit_score_drop") or 0)
    target.trade_strategy_forced = bool(option.get("trade_strategy_forced"))
    target.trade_strategy_variant_id = str(option.get("trade_strategy_variant_id") or "")
    target.trade_strategy_risk_tags = list(option.get("trade_strategy_risk_tags") or [])
    target.trade_strategy_handoff_hint = str(option.get("trade_strategy_handoff_hint") or "")
    target.trade_strategy_source_queue_action = str(option.get("trade_strategy_source_queue_action") or "")
    target.daily_news_context = dict(option.get("daily_news_context") or {})
    target.daily_news_status = dict(option.get("daily_news_status") or {})


def _apply_high_conviction_ticket(target: Any, inputs: dict[str, Any]) -> None:
    target.high_conviction_ticket = build_high_conviction_ticket(
        target,
        inputs,
        mode="practice",
    )

# Cascade playbooks override the base regime playbook when WHALE→HERD
# direct transition fires (whale-tripped-the-herd; higher conviction).
CASCADE_PLAYBOOKS: dict[str, str] = {
    "WHALE_TO_HERD_UP": (
        "Whale-tripped FOMO. Big buyer's pressure pulled the herd in. "
        "Highest-conviction long-side cascade: ride with very tight stop, "
        "exit on first sign of buying exhaustion (volume drops, dipole "
        "fades). Do NOT chase late - the overshoot is where the fade "
        "trade lives."
    ),
    "WHALE_TO_HERD_DOWN": (
        "Whale-tripped capitulation. Big seller's pressure broke retail "
        "stops; herd is selling the fear. Highest-conviction short-side "
        "cascade: short the cascade with a tight stop, OR wait for the "
        "fade-buy at exhaustion (volume drops, dipole flips). Do NOT "
        "catch the falling knife mid-cascade."
    ),
}

# Cross-venue cascade: WHALE on one venue + HERD on the other, same direction
# in the same wall-clock window. Independent confirmation across venues =
# strongest possible regime signal we can emit (top-of-book event).
CROSS_VENUE_CASCADE_PLAYBOOKS: dict[str, str] = {
    "CROSS_VENUE_WHALE_HERD_UP": (
        "CROSS-VENUE WHALE+HERD UP: one venue shows whale-style sustained "
        "buying, the other shows herd-style multi-actor FOMO, same "
        "direction, same wall-clock window. Independent confirmation across "
        "venues = strongest long signal we can emit. Size accordingly. "
        "Tight stop; exit before the fade."
    ),
    "CROSS_VENUE_WHALE_HERD_DOWN": (
        "CROSS-VENUE WHALE+HERD DOWN: one venue shows whale-style sustained "
        "selling, the other shows herd-style multi-actor capitulation, same "
        "direction, same wall-clock window. Independent confirmation across "
        "venues = strongest short signal we can emit. Size accordingly. "
        "Tight stop; do NOT catch the knife on the way down."
    ),
}


# ---------------------------------------------------------------------------
# Direction inference (matches executor logic)
# ---------------------------------------------------------------------------

def expected_direction_from_signal(regime: str, mean_dipole: float) -> int:
    if regime.endswith("_UP"):
        return +1
    if regime.endswith("_DOWN"):
        return -1
    if regime in ("EQUILIBRIUM_TWO_SIDED", "EQUILIBRIUM_EXTREME_DEMO"):
        return -1 if mean_dipole > 0 else +1   # fade
    return 0


# ---------------------------------------------------------------------------
# SignalStore: polls bins, runs classifier, accumulates events
# ---------------------------------------------------------------------------

class SignalStore:
    def __init__(self):
        self.current_status: dict[tuple[str, str], RegimeStatus] = {}
        self.recent_signals: deque[SignalEvent] = deque(maxlen=RECENT_SIGNALS_CAP)
        self.signal_index: dict[str, SignalEvent] = {}
        self.event_queue: asyncio.Queue[dict] = asyncio.Queue()
        self.last_chunk_id_per_source: dict[tuple[str, str], str | None] = {}
        # Tracks the chunk id we last considered for forward paper-trade
        # cell predicates, so we open at most one trade per cell per chunk.
        self.last_paper_chunk_id_per_source: dict[tuple[str, str], str | None] = {}
        # Cross-venue minute->regime maps for F6 multiplier
        self._minute_regime_per_venue: dict[tuple[str, str], dict[float, str]] = {}
        # Latest fully-classified chunk per (asset, venue) — needed by
        # _emit_cross_venue_cascades to read wall-clock windows + bars
        self._latest_chunk_per_venue: dict[tuple[str, str], "MarketChunk"] = {}
        # Latest pressure-watch inputs per (asset, venue). Raw dipole stays
        # internal; _apply_pressure_watch converts this into trader-safe
        # status fields after all venues have polled.
        self._pressure_inputs: dict[tuple[str, str], dict[str, Any]] = {}
        self._pressure_watch_alerted: set[tuple] = set()
        self._mock_opportunity_logged: set[str] = set()
        # Present-tense trade setup tracker. Historical pass-22 showed stage
        # matters: a strong read at onset is different from a mature continuation.
        self._trade_setup_tracker: dict[tuple[str, str], dict[str, Any]] = {}
        # Dedup set for cross-venue cascade emits (asset, frozenset(venues),
        # window_start_ts, window_end_ts). Reset on backend restart.
        self._cross_venue_cascade_emitted: set[tuple] = set()
        # Per-cell signal-outcome contradiction streak. When a signal whose
        # registry cell predicts "momentum" actually loses (or vice versa),
        # we increment the streak; on a streak >= 3, we emit a drift_alert
        # SSE event so users see real-time drift before waiting for the
        # next registry rebuild.
        self._cell_contradiction_streak: dict[str, int] = {}
        # Recent drift alerts kept in memory for fast /api/drift-alerts read.
        self.recent_drift_alerts: deque[dict] = deque(maxlen=200)
        self._controls_path = os.path.join(
            REPO_ROOT, DEFAULT_CONTROLS_OUTPUT_PATH)
        self._controls_refresh_interval_s = 300.0
        self._next_controls_refresh_utc = 0.0
        self._suppressed_cell_ids: set[str] = set()
        # Persistent signal log (JSONL); restored on startup
        self._persist_path = os.path.join(REPO_ROOT, "backend_signals.jsonl")
        self._drift_alerts_path = os.path.join(REPO_ROOT, "backend_drift_alerts.jsonl")
        self._restore_signals()
        self._restore_drift_alerts()
        # Spot-perp basis tracker; emits BASIS_DIVERGENT_{HOT,COLD,CLEARED}
        # drift alerts when (perp - spot) drifts beyond a rolling-z
        # threshold and stays there for SUSTAINED_CYCLES polls.
        self.basis_monitor = BasisMonitor(BASIS_SPOT_PATHS, BASIS_PERP_PATHS)
        # Perp funding-rate watcher; emits FUNDING_OVERLEVERED_{LONG,SHORT}
        # / FUNDING_CLEARED on threshold transitions. Persists every
        # new funding-cycle observation to backend_funding_history.jsonl.
        # funding_calibration.json (from calibrate_funding.py once
        # ~30+ cycles accumulate) gives per-(asset, venue) p75/p95
        # thresholds; absent => hardcoded fallback.
        self.funding_monitor = FundingMonitor(
            history_path=os.path.join(REPO_ROOT, "backend_funding_history.jsonl"),
            calibration_path=os.path.join(REPO_ROOT, "funding_calibration.json"))
        # Liquidation-burst detector. Reads the same perp bins the basis
        # monitor uses; flags 1-min bars with extreme volume z + one-sided
        # flow + bar-to-bar price gap. Synthetic detection on existing
        # data; upgrade path is a real WSS liquidation feed.
        # liq_calibration.json (from calibrate_liq.py) gives per-asset
        # p99 thresholds; absent => hardcoded fallback.
        self.liq_monitor = LiqMonitor(
            BASIS_PERP_PATHS,
            calibration_path=os.path.join(REPO_ROOT, "liq_calibration.json"))
        # Open-interest watcher. Polls Binance + Bybit perp APIs each
        # cycle; emits OI_BUILDING_{LONG,SHORT} / OI_UNWIND_{SHORTS,LONGS}
        # / OI_CLEARED on Δoi-z transitions. Persists every observation
        # to backend_oi_history.jsonl. oi_calibration.json (from
        # calibrate_oi.py once history accumulates) overrides the
        # hardcoded build_z / clear_z thresholds per (asset, venue).
        self.oi_monitor = OIMonitor(
            history_path=os.path.join(REPO_ROOT, "backend_oi_history.jsonl"),
            calibration_path=os.path.join(REPO_ROOT, "oi_calibration.json"))
        # Coinbase premium index. Tracks (CB_USD - BN_USDT * USDT/USD)
        # in bps and emits CB_PREMIUM_{HOT,COLD,CLEARED} drift alerts.
        # US-institutional flow proxy; persists every observation to
        # backend_cb_premium_history.jsonl so the calibration script
        # can later derive empirical thresholds.
        self.cb_premium_monitor = CoinbasePremiumMonitor(
            history_path=os.path.join(REPO_ROOT,
                                       "backend_cb_premium_history.jsonl"))
        # F8 scheduled-event calendar (FOMC/CPI/etc.). Hot-reloads by mtime.
        # Confidence dampener fires within ±60 min of an event or on weekends.
        self.event_calendar = EventCalendar(
            os.path.join(REPO_ROOT, "events_calendar.json"))
        # F11 multi-horizon edge tracker. Per-(asset, venue, regime) cell
        # rolling Gate I-style r over daily / weekly / longterm windows.
        # Persists to backend_edge_history.jsonl so warm starts retain
        # weekly/longterm reads immediately.
        self.edge_tracker = MultiHorizonEdgeTracker(
            history_path=os.path.join(REPO_ROOT, "backend_edge_history.jsonl"))
        # Per-(asset, venue) "prior chunk" cache so we can compute the
        # forward-return for the previous chunk's mean_dipole — Gate I
        # lag-1 convention. Holds (chunk_id, regime, mean_dipole, ts,
        # close_price).
        self._prior_chunk_for_edge: dict[tuple[str, str], tuple[str, str, float, float, float]] = {}

    def _restore_signals(self):
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    sig = SignalEvent(**{k: v for k, v in d.items()
                                          if k in SignalEvent.__dataclass_fields__})
                    self.recent_signals.append(sig)
                    self.signal_index[sig.signal_id] = sig
            print(f"[SignalStore] restored {len(self.recent_signals)} signals from disk", flush=True)
        except Exception as e:
            print(f"[SignalStore] could not restore: {e}", flush=True)

    def _persist_signal(self, sig: SignalEvent):
        try:
            with open(self._persist_path, "a") as f:
                f.write(json.dumps(asdict(sig)) + "\n")
        except Exception as e:
            print(f"[SignalStore] persist error: {e}", flush=True)

    def _rewrite_signals(self):
        """Rewrite the persisted log with the current in-memory state.
        Used after outcome resolution to update the on-disk record."""
        try:
            tmp = self._persist_path + ".tmp"
            with open(tmp, "w") as f:
                for sig in self.recent_signals:
                    f.write(json.dumps(asdict(sig)) + "\n")
            os.replace(tmp, self._persist_path)
        except Exception as e:
            print(f"[SignalStore] rewrite error: {e}", flush=True)

    def _restore_drift_alerts(self):
        if not os.path.exists(self._drift_alerts_path):
            return
        try:
            with open(self._drift_alerts_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.recent_drift_alerts.append(json.loads(line))
        except Exception as e:
            print(f"[SignalStore] drift restore error: {e}", flush=True)

    async def _emit_drift_alert(self, alert: dict):
        """Persist + queue a drift_alert SSE event. Idempotent on
        (alert_id) — repeats deduped by the caller."""
        alert = {**alert, "id": alert.get("id") or str(uuid.uuid4())[:12],
                  "ts_utc": alert.get("ts_utc") or time.time()}
        self.recent_drift_alerts.append(alert)
        try:
            with open(self._drift_alerts_path, "a") as f:
                f.write(json.dumps(alert) + "\n")
        except Exception as e:
            print(f"[SignalStore] drift persist error: {e}", flush=True)
        await self.event_queue.put({"type": "drift_alert", "data": alert})
        return alert

    async def _refresh_cell_runtime_controls(self) -> None:
        now = time.time()
        if now < self._next_controls_refresh_utc:
            return
        self._next_controls_refresh_utc = now + self._controls_refresh_interval_s
        try:
            _report, controls = refresh_runtime_controls(
                registry_path=os.path.join(REPO_ROOT, "cells_registry.json"),
                practice_trades_path=os.path.join(REPO_ROOT, "backend_practice_trades.jsonl"),
                output_path=self._controls_path,
            )
        except Exception as e:
            print(f"[cells] runtime control refresh error: {e}", flush=True)
            return
        control_rows = controls.get("controls") or {}
        new_suppressed = {
            cell_id
            for cell_id, meta in control_rows.items()
            if isinstance(meta, dict) and meta.get("action") == "suppress"
        }
        became_suppressed = new_suppressed - self._suppressed_cell_ids
        became_active = self._suppressed_cell_ids - new_suppressed
        self._suppressed_cell_ids = new_suppressed
        for cell_id in sorted(became_suppressed):
            meta = control_rows.get(cell_id) or {}
            await self._emit_drift_alert({
                "type": "cell_runtime_suppressed",
                "key": cell_id,
                "cell_id": cell_id,
                "summary": (
                    f"{cell_id} suppressed by decay monitor: "
                    f"{meta.get('reason') or meta.get('status') or 'retire_candidate'}"
                ),
                "status": meta.get("status"),
                "reason": meta.get("reason"),
            })
        for cell_id in sorted(became_active):
            await self._emit_drift_alert({
                "type": "cell_runtime_reactivated",
                "key": cell_id,
                "cell_id": cell_id,
                "summary": f"{cell_id} reactivated by decay monitor",
            })

    def _bars_from_bins(self, bins_path: str) -> list[MarketBar]:
        if not os.path.exists(bins_path):
            return []
        try:
            with open(bins_path) as f:
                sec_bins = {float(k): v for k, v in json.load(f).items()}
        except Exception:
            return []
        from collections import defaultdict
        minute_groups: dict[float, list[tuple[float, dict]]] = defaultdict(list)
        for ts, b in sec_bins.items():
            if b.get("mid") is None:
                continue
            m_ts = int(ts / 60.0) * 60.0
            minute_groups[m_ts].append((ts, b))
        bars: list[MarketBar] = []
        for m_ts in sorted(minute_groups):
            members = sorted(minute_groups[m_ts], key=lambda x: x[0])
            mids = [b["mid"] for _, b in members if b["mid"] is not None]
            if not mids:
                continue
            # Latest bid/ask + last_aggressor side in the minute (members
            # are time-sorted; iterate in order so the last non-empty value
            # wins). Falls back to 0.0 / "" when collectors haven't been
            # updated yet — UI handles missing values gracefully.
            last_bid = 0.0
            last_ask = 0.0
            last_bid_qty = 0.0
            last_ask_qty = 0.0
            last_aggressor = ""
            for _, bb in members:
                if bb.get("bid"):
                    last_bid = float(bb["bid"])
                if bb.get("ask"):
                    last_ask = float(bb["ask"])
                # bid_qty/ask_qty added 2026-05; older bins won't have them
                # and last_*_qty stays 0 -> microprice falls back to (b+a)/2.
                if bb.get("bid_qty"):
                    last_bid_qty = float(bb["bid_qty"])
                if bb.get("ask_qty"):
                    last_ask_qty = float(bb["ask_qty"])
                if bb.get("last_aggressor"):
                    last_aggressor = str(bb["last_aggressor"])
            bars.append(MarketBar(
                ts=float(m_ts),
                close=float(mids[-1]), open_=float(mids[0]),
                high=float(max(mids)), low=float(min(mids)),
                volume=float(sum(b["buy"] + b["sell"] for _, b in members)),
                buy_vol=float(sum(b["buy"] for _, b in members)),
                sell_vol=float(sum(b["sell"] for _, b in members)),
                n_trades=int(sum(b.get("n_trades", 0) for _, b in members)),
                bid=last_bid,
                ask=last_ask,
                bid_qty=last_bid_qty,
                ask_qty=last_ask_qty,
                last_aggressor=last_aggressor,
            ))
        return bars

    async def poll_all(self):
        try:
            await self._refresh_cell_runtime_controls()
        except Exception as e:
            print(f"[cells] runtime control poll hook error: {e}", flush=True)

        for asset, venue, path in DATA_SOURCES:
            try:
                await self._poll_one(asset, venue, path)
            except Exception as e:
                print(f"[SignalStore] error polling {asset}/{venue}: {e}", flush=True)

        # Apply F6 cross-venue multiplier to current statuses
        self._apply_cross_venue_F6()
        # Convert internal dipole-derived pressure into reusable,
        # trader-safe amber watch metadata.
        self._apply_pressure_watch()
        try:
            await self._emit_high_priority_pressure_watch_alerts()
        except Exception as e:
            print(f"[pressure-watch] alert error: {e}", flush=True)
        # Emit cross-venue WHALE+HERD cascade signals (independent
        # confirmation across venues = top-of-book event)
        try:
            await self._emit_cross_venue_cascades()
        except Exception as e:
            print(f"[SignalStore] cross-venue cascade error: {e}", flush=True)

        # Sweep-close any forward paper trades whose hold has elapsed.
        try:
            self._sweep_close_forward_paper_trades()
        except Exception as e:
            print(f"[forward-paper] sweep error: {e}", flush=True)

        # Spot-perp basis: update once per asset (independent of venue
        # poll calls) and emit a drift_alert on state transitions.
        try:
            for asset in {a for a, _, _ in DATA_SOURCES}:
                alert = self.basis_monitor.update_asset(asset)
                if alert:
                    await self._emit_drift_alert(alert)
        except Exception as e:
            print(f"[basis-monitor] error: {e}", flush=True)

        # Funding rates (perp). Polls Binance + Bybit for both BTC and
        # ETH; HTTP failures are isolated per source. Emits drift alerts
        # only on state transitions, so steady-state polls cost just two
        # HTTP roundtrips per asset.
        try:
            for alert in self.funding_monitor.update_all():
                await self._emit_drift_alert(alert)
                # T3.3: open carry paper trade on OVERLEVERED, close on
                # CLEARED. Trade represents the perp leg of an assumed
                # delta-neutral pair; spot leg is not modeled.
                try:
                    self._handle_carry_alert(alert)
                except Exception as e2:
                    print(f"[carry-paper] alert handling error: {e2}",
                          flush=True)
        except Exception as e:
            print(f"[funding-monitor] error: {e}", flush=True)

        # Liquidation-burst detector on perp bins.
        try:
            for asset in {a for a, _, _ in DATA_SOURCES}:
                alert = self.liq_monitor.update_asset(asset)
                if alert:
                    await self._emit_drift_alert(alert)
        except Exception as e:
            print(f"[liq-monitor] error: {e}", flush=True)

        # Open-interest watcher. One HTTP roundtrip per (asset, venue);
        # state transitions only emit drift alerts.
        try:
            for alert in self.oi_monitor.update_all():
                await self._emit_drift_alert(alert)
        except Exception as e:
            print(f"[oi-monitor] error: {e}", flush=True)

        # Coinbase premium index (CB-USD vs BN-USDT*peg).
        try:
            for alert in self.cb_premium_monitor.update_all():
                await self._emit_drift_alert(alert)
        except Exception as e:
            print(f"[cb-premium] error: {e}", flush=True)

    async def _poll_one(self, asset: str, venue: str, bins_path: str):
        bars = self._bars_from_bins(bins_path)
        if len(bars) < CHUNK_MIN_SEGMENT:
            if bars:
                latest = bars[-1]
                self.current_status[(asset, venue)] = RegimeStatus(
                    asset=asset,
                    venue=venue,
                    regime="EQUILIBRIUM_TWO_SIDED",
                    confidence=0.45,
                    cross_venue_multiplier=1.0,
                    adjusted_confidence=0.45,
                    notes=[f"warming up live read ({len(bars)}/{CHUNK_MIN_SEGMENT} bars)"],
                    mean_dipole=float(latest.dipole),
                    realized_vol=0.0,
                    chunk_window=(max(0, len(bars) - 1), len(bars)),
                    last_update_utc=time.time(),
                    current_price=float(latest.close),
                    current_bid=float(latest.bid),
                    current_ask=float(latest.ask),
                    last_aggressor=str(latest.last_aggressor),
                    chunk_buy_volume=float(latest.buy_vol),
                    chunk_sell_volume=float(latest.sell_vol),
                    chunk_n_trades=int(latest.n_trades),
                )
            return
        chunker = MarketChunker(max_window_size=CHUNK_MAX_SIZE,
                                  stride=CHUNK_MAX_SIZE // 2,
                                  min_segment=CHUNK_MIN_SEGMENT, mode="hybrid")
        encoder = MarketChunkEncoder(d_enc=64)
        chunks = chunker.chunk(f"{venue}-{asset}", bars)
        if not chunks:
            return
        # VPIN bucket size: prefer per-(asset, venue) calibration; fall
        # back to corpus-derived (mean chunk volume / 10) since we have
        # the chunks in hand. The fallback gives us correct relative
        # ranking even before calibrate_vpin.py is run.
        bv = _vpin_bucket_volume_for(asset, venue)
        if bv <= 0:
            bv = _vpin_bucket_volume_from_corpus(chunks)
        feats = [encoder._extract(c, vpin_bucket_volume=bv) for c in chunks]
        base = baselines_from_corpus(feats)
        # Per-(asset, venue) VPIN + Hawkes-η thresholds; both fall back to
        # literature defaults when an entry is missing.
        vpin_elev, vpin_diff = _vpin_thresholds_for(asset, venue)
        haw_elev, haw_diff = _hawkes_thresholds_for(asset, venue)
        results = [classify_regime(f, base,
                                     vpin_elevated=vpin_elev,
                                     vpin_diffuse=vpin_diff,
                                     hawkes_elevated=haw_elev,
                                     hawkes_diffuse=haw_diff) for f in feats]
        apply_herd_persistence(results)

        # F7 cross-asset directional confirmation. BTC and ETH lead each
        # other on intraday horizons; if the sibling asset is currently in
        # a same-direction regime we boost confidence, opposite direction
        # damps it. Uses sibling's most recent RegimeStatus (set by an
        # earlier _poll_one within this cycle, or the previous cycle).
        sibling_dir = self._sibling_asset_direction(asset, venue)
        apply_cross_asset_multiplier_uniform(results, sibling_dir)

        # F8 event-proximity / weekend dampener. Hot-reloads from
        # events_calendar.json by mtime; absent file = no event dampening
        # but weekend dampener still applies.
        apply_event_multiplier(results, chunks, bars, self.event_calendar)

        # Build minute->regime map for cross-venue agreement (F6)
        m_map: dict[float, str] = {}
        for c, r in zip(chunks, results):
            for bar_idx in range(c.window_start, c.window_end):
                if 0 <= bar_idx < len(bars):
                    m_map[bars[bar_idx].ts] = r.regime.value
        self._minute_regime_per_venue[(asset, venue)] = m_map
        # Persist the latest chunk so _emit_cross_venue_cascades can reach
        # its wall-clock window and bar list
        self._latest_chunk_per_venue[(asset, venue)] = chunks[-1]

        # Use most recent chunk as current status
        latest_chunk = chunks[-1]
        latest_feat = feats[-1]
        latest_result = results[-1]

        chunk_buy_v = float(sum(b.buy_vol for b in latest_chunk.bars))
        chunk_sell_v = float(sum(b.sell_vol for b in latest_chunk.bars))
        chunk_n_tr = int(sum(b.n_trades for b in latest_chunk.bars))
        status = RegimeStatus(
            asset=asset, venue=venue,
            regime=latest_result.regime.value,
            confidence=latest_result.confidence,
            cross_venue_multiplier=latest_result.cross_venue_multiplier,
            adjusted_confidence=latest_result.adjusted_confidence,
            notes=latest_result.notes[:3],
            mean_dipole=float(latest_feat.mean_dipole),
            realized_vol=float(latest_feat.realized_vol),
            chunk_window=(latest_chunk.window_start, latest_chunk.window_end),
            last_update_utc=time.time(),
            current_price=float(latest_chunk.bars[-1].close) if latest_chunk.bars else 0.0,
            current_bid=float(latest_chunk.bars[-1].bid) if latest_chunk.bars else 0.0,
            current_ask=float(latest_chunk.bars[-1].ask) if latest_chunk.bars else 0.0,
            last_aggressor=str(latest_chunk.bars[-1].last_aggressor) if latest_chunk.bars else "",
            chunk_buy_volume=chunk_buy_v,
            chunk_sell_volume=chunk_sell_v,
            chunk_n_trades=chunk_n_tr,
            vpin=float(getattr(latest_result, "vpin", 0.0)),
            vpin_multiplier=float(getattr(latest_result, "vpin_multiplier", 1.0)),
            cross_asset_multiplier=float(getattr(latest_result, "cross_asset_multiplier", 1.0)),
            event_multiplier=float(getattr(latest_result, "event_multiplier", 1.0)),
            hurst=float(getattr(latest_result, "hurst", 0.5)),
            hurst_label=str(getattr(latest_result, "hurst_label", "")),
            hawkes_multiplier=float(getattr(latest_result, "hawkes_multiplier", 1.0)),
        )

        prev_status = self.current_status.get((asset, venue))
        regime_changed = (prev_status is None) or (prev_status.regime != status.regime)
        self.current_status[(asset, venue)] = status
        prev_feat = feats[-2] if len(feats) >= 2 else None
        self._pressure_inputs[(asset, venue)] = {
            "regime": status.regime,
            "mean_dipole": float(latest_feat.mean_dipole),
            "volume_zscore": float(latest_feat.volume_zscore),
            "dipole_acl1": float(latest_feat.dipole_autocorr_lag1),
            "prev_mean_dipole": (
                float(prev_feat.mean_dipole) if prev_feat is not None else None
            ),
            "chunk_id": latest_chunk.chunk_id,
            "spread_bps": (
                ((status.current_ask - status.current_bid)
                 / max((status.current_ask + status.current_bid) / 2.0, 1e-12)
                 * 10000.0)
                if status.current_ask > 0 and status.current_bid > 0
                else 0.0
            ),
            "signed_move_bps": (
                (1 if latest_feat.mean_dipole > 0 else -1)
                * math.log(
                    max(float(latest_chunk.bars[-1].close), 1e-12)
                    / max(float(latest_chunk.bars[0].close), 1e-12)
                ) * 10000.0
                if latest_chunk.bars and latest_feat.mean_dipole != 0
                else 0.0
            ),
            "realized_vol_bps": float(latest_feat.realized_vol) * 10000.0,
            "chunk_total_volume": float(latest_feat.chunk_total_volume),
            "chunk_start_price": (
                float(latest_chunk.bars[0].close) if latest_chunk.bars else 0.0
            ),
            "chunk_close_price": (
                float(latest_chunk.bars[-1].close) if latest_chunk.bars else 0.0
            ),
            "recent_2chunk_start_price": (
                float(chunks[-2].bars[0].close)
                if len(chunks) >= 2 and chunks[-2].bars else (
                    float(latest_chunk.bars[0].close) if latest_chunk.bars else 0.0
                )
            ),
            "strategy_mode": (
                "live_paper"
                if bool(_load_auto_trade_settings().get("practice", True))
                else "product"
            ),
            "bucket_session": _live_bucket_session(),
            "allow_context_probes": False,
            "allow_promoted_context_rerun": False,
            "requested_strategy_families": [
                "SMALL_MOVE_FADE",
                "BUY_UP_CONTINUATION",
                "BUY_FADE",
                "SELL_DOWN_CONTINUATION",
                "MEAN_REVERSION_CHOP",
                "NEWS_BREAKOUT",
                "LIQUIDITY_SQUEEZE",
                "VOL_BREAKOUT",
                "BASIS_DISLOCATION",
                "RELATIVE_STRENGTH",
            ],
        }
        local_watch = _pressure_watch_from_features(
            regime=status.regime,
            mean_dipole=float(latest_feat.mean_dipole),
            volume_zscore=float(latest_feat.volume_zscore),
            dipole_acl1=float(latest_feat.dipole_autocorr_lag1),
            prev_mean_dipole=(
                float(prev_feat.mean_dipole) if prev_feat is not None else None
            ),
        )
        _apply_pressure_fields(status, local_watch)
        self._apply_present_trade_context((asset, venue), status, self._pressure_inputs[(asset, venue)])
        _apply_trade_option_fields(
            status,
            _trade_option_from_status(
                status, self._pressure_inputs[(asset, venue)]),
        )
        _apply_high_conviction_ticket(status, self._pressure_inputs[(asset, venue)])

        # Track new-chunk transitions for both the production and demo emit paths
        last_emitted = self.last_chunk_id_per_source.get((asset, venue))
        chunk_changed = (last_emitted != latest_chunk.chunk_id)

        # F11 edge tracker update: when a NEW chunk lands, the previously
        # cached chunk's mean_dipole is the predictor, and THIS chunk's
        # log_return is the target — Gate I's lag-1 convention.
        if chunk_changed:
            prior = self._prior_chunk_for_edge.get((asset, venue))
            if prior is not None:
                prior_chunk_id, prior_regime, prior_dipole, prior_ts, prior_close = prior
                if latest_chunk.bars:
                    cur_close = float(latest_chunk.bars[-1].close)
                    if prior_close > 1e-12 and cur_close > 1e-12:
                        import math as _m
                        forward_ret = _m.log(cur_close / prior_close)
                        self.edge_tracker.update(
                            asset=asset, venue=venue, regime=prior_regime,
                            ts=prior_ts, mean_dipole=prior_dipole,
                            forward_return=forward_ret)
            # Cache THIS chunk as the next prior — forward_return will be
            # computed when the NEXT new chunk lands.
            if latest_chunk.bars:
                self._prior_chunk_for_edge[(asset, venue)] = (
                    latest_chunk.chunk_id,
                    status.regime,
                    float(latest_feat.mean_dipole),
                    float(latest_chunk.bars[-1].ts),
                    float(latest_chunk.bars[-1].close),
                )

        # Pull current cell tags for surfacing on RegimeStatus / SignalEvent
        edge_tags = self.edge_tracker.cell_tags(asset, venue, status.regime)
        status.edge_summary = edge_tags.summary
        status.edge_intraday_strength = edge_tags.intraday.strength
        status.edge_daily_strength = edge_tags.daily.strength
        status.edge_weekly_strength = edge_tags.weekly.strength
        status.edge_longterm_strength = edge_tags.longterm.strength
        status.edge_intraday_self_trend = edge_tags.intraday.self_trend
        status.edge_daily_self_trend = edge_tags.daily.self_trend
        status.edge_weekly_self_trend = edge_tags.weekly.self_trend
        status.edge_longterm_self_trend = edge_tags.longterm.self_trend

        live_cells = _fp_find_cells(
            asset, venue, status.regime, latest_feat, latest_chunk)
        convergence = _fp_summarize_convergence(
            asset, venue, status.regime, live_cells, min_support=3)
        if convergence is not None:
            status.convergence_support_count = int(convergence.get("support_count") or 0)
            status.convergence_direction = str(convergence.get("direction_label") or "")
            status.convergence_side = str(convergence.get("side") or "")
            status.convergence_cell_ids = list(convergence.get("cell_ids") or [])
            status.convergence_features = list(convergence.get("features") or [])
            status.convergence_tier = str(convergence.get("confidence_tier") or "")
            status.convergence_bonus = float(convergence.get("bonus_multiplier") or 1.0)
            status.convergence_summary = str(convergence.get("summary") or "")

        emitted = False
        # Production emit: regime transitions to actionable states
        if regime_changed and status.regime not in ("EQUILIBRIUM_TWO_SIDED", "DEPLETED", "UNKNOWN"):
            # Cascade detection: is the latest chunk a HERD that came directly
            # from a same-direction WHALE on the previous chunk?
            cascade_event = ""
            cascade_detail = ""
            confidence_boost = 1.0
            if "HERD" in status.regime and len(results) >= 2:
                prev_r = results[-2]
                if ("WHALE" in prev_r.regime.value
                        and prev_r.regime.value.endswith(status.regime[-3:])):
                    direction = "UP" if status.regime.endswith("_UP") else "DOWN"
                    cascade_event = f"WHALE_TO_HERD_{direction}"
                    cascade_detail = (
                        f"WHALE_{direction} chunk immediately preceding this "
                        f"HERD_{direction}; whale-tripped-the-herd cascade "
                        f"(higher conviction signal)")
                    confidence_boost = 1.3
            # Buy/sell volume breakdown for this chunk — explicit aggressor-
            # side imbalance is more actionable for traders than the regime
            # label alone (which only encodes net direction).
            chunk_buy = float(sum(b.buy_vol for b in latest_chunk.bars))
            chunk_sell = float(sum(b.sell_vol for b in latest_chunk.bars))
            total_v = chunk_buy + chunk_sell
            buy_pct = (chunk_buy / total_v * 100) if total_v > 0 else 0.0
            split_note = f"aggressor split: {buy_pct:.0f}% buy / {100 - buy_pct:.0f}% sell ({total_v:.2f} units)"
            base_notes = list(latest_result.notes[:3]) + [split_note]
            # Dynamic per-(asset, venue, regime) playbook — reads
            # playbook_registry.json (built by build_playbook_registry.py)
            # and falls back to the per-regime DEFAULT_PLAYBOOKS when the
            # registry has no qualifying entry. The text includes the
            # current sample size + r + p so users see how the read
            # evolves run-to-run.
            playbook = get_dynamic_playbook(asset, venue, status.regime)
            if cascade_event:
                playbook = (
                    f"[CASCADE: WHALE→HERD same direction] "
                    + CASCADE_PLAYBOOKS.get(cascade_event, playbook))
            playbook = playbook + f"  ({split_note}.)"
            # F11 multi-horizon edge read prepended to the playbook so the
            # user sees long-term / weekly / daily strength + trend up front.
            if status.edge_summary:
                playbook = f"[edge] {status.edge_summary}\n\n" + playbook
            event_label = EVENT_LABELS.get(status.regime, "Unclassified pattern")
            if cascade_event:
                event_label = (f"Whale-tripped {('buying' if cascade_event.endswith('_UP') else 'selling')} cascade"
                                if cascade_event.startswith("WHALE_TO_HERD")
                                else f"Cross-venue {('buying' if cascade_event.endswith('_UP') else 'selling')} cascade confirmed")
            sig = SignalEvent(
                signal_id=str(uuid.uuid4())[:12],
                asset=asset, venue=venue,
                regime=status.regime,
                confidence=min(1.0, status.confidence * confidence_boost),
                cross_venue_multiplier=status.cross_venue_multiplier,
                adjusted_confidence=min(1.0,
                    status.adjusted_confidence * confidence_boost),
                mean_dipole=float(latest_feat.mean_dipole),
                realized_vol=float(latest_feat.realized_vol),
                chunk_volume=float(latest_feat.chunk_total_volume),
                notes=base_notes,
                playbook=playbook,
                timestamp_utc=time.time(),
                chunk_window=(latest_chunk.window_start, latest_chunk.window_end),
                cascade_event=cascade_event,
                cascade_detail=cascade_detail,
                chunk_buy_volume=chunk_buy,
                chunk_sell_volume=chunk_sell,
                chunk_n_trades=int(sum(b.n_trades for b in latest_chunk.bars)),
                current_price=float(latest_chunk.bars[-1].close) if latest_chunk.bars else 0.0,
                current_bid=float(latest_chunk.bars[-1].bid) if latest_chunk.bars else 0.0,
                current_ask=float(latest_chunk.bars[-1].ask) if latest_chunk.bars else 0.0,
                last_aggressor=str(latest_chunk.bars[-1].last_aggressor) if latest_chunk.bars else "",
                event_label=event_label,
                drift_status=get_drift_status(asset, venue, status.regime),
                vpin=float(getattr(latest_result, "vpin", 0.0)),
                vpin_multiplier=float(getattr(latest_result, "vpin_multiplier", 1.0)),
                cross_asset_multiplier=float(getattr(latest_result, "cross_asset_multiplier", 1.0)),
                event_multiplier=float(getattr(latest_result, "event_multiplier", 1.0)),
                hurst=float(getattr(latest_result, "hurst", 0.5)),
                hurst_label=str(getattr(latest_result, "hurst_label", "")),
                hawkes_multiplier=float(getattr(latest_result, "hawkes_multiplier", 1.0)),
                edge_summary=status.edge_summary,
                edge_daily_strength=status.edge_daily_strength,
                edge_weekly_strength=status.edge_weekly_strength,
                edge_longterm_strength=status.edge_longterm_strength,
                edge_daily_self_trend=status.edge_daily_self_trend,
                edge_weekly_self_trend=status.edge_weekly_self_trend,
                edge_longterm_self_trend=status.edge_longterm_self_trend,
                signal_tier=("convergence" if convergence else "actionable"),
                convergence_support_count=status.convergence_support_count,
                convergence_direction=status.convergence_direction,
                convergence_side=status.convergence_side,
                convergence_cell_ids=list(status.convergence_cell_ids),
                convergence_features=list(status.convergence_features),
                convergence_tier=status.convergence_tier,
                convergence_bonus=status.convergence_bonus,
                convergence_summary=status.convergence_summary,
                pressure_watch_state=status.pressure_watch_state,
                pressure_watch_label=status.pressure_watch_label,
                pressure_watch_direction=status.pressure_watch_direction,
                pressure_watch_intensity=status.pressure_watch_intensity,
                pressure_watch_priority=status.pressure_watch_priority,
                pressure_watch_reasons=list(status.pressure_watch_reasons),
                trade_option_state=status.trade_option_state,
                trade_option_label=status.trade_option_label,
                trade_option_side=status.trade_option_side,
                trade_option_readiness=status.trade_option_readiness,
                trade_option_profile=status.trade_option_profile,
                trade_option_size_hint=status.trade_option_size_hint,
                trade_option_notional_scale=status.trade_option_notional_scale,
                trade_option_hold_minutes=status.trade_option_hold_minutes,
                trade_option_entry_reasons=list(status.trade_option_entry_reasons),
                trade_option_exit_rules=list(status.trade_option_exit_rules),
                trade_option_blockers=list(status.trade_option_blockers),
                trade_strategy_id=status.trade_strategy_id,
                trade_strategy_label=status.trade_strategy_label,
                trade_strategy_confidence=status.trade_strategy_confidence,
                trade_strategy_reasons=list(status.trade_strategy_reasons),
                trade_strategy_blockers=list(status.trade_strategy_blockers),
                trade_strategy_stop_loss_bps=status.trade_strategy_stop_loss_bps,
                trade_strategy_take_profit_bps=status.trade_strategy_take_profit_bps,
                trade_strategy_exit_score_drop=status.trade_strategy_exit_score_drop,
                daily_news_context=dict(status.daily_news_context),
                daily_news_status=dict(status.daily_news_status),
            )
            self.recent_signals.append(sig)
            self.signal_index[sig.signal_id] = sig
            self._persist_signal(sig)
            await self.event_queue.put({"type": "signal", "data": asdict(sig)})
            emitted = True

        # XXX DEMO_MODE: also emit when a NEW chunk in EQUILIBRIUM has extreme
        # dipole + volume (mean-reversion candidate per autoresearch). Revert
        # before Tier 1 launch. Tracked in /TODO.md.
        elif (
            DEMO_MODE_EMIT_EQUILIBRIUM_EXTREMES
            and chunk_changed
            and status.regime == "EQUILIBRIUM_TWO_SIDED"
            and abs(latest_feat.mean_dipole) > DEMO_DIPOLE_THRESHOLD
            and abs(latest_feat.volume_zscore) > DEMO_VOL_Z_THRESHOLD
        ):
            direction = "Fade SHORT" if latest_feat.mean_dipole > 0 else "Fade LONG"
            demo_playbook = (
                f"[DEMO] EQUILIBRIUM with extreme dipole ({latest_feat.mean_dipole:+.2f}) "
                f"and elevated volume (z={latest_feat.volume_zscore:+.2f}). "
                f"Mean-reversion candidate: {direction} one chunk, exit at next chunk close. "
                f"NB: synthetic demo signal; production filter is regime transitions only."
            )
            sig = SignalEvent(
                signal_id=str(uuid.uuid4())[:12],
                asset=asset, venue=venue,
                regime="EQUILIBRIUM_EXTREME_DEMO",
                confidence=status.confidence * 0.6,   # soft-flag as lower-trust
                cross_venue_multiplier=status.cross_venue_multiplier,
                adjusted_confidence=max(0.0, min(1.0,
                    status.confidence * 0.6 * status.cross_venue_multiplier)),
                mean_dipole=float(latest_feat.mean_dipole),
                realized_vol=float(latest_feat.realized_vol),
                chunk_volume=float(latest_feat.chunk_total_volume),
                notes=[f"|dipole|={abs(latest_feat.mean_dipole):.2f} > {DEMO_DIPOLE_THRESHOLD}",
                        f"|vol_z|={abs(latest_feat.volume_zscore):.2f} > {DEMO_VOL_Z_THRESHOLD}",
                        "DEMO mode emit; not a regime transition"],
                playbook=demo_playbook,
                timestamp_utc=time.time(),
                chunk_window=(latest_chunk.window_start, latest_chunk.window_end),
                entry_price=float(latest_chunk.bars[-1].close) if latest_chunk.bars else 0.0,
                expected_direction=expected_direction_from_signal(
                    "EQUILIBRIUM_EXTREME_DEMO", latest_feat.mean_dipole),
                pressure_watch_state=status.pressure_watch_state,
                pressure_watch_label=status.pressure_watch_label,
                pressure_watch_direction=status.pressure_watch_direction,
                pressure_watch_intensity=status.pressure_watch_intensity,
                pressure_watch_priority=status.pressure_watch_priority,
                pressure_watch_reasons=list(status.pressure_watch_reasons),
                trade_option_state=status.trade_option_state,
                trade_option_label=status.trade_option_label,
                trade_option_side=status.trade_option_side,
                trade_option_readiness=status.trade_option_readiness,
                trade_option_profile=status.trade_option_profile,
                trade_option_size_hint=status.trade_option_size_hint,
                trade_option_notional_scale=status.trade_option_notional_scale,
                trade_option_hold_minutes=status.trade_option_hold_minutes,
                trade_option_entry_reasons=list(status.trade_option_entry_reasons),
                trade_option_exit_rules=list(status.trade_option_exit_rules),
                trade_option_blockers=list(status.trade_option_blockers),
                trade_strategy_id=status.trade_strategy_id,
                trade_strategy_label=status.trade_strategy_label,
                trade_strategy_confidence=status.trade_strategy_confidence,
                trade_strategy_reasons=list(status.trade_strategy_reasons),
                trade_strategy_blockers=list(status.trade_strategy_blockers),
                trade_strategy_stop_loss_bps=status.trade_strategy_stop_loss_bps,
                trade_strategy_take_profit_bps=status.trade_strategy_take_profit_bps,
                trade_strategy_exit_score_drop=status.trade_strategy_exit_score_drop,
                daily_news_context=dict(status.daily_news_context),
                daily_news_status=dict(status.daily_news_status),
            )
            self.recent_signals.append(sig)
            self.signal_index[sig.signal_id] = sig
            self._persist_signal(sig)
            await self.event_queue.put({"type": "signal", "data": asdict(sig)})
            emitted = True

        paper_chunk_changed = (
            self.last_paper_chunk_id_per_source.get((asset, venue))
            != latest_chunk.chunk_id
        )
        if (not emitted) and paper_chunk_changed and convergence is not None:
            base_notes = list(latest_result.notes[:3]) + [status.convergence_summary]
            conv_playbook = (
                f"[convergence] {status.convergence_summary}\n\n"
                f"{get_dynamic_playbook(asset, venue, status.regime)}"
            )
            conv_label = (
                "Convergence long confirmed"
                if status.convergence_side == "buy"
                else "Convergence short confirmed"
            )
            conv_conf = min(
                1.0,
                status.adjusted_confidence * max(1.0, status.convergence_bonus),
            )
            sig = SignalEvent(
                signal_id=str(uuid.uuid4())[:12],
                asset=asset,
                venue=venue,
                regime=status.regime,
                confidence=conv_conf,
                cross_venue_multiplier=status.cross_venue_multiplier,
                adjusted_confidence=conv_conf,
                mean_dipole=float(latest_feat.mean_dipole),
                realized_vol=float(latest_feat.realized_vol),
                chunk_volume=float(latest_feat.chunk_total_volume),
                notes=base_notes,
                playbook=conv_playbook,
                timestamp_utc=time.time(),
                chunk_window=(latest_chunk.window_start, latest_chunk.window_end),
                chunk_buy_volume=chunk_buy_v,
                chunk_sell_volume=chunk_sell_v,
                chunk_n_trades=chunk_n_tr,
                current_price=float(latest_chunk.bars[-1].close) if latest_chunk.bars else 0.0,
                current_bid=float(latest_chunk.bars[-1].bid) if latest_chunk.bars else 0.0,
                current_ask=float(latest_chunk.bars[-1].ask) if latest_chunk.bars else 0.0,
                last_aggressor=str(latest_chunk.bars[-1].last_aggressor) if latest_chunk.bars else "",
                event_label=conv_label,
                drift_status=get_drift_status(asset, venue, status.regime),
                vpin=float(getattr(latest_result, "vpin", 0.0)),
                vpin_multiplier=float(getattr(latest_result, "vpin_multiplier", 1.0)),
                cross_asset_multiplier=float(getattr(latest_result, "cross_asset_multiplier", 1.0)),
                event_multiplier=float(getattr(latest_result, "event_multiplier", 1.0)),
                hurst=float(getattr(latest_result, "hurst", 0.5)),
                hurst_label=str(getattr(latest_result, "hurst_label", "")),
                hawkes_multiplier=float(getattr(latest_result, "hawkes_multiplier", 1.0)),
                edge_summary=status.edge_summary,
                edge_daily_strength=status.edge_daily_strength,
                edge_weekly_strength=status.edge_weekly_strength,
                edge_longterm_strength=status.edge_longterm_strength,
                edge_daily_self_trend=status.edge_daily_self_trend,
                edge_weekly_self_trend=status.edge_weekly_self_trend,
                edge_longterm_self_trend=status.edge_longterm_self_trend,
                signal_tier="convergence",
                convergence_support_count=status.convergence_support_count,
                convergence_direction=status.convergence_direction,
                convergence_side=status.convergence_side,
                convergence_cell_ids=list(status.convergence_cell_ids),
                convergence_features=list(status.convergence_features),
                convergence_tier=status.convergence_tier,
                convergence_bonus=status.convergence_bonus,
                convergence_summary=status.convergence_summary,
                pressure_watch_state=status.pressure_watch_state,
                pressure_watch_label=status.pressure_watch_label,
                pressure_watch_direction=status.pressure_watch_direction,
                pressure_watch_intensity=status.pressure_watch_intensity,
                pressure_watch_priority=status.pressure_watch_priority,
                pressure_watch_reasons=list(status.pressure_watch_reasons),
                trade_option_state=status.trade_option_state,
                trade_option_label=status.trade_option_label,
                trade_option_side=status.trade_option_side,
                trade_option_readiness=status.trade_option_readiness,
                trade_option_profile=status.trade_option_profile,
                trade_option_size_hint=status.trade_option_size_hint,
                trade_option_notional_scale=status.trade_option_notional_scale,
                trade_option_hold_minutes=status.trade_option_hold_minutes,
                trade_option_entry_reasons=list(status.trade_option_entry_reasons),
                trade_option_exit_rules=list(status.trade_option_exit_rules),
                trade_option_blockers=list(status.trade_option_blockers),
                trade_strategy_id=status.trade_strategy_id,
                trade_strategy_label=status.trade_strategy_label,
                trade_strategy_confidence=status.trade_strategy_confidence,
                trade_strategy_reasons=list(status.trade_strategy_reasons),
                trade_strategy_blockers=list(status.trade_strategy_blockers),
                trade_strategy_stop_loss_bps=status.trade_strategy_stop_loss_bps,
                trade_strategy_take_profit_bps=status.trade_strategy_take_profit_bps,
                trade_strategy_exit_score_drop=status.trade_strategy_exit_score_drop,
                daily_news_context=dict(status.daily_news_context),
                daily_news_status=dict(status.daily_news_status),
            )
            self.recent_signals.append(sig)
            self.signal_index[sig.signal_id] = sig
            self._persist_signal(sig)
            await self.event_queue.put({"type": "signal", "data": asdict(sig)})
            emitted = True

        if emitted:
            self.last_chunk_id_per_source[(asset, venue)] = latest_chunk.chunk_id

        # Forward paper-trade cell evaluator. Runs once per new chunk per
        # source, regardless of whether a regime-transition signal emitted
        # — the candidate cells trigger on regime+feature combinations
        # that don't always coincide with a transition (e.g. the second
        # consecutive HERD_UP chunk in vol-Q3 is still a fade candidate).
        last_paper = self.last_paper_chunk_id_per_source.get((asset, venue))
        if last_paper != latest_chunk.chunk_id:
            try:
                self._maybe_open_forward_paper_trades(
                    asset, venue, status.regime, latest_feat, latest_chunk,
                    cells=live_cells, convergence=convergence)
            except Exception as e:
                print(f"[forward-paper] open error {asset}/{venue}: {e}", flush=True)
            try:
                self._maybe_open_auto_trade_option(asset, venue, status, latest_chunk)
            except Exception as e:
                print(f"[auto-trade] open error {asset}/{venue}: {e}", flush=True)
            try:
                self._maybe_open_mock_trade_scenarios(asset, venue, status, latest_chunk)
            except Exception as e:
                print(f"[mock-trade] open/log error {asset}/{venue}: {e}", flush=True)
            self.last_paper_chunk_id_per_source[(asset, venue)] = latest_chunk.chunk_id

    def _maybe_open_auto_trade_option(self, asset: str, venue: str,
                                      status: RegimeStatus, chunk) -> None:
        settings = _load_auto_trade_settings()
        if not settings.get("enabled"):
            return
        if status.trade_option_state not in ("early_probe", "confirmed"):
            return
        profile = status.trade_option_profile or ""
        if profile not in settings.get("profiles", []):
            return
        if int(status.trade_option_readiness or 0) < int(settings.get("min_readiness") or 55):
            return
        if status.trade_option_blockers:
            return

        trades = _load_practice_trades()
        open_auto = [
            t for t in trades
            if t.get("status") == "open"
            and t.get("auto") is True
            and str(t.get("cell_id", "")).startswith("auto_trade_option_")
        ]
        if len(open_auto) >= int(settings.get("max_open_trades") or 3):
            return
        prefix = f"auto_trade_option_{asset.lower()}_{venue.lower()}_{profile}_"
        for t in open_auto:
            if str(t.get("cell_id", "")).startswith(prefix):
                return

        side = status.trade_option_side
        if side not in ("buy", "sell"):
            return
        bid, ask, mid = _current_quote(asset, venue)
        fill_price = float(ask if side == "buy" else bid) or float(mid)
        if fill_price <= 0:
            return

        scale = float(status.trade_option_notional_scale or 0.0)
        if scale <= 0:
            return
        notional = float(settings.get("base_notional_usd") or 1000.0) * scale
        qty = notional / fill_price
        fee_usd = notional * (_PRACTICE_FEE_BPS / 10000.0)
        chunk_id = getattr(chunk, "chunk_id", str(round(time.time())))
        trade = {
            "intent_id": str(uuid.uuid4())[:12],
            "asset": asset,
            "venue": venue,
            "side": side,
            "price": float(fill_price),
            "qty": float(qty),
            "notional": float(notional),
            "note": (
                f"auto {status.trade_option_label}: "
                f"readiness={status.trade_option_readiness}/100; "
                f"{'; '.join(status.trade_option_entry_reasons[:3])}"
            ),
            "ts_utc": time.time(),
            "practice": bool(settings.get("practice", True)),
            "auto": True,
            "cell_id": f"{prefix}{chunk_id}",
            "kind": "practice" if settings.get("practice", True) else "live_intent",
            "status": "open",
            "fill_price": float(fill_price),
            "fees_usd": float(fee_usd),
            "fee_bps": _PRACTICE_FEE_BPS,
            "bucket_session": str(self._pressure_inputs.get((asset, venue), {}).get("bucket_session") or _live_bucket_session()),
            "exit_price": 0.0,
            "exit_ts_utc": 0.0,
            "realized_pnl_usd": 0.0,
            "hold_minutes": float(status.trade_option_hold_minutes or 10),
            "trade_option_state": status.trade_option_state,
            "trade_option_profile": status.trade_option_profile,
            "trade_option_readiness": status.trade_option_readiness,
            "trade_stage": status.trade_stage,
            "trade_age_chunks": status.trade_age_chunks,
            "trade_present_score": status.trade_present_score,
            "trade_score_band": status.trade_score_band,
            "trade_from_onset_bps": status.trade_from_onset_bps,
            "trade_current_chunk_bps": status.trade_current_chunk_bps,
            "trade_recent_2chunk_bps": status.trade_recent_2chunk_bps,
            "mean_dipole": float(status.mean_dipole),
            "trade_option_exit_rules": list(status.trade_option_exit_rules),
            "trade_strategy_id": status.trade_strategy_id,
            "trade_strategy_label": status.trade_strategy_label,
            "trade_strategy_mode": "live_paper" if settings.get("practice", True) else "product",
            "trade_strategy_confidence": status.trade_strategy_confidence,
            "trade_strategy_reasons": list(status.trade_strategy_reasons),
            "trade_strategy_blockers": list(status.trade_strategy_blockers),
            "trade_strategy_stop_loss_bps": status.trade_strategy_stop_loss_bps,
            "trade_strategy_take_profit_bps": status.trade_strategy_take_profit_bps,
            "trade_strategy_exit_score_drop": status.trade_strategy_exit_score_drop,
            "trade_strategy_forced": bool(status.trade_strategy_forced),
            "trade_strategy_variant_id": status.trade_strategy_variant_id,
            "trade_strategy_risk_tags": list(status.trade_strategy_risk_tags),
            "trade_strategy_handoff_hint": status.trade_strategy_handoff_hint,
            "trade_strategy_source_queue_action": status.trade_strategy_source_queue_action,
            "daily_news_context": dict(status.daily_news_context),
            "daily_news_status": dict(status.daily_news_status),
            "high_conviction_ticket": dict(status.high_conviction_ticket),
            "dipole_coupling": dict((status.high_conviction_ticket.get("dipole_coupling") if status.high_conviction_ticket else {}) or {}),
            "onchain_features": dict(((status.high_conviction_ticket.get("onchain_context") if status.high_conviction_ticket else {}) or {}).get("features") or {}),
            "pressure_watch_state": status.pressure_watch_state,
            "pressure_watch_label": status.pressure_watch_label,
            "pressure_watch_reasons": list(status.pressure_watch_reasons),
        }
        if settings.get("practice", True):
            _persist_practice_trade(trade)
            print(
                f"[auto-trade] practice opened {trade['cell_id']} "
                f"{side} {asset}/{venue} @ {fill_price:.4f} "
                f"notional={notional:.2f} readiness={status.trade_option_readiness}",
                flush=True,
            )
            return

        # Disabled unless MARKETS_WATCH_ALLOW_LIVE_AUTO_TRADE=1.
        live_intent = dict(trade)
        live_intent["status"] = "submitted"
        with open(_MANUAL_INTENT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(live_intent) + "\n")
        self.event_queue.put_nowait({"type": "manual_trade_intent", "data": live_intent})

    def _mock_scenario_blocker(self, scenario: dict, status: RegimeStatus) -> str:
        route_action = str(status.trade_strategy_source_queue_action or "")
        risk_tags = {str(tag) for tag in (status.trade_strategy_risk_tags or [])}
        if bool(status.trade_strategy_forced) and (
            route_action in {
                "oracle_distilled_no_side_context",
                "oracle_distilled_strategy_context",
                "context_routing_exact_positive_pnl_instance",
                "context_routing_exact_instance_avoided_bad_queue",
            }
            or "oracle_distilled_context" in risk_tags
        ):
            return ""
        score = int(status.trade_present_score or status.trade_option_readiness or 0)
        if score < int(scenario.get("min_present_score") or 0):
            return f"present score {score} below scenario minimum"
        if score > int(scenario.get("max_present_score") or 100):
            return f"present score {score} above scenario maximum"
        if status.trade_stage not in set(scenario.get("allowed_stages") or []):
            return f"stage {status.trade_stage or 'unknown'} not allowed"
        if status.trade_option_state not in set(scenario.get("allowed_trade_states") or []):
            return f"trade state {status.trade_option_state or 'unknown'} not allowed"
        if status.pressure_watch_state not in set(scenario.get("allowed_pressure_states") or []):
            return f"pressure state {status.pressure_watch_state or 'none'} not allowed"
        allowed_strategies = {str(x).upper() for x in scenario.get("allowed_strategies") or []}
        disabled_strategies = {str(x).upper() for x in scenario.get("disabled_strategies") or []}
        strategy_id = str(status.trade_strategy_id or NO_TRADE).upper()
        if strategy_id in DISABLED_STRATEGIES:
            return f"strategy {strategy_id} disabled globally"
        if strategy_id == NO_TRADE:
            return "strategy no trade"
        if bool(status.trade_strategy_forced):
            return "forced learning probe not eligible for compounding mock execution"
        if route_action not in {
            "context_routing_exact_positive_pnl_instance",
            "context_routing_exact_instance_avoided_bad_queue",
        }:
            return "strategy lacks exact positive historical route"
        if allowed_strategies and strategy_id not in allowed_strategies:
            return f"strategy {strategy_id} not allowed"
        if strategy_id in disabled_strategies:
            return f"strategy {strategy_id} disabled"

        if status.trade_strategy_blockers:
            return str(status.trade_strategy_blockers[0])
        for blocker in status.trade_option_blockers or []:
            text = str(blocker)
            if "Daily news context is stale" in text:
                continue
            return text
        return ""

    def _log_mock_trade_opportunity(
        self,
        *,
        settings: dict,
        scenario: dict,
        status: RegimeStatus,
        chunk_id: str,
        decision: str,
        reason: str,
        side: str = "",
        fill_price: float = 0.0,
        notional: float = 0.0,
        bankroll: dict[str, Any] | None = None,
        cell_id: str = "",
        inputs: dict[str, Any] | None = None,
        trade: dict | None = None,
    ) -> None:
        sid = str(scenario.get("id") or "")
        if not sid:
            return
        key = "|".join([
            sid,
            str(status.asset),
            str(status.venue),
            str(chunk_id),
            str(decision),
            str(reason),
        ])
        if key in self._mock_opportunity_logged:
            return
        self._mock_opportunity_logged.add(key)
        if len(self._mock_opportunity_logged) > 50000:
            self._mock_opportunity_logged = set(list(self._mock_opportunity_logged)[-25000:])

        inputs = inputs or {}
        row = {
            "schema": "live_mock_trade_opportunity_v1",
            "ts_utc": time.time(),
            "source": "backend_live_mock_trade_opportunity",
            "decision": decision,
            "reason": reason,
            "asset": status.asset,
            "venue": status.venue,
            "side": side or status.trade_option_side or status.pressure_watch_direction,
            "cell_id": cell_id,
            "chunk_id": str(chunk_id),
            "bucket_session": str(inputs.get("bucket_session") or _live_bucket_session()),
            "scenario_id": sid,
            "scenario_label": str(scenario.get("label") or sid),
            "notional_pct_bank": float(scenario.get("notional_pct_bank") or 0.0),
            "initial_bank_usd": float(settings.get("initial_bank_usd") or 10000.0),
            "mock_equity_usd": float((bankroll or {}).get("equity_usd") or 0.0),
            "mock_bank_usd": float((bankroll or {}).get("bank_usd") or 0.0),
            "mock_realized_pnl_usd": float((bankroll or {}).get("realized_pnl_usd") or 0.0),
            "mock_open_exposure_usd": float((bankroll or {}).get("open_exposure_usd") or 0.0),
            "planned_notional_usd": float(notional or 0.0),
            "fill_price": float(fill_price or 0.0),
            "actual_execution": False,
            "actual_notional": 0.0,
            "learning_capital_model": "full_bank_hypothetical_no_exposure_lock",
            "exit_params_path": str(settings.get("exit_params_path") or ""),
            "exit_params_loaded": bool(settings.get("exit_params_loaded")),
            "trade_strategy_id": status.trade_strategy_id,
            "trade_strategy_label": status.trade_strategy_label,
            "trade_strategy_mode": "live_paper",
            "trade_strategy_confidence": status.trade_strategy_confidence,
            "trade_strategy_variant_id": status.trade_strategy_variant_id,
            "trade_strategy_forced": bool(status.trade_strategy_forced),
            "trade_strategy_reasons": list(status.trade_strategy_reasons),
            "trade_strategy_blockers": list(status.trade_strategy_blockers),
            "trade_strategy_risk_tags": list(status.trade_strategy_risk_tags),
            "trade_strategy_source_queue_action": status.trade_strategy_source_queue_action,
            "trade_option_state": status.trade_option_state,
            "trade_option_profile": status.trade_option_profile,
            "trade_option_readiness": status.trade_option_readiness,
            "trade_option_blockers": list(status.trade_option_blockers),
            "trade_stage": status.trade_stage,
            "trade_age_chunks": status.trade_age_chunks,
            "trade_present_score": status.trade_present_score,
            "trade_score_band": status.trade_score_band,
            "trade_from_onset_bps": status.trade_from_onset_bps,
            "trade_current_chunk_bps": status.trade_current_chunk_bps,
            "trade_recent_2chunk_bps": status.trade_recent_2chunk_bps,
            "pressure_watch_state": status.pressure_watch_state,
            "pressure_watch_label": status.pressure_watch_label,
            "pressure_watch_direction": status.pressure_watch_direction,
            "pressure_watch_reasons": list(status.pressure_watch_reasons),
            "regime": status.regime,
            "confidence": status.confidence,
            "adjusted_confidence": status.adjusted_confidence,
            "mean_dipole": status.mean_dipole,
            "volume_zscore": float(inputs.get("volume_zscore") or 0.0),
            "dipole_acl1": float(inputs.get("dipole_acl1") or 0.0),
            "daily_news_context": dict(status.daily_news_context),
            "daily_news_status": dict(status.daily_news_status),
            "opened_trade_intent_id": str((trade or {}).get("intent_id") or ""),
        }
        try:
            os.makedirs(os.path.dirname(_LIVE_MOCK_OPPORTUNITIES_PATH), exist_ok=True)
            with open(_LIVE_MOCK_OPPORTUNITIES_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        except Exception as e:
            print(f"[mock-trade] opportunity log error: {e}", flush=True)

    def _maybe_open_mock_trade_scenarios(self, asset: str, venue: str,
                                         status: RegimeStatus, chunk) -> None:
        settings = _load_mock_trade_settings(load_exit_params=True)
        if not settings.get("enabled") or not settings.get("backend_controller_enabled", True):
            return
        side = status.trade_option_side or status.pressure_watch_direction
        bid, ask, mid = _current_quote(asset, venue)
        fill_price = float((ask if side == "buy" else bid) if side in ("buy", "sell") else 0.0) or float(mid)

        trades = _load_practice_trades()
        min_notional = float(settings.get("min_trade_notional_usd") or 25.0)
        inputs = self._pressure_inputs.get((asset, venue), {})
        bucket_session = str(inputs.get("bucket_session") or _live_bucket_session())
        exit_params_map = settings.get("exit_params_map") or {}

        chunk_id = getattr(chunk, "chunk_id", str(round(time.time())))
        for scenario in settings.get("scenarios") or []:
            if not scenario.get("enabled", True):
                continue
            sid = str(scenario.get("id") or "")
            if not sid:
                continue
            prefix = f"mock_trade_scenario_{sid}_{asset.lower()}_{venue.lower()}_"
            cell_id = f"{prefix}{chunk_id}"
            bankroll = _mock_trade_bankroll(settings, trades, scenario_id=sid)
            if side not in ("buy", "sell"):
                self._log_mock_trade_opportunity(
                    settings=settings,
                    scenario=scenario,
                    status=status,
                    chunk_id=str(chunk_id),
                    decision="skipped",
                    reason="no_trade_side",
                    cell_id=cell_id,
                    bankroll=bankroll,
                    inputs=inputs,
                )
                continue
            if fill_price <= 0:
                self._log_mock_trade_opportunity(
                    settings=settings,
                    scenario=scenario,
                    status=status,
                    chunk_id=str(chunk_id),
                    decision="skipped",
                    reason="no_fill_price",
                    side=side,
                    cell_id=cell_id,
                    bankroll=bankroll,
                    inputs=inputs,
                )
                continue
            blocker = self._mock_scenario_blocker(scenario, status)
            if blocker:
                self._log_mock_trade_opportunity(
                    settings=settings,
                    scenario=scenario,
                    status=status,
                    chunk_id=str(chunk_id),
                    decision="blocked",
                    reason=blocker,
                    side=side,
                    fill_price=fill_price,
                    cell_id=cell_id,
                    bankroll=bankroll,
                    inputs=inputs,
                )
                continue
            if any(str(t.get("cell_id", "")) == cell_id for t in trades):
                self._log_mock_trade_opportunity(
                    settings=settings,
                    scenario=scenario,
                    status=status,
                    chunk_id=str(chunk_id),
                    decision="skipped",
                    reason="already_opened_for_chunk",
                    side=side,
                    fill_price=fill_price,
                    cell_id=cell_id,
                    bankroll=bankroll,
                    inputs=inputs,
                )
                continue
            notional = float(settings.get("initial_bank_usd") or 10000.0) * float(
                scenario.get("notional_pct_bank") or 0.0
            )
            if notional < min_notional:
                self._log_mock_trade_opportunity(
                    settings=settings,
                    scenario=scenario,
                    status=status,
                    chunk_id=str(chunk_id),
                    decision="blocked",
                    reason="below_min_notional",
                    side=side,
                    fill_price=fill_price,
                    notional=notional,
                    cell_id=cell_id,
                    bankroll=bankroll,
                    inputs=inputs,
                )
                continue
            qty = notional / fill_price
            fee_bps = float(settings.get("mock_fee_bps") or _PRACTICE_FEE_BPS)
            fee_usd = notional * (fee_bps / 10000.0)
            scenario_for_exit = dict(scenario)
            if exit_params_map:
                scenario_for_exit["exit_params_map"] = exit_params_map
            exit_profile = trade_exit_strategy.exit_profile_from_scenario(scenario_for_exit)
            trade = {
                "intent_id": str(uuid.uuid4())[:12],
                "asset": asset,
                "venue": venue,
                "side": side,
                "price": float(fill_price),
                "qty": float(qty),
                "qty_initial": float(qty),
                "qty_open": float(qty),
                "notional": float(notional),
                "note": (
                    f"mock {scenario.get('label') or sid}: "
                    f"score={status.trade_present_score}/100 stage={status.trade_stage}; "
                    f"{'; '.join((status.trade_option_entry_reasons or [])[:2])}"
                ),
                "ts_utc": time.time(),
                "practice": True,
                "auto": True,
                "source": "mock_scenario",
                "cell_id": cell_id,
                "kind": "practice",
                "status": "open",
                "fill_price": float(fill_price),
                "fees_usd": float(fee_usd),
                "entry_fees_usd": float(fee_usd),
                "fee_bps": fee_bps,
                "hypothetical_notional": float(notional),
                "actual_notional": 0.0,
                "actual_execution": False,
                "actual_side": side,
                "learning_capital_model": "full_bank_hypothetical_no_exposure_lock",
                "bucket_session": bucket_session,
                "exit_management_model": exit_profile.profile_id,
                "exit_strategy_id": exit_profile.profile_id,
                "exit_strategy_label": exit_profile.label,
                "score_exit_min_hold_minutes": exit_profile.score_exit_min_hold_minutes,
                "score_exit_min_profit_bps": exit_profile.score_exit_min_profit_bps,
                "profitable_hold_extension_minutes": exit_profile.profitable_hold_extension_minutes,
                "exit_tp1_bps": exit_profile.tp1_bps,
                "exit_scale_out_fraction": exit_profile.scale_out_fraction,
                "exit_runner_trail_bps": exit_profile.runner_trail_bps,
                "exit_max_hold_minutes": exit_profile.max_hold_minutes,
                "suggested_exit_strategy_id": trade_exit_strategy.suggested_exit_profile_id_for_strategy(status.trade_strategy_id),
                "exit_stage": "stage1",
                "scale_out_count": 0,
                "scale_out_fraction_realized": 0.0,
                "scale_out_tp1_bps": 0.0,
                "runner_exit_reason": "",
                "exit_legs": [],
                "exit_price": 0.0,
                "exit_ts_utc": 0.0,
                "gross_pnl_usd": 0.0,
                "realized_pnl_usd": 0.0,
                "hold_minutes": float(scenario.get("hold_minutes") or status.trade_option_hold_minutes or 10),
                "mock_scenario_id": sid,
                "mock_scenario_label": str(scenario.get("label") or sid),
                "mock_scenario_min_present_score": int(scenario.get("min_present_score") or 0),
                "mock_scenario_exit_score_drop": int(scenario.get("exit_score_drop") or 0),
                "mock_scenario_stop_loss_bps": float(scenario.get("stop_loss_bps") or 0.0),
                "mock_scenario_take_profit_bps": float(scenario.get("take_profit_bps") or 0.0),
                "mock_bank_usd_at_entry": float(settings.get("initial_bank_usd") or 10000.0),
                "mock_equity_usd_at_entry": float(bankroll["equity_usd"]),
                "mock_realized_pnl_usd_at_entry": float(bankroll["realized_pnl_usd"]),
                "mock_exposure_cap_usd_at_entry": float(bankroll["exposure_cap_usd"]),
                "trade_option_state": status.trade_option_state,
                "trade_option_profile": status.trade_option_profile,
                "trade_option_readiness": status.trade_option_readiness,
                "trade_stage": status.trade_stage,
                "trade_age_chunks": status.trade_age_chunks,
                "trade_present_score": status.trade_present_score,
                "trade_score_band": status.trade_score_band,
                "trade_from_onset_bps": status.trade_from_onset_bps,
                "trade_current_chunk_bps": status.trade_current_chunk_bps,
                "trade_recent_2chunk_bps": status.trade_recent_2chunk_bps,
                "mean_dipole": float(status.mean_dipole),
                "trade_option_exit_rules": list(status.trade_option_exit_rules),
                "trade_strategy_id": status.trade_strategy_id,
                "trade_strategy_label": status.trade_strategy_label,
                "trade_strategy_mode": "live_paper",
                "trade_strategy_confidence": status.trade_strategy_confidence,
                "trade_strategy_reasons": list(status.trade_strategy_reasons),
                "trade_strategy_blockers": list(status.trade_strategy_blockers),
                "trade_strategy_stop_loss_bps": status.trade_strategy_stop_loss_bps,
                "trade_strategy_take_profit_bps": status.trade_strategy_take_profit_bps,
                "trade_strategy_exit_score_drop": status.trade_strategy_exit_score_drop,
                "trade_strategy_forced": bool(status.trade_strategy_forced),
                "trade_strategy_variant_id": status.trade_strategy_variant_id,
                "trade_strategy_risk_tags": list(status.trade_strategy_risk_tags),
                "trade_strategy_handoff_hint": status.trade_strategy_handoff_hint,
                "trade_strategy_source_queue_action": status.trade_strategy_source_queue_action,
                "daily_news_context": dict(status.daily_news_context),
                "daily_news_status": dict(status.daily_news_status),
                "high_conviction_ticket": dict(status.high_conviction_ticket),
                "dipole_coupling": dict((status.high_conviction_ticket.get("dipole_coupling") if status.high_conviction_ticket else {}) or {}),
                "onchain_features": dict(((status.high_conviction_ticket.get("onchain_context") if status.high_conviction_ticket else {}) or {}).get("features") or {}),
                "pressure_watch_state": status.pressure_watch_state,
                "pressure_watch_label": status.pressure_watch_label,
                "pressure_watch_reasons": list(status.pressure_watch_reasons),
            }
            _stamp_practice_exit_profile(trade, scenario_for_exit)
            _persist_practice_trade(trade)
            self._log_mock_trade_opportunity(
                settings=settings,
                scenario=scenario,
                status=status,
                chunk_id=str(chunk_id),
                decision="opened",
                reason="opened",
                side=side,
                fill_price=fill_price,
                notional=notional,
                bankroll=bankroll,
                cell_id=cell_id,
                inputs=inputs,
                trade=trade,
            )
            print(
                f"[mock-trade] opened {sid} {side} {asset}/{venue} "
                f"notional={notional:.2f} bank={bankroll['bank_usd']:.2f} "
                f"score={status.trade_present_score}",
                flush=True,
            )

    def _maybe_rotate_mock_trade(self, scenario: dict, incoming_status: RegimeStatus,
                                 trades: list[dict], min_notional: float) -> bool:
        sid = str(scenario.get("id") or "")
        incoming_score = int(incoming_status.trade_present_score or 0)
        open_same = [
            t for t in trades
            if t.get("status") == "open"
            and t.get("source") == "mock_scenario"
            and str(t.get("mock_scenario_id") or "") == sid
        ]
        if not open_same:
            return False

        stage_penalty = {"late": 0, "mature": 1, "early_follow": 2, "onset": 3}

        def _row(t: dict) -> tuple[float, int, int, bool, dict]:
            unreal_bps = _practice_trade_unrealized_bps(t)
            st = self.current_status.get((str(t.get("asset") or ""), str(t.get("venue") or "")))
            live_score = int(
                (st.trade_present_score if st is not None else 0)
                or t.get("trade_present_score")
                or 0
            )
            live_stage = str((st.trade_stage if st is not None else "") or t.get("trade_stage") or "")
            entry_score = int(t.get("trade_present_score") or live_score or 0)
            degrading = (
                unreal_bps <= float(scenario.get("rotation_min_underperform_bps", -5.0))
                or live_stage == "late"
                or live_score <= entry_score - int(scenario.get("rotation_min_score_advantage") or 10)
            )
            return (
                float(unreal_bps),
                live_score,
                int(stage_penalty.get(live_stage, 0)),
                bool(degrading),
                t,
            )

        ranked = sorted((_row(t) for t in open_same), key=lambda r: (r[0], r[1], r[2]))
        weakest_unreal_bps, weakest_score, _stage_rank, degrading, weakest = ranked[0]
        score_advantage = int(scenario.get("rotation_min_score_advantage") or 10)
        if incoming_score < weakest_score + score_advantage:
            return False
        if bool(scenario.get("rotation_require_degrading", True)) and not degrading:
            return False
        if float(weakest.get("notional") or 0.0) < min_notional:
            return False
        if _close_practice_trade_at_market(weakest, "rotation_to_better_performer"):
            weakest["rotation_to_asset"] = incoming_status.asset
            weakest["rotation_to_venue"] = incoming_status.venue
            weakest["rotation_to_score"] = incoming_score
            weakest["rotation_from_score"] = weakest_score
            weakest["rotation_from_unrealized_bps"] = round(float(weakest_unreal_bps), 4)
            print(
                f"[mock-trade] rotated {sid}: closed {weakest.get('asset')}/"
                f"{weakest.get('venue')} score={weakest_score} "
                f"unreal_bps={weakest_unreal_bps:.2f} for "
                f"{incoming_status.asset}/{incoming_status.venue} score={incoming_score}",
                flush=True,
            )
            return True
        return False

    def _auto_trade_invalidation_reason(self, trade: dict) -> str:
        if trade.get("status") != "open":
            return ""
        if trade.get("auto") is not True:
            return ""
        cell_id = str(trade.get("cell_id", ""))
        is_trade_option = cell_id.startswith("auto_trade_option_")
        is_mock_scenario = cell_id.startswith("mock_trade_scenario_")
        if not is_trade_option and not is_mock_scenario:
            return ""

        asset = str(trade.get("asset") or "")
        venue = str(trade.get("venue") or "")
        status = self.current_status.get((asset, venue))
        if status is None:
            return ""

        side = str(trade.get("side") or "")
        if side not in ("buy", "sell"):
            return ""

        pressure_dir = str(status.pressure_watch_direction or "")
        if pressure_dir in ("buy", "sell") and pressure_dir != side:
            return "pressure_flipped"

        if status.regime in STRONG_PRESSURE_REGIMES:
            strong_side = "buy" if status.regime.endswith("_UP") else "sell"
            if strong_side != side:
                return "opposite_whale_herd"

        profile = str(trade.get("trade_option_profile") or "")
        if profile == "early_probe" and status.trade_option_state == "watch":
            return "setup_degraded_to_watch"

        if status.trade_stage == "late":
            return "setup_late"

        min_score = int(trade.get("mock_scenario_min_present_score") or 55)
        if int(status.trade_present_score or 0) and status.trade_present_score < min_score:
            return "present_score_degraded"

        if is_mock_scenario:
            entry_score = int(trade.get("trade_present_score") or 0)
            score_drop = int(trade.get("mock_scenario_exit_score_drop") or 0)
            score_drop = score_drop or int(trade.get("trade_strategy_exit_score_drop") or 0)
            if score_drop and entry_score and int(status.trade_present_score or 0) <= entry_score - score_drop:
                return "present_score_dropped_from_entry"
            u_bps = _practice_trade_unrealized_bps(trade)
            stop_loss = float(trade.get("mock_scenario_stop_loss_bps") or 0.0)
            take_profit = float(trade.get("mock_scenario_take_profit_bps") or 0.0)
            stop_loss = stop_loss or float(trade.get("trade_strategy_stop_loss_bps") or 0.0)
            take_profit = take_profit or float(trade.get("trade_strategy_take_profit_bps") or 0.0)
            if stop_loss and u_bps <= -stop_loss:
                return "stop_loss"
            if take_profit and u_bps >= take_profit:
                return "take_profit"

        if status.trade_option_blockers:
            return "setup_blocker"

        news_ctx = status.daily_news_context or {}
        starter_actions = {
            str(action).upper()
            for action in (news_ctx.get("starter_actions") or [])
        }
        if side == "buy" and (
            "EXIT_LONGS" in starter_actions
            or "REDUCE_GROSS_EXPOSURE" in starter_actions
        ):
            return "news_started_exit_longs"
        if side == "sell" and (
            "EXIT_SHORTS" in starter_actions
            or "REDUCE_GROSS_EXPOSURE" in starter_actions
        ):
            return "news_started_exit_shorts"

        return ""

    def _mock_scenario_for_trade(self, trade: dict) -> dict:
        settings = _load_mock_trade_settings(load_exit_params=True)
        sid = str(trade.get("mock_scenario_id") or "")
        scenario = next(
            (
                dict(raw)
                for raw in (settings.get("scenarios") or [])
                if str(raw.get("id") or "") == sid
            ),
            {},
        )
        if not scenario:
            scenario = {
                "id": sid,
                "label": str(trade.get("mock_scenario_label") or sid),
                "hold_minutes": float(trade.get("hold_minutes") or 10.0),
                "min_present_score": int(trade.get("mock_scenario_min_present_score") or 55),
                "exit_score_drop": int(trade.get("mock_scenario_exit_score_drop") or 0),
                "stop_loss_bps": float(trade.get("mock_scenario_stop_loss_bps") or 0.0),
                "take_profit_bps": float(trade.get("mock_scenario_take_profit_bps") or 0.0),
            }
        if settings.get("exit_params_map"):
            scenario["exit_params_map"] = settings["exit_params_map"]
        return scenario

    def _handle_mock_scenario_exit(self, trade: dict) -> bool:
        if trade.get("status") != "open" or trade.get("source") != "mock_scenario":
            return False
        asset = str(trade.get("asset") or "")
        venue = str(trade.get("venue") or "")
        status = self.current_status.get((asset, venue))
        if status is None:
            return False
        bid, ask, mid = _current_quote(asset, venue)
        if max(float(bid or 0.0), float(ask or 0.0), float(mid or 0.0)) <= 0:
            return False
        scenario = self._mock_scenario_for_trade(trade)
        _stamp_practice_exit_profile(trade, scenario)
        elapsed_min = (time.time() - float(trade.get("ts_utc") or time.time())) / 60.0
        unreal_bps = trade_exit_strategy.unrealized_bps(trade, bid, ask, mid)
        setup_blocker = self._mock_scenario_blocker(scenario, status)
        decision = trade_exit_strategy.decide_trade_exit(
            trade,
            status,
            scenario,
            unreal_bps,
            elapsed_min,
            setup_blocker_reason=setup_blocker,
        )
        trade["last_exit_decision"] = decision.to_trade_metadata()
        trade["exit_strategy_id"] = decision.profile_id
        if decision.deferred_signal:
            trade.setdefault("deferred_exit_signals", []).append(decision.deferred_signal)
        if decision.action == "scale_out":
            fraction = float((decision.metadata or {}).get("scale_out_fraction") or 0.0)
            trade["exit_decision"] = decision.to_trade_metadata()
            if _scale_out_practice_trade(trade, bid, ask, mid, time.time(), decision.reason, fraction):
                _apply_practice_exit_decision_metadata(trade, decision)
                return True
            _apply_practice_exit_decision_metadata(trade, decision)
            return bool(decision.metadata)
        _apply_practice_exit_decision_metadata(trade, decision)
        if decision.action == "close" and decision.reason:
            trade["exit_decision"] = decision.to_trade_metadata()
            return _close_practice_trade_at_market(trade, decision.reason)
        return bool(decision.metadata or decision.deferred_signal)

    def _handle_carry_alert(self, alert: dict) -> None:
        """T3.3 carry paper-trade dispatcher. Open on
        FUNDING_OVERLEVERED_{LONG,SHORT} (one trade per asset, perp
        venue at a time — dedup by checking persisted trades). Close
        on FUNDING_CLEARED for that key. Timeout closes are handled
        by the same sweep that closes regime-driven cells."""
        atype = alert.get("type", "")
        asset = alert.get("asset", "")
        venue = alert.get("venue", "")
        if not asset or not venue:
            return

        if atype == "FUNDING_CLEARED":
            trades = _load_practice_trades()
            changed = False
            for t in trades:
                if not _fp_is_carry(t):
                    continue
                if t.get("asset") != asset or t.get("venue") != venue:
                    continue
                # Use the perp current price as the closing mark; if
                # we don't have one, fall back to fill_price (best we
                # can do without quote streams for perp venues yet).
                bid, ask, mid = _current_quote(asset, venue)
                close_px = (mid or float(t.get("fill_price", 0.0)))
                if close_px <= 0:
                    continue
                _fp_close_carry(t, close_px, close_reason="funding_cleared")
                changed = True
                print(f"[carry-paper] closed {t.get('cell_id')} "
                      f"{asset}/{venue} on funding clear: "
                      f"realized_pnl={t.get('realized_pnl_usd', 0):.2f} "
                      f"funding_income={t.get('funding_income_usd', 0):.2f} "
                      f"hours={t.get('elapsed_hours', 0):.1f}",
                      flush=True)
            if changed:
                _rewrite_practice_trades(trades)
            return

        if not atype.startswith("FUNDING_OVERLEVERED_"):
            return

        spec = _fp_find_carry_spec(asset, venue)
        if spec is None:
            return

        # Dedup: skip if there's already an open carry trade for this
        # (asset, perp venue) — funding alerts can re-fire (e.g.
        # ELEVATED -> EXTREME).
        existing = _load_practice_trades()
        for t in existing:
            if (_fp_is_carry(t)
                    and t.get("asset") == asset
                    and t.get("venue") == venue):
                return

        rate = float(alert.get("rate", 0.0))
        bid, ask, mid = _current_quote(asset, venue)
        perp_price = mid if mid > 0 else (bid or ask or 0.0)
        if perp_price <= 0:
            print(f"[carry-paper] no perp quote for {asset}/{venue}; "
                  f"skipping carry open", flush=True)
            return

        trade = _fp_open_carry(spec, funding_rate_at_open=rate,
                                 perp_price=perp_price)
        _persist_practice_trade(trade)
        print(f"[carry-paper] opened {spec.cell_id} {trade['side']} "
              f"{asset}/{venue} @ {perp_price:.4f} "
              f"(rate={rate*1e4:+.2f}bps/8h max_hold={spec.max_hold_minutes:.0f}m "
              f"intent_id={trade['intent_id']})", flush=True)

    def _maybe_open_forward_paper_trades(self, asset: str, venue: str,
                                          regime: str, feat, chunk,
                                          cells=None, convergence: dict | None = None) -> None:
        # Static CellSpec-based path (Pass-5 hand-picked cells)
        cells = list(cells) if cells is not None else _fp_find_cells(
            asset, venue, regime, feat, chunk)
        bid, ask, mid = _current_quote(asset, venue)
        # Vol-target sizing: scale notional ∝ VOL_TARGET / chunk realized_vol,
        # clipped to [0.5x, 2.0x]. Same multiplier applies to all cells
        # firing on this chunk since they share the same regime context.
        rv = float(getattr(feat, "realized_vol", 0.0) or 0.0)
        vol_mult = _fp_vol_mult(rv, asset=asset, venue=venue)
        for cell in cells:
            fill_price = _fp_entry_price(cell, bid, ask, mid)
            if fill_price <= 0:
                continue
            trade = _fp_open_trade(cell, fill_price, vol_multiplier=vol_mult)
            _persist_practice_trade(trade)
            print(f"[forward-paper] opened {cell.cell_id} "
                  f"({cell.kind}) {cell.side} {asset}/{venue} @ {fill_price:.4f} "
                  f"(intent_id={trade['intent_id']} "
                  f"rv={rv:.4f} vol_mult={vol_mult:.2f})", flush=True)

        if convergence is not None:
            existing_open_conv = {
                t.get("cell_id", "")
                for t in _load_practice_trades()
                if t.get("status") == "open"
                and t.get("auto") is True
                and isinstance(t.get("cell_id"), str)
                and t.get("cell_id", "").startswith("conv_")
            }
            conv_side = str(convergence.get("side") or "")
            conv_fill = float(ask if conv_side == "buy" else bid)
            if conv_fill <= 0:
                conv_fill = float(mid)
            conv_trade = _fp_open_convergence_trade(
                convergence,
                conv_fill,
                vol_multiplier=vol_mult,
            )
            if conv_trade is not None and conv_trade["cell_id"] not in existing_open_conv:
                _persist_practice_trade(conv_trade)
                print(
                    f"[conv-paper] opened {conv_trade['cell_id']} "
                    f"{conv_trade['side']} {asset}/{venue} @ "
                    f"{conv_trade['fill_price']:.4f} "
                    f"support={conv_trade['convergence_support_count']} "
                    f"vol_mult={vol_mult:.2f}",
                    flush=True,
                )

        # F11 edge-driven path: open a trade when ANY horizon is STRONG.
        # Dedup against currently-open edge trades for this (asset, venue,
        # regime, horizon) so we don't fire the same cell repeatedly while
        # the strength persists.
        from backend.forward_paper import try_open_edge_driven_trade
        edge_tags = self.edge_tracker.cell_tags(asset, venue, regime)
        if any(s == "STRONG" for s in (
                edge_tags.intraday.strength, edge_tags.daily.strength,
                edge_tags.weekly.strength, edge_tags.longterm.strength)):
            existing_open = {
                t.get("cell_id", "")
                for t in _load_practice_trades()
                if t.get("status") == "open"
                and t.get("auto") is True
                and isinstance(t.get("cell_id"), str)
                and t.get("cell_id", "").startswith("edge_")
            }
            edge_trade = try_open_edge_driven_trade(
                asset, venue, regime, edge_tags, bid, ask, mid,
                vol_multiplier=vol_mult)
            if edge_trade is not None and edge_trade["cell_id"] not in existing_open:
                _persist_practice_trade(edge_trade)
                print(f"[edge-paper] opened {edge_trade['cell_id']} "
                      f"{edge_trade['side']} {asset}/{venue} @ "
                      f"{edge_trade['fill_price']:.4f} "
                      f"horizon={edge_trade['edge_horizon']} "
                      f"r={edge_trade['edge_r']:+.2f} n={edge_trade['edge_n']} "
                      f"hold_min={edge_trade['hold_minutes']:.0f}",
                      flush=True)

    def _sweep_close_forward_paper_trades(self) -> None:
        trades = _load_practice_trades()
        now = time.time()
        any_changed = False
        for t in trades:
            if t.get("status") == "open" and t.get("source") == "mock_scenario":
                before_status = t.get("status")
                if self._handle_mock_scenario_exit(t):
                    any_changed = True
                    if t.get("status") != before_status:
                        print(f"[forward-paper] closed {t.get('cell_id')} "
                              f"intent_id={t.get('intent_id')} "
                              f"reason={t.get('close_reason', '')} "
                              f"realized_pnl_usd={t.get('realized_pnl_usd', 0):.2f}",
                              flush=True)
                continue
            invalid_reason = self._auto_trade_invalidation_reason(t)
            expired = _fp_is_expired(t, now)
            if not expired and not invalid_reason:
                continue
            bid, ask, mid = _current_quote(t.get("asset", ""), t.get("venue", ""))
            before_status = t.get("status")
            # Carry trades (T3.3) use a different close path: funding
            # accrual P&L instead of price-direction P&L.
            if _fp_is_carry(t):
                close_px = mid if mid > 0 else (bid or ask or float(t.get("fill_price", 0.0)))
                if close_px > 0:
                    _fp_close_carry(t, close_px, close_reason="max_hold_elapsed")
            else:
                _fp_close_trade(t, bid, ask, mid)
                if invalid_reason and t.get("status") != before_status:
                    t["close_reason"] = f"auto_{invalid_reason}"
            if t.get("status") != before_status:
                any_changed = True
                print(f"[forward-paper] closed {t.get('cell_id')} "
                      f"intent_id={t.get('intent_id')} "
                      f"reason={t.get('close_reason', '')} "
                      f"realized_pnl_usd={t.get('realized_pnl_usd', 0):.2f}",
                      flush=True)
        if any_changed:
            _rewrite_practice_trades(trades)

    async def resolve_pending_outcomes(self, hold_minutes: int = 30,
                                         abandon_after_minutes: int = 120,
                                         fee_bps_round_trip: float = 50.0):
        """For each pending signal whose hold window has elapsed, fetch the
        current price for its (asset, venue) and compute realized P&L.

        Called every poll cycle. Idempotent: skips already-resolved signals.
        """
        now = time.time()
        changed = False
        for sig in list(self.recent_signals):
            if sig.outcome_status != "pending":
                continue
            elapsed_min = (now - sig.timestamp_utc) / 60.0
            if elapsed_min < hold_minutes:
                continue   # not yet time to evaluate
            # Fetch current price from the bins file
            path = next((p for a, v, p in DATA_SOURCES if a == sig.asset and v == sig.venue), None)
            if not path:
                continue
            bars = self._bars_from_bins(path)
            if not bars:
                continue
            latest_price = float(bars[-1].close)
            if elapsed_min > abandon_after_minutes:
                sig.outcome_status = "abandoned"
                sig.outcome_resolved_utc = now
                sig.outcome_exit_price = latest_price
                sig.outcome_realized_bps = 0.0
                changed = True
                continue
            # Resolve: signed return = expected_direction * log(exit/entry) * 10000
            if sig.entry_price > 0 and sig.expected_direction != 0:
                import math as _math
                signed_log_ret = sig.expected_direction * _math.log(latest_price / sig.entry_price)
                bps = signed_log_ret * 10000.0 - fee_bps_round_trip
                sig.outcome_realized_bps = float(bps)
                sig.outcome_exit_price = latest_price
                sig.outcome_resolved_utc = now
                sig.outcome_status = "resolved"
                changed = True

                # Per-cell drift tracking — when an outcome contradicts the
                # cell's currently-claimed direction (e.g. registry says
                # "momentum" but the trade lost), increment a streak. On
                # streak >= 3 we emit a drift_alert SSE event so users see
                # the read going stale BEFORE waiting for the next registry
                # rebuild. Wins reset the streak.
                from playbook_generator import _load_registry_if_stale
                registry = _load_registry_if_stale()
                venue_short = "CB" if sig.venue.lower().startswith("c") else (
                    "KR" if sig.venue.lower().startswith("k") else sig.venue)
                cell_key = f"{sig.asset}/{venue_short}/{sig.regime}"
                cell = registry.get(cell_key) or {}
                cell_current = cell.get("current") or {}
                cell_direction = cell_current.get("direction") or ""
                if cell_direction in ("momentum", "mean_revert"):
                    contradicted = (cell_direction == "momentum" and bps < 0) \
                                    or (cell_direction == "mean_revert" and bps < 0)
                    # NB: with expected_direction baked into bps already,
                    # bps<0 means the signal lost. For momentum the cell
                    # predicted continuation and we lost = contradiction.
                    # For mean_revert the cell predicted fade and we lost = contradiction.
                    if contradicted:
                        streak = self._cell_contradiction_streak.get(cell_key, 0) + 1
                        self._cell_contradiction_streak[cell_key] = streak
                        if streak >= 3:
                            await self._emit_drift_alert({
                                "type": "outcome_contradiction_streak",
                                "key": cell_key,
                                "asset": sig.asset, "venue": venue_short,
                                "regime": sig.regime,
                                "streak": streak,
                                "expected_direction": cell_direction,
                                "latest_outcome_bps": float(bps),
                                "summary": (
                                    f"{cell_key} predicted {cell_direction} but "
                                    f"the last {streak} signals all lost — "
                                    f"the cell's read may be drifting; "
                                    f"check next registry rebuild."),
                            })
                            # Reset streak on emit so we don't spam — next 3
                            # contradictions in a row would trigger again.
                            self._cell_contradiction_streak[cell_key] = 0
                    else:
                        self._cell_contradiction_streak[cell_key] = 0
        if changed:
            self._rewrite_signals()

    async def _emit_cross_venue_cascades(self):
        """Detect WHALE+HERD same-direction simultaneity across venues for
        the same asset and emit a CROSS_VENUE_WHALE_HERD signal per event.

        Runs after both venues have polled in poll_all(). Dedupes by
        (asset, frozenset(venues), latest_chunk_id) so we only emit once
        per cross-venue cascade window.
        """
        from collections import Counter, defaultdict
        by_asset: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for (asset, venue) in self._latest_chunk_per_venue:
            by_asset[asset].append((asset, venue))

        for asset, keys in by_asset.items():
            if len(keys) < 2:
                continue
            for (a, primary_venue) in keys:
                primary_chunk = self._latest_chunk_per_venue.get((a, primary_venue))
                primary_status = self.current_status.get((a, primary_venue))
                if primary_chunk is None or primary_status is None:
                    continue
                primary_kind = ("WHALE" if "WHALE" in primary_status.regime
                                else ("HERD" if "HERD" in primary_status.regime
                                       else None))
                if primary_kind is None:
                    continue
                if primary_status.regime.endswith("_UP"):
                    primary_dir = "UP"
                elif primary_status.regime.endswith("_DOWN"):
                    primary_dir = "DOWN"
                else:
                    continue
                for (a2, other_venue) in keys:
                    if other_venue == primary_venue:
                        continue
                    other_map = self._minute_regime_per_venue.get((a, other_venue), {})
                    if not other_map or not primary_chunk.bars:
                        continue
                    ts_lo = primary_chunk.bars[0].ts
                    ts_hi = primary_chunk.bars[-1].ts
                    covering = [other_map[ts] for ts in other_map
                                  if ts_lo <= ts <= ts_hi]
                    if not covering:
                        continue
                    modal_other = Counter(covering).most_common(1)[0][0]
                    other_kind = ("WHALE" if "WHALE" in modal_other
                                    else ("HERD" if "HERD" in modal_other
                                           else None))
                    other_dir = ("UP" if modal_other.endswith("_UP")
                                  else ("DOWN" if modal_other.endswith("_DOWN")
                                          else None))
                    if (other_kind is None or other_dir != primary_dir
                            or {primary_kind, other_kind} != {"WHALE", "HERD"}):
                        continue
                    cascade_key = (asset, frozenset({primary_venue, other_venue}),
                                    round(ts_lo), round(ts_hi))
                    if cascade_key in self._cross_venue_cascade_emitted:
                        continue
                    self._cross_venue_cascade_emitted.add(cascade_key)
                    if len(self._cross_venue_cascade_emitted) > 1000:
                        # Bound memory; drop oldest 200 (set has no order so
                        # just clear half — these are stale anyway)
                        for k in list(self._cross_venue_cascade_emitted)[:200]:
                            self._cross_venue_cascade_emitted.discard(k)

                    cascade_event = f"CROSS_VENUE_WHALE_HERD_{primary_dir}"
                    cascade_detail = (
                        f"{primary_venue} shows {primary_status.regime}; "
                        f"{other_venue} shows {modal_other} over the same "
                        f"wall-clock window — independent cross-venue "
                        f"WHALE+HERD confirmation in direction {primary_dir}")
                    chunk_buy = float(sum(b.buy_vol for b in primary_chunk.bars))
                    chunk_sell = float(sum(b.sell_vol for b in primary_chunk.bars))
                    total_v = chunk_buy + chunk_sell
                    buy_pct = (chunk_buy / total_v * 100) if total_v > 0 else 0.0
                    split_note = (f"primary aggressor split: {buy_pct:.0f}% buy / "
                                  f"{100 - buy_pct:.0f}% sell ({total_v:.2f} units)")
                    playbook = CROSS_VENUE_CASCADE_PLAYBOOKS.get(
                        cascade_event, "(no cascade playbook configured)"
                    ) + f"  ({split_note}.)"
                    chunk_n_tr = int(sum(b.n_trades for b in primary_chunk.bars))
                    cur_price = float(primary_chunk.bars[-1].close)
                    sig = SignalEvent(
                        signal_id=str(uuid.uuid4())[:12],
                        asset=asset,
                        venue=f"{primary_venue}+{other_venue}",
                        regime=f"CROSS_VENUE_{primary_kind}_{other_kind}_{primary_dir}",
                        confidence=min(1.0, primary_status.confidence * 1.5),
                        cross_venue_multiplier=1.5,
                        adjusted_confidence=min(1.0, primary_status.confidence * 1.5),
                        mean_dipole=primary_status.mean_dipole,
                        realized_vol=primary_status.realized_vol,
                        chunk_volume=total_v,
                        notes=[cascade_detail, split_note,
                                f"primary={primary_status.regime}, other={modal_other}"],
                        playbook=playbook,
                        timestamp_utc=time.time(),
                        chunk_window=primary_status.chunk_window,
                        cascade_event=cascade_event,
                        cascade_detail=cascade_detail,
                        chunk_buy_volume=chunk_buy,
                        chunk_sell_volume=chunk_sell,
                        chunk_n_trades=chunk_n_tr,
                        current_price=cur_price,
                        current_bid=float(primary_chunk.bars[-1].bid),
                        current_ask=float(primary_chunk.bars[-1].ask),
                        last_aggressor=str(primary_chunk.bars[-1].last_aggressor),
                        event_label=("Cross-venue buying cascade confirmed"
                                       if primary_dir == "UP"
                                       else "Cross-venue selling cascade confirmed"),
                        drift_status=get_drift_status(asset, primary_venue, primary_status.regime),
                        entry_price=cur_price,
                        expected_direction=+1 if primary_dir == "UP" else -1,
                        pressure_watch_state=primary_status.pressure_watch_state,
                        pressure_watch_label=primary_status.pressure_watch_label,
                        pressure_watch_direction=primary_status.pressure_watch_direction,
                        pressure_watch_intensity=primary_status.pressure_watch_intensity,
                        pressure_watch_priority=primary_status.pressure_watch_priority,
                        pressure_watch_reasons=list(primary_status.pressure_watch_reasons),
                        trade_option_state=primary_status.trade_option_state,
                        trade_option_label=primary_status.trade_option_label,
                        trade_option_side=primary_status.trade_option_side,
                        trade_option_readiness=primary_status.trade_option_readiness,
                        trade_option_profile=primary_status.trade_option_profile,
                        trade_option_size_hint=primary_status.trade_option_size_hint,
                        trade_option_notional_scale=primary_status.trade_option_notional_scale,
                        trade_option_hold_minutes=primary_status.trade_option_hold_minutes,
                        trade_option_entry_reasons=list(primary_status.trade_option_entry_reasons),
                        trade_option_exit_rules=list(primary_status.trade_option_exit_rules),
                        trade_option_blockers=list(primary_status.trade_option_blockers),
                        trade_strategy_id=primary_status.trade_strategy_id,
                        trade_strategy_label=primary_status.trade_strategy_label,
                        trade_strategy_confidence=primary_status.trade_strategy_confidence,
                        trade_strategy_reasons=list(primary_status.trade_strategy_reasons),
                        trade_strategy_blockers=list(primary_status.trade_strategy_blockers),
                        trade_strategy_stop_loss_bps=primary_status.trade_strategy_stop_loss_bps,
                        trade_strategy_take_profit_bps=primary_status.trade_strategy_take_profit_bps,
                        trade_strategy_exit_score_drop=primary_status.trade_strategy_exit_score_drop,
                        daily_news_context=dict(primary_status.daily_news_context),
                        daily_news_status=dict(primary_status.daily_news_status),
                    )
                    self.recent_signals.append(sig)
                    self.signal_index[sig.signal_id] = sig
                    self._persist_signal(sig)
                    await self.event_queue.put({"type": "signal", "data": asdict(sig)})

    def _sibling_asset_direction(self, asset: str, venue: str) -> str | None:
        """Return the sibling asset's most recent regime direction (UP/DOWN/None).

        F7 cross-asset confirmation prefers same-venue sibling (BTC/Kraken vs
        ETH/Kraken: same exchange ecosystem, comparable liquidity profile)
        and falls back to any sibling status if same-venue is missing.
        Returns None when no sibling status exists or sibling regime is
        non-directional (EQUILIBRIUM/DEPLETED/WASH/UNKNOWN).
        """
        sibling = "ETH" if asset == "BTC" else ("BTC" if asset == "ETH" else None)
        if sibling is None:
            return None
        status = self.current_status.get((sibling, venue))
        if status is None:
            for (a, v), s in self.current_status.items():
                if a == sibling:
                    status = s
                    break
        if status is None:
            return None
        return _direction(status.regime)

    def _apply_cross_venue_F6(self):
        """For each (asset, venue), set cross_venue_multiplier on its current status
        based on the OTHER venue's regime label at the same wall-clock minute."""
        # Group by asset
        from collections import defaultdict
        by_asset: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for (asset, venue) in self.current_status:
            by_asset[asset].append((asset, venue))

        for asset, keys in by_asset.items():
            if len(keys) < 2:
                continue
            # Pair up: each venue's status against the other venue's minute->regime map
            for (asset_, venue) in keys:
                status = self.current_status.get((asset, venue))
                if status is None:
                    continue
                other_keys = [k for k in keys if k != (asset, venue)]
                if not other_keys:
                    continue
                # Pick first other venue (we're 1:1 in MVP)
                other_asset, other_venue = other_keys[0]
                other_map = self._minute_regime_per_venue.get((other_asset, other_venue), {})
                if not other_map:
                    status.cross_venue_multiplier = 1.0
                else:
                    # Pick the most recent timestamps from other_map's keys overlapping our chunk window
                    # For simplicity: most recent label from the other venue
                    latest_other_ts = max(other_map.keys())
                    latest_other_regime = other_map[latest_other_ts]
                    if latest_other_regime == status.regime:
                        status.cross_venue_multiplier = 1.5
                    else:
                        status.cross_venue_multiplier = 0.5
                # adjusted_confidence reflects all six multipliers consistently
                # with ClassificationResult.adjusted_confidence so /api/status
                # mirrors what signals carry.
                status.adjusted_confidence = max(0.0, min(1.0,
                    status.confidence
                    * status.cross_venue_multiplier
                    * status.vpin_multiplier
                    * status.cross_asset_multiplier
                    * status.event_multiplier
                    * status.hawkes_multiplier))

    def _apply_present_trade_context(self, key: tuple[str, str],
                                     status: RegimeStatus,
                                     inputs: dict[str, Any]) -> None:
        side = status.pressure_watch_direction
        if side not in ("buy", "sell"):
            self._trade_setup_tracker.pop(key, None)
            return

        chunk_id = str(inputs.get("chunk_id") or "")
        start_price = float(inputs.get("chunk_start_price") or 0.0)
        close_price = float(inputs.get("chunk_close_price") or status.current_price or 0.0)
        recent_start = float(inputs.get("recent_2chunk_start_price") or start_price)
        tracker = self._trade_setup_tracker.get(key)
        if tracker is None or tracker.get("side") != side:
            tracker = {
                "side": side,
                "age_chunks": 0,
                "onset_price": start_price or close_price,
                "last_chunk_id": chunk_id,
            }
        elif tracker.get("last_chunk_id") != chunk_id:
            tracker["age_chunks"] = int(tracker.get("age_chunks") or 0) + 1
            tracker["last_chunk_id"] = chunk_id
        self._trade_setup_tracker[key] = tracker

        age = int(tracker.get("age_chunks") or 0)
        inputs["trade_age_chunks"] = age
        inputs["trade_stage"] = _trade_stage_from_age(age)
        inputs["trade_from_onset_bps"] = _signed_bps(
            float(tracker.get("onset_price") or close_price), close_price, side)
        inputs["trade_current_chunk_bps"] = _signed_bps(start_price, close_price, side)
        inputs["trade_recent_2chunk_bps"] = _signed_bps(recent_start, close_price, side)
        inputs["trade_present_score"] = _present_trade_score(status, inputs)
        inputs["trade_score_band"] = _trade_score_band(int(inputs["trade_present_score"]))

    def _apply_pressure_watch(self):
        """Apply dipole-derived pressure watch fields to current statuses.

        The status object is the right production home because this is a
        current-market read, not necessarily a signal event. Cross-venue
        promotion runs here after all venues have polled.
        """
        for key, status in self.current_status.items():
            inputs = self._pressure_inputs.get(key)
            if not inputs:
                continue
            watch = _pressure_watch_from_features(
                regime=status.regime,
                mean_dipole=float(inputs.get("mean_dipole") or 0.0),
                volume_zscore=float(inputs.get("volume_zscore") or 0.0),
                dipole_acl1=float(inputs.get("dipole_acl1") or 0.0),
                prev_mean_dipole=inputs.get("prev_mean_dipole"),
            )
            _apply_pressure_fields(status, watch)

        by_asset_dir: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for (asset, venue), status in self.current_status.items():
            if not status.pressure_watch_direction:
                continue
            if status.pressure_watch_priority <= 0:
                continue
            by_asset_dir.setdefault((asset, status.pressure_watch_direction), []).append((asset, venue))

        for (_asset, direction), keys in by_asset_dir.items():
            if len(keys) < 2:
                continue
            venues = sorted({venue for _, venue in keys})
            reason = f"Same-direction pressure on {len(venues)} venues: {', '.join(venues)}"
            for key in keys:
                status = self.current_status.get(key)
                if status is None:
                    continue
                if status.pressure_watch_state != "confirmed":
                    status.pressure_watch_state = "high_priority"
                    status.pressure_watch_label = _pressure_label(direction, "high_priority")
                    status.pressure_watch_priority = max(status.pressure_watch_priority, 3)
                    if not status.pressure_watch_intensity:
                        status.pressure_watch_intensity = "moderate"
                if reason not in status.pressure_watch_reasons:
                    status.pressure_watch_reasons.append(reason)

        for key, status in self.current_status.items():
            inputs = self._pressure_inputs.get(key)
            if inputs:
                self._apply_present_trade_context(key, status, inputs)
                _apply_trade_option_fields(
                    status, _trade_option_from_status(status, inputs))
                _apply_high_conviction_ticket(status, inputs)

    async def _emit_high_priority_pressure_watch_alerts(self):
        """Emit a guarded drift_alert for cross-venue pressure watches.

        Weak and single-venue watches stay quiet. This alert is for the
        "something is forming across venues" scenario and is deduped by
        asset/direction/current chunk ids.
        """
        by_asset_dir: dict[tuple[str, str], list[tuple[tuple[str, str], RegimeStatus]]] = {}
        for key, status in self.current_status.items():
            if status.pressure_watch_state != "high_priority":
                continue
            if status.pressure_watch_priority < 3:
                continue
            by_asset_dir.setdefault(
                (status.asset, status.pressure_watch_direction),
                [],
            ).append((key, status))

        for (asset, direction), rows in by_asset_dir.items():
            if len(rows) < 2:
                continue
            chunk_ids = tuple(sorted(
                str((self._pressure_inputs.get(key) or {}).get("chunk_id") or "")
                for key, _status in rows
            ))
            venues = tuple(sorted(status.venue for _key, status in rows))
            alert_key = (asset, direction, venues, chunk_ids)
            if alert_key in self._pressure_watch_alerted:
                continue
            self._pressure_watch_alerted.add(alert_key)
            if len(self._pressure_watch_alerted) > 1000:
                for k in list(self._pressure_watch_alerted)[:200]:
                    self._pressure_watch_alerted.discard(k)

            side = "buy" if direction == "buy" else "sell"
            labels = sorted({status.pressure_watch_label for _key, status in rows if status.pressure_watch_label})
            reasons = []
            for _key, status in rows:
                reasons.extend(status.pressure_watch_reasons)
            summary = (
                f"{asset} {side} pressure is forming across "
                f"{len(venues)} venues: {', '.join(venues)}"
            )
            await self._emit_drift_alert({
                "type": "pressure_watch_high_priority",
                "asset": asset,
                "venues": list(venues),
                "direction": direction,
                "label": labels[0] if labels else f"{side.title()} pressure across venues",
                "summary": summary,
                "reasons": list(dict.fromkeys(reasons))[:4],
                "priority": 3,
                "ts_utc": time.time(),
                "timestamp_utc": time.time(),
            })

    async def tape_data(self, asset: str, venue: str, n_seconds: int = 60) -> dict:
        """1-second resolution tape feed for the click-to-trade UI's flash
        animation. Returns the last N seconds of raw bin records so the
        frontend can detect each individual aggressor-side hit."""
        path = next((p for a, v, p in DATA_SOURCES if a == asset and v == venue), None)
        if not path:
            return {"error": "no such (asset, venue)"}
        if not os.path.exists(path):
            return {"error": "no data"}
        try:
            with open(path) as f:
                sec_bins = {float(k): v for k, v in json.load(f).items()}
        except Exception as e:
            return {"error": str(e)}
        if not sec_bins:
            return {"asset": asset, "venue": venue, "data": []}
        keys = sorted(sec_bins.keys())
        cutoff = keys[-1] - n_seconds
        out = []
        for k in keys:
            if k < cutoff:
                continue
            b = sec_bins[k]
            out.append({
                "ts": k,
                "buy": b.get("buy", 0.0),
                "sell": b.get("sell", 0.0),
                "n_trades": b.get("n_trades", 0),
                "bid": b.get("bid", 0.0),
                "ask": b.get("ask", 0.0),
                "last_aggressor": b.get("last_aggressor", ""),
                "mid": b.get("mid", 0.0),
            })
        return {"asset": asset, "venue": venue, "data": out}

    async def chart_data(self, asset: str, venue: str, n_minutes: int = 240) -> dict:
        path = next((p for a, v, p in DATA_SOURCES if a == asset and v == venue), None)
        if not path:
            return {"error": "no such (asset, venue)"}
        bars = self._bars_from_bins(path)
        if not bars:
            return {"error": "no data"}
        bars = bars[-n_minutes:]
        return {
            "asset": asset, "venue": venue,
            "n_points": len(bars),
            "data": [
                {"ts": b.ts, "price": b.close,
                 "bid": b.bid, "ask": b.ask,
                 "buy_volume": b.buy_vol, "sell_volume": b.sell_vol,
                 "n_trades": b.n_trades,
                 "last_aggressor": b.last_aggressor,
                 "high": b.high, "low": b.low}
                for b in bars
            ],
        }


store = SignalStore()


# ---------------------------------------------------------------------------
# Background polling task
# ---------------------------------------------------------------------------

async def _polling_loop():
    await asyncio.sleep(POLL_INTERVAL_S)
    while True:
        await store.poll_all()
        write_frontend_live_preload()
        await store.resolve_pending_outcomes(
            hold_minutes=30, abandon_after_minutes=120, fee_bps_round_trip=50.0,
        )
        await asyncio.sleep(POLL_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_polling_loop())
    print("[api_server] polling task started", flush=True)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="markets-watch", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten before prod
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*", "Authorization"],
)

# /api/health stays unauthenticated for liveness probes
@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "mode": "live" if LIVE_MODE else "historical",
        "live_data_dir": LIVE_DATA_DIR if LIVE_MODE else "",
        "tracked_sources": [{"asset": a, "venue": v, "has_data": (a, v) in store.current_status}
                             for a, v, _ in DATA_SOURCES],
        "sources": _source_freshness(),
        "n_recent_signals": len(store.recent_signals),
    }


@app.get("/api/live-sources", dependencies=[Depends(verify_token)])
async def live_sources():
    return {
        "mode": "live" if LIVE_MODE else "historical",
        "live": LIVE_MODE,
        "sources": _source_freshness(),
        "as_of_utc": time.time(),
    }


@app.get("/api/status", dependencies=[Depends(verify_token)])
async def status():
    return market_reads_payload()


def market_reads_payload() -> dict:
    return {
        "statuses": [asdict(s) for s in store.current_status.values()],
        "mode": "live" if LIVE_MODE else "historical",
        "sources": _source_freshness(),
        "tapes": _preload_tapes(),
        "as_of_utc": time.time(),
    }


def _preload_tapes(n_seconds: int = 90) -> dict[str, Any]:
    tapes: dict[str, Any] = {}
    for asset, venue, path in DATA_SOURCES:
        key = f"{asset}/{venue}".lower()
        if not os.path.exists(path):
            tapes[key] = {"asset": asset, "venue": venue, "data": []}
            continue
        try:
            with open(path, encoding="utf-8") as f:
                sec_bins = {float(k): v for k, v in json.load(f).items()}
        except Exception:
            tapes[key] = {"asset": asset, "venue": venue, "data": []}
            continue
        if not sec_bins:
            tapes[key] = {"asset": asset, "venue": venue, "data": []}
            continue
        keys = sorted(sec_bins.keys())
        cutoff = keys[-1] - n_seconds
        data = []
        for k in keys:
            if k < cutoff:
                continue
            b = sec_bins[k]
            data.append({
                "ts": k,
                "buy": b.get("buy", 0.0),
                "sell": b.get("sell", 0.0),
                "n_trades": b.get("n_trades", 0),
                "bid": b.get("bid", 0.0),
                "ask": b.get("ask", 0.0),
                "last_aggressor": b.get("last_aggressor", ""),
                "mid": b.get("mid", 0.0),
            })
        tapes[key] = {"asset": asset, "venue": venue, "data": data}
    return tapes


def write_frontend_live_preload() -> None:
    """Write current market reads as static JS for demo browsers."""
    payload = json.dumps(market_reads_payload(), separators=(",", ":"))
    content = f"window.__MW_LIVE__={payload};\n"
    for path in (
        os.path.join(REPO_ROOT, "frontend", "public", "live-preload.js"),
        os.path.join(REPO_ROOT, "frontend", "dist", "live-preload.js"),
    ):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, path)
        except Exception as e:
            print(f"[live-preload] write error for {path}: {e}", flush=True)


@app.get("/api/market-reads", dependencies=[Depends(verify_token)])
async def market_reads():
    return market_reads_payload()


@app.get("/api/market-reads.mjs", dependencies=[Depends(verify_token)])
async def market_reads_module():
    payload = json.dumps(market_reads_payload())
    return Response(
        content=f"export default {payload};\n",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/signals", dependencies=[Depends(verify_token)])
async def signals(limit: int = 50):
    sigs = list(store.recent_signals)[-limit:]
    sigs.reverse()  # newest first
    return {"signals": [asdict(s) for s in sigs]}


@app.get("/api/signal/{signal_id}", dependencies=[Depends(verify_token)])
async def signal_detail(signal_id: str):
    sig = store.signal_index.get(signal_id)
    if not sig:
        raise HTTPException(404, "signal not found")
    chart = await store.chart_data(sig.asset, sig.venue, n_minutes=120)
    return {"signal": asdict(sig), "chart": chart}


@app.get("/api/chart/{asset}/{venue}", dependencies=[Depends(verify_token)])
async def chart(asset: str, venue: str, n_minutes: int = 240):
    return await store.chart_data(asset, venue, n_minutes=n_minutes)


@app.get("/api/tape/{asset}/{venue}", dependencies=[Depends(verify_token)])
async def tape(asset: str, venue: str, n_seconds: int = 60):
    """1-second resolution tape feed. UI polls at ~1Hz and flashes the
    bid/ask cell on each new sec-bin with activity on that side."""
    return await store.tape_data(asset, venue, n_seconds=n_seconds)


class AutoTradeSettingsBody(BaseModel):
    enabled: bool = False
    practice: bool = True
    tolerance: str = "balanced"
    apply_preset: bool = False
    profiles: list[str] = ["early_probe", "confirmed_follow"]
    min_readiness: int = 65
    max_open_trades: int = 3
    base_notional_usd: float = 1000.0


class MockTradeSettingsBody(BaseModel):
    enabled: bool = False
    initial_bank_usd: float = 10000.0
    tier_high_bank_threshold_usd: float = 20000.0
    tier_high_exposure_cap_usd: float = 1000000.0
    tier_mid_bank_threshold_usd: float = 10000.0
    tier_mid_exposure_pct: float = 1.00
    tier_low_bank_threshold_usd: float = 5000.0
    tier_low_exposure_cap_usd: float = 1000000.0
    min_trade_notional_usd: float = 25.0
    scenarios: list[dict[str, Any]] = []


@app.get("/api/auto-trade-settings", dependencies=[Depends(verify_token)])
async def get_auto_trade_settings():
    return _load_auto_trade_settings()


@app.post("/api/auto-trade-settings", dependencies=[Depends(verify_token)])
async def post_auto_trade_settings(body: AutoTradeSettingsBody):
    settings = {
        "enabled": body.enabled,
        "practice": body.practice,
        "tolerance": body.tolerance,
        "apply_preset": body.apply_preset,
        "profiles": body.profiles,
        "min_readiness": max(0, min(100, int(body.min_readiness))),
        "max_open_trades": max(0, min(25, int(body.max_open_trades))),
        "base_notional_usd": max(1.0, float(body.base_notional_usd)),
    }
    return _save_auto_trade_settings(settings)


@app.get("/api/mock-trade-settings", dependencies=[Depends(verify_token)])
async def get_mock_trade_settings():
    return _load_mock_trade_settings()


@app.post("/api/mock-trade-settings", dependencies=[Depends(verify_token)])
async def post_mock_trade_settings(body: MockTradeSettingsBody):
    settings = {
        "enabled": body.enabled,
        "initial_bank_usd": max(0.0, float(body.initial_bank_usd)),
        "tier_high_bank_threshold_usd": max(0.0, float(body.tier_high_bank_threshold_usd)),
        "tier_high_exposure_cap_usd": max(0.0, float(body.tier_high_exposure_cap_usd)),
        "tier_mid_bank_threshold_usd": max(0.0, float(body.tier_mid_bank_threshold_usd)),
        "tier_mid_exposure_pct": max(0.0, min(1.0, float(body.tier_mid_exposure_pct))),
        "tier_low_bank_threshold_usd": max(0.0, float(body.tier_low_bank_threshold_usd)),
        "tier_low_exposure_cap_usd": max(0.0, float(body.tier_low_exposure_cap_usd)),
        "min_trade_notional_usd": max(1.0, float(body.min_trade_notional_usd)),
        "scenarios": body.scenarios or _default_mock_trade_settings()["scenarios"],
    }
    return _save_mock_trade_settings(settings)


@app.get("/api/mock-trade-bankroll", dependencies=[Depends(verify_token)])
async def get_mock_trade_bankroll():
    return _mock_trade_bankroll()


@app.get("/api/stats", dependencies=[Depends(verify_token)])
async def stats(window_hours: int = 24):
    """Aggregate stats over recent signals: counts, distribution, top sources,
    plus realized hit rate and P&L when outcomes are available."""
    from collections import Counter, defaultdict
    cutoff = time.time() - window_hours * 3600
    sigs = [s for s in store.recent_signals if s.timestamp_utc >= cutoff]
    by_regime: Counter[str] = Counter(s.regime for s in sigs)
    by_asset: Counter[str] = Counter(s.asset for s in sigs)
    by_venue: Counter[str] = Counter(s.venue for s in sigs)
    by_source: Counter[str] = Counter(f"{s.asset}-{s.venue}" for s in sigs)
    by_pressure_state: Counter[str] = Counter(
        s.pressure_watch_state or "none" for s in sigs)
    by_pressure_label: Counter[str] = Counter(
        s.pressure_watch_label for s in sigs if s.pressure_watch_label)
    confirmed = sum(1 for s in sigs if s.cross_venue_multiplier > 1.0)
    disagreed = sum(1 for s in sigs if s.cross_venue_multiplier < 1.0)
    avg_conf = (sum(s.adjusted_confidence for s in sigs) / len(sigs)) if sigs else 0.0

    # Outcome stats
    resolved = [s for s in sigs if s.outcome_status == "resolved"]
    pending = sum(1 for s in sigs if s.outcome_status == "pending")
    abandoned = sum(1 for s in sigs if s.outcome_status == "abandoned")
    n_resolved = len(resolved)
    wins = sum(1 for s in resolved if s.outcome_realized_bps > 0)
    win_rate = (wins / n_resolved) if n_resolved > 0 else None
    avg_realized_bps = (sum(s.outcome_realized_bps for s in resolved) / n_resolved) if n_resolved > 0 else None
    total_realized_bps = sum(s.outcome_realized_bps for s in resolved) if resolved else 0.0
    # Per-source realized P&L
    by_source_pnl: dict[str, dict] = {}
    for s in resolved:
        key = f"{s.asset}-{s.venue}"
        d = by_source_pnl.setdefault(key, {"n": 0, "wins": 0, "total_bps": 0.0})
        d["n"] += 1
        if s.outcome_realized_bps > 0:
            d["wins"] += 1
        d["total_bps"] += s.outcome_realized_bps

    pressure_outcomes: dict[str, dict] = {}
    for s in resolved:
        key = s.pressure_watch_state or "none"
        d = pressure_outcomes.setdefault(
            key, {"n": 0, "wins": 0, "total_bps": 0.0})
        d["n"] += 1
        if s.outcome_realized_bps > 0:
            d["wins"] += 1
        d["total_bps"] += s.outcome_realized_bps
    for d in pressure_outcomes.values():
        n = int(d["n"] or 0)
        d["win_rate"] = round((d["wins"] / n), 3) if n else None
        d["avg_bps"] = round((d["total_bps"] / n), 2) if n else None
        d["total_bps"] = round(float(d["total_bps"]), 2)

    by_source_series: dict[str, list[dict]] = defaultdict(list)
    for s in sigs:
        by_source_series[f"{s.asset}-{s.venue}"].append({
            "ts": s.timestamp_utc, "regime": s.regime, "conf": s.adjusted_confidence,
        })

    return {
        "window_hours": window_hours,
        "n_signals": len(sigs),
        "by_regime": dict(by_regime.most_common()),
        "by_asset": dict(by_asset),
        "by_venue": dict(by_venue),
        "by_source": dict(by_source.most_common()),
        "pressure_watch": {
            "by_state": dict(by_pressure_state.most_common()),
            "by_label": dict(by_pressure_label.most_common()),
            "outcomes_by_state": pressure_outcomes,
        },
        "cross_venue_confirmed": confirmed,
        "cross_venue_disagreed": disagreed,
        "avg_adjusted_confidence": round(avg_conf, 3),
        "outcomes": {
            "resolved": n_resolved,
            "pending": pending,
            "abandoned": abandoned,
            "win_rate": round(win_rate, 3) if win_rate is not None else None,
            "avg_realized_bps": round(avg_realized_bps, 2) if avg_realized_bps is not None else None,
            "total_realized_bps": round(total_realized_bps, 2),
            "by_source_pnl": by_source_pnl,
        },
        "as_of_utc": time.time(),
        "by_source_series": dict(by_source_series),
    }


@app.get("/api/regime_history/{asset}/{venue}", dependencies=[Depends(verify_token)])
async def regime_history(asset: str, venue: str, n_points: int = 60):
    """Return last N regime classifications (one per chunk) for an (asset, venue).

    Used by the frontend's regime-timeline view.
    """
    path = next((p for a, v, p in DATA_SOURCES if a == asset and v == venue), None)
    if not path:
        raise HTTPException(404, "no such (asset, venue)")
    bars = store._bars_from_bins(path)
    if not bars:
        return {"asset": asset, "venue": venue, "points": []}
    chunker = MarketChunker(max_window_size=CHUNK_MAX_SIZE,
                              stride=CHUNK_MAX_SIZE // 2,
                              min_segment=CHUNK_MIN_SEGMENT, mode="hybrid")
    encoder = MarketChunkEncoder(d_enc=64)
    chunks = chunker.chunk(f"{venue}-{asset}", bars)
    if not chunks:
        return {"asset": asset, "venue": venue, "points": []}
    bv = _vpin_bucket_volume_for(asset, venue)
    if bv <= 0:
        bv = _vpin_bucket_volume_from_corpus(chunks)
    feats = [encoder._extract(c, vpin_bucket_volume=bv) for c in chunks]
    base = baselines_from_corpus(feats)
    vpin_elev, vpin_diff = _vpin_thresholds_for(asset, venue)
    results = [classify_regime(f, base,
                                 vpin_elevated=vpin_elev,
                                 vpin_diffuse=vpin_diff) for f in feats]
    points = []
    start_i = max(0, len(chunks) - n_points)
    for i in range(start_i, len(chunks)):
        c = chunks[i]
        f = feats[i]
        r = results[i]
        prev_f = feats[i - 1] if i > 0 else None
        pressure = _pressure_watch_from_features(
            regime=r.regime.value,
            mean_dipole=float(f.mean_dipole),
            volume_zscore=float(f.volume_zscore),
            dipole_acl1=float(f.dipole_autocorr_lag1),
            prev_mean_dipole=(
                float(prev_f.mean_dipole) if prev_f is not None else None
            ),
        )
        points.append({
            "chunk_idx": c.window_start,
            "regime": r.regime.value,
            "mean_dipole": float(f.mean_dipole),
            "realized_vol": float(f.realized_vol),
            "confidence": r.confidence,
            "pressure_watch_state": pressure.get("pressure_watch_state", ""),
            "pressure_watch_label": pressure.get("pressure_watch_label", ""),
            "pressure_watch_direction": pressure.get("pressure_watch_direction", ""),
            "pressure_watch_priority": pressure.get("pressure_watch_priority", 0),
            "ts_start": float(bars[c.window_start].ts) if c.window_start < len(bars) else 0,
            "ts_end": float(bars[min(c.window_end - 1, len(bars) - 1)].ts) if bars else 0,
        })
    return {"asset": asset, "venue": venue, "n_chunks_total": len(chunks), "points": points}


# ---------------------------------------------------------------------------
# Web Push subscription endpoints
# ---------------------------------------------------------------------------

class PushSubscribeBody(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str = ""


@app.get("/api/push/vapid-public-key")
async def push_vapid_public_key():
    """Frontend fetches this on first run to call subscribe with the right VAPID key."""
    return {"public_key": VAPID_PUBLIC, "configured": bool(VAPID_PUBLIC)}


@app.post("/api/push/subscribe", dependencies=[Depends(verify_token)])
async def push_subscribe(body: PushSubscribeBody):
    sub = PushSubscription(
        endpoint=body.endpoint, keys_p256dh=body.p256dh,
        keys_auth=body.auth, user_agent=body.user_agent,
    )
    n = add_sub(sub)
    return {"ok": True, "n_subs": n}


@app.post("/api/push/unsubscribe", dependencies=[Depends(verify_token)])
async def push_unsubscribe(body: PushSubscribeBody):
    removed = remove_sub(body.endpoint)
    return {"ok": True, "removed": removed}


# ---------------------------------------------------------------------------
# Manual-trade intent: click-to-trade audit log
# ---------------------------------------------------------------------------

class ManualTradeIntentBody(BaseModel):
    asset: str
    venue: str
    side: str            # "buy" | "sell"
    price: float
    qty: float
    note: str = ""
    practice: bool = True   # default ON for safety; set false from UI toggle for live


_MANUAL_INTENT_PATH = os.path.join(REPO_ROOT, "backend_manual_trade_intents.jsonl")
_PRACTICE_TRADE_PATH = os.path.join(REPO_ROOT, "backend_practice_trades.jsonl")
_PRACTICE_FEE_BPS = 25.0    # symmetric simulated fee on practice fills


def _persist_practice_trade(trade: dict) -> None:
    try:
        with open(_PRACTICE_TRADE_PATH, "a") as f:
            f.write(json.dumps(trade) + "\n")
        record_trade_attempt_open_json(
            trade,
            source="backend_practice_trade_open",
            run_id=str(trade.get("cell_id") or trade.get("intent_id") or "backend_practice_trade_open"),
        )
    except Exception as e:
        print(f"[practice] persist error: {e}", flush=True)


def _rewrite_practice_trades(trades: list[dict]) -> None:
    try:
        tmp = _PRACTICE_TRADE_PATH + ".tmp"
        with open(tmp, "w") as f:
            for t in trades:
                f.write(json.dumps(t) + "\n")
        os.replace(tmp, _PRACTICE_TRADE_PATH)
    except Exception as e:
        print(f"[practice] rewrite error: {e}", flush=True)


def _load_practice_trades() -> list[dict]:
    if not os.path.exists(_PRACTICE_TRADE_PATH):
        return []
    out = []
    with open(_PRACTICE_TRADE_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out


def _load_live_hindsight_audit(limit: int = 50) -> dict:
    if not os.path.exists(_LIVE_HINDSIGHT_AUDIT_PATH):
        return {"available": False, "summary": {}, "top_missed_entries": [], "top_exit_leaks": []}
    try:
        with open(_LIVE_HINDSIGHT_AUDIT_PATH, encoding="utf-8") as f:
            audit = json.load(f)
    except Exception as e:
        return {"available": False, "error": str(e), "summary": {}, "top_missed_entries": [], "top_exit_leaks": []}
    counts = audit.get("counts") or {}
    pnl = audit.get("pnl") or {}
    pace = audit.get("pace") or {}
    return {
        "available": True,
        "created_at": audit.get("created_at"),
        "summary": {
            "oracle_winner_rows_after_fees": counts.get("oracle_winner_rows_after_fees", 0),
            "missed_entry_rows": counts.get("missed_entry_rows", 0),
            "exit_missed_or_fee_leak_rows": counts.get("exit_missed_or_fee_leak_rows", 0),
            "captured_net_win_rows": counts.get("captured_net_win_rows", 0),
            "closed_actual_realized_pnl_usd": pnl.get("closed_actual_realized_pnl_usd", 0.0),
            "oracle_winner_net_pnl_usd": pnl.get("oracle_winner_net_pnl_usd", 0.0),
            "missed_entry_oracle_net_pnl_usd": pnl.get("missed_entry_oracle_net_pnl_usd", 0.0),
            "oracle_incremental_vs_closed_actual_usd": pnl.get("oracle_incremental_vs_closed_actual_usd", 0.0),
            "oracle_winner_weekly_pace_usd": pace.get("oracle_winner_weekly_pace_usd"),
            "closed_actual_weekly_pace_usd": pace.get("closed_actual_weekly_pace_usd"),
        },
        "by_blocker": (audit.get("by_blocker") or [])[:limit],
        "by_context": (audit.get("by_context") or [])[:limit],
        "top_missed_entries": (audit.get("top_missed_entries") or [])[:limit],
        "top_exit_leaks": (audit.get("top_exit_leaks") or [])[:limit],
    }


def _mock_trade_exposure_cap(settings: dict[str, Any], equity_usd: float) -> float:
    equity_usd = max(0.0, float(equity_usd))
    return equity_usd


def _mock_trade_bankroll(settings: dict[str, Any] | None = None,
                         trades: list[dict] | None = None,
                         scenario_id: str | None = None) -> dict[str, Any]:
    settings = settings or _load_mock_trade_settings()
    trades = trades if trades is not None else _load_practice_trades()
    mock_trades = [t for t in trades if t.get("source") == "mock_scenario"]
    if scenario_id:
        mock_trades = [
            t for t in mock_trades
            if str(t.get("mock_scenario_id") or "") == str(scenario_id)
        ]
    realized = sum(
        float(t.get("realized_pnl_usd") or 0.0)
        for t in mock_trades
        if t.get("status") == "closed"
    )
    initial_bank = float(settings.get("initial_bank_usd") or 10000.0)
    equity = max(0.0, initial_bank + realized)
    bank = equity
    open_trades = [t for t in mock_trades if t.get("status") == "open"]
    open_exposure = sum(float(t.get("notional") or 0.0) for t in open_trades)
    exposure_cap = _mock_trade_exposure_cap(settings, equity)
    remaining = max(0.0, min(equity, exposure_cap - open_exposure))
    by_scenario: dict[str, dict[str, Any]] = {}
    for t in mock_trades:
        sid = str(t.get("mock_scenario_id") or "unknown")
        row = by_scenario.setdefault(
            sid, {"n": 0, "open": 0, "closed": 0, "wins": 0, "realized_pnl_usd": 0.0})
        row["n"] += 1
        if t.get("status") == "open":
            row["open"] += 1
        elif t.get("status") == "closed":
            row["closed"] += 1
            pnl = float(t.get("realized_pnl_usd") or 0.0)
            row["realized_pnl_usd"] += pnl
            if pnl > 0:
                row["wins"] += 1
    for row in by_scenario.values():
        closed = int(row["closed"] or 0)
        row["win_rate"] = round(row["wins"] / closed, 3) if closed else None
        row["realized_pnl_usd"] = round(float(row["realized_pnl_usd"]), 4)
    return {
        "initial_bank_usd": float(initial_bank),
        "equity_usd": float(equity),
        "bank_usd": float(bank),
        "realized_pnl_usd": float(realized),
        "open_exposure_usd": float(open_exposure),
        "exposure_cap_usd": float(exposure_cap),
        "remaining_exposure_capacity_usd": float(remaining),
        "n_open": len(open_trades),
        "n_total": len(mock_trades),
        "by_scenario": by_scenario,
        "scenario_id": scenario_id or "",
        "rule": (
            "learning trades use the historical full-bank hypothetical model: "
            "notional = initial_bank_usd * notional_pct_bank, open exposure is "
            "reported but does not suppress later evidence trades"
        ),
    }


def _practice_trade_unrealized_bps(trade: dict) -> float:
    bid, ask, mid = _current_quote(str(trade.get("asset") or ""), str(trade.get("venue") or ""))
    exit_price = bid if trade.get("side") == "buy" else ask
    if exit_price <= 0:
        exit_price = mid
    fill = float(trade.get("fill_price") or 0.0)
    if fill <= 0 or exit_price <= 0:
        return 0.0
    sign = 1 if trade.get("side") == "buy" else -1
    return sign * math.log(max(exit_price, 1e-12) / max(fill, 1e-12)) * 10000.0


def _practice_exit_price_for_trade(trade: dict, bid: float, ask: float, mid: float) -> float:
    exit_price = bid if trade.get("side") == "buy" else ask
    if exit_price <= 0:
        exit_price = mid
    return float(exit_price or 0.0)


def _append_practice_exit_leg(
    trade: dict,
    *,
    leg_type: str,
    reason: str,
    qty: float,
    price: float,
    ts: float,
    gross: float,
    entry_fee_alloc: float,
    exit_fee: float,
    realized: float,
) -> None:
    trade.setdefault("exit_legs", []).append({
        "leg_type": leg_type,
        "reason": reason,
        "qty": round(float(qty), 12),
        "price": round(float(price), 8),
        "ts_utc": float(ts),
        "gross_pnl_usd": round(float(gross), 8),
        "entry_fee_alloc_usd": round(float(entry_fee_alloc), 8),
        "exit_fee_usd": round(float(exit_fee), 8),
        "leg_pnl_usd": round(float(realized), 8),
    })


def _refresh_practice_scaleout_summary(trade: dict) -> None:
    qty_initial = max(float(trade.get("qty_initial") or trade.get("qty") or 0.0), 1e-12)
    legs = trade.get("exit_legs") or []
    scale_legs = [leg for leg in legs if leg.get("leg_type") == "scale_out"]
    scale_qty = sum(float(leg.get("qty") or 0.0) for leg in scale_legs)
    trade["scale_out_count"] = len(scale_legs)
    trade["scale_out_fraction_realized"] = round(max(0.0, min(1.0, scale_qty / qty_initial)), 6)
    if scale_legs and not trade.get("scale_out_tp1_bps"):
        decision = trade.get("exit_decision") or trade.get("last_exit_decision") or {}
        trade["scale_out_tp1_bps"] = float(decision.get("net_unrealized_bps") or 0.0)


def _realize_practice_exit_leg(
    trade: dict,
    bid: float,
    ask: float,
    mid: float,
    ts: float,
    reason: str,
    leg_type: str,
    qty: float,
) -> bool:
    exit_price = _practice_exit_price_for_trade(trade, bid, ask, mid)
    if exit_price <= 0:
        return False
    fill = float(trade.get("fill_price") or 0.0)
    qty = max(0.0, float(qty))
    qty_initial = max(float(trade.get("qty_initial") or trade.get("qty") or 0.0), 1e-12)
    if fill <= 0 or qty <= 0:
        return False
    signed = 1 if trade.get("side") == "buy" else -1
    gross = signed * (exit_price - fill) * qty
    fee_bps = float(trade.get("fee_bps") or _PRACTICE_FEE_BPS)
    exit_fee = exit_price * qty * (fee_bps / 10000.0)
    entry_fee_total = float(trade.get("entry_fees_usd") or 0.0)
    if entry_fee_total <= 0:
        entry_fee_total = float(trade.get("notional") or 0.0) * (fee_bps / 10000.0)
    entry_fee_alloc = entry_fee_total * (qty / qty_initial)
    realized = gross - entry_fee_alloc - exit_fee
    trade["gross_pnl_usd"] = float(trade.get("gross_pnl_usd") or 0.0) + float(gross)
    trade["realized_pnl_usd"] = float(trade.get("realized_pnl_usd") or 0.0) + float(realized)
    trade["fees_usd"] = float(trade.get("fees_usd") or 0.0) + float(exit_fee)
    _append_practice_exit_leg(
        trade,
        leg_type=leg_type,
        reason=reason,
        qty=qty,
        price=exit_price,
        ts=ts,
        gross=gross,
        entry_fee_alloc=entry_fee_alloc,
        exit_fee=exit_fee,
        realized=realized,
    )
    return True


def _scale_out_practice_trade(
    trade: dict,
    bid: float,
    ask: float,
    mid: float,
    ts: float,
    reason: str,
    fraction: float,
) -> bool:
    if trade.get("status") != "open":
        return False
    qty_open = float(trade.get("qty_open") or trade.get("qty") or 0.0)
    leg_qty = qty_open * max(0.0, min(1.0, float(fraction)))
    if leg_qty <= 0 or leg_qty >= qty_open:
        return False
    if not _realize_practice_exit_leg(trade, bid, ask, mid, ts, reason, "scale_out", leg_qty):
        return False
    trade["qty_open"] = max(0.0, qty_open - leg_qty)
    _refresh_practice_scaleout_summary(trade)
    return True


def _apply_practice_exit_decision_metadata(
    trade: dict,
    decision: trade_exit_strategy.ExitDecision,
) -> None:
    metadata = decision.metadata or {}
    cfg = metadata.get("exit_config") or {}
    if cfg:
        trade["exit_config_level"] = str(cfg.get("config_level") or "")
        trade["exit_config_key"] = str(cfg.get("config_key") or "")
        if cfg.get("hold_minutes") is not None:
            trade["hold_minutes"] = float(cfg.get("hold_minutes") or trade.get("hold_minutes") or 0.0)
        trade["exit_tp1_bps"] = float(cfg.get("tp1_bps") or trade.get("exit_tp1_bps") or 0.0)
        trade["exit_scale_out_fraction"] = float(cfg.get("scale_out_fraction") or trade.get("exit_scale_out_fraction") or 0.0)
        trade["exit_runner_trail_bps"] = float(cfg.get("trail_bps") or trade.get("exit_runner_trail_bps") or 0.0)
        trade["exit_max_hold_minutes"] = float(cfg.get("max_hold_minutes") or trade.get("exit_max_hold_minutes") or 0.0)
        trade["score_exit_min_profit_bps"] = float(cfg.get("min_profit_bps_for_score_exit") or trade.get("score_exit_min_profit_bps") or 0.0)
        trade["score_exit_min_hold_minutes"] = float(cfg.get("min_hold_minutes") or trade.get("score_exit_min_hold_minutes") or 0.0)
    if metadata.get("next_exit_stage"):
        trade["exit_stage"] = str(metadata["next_exit_stage"])
    if metadata.get("mark_under_gate_trim_done"):
        trade["exit_under_gate_trim_done"] = True
    if metadata.get("runner_anchor_net_bps") is not None:
        trade["exit_runner_anchor_net_bps"] = float(metadata["runner_anchor_net_bps"])
    if metadata.get("runner_stop_net_bps") is not None:
        trade["exit_runner_stop_net_bps"] = float(metadata["runner_stop_net_bps"])
    if metadata.get("trail_bps") is not None:
        trade["exit_active_trail_bps"] = float(metadata["trail_bps"])
    if metadata.get("tighten_runner_stop"):
        trade.setdefault("exit_stop_tighten_events", []).append({
            "reason": str(metadata.get("tighten_reason") or decision.reason or ""),
            "elapsed_min": decision.elapsed_min,
            "net_unrealized_bps": decision.net_unrealized_bps,
            "runner_stop_net_bps": float(metadata.get("runner_stop_net_bps") or 0.0),
            "trail_bps": float(metadata.get("trail_bps") or 0.0),
            "aggressive": bool(metadata.get("aggressive")),
        })


def _stamp_practice_exit_profile(trade: dict, scenario: dict) -> None:
    profile, cfg = trade_exit_strategy.exit_profile_for_trade(trade, scenario)
    trade["exit_strategy_id"] = profile.profile_id
    trade["exit_strategy_label"] = profile.label
    trade["exit_tp1_bps"] = float(profile.tp1_bps)
    trade["exit_scale_out_fraction"] = float(profile.scale_out_fraction)
    trade["exit_runner_trail_bps"] = float(profile.runner_trail_bps)
    trade["exit_max_hold_minutes"] = float(profile.max_hold_minutes)
    trade["score_exit_min_profit_bps"] = float(profile.score_exit_min_profit_bps)
    trade["score_exit_min_hold_minutes"] = float(profile.score_exit_min_hold_minutes)
    if cfg:
        trade["exit_config_level"] = str(cfg.get("config_level") or "")
        trade["exit_config_key"] = str(cfg.get("config_key") or "")
        if cfg.get("hold_minutes") is not None:
            trade["hold_minutes"] = float(cfg.get("hold_minutes") or trade.get("hold_minutes") or 0.0)


def _close_practice_trade_at_market(trade: dict, close_reason: str) -> bool:
    bid, ask, mid = _current_quote(str(trade.get("asset") or ""), str(trade.get("venue") or ""))
    before = trade.get("status")
    side = trade.get("side")
    exit_price = _practice_exit_price_for_trade(trade, bid, ask, mid)
    if exit_price <= 0:
        return False
    qty_open = float(trade.get("qty_open") or trade.get("qty") or 0.0)
    if not _realize_practice_exit_leg(
        trade,
        bid,
        ask,
        mid,
        time.time(),
        close_reason,
        "final_exit",
        qty_open,
    ):
        return False
    trade["status"] = "closed"
    trade["exit_price"] = float(exit_price)
    trade["exit_ts_utc"] = time.time()
    trade["qty_open"] = 0.0
    trade["close_reason"] = close_reason
    trade["runner_exit_reason"] = close_reason
    _refresh_practice_scaleout_summary(trade)
    if trade.get("status") != before:
        return True
    return False


def _current_quote(asset: str, venue: str) -> tuple[float, float, float]:
    """Return (bid, ask, mid) from the latest tracked status; falls back
    to the bins file if necessary. Returns (0,0,0) if not available."""
    st = store.current_status.get((asset, venue))
    if st and (st.current_bid or st.current_ask):
        bid = st.current_bid or st.current_price
        ask = st.current_ask or st.current_price
        mid = st.current_price or (bid + ask) / 2
        return bid, ask, mid
    return 0.0, 0.0, 0.0


@app.post("/api/manual-trade-intent", dependencies=[Depends(verify_token)])
async def post_manual_trade_intent(body: ManualTradeIntentBody):
    """Record a click-to-trade intent.

    practice=True (default): simulate the fill against the current
    bid/ask on the central host with a 25 bp symmetric fee, persist to
    the practice trades log, and return the simulated fill. NO real
    exchange call. NO SSE emit (executor doesn't see it). Lets users
    learn the workflow with no money at risk.

    practice=False: persist to the manual-intent audit log and emit on
    the SSE stream so the user's local executor (configured for their
    exchange) can route to their wallet.
    """
    if body.side not in ("buy", "sell"):
        return {"ok": False, "error": "side must be 'buy' or 'sell'"}
    if body.qty <= 0 or body.price <= 0:
        return {"ok": False, "error": "qty and price must be positive"}

    intent_id = str(uuid.uuid4())[:12]
    base = {
        "intent_id": intent_id,
        "asset": body.asset,
        "venue": body.venue,
        "side": body.side,
        "price": body.price,
        "qty": body.qty,
        "notional": body.price * body.qty,
        "note": body.note,
        "ts_utc": time.time(),
        "practice": body.practice,
    }

    if body.practice:
        # Fill against current bid (sell) or ask (buy); fall back to
        # clicked price if no live quote available.
        bid, ask, mid = _current_quote(body.asset, body.venue)
        fill_price = (ask if body.side == "buy" else bid) or body.price
        notional = fill_price * body.qty
        fee_usd = notional * (_PRACTICE_FEE_BPS / 10000.0)
        trade = {
            **base,
            "kind": "practice",
            "status": "open",
            "fill_price": float(fill_price),
            "fees_usd": float(fee_usd),
            "fee_bps": _PRACTICE_FEE_BPS,
            "exit_price": 0.0,
            "exit_ts_utc": 0.0,
            "realized_pnl_usd": 0.0,
        }
        _persist_practice_trade(trade)
        return {"ok": True, **trade}

    # Live (real money) path: persist to audit log + emit on SSE for
    # the user's own executor to handle.
    try:
        with open(_MANUAL_INTENT_PATH, "a") as f:
            f.write(json.dumps(base) + "\n")
    except Exception as e:
        print(f"[manual-intent] persist error: {e}", flush=True)
    await store.event_queue.put({"type": "manual_trade_intent", "data": base})
    return {"ok": True, **base}


@app.get("/api/manual-trade-intents", dependencies=[Depends(verify_token)])
async def get_manual_trade_intents(limit: int = 50):
    """List recent live manual-trade intents (real-money audit feed)."""
    if not os.path.exists(_MANUAL_INTENT_PATH):
        return {"intents": []}
    intents = []
    try:
        with open(_MANUAL_INTENT_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    intents.append(json.loads(line))
    except Exception as e:
        return {"error": str(e), "intents": []}
    intents.reverse()
    return {"intents": intents[:limit]}


# ---------------------------------------------------------------------------
# Drift alerts — refrag_audit.py POSTs detected drift events here, backend
# emits them on the SSE stream so Discord + PWA surface them in real time.
# Backend also emits drift alerts itself when signal-outcome contradiction
# streaks accumulate (see SignalStore.resolve_pending_outcomes).
# ---------------------------------------------------------------------------


class DriftAlertBody(BaseModel):
    type: str            # "direction_flip" | "edge_decay" | "edge_strengthen" | "sample_milestone" | other
    key: str             # "<ASSET>/<VENUE>/<REGIME>"
    summary: str = ""
    # Free-form fields preserved on persistence and forwarded via SSE
    # so the consumer (Discord embed, PWA banner) has full detail.
    extra: dict = {}


class EvolveRequestBody(BaseModel):
    prompt: str
    mode: str = "codebase"
    source: str = "evolve_tab"


def _load_evolve_requests(limit: int = 20) -> list[dict[str, Any]]:
    if not os.path.exists(_EVOLVE_REQUESTS_PATH):
        return []
    requests: list[dict[str, Any]] = []
    try:
        with open(_EVOLVE_REQUESTS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    requests.append(json.loads(line))
    except Exception as e:
        print(f"[evolve-request] load error: {e}", flush=True)
        return []
    requests.reverse()
    return requests[:limit]


@app.get("/api/evolve-requests", dependencies=[Depends(verify_token)])
async def get_evolve_requests(limit: int = 20):
    return {"requests": _load_evolve_requests(max(1, min(limit, 100)))}


@app.post("/api/evolve-request", dependencies=[Depends(verify_token)])
async def post_evolve_request(body: EvolveRequestBody):
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="prompt is too long")
    record = {
        "id": f"EVREQ-{uuid.uuid4().hex[:8].upper()}",
        "ts_utc": time.time(),
        "prompt": prompt,
        "mode": body.mode,
        "source": body.source,
        "status": "new",
    }
    try:
        with open(_EVOLVE_REQUESTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[evolve-request] persist error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="could not save request")
    return {"ok": True, "request": record}


@app.post("/api/drift-alert", dependencies=[Depends(verify_token)])
async def post_drift_alert(body: DriftAlertBody):
    alert = {
        "type": body.type,
        "key": body.key,
        "summary": body.summary,
        **body.extra,
    }
    persisted = await store._emit_drift_alert(alert)
    return {"ok": True, **persisted}


@app.get("/api/drift-alerts", dependencies=[Depends(verify_token)])
async def get_drift_alerts(limit: int = 50):
    """Recent drift alerts (in-memory + persisted). Newest first."""
    alerts = list(store.recent_drift_alerts)[-limit:]
    alerts.reverse()
    return {"alerts": alerts, "n_total": len(store.recent_drift_alerts)}


@app.get("/api/basis-status", dependencies=[Depends(verify_token)])
async def get_basis_status():
    """Per-asset spot-perp basis snapshot: latest bps, z-score, current
    state (normal/hot/cold), and streak counters. Powers a frontend
    badge / Discord pin showing where leverage is currently building."""
    return {"basis": store.basis_monitor.snapshot()}


@app.get("/api/funding-status", dependencies=[Depends(verify_token)])
async def get_funding_status():
    """Per-(asset, venue) funding-rate snapshot: latest rate, bps/8h,
    annualized APR (rate * 3 * 365), current state. Surfaces leverage
    crowdedness that doesn't show up in chunk-level regimes."""
    return {"funding": store.funding_monitor.snapshot()}


@app.get("/api/oi-status", dependencies=[Depends(verify_token)])
async def get_oi_status():
    """Per-(asset, venue) open-interest snapshot: latest oi, latest
    price, Δoi/Δprice over the trailing window, rolling z-score, and
    current state (normal / building_long / building_short /
    unwind_shorts / unwind_longs). Distinguishes trend conviction
    (OI↑ with price) from leverage build-up (OI↑ counter to price)
    and from squeezes / capitulations (OI↓)."""
    return {"oi": store.oi_monitor.snapshot()}


@app.get("/api/cb-premium-status", dependencies=[Depends(verify_token)])
async def get_cb_premium_status():
    """Per-asset Coinbase-premium snapshot: peg-corrected
    (CB_USD - BN_USDT * USDT/USD) in bps, rolling z, current state.
    Sustained positive premium = US-institutional buying pressure;
    sustained negative = US-side selling pressure. Use as a daily-bias
    multiplier on US-hours signals."""
    return {"cb_premium": store.cb_premium_monitor.snapshot()}


@app.get("/api/carry-opportunities", dependencies=[Depends(verify_token)])
async def get_carry_opportunities():
    """Score funding-rate carry / basis-arb opportunities given the
    current funding-monitor snapshot. Returns only entries whose net
    APR (gross funding minus assumed spot lending cost minus amortized
    round-trip fee) clears the opportunity threshold; full list also
    returned under all_evaluated for diagnostics."""
    return evaluate_all_carry(store.funding_monitor.snapshot())


@app.get("/api/edge-tracker", dependencies=[Depends(verify_token)])
async def get_edge_tracker():
    """Per-(asset, venue, regime) multi-horizon edge tags: long-term /
    weekly / daily strength + direction + self_trend (strengthening /
    decaying / flipping / stable). Plus cross-horizon trends and a
    human-readable summary line per cell.

    Cells appear once they have at least one observation in any window;
    new cells will tag NEW until enough samples accumulate.
    """
    cells = store.edge_tracker.all_cell_tags()
    return {
        "n_cells": len(cells),
        "n_total_samples": store.edge_tracker.n_total_samples(),
        "cells": [c.to_dict() for c in cells],
    }


@app.get("/api/cell-controls", dependencies=[Depends(verify_token)])
async def get_cell_controls():
    controls = _fp_load_cell_controls()
    return {
        "n_controls": len(controls),
        "controls": controls,
    }


@app.get("/api/practice-trades", dependencies=[Depends(verify_token)])
async def get_practice_trades(limit: int = 100, source: str = "all"):
    """List practice trades. Auto-marks open positions to current
    market mid on read so the running P&L is fresh.

    source: "all" (default), "manual" (human click-to-trade), or "auto"
    (forward paper-trades opened by candidate-cell predicates).
    """
    trades = _load_practice_trades()
    if source == "manual":
        trades = [t for t in trades if not t.get("auto")]
    elif source == "auto":
        trades = [t for t in trades if t.get("auto")]
    # Mark to market: for any "open" practice trade, compute unrealized
    # P&L against the current mid. (Doesn't persist; just decorates.)
    for t in trades:
        if t.get("status") == "open":
            _, _, mid = _current_quote(t["asset"], t["venue"])
            if mid > 0:
                signed = +1 if t["side"] == "buy" else -1
                t["mark_price"] = mid
                t["unrealized_pnl_usd"] = signed * (mid - t["fill_price"]) * t["qty"] - t["fees_usd"]
    trades.reverse()
    # Aggregate stats
    closed = [t for t in trades if t.get("status") == "closed"]
    n_wins = sum(1 for t in closed if t.get("realized_pnl_usd", 0) > 0)
    total_realized = sum(t.get("realized_pnl_usd", 0) for t in closed)
    # Per-cell aggregates for forward-paper visibility.
    by_cell: dict[str, dict] = {}
    for t in closed:
        cid = t.get("cell_id")
        if not cid:
            continue
        agg = by_cell.setdefault(cid, {"n": 0, "wins": 0, "realized_pnl_usd": 0.0})
        agg["n"] += 1
        if t.get("realized_pnl_usd", 0) > 0:
            agg["wins"] += 1
        agg["realized_pnl_usd"] += float(t.get("realized_pnl_usd", 0.0))
    for cid, agg in by_cell.items():
        agg["win_rate"] = (agg["wins"] / agg["n"]) if agg["n"] else None
        agg["realized_pnl_usd"] = round(agg["realized_pnl_usd"], 4)
    mock_bankroll = _mock_trade_bankroll(trades=trades)
    return {
        "trades": trades[:limit],
        "n_open": sum(1 for t in trades if t.get("status") == "open"),
        "n_closed": len(closed),
        "win_rate": (n_wins / len(closed)) if closed else None,
        "total_realized_pnl_usd": float(total_realized),
        "by_cell": by_cell,
        "mock_bankroll": mock_bankroll,
        "live_hindsight_audit": _load_live_hindsight_audit(limit=min(max(int(limit), 1), 200)),
    }


@app.get("/api/live-hindsight-audit", dependencies=[Depends(verify_token)])
async def get_live_hindsight_audit(limit: int = 100):
    return _load_live_hindsight_audit(limit=min(max(int(limit), 1), 500))


class PracticeCloseBody(BaseModel):
    intent_id: str


@app.post("/api/practice-trade/close", dependencies=[Depends(verify_token)])
async def close_practice_trade(body: PracticeCloseBody):
    """Manually close an open practice trade at current market mid + fee."""
    trades = _load_practice_trades()
    target = None
    for t in trades:
        if t.get("intent_id") == body.intent_id and t.get("status") == "open":
            target = t
            break
    if target is None:
        return {"ok": False, "error": "trade not found or already closed"}
    bid, ask, mid = _current_quote(target["asset"], target["venue"])
    if mid <= 0:
        return {"ok": False, "error": "no live quote to mark against"}
    # Exit at the opposite side: if we bought, sell at bid; if we sold, buy at ask
    exit_price = bid if target["side"] == "buy" else ask
    if exit_price <= 0:
        exit_price = mid
    notional_in = target["fill_price"] * target["qty"]
    notional_out = exit_price * target["qty"]
    signed = +1 if target["side"] == "buy" else -1
    gross_pnl = signed * (exit_price - target["fill_price"]) * target["qty"]
    fee_bps = float(target.get("fee_bps") or _PRACTICE_FEE_BPS)
    exit_fee = notional_out * (fee_bps / 10000.0)
    realized = gross_pnl - target["fees_usd"] - exit_fee
    target["status"] = "closed"
    target["exit_price"] = float(exit_price)
    target["exit_ts_utc"] = time.time()
    target["fees_usd"] = float(target["fees_usd"] + exit_fee)
    target["realized_pnl_usd"] = float(realized)
    _rewrite_practice_trades(trades)
    return {"ok": True, **target}


@app.get("/api/stream", dependencies=[Depends(verify_token)])
async def stream():
    """Server-Sent Events stream of new signal events."""
    async def event_gen():
        # Send initial state
        yield {"event": "snapshot",
               "data": json.dumps({"statuses": [asdict(s) for s in store.current_status.values()]})}
        # Then live updates
        while True:
            try:
                event = await asyncio.wait_for(store.event_queue.get(), timeout=20.0)
                yield {"event": event["type"], "data": json.dumps(event["data"])}
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": json.dumps({"ts": time.time()})}
    return EventSourceResponse(event_gen())
