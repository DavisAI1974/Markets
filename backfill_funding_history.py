"""
backfill_funding_history.py — fetch historical perp funding into the backend
JSONL schema expected by calibrate_funding.py and the offline feature loaders.

Note: from this US-based dev environment, Binance/Bybit may geoblock the HTTP
requests (451/403). The script is still useful on the remote box where the
backend pollers already run.
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
FUNDING_INTERVAL_MS = 8 * 60 * 60 * 1000


def _http_get_json(url: str):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "markets-backfill-funding/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read())


def _fetch_binance(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    rows: list[dict] = []
    cursor = start_ms
    while cursor <= end_ms:
        query = urllib.parse.urlencode({
            "symbol": symbol,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": 1000,
        })
        body = _http_get_json(f"https://fapi.binance.com/fapi/v1/fundingRate?{query}")
        if not isinstance(body, list) or not body:
            break
        parsed = []
        for item in body:
            try:
                ts_ms = int(item["fundingTime"])
                rate = float(item["fundingRate"])
            except (KeyError, TypeError, ValueError):
                continue
            parsed.append({
                "ts_utc": ts_ms / 1000.0,
                "asset": None,
                "venue": "Binance",
                "symbol": symbol,
                "rate": rate,
                "next_funding_ts": ts_ms / 1000.0,
            })
        if not parsed:
            break
        rows.extend(parsed)
        last_ts = int(parsed[-1]["next_funding_ts"] * 1000)
        if last_ts <= cursor:
            break
        cursor = last_ts + 1
    return rows


def _fetch_bybit(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    rows: list[dict] = []
    cursor = start_ms
    while cursor <= end_ms:
        window_end = min(end_ms, cursor + 199 * FUNDING_INTERVAL_MS)
        query = urllib.parse.urlencode({
            "category": "linear",
            "symbol": symbol,
            "startTime": cursor,
            "endTime": window_end,
            "limit": 200,
        })
        body = _http_get_json(f"https://api.bybit.com/v5/market/funding/history?{query}")
        if not isinstance(body, dict) or body.get("retCode") != 0:
            break
        items = (body.get("result") or {}).get("list") or []
        if not items:
            break
        parsed = []
        for item in items:
            try:
                ts_ms = int(item["fundingRateTimestamp"])
                rate = float(item["fundingRate"])
            except (KeyError, TypeError, ValueError):
                continue
            parsed.append({
                "ts_utc": ts_ms / 1000.0,
                "asset": None,
                "venue": "Bybit",
                "symbol": symbol,
                "rate": rate,
                "next_funding_ts": ts_ms / 1000.0,
            })
        if not parsed:
            break
        parsed.sort(key=lambda row: row["next_funding_ts"])
        rows.extend(parsed)
        last_ts = int(parsed[-1]["next_funding_ts"] * 1000)
        if last_ts <= cursor:
            break
        cursor = last_ts + 1
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
                ts = int(float(row.get("next_funding_ts") or row.get("ts_utc") or 0.0))
                if asset and venue and ts > 0:
                    seen.add((asset, venue, ts))
    except FileNotFoundError:
        return [], set()
    return rows, seen


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--output-path", default="backend_funding_history.jsonl")
    p.add_argument("--append", action="store_true")
    args = p.parse_args()

    end_ms = int(time.time() * 1000)
    start_ms = end_ms - args.days * 24 * 60 * 60 * 1000

    existing_rows, seen = _load_existing(args.output_path) if args.append else ([], set())
    new_rows: list[dict] = []
    for asset, venue, symbol in SOURCES:
        print(f"[fund-backfill] {asset}/{venue} {symbol}", flush=True)
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
            key = (asset, venue, int(float(row["next_funding_ts"])))
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
        float(row.get("next_funding_ts") or row.get("ts_utc") or 0.0),
    ))
    with open(args.output_path, "w") as fh:
        for row in all_rows:
            fh.write(json.dumps(row) + "\n")
    print(f"[fund-backfill] wrote {args.output_path}: +{len(new_rows)} new rows ({len(all_rows)} total)")


if __name__ == "__main__":
    main()
