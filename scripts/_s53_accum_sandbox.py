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

# cross-cell rerun: same cell params as the S52 head-to-head (Coinbase mk-1/tk5; Bybit MM3 target tier)
CELLS = [
    ("sol_coinbase",  "/tmp/sol_coinbase_book.jsonl.gz",  1, 300, -1.0, 5.0),
    ("eth_coinbase",  "/tmp/eth_coinbase_book.jsonl.gz",  1, 300, -1.0, 5.0),
    ("btc_coinbase",  "/tmp/btc_coinbase_book.jsonl.gz", 10, 300, -1.0, 5.0),
    ("doge_coinbase", "/tmp/doge_coinbase_book.jsonl.gz", 1, 600, -1.0, 5.0),
    ("xrp_coinbase",  "/tmp/xrp_coinbase_book.jsonl.gz",  1, 300, -1.0, 5.0),
    ("sol_bybit",     "/tmp/sol_bybit_book.jsonl.gz",     1, 300, -1.25, 5.5),
    ("eth_bybit",     "/tmp/eth_bybit_book.jsonl.gz",     1, 300, -1.25, 5.5),
]


def load_cell(path=PATH, k=K, tk=TK):
    raw = load_book(path)
    ch, g = build_channels(path, k, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    theta = _h2h.ZIG_K * (hs + tk)
    flips = _h2h._price_zigzag(mid, theta)
    gdip = _h2h._dipole_gate(flips, mid, buy, sell)
    return mid, bb, ba, buy, sell, hs, hrs, theta, flips, gdip


def rolling_conf_bps(flips, mid, hs, confirm_k=0.25, swing_roll=100, tk=TK):
    """Replicates the executor's causal rolling-median swing stat -> conf_bps per flip index."""
    n = len(mid)
    fee_floor = hs + tk
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


VARIANTS = [
    ("base (S52)",            {}),
    ("C2 dump x0.75",         {"dump_mult": 0.75}),
    ("C2 dump x1.5",          {"dump_mult": 1.5}),
    ("C2 dump x2.0",          {"dump_mult": 2.0}),
    ("C2 dump x3.0",          {"dump_mult": 3.0}),
    ("C3 taker cap 0",        {"p2_taker_cap": 0.0}),
    ("C3 taker cap 0.5",      {"p2_taker_cap": 0.5}),
    ("B1 rungs 1/2/3",        {"harvest_rungs": [(1.0, 0.33), (2.0, 0.33), (3.0, 0.34)]}),
    ("B1 rung 2x half",       {"harvest_rungs": [(2.0, 0.5)]}),
    ("B2 slideX x0.5",        {"slide_x_mult": 0.5}),
    ("B2 slideX x2.0",        {"slide_x_mult": 2.0}),
]


def sweep(mid, bb, ba, buy, sell, hs, hrs, flips, gdip):
    rng = np.random.default_rng(7)
    gshuf = rng.permutation(gdip)
    rflips = [(c, p, -s) for (c, p, s) in flips]
    base_kw = dict(half_spread_bps=hs, maker_fee_bps=MK, taker_fee_bps=TK, S_max=SMAX,
                   unload_grace=GRACE)

    def run(fl, g, qf, **kw):
        r = simulate_swing_accum(mid, bb, ba, buy, sell, fl, queue_frac=qf, entry_ok=g,
                                 **base_kw, **kw)
        tak = r.taker_usd / max(1.0, r.maker_usd + r.taker_usd)
        return dict(dphr=r.net_usd / hrs, legs=r.n_legs, win=r.win_frac,
                    conf=r.n_confirmed / max(1, r.n_legs), dump=r.n_dumped / max(1, r.n_legs),
                    tak=tak)

    print("\n== S53 VARIANT SWEEP (SOL Coinbase zigzag window; $/hr; one window — no deploy verdicts) ==")
    print(f"{'variant':18s} {'dipole':>8s} {'ungated':>8s} {'shuffle':>8s} {'REVERSED':>8s} "
          f"{'Q1dip':>8s}   legs win% conf% dump% taker%")
    out = {}
    for name, kw in VARIANTS:
        d = run(flips, gdip, 0.0, **kw)
        u = run(flips, None, 0.0, **kw)
        sh = run(flips, gshuf, 0.0, **kw)
        rv = run(rflips, gdip, 0.0, **kw)
        q1 = run(flips, gdip, 1.0, **kw)
        out[name] = dict(dipole=d, ungated=u, shuffle=sh, reversed=rv, q1=q1)
        print(f"{name:18s} {d['dphr']:+8.2f} {u['dphr']:+8.2f} {sh['dphr']:+8.2f} {rv['dphr']:+8.2f} "
              f"{q1['dphr']:+8.2f}   {d['legs']:3d}  {d['win']*100:3.0f}  {d['conf']*100:3.0f}  "
              f"{d['dump']*100:3.0f}  {d['tak']*100:3.0f}")
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_s53_accum_sandbox_results.json"), "w") as f:
        json.dump(out, f, indent=2, default=float)
    return out


CANDIDATES = [
    ("base",     {}),
    ("d1.5",     {"dump_mult": 1.5}),
    ("d3.0",     {"dump_mult": 3.0}),
    ("cap0",     {"p2_taker_cap": 0.0}),
    ("stack",    {"dump_mult": 3.0, "p2_taker_cap": 0.0, "slide_x_mult": 2.0}),
]


def run_cells():
    """Cross-cell generalization check (Greg, S53): mechanism or SOL quirk? Per cell: A3 false-dump
    rate + A2 taker corr on the base dipole arm, then base vs candidate configs with full controls.
    Decision rule (stated up front): candidate graduates to 'awaiting time-OOS' only if the false-dump
    mechanism shows broadly AND the lift holds on most cells; SOL-only => window/cell noise."""
    allout = {}
    for (cell, path, k, grace, mk, tk) in CELLS:
        if not os.path.exists(path):
            print(f"\n[{cell}] no book"); continue
        mid, bb, ba, buy, sell, hs, hrs, theta, flips, gdip = load_cell(path, k, tk)
        print(f"\n[{cell}] {hrs:.2f}h  hs {hs:.2f}bps  theta {theta:.1f}bps  flips {len(flips)} "
              f"({len(flips)/hrs:.1f}/hr)  dipole pass {gdip.mean()*100:.0f}%")
        if len(flips) < 20:
            print(f"  TOO THIN ({len(flips)} flips) — reported, not scored"); continue
        rng = np.random.default_rng(7)
        gshuf = rng.permutation(gdip)
        rflips = [(c, p, -s) for (c, p, s) in flips]
        base_kw = dict(half_spread_bps=hs, maker_fee_bps=mk, taker_fee_bps=tk, S_max=SMAX,
                       unload_grace=grace)

        # diagnostics-lite on the base dipole arm: A3 false-dump rate + A2 taker corr
        r0 = simulate_swing_accum(mid, bb, ba, buy, sell, flips, queue_frac=0.0, entry_ok=gdip,
                                  **base_kw)
        conf_of = rolling_conf_bps(flips, mid, hs, tk=tk)
        confmap = {int(flips[j][0]): float(conf_of[j]) for j in range(len(flips))}
        flip_cells = np.asarray([int(c) for (c, p, s) in flips])
        n_dump = n_false = 0
        for l in r0.legs:
            if not l.dumped:
                continue
            n_dump += 1
            ref, cb = mid[l.flip_idx], confmap.get(l.flip_idx, hs + tk)
            nx = flip_cells[flip_cells > l.flip_idx]
            nx = int(nx[0]) if len(nx) else len(mid) - 1
            seg = mid[l.close_flip_idx:nx]
            if len(seg) and ((seg >= ref * (1 + cb / 1e4)).any() if l.side > 0
                             else (seg <= ref * (1 - cb / 1e4)).any()):
                n_false += 1
        tf = [l.taker_usd / max(1.0, l.maker_usd + l.taker_usd) for l in r0.legs if l.confirmed]
        tn = [l.net_usd for l in r0.legs if l.confirmed]
        print(f"  diag: false dumps {n_false}/{n_dump} ({100*n_false/max(1,n_dump):.0f}%)  "
              f"taker-share corr vs net {_corr(tf, tn):+.2f}  (n_conf={len(tn)})")

        rows = {}
        print(f"  {'config':8s} {'dipole':>8s} {'shuffle':>8s} {'REVERSED':>8s} {'Q1dip':>8s}  legs win% dump%")
        for name, kw in CANDIDATES:
            d = simulate_swing_accum(mid, bb, ba, buy, sell, flips, queue_frac=0.0, entry_ok=gdip,
                                     **base_kw, **kw)
            s_ = simulate_swing_accum(mid, bb, ba, buy, sell, flips, queue_frac=0.0, entry_ok=gshuf,
                                      **base_kw, **kw)
            r_ = simulate_swing_accum(mid, bb, ba, buy, sell, rflips, queue_frac=0.0, entry_ok=gdip,
                                      **base_kw, **kw)
            q_ = simulate_swing_accum(mid, bb, ba, buy, sell, flips, queue_frac=1.0, entry_ok=gdip,
                                      **base_kw, **kw)
            rows[name] = dict(dipole=d.net_usd / hrs, shuffle=s_.net_usd / hrs,
                              reversed=r_.net_usd / hrs, q1=q_.net_usd / hrs, legs=d.n_legs,
                              win=d.win_frac, dump=d.n_dumped / max(1, d.n_legs))
            print(f"  {name:8s} {rows[name]['dipole']:+8.2f} {rows[name]['shuffle']:+8.2f} "
                  f"{rows[name]['reversed']:+8.2f} {rows[name]['q1']:+8.2f}  {d.n_legs:3d}  "
                  f"{d.win_frac*100:3.0f}  {rows[name]['dump']*100:3.0f}")
        allout[cell] = dict(hrs=hrs, theta=theta, n_flips=len(flips),
                            false_dump=f"{n_false}/{n_dump}", taker_corr=_corr(tf, tn), rows=rows)
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_s53_accum_crosscell_results.json"), "w") as f:
        json.dump(allout, f, indent=2, default=float)
    return allout


def main():
    if "--cells" in sys.argv:
        run_cells()
        return
    mid, bb, ba, buy, sell, hs, hrs, theta, flips, gdip = load_cell()
    print(f"[sol_coinbase] {hrs:.2f}h  hs {hs:.2f}bps  zigzag theta {theta:.1f}bps  "
          f"flips {len(flips)} ({len(flips)/hrs:.1f}/hr)  dipole pass {gdip.mean()*100:.0f}%")
    if "--sweep" in sys.argv:
        sweep(mid, bb, ba, buy, sell, hs, hrs, flips, gdip)
    else:
        diagnostics(mid, bb, ba, buy, sell, hs, hrs, flips, gdip)


if __name__ == "__main__":
    main()
