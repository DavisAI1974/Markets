"""
_s68_rebatemm_book.py  --  book-honest markout validation for the S68 rebate thesis.

Majors (BTC/ETH Kraken L2 book) are 0bp -- NO rebate -- so they are the METHODOLOGY
CONTROL, not a deployment target. Goal: show the tape-only front-of-line markout
accounting used on the smallcaps is realistic by cross-checking it against a
queue-honest fill on real book depth, on data that has a TRUE mid (so no bounce bias).

Two fill models, same true-mid markout:
  (A) TAPE-PROXY (front-of-line): every opposing taker print fills our resting touch quote
      (a resting bid fills on sell flow). Entry = best touch. This is the smallcap model.
  (B) BOOK-HONEST (queue): join the back of the best level (queue_ahead = best-level size);
      fill only once cumulative opposing taker volume within a window exceeds the queue.
      Entry = best touch. This charges queue position (maker_book.py mechanic).

If (A) and (B) give similar ADVERSE MARKOUT (bps) and spread capture, the tape-only
smallcap numbers are trustworthy for the adverse-selection accounting.
"""
from __future__ import annotations
import json, sys
import subprocess
import numpy as np

HORIZONS = [1, 5, 30, 60]
CLIP = 5000.0


def load_book(coin, max_rows=400000):
    """Stream the gz book jsonl -> arrays. Subsample to max_rows for speed."""
    p = subprocess.Popen(
        f"git -C /home/user/Markets show origin/data/{coin}-kraken-book:{coin}_kraken_book.jsonl.gz | gunzip",
        shell=True, stdout=subprocess.PIPE, text=True)
    ts, mid, bbpx, bbsz, basz, buy, sell = [], [], [], [], [], [], []
    for i, line in enumerate(p.stdout):
        if not line.strip():
            continue
        d = json.loads(line)
        b = d["bids"]; a = d["asks"]
        if not b or not a:
            continue
        m = d["mid"]
        ts.append(d["ts"]); mid.append(m)
        bbpx.append(m + b[0][0]); bbsz.append(b[0][1]); basz.append(a[0][1])
        buy.append(d.get("buy", 0.0)); sell.append(d.get("sell", 0.0))
    p.wait()
    A = lambda x: np.asarray(x, float)
    ts, mid, bbpx, bbsz, basz, buy, sell = map(A, (ts, mid, bbpx, bbsz, basz, buy, sell))
    if len(ts) > max_rows:                       # even stride subsample (keep flow via block-sum? keep simple)
        idx = np.linspace(0, len(ts) - 1, max_rows).astype(int)
        ts, mid, bbpx, bbsz, basz, buy, sell = (x[idx] for x in (ts, mid, bbpx, bbsz, basz, buy, sell))
    return ts, mid, bbpx, bbsz, basz, buy, sell


def val_at(t, s, q):
    i = np.clip(np.searchsorted(t, q, side="right") - 1, 0, len(s) - 1)
    return s[i]


def queue_fill_idx(qa, opp, window):
    """maker_book mechanic: first future index within `window` bins where cumulative
    opposing taker vol >= queue_ahead. -1 if none."""
    n = len(opp); cum = np.zeros(n); out = np.full(n, -1, int); idx = np.arange(n)
    for w in range(1, window + 1):
        sh = np.concatenate([opp[w:], np.zeros(w)])
        cum += sh
        reach = (idx + w) < n
        newly = (out < 0) & reach & (cum >= qa)
        out[newly] = idx[newly] + w
    return out


def run(coin):
    ts, mid, bbpx, bbsz, basz, buy, sell = load_book(coin)
    n = len(ts)
    span_hr = (ts[-1] - ts[0]) / 3600.0
    half_spread_bps = float(np.average((mid - bbpx) / mid * 1e4))   # real, known half-spread

    res = {"coin": coin, "n_rows": n, "span_hr": round(span_hr, 1),
           "real_half_spread_bps": round(half_spread_bps, 4), "horizons": {}}

    # ---- (A) TAPE-PROXY: front-of-line, fill on every opposing print ----
    bidmask = sell > 0                       # our bid fills on sell flow (we buy)
    askmask = buy > 0
    tb, mb = ts[bidmask], mid[bidmask]
    ta, ma = ts[askmask], mid[askmask]

    # ---- (B) BOOK-HONEST: queue gate ----
    WIN = 100
    fb = queue_fill_idx(bbsz, sell, WIN)     # bid filled by sell flow after queue clears
    fa = queue_fill_idx(basz, buy, WIN)
    bidok = fb >= 0; askok = fa >= 0
    tb2, mb2 = ts[bidok], mid[bidok]         # entry time/mid at post
    ta2, ma2 = ts[askok], mid[askok]
    res["proxy_fill_rate_bid"] = round(float(bidmask.mean()), 4)
    res["book_fill_rate_bid"]  = round(float(bidok.mean()), 4)

    for dt in HORIZONS:
        # A: true-mid adverse markout, favorable-signed
        amk = np.concatenate([(val_at(ts, mid, tb + dt) - mb) / mb * 1e4,
                              (ma - val_at(ts, mid, ta + dt)) / ma * 1e4])
        # B: same, on queue-filled set
        bmk = np.concatenate([(val_at(ts, mid, tb2 + dt) - mb2) / mb2 * 1e4,
                              (ma2 - val_at(ts, mid, ta2 + dt)) / ma2 * 1e4])
        res["horizons"][dt] = {
            "proxy_adverse_markout_bps": round(float(amk.mean()), 4),
            "book_adverse_markout_bps": round(float(bmk.mean()), 4),
            # net at 0bp (majors): spread capture + markout (no rebate)
            "proxy_net_bps_0fee": round(half_spread_bps + float(amk.mean()), 4),
            "book_net_bps_0fee": round(half_spread_bps + float(bmk.mean()), 4),
        }
    return res


if __name__ == "__main__":
    coins = sys.argv[1:] or ["btc", "eth"]
    allr = {}
    for c in coins:
        r = run(c); allr[c] = r
        print(f"\n=== {c.upper()} n={r['n_rows']} span={r['span_hr']}h "
              f"half_spread={r['real_half_spread_bps']}bp "
              f"fill_rate proxy={r['proxy_fill_rate_bid']} book={r['book_fill_rate_bid']} ===")
        for dt in HORIZONS:
            h = r["horizons"][dt]
            print(f"  {dt:2d}s  adverse_markout  proxy={h['proxy_adverse_markout_bps']:+7.3f}  "
                  f"book={h['book_adverse_markout_bps']:+7.3f}   |  net@0fee  "
                  f"proxy={h['proxy_net_bps_0fee']:+7.3f}  book={h['book_net_bps_0fee']:+7.3f}")
    json.dump(allr, open("/tmp/sc/_s68_book_results.json", "w"), indent=2)
    print("\nwrote /tmp/sc/_s68_book_results.json")
