from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


MEAN_REVERSION_CHOP = "MEAN_REVERSION_CHOP"
SMALL_MOVE_FADE = "SMALL_MOVE_FADE"
BUY_UP_CONTINUATION = "BUY_UP_CONTINUATION"
BUY_FADE = "BUY_FADE"
SELL_DOWN_CONTINUATION = "SELL_DOWN_CONTINUATION"
NEWS_BREAKOUT = "NEWS_BREAKOUT"
LIQUIDITY_SQUEEZE = "LIQUIDITY_SQUEEZE"
VOL_BREAKOUT = "VOL_BREAKOUT"
BASIS_DISLOCATION = "BASIS_DISLOCATION"
RELATIVE_STRENGTH = "RELATIVE_STRENGTH"

PRACTICE_MODES = {"practice", "explore", "autoresearch", "learning", "live_paper"}

CHOP_REGIMES = {"EQUILIBRIUM_TWO_SIDED", "WASH_HAWKES", "WASH_PAIRED", "DEPLETED"}
SQUEEZE_REGIMES = {"HERD_UP", "HERD_DOWN", "WHALE_UP", "WHALE_DOWN"}
NEWS_REGIMES = {"HERD_UP", "HERD_DOWN", "WHALE_UP", "WHALE_DOWN", "WHALE_NASCENT_UP", "WHALE_NASCENT_DOWN"}
VOL_BREAKOUT_REGIMES = {"HERD_UP", "HERD_DOWN", "WHALE_UP", "WHALE_DOWN", "WHALE_NASCENT_UP", "WHALE_NASCENT_DOWN"}

_DEBUG: dict[str, Counter[str]] = defaultdict(Counter)


@dataclass(frozen=True)
class PracticeStrategySignal:
    strategy_id: str
    label: str
    side: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    forced: bool = False
    variant_id: str = ""
    risk_tags: list[str] = field(default_factory=list)
    handoff_hint: str = ""
    source_queue_action: str = ""


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _opposite(side: str) -> str:
    return "sell" if side == "buy" else "buy" if side == "sell" else ""


def _pressure_side(status: Any) -> str:
    side = str(getattr(status, "trade_option_side", "") or getattr(status, "pressure_watch_direction", "") or "").lower()
    return side if side in {"buy", "sell"} else ""


def _news_side(asset_news: Any) -> str:
    if asset_news is None:
        return ""
    bias = str(getattr(asset_news, "narrative_bias", "") or "").upper()
    if bias == "BULLISH":
        return "buy"
    if bias == "BEARISH":
        return "sell"
    dipole = _float(getattr(asset_news, "news_dipole", 0.0))
    if dipole >= 0.20:
        return "buy"
    if dipole <= -0.20:
        return "sell"
    return ""


def _variant_id(strategy_id: str, status: Any, inputs: dict[str, Any], *, forced: bool = False) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    asset = str(getattr(status, "asset", "") or "asset").lower()
    venue = str(getattr(status, "venue", "") or "venue").lower()
    session = str(inputs.get("bucket_session") or "session").lower()
    mode = "forced" if forced else "normal"
    return f"{strategy_id.lower()}__{mode}_{asset}_{venue}_{session}__{stamp}"


def _risk_tags(status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> list[str]:
    tags: list[str] = []
    asset = str(getattr(status, "asset", "") or "").upper()
    venue = str(getattr(status, "venue", "") or "").lower()
    session = str(inputs.get("bucket_session") or "").lower()
    if asset == "ETH" and venue in {"coinbase", "kraken"} and session == "first6h":
        tags.append("known_bad_bucket")
    if asset_news is None:
        tags.append("news_context_missing")
    return list(dict.fromkeys(tags))


class PracticeStrategy:
    strategy_id = ""
    label = ""

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        raise NotImplementedError

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        raise NotImplementedError

    def _drop(self, reason: str) -> None:
        _DEBUG[self.strategy_id][reason] += 1

    def _hit(self) -> None:
        _DEBUG[self.strategy_id]["signals"] += 1


class MeanReversionChopStrategy(PracticeStrategy):
    strategy_id = MEAN_REVERSION_CHOP
    label = "Mean reversion chop"

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("no_pressure_side")
            return None
        regime = str(getattr(status, "regime", "") or "")
        stage = str(inputs.get("trade_stage") or getattr(status, "trade_stage", "") or "")
        score = _int(inputs.get("trade_present_score") or getattr(status, "trade_present_score", 0))
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        from_onset_bps = _float(inputs.get("trade_from_onset_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        abs_dipole = abs(_float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0)))
        risk_tags = _risk_tags(status, inputs, asset_news)
        if "known_bad_bucket" in risk_tags:
            self._drop("known_bad_bucket_risk")

        is_chop = regime in CHOP_REGIMES
        is_stalled = stage in {"early_follow", "mature"} and recent_bps <= 1.0 and score <= 72
        is_stretched = abs(current_bps) >= 1.2 or abs(from_onset_bps) >= 5.0 or abs_dipole >= 0.18
        if not (is_chop or is_stalled):
            self._drop("wrong_regime_or_not_stalled")
            return None
        if not is_stretched:
            self._drop("not_stretched")
            return None

        fade_side = _opposite(side) or side
        confidence = 0.50 + min(0.18, abs(current_bps) / 70.0) + min(0.12, abs(from_onset_bps) / 140.0)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=fade_side,
            confidence=min(0.82, confidence),
            reasons=["Practice mean-reversion: chop/stall plus stretched pressure"],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=risk_tags,
            handoff_hint="If fade fails, pass stretch/chop context to vol_breakout or liquidity_squeeze.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("forced_no_pressure_side")
            return None
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=_opposite(side) or side,
            confidence=0.41,
            reasons=["Forced learning probe: mean-reversion family must trade and report fit"],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", *_risk_tags(status, inputs, asset_news)],
            handoff_hint="Report whether forced fade improved over pressure-following alternatives.",
            source_queue_action=source_queue_action,
        )


class SmallMoveFadeStrategy(PracticeStrategy):
    strategy_id = SMALL_MOVE_FADE
    label = "Small move fade"

    def _is_small_up_fade_shape(self, status: Any, inputs: dict[str, Any]) -> bool:
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        from_onset_bps = _float(inputs.get("trade_from_onset_bps"))
        volume_z = _float(inputs.get("volume_zscore"))
        mean_dipole = _float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0))
        pressure_state = str(getattr(status, "pressure_watch_state", "") or "")
        pressure_side = _pressure_side(status)
        if not (0.0 <= current_bps < 5.0 and 0.0 <= recent_bps < 5.0):
            return False
        if from_onset_bps >= 12.0:
            return False
        if pressure_side == "buy" and mean_dipole >= 0.05:
            return False
        strong_continuation = mean_dipole >= 0.35 and volume_z >= 1.5 and pressure_state in {"high_priority", "confirmed"}
        return not strong_continuation

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        if not self._is_small_up_fade_shape(status, inputs):
            self._drop("not_small_up_fade_shape")
            return None
        risk_tags = [*_risk_tags(status, inputs, asset_news), "small_up_sell_fade"]
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        volume_z = _float(inputs.get("volume_zscore"))
        confidence = 0.54 + min(0.08, (5.0 - min(current_bps, 5.0)) / 80.0) + min(0.08, max(0.0, 1.5 - volume_z) / 20.0)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side="sell",
            confidence=min(0.78, confidence),
            reasons=[
                "Small upward push is not confirming continuation; testing the sell fade pattern",
                f"Current/recent move: {current_bps:.2f}/{recent_bps:.2f} bps",
            ],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=risk_tags,
            handoff_hint="Promote only when repeated small-up sell fades remain positive after fees.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        if not self._is_small_up_fade_shape(status, inputs):
            self._drop("forced_not_small_up_fade_shape")
            return None
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side="sell",
            confidence=0.44,
            reasons=[
                "Forced learning probe: small move up sell fade must collect live evidence",
                f"Current/recent move: {current_bps:.2f}/{recent_bps:.2f} bps",
            ],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", "small_up_sell_fade", *_risk_tags(status, inputs, asset_news)],
            handoff_hint="Compare against VOL_BREAKOUT, BASIS_DISLOCATION, and RELATIVE_STRENGTH sell variants.",
            source_queue_action=source_queue_action,
        )


class BuyUpContinuationStrategy(PracticeStrategy):
    strategy_id = BUY_UP_CONTINUATION
    label = "Buy up continuation"

    def _is_buy_up_continuation_shape(self, status: Any, inputs: dict[str, Any]) -> bool:
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        from_onset_bps = _float(inputs.get("trade_from_onset_bps"))
        volume_z = _float(inputs.get("volume_zscore"))
        mean_dipole = _float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0))
        pressure_side = _pressure_side(status)
        if recent_bps < 0.0:
            return False
        if current_bps < -2.0 and from_onset_bps < 0.0:
            return False
        if mean_dipole <= -0.25 and volume_z >= 1.0:
            return False
        if pressure_side == "sell" and mean_dipole < -0.05:
            return False
        return True

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        if not self._is_buy_up_continuation_shape(status, inputs):
            self._drop("not_buy_up_continuation_shape")
            return None
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        from_onset_bps = _float(inputs.get("trade_from_onset_bps"))
        mean_dipole = _float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0))
        confidence = 0.52 + min(0.10, max(recent_bps, 0.0) / 120.0) + min(0.08, max(mean_dipole, 0.0) * 0.20)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side="buy",
            confidence=min(0.82, confidence),
            reasons=[
                "Upward continuation shape is repeating in hindsight winners; testing the buy follow-through pattern",
                f"Current/recent/onset move: {current_bps:.2f}/{recent_bps:.2f}/{from_onset_bps:.2f} bps",
            ],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=[*_risk_tags(status, inputs, asset_news), "buy_up_continuation"],
            handoff_hint="Pair with the top buy-up continuation exits only after live/shadow evidence separates a clear winner.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        if not self._is_buy_up_continuation_shape(status, inputs):
            self._drop("forced_not_buy_up_continuation_shape")
            return None
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side="buy",
            confidence=0.44,
            reasons=[
                "Forced learning probe: buy-up continuation must collect executable evidence",
                f"Current/recent move: {current_bps:.2f}/{recent_bps:.2f} bps",
            ],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", "buy_up_continuation", *_risk_tags(status, inputs, asset_news)],
            handoff_hint="Compare hold-20 gated, hold-10 gated, and hard TP/SL exits before allowing a primary route.",
            source_queue_action=source_queue_action,
        )


class BuyFadeStrategy(PracticeStrategy):
    strategy_id = BUY_FADE
    label = "Buy fade"

    def _is_buy_fade_shape(self, status: Any, inputs: dict[str, Any]) -> bool:
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        volume_z = _float(inputs.get("volume_zscore"))
        mean_dipole = _float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0))
        pressure_state = str(getattr(status, "pressure_watch_state", "") or "")
        if not (current_bps < 0.0 or recent_bps < 0.0):
            return False
        strong_down_continuation = (
            mean_dipole <= -0.35
            and volume_z >= 1.5
            and pressure_state in {"high_priority", "confirmed"}
        )
        return not strong_down_continuation

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        if not self._is_buy_fade_shape(status, inputs):
            self._drop("not_buy_fade_shape")
            return None
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        shape = "extended_down_buy_fade" if min(current_bps, recent_bps) <= -5.0 else "small_down_buy_fade"
        confidence = 0.48 + min(0.10, abs(min(current_bps, recent_bps, 0.0)) / 140.0)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side="buy",
            confidence=min(0.72, confidence),
            reasons=[
                "Downward move is not confirmed enough to chase; testing the buy fade pattern",
                f"Current/recent move: {current_bps:.2f}/{recent_bps:.2f} bps",
            ],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=[*_risk_tags(status, inputs, asset_news), shape],
            handoff_hint="Keep mock-only until an exit mutation turns this family positive after fees.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        if not self._is_buy_fade_shape(status, inputs):
            self._drop("forced_not_buy_fade_shape")
            return None
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side="buy",
            confidence=0.42,
            reasons=[
                "Forced learning probe: buy fade must test whether downside exhaustion is executable",
                f"Current/recent move: {current_bps:.2f}/{recent_bps:.2f} bps",
            ],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", "buy_fade", *_risk_tags(status, inputs, asset_news)],
            handoff_hint="Evolve should create exits if all tested candidates remain low-margin or negative.",
            source_queue_action=source_queue_action,
        )


class SellDownContinuationStrategy(PracticeStrategy):
    strategy_id = SELL_DOWN_CONTINUATION
    label = "Sell down continuation"

    def _is_sell_down_continuation_shape(self, status: Any, inputs: dict[str, Any]) -> bool:
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        from_onset_bps = _float(inputs.get("trade_from_onset_bps"))
        volume_z = _float(inputs.get("volume_zscore"))
        mean_dipole = _float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0))
        pressure_side = _pressure_side(status)
        pressure_state = str(getattr(status, "pressure_watch_state", "") or "")
        if recent_bps >= 0.0:
            return False
        if current_bps > 2.0 and from_onset_bps > 0.0:
            return False
        if not (
            pressure_side == "sell"
            or mean_dipole <= -0.05
            or recent_bps <= -5.0
            or pressure_state in {"forming", "high_priority", "confirmed"}
        ):
            return False
        if mean_dipole >= 0.25 and volume_z >= 1.0:
            return False
        if pressure_side == "buy" and mean_dipole > 0.05:
            return False
        return True

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        if not self._is_sell_down_continuation_shape(status, inputs):
            self._drop("not_sell_down_continuation_shape")
            return None
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        mean_dipole = _float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0))
        confidence = 0.50 + min(0.10, abs(min(recent_bps, 0.0)) / 120.0) + min(0.08, abs(min(mean_dipole, 0.0)) * 0.20)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side="sell",
            confidence=min(0.80, confidence),
            reasons=[
                "Downward continuation shape is repeating in hindsight winners; testing the sell follow-through pattern",
                f"Current/recent move: {current_bps:.2f}/{recent_bps:.2f} bps",
            ],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=[*_risk_tags(status, inputs, asset_news), "sell_down_continuation"],
            handoff_hint="Keep shadow/evolve pressure on exits until this family proves positive after fees.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        if not self._is_sell_down_continuation_shape(status, inputs):
            self._drop("forced_not_sell_down_continuation_shape")
            return None
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side="sell",
            confidence=0.43,
            reasons=[
                "Forced learning probe: sell-down continuation must collect executable evidence",
                f"Current/recent move: {current_bps:.2f}/{recent_bps:.2f} bps",
            ],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", "sell_down_continuation", *_risk_tags(status, inputs, asset_news)],
            handoff_hint="Compare continuation exits against quick hard TP/SL before selecting a primary route.",
            source_queue_action=source_queue_action,
        )


class LiquiditySqueezeStrategy(PracticeStrategy):
    strategy_id = LIQUIDITY_SQUEEZE
    label = "Liquidity squeeze fade"

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("no_pressure_side")
            return None
        regime = str(getattr(status, "regime", "") or "")
        volume_z = _float(inputs.get("volume_zscore"))
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        from_onset_bps = _float(inputs.get("trade_from_onset_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        abs_move = max(abs(current_bps), abs(from_onset_bps))

        if regime not in SQUEEZE_REGIMES and volume_z < 1.2:
            self._drop("wrong_regime_or_no_thinness_proxy")
            return None
        if abs_move < 7.0:
            self._drop("move_not_extreme")
            return None
        if recent_bps > 3.0:
            self._drop("move_still_extending")
            return None

        fade_side = _opposite(side) or side
        confidence = 0.51 + min(0.16, abs_move / 160.0) + min(0.12, max(volume_z, 0.0) / 10.0)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=fade_side,
            confidence=min(0.82, confidence),
            reasons=["Practice liquidity squeeze: extreme move is losing extension"],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=_risk_tags(status, inputs, asset_news),
            handoff_hint="If squeeze fade fails, hand off volume/thinness diagnostics to vol_breakout or basis_dislocation.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("forced_no_pressure_side")
            return None
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=_opposite(side) or side,
            confidence=0.40,
            reasons=["Forced learning probe: liquidity squeeze family must test fade fit"],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", *_risk_tags(status, inputs, asset_news)],
            handoff_hint="Report whether the move had enough extension/thinness for squeeze logic.",
            source_queue_action=source_queue_action,
        )


class NewsBreakoutStrategy(PracticeStrategy):
    strategy_id = NEWS_BREAKOUT
    label = "News breakout"

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        news_side = _news_side(asset_news)
        if not news_side:
            self._drop("no_news_bias")
            return None
        market_side = _pressure_side(status)
        if market_side and market_side != news_side:
            self._drop("news_market_conflict")
            return None
        regime = str(getattr(status, "regime", "") or "")
        confirmation = str(getattr(asset_news, "market_confirmation", "") or "").upper() if asset_news is not None else ""
        dipole = abs(_float(getattr(asset_news, "news_dipole", 0.0))) if asset_news is not None else 0.0
        volume_z = _float(inputs.get("volume_zscore"))
        current_bps = abs(_float(inputs.get("trade_current_chunk_bps")))

        if regime not in NEWS_REGIMES and confirmation not in {"CONFIRMED", "STRONG"}:
            self._drop("no_structural_confirmation")
            return None
        if dipole < 0.20 and volume_z < 0.7 and current_bps < 4.0:
            self._drop("shock_too_small")
            return None

        confidence = 0.52 + min(0.18, dipole * 0.20) + min(0.10, max(volume_z, 0.0) / 12.0)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=news_side,
            confidence=min(0.86, confidence),
            reasons=["Practice news breakout: news bias has market confirmation"],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=_risk_tags(status, inputs, asset_news),
            handoff_hint="If news breakout fails, report whether news bias or market confirmation was missing.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        side = _news_side(asset_news) or _pressure_side(status)
        if not side:
            self._drop("forced_no_side")
            return None
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=side,
            confidence=0.40,
            reasons=["Forced learning probe: news breakout family must trade even with weak news context"],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", *_risk_tags(status, inputs, asset_news)],
            handoff_hint="Report whether live/news context is absent, stale, or directionally useful.",
            source_queue_action=source_queue_action,
        )


class VolBreakoutStrategy(PracticeStrategy):
    strategy_id = VOL_BREAKOUT
    label = "Volume-confirmed breakout"

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("no_pressure_side")
            return None

        asset = str(getattr(status, "asset", "") or "").upper()
        venue = str(getattr(status, "venue", "") or "").lower()
        session = str(inputs.get("bucket_session") or "").lower()
        risk_tags = _risk_tags(status, inputs, asset_news)
        if "known_bad_bucket" in risk_tags:
            self._drop("known_bad_bucket_risk")

        regime = str(getattr(status, "regime", "") or "")
        stage = str(inputs.get("trade_stage") or getattr(status, "trade_stage", "") or "")
        score = _int(inputs.get("trade_present_score") or getattr(status, "trade_present_score", 0))
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        from_onset_bps = _float(inputs.get("trade_from_onset_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        volume_z = _float(inputs.get("volume_zscore"))
        abs_dipole = abs(_float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0)))

        if regime not in VOL_BREAKOUT_REGIMES:
            self._drop("wrong_regime")
            return None
        if stage not in {"onset", "early_follow", "mature"} or score < 45:
            self._drop("wrong_stage_or_score")
            return None
        if volume_z < 0.7:
            self._drop("volume_not_confirmed")
            return None
        if abs_dipole < 0.18:
            self._drop("dipole_too_weak")
            return None
        if current_bps <= 0.0 or recent_bps <= 0.0 or from_onset_bps <= 3.0:
            self._drop("no_positive_follow_through")
            return None

        confidence = 0.53 + min(0.14, volume_z / 12.0) + min(0.12, abs_dipole * 0.25) + min(0.10, from_onset_bps / 180.0)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=side,
            confidence=min(0.86, confidence),
            reasons=["Practice volume breakout: dipole, volume, and follow-through are aligned"],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=risk_tags,
            handoff_hint="If breakout fails, hand off volume/follow-through diagnostics to basis_dislocation or relative_strength.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("forced_no_pressure_side")
            return None
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=side,
            confidence=0.42,
            reasons=["Forced learning probe: volume breakout family must test pressure-following fit"],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", *_risk_tags(status, inputs, asset_news)],
            handoff_hint="Report whether dipole, volume, or follow-through was the missing breakout ingredient.",
            source_queue_action=source_queue_action,
        )


class BasisDislocationStrategy(PracticeStrategy):
    strategy_id = BASIS_DISLOCATION
    label = "Basis dislocation"

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("no_pressure_side")
            return None
        volume_z = _float(inputs.get("volume_zscore"))
        abs_dipole = abs(_float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0)))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"))
        if abs_dipole < 0.20 and abs(recent_bps) < 12.0:
            self._drop("no_dislocation_proxy")
            return None
        risk_tags = _risk_tags(status, inputs, asset_news)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=side,
            confidence=min(0.78, 0.48 + min(0.12, abs_dipole * 0.20) + min(0.08, max(volume_z, 0.0) / 12.0)),
            reasons=["Practice basis dislocation: pressure/dipole proxy suggests cross-market imbalance"],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=risk_tags,
            handoff_hint="Report whether basis proxy needs real spot/perp funding, venue spread, or relative-strength context.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("forced_no_pressure_side")
            return None
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=side,
            confidence=0.40,
            reasons=["Forced learning probe: basis dislocation family must test pressure/basis proxy fit"],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", *_risk_tags(status, inputs, asset_news), "basis_proxy_missing"],
            handoff_hint="Report whether real basis/funding inputs are required or pressure proxy is sufficient.",
            source_queue_action=source_queue_action,
        )


class RelativeStrengthStrategy(PracticeStrategy):
    strategy_id = RELATIVE_STRENGTH
    label = "Relative strength"

    def suggest(self, status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("no_pressure_side")
            return None
        current_bps = _float(inputs.get("trade_current_chunk_bps"))
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"), current_bps)
        from_onset_bps = _float(inputs.get("trade_from_onset_bps"))
        abs_dipole = abs(_float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0)))
        if abs(recent_bps) < 8.0 and abs(from_onset_bps) < 12.0 and abs_dipole < 0.20:
            self._drop("no_relative_strength_proxy")
            return None
        trade_side = side if recent_bps >= 0.0 or current_bps >= 0.0 else (_opposite(side) or side)
        risk_tags = [*_risk_tags(status, inputs, asset_news), "relative_strength_proxy"]
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=trade_side,
            confidence=min(0.80, 0.47 + min(0.12, abs(recent_bps) / 160.0) + min(0.10, abs_dipole * 0.20)),
            reasons=["Practice relative strength: venue/session strength proxy is directionally active"],
            variant_id=_variant_id(self.strategy_id, status, inputs),
            risk_tags=risk_tags,
            handoff_hint="Report whether relative movement beats basis/volume proxies and which venue-side bucket led.",
        )

    def force_probe(
        self,
        status: Any,
        inputs: dict[str, Any],
        asset_news: Any | None = None,
        *,
        source_queue_action: str = "",
    ) -> PracticeStrategySignal | None:
        side = _pressure_side(status)
        if not side:
            self._drop("forced_no_pressure_side")
            return None
        recent_bps = _float(inputs.get("trade_recent_2chunk_bps"))
        trade_side = side if recent_bps >= 0.0 else (_opposite(side) or side)
        self._hit()
        return PracticeStrategySignal(
            strategy_id=self.strategy_id,
            label=self.label,
            side=trade_side,
            confidence=0.41,
            reasons=["Forced learning probe: relative strength family must test venue/session leadership"],
            forced=True,
            variant_id=_variant_id(self.strategy_id, status, inputs, forced=True),
            risk_tags=["forced_exploration", *_risk_tags(status, inputs, asset_news), "relative_strength_proxy"],
            handoff_hint="Report whether leader/follower behavior is present or needs cross-venue spread features.",
            source_queue_action=source_queue_action,
        )


REGISTRY: dict[str, list[PracticeStrategy]] = {}


def init_strategies() -> None:
    if REGISTRY:
        return
    strategies: list[PracticeStrategy] = [
        SmallMoveFadeStrategy(),
        BuyUpContinuationStrategy(),
        BuyFadeStrategy(),
        SellDownContinuationStrategy(),
        MeanReversionChopStrategy(),
        NewsBreakoutStrategy(),
        LiquiditySqueezeStrategy(),
        VolBreakoutStrategy(),
        BasisDislocationStrategy(),
        RelativeStrengthStrategy(),
    ]
    for asset in ("BTC", "ETH", "BTCUSDT_PERP", "ETHUSDT_PERP"):
        REGISTRY[asset] = list(strategies)


def get_strategies_for_asset(asset: str) -> list[PracticeStrategy]:
    init_strategies()
    return list(REGISTRY.get(str(asset or "").upper(), []))


def suggest_practice_strategy(status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> PracticeStrategySignal | None:
    mode = str(inputs.get("strategy_mode") or "").lower()
    if mode not in PRACTICE_MODES:
        return None
    requested = {str(x).upper() for x in inputs.get("requested_strategy_families") or [] if str(x).strip()}
    signals: list[PracticeStrategySignal] = []
    for strategy in get_strategies_for_asset(str(getattr(status, "asset", "") or "")):
        if requested and strategy.strategy_id not in requested:
            _DEBUG[strategy.strategy_id]["not_requested"] += 1
            continue
        signal = strategy.suggest(status, inputs, asset_news)
        if signal is not None:
            signals.append(signal)
    if not signals:
        return None
    signals.sort(key=lambda row: row.confidence, reverse=True)
    return signals[0]


def force_practice_strategy(
    status: Any,
    inputs: dict[str, Any],
    asset_news: Any | None = None,
    *,
    preferred_family: str = "",
    source_queue_action: str = "",
) -> PracticeStrategySignal | None:
    mode = str(inputs.get("strategy_mode") or "").lower()
    if mode not in PRACTICE_MODES:
        return None
    requested = [str(x).upper() for x in inputs.get("requested_strategy_families") or [] if str(x).strip()]
    active_order = [
        SMALL_MOVE_FADE,
        BUY_UP_CONTINUATION,
        BUY_FADE,
        SELL_DOWN_CONTINUATION,
        MEAN_REVERSION_CHOP,
        VOL_BREAKOUT,
        BASIS_DISLOCATION,
        RELATIVE_STRENGTH,
        LIQUIDITY_SQUEEZE,
        NEWS_BREAKOUT,
    ]
    preferred = str(preferred_family or "").upper()
    order = [preferred] if preferred else []
    order.extend(requested)
    order.extend(active_order)
    seen: set[str] = set()
    ordered_ids = [sid for sid in order if sid and not (sid in seen or seen.add(sid))]
    strategies = {strategy.strategy_id: strategy for strategy in get_strategies_for_asset(str(getattr(status, "asset", "") or ""))}
    for sid in ordered_ids:
        strategy = strategies.get(sid)
        if strategy is None:
            continue
        signal = strategy.force_probe(status, inputs, asset_news, source_queue_action=source_queue_action)
        if signal is not None:
            return signal
    return None


def reset_strategy_debug() -> None:
    _DEBUG.clear()


def strategy_debug_snapshot() -> dict[str, dict[str, int]]:
    init_strategies()
    out = {sid: dict(counter) for sid, counter in _DEBUG.items()}
    for strategies in REGISTRY.values():
        for strategy in strategies:
            out.setdefault(strategy.strategy_id, {})
    return out
