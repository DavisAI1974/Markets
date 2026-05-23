from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_PRACTICE_FEE_BPS = 25.0
_EXIT_KILLLIST_PATH = Path(__file__).resolve().parent / "research" / "strategy_evolution" / "_live_exit_killlist.json"
_FAMILY_EXIT_PAIRINGS_PATH = (
    Path(__file__).resolve().parent / "research" / "strategy_evolution" / "_family_exit_pairings.json"
)
_HINDSIGHT_AUDIT_ROWS_PATH = (
    Path(__file__).resolve().parent / "research" / "strategy_evolution" / "live_mock_replay" / "live_hindsight_missed_winner_audit_rows.csv"
)
_RUNTIME_COUNTERFACTUAL_POLICY_ROWS_PATH = (
    Path(__file__).resolve().parent / "research" / "strategy_evolution" / "live_mock_replay" / "live_counterfactual_exit_policy_rows.csv"
)
_RUNTIME_COUNTERFACTUAL_ROWS_PATH = (
    Path(__file__).resolve().parent / "research" / "strategy_evolution" / "live_mock_replay" / "live_sidecar_exit_restatement_rows.csv"
)
_WINNER_PNL_ASSIGNMENTS_PATH = (
    Path(__file__).resolve().parent / "research" / "strategy_evolution" / "_winner_trade_pnl_strategy_assignments_h0_h168.json"
)
_RUNTIME_ORACLE_EXIT_CACHE: dict[str, Any] = {"mtime_ns": None, "configs": {}}
_HISTORIC_SELECTOR_CACHE: dict[str, Any] = {"mtime_ns": None, "index": {}}
_RUNTIME_COUNTERFACTUAL_SELECTOR_CACHE: dict[str, Any] = {"mtime_ns": None, "index": {}}
DEFAULT_RUNTIME_COUNTERFACTUAL_FIXED_HOLD_MINUTES = (10, 30, 60, 120, 240, 360)
BANK_PROGRESS_EXIT_REASONS = {
    "oracle_bank_fee_not_covered_by_15m",
    "oracle_bank_slow_progress_bps_per_min",
    "oracle_bank_no_20bps_by_30m",
    "oracle_bank_peak_giveback_exit",
}


GATED_PROFITABLE_SCORE_NEWS_EXITS = "gated_profitable_score_news_exits_v1"
BASIS_DISLOCATION_RUNNER_EXITS = "basis_dislocation_runner_exits_v1"
LIQUIDITY_SQUEEZE_RUNNER_EXITS = "liquidity_squeeze_runner_exits_v1"
MEAN_REVERSION_CHOP_TIGHT_EXITS = "mean_reversion_chop_tight_exits_v1"
BUY_UP_CONTINUATION_FAST_FAIL_EXITS = "buy_up_continuation_fast_fail_exits_v1"


@dataclass(frozen=True)
class ExitProfile:
    profile_id: str
    label: str
    family_hint: str = ""
    score_exit_min_hold_minutes: float = 30.0
    score_exit_min_profit_bps: float = 20.0
    profitable_hold_extension_minutes: float = 60.0
    tp1_bps: float = 0.0
    scale_out_fraction: float = 0.0
    runner_trail_bps: float = 0.0
    max_hold_minutes: float = 0.0
    counterfactual_horizon_minutes: int = 30
    under_gate_trim_fraction: float = 0.25
    news_can_full_flat_profitable: bool = False
    gate_profitable_score_exits: bool = True
    gate_profitable_news_exits: bool = True
    gate_profitable_pressure_exits: bool = True
    gate_profitable_setup_exits: bool = True
    defer_unprofitable_pressure_exits: bool = False


@dataclass(frozen=True)
class ExitDecision:
    action: str
    reason: str = ""
    profile_id: str = GATED_PROFITABLE_SCORE_NEWS_EXITS
    unrealized_bps: float = 0.0
    net_unrealized_bps: float = 0.0
    elapsed_min: float = 0.0
    deferred: bool = False
    deferred_signal: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def to_trade_metadata(self) -> dict[str, Any]:
        out = asdict(self)
        out.pop("deferred_signal", None)
        out["metadata"] = self.metadata or {}
        return out


EXIT_PROFILES: dict[str, ExitProfile] = {
    GATED_PROFITABLE_SCORE_NEWS_EXITS: ExitProfile(
        profile_id=GATED_PROFITABLE_SCORE_NEWS_EXITS,
        label="Gate profitable score/news exits before full close",
    ),
    BASIS_DISLOCATION_RUNNER_EXITS: ExitProfile(
        profile_id=BASIS_DISLOCATION_RUNNER_EXITS,
        label="Basis dislocation partial take-profit with modest runner",
        family_hint="BASIS_DISLOCATION",
        score_exit_min_profit_bps=15.0,
        tp1_bps=20.0,
        scale_out_fraction=0.50,
        runner_trail_bps=12.0,
        max_hold_minutes=90.0,
    ),
    LIQUIDITY_SQUEEZE_RUNNER_EXITS: ExitProfile(
        profile_id=LIQUIDITY_SQUEEZE_RUNNER_EXITS,
        label="Liquidity squeeze small lock with loose runner",
        family_hint="LIQUIDITY_SQUEEZE",
        score_exit_min_profit_bps=10.0,
        tp1_bps=12.0,
        scale_out_fraction=0.33,
        runner_trail_bps=25.0,
        max_hold_minutes=120.0,
    ),
    MEAN_REVERSION_CHOP_TIGHT_EXITS: ExitProfile(
        profile_id=MEAN_REVERSION_CHOP_TIGHT_EXITS,
        label="Mean reversion tighter scale-out and cleanup",
        family_hint="MEAN_REVERSION_CHOP",
        score_exit_min_profit_bps=12.0,
        tp1_bps=18.0,
        scale_out_fraction=0.50,
        runner_trail_bps=8.0,
        max_hold_minutes=60.0,
    ),
    BUY_UP_CONTINUATION_FAST_FAIL_EXITS: ExitProfile(
        profile_id=BUY_UP_CONTINUATION_FAST_FAIL_EXITS,
        label="Buy-up continuation fast-fail with partial runner",
        family_hint="BUY_UP_CONTINUATION",
        score_exit_min_hold_minutes=6.0,
        score_exit_min_profit_bps=8.0,
        profitable_hold_extension_minutes=24.0,
        tp1_bps=9.0,
        scale_out_fraction=0.50,
        runner_trail_bps=5.0,
        max_hold_minutes=35.0,
        under_gate_trim_fraction=0.20,
        news_can_full_flat_profitable=True,
    ),
}


SUGGESTED_EXIT_PROFILE_BY_STRATEGY: dict[str, str] = {
    "SMALL_MOVE_FADE": GATED_PROFITABLE_SCORE_NEWS_EXITS,
    "BUY_UP_CONTINUATION": BUY_UP_CONTINUATION_FAST_FAIL_EXITS,
    "BUY_FADE": GATED_PROFITABLE_SCORE_NEWS_EXITS,
    "SELL_DOWN_CONTINUATION": GATED_PROFITABLE_SCORE_NEWS_EXITS,
    "BASIS_DISLOCATION": BASIS_DISLOCATION_RUNNER_EXITS,
    "LIQUIDITY_SQUEEZE": LIQUIDITY_SQUEEZE_RUNNER_EXITS,
    "MEAN_REVERSION_CHOP": MEAN_REVERSION_CHOP_TIGHT_EXITS,
}


def _disabled_exit_profiles() -> set[str]:
    try:
        payload = json.loads(_EXIT_KILLLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    disabled: set[str] = set()
    for row in payload.get("disabled_exit_profiles") or payload.get("killed_exit_profiles") or []:
        if isinstance(row, str):
            profile_id = row
        elif isinstance(row, dict):
            profile_id = str(row.get("profile_id") or row.get("id") or "")
        else:
            profile_id = ""
        profile_id = profile_id.strip()
        if profile_id:
            disabled.add(profile_id)
    return disabled


def _is_exit_profile_disabled(profile_id: str) -> bool:
    return str(profile_id or "").strip() in _disabled_exit_profiles()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _quantile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    pos = (len(values) - 1) * fraction
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return values[lo]
    return values[lo] * (hi - pos) + values[hi] * (pos - lo)


def _runtime_oracle_exit_configs() -> dict[str, dict[str, Any]]:
    global _RUNTIME_ORACLE_EXIT_CACHE
    try:
        stat = _HINDSIGHT_AUDIT_ROWS_PATH.stat()
    except OSError:
        return {}
    if _RUNTIME_ORACLE_EXIT_CACHE.get("mtime_ns") == stat.st_mtime_ns:
        return dict(_RUNTIME_ORACLE_EXIT_CACHE.get("configs") or {})

    grouped: dict[str, list[dict[str, float]]] = {}
    pattern_grouped: dict[str, list[dict[str, float]]] = {}
    try:
        with _HINDSIGHT_AUDIT_ROWS_PATH.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("is_oracle_winner_after_fees") or "").lower() not in {"true", "1", "yes"}:
                    continue
                bps = _safe_float(row.get("oracle_net_bps"))
                horizon = _safe_int(row.get("oracle_horizon_minutes"))
                pnl = _safe_float(row.get("oracle_net_pnl_usd"))
                if bps <= 0 or horizon <= 0:
                    continue
                item = {"bps": bps, "horizon": float(horizon), "pnl": pnl}
                strategy = str(row.get("strategy_id") or "").strip().upper()
                pattern = str(row.get("pattern_family") or "").strip().upper()
                if strategy and strategy not in {"NO_STRATEGY", "NO_TRADE"}:
                    grouped.setdefault(strategy, []).append(item)
                if pattern:
                    pattern_grouped.setdefault(pattern, []).append(item)
    except (OSError, csv.Error):
        return {}

    configs: dict[str, dict[str, Any]] = {}
    for strategy in sorted(set(grouped) | set(pattern_grouped)):
        data = grouped.get(strategy) or []
        source_group = "strategy_id"
        if len(data) < 20 and pattern_grouped.get(strategy):
            data = pattern_grouped[strategy]
            source_group = "pattern_family"
        if len(data) < 2:
            continue
        bps_values = [float(row["bps"]) for row in data]
        horizon_counts: dict[int, int] = {}
        for row in data:
            horizon = int(row["horizon"])
            horizon_counts[horizon] = horizon_counts.get(horizon, 0) + 1
        mode_horizon = sorted(horizon_counts.items(), key=lambda item: (item[1], item[0]), reverse=True)[0][0]
        p25 = _quantile(bps_values, 0.25)
        median = _quantile(bps_values, 0.50)
        p75 = _quantile(bps_values, 0.75)
        configs[strategy] = {
            "id": f"{strategy.lower()}_runtime_oracle_exit_solution",
            "role": "runtime_oracle_exit_solution",
            "label": f"{strategy} runtime oracle exit solution",
            "shadow_enabled": True,
            "execution_enabled": True,
            "exit_profile_id": GATED_PROFITABLE_SCORE_NEWS_EXITS,
            "hold_minutes": mode_horizon,
            "stop_loss_bps": round(max(6.0, min(16.0, p25 * 0.55)), 2),
            "take_profit_bps": round(p75, 2),
            "score_exit_min_hold_minutes": round(max(8.0, min(float(mode_horizon) * 0.50, float(mode_horizon))), 2),
            "score_exit_min_profit_bps": round(median, 2),
            "profitable_hold_extension_minutes": mode_horizon,
            "tp1_bps": round(median, 2),
            "scale_out_fraction": 0.5,
            "runner_trail_bps": round(max(5.0, min(22.0, (p75 - median) * 0.55)), 2),
            "max_hold_minutes": mode_horizon,
            "defer_unprofitable_pressure_exits": True,
            "news_can_full_flat_profitable": True,
            "config_level": "runtime_oracle_exit_solution",
            "config_key": strategy,
            "runtime_oracle_source_path": str(_HINDSIGHT_AUDIT_ROWS_PATH),
            "runtime_oracle_source_group": source_group,
            "runtime_oracle_rows": len(data),
        }
    _RUNTIME_ORACLE_EXIT_CACHE = {"mtime_ns": stat.st_mtime_ns, "configs": configs}
    return dict(configs)


def _family_exit_pairings() -> dict[str, Any]:
    try:
        payload = json.loads(_FAMILY_EXIT_PAIRINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def family_exit_pairing_for_trade(trade: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    if bool(scenario.get("disable_family_exit_pairing")):
        return {}
    if scenario.get("exit_variant_id"):
        return {}
    if scenario.get("exit_profile_id") or scenario.get("exit_management_model"):
        return {}
    strategy = _trade_strategy_id(trade)
    if not strategy:
        return {}
    payload = _family_exit_pairings()
    family = ((payload.get("families") or {}).get(strategy) or {})
    if not isinstance(family, dict):
        return {}
    active_id = str(family.get("active_candidate_id") or "").strip()
    if not active_id:
        return {}
    candidates = family.get("candidate_exits") or []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("id") or "").strip() != active_id:
            continue
        if not bool(candidate.get("execution_enabled", candidate.get("enabled", False))):
            return {}
        profile_id = str(candidate.get("exit_profile_id") or GATED_PROFITABLE_SCORE_NEWS_EXITS)
        if _is_exit_profile_disabled(profile_id):
            return {}
        out = dict(candidate)
        out["config_level"] = "family_exit_pairing"
        out["config_key"] = f"{strategy}|{active_id}"
        out["family_exit_pairing_path"] = str(_FAMILY_EXIT_PAIRINGS_PATH)
        return out
    runtime = _runtime_oracle_exit_configs().get(strategy) or {}
    if runtime and not _is_exit_profile_disabled(str(runtime.get("exit_profile_id") or "")):
        return dict(runtime)
    return {}


def exit_profile_from_scenario(scenario: dict[str, Any]) -> ExitProfile:
    profile_id = str(scenario.get("exit_profile_id") or scenario.get("exit_management_model") or GATED_PROFITABLE_SCORE_NEWS_EXITS)
    if _is_exit_profile_disabled(profile_id):
        profile_id = GATED_PROFITABLE_SCORE_NEWS_EXITS
    base = EXIT_PROFILES.get(profile_id, EXIT_PROFILES[GATED_PROFITABLE_SCORE_NEWS_EXITS])
    return ExitProfile(
        profile_id=base.profile_id,
        label=base.label,
        family_hint=base.family_hint,
        score_exit_min_hold_minutes=float(
            scenario.get("score_exit_min_hold_minutes") or base.score_exit_min_hold_minutes
        ),
        score_exit_min_profit_bps=float(
            scenario.get("score_exit_min_profit_bps") or base.score_exit_min_profit_bps
        ),
        profitable_hold_extension_minutes=float(
            scenario.get("profitable_hold_extension_minutes") or base.profitable_hold_extension_minutes
        ),
        tp1_bps=float(scenario.get("tp1_bps") or base.tp1_bps),
        scale_out_fraction=float(scenario.get("scale_out_fraction") or base.scale_out_fraction),
        runner_trail_bps=float(scenario.get("runner_trail_bps") or base.runner_trail_bps),
        max_hold_minutes=float(scenario.get("max_hold_minutes") or base.max_hold_minutes),
        counterfactual_horizon_minutes=int(
            scenario.get("counterfactual_horizon_minutes") or base.counterfactual_horizon_minutes
        ),
        under_gate_trim_fraction=float(scenario.get("under_gate_trim_fraction") or base.under_gate_trim_fraction),
        news_can_full_flat_profitable=bool(
            scenario.get("news_can_full_flat_profitable", base.news_can_full_flat_profitable)
        ),
        gate_profitable_score_exits=bool(scenario.get("gate_profitable_score_exits", base.gate_profitable_score_exits)),
        gate_profitable_news_exits=bool(scenario.get("gate_profitable_news_exits", base.gate_profitable_news_exits)),
        gate_profitable_pressure_exits=bool(
            scenario.get("gate_profitable_pressure_exits", base.gate_profitable_pressure_exits)
        ),
        gate_profitable_setup_exits=bool(scenario.get("gate_profitable_setup_exits", base.gate_profitable_setup_exits)),
        defer_unprofitable_pressure_exits=bool(
            scenario.get("defer_unprofitable_pressure_exits", base.defer_unprofitable_pressure_exits)
        ),
    )


def suggested_exit_profile_id_for_strategy(strategy_id: str) -> str:
    return SUGGESTED_EXIT_PROFILE_BY_STRATEGY.get(str(strategy_id or "").strip().upper(), GATED_PROFITABLE_SCORE_NEWS_EXITS)


def load_exit_params(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _signed_bps(entry: float, exit_price: float, side: str) -> float:
    if entry <= 0 or exit_price <= 0:
        return 0.0
    sign = 1 if side == "buy" else -1 if side == "sell" else 0
    if sign == 0:
        return 0.0
    return sign * math.log(max(exit_price, 1e-12) / max(entry, 1e-12)) * 10000.0


def _trade_strategy_id(trade: dict[str, Any]) -> str:
    return str(trade.get("trade_strategy_id") or trade.get("strategy_id") or "").strip().upper()


def _trade_asset(trade: dict[str, Any]) -> str:
    return str(trade.get("asset") or "").strip().upper()


def _trade_venue(trade: dict[str, Any]) -> str:
    return str(trade.get("venue") or "").strip()


def _trade_session(trade: dict[str, Any]) -> str:
    return str(trade.get("bucket_session") or "").strip()


def _trade_side(trade: dict[str, Any]) -> str:
    return str(trade.get("side") or "").strip().lower()


def _score_band(row: dict[str, Any]) -> str:
    existing = str(row.get("trade_score_band") or "").strip()
    if existing:
        return existing
    score = int(_safe_float(row.get("trade_present_score")))
    if score <= 0:
        return "none"
    if score < 40:
        return "0_39"
    if score < 55:
        return "40_54"
    if score < 70:
        return "55_69"
    if score < 85:
        return "70_84"
    return "85_100"


def _signed_bps_band(value: Any) -> str:
    bps = _safe_float(value)
    if bps <= -20:
        return "down_extreme_le_-20"
    if bps <= -10:
        return "down_extended_-20_-10"
    if bps <= -5:
        return "down_edge_-10_-5"
    if bps < 0:
        return "down_small_-5_0"
    if bps == 0:
        return "flat_0"
    if bps < 5:
        return "up_small_0_5"
    if bps < 10:
        return "up_edge_5_10"
    if bps < 20:
        return "up_extended_10_20"
    return "up_extreme_ge_20"


def _pressure_relation(row: dict[str, Any]) -> str:
    side = _trade_side(row)
    pressure = str(row.get("pressure_watch_direction") or "").strip().lower()
    if side not in {"buy", "sell"} or pressure not in {"buy", "sell"}:
        value = str(row.get("pressure_relation") or "").strip()
        return value or "none"
    return "aligned" if side == pressure else "fade_pressure"


def _move_shape_category(row: dict[str, Any]) -> str:
    existing = str(row.get("move_shape_category") or "").strip()
    if existing:
        return existing
    side = _trade_side(row)
    chunk = _signed_bps_band(row.get("trade_current_chunk_bps"))
    recent = _signed_bps_band(row.get("trade_recent_2chunk_bps"))
    onset = _signed_bps_band(row.get("trade_from_onset_bps"))
    pressure = _pressure_relation(row)
    if side == "sell" and chunk == "up_small_0_5" and recent == "up_small_0_5":
        return "small_up_sell_fade"
    if side == "sell" and chunk in {"up_edge_5_10", "up_extended_10_20", "up_extreme_ge_20"}:
        return "extended_up_sell_fade"
    if side == "sell" and recent in {"down_small_-5_0", "down_edge_-10_-5", "down_extended_-20_-10", "down_extreme_le_-20"}:
        return "sell_down_continuation"
    if side == "buy" and chunk == "down_small_-5_0" and recent == "down_small_-5_0":
        return "small_down_buy_fade"
    if side == "buy" and chunk in {"down_edge_-10_-5", "down_extended_-20_-10", "down_extreme_le_-20"}:
        return "extended_down_buy_fade"
    if side == "buy" and recent in {"up_small_0_5", "up_edge_5_10", "up_extended_10_20", "up_extreme_ge_20"}:
        return "buy_up_continuation"
    if side == "sell" and onset == "up_small_0_5":
        return "onset_small_up_sell_fade"
    if side == "sell" and pressure == "fade_pressure":
        return "generic_sell_fade"
    if side == "buy" and pressure == "fade_pressure":
        return "generic_buy_fade"
    return f"{side or 'no_side'}_{chunk}_{recent}"


def _oracle_memory_key_values(row: dict[str, Any]) -> dict[str, str]:
    return {
        "family": _trade_strategy_id(row),
        "asset": _trade_asset(row),
        "venue": _trade_venue(row).lower(),
        "side": _trade_side(row),
        "session": _trade_session(row).lower(),
        "stage": str(row.get("trade_stage") or "").strip().lower(),
        "score": _score_band(row),
        "move": _move_shape_category(row),
        "onset": str(row.get("onset_move_band") or _signed_bps_band(row.get("trade_from_onset_bps"))).strip(),
        "chunk": str(row.get("current_chunk_band") or _signed_bps_band(row.get("trade_current_chunk_bps"))).strip(),
        "recent2": str(row.get("recent_2chunk_band") or _signed_bps_band(row.get("trade_recent_2chunk_bps"))).strip(),
        "pressure": _pressure_relation(row),
    }


def _oracle_memory_route_keys(row: dict[str, Any]) -> list[tuple[str, str]]:
    values = _oracle_memory_key_values(row)
    base = [values["family"], values["asset"], values["venue"], values["side"]]
    return [
        ("exact_trait", _route_token("exact_trait", *base, values["session"], values["stage"], values["score"], values["move"], values["onset"], values["chunk"], values["recent2"], values["pressure"])),
        ("shape_score", _route_token("shape_score", *base, values["session"], values["score"], values["move"])),
        ("shape", _route_token("shape", *base, values["session"], values["move"])),
        ("route_score", _route_token("route_score", *base, values["session"], values["score"])),
        ("route_session", _route_token("route_session", *base, values["session"])),
        ("route", _route_token("route", *base)),
    ]


def _route_token(*parts: str) -> str:
    return "|".join(str(part or "").strip() for part in parts)


def _counterfactual_selection_policy(candidate_id: str) -> dict[str, Any]:
    candidate_id = str(candidate_id or "").strip()
    if candidate_id.startswith("fixed_hold_") and "_after_" in candidate_id:
        raw = candidate_id.replace("fixed_hold_", "").split("m_after_", 1)[0]
        try:
            horizon = int(raw)
        except ValueError:
            horizon = 0
        start_label = candidate_id.split("m_after_", 1)[1]
        selected_class = "fixed_hold_after_runtime_exit"
        if start_label == "entry":
            selected_class = "fixed_hold_after_entry"
        return {
            "selected_counterfactual_class": selected_class,
            "fixed_hold_minutes": horizon,
            "fixed_hold_start": start_label,
            "preferred_exit_config_level": "",
        }
    if candidate_id.startswith("actual_exit::"):
        profile = candidate_id.split("::", 1)[1]
        preferred = ""
        if profile.startswith("bucket_counterfactual"):
            preferred = "bucket"
        elif profile.startswith("family_counterfactual"):
            preferred = "family"
        elif profile.startswith("venue_counterfactual"):
            preferred = "venue"
        elif profile.startswith("gated_profitable"):
            preferred = "gated"
        return {
            "selected_counterfactual_class": "actual_exit",
            "actual_exit_profile_id": profile,
            "preferred_exit_config_level": preferred,
        }
    return {
        "selected_counterfactual_class": "unknown",
        "preferred_exit_config_level": "",
    }


def _runtime_counterfactual_allowed_fixed_hold_minutes(scenario: dict[str, Any] | None) -> set[int]:
    scenario = scenario or {}
    raw = scenario.get("counterfactual_exit_selector_allowed_horizons_minutes")
    if raw is None:
        raw = scenario.get("counterfactual_exit_selector_allowed_fixed_hold_minutes")
    if raw is None:
        raw = DEFAULT_RUNTIME_COUNTERFACTUAL_FIXED_HOLD_MINUTES
    if isinstance(raw, str):
        values = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        values = [raw]
    allowed: set[int] = set()
    for value in values:
        try:
            minutes = int(float(value or 0))
        except (TypeError, ValueError):
            continue
        if minutes > 0:
            allowed.add(minutes)
    return allowed


def _runtime_counterfactual_candidate_allowed(candidate_id: str, scenario: dict[str, Any] | None) -> bool:
    policy = _counterfactual_selection_policy(candidate_id)
    selected_class = str(policy.get("selected_counterfactual_class") or "")
    if selected_class == "actual_exit":
        return True
    if selected_class in {"fixed_hold_after_entry", "fixed_hold_after_runtime_exit"}:
        return int(policy.get("fixed_hold_minutes") or 0) in _runtime_counterfactual_allowed_fixed_hold_minutes(scenario)
    return False


def runtime_counterfactual_exit_selection_allowed(
    selection: dict[str, Any] | None,
    scenario: dict[str, Any] | None = None,
) -> bool:
    if not isinstance(selection, dict) or not selection:
        return False
    return _runtime_counterfactual_candidate_allowed(str(selection.get("selected_counterfactual_id") or ""), scenario)


def _runtime_counterfactual_rows_path() -> Path:
    if _RUNTIME_COUNTERFACTUAL_POLICY_ROWS_PATH.exists():
        return _RUNTIME_COUNTERFACTUAL_POLICY_ROWS_PATH
    return _RUNTIME_COUNTERFACTUAL_ROWS_PATH


def _runtime_counterfactual_selector_index(policy_epoch_id: str = "") -> dict[str, Any]:
    global _RUNTIME_COUNTERFACTUAL_SELECTOR_CACHE
    rows_path = _runtime_counterfactual_rows_path()
    try:
        stat = rows_path.stat()
    except OSError:
        return {}
    policy_epoch_id = str(policy_epoch_id or "").strip()
    cache_key = f"{rows_path}:{stat.st_mtime_ns}:{policy_epoch_id}"
    if _RUNTIME_COUNTERFACTUAL_SELECTOR_CACHE.get("cache_key") == cache_key:
        return dict(_RUNTIME_COUNTERFACTUAL_SELECTOR_CACHE.get("index") or {})

    groups: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {
        "count": 0.0,
        "runtime_net": 0.0,
        "counterfactual_net": 0.0,
        "incremental": 0.0,
        "wins": 0.0,
    }))
    try:
        with rows_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("status") or "").strip().lower() != "closed":
                    continue
                if policy_epoch_id and str(row.get("policy_epoch_id") or "").strip() != policy_epoch_id:
                    continue
                runtime_candidate_id = str(row.get("cf_best_runtime_executable_id") or "").strip()
                candidate_id = runtime_candidate_id or str(row.get("cf_best_executable_id") or "").strip()
                if not candidate_id:
                    continue
                if str(_counterfactual_selection_policy(candidate_id).get("selected_counterfactual_class") or "") == "unknown":
                    continue
                family = str(row.get("family") or row.get("trade_strategy_id") or "").strip().upper()
                asset = str(row.get("asset") or "").strip().upper()
                venue = str(row.get("venue") or "").strip().lower()
                side = str(row.get("side") or "").strip().lower()
                if not family or side not in {"buy", "sell"}:
                    continue
                runtime_net = _safe_float(row.get("runtime_net_pnl_usd_at_target_notional"))
                if runtime_candidate_id:
                    cf_net = _safe_float(row.get("cf_best_runtime_executable_net_pnl_usd_at_target_notional"))
                    incremental = _safe_float(
                        row.get("cf_best_runtime_executable_incremental_vs_runtime_usd_at_target_notional")
                    )
                else:
                    cf_net = _safe_float(row.get("cf_best_executable_net_pnl_usd_at_target_notional"))
                    incremental = _safe_float(row.get("cf_best_executable_incremental_vs_runtime_usd_at_target_notional"))
                row_for_key = dict(row)
                row_for_key["trade_strategy_id"] = family
                row_for_key["asset"] = asset
                row_for_key["venue"] = venue
                row_for_key["side"] = side
                keys = [key for _level, key in _oracle_memory_route_keys(row_for_key)]
                for key in keys:
                    bucket = groups[key][candidate_id]
                    bucket["count"] += 1.0
                    bucket["runtime_net"] += runtime_net
                    bucket["counterfactual_net"] += cf_net
                    bucket["incremental"] += incremental
                    bucket["wins"] += 1.0 if cf_net > 0 else 0.0
    except (OSError, csv.Error):
        return {}

    selections: dict[str, dict[str, Any]] = {}
    for key, candidates in groups.items():
        viable = [
            (candidate_id, stats)
            for candidate_id, stats in candidates.items()
            if stats["count"] > 0 and stats["incremental"] > 0
        ]
        if not viable:
            continue
        candidate_id, stats = sorted(
            viable,
            key=lambda item: (
                float(item[1]["incremental"]),
                float(item[1]["counterfactual_net"]),
                float(item[1]["count"]),
            ),
            reverse=True,
        )[0]
        ranked_candidates = [
            {
                "candidate_id": cid,
                "count": int(data["count"]),
                "runtime_net": round(float(data["runtime_net"]), 6),
                "incremental": round(float(data["incremental"]), 6),
                "counterfactual_net": round(float(data["counterfactual_net"]), 6),
                "win_rate": round(float(data["wins"]) / float(data["count"]), 6) if data["count"] else None,
            }
            for cid, data in sorted(
                candidates.items(),
                key=lambda item: (
                    float(item[1]["incremental"]),
                    float(item[1]["counterfactual_net"]),
                    float(item[1]["count"]),
                ),
                reverse=True,
            )
        ]
        selections[key] = {
            "candidate_id": candidate_id,
            "count": int(stats["count"]),
            "runtime_net": round(float(stats["runtime_net"]), 6),
            "counterfactual_net": round(float(stats["counterfactual_net"]), 6),
            "incremental": round(float(stats["incremental"]), 6),
            "win_rate": round(float(stats["wins"]) / float(stats["count"]), 6) if stats["count"] else None,
            "top_candidates": ranked_candidates[:8],
            "ranked_candidates": ranked_candidates,
        }
    index = {
        "source_path": str(rows_path),
        "selections": selections,
    }
    _RUNTIME_COUNTERFACTUAL_SELECTOR_CACHE = {"cache_key": cache_key, "mtime_ns": stat.st_mtime_ns, "index": index}
    return dict(index)


def runtime_counterfactual_exit_selection_for_trade(
    trade: dict[str, Any],
    scenario: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenario = scenario or {}
    if not bool(scenario.get("counterfactual_exit_selector_enabled")):
        return {}
    policy_epoch_id = ""
    if bool(scenario.get("counterfactual_exit_selector_policy_epoch_only")):
        policy_epoch_id = str(
            scenario.get("policy_epoch_id")
            or trade.get("policy_epoch_id")
            or ""
        ).strip()
    family = _trade_strategy_id(trade)
    side = _trade_side(trade)
    if not family or side not in {"buy", "sell"}:
        return {}
    asset = _trade_asset(trade)
    venue = _trade_venue(trade).lower()
    route_keys = _oracle_memory_route_keys(trade)
    min_count = max(1, int(scenario.get("counterfactual_exit_selector_min_count") or 3))
    min_net = float(scenario.get("counterfactual_exit_selector_min_net_usd_at_target_notional") or 0.0)
    min_win_rate_raw = scenario.get("counterfactual_exit_selector_min_win_rate")
    min_win_rate = float(min_win_rate_raw) if min_win_rate_raw is not None else 0.0
    def select_from_index(index: dict[str, Any], source_scope: str) -> dict[str, Any]:
        selections = index.get("selections") or {}
        if not isinstance(selections, dict) or not selections:
            return {}
        for level, key in route_keys:
            selected = selections.get(key)
            if not isinstance(selected, dict):
                continue
            count = int(selected.get("count") or 0)
            if count < min_count:
                continue
            candidates = selected.get("ranked_candidates") or selected.get("top_candidates") or []
            if not isinstance(candidates, list) or not candidates:
                candidates = [selected]
            allowed_candidates = [
                candidate for candidate in candidates
                if isinstance(candidate, dict)
                and _runtime_counterfactual_candidate_allowed(str(candidate.get("candidate_id") or ""), scenario)
                and int(candidate.get("count") or 0) >= min_count
                and float(candidate.get("counterfactual_net") or 0.0) > min_net
                and (
                    min_win_rate <= 0.0
                    or candidate.get("win_rate") is None
                    or float(candidate.get("win_rate") or 0.0) >= min_win_rate
                )
            ]
            if not allowed_candidates:
                continue
            candidate = allowed_candidates[0]
            candidate_id = str(candidate.get("candidate_id") or "").strip()
            return {
                "schema": "runtime_counterfactual_exit_selection_v1",
                "source_path": str(index.get("source_path") or _RUNTIME_COUNTERFACTUAL_ROWS_PATH),
                "source_scope": source_scope,
                "active_policy_epoch_id": policy_epoch_id,
                "selection_level": level,
                "selection_key": key,
                "selected_counterfactual_id": candidate_id,
                "sample_count": int(candidate.get("count") or count),
                "runtime_net_usd_at_target_notional": candidate.get("runtime_net", selected.get("runtime_net")),
                "counterfactual_net_usd_at_target_notional": candidate.get("counterfactual_net", selected.get("counterfactual_net")),
                "incremental_usd_at_target_notional": candidate.get("incremental", selected.get("incremental")),
                "counterfactual_win_rate": candidate.get("win_rate", selected.get("win_rate")),
                "allowed_fixed_hold_minutes": sorted(_runtime_counterfactual_allowed_fixed_hold_minutes(scenario)),
                "top_candidates": selected.get("top_candidates") or [],
                **_counterfactual_selection_policy(candidate_id),
            }
        return {}

    scoped = select_from_index(_runtime_counterfactual_selector_index(policy_epoch_id), "active_policy_epoch")
    if scoped:
        return scoped
    if policy_epoch_id and bool(scenario.get("counterfactual_exit_selector_allow_policy_source_fallback")):
        fallback = select_from_index(_runtime_counterfactual_selector_index(""), "strict_policy_source_fallback")
        if fallback:
            fallback["fallback_reason"] = "no_qualified_active_epoch_candidate"
            return fallback
    return {}


def _historic_selector_index() -> dict[str, Any]:
    global _HISTORIC_SELECTOR_CACHE
    try:
        stat = _WINNER_PNL_ASSIGNMENTS_PATH.stat()
    except OSError:
        return {}
    if _HISTORIC_SELECTOR_CACHE.get("mtime_ns") == stat.st_mtime_ns:
        return dict(_HISTORIC_SELECTOR_CACHE.get("index") or {})
    try:
        payload = json.loads(_WINNER_PNL_ASSIGNMENTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    assignments = payload.get("assignments") if isinstance(payload, dict) else []
    bucket_counts: dict[str, Counter[str]] = defaultdict(Counter)
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    global_counts: Counter[str] = Counter()
    for row in assignments if isinstance(assignments, list) else []:
        if not isinstance(row, dict):
            continue
        selected = str(row.get("best_executable_pnl_strategy_id") or "").strip()
        family = str(row.get("entry_strategy_id") or "").strip().upper()
        bucket = str(row.get("bucket_key") or "").strip()
        if not selected or not family:
            continue
        global_counts[selected] += 1
        family_counts[family][selected] += 1
        if bucket:
            bucket_counts[bucket][selected] += 1
    index = {
        "bucket": {key: dict(value) for key, value in bucket_counts.items()},
        "family": {key: dict(value) for key, value in family_counts.items()},
        "global": dict(global_counts),
        "source_path": str(_WINNER_PNL_ASSIGNMENTS_PATH),
    }
    _HISTORIC_SELECTOR_CACHE = {"mtime_ns": stat.st_mtime_ns, "index": index}
    return dict(index)


def _historic_selection_policy(strategy_id: str) -> dict[str, Any]:
    strategy_id = str(strategy_id or "")
    if strategy_id.startswith("fixed_hold_") and strategy_id.endswith("m_after_actual_exit"):
        raw = strategy_id.replace("fixed_hold_", "").split("m_after_actual_exit", 1)[0]
        try:
            horizon = int(raw)
        except ValueError:
            horizon = 0
        return {
            "selected_pnl_strategy_class": "fixed_hold_after_actual_exit",
            "fixed_hold_after_exit_minutes": horizon,
            "preferred_exit_config_level": "",
        }
    if strategy_id.startswith("actual_exit::"):
        profile = strategy_id.split("::", 1)[1]
        preferred = ""
        if profile.startswith("bucket_counterfactual"):
            preferred = "bucket"
        elif profile.startswith("family_counterfactual"):
            preferred = "family"
        elif profile.startswith("venue_counterfactual"):
            preferred = "venue"
        elif profile.startswith("gated_profitable"):
            preferred = "gated"
        return {
            "selected_pnl_strategy_class": "actual_exit",
            "actual_exit_profile_id": profile,
            "preferred_exit_config_level": preferred,
        }
    return {
        "selected_pnl_strategy_class": "unknown",
        "preferred_exit_config_level": "",
    }


def _historic_selection_from_counts(counts: dict[str, int], level: str, key: str) -> dict[str, Any]:
    counter = Counter({str(k): int(v) for k, v in counts.items() if str(k)})
    if not counter:
        return {}
    selected, selected_count = counter.most_common(1)[0]
    return {
        "schema": "historic_parity_exit_selection_v1",
        "source_path": str(_WINNER_PNL_ASSIGNMENTS_PATH),
        "selection_level": level,
        "selection_key": key,
        "selected_pnl_strategy_id": selected,
        "sample_count": int(sum(counter.values())),
        "selected_count": int(selected_count),
        "strategy_counts": counter.most_common(8),
        **_historic_selection_policy(selected),
    }


def historic_parity_exit_selection_for_trade(trade: dict[str, Any]) -> dict[str, Any]:
    index = _historic_selector_index()
    if not index:
        return {}
    strategy = _trade_strategy_id(trade)
    if not strategy:
        return {}
    bucket_key = "|".join([strategy, _trade_asset(trade), _trade_venue(trade), _trade_session(trade)])
    bucket_counts = (index.get("bucket") or {}).get(bucket_key)
    if isinstance(bucket_counts, dict) and bucket_counts:
        return _historic_selection_from_counts(bucket_counts, "bucket", bucket_key)
    family_counts = (index.get("family") or {}).get(strategy)
    if isinstance(family_counts, dict) and family_counts:
        return _historic_selection_from_counts(family_counts, "family", strategy)
    global_counts = index.get("global")
    if isinstance(global_counts, dict) and global_counts:
        return _historic_selection_from_counts(global_counts, "global", "GLOBAL")
    return {}


def exit_config_for_trade(trade: dict[str, Any], scenario: dict[str, Any]) -> tuple[dict[str, Any], str]:
    pairing = family_exit_pairing_for_trade(trade, scenario)
    if pairing:
        return pairing, "family_exit_pairing"
    maps = scenario.get("exit_params_map") or {}
    if not isinstance(maps, dict):
        return {}, ""
    strategy = _trade_strategy_id(trade)
    asset = _trade_asset(trade)
    venue = _trade_venue(trade)
    session = _trade_session(trade)
    bucket_key = "|".join([strategy, asset, venue, session])
    venue_key = "|".join([strategy, asset, venue])
    family_venue_key = "|".join([strategy, venue])
    family_key = strategy
    runtime_selection = (
        trade.get("runtime_counterfactual_exit_selection")
        if isinstance(trade.get("runtime_counterfactual_exit_selection"), dict)
        else {}
    )
    historic_selection = (
        trade.get("historic_parity_exit_selection")
        if isinstance(trade.get("historic_parity_exit_selection"), dict)
        else {}
    )
    selection = runtime_selection or historic_selection
    preferred = str(selection.get("preferred_exit_config_level") or "").lower()
    if preferred == "gated":
        return {}, ""
    lookup_map = {
        "bucket": (maps.get("bucket_params") or maps.get("params") or {}).get(bucket_key),
        "venue": (maps.get("venue_params") or {}).get(venue_key),
        "family_venue": (maps.get("family_venue_defaults") or {}).get(family_venue_key),
        "family": (maps.get("family_params") or maps.get("family_defaults") or {}).get(family_key),
    }
    order = ["bucket", "venue", "family_venue", "family"]
    if preferred in {"bucket", "venue", "family_venue", "family"}:
        order = [preferred, *[item for item in order if item != preferred]]
    lookups = [
        (level, lookup_map.get(level))
        for level in order
    ]
    defaults = maps.get("defaults") or {}
    if isinstance(defaults, dict):
        default_families = defaults.get("family") or {}
        lookups.append(("default_family", default_families.get(family_key) if isinstance(default_families, dict) else None))
        lookups.append(("default_global", defaults.get("global")))
    for level, cfg in lookups:
        if isinstance(cfg, dict):
            out = dict(cfg)
            out["config_level"] = level
            out["config_key"] = {
                "bucket": bucket_key,
                "venue": venue_key,
                "family_venue": family_venue_key,
                "family": family_key,
                "default_family": family_key,
                "default_global": "GLOBAL",
            }[level]
            return out, level
    return {}, ""


def exit_profile_for_trade(trade: dict[str, Any], scenario: dict[str, Any]) -> tuple[ExitProfile, dict[str, Any]]:
    base = exit_profile_from_scenario(scenario)
    cfg, level = exit_config_for_trade(trade, scenario)
    if not cfg:
        return base, {}
    if level == "family_exit_pairing":
        profile_id = str(cfg.get("exit_profile_id") or base.profile_id)
        label = str(cfg.get("label") or "Family exit pairing")
    else:
        profile_id = f"{level}_counterfactual_runner_exits_v1"
        label = f"{level.title()} counterfactual partial-runner exits"
    if _is_exit_profile_disabled(profile_id):
        return base, {}
    profile = ExitProfile(
        profile_id=profile_id,
        label=label,
        family_hint=base.family_hint or _trade_strategy_id(trade),
        score_exit_min_hold_minutes=float(
            cfg.get("min_hold_minutes") or cfg.get("score_exit_min_hold_minutes") or base.score_exit_min_hold_minutes
        ),
        score_exit_min_profit_bps=float(
            cfg.get("min_profit_bps_for_score_exit")
            or cfg.get("score_exit_min_profit_bps")
            or base.score_exit_min_profit_bps
        ),
        profitable_hold_extension_minutes=float(
            cfg.get("profitable_hold_extension_minutes") or base.profitable_hold_extension_minutes
        ),
        tp1_bps=float(cfg.get("tp1_bps") or base.tp1_bps),
        scale_out_fraction=float(cfg.get("scale_out_fraction") or base.scale_out_fraction),
        runner_trail_bps=float(cfg.get("trail_bps") or cfg.get("runner_trail_bps") or base.runner_trail_bps),
        max_hold_minutes=float(cfg.get("max_hold_minutes") or base.max_hold_minutes),
        counterfactual_horizon_minutes=base.counterfactual_horizon_minutes,
        under_gate_trim_fraction=float(cfg.get("under_gate_trim_fraction") or base.under_gate_trim_fraction),
        news_can_full_flat_profitable=bool(cfg.get("news_can_full_flat_profitable", base.news_can_full_flat_profitable)),
        gate_profitable_score_exits=base.gate_profitable_score_exits,
        gate_profitable_news_exits=base.gate_profitable_news_exits,
        gate_profitable_pressure_exits=base.gate_profitable_pressure_exits,
        gate_profitable_setup_exits=base.gate_profitable_setup_exits,
        defer_unprofitable_pressure_exits=bool(
            cfg.get("defer_unprofitable_pressure_exits", base.defer_unprofitable_pressure_exits)
        ),
    )
    return profile, cfg


def unrealized_bps(trade: dict[str, Any], bid: float, ask: float, mid: float) -> float:
    exit_price = bid if trade["side"] == "buy" else ask
    if exit_price <= 0:
        exit_price = mid
    return _signed_bps(float(trade.get("fill_price") or 0.0), float(exit_price), str(trade.get("side") or ""))


def net_unrealized_bps(trade: dict[str, Any], unreal_bps: float) -> float:
    fee_bps = float(trade.get("fee_bps") or _PRACTICE_FEE_BPS)
    return float(unreal_bps) - (2.0 * fee_bps)


def _gate_enabled(profile: ExitProfile, reason: str) -> bool:
    if reason in {"present_score_degraded", "present_score_dropped_from_entry"}:
        return profile.gate_profitable_score_exits
    if reason in {"news_started_exit_longs", "news_started_exit_shorts"}:
        return profile.gate_profitable_news_exits
    if reason == "pressure_flipped":
        return profile.gate_profitable_pressure_exits
    if reason in {"setup_late", "setup_blocker"}:
        return profile.gate_profitable_setup_exits
    return True


def profitable_exit_gate_signal(
    trade: dict[str, Any],
    profile: ExitProfile,
    net_bps: float,
    elapsed_min: float,
    reason: str,
) -> dict[str, Any] | None:
    if net_bps <= 0 or not _gate_enabled(profile, reason):
        return None
    if elapsed_min >= profile.score_exit_min_hold_minutes and net_bps >= profile.score_exit_min_profit_bps:
        return None
    return {
        "reason": reason,
        "elapsed_min": round(float(elapsed_min), 4),
        "net_unrealized_bps": round(float(net_bps), 4),
        "required_min_hold_minutes": profile.score_exit_min_hold_minutes,
        "required_min_profit_bps": profile.score_exit_min_profit_bps,
        "exit_profile_id": profile.profile_id,
    }


def _decision(
    action: str,
    reason: str,
    profile: ExitProfile,
    unreal_bps: float,
    net_bps: float,
    elapsed_min: float,
    deferred_signal: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ExitDecision:
    return ExitDecision(
        action=action,
        reason=reason,
        profile_id=profile.profile_id,
        unrealized_bps=round(float(unreal_bps), 6),
        net_unrealized_bps=round(float(net_bps), 6),
        elapsed_min=round(float(elapsed_min), 6),
        deferred=bool(deferred_signal),
        deferred_signal=deferred_signal,
        metadata=metadata or {},
    )


def apply_historic_parity_exit_selector(
    trade: dict[str, Any],
    scenario: dict[str, Any],
    decision: ExitDecision,
) -> ExitDecision:
    if not bool(scenario.get("historic_parity_exit_selector_enabled")):
        return decision
    selection = trade.get("historic_parity_exit_selection")
    if not isinstance(selection, dict):
        return decision
    if str(selection.get("selected_pnl_strategy_class") or "") != "fixed_hold_after_actual_exit":
        return decision
    if decision.action != "close":
        return decision
    hard_reasons = {"stop_loss", "early_loss_cut"}
    if decision.reason in hard_reasons and not bool(scenario.get("historic_parity_defer_hard_exits")):
        return decision
    horizon = int(selection.get("fixed_hold_after_exit_minutes") or 0)
    if horizon <= 0:
        return decision
    first_elapsed = trade.get("historic_parity_first_exit_signal_elapsed_min")
    if first_elapsed is None:
        first_elapsed = float(decision.elapsed_min)
        trade["historic_parity_first_exit_signal_elapsed_min"] = float(first_elapsed)
        trade["historic_parity_first_exit_signal_reason"] = str(decision.reason or "")
        trade["historic_parity_first_exit_signal_profile_id"] = str(decision.profile_id or "")
        trade["historic_parity_fixed_hold_due_elapsed_min"] = float(first_elapsed) + float(horizon)
    due_elapsed = float(trade.get("historic_parity_fixed_hold_due_elapsed_min") or (float(first_elapsed) + float(horizon)))
    metadata = {
        **(decision.metadata or {}),
        "historic_parity_exit_selection": selection,
        "first_exit_signal_elapsed_min": round(float(first_elapsed), 6),
        "due_elapsed_min": round(float(due_elapsed), 6),
    }
    if float(decision.elapsed_min) + 1e-9 < due_elapsed:
        deferred_signal = {
            "reason": decision.reason,
            "elapsed_min": round(float(decision.elapsed_min), 4),
            "net_unrealized_bps": round(float(decision.net_unrealized_bps), 4),
            "exit_profile_id": decision.profile_id,
            "action": "historic_parity_fixed_hold_after_actual_exit",
            "hold_after_exit_signal_minutes": horizon,
            "due_elapsed_min": round(float(due_elapsed), 4),
        }
        return ExitDecision(
            action="hold",
            reason=f"historic_parity_hold_{horizon}m_after_actual_exit_signal",
            profile_id=decision.profile_id,
            unrealized_bps=decision.unrealized_bps,
            net_unrealized_bps=decision.net_unrealized_bps,
            elapsed_min=decision.elapsed_min,
            deferred=True,
            deferred_signal=deferred_signal,
            metadata=metadata,
        )
    return ExitDecision(
        action="close",
        reason=f"historic_parity_fixed_hold_{horizon}m_after_actual_exit",
        profile_id=decision.profile_id,
        unrealized_bps=decision.unrealized_bps,
        net_unrealized_bps=decision.net_unrealized_bps,
        elapsed_min=decision.elapsed_min,
        deferred=False,
        deferred_signal=None,
        metadata=metadata,
    )


def apply_runtime_counterfactual_exit_selector(
    trade: dict[str, Any],
    scenario: dict[str, Any],
    decision: ExitDecision,
) -> ExitDecision:
    if not bool(scenario.get("counterfactual_exit_selector_enabled")):
        return decision
    selection = trade.get("runtime_counterfactual_exit_selection")
    if not isinstance(selection, dict) or not selection:
        return decision
    selected_class = str(selection.get("selected_counterfactual_class") or "")
    if selected_class not in {"fixed_hold_after_entry", "fixed_hold_after_runtime_exit"}:
        return decision
    horizon = int(selection.get("fixed_hold_minutes") or 0)
    if horizon <= 0:
        return decision

    hard_reasons = {"stop_loss", "early_loss_cut"}
    if decision.reason in BANK_PROGRESS_EXIT_REASONS:
        return decision
    defer_hard = bool(scenario.get("counterfactual_exit_selector_defer_hard_exits", True))
    if decision.reason in hard_reasons and not defer_hard:
        return decision

    metadata = {
        **(decision.metadata or {}),
        "runtime_counterfactual_exit_selection": selection,
    }
    oracle_source = str(selection.get("source_scope") or "") == "oracle_winner_source_of_truth"
    bank_counted_trade = (
        bool(trade.get("pnl_counted_as_real"))
        or float(trade.get("bank_allocated_notional_usd") or 0.0) > 0.0
        or float(trade.get("real_mock_notional_usd") or 0.0) > 0.0
    )
    elapsed = float(decision.elapsed_min)
    min_close_net_bps = float(scenario.get("counterfactual_exit_selector_min_close_net_bps") or 0.0)
    if selected_class == "fixed_hold_after_entry":
        due_elapsed = float(horizon)
        metadata["due_elapsed_min"] = round(due_elapsed, 6)
        if elapsed + 1e-9 < due_elapsed:
            deferred_signal = {
                "reason": decision.reason or "fixed_hold_after_entry",
                "elapsed_min": round(elapsed, 4),
                "net_unrealized_bps": round(float(decision.net_unrealized_bps), 4),
                "exit_profile_id": decision.profile_id,
                "action": "runtime_counterfactual_fixed_hold_after_entry",
                "hold_minutes": horizon,
                "due_elapsed_min": round(due_elapsed, 4),
            }
            return ExitDecision(
                action="hold",
                reason=f"runtime_counterfactual_hold_{horizon}m_after_entry",
                profile_id=decision.profile_id,
                unrealized_bps=decision.unrealized_bps,
                net_unrealized_bps=decision.net_unrealized_bps,
                elapsed_min=decision.elapsed_min,
                deferred=True,
                deferred_signal=deferred_signal,
                metadata=metadata,
            )
        if (
            (not oracle_source or bank_counted_trade)
            and float(decision.net_unrealized_bps) < min_close_net_bps
            and decision.reason not in hard_reasons
        ):
            deferred_signal = {
                "reason": decision.reason or "fixed_hold_after_entry_due_but_negative",
                "elapsed_min": round(elapsed, 4),
                "net_unrealized_bps": round(float(decision.net_unrealized_bps), 4),
                "exit_profile_id": decision.profile_id,
                "action": "runtime_counterfactual_wait_for_positive_after_entry_due",
                "hold_minutes": horizon,
                "due_elapsed_min": round(due_elapsed, 4),
                "min_close_net_bps": round(min_close_net_bps, 4),
                "fee_aware_bank_exit": bool(bank_counted_trade),
            }
            return ExitDecision(
                action="hold",
                reason=f"runtime_counterfactual_wait_positive_{horizon}m_after_entry",
                profile_id=decision.profile_id,
                unrealized_bps=decision.unrealized_bps,
                net_unrealized_bps=decision.net_unrealized_bps,
                elapsed_min=decision.elapsed_min,
                deferred=True,
                deferred_signal=deferred_signal,
                metadata=metadata,
            )
        return ExitDecision(
            action="close",
            reason=f"runtime_counterfactual_fixed_hold_{horizon}m_after_entry",
            profile_id=decision.profile_id,
            unrealized_bps=decision.unrealized_bps,
            net_unrealized_bps=decision.net_unrealized_bps,
            elapsed_min=decision.elapsed_min,
            deferred=False,
            deferred_signal=None,
            metadata=metadata,
        )

    due_elapsed_raw = trade.get("runtime_counterfactual_fixed_hold_due_elapsed_min")
    if due_elapsed_raw is not None:
        due_elapsed = float(due_elapsed_raw)
        metadata["due_elapsed_min"] = round(due_elapsed, 6)
        if elapsed + 1e-9 >= due_elapsed:
            if (
                (not oracle_source or bank_counted_trade)
                and float(decision.net_unrealized_bps) < min_close_net_bps
                and decision.reason not in hard_reasons
            ):
                deferred_signal = {
                    "reason": decision.reason or "fixed_hold_after_runtime_exit_due_but_negative",
                    "elapsed_min": round(elapsed, 4),
                    "net_unrealized_bps": round(float(decision.net_unrealized_bps), 4),
                    "exit_profile_id": decision.profile_id,
                    "action": "runtime_counterfactual_wait_for_positive_after_runtime_exit_due",
                    "hold_after_exit_signal_minutes": horizon,
                    "due_elapsed_min": round(due_elapsed, 4),
                    "min_close_net_bps": round(min_close_net_bps, 4),
                    "fee_aware_bank_exit": bool(bank_counted_trade),
                }
                return ExitDecision(
                    action="hold",
                    reason=f"runtime_counterfactual_wait_positive_{horizon}m_after_runtime_exit",
                    profile_id=decision.profile_id,
                    unrealized_bps=decision.unrealized_bps,
                    net_unrealized_bps=decision.net_unrealized_bps,
                    elapsed_min=decision.elapsed_min,
                    deferred=True,
                    deferred_signal=deferred_signal,
                    metadata=metadata,
                )
            return ExitDecision(
                action="close",
                reason=f"runtime_counterfactual_fixed_hold_{horizon}m_after_runtime_exit",
                profile_id=decision.profile_id,
                unrealized_bps=decision.unrealized_bps,
                net_unrealized_bps=decision.net_unrealized_bps,
                elapsed_min=decision.elapsed_min,
                deferred=False,
                deferred_signal=None,
                metadata=metadata,
            )
        deferred_signal = {
            "reason": decision.reason or "waiting_for_counterfactual_due",
            "elapsed_min": round(elapsed, 4),
            "net_unrealized_bps": round(float(decision.net_unrealized_bps), 4),
            "exit_profile_id": decision.profile_id,
            "action": "runtime_counterfactual_fixed_hold_after_runtime_exit_signal",
            "hold_after_exit_signal_minutes": horizon,
            "due_elapsed_min": round(due_elapsed, 4),
        }
        return ExitDecision(
            action="hold",
            reason=f"runtime_counterfactual_hold_{horizon}m_after_runtime_exit_signal",
            profile_id=decision.profile_id,
            unrealized_bps=decision.unrealized_bps,
            net_unrealized_bps=decision.net_unrealized_bps,
            elapsed_min=decision.elapsed_min,
            deferred=True,
            deferred_signal=deferred_signal,
            metadata=metadata,
        )

    if decision.action != "close" and not decision.reason:
        return decision
    if decision.action == "scale_out":
        metadata["suppressed_scale_out_reason"] = decision.reason
    first_signal_reason = decision.reason or decision.action or "runtime_exit_signal"

    first_elapsed = float(decision.elapsed_min)
    due_elapsed = first_elapsed + float(horizon)
    trade["runtime_counterfactual_first_exit_signal_elapsed_min"] = first_elapsed
    trade["runtime_counterfactual_first_exit_signal_reason"] = str(first_signal_reason)
    trade["runtime_counterfactual_first_exit_signal_profile_id"] = str(decision.profile_id or "")
    trade["runtime_counterfactual_fixed_hold_due_elapsed_min"] = due_elapsed
    metadata["first_exit_signal_elapsed_min"] = round(first_elapsed, 6)
    metadata["due_elapsed_min"] = round(due_elapsed, 6)
    deferred_signal = {
        "reason": decision.reason,
        "elapsed_min": round(elapsed, 4),
        "net_unrealized_bps": round(float(decision.net_unrealized_bps), 4),
        "exit_profile_id": decision.profile_id,
        "action": "runtime_counterfactual_fixed_hold_after_runtime_exit_signal",
        "hold_after_exit_signal_minutes": horizon,
        "due_elapsed_min": round(due_elapsed, 4),
    }
    return ExitDecision(
        action="hold",
        reason=f"runtime_counterfactual_hold_{horizon}m_after_runtime_exit_signal",
        profile_id=decision.profile_id,
        unrealized_bps=decision.unrealized_bps,
        net_unrealized_bps=decision.net_unrealized_bps,
        elapsed_min=decision.elapsed_min,
        deferred=True,
        deferred_signal=deferred_signal,
        metadata=metadata,
    )


def close_or_defer(
    trade: dict[str, Any],
    profile: ExitProfile,
    reason: str,
    unreal_bps: float,
    net_bps: float,
    elapsed_min: float,
) -> ExitDecision:
    deferred_signal = profitable_exit_gate_signal(trade, profile, net_bps, elapsed_min, reason)
    if deferred_signal:
        return _decision("hold", reason, profile, unreal_bps, net_bps, elapsed_min, deferred_signal)
    return _decision("close", reason, profile, unreal_bps, net_bps, elapsed_min)


def _is_oracle_managed_exit(trade: dict[str, Any], cfg: dict[str, Any]) -> bool:
    source = str(trade.get("trade_strategy_source_queue_action") or "")
    if source.startswith("oracle_distilled"):
        return True
    tokens = [
        trade.get("exit_config_key"),
        cfg.get("id"),
        cfg.get("role"),
        cfg.get("config_level"),
        cfg.get("label"),
    ]
    return any("oracle" in str(token).lower() for token in tokens if token is not None)


def _is_bank_counted_trade(trade: dict[str, Any]) -> bool:
    return (
        str(trade.get("pnl_accounting_role") or "") == "bank_allocated"
        or bool(trade.get("pnl_counted_as_real"))
        or _safe_float(trade.get("bank_allocated_notional_usd")) > 0.0
        or _safe_float(trade.get("real_mock_notional_usd")) > 0.0
    )


def _is_oracle_source_trade(trade: dict[str, Any]) -> bool:
    if bool(trade.get("oracle_winner_source_of_truth")):
        return True
    match = trade.get("oracle_winner_match")
    return isinstance(match, dict) and bool(match)


def _bank_progress_exit_decision(
    trade: dict[str, Any],
    scenario: dict[str, Any],
    profile: ExitProfile,
    unreal_bps: float,
    net_bps: float,
    elapsed_min: float,
) -> ExitDecision | None:
    if not bool(scenario.get("oracle_bank_progress_exit_enabled")):
        return None
    if not _is_oracle_source_trade(trade):
        return None

    max_net = max(_safe_float(trade.get("oracle_bank_max_net_unrealized_bps"), float("-inf")), float(net_bps))
    trade["oracle_bank_max_net_unrealized_bps"] = round(float(max_net), 6)
    if net_bps >= 0 and not trade.get("oracle_bank_first_fee_cover_elapsed_min"):
        trade["oracle_bank_first_fee_cover_elapsed_min"] = round(float(elapsed_min), 6)
    profit_confirm_bps = _safe_float(scenario.get("oracle_bank_profit_confirm_bps"), 20.0)
    if max_net >= profit_confirm_bps and not trade.get("oracle_bank_first_profit_confirm_elapsed_min"):
        trade["oracle_bank_first_profit_confirm_elapsed_min"] = round(float(elapsed_min), 6)

    if bool(scenario.get("oracle_bank_peak_exit_enabled")):
        peak_min = _safe_float(scenario.get("oracle_bank_peak_exit_min_net_bps"), profit_confirm_bps)
        giveback_floor = _safe_float(scenario.get("oracle_bank_peak_exit_giveback_bps"), 12.0)
        giveback_fraction = max(0.0, _safe_float(scenario.get("oracle_bank_peak_exit_giveback_fraction"), 0.25))
        if peak_min > 0 and max_net >= peak_min:
            giveback_bps = max(float(giveback_floor), float(max_net) * giveback_fraction)
            exit_floor = float(max_net) - giveback_bps
            trade["oracle_bank_peak_exit_armed"] = True
            trade["oracle_bank_peak_exit_floor_net_bps"] = round(float(exit_floor), 6)
            trade["oracle_bank_peak_exit_giveback_bps"] = round(float(giveback_bps), 6)
            if float(net_bps) <= exit_floor:
                return _decision(
                    "close",
                    "oracle_bank_peak_giveback_exit",
                    profile,
                    unreal_bps,
                    net_bps,
                    elapsed_min,
                    metadata={
                        "peak_net_unrealized_bps": round(float(max_net), 6),
                        "current_net_unrealized_bps": round(float(net_bps), 6),
                        "peak_exit_min_net_bps": round(float(peak_min), 6),
                        "peak_exit_giveback_bps": round(float(giveback_bps), 6),
                        "peak_exit_giveback_floor_bps": round(float(giveback_floor), 6),
                        "peak_exit_giveback_fraction": round(float(giveback_fraction), 6),
                        "peak_exit_floor_net_bps": round(float(exit_floor), 6),
                    },
                )

    fee_cut_min = _safe_float(scenario.get("oracle_bank_fee_cover_cut_minutes"), 15.0)
    if fee_cut_min > 0 and elapsed_min >= fee_cut_min and not trade.get("oracle_bank_first_fee_cover_elapsed_min"):
        return _decision(
            "close",
            "oracle_bank_fee_not_covered_by_15m",
            profile,
            unreal_bps,
            net_bps,
            elapsed_min,
            metadata={
                "fee_cover_cut_minutes": round(float(fee_cut_min), 6),
                "max_net_unrealized_bps": round(float(max_net), 6),
            },
        )

    rate_check_min = _safe_float(scenario.get("oracle_bank_min_net_bps_per_min_after_minutes"), 15.0)
    min_rate = _safe_float(scenario.get("oracle_bank_min_net_bps_per_min"), 0.10)
    if rate_check_min > 0 and elapsed_min >= rate_check_min and elapsed_min > 0:
        net_bps_per_min = float(net_bps) / max(float(elapsed_min), 1e-9)
        if (
            net_bps_per_min < min_rate
            and not trade.get("oracle_bank_first_profit_confirm_elapsed_min")
        ):
            return _decision(
                "close",
                "oracle_bank_slow_progress_bps_per_min",
                profile,
                unreal_bps,
                net_bps,
                elapsed_min,
                metadata={
                    "min_net_bps_per_min": round(float(min_rate), 6),
                    "net_bps_per_min": round(float(net_bps_per_min), 6),
                    "rate_check_after_minutes": round(float(rate_check_min), 6),
                    "max_net_unrealized_bps": round(float(max_net), 6),
                },
            )

    require_confirm = bool(scenario.get("oracle_bank_require_20bps_by_30m"))
    confirm_min = _safe_float(scenario.get("oracle_bank_profit_confirm_minutes"), 30.0)
    if require_confirm and confirm_min > 0 and elapsed_min >= confirm_min and max_net < profit_confirm_bps:
        return _decision(
            "close",
            "oracle_bank_no_20bps_by_30m",
            profile,
            unreal_bps,
            net_bps,
            elapsed_min,
            metadata={
                "profit_confirm_bps": round(float(profit_confirm_bps), 6),
                "profit_confirm_minutes": round(float(confirm_min), 6),
                "max_net_unrealized_bps": round(float(max_net), 6),
            },
        )
    return None


def _oracle_setup_defer_decision(
    trade: dict[str, Any],
    profile: ExitProfile,
    cfg: dict[str, Any],
    reason: str,
    unreal_bps: float,
    net_bps: float,
    elapsed_min: float,
    setup_blocker_reason: str = "",
) -> ExitDecision | None:
    if not _is_oracle_managed_exit(trade, cfg):
        return None
    under_gate = elapsed_min < profile.score_exit_min_hold_minutes or net_bps < profile.score_exit_min_profit_bps
    if not under_gate:
        return None
    deferred_signal = {
        "reason": reason,
        "setup_blocker_reason": setup_blocker_reason,
        "elapsed_min": round(float(elapsed_min), 4),
        "net_unrealized_bps": round(float(net_bps), 4),
        "required_min_hold_minutes": profile.score_exit_min_hold_minutes,
        "required_min_profit_bps": profile.score_exit_min_profit_bps,
        "exit_profile_id": profile.profile_id,
        "action": "oracle_hold_until_profit_or_hard_stop",
    }
    return _decision(
        "hold",
        reason,
        profile,
        unreal_bps,
        net_bps,
        elapsed_min,
        deferred_signal,
        metadata={"exit_config": cfg, "setup_blocker_reason": setup_blocker_reason},
    )


def _oracle_hard_stop_floor_bps(cfg: dict[str, Any], take_profit_bps: float, stop_loss_bps: float) -> float:
    configured = _safe_float(cfg.get("oracle_hard_stop_bps"))
    if configured > 0:
        return configured
    target = max(float(take_profit_bps or 0.0), float(cfg.get("take_profit_bps") or 0.0))
    return max(float(stop_loss_bps or 0.0), target * 1.5, 100.0)


def _is_score_or_news_reason(reason: str) -> bool:
    return reason in {
        "present_score_degraded",
        "present_score_dropped_from_entry",
        "news_started_exit_longs",
        "news_started_exit_shorts",
    }


def _is_news_reason(reason: str) -> bool:
    return reason in {"news_started_exit_longs", "news_started_exit_shorts"}


def _runner_stop_hit(trade: dict[str, Any], net_bps: float) -> bool:
    stop = trade.get("exit_runner_stop_net_bps")
    if stop is None:
        return False
    return float(net_bps) <= float(stop)


def _tighten_metadata(
    trade: dict[str, Any],
    profile: ExitProfile,
    net_bps: float,
    reason: str,
    aggressive: bool = False,
) -> dict[str, Any]:
    trail = max(float(profile.runner_trail_bps or 0.0), 1.0)
    if aggressive:
        trail *= 0.50
    current_stop = trade.get("exit_runner_stop_net_bps")
    new_stop = float(net_bps) - trail
    if current_stop is not None:
        new_stop = max(float(current_stop), new_stop)
    return {
        "tighten_runner_stop": True,
        "runner_stop_net_bps": round(float(new_stop), 6),
        "trail_bps": round(float(trail), 6),
        "tighten_reason": reason,
        "aggressive": bool(aggressive),
    }


def _score_news_degradation_decision(
    trade: dict[str, Any],
    profile: ExitProfile,
    reason: str,
    unreal_bps: float,
    net_bps: float,
    elapsed_min: float,
) -> ExitDecision:
    under_gate = elapsed_min < profile.score_exit_min_hold_minutes or net_bps < profile.score_exit_min_profit_bps
    if net_bps <= 0:
        deferred_signal = {
            "reason": reason,
            "elapsed_min": round(float(elapsed_min), 4),
            "net_unrealized_bps": round(float(net_bps), 4),
            "required_min_profit_bps": profile.score_exit_min_profit_bps,
            "exit_profile_id": profile.profile_id,
            "action": "hold_until_profit_or_hard_stop",
        }
        return _decision("hold", reason, profile, unreal_bps, net_bps, elapsed_min, deferred_signal)
    if _is_news_reason(reason) and not profile.news_can_full_flat_profitable:
        under_gate = True
    if under_gate:
        metadata = _tighten_metadata(trade, profile, net_bps, reason)
        if not bool(trade.get("exit_under_gate_trim_done")) and profile.under_gate_trim_fraction > 0:
            metadata["scale_out_fraction"] = round(float(profile.under_gate_trim_fraction), 6)
            metadata["mark_under_gate_trim_done"] = True
            return _decision("scale_out", "score_or_news_early_risk_trim", profile, unreal_bps, net_bps, elapsed_min, metadata=metadata)
        deferred_signal = {
            "reason": reason,
            "elapsed_min": round(float(elapsed_min), 4),
            "net_unrealized_bps": round(float(net_bps), 4),
            "required_min_hold_minutes": profile.score_exit_min_hold_minutes,
            "required_min_profit_bps": profile.score_exit_min_profit_bps,
            "exit_profile_id": profile.profile_id,
            "action": "tighten_runner_stop",
        }
        return _decision("hold", reason, profile, unreal_bps, net_bps, elapsed_min, deferred_signal, metadata)
    if str(trade.get("exit_stage") or "stage1") == "stage2":
        metadata = _tighten_metadata(trade, profile, net_bps, reason, aggressive=True)
        if _runner_stop_hit(trade, net_bps):
            return _decision("close", reason, profile, unreal_bps, net_bps, elapsed_min, metadata=metadata)
        return _decision("hold", reason, profile, unreal_bps, net_bps, elapsed_min, metadata=metadata)
    if profile.runner_trail_bps > 0 and profile.under_gate_trim_fraction > 0:
        metadata = _tighten_metadata(trade, profile, net_bps, reason, aggressive=_is_news_reason(reason))
        metadata["scale_out_fraction"] = round(float(profile.under_gate_trim_fraction), 6)
        metadata["next_exit_stage"] = "stage2"
        metadata["runner_anchor_net_bps"] = round(float(net_bps), 6)
        metadata["mark_under_gate_trim_done"] = True
        return _decision(
            "scale_out",
            "score_or_news_profit_protect_trim",
            profile,
            unreal_bps,
            net_bps,
            elapsed_min,
            metadata=metadata,
        )
    return _decision("close", reason, profile, unreal_bps, net_bps, elapsed_min)


def _update_runner_anchor_metadata(trade: dict[str, Any], profile: ExitProfile, net_bps: float) -> dict[str, Any]:
    anchor = max(float(trade.get("exit_runner_anchor_net_bps") or net_bps), float(net_bps))
    stop = anchor - max(float(profile.runner_trail_bps or 0.0), 1.0)
    current_stop = trade.get("exit_runner_stop_net_bps")
    if current_stop is not None:
        stop = max(float(current_stop), stop)
    return {
        "runner_anchor_net_bps": round(float(anchor), 6),
        "runner_stop_net_bps": round(float(stop), 6),
        "trail_bps": round(float(profile.runner_trail_bps or 0.0), 6),
    }


def _stage1_runner_scale_metadata(profile: ExitProfile, net_bps: float, cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "scale_out_fraction": round(float(profile.scale_out_fraction), 6),
        "next_exit_stage": "stage2",
        "runner_anchor_net_bps": round(float(net_bps), 6),
        "runner_stop_net_bps": round(
            max(0.0, float(net_bps) - max(float(profile.runner_trail_bps or 0.0), 1.0)),
            6,
        ),
        "trail_bps": round(float(profile.runner_trail_bps or 0.0), 6),
        "exit_config": cfg,
    }


def decide_trade_exit(
    trade: dict[str, Any],
    status: Any,
    scenario: dict[str, Any],
    unreal_bps: float,
    elapsed_min: float,
    setup_blocker_reason: str = "",
) -> ExitDecision:
    profile, cfg = exit_profile_for_trade(trade, scenario)
    net_bps = net_unrealized_bps(trade, unreal_bps)
    stop_loss = float(cfg.get("stop_loss_bps") or scenario.get("stop_loss_bps") or 0.0)
    take_profit = float(cfg.get("take_profit_bps") or scenario.get("take_profit_bps") or 0.0)
    stop_loss = stop_loss or float(trade.get("trade_strategy_stop_loss_bps") or 0.0)
    take_profit = take_profit or float(trade.get("trade_strategy_take_profit_bps") or 0.0)
    if _is_oracle_managed_exit(trade, cfg):
        stop_loss = max(stop_loss, _oracle_hard_stop_floor_bps(cfg, take_profit, stop_loss))
    early_loss = float(cfg.get("early_loss_bps") or scenario.get("early_loss_bps") or 0.0)
    early_loss_after = float(cfg.get("early_loss_after_minutes") or scenario.get("early_loss_after_minutes") or 0.0)
    if str(trade.get("exit_stage") or "stage1") == "stage2" and profile.runner_trail_bps > 0:
        trail_meta = _update_runner_anchor_metadata(trade, profile, net_bps)
        trade["exit_runner_anchor_net_bps"] = float(trail_meta["runner_anchor_net_bps"])
        trade["exit_runner_stop_net_bps"] = float(trail_meta["runner_stop_net_bps"])
        trade["exit_active_trail_bps"] = float(trail_meta["trail_bps"])
        if net_bps <= float(trail_meta["runner_stop_net_bps"]):
            return _decision(
                "close",
                "trailing_stop",
                profile,
                unreal_bps,
                net_bps,
                elapsed_min,
                metadata={"exit_config": cfg, **trail_meta},
            )
    if early_loss and elapsed_min >= early_loss_after and unreal_bps <= -early_loss:
        return _decision("close", "early_loss_cut", profile, unreal_bps, net_bps, elapsed_min)
    if stop_loss and unreal_bps <= -stop_loss:
        return _decision("close", "stop_loss", profile, unreal_bps, net_bps, elapsed_min)
    bank_progress_decision = _bank_progress_exit_decision(trade, scenario, profile, unreal_bps, net_bps, elapsed_min)
    if bank_progress_decision:
        return bank_progress_decision
    side = str(trade.get("side") or "")
    pressure_dir = str(getattr(status, "pressure_watch_direction", "") or "")
    if pressure_dir in ("buy", "sell") and pressure_dir != side:
        if net_bps > 0 and profile.runner_trail_bps > 0:
            return _score_news_degradation_decision(trade, profile, "pressure_flipped", unreal_bps, net_bps, elapsed_min)
        if profile.defer_unprofitable_pressure_exits and net_bps <= 0:
            if early_loss and elapsed_min >= early_loss_after and unreal_bps <= -early_loss:
                return _decision("close", "early_loss_cut", profile, unreal_bps, net_bps, elapsed_min)
            if stop_loss and unreal_bps <= -stop_loss:
                return _decision("close", "stop_loss", profile, unreal_bps, net_bps, elapsed_min)
            deferred_signal = {
                "reason": "pressure_flipped",
                "elapsed_min": round(float(elapsed_min), 4),
                "net_unrealized_bps": round(float(net_bps), 4),
                "required_min_profit_bps": profile.score_exit_min_profit_bps,
                "exit_profile_id": profile.profile_id,
                "action": "hold_pressure_flip_until_profit_or_hard_stop",
            }
            return _decision("hold", "pressure_flipped", profile, unreal_bps, net_bps, elapsed_min, deferred_signal)
        return close_or_defer(trade, profile, "pressure_flipped", unreal_bps, net_bps, elapsed_min)

    if early_loss and elapsed_min >= early_loss_after and unreal_bps <= -early_loss:
        return _decision("close", "early_loss_cut", profile, unreal_bps, net_bps, elapsed_min)
    if stop_loss and unreal_bps <= -stop_loss:
        return _decision("close", "stop_loss", profile, unreal_bps, net_bps, elapsed_min)
    if (
        profile.tp1_bps > 0
        and profile.scale_out_fraction > 0
        and str(trade.get("exit_stage") or "stage1") == "stage1"
        and net_bps >= profile.tp1_bps
    ):
        return _decision(
            "scale_out",
            "tp1_partial",
            profile,
            unreal_bps,
            net_bps,
            elapsed_min,
            metadata=_stage1_runner_scale_metadata(profile, net_bps, cfg),
        )
    if take_profit and unreal_bps >= take_profit:
        if str(trade.get("exit_stage") or "stage1") == "stage2" and profile.runner_trail_bps > 0:
            return _decision(
                "hold",
                "runner_take_profit_ignored",
                profile,
                unreal_bps,
                net_bps,
                elapsed_min,
                metadata={"ignored_full_close_take_profit_bps": take_profit},
            )
        if (
            profile.scale_out_fraction > 0
            and profile.runner_trail_bps > 0
            and str(trade.get("exit_stage") or "stage1") == "stage1"
        ):
            return _decision(
                "scale_out",
                "take_profit_partial",
                profile,
                unreal_bps,
                net_bps,
                elapsed_min,
                metadata=_stage1_runner_scale_metadata(profile, net_bps, cfg),
            )
        return _decision("close", "take_profit", profile, unreal_bps, net_bps, elapsed_min)

    if getattr(status, "trade_stage", "") == "late":
        oracle_defer = _oracle_setup_defer_decision(
            trade, profile, cfg, "setup_late", unreal_bps, net_bps, elapsed_min
        )
        if oracle_defer:
            return oracle_defer
        return close_or_defer(trade, profile, "setup_late", unreal_bps, net_bps, elapsed_min)

    min_score = int(scenario.get("min_present_score") or 55)
    if int(getattr(status, "trade_present_score", 0) or 0) < min_score:
        return _score_news_degradation_decision(trade, profile, "present_score_degraded", unreal_bps, net_bps, elapsed_min)

    entry_score = int(trade.get("trade_present_score") or 0)
    score_drop = int(scenario.get("exit_score_drop") or 0)
    score_drop = score_drop or int(trade.get("trade_strategy_exit_score_drop") or 0)
    if score_drop and entry_score and int(getattr(status, "trade_present_score", 0) or 0) <= entry_score - score_drop:
        return _score_news_degradation_decision(
            trade, profile, "present_score_dropped_from_entry", unreal_bps, net_bps, elapsed_min
        )

    if setup_blocker_reason:
        oracle_defer = _oracle_setup_defer_decision(
            trade,
            profile,
            cfg,
            "setup_blocker",
            unreal_bps,
            net_bps,
            elapsed_min,
            setup_blocker_reason,
        )
        if oracle_defer:
            return oracle_defer
        return close_or_defer(trade, profile, "setup_blocker", unreal_bps, net_bps, elapsed_min)

    news_ctx = getattr(status, "daily_news_context", None) or {}
    starter_actions = {str(action).upper() for action in (news_ctx.get("starter_actions") or [])}
    if side == "buy" and ("EXIT_LONGS" in starter_actions or "REDUCE_GROSS_EXPOSURE" in starter_actions):
        return _score_news_degradation_decision(trade, profile, "news_started_exit_longs", unreal_bps, net_bps, elapsed_min)
    if side == "sell" and ("EXIT_SHORTS" in starter_actions or "REDUCE_GROSS_EXPOSURE" in starter_actions):
        return _score_news_degradation_decision(trade, profile, "news_started_exit_shorts", unreal_bps, net_bps, elapsed_min)

    if profile.max_hold_minutes > 0 and elapsed_min >= profile.max_hold_minutes:
        if net_bps <= 0:
            return _decision("close", "max_hold_time_no_profit", profile, unreal_bps, net_bps, elapsed_min)
        if str(trade.get("exit_stage") or "stage1") == "stage2":
            metadata = _tighten_metadata(trade, profile, net_bps, "max_hold_trailing_tighten", aggressive=True)
            if _runner_stop_hit(trade, net_bps):
                return _decision("close", "max_hold_trailing_stop", profile, unreal_bps, net_bps, elapsed_min, metadata=metadata)
            return _decision("hold", "max_hold_trailing_tighten", profile, unreal_bps, net_bps, elapsed_min, metadata=metadata)
        return _decision("close", "max_hold_time_flat", profile, unreal_bps, net_bps, elapsed_min)

    resolved_hold_minutes = float(cfg.get("hold_minutes") or trade["hold_minutes"])
    if elapsed_min >= resolved_hold_minutes:
        min_profit = profile.score_exit_min_profit_bps
        extension = profile.profitable_hold_extension_minutes
        if net_bps <= 0:
            deferred_signal = {
                "reason": "auto_hold_elapsed_waiting_for_profit",
                "elapsed_min": round(float(elapsed_min), 4),
                "net_unrealized_bps": round(float(net_bps), 4),
                "required_min_profit_bps": min_profit,
                "exit_profile_id": profile.profile_id,
                "action": "hold_until_profit_or_hard_stop",
            }
            return _decision("hold", "auto_hold_elapsed_waiting_for_profit", profile, unreal_bps, net_bps, elapsed_min, deferred_signal)
        if net_bps > 0 and net_bps < min_profit and elapsed_min < extension:
            deferred_signal = {
                "reason": "auto_hold_elapsed",
                "elapsed_min": round(float(elapsed_min), 4),
                "net_unrealized_bps": round(float(net_bps), 4),
                "required_min_profit_bps": min_profit,
                "extension_until_minutes": extension,
                "exit_profile_id": profile.profile_id,
            }
            return _decision("hold", "auto_hold_elapsed", profile, unreal_bps, net_bps, elapsed_min, deferred_signal)
        return _decision("close", "auto_hold_elapsed", profile, unreal_bps, net_bps, elapsed_min)

    return _decision("hold", "", profile, unreal_bps, net_bps, elapsed_min)
