"""
pyth_backfill.py — HISTORICAL per-second NYMEX tape from Pyth Hermes (S84).

Why: NYMEX is the canary (leads Kalshi; see NYMEX_CANARY_NOTES_S84.md). To characterize event moves
and validate the lag WITHOUT waiting for the next live release, backfill the futures tape around PAST
release windows from Pyth's historical timestamp endpoint.

Endpoint: GET /v2/updates/price/{unix_ts}?ids[]={feed}  -> the price update at/just-before that second.
Walk the window second-by-second -> reconstruct a ~1-sec tape. HONEST LIMIT (Greg): NYMEX prints faster
than 1/sec around a release, so this UNDERSAMPLES — every readout off it is a LOWER BOUND on move
speed/count, never the full tape. Tagged src="pyth_hist_1s" so it is never confused with the live SSE
feed (which is finer). WTI ONLY: Pyth has no natural gas feed, and Brent-historical 404s (see notes).

Rate limit: the public endpoint 429s after a few rapid calls -> throttle (~2-3 req/s) + backoff.

Output: data/pyth_ticks/{symbol}_{YYYYMMDD}.jsonl, records {"ts","price","conf","symbol","src"} — the
same shape the live collector writes, so the lag/backfill code consumes both identically. Zero synthetic.

CLI:
  python research/kalshi/pyth_backfill.py --symbol WTIQ6 --release 2026-07-08T14:30:00Z --pre 60 --post 300
  python research/kalshi/pyth_backfill.py --symbol WTIQ6 --releases eia_crude_dates.txt --pre 120 --post 1800
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERMES = "https://hermes.pyth.network"

# Full 64-char feed ids. WTIQ6 from pyth_collector.py; extend the WTI curve as needed (resolve via
# --feed-id or the catalog). Pyth has the full monthly WTI curve WTIF6..WTIZ6.
KNOWN_FEEDS = {
    "WTIQ6": "05e7c9b556df67e455c52ea2d31658744e3f4ade60db7dab887008844f2ae472",
}


def resolve_feed(symbol: str, override: str | None) -> str:
    """Feed id from --feed-id, the known table, or the Pyth catalog (Commodities.{symbol}/USD)."""
    if override:
        return override
    if symbol in KNOWN_FEEDS:
        return KNOWN_FEEDS[symbol]
    url = f"{HERMES}/v2/price_feeds?query={urllib.parse.quote(symbol)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    feeds = json.loads(urllib.request.urlopen(req, timeout=25).read())
    want = f"Commodities.{symbol}/USD"
    for f in feeds:
        if f.get("attributes", {}).get("symbol") == want:
            return f["id"]
    raise SystemExit(f"[backfill] could not resolve feed id for {symbol} (Pyth may not carry it)")


def price_at(feed: str, ts: int, throttle: list[float]) -> tuple[float, float, int] | None:
    """(price, conf, publish_time) at/just-before ts, or None if no update (404). Adaptive throttle +
    429 backoff via throttle[0] (current inter-request sleep)."""
    url = f"{HERMES}/v2/updates/price/{ts}?ids[]={feed}"
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read())
            parsed = d.get("parsed") or []
            if not parsed:
                return None
            p = parsed[0]["price"]
            scale = 10.0 ** int(p["expo"])
            return int(p["price"]) * scale, int(p["conf"]) * scale, int(p["publish_time"])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 or e.code >= 500:                 # rate-limit OR transient 5xx (520 CF)
                if e.code == 429:
                    throttle[0] = min(throttle[0] * 1.5, 3.0)  # persistent slow-down only on 429
                time.sleep(2.0 * (attempt + 1) ** 2)           # 2,8,18,32,50s backoff
                continue
            raise
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return None


def backfill_window(symbol: str, feed: str, release_ts: int, pre: int, post: int,
                    step: int, out_dir: str, throttle: list[float]) -> int:
    """Walk [release-pre, release+post] at `step` seconds; dedup on ADVANCING publish_time (a real new
    tick); append to the per-day file. Returns distinct ticks written."""
    os.makedirs(out_dir, exist_ok=True)
    handles: dict[str, object] = {}
    last_pub = -1
    n = 0
    total = (pre + post) // step + 1
    for i, sec in enumerate(range(-pre, post + 1, step)):
        ts = release_ts + sec
        res = price_at(feed, ts, throttle)
        time.sleep(throttle[0])
        if res is None:
            continue
        px, conf, pub = res
        if pub <= last_pub:                                    # not a new tick -> skip (dedup)
            continue
        last_pub = pub
        day = datetime.fromtimestamp(pub, timezone.utc).strftime("%Y%m%d")
        fh = handles.get(day)
        if fh is None:
            fh = open(os.path.join(out_dir, f"{symbol}_{day}.jsonl"), "a", buffering=1)
            handles[day] = fh
        fh.write(json.dumps({"ts": float(pub), "price": px, "conf": conf,
                             "symbol": symbol, "src": "pyth_hist_1s"}) + "\n")
        n += 1
        if i % 60 == 0:
            rel = datetime.fromtimestamp(release_ts, timezone.utc).strftime("%m-%d %H:%M")
            print(f"  [{symbol} @ {rel}] {i}/{total} probed, {n} distinct ticks "
                  f"(throttle {throttle[0]:.2f}s)")
    for fh in handles.values():
        fh.close()
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Historical per-second NYMEX backfill from Pyth Hermes")
    ap.add_argument("--symbol", required=True, help="e.g. WTIQ6 (WTI only — Pyth has no NG)")
    ap.add_argument("--feed-id", default=None, help="override the 64-char feed id")
    ap.add_argument("--release", default=None, help="single release RFC3339, e.g. 2026-07-08T14:30:00Z")
    ap.add_argument("--releases", default=None, help="file of RFC3339 release timestamps, one per line")
    ap.add_argument("--pre", type=int, default=60, help="seconds before release")
    ap.add_argument("--post", type=int, default=300, help="seconds after release")
    ap.add_argument("--step", type=int, default=1, help="sampling step seconds (1 = per-second floor)")
    ap.add_argument("--throttle", type=float, default=0.35, help="initial inter-request sleep (s)")
    ap.add_argument("--out-dir", default="data/pyth_ticks")
    args = ap.parse_args()

    feed = resolve_feed(args.symbol, args.feed_id)
    releases: list[str] = []
    if args.release:
        releases.append(args.release)
    if args.releases:
        releases += [ln.strip() for ln in open(args.releases) if ln.strip() and not ln.startswith("#")]
    if not releases:
        raise SystemExit("[backfill] give --release or --releases")

    throttle = [args.throttle]
    grand = 0
    for r in releases:
        rt = int(datetime.fromisoformat(r.replace("Z", "+00:00")).timestamp())
        print(f"[backfill] {args.symbol} window [-{args.pre}s,+{args.post}s] around {r}")
        got = backfill_window(args.symbol, feed, rt, args.pre, args.post, args.step,
                              args.out_dir, throttle)
        print(f"[backfill] -> {got} distinct ticks written")
        grand += got
    print(f"[backfill] DONE: {grand} distinct ticks across {len(releases)} window(s) -> {args.out_dir}")


if __name__ == "__main__":
    main()
