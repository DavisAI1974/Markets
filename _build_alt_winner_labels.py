"""_build_alt_winner_labels.py — winner-onset labels for cells with NO live opportunity log
(the small coins SOL/DOGE/XRP, any new venue), computed entirely on 1-SECOND bins.

Why this exists: the 128-dim coeff fingerprint thread (S25-S35) is fed by WINNING entry
episodes (winner_onsets.json), which existed only for the 12 BTC/ETH cells (built on the box
from the live mock-replay). The backfilled alt cells have no such log, so coeff discovery had
nothing to discover FROM. This reconstructs the SAME winner definition directly off the bins.

1-SECOND, NOT minute (Greg, S38): aggregating 1-sec bins to minute bars smooths away the sub-
minute order-flow structure that carries the timing edge (S36b: 1-sec enters ~5-6 bps off the
turn vs ~9-11 at 1-min). The earlier minute-bar version (load_minute_bars + MarketChunker) was
the regime-classifier machinery and is NOT used here. Everything below runs on the per-second
BinSeries (odcore.io.load_bins): the oracle exit, the onset, and the micros.

Winner definition (verbatim from the S31 oracle fix, on 1-sec mid):
  - decision points keyed ASSET|venue|onset|side at a fixed 1-sec stride.
  - oracle_entry = mid at the decision second.
  - horizon      = per side (buy 360 / sell 60 min), verbatim.
  - best favorable exit within (t, t+horizon] on 1-sec mid: buy = MAX, sell = MIN.
  - net_bps      = sign*(exit/entry - 1)*1e4 - 10 bps (5 bps/side; buy +1 / sell -1).
  - winner       = net_bps > 0.
  Leakage-safe: exit is forward-bounded; micros use the pre-entry 1-sec window only.

PER CELL, never pooled / averaged / smoothed; buy/sell stay separate.

Out per cell: _alt_labels/<asset>_<venue>_<side>_winner_onsets.json (winner_onsets schema) and
              _alt_labels/<asset>_<venue>_opportunities.jsonl (the winners, one per line).

Usage:
  python _build_alt_winner_labels.py --bins-path realbins/sol_bybit_perp_bins.json \\
      --asset SOL --venue bybit_perp
  # canary on a BTC cell (sanity-check oracle win-rate):
  python _build_alt_winner_labels.py --bins-path realbins/btc_bybit_perp_bins.json \\
      --asset BTC --venue bybit_perp --canary
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from odcore.io import load_bins
from odcore.info_dipole import signed_flow_features
from odcore.fingerprint import signed_bps

HORIZON_SEC = {"buy": 360 * 60, "sell": 60 * 60}   # per-side horizons (verbatim from the oracle fix)
FEE_RT_BPS = 10.0                                   # 5 bps/side round-trip
PREENTRY_SEC = 30 * 60                              # 30-min pre-entry window (1-sec resolution)
CURRENT_SEC = 60                                    # "current chunk" head window
RECENT_SEC = 300                                    # "recent" tail window
DECISION_STRIDE_SEC = 600                           # a decision point every 10 min
OUT = Path("_alt_labels")


def oracle_net_bps(mid: np.ndarray, i: int, horizon_sec: int, side: str) -> float | None:
    """Best favorable exit within the side's horizon on 1-sec mid, net of fees. Forward-only."""
    entry = mid[i]
    if entry <= 0:
        return None
    fwd = mid[i + 1: i + 1 + horizon_sec]
    fwd = fwd[fwd > 0]
    if fwd.size == 0:
        return None
    exit_p, sgn = (float(fwd.max()), 1.0) if side == "buy" else (float(fwd.min()), -1.0)
    return sgn * (exit_p / entry - 1.0) * 1e4 - FEE_RT_BPS


def onset_micros_1s(bs, i: int, side: str) -> dict:
    """The 6 winner_onsets micros computed on the pre-entry 1-second window (no look-ahead)."""
    lo = max(0, i - PREENTRY_SEC)
    buy, sell, mid = bs.buy[lo:i + 1], bs.sell[lo:i + 1], bs.mid[lo:i + 1]
    # per-second order-flow dipole over the window
    tot = buy + sell
    dip = np.where(tot > 0, (buy - sell) / np.maximum(tot, 1e-12), 0.0)
    mean_dipole = float(dip.mean()) if dip.size else 0.0
    if dip.size > 2 and dip.std() > 0:
        d = dip - dip.mean()
        dipole_acl1 = float(np.dot(d[:-1], d[1:]) / np.dot(d, d))
    else:
        dipole_acl1 = 0.0
    vol = tot
    if vol.size > 1 and vol.std() > 0:
        recent_vol = vol[-CURRENT_SEC:].mean()
        volume_zscore = float((recent_vol - vol.mean()) / vol.std())
    else:
        volume_zscore = 0.0
    entry_mid = float(bs.mid[i])
    onset_mid = float(bs.mid[lo]) if bs.mid[lo] > 0 else entry_mid
    rec_mid = float(bs.mid[max(0, i - RECENT_SEC)])
    cur_mid = float(bs.mid[max(0, i - CURRENT_SEC)])
    return {
        "trade_current_chunk_bps": signed_bps(cur_mid, entry_mid, side),
        "trade_recent_2chunk_bps": signed_bps(rec_mid, entry_mid, side),
        "trade_from_onset_bps": signed_bps(onset_mid, entry_mid, side),
        "mean_dipole": mean_dipole, "dipole_acl1": dipole_acl1,
        "volume_zscore": volume_zscore,
    }


def label_cell(bs, asset: str, venue: str, side: str, canary: bool) -> list[dict]:
    cell = f"{asset.lower()}_{venue.lower()}_{side}"
    mid = bs.mid
    hz = HORIZON_SEC[side]
    n = len(bs)
    winners, n_dec, n_win = [], 0, 0
    for i in range(PREENTRY_SEC, n - 1, DECISION_STRIDE_SEC):
        net = oracle_net_bps(mid, i, hz, side)
        if net is None:
            continue
        n_dec += 1
        if net <= 0:
            continue
        n_win += 1
        if canary:
            continue
        lo = max(0, i - PREENTRY_SEC)
        flow = signed_flow_features(bs.buy[lo:i + 1], bs.sell[lo:i + 1])
        if flow is None:
            continue
        onset_ts = int(bs.ts[lo])
        dts_i = int(bs.ts[i])
        chunk_id = hashlib.sha256(
            f"{venue.lower()}-{asset.upper()}:{onset_ts}:{dts_i}".encode()).hexdigest()[:16]
        winners.append({
            "cell": cell,
            # decision_ts embedded so source_id is UNIQUE per episode (S35 collision fix:
            # a chunk-keyed id alone recurs across episodes -> overwrites in the coeff index).
            "source_id": f"{asset.upper()}|{venue.lower()}|{chunk_id}_{dts_i}|{side}",
            "side": side, "asset": asset.upper(), "venue": venue,
            "decision_ts_utc": float(bs.ts[i]),
            "true_onset_ts_utc": float(onset_ts),
            "onset_chunk_id": chunk_id,
            "onset_moved": True,
            "onset_micros": onset_micros_1s(bs, i, side),
            "flow_features": {k: float(v) for k, v in flow.items()},
            "net_bps": round(float(net), 4),
            "horizon_minutes": HORIZON_SEC[side] / 60.0,
            "bar_resolution": "1s",
        })
    wr = (n_win / n_dec) if n_dec else 0.0
    print(f"  [{cell}] decisions={n_dec} winners={n_win} ({wr:.1%}) emitted={len(winners)}", flush=True)
    return winners


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bins-path", required=True)
    p.add_argument("--asset", required=True)
    p.add_argument("--venue", required=True)
    p.add_argument("--sides", default="buy,sell")
    p.add_argument("--canary", action="store_true")
    args = p.parse_args()

    OUT.mkdir(exist_ok=True)
    print(f"alt winner-labeling (1-SECOND bars): {args.asset} {args.venue}  bins={args.bins_path}",
          flush=True)
    bs = load_bins(args.bins_path)
    print(f"  loaded {len(bs)} 1-sec bins ({(bs.ts[-1]-bs.ts[0])/86400:.1f}d)", flush=True)

    opp = None if args.canary else open(OUT / f"{args.asset.lower()}_{args.venue.lower()}_opportunities.jsonl", "w")
    total = 0
    for side in [s.strip() for s in args.sides.split(",") if s.strip()]:
        winners = label_cell(bs, args.asset, args.venue, side, args.canary)
        total += len(winners)
        if args.canary:
            continue
        cell = f"{args.asset.lower()}_{args.venue.lower()}_{side}"
        with open(OUT / f"{cell}_winner_onsets.json", "w") as f:
            json.dump(winners, f, indent=1)
        for w in winners:
            opp.write(json.dumps(w) + "\n")
    if opp:
        opp.close()
        print(f"wrote {total} winner episodes -> {OUT}/", flush=True)
    else:
        print(f"[canary] {total} winners (no files written)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
