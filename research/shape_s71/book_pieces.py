"""S75 BOOK-PIECES + PER-CELL DISTINCT-TELL extractor & separation diagnostic (Greg's spec).

Greg (S75): "focus on the things that make them distinct" + "do the book plus numbers — two
different numbers. even if the sums are close, the 2 pieces aren't."

So we do NOT collapse the book into one net imbalance ratio. We carry the book as TWO SEPARATE
scale-free pieces per level K:
    book_with    = with-side resting depth / (causal rolling mean total depth)   [scale-free]
    book_against = against-side resting depth / (causal rolling mean total depth)
plus, for reference only, the NET ratio book_net=(with-against)/(with+against) — the "sum" that can be
close while the 2 pieces differ. All evaluated at ONSET (mean of the last 5s of the causal pre-fire limb).

Trade features are the existing sep_diag set (peak, climb=ascent-rate, b_blade, ...). The DISTINCT tell per
cell (Greg's map): peak for most cells; climb/blade for SOL-short; book pieces for BTC-long / wherever net
is flat. This script EXTRACTS everything through the LIVE path (run_kraken_cell) and then runs a per-cell
SEPARATION diagnostic: for each candidate tell, gap(L-W) + win% in the skipped loser-tail, per SHORT/LONG
category, per coin. It answers Greg's hypothesis with data BEFORE we wire the gate. Shape/RATIO only; doge excluded.
Caches per-leg features to /tmp/kbook/{coin}_feats3.npz for the gate script (book_gate.py).
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from arc_gate import (load_raw, rolling_imb, build_channels, median_spread_bps,
                      run_kraken_cell, KRAKEN, PRE, CPS)
from sep_diag import features as trade_features, FEATS as TRADE_FEATS
SMOOTH_SEC = 20
BASE_SEC = 300              # causal rolling window for the scale-free depth baseline
ONSET_SEC = 5              # onset book value = mean of the last ONSET_SEC before the fire
LEVELS = [1, 5, 10]
COINS = ["btc", "eth", "sol", "xrp"]


def causal_rollmean(x, w):
    """Causal (past-only) rolling mean over w cells. No look-ahead."""
    c = np.concatenate([[0.0], np.cumsum(x)])
    ix = np.arange(len(x)); lo = np.maximum(ix + 1 - w, 0)
    return (c[ix + 1] - c[lo]) / (ix + 1 - lo)


def book_piece_arrays(g):
    """Two scale-free book pieces per level, UNSIGNED (bid/ask); sign to side per-leg later."""
    wbase = int(BASE_SEC * CPS)
    out = {}
    for K in LEVELS:
        bid = np.asarray(g["bidK"][K], float); ask = np.asarray(g["askK"][K], float)
        base = causal_rollmean(bid + ask, wbase) + 1e-12       # coin's own typical total depth (scale-free divisor)
        out[K] = (bid / base, ask / base)                       # (bid_rel, ask_rel) — two independent pieces
    return out


def extract_full(coin):
    path = f"/tmp/kbook/{coin}_book.jsonl"; cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0; N = len(mid); hours = N * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)           # LIVE legs
    imb = rolling_imb(buy, sell, SMOOTH_SEC)
    bpieces = book_piece_arrays(g)                                      # {K:(bid_rel, ask_rel)}
    onset_w = int(ONSET_SEC * CPS)
    rows, net, dur = [], [], []
    for l in res.legs:
        o = int(l.open_idx); c = int(l.close_idx); s = int(l.side)
        if o - PRE < 0 or c <= o:
            continue
        pre = imb[o - PRE:o + 1] * s
        feat = dict(trade_features(pre))                               # existing trade-shape features
        # ---- BOOK: two scale-free pieces per level, signed to side, at onset (last ONSET_SEC, causal) ----
        oa = max(0, o - onset_w)
        for K in LEVELS:
            bid_rel, ask_rel = bpieces[K]
            bw = bid_rel[oa:o + 1].mean(); aw = ask_rel[oa:o + 1].mean()   # bid_rel, ask_rel at onset
            with_d = bw if s > 0 else aw                                    # with-side depth (piece 1)
            agn_d = aw if s > 0 else bw                                     # against-side depth (piece 2)
            feat[f"bwith{K}"] = float(with_d)
            feat[f"bagn{K}"] = float(agn_d)
            feat[f"bnet{K}"] = float((with_d - agn_d) / (with_d + agn_d + 1e-12))   # the "sum" (reference)
        rows.append(feat); net.append(float(l.net_bps)); dur.append((c - o) * 0.1)
    return rows, np.array(net), np.array(dur), hours


BOOK_FEATS = [f"{p}{K}" for K in LEVELS for p in ("bwith", "bagn", "bnet")]
# The candidate DISTINCT tells we report (trade shape + the two book pieces + net for contrast):
TELLS = ["peak", "climb", "b_blade", "convexity", "below0",
         "bwith5", "bagn5", "bnet5", "bwith1", "bagn1", "bwith10", "bagn10"]


def sep_report(coin, rows, net, dur):
    F = {k: np.array([r.get(k, np.nan) for r in rows]) for k in set(TRADE_FEATS) | set(BOOK_FEATS)}
    win = net > 0; med = np.median(dur); short = dur < med; base = win.mean()
    print(f"\n===== {coin.upper()}  n={len(rows)}  base win%={base*100:.1f}  med={med:.0f}s =====", flush=True)
    for cat, cmask in [("SHORT", short), ("LONG", ~short)]:
        w = cmask & win; l = cmask & ~win
        cw = w.sum() / max(1, (w.sum() + l.sum()))
        print(f"  --- {cat}  cat-win%={cw*100:.1f}  (win {int(w.sum())}, lose {int(l.sum())}) ---", flush=True)
        print(f"    {'tell':10}{'W-mean':>9}{'L-mean':>9}{'gap(L-W)':>10}   win%@skip loser-tail[10/20/30%]  (base {cw*100:.0f})", flush=True)
        for k in TELLS:
            if k not in F:
                continue
            fw, fl = F[k][w], F[k][l]
            if not (np.isfinite(fw).any() and np.isfinite(fl).any()):
                continue
            gap = np.nanmean(fl) - np.nanmean(fw)
            direction = 1 if gap > 0 else -1
            fc = F[k][cmask]; yc = win[cmask]
            order = np.argsort(-fc if direction > 0 else fc)               # most loser-like first
            wr = []
            for frac in (0.10, 0.20, 0.30):
                kn = max(1, int(frac * len(fc)))
                wr.append(yc[order[:kn]].mean() * 100)
            flag = "  <== SEPARATES" if wr[0] < cw * 100 - 12 else ""
            print(f"    {k:10}{np.nanmean(fw):>9.3f}{np.nanmean(fl):>9.3f}{gap:>+10.4f}   "
                  f"{wr[0]:5.1f} {wr[1]:5.1f} {wr[2]:5.1f}{flag}", flush=True)
    return F, win, short


def main():
    coins = sys.argv[1:] or COINS
    for coin in coins:
        print(f"\n... loading+running {coin} (live executor) ...", flush=True)
        rows, net, dur, hours = extract_full(coin)
        sep_report(coin, rows, net, dur)
        allk = sorted(set(TRADE_FEATS) | set(BOOK_FEATS))
        np.savez(f"/tmp/kbook/{coin}_feats3.npz",
                 **{k: np.array([r.get(k, np.nan) for r in rows]) for k in allk},
                 net=net, dur=dur, hours=hours)
        print(f"  saved /tmp/kbook/{coin}_feats3.npz  ({len(allk)} features)", flush=True)
    print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
