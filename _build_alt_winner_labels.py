"""_build_alt_winner_labels.py — produce winner-onset labels for cells that have NO live
opportunity log yet (the small coins: SOL/DOGE/XRP, and any new venue), the prerequisite
for per-cell coefficient discovery.

Why this exists: the 128-dim coeff fingerprint thread (S25-S35) is fed by WINNING entry
episodes (winner_onsets.json). Those exist ONLY for the 12 BTC/ETH buy/sell cells, built on
the box from the live mock-replay + hindsight audit. The newly-backfilled alt cells have no
such log. This script reconstructs the SAME winner definition directly off the 1-sec bins so
the alts get a winner_onsets-shaped label set that downstream (_build_onset_coeff_lists ->
arch_workflow coeff discovery) can consume unchanged.

Winner definition (verbatim from the S31 oracle fix, HINDSIGHT_AUDIT_ORACLE_FIX_2026-06-21.md):
  - decision points keyed ASSET|venue|chunk|side at their own ts (here: a fixed minute-bar stride).
  - oracle_entry_price = close at the decision bar.
  - horizon          = per side (buy 360 min / sell 60 min), kept verbatim.
  - best favorable exit within (ts, ts+horizon]: buy = MAX close, sell = MIN close.
  - net_bps          = sign*(exit/entry - 1)*1e4 - 10 bps  (5 bps/side; buy +1 / sell -1).
  - winner           = net_bps > 0.
  Leakage-safe by construction: the exit is bounded to the FORWARD horizon and the
  fingerprint (chunk_id + 6 micros) is computed from VISIBLE (pre-entry) bars only.

PER CELL, never pooled / averaged / smoothed — each (asset,venue,side) is its own bucket and
buy/sell stay separate (bucket-distinctiveness-is-the-goal).

Out per cell: _alt_labels/<asset>_<venue>_<side>_winner_onsets.json (winner_onsets schema) and
              _alt_labels/<asset>_<venue>_opportunities.jsonl (all decision points, win+lose).

Usage:
  python _build_alt_winner_labels.py --bins-path realbins/sol_bybit_perp_bins.json \\
      --asset SOL --venue bybit_perp --stride 128
  # canary against an existing BTC cell (sanity-check the oracle win-rate is plausible):
  python _build_alt_winner_labels.py --bins-path realbins/btc_bybit_perp_bins.json \\
      --asset BTC --venue bybit_perp --canary
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

from markets_adapter import load_minute_bars
from odcore.fingerprint import compute_fingerprint, MICRO_KEYS

HORIZON_MIN = {"buy": 360.0, "sell": 60.0}   # per-side horizons (verbatim from the oracle fix)
FEE_RT_BPS = 10.0                            # 5 bps/side round-trip
VIS_LOOKBACK_BARS = 1024                     # bars visible to the fingerprint chunker (recent; bounds cost,
                                             # >> max_window 256 so the current chunk is fully contained)
OUT = Path("_alt_labels")


def oracle_net_bps(closes: np.ndarray, ts: np.ndarray, i: int, side: str) -> float | None:
    """Best favorable exit within the side's horizon, net of fees. Forward-only (no look-ahead)."""
    entry = closes[i]
    if entry <= 0:
        return None
    t_end = ts[i] + HORIZON_MIN[side] * 60.0
    j_hi = int(np.searchsorted(ts, t_end, side="right"))
    fwd = closes[i + 1:j_hi]
    if fwd.size == 0:
        return None
    if side == "buy":
        exit_p = float(fwd.max()); sgn = 1.0
    else:
        exit_p = float(fwd.min()); sgn = -1.0
    return sgn * (exit_p / entry - 1.0) * 1e4 - FEE_RT_BPS


def label_cell(bins_path: str, asset: str, venue: str, side: str, stride: int) -> list[dict]:
    bars = load_minute_bars(bins_path)
    if len(bars) < 64:
        print(f"  [{asset}_{venue}_{side}] too few minute bars ({len(bars)})", flush=True)
        return []
    ts = np.array([b.ts for b in bars], float)
    closes = np.array([b.close for b in bars], float)
    cell = f"{asset.lower()}_{venue.lower()}_{side}"

    winners = []
    n_dec = n_win = 0
    # decision points on a fixed stride; entry at bar i; fingerprint from visible bars only.
    start = max(VIS_LOOKBACK_BARS // 4, 32)
    for i in range(start, len(bars) - 1, stride):
        net = oracle_net_bps(closes, ts, i, side)
        if net is None:
            continue
        n_dec += 1
        if net <= 0:
            continue
        n_win += 1
        visible = bars[max(0, i - VIS_LOOKBACK_BARS): i + 1]   # pre-entry, includes decision bar
        fp = compute_fingerprint(asset.upper(), venue, side, visible)
        if fp is None:
            continue
        onset_ts = float(bars[max(0, i - VIS_LOOKBACK_BARS) + fp.window_start].ts) \
            if fp.window_start < len(visible) else float(ts[i])
        winners.append({
            "cell": cell,
            "source_id": f"{asset.upper()}|{venue.lower()}|{fp.chunk_id}|{side}",
            "side": side, "asset": asset.upper(), "venue": venue,
            "decision_ts_utc": float(ts[i]),
            "true_onset_ts_utc": float(onset_ts),
            "onset_chunk_id": fp.chunk_id,
            "onset_moved": True,
            "onset_micros": {k: float(fp.micros().get(k, 0.0)) for k in MICRO_KEYS},
            "net_bps": round(float(net), 4),
            "horizon_minutes": HORIZON_MIN[side],
        })
    win_rate = (n_win / n_dec) if n_dec else 0.0
    print(f"  [{cell}] decisions={n_dec} winners={n_win} ({win_rate:.1%}) "
          f"emitted={len(winners)}", flush=True)
    return winners


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bins-path", required=True)
    p.add_argument("--asset", required=True, help="e.g. SOL, DOGE, XRP")
    p.add_argument("--venue", required=True, help="e.g. bybit_perp")
    p.add_argument("--sides", default="buy,sell")
    p.add_argument("--stride", type=int, default=128, help="minute-bar stride between decision points")
    p.add_argument("--canary", action="store_true",
                   help="sanity mode: just report the oracle win-rate, write nothing")
    args = p.parse_args()

    OUT.mkdir(exist_ok=True)
    print(f"alt winner-labeling: {args.asset} {args.venue}  bins={args.bins_path}", flush=True)
    opp_path = OUT / f"{args.asset.lower()}_{args.venue.lower()}_opportunities.jsonl"
    opp_f = None if args.canary else open(opp_path, "w")
    total = 0
    for side in [s.strip() for s in args.sides.split(",") if s.strip()]:
        winners = label_cell(args.bins_path, args.asset, args.venue, side, args.stride)
        total += len(winners)
        if args.canary:
            continue
        cell = f"{args.asset.lower()}_{args.venue.lower()}_{side}"
        with open(OUT / f"{cell}_winner_onsets.json", "w") as f:
            json.dump(winners, f, indent=1)
        for w in winners:
            opp_f.write(json.dumps(w) + "\n")
    if opp_f:
        opp_f.close()
        print(f"wrote {total} winner episodes -> {OUT}/  (+ {opp_path.name})", flush=True)
    else:
        print(f"[canary] {total} winners (no files written)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
