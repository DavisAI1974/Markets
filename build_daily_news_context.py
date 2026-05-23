from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from news_coupling_research import BIAS_SIGN, SOURCE_WEIGHTS, load_events


def _pressure(event: dict[str, Any]) -> float:
    quality = str(event.get("source_quality") or "UNKNOWN").upper()
    return (
        float(event.get("confidence") or 0.5)
        * float(event.get("impact") or 0.5)
        * SOURCE_WEIGHTS.get(quality, 0.5)
    )


def _bias_from_pressure(bull: float, bear: float) -> str:
    total = bull + bear
    if total <= 0:
        return "UNKNOWN"
    dipole = (bull - bear) / total
    if dipole >= 0.25:
        return "BULLISH"
    if dipole <= -0.25:
        return "BEARISH"
    return "MIXED"


def _load_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _best_policy_entry(policy: dict[str, Any], categories: dict[str, int], bias: str) -> tuple[str, int | None, dict[str, Any]]:
    if not policy or bias not in {"BULLISH", "BEARISH"}:
        return "", None, {}
    policy_categories = policy.get("categories") or {}
    candidates: list[dict[str, Any]] = []
    for category, count in categories.items():
        by_bias = (policy_categories.get(str(category).upper()) or {}).get(bias) or {}
        for horizon_text, entry in by_bias.items():
            try:
                horizon = int(horizon_text)
            except ValueError:
                continue
            edge = float(entry.get("signed_bps_edge_vs_placebo") or 0.0)
            enabled_rank = 1 if entry.get("enabled") else 0
            candidates.append({
                "enabled_rank": enabled_rank,
                "edge": edge,
                "count": int(count),
                "category": str(category).upper(),
                "horizon": horizon,
                "entry": dict(entry),
            })
    if not candidates:
        return "", None, {}
    candidates.sort(key=lambda x: (x["enabled_rank"], x["edge"], x["count"], -x["horizon"]), reverse=True)
    best = candidates[0]
    category = str(best["category"])
    horizon = int(best["horizon"])
    entry = dict(best["entry"])
    entry = {
        "category": category,
        "directional_bias": bias,
        "horizon_min": horizon,
        **entry,
    }
    return category, horizon, entry


def _auto_posture(
    bias: str,
    total_pressure: float,
    security_pressure: float,
    policy_entry: dict[str, Any],
) -> dict[str, Any]:
    shock = policy_entry.get("shock") or {}
    if shock.get("is_shock"):
        actions = list(shock.get("starter_actions") or [])
        urgency = "HIGH" if policy_entry.get("enabled") or security_pressure >= 0.5 else "MEDIUM"
        mode = "PAUSE" if urgency == "HIGH" else "ALLOW"
        return {
            "auto_trade_mode": mode,
            "risk_multiplier": min(0.5, float(policy_entry.get("risk_multiplier") or 0.5)),
            "trade_posture": f"{bias}_POLICY_SHOCK",
            "requires_confirmation": bool(policy_entry.get("requires_confirmation", True)),
            "blockers": [] if mode == "ALLOW" else [f"{policy_entry.get('category', 'NEWS')} shock requires defensive posture"],
            "starter_actions": actions,
            "starter_reason": f"{bias.title()} {policy_entry.get('category', 'news').lower()} shock mapped from coupling policy.",
            "starter_urgency": urgency,
            "starter_valid_minutes": int(shock.get("valid_minutes") or 180),
        }
    if security_pressure >= 0.5:
        actions = ["PAUSE_NEW_ENTRIES"]
        if bias == "BEARISH":
            actions.extend(["EXIT_LONGS", "ALLOW_HEDGE_SHORT", "START_SHORT"])
        elif bias == "BULLISH":
            actions.extend(["EXIT_SHORTS", "ALLOW_HEDGE_LONG", "START_LONG"])
        else:
            actions.append("REDUCE_GROSS_EXPOSURE")
        return {
            "auto_trade_mode": "MANUAL_REVIEW",
            "risk_multiplier": 0.0,
            "trade_posture": "SECURITY_NEWS_MANUAL_REVIEW",
            "requires_confirmation": True,
            "blockers": ["Security/exploit narrative is elevated; require manual review"],
            "starter_actions": actions,
            "starter_reason": "Elevated security/exploit narrative can start exits, hedges, or fresh directional trades under shock-news risk rules.",
            "starter_urgency": "HIGH",
            "starter_valid_minutes": 180,
        }
    if total_pressure < 0.2 or bias == "UNKNOWN":
        return {
            "auto_trade_mode": "ALLOW",
            "risk_multiplier": 0.5,
            "trade_posture": "ALLOW_REDUCED_SIZE_CONFIRMED_SETUPS",
            "requires_confirmation": True,
            "blockers": [],
            "starter_actions": [],
            "starter_reason": "",
            "starter_urgency": "NONE",
            "starter_valid_minutes": 0,
        }
    if bias == "MIXED":
        return {
            "auto_trade_mode": "ALLOW",
            "risk_multiplier": 0.5,
            "trade_posture": "MIXED_NEWS_REDUCED_SIZE",
            "requires_confirmation": True,
            "blockers": [],
            "starter_actions": [],
            "starter_reason": "",
            "starter_urgency": "NONE",
            "starter_valid_minutes": 0,
        }
    actions = ["PAUSE_CONFLICTING_ENTRIES"]
    if bias == "BEARISH":
        actions.extend(["EXIT_LONGS_IF_UNCONFIRMED", "START_SHORT_IF_CONFIRMED"])
    elif bias == "BULLISH":
        actions.extend(["EXIT_SHORTS_IF_UNCONFIRMED", "START_LONG_IF_CONFIRMED"])
    return {
        "auto_trade_mode": "ALLOW",
        "risk_multiplier": 0.75,
        "trade_posture": f"{bias}_NEWS_CONFIRMATION_REQUIRED",
        "requires_confirmation": True,
        "blockers": [],
        "starter_actions": actions,
        "starter_reason": f"{bias.title()} news pressure may start a trade when source quality and market confirmation pass.",
        "starter_urgency": "MEDIUM",
        "starter_valid_minutes": 120,
    }


def build_context(events: list[dict[str, Any]], max_age_hours: float, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - max_age_hours * 3600.0
    per_asset: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "bullish_pressure": 0.0,
        "bearish_pressure": 0.0,
        "security_pressure": 0.0,
        "source_count": 0,
        "titles": [],
        "categories": defaultdict(int),
    })
    for event in events:
        if float(event.get("published_ts") or 0.0) < cutoff:
            continue
        sign = BIAS_SIGN.get(str(event.get("directional_bias") or "").upper(), 0)
        pressure = _pressure(event)
        for asset in event.get("assets") or []:
            row = per_asset[str(asset).upper()]
            row["source_count"] += 1
            row["categories"][str(event.get("category") or "UNKNOWN").upper()] += 1
            if event.get("title"):
                row["titles"].append(str(event["title"])[:140])
            if sign > 0:
                row["bullish_pressure"] += pressure
            elif sign < 0:
                row["bearish_pressure"] += pressure
            if str(event.get("category") or "").upper() == "SECURITY":
                row["security_pressure"] += pressure

    assets: dict[str, Any] = {}
    for asset in ("BTC", "ETH"):
        row = per_asset.get(asset, {
            "bullish_pressure": 0.0,
            "bearish_pressure": 0.0,
            "security_pressure": 0.0,
            "source_count": 0,
            "titles": [],
            "categories": {},
        })
        bull = float(row["bullish_pressure"])
        bear = float(row["bearish_pressure"])
        total = bull + bear
        bias = _bias_from_pressure(bull, bear)
        categories = row.get("categories") or {}
        starter_category, starter_horizon, policy_entry = _best_policy_entry(policy or {}, dict(categories), bias)
        posture = _auto_posture(bias, total, float(row["security_pressure"]), policy_entry)
        top_categories = sorted(categories.items(), key=lambda kv: kv[1], reverse=True)[:3]
        summary_bits = []
        if row["source_count"]:
            summary_bits.append(f"{row['source_count']} recent item(s)")
        if top_categories:
            summary_bits.append("top categories: " + ", ".join(k for k, _v in top_categories))
        if row["titles"]:
            summary_bits.append("latest: " + " | ".join(row["titles"][:2]))
        valid_minutes = int(posture.get("starter_valid_minutes") or 0)
        starter_valid_until = (now + timedelta(minutes=valid_minutes)).isoformat() if valid_minutes and posture["starter_actions"] else ""
        assets[asset] = {
            "narrative_bias": bias,
            "market_confirmation": "UNKNOWN",
            "crowding_risk": "UNKNOWN",
            "volatility_regime": "ELEVATED",
            "trade_posture": posture["trade_posture"],
            "risk_multiplier": posture["risk_multiplier"],
            "max_leverage": 2,
            "requires_confirmation": posture["requires_confirmation"],
            "auto_trade_mode": posture["auto_trade_mode"],
            "allowed_strategies": ["MOMENTUM", "BREAKOUT_PULLBACK", "CONFIRMED_FOLLOW"],
            "disabled_strategies": ["HIGH_LEVERAGE_SCALP", "NEWS_ONLY_ENTRY"],
            "summary": "; ".join(summary_bits) or "No recent BTC/ETH news items found.",
            "blockers": posture["blockers"],
            "starter_actions": posture["starter_actions"],
            "starter_reason": posture["starter_reason"],
            "starter_urgency": posture["starter_urgency"],
            "starter_valid_until": starter_valid_until,
            "starter_category": starter_category,
            "starter_horizon_min": starter_horizon,
            "policy": policy_entry,
            "source_count": int(row["source_count"]),
            "bullish_pressure": round(bull, 4),
            "bearish_pressure": round(bear, 4),
            "news_dipole": round(bull - bear, 4),
        }
    return {
        "generated_at": now.isoformat(),
        "max_age_hours": max_age_hours,
        "notes": [
            "Generated from news_events.jsonl by build_daily_news_context.py.",
            "Routine news adjusts score/risk; high-confidence shocks can start defensive actions or confirmed directional trades.",
            "Market confirmation remains UNKNOWN until coupling/live market checks update it.",
        ],
        "global_blockers": [],
        "assets": assets,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--events", default="news_events.jsonl")
    p.add_argument("--output", default="daily_news_context.json")
    p.add_argument("--policy", default="news_policy.json")
    p.add_argument("--max-age-hours", type=float, default=36.0)
    args = p.parse_args()

    events = load_events(Path(args.events))
    policy = _load_policy(Path(args.policy))
    context = build_context(events, args.max_age_hours, policy)
    Path(args.output).write_text(json.dumps(context, indent=2), encoding="utf-8")
    print(f"[daily-news-context] events={len(events)} wrote {args.output}")


if __name__ == "__main__":
    main()
