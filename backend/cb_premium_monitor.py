"""
cb_premium_monitor.py — Coinbase premium index. Tracks the gap
between Coinbase BTC-USD / ETH-USD spot and Binance BTCUSDT /
ETHUSDT spot (peg-corrected by current USDT/USD), expressed in bps,
and emits CB_PREMIUM_HOT / CB_PREMIUM_COLD / CB_PREMIUM_CLEARED
drift alerts on rolling-z transitions.

Mechanism (per asset):
  1. Each cycle, poll Coinbase ticker for the asset (BTC-USD, ETH-USD)
     plus USDT-USD (the peg), and Binance spot for BTCUSDT / ETHUSDT.
  2. Convert Binance USDT price into USD by multiplying by USDT/USD.
  3. premium_bps = ((cb_usd - bn_in_usd) / cb_usd) * 1e4
  4. Maintain rolling deque of premium_bps; z-score against rolling
     mean+std.
  5. Emit HOT (z >= +HOT_Z) when CB consistently leads up (US-side
     buying pressure); COLD (z <= -HOT_Z) when CB consistently lags
     (US-side selling pressure). Sustained-streak gating + hysteresis
     clear, mirroring basis_monitor.

Why this matters (per microstructure literature, 2025-2026):
  - Sustained positive CB premium is a classic US-institutional
    buying signal (the CryptoQuant "Coinbase Premium Index").
  - Sustained negative CB premium is a US-side selling / outflow
    signal that often leads price decay during US hours.
  - The peg correction matters: a 50-bps USDT depeg can swamp the
    raw CB-vs-BN gap and falsely look like a CB premium.
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


ROLLING_WINDOW_OBS = 240        # ~120 min at 30s poll cadence
HOT_Z = 2.0
CLEAR_Z = 1.0
SUSTAINED_CYCLES = 5
MIN_OBS_FOR_Z = 60
HISTORY_PATH_DEFAULT = "backend_cb_premium_history.jsonl"
HTTP_TIMEOUT_S = 6.0
# TODO calibration: this monitor currently uses sigma cuts (HOT_Z=2.0
# / CLEAR_Z=1.0) as policy. If we want empirical per-asset thresholds
# the way oi_monitor and funding_monitor have, ship
# calibrate_cb_premium.py that walks backend_cb_premium_history.jsonl
# for p95/p50 of |premium_z|. Defer until ≥240 observations exist on
# AWS. See TODO.md "CB premium calibration (deferred)".


PREMIUM_SOURCES = [
    ("BTC", "BTC-USD", "BTCUSDT"),
    ("ETH", "ETH-USD", "ETHUSDT"),
]


def _http_get_json(url: str) -> Optional[dict]:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "markets-watch-cbprem/1.0",
                          "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[cb-premium] HTTP error on {url}: {e}", flush=True)
        return None
    except Exception as e:
        print(f"[cb-premium] unexpected error on {url}: {e}", flush=True)
        return None


def _fetch_coinbase_price(pair: str) -> Optional[float]:
    body = _http_get_json(
        f"https://api.exchange.coinbase.com/products/{pair}/ticker")
    if not body:
        return None
    try:
        px = float(body.get("price", 0.0))
        return px if px > 0 else None
    except (TypeError, ValueError):
        return None


def _fetch_binance_spot_price(symbol: str) -> Optional[float]:
    body = _http_get_json(
        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
    if not body:
        return None
    try:
        px = float(body.get("price", 0.0))
        return px if px > 0 else None
    except (TypeError, ValueError):
        return None


@dataclass
class _PremiumState:
    history: deque = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW_OBS))
    last_premium_bps: float = 0.0
    last_z: float = 0.0
    last_cb_price: float = 0.0
    last_bn_price_usd: float = 0.0
    last_usdt_usd: float = 0.0
    streak_above_hot: int = 0
    streak_below_cold: int = 0
    current_state: str = "normal"   # normal | hot | cold


class CoinbasePremiumMonitor:
    def __init__(self, history_path: Optional[str] = None,
                  sources: Optional[list[tuple[str, str, str]]] = None):
        self.history_path = history_path or HISTORY_PATH_DEFAULT
        self.sources = sources or PREMIUM_SOURCES
        self._state: dict[str, _PremiumState] = {}
        # USDT/USD is shared across all assets in a single cycle; cache
        # for ~30s so we don't hit Coinbase USDT-USD ticker N times per
        # poll. (Negligible network savings, but cleaner.)
        self._usdt_usd_cache: tuple[float, float] = (0.0, 0.0)  # (price, ts)

    def _state_for(self, asset: str) -> _PremiumState:
        s = self._state.get(asset)
        if s is None:
            s = _PremiumState()
            self._state[asset] = s
        return s

    def _get_usdt_usd(self) -> Optional[float]:
        px, ts = self._usdt_usd_cache
        if px > 0 and (time.time() - ts) < 30.0:
            return px
        fresh = _fetch_coinbase_price("USDT-USD")
        if fresh is None:
            # If the USDT-USD ticker fails, fall back to 1.0 (neutral
            # peg assumption). Better than emitting no alert at all.
            return 1.0
        self._usdt_usd_cache = (fresh, time.time())
        return fresh

    def _persist(self, asset: str, cb_price: float, bn_price_usd: float,
                  usdt_usd: float, premium_bps: float) -> None:
        try:
            with open(self.history_path, "a") as f:
                f.write(json.dumps({
                    "ts_utc": time.time(),
                    "asset": asset,
                    "cb_price": float(cb_price),
                    "bn_price_usd": float(bn_price_usd),
                    "usdt_usd": float(usdt_usd),
                    "premium_bps": float(premium_bps),
                }) + "\n")
        except Exception as e:
            print(f"[cb-premium] persist error: {e}", flush=True)

    def update_all(self) -> list[dict]:
        alerts: list[dict] = []
        usdt_usd = self._get_usdt_usd()
        if usdt_usd is None or usdt_usd <= 0:
            return alerts

        for asset, cb_pair, bn_symbol in self.sources:
            cb_px = _fetch_coinbase_price(cb_pair)
            bn_px_usdt = _fetch_binance_spot_price(bn_symbol)
            if cb_px is None or bn_px_usdt is None:
                continue
            bn_px_usd = bn_px_usdt * usdt_usd
            premium_bps = ((cb_px - bn_px_usd) / cb_px) * 1e4 if cb_px > 0 else 0.0

            st = self._state_for(asset)
            st.history.append(premium_bps)
            st.last_premium_bps = premium_bps
            st.last_cb_price = cb_px
            st.last_bn_price_usd = bn_px_usd
            st.last_usdt_usd = usdt_usd
            self._persist(asset, cb_px, bn_px_usd, usdt_usd, premium_bps)

            if len(st.history) < MIN_OBS_FOR_Z:
                continue
            mean = sum(st.history) / len(st.history)
            var = sum((x - mean) ** 2 for x in st.history) / len(st.history)
            std = var ** 0.5
            if std < 1e-9:
                continue
            z = (premium_bps - mean) / std
            st.last_z = z

            if z >= HOT_Z:
                st.streak_above_hot += 1
                st.streak_below_cold = 0
            elif z <= -HOT_Z:
                st.streak_below_cold += 1
                st.streak_above_hot = 0
            else:
                st.streak_above_hot = 0
                st.streak_below_cold = 0

            new_state = st.current_state
            alert_type = None
            if st.current_state != "hot" and st.streak_above_hot >= SUSTAINED_CYCLES:
                new_state = "hot"
                alert_type = "CB_PREMIUM_HOT"
            elif st.current_state != "cold" and st.streak_below_cold >= SUSTAINED_CYCLES:
                new_state = "cold"
                alert_type = "CB_PREMIUM_COLD"
            elif st.current_state != "normal" and abs(z) <= CLEAR_Z:
                new_state = "normal"
                alert_type = "CB_PREMIUM_CLEARED"

            if new_state == st.current_state:
                continue
            prev = st.current_state
            st.current_state = new_state

            if alert_type == "CB_PREMIUM_CLEARED":
                summary = (f"{asset} CB premium cleared "
                           f"(premium={premium_bps:+.1f}bps z={z:+.2f}; was {prev})")
            else:
                side = ("US bid: CB leading up" if alert_type == "CB_PREMIUM_HOT"
                        else "US offer: CB leading down")
                summary = (f"{asset} CB premium {alert_type[-3:].lower()} — {side} "
                           f"(premium={premium_bps:+.1f}bps z={z:+.2f})")
            alerts.append({
                "type": alert_type,
                "key": f"{asset}/cb-premium",
                "summary": summary,
                "asset": asset,
                "premium_bps": float(premium_bps),
                "premium_z": float(z),
                "cb_price": float(cb_px),
                "bn_price_usd": float(bn_px_usd),
                "usdt_usd": float(usdt_usd),
                "previous_state": prev,
            })
        return alerts

    def snapshot(self) -> dict[str, dict]:
        out = {}
        for asset, st in self._state.items():
            out[asset] = {
                "n_obs": len(st.history),
                "last_premium_bps": float(st.last_premium_bps),
                "last_premium_z": float(st.last_z),
                "last_cb_price": float(st.last_cb_price),
                "last_bn_price_usd": float(st.last_bn_price_usd),
                "last_usdt_usd": float(st.last_usdt_usd),
                "current_state": st.current_state,
                "streak_above_hot": st.streak_above_hot,
                "streak_below_cold": st.streak_below_cold,
            }
        return out
