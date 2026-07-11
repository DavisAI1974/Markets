from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


BIAS_TO_SIDE = {
    "BULLISH": "buy",
    "BEARISH": "sell",
}


@dataclass
class AssetNewsContext:
    asset: str
    narrative_bias: str = "UNKNOWN"
    market_confirmation: str = "UNKNOWN"
    crowding_risk: str = "UNKNOWN"
    volatility_regime: str = "UNKNOWN"
    trade_posture: str = "NEUTRAL"
    risk_multiplier: float = 1.0
    max_leverage: float | None = None
    requires_confirmation: bool = False
    auto_trade_mode: str = "ALLOW"
    allowed_strategies: list[str] = field(default_factory=list)
    disabled_strategies: list[str] = field(default_factory=list)
    summary: str = ""
    blockers: list[str] = field(default_factory=list)
    starter_actions: list[str] = field(default_factory=list)
    starter_reason: str = ""
    starter_urgency: str = "NONE"
    starter_valid_until: str = ""
    starter_category: str = ""
    starter_horizon_min: int | None = None
    policy: dict[str, Any] = field(default_factory=dict)
    news_dipole: float | None = None
    source_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyNewsContext:
    generated_at: str = ""
    status: str = "missing"
    stale: bool = False
    max_age_hours: float = 36.0
    assets: dict[str, AssetNewsContext] = field(default_factory=dict)
    global_blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def for_asset(self, asset: str) -> AssetNewsContext:
        key = str(asset).upper()
        return self.assets.get(key, AssetNewsContext(asset=key))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "status": self.status,
            "stale": self.stale,
            "max_age_hours": self.max_age_hours,
            "global_blockers": list(self.global_blockers),
            "notes": list(self.notes),
            "assets": {k: v.to_dict() for k, v in self.assets.items()},
        }


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or default).strip().upper()
    return text or default


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_generated_at(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_stale(generated_at: str, max_age_hours: float, now: datetime | None) -> bool:
    dt = _parse_generated_at(generated_at)
    if dt is None:
        return bool(generated_at)
    now = now or datetime.now(timezone.utc)
    return (now - dt).total_seconds() > max_age_hours * 3600.0


def _is_expired(iso_value: str, now: datetime | None = None) -> bool:
    dt = _parse_generated_at(iso_value)
    if dt is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc) > dt


def _asset_from_dict(asset: str, raw: dict[str, Any]) -> AssetNewsContext:
    risk_multiplier = _float_or_none(raw.get("risk_multiplier"))
    if risk_multiplier is None:
        risk_multiplier = 1.0
    risk_multiplier = max(0.0, min(1.0, risk_multiplier))
    return AssetNewsContext(
        asset=asset.upper(),
        narrative_bias=_upper(raw.get("narrative_bias")),
        market_confirmation=_upper(raw.get("market_confirmation")),
        crowding_risk=_upper(raw.get("crowding_risk")),
        volatility_regime=_upper(raw.get("volatility_regime")),
        trade_posture=_upper(raw.get("trade_posture"), "NEUTRAL"),
        risk_multiplier=risk_multiplier,
        max_leverage=_float_or_none(raw.get("max_leverage")),
        requires_confirmation=bool(raw.get("requires_confirmation", False)),
        auto_trade_mode=_upper(raw.get("auto_trade_mode"), "ALLOW"),
        allowed_strategies=[str(x).upper() for x in raw.get("allowed_strategies", [])],
        disabled_strategies=[str(x).upper() for x in raw.get("disabled_strategies", [])],
        summary=str(raw.get("summary") or ""),
        blockers=[str(x) for x in raw.get("blockers", [])],
        starter_actions=[str(x).upper() for x in raw.get("starter_actions", [])],
        starter_reason=str(raw.get("starter_reason") or ""),
        starter_urgency=_upper(raw.get("starter_urgency"), "NONE"),
        starter_valid_until=str(raw.get("starter_valid_until") or ""),
        starter_category=_upper(raw.get("starter_category"), ""),
        starter_horizon_min=int(raw["starter_horizon_min"]) if raw.get("starter_horizon_min") not in (None, "") else None,
        policy=dict(raw.get("policy") or {}),
        news_dipole=_float_or_none(raw.get("news_dipole")),
        source_count=int(raw.get("source_count") or 0),
    )


def adjust_present_score_with_news(
    base_score: float,
    side: str,
    asset_ctx: AssetNewsContext,
    *,
    now: datetime | None = None,
    news_dipole_value: float | None = None,
) -> int:
    """Bounded news modifier for market-derived present scores.

    Routine news nudges readiness; blockers and shock postures still flow through
    trade-option blockers so the score does not silently authorize bad trades.
    """
    score = float(base_score)
    mode = asset_ctx.auto_trade_mode
    if mode in {"PAUSE", "MANUAL_REVIEW", "BLOCK"} or asset_ctx.blockers:
        score = max(score - 20.0, 0.0)

    policy = asset_ctx.policy or {}
    if policy:
        edge = float(policy.get("signed_bps_edge_vs_placebo") or 0.0)
        risk_mult = float(policy.get("risk_multiplier") or asset_ctx.risk_multiplier or 1.0)
        bias = _upper(policy.get("directional_bias") or asset_ctx.narrative_bias)
        delta = min(7.0, max(0.0, edge / 2.0))
        delta *= max(0.5, min(1.2, risk_mult))
        side_bias = "BULLISH" if str(side).lower() == "buy" else "BEARISH"
        if bias == side_bias:
            score += delta
        elif bias in {"BULLISH", "BEARISH"}:
            score -= delta

    dipole = news_dipole_value if news_dipole_value is not None else asset_ctx.news_dipole
    if dipole is not None:
        dipole = float(dipole)
        if dipole:
            dipole_mag = min(1.0, abs(dipole))
            dipole_sign = 1 if dipole > 0 else -1
            side_sign = 1 if str(side).lower() == "buy" else -1
            score += dipole_mag * (3.0 if dipole_sign == side_sign else -3.0)

    if asset_ctx.crowding_risk in {"HIGH", "EXTREME"}:
        score -= 3.0
    if asset_ctx.volatility_regime == "CRISIS":
        score -= 5.0

    if asset_ctx.starter_valid_until and _is_expired(asset_ctx.starter_valid_until, now):
        score -= 2.0
    return int(max(0, min(100, round(score))))


def load_daily_news_context(
    path: str = "daily_news_context.json",
    *,
    now: datetime | None = None,
) -> DailyNewsContext:
    if not os.path.exists(path):
        return DailyNewsContext(
            status="missing",
            notes=[f"No daily news context found at {path}"],
        )
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        return DailyNewsContext(
            status="error",
            notes=[f"Could not parse daily news context: {e}"],
        )

    generated_at = str(raw.get("generated_at") or "")
    max_age_hours = float(raw.get("max_age_hours") or 36.0)
    assets_raw = raw.get("assets") or {}
    assets: dict[str, AssetNewsContext] = {}
    if isinstance(assets_raw, dict):
        for asset, value in assets_raw.items():
            if isinstance(value, dict):
                assets[str(asset).upper()] = _asset_from_dict(str(asset), value)
    return DailyNewsContext(
        generated_at=generated_at,
        status="ok",
        stale=_is_stale(generated_at, max_age_hours, now),
        max_age_hours=max_age_hours,
        assets=assets,
        global_blockers=[str(x) for x in raw.get("global_blockers", [])],
        notes=[str(x) for x in raw.get("notes", [])],
    )


def news_adjusted_trade_option(
    option: dict[str, Any],
    context: DailyNewsContext,
    asset: str,
    side: str,
) -> dict[str, Any]:
    if not option:
        return option

    out = dict(option)
    blockers = list(out.get("trade_option_blockers") or [])
    reasons = list(out.get("trade_option_entry_reasons") or [])
    asset_ctx = context.for_asset(asset)
    side = str(side or "").lower()

    if context.status in {"missing", "error"}:
        reasons.append("Daily news context unavailable; news layer did not change criteria")
    elif context.stale:
        blockers.append("Daily news context is stale; auto-trade needs a fresh brief")
    else:
        bias_side = BIAS_TO_SIDE.get(asset_ctx.narrative_bias)
        starter_expired = _is_expired(asset_ctx.starter_valid_until)
        if starter_expired and asset_ctx.starter_actions:
            asset_ctx = AssetNewsContext(
                **{
                    **asset_ctx.to_dict(),
                    "starter_actions": [],
                    "starter_urgency": "EXPIRED",
                }
            )
        if asset_ctx.summary:
            reasons.append(f"Daily news: {asset_ctx.summary}")
        else:
            reasons.append(
                f"Daily news bias {asset_ctx.narrative_bias.lower()}, "
                f"confirmation {asset_ctx.market_confirmation.lower()}"
            )
        if asset_ctx.auto_trade_mode in {"PAUSE", "MANUAL_REVIEW", "BLOCK"}:
            blockers.append(f"Daily news posture requires {asset_ctx.auto_trade_mode.lower().replace('_', ' ')}")
        if context.global_blockers:
            blockers.extend(context.global_blockers)
        if asset_ctx.blockers:
            blockers.extend(asset_ctx.blockers)
        if asset_ctx.requires_confirmation and asset_ctx.market_confirmation in {"WEAK", "LOW", "UNKNOWN"}:
            blockers.append("Daily news requires stronger market confirmation")
        if bias_side and side and bias_side != side and asset_ctx.market_confirmation != "STRONG":
            blockers.append(f"Daily news bias conflicts with {side} setup")
        if starter_expired:
            reasons.append("Shock-news starter window expired; posture remains as context only")

    base_scale = float(out.get("trade_option_notional_scale") or 0.0)
    risk_multiplier = asset_ctx.risk_multiplier
    if context.status in {"missing", "error"}:
        risk_multiplier = 1.0
    elif context.stale:
        risk_multiplier = 0.0
    out["trade_option_notional_scale"] = base_scale * risk_multiplier
    out["daily_news_context"] = asset_ctx.to_dict()
    out["daily_news_status"] = {
        "status": context.status,
        "stale": context.stale,
        "generated_at": context.generated_at,
    }
    out["trade_option_entry_reasons"] = reasons[:6]
    out["trade_option_blockers"] = list(dict.fromkeys(blockers))[:6]
    return out
