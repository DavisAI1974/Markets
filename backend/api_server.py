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
import os
import sys
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict, field
from typing import Any

# Allow imports from the parent Markets directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
)
from backend.auth import verify_token, ACCESS_TOKEN
from backend.push import (
    PushSubscription, add_sub, remove_sub, get_subs, send_to_all, VAPID_PUBLIC,
)
from playbook_generator import get_playbook as get_dynamic_playbook
from playbook_generator import get_drift_status
from backend.forward_paper import (
    entry_price_for_cell as _fp_entry_price,
    find_matching_cells as _fp_find_cells,
    open_paper_trade as _fp_open_trade,
    vol_target_multiplier as _fp_vol_mult,
    is_expired as _fp_is_expired,
    close_paper_trade as _fp_close_trade,
)
from backend.basis_monitor import BasisMonitor
from backend.cb_premium_monitor import CoinbasePremiumMonitor
from backend.funding_monitor import FundingMonitor
from backend.oi_monitor import OIMonitor
from backend.liq_monitor import LiqMonitor
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration: which (asset, venue) pairs to track and where their bins live
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DATA_SOURCES = [
    # (asset, venue, bins_path)
    ("BTC", "Coinbase", os.path.join(REPO_ROOT, "phase1_bins.json")),
    ("BTC", "Kraken",   os.path.join(REPO_ROOT, "kraken_bins.json")),
    ("ETH", "Coinbase", os.path.join(REPO_ROOT, "eth_coinbase_bins.json")),
    ("ETH", "Kraken",   os.path.join(REPO_ROOT, "eth_kraken_bins.json")),
]

# Spot/perp paths for the basis_monitor. Per-asset; we pick whichever
# spot venue is deepest (KR for both ETH/BTC at present) and whichever
# perp source has the longest history (Binance Vision once backfilled,
# else the RT Bybit collector).
BASIS_SPOT_PATHS = {
    "BTC": os.path.join(REPO_ROOT, "kraken_bins.json"),
    "ETH": os.path.join(REPO_ROOT, "eth_kraken_bins.json"),
}
BASIS_PERP_PATHS = {
    "BTC": os.path.join(REPO_ROOT, "btc_binance_perp_bins.json"),
    "ETH": os.path.join(REPO_ROOT, "eth_binance_perp_bins.json"),
}

POLL_INTERVAL_S = 30.0
RECENT_SIGNALS_CAP = 200
CHUNK_MAX_SIZE = 30
CHUNK_MIN_SEGMENT = 10

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
    "DEPLETED":    "Market quiet — no activity",
    "EQUILIBRIUM_TWO_SIDED": "Healthy two-sided trading",
    "UNKNOWN":     "Unclassified pattern",
}

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
        for asset, venue, path in DATA_SOURCES:
            try:
                await self._poll_one(asset, venue, path)
            except Exception as e:
                print(f"[SignalStore] error polling {asset}/{venue}: {e}", flush=True)

        # Apply F6 cross-venue multiplier to current statuses
        self._apply_cross_venue_F6()
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
        # Per-(asset, venue) VPIN thresholds; falls back to defaults.
        vpin_elev, vpin_diff = _vpin_thresholds_for(asset, venue)
        results = [classify_regime(f, base,
                                     vpin_elevated=vpin_elev,
                                     vpin_diffuse=vpin_diff) for f in feats]
        apply_herd_persistence(results)

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
        )

        prev_status = self.current_status.get((asset, venue))
        regime_changed = (prev_status is None) or (prev_status.regime != status.regime)
        self.current_status[(asset, venue)] = status

        # Track new-chunk transitions for both the production and demo emit paths
        last_emitted = self.last_chunk_id_per_source.get((asset, venue))
        chunk_changed = (last_emitted != latest_chunk.chunk_id)

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
            )
            self.recent_signals.append(sig)
            self.signal_index[sig.signal_id] = sig
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
                    asset, venue, status.regime, latest_feat, latest_chunk)
            except Exception as e:
                print(f"[forward-paper] open error {asset}/{venue}: {e}", flush=True)
            self.last_paper_chunk_id_per_source[(asset, venue)] = latest_chunk.chunk_id

    def _maybe_open_forward_paper_trades(self, asset: str, venue: str,
                                          regime: str, feat, chunk) -> None:
        cells = _fp_find_cells(asset, venue, regime, feat, chunk)
        if not cells:
            return
        bid, ask, mid = _current_quote(asset, venue)
        # Vol-target sizing: scale notional ∝ VOL_TARGET / chunk realized_vol,
        # clipped to [0.5x, 2.0x]. Same multiplier applies to all cells
        # firing on this chunk since they share the same regime context.
        rv = float(getattr(feat, "realized_vol", 0.0) or 0.0)
        vol_mult = _fp_vol_mult(rv)
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

    def _sweep_close_forward_paper_trades(self) -> None:
        trades = _load_practice_trades()
        now = time.time()
        any_changed = False
        for t in trades:
            if not _fp_is_expired(t, now):
                continue
            bid, ask, mid = _current_quote(t.get("asset", ""), t.get("venue", ""))
            before_status = t.get("status")
            _fp_close_trade(t, bid, ask, mid)
            if t.get("status") != before_status:
                any_changed = True
                print(f"[forward-paper] closed {t.get('cell_id')} "
                      f"intent_id={t.get('intent_id')} "
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
                    )
                    self.recent_signals.append(sig)
                    self.signal_index[sig.signal_id] = sig
                    self._persist_signal(sig)
                    await self.event_queue.put({"type": "signal", "data": asdict(sig)})

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
                    status.adjusted_confidence = status.confidence
                    continue
                # Pick the most recent timestamps from other_map's keys overlapping our chunk window
                # For simplicity: most recent label from the other venue
                latest_other_ts = max(other_map.keys())
                latest_other_regime = other_map[latest_other_ts]
                if latest_other_regime == status.regime:
                    status.cross_venue_multiplier = 1.5
                else:
                    status.cross_venue_multiplier = 0.5
                status.adjusted_confidence = max(0.0, min(1.0,
                    status.confidence * status.cross_venue_multiplier))

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
    while True:
        await store.poll_all()
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
        "tracked_sources": [{"asset": a, "venue": v, "has_data": (a, v) in store.current_status}
                             for a, v, _ in DATA_SOURCES],
        "n_recent_signals": len(store.recent_signals),
    }


@app.get("/api/status", dependencies=[Depends(verify_token)])
async def status():
    return {
        "statuses": [asdict(s) for s in store.current_status.values()],
        "as_of_utc": time.time(),
    }


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
    for c, f, r in zip(chunks[-n_points:], feats[-n_points:], results[-n_points:]):
        points.append({
            "chunk_idx": c.window_start,
            "regime": r.regime.value,
            "mean_dipole": float(f.mean_dipole),
            "realized_vol": float(f.realized_vol),
            "confidence": r.confidence,
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
    return {
        "trades": trades[:limit],
        "n_open": sum(1 for t in trades if t.get("status") == "open"),
        "n_closed": len(closed),
        "win_rate": (n_wins / len(closed)) if closed else None,
        "total_realized_pnl_usd": float(total_realized),
        "by_cell": by_cell,
    }


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
    exit_fee = notional_out * (_PRACTICE_FEE_BPS / 10000.0)
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
