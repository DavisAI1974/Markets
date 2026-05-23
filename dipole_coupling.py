from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from onchain_features import (
    ONCHAIN_ACCUMULATION,
    ONCHAIN_DISTRIBUTION,
    ONCHAIN_ROTATION,
    ONCHAIN_STRESS,
    classify_onchain_regime,
)


COUPLING_ALIGNED = "aligned"
COUPLING_NEUTRAL = "neutral"
COUPLING_CONFLICTING = "conflicting"


FAMILY_WEIGHTS = {
    "NEWS_CONFIRMED_DIRECTIONAL": 0.85,
    "NEWS_BREAKOUT": 0.85,
    "BASIS_DISLOCATION": 0.75,
    "LIQUIDITY_SQUEEZE": 0.70,
    "VOL_BREAKOUT": 0.65,
    "BREAKOUT_PULLBACK": 0.65,
    "RELATIVE_STRENGTH": 0.60,
    "SESSION_STRUCTURE": 0.45,
    "MEAN_REVERSION_CHOP": 0.35,
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _side_sign(side: Any) -> int:
    text = str(side or "").lower()
    if text in {"buy", "long", "bullish"}:
        return 1
    if text in {"sell", "short", "bearish"}:
        return -1
    return 0


def _regime_from_onchain(onchain: dict[str, Any]) -> str:
    labels = onchain.get("labels") or {}
    regime = str(labels.get("onchain_regime") or onchain.get("onchain_regime") or "")
    return regime or classify_onchain_regime(onchain)


@dataclass
class DipoleCoupling:
    market_dipole: float = 0.0
    news_dipole: float = 0.0
    onchain_dipole: float = 0.0
    family_dipole: float = 0.0
    coupling_score: float = 0.0
    coupling_state: str = COUPLING_NEUTRAL
    conflicts: list[str] = field(default_factory=list)
    components_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        for key in ("market_dipole", "news_dipole", "onchain_dipole", "family_dipole", "coupling_score"):
            out[key] = round(float(out[key]), 6)
        return out


def market_dipole_from_inputs(inputs: dict[str, Any] | None = None, status: Any | None = None) -> float:
    inputs = inputs or {}
    value = inputs.get("mean_dipole")
    if value is None and status is not None:
        value = getattr(status, "mean_dipole", 0.0)
    return _clamp(_float(value))


def news_dipole_from_context(news_context: dict[str, Any] | None = None, asset_news: Any | None = None) -> float:
    if asset_news is not None:
        return _clamp(_float(getattr(asset_news, "news_dipole", 0.0)))
    news_context = news_context or {}
    return _clamp(_float(news_context.get("news_dipole")))


def onchain_dipole_from_features(onchain: dict[str, Any] | None = None) -> float:
    onchain = onchain or {}
    if not onchain:
        return 0.0
    regime = _regime_from_onchain(onchain)
    if regime == ONCHAIN_ACCUMULATION:
        base = 0.75
    elif regime == ONCHAIN_DISTRIBUTION:
        base = -0.75
    elif regime == ONCHAIN_ROTATION:
        base = 0.25
    elif regime == ONCHAIN_STRESS:
        base = -0.45
    else:
        base = 0.0

    flows = onchain.get("exchange_flows") or {}
    whales = onchain.get("whales") or {}
    smart = onchain.get("smart_money") or {}
    stables = onchain.get("stablecoins") or {}
    netflow_z = _float(flows.get("netflow_zscore"))
    whale_z = _float(whales.get("accumulation_zscore")) - _float(whales.get("distribution_zscore"))
    smart_in = _float(smart.get("net_into_asset_usd"))
    smart_out = _float(smart.get("net_out_of_asset_usd"))
    smart_flow = (smart_in - smart_out) / max(abs(smart_in) + abs(smart_out), 1.0)
    stable_z = _float(stables.get("netflow_zscore"))

    # Exchange net outflows are bullish for supply, hence the negative sign.
    score = base
    score += _clamp(-netflow_z / 3.0) * 0.30
    score += _clamp(whale_z / 3.0) * 0.30
    score += _clamp(smart_flow) * 0.25
    score += _clamp(stable_z / 3.0) * 0.15
    return _clamp(score)


def family_dipole_from_trade(trade: dict[str, Any]) -> float:
    family = str(
        trade.get("trade_strategy_id")
        or trade.get("family")
        or trade.get("strategy_family")
        or ""
    ).upper()
    sign = _side_sign(trade.get("side") or trade.get("trade_option_side"))
    confidence = _float(trade.get("trade_strategy_confidence"), 1.0)
    weight = FAMILY_WEIGHTS.get(family, 0.50 if family else 0.0)
    return _clamp(sign * max(0.0, min(1.0, confidence)) * weight)


def family_dipole_from_status(status: Any | None = None, side: Any = None) -> float:
    if status is None:
        return 0.0
    family = str(getattr(status, "trade_strategy_id", "") or "").upper()
    sign = _side_sign(side or getattr(status, "trade_option_side", "") or getattr(status, "pressure_watch_direction", ""))
    confidence = _float(getattr(status, "trade_strategy_confidence", 0.0), 1.0)
    weight = FAMILY_WEIGHTS.get(family, 0.50 if family else 0.0)
    return _clamp(sign * max(0.0, min(1.0, confidence)) * weight)


def classify_coupling_state(components: dict[str, float]) -> tuple[str, list[str]]:
    active = {k: v for k, v in components.items() if abs(v) >= 0.10}
    conflicts: list[str] = []
    names = list(active)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            if active[left] * active[right] <= -0.0625:
                conflicts.append(f"{left}_vs_{right}_conflict")
    if conflicts:
        return COUPLING_CONFLICTING, conflicts
    avg_abs = sum(abs(v) for v in active.values()) / max(1, len(active))
    if len(active) >= 2 and avg_abs >= 0.25:
        return COUPLING_ALIGNED, []
    return COUPLING_NEUTRAL, []


def build_dipole_coupling(
    *,
    status: Any | None = None,
    inputs: dict[str, Any] | None = None,
    news_context: dict[str, Any] | None = None,
    asset_news: Any | None = None,
    onchain: dict[str, Any] | None = None,
    trade: dict[str, Any] | None = None,
) -> DipoleCoupling:
    trade = trade or {}
    market = market_dipole_from_inputs(inputs, status)
    news = news_dipole_from_context(news_context or trade.get("daily_news_context"), asset_news)
    onchain_value = onchain_dipole_from_features(onchain or trade.get("onchain_features"))
    family = family_dipole_from_trade(trade) if trade else family_dipole_from_status(status)
    components = {
        "market": market,
        "news": news,
        "onchain": onchain_value,
        "family": family,
    }
    used = [k for k, v in components.items() if abs(v) >= 0.05]
    denom = max(1, len(used))
    score = _clamp(sum(components[k] for k in used) / denom if used else 0.0)
    state, conflicts = classify_coupling_state(components)
    return DipoleCoupling(
        market_dipole=market,
        news_dipole=news,
        onchain_dipole=onchain_value,
        family_dipole=family,
        coupling_score=score,
        coupling_state=state,
        conflicts=conflicts,
        components_used=used,
    )
