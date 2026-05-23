from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ExitConfig:
    tp1_bps: float
    scale_out_fraction: float
    trail_bps: float
    min_hold_minutes: int
    max_hold_minutes: int
    min_profit_bps_for_score_exit: float
    allow_full_score_exit: bool = True
    allow_news_full_exit: bool = True


@dataclass
class TradeState:
    strategy_id: str
    asset: str
    venue: str
    bucket_session: str
    side: str
    entry_price: float
    entry_ts_utc: datetime
    initial_qty: float
    remaining_qty: float
    total_initial_notional: float

    stage: str = "stage1"
    trailing_anchor_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    has_trimmed_on_score: bool = False

    last_price: Optional[float] = None
    net_pnl_usd: float = 0.0
    net_pnl_bps: float = 0.0
    hold_minutes_actual: float = 0.0


@dataclass
class Scores:
    present_score: float
    score_threshold: float
    news_exit_signal: Optional[str] = None


@dataclass
class ExitDecision:
    action: str
    reason: Optional[str] = None
    scale_out_size: float = 0.0
    keep_size: float = 0.0


class ExitEngine:
    def __init__(self, exit_params: Dict[str, Any]) -> None:
        self.bucket_params = exit_params.get("bucket_params", {})
        self.family_defaults = exit_params.get("family_defaults", {})
        self.family_venue_defaults = exit_params.get("family_venue_defaults", {})

    def _resolve_config_key(
        self, strategy_id: str, asset: str, venue: str, bucket_session: str
    ) -> ExitConfig:
        strat = strategy_id.strip().upper()
        asset_u = asset.strip().upper()
        venue_u = venue.strip()
        session = bucket_session.strip()

        bucket_key = f"{strat}|{asset_u}|{venue_u}|{session}"
        if bucket_key in self.bucket_params:
            p = self.bucket_params[bucket_key]
            return ExitConfig(
                tp1_bps=p["tp1_bps"],
                scale_out_fraction=p["scale_out_fraction"],
                trail_bps=p["trail_bps"],
                min_hold_minutes=p["min_hold_minutes"],
                max_hold_minutes=p["max_hold_minutes"],
                min_profit_bps_for_score_exit=p["min_profit_bps_for_score_exit"],
                allow_full_score_exit=p.get("allow_full_score_exit", True),
                allow_news_full_exit=p.get("allow_news_full_exit", True),
            )

        venue_key = f"{strat}|{venue_u}"
        if venue_key in self.family_venue_defaults:
            p = self.family_venue_defaults[venue_key]
            return ExitConfig(
                tp1_bps=p["tp1_bps"],
                scale_out_fraction=p["scale_out_fraction"],
                trail_bps=p["trail_bps"],
                min_hold_minutes=p["min_hold_minutes"],
                max_hold_minutes=p["max_hold_minutes"],
                min_profit_bps_for_score_exit=p["min_profit_bps_for_score_exit"],
            )

        if strat in self.family_defaults:
            p = self.family_defaults[strat]
            return ExitConfig(
                tp1_bps=p["tp1_bps"],
                scale_out_fraction=p["scale_out_fraction"],
                trail_bps=p["trail_bps"],
                min_hold_minutes=p["min_hold_minutes"],
                max_hold_minutes=p["max_hold_minutes"],
                min_profit_bps_for_score_exit=p["min_profit_bps_for_score_exit"],
            )

        return ExitConfig(
            tp1_bps=10.0,
            scale_out_fraction=0.5,
            trail_bps=10.0,
            min_hold_minutes=10,
            max_hold_minutes=90,
            min_profit_bps_for_score_exit=5.0,
        )

    def evaluate_exit(
        self,
        trade: TradeState,
        last_price: float,
        now_ts_utc: datetime,
        scores: Scores,
    ) -> ExitDecision:
        cfg = self._resolve_config_key(
            trade.strategy_id,
            trade.asset,
            trade.venue,
            trade.bucket_session,
        )

        trade.last_price = last_price

        if trade.side == "buy":
            trade.net_pnl_usd = (last_price - trade.entry_price) * trade.remaining_qty
        else:
            trade.net_pnl_usd = (trade.entry_price - last_price) * trade.remaining_qty

        trade.net_pnl_bps = (
            trade.net_pnl_usd / max(trade.total_initial_notional, 1e-12)
        ) * 1e4
        trade.hold_minutes_actual = (
            now_ts_utc - trade.entry_ts_utc
        ).total_seconds() / 60.0

        if trade.trailing_anchor_price is None:
            trade.trailing_anchor_price = last_price
        else:
            if trade.side == "buy":
                trade.trailing_anchor_price = max(
                    trade.trailing_anchor_price, last_price
                )
            else:
                trade.trailing_anchor_price = min(
                    trade.trailing_anchor_price, last_price
                )

        if self._hit_hard_stop(trade, cfg):
            return ExitDecision(action="close", reason="hard_stop")

        if trade.stage == "stage1" and trade.net_pnl_bps >= cfg.tp1_bps:
            scale_fraction = cfg.scale_out_fraction
            scaled_size = trade.remaining_qty * scale_fraction
            keep_size = trade.remaining_qty - scaled_size
            trade.remaining_qty = keep_size
            trade.stage = "stage2"
            trade.trailing_stop_price = self._breakeven_stop(trade, cfg)
            return ExitDecision(
                action="scale_out",
                reason="tp1_partial",
                scale_out_size=scaled_size,
                keep_size=keep_size,
            )

        if trade.stage == "stage2":
            self._update_trailing_stop(trade, cfg)
            if self._hit_trailing_stop(trade, last_price):
                return ExitDecision(action="close", reason="trailing_stop")

        score_degraded = scores.present_score < scores.score_threshold
        news_exit = scores.news_exit_signal is not None
        profitable = trade.net_pnl_bps > 0.0

        if score_degraded or news_exit:
            if news_exit and not profitable:
                return ExitDecision(action="close", reason=scores.news_exit_signal)

            if profitable and (
                trade.net_pnl_bps < cfg.min_profit_bps_for_score_exit
                or trade.hold_minutes_actual < cfg.min_hold_minutes
            ):
                if not trade.has_trimmed_on_score:
                    trim_fraction = 0.25
                    scaled_size = trade.remaining_qty * trim_fraction
                    keep_size = trade.remaining_qty - scaled_size
                    trade.remaining_qty = keep_size
                    trade.has_trimmed_on_score = True
                    self._tighten_trailing_stop(trade, cfg)
                    return ExitDecision(
                        action="scale_out",
                        reason="score_or_news_early_risk_trim",
                        scale_out_size=scaled_size,
                        keep_size=keep_size,
                    )
                self._tighten_trailing_stop(trade, cfg)
                return ExitDecision(action="hold", reason=None)

            if profitable and (
                trade.net_pnl_bps >= cfg.min_profit_bps_for_score_exit
                and trade.hold_minutes_actual >= cfg.min_hold_minutes
            ):
                if trade.stage == "stage2":
                    self._tighten_trailing_stop(trade, cfg, aggressive=True)
                    if self._hit_trailing_stop(trade, last_price):
                        reason = (
                            scores.news_exit_signal
                            if news_exit
                            else "present_score_degraded"
                        )
                        return ExitDecision(action="close", reason=reason)
                    return ExitDecision(action="hold", reason=None)
                reason = (
                    scores.news_exit_signal
                    if news_exit
                    else "present_score_degraded"
                )
                return ExitDecision(action="close", reason=reason)

        if trade.hold_minutes_actual >= cfg.max_hold_minutes:
            if not profitable:
                return ExitDecision(
                    action="close", reason="max_hold_time_no_profit"
                )
            if trade.stage == "stage2":
                self._tighten_trailing_stop(trade, cfg, aggressive=True)
                if self._hit_trailing_stop(trade, last_price):
                    return ExitDecision(
                        action="close", reason="max_hold_trailing_stop"
                    )
                return ExitDecision(action="hold", reason=None)
            return ExitDecision(action="close", reason="max_hold_time_flat")

        return ExitDecision(action="hold", reason=None)

    def _hit_hard_stop(self, trade: TradeState, cfg: ExitConfig) -> bool:
        return False

    def _breakeven_stop(self, trade: TradeState, cfg: ExitConfig) -> float:
        if trade.side == "buy":
            return trade.entry_price * (1.0 + 2.0 / 1e4)
        return trade.entry_price * (1.0 - 2.0 / 1e4)

    def _update_trailing_stop(self, trade: TradeState, cfg: ExitConfig) -> None:
        if trade.trailing_anchor_price is None:
            return
        if trade.side == "buy":
            trade.trailing_stop_price = trade.trailing_anchor_price * (
                1.0 - cfg.trail_bps / 1e4
            )
        else:
            trade.trailing_stop_price = trade.trailing_anchor_price * (
                1.0 + cfg.trail_bps / 1e4
            )

    def _tighten_trailing_stop(
        self, trade: TradeState, cfg: ExitConfig, aggressive: bool = False
    ) -> None:
        factor = 0.5 if aggressive else 0.75
        tightened_cfg = ExitConfig(
            tp1_bps=cfg.tp1_bps,
            scale_out_fraction=cfg.scale_out_fraction,
            trail_bps=cfg.trail_bps * factor,
            min_hold_minutes=cfg.min_hold_minutes,
            max_hold_minutes=cfg.max_hold_minutes,
            min_profit_bps_for_score_exit=cfg.min_profit_bps_for_score_exit,
            allow_full_score_exit=cfg.allow_full_score_exit,
            allow_news_full_exit=cfg.allow_news_full_exit,
        )
        self._update_trailing_stop(trade, tightened_cfg)

    def _hit_trailing_stop(self, trade: TradeState, last_price: float) -> bool:
        if trade.trailing_stop_price is None:
            return False
        if trade.side == "buy":
            return last_price <= trade.trailing_stop_price
        return last_price >= trade.trailing_stop_price
