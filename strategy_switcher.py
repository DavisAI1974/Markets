from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


NO_TRADE = "NO_TRADE"
PRESSURE_CONTINUATION = "PRESSURE_CONTINUATION"
NEWS_SHOCK_EXIT_OR_HEDGE = "NEWS_SHOCK_EXIT_OR_HEDGE"
NEWS_CONFIRMED_DIRECTIONAL = "NEWS_CONFIRMED_DIRECTIONAL"
NEWS_BREAKOUT = "NEWS_BREAKOUT"
LIQUIDATION_SWEEP_FADE = "LIQUIDATION_SWEEP_FADE"
SMALL_MOVE_FADE = "SMALL_MOVE_FADE"
BUY_UP_CONTINUATION = "BUY_UP_CONTINUATION"
BUY_FADE = "BUY_FADE"
SELL_DOWN_CONTINUATION = "SELL_DOWN_CONTINUATION"
LIQUIDITY_SQUEEZE = "LIQUIDITY_SQUEEZE"
VOL_BREAKOUT = "VOL_BREAKOUT"
BASIS_DISLOCATION = "BASIS_DISLOCATION"
RELATIVE_STRENGTH = "RELATIVE_STRENGTH"
BREAKOUT_PULLBACK = "BREAKOUT_PULLBACK"
MEAN_REVERSION_CHOP = "MEAN_REVERSION_CHOP"

LEARNING_MODES = {"practice", "explore", "autoresearch", "learning", "live_paper"}
ACTIVE_PRACTICE_FAMILIES = (
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
)
EVOLUTION_QUEUE_PATH = Path(__file__).resolve().parent / "research" / "strategy_evolution" / "_queue.json"
EVOLUTION_ROUTING_PATH = Path(__file__).resolve().parent / "research" / "strategy_evolution" / "_routing.json"
EVOLUTION_STUDY_PATH = Path(__file__).resolve().parent / "research" / "strategy_evolution" / "_study_list.json"
HINDSIGHT_QUEUE_PATH = Path(__file__).resolve().parent / "research" / "strategy_evolution" / "_hindsight_missed_winner_queue.json"
HINDSIGHT_AUDIT_ROWS_PATH = Path(__file__).resolve().parent / "research" / "strategy_evolution" / "live_mock_replay" / "live_hindsight_missed_winner_audit_rows.csv"
LIVE_FAMILY_KILLLIST_PATH = Path(__file__).resolve().parent / "research" / "strategy_evolution" / "_live_family_killlist.json"
MIN_CONTEXT_FAMILY_SAMPLES_BEFORE_ROUTING = 3
_ORACLE_AUDIT_CONTEXT_CACHE: dict[str, Any] = {"mtime_ns": None, "rows": []}
_ORACLE_AUDIT_STRATEGY_CONTEXT_CACHE: dict[str, Any] = {"mtime_ns": None, "rows": []}

DISABLED_STRATEGIES = {
    PRESSURE_CONTINUATION,
}


STRATEGY_LABELS = {
    NO_TRADE: "No trade",
    NEWS_SHOCK_EXIT_OR_HEDGE: "News shock exit or hedge",
    NEWS_CONFIRMED_DIRECTIONAL: "News-confirmed directional",
    NEWS_BREAKOUT: "News breakout",
    LIQUIDATION_SWEEP_FADE: "Liquidation sweep fade",
    SMALL_MOVE_FADE: "Small move fade",
    BUY_UP_CONTINUATION: "Buy up continuation",
    BUY_FADE: "Buy fade",
    SELL_DOWN_CONTINUATION: "Sell down continuation",
    LIQUIDITY_SQUEEZE: "Liquidity squeeze fade",
    VOL_BREAKOUT: "Volume-confirmed breakout",
    BASIS_DISLOCATION: "Basis dislocation",
    RELATIVE_STRENGTH: "Relative strength",
    BREAKOUT_PULLBACK: "Breakout pullback",
    MEAN_REVERSION_CHOP: "Mean reversion chop",
}


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    label: str
    allowed_sides: tuple[str, ...] = ("buy", "sell")
    allowed_venues: tuple[str, ...] = ("Coinbase", "Kraken", "Bybit")
    min_present_score: int = 55
    notional_scale_multiplier: float = 1.0
    hold_minutes: int = 10
    stop_loss_bps: float = 10.0
    take_profit_bps: float = 18.0
    exit_score_drop: int = 12
    requires_market_confirmation: bool = True


STRATEGY_SPECS: dict[str, StrategySpec] = {
    NO_TRADE: StrategySpec(
        strategy_id=NO_TRADE,
        label=STRATEGY_LABELS[NO_TRADE],
        min_present_score=101,
        notional_scale_multiplier=0.0,
        hold_minutes=0,
    ),
    NEWS_SHOCK_EXIT_OR_HEDGE: StrategySpec(
        strategy_id=NEWS_SHOCK_EXIT_OR_HEDGE,
        label=STRATEGY_LABELS[NEWS_SHOCK_EXIT_OR_HEDGE],
        min_present_score=45,
        notional_scale_multiplier=0.50,
        hold_minutes=8,
        stop_loss_bps=8.0,
        take_profit_bps=14.0,
        exit_score_drop=8,
        requires_market_confirmation=False,
    ),
    NEWS_CONFIRMED_DIRECTIONAL: StrategySpec(
        strategy_id=NEWS_CONFIRMED_DIRECTIONAL,
        label=STRATEGY_LABELS[NEWS_CONFIRMED_DIRECTIONAL],
        min_present_score=65,
        notional_scale_multiplier=0.60,
        hold_minutes=12,
        stop_loss_bps=10.0,
        take_profit_bps=20.0,
        exit_score_drop=12,
    ),
    NEWS_BREAKOUT: StrategySpec(
        strategy_id=NEWS_BREAKOUT,
        label=STRATEGY_LABELS[NEWS_BREAKOUT],
        min_present_score=45,
        notional_scale_multiplier=0.50,
        hold_minutes=12,
        stop_loss_bps=10.0,
        take_profit_bps=20.0,
        exit_score_drop=10,
    ),
    LIQUIDATION_SWEEP_FADE: StrategySpec(
        strategy_id=LIQUIDATION_SWEEP_FADE,
        label=STRATEGY_LABELS[LIQUIDATION_SWEEP_FADE],
        min_present_score=60,
        notional_scale_multiplier=0.35,
        hold_minutes=6,
        stop_loss_bps=7.0,
        take_profit_bps=12.0,
        exit_score_drop=8,
    ),
    SMALL_MOVE_FADE: StrategySpec(
        strategy_id=SMALL_MOVE_FADE,
        label=STRATEGY_LABELS[SMALL_MOVE_FADE],
        allowed_sides=("sell",),
        min_present_score=35,
        notional_scale_multiplier=0.25,
        hold_minutes=8,
        stop_loss_bps=6.0,
        take_profit_bps=12.0,
        exit_score_drop=7,
        requires_market_confirmation=False,
    ),
    BUY_UP_CONTINUATION: StrategySpec(
        strategy_id=BUY_UP_CONTINUATION,
        label=STRATEGY_LABELS[BUY_UP_CONTINUATION],
        allowed_sides=("buy",),
        min_present_score=35,
        notional_scale_multiplier=0.25,
        hold_minutes=20,
        stop_loss_bps=8.0,
        take_profit_bps=16.0,
        exit_score_drop=8,
        requires_market_confirmation=False,
    ),
    BUY_FADE: StrategySpec(
        strategy_id=BUY_FADE,
        label=STRATEGY_LABELS[BUY_FADE],
        allowed_sides=("buy",),
        min_present_score=35,
        notional_scale_multiplier=0.20,
        hold_minutes=8,
        stop_loss_bps=7.0,
        take_profit_bps=12.0,
        exit_score_drop=7,
        requires_market_confirmation=False,
    ),
    SELL_DOWN_CONTINUATION: StrategySpec(
        strategy_id=SELL_DOWN_CONTINUATION,
        label=STRATEGY_LABELS[SELL_DOWN_CONTINUATION],
        allowed_sides=("sell",),
        min_present_score=35,
        notional_scale_multiplier=0.20,
        hold_minutes=8,
        stop_loss_bps=8.0,
        take_profit_bps=16.0,
        exit_score_drop=8,
        requires_market_confirmation=False,
    ),
    LIQUIDITY_SQUEEZE: StrategySpec(
        strategy_id=LIQUIDITY_SQUEEZE,
        label=STRATEGY_LABELS[LIQUIDITY_SQUEEZE],
        min_present_score=35,
        notional_scale_multiplier=0.30,
        hold_minutes=6,
        stop_loss_bps=7.0,
        take_profit_bps=12.0,
        exit_score_drop=7,
    ),
    VOL_BREAKOUT: StrategySpec(
        strategy_id=VOL_BREAKOUT,
        label=STRATEGY_LABELS[VOL_BREAKOUT],
        min_present_score=45,
        notional_scale_multiplier=0.35,
        hold_minutes=8,
        stop_loss_bps=8.0,
        take_profit_bps=16.0,
        exit_score_drop=8,
    ),
    BASIS_DISLOCATION: StrategySpec(
        strategy_id=BASIS_DISLOCATION,
        label=STRATEGY_LABELS[BASIS_DISLOCATION],
        min_present_score=35,
        notional_scale_multiplier=0.25,
        hold_minutes=8,
        stop_loss_bps=8.0,
        take_profit_bps=16.0,
        exit_score_drop=8,
    ),
    RELATIVE_STRENGTH: StrategySpec(
        strategy_id=RELATIVE_STRENGTH,
        label=STRATEGY_LABELS[RELATIVE_STRENGTH],
        min_present_score=35,
        notional_scale_multiplier=0.25,
        hold_minutes=8,
        stop_loss_bps=8.0,
        take_profit_bps=16.0,
        exit_score_drop=8,
    ),
    BREAKOUT_PULLBACK: StrategySpec(
        strategy_id=BREAKOUT_PULLBACK,
        label=STRATEGY_LABELS[BREAKOUT_PULLBACK],
        min_present_score=70,
        notional_scale_multiplier=0.70,
        hold_minutes=12,
        stop_loss_bps=10.0,
        take_profit_bps=22.0,
        exit_score_drop=12,
    ),
    MEAN_REVERSION_CHOP: StrategySpec(
        strategy_id=MEAN_REVERSION_CHOP,
        label=STRATEGY_LABELS[MEAN_REVERSION_CHOP],
        min_present_score=40,
        notional_scale_multiplier=0.25,
        hold_minutes=5,
        stop_loss_bps=6.0,
        take_profit_bps=9.0,
        exit_score_drop=6,
    ),
}

TREND_FOLLOW_THROUGH_REGIMES = {
    "HERD_UP",
    "HERD_DOWN",
    "WHALE_UP",
    "WHALE_DOWN",
    "WHALE_NASCENT_UP",
    "WHALE_NASCENT_DOWN",
}

LEGACY_STRATEGY_ALIASES = {
    "MOMENTUM": {BREAKOUT_PULLBACK},
    "CONFIRMED_FOLLOW": {NEWS_CONFIRMED_DIRECTIONAL, BREAKOUT_PULLBACK},
    "EARLY_PROBE": {MEAN_REVERSION_CHOP},
    "NEWS_ONLY_ENTRY": {NEWS_BREAKOUT},
    "HIGH_LEVERAGE_SCALP": set(),
}


def normalize_strategy_id(strategy_id: str) -> str:
    return str(strategy_id or NO_TRADE).strip().upper() or NO_TRADE


def strategy_family_health(strategy_id: str, stats: dict[str, Any] | None) -> dict[str, Any]:
    sid = normalize_strategy_id(strategy_id)
    stats = dict(stats or {})
    trades = int(stats.get("trades") or stats.get("n_trades") or 0)
    win_rate = stats.get("win_rate")
    sharpe = stats.get("sharpe")
    win = float(win_rate) if win_rate is not None else None
    shp = float(sharpe) if sharpe is not None else None
    state = "ok"
    reasons: list[str] = []
    if trades < 50:
        state = "learning"
        reasons.append(f"{sid} has {trades} family trades; learning until 50+")
    elif win is not None and shp is not None and (win < 0.45 or shp < 0.8):
        state = "dead"
        reasons.append(f"{sid} family stats below survival floor")
    return {
        "strategy_id": sid,
        "state": state,
        "stats": {
            "trades": trades,
            "win_rate": win,
            "sharpe": shp,
        },
        "reasons": reasons,
    }


def continuation_regime_ok(regime: str, current_bps: float, recent_bps: float) -> bool:
    return str(regime or "") in TREND_FOLLOW_THROUGH_REGIMES and current_bps > 0.0 and recent_bps > 0.0


@dataclass
class StrategyDecision:
    strategy_id: str = NO_TRADE
    label: str = STRATEGY_LABELS[NO_TRADE]
    confidence: float = 0.0
    side_override: str = ""
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    spec: StrategySpec = STRATEGY_SPECS[NO_TRADE]
    forced: bool = False
    variant_id: str = ""
    risk_tags: list[str] = field(default_factory=list)
    handoff_hint: str = ""
    source_queue_action: str = ""

    def to_option_fields(self) -> dict[str, Any]:
        return {
            "trade_strategy_id": self.strategy_id,
            "trade_strategy_label": self.label,
            "trade_strategy_confidence": round(float(self.confidence), 4),
            "trade_strategy_side_override": self.side_override,
            "trade_strategy_reasons": list(self.reasons[:5]),
            "trade_strategy_blockers": list(dict.fromkeys(self.blockers))[:5],
            "trade_strategy_forced": bool(self.forced),
            "trade_strategy_variant_id": self.variant_id,
            "trade_strategy_risk_tags": list(dict.fromkeys(self.risk_tags))[:8],
            "trade_strategy_handoff_hint": self.handoff_hint,
            "trade_strategy_source_queue_action": self.source_queue_action,
        }


def _side_bias(side: str) -> str:
    return "BULLISH" if side == "buy" else "BEARISH" if side == "sell" else "UNKNOWN"


def _opposite_side(side: str) -> str:
    return "sell" if side == "buy" else "buy" if side == "sell" else ""


def _news_side(value: Any) -> str:
    text = str(value or "").upper()
    if text == "BULLISH":
        return "buy"
    if text == "BEARISH":
        return "sell"
    return ""


def _starter_actions(asset_news: Any) -> set[str]:
    return {str(action).upper() for action in getattr(asset_news, "starter_actions", []) or []}


def _news_allows_strategy(asset_news: Any, strategy_id: str) -> tuple[bool, str]:
    if strategy_id in DISABLED_STRATEGIES:
        return False, f"{strategy_id} is disabled after negative evidence"
    raw_allowed = [str(x).upper() for x in getattr(asset_news, "allowed_strategies", []) or []]
    raw_disabled = [str(x).upper() for x in getattr(asset_news, "disabled_strategies", []) or []]
    allowed = set(raw_allowed)
    disabled = set(raw_disabled)
    for item in raw_allowed:
        allowed.update(LEGACY_STRATEGY_ALIASES.get(item, set()))
    for item in raw_disabled:
        disabled.update(LEGACY_STRATEGY_ALIASES.get(item, set()))
    if strategy_id in disabled:
        return False, f"Daily news disabled {strategy_id}"
    if allowed and strategy_id not in allowed:
        return False, f"Daily news allowed only {', '.join(sorted(allowed)[:4])}"
    return True, ""


def _queued_practice_family(requested: set[str] | None = None) -> tuple[str, str]:
    requested = requested or set()
    try:
        payload = json.loads(EVOLUTION_QUEUE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    for row in payload.get("items") or []:
        family = normalize_strategy_id(str(row.get("family") or ""))
        if family not in ACTIVE_PRACTICE_FAMILIES:
            continue
        if requested and family not in requested:
            continue
        return family, str(row.get("action") or "")
    for family in ACTIVE_PRACTICE_FAMILIES:
        if not requested or family in requested:
            return family, "default_active_order"
    return "", ""


def _route_family_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _route_side_for_family(family: str, pressure_side: str) -> str:
    family = normalize_strategy_id(family)
    if family == SMALL_MOVE_FADE:
        return "sell"
    if family in {BUY_UP_CONTINUATION, BUY_FADE}:
        return "buy"
    if family == SELL_DOWN_CONTINUATION:
        return "sell"
    if family in {MEAN_REVERSION_CHOP, LIQUIDITY_SQUEEZE}:
        return _opposite_side(pressure_side) or pressure_side
    return pressure_side


def _context_route_key(family: str, status: Any, inputs: dict[str, Any], side: str) -> str:
    asset = str(getattr(status, "asset", "") or "").upper()
    venue = str(getattr(status, "venue", "") or "").lower()
    session = str(inputs.get("bucket_session") or "").lower()
    route_side = _route_side_for_family(family, side)
    return "|".join([_route_family_name(family), asset, venue, route_side, session])


def _context_key_for_family(family: str, status: Any, inputs: dict[str, Any], side: str) -> str:
    asset = str(getattr(status, "asset", "") or "").upper()
    venue = str(getattr(status, "venue", "") or "").lower()
    session = str(inputs.get("bucket_session") or "").lower()
    route_side = _route_side_for_family(family, side)
    return "|".join([asset, venue, route_side, session])


def _promoted_contexts() -> set[str]:
    try:
        payload = json.loads(EVOLUTION_STUDY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        str(row.get("context") or "").strip()
        for row in payload.get("promoted_contexts") or []
        if str(row.get("context") or "").strip()
    }


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _oracle_audit_no_side_contexts() -> list[dict[str, Any]]:
    global _ORACLE_AUDIT_CONTEXT_CACHE
    try:
        stat = HINDSIGHT_AUDIT_ROWS_PATH.stat()
    except OSError:
        return []
    if _ORACLE_AUDIT_CONTEXT_CACHE.get("mtime_ns") == stat.st_mtime_ns:
        return list(_ORACLE_AUDIT_CONTEXT_CACHE.get("rows") or [])

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        with HINDSIGHT_AUDIT_ROWS_PATH.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("strategy_id") or "") != "NO_STRATEGY":
                    continue
                if str(row.get("blocker_reason") or "") != "no_trade_side":
                    continue
                if str(row.get("miss_type") or "") != "missed_entry":
                    continue
                if str(row.get("is_oracle_winner_after_fees") or "").lower() not in {"true", "1", "yes"}:
                    continue
                context = str(row.get("context_key") or "")
                parts = context.split("|")
                if len(parts) != 5 or parts[0] != "NO_STRATEGY":
                    continue
                family = normalize_strategy_id(str(row.get("pattern_family") or ""))
                if family not in ACTIVE_PRACTICE_FAMILIES:
                    continue
                bucket = grouped.setdefault(
                    (context, family),
                    {
                        "context_key": context,
                        "family": family,
                        "missed_entry_rows": 0,
                        "oracle_net_pnl_usd": 0.0,
                        "oracle_incremental_vs_actual_usd": 0.0,
                        "oracle_horizons_minutes": {},
                        "experiment_id": f"oracle_audit__{context.lower().replace('|', '_')}__{family.lower()}",
                        "source": "live_hindsight_missed_winner_audit_rows",
                    },
                )
                bucket["missed_entry_rows"] += 1
                bucket["oracle_net_pnl_usd"] += _safe_float(row.get("oracle_net_pnl_usd"))
                bucket["oracle_incremental_vs_actual_usd"] += _safe_float(row.get("oracle_incremental_vs_actual_usd") or row.get("oracle_net_pnl_usd"))
                horizon = str(_safe_int(row.get("oracle_horizon_minutes")))
                bucket["oracle_horizons_minutes"][horizon] = bucket["oracle_horizons_minutes"].get(horizon, 0) + 1
    except (OSError, csv.Error):
        return []

    rows = list(grouped.values())
    _ORACLE_AUDIT_CONTEXT_CACHE = {"mtime_ns": stat.st_mtime_ns, "rows": rows}
    return list(rows)


def _oracle_row_matches_no_side_context(row: dict[str, Any], status: Any, inputs: dict[str, Any]) -> bool:
    context = str(row.get("context_key") or "")
    parts = context.split("|")
    if len(parts) != 5 or parts[0] != "NO_STRATEGY":
        return False
    _, row_asset, row_venue, row_side, row_session = parts
    side = row_side.lower()
    if side not in {"buy", "sell"}:
        return False
    asset = str(getattr(status, "asset", "") or "").upper()
    venue = str(getattr(status, "venue", "") or "").lower()
    session = str(inputs.get("bucket_session") or "").lower()
    if row_asset.upper() != asset or row_venue.lower() != venue or row_session.lower() != session:
        return False
    family = normalize_strategy_id(str(row.get("family") or ""))
    if family not in ACTIVE_PRACTICE_FAMILIES:
        return False
    if _safe_int(row.get("missed_entry_rows")) < 10:
        return False
    if _safe_float(row.get("oracle_incremental_vs_actual_usd") or row.get("oracle_net_pnl_usd")) <= 50.0:
        return False
    return not _family_kill_reason(family, status, inputs, side)


def _oracle_audit_strategy_contexts() -> list[dict[str, Any]]:
    global _ORACLE_AUDIT_STRATEGY_CONTEXT_CACHE
    try:
        stat = HINDSIGHT_AUDIT_ROWS_PATH.stat()
    except OSError:
        return []
    if _ORACLE_AUDIT_STRATEGY_CONTEXT_CACHE.get("mtime_ns") == stat.st_mtime_ns:
        return list(_ORACLE_AUDIT_STRATEGY_CONTEXT_CACHE.get("rows") or [])

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        with HINDSIGHT_AUDIT_ROWS_PATH.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("is_oracle_winner_after_fees") or "").lower() not in {"true", "1", "yes"}:
                    continue
                if str(row.get("miss_type") or "") != "missed_entry":
                    continue
                context = str(row.get("context_key") or "")
                parts = context.split("|")
                if len(parts) != 5 or parts[0] in {"", "NO_STRATEGY", "NO_TRADE"}:
                    continue
                family = normalize_strategy_id(parts[0])
                if family not in ACTIVE_PRACTICE_FAMILIES:
                    continue
                bucket = grouped.setdefault(
                    (context, family),
                    {
                        "context_key": context,
                        "family": family,
                        "missed_entry_rows": 0,
                        "oracle_net_pnl_usd": 0.0,
                        "oracle_incremental_vs_actual_usd": 0.0,
                        "blocker_counts": {},
                        "oracle_horizons_minutes": {},
                        "experiment_id": f"oracle_strategy__{context.lower().replace('|', '_')}__{family.lower()}",
                        "source": "live_hindsight_missed_winner_audit_rows",
                    },
                )
                bucket["missed_entry_rows"] += 1
                bucket["oracle_net_pnl_usd"] += _safe_float(row.get("oracle_net_pnl_usd"))
                bucket["oracle_incremental_vs_actual_usd"] += _safe_float(row.get("oracle_incremental_vs_actual_usd") or row.get("oracle_net_pnl_usd"))
                blocker = str(row.get("blocker_reason") or "")
                bucket["blocker_counts"][blocker] = bucket["blocker_counts"].get(blocker, 0) + 1
                horizon = str(_safe_int(row.get("oracle_horizon_minutes")))
                bucket["oracle_horizons_minutes"][horizon] = bucket["oracle_horizons_minutes"].get(horizon, 0) + 1
    except (OSError, csv.Error):
        return []

    rows = list(grouped.values())
    _ORACLE_AUDIT_STRATEGY_CONTEXT_CACHE = {"mtime_ns": stat.st_mtime_ns, "rows": rows}
    return list(rows)


def _oracle_row_matches_strategy_context(row: dict[str, Any], status: Any, inputs: dict[str, Any], side: str) -> bool:
    context = str(row.get("context_key") or "")
    parts = context.split("|")
    if len(parts) != 5:
        return False
    family, row_asset, row_venue, row_side, row_session = parts
    family = normalize_strategy_id(family)
    if family not in ACTIVE_PRACTICE_FAMILIES:
        return False
    if row_side.lower() != side:
        return False
    spec = STRATEGY_SPECS.get(family, STRATEGY_SPECS[NO_TRADE])
    if side not in spec.allowed_sides:
        return False
    asset = str(getattr(status, "asset", "") or "").upper()
    venue = str(getattr(status, "venue", "") or "").lower()
    session = str(inputs.get("bucket_session") or "").lower()
    if row_asset.upper() != asset or row_venue.lower() != venue or row_session.lower() != session:
        return False
    if _safe_int(row.get("missed_entry_rows")) < 2:
        return False
    if _safe_float(row.get("oracle_incremental_vs_actual_usd") or row.get("oracle_net_pnl_usd")) <= 5.0:
        return False
    return not _family_kill_reason(family, status, inputs, side)


def _oracle_distilled_strategy_context(status: Any, inputs: dict[str, Any], side: str) -> dict[str, Any]:
    matches = [
        row for row in _oracle_audit_strategy_contexts()
        if _oracle_row_matches_strategy_context(row, status, inputs, side)
    ]
    if not matches:
        return {}
    matches.sort(
        key=lambda row: (
            _safe_float(row.get("oracle_incremental_vs_actual_usd") or row.get("oracle_net_pnl_usd")),
            _safe_int(row.get("missed_entry_rows")),
        ),
        reverse=True,
    )
    return matches[0]


def _oracle_distilled_no_side_context(status: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(HINDSIGHT_QUEUE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    matches: list[dict[str, Any]] = []
    for row in payload.get("candidate_experiments") or []:
        if not isinstance(row, dict):
            continue
        if _oracle_row_matches_no_side_context(row, status, inputs):
            matches.append({**row, "source": row.get("source") or "hindsight_missed_winner_queue"})
    if not matches:
        matches.extend(row for row in _oracle_audit_no_side_contexts() if _oracle_row_matches_no_side_context(row, status, inputs))
    if not matches:
        return {}
    matches.sort(
        key=lambda row: (
            _safe_float(row.get("oracle_incremental_vs_actual_usd") or row.get("oracle_net_pnl_usd")),
            _safe_int(row.get("missed_entry_rows")),
        ),
        reverse=True,
    )
    return matches[0]


def _live_family_killlist() -> dict[str, Any]:
    try:
        payload = json.loads(LIVE_FAMILY_KILLLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _globally_killed_families() -> set[str]:
    payload = _live_family_killlist()
    return {
        normalize_strategy_id(str(row))
        for row in payload.get("disabled_families") or payload.get("killed_families") or []
        if str(row or "").strip()
    }


def _family_kill_reason(family: str, status: Any, inputs: dict[str, Any], side: str) -> str:
    payload = _live_family_killlist()
    sid = normalize_strategy_id(family)
    for row in payload.get("disabled_families") or payload.get("killed_families") or []:
        if normalize_strategy_id(str(row)) == sid:
            return f"{sid} is disabled by live family killlist"
    context = _context_key_for_family(sid, status, inputs, side)
    avoid = payload.get("avoid_contexts") or {}
    rows = []
    if isinstance(avoid, dict):
        rows = list(avoid.get(sid) or avoid.get(_route_family_name(sid)) or [])
    elif isinstance(avoid, list):
        rows = avoid
    for row in rows:
        if isinstance(row, str) and row == context:
            return f"{sid} is killed for context {context}"
        if isinstance(row, dict) and str(row.get("context") or "") == context:
            return str(row.get("reason") or f"{sid} is killed for context {context}")
    return ""


def _context_routing_family(
    status: Any,
    inputs: dict[str, Any],
    side: str,
    *,
    requested: set[str],
    queued_family: str,
) -> tuple[str, str, dict[str, Any]]:
    try:
        payload = json.loads(EVOLUTION_ROUTING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", "", {}
    routes = payload.get("routes") or {}
    globally_killed = _globally_killed_families()
    active = [
        family for family in ACTIVE_PRACTICE_FAMILIES
        if family not in globally_killed and (not requested or family in requested)
    ]
    all_active = [family for family in ACTIVE_PRACTICE_FAMILIES if family not in globally_killed]
    if not active:
        return "", "context_routing_all_families_killed", {
            "reason": "every requested family is disabled by live family killlist",
            "requested": sorted(requested),
            "killed_families": sorted(globally_killed),
        }
    allow_context_probes = bool(inputs.get("allow_context_probes"))
    if (
        allow_context_probes
        and requested
        and len(active) == 1
        and not bool(inputs.get("allow_promoted_context_rerun"))
    ):
        context = _context_key_for_family(active[0], status, inputs, side)
        if context in _promoted_contexts():
            return "", "context_routing_promoted_context_skip", {
                "reason": f"{context} already has a promoted winner; skip forced probe rerun",
                "context": context,
                "family": active[0],
            }

    def route_for(family: str) -> dict[str, Any] | None:
        return routes.get(_context_route_key(family, status, inputs, side)) if family else None

    def route_is_positive(route: dict[str, Any] | None) -> bool:
        return bool(route) and float(route.get("pnl_R") or 0.0) > 0.0 and int(route.get("trades") or 0) > 0

    def route_is_callable(route: dict[str, Any] | None) -> bool:
        if not route_is_positive(route):
            return False
        if str(route.get("status") or "") == "avoid_context":
            return False
        family = normalize_strategy_id(str((route or {}).get("family") or ""))
        if family and _family_kill_reason(family, status, inputs, side):
            return False
        return True

    queued_route = route_for(queued_family)
    seen_families = [family for family in all_active if route_for(family) is not None]
    unseen_families = [family for family in active if route_for(family) is None]
    min_samples = int(payload.get("min_context_family_samples_before_migration") or MIN_CONTEXT_FAMILY_SAMPLES_BEFORE_ROUTING)
    if len(seen_families) < min_samples:
        if not allow_context_probes:
            return "", "context_routing_calibration_pending_no_probe", {
                "reason": "context has not sampled enough families yet; routed execution will wait instead of probing",
                "seen_family_count": len(seen_families),
                "min_family_count": min_samples,
            }
        if queued_family and queued_route is None:
            return queued_family, "context_calibration_unseen_probe", {
                "seen_family_count": len(seen_families),
                "min_family_count": min_samples,
            }
        if unseen_families:
            return unseen_families[0], "context_calibration_unseen_probe", {
                "seen_family_count": len(seen_families),
                "min_family_count": min_samples,
                "reason": "random calibration continues until several families have sampled this context",
            }
        return "", "", {}

    if allow_context_probes and queued_family and requested and len(active) == 1:
        return queued_family, "context_routing_forced_requested_probe", {
            "reason": "forced broad-sweep evidence probe for the requested family",
            "route": queued_route or {},
            "seen_family_count": len(seen_families),
            "min_family_count": min_samples,
        }

    if (
        queued_route
        and str(queued_route.get("status") or "") == "avoid_context"
        and requested
        and len(active) == 1
        and not allow_context_probes
    ):
        return "", "context_routing_hard_avoid_instance", {
            "reason": (
                f"{queued_family} is marked avoid_context for "
                f"{_context_route_key(queued_family, status, inputs, side)} after {len(seen_families)} family samples"
            ),
            "route": queued_route,
            "seen_family_count": len(seen_families),
            "min_family_count": min_samples,
        }

    candidates: list[dict[str, Any]] = []
    for route in routes.values():
        family = normalize_strategy_id(str(route.get("family") or ""))
        if family not in active:
            continue
        if requested and family not in requested:
            continue
        if str(route.get("asset") or "").upper() != str(getattr(status, "asset", "") or "").upper():
            continue
        if str(route.get("venue") or "").lower() != str(getattr(status, "venue", "") or "").lower():
            continue
        if str(route.get("session") or "").lower() != str(inputs.get("bucket_session") or "").lower():
            continue
        if str(route.get("side") or "").lower() != _route_side_for_family(family, side):
            continue
        if not route_is_callable(route):
            continue
        candidates.append(dict(route))

    candidates.sort(
        key=lambda row: (
            float(row.get("pnl_R") or 0.0),
            float(row.get("fit_score") or 0.0),
            int(row.get("trades") or 0),
        ),
        reverse=True,
    )
    best = candidates[0] if candidates else {}
    queued_is_bad = bool(queued_route) and str(queued_route.get("status") or "") == "avoid_context"
    if queued_is_bad and best:
        return normalize_strategy_id(str(best.get("family") or "")), "context_routing_exact_instance_avoided_bad_queue", best
    if queued_is_bad:
        if allow_context_probes and queued_family and requested and len(active) == 1:
            return queued_family, "context_routing_forced_requested_probe", {
                "reason": f"{queued_family} is already marked avoid_context here; forced broad-sweep evidence probe is enabled",
                "route": queued_route,
            }
        if allow_context_probes:
            for family in active:
                if route_for(family) is None:
                    return family, "context_routing_unseen_probe", {
                        "reason": f"{queued_family} is already marked avoid_context here; probing unseen family-context pair"
                    }
        return "", "context_routing_no_safe_unseen", {
            "reason": f"{queued_family} is already marked avoid_context here and every active family has evidence"
        }
    if best:
        return normalize_strategy_id(str(best.get("family") or "")), "context_routing_exact_positive_pnl_instance", best
    if allow_context_probes and queued_family and requested and len(active) == 1:
        return queued_family, "context_routing_forced_requested_probe", {
            "reason": "forced broad-sweep evidence probe for the requested family",
            "route": queued_route or {},
        }
    if allow_context_probes and queued_family and queued_route is None:
        return queued_family, "context_routing_unseen_probe", {"reason": "queued family has no evidence in this context"}
    if allow_context_probes and unseen_families:
        return unseen_families[0], "context_routing_unseen_until_positive_pnl", {
            "reason": "no positive-PnL route exists yet for this context; probing an unseen family-context pair"
        }
    if allow_context_probes and queued_family:
        return queued_family, "context_routing_study_queue_probe", {
            "reason": "no positive-PnL route exists yet; execute the study-queue family to keep mining the context",
            "route": queued_route or {},
        }
    if seen_families:
        return "", "context_routing_no_positive_pnl", {
            "reason": "every sampled family-context route is non-positive PnL; do not execute this context until a mutation wins",
            "seen_family_count": len(seen_families),
            "min_family_count": min_samples,
        }
    return "", "context_routing_no_evidence_no_probe", {
        "reason": "no callable positive route exists and context probes are disabled for routed execution"
    }


def classify_strategy(status: Any, inputs: dict[str, Any], asset_news: Any | None = None) -> StrategyDecision:
    """Map current market/news context to one explicit strategy family.

    This is intentionally present-tense and deterministic. It does not look at
    future replay outcomes, so the same function can be used by live mock
    trading and historical replay.
    """
    side = str(getattr(status, "trade_option_side", "") or getattr(status, "pressure_watch_direction", "") or "")
    side = side.lower()
    disable_oracle = bool(inputs.get("disable_oracle_distilled_context"))
    disable_oracle_no_side = disable_oracle or bool(inputs.get("disable_oracle_distilled_no_side_context"))
    disable_oracle_strategy = disable_oracle or bool(inputs.get("disable_oracle_distilled_strategy_context"))
    exact_context_only = bool(inputs.get("exact_context_routing_only"))
    if side not in {"buy", "sell"}:
        practice_mode = str(inputs.get("strategy_mode") or "").lower() in LEARNING_MODES
        if practice_mode and not disable_oracle_no_side:
            oracle_row = _oracle_distilled_no_side_context(status, inputs)
            if oracle_row:
                family = normalize_strategy_id(str(oracle_row.get("family") or ""))
                inferred_side = str(oracle_row.get("context_key") or "").split("|")[3].lower()
                spec = STRATEGY_SPECS.get(family, STRATEGY_SPECS[NO_TRADE])
                pnl = float(oracle_row.get("oracle_incremental_vs_actual_usd") or oracle_row.get("oracle_net_pnl_usd") or 0.0)
                missed = int(oracle_row.get("missed_entry_rows") or 0)
                confidence = min(0.90, 0.50 + min(0.25, pnl / 2500.0) + min(0.15, missed / 500.0))
                return StrategyDecision(
                    strategy_id=family,
                    label=spec.label,
                    confidence=confidence,
                    side_override=inferred_side,
                    reasons=[
                        (
                            "Oracle-distilled no-side context: "
                            f"{family} {inferred_side} has {missed} missed winners "
                            f"and ${pnl:.2f} incremental oracle PnL"
                        )
                    ],
                    spec=spec,
                    forced=True,
                    variant_id=str(oracle_row.get("experiment_id") or f"{family.lower()}__oracle_distilled_no_side"),
                    risk_tags=["oracle_distilled_context", "hindsight_missed_winner", "mock_only"],
                    handoff_hint="Use the oracle-derived side/family as a live-observable mock route; promotion still requires live/shadow PnL.",
                    source_queue_action="oracle_distilled_no_side_context",
                )
        if exact_context_only:
            return StrategyDecision(blockers=["Historic parity requires an observable side and exact positive context route"])
        return StrategyDecision(blockers=["No directional side is available"])

    practice_mode = str(inputs.get("strategy_mode") or "").lower() in LEARNING_MODES
    if practice_mode:
        oracle_row = None if disable_oracle_strategy else _oracle_distilled_strategy_context(status, inputs, side)
        if oracle_row:
            family = normalize_strategy_id(str(oracle_row.get("family") or ""))
            spec = STRATEGY_SPECS.get(family, STRATEGY_SPECS[NO_TRADE])
            pnl = _safe_float(oracle_row.get("oracle_incremental_vs_actual_usd") or oracle_row.get("oracle_net_pnl_usd"))
            missed = _safe_int(oracle_row.get("missed_entry_rows"))
            confidence = min(0.92, 0.55 + min(0.25, pnl / 1500.0) + min(0.12, missed / 300.0))
            return StrategyDecision(
                strategy_id=family,
                label=spec.label,
                confidence=confidence,
                side_override="",
                reasons=[
                    (
                        "Oracle-distilled strategy context: "
                        f"{family} {side} has {missed} missed winners "
                        f"and ${pnl:.2f} incremental oracle PnL"
                    )
                ],
                spec=spec,
                forced=True,
                variant_id=str(oracle_row.get("experiment_id") or f"{family.lower()}__oracle_distilled_strategy_context"),
                risk_tags=["oracle_distilled_context", "hindsight_missed_winner", "mock_only"],
                handoff_hint="Use the oracle-derived strategy context as the active mock route; sidecar exits keep challenging it.",
                source_queue_action="oracle_distilled_strategy_context",
            )
        allow_context_probes = bool(inputs.get("allow_context_probes"))
        requested = {str(x).upper() for x in inputs.get("requested_strategy_families") or [] if str(x).strip()}
        queued_family, queue_action = _queued_practice_family(requested)
        routed_family, routing_action, routing_route = _context_routing_family(
            status,
            inputs,
            side,
            requested=requested,
            queued_family=queued_family,
        )
        if routing_action in {
            "context_routing_no_safe_unseen",
            "context_routing_hard_avoid_instance",
            "context_routing_no_positive_pnl",
            "context_routing_calibration_pending_no_probe",
            "context_routing_no_evidence_no_probe",
            "context_routing_promoted_context_skip",
            "context_routing_all_families_killed",
        }:
            return StrategyDecision(blockers=[str(routing_route.get("reason") or "Context routing found no unseen or fit family")])
        if routed_family:
            queued_family = routed_family
            queue_action = routing_action
            if routing_action in {
                "context_routing_exact_positive_pnl_instance",
                "context_routing_exact_instance_avoided_bad_queue",
            }:
                spec = STRATEGY_SPECS.get(routed_family, STRATEGY_SPECS[NO_TRADE])
                route_side = str(routing_route.get("side") or _route_side_for_family(routed_family, side)).lower()
                fit_score = float(routing_route.get("fit_score") or 0.0)
                pnl_r = float(routing_route.get("pnl_R") or 0.0)
                trades = int(routing_route.get("trades") or 0)
                win_rate = routing_route.get("win_rate")
                confidence = max(0.35, min(0.95, 0.45 + (fit_score / 200.0)))
                return StrategyDecision(
                    strategy_id=routed_family,
                    label=spec.label,
                    confidence=confidence,
                    side_override=route_side if route_side in {"buy", "sell"} and route_side != side else "",
                    reasons=[
                        (
                            "Historical route winner: "
                            f"{routed_family} exact context pnl_R={pnl_r:.3f}, "
                            f"trades={trades}, win_rate={win_rate}"
                        )
                    ],
                    spec=spec,
                    forced=True,
                    variant_id=str(routing_route.get("bucket_id") or f"{routed_family.lower()}__routed"),
                    risk_tags=["historical_route", "context_routed", "mock_only"],
                    handoff_hint="Execute the best positive exact-context family from strategy_evolution routing JSON.",
                source_queue_action=routing_action,
            )
        if exact_context_only:
            return StrategyDecision(blockers=["Historic parity requires an exact positive context-routed family"])
        should_force_learning_family = bool(queued_family) and (
            bool(routing_action)
            or str(queue_action).startswith("evolve_from_")
        )
        if should_force_learning_family and allow_context_probes:
            try:
                from strategy_library import force_practice_strategy
                forced_signal = force_practice_strategy(
                    status,
                    inputs,
                    asset_news,
                    preferred_family=queued_family,
                    source_queue_action=queue_action,
                )
            except Exception:
                forced_signal = None
            if forced_signal is not None:
                spec = STRATEGY_SPECS.get(forced_signal.strategy_id, STRATEGY_SPECS[NO_TRADE])
                return StrategyDecision(
                    strategy_id=forced_signal.strategy_id,
                    label=spec.label,
                    confidence=max(0.0, min(1.0, forced_signal.confidence)),
                    side_override=forced_signal.side if forced_signal.side != side else "",
                    reasons=list(forced_signal.reasons),
                    spec=spec,
                    forced=True,
                    variant_id=str(forced_signal.variant_id or ""),
                    risk_tags=[
                        *list(forced_signal.risk_tags or []),
                        *(["context_routed"] if routing_action else []),
                    ],
                    handoff_hint=str(forced_signal.handoff_hint or ""),
                    source_queue_action=str(forced_signal.source_queue_action or queue_action or ""),
                )
        try:
            from strategy_library import force_practice_strategy, suggest_practice_strategy
            practice_signal = suggest_practice_strategy(status, inputs, asset_news)
        except Exception:
            practice_signal = None
        if practice_signal is not None:
            spec = STRATEGY_SPECS.get(practice_signal.strategy_id, STRATEGY_SPECS[NO_TRADE])
            return StrategyDecision(
                strategy_id=practice_signal.strategy_id,
                label=spec.label,
                confidence=max(0.0, min(1.0, practice_signal.confidence)),
                side_override=practice_signal.side if practice_signal.side != side else "",
                reasons=list(practice_signal.reasons),
                spec=spec,
                forced=bool(getattr(practice_signal, "forced", False)),
                variant_id=str(getattr(practice_signal, "variant_id", "") or ""),
                risk_tags=list(getattr(practice_signal, "risk_tags", []) or []),
                handoff_hint=str(getattr(practice_signal, "handoff_hint", "") or ""),
                source_queue_action=str(getattr(practice_signal, "source_queue_action", "") or ""),
            )
        if allow_context_probes:
            try:
                forced_signal = force_practice_strategy(
                    status,
                    inputs,
                    asset_news,
                    preferred_family=queued_family,
                    source_queue_action=queue_action,
                )
            except Exception:
                forced_signal = None
            if forced_signal is not None:
                spec = STRATEGY_SPECS.get(forced_signal.strategy_id, STRATEGY_SPECS[NO_TRADE])
                return StrategyDecision(
                    strategy_id=forced_signal.strategy_id,
                    label=spec.label,
                    confidence=max(0.0, min(1.0, forced_signal.confidence)),
                    side_override=forced_signal.side if forced_signal.side != side else "",
                    reasons=list(forced_signal.reasons),
                    spec=spec,
                    forced=True,
                    variant_id=str(forced_signal.variant_id or ""),
                    risk_tags=[
                        *list(forced_signal.risk_tags or []),
                        *(["context_routed"] if routing_action else []),
                    ],
                    handoff_hint=str(forced_signal.handoff_hint or ""),
                    source_queue_action=str(forced_signal.source_queue_action or queue_action or ""),
                )
            return StrategyDecision(blockers=["No side available for forced learning probe"])
        return StrategyDecision(blockers=["No routed practice strategy and forced probes are disabled"])

    venue = str(getattr(status, "venue", "") or "")
    score = int(inputs.get("trade_present_score") or getattr(status, "trade_present_score", 0) or 0)
    stage = str(inputs.get("trade_stage") or getattr(status, "trade_stage", "") or "")
    regime = str(getattr(status, "regime", "") or "")
    pressure_state = str(getattr(status, "pressure_watch_state", "") or "")
    pressure_priority = int(getattr(status, "pressure_watch_priority", 0) or 0)
    volume_z = float(inputs.get("volume_zscore") or 0.0)
    current_bps = float(inputs.get("trade_current_chunk_bps") or 0.0)
    recent_bps = float(inputs.get("trade_recent_2chunk_bps") or current_bps)
    from_onset_bps = float(inputs.get("trade_from_onset_bps") or 0.0)
    abs_dipole = abs(float(inputs.get("mean_dipole") or getattr(status, "mean_dipole", 0.0) or 0.0))
    news_dipole = float(getattr(asset_news, "news_dipole", 0.0) or 0.0) if asset_news is not None else 0.0
    news_bias = str(getattr(asset_news, "narrative_bias", "") or "").upper() if asset_news is not None else ""
    news_confirmation = str(getattr(asset_news, "market_confirmation", "") or "").upper() if asset_news is not None else ""
    starters = _starter_actions(asset_news) if asset_news is not None else set()

    candidates: list[tuple[float, str, list[str], str]] = []

    if starters:
        defensive_short = side == "sell" and ("EXIT_LONGS" in starters or "REDUCE_GROSS_EXPOSURE" in starters or "ALLOW_HEDGE" in starters)
        defensive_long = side == "buy" and ("EXIT_SHORTS" in starters or "REDUCE_GROSS_EXPOSURE" in starters or "ALLOW_HEDGE" in starters)
        if defensive_short or defensive_long:
            confidence = 0.55 + min(0.25, score / 400.0)
            candidates.append((confidence, NEWS_SHOCK_EXIT_OR_HEDGE, ["Shock-news starter supports a defensive action"], side))

    bias_side = _news_side(news_bias)
    if bias_side == side and news_confirmation in {"STRONG", "CONFIRMED"}:
        confidence = 0.50 + min(0.20, score / 500.0) + min(0.15, abs(news_dipole) * 0.15)
        candidates.append((confidence, NEWS_CONFIRMED_DIRECTIONAL, ["News bias and market side are aligned"], side))

    if regime in {"HERD_UP", "HERD_DOWN"} and volume_z >= 1.0 and from_onset_bps >= 12.0 and recent_bps <= 1.0:
        confidence = 0.52 + min(0.20, volume_z / 10.0) + min(0.15, from_onset_bps / 200.0)
        fade_side = _opposite_side(side) or side
        candidates.append((confidence, LIQUIDATION_SWEEP_FADE, ["Herd move looks extended and is losing follow-through"], fade_side))

    if stage == "mature" and score >= 70 and from_onset_bps > 6.0 and recent_bps > 0.0:
        confidence = 0.50 + min(0.20, score / 500.0) + min(0.10, recent_bps / 100.0)
        candidates.append((confidence, BREAKOUT_PULLBACK, ["Mature setup is still advancing after the initial move"], side))

    has_follow_through = continuation_regime_ok(regime, current_bps, recent_bps)
    if (
        pressure_state in {"forming", "high_priority", "confirmed"}
        and stage in {"onset", "early_follow"}
        and has_follow_through
    ):
        candidates.append((
            0.05,
            NO_TRADE,
            ["Continuation-style entry is outside the active strategy universe"],
            "",
        ))
    elif pressure_state in {"forming", "high_priority", "confirmed"} and stage in {"onset", "early_follow"}:
        candidates.append((
            0.05,
            NO_TRADE,
            ["Pressure is visible but regime/follow-through does not justify continuation"],
            "",
        ))

    is_chop_regime = regime in {"EQUILIBRIUM_TWO_SIDED", "WASH_HAWKES", "WASH_PAIRED"}
    is_stalled_directional = stage in {"early_follow", "mature"} and recent_bps <= 0.0 and score < 72
    is_stretched = abs(current_bps) >= 2.0 or abs(from_onset_bps) >= 8.0
    if (is_chop_regime or is_stalled_directional) and is_stretched:
        fade_side = _opposite_side(side) or side
        confidence = 0.48 + min(0.18, abs(current_bps) / 80.0) + min(0.12, abs(from_onset_bps) / 160.0)
        candidates.append((confidence, MEAN_REVERSION_CHOP, ["Chop or stalled tape favors fading the stretched side"], fade_side))

    if not candidates:
        return StrategyDecision(blockers=["No strategy family matched current context"])

    candidates.sort(key=lambda row: row[0], reverse=True)
    blockers: list[str] = []
    for confidence, strategy_id, reasons, candidate_side in candidates:
        spec = STRATEGY_SPECS[strategy_id]
        effective_side = candidate_side or side
        if effective_side not in spec.allowed_sides:
            blockers.append(f"{strategy_id} does not allow {effective_side}")
            continue
        if venue and venue not in spec.allowed_venues:
            blockers.append(f"{strategy_id} does not allow {venue}")
            continue
        if score < spec.min_present_score:
            blockers.append(f"{strategy_id} needs score {spec.min_present_score}+")
            continue
        if asset_news is not None:
            ok, reason = _news_allows_strategy(asset_news, strategy_id)
            if not ok:
                blockers.append(reason)
                continue
        if spec.requires_market_confirmation and news_bias in {"BULLISH", "BEARISH"} and _side_bias(effective_side) != news_bias and news_confirmation != "STRONG":
            blockers.append(f"{strategy_id} conflicts with unresolved daily news bias")
            continue
        return StrategyDecision(
            strategy_id=strategy_id,
            label=spec.label,
            confidence=max(0.0, min(1.0, confidence)),
            side_override=effective_side if effective_side != side else "",
            reasons=reasons,
            blockers=blockers,
            spec=spec,
        )

    return StrategyDecision(blockers=blockers or ["Candidate strategies were blocked"])


def apply_strategy_to_option(option: dict[str, Any], decision: StrategyDecision) -> dict[str, Any]:
    if not option:
        return option
    out = dict(option)
    if decision.strategy_id in DISABLED_STRATEGIES:
        decision = StrategyDecision(
            blockers=[f"{decision.strategy_id} is disabled after negative evidence"],
        )
    out.update(decision.to_option_fields())
    reasons = list(out.get("trade_option_entry_reasons") or [])
    blockers = list(out.get("trade_option_blockers") or [])

    if decision.strategy_id == NO_TRADE:
        blockers.extend(decision.blockers or ["No trade strategy selected"])
    else:
        if decision.side_override in {"buy", "sell"}:
            out["trade_option_side"] = decision.side_override
            reasons.append(f"Strategy side override: {decision.side_override}")
        reasons.append(f"Strategy: {decision.label}")
        reasons.extend(decision.reasons)
        blockers.extend(decision.blockers)
        base_scale = float(out.get("trade_option_notional_scale") or 0.0)
        out["trade_option_notional_scale"] = base_scale * decision.spec.notional_scale_multiplier
        if decision.spec.hold_minutes:
            current_hold = int(out.get("trade_option_hold_minutes") or 0)
            out["trade_option_hold_minutes"] = min(current_hold or decision.spec.hold_minutes, decision.spec.hold_minutes)
        out["trade_strategy_stop_loss_bps"] = decision.spec.stop_loss_bps
        out["trade_strategy_take_profit_bps"] = decision.spec.take_profit_bps
        out["trade_strategy_exit_score_drop"] = decision.spec.exit_score_drop

        mode = str(out.get("trade_strategy_mode") or "").lower()
        if mode in LEARNING_MODES:
            out["trade_option_state"] = "early_probe"
            out["trade_option_profile"] = "practice_probe"
            out["trade_option_label"] = f"{out['trade_option_side'].title()} {decision.label}"
            out["trade_option_size_hint"] = "forced learning size" if decision.forced else "practice learning size"
            floor = 0.05 if decision.forced else 0.10
            out["trade_option_notional_scale"] = max(float(out.get("trade_option_notional_scale") or 0.0), floor)
            if decision.forced:
                out["trade_option_readiness"] = max(int(out.get("trade_option_readiness") or 0), 55)
                reasons.append("Forced exploration: Refrag learning loop requires this family to trade and report")
            blockers = [
                blocker for blocker in blockers
                if not any(token in str(blocker) for token in (
                    "Present score below",
                    "Pressure is not visible enough",
                    "Transition risk without clean directional edge",
                    "Move already extended",
                    "Setup is strong but no longer advancing",
                ))
            ]

    out["trade_option_entry_reasons"] = reasons[:6]
    out["trade_option_blockers"] = list(dict.fromkeys(blockers))[:6]
    return out
