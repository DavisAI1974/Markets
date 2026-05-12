"""Append current Bybit perp funding/OI snapshots to local JSONL history.

This is not a true historical backfill. It is a durable forward collector for
environments where Bybit REST history is geoblocked but the public linear
ticker WebSocket is still reachable.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from typing import Iterable

from bybit_public_tickers import fetch_bybit_ticker_snapshots


SOURCES = [
    ("BTC", "Bybit", "BTCUSDT"),
    ("ETH", "Bybit", "ETHUSDT"),
]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def _load_funding_seen(path: str) -> set[tuple[str, str, int]]:
    seen: set[tuple[str, str, int]] = set()
    if not path or not os.path.exists(path):
        return seen
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                asset = str(row.get("asset") or "")
                venue = str(row.get("venue") or "")
                ts = int(_safe_float(row.get("next_funding_ts"), 0.0))
                if asset and venue and ts > 0:
                    seen.add((asset, venue, ts))
    except Exception:
        return seen
    return seen


def _load_last_oi_ts(path: str) -> dict[tuple[str, str], float]:
    last: dict[tuple[str, str], float] = {}
    if not path or not os.path.exists(path):
        return last
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                asset = str(row.get("asset") or "")
                venue = str(row.get("venue") or "")
                ts = _safe_float(row.get("ts_utc"), 0.0)
                if asset and venue and ts > 0:
                    prev = last.get((asset, venue), 0.0)
                    if ts > prev:
                        last[(asset, venue)] = ts
    except Exception:
        return last
    return last


def _append_jsonl(path: str, rows: Iterable[dict]) -> int:
    kept = 0
    rows_list = [row for row in rows if isinstance(row, dict)]
    if not rows_list:
        return 0
    with open(path, "a") as fh:
        for row in rows_list:
            fh.write(json.dumps(row) + "\n")
            kept += 1
    return kept


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--funding-output-path", default="backend_funding_history.jsonl")
    p.add_argument("--oi-output-path", default="backend_oi_history.jsonl")
    p.add_argument("--min-oi-gap-sec", type=float, default=600.0)
    p.add_argument("--timeout-sec", type=float, default=20.0)
    args = p.parse_args()

    funding_seen = _load_funding_seen(args.funding_output_path)
    last_oi_ts = _load_last_oi_ts(args.oi_output_path)
    snaps = fetch_bybit_ticker_snapshots(
        [symbol for _, _, symbol in SOURCES],
        timeout_s=args.timeout_sec,
    )

    funding_rows: list[dict] = []
    oi_rows: list[dict] = []
    for asset, venue, symbol in SOURCES:
        snap = snaps.get(symbol) or {}
        if not snap:
            print(f"[bybit-history] missing snapshot for {asset}/{symbol}", flush=True)
            continue
        obs_ts = _safe_float(snap.get("_ws_ts"), 0.0)
        funding_rate = _safe_float(snap.get("fundingRate"), float("nan"))
        next_funding_ts = _safe_float(snap.get("nextFundingTime"), 0.0) / 1000.0
        open_interest = _safe_float(snap.get("openInterest"), 0.0)
        last_price = _safe_float(snap.get("lastPrice"), 0.0)
        if last_price <= 0:
            last_price = _safe_float(snap.get("markPrice"), 0.0)

        if math.isfinite(funding_rate) and next_funding_ts > 0:
            funding_key = (asset, venue, int(next_funding_ts))
            if funding_key not in funding_seen:
                funding_seen.add(funding_key)
                funding_rows.append({
                    "ts_utc": obs_ts,
                    "asset": asset,
                    "venue": venue,
                    "symbol": symbol,
                    "rate": funding_rate,
                    "next_funding_ts": next_funding_ts,
                })

        last_seen_ts = last_oi_ts.get((asset, venue), 0.0)
        if open_interest > 0 and last_price > 0 and obs_ts > 0:
            if (obs_ts - last_seen_ts) >= args.min_oi_gap_sec:
                oi_rows.append({
                    "ts_utc": obs_ts,
                    "asset": asset,
                    "venue": venue,
                    "symbol": symbol,
                    "oi": open_interest,
                    "price": last_price,
                })
                last_oi_ts[(asset, venue)] = obs_ts

        print(
            f"[bybit-history] {asset}/{symbol} "
            f"funding={funding_rate:+.6f} next={next_funding_ts:.0f} "
            f"oi={open_interest:.3f} price={last_price:.2f}",
            flush=True,
        )

    n_funding = _append_jsonl(args.funding_output_path, funding_rows)
    n_oi = _append_jsonl(args.oi_output_path, oi_rows)
    print(
        f"[bybit-history] wrote funding +{n_funding} rows to {args.funding_output_path}; "
        f"oi +{n_oi} rows to {args.oi_output_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
