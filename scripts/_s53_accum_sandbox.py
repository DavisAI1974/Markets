"""_s53_accum_sandbox.py — S53 sandbox: diagnostics + variant sweeps for the Set B accum arm.

Scope (Greg, S53 walkthrough): Set B only — SOL Coinbase, zigzag swing stream. Plan approved:
  A. DIAGNOSTICS (measure, change nothing):
     A1 confirm quality: bps-consumed-since-turn-extreme at confirm + confirm latency, vs net.
     A2 taker fractions: phase-2 taker % and unload taker % vs net.
     A3 false-dump rate: after each dump, would the leg have confirmed before the next turn?
  B. WINNER-HARVEST variants (exit mechanics; same trades, same count) — unload-into-strength rungs,
     tighter slide-cross on extended swings.
  C. ENTRY/EXECUTION variants (not gates): asymmetric dump floor, taker-completion cap.
  D. EXCLUDED per "no gates" (confirm-budget blocker, timeouts, stricter confirm modes).

Both the dipole-gated arm (S52 validated) and the ungated arm are reported for every table —
frequency is part of the score (Greg: the point is $/hr; gates cost legs/hr).
All rows: full leg population on the window, front-of-queue primary + Q1 honest bracket where it
matters, shuffle + reversed controls on variant sweeps. ONE window — nothing here is a deploy verdict.
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.swing_accum import simulate_swing_accum
from _capacity_model import FLOW_W
from importlib import import_module
_h2h = import_module("_s52_accum_vs_oneshot")

PATH = "/tmp/sol_coinbase_book.jsonl.gz"
K, GRACE, MK, TK, SMAX = 1, 300, -1.0, 5.0, 5000.0


def load_cell():
    raw = load_book(PATH)
    ch, g = build_channels(PATH, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(PATH, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    theta = _h2h.ZIG_K * (hs + TK)
    flips = _h2h._price_zigzag(mid, theta)
    gdip = _h2h._dipole_gate(flips, mid, buy, sell)
    return mid, bb, ba, buy, sell, hs, hrs, theta, flips, gdip


def rolling_conf_bps(flips, mid, hs, confirm_k=0.25, swing_roll=100):
    """Replicates the executor's causal rolling-median swing stat -> conf_bps per flip index."""
    n = len(mid)
    fee_floor = hs + TK
    swings, med = [], np.full(len(flips), np.nan)
    for k in range(1, len(flips)):
        a, b = flips[k - 1][0], flips[k][0]
        if 0 < a < b < n:
            swings.append(abs(mid[b] - mid[a]) / mid[a] * 1e4)
            lo = max(0, len(swings) - swing_roll)
            med[k] = float(np.median(swings[lo:]))
    conf = np.where(np.isfinite(med), np.maximum(fee_floor, confirm_k * med), fee_floor)
    return conf


def _corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5:
        return float("nan")
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


def _quartile_table(vals, nets, label):
    vals, nets = np.asarray(vals, float), np.asarray(nets, float)
    ok = np.isfinite(vals)
    vals, nets = vals[ok], nets[ok]
    if len(vals) < 8:
        print(f"    {label}: n={len(vals)} too thin for quartiles")
        return
    qs = np.quantile(vals, [0.25, 0.5, 0.75])
    b = np.digitize(vals, qs)
    print(f"    {label}  (n={len(vals)}, corr vs net {_corr(vals, nets):+.2f})")
    for q in range(4):
        m = b == q
        if m.any():
            print(f"      Q{q+1} [{vals[m].min():8.2f}..{vals[m].max():8.2f}]  n={m.sum():3d}  "
                  f"med net ${np.median(nets[m]):+7.2f}  mean ${nets[m].mean():+7.2f}  "
                  f"win {(nets[m] > 0).mean()*100:3.0f}%")


def diagnostics(mid, bb, ba, buy, sell, hs, hrs, flips, gdip):
    pivot_of = {int(c): int(p) for (c, p, s) in flips}
    side_of = {int(c): int(s) for (c, p, s) in flips}
    conf_of = rolling_conf_bps(flips, mid, hs)
    confmap = {int(flips[k][0]): float(conf_of[k]) for k in range(len(flips))}
    flip_cells = np.asarray([int(c) for (c, p, s) in flips])

    for gname, gmask in (("dipole (S52 validated arm)", gdip), ("ungated", None)):
        r = simulate_swing_accum(mid, bb, ba, buy, sell, flips, half_spread_bps=hs,
                                 maker_fee_bps=MK, taker_fee_bps=TK, S_max=SMAX,
                                 unload_grace=GRACE, queue_frac=0.0, entry_ok=gmask, arm=gname)
        legs = r.legs
        nets = np.asarray([l.net_usd for l in legs])
        print(f"\n== DIAGNOSTICS [{gname}] legs={r.n_legs} conf={r.n_confirmed} dump={r.n_dumped} "
              f"net ${r.net_usd:+.2f} (${r.net_usd/hrs:+.2f}/hr) win {r.win_frac*100:.0f}% ==")

        # A1: confirm quality (confirmed legs only)
        consumed, latency, cnets = [], [], []
        for l in legs:
            if not l.confirmed or l.confirm_idx < 0:
                continue
            piv = pivot_of.get(l.flip_idx)
            if piv is None:
                continue
            consumed.append(abs(mid[l.confirm_idx] - mid[piv]) / mid[piv] * 1e4)
            latency.append((l.confirm_idx - l.flip_idx) / 10.0)
            cnets.append(l.net_usd)
        print("  A1 confirm quality (confirmed legs):")
        _quartile_table(consumed, cnets, "bps consumed extreme->confirm")
        _quartile_table(latency, cnets, "confirm latency (s)")

        # A2: taker fractions
        p2f, unf, allf_, cnets2 = [], [], [], []
        for l in legs:
            if not l.confirmed:
                continue
            p2 = l.phase2_maker_usd + l.phase2_taker_usd
            un = l.unload_maker_usd + l.unload_taker_usd
            tot = l.maker_usd + l.taker_usd
            p2f.append(l.phase2_taker_usd / p2 if p2 > 0 else np.nan)
            unf.append(l.unload_taker_usd / un if un > 0 else np.nan)
            allf_.append(l.taker_usd / tot if tot > 0 else np.nan)
            cnets2.append(l.net_usd)
        print("  A2 taker fractions (confirmed legs):")
        _quartile_table(p2f, cnets2, "phase-2 taker fraction")
        _quartile_table(unf, cnets2, "unload taker fraction")
        _quartile_table(allf_, cnets2, "total taker share")

        # A3: false dumps — would the confirm have fired in the remaining segment?
        n_dump = n_false = 0
        dump_net = false_net = 0.0
        for l in legs:
            if not l.dumped:
                continue
            n_dump += 1
            dump_net += l.net_usd
            ci, tr, s = l.flip_idx, l.close_flip_idx, l.side
            ref = mid[ci]
            cb = confmap.get(ci, hs + TK)
            nxt_after = flip_cells[flip_cells > ci]
            nxt = int(nxt_after[0]) if len(nxt_after) else len(mid) - 1
            seg = mid[tr:nxt]
            if len(seg) == 0:
                continue
            green = (seg >= ref * (1 + cb / 1e4)) if s > 0 else (seg <= ref * (1 - cb / 1e4))
            if green.any():
                n_false += 1
                false_net += l.net_usd
        print(f"  A3 false dumps: {n_false}/{n_dump} dumps would have CONFIRMED before the next turn "
              f"({100*n_false/max(1,n_dump):.0f}%)  [dump col total ${dump_net:+.2f}, "
              f"false-dump share ${false_net:+.2f}]")


def main():
    mid, bb, ba, buy, sell, hs, hrs, theta, flips, gdip = load_cell()
    print(f"[sol_coinbase] {hrs:.2f}h  hs {hs:.2f}bps  zigzag theta {theta:.1f}bps  "
          f"flips {len(flips)} ({len(flips)/hrs:.1f}/hr)  dipole pass {gdip.mean()*100:.0f}%")
    diagnostics(mid, bb, ba, buy, sell, hs, hrs, flips, gdip)


if __name__ == "__main__":
    main()
