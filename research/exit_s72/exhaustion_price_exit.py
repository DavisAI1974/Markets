"""S72 EXIT/EXHAUSTION study — per INDIVIDUAL trade, characterize the relationship between
order-flow EXHAUSTION (with-trade flow rolling back toward balance after entry) and PRICE
behavior over the RIDE (post-entry portion). Descriptive research; commits a script + a
findings writeup, changes NO strategy/firing code.

HARD RULES obeyed:
  * SIM = LIVE: legs come from the LIVE executor odcore.platform.run_kraken_cell. No reimplementation.
  * NO AVERAGING of shapes. Every measurement is computed PER INDIVIDUAL TRADE first; we then
    tally DISTRIBUTIONS (medians/quantiles/counts) across trades. No mean-curve reading.
  * NO baked-in hypothesis about what marks the exit. We measure where the favorable price
    extremum falls RELATIVE to flow features (peak, zero-cross, half-peak, return-to-balance)
    as measurements, and let the data speak.

Run per coin:   python research/exit_s72/exhaustion_price_exit.py btc
Run all:        python research/exit_s72/exhaustion_price_exit.py all
"""
import os, sys, json, gc
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/user/Markets"
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _birth_probe import _depthK
import _liquidity_dive as LD
from _liquidity_dive import build_channels, median_spread_bps
from odcore.platform import run_kraken_cell, KRAKEN, FLOW_W

CELLS_PER_SEC = 10
SMOOTH_SEC    = 20                     # same with-trade-flow smoothing as S71 shape_arc
HORIZON_SEC   = 600                    # LONG post-entry ride horizon (S72 lead: +120s clipped long runners).
HORIZON       = HORIZON_SEC * CELLS_PER_SEC   # require the FULL window to exist per leg.
OLD_HORIZON_SEC = 120                  # the previous (too-short) horizon, kept only to count what it clipped.
PLOT_SAMPLE   = 200                    # cap of INDIVIDUAL winner rides overlaid per cell (never a mean curve)
BOOKDIR       = "/tmp/kbook"
OUT           = "/tmp/kbook"           # PNGs (gitignored); numbers go in the findings md


def load_raw(book):
    ts, mid, buy, sell, spread = [], [], [], [], []
    b1, b3, b5, b10, a1, a3, a5, a10 = [], [], [], [], [], [], [], []
    with open(book) as f:
        for line in f:
            r = json.loads(line)
            ts.append(r["ts"]); mid.append(r["mid"]); spread.append(r.get("spread"))
            buy.append(r.get("buy", 0.0) or 0.0); sell.append(r.get("sell", 0.0) or 0.0)
            x1, x3, x5, x10 = _depthK(r["bids"]); b1.append(x1); b3.append(x3); b5.append(x5); b10.append(x10)
            y1, y3, y5, y10 = _depthK(r["asks"]); a1.append(y1); a3.append(y3); a5.append(y5); a10.append(y10)
    return dict(ts=np.array(ts), mid=np.array(mid), buy=np.array(buy), sell=np.array(sell),
                spread=np.array([np.nan if x is None else x for x in spread], float),
                bidK={1: np.array(b1), 3: np.array(b3), 5: np.array(b5), 10: np.array(b10)},
                askK={1: np.array(a1), 3: np.array(a3), 5: np.array(a5), 10: np.array(a10)})


def rolling_imb(buy, sell, w_sec):
    """Rolling (buy-sell)/(buy+sell) imbalance over w_sec, SAME as S71 shape_arc."""
    w = int(w_sec * CELLS_PER_SEC)
    cb = np.concatenate([[0.], np.cumsum(buy)]); cs = np.concatenate([[0.], np.cumsum(sell)])
    ix = np.arange(len(buy)); lo = np.maximum(ix + 1 - w, 0)
    B = cb[ix + 1] - cb[lo]; S = cs[ix + 1] - cs[lo]; tot = B + S
    out = np.zeros(len(buy)); nz = tot > 0
    out[nz] = (B[nz] - S[nz]) / tot[nz]
    return out


def qtiles(a, qs=(10, 25, 50, 75, 90, 95)):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    if a.size == 0:
        return {q: float("nan") for q in qs}
    return {q: float(np.percentile(a, q)) for q in qs}


def fmt_q(d):
    return "  ".join(f"p{q}={d[q]:+.1f}" for q in sorted(d))


def analyze_coin(coin):
    book = os.path.join(BOOKDIR, f"{coin}_book.jsonl")
    cfg = [c for c in KRAKEN if c.coin == coin][0]
    print(f"\n{'='*78}\n=== {coin}_kraken ===\n{'='*78}", flush=True)
    print("loading book...", flush=True)
    raw = load_raw(book)
    ch, g = build_channels(book, cfg.K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    gbuy = np.asarray(g["buy"], float); gsell = np.asarray(g["sell"], float)
    hs = median_spread_bps(book, raw=raw) / 2.0
    N = len(mid)
    print(f"  grid cells: {N}  ({N*0.1/3600:.1f}h)  half_spread={hs:.3f}bps", flush=True)

    print("running LIVE executor run_kraken_cell...", flush=True)
    res, desc = run_kraken_cell(cfg, mid, gbuy, gsell, bb, ba, hs)
    legs = res.legs
    print(f"  {len(legs)} legs", flush=True)

    imb_signed = rolling_imb(gbuy, gsell, SMOOTH_SEC)

    OLD_HZ = OLD_HORIZON_SEC * CELLS_PER_SEC
    # ---- PER-INDIVIDUAL-TRADE measurements ----
    rows = []
    n_no_full_window = 0
    for l in legs:
        o = int(l.open_idx); c = int(l.close_idx); side = int(l.side)
        if c <= o:
            continue
        hi = o + HORIZON                      # require the FULL long window to exist (no edge bias)
        if hi >= N:
            n_no_full_window += 1
            continue
        px0 = mid[o]
        # favorable price move (bps), in the trade's direction, along the ride
        fav = side * (mid[o:hi + 1] - px0) / px0 * 1e4
        # with-trade flow along the ride (rises into the turn, exhausts back toward/through 0)
        flow = imb_signed[o:hi + 1] * side
        t = np.arange(len(fav)) * 0.1        # seconds since entry

        # --- PRICE extremum (best exit) over the FULL long ride window ---
        pk = int(np.argmax(fav))
        price_ext_sec = t[pk]
        fav_ext = float(fav[pk])
        # --- what the OLD 120s window would have found (to measure the clipping) ---
        pk120 = int(np.argmax(fav[:OLD_HZ + 1]))
        fav_ext_120 = float(fav[pk120])
        price_ext_120_sec = pk120 * 0.1
        extra_beyond_120 = fav_ext - fav_ext_120     # extra favorable bps available past +120s (>=0)
        beyond_120 = bool(price_ext_sec > OLD_HORIZON_SEC + 0.05)  # true top lands past +120s

        # --- actual close (favorable captured at the real close) ---
        close_off = c - o
        close_sec = close_off * 0.1
        within = close_off <= (hi - o)
        fav_close = float(side * (mid[c] - px0) / px0 * 1e4) if c < N else float("nan")

        # --- FLOW features post-entry (measured openly; no rule baked in) ---
        flow0 = float(flow[0])
        fpk = int(np.argmax(flow))
        flow_peak_sec = t[fpk]
        flow_peak_val = float(flow[fpk])
        # first return to balance (<=0) AFTER the flow peak
        zero_sec = float("nan")
        after = np.where(flow[fpk:] <= 0.0)[0]
        if after.size:
            zero_sec = t[fpk + after[0]]
        # first fall to half of the post-entry peak, after the peak
        half_sec = float("nan")
        halflev = flow_peak_val * 0.5
        afterh = np.where(flow[fpk:] <= halflev)[0]
        if afterh.size and flow_peak_val > 0:
            half_sec = t[fpk + afterh[0]]

        rows.append(dict(
            open_idx=o, side=side, net_bps=float(l.net_bps),
            winner=bool(l.net_bps > 0),
            close_sec=close_sec, close_within_horizon=bool(within),
            price_ext_sec=price_ext_sec, fav_ext=fav_ext, fav_close=fav_close,
            fav_capture_frac=(fav_close / fav_ext) if fav_ext > 1e-9 else float("nan"),
            flow0=flow0, flow_peak_sec=flow_peak_sec, flow_peak_val=flow_peak_val,
            flow_zero_sec=zero_sec, flow_half_sec=half_sec,
            # lead/lag of price extremum vs flow features (positive = price extremum LATER)
            lag_ext_vs_zero=(price_ext_sec - zero_sec) if np.isfinite(zero_sec) else float("nan"),
            lag_ext_vs_half=(price_ext_sec - half_sec) if np.isfinite(half_sec) else float("nan"),
            lag_ext_vs_flowpeak=(price_ext_sec - flow_peak_sec),
            # flow-zero-crossing TIMING relative to (a) price extremum and (b) actual close (plain
            # measurements; no assumption they coincide):
            zero_minus_ext=(zero_sec - price_ext_sec) if np.isfinite(zero_sec) else float("nan"),
            zero_minus_close=(zero_sec - close_sec) if np.isfinite(zero_sec) else float("nan"),
            close_vs_ext=(close_sec - price_ext_sec),
            tail_bps=(fav_ext - fav_close),
            fav_ext_120=fav_ext_120, price_ext_120_sec=price_ext_120_sec,
            extra_beyond_120=extra_beyond_120, beyond_120=beyond_120,
            ext_at_horizon_edge=bool(pk >= (hi - o) - 1),  # extremum pinned at LONG-window edge => need MORE
        ))

    n = len(rows)
    print(f"  {n} individual trades with a full {HORIZON_SEC}s ride window "
          f"({n_no_full_window} legs dropped for lacking the full window)", flush=True)
    if n == 0:
        return dict(coin=coin, n=0)

    def summarize(sub, label):
        """PER-TRADE distributions over a subset (winners / losers / all). NOT averaged shapes."""
        m = len(sub)
        if m == 0:
            print(f"\n  --- {coin}_kraken {label}: n=0 (honest null: no trades in this class) ---")
            return dict(label=label, n=0)
        def col(k):
            return np.array([r[k] for r in sub], float)
        price_ext = col("price_ext_sec"); close_s = col("close_sec")
        fav_ext = col("fav_ext"); fav_close = col("fav_close")
        cap_frac = col("fav_capture_frac"); tail = col("tail_bps")
        flow_zero = col("flow_zero_sec"); flow_half = col("flow_half_sec"); flow_pks = col("flow_peak_sec")
        lag_zero = col("lag_ext_vs_zero"); lag_half = col("lag_ext_vs_half"); lag_fpk = col("lag_ext_vs_flowpeak")
        zero_ext = col("zero_minus_ext"); zero_close = col("zero_minus_close")
        cve = col("close_vs_ext")
        edge_pin = np.array([r["ext_at_horizon_edge"] for r in sub])
        close_within = np.array([r["close_within_horizon"] for r in sub])

        beyond120 = np.array([r["beyond_120"] for r in sub])
        extra120  = col("extra_beyond_120")
        price_ext_120 = col("price_ext_120_sec")

        n_after  = int(np.sum(cve > 0.5))    # close AFTER price top -> giving back tail
        n_before = int(np.sum(cve < -0.5))   # close BEFORE price top -> top still ahead
        n_near   = int(np.sum(np.abs(cve) <= 0.5))
        n_edge   = int(np.sum(edge_pin))
        n_beyond = int(np.sum(beyond120))    # true price top lands PAST +120s (old window clipped it)
        frac_zero = float(np.mean(np.isfinite(flow_zero)))
        extra_when_beyond = extra120[beyond120]   # extra bps only on the clipped trades

        d = dict(
            label=label, n=m,
            med_net_bps=float(np.median(col("net_bps"))),
            med_price_ext_sec=float(np.median(price_ext)), q_price_ext=qtiles(price_ext),
            # --- CLIPPING re-check: how many tops fell past the OLD 120s window, and the extra bps ---
            n_beyond_120=n_beyond, frac_beyond_120=float(n_beyond / m),
            med_price_ext_120_sec=float(np.median(price_ext_120)),
            med_extra_beyond_120=float(np.median(extra120)), q_extra_beyond_120=qtiles(extra120),
            med_extra_when_beyond=float(np.median(extra_when_beyond)) if extra_when_beyond.size else float("nan"),
            q_extra_when_beyond=qtiles(extra_when_beyond) if extra_when_beyond.size else {},
            med_close_sec=float(np.median(close_s)), q_close=qtiles(close_s),
            med_fav_ext=float(np.median(fav_ext)), q_fav_ext=qtiles(fav_ext),
            med_fav_close=float(np.median(fav_close)), q_fav_close=qtiles(fav_close),
            med_cap_frac=float(np.nanmedian(cap_frac)), q_cap_frac=qtiles(cap_frac[np.isfinite(cap_frac)]),
            med_tail_bps=float(np.median(tail)), q_tail=qtiles(tail),
            med_flow_peak_sec=float(np.nanmedian(flow_pks)),
            frac_flow_returns_zero=frac_zero,
            med_flow_zero_sec=float(np.nanmedian(flow_zero)), q_flow_zero=qtiles(flow_zero[np.isfinite(flow_zero)]),
            med_flow_half_sec=float(np.nanmedian(flow_half)),
            med_lag_ext_vs_zero=float(np.nanmedian(lag_zero)), q_lag_zero=qtiles(lag_zero[np.isfinite(lag_zero)]),
            med_lag_ext_vs_half=float(np.nanmedian(lag_half)),
            med_lag_ext_vs_flowpeak=float(np.nanmedian(lag_fpk)),
            # flow-zero timing vs price extremum and vs actual close (plain measurements)
            med_zero_minus_ext=float(np.nanmedian(zero_ext)), q_zero_minus_ext=qtiles(zero_ext[np.isfinite(zero_ext)]),
            med_zero_minus_close=float(np.nanmedian(zero_close)), q_zero_minus_close=qtiles(zero_close[np.isfinite(zero_close)]),
            n_close_after=n_after, n_close_before=n_before, n_close_near=n_near,
            n_edge_pin=n_edge, frac_close_within_horizon=float(np.mean(close_within)),
        )
        print(f"\n  --- {coin}_kraken {label} PER-TRADE DISTRIBUTIONS (n={m}, med net {d['med_net_bps']:+.1f}bps) ---")
        print(f"    price-extremum time (best-exit sec):   median {d['med_price_ext_sec']:.1f}s   {fmt_q(d['q_price_ext'])}")
        print(f"    >> top PAST +120s (old window clipped): {n_beyond}/{m} ({n_beyond/m*100:.0f}%)   "
              f"extra bps beyond 120s: median-all {d['med_extra_beyond_120']:+.1f}, "
              f"median-on-clipped {d['med_extra_when_beyond']:+.1f}  {fmt_q(d['q_extra_beyond_120'])}")
        print(f"    actual close time (sec):               median {d['med_close_sec']:.1f}s   {fmt_q(d['q_close'])}")
        print(f"    favorable @ extremum (bps):            median {d['med_fav_ext']:+.1f}   {fmt_q(d['q_fav_ext'])}")
        print(f"    favorable @ actual close (bps):        median {d['med_fav_close']:+.1f}   {fmt_q(d['q_fav_close'])}")
        print(f"    capture frac (close/extremum):         median {d['med_cap_frac']:.2f}   {fmt_q(d['q_cap_frac'])}")
        print(f"    tail given back (ext-close bps):       median {d['med_tail_bps']:+.1f}   {fmt_q(d['q_tail'])}")
        print(f"    flow post-entry peak time:             median {d['med_flow_peak_sec']:.1f}s")
        print(f"    flow returns to balance(<=0):          {frac_zero*100:.0f}% of trades; median {d['med_flow_zero_sec']:.1f}s  {fmt_q(d['q_flow_zero'])}")
        print(f"    flow falls to half-peak:               median {d['med_flow_half_sec']:.1f}s")
        print(f"    price-ext MINUS flow-zero-cross:       median {d['med_lag_ext_vs_zero']:+.1f}s   {fmt_q(d['q_lag_zero'])}")
        print(f"    price-ext MINUS flow-peak:             median {d['med_lag_ext_vs_flowpeak']:+.1f}s")
        print(f"    flow-zero MINUS price-ext:             median {d['med_zero_minus_ext']:+.1f}s   {fmt_q(d['q_zero_minus_ext'])}")
        print(f"    flow-zero MINUS actual-close:          median {d['med_zero_minus_close']:+.1f}s   {fmt_q(d['q_zero_minus_close'])}")
        print(f"    close AFTER price-top (tail):          {n_after}/{m} ({n_after/m*100:.0f}%)")
        print(f"    close BEFORE price-top (top ahead):    {n_before}/{m} ({n_before/m*100:.0f}%)")
        print(f"    close ~AT price-top (+-0.5s):          {n_near}/{m} ({n_near/m*100:.0f}%)")
        print(f"    extremum pinned at {HORIZON_SEC}s edge (EXTEND?): {n_edge}/{m} ({n_edge/m*100:.0f}%)")
        print(f"    close within {HORIZON_SEC}s horizon:           {d['frac_close_within_horizon']*100:.0f}%")
        return d

    winners = [r for r in rows if r["winner"]]
    losers  = [r for r in rows if not r["winner"]]
    out = dict(coin=coin, n=n, n_winners=len(winners), n_losers=len(losers),
               win_frac=float(len(winners) / n),
               winners=summarize(winners, "WINNERS"),
               losers=summarize(losers, "LOSERS"),
               all=summarize(rows, "ALL"))

    # ---- GRAPH the full long ride: overlay INDIVIDUAL winner rides (NOT a mean curve) ----
    if winners:
        rng = np.random.default_rng(0)
        step = CELLS_PER_SEC                                   # downsample to 1s for the plot
        tsec = np.arange(0, HORIZON + 1, step) * 0.1
        # panel A (price): many faint individual rides; panel B (flow): fewer lines, display-smoothed
        # so the per-trade EXHAUSTION envelope is legible (raw 20s flow saturates to +-1 under Kraken
        # trade sparsity). The display smoothing is applied PER TRADE — never across trades.
        pickA = rng.choice(len(winners), size=min(PLOT_SAMPLE, len(winners)), replace=False)
        pickB = rng.choice(len(winners), size=min(40, len(winners)), replace=False)
        DSMOOTH = 60                                           # 60s moving average, display only, per trade
        kern = np.ones(DSMOOTH) / DSMOOTH
        fig, ax = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        n_beyond_plot = 0
        for i in pickA:
            o = winners[i]["open_idx"]; side = winners[i]["side"]; px0 = mid[o]
            favp = (side * (mid[o:o + HORIZON + 1:step] - px0) / px0 * 1e4)
            ax[0].plot(tsec, favp, lw=0.4, alpha=0.20, color="C0")
            pex = winners[i]["price_ext_sec"]; pev = winners[i]["fav_ext"]
            ax[0].plot(pex, pev, ".", color="k", ms=3, alpha=0.5)   # each trade's OWN top (no averaging)
            if pex > OLD_HORIZON_SEC:
                n_beyond_plot += 1
        for i in pickB:
            o = winners[i]["open_idx"]; side = winners[i]["side"]
            flowp = imb_signed[o:o + HORIZON + 1:step] * side
            flow_disp = np.convolve(flowp, kern, mode="same")       # PER-TRADE display smoothing
            ax[1].plot(tsec, flow_disp, lw=0.7, alpha=0.35, color="C1")
            fz = winners[i]["flow_zero_sec"]                         # each trade's OWN return-to-balance
            if np.isfinite(fz) and fz <= HORIZON_SEC:
                ax[1].plot(fz, 0.0, "|", color="k", ms=8, alpha=0.5)
        for a in ax:
            a.axvline(OLD_HORIZON_SEC, color="red", ls="--", lw=1.2, alpha=0.8, label="old +120s horizon")
            a.grid(alpha=0.25); a.axhline(0, color="gray", lw=0.6)
        ax[0].set_title(f"{coin}_kraken WINNERS — full {HORIZON_SEC}s ride, {len(pickA)} INDIVIDUAL trades "
                        f"(no mean curve; black dot = each trade's own price top)\n"
                        f"tops past +120s in this sample: {n_beyond_plot}/{len(pickA)}  "
                        f"(cell-wide: {out['winners']['n_beyond_120']}/{out['winners']['n']} "
                        f"= {out['winners']['frac_beyond_120']*100:.0f}%)")
        ax[0].set_ylabel("favorable price move (bps)"); ax[0].legend(fontsize=8, loc="upper right")
        ax[1].set_title(f"same winners (n={len(pickB)}) — with-trade flow, per-trade {DSMOOTH}s display-smoothed "
                        f"to show the EXHAUSTION envelope; '|' = each trade's own return-to-balance")
        ax[1].set_ylabel("with-trade flow (display-smoothed)"); ax[1].set_xlabel("seconds since entry")
        plt.tight_layout()
        pth = os.path.join(OUT, f"{coin}_kraken_winners_longride.png")
        plt.savefig(pth, dpi=110); plt.close()
        print(f"  saved plot {pth}", flush=True)
        out["plot"] = pth

    # free memory before next coin
    del raw, ch, g, mid, bb, ba, gbuy, gsell, imb_signed, legs, res, rows, winners, losers
    gc.collect()
    return out


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "btc"
    coins = ["btc", "eth", "sol", "xrp", "doge"] if which == "all" else [which]
    results = {}
    for coin in coins:
        results[coin] = analyze_coin(coin)
        gc.collect()
    outp = os.path.join(ROOT, "research", "exit_s72", f"results_{which}.json")
    with open(outp, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print(f"\nwrote {outp}", flush=True)


if __name__ == "__main__":
    main()
