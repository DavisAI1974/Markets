"""S35b — extract a COMPACT minute-bar test slice into the markets repo so the encoder/onset canary
runs standalone (no 9GB live_data_history). Winner onsets span only 2026-05-23/24; we take
05-22..05-24 (covers the 180-min pre-entry lookback) for the 6 winner venues, aggregate seconds->
minute MarketBars, and write per-venue compact JSON. ~1-2MB total.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

HIST = Path(r"E:\Markets\live_data_history")
OUT = Path(r"E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6\fingerprint_dataset\test_bars")
DATES = ["2026-05-22", "2026-05-23", "2026-05-24"]
# (asset, venue) -> live_data_history bin stem
STEMS = {("BTC", "Bybit"): "btc_bybit_perp", ("BTC", "Coinbase"): "btc_coinbase",
         ("BTC", "Kraken"): "btc_kraken", ("ETH", "Bybit"): "eth_bybit_perp",
         ("ETH", "Coinbase"): "eth_coinbase", ("ETH", "Kraken"): "eth_kraken"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for (asset, venue), stem in STEMS.items():
        sec = {}
        for d in DATES:
            fp = HIST / d / f"{stem}_bins.jsonl"
            if not fp.exists():
                continue
            for ln in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    b = json.loads(ln)
                except ValueError:
                    continue
                ts = float(b.get("ts") or 0)
                if ts > 0 and (b.get("mid") or b.get("close")) is not None:
                    sec[ts] = b
        groups = defaultdict(list)
        for ts, b in sec.items():
            groups[int(ts / 60.0) * 60.0].append((ts, b))
        bars = []
        for m in sorted(groups):
            mem = sorted(groups[m], key=lambda x: x[0])
            mids = [float(b.get("mid") or b.get("close")) for _, b in mem if (b.get("mid") or b.get("close"))]
            if not mids:
                continue
            bars.append({"ts": m, "close": mids[-1], "open": mids[0], "high": max(mids), "low": min(mids),
                         "buy_vol": float(sum(b.get("buy") or 0 for _, b in mem)),
                         "sell_vol": float(sum(b.get("sell") or 0 for _, b in mem))})
        out_fp = OUT / f"{stem}_minbars.json"
        out_fp.write_text(json.dumps({"asset": asset, "venue": venue, "stem": stem,
                                      "dates": DATES, "bars": bars}), encoding="utf-8")
        print(f"  {stem:18s} {len(bars):>5d} minute bars -> {out_fp.name}")
        total += len(bars)
    sz = sum(f.stat().st_size for f in OUT.glob("*.json")) / 1e6
    print(f"\n{total} minute bars across {len(STEMS)} venues; {sz:.1f}MB total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
