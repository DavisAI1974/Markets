from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from daily_limits import DailyPnlTracker, daily_limit_health, load_daily_limits
from dipole_coupling import build_dipole_coupling
from feature_store import latest_onchain_features
from daily_health_loader import bucket_report, family_report, load_daily_health_report, venue_report
from onchain_features import onchain_allows_side
from strategy_switcher import DISABLED_STRATEGIES, PRESSURE_CONTINUATION, strategy_family_health
from strategy_bucket_stats import (
    bucket_health,
    bucket_id,
    load_thresholds,
    load_venue_prefs,
    venue_weight,
)


@dataclass(frozen=True)
class StrategyClassMetrics:
    strategy_id: str
    regime: str = ""
    n_trades: int = 0
    win_rate: float | None = None
    sharpe: float | None = None
    expected_rr: float | None = None
    backtest_span: str = ""


@dataclass(frozen=True)
class TicketThresholds:
    min_win_rate: float = 0.82
    min_sharpe: float = 1.50
    min_trades: int = 150
    tier_a_score: float = 0.90
    tier_b_score: float = 0.80


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso_from_ts(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(float(ts), timezone.utc) if ts else datetime.now(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _ticket_id(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _news_alignment(asset_news: dict[str, Any], side: str) -> tuple[str, list[dict[str, Any]]]:
    bias = str(asset_news.get("narrative_bias") or "UNKNOWN").upper()
    dipole = asset_news.get("news_dipole")
    dipole_side = ""
    if dipole is not None:
        d = _float(dipole)
        dipole_side = "buy" if d > 0 else "sell" if d < 0 else ""
    bias_side = "buy" if bias == "BULLISH" else "sell" if bias == "BEARISH" else ""
    if bias_side and bias_side != side:
        state = "conflicting"
    elif dipole_side and dipole_side != side and abs(_float(dipole)) >= 0.25:
        state = "conflicting"
    elif bias_side == side or dipole_side == side:
        state = "aligned"
    else:
        state = "neutral"
    driver = {
        "id": asset_news.get("starter_category") or "daily_news_context",
        "category": asset_news.get("starter_category") or "daily_context",
        "polarity": bias.lower(),
        "horizon_minutes": asset_news.get("starter_horizon_min"),
        "source_tier": "policy",
    }
    return state, [driver]


def _structural_score(inputs: dict[str, Any], status: Any) -> float:
    abs_dipole = min(1.0, abs(_float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0))))
    vol_z = _clamp((_float(inputs.get("volume_zscore")) + 1.0) / 4.0)
    spread_bps = _float(inputs.get("spread_bps"))
    spread_score = 1.0 if 0.0 < spread_bps <= 4.0 else 0.6 if spread_bps <= 8.0 else 0.0
    follow = _clamp(_float(inputs.get("trade_recent_2chunk_bps")) / 12.0)
    return _clamp(0.30 * abs_dipole + 0.25 * vol_z + 0.20 * spread_score + 0.25 * follow)


def _strategy_score(status: Any, metrics: StrategyClassMetrics | None) -> float:
    live_conf = _clamp(_float(getattr(status, "trade_strategy_confidence", 0.0)))
    if metrics is None or metrics.win_rate is None:
        return 0.50 * live_conf
    sharpe_component = _clamp((_float(metrics.sharpe) / 3.0) if metrics.sharpe is not None else live_conf)
    return _clamp(0.50 * _float(metrics.win_rate) + 0.25 * sharpe_component + 0.25 * live_conf)


def _metrics_are_eligible(metrics: StrategyClassMetrics | None, thresholds: TicketThresholds) -> tuple[bool, str]:
    if metrics is None:
        return False, "No historical strategy-class metrics attached"
    if metrics.n_trades < thresholds.min_trades:
        return False, f"Strategy class has only {metrics.n_trades} trades; needs {thresholds.min_trades}+"
    if metrics.win_rate is None or metrics.win_rate < thresholds.min_win_rate:
        return False, f"Strategy class win rate below {thresholds.min_win_rate:.0%}"
    if metrics.sharpe is None or metrics.sharpe < thresholds.min_sharpe:
        return False, f"Strategy class Sharpe below {thresholds.min_sharpe:.2f}"
    return True, ""


def build_high_conviction_ticket(
    status: Any,
    inputs: dict[str, Any],
    *,
    mode: str = "practice",
    strategy_metrics: StrategyClassMetrics | None = None,
    family_stats: dict[str, Any] | None = None,
    bucket_stats: dict[str, Any] | None = None,
    venue_stats: dict[str, Any] | None = None,
    daily_tracker: DailyPnlTracker | None = None,
    thresholds: TicketThresholds = TicketThresholds(),
    bucket_thresholds_path: str = "bucket_thresholds.json",
    venue_prefs_path: str = "venue_prefs.json",
    daily_limits_path: str = "daily_limits.json",
    daily_health_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    side = str(getattr(status, "trade_option_side", "") or getattr(status, "pressure_watch_direction", "") or "")
    side = side.lower()
    ts = _float(getattr(status, "last_update_utc", 0.0))
    strategy_id = str(getattr(status, "trade_strategy_id", "") or "NO_TRADE")
    bucket = bucket_id(
        strategy_id,
        getattr(status, "asset", ""),
        getattr(status, "venue", ""),
        side,
        str(inputs.get("bucket_session") or "all"),
    )
    day = datetime.fromtimestamp(ts, timezone.utc).date().isoformat() if ts > 0 else datetime.now(timezone.utc).date().isoformat()
    health_report = daily_health_report if daily_health_report is not None else load_daily_health_report(day)
    family_row = family_report(health_report, strategy_id)
    bucket_row = bucket_report(health_report, bucket)
    venue_row = venue_report(health_report, strategy_id, getattr(status, "asset", ""), getattr(status, "venue", ""))
    if family_row:
        family_audit = {
            "strategy_id": strategy_id,
            "state": "dead" if family_row.get("status") == "deallocated" else family_row.get("status", "learning"),
            "stats": {
                "trades": family_row.get("trades", 0),
                "win_rate": family_row.get("win_rate"),
                "sharpe": family_row.get("sharpe"),
            },
            "reasons": [],
        }
    else:
        family_audit = strategy_family_health(strategy_id, family_stats)
    if bucket_row:
        bucket_audit = {
            "bucket_id": bucket,
            "state": "hard_kill" if bucket_row.get("status") == "hard_kill" else "kill" if bucket_row.get("status") == "kill" else "paper_only" if bucket_row.get("status") == "learning" else "ok",
            "reasons": [],
            "thresholds": {},
            "stats": bucket_row,
        }
    else:
        threshold_cfg = load_thresholds(bucket_thresholds_path)
        bucket_audit = bucket_health(bucket, bucket_stats, threshold_cfg)
    if venue_row:
        venue_status = str(venue_row.get("status") or "ok")
        venue_weight_value = 0.0 if venue_status == "kill" else 0.5 if venue_status == "degraded" else 1.0
        venue_audit = {
            "venue_key": "|".join([strategy_id.lower(), str(getattr(status, "asset", "")).upper(), str(getattr(status, "venue", "")).lower()]),
            "base": 1.0,
            "adjustment": venue_weight_value,
            "weight": venue_weight_value,
            "stats": venue_row,
            "reasons": [],
        }
    else:
        venue_cfg = load_venue_prefs(venue_prefs_path)
        venue_audit = venue_weight(
            strategy_id,
            getattr(status, "asset", ""),
            getattr(status, "venue", ""),
            venue_stats,
            venue_cfg,
        )
    daily_family_state = (((health_report.get("daily_limits_state") or {}).get("families") or {}).get(strategy_id.lower()) or {})
    daily_bucket_state = (((health_report.get("daily_limits_state") or {}).get("buckets") or {}).get(bucket) or {})
    if daily_family_state or daily_bucket_state:
        daily_blockers: list[str] = []
        if daily_family_state.get("limit_reached"):
            daily_blockers.append("Family daily loss limit reached")
        if daily_bucket_state.get("limit_reached"):
            daily_blockers.append("Bucket daily loss limit reached")
        daily_audit = {
            "day": day,
            "family": strategy_id.lower(),
            "bucket": bucket,
            "family_pnl_R": daily_family_state.get("pnl_R_today", 0.0),
            "family_max_loss_R": daily_family_state.get("max_loss_R"),
            "bucket_pnl_R": daily_bucket_state.get("pnl_R_today", 0.0),
            "bucket_max_loss_R": daily_bucket_state.get("max_loss_R"),
            "state": "blocked" if daily_blockers else "ok",
            "blockers": daily_blockers,
        }
    else:
        daily_audit = daily_limit_health(
            family=strategy_id,
            bucket=bucket,
            day=day,
            tracker=daily_tracker,
            limits=load_daily_limits(daily_limits_path),
        )
    asset_news = dict(getattr(status, "daily_news_context", {}) or {})
    news_state, news_drivers = _news_alignment(asset_news, side)
    onchain = latest_onchain_features(getattr(status, "asset", "")) or {}
    onchain_regime = str(((onchain.get("labels") or {}).get("onchain_regime") if onchain else "") or "unknown")
    coupling = build_dipole_coupling(
        status=status,
        inputs=inputs,
        news_context=asset_news,
        onchain=onchain,
    ).to_dict()
    regime_score = _clamp(_float(getattr(status, "adjusted_confidence", 0.0) or getattr(status, "confidence", 0.0)))
    structural_score = _structural_score(inputs, status)
    news_score = {"aligned": 1.0, "neutral": 0.7, "conflicting": 0.0}.get(news_state, 0.5)
    strategy_score = _strategy_score(status, strategy_metrics)
    base_go_score = _clamp(
        0.25 * regime_score
        + 0.30 * structural_score
        + 0.20 * news_score
        + 0.25 * strategy_score
    )
    go_score = _clamp(base_go_score * _float(venue_audit.get("weight"), 1.0))

    blockers: list[str] = []
    blockers.extend(str(x) for x in getattr(status, "trade_option_blockers", []) or [])
    blockers.extend(str(x) for x in getattr(status, "trade_strategy_blockers", []) or [])
    metrics_ok, metrics_blocker = _metrics_are_eligible(strategy_metrics, thresholds)
    if not metrics_ok:
        blockers.append(metrics_blocker)
    family_state = str(family_audit.get("state") or "")
    if family_state == "dead":
        blockers.append("Strategy family health is dead")
    elif strategy_id == PRESSURE_CONTINUATION and family_state != "ok":
        blockers.append("Pressure continuation family is not product-eligible yet")
    if strategy_id == "NO_TRADE":
        blockers.append("No actionable strategy selected")
    if strategy_id in DISABLED_STRATEGIES:
        blockers.append(f"{strategy_id} is disabled after negative evidence")
    if news_state == "conflicting":
        blockers.append("News context conflicts with trade side")
    onchain_ok, onchain_reason = onchain_allows_side(onchain_regime, side)
    if not onchain_ok:
        blockers.append(onchain_reason)
    if mode == "live" and coupling.get("coupling_state") == "conflicting":
        blockers.append("Dipole coupling is conflicting across market/news/on-chain/family")
    if _float(inputs.get("trade_recent_2chunk_bps")) <= 0 and strategy_id == "PRESSURE_CONTINUATION":
        blockers.append("Pressure continuation lacks recent follow-through")
    bucket_state = str(bucket_audit.get("state") or "")
    if bucket_state in {"kill", "hard_kill"}:
        blockers.append(f"Bucket health is {bucket_state}")
    elif bucket_state == "paper_only" and mode == "live":
        blockers.append("Bucket is practice-only while it gathers evidence")
    if _float(venue_audit.get("weight"), 1.0) <= 0.0:
        blockers.append("Venue health weight is zero for this strategy family")
    blockers.extend(str(x) for x in daily_audit.get("blockers") or [])

    if blockers:
        ticket_state = "BLOCK"
        tier = "NONE"
    elif go_score >= thresholds.tier_a_score:
        ticket_state = "GO"
        tier = "A"
    elif go_score >= thresholds.tier_b_score:
        ticket_state = "GO"
        tier = "B"
    else:
        ticket_state = "WATCH"
        tier = "C"

    price = _float(getattr(status, "current_price", 0.0))
    stop_bps = _float(getattr(status, "trade_strategy_stop_loss_bps", 0.0), 10.0) or 10.0
    take_bps = _float(getattr(status, "trade_strategy_take_profit_bps", 0.0), 18.0) or 18.0
    sign = 1 if side == "buy" else -1
    stop_price = price * (1.0 - sign * stop_bps / 10000.0) if price > 0 else 0.0
    take_price = price * (1.0 + sign * take_bps / 10000.0) if price > 0 else 0.0

    reasons = [
        *(str(x) for x in getattr(status, "trade_strategy_reasons", []) or []),
        *(str(x) for x in getattr(status, "trade_option_entry_reasons", []) or []),
    ]
    ticket = {
        "id": _ticket_id(ts, getattr(status, "asset", ""), getattr(status, "venue", ""), side, strategy_id),
        "mode": mode,
        "ticket_state": ticket_state,
        "timestamp": _iso_from_ts(ts),
        "asset": getattr(status, "asset", ""),
        "venue": getattr(status, "venue", ""),
        "side": "long" if side == "buy" else "short" if side == "sell" else "",
        "timeframe": "intraday",
        "entry": {
            "type": "market",
            "price": price,
            "valid_for_seconds": int((getattr(status, "trade_option_hold_minutes", 0) or 10) * 60),
        },
        "risk": {
            "account_risk_fraction": 0.01 if tier == "A" else 0.005 if tier == "B" else 0.0,
            "vol_target_notional": 0.0,
            "stop_price": stop_price,
            "take_profits": [{"price": take_price, "size_fraction": 1.0}],
            "notional_scale": _float(getattr(status, "trade_option_notional_scale", 0.0)) if ticket_state == "GO" else 0.0,
        },
        "regime": {
            "label": getattr(status, "regime", ""),
            "confidence": regime_score,
            "features_snapshot": {
                "mean_dipole": _float(inputs.get("mean_dipole")),
                "volume_zscore": _float(inputs.get("volume_zscore")),
                "spread_bps": _float(inputs.get("spread_bps")),
                "trade_recent_2chunk_bps": _float(inputs.get("trade_recent_2chunk_bps")),
            },
        },
        "structural_edge": {
            "structural_score": structural_score,
            "pressure_state": getattr(status, "pressure_watch_state", ""),
            "pressure_priority": getattr(status, "pressure_watch_priority", 0),
        },
        "news_context": {
            "state": news_state,
            "drivers": news_drivers,
        },
        "onchain_context": {
            "regime": onchain_regime,
            "features": onchain,
        },
        "dipole_coupling": coupling,
        "strategy": {
            "id": strategy_id,
            "class": strategy_id,
            "bucket": {
                "id": bucket,
                "asset": getattr(status, "asset", ""),
                "venue": getattr(status, "venue", ""),
                "side": side,
                "session": str(inputs.get("bucket_session") or "all"),
                "state": bucket_state,
                "stats": bucket_audit.get("stats") or {},
                "thresholds": bucket_audit.get("thresholds") or {},
                "reasons": bucket_audit.get("reasons") or [],
            },
            "confidence": _float(getattr(status, "trade_strategy_confidence", 0.0)),
            "family_health": family_audit,
            "hist_win_rate_class": strategy_metrics.win_rate if strategy_metrics else None,
            "expected_rr": strategy_metrics.expected_rr if strategy_metrics else None,
            "backtest_span": strategy_metrics.backtest_span if strategy_metrics else "",
            "n_trades": strategy_metrics.n_trades if strategy_metrics else 0,
            "sharpe": strategy_metrics.sharpe if strategy_metrics else None,
        },
        "venue_health": venue_audit,
        "daily_limits": daily_audit,
        "composite": {
            "go_score": round(go_score, 4),
            "base_go_score": round(base_go_score, 4),
            "tier": tier,
            "reasons": list(dict.fromkeys(reasons))[:8],
            "blockers": list(dict.fromkeys(blockers))[:8],
        },
    }
    return ticket


def compact_ticket(ticket: dict[str, Any]) -> str:
    return json.dumps(ticket, sort_keys=True, separators=(",", ":"))
