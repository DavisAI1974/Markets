"""
oi_monitor.py — open interest watcher emitting OI_BUILDING_LONG /
OI_BUILDING_SHORT / OI_UNWIND_SHORTS / OI_UNWIND_LONGS / OI_CLEARED
drift alerts on perp positioning shifts.

Mechanism (per asset, venue):
  1. Each cycle, poll Binance USDT-M /fapi/v1/openInterest +
     /fapi/v1/ticker/price and Bybit linear /v5/market/tickers for
     the latest open interest and last price.
  2. Maintain a rolling deque of (oi, price, ts) observations.
     Compute Δoi_pct and Δprice_pct over a window of WINDOW_OBS
     observations (≈ 6 min at 30s poll).
  3. Z-score Δoi_pct against the rolling history. When |z| crosses
     BUILD_Z (alert threshold) for SUSTAINED_CYCLES consecutive
     polls, emit a drift alert keyed on (sign Δoi, sign Δprice).
  4. Hysteresis on clear: emit OI_CLEARED when |z| falls back
     below CLEAR_Z.
  5. Persist every observation to backend_oi_history.jsonl so a
     calibration script (calibrate_oi.py) can later pin per-(asset,
     venue) percentile thresholds.

Why this matters (per microstructure literature, 2025-2026):
  - OI↑ alongside price↑ confirms trend conviction (new positions
    opening on the dominant side).
  - OI↑ alongside price↓ means new shorts are leveraging in;
    cascade risk grows.
  - OI↓ alongside price↑ is a short-squeeze (shorts being closed).
  - OI↓ alongside price↓ is long capitulation.
  - The same Δprice paired with rising vs falling OI is a different
    regime; reading them in isolation is throwing information away.
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


WINDOW_OBS = 12                 # observations spanned by Δ measurement
ROLLING_WINDOW_OBS = 240        # rolling z baseline (~120 min @ 30s)
BUILD_Z = 2.0                   # |z| trigger
CLEAR_Z = 1.0                   # |z| hysteresis clear
SUSTAINED_CYCLES = 3            # consecutive polls above BUILD_Z
MIN_OBS_FOR_Z = 60              # need this much history before z-scoring
HISTORY_PATH_DEFAULT = "backend_oi_history.jsonl"
HTTP_TIMEOUT_S = 6.0
# TODO recalibration: re-run `python calibrate_oi.py` once
# backend_oi_history.jsonl has ≥240 observations per (asset, venue)
# on AWS to swap BUILD_Z=2.0 / CLEAR_Z=1.0 for empirical p95 / p50
# of |Δoi z|. Sigma cuts are deliberate policy until then; do not
# tighten without data. See TODO.md "Recalibrations to re-run as
# the corpus grows".
# TODO empirical: WINDOW_OBS=12 (~6 min) is a guess; OI typically
# moves on hourly cadences and 12 may pick up too much short-term
# noise. Once history accumulates, compare 12 vs 60 vs 120 by
# alert-rate vs realized-cascade fraction.
# TODO consistency: SUSTAINED_CYCLES=3 differs from basis_monitor's
# 5 with no derivation. Either harmonize or document why OI moves
# require fewer confirmation cycles than basis.


OI_SOURCES = [
    ("BTC", "Binance", "BTCUSDT"),
    ("ETH", "Binance", "ETHUSDT"),
    ("BTC", "Bybit",   "BTCUSDT"),
    ("ETH", "Bybit",   "ETHUSDT"),
]


def _load_oi_calibration(path: str) -> dict[str, dict]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            payload = json.load(f)
        return payload.get("calibration", {}) or {}
    except Exception as e:
        print(f"[oi] could not parse {path}: {e}; using defaults", flush=True)
        return {}


def _http_get_json(url: str) -> Optional[dict]:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "markets-watch-oi/1.0",
                          "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[oi] HTTP error on {url}: {e}", flush=True)
        return None
    except Exception as e:
        print(f"[oi] unexpected error on {url}: {e}", flush=True)
        return None


def _fetch_binance(symbol: str) -> Optional[dict]:
    """Returns {'oi': float, 'price': float}. Two HTTP calls; both
    public + free."""
    oi_body = _http_get_json(
        f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}")
    px_body = _http_get_json(
        f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}")
    if not oi_body or not px_body:
        return None
    try:
        return {"oi": float(oi_body.get("openInterest", 0.0)),
                "price": float(px_body.get("price", 0.0))}
    except (TypeError, ValueError):
        return None


def _fetch_bybit(symbol: str) -> Optional[dict]:
    """Returns {'oi': float, 'price': float} from a single
    /v5/market/tickers call."""
    body = _http_get_json(
        f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}")
    if not body or body.get("retCode") != 0:
        return None
    try:
        items = body["result"]["list"]
        if not items:
            return None
        item = items[0]
        return {"oi": float(item.get("openInterest", 0.0)),
                "price": float(item.get("lastPrice", 0.0))}
    except (KeyError, TypeError, ValueError):
        return None


@dataclass
class _OIState:
    history: deque = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW_OBS))
    delta_history: deque = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW_OBS))
    last_oi: float = 0.0
    last_price: float = 0.0
    last_delta_oi_pct: float = 0.0
    last_delta_price_pct: float = 0.0
    last_z: float = 0.0
    streak_above: int = 0
    streak_below: int = 0
    current_state: str = "normal"   # normal | building_long | building_short |
                                    # unwind_shorts | unwind_longs


class OIMonitor:
    def __init__(self, history_path: Optional[str] = None,
                  sources: Optional[list[tuple[str, str, str]]] = None,
                  calibration_path: Optional[str] = None):
        self.history_path = history_path or HISTORY_PATH_DEFAULT
        self.sources = sources or OI_SOURCES
        self._state: dict[tuple[str, str], _OIState] = {}
        cal = _load_oi_calibration(calibration_path) if calibration_path else {}
        # Per-(asset, venue) thresholds: build_z, clear_z. Calibration
        # script may override these from observed |Δoi z| percentiles.
        self._thresholds: dict[tuple[str, str], tuple[float, float]] = {}
        for asset, venue, _symbol in self.sources:
            entry = cal.get(f"{asset}/{venue}") or {}
            build = float(entry.get("build_z", BUILD_Z))
            clear = float(entry.get("clear_z", CLEAR_Z))
            self._thresholds[(asset, venue)] = (build, clear)
            calibrated = f"{asset}/{venue}" in cal
            print(f"[oi] {asset}/{venue}: build_z={build:.2f} clear_z={clear:.2f} "
                  f"({'calibrated' if calibrated else 'hardcoded fallback'})",
                  flush=True)

    def _state_for(self, asset: str, venue: str) -> _OIState:
        k = (asset, venue)
        s = self._state.get(k)
        if s is None:
            s = _OIState()
            self._state[k] = s
        return s

    def _thresholds_for(self, asset: str, venue: str) -> tuple[float, float]:
        return self._thresholds.get((asset, venue), (BUILD_Z, CLEAR_Z))

    def _persist(self, asset: str, venue: str, symbol: str, oi: float,
                  price: float) -> None:
        try:
            with open(self.history_path, "a") as f:
                f.write(json.dumps({
                    "ts_utc": time.time(),
                    "asset": asset,
                    "venue": venue,
                    "symbol": symbol,
                    "oi": float(oi),
                    "price": float(price),
                }) + "\n")
        except Exception as e:
            print(f"[oi] persist error: {e}", flush=True)

    def _classify(self, delta_oi_pct: float, delta_price_pct: float,
                   z: float, build_z: float, clear_z: float,
                   prev_state: str, streak_above: int, streak_below: int
                   ) -> tuple[str, Optional[str]]:
        """Return (new_state, alert_type_or_none)."""
        # Hysteresis clear: any non-normal state with |z| <= clear_z
        # transitions back to normal first.
        if prev_state != "normal" and abs(z) <= clear_z:
            return "normal", "OI_CLEARED"

        # Otherwise need SUSTAINED_CYCLES of |z| >= build_z to fire.
        if streak_above < SUSTAINED_CYCLES and streak_below < SUSTAINED_CYCLES:
            return prev_state, None

        if delta_oi_pct > 0:
            new = "building_long" if delta_price_pct > 0 else "building_short"
        else:
            new = "unwind_shorts" if delta_price_pct > 0 else "unwind_longs"
        if new == prev_state:
            return prev_state, None
        alert_map = {
            "building_long": "OI_BUILDING_LONG",
            "building_short": "OI_BUILDING_SHORT",
            "unwind_shorts": "OI_UNWIND_SHORTS",
            "unwind_longs": "OI_UNWIND_LONGS",
        }
        return new, alert_map[new]

    def update_all(self) -> list[dict]:
        alerts: list[dict] = []
        for asset, venue, symbol in self.sources:
            try:
                snap = (_fetch_binance(symbol) if venue == "Binance"
                        else _fetch_bybit(symbol) if venue == "Bybit"
                        else None)
            except Exception as e:
                print(f"[oi] fetch error {asset}/{venue}: {e}", flush=True)
                continue
            if not snap or snap["oi"] <= 0 or snap["price"] <= 0:
                continue

            oi = snap["oi"]
            price = snap["price"]
            st = self._state_for(asset, venue)

            self._persist(asset, venue, symbol, oi, price)
            st.history.append({"oi": oi, "price": price, "ts": time.time()})
            st.last_oi = oi
            st.last_price = price

            # Δ over the last WINDOW_OBS observations.
            if len(st.history) <= WINDOW_OBS:
                continue
            anchor = st.history[-WINDOW_OBS - 1]
            if anchor["oi"] <= 0 or anchor["price"] <= 0:
                continue
            d_oi = (oi - anchor["oi"]) / anchor["oi"]
            d_px = (price - anchor["price"]) / anchor["price"]
            st.last_delta_oi_pct = d_oi
            st.last_delta_price_pct = d_px
            st.delta_history.append(d_oi)

            if len(st.delta_history) < MIN_OBS_FOR_Z:
                continue
            mean = sum(st.delta_history) / len(st.delta_history)
            var = sum((x - mean) ** 2 for x in st.delta_history) / len(st.delta_history)
            std = var ** 0.5
            if std < 1e-12:
                continue
            z = (d_oi - mean) / std
            st.last_z = z

            build_z, clear_z = self._thresholds_for(asset, venue)
            if z >= build_z:
                st.streak_above += 1
                st.streak_below = 0
            elif z <= -build_z:
                st.streak_below += 1
                st.streak_above = 0
            else:
                st.streak_above = 0
                st.streak_below = 0

            new_state, alert_type = self._classify(
                d_oi, d_px, z, build_z, clear_z, st.current_state,
                st.streak_above, st.streak_below)
            if new_state == st.current_state:
                continue
            prev = st.current_state
            st.current_state = new_state

            if alert_type == "OI_CLEARED":
                alerts.append({
                    "type": "OI_CLEARED",
                    "key": f"{asset}/{venue}/oi",
                    "summary": (f"{asset} {venue} OI shift cleared "
                                f"(Δoi={d_oi*100:+.2f}% z={z:+.2f}; was {prev})"),
                    "asset": asset, "venue": venue,
                    "delta_oi_pct": float(d_oi),
                    "delta_price_pct": float(d_px),
                    "oi_z": float(z),
                    "previous_state": prev,
                })
            else:
                alerts.append({
                    "type": alert_type,
                    "key": f"{asset}/{venue}/oi",
                    "summary": (f"{asset} {venue} {alert_type[3:].replace('_',' ').lower()} "
                                f"(Δoi={d_oi*100:+.2f}% Δpx={d_px*100:+.2f}% z={z:+.2f})"),
                    "asset": asset, "venue": venue,
                    "delta_oi_pct": float(d_oi),
                    "delta_price_pct": float(d_px),
                    "oi_z": float(z),
                    "previous_state": prev,
                })
        return alerts

    # Internal lowercase state -> gate-facing emitted literal.
    _STATE_LITERAL = {
        "building_long": "OI_BUILDING_LONG",
        "building_short": "OI_BUILDING_SHORT",
        "unwind_longs": "OI_UNWIND_LONGS",
        "unwind_shorts": "OI_UNWIND_SHORTS",
    }

    def current_state_for(self, asset: str, venue: str) -> Optional[str]:
        """Gate accessor: the current OI state literal (e.g.
        'OI_BUILDING_LONG') for (asset, venue), or None when normal /
        unknown. `venue` is the OI-native perp venue ('Binance'/'Bybit')."""
        st = self._state.get((asset, venue))
        return self._STATE_LITERAL.get(st.current_state) if st else None

    def snapshot(self) -> dict:
        out: dict = {}
        for (asset, venue), st in self._state.items():
            out[f"{asset}/{venue}"] = {
                "oi": float(st.last_oi),
                "price": float(st.last_price),
                "delta_oi_pct": float(st.last_delta_oi_pct),
                "delta_price_pct": float(st.last_delta_price_pct),
                "oi_z": float(st.last_z),
                "current_state": st.current_state,
                "n_obs": len(st.history),
            }
        return out
