"""backfill_kraken_trades.py — Kraken REST Trades history -> 1-sec bins (S59).

The KRAKEN sibling of backfill_binance_spot.py (venue in the file title — platforms stay
separate). Purpose: the kr_mk0 re-price showed every surviving mid-band entry config flips
positive at Kraken's verified 0bp maker tier — but that arithmetic rode Binance-instrument
gross. Venue law demands the machine's gross be re-earned on KRAKEN'S OWN TAPE before the
number means anything. Kraken's public REST `Trades` endpoint serves full tick history
(price, volume, time, taker side), so the 30d multi-regime tape is reconstructable today —
this quickens the Kraken validation from "wait weeks for book accrual" to "price/flow answer
now, fill/queue answer accrues" (books stay the only source for depth truth).

Same output bin schema as the other backfills (interchangeable with load_bins):
    {ts_1sec: {"buy": taker_buy_vol, "sell": taker_sell_vol, "mid": last_px,
               "high": hi, "low": lo, "n_trades": n}}

Kraken REST specifics:
  - GET /0/public/Trades?pair=<PAIR>&since=<ns_cursor>&count=1000
    result: {<canonical_pair_key>: [[px, vol, t_sec, side, ordertype, misc, id]...],
             "last": <ns cursor for the next page>}
  - `side` is the TAKER side ('b' buy / 's' sell) — same convention as the S37 WS collector.
  - REST pair names differ from WS v2: BTC = XBTUSD, DOGE = XDGUSD (the legacy names live
    on REST; WS v2 uses BTC/USD, DOGE/USD).
  - Public rate limit ~1 req/s per IP: paced at PACE_S with exponential backoff on errors;
    a cursor checkpoint + periodic bin saves make the pull fully resumable.

Run (one coin):
    python backfill_kraken_trades.py --pair SOLUSD --days 30 \
        --bins-path /tmp/kraken_backfill/SOLUSD_30d_bins.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request

API = "https://api.kraken.com/0/public/Trades?pair={pair}&since={since}&count=1000"
SECOND_BIN_S = 1.0
PACE_S = 1.05           # public-endpoint pacing (~1 req/s sustained)
SAVE_EVERY = 50         # pages between checkpoint saves


def _get(url: str, tries: int = 6) -> dict | None:
    back = 2.0
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "markets-backfill/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                d = json.loads(resp.read())
            if d.get("error"):
                # EAPI:Rate limit / EService:Unavailable etc — back off, retry
                print(f"[kr-backfill] api error {d['error']}; backoff {back:.0f}s", flush=True)
                time.sleep(back)
                back = min(back * 2, 60)
                continue
            return d["result"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            print(f"[kr-backfill] {type(e).__name__}: {e}; backoff {back:.0f}s", flush=True)
            time.sleep(back)
            back = min(back * 2, 60)
    return None


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return {float(k): v for k, v in json.load(f).items()}


def _save(bins: dict, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({str(k): v for k, v in bins.items()}, f)
    os.replace(tmp, path)


def ingest(bins: dict, trades: list) -> int:
    n = 0
    for px_s, vol_s, t, side, *_rest in trades:
        px, vol = float(px_s), float(vol_s)
        ts = int(float(t) / SECOND_BIN_S) * SECOND_BIN_S
        b = bins.setdefault(ts, {"buy": 0.0, "sell": 0.0, "mid": px,
                                 "high": 0.0, "low": 0.0, "n_trades": 0})
        if side == "b":                 # taker bought
            b["buy"] += vol
        else:
            b["sell"] += vol
        if b["high"] == 0.0 or px > b["high"]:
            b["high"] = px
        if b["low"] == 0.0 or px < b["low"]:
            b["low"] = px
        b["mid"] = px
        b["n_trades"] += 1
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True, help="Kraken REST pair, e.g. SOLUSD, XBTUSD, XDGUSD")
    ap.add_argument("--days", type=float, default=30.0)
    ap.add_argument("--bins-path", required=True)
    a = ap.parse_args()

    ckpt = a.bins_path + ".cursor"
    t_end = time.time()
    t_start = t_end - a.days * 86400.0
    since = int(t_start * 1e9)
    if os.path.exists(ckpt):
        with open(ckpt) as f:
            since = int(f.read().strip())
        print(f"[kr-backfill] resume cursor {since}", flush=True)

    bins = _load(a.bins_path)
    total = 0
    page = 0
    t0 = time.time()
    while True:
        res = _get(API.format(pair=a.pair, since=since))
        if res is None:
            print("[kr-backfill] giving up after retries; checkpoint kept", flush=True)
            break
        last = int(res.pop("last", since))
        rows = next(iter(res.values()), [])
        total += ingest(bins, rows)
        page += 1
        done = last <= since or (rows and float(rows[-1][2]) >= t_end) or not rows
        since = max(last, since)
        if page % SAVE_EVERY == 0 or done:
            _save(bins, a.bins_path)
            with open(ckpt, "w") as f:
                f.write(str(since))
            cov_h = (float(rows[-1][2]) - t_start) / 3600.0 if rows else 0.0
            print(f"[kr-backfill] {a.pair} page {page}: {total:,} trades, "
                  f"{len(bins):,} bins, tape reaches +{cov_h:.1f}h "
                  f"({time.time()-t0:.0f}s elapsed)", flush=True)
        if done:
            print(f"[kr-backfill] {a.pair} DONE: {total:,} trades -> {len(bins):,} bins "
                  f"({a.days:.0f}d) saved {a.bins_path}", flush=True)
            break
        time.sleep(PACE_S)


if __name__ == "__main__":
    main()
