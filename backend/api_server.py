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


# ---------------------------------------------------------------------------
# Direction inference (matches executor logic)
# ---------------------------------------------------------------------------

def expected_direction_from_signal(regime: str, mean_dipole: float) -> int:
    if regime == "WHALE_UP" or regime == "HERD_UP":
        return +1
    if regime == "WHALE_DOWN" or regime == "HERD_DOWN":
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
        # Cross-venue minute->regime maps for F6 multiplier
        self._minute_regime_per_venue: dict[tuple[str, str], dict[float, str]] = {}
        # Persistent signal log (JSONL); restored on startup
        self._persist_path = os.path.join(REPO_ROOT, "backend_signals.jsonl")
        self._restore_signals()

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
        apply_herd_persistence(results)

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
            playbook = PLAYBOOKS.get(status.regime, "(no playbook configured)")
            if cascade_event:
                playbook = (
                    f"[CASCADE: WHALE→HERD same direction] "
                    + CASCADE_PLAYBOOKS.get(cascade_event, playbook))
            playbook = playbook + f"  ({split_note}.)"
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
        if changed:
            self._rewrite_signals()

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
    feats = [encoder._extract(c) for c in chunks]
    base = baselines_from_corpus(feats)
    results = [classify_regime(f, base) for f in feats]
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
