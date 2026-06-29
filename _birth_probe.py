"""_birth_probe.py — S41 BIRTH stage: does LIQUIDITY create HEAD PRESSURE before the market moves?

REFINEMENT mindset (Greg): this is NOT a kill gate. We map WHERE and HOW MUCH the macro
liquidity layer leads the micro flow (head pressure) and price -- across depth-K, smoothing,
and event-aligned at the turns -- so we can tune toward the configuration that surfaces the
lead. A coincident result = "wrong measure/horizon, refine", not "dead".

THE CHAIN we're testing:   book liquidity (MACRO)  ->  head pressure / flow (MICRO)  ->  price.
Data = the coinbase book file (both layers on one 100ms clock):
  ts, mid, spread, bids[[offset,size]x10], asks[[offset,size]x10], buy, sell, n_trades.

Signals (per 100ms grid cell):
  LIQ_K   = (sum bid_size - sum ask_size)/(sum) over the top-K nearest levels  (the curve tilt)
  dLIQ_K  = change in LIQ_K                                                     (curve shifting / withdrawal)
  FLOW    = trailing-W (buy-sell)/(buy+sell) executed taker imbalance           (head pressure / the dipole)
  PXV     = d log(mid)                                                          (price velocity)

Lead/lag: normalized cross-correlation over a lag grid; argmax lag = who leads (+lag => first arg leads).
Event-aligned: at price-move onsets, average LIQ / FLOW / |PXV| in the seconds around onset.
"""
from __future__ import annotations
import argparse, json, gzip
import numpy as np


def load_book(path):
    ts, mid, buy, sell = [], [], [], []
    bidK = {1: [], 3: [], 5: [], 10: []}
    askK = {1: [], 3: [], 5: [], 10: []}
    with gzip.open(path, "rt") as f:
        for line in f:
            r = json.loads(line)
            ts.append(r["ts"]); mid.append(r["mid"])
            buy.append(r.get("buy", 0.0) or 0.0); sell.append(r.get("sell", 0.0) or 0.0)
            b = [s for (_, s) in r["bids"]]; a = [s for (_, s) in r["asks"]]
            for K in bidK:
                bidK[K].append(float(np.sum(b[:K]))); askK[K].append(float(np.sum(a[:K])))
    ts = np.array(ts); mid = np.array(mid)
    return dict(ts=ts, mid=mid, buy=np.array(buy), sell=np.array(sell),
                bidK={K: np.array(v) for K, v in bidK.items()},
                askK={K: np.array(v) for K, v in askK.items()})


def to_grid(d, dt=0.1):
    """Bin onto a regular dt grid: book fields = last-in-cell (ffill), flow = sum-in-cell."""
    ts = d["ts"]; t0 = ts[0]
    cell = np.round((ts - t0) / dt).astype(int)
    n = cell[-1] + 1
    def last_in(x):
        out = np.full(n, np.nan); out[cell] = x
        # forward fill
        idx = np.where(~np.isnan(out))[0]
        out[:idx[0]] = out[idx[0]]
        last = np.maximum.accumulate(np.where(~np.isnan(out), np.arange(n), 0))
        return out[last]
    def sum_in(x):
        out = np.zeros(n); np.add.at(out, cell, x); return out
    g = dict(mid=last_in(d["mid"]), buy=sum_in(d["buy"]), sell=sum_in(d["sell"]),
             bidK={K: last_in(v) for K, v in d["bidK"].items()},
             askK={K: last_in(v) for K, v in d["askK"].items()}, dt=dt, n=n)
    return g


def lean(buy, sell, W):
    cb = np.concatenate([[0.], np.cumsum(buy)]); cs = np.concatenate([[0.], np.cumsum(sell)])
    n = len(buy); ix = np.arange(n); lo = np.maximum(ix + 1 - W, 0)
    B = cb[ix + 1] - cb[lo]; S = cs[ix + 1] - cs[lo]; tot = B + S
    out = np.zeros(n); nz = tot > 0; out[nz] = (B[nz] - S[nz]) / tot[nz]
    return out


def xcorr_lead(x, y, max_lag):
    """Normalized cross-corr; returns (best_lag, best_corr, corr_at_0). best_lag>0 => x leads y."""
    x = x - x.mean(); y = y - y.mean()
    sx = x.std() + 1e-12; sy = y.std() + 1e-12
    n = len(x); lags = range(-max_lag, max_lag + 1); best = (0, 0.0); c0 = 0.0
    for L in lags:
        if L >= 0:
            c = np.mean(x[:n - L] * y[L:]) / (sx * sy) if n - L > 10 else 0.0
        else:
            c = np.mean(x[-L:] * y[:n + L]) / (sx * sy) if n + L > 10 else 0.0
        if L == 0: c0 = c
        if abs(c) > abs(best[1]): best = (L, c)
    return best[0], best[1], c0


def run(path, W, max_lag_s, render):
    raw = load_book(path); g = to_grid(raw, 0.1)
    dt = g["dt"]; max_lag = int(max_lag_s / dt)
    pxv = np.concatenate([[0.], np.diff(np.log(np.where(g["mid"] > 0, g["mid"], np.nan)))])
    pxv = np.nan_to_num(pxv)
    flow = lean(g["buy"], g["sell"], W)
    print(f"# book: {g['n']:,} cells @ {dt*1000:.0f}ms = {g['n']*dt/3600:.2f}h ; flow W={W} cells ({W*dt:.1f}s); "
          f"lag grid +/-{max_lag_s}s")
    print(f"# lead/lag: +lag => FIRST series leads. (refinement: scan K + which chain link leads)\n")
    results = {}
    for K in (1, 3, 5, 10):
        liq = (g["bidK"][K] - g["askK"][K]) / (g["bidK"][K] + g["askK"][K] + 1e-12)
        dliq = np.concatenate([[0.], np.diff(liq)])
        chains = {
            "LIQ ->FLOW": xcorr_lead(liq, flow, max_lag),
            "LIQ ->PXV ": xcorr_lead(liq, pxv, max_lag),
            "dLIQ->PXV ": xcorr_lead(dliq, pxv, max_lag),
            "FLOW->PXV ": xcorr_lead(flow, pxv, max_lag),
        }
        results[K] = {k: dict(lag_s=round(v[0]*dt, 2), peak=round(v[1], 3), at0=round(v[2], 3))
                      for k, v in chains.items()}
        print(f"K={K:>2} levels:")
        for name, (L, c, c0) in chains.items():
            lead = "leads" if L > 0 else ("lags" if L < 0 else "coincident")
            print(f"   {name}  peak r={c:+.3f} @ {L*dt:+.2f}s ({lead})   r@0={c0:+.3f}")
        print()

    # event-aligned at price-move onsets (refinement view): big |PXV| events
    thr = np.quantile(np.abs(pxv), 0.999)
    onsets = np.where(np.abs(pxv) > thr)[0]
    onsets = onsets[(onsets > 60) & (onsets < g["n"] - 60)]
    # de-dup nearby onsets
    keep = []; last = -999
    for o in onsets:
        if o - last > 30: keep.append(o); last = o
    onsets = np.array(keep)
    win = int(5 / dt)  # +/-5s
    K = 5
    liq5 = (g["bidK"][K] - g["askK"][K]) / (g["bidK"][K] + g["askK"][K] + 1e-12)
    comp = dict(liq=[], flow=[], pxv=[])
    for o in onsets:
        sgn = np.sign(pxv[o]) or 1.0
        comp["liq"].append(sgn * liq5[o - win:o + win])
        comp["flow"].append(sgn * flow[o - win:o + win])
        comp["pxv"].append(sgn * np.cumsum(pxv[o - win:o + win]))   # cumulative move
    comp = {k: np.mean(np.array(v), axis=0) for k, v in comp.items() if len(v)}
    print(f"# event-aligned at {len(onsets)} price-move onsets (sign-aligned, +/-5s):")
    tax = (np.arange(-win, win)) * dt
    for lbl, key in [("LIQ(K5)", "liq"), ("FLOW", "flow"), ("price(cum)", "pxv")]:
        pre = comp[key][:win].mean(); post = comp[key][win:].mean()
        print(f"   {lbl:>11}: pre-onset mean {pre:+.4f}  post {post:+.4f}  (lead if pre already moved)")

    out = dict(path=path, W=W, dt=dt, n=int(g["n"]), xcorr=results, n_onsets=int(len(onsets)))
    with open("_birth_probe_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\n[saved] _birth_probe_results.json")
    if render:
        _render(results, tax, comp)


def _render(results, tax, comp):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(15, 6))
    # left: event-aligned composite (the BIRTH picture)
    ax0 = ax[0]; ax0b = ax0.twinx()
    ax0.axvline(0, color="b", ls="--", lw=1)
    ax0.plot(tax, comp["liq"], color="#0050b3", lw=2, label="LIQ (book tilt, K5)")
    ax0.plot(tax, comp["flow"], color="#d4380d", lw=2, label="FLOW (head pressure)")
    ax0b.plot(tax, comp["pxv"], color="#222", lw=2, label="price (cum, sign-aligned)")
    ax0.set_xlabel("seconds from price-move onset"); ax0.set_ylabel("liq / flow (sign-aligned)")
    ax0b.set_ylabel("cumulative price move")
    ax0.set_title("BIRTH: does liquidity/head-pressure move BEFORE price (t<0)?")
    h0, l0 = ax0.get_legend_handles_labels(); h1, l1 = ax0b.get_legend_handles_labels()
    ax0.legend(h0 + h1, l0 + l1, loc="upper left", fontsize=9)
    # right: lead/lag peaks per K
    ax1 = ax[1]; Ks = list(results.keys())
    for name in ("LIQ ->FLOW", "LIQ ->PXV ", "dLIQ->PXV ", "FLOW->PXV "):
        lags = [results[K][name]["lag_s"] for K in Ks]
        ax1.plot(Ks, lags, marker="o", label=name.strip())
    ax1.axhline(0, color="k", lw=0.6)
    ax1.set_xlabel("depth K (levels)"); ax1.set_ylabel("lead time (s)  +ve = first leads")
    ax1.set_title("lead/lag of each chain link vs depth-K"); ax1.legend(fontsize=9)
    fig.tight_layout(); fig.savefig("_birth_probe.png", dpi=110); plt.close(fig)
    print("[render] _birth_probe.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="/tmp/book.jsonl.gz")
    ap.add_argument("--W", type=int, default=20, help="flow lean window in 100ms cells (20=2s)")
    ap.add_argument("--max_lag_s", type=float, default=5.0)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    run(a.path, a.W, a.max_lag_s, not a.no_render)
