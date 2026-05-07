"""
liq_monitor.py — synthetic liquidation-burst detector reading perp
bins.

Real liquidation feeds for Binance/Bybit are WebSocket-only and would
need a separate streaming worker. As an MVP that runs in the existing
poll loop, we infer liquidation bursts from the perp bins we already
collect — a single-minute bar with all three of:
  - volume_z >= VOLUME_Z_THRESHOLD vs the trailing 60-min mean
  - |dipole| >= ONE_SIDED_THRESHOLD (taker flow strongly one-sided)
  - |price_move| >= PRICE_MOVE_THRESHOLD across the bar

is the textbook liquidation signature: forced taker buys/sells push
price aggressively in one direction with abnormal volume.

When detected, we emit LIQ_BURST_{UP,DOWN} drift alerts through the
shared pipeline, deduplicated by bar timestamp so each burst fires
exactly once.

This is a proxy, not a count of actual liquidated USD notional. To
upgrade to a real liquidation count, plug Bybit's
`wss://stream.bybit.com/v5/public/linear` topic `liquidation.<symbol>`
into a separate task and replace the synthetic detector.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field


# Fallback thresholds, used only when liq_calibration.json is missing
# or has no entry for this asset. Empirical per-asset thresholds
# (p99 of historical distribution) come from calibrate_liq.py and
# override these at LiqMonitor construction time.
VOLUME_Z_THRESHOLD = 4.0
ONE_SIDED_THRESHOLD = 0.6
PRICE_MOVE_THRESHOLD = 0.003
ROLLING_BAR_WINDOW = 60          # minutes of context for vol-z


def _load_liq_calibration(path: str) -> dict[str, dict]:
    """Read liq_calibration.json once and return per-asset threshold
    dicts. Errors are non-fatal — caller falls back to hardcoded
    defaults."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            payload = json.load(f)
        return payload.get("calibration", {}) or {}
    except Exception as e:
        print(f"[liq] could not parse {path}: {e}; using defaults",
              flush=True)
        return {}


@dataclass
class _AssetState:
    last_bar_ts_emitted: float = 0.0
    recent_volumes: deque = field(default_factory=lambda: deque(maxlen=ROLLING_BAR_WINDOW))


def _aggregate_to_minute_bars(bins: dict[float, dict]) -> list[dict]:
    """Group 1-second bins into 1-minute bars. Each bar dict carries
    {ts, open, close, high, low, buy_vol, sell_vol, volume}."""
    if not bins:
        return []
    by_min: dict[float, list[tuple[float, dict]]] = defaultdict(list)
    for ts, b in bins.items():
        m_ts = math.floor(float(ts) / 60.0) * 60.0
        by_min[m_ts].append((float(ts), b))
    bars = []
    for m_ts in sorted(by_min):
        members = sorted(by_min[m_ts], key=lambda x: x[0])
        mids = [m["mid"] for _, m in members
                if isinstance(m.get("mid"), (int, float)) and m["mid"] > 0]
        if not mids:
            continue
        buy = sum(float(m.get("buy", 0.0)) for _, m in members)
        sell = sum(float(m.get("sell", 0.0)) for _, m in members)
        bars.append({
            "ts": m_ts,
            "open": float(mids[0]),
            "close": float(mids[-1]),
            "high": float(max(mids)),
            "low": float(min(mids)),
            "buy_vol": buy,
            "sell_vol": sell,
            "volume": buy + sell,
        })
    return bars


def _load_bins(path: str) -> dict[float, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as e:
        print(f"[liq] could not load bins {path}: {e}", flush=True)
        return {}


class LiqMonitor:
    """Per-asset liquidation-burst detector reading perp bins.

    calibration_path: path to liq_calibration.json. When present, each
    asset uses its own empirical p99 thresholds (via calibrate_liq.py).
    When missing or asset-not-in-cal, falls back to module-level
    hardcoded defaults.
    """

    def __init__(self, perp_paths: dict[str, str],
                  calibration_path: str | None = None):
        self.perp_paths = dict(perp_paths)
        self._state: dict[str, _AssetState] = {}
        cal = _load_liq_calibration(calibration_path) if calibration_path else {}
        self._thresholds: dict[str, tuple[float, float, float]] = {}
        for asset in self.perp_paths:
            entry = cal.get(asset) or {}
            vol_z = float(entry.get("vol_z_threshold", VOLUME_Z_THRESHOLD))
            one_sided = float(entry.get("one_sided_threshold", ONE_SIDED_THRESHOLD))
            price_move = float(entry.get("price_move_threshold", PRICE_MOVE_THRESHOLD))
            self._thresholds[asset] = (vol_z, one_sided, price_move)
            calibrated = asset in cal
            print(f"[liq] {asset}: vol_z>={vol_z:.2f} |dip|>={one_sided:.2f} "
                  f"|gap|>={price_move*100:.3f}% "
                  f"({'calibrated' if calibrated else 'hardcoded fallback'})",
                  flush=True)

    def _state_for(self, asset: str) -> _AssetState:
        s = self._state.get(asset)
        if s is None:
            s = _AssetState()
            self._state[asset] = s
        return s

    def _thresholds_for(self, asset: str) -> tuple[float, float, float]:
        return self._thresholds.get(
            asset, (VOLUME_Z_THRESHOLD, ONE_SIDED_THRESHOLD, PRICE_MOVE_THRESHOLD))

    def update_asset(self, asset: str) -> dict | None:
        path = self.perp_paths.get(asset)
        if not path:
            return None
        bins = _load_bins(path)
        if not bins:
            return None
        bars = _aggregate_to_minute_bars(bins)
        # Need ROLLING_BAR_WINDOW prior bars + the test bar + the live bar.
        if len(bars) < ROLLING_BAR_WINDOW + 2:
            return None
        # Use the most recent COMPLETE minute (bars[-1] is the live
        # in-progress minute and may be incomplete; bars[-2] is the
        # last fully-closed minute).
        bar = bars[-2]
        st = self._state_for(asset)
        # Don't double-fire on the same bar.
        if bar["ts"] <= st.last_bar_ts_emitted:
            return None

        window = bars[-(ROLLING_BAR_WINDOW + 2):-2]  # ROLLING_BAR_WINDOW prior bars
        if len(window) < ROLLING_BAR_WINDOW:
            return None
        mean_v = sum(b["volume"] for b in window) / len(window)
        var_v = sum((b["volume"] - mean_v) ** 2 for b in window) / len(window)
        std_v = var_v ** 0.5
        if std_v < 1e-9:
            return None

        vol_z = (bar["volume"] - mean_v) / std_v
        total = max(bar["volume"], 1e-9)
        dipole = (bar["buy_vol"] - bar["sell_vol"]) / total
        # Use the gap from the prior bar's close so we catch liquidation
        # prints that consume a price level — those typically clear
        # mostly at the new level (in-bar high == in-bar low) so a
        # close-vs-open metric would miss them.
        prior_close = window[-1]["close"] if window else 0.0
        if prior_close > 0:
            price_move = (bar["close"] - prior_close) / prior_close
        else:
            price_move = 0.0

        vol_thr, dip_thr, gap_thr = self._thresholds_for(asset)
        if (vol_z >= vol_thr
                and abs(dipole) >= dip_thr
                and abs(price_move) >= gap_thr):
            direction = "UP" if (dipole > 0 and price_move > 0) else \
                ("DOWN" if (dipole < 0 and price_move < 0) else None)
            if direction is None:
                # Mismatched dipole/price-move (shouldn't happen
                # in a clean burst). Skip rather than emit garbage.
                return None
            st.last_bar_ts_emitted = bar["ts"]
            return {
                "type": f"LIQ_BURST_{direction}",
                "key": f"{asset}/perp/liq",
                "summary": (f"{asset} perp liquidation-burst {direction} "
                            f"(vol_z={vol_z:+.1f}, dipole={dipole:+.2f}, "
                            f"price_move={price_move*100:+.2f}%)"),
                "asset": asset,
                "bar_ts": float(bar["ts"]),
                "bar_close": float(bar["close"]),
                "vol_z": float(vol_z),
                "dipole": float(dipole),
                "price_move_pct": float(price_move * 100),
                "buy_vol": float(bar["buy_vol"]),
                "sell_vol": float(bar["sell_vol"]),
            }
        return None

    def snapshot(self) -> dict:
        return {
            asset: {
                "last_bar_ts_emitted": float(st.last_bar_ts_emitted),
            }
            for asset, st in self._state.items()
        }
