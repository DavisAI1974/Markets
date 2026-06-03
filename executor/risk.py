"""
risk.py — risk gates with per-(asset, venue) hierarchical config.

Each gate is a pure function: takes (signal, config, recent_trades) and returns
either ALLOW or a deny reason. The executor runs all gates in order; first deny
short-circuits.

Config hierarchy: default -> per-asset overrides -> per-(asset, venue) overrides.
At lookup time for a specific (asset, venue), we merge top-down so the most-
specific value wins. This lets the same executor handle BTC on Coinbase
differently from BTC on Kraken or ETH on Coinbase.

Backwards compatible: the old flat config (single `"risk"` block) still works
- LayeredRiskConfig.load() detects shape and routes accordingly.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any


@dataclass
class RiskConfig:
    """Per-(asset, venue) trading constraints. Resolved from layered config."""

    asset_whitelist: list[str] = field(default_factory=list)
    venue_whitelist: list[str] = field(default_factory=list)
    regime_whitelist: list[str] = field(default_factory=lambda: [
        "WHALE_UP", "WHALE_DOWN", "HERD_UP", "HERD_DOWN",
    ])
    min_confidence: float = 0.6
    position_size_usd: float = 100.0
    max_trades_per_day: int = 6
    max_daily_loss_usd: float = 50.0
    max_position_usd: float = 500.0
    stop_loss_bps: float = 80.0
    take_profit_bps: float = 60.0
    max_hold_minutes: int = 35
    require_cross_venue_confirm: bool = False
    simulated_fee_bps: float = 25.0    # per-venue; Coinbase taker default
    # --- OD-native sizing (opt-in; falls back to fixed position_size_usd when off) ---
    od_sizing: bool = False            # size from OD confidence x measured edge (odcore.sizing)
    position_floor_usd: float = 0.0    # below this OD notional, size to 0 (don't trade)
    # --- circuit breaker (0 disables) ---
    max_consecutive_losses: int = 0    # deny after this many trailing closed losers on a source

    @classmethod
    def from_dict(cls, d: dict) -> "RiskConfig":
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid})


@dataclass
class LayeredRiskConfig:
    """Merge order at lookup: default <- per_asset[asset] <- per_source[(asset, venue)]."""

    default: RiskConfig = field(default_factory=RiskConfig)
    per_asset: dict[str, dict] = field(default_factory=dict)
    per_source: dict[str, dict] = field(default_factory=dict)   # key "ASSET.VENUE"

    def for_source(self, asset: str, venue: str) -> RiskConfig:
        """Return resolved RiskConfig for this (asset, venue)."""
        merged = {f.name: getattr(self.default, f.name) for f in fields(RiskConfig)}
        if asset in self.per_asset:
            merged.update(self.per_asset[asset])
        key = f"{asset}.{venue}"
        if key in self.per_source:
            merged.update(self.per_source[key])
        return RiskConfig.from_dict(merged)

    @classmethod
    def load(cls, path: str) -> "LayeredRiskConfig":
        """Load from JSON, autodetecting flat vs layered shape."""
        with open(path) as f:
            raw = json.load(f)
        risk_block = raw.get("risk", {})
        if not isinstance(risk_block, dict):
            return cls()
        # Layered shape: has "default" key
        if "default" in risk_block or "per_asset" in risk_block or "per_source" in risk_block:
            default_d = risk_block.get("default", {})
            return cls(
                default=RiskConfig.from_dict(default_d),
                per_asset=risk_block.get("per_asset", {}),
                per_source=risk_block.get("per_source", {}),
            )
        # Flat shape (backwards compatible): treat whole block as the default
        return cls(default=RiskConfig.from_dict(risk_block))


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
        return GateResult(False, f"cross-venue mult {cvm:.2f} not > 1.0; require_cross_venue_confirm on")
    return GateResult(True)


def _today_key_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def gate_daily_trade_count(signal: dict, cfg: RiskConfig, recent: list[dict]) -> GateResult:
    today = _today_key_utc()
    # Per-(asset, venue) trade count if we want max-trades-per-source enforcement
    src_today = [t for t in recent
                 if t.get("date_utc") == today
                 and t.get("asset") == signal["asset"]
                 and t.get("venue") == signal["venue"]]
    if len(src_today) >= cfg.max_trades_per_day:
        return GateResult(False, f"already {len(src_today)} trades today on "
                                  f"{signal['asset']}/{signal['venue']} (max {cfg.max_trades_per_day})")
    return GateResult(True)


def gate_daily_loss(signal: dict, cfg: RiskConfig, recent: list[dict]) -> GateResult:
    today = _today_key_utc()
    today_pnl = sum(float(t.get("realized_pnl_usd", 0.0))
                    for t in recent
                    if t.get("date_utc") == today
                    and t.get("asset") == signal["asset"]
                    and t.get("venue") == signal["venue"]
                    and t.get("status") == "closed")
    if today_pnl <= -cfg.max_daily_loss_usd:
        return GateResult(False, f"today PnL ${today_pnl:.2f} <= -${cfg.max_daily_loss_usd:.2f} "
                                  f"on {signal['asset']}/{signal['venue']}")
    return GateResult(True)


def gate_circuit_breaker(signal: dict, cfg: RiskConfig, recent: list[dict]) -> GateResult:
    """Trip after `max_consecutive_losses` trailing closed losing trades on this source.

    A losing-streak guard independent of the calendar-day loss cap: it halts a source that
    is bleeding regardless of the daily total. 0 disables the breaker.
    """
    if cfg.max_consecutive_losses <= 0:
        return GateResult(True)
    closed = [t for t in recent
              if t.get("status") == "closed"
              and t.get("asset") == signal["asset"]
              and t.get("venue") == signal["venue"]]
    # recent is append-ordered; count trailing losers
    streak = 0
    for t in reversed(closed):
        if float(t.get("realized_pnl_usd", 0.0)) < 0:
            streak += 1
        else:
            break
    if streak >= cfg.max_consecutive_losses:
        return GateResult(False, f"circuit breaker: {streak} consecutive losses on "
                                  f"{signal['asset']}/{signal['venue']} (max {cfg.max_consecutive_losses})")
    return GateResult(True)


ALL_GATES = [
    gate_asset_whitelist,
    gate_venue_whitelist,
    gate_regime_whitelist,
    gate_confidence,
    gate_cross_venue_confirm,
    gate_daily_trade_count,
    gate_daily_loss,
    gate_circuit_breaker,
]


def evaluate(signal: dict, layered: LayeredRiskConfig | RiskConfig, recent: list[dict]) -> GateResult:
    """Run all gates; return first deny or final ALLOW.

    Accepts either a RiskConfig (legacy) or LayeredRiskConfig (new).
    With layered, resolves the right config for the signal's (asset, venue).
    """
    if isinstance(layered, LayeredRiskConfig):
        cfg = layered.for_source(signal["asset"], signal["venue"])
    else:
        cfg = layered
    for gate in ALL_GATES:
        r = gate(signal, cfg, recent)
        if not r.allow:
            return r
    return GateResult(True, "all gates passed")
