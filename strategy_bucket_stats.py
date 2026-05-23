from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


DEFAULT_THRESHOLDS_PATH = "bucket_thresholds.json"
DEFAULT_VENUE_PREFS_PATH = "venue_prefs.json"


def normalize_family(strategy_id: str) -> str:
    text = str(strategy_id or "unknown").strip().lower()
    return text or "unknown"


def normalize_side(side: str) -> str:
    text = str(side or "").strip().lower()
    if text == "buy":
        return "buy"
    if text == "sell":
        return "sell"
    if text == "long":
        return "buy"
    if text == "short":
        return "sell"
    return text or "unknown"


def session_from_offset_hours(offset_hours: float) -> str:
    day_hour = float(offset_hours) % 24.0
    return "first6h" if day_hour < 6.0 else "remaining18h"


def session_from_trade(trade: dict[str, Any]) -> str:
    explicit = str(trade.get("bucket_session") or "").strip().lower()
    if explicit:
        return explicit
    entry_offset = trade.get("replay_offset_hours")
    if entry_offset is not None:
        return session_from_offset_hours(float(entry_offset))
    return "all"


def bucket_id(
    strategy_family: str,
    asset: str,
    venue: str,
    side: str,
    session: str = "all",
) -> str:
    return "|".join([
        normalize_family(strategy_family),
        str(asset or "unknown").upper(),
        str(venue or "unknown").lower(),
        normalize_side(side),
        str(session or "all").lower(),
    ])


def venue_key(
    strategy_family: str,
    asset: str,
    venue: str,
) -> str:
    return "|".join([
        normalize_family(strategy_family),
        str(asset or "unknown").upper(),
        str(venue or "unknown").lower(),
    ])


@dataclass
class BucketStat:
    bucket_id: str
    strategy_family: str
    asset: str
    venue: str
    side: str
    session: str
    trades: int = 0
    wins: int = 0
    pnl_usd: float = 0.0
    pnl_R: float = 0.0
    avg_R: float = 0.0
    win_rate: float | None = None
    last_updated: float | None = None

    def add_trade(self, trade: dict[str, Any]) -> None:
        pnl = float(trade.get("realized_pnl_usd") or 0.0)
        profit_r = profit_R_for_trade(trade)
        self.trades += 1
        self.wins += 1 if pnl > 0 else 0
        self.pnl_usd += pnl
        self.pnl_R += profit_r
        self.last_updated = float(trade.get("exit_ts_utc") or trade.get("ts_utc") or 0.0) or self.last_updated
        self.win_rate = self.wins / self.trades if self.trades else None
        self.avg_R = self.pnl_R / self.trades if self.trades else 0.0

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["pnl_usd"] = round(float(self.pnl_usd), 6)
        out["pnl_R"] = round(float(self.pnl_R), 6)
        out["avg_R"] = round(float(self.avg_R), 6)
        out["win_rate"] = round(float(self.win_rate), 6) if self.win_rate is not None else None
        return out


@dataclass
class VenueStat:
    venue_key: str
    strategy_family: str
    asset: str
    venue: str
    trades: int = 0
    wins: int = 0
    pnl_usd: float = 0.0
    pnl_R: float = 0.0
    avg_R: float = 0.0
    win_rate: float | None = None
    last_updated: float | None = None

    def add_trade(self, trade: dict[str, Any]) -> None:
        pnl = float(trade.get("realized_pnl_usd") or 0.0)
        profit_r = profit_R_for_trade(trade)
        self.trades += 1
        self.wins += 1 if pnl > 0 else 0
        self.pnl_usd += pnl
        self.pnl_R += profit_r
        self.last_updated = float(trade.get("exit_ts_utc") or trade.get("ts_utc") or 0.0) or self.last_updated
        self.win_rate = self.wins / self.trades if self.trades else None
        self.avg_R = self.pnl_R / self.trades if self.trades else 0.0

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["pnl_usd"] = round(float(self.pnl_usd), 6)
        out["pnl_R"] = round(float(self.pnl_R), 6)
        out["avg_R"] = round(float(self.avg_R), 6)
        out["win_rate"] = round(float(self.win_rate), 6) if self.win_rate is not None else None
        return out


def profit_R_for_trade(trade: dict[str, Any]) -> float:
    pnl = float(trade.get("realized_pnl_usd") or 0.0)
    notional = float(trade.get("notional") or 0.0)
    stop_bps = float(
        trade.get("trade_strategy_stop_loss_bps")
        or trade.get("mock_scenario_stop_loss_bps")
        or 10.0
    )
    risk_usd = notional * max(stop_bps, 1.0) / 10000.0
    if risk_usd <= 0:
        return 0.0
    return pnl / risk_usd


def bucket_id_for_trade(trade: dict[str, Any]) -> str:
    return bucket_id(
        trade.get("trade_strategy_id") or "unknown",
        trade.get("asset") or "unknown",
        trade.get("venue") or "unknown",
        trade.get("side") or "unknown",
        session_from_trade(trade),
    )


def venue_key_for_trade(trade: dict[str, Any]) -> str:
    return venue_key(
        trade.get("trade_strategy_id") or "unknown",
        trade.get("asset") or "unknown",
        trade.get("venue") or "unknown",
    )


def aggregate_bucket_stats(trades: list[dict[str, Any]]) -> dict[str, BucketStat]:
    stats: dict[str, BucketStat] = {}
    for trade in trades:
        if trade.get("status") != "closed":
            continue
        bid = bucket_id_for_trade(trade)
        family, asset, venue, side, session = bid.split("|", 4)
        row = stats.setdefault(
            bid,
            BucketStat(
                bucket_id=bid,
                strategy_family=family,
                asset=asset,
                venue=venue,
                side=side,
                session=session,
            ),
        )
        row.add_trade(trade)
    return stats


def aggregate_venue_stats(trades: list[dict[str, Any]]) -> dict[str, VenueStat]:
    stats: dict[str, VenueStat] = {}
    for trade in trades:
        if trade.get("status") != "closed":
            continue
        key = venue_key_for_trade(trade)
        family, asset, venue = key.split("|", 2)
        row = stats.setdefault(
            key,
            VenueStat(
                venue_key=key,
                strategy_family=family,
                asset=asset,
                venue=venue,
            ),
        )
        row.add_trade(trade)
    return stats


def load_thresholds(path: str | Path = DEFAULT_THRESHOLDS_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "default": {
                "min_trades": 80,
                "win_rate_floor": 0.45,
                "max_loss_R": -3.0,
                "paper_only_trades": 40,
            },
            "families": {},
            "buckets": {},
        }
    return json.loads(p.read_text(encoding="utf-8"))


def load_venue_prefs(path: str | Path = DEFAULT_VENUE_PREFS_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "default": {
                "binance": 1.0,
                "bybit": 1.0,
                "coinbase": 0.7,
                "kraken": 0.9,
            },
            "families": {},
        }
    return json.loads(p.read_text(encoding="utf-8"))


def venue_weight(
    strategy_family: str,
    asset: str,
    venue: str,
    stats: VenueStat | dict[str, Any] | None,
    prefs: dict[str, Any],
) -> dict[str, Any]:
    family = normalize_family(strategy_family)
    venue_norm = str(venue or "unknown").lower()
    base = float(
        ((prefs.get("families") or {}).get(family) or {}).get(
            venue_norm,
            (prefs.get("default") or {}).get(venue_norm, 1.0),
        )
    )
    if stats is None:
        stats_dict = {"trades": 0, "wins": 0, "pnl_R": 0.0, "pnl_usd": 0.0, "win_rate": None}
    elif isinstance(stats, VenueStat):
        stats_dict = stats.to_dict()
    else:
        stats_dict = dict(stats)
    trades = int(stats_dict.get("trades") or 0)
    wins = int(stats_dict.get("wins") or 0)
    win_rate = (wins / trades) if trades else None
    adj = 1.0
    reasons: list[str] = []
    if trades < 50:
        adj = 0.75
        reasons.append(f"Venue has {trades} family trades; applying discovery haircut")
    elif win_rate is not None and win_rate < 0.45:
        adj = 0.0
        reasons.append(f"Venue family win rate {win_rate:.1%} below 45%")
    elif win_rate is not None and win_rate < 0.50:
        adj = 0.30
        reasons.append(f"Venue family win rate {win_rate:.1%} below 50%")
    elif win_rate is not None and win_rate < 0.55:
        adj = 0.70
        reasons.append(f"Venue family win rate {win_rate:.1%} below 55%")
    return {
        "venue_key": venue_key(family, asset, venue_norm),
        "base": round(base, 6),
        "adjustment": round(adj, 6),
        "weight": round(base * adj, 6),
        "stats": {
            **stats_dict,
            "win_rate": round(win_rate, 6) if win_rate is not None else None,
        },
        "reasons": reasons,
    }


def threshold_for(bucket: str, family: str, cfg: dict[str, Any]) -> dict[str, Any]:
    out = dict(cfg.get("default") or {})
    out.update((cfg.get("families") or {}).get(str(family).lower(), {}))
    out.update((cfg.get("buckets") or {}).get(bucket, {}))
    return out


def bucket_health(
    bucket: str,
    stats: BucketStat | dict[str, Any] | None,
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    family = bucket.split("|", 1)[0].lower() if bucket else "unknown"
    cfg = threshold_for(bucket, family, thresholds)
    if stats is None:
        stats_dict = {
            "trades": 0,
            "wins": 0,
            "pnl_R": 0.0,
            "pnl_usd": 0.0,
            "win_rate": None,
        }
    elif isinstance(stats, BucketStat):
        stats_dict = stats.to_dict()
    else:
        stats_dict = dict(stats)
    trades = int(stats_dict.get("trades") or 0)
    wins = int(stats_dict.get("wins") or 0)
    win_rate = (wins / trades) if trades else None
    pnl_R = float(stats_dict.get("pnl_R") or 0.0)
    state = "ok"
    reasons: list[str] = []
    if bool(cfg.get("hard_kill")):
        state = "hard_kill"
        reasons.append("Bucket is hard-killed by thresholds config")
    elif trades < int(cfg.get("paper_only_trades") or 0):
        state = "paper_only"
        reasons.append(f"Bucket has {trades} trades; paper-only until {int(cfg.get('paper_only_trades') or 0)}")
    elif trades >= int(cfg.get("min_trades") or 0):
        if win_rate is not None and win_rate < float(cfg.get("win_rate_floor") or 0.0):
            state = "kill"
            reasons.append(f"Bucket win rate {win_rate:.1%} below floor {float(cfg.get('win_rate_floor') or 0.0):.1%}")
        if pnl_R <= float(cfg.get("max_loss_R") or -999999.0):
            state = "kill"
            reasons.append(f"Bucket pnl_R {pnl_R:.2f} below floor {float(cfg.get('max_loss_R') or 0.0):.2f}")
    return {
        "bucket_id": bucket,
        "state": state,
        "reasons": reasons,
        "thresholds": cfg,
        "stats": {
            **stats_dict,
            "win_rate": round(win_rate, 6) if win_rate is not None else None,
        },
    }


def write_bucket_stats(
    trades: list[dict[str, Any]],
    output_path: str | Path,
    thresholds_path: str | Path = DEFAULT_THRESHOLDS_PATH,
) -> dict[str, Any]:
    stats = aggregate_bucket_stats(trades)
    thresholds = load_thresholds(thresholds_path)
    payload = {
        "thresholds_path": str(thresholds_path),
        "buckets": {
            bid: {
                **row.to_dict(),
                "health": bucket_health(bid, row, thresholds),
            }
            for bid, row in sorted(stats.items())
        },
    }
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def write_venue_stats(
    trades: list[dict[str, Any]],
    output_path: str | Path,
    venue_prefs_path: str | Path = DEFAULT_VENUE_PREFS_PATH,
) -> dict[str, Any]:
    stats = aggregate_venue_stats(trades)
    prefs = load_venue_prefs(venue_prefs_path)
    payload = {
        "venue_prefs_path": str(venue_prefs_path),
        "venues": {
            key: {
                **row.to_dict(),
                "health": venue_weight(row.strategy_family, row.asset, row.venue, row, prefs),
            }
            for key, row in sorted(stats.items())
        },
    }
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
