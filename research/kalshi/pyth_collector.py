"""
pyth_collector.py — sub-second tick collector for the NYMEX/ICE futures Kalshi settles on, via Pyth Hermes.

The S81 finding: futures LEAD Kalshi and the lag edge is real but SIZE-vs-fee-bound at 1-min resolution
(median reprice ~1c < fee; only big moves clear). The edge lives BELOW one minute — to see the intra-minute
NYMEX move and capture the FULL reprice before it decays, we need the real tick feed. Pyth is Kalshi's own
settlement source (Henry Hub NG, WTI, Brent), sub-second, public (no key), and reachable through the proxy.

Feeds = the CURRENT FRONT-MONTH contracts (roll dates noted; re-point when they expire):
  WTIQ6   WTI  exp 2026-07-21   (KXWTI  = Cushing/ICE-settle, front-month NYMEX driver)
  NGDQ6   Henry Hub NG exp 2026-07-29 (KXNATGASD)
  BRENTU6 Brent exp 2026-07-31  (KXBRENTD)

Stores raw ticks to data/pyth_ticks/<symbol>_<YYYYMMDD>.jsonl (LOCAL, gitignored): {ts, price, conf, symbol}.
ts = Pyth publish_time (sub-second float where available). Skips price==0 / publish_time==0 (market closed).
Streaming via Hermes SSE (real-time push); reconnects with backoff. Zero synthetic — every tick is a real
oracle print.

Usage:
  python research/kalshi/pyth_collector.py                      # stream all 3, forever (durable)
  python research/kalshi/pyth_collector.py --seconds 30         # short capture / connection test
  python research/kalshi/pyth_collector.py --symbols NGDQ6      # one feed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

HERMES = "https://hermes.pyth.network"
OUT_DIR = "data/pyth_ticks"

# front-month feed IDs (see roll dates in the module docstring)
FEEDS = {
    "WTIQ6":   "05e7c9b556df67e455c52ea2d31658744e3f4ade60db7dab887008844f2ae472",
    "NGDQ6":   "3ea3adf4dfa7eed79e357c9bdf8a15c6d4dc8fb5454cf71110c73390fb230436",
    "BRENTU6": "93fdb7c6f23c6ba97baf2f086891e6749461a5f6cd620338102845acf210e96b",
}
_ID2SYM = {v: k for k, v in FEEDS.items()}


def _px(p: dict) -> tuple[float, float, float]:
    """Pyth price obj -> (price, conf, publish_time). price = mantissa * 10^expo."""
    expo = int(p["expo"])
    scale = 10.0 ** expo
    return int(p["price"]) * scale, int(p["conf"]) * scale, float(p.get("publish_time", 0))


def _writer(out_dir: str):
    """Return append(symbol, rec) that writes to a per-symbol per-UTC-day JSONL (opened lazily, line-buffered)."""
    os.makedirs(out_dir, exist_ok=True)
    handles: dict[tuple[str, str], object] = {}

    def append(symbol: str, rec: dict) -> None:
        day = datetime.fromtimestamp(rec["ts"], timezone.utc).strftime("%Y%m%d")
        key = (symbol, day)
        fh = handles.get(key)
        if fh is None:
            fh = open(os.path.join(out_dir, f"{symbol}_{day}.jsonl"), "a", buffering=1)
            handles[key] = fh
        fh.write(json.dumps(rec) + "\n")
    return append, handles


def stream(symbols: list[str], out_dir: str, seconds: float | None) -> None:
    ids = [FEEDS[s] for s in symbols]
    url = HERMES + "/v2/updates/price/stream?" + "&".join(f"ids[]={i}" for i in ids)
    append, handles = _writer(out_dir)
    start = time.time()
    n_ticks = 0
    n_stale = 0
    backoff = 1.0
    last_report = start
    last_pub: dict[str, float] = {}          # per-symbol: only record when publish_time ADVANCES (real new tick)
    while True:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/event-stream"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                backoff = 1.0
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        payload = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    for item in payload.get("parsed", []):
                        sym = _ID2SYM.get(item["id"], item["id"][:8])
                        price, conf, pub = _px(item["price"])
                        if price == 0.0 or pub == 0.0 or pub <= last_pub.get(sym, 0.0):
                            n_stale += 1                          # closed, or a frozen repeat of the last price
                            continue
                        last_pub[sym] = pub
                        append(sym, {"ts": pub, "price": round(price, 6),
                                     "conf": round(conf, 6), "symbol": sym})
                        n_ticks += 1
                    now = time.time()
                    if now - last_report >= 10:
                        print(f"[pyth] {n_ticks} ticks ({n_stale} stale/closed) "
                              f"{int(now - start)}s elapsed", flush=True)
                        last_report = now
                    if seconds is not None and now - start >= seconds:
                        print(f"[pyth] done: {n_ticks} ticks, {n_stale} stale in {int(now - start)}s", flush=True)
                        for fh in handles.values():
                            fh.close()
                        return
        except KeyboardInterrupt:
            print(f"[pyth] stopped: {n_ticks} ticks", flush=True)
            for fh in handles.values():
                fh.close()
            return
        except Exception as e:                                    # network / stream drop -> reconnect
            if seconds is not None and time.time() - start >= seconds:
                for fh in handles.values():
                    fh.close()
                return
            print(f"[pyth] stream error ({type(e).__name__}: {e}); reconnect in {backoff:.0f}s", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


def main() -> None:
    ap = argparse.ArgumentParser(description="Pyth Hermes sub-second futures tick collector")
    ap.add_argument("--symbols", nargs="*", default=list(FEEDS), choices=list(FEEDS))
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--seconds", type=float, default=None, help="stop after N seconds (omit = run forever)")
    args = ap.parse_args()
    print(f"[pyth] streaming {args.symbols} -> {args.out_dir}  "
          f"({'forever' if args.seconds is None else str(args.seconds) + 's'})", flush=True)
    stream(args.symbols, args.out_dir, args.seconds)


if __name__ == "__main__":
    main()
