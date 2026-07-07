"""_s68_fp_book.py — Kraken L2 BOOK depth-imbalance fingerprint for the 5 majors (S68).

The tape gives taker FLOW; the book gives resting DEPTH. This tests whether pre-onset DEPTH imbalance
(top-K bid size vs ask size) carries a CAUSAL directional fingerprint for down-slides vs up-hills, and
whether book imbalance LEADS price (the canonical top-of-book signal, on Kraken's own book).

Book covers only the last ~30-67h of the tape (per coin) -> characterization, not sizing-grade.
No commits, no live-code edits.
"""
from __future__ import annotations
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from odcore.io import load_bins                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K = 5           # top-K book levels per side
WDIP = 600


def auc(x, y):
    x = np.asarray(x, float); y = np.asarray(y, int)
    m = np.isfinite(x); x, y = x[m], y[m]
    npos = int((y == 1).sum()); nneg = int((y == 0).sum())
    if npos == 0 or nneg == 0:
        return np.nan
    order = np.argsort(x, kind="mergesort"); ranks = np.empty(len(x)); ranks[order] = np.arange(1, len(x) + 1)
    _, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    sr = np.zeros(len(cnt)); np.add.at(sr, inv, ranks); ranks = (sr / cnt)[inv]
    return float((ranks[y == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def build_dib(path, tape_ts0, n):
    """1s tape-aligned depth-imbalance (top-K) array, NaN where no book. Returns (dib, lo, hi) index range."""
    dib = np.full(n, np.nan)
    seen_lo, seen_hi = n, 0
    for line in open(path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        i = int(round(r["ts"])) - tape_ts0
        if i < 0 or i >= n:
            continue
        bids = r.get("bids", [])[:K]; asks = r.get("asks", [])[:K]
        bsz = sum(abs(float(x[1])) for x in bids); asz = sum(abs(float(x[1])) for x in asks)
        t = bsz + asz
        if t <= 0:
            continue
        dib[i] = (bsz - asz) / t          # +bid-heavy (support) / -ask-heavy (resistance); last write per second wins
        seen_lo = min(seen_lo, i); seen_hi = max(seen_hi, i)
    return dib, seen_lo, seen_hi


def price_zigzag(mid, theta_bps, lo, hi):
    """Correct zigzag (single direction state, if/elif) over [lo,hi)."""
    th = theta_bps / 1e4; piv = []
    d = 1; ext = mid[lo]; exti = lo
    for t in range(lo + 1, hi):
        x = mid[t]
        if x <= 0:
            continue
        if ext <= 0:
            ext = x; exti = t; continue
        if d == 1:
            if x > ext: ext = x; exti = t
            elif x <= ext * (1 - th): piv.append((exti, "H")); d = -1; ext = x; exti = t
        else:
            if x < ext: ext = x; exti = t
            elif x >= ext * (1 + th): piv.append((exti, "L")); d = 1; ext = x; exti = t
    return piv


def main():
    coins = sys.argv[1:] or ["btc", "eth", "sol", "xrp", "doge"]
    out = {}
    for c in coins:
        bp = f"/tmp/{c}_book.jsonl"
        if not os.path.exists(bp):
            print(f"{c}: no book at {bp}"); continue
        s = load_bins(os.path.join(ROOT, "realbins", f"{c}_kraken_bins.json"))
        mid = np.asarray(s.mid, float); ts0 = int(s.ts[0]); n = len(mid)
        dib, lo, hi = build_dib(bp, ts0, n)
        cov = np.isfinite(dib).sum()
        if cov < 1000 or hi - lo < 3600:
            print(f"{c}: book coverage too thin ({cov})"); continue
        # forward-fill dib within the covered range so every second has a (causal, last-known) value
        idx = np.where(np.isfinite(dib))[0]
        ff = np.copy(dib)
        # simple causal ffill
        last = np.nan
        for i in range(lo, hi + 1):
            if np.isfinite(dib[i]): last = dib[i]
            ff[i] = last
        # theta auto (6x median 300s |ret| within window)
        seg = mid[lo:hi]
        r = np.abs(np.log(np.maximum(seg[300:], 1e-12) / np.maximum(seg[:-300], 1e-12)) * 1e4)
        theta = float(max(8.0, 6 * np.median(r[np.isfinite(r)])))
        piv = price_zigzag(mid, theta, lo + WDIP + 5, hi)
        slides, hills = [], []
        for k in range(len(piv) - 1):
            (i0, k0), (i1, _) = piv[k], piv[k + 1]
            if mid[i0] <= 0 or mid[i1] <= 0: continue
            if abs(np.log(mid[i1] / mid[i0]) * 1e4) < theta: continue
            (slides if k0 == "H" else hills).append(i0)
        if len(slides) < 20 or len(hills) < 20:
            print(f"{c}: too few episodes in book window (s={len(slides)} h={len(hills)})"); continue
        # pre-onset depth imbalance: mean dib over [onset-WDIP, onset]
        def pre_dib(idxs):
            vals = []
            for i in idxs:
                w = ff[max(lo, i - WDIP):i]
                w = w[np.isfinite(w)]
                vals.append(float(np.mean(w)) if len(w) else np.nan)
            return np.array(vals)
        S = pre_dib(np.array(slides)); H = pre_dib(np.array(hills))
        x = np.concatenate([S, H]); y = np.concatenate([np.ones(len(S)), np.zeros(len(H))])
        a_dir = auc(x, y)
        # book-leads-price: corr(dib[t], fwd 60s return) within window (causal lead test)
        ii = np.arange(lo + WDIP, hi - 60)
        fwd = np.log(np.maximum(mid[ii + 60], 1e-12) / np.maximum(mid[ii], 1e-12)) * 1e4
        d0 = ff[ii]
        mfin = np.isfinite(d0) & np.isfinite(fwd)
        lead = float(np.corrcoef(d0[mfin], fwd[mfin])[0, 1]) if mfin.sum() > 100 else np.nan
        out[c] = dict(cov_hours=round(cov / 3600, 1), theta=round(theta, 1), nslide=len(slides), nhill=len(hills),
                      slide_predib=round(float(np.nanmean(S)), 4), hill_predib=round(float(np.nanmean(H)), 4),
                      auc_slide_vs_hill=round(a_dir, 4), book_leads_price_corr60=round(lead, 4))
        print(f"[{c}] book {out[c]['cov_hours']}h theta={theta:.1f} s={len(slides)} h={len(hills)} "
              f"slide_dib={out[c]['slide_predib']:+.3f} hill_dib={out[c]['hill_predib']:+.3f} "
              f"AUC_dir={a_dir:.3f} lead_corr60={lead:+.3f}")
    json.dump(out, open("/tmp/s68_book.json", "w"), indent=1)
    print("wrote /tmp/s68_book.json")


if __name__ == "__main__":
    main()
