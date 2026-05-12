"""
backfill_oi_history.py — fetch historical 1h open interest into the backend
JSONL schema expected by calibrate_oi.py and the offline feature loaders.

Like the funding backfill, public exchange endpoints may geoblock from this
US-based local environment; the script is still intended for the remote box.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request


SOURCES = [
    ("BTC", "Binance", "BTCUSDT"),
    ("ETH", "Binance", "ETHUSDT"),
    ("BTC", "Bybit", "BTCUSDT"),
    ("ETH", "Bybit", "ETHUSDT"),
]
HTTP_TIMEOUT_S = 12.0
ONE_HOUR_MS = 60 * 60 * 1000


def _http_get_json(url: str):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "markets-backfill-oi/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read())


def _fetch_binance(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    rows: list[dict] = []
    cursor = start_ms
    step_ms = 500 * ONE_HOUR_MS
    while cursor <= end_ms:
        window_end = min(end_ms, cursor + step_ms)
        query = urllib.parse.urlencode({
            "symbol": symbol,
            "period": "1h",
            "startTime": cursor,
            "endTime": window_end,
            "limit": 500,
        })
        body = _http_get_json(f"https://fapi.binance.com/futures/data/openInterestHist?{query}")
        if not isinstance(body, list) or not body:
            break
        parsed = []
        for item in body:
            try:
                ts_ms = int(item["timestamp"])
                oi = float(item["sumOpenInterest"])
            except (KeyError, TypeError, ValueError):
                continue
            parsed.append({
                "ts_utc": ts_ms / 1000.0,
                "asset": None,
                "venue": "Binance",
                "symbol": symbol,
                "oi": oi,
                "price": 0.0,
            })
        if not parsed:
            break
        parsed.sort(key=lambda row: row["ts_utc"])
        rows.extend(parsed)
        last_ts = int(parsed[-1]["ts_utc"] * 1000)
        if last_ts <= cursor:
            break
        cursor = last_ts + 1
    return rows


def _fetch_bybit(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    rows: list[dict] = []
    cursor_token = ""
    while True:
        params = {
            "category": "linear",
            "symbol": symbol,
            "intervalTime": "1h",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 200,
        }
        if cursor_token:
            params["cursor"] = cursor_token
        query = urllib.parse.urlencode(params)
        body = _http_get_json(f"https://api.bybit.com/v5/market/open-interest?{query}")
        if not isinstance(body, dict) or body.get("retCode") != 0:
            break
        result = body.get("result") or {}
        items = result.get("list") or []
        if not items:
            break
        for item in items:
            try:
                ts_ms = int(item["timestamp"])
                oi = float(item["openInterest"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append({
                "ts_utc": ts_ms / 1000.0,
                "asset": None,
                "venue": "Bybit",
                "symbol": symbol,
                "oi": oi,
                "price": 0.0,
            })
        cursor_token = str(result.get("nextPageCursor") or "")
        if not cursor_token:
            break
    rows.sort(key=lambda row: row["ts_utc"])
    return rows


def _load_existing(path: str) -> tuple[list[dict], set[tuple[str, str, int]]]:
    rows: list[dict] = []
    seen: set[tuple[str, str, int]] = set()
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
                if not isinstance(row, dict):
                    continue
                rows.append(row)
                asset = str(row.get("asset") or "")
                venue = str(row.get("venue") or "")
                ts = int(float(row.get("ts_utc") or 0.0))
                if asset and venue and ts > 0:
                    seen.add((asset, venue, ts))
    except FileNotFoundError:
        return [], set()
    return rows, seen


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--output-path", default="backend_oi_history.jsonl")
    p.add_argument("--append", action="store_true")
    args = p.parse_args()

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - args.days * 24 * 60 * 60 * 1000

    existing_rows, seen = _load_existing(args.output_path) if args.append else ([], set())
    new_rows: list[dict] = []
    for asset, venue, symbol in SOURCES:
        print(f"[oi-backfill] {asset}/{venue} {symbol}", flush=True)
        try:
            fetched = (
                _fetch_binance(symbol, start_ms, end_ms)
                if venue == "Binance" else
                _fetch_bybit(symbol, start_ms, end_ms)
            )
        except urllib.error.HTTPError as exc:
            print(f"  HTTP {exc.code}; source blocked or unavailable", flush=True)
            continue
        except Exception as exc:
            print(f"  error: {type(exc).__name__}: {exc}", flush=True)
            continue
        kept = 0
        for row in fetched:
            row["asset"] = asset
            key = (asset, venue, int(float(row["ts_utc"])))
            if key in seen:
                continue
            seen.add(key)
            new_rows.append(row)
            kept += 1
        print(f"  fetched={len(fetched)} appended={kept}", flush=True)

    all_rows = existing_rows + new_rows
    all_rows.sort(key=lambda row: (
        str(row.get("asset") or ""),
        str(row.get("venue") or ""),
        float(row.get("ts_utc") or 0.0),
    ))
    with open(args.output_path, "w") as fh:
        for row in all_rows:
            fh.write(json.dumps(row) + "\n")
    print(f"[oi-backfill] wrote {args.output_path}: +{len(new_rows)} new rows ({len(all_rows)} total)")


if __name__ == "__main__":
    main()
