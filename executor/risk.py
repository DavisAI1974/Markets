"""
risk.py — risk gates for the executor.

Each gate is a pure function: takes (signal, config, recent_trades) and returns
either ALLOW or a deny reason. The executor runs all gates in order; first deny
short-circuits.

Philosophy: every gate explains *why* it denied. Friends should be able to
debug "why didn't I trade this?" by reading the deny reasons.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RiskConfig:
    """Per-friend trading constraints. Loaded from JSON config file."""

    # Asset whitelist: only signals for these assets are eligible.
    # Empty list = allow all.
    asset_whitelist: list[str] = field(default_factory=list)

    # Venue whitelist: only signals from these venues are eligible.
    venue_whitelist: list[str] = field(default_factory=list)

    # Regime whitelist: which regime classes are tradeable.
    # Default: only the actionable ones; explicitly excludes EQUILIBRIUM_EXTREME_DEMO
    # to prevent demo signals from triggering paper trades automatically.
    regime_whitelist: list[str] = field(default_factory=lambda: [
        "WHALE_UP", "WHALE_DOWN", "HERD_UP", "HERD_DOWN",
    ])

    # Confidence floor: skip signals below this.
    min_confidence: float = 0.6

    # Position sizing: fixed USD notional per trade.
    position_size_usd: float = 100.0

    # Daily limits.
    max_trades_per_day: int = 6
    max_daily_loss_usd: float = 50.0

    # Per-trade risk limits.
    max_position_usd: float = 500.0     # cap on single position
    stop_loss_bps: float = 80.0         # exit if down this much from entry
    take_profit_bps: float = 60.0       # exit if up this much
    max_hold_minutes: int = 35          # exit unconditionally after this long

    # Cross-venue requirement: only trade if cross-venue confirms.
    require_cross_venue_confirm: bool = False


@dataclass
class GateResult:
    allow: bool
    reason: str = ""


def gate_asset_whitelist(signal: dict, cfg: RiskConfig, _recent) -> GateResult:
    if cfg.asset_whitelist and signal["asset"] not in cfg.asset_whitelist:
        return GateResult(False, f"asset {signal['asset']} not in whitelist {cfg.asset_whitelist}")
    return GateResult(True)


def gate_venue_whitelist(signal: dict, cfg: RiskConfig, _recent) -> GateResult:
    if cfg.venue_whitelist and signal["venue"] not in cfg.venue_whitelist:
        return GateResult(False, f"venue {signal['venue']} not in whitelist {cfg.venue_whitelist}")
    return GateResult(True)


def gate_regime_whitelist(signal: dict, cfg: RiskConfig, _recent) -> GateResult:
    if signal["regime"] not in cfg.regime_whitelist:
        return GateResult(False, f"regime {signal['regime']} not in whitelist {cfg.regime_whitelist}")
    return GateResult(True)


def gate_confidence(signal: dict, cfg: RiskConfig, _recent) -> GateResult:
    conf = signal.get("adjusted_confidence", signal.get("confidence", 0.0))
    if conf < cfg.min_confidence:
        return GateResult(False, f"confidence {conf:.2f} below floor {cfg.min_confidence}")
    return GateResult(True)


def gate_cross_venue_confirm(signal: dict, cfg: RiskConfig, _recent) -> GateResult:
    if not cfg.require_cross_venue_confirm:
        return GateResult(True)
    cvm = signal.get("cross_venue_multiplier", 1.0)
    if cvm <= 1.0:
        return GateResult(False, f"cross-venue multiplier {cvm:.2f} not > 1.0; require_cross_venue_confirm is on")
    return GateResult(True)


def _today_key_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def gate_daily_trade_count(_signal, cfg: RiskConfig, recent: list[dict]) -> GateResult:
    today = _today_key_utc()
    today_trades = [t for t in recent if t.get("date_utc") == today]
    if len(today_trades) >= cfg.max_trades_per_day:
        return GateResult(False, f"already {len(today_trades)} trades today (max {cfg.max_trades_per_day})")
    return GateResult(True)


def gate_daily_loss(_signal, cfg: RiskConfig, recent: list[dict]) -> GateResult:
    today = _today_key_utc()
    today_pnl = sum(float(t.get("realized_pnl_usd", 0.0))
                    for t in recent if t.get("date_utc") == today and t.get("status") == "closed")
    if today_pnl <= -cfg.max_daily_loss_usd:
        return GateResult(False, f"today PnL ${today_pnl:.2f} <= -${cfg.max_daily_loss_usd:.2f} (daily loss limit)")
    return GateResult(True)


# Ordered list of gates. First deny short-circuits.
ALL_GATES = [
    gate_asset_whitelist,
    gate_venue_whitelist,
    gate_regime_whitelist,
    gate_confidence,
    gate_cross_venue_confirm,
    gate_daily_trade_count,
    gate_daily_loss,
]


def evaluate(signal: dict, cfg: RiskConfig, recent: list[dict]) -> GateResult:
    """Run all gates; return first deny or final ALLOW."""
    for gate in ALL_GATES:
        r = gate(signal, cfg, recent)
        if not r.allow:
            return r
    return GateResult(True, "all gates passed")
