#!/usr/bin/env python3
"""Durable live prompt-Henry-Hub collector, isolated from historical jobs.

A single Databento GLBX.MDP3 session writes a mixed DBN archive containing MBO,
MBP-10, trades, TBBO, definitions, statistics, and status. It also maintains an
atomic health.json used by the Markets API/UI. Credentials come only from the
runtime environment. The process rotates at UTC midnight so continuous-symbol
mapping refreshes and archive files stay bounded.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import databento as db

DATASET = "GLBX.MDP3"
PRICE_SCALE = 1_000_000_000
UNDEF_PRICE = 9_000_000_000_000_000_000
DEFAULT_BUCKET = "bento-568968024170-us-east-2-an"
DEFAULT_PREFIX = "nymex/live/ng"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def decimal_price(value: Any) -> float | None:
    try:
        fixed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return None if abs(fixed) >= UNDEF_PRICE else fixed / PRICE_SCALE


def enum_text(value: Any) -> str | None:
    return None if value is None else str(getattr(value, "name", value))


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def seconds_to_midnight() -> float:
    now = time.time()
    return max(60.0, ((int(now) // 86400 + 1) * 86400) - now + 2.0)


class State:
    def __init__(self, symbol: str, archive: Path) -> None:
        self.symbol = symbol
        self.archive = archive
        self.started_at = utc_now()
        self.connection = "connecting"
        self.last_error: str | None = None
        self.last_record_wall_ns: int | None = None
        self.last_ts_event_ns: int | None = None
        self.last_ts_recv_ns: int | None = None
        self.instrument_id: int | None = None
        self.raw_symbol: str | None = None
        self.trade_price: float | None = None
        self.trade_size: int | None = None
        self.trade_side: str | None = None
        self.best_bid: float | None = None
        self.best_ask: float | None = None
        self.best_bid_size: int | None = None
        self.best_ask_size: int | None = None
        self.bid_depth_10: int | None = None
        self.ask_depth_10: int | None = None
        self.mbo_action: str | None = None
        self.mbo_side: str | None = None
        self.mbo_price: float | None = None
        self.mbo_size: int | None = None
        self.counts: Counter[str] = Counter()
        self.latencies_ms: deque[float] = deque(maxlen=5000)
        self.reconnects = 0
        self.lock = threading.Lock()

    def on_record(self, record: Any) -> None:
        kind = type(record).__name__
        now_ns = time.time_ns()
        with self.lock:
            self.connection = "live"
            self.last_record_wall_ns = now_ns
            self.counts[kind] += 1
            try:
                self.instrument_id = int(record.instrument_id)
            except (AttributeError, TypeError, ValueError, OverflowError):
                pass
            for field in ("ts_event", "ts_recv"):
                try:
                    value = int(getattr(record, field))
                except (AttributeError, TypeError, ValueError, OverflowError):
                    continue
                if value <= 0:
                    continue
                if field == "ts_event":
                    self.last_ts_event_ns = max(self.last_ts_event_ns or 0, value)
                else:
                    self.last_ts_recv_ns = max(self.last_ts_recv_ns or 0, value)
                    latency = (now_ns - value) / 1e6
                    if -1000 <= latency <= 120000:
                        self.latencies_ms.append(latency)

            raw_symbol = getattr(record, "raw_symbol", None)
            if raw_symbol:
                self.raw_symbol = str(raw_symbol)

            # All trade-bearing records expose price, size, side. MBO is excluded
            # because its price/size describe an order event, not necessarily a trade.
            if kind != "MboMsg" and all(hasattr(record, name) for name in ("price", "size", "side")):
                price = decimal_price(record.price)
                if price is not None:
                    self.trade_price = price
                    try:
                        self.trade_size = int(record.size)
                    except (TypeError, ValueError, OverflowError):
                        self.trade_size = None
                    self.trade_side = enum_text(record.side)

            levels = getattr(record, "levels", None)
            if levels is not None:
                try:
                    level0 = levels[0]
                    self.best_bid = decimal_price(level0.bid_px)
                    self.best_ask = decimal_price(level0.ask_px)
                    self.best_bid_size = int(level0.bid_sz)
                    self.best_ask_size = int(level0.ask_sz)
                    self.bid_depth_10 = sum(int(level.bid_sz) for level in levels[:10])
                    self.ask_depth_10 = sum(int(level.ask_sz) for level in levels[:10])
                except (IndexError, TypeError, ValueError, OverflowError):
                    pass

            if kind == "MboMsg":
                self.mbo_action = enum_text(getattr(record, "action", None))
                self.mbo_side = enum_text(getattr(record, "side", None))
                self.mbo_price = decimal_price(getattr(record, "price", None))
                try:
                    self.mbo_size = int(record.size)
                except (AttributeError, TypeError, ValueError, OverflowError):
                    self.mbo_size = None

    def on_reconnect(self, *_: Any) -> None:
        with self.lock:
            self.reconnects += 1
            self.connection = "reconnecting"

    def on_error(self, error: Exception) -> None:
        with self.lock:
            self.last_error = repr(error)
            self.connection = "error"

    def set_connection(self, value: str) -> None:
        with self.lock:
            self.connection = value

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            age_ms = None
            if self.last_record_wall_ns is not None:
                age_ms = (time.time_ns() - self.last_record_wall_ns) / 1e6
            latencies = list(self.latencies_ms)
            spread = None
            if self.best_bid is not None and self.best_ask is not None:
                spread = self.best_ask - self.best_bid
            depth_imbalance = None
            if self.bid_depth_10 is not None and self.ask_depth_10 is not None:
                total = self.bid_depth_10 + self.ask_depth_10
                if total:
                    depth_imbalance = (self.bid_depth_10 - self.ask_depth_10) / total
            return {
                "service": "markets-ng-live",
                "dataset": DATASET,
                "requested_symbol": self.symbol,
                "raw_symbol": self.raw_symbol,
                "instrument_id": self.instrument_id,
                "connection": self.connection,
                "started_at": self.started_at,
                "updated_at": utc_now(),
                "record_age_ms": age_ms,
                "last_ts_event_ns": self.last_ts_event_ns,
                "last_ts_recv_ns": self.last_ts_recv_ns,
                "latency_ms": {
                    "p50": percentile(latencies, 0.50),
                    "p95": percentile(latencies, 0.95),
                    "max": max(latencies) if latencies else None,
                },
                "market": {
                    "trade_price": self.trade_price,
                    "trade_size": self.trade_size,
                    "trade_side": self.trade_side,
                    "best_bid": self.best_bid,
                    "best_ask": self.best_ask,
                    "spread": spread,
                    "best_bid_size": self.best_bid_size,
                    "best_ask_size": self.best_ask_size,
                    "bid_depth_10": self.bid_depth_10,
                    "ask_depth_10": self.ask_depth_10,
                    "depth_imbalance_10": depth_imbalance,
                },
                "latest_mbo": {
                    "action": self.mbo_action,
                    "side": self.mbo_side,
                    "price": self.mbo_price,
                    "size": self.mbo_size,
                },
                "record_counts": dict(self.counts),
                "reconnect_count": self.reconnects,
                "archive_path": str(self.archive),
                "archive_bytes": self.archive.stat().st_size if self.archive.exists() else 0,
                "last_error": self.last_error,
            }


def upload(path: Path, bucket: str, key: str) -> None:
    import boto3

    boto3.client("s3").upload_file(str(path), bucket, key)


def run(args: argparse.Namespace) -> int:
    local_dir = Path(args.local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = local_dir / f"NG_live_{stamp}.dbn"
    health = local_dir / "health.json"
    state = State(args.symbol, archive)
    stop_health = threading.Event()

    def health_loop() -> None:
        while not stop_health.wait(args.health_interval):
            atomic_json(health, state.snapshot())

    thread = threading.Thread(target=health_loop, name="ng-live-health", daemon=True)
    thread.start()

    # MBO is stateful, so never skip records. The callback is deliberately light;
    # raw DBN writing is handled by Databento's native output stream.
    client = db.Live(heartbeat_interval_s=10, reconnect_policy="reconnect", slow_reader_behavior="warn")
    client.add_stream(str(archive), exception_callback=state.on_error)
    client.add_callback(state.on_record, exception_callback=state.on_error)
    client.add_reconnect_callback(state.on_reconnect, exception_callback=state.on_error)
    client.subscribe(dataset=DATASET, schema="mbo", stype_in="continuous", symbols=args.symbol, snapshot=True)
    for schema in ("mbp-10", "trades", "tbbo", "definition", "statistics", "status"):
        client.subscribe(dataset=DATASET, schema=schema, stype_in="continuous", symbols=args.symbol)

    def request_stop(*_: Any) -> None:
        state.set_connection("stopping")
        client.stop()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    exit_code = 0
    try:
        client.start()
        client.block_for_close(timeout=args.session_seconds or seconds_to_midnight())
        state.set_connection("closed")
    except Exception as error:
        state.on_error(error)
        exit_code = 1
    finally:
        stop_health.set()
        thread.join(timeout=2)
        atomic_json(health, state.snapshot())
        if args.upload and archive.exists() and archive.stat().st_size > 0:
            day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
            prefix = args.s3_prefix.strip("/")
            try:
                upload(archive, args.s3_bucket, f"{prefix}/{day}/{archive.name}")
                upload(health, args.s3_bucket, f"{prefix}/health.json")
                if not args.keep_local:
                    archive.unlink(missing_ok=True)
            except Exception as error:
                state.on_error(error)
                atomic_json(health, state.snapshot())
                exit_code = 1
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=os.getenv("NG_LIVE_SYMBOL", "NG.v.0"))
    parser.add_argument("--local-dir", default=os.getenv("NG_LIVE_LOCAL_DIR", "/var/lib/markets/ng_live"))
    parser.add_argument("--s3-bucket", default=os.getenv("NG_LIVE_S3_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--s3-prefix", default=os.getenv("NG_LIVE_S3_PREFIX", DEFAULT_PREFIX))
    parser.add_argument("--health-interval", type=float, default=float(os.getenv("NG_LIVE_HEALTH_INTERVAL", "5")))
    parser.add_argument("--session-seconds", type=float, default=None, help="Test override; default is UTC midnight")
    parser.add_argument("--upload", action=argparse.BooleanOptionalAction, default=os.getenv("NG_LIVE_UPLOAD_ENABLED", "1") == "1")
    parser.add_argument("--keep-local", action=argparse.BooleanOptionalAction, default=os.getenv("NG_LIVE_KEEP_LOCAL", "0") == "1")
    args = parser.parse_args()
    if not os.getenv("DATABENTO_API_KEY"):
        parser.error("DATABENTO_API_KEY is required in the runtime environment")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
