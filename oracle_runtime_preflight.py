from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import strategy_switcher
import trade_exit_strategy
from mock_trade_replay import scenario_blocker


ROOT = Path(__file__).resolve().parent


class _Status:
    def __init__(self, asset: str, venue: str, side: str = "") -> None:
        self.asset = asset
        self.venue = venue
        self.trade_option_side = side
        self.pressure_watch_direction = ""
        self.move_shape_category = ""
        self.pattern_family = ""
        self.price = 0.0


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _no_side_oracle_probe() -> tuple[_Status, dict[str, str], bool]:
    rows = []
    try:
        import json

        payload = json.loads(strategy_switcher.HINDSIGHT_QUEUE_PATH.read_text(encoding="utf-8"))
        rows.extend(row for row in payload.get("candidate_experiments") or [] if isinstance(row, dict))
    except Exception:
        pass
    try:
        rows.extend(strategy_switcher._oracle_audit_no_side_contexts())
    except Exception:
        pass
    rows.sort(
        key=lambda row: (
            float(row.get("oracle_incremental_vs_actual_usd") or row.get("oracle_net_pnl_usd") or 0.0),
            int(float(row.get("missed_entry_rows") or 0)),
        ),
        reverse=True,
    )
    for row in rows:
        context = str(row.get("context_key") or "")
        parts = context.split("|")
        if len(parts) == 5 and parts[0] == "NO_STRATEGY":
            _, asset, venue, _side, session = parts
            probe_status = _Status(asset, venue)
            probe_inputs = {"strategy_mode": "practice", "bucket_session": session}
            if strategy_switcher._oracle_row_matches_no_side_context(row, probe_status, probe_inputs):
                return probe_status, probe_inputs, True
    return _Status("ETH", "Bybit"), {"strategy_mode": "practice", "bucket_session": "remaining18h"}, False


def _strategy_oracle_probe() -> tuple[_Status, dict[str, str], bool]:
    rows = []
    try:
        rows = list(strategy_switcher._oracle_audit_strategy_contexts())
    except Exception:
        rows = []
    rows.sort(
        key=lambda row: (
            float(row.get("oracle_incremental_vs_actual_usd") or row.get("oracle_net_pnl_usd") or 0.0),
            int(float(row.get("missed_entry_rows") or 0)),
        ),
        reverse=True,
    )
    for row in rows:
        context = str(row.get("context_key") or "")
        parts = context.split("|")
        if len(parts) == 5:
            _family, asset, venue, side, session = parts
            probe_status = _Status(asset, venue, side)
            probe_inputs = {"strategy_mode": "practice", "bucket_session": session}
            if strategy_switcher._oracle_row_matches_strategy_context(row, probe_status, probe_inputs, side):
                return probe_status, probe_inputs, True
    return _Status("BTC", "Coinbase", "sell"), {"strategy_mode": "practice", "bucket_session": "remaining18h"}, False


def verify_oracle_runtime_paths() -> None:
    no_side_status, no_side_inputs, has_no_side_probe = _no_side_oracle_probe()
    if has_no_side_probe:
        no_side = strategy_switcher.classify_strategy(
            no_side_status,
            no_side_inputs,
        )
        _assert(no_side.forced, "no-side oracle decision must be forced")
        _assert(no_side.source_queue_action == "oracle_distilled_no_side_context", "no-side oracle source missing")
        _assert(no_side.side_override in {"buy", "sell"}, "no-side oracle decision must infer a side")

    strategy_status, strategy_inputs, has_strategy_probe = _strategy_oracle_probe()
    strategy_ctx = strategy_switcher.classify_strategy(strategy_status, strategy_inputs)
    if has_strategy_probe:
        _assert(strategy_ctx.forced, "strategy-context oracle decision must be forced")
        _assert(
            strategy_ctx.source_queue_action == "oracle_distilled_strategy_context",
            "strategy-context oracle source missing",
        )

    blocked_status = SimpleNamespace(
        trade_option_side="sell",
        pressure_watch_direction="",
        trade_strategy_id=strategy_ctx.strategy_id if has_strategy_probe else "SMALL_MOVE_FADE",
        trade_strategy_forced=True,
        venue="Coinbase",
        trade_present_score=0,
        trade_option_readiness=0,
        high_conviction_ticket={},
        trade_stage="",
        trade_option_state="",
        pressure_watch_state="",
    )
    blocker = scenario_blocker(
        {
            "side_filter": "both",
            "blocked_sides": ["sell"],
            "blocked_strategy_sides": [f"{strategy_ctx.strategy_id.lower()}:sell"],
            "enforce_bucket_health": True,
            "allowed_stages": ["onset"],
            "allowed_trade_states": ["confirmed"],
            "allowed_pressure_states": ["confirmed"],
        },
        blocked_status,
    )
    _assert(blocker == "", f"forced oracle route should bypass mock guards, got {blocker!r}")

    trade = {
        "trade_strategy_id": "SMALL_MOVE_FADE",
        "asset": "BTC",
        "venue": "Bybit",
        "bucket_session": "remaining18h",
        "side": "sell",
        "fill_price": 100.0,
        "fee_bps": 5.0,
        "hold_minutes": 10,
        "trade_present_score": 90,
        "trade_strategy_exit_score_drop": 0,
        "exit_stage": "stage1",
    }
    profile, cfg = trade_exit_strategy.exit_profile_for_trade(trade, {})
    _assert(bool(cfg), "oracle exit config must resolve for SMALL_MOVE_FADE")
    _assert(float(cfg.get("hold_minutes") or 0) > 10, "oracle exit config must carry long hold window")
    decision = trade_exit_strategy.decide_trade_exit(
        trade,
        SimpleNamespace(
            pressure_watch_direction="sell",
            trade_stage="mature",
            trade_present_score=90,
            daily_news_context={},
        ),
        {},
        unreal_bps=20.0,
        elapsed_min=20.0,
    )
    _assert(decision.reason != "auto_hold_elapsed", "resolved oracle hold must prevent short auto-hold exits")
    _assert(profile.profile_id == trade_exit_strategy.GATED_PROFITABLE_SCORE_NEWS_EXITS, "unexpected profile")
    setup_decision = trade_exit_strategy.decide_trade_exit(
        trade,
        SimpleNamespace(
            pressure_watch_direction="sell",
            trade_stage="mature",
            trade_present_score=90,
            daily_news_context={},
        ),
        {},
        unreal_bps=2.0,
        elapsed_min=5.0,
        setup_blocker_reason="strategy_side_blocked_by_live_pnl_guard",
    )
    _assert(
        setup_decision.action == "hold" and setup_decision.reason == "setup_blocker",
        "oracle setup blockers must defer instead of fee-grinding early closes",
    )
    stop_decision = trade_exit_strategy.decide_trade_exit(
        trade,
        SimpleNamespace(
            pressure_watch_direction="sell",
            trade_stage="mature",
            trade_present_score=90,
            daily_news_context={},
        ),
        {},
        unreal_bps=-40.0,
        elapsed_min=0.0,
    )
    _assert(
        stop_decision.action == "hold",
        "oracle hard-stop floor must prevent immediate spread/noise stop-outs",
    )

    sidecar_source = (ROOT / "live_family_registry_compare.py").read_text(encoding="utf-8")
    for required in ("oracle_p25_60m", "oracle_median_120m", "oracle_p75_240m_runner"):
        _assert(required in sidecar_source, f"sidecar missing {required}")


def run_startup_preflight(source: str) -> None:
    verify_oracle_runtime_paths()
    print(f"[oracle-preflight] {source}: runtime paths ok", flush=True)
