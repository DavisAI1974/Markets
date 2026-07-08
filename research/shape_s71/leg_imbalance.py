"""S74 LEG-IMBALANCE characterization (Greg's clarified spec).
Whole TRADE legs (4 cells kept separate, per-cell AVERAGE like the original archetype graphs), each leg
EXTENDED turn-to-turn: from the VALLEY where it is born, through the PEAK (onset), to the exhaustion at
close. TWO imbalance channels tracked THROUGH the whole leg (beginning->end):
  TRADE imbalance = rolling (buy-sell)/(buy+sell)      [Greg: likely the SHORT vs LONG decider]
  BOOK  imbalance = rolling (bidK-askK)/(bidK+askK)     [Greg: value at the START (valley) and END (peak)]
Both signed to the trade's side. Reports per cell: each channel at the VALLEY (birth), PEAK (onset), and
EXHAUSTION (close); whether TRADE imbalance separates short vs long; and saves the per-cell average
whole-leg arcs (turn-to-turn) as a PNG. LIVE decision path (run_kraken_cell). Shape/RATIO only. doge excluded.
"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import load_raw, rolling_imb, build_channels, median_spread_bps, run_kraken_cell, KRAKEN, CPS
from whole_legs import ignition_idx, resample
from fit_shapes import best_form, fmt_form, limb_stats, flatten_point
SMOOTH_SEC = 20; NRS = 100; LOOKBACK = 150 * CPS
COINS = ["sol", "btc", "eth", "xrp"]
LEVELS = [1, 5, 10]
CELLS = ["short-win", "short-lose", "long-win", "long-lose"]


def rolling_ratio(num_ch, den_a, den_b, w_sec):
    """Smoothed ratio (a-b)/(a+b) over a w_sec rolling window (same style as rolling_imb)."""
    w = int(w_sec * CPS)
    r = np.zeros(len(den_a)); den = den_a + den_b; nz = den > 0
    r[nz] = num_ch[nz] / den[nz]
    c = np.concatenate([[0.], np.cumsum(r)]); ix = np.arange(len(r)); lo = np.maximum(ix + 1 - w, 0)
    return (c[ix + 1] - c[lo]) / (ix + 1 - lo)


def extract(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"; cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0; N = len(mid); hours = N * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)                      # LIVE legs
    timb = rolling_imb(buy, sell, SMOOTH_SEC)                                      # TRADE-flow imbalance
    bimb = {K: rolling_ratio(np.asarray(g["bidK"][K], float) - np.asarray(g["askK"][K], float),
                             np.asarray(g["bidK"][K], float), np.asarray(g["askK"][K], float), SMOOTH_SEC)
            for K in LEVELS}                                                       # BOOK-depth imbalance/level
    legs = sorted(res.legs, key=lambda z: int(z.open_idx)); prev_close = -1
    rows = []
    for l in legs:
        o = int(l.open_idx); c = int(l.close_idx); s = int(l.side)
        if c <= o:
            continue
        lo = max(0, o - LOOKBACK, prev_close + 1)
        seg = timb[lo:o + 1] * s
        if len(seg) < 30:
            prev_close = c; continue
        ig = ignition_idx(seg); birth = lo + ig
        prev_close = c
        tp = timb[birth:o + 1] * s; tt = timb[o:c + 1] * s                        # trade: pre-fire, tail
        if len(tp) < 12 or len(tt) < 4:
            continue
        row = dict(net=float(l.net_bps), dur=(c - o) * 0.1, side=s,
                   pre_ext=(o - birth) * 0.1, tail_ext=(c - o) * 0.1,
                   t_valley=float(tp[0]), t_peak=float(tp[-1]), t_exh=float(tt[-1]),
                   t_pre_mean=float(tp.mean()), t_tail_mean=float(tt.mean()),
                   t_pre_arc=resample(tp), t_tail_arc=resample(tt),
                   # RAW (unsigned) trade imbalance at valley/peak -> DIRECTION test (buy vs sell side)
                   traw_valley=float(tp[0]) * s, traw_peak=float(tp[-1]) * s)
        for K in LEVELS:
            bp = bimb[K][birth:o + 1] * s; bt = bimb[K][o:c + 1] * s               # book: pre-fire, tail (signed)
            row[f"b{K}_valley"] = float(bp[0]); row[f"b{K}_peak"] = float(bp[-1]); row[f"b{K}_exh"] = float(bt[-1])
            row[f"b{K}_pre_arc"] = resample(bp); row[f"b{K}_tail_arc"] = resample(bt)
            if K == 5:
                row["braw5_valley"] = float(bp[0]) * s; row["braw5_peak"] = float(bp[-1]) * s
        rows.append(row)
    return rows, hours


def cell_masks(net, dur):
    win = net > 0; med = np.median(dur); short = dur < med
    return {"short-win": short & win, "short-lose": short & ~win,
            "long-win": ~short & win, "long-lose": ~short & ~win}, med


def main():
    coins = sys.argv[1:] or COINS
    for coin in coins:
        print(f"\n======================= {coin.upper()} =======================", flush=True)
        rows, hours = extract(coin)
        n = len(rows); net = np.array([r["net"] for r in rows]); dur = np.array([r["dur"] for r in rows])
        masks, med = cell_masks(net, dur)
        base_win = (net > 0).mean() * 100
        print(f"  legs={n}  {hours:.1f}h  base-win%={base_win:.1f}  median-dur={med:.0f}s", flush=True)
        F = lambda k: np.array([r[k] for r in rows])

        # ---- TRADE imbalance: valley / peak / exhaustion + is it the short/long decider? ----
        print("\n  TRADE imbalance (buy/sell), signed to side  [valley=birth, peak=onset, exh=close]:", flush=True)
        print(f"    {'cell':11}{'n':>5}{'valley':>9}{'peak':>9}{'exh':>9}{'pre_mean':>10}{'tail_mean':>10}{'pre_ext':>9}", flush=True)
        for cell in CELLS:
            m = masks[cell]
            if not m.sum():
                continue
            print(f"    {cell:11}{int(m.sum()):>5}{F('t_valley')[m].mean():>9.3f}{F('t_peak')[m].mean():>9.3f}"
                  f"{F('t_exh')[m].mean():>9.3f}{F('t_pre_mean')[m].mean():>10.3f}{F('t_tail_mean')[m].mean():>10.3f}"
                  f"{F('pre_ext')[m].mean():>9.1f}", flush=True)
        sh = masks["short-win"] | masks["short-lose"]; lo_ = masks["long-win"] | masks["long-lose"]
        print("    [duration] SHORT-dur vs LONG-dur cells (signed-to-side imbalance):", flush=True)
        for k in ("t_valley", "t_peak", "t_pre_mean"):
            a, b = F(k)[sh].mean(), F(k)[lo_].mean()
            print(f"      {k:12}: short-dur={a:+.3f} long-dur={b:+.3f} gap={a-b:+.3f}", flush=True)
        # ---- DIRECTION test: does RAW trade imbalance decide the trade SIDE (buy vs sell)? ----
        sd = F("side"); buy = sd > 0; sell = sd < 0
        print(f"    [direction] BUY-side (n={int(buy.sum())}) vs SELL-side (n={int(sell.sum())}) RAW (unsigned) imbalance:", flush=True)
        for k, lbl in (("traw_valley", "trade valley"), ("traw_peak", "trade peak"),
                       ("braw5_valley", "book5 valley"), ("braw5_peak", "book5 peak")):
            a, b = F(k)[buy].mean(), F(k)[sell].mean()
            print(f"      {lbl:13}: buy={a:+.3f} sell={b:+.3f} gap={a-b:+.3f}", flush=True)

        # ---- BOOK imbalance: valley / peak / exhaustion, per level ----
        for K in LEVELS:
            print(f"\n  BOOK imbalance K={K} (bid/ask depth), signed  [valley, peak, exh]:", flush=True)
            print(f"    {'cell':11}{'valley':>9}{'peak':>9}{'exh':>9}", flush=True)
            for cell in CELLS:
                m = masks[cell]
                if not m.sum():
                    continue
                print(f"    {cell:11}{F(f'b{K}_valley')[m].mean():>9.3f}{F(f'b{K}_peak')[m].mean():>9.3f}"
                      f"{F(f'b{K}_exh')[m].mean():>9.3f}", flush=True)

        # ---- PER-CELL EQUATIONS: pre-fire (ascension) + tail (recovery), split at fire ----
        #      Fit BOTH representations (trade arc, book K5 arc); report which is cleaner/more distinct.
        cell_arcs = {}  # cache mean arcs for PNG + npz
        eq_r2 = {"trade": [], "book": []}
        for chan, tag in (("t", "trade"), ("b5", "book")):
            print(f"\n  EQUATIONS [{tag} imbalance] — 4 DISTINCT cells x 2 limbs (pre-fire | tail):", flush=True)
            for cell in CELLS:
                m = masks[cell]
                if not m.sum():
                    continue
                pre = np.stack(F(f'{chan}_pre_arc')[m]).mean(0)
                tail = np.stack(F(f'{chan}_tail_arc')[m]).mean(0)
                cell_arcs[(tag, cell, "pre")] = pre; cell_arcs[(tag, cell, "tail")] = tail
                (pn, pc, pr2, _), _ = best_form(pre); ps = limb_stats(pre)
                (tn, tc, tr2, _), _ = best_form(tail); ts = limb_stats(tail)
                mext = float(np.median(F('tail_ext')[m]))
                fpt = flatten_point(tn, tc, mext)
                eq_r2[tag].append(pr2); eq_r2[tag].append(tr2)
                print(f"    [{cell:11}] PRE : {fmt_form(pn, pc):58} R²={pr2:.3f}  "
                      f"start-y={ps['start']:+.3f} end-y(peak)={ps['end']:+.3f}", flush=True)
                print(f"    {'':13} TAIL: {fmt_form(tn, tc):58} R²={tr2:.3f}  "
                      f"start-y={ts['start']:+.3f} end-y(close)={ts['end']:+.3f}  "
                      f"exhaust={fpt[1]}@t={fpt[0]:.2f}(~{fpt[2]:.0f}s)", flush=True)
        mt = np.mean(eq_r2["trade"]); mb = np.mean(eq_r2["book"])
        cleaner = "TRADE" if mt > mb else "BOOK"
        print(f"\n    mean fit-R²: trade={mt:.3f}  book={mb:.3f}  -> cleaner representation: {cleaner}", flush=True)
        # save per-cell mean arcs (both channels) for offline re-fit / record
        np.savez(os.path.join(os.path.dirname(__file__), f"leg_imbalance_arcs_{coin}.npz"),
                 **{f"{tag}|{cell}|{limb}": v for (tag, cell, limb), v in cell_arcs.items()})

        # ---- per-cell AVERAGE whole-leg arcs (turn-to-turn) -> PNG ----
        fig, axs = plt.subplots(2, 2, figsize=(14, 8))
        x = np.concatenate([np.linspace(-1, 0, NRS), np.linspace(0, 1, NRS)])       # norm time: birth..onset..close
        for ax, cell in zip(axs.ravel(), CELLS):
            m = masks[cell]
            if not m.sum():
                continue
            t_arc = np.concatenate([np.stack(F('t_pre_arc')[m]).mean(0), np.stack(F('t_tail_arc')[m]).mean(0)])
            b_arc = np.concatenate([np.stack(F('b5_pre_arc')[m]).mean(0), np.stack(F('b5_tail_arc')[m]).mean(0)])
            ax.plot(x, t_arc, color="tab:blue", lw=1.8, label="trade imb")
            ax.plot(x, b_arc, color="tab:red", lw=1.8, label="book imb K5")
            ax.axvline(0, color="k", ls="--", lw=1, alpha=0.6); ax.axhline(0, color="gray", lw=0.6)
            ax.set_title(f"{coin.upper()} {cell} (n={int(m.sum())})", fontsize=11, fontweight="bold")
            ax.set_xlabel("normalized leg time  (-1=valley/birth, 0=peak/onset, +1=exhaustion/close)")
            ax.set_ylabel("signed imbalance"); ax.legend(fontsize=8); ax.grid(alpha=0.25)
        fig.suptitle(f"{coin.upper()} whole-leg imbalance (trade vs book), per cell, turn-to-turn", fontsize=13)
        plt.tight_layout(rect=[0, 0, 1, 0.97])
        pp = os.path.join(os.path.dirname(__file__), f"leg_imbalance_{coin}.png")
        plt.savefig(pp, dpi=110); plt.close()
        print(f"\n  saved {pp}", flush=True)
    print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
