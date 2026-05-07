"""
basis_monitor.py — spot-perp basis tracker emitting BASIS_DIVERGENT
drift alerts when (perp - spot) drifts beyond a rolling-z threshold.

Mechanism (per asset):
  1. Pull the freshest spot mid (from a chosen spot venue bins file)
     and the freshest perp mid (from a chosen perp venue bins file).
  2. Compute basis = (perp - spot) / spot in bps.
  3. Maintain a rolling deque of basis observations; z-score against
     the rolling mean+std.
  4. When |z| crosses HOT_THRESHOLD for SUSTAINED_CYCLES consecutive
     polls, fire BASIS_DIVERGENT_HOT (z>0) or BASIS_DIVERGENT_COLD
     (z<0); fire a "CLEARED" alert when |z| falls back under
     CLEAR_THRESHOLD.

Why this matters (per microstructure literature, 2025-2026):
  - Spot-leading-down with perps offside (positive basis) tends to
    precede a perp-side capitulation cascade.
  - Spot-leading-up with negative basis (perps short) tends to
    precede a short-squeeze cascade.
  - Sustained extreme basis is a leverage build-up signal independent
    of regime classification on either venue alone.
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import dataclass, field


# Tunables. Z-thresholds chosen so that ~95th percentile of normal
# basis fluctuation does NOT trip the alert; only persistent
# 2-sigma+ deviations do.
ROLLING_WINDOW_OBS = 240        # ~120 min at 30s poll interval
HOT_THRESHOLD_Z = 2.0
CLEAR_THRESHOLD_Z = 1.0
SUSTAINED_CYCLES = 5            # ~2.5 min at 30s poll
MIN_OBS_FOR_Z = 60              # need ~30 min of history before z-scoring


@dataclass
class _AssetState:
    history: deque = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW_OBS))
    last_basis_bps: float = 0.0
    last_z: float = 0.0
    streak_above_hot: int = 0
    streak_below_cold: int = 0
    current_state: str = "normal"   # "normal" | "hot" | "cold"
    last_alert_ts: float = 0.0


def _read_latest_bin_mid(bins_path: str) -> tuple[float, float]:
    """Return (latest_ts, latest_mid) from a bins JSON file. Falls back
    to (0, 0) if the file is missing or empty. Uses the file's last
    bin (newest ts). Mid prefers (bid+ask)/2 if both present, else
    falls back to whichever of bid/ask/mid/close exists."""
    if not os.path.exists(bins_path):
        return 0.0, 0.0
    try:
        with open(bins_path) as f:
            raw = json.load(f)
    except Exception:
        return 0.0, 0.0
    if not raw:
        return 0.0, 0.0
    try:
        ts_keys = sorted(float(k) for k in raw.keys())
    except Exception:
        return 0.0, 0.0
    if not ts_keys:
        return 0.0, 0.0
    latest_ts = ts_keys[-1]
    bin_ = raw.get(str(latest_ts)) or raw.get(str(int(latest_ts))) or raw.get(repr(latest_ts))
    if bin_ is None:
        # Slow fallback: scan for matching float key as string
        for k, v in raw.items():
            try:
                if float(k) == latest_ts:
                    bin_ = v
                    break
            except Exception:
                continue
    if not isinstance(bin_, dict):
        return latest_ts, 0.0
    bid = float(bin_.get("bid") or 0.0)
    ask = float(bin_.get("ask") or 0.0)
    if bid > 0 and ask > 0:
        return latest_ts, (bid + ask) / 2.0
    for key in ("mid", "close", "last", "price"):
        v = bin_.get(key)
        if v is not None and float(v) > 0:
            return latest_ts, float(v)
    return latest_ts, 0.0


class BasisMonitor:
    """Per-asset spot-perp basis tracker with hysteresis + sustained-
    streak gating.

    spot_paths / perp_paths: dict[asset] -> bins-file path. The monitor
    is venue-agnostic; the caller picks which spot venue and which
    perp venue to compare for each asset.
    """

    def __init__(self, spot_paths: dict[str, str], perp_paths: dict[str, str]):
        self.spot_paths = dict(spot_paths)
        self.perp_paths = dict(perp_paths)
        self._state: dict[str, _AssetState] = {}

    def _state_for(self, asset: str) -> _AssetState:
        s = self._state.get(asset)
        if s is None:
            s = _AssetState()
            self._state[asset] = s
        return s

    def update_asset(self, asset: str) -> dict | None:
        """Pull the latest spot+perp mid, push a new basis observation,
        and return an alert dict iff a state transition occurred.
        Returns None for steady-state polls."""
        spot_path = self.spot_paths.get(asset)
        perp_path = self.perp_paths.get(asset)
        if not spot_path or not perp_path:
            return None
        _, spot_mid = _read_latest_bin_mid(spot_path)
        _, perp_mid = _read_latest_bin_mid(perp_path)
        if spot_mid <= 0 or perp_mid <= 0:
            return None

        basis = (perp_mid - spot_mid) / spot_mid
        basis_bps = basis * 1e4

        st = self._state_for(asset)
        st.history.append(basis_bps)
        st.last_basis_bps = basis_bps

        # Need enough history before z-scoring is meaningful.
        if len(st.history) < MIN_OBS_FOR_Z:
            return None

        mean = sum(st.history) / len(st.history)
        var = sum((x - mean) ** 2 for x in st.history) / len(st.history)
        std = var ** 0.5
        if std < 1e-9:
            return None
        z = (basis_bps - mean) / std
        st.last_z = z

        # Streak counters: consecutive polls above HOT or below -HOT.
        if z >= HOT_THRESHOLD_Z:
            st.streak_above_hot += 1
            st.streak_below_cold = 0
        elif z <= -HOT_THRESHOLD_Z:
            st.streak_below_cold += 1
            st.streak_above_hot = 0
        else:
            st.streak_above_hot = 0
            st.streak_below_cold = 0

        # State machine: emit alert on transition only.
        new_state = st.current_state
        alert_type = None
        if st.current_state != "hot" and st.streak_above_hot >= SUSTAINED_CYCLES:
            new_state = "hot"
            alert_type = "BASIS_DIVERGENT_HOT"
        elif st.current_state != "cold" and st.streak_below_cold >= SUSTAINED_CYCLES:
            new_state = "cold"
            alert_type = "BASIS_DIVERGENT_COLD"
        elif st.current_state != "normal" and abs(z) <= CLEAR_THRESHOLD_Z:
            new_state = "normal"
            alert_type = "BASIS_DIVERGENT_CLEARED"

        if new_state == st.current_state:
            return None

        st.current_state = new_state
        st.last_alert_ts = time.time()

        side_note = "perp premium (overcrowded long)" if z > 0 \
            else ("spot premium (overcrowded short / squeeze risk)" if z < 0
                  else "")
        return {
            "type": alert_type,
            "key": f"{asset}/spot-perp/basis",
            "summary": (f"{asset} spot-perp basis "
                        f"{basis_bps:+.1f}bps (z={z:+.2f}); {side_note}"
                        if alert_type != "BASIS_DIVERGENT_CLEARED"
                        else f"{asset} spot-perp basis cleared (z={z:+.2f})"),
            "asset": asset,
            "basis_bps": float(basis_bps),
            "basis_z": float(z),
            "previous_state": ({
                "normal": "normal", "hot": "hot", "cold": "cold"
            }.get(st.current_state, st.current_state)),
        }

    def snapshot(self) -> dict[str, dict]:
        """Read-only summary for /api/basis-status."""
        out = {}
        for asset, st in self._state.items():
            out[asset] = {
                "n_obs": len(st.history),
                "last_basis_bps": float(st.last_basis_bps),
                "last_basis_z": float(st.last_z),
                "current_state": st.current_state,
                "streak_above_hot": st.streak_above_hot,
                "streak_below_cold": st.streak_below_cold,
            }
        return out
