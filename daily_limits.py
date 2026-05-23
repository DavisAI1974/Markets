from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_bucket_stats import bucket_id_for_trade, normalize_family, profit_R_for_trade


DEFAULT_DAILY_LIMITS_PATH = "daily_limits.json"


def _trade_day(trade: dict[str, Any]) -> str:
    ts = float(trade.get("exit_ts_utc") or trade.get("ts_utc") or 0.0)
    if ts <= 0:
        return datetime.now(timezone.utc).date().isoformat()
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def load_daily_limits(path: str | Path = DEFAULT_DAILY_LIMITS_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "families": {},
            "buckets": {},
            "default": {"max_loss_R": -3.0},
        }
    return json.loads(p.read_text(encoding="utf-8"))


class DailyPnlTracker:
    def __init__(self) -> None:
        self.family_pnl_R: defaultdict[tuple[str, str], float] = defaultdict(float)
        self.bucket_pnl_R: defaultdict[tuple[str, str], float] = defaultdict(float)

    def apply_trade(self, trade: dict[str, Any]) -> None:
        if trade.get("status") != "closed":
            return
        day = _trade_day(trade)
        family = normalize_family(trade.get("trade_strategy_id") or "unknown")
        bucket = str(trade.get("bucket_id") or bucket_id_for_trade(trade))
        profit_r = float(trade.get("profit_R") if trade.get("profit_R") is not None else profit_R_for_trade(trade))
        self.family_pnl_R[(day, family)] += profit_r
        self.bucket_pnl_R[(day, bucket)] += profit_r

    def family_today(self, family: str, day: str) -> float:
        return float(self.family_pnl_R.get((day, normalize_family(family)), 0.0))

    def bucket_today(self, bucket: str, day: str) -> float:
        return float(self.bucket_pnl_R.get((day, bucket), 0.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "families": {
                f"{day}|{family}": round(value, 6)
                for (day, family), value in sorted(self.family_pnl_R.items())
            },
            "buckets": {
                f"{day}|{bucket}": round(value, 6)
                for (day, bucket), value in sorted(self.bucket_pnl_R.items())
            },
        }


def build_daily_tracker(trades: list[dict[str, Any]]) -> DailyPnlTracker:
    tracker = DailyPnlTracker()
    for trade in trades:
        tracker.apply_trade(trade)
    return tracker


def daily_limit_health(
    *,
    family: str,
    bucket: str,
    day: str,
    tracker: DailyPnlTracker | None,
    limits: dict[str, Any],
) -> dict[str, Any]:
    family_norm = normalize_family(family)
    default_limit = float((limits.get("default") or {}).get("max_loss_R", -3.0))
    family_limit = float(((limits.get("families") or {}).get(family_norm) or {}).get("max_loss_R", default_limit))
    bucket_limit_raw = ((limits.get("buckets") or {}).get(bucket) or {}).get("max_loss_R")
    bucket_limit = float(bucket_limit_raw) if bucket_limit_raw is not None else None
    family_pnl = tracker.family_today(family_norm, day) if tracker is not None else 0.0
    bucket_pnl = tracker.bucket_today(bucket, day) if tracker is not None else 0.0
    blockers: list[str] = []
    if family_pnl <= family_limit:
        blockers.append(f"Family daily loss {family_pnl:.2f}R reached limit {family_limit:.2f}R")
    if bucket_limit is not None and bucket_pnl <= bucket_limit:
        blockers.append(f"Bucket daily loss {bucket_pnl:.2f}R reached limit {bucket_limit:.2f}R")
    return {
        "day": day,
        "family": family_norm,
        "bucket": bucket,
        "family_pnl_R": round(family_pnl, 6),
        "family_max_loss_R": family_limit,
        "bucket_pnl_R": round(bucket_pnl, 6),
        "bucket_max_loss_R": bucket_limit,
        "state": "blocked" if blockers else "ok",
        "blockers": blockers,
    }
