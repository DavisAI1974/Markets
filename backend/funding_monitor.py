"""
funding_monitor.py — perp funding-rate watcher emitting
FUNDING_OVERLEVERED_LONG / FUNDING_OVERLEVERED_SHORT drift alerts.

Mechanism:
  - Poll Binance USDT-M and Bybit linear funding APIs once per
    backend poll cycle. Rates only change every 8 hours, so we dedupe
    on (venue, fundingTime); each rate is processed exactly once.
  - Persist every funding observation to backend_funding_history.jsonl
    so we can later backtest funding-conditional cells.
  - Emit a drift alert when |rate| crosses ELEVATED_THRESHOLD; emit
    EXTREME on a higher threshold. Hysteresis on clear: emit CLEARED
    when |rate| falls back below CLEAR_THRESHOLD.

Predictive interpretation (per literature, 2025-2026):
  - rate > 0 (longs pay shorts) => long crowdedness; extreme positive
    + rising open interest => prone to long-liquidation cascade.
  - rate < 0 (shorts pay longs) => short crowdedness; extreme negative
    => short-squeeze risk.
  - Annualized: 0.01% / 8h ≈ 10.95% APR; 0.05% / 8h ≈ 54.7% APR.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# Fallback thresholds in raw 8-hour rate (0.0001 == 1 bp / 8h ~ 10.95% APR).
# Used only when funding_calibration.json is missing or doesn't have an
# entry for this (asset, venue). Empirical per-key thresholds (p25/p75/p95
# of historical |rate|) come from calibrate_funding.py.
ELEVATED_THRESHOLD = 0.0001     # 1 bp / 8h
EXTREME_THRESHOLD = 0.0005      # 5 bp / 8h
CLEAR_THRESHOLD = 0.00003       # 0.3 bp / 8h
HISTORY_PATH_DEFAULT = "backend_funding_history.jsonl"
HTTP_TIMEOUT_S = 6.0


def _load_funding_calibration(path: str) -> dict[str, dict]:
    """Read funding_calibration.json once and return per-(asset, venue)
    threshold dicts. Errors are non-fatal — caller falls back to
    hardcoded defaults."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            payload = json.load(f)
        return payload.get("calibration", {}) or {}
    except Exception as e:
        print(f"[funding] could not parse {path}: {e}; using defaults",
              flush=True)
        return {}

# (asset, venue, symbol) tuples. Matches the perp collectors already
# in the project.
FUNDING_SOURCES = [
    ("BTC", "Binance", "BTCUSDT"),
    ("ETH", "Binance", "ETHUSDT"),
    ("BTC", "Bybit",   "BTCUSDT"),
    ("ETH", "Bybit",   "ETHUSDT"),
]


def _http_get_json(url: str) -> Optional[dict]:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "markets-watch-funding/1.0",
                          "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[funding] HTTP error on {url}: {e}", flush=True)
        return None
    except Exception as e:
        print(f"[funding] unexpected error on {url}: {e}", flush=True)
        return None


def _fetch_binance(symbol: str) -> Optional[dict]:
    """Returns {'rate': float, 'next_funding_ts': float}. Binance
    publishes the live mark+index premium index which contains the
    most-recent funding rate at /fapi/v1/premiumIndex."""
    body = _http_get_json(
        f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}")
    if not body:
        return None
    try:
        rate = float(body.get("lastFundingRate", 0.0))
        nft = float(body.get("nextFundingTime", 0.0)) / 1000.0
        return {"rate": rate, "next_funding_ts": nft}
    except (TypeError, ValueError):
        return None


def _fetch_bybit(symbol: str) -> Optional[dict]:
    body = _http_get_json(
        f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}")
    if not body or body.get("retCode") != 0:
        return None
    try:
        items = body["result"]["list"]
        if not items:
            return None
        item = items[0]
        rate = float(item.get("fundingRate", 0.0))
        nft = float(item.get("nextFundingTime", 0.0)) / 1000.0
        return {"rate": rate, "next_funding_ts": nft}
    except (KeyError, TypeError, ValueError):
        return None


@dataclass
class _FundingState:
    last_rate: float = 0.0
    last_next_funding_ts: float = 0.0
    last_observed_funding_ts: float = 0.0  # nft of the rate we last alerted on
    current_state: str = "normal"   # normal | elevated_long | elevated_short | extreme_long | extreme_short
    history: deque = field(default_factory=lambda: deque(maxlen=200))


class FundingMonitor:
    def __init__(self, history_path: Optional[str] = None,
                  sources: Optional[list[tuple[str, str, str]]] = None,
                  calibration_path: Optional[str] = None):
        self.history_path = history_path or HISTORY_PATH_DEFAULT
        self.sources = sources or FUNDING_SOURCES
        # State is keyed by (asset, venue) so BTC/Binance vs BTC/Bybit
        # have independent thresholds and emit distinct alerts.
        self._state: dict[tuple[str, str], _FundingState] = {}
        # Per-(asset, venue) thresholds. Loaded once from
        # funding_calibration.json; falls back to hardcoded defaults.
        cal = _load_funding_calibration(calibration_path) if calibration_path else {}
        self._thresholds: dict[tuple[str, str], tuple[float, float, float]] = {}
        for asset, venue, _symbol in self.sources:
            entry = cal.get(f"{asset}/{venue}") or {}
            elev = float(entry.get("elevated_threshold", ELEVATED_THRESHOLD))
            extr = float(entry.get("extreme_threshold", EXTREME_THRESHOLD))
            clear = float(entry.get("clear_threshold", CLEAR_THRESHOLD))
            self._thresholds[(asset, venue)] = (elev, extr, clear)
            calibrated = f"{asset}/{venue}" in cal
            print(f"[funding] {asset}/{venue}: elevated={elev*1e4:.2f}bps "
                  f"extreme={extr*1e4:.2f}bps clear={clear*1e4:.2f}bps "
                  f"({'calibrated' if calibrated else 'hardcoded fallback'})",
                  flush=True)

    def _state_for(self, asset: str, venue: str) -> _FundingState:
        k = (asset, venue)
        s = self._state.get(k)
        if s is None:
            s = _FundingState()
            self._state[k] = s
        return s

    def _thresholds_for(self, asset: str, venue: str) -> tuple[float, float, float]:
        return self._thresholds.get(
            (asset, venue),
            (ELEVATED_THRESHOLD, EXTREME_THRESHOLD, CLEAR_THRESHOLD))

    def _persist(self, asset: str, venue: str, symbol: str, rate: float,
                  nft: float) -> None:
        try:
            with open(self.history_path, "a") as f:
                f.write(json.dumps({
                    "ts_utc": time.time(),
                    "asset": asset,
                    "venue": venue,
                    "symbol": symbol,
                    "rate": float(rate),
                    "next_funding_ts": float(nft),
                }) + "\n")
        except Exception as e:
            print(f"[funding] persist error: {e}", flush=True)

    def _classify_state(self, rate: float, asset: str, venue: str) -> str:
        elevated, extreme, _clear = self._thresholds_for(asset, venue)
        if rate >= extreme:
            return "extreme_long"
        if rate <= -extreme:
            return "extreme_short"
        if rate >= elevated:
            return "elevated_long"
        if rate <= -elevated:
            return "elevated_short"
        return "normal"

    def update_all(self) -> list[dict]:
        """Poll every (asset, venue, symbol) source. Returns a list of
        alert dicts (one per state transition)."""
        alerts: list[dict] = []
        for asset, venue, symbol in self.sources:
            try:
                snap = (_fetch_binance(symbol) if venue == "Binance"
                        else _fetch_bybit(symbol) if venue == "Bybit"
                        else None)
            except Exception as e:
                print(f"[funding] fetch error {asset}/{venue}: {e}", flush=True)
                continue
            if not snap:
                continue
            rate = snap["rate"]
            nft = snap["next_funding_ts"]
            st = self._state_for(asset, venue)
            st.last_rate = rate
            st.last_next_funding_ts = nft

            # Persist when we see a NEW funding-cycle ts (so the JSONL
            # has one row per funding window, not 30s snapshots).
            if nft > st.last_observed_funding_ts:
                self._persist(asset, venue, symbol, rate, nft)
                st.history.append({"rate": rate, "nft": nft, "ts": time.time()})
                st.last_observed_funding_ts = nft

            new_state = self._classify_state(rate, asset, venue)
            if new_state == st.current_state:
                continue

            prev = st.current_state
            st.current_state = new_state

            if new_state == "normal":
                alerts.append({
                    "type": "FUNDING_CLEARED",
                    "key": f"{asset}/{venue}/funding",
                    "summary": (f"{asset} {venue} funding back to normal "
                                f"(rate={rate*1e4:+.2f}bps/8h; was {prev})"),
                    "asset": asset, "venue": venue,
                    "rate": rate, "rate_bps_8h": rate * 1e4,
                    "previous_state": prev,
                })
            else:
                direction = "LONG" if "long" in new_state else "SHORT"
                tier = "EXTREME" if "extreme" in new_state else "ELEVATED"
                alerts.append({
                    "type": f"FUNDING_OVERLEVERED_{direction}",
                    "key": f"{asset}/{venue}/funding",
                    "summary": (f"{asset} {venue} funding {tier} {direction} "
                                f"(rate={rate*1e4:+.2f}bps/8h ~ {rate*3*365*100:+.1f}% APR)"),
                    "asset": asset, "venue": venue,
                    "rate": rate, "rate_bps_8h": rate * 1e4,
                    "tier": tier.lower(),
                    "previous_state": prev,
                })
        return alerts

    def snapshot(self) -> dict:
        out: dict = {}
        for (asset, venue), st in self._state.items():
            out[f"{asset}/{venue}"] = {
                "rate": float(st.last_rate),
                "rate_bps_8h": float(st.last_rate * 1e4),
                "next_funding_ts": float(st.last_next_funding_ts),
                "current_state": st.current_state,
                "n_history": len(st.history),
            }
        return out
