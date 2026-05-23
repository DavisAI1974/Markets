"""
live_collectors.py - one-process public-market live feed for markets-watch.

Collects live spot and perp market data into the same 1-second bin schema
consumed by backend.api_server, but into live_data/ so the proof-of-concept
can run without mutating the historical research files.

No exchange auth is required.

Run:
  python live_collectors.py --reset
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import websockets


SECOND_BIN_S = 1.0
ARCHIVE_REWRITE_SECONDS = 5.0

_ARCHIVE_WATERMARKS: dict[str, float] = {}


@dataclass(frozen=True)
class FeedSpec:
    asset: str
    venue: str
    kind: str
    symbol: str
    path: str
    label: str


FEEDS = [
    FeedSpec("BTC", "Coinbase", "coinbase", "BTC-USD", "btc_coinbase_bins.json", "cb-btc"),
    FeedSpec("ETH", "Coinbase", "coinbase", "ETH-USD", "eth_coinbase_bins.json", "cb-eth"),
    FeedSpec("XRP", "Coinbase", "coinbase", "XRP-USD", "xrp_coinbase_bins.json", "cb-xrp"),
    FeedSpec("DOGE", "Coinbase", "coinbase", "DOGE-USD", "doge_coinbase_bins.json", "cb-doge"),
    FeedSpec("LINK", "Coinbase", "coinbase", "LINK-USD", "link_coinbase_bins.json", "cb-link"),
    FeedSpec("BTC", "Kraken", "kraken", "BTC/USD", "btc_kraken_bins.json", "kr-btc"),
    FeedSpec("ETH", "Kraken", "kraken", "ETH/USD", "eth_kraken_bins.json", "kr-eth"),
    FeedSpec("XRP", "Kraken", "kraken", "XRP/USD", "xrp_kraken_bins.json", "kr-xrp"),
    FeedSpec("DOGE", "Kraken", "kraken", "DOGE/USD", "doge_kraken_bins.json", "kr-doge"),
    FeedSpec("LINK", "Kraken", "kraken", "LINK/USD", "link_kraken_bins.json", "kr-link"),
    FeedSpec("BTC", "Bybit", "bybit", "BTCUSDT", "btc_bybit_perp_bins.json", "by-btc"),
    FeedSpec("ETH", "Bybit", "bybit", "ETHUSDT", "eth_bybit_perp_bins.json", "by-eth"),
    FeedSpec("XRP", "Bybit", "bybit", "XRPUSDT", "xrp_bybit_perp_bins.json", "by-xrp"),
    FeedSpec("DOGE", "Bybit", "bybit", "DOGEUSDT", "doge_bybit_perp_bins.json", "by-doge"),
    FeedSpec("LINK", "Bybit", "bybit", "LINKUSDT", "link_bybit_perp_bins.json", "by-link"),
]


def _bin_ts() -> float:
    return int(time.time() / SECOND_BIN_S) * SECOND_BIN_S


def _blank_bin(mid: float | None = None) -> dict[str, Any]:
    return {
        "buy": 0.0,
        "sell": 0.0,
        "mid": mid,
        "high": 0.0,
        "low": 0.0,
        "n_trades": 0,
        "bid": 0.0,
        "ask": 0.0,
        "bid_qty": 0.0,
        "ask_qty": 0.0,
        "last_aggressor": "",
    }


def _touch_price(b: dict[str, Any], price: float) -> None:
    if b["high"] == 0.0 or price > b["high"]:
        b["high"] = price
    if b["low"] == 0.0 or price < b["low"]:
        b["low"] = price
    if not b.get("mid"):
        b["mid"] = price


def _load_bins(path: str) -> dict[float, dict[str, Any]]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return {float(k): v for k, v in raw.items()}
    except Exception as exc:
        print(f"[live] could not load {path}: {exc}", flush=True)
        return {}


def _existing_archive_watermark(path: str, archive_dir: str) -> float | None:
    file_name = os.path.basename(path).replace(".json", ".jsonl")
    latest: float | None = None
    try:
        day_dirs = sorted(
            (entry for entry in os.scandir(archive_dir) if entry.is_dir()),
            key=lambda entry: entry.name,
            reverse=True,
        )
    except FileNotFoundError:
        return None
    for day_dir in day_dirs:
        archive_path = os.path.join(day_dir.path, file_name)
        if not os.path.exists(archive_path):
            continue
        try:
            with open(archive_path, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    ts = float(row.get("ts", 0.0))
                    if latest is None or ts > latest:
                        latest = ts
        except Exception as exc:
            print(f"[live] could not scan archive {archive_path}: {exc}", flush=True)
        if latest is not None:
            return latest
    return latest


def _archive_bins(path: str, bins: dict[float, dict[str, Any]], archive_dir: str) -> None:
    if not archive_dir or not bins:
        return
    max_ts = max(bins)
    watermark = _ARCHIVE_WATERMARKS.get(path)
    if watermark is None:
        watermark = _existing_archive_watermark(path, archive_dir)
    if watermark is None:
        rows = sorted(bins.items())
    else:
        cutoff = watermark - ARCHIVE_REWRITE_SECONDS
        rows = sorted((ts, b) for ts, b in bins.items() if ts >= cutoff)
    if not rows:
        return

    grouped: dict[str, list[tuple[float, dict[str, Any]]]] = {}
    for ts, b in rows:
        day = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
        grouped.setdefault(day, []).append((ts, b))

    file_name = os.path.basename(path).replace(".json", ".jsonl")
    for day, day_rows in grouped.items():
        out_dir = os.path.join(archive_dir, day)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, file_name)
        with open(out_path, "a", encoding="utf-8") as f:
            for ts, b in day_rows:
                row = {"ts": ts, **b}
                f.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")
    _ARCHIVE_WATERMARKS[path] = max_ts


def _save_bins(path: str, bins: dict[float, dict[str, Any]], keep_seconds: int) -> None:
    if keep_seconds > 0 and bins:
        cutoff = max(bins) - keep_seconds
        old = [ts for ts in bins if ts < cutoff]
        for ts in old:
            del bins[ts]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in bins.items()}, f, separators=(",", ":"))
    os.replace(tmp, path)


async def collect_coinbase(
    spec: FeedSpec,
    out_dir: str,
    save_interval: float,
    keep_seconds: int,
    archive_dir: str,
    archive_interval: float,
) -> None:
    uri = "wss://ws-feed.exchange.coinbase.com"
    sub = {"type": "subscribe", "product_ids": [spec.symbol], "channels": ["matches", "ticker"]}
    path = os.path.join(out_dir, spec.path)
    bins = _load_bins(path)
    last_mid: float | None = None
    last_save = 0.0
    last_archive = 0.0
    reconnects = 0
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, close_timeout=5) as ws:
                await ws.send(json.dumps(sub))
                print(f"[{spec.label}] connected {spec.symbol}", flush=True)
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=35.0))
                    ts = _bin_ts()
                    mtype = msg.get("type", "")
                    if mtype in ("match", "last_match"):
                        try:
                            qty = float(msg["size"])
                            price = float(msg.get("price", last_mid or 0.0))
                        except (KeyError, TypeError, ValueError):
                            continue
                        b = bins.setdefault(ts, _blank_bin(last_mid))
                        # Coinbase match side is maker side. sell maker means taker bought.
                        if msg.get("side") == "sell":
                            b["buy"] += qty
                            b["last_aggressor"] = "buy"
                        elif msg.get("side") == "buy":
                            b["sell"] += qty
                            b["last_aggressor"] = "sell"
                        _touch_price(b, price)
                        b["n_trades"] += 1
                    elif mtype == "ticker":
                        try:
                            bid = float(msg["best_bid"])
                            ask = float(msg["best_ask"])
                            bid_qty = float(msg.get("best_bid_size") or 0.0)
                            ask_qty = float(msg.get("best_ask_size") or 0.0)
                        except (KeyError, TypeError, ValueError):
                            continue
                        last_mid = 0.5 * (bid + ask)
                        b = bins.setdefault(ts, _blank_bin(last_mid))
                        b.update({"mid": last_mid, "bid": bid, "ask": ask, "bid_qty": bid_qty, "ask_qty": ask_qty})
                    now = time.time()
                    if archive_dir and now - last_archive >= archive_interval:
                        _archive_bins(path, bins, archive_dir)
                        last_archive = now
                    if now - last_save >= save_interval:
                        _save_bins(path, bins, keep_seconds)
                        last_save = now
        except Exception as exc:
            reconnects += 1
            print(f"[{spec.label}] reconnect {reconnects}: {type(exc).__name__}: {exc}", flush=True)
            if archive_dir:
                _archive_bins(path, bins, archive_dir)
            _save_bins(path, bins, keep_seconds)
            await asyncio.sleep(3)


async def collect_kraken(
    spec: FeedSpec,
    out_dir: str,
    save_interval: float,
    keep_seconds: int,
    archive_dir: str,
    archive_interval: float,
) -> None:
    uri = "wss://ws.kraken.com/v2"
    path = os.path.join(out_dir, spec.path)
    bins = _load_bins(path)
    sub_trade = {"method": "subscribe", "params": {"channel": "trade", "symbol": [spec.symbol]}}
    sub_ticker = {"method": "subscribe", "params": {"channel": "ticker", "symbol": [spec.symbol]}}
    last_mid: float | None = None
    last_save = 0.0
    last_archive = 0.0
    reconnects = 0
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, close_timeout=5) as ws:
                await ws.send(json.dumps(sub_trade))
                await ws.send(json.dumps(sub_ticker))
                print(f"[{spec.label}] connected {spec.symbol}", flush=True)
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=35.0))
                    channel = msg.get("channel", "")
                    if channel == "trade" and msg.get("type") in ("snapshot", "update"):
                        for tr in msg.get("data", []):
                            try:
                                side = str(tr.get("side", ""))
                                qty = float(tr.get("qty", 0.0))
                                price = float(tr.get("price", last_mid or 0.0))
                            except (TypeError, ValueError):
                                continue
                            ts = _bin_ts()
                            b = bins.setdefault(ts, _blank_bin(last_mid))
                            if side == "buy":
                                b["buy"] += qty
                                b["last_aggressor"] = "buy"
                            elif side == "sell":
                                b["sell"] += qty
                                b["last_aggressor"] = "sell"
                            _touch_price(b, price)
                            b["n_trades"] += 1
                    elif channel == "ticker":
                        for tick in msg.get("data", []):
                            try:
                                bid = float(tick["bid"])
                                ask = float(tick["ask"])
                                bid_qty = float(tick.get("bid_qty") or 0.0)
                                ask_qty = float(tick.get("ask_qty") or 0.0)
                            except (KeyError, TypeError, ValueError):
                                continue
                            last_mid = 0.5 * (bid + ask)
                            ts = _bin_ts()
                            b = bins.setdefault(ts, _blank_bin(last_mid))
                            b.update({"mid": last_mid, "bid": bid, "ask": ask, "bid_qty": bid_qty, "ask_qty": ask_qty})
                    now = time.time()
                    if archive_dir and now - last_archive >= archive_interval:
                        _archive_bins(path, bins, archive_dir)
                        last_archive = now
                    if now - last_save >= save_interval:
                        _save_bins(path, bins, keep_seconds)
                        last_save = now
        except Exception as exc:
            reconnects += 1
            print(f"[{spec.label}] reconnect {reconnects}: {type(exc).__name__}: {exc}", flush=True)
            if archive_dir:
                _archive_bins(path, bins, archive_dir)
            _save_bins(path, bins, keep_seconds)
            await asyncio.sleep(3)


async def collect_bybit(
    spec: FeedSpec,
    out_dir: str,
    save_interval: float,
    keep_seconds: int,
    archive_dir: str,
    archive_interval: float,
) -> None:
    uri = "wss://stream.bybit.com/v5/public/linear"
    sub = {"op": "subscribe", "args": [f"publicTrade.{spec.symbol}", f"tickers.{spec.symbol}"]}
    path = os.path.join(out_dir, spec.path)
    bins = _load_bins(path)
    last_mid: float | None = None
    last_save = 0.0
    last_archive = 0.0
    reconnects = 0
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, close_timeout=5) as ws:
                await ws.send(json.dumps(sub))
                print(f"[{spec.label}] connected {spec.symbol}", flush=True)
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=35.0))
                    topic = msg.get("topic", "")
                    ts = _bin_ts()
                    if topic.startswith("publicTrade."):
                        for tr in msg.get("data", []):
                            try:
                                side = str(tr.get("S", "")).lower()
                                qty = float(tr["v"])
                                price = float(tr["p"])
                            except (KeyError, TypeError, ValueError):
                                continue
                            b = bins.setdefault(ts, _blank_bin(last_mid))
                            if side == "buy":
                                b["buy"] += qty
                                b["last_aggressor"] = "buy"
                            elif side == "sell":
                                b["sell"] += qty
                                b["last_aggressor"] = "sell"
                            _touch_price(b, price)
                            b["n_trades"] += 1
                    elif topic.startswith("tickers."):
                        d = msg.get("data", {}) or {}
                        try:
                            bid = float(d["bid1Price"])
                            ask = float(d["ask1Price"])
                            bid_qty = float(d.get("bid1Size") or 0.0)
                            ask_qty = float(d.get("ask1Size") or 0.0)
                        except (KeyError, TypeError, ValueError):
                            continue
                        last_mid = 0.5 * (bid + ask)
                        b = bins.setdefault(ts, _blank_bin(last_mid))
                        b.update({"mid": last_mid, "bid": bid, "ask": ask, "bid_qty": bid_qty, "ask_qty": ask_qty})
                    now = time.time()
                    if archive_dir and now - last_archive >= archive_interval:
                        _archive_bins(path, bins, archive_dir)
                        last_archive = now
                    if now - last_save >= save_interval:
                        _save_bins(path, bins, keep_seconds)
                        last_save = now
        except Exception as exc:
            reconnects += 1
            print(f"[{spec.label}] reconnect {reconnects}: {type(exc).__name__}: {exc}", flush=True)
            if archive_dir:
                _archive_bins(path, bins, archive_dir)
            _save_bins(path, bins, keep_seconds)
            await asyncio.sleep(3)


async def main_async(args: argparse.Namespace) -> None:
    out_dir = os.path.abspath(args.out_dir)
    archive_dir = os.path.abspath(args.archive_dir) if args.archive_dir else ""
    os.makedirs(out_dir, exist_ok=True)
    if archive_dir:
        os.makedirs(archive_dir, exist_ok=True)
    if args.reset:
        for spec in FEEDS:
            path = os.path.join(out_dir, spec.path)
            if os.path.exists(path):
                os.remove(path)
    print(f"[live] writing live bins to {out_dir}", flush=True)
    if archive_dir:
        print(f"[live] archiving live bins to {archive_dir}", flush=True)
    print(f"[live] feeds: {', '.join(f'{f.asset}/{f.venue}' for f in FEEDS)}", flush=True)
    tasks = []
    for spec in FEEDS:
        if spec.kind == "coinbase":
            coro = collect_coinbase(
                spec, out_dir, args.save_interval, args.keep_seconds, archive_dir, args.archive_interval
            )
        elif spec.kind == "kraken":
            coro = collect_kraken(
                spec, out_dir, args.save_interval, args.keep_seconds, archive_dir, args.archive_interval
            )
        elif spec.kind == "bybit":
            coro = collect_bybit(
                spec, out_dir, args.save_interval, args.keep_seconds, archive_dir, args.archive_interval
            )
        else:
            raise ValueError(spec.kind)
        tasks.append(asyncio.create_task(coro))
    await asyncio.gather(*tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all public live market collectors.")
    parser.add_argument("--out-dir", default="live_data")
    parser.add_argument("--save-interval", type=float, default=2.0)
    parser.add_argument("--keep-seconds", type=int, default=6 * 60 * 60)
    parser.add_argument("--archive-dir", default="live_data_history")
    parser.add_argument("--archive-interval", type=float, default=60.0)
    parser.add_argument("--reset", action="store_true", help="Start with empty live_data files.")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
