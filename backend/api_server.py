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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from markets_adapter import (
    MarketBar, MarketChunker, MarketChunkEncoder,
)
from regime_classifier import (
    Regime, classify_regime, baselines_from_corpus,
    apply_cross_venue_multiplier, _session_phase_of,
)


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


# ---------------------------------------------------------------------------
# Playbook strings per regime (the actionable text users see)
# ---------------------------------------------------------------------------

PLAYBOOKS: dict[str, str] = {
    "EQUILIBRIUM_TWO_SIDED": "Healthy two-sided market. No edge. Sit out unless dipole is extreme - then mean-revert.",
    "WHALE_UP": "One big buyer dominating. Piggyback if early; get out of way if late. Watch for inventory exhaustion.",
    "WHALE_DOWN": "One big seller dominating. Piggyback short if early; sit out if late. Watch for capitulation bottom.",
    "HERD_UP": "FOMO/panic buy. Follow with tight stops; fade after overshoot.",
    "HERD_DOWN": "Panic sell / capitulation. Fade after the worst is over; do NOT catch the falling knife.",
    "WASH_PAIRED": "Wash-trade signature. Do not trade. Manipulation, no real price discovery.",
    "DEPLETED": "Market is asleep (lunch / off-hours). Sit out - no work being done here.",
    "UNKNOWN": "Pattern doesn't match a known regime. Skip until classifier resolves.",
}


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
        # Cross-venue minute->regime maps for F6 multiplier
        self._minute_regime_per_venue: dict[tuple[str, str], dict[float, str]] = {}

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
            bars.append(MarketBar(
                ts=float(m_ts),
                close=float(mids[-1]), open_=float(mids[0]),
                high=float(max(mids)), low=float(min(mids)),
                volume=float(sum(b["buy"] + b["sell"] for _, b in members)),
                buy_vol=float(sum(b["buy"] for _, b in members)),
                sell_vol=float(sum(b["sell"] for _, b in members)),
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
        feats = [encoder._extract(c) for c in chunks]
        base = baselines_from_corpus(feats)
        results = [classify_regime(f, base) for f in feats]

        # Build minute->regime map for cross-venue agreement (F6)
        m_map: dict[float, str] = {}
        for c, r in zip(chunks, results):
            for bar_idx in range(c.window_start, c.window_end):
                if 0 <= bar_idx < len(bars):
                    m_map[bars[bar_idx].ts] = r.regime.value
        self._minute_regime_per_venue[(asset, venue)] = m_map

        # Use most recent chunk as current status
        latest_chunk = chunks[-1]
        latest_feat = feats[-1]
        latest_result = results[-1]

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
            sig = SignalEvent(
                signal_id=str(uuid.uuid4())[:12],
                asset=asset, venue=venue,
                regime=status.regime,
                confidence=status.confidence,
                cross_venue_multiplier=status.cross_venue_multiplier,
                adjusted_confidence=status.adjusted_confidence,
                mean_dipole=float(latest_feat.mean_dipole),
                realized_vol=float(latest_feat.realized_vol),
                chunk_volume=float(latest_feat.chunk_total_volume),
                notes=latest_result.notes[:3],
                playbook=PLAYBOOKS.get(status.regime, "(no playbook configured)"),
                timestamp_utc=time.time(),
                chunk_window=(latest_chunk.window_start, latest_chunk.window_end),
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
            )
            self.recent_signals.append(sig)
            self.signal_index[sig.signal_id] = sig
            await self.event_queue.put({"type": "signal", "data": asdict(sig)})
            emitted = True

        if emitted:
            self.last_chunk_id_per_source[(asset, venue)] = latest_chunk.chunk_id

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
                 "dipole": b.dipole, "ofi": b.ofi,
                 "volume": b.volume}
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
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "tracked_sources": [{"asset": a, "venue": v, "has_data": (a, v) in store.current_status}
                             for a, v, _ in DATA_SOURCES],
        "n_recent_signals": len(store.recent_signals),
    }


@app.get("/api/status")
async def status():
    return {
        "statuses": [asdict(s) for s in store.current_status.values()],
        "as_of_utc": time.time(),
    }


@app.get("/api/signals")
async def signals(limit: int = 50):
    sigs = list(store.recent_signals)[-limit:]
    sigs.reverse()  # newest first
    return {"signals": [asdict(s) for s in sigs]}


@app.get("/api/signal/{signal_id}")
async def signal_detail(signal_id: str):
    sig = store.signal_index.get(signal_id)
    if not sig:
        raise HTTPException(404, "signal not found")
    chart = await store.chart_data(sig.asset, sig.venue, n_minutes=120)
    return {"signal": asdict(sig), "chart": chart}


@app.get("/api/chart/{asset}/{venue}")
async def chart(asset: str, venue: str, n_minutes: int = 240):
    return await store.chart_data(asset, venue, n_minutes=n_minutes)


@app.get("/api/stream")
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
