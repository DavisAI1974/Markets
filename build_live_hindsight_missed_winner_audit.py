from __future__ import annotations

import argparse
import csv
import json
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mock_trade_replay import VENUES
from phase1_5_evaluator import load_bars
from strategy_family_evolution import _evolution_write_lock, merge_candidate_experiments


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
DEFAULT_DATA_DIR = REPO_ROOT / "live_data"
DEFAULT_OUT_DIR = EVOLUTION_DIR / "live_mock_replay"
OPPORTUNITY_LOG = EVOLUTION_DIR / "_live_mock_opportunities.jsonl"
TRADE_LOG = EVOLUTION_DIR / "_live_replay_mock_trades.jsonl"
HINDSIGHT_QUEUE = EVOLUTION_DIR / "_hindsight_missed_winner_queue.json"
CANDIDATE_EXPERIMENTS = EVOLUTION_DIR / "_candidate_experiments.json"
FEE_BPS = 5.0
NOTIONAL_USD = 1000.0
HORIZONS_MINUTES = (10, 30, 60, 120, 240, 360)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _norm_venue(value: Any) -> str:
    return str(value or "").strip().lower()


def _norm_asset(value: Any) -> str:
    return str(value or "").strip().upper()


def _side_price(bar: Any, side: str, *, entry: bool) -> float:
    if entry:
        if side == "buy":
            return _float(getattr(bar, "ask", 0.0)) or _float(getattr(bar, "close", 0.0))
        return _float(getattr(bar, "bid", 0.0)) or _float(getattr(bar, "close", 0.0))
    if side == "buy":
        return _float(getattr(bar, "high", 0.0)) or _float(getattr(bar, "close", 0.0))
    return _float(getattr(bar, "low", 0.0)) or _float(getattr(bar, "close", 0.0))


def _signed_bps(side: str, entry: float, exit_price: float) -> float:
    if entry <= 0 or exit_price <= 0:
        return 0.0
    if side == "buy":
        return ((exit_price - entry) / entry) * 10000.0
    if side == "sell":
        return ((entry - exit_price) / entry) * 10000.0
    return 0.0


def _load_bars(data_dir: Path) -> dict[tuple[str, str], list[Any]]:
    out: dict[tuple[str, str], list[Any]] = {}
    for asset, venues in VENUES.items():
        for venue, filename in venues.items():
            path = data_dir / filename
            if not path.exists():
                continue
            try:
                bars = load_bars(str(path))
            except Exception:
                bars = []
            if bars:
                out[(asset.upper(), venue.lower())] = bars
    return out


def _trade_key(row: dict[str, Any]) -> tuple[str, str, str, float]:
    return (
        _norm_asset(row.get("asset")),
        _norm_venue(row.get("venue")),
        str(row.get("side") or "").lower(),
        round(_float(row.get("ts_utc")), 0),
    )


def _trade_lookup(trades: list[dict[str, Any]]) -> dict[tuple[str, str, str, float], list[dict[str, Any]]]:
    out: dict[tuple[str, str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        out[_trade_key(trade)].append(trade)
    return out


def _nearest_trade(
    opp: dict[str, Any],
    trades_by_key: dict[tuple[str, str, str, float], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    asset = _norm_asset(opp.get("asset"))
    venue = _norm_venue(opp.get("venue"))
    side = str(opp.get("side") or "").lower()
    ts = _float(opp.get("ts_utc"))
    for rounded in (round(ts, 0), round(ts / 60.0) * 60.0):
        rows = trades_by_key.get((asset, venue, side, rounded)) or []
        if rows:
            return rows[-1]
    candidates = []
    for (a, v, s, t), rows in trades_by_key.items():
        if a == asset and v == venue and s == side and abs(t - ts) <= 90:
            candidates.extend(rows)
    if not candidates:
        return None
    return sorted(candidates, key=lambda row: abs(_float(row.get("ts_utc")) - ts))[0]


def _context_key(row: dict[str, Any], side: str) -> str:
    return "|".join([
        str(row.get("trade_strategy_id") or "NO_STRATEGY").upper(),
        _norm_asset(row.get("asset")),
        str(row.get("venue") or ""),
        side,
        str(row.get("bucket_session") or ""),
    ])


def _trait_key(row: dict[str, Any], side: str) -> str:
    news = row.get("daily_news_context") or {}
    news_state = "stale_news" if (row.get("daily_news_status") or {}).get("stale") else str(news.get("trade_posture") or "")
    return "|".join([
        str(row.get("trade_strategy_id") or "NO_STRATEGY").upper(),
        str(row.get("trade_stage") or "none"),
        str(row.get("trade_option_state") or "none"),
        str(row.get("trade_score_band") or "none"),
        str(row.get("pressure_watch_state") or "none"),
        side,
        f"move={_band_bps(_float(row.get('trade_current_chunk_bps')))}",
        f"recent2={_band_bps(_float(row.get('trade_recent_2chunk_bps')))}",
        f"dipole={_band_signed(_float(row.get('mean_dipole')), 0.25)}",
        f"acl1={_band_signed(_float(row.get('dipole_acl1')), 0.25)}",
        f"vol={_band_signed(_float(row.get('volume_zscore')), 1.0)}",
        f"news={news_state or 'none'}",
    ])


def _band_bps(value: float) -> str:
    if value <= -20:
        return "down_extreme_le_-20"
    if value <= -10:
        return "down_extended_-20_-10"
    if value <= -5:
        return "down_edge_-10_-5"
    if value < 0:
        return "down_small_-5_0"
    if value < 5:
        return "up_small_0_5"
    if value < 10:
        return "up_edge_5_10"
    if value < 20:
        return "up_extended_10_20"
    return "up_extreme_ge_20"


def _band_signed(value: float, threshold: float) -> str:
    if value >= threshold * 2:
        return "strong_buy"
    if value >= threshold:
        return "buy"
    if value <= -threshold * 2:
        return "strong_sell"
    if value <= -threshold:
        return "sell"
    return "neutral"


def _move_shape_category(row: dict[str, Any], side: str) -> str:
    chunk = _band_bps(_float(row.get("trade_current_chunk_bps")))
    recent = _band_bps(_float(row.get("trade_recent_2chunk_bps")))
    onset = _band_bps(_float(row.get("trade_from_onset_bps")))
    if side == "sell" and chunk == "up_small_0_5" and recent == "up_small_0_5":
        return "small_up_sell_fade"
    if side == "sell" and chunk in {"up_edge_5_10", "up_extended_10_20", "up_extreme_ge_20"}:
        return "extended_up_sell_fade"
    if side == "sell" and recent in {"down_small_-5_0", "down_edge_-10_-5", "down_extended_-20_-10", "down_extreme_le_-20"}:
        return "sell_down_continuation"
    if side == "sell" and onset == "up_small_0_5":
        return "onset_small_up_sell_fade"
    if side == "buy" and chunk == "down_small_-5_0" and recent == "down_small_-5_0":
        return "small_down_buy_fade"
    if side == "buy" and chunk in {"down_edge_-10_-5", "down_extended_-20_-10", "down_extreme_le_-20"}:
        return "extended_down_buy_fade"
    if side == "buy" and recent in {"up_small_0_5", "up_edge_5_10", "up_extended_10_20", "up_extreme_ge_20"}:
        return "buy_up_continuation"
    return f"{side or 'no_side'}_{chunk}_{recent}"


def _pattern_family_from_move_shape(move_shape: str) -> str:
    if move_shape == "small_up_sell_fade":
        return "SMALL_MOVE_FADE"
    if move_shape == "onset_small_up_sell_fade":
        return "SMALL_MOVE_FADE_NEIGHBOR"
    if move_shape == "extended_up_sell_fade":
        return "EXTENDED_UP_SELL_FADE"
    if move_shape == "sell_down_continuation":
        return "SELL_DOWN_CONTINUATION"
    if move_shape in {"small_down_buy_fade", "extended_down_buy_fade"}:
        return "BUY_FADE"
    if move_shape == "buy_up_continuation":
        return "BUY_UP_CONTINUATION"
    if move_shape.startswith("sell_"):
        return "SELL_SHAPE_WATCHLIST"
    if move_shape.startswith("buy_"):
        return "BUY_SHAPE_WATCHLIST"
    return "UNCATALOGED"


def _promotion_state_for_pattern(row: dict[str, Any]) -> str:
    family = str(row.get("pattern_family") or "")
    rows = int(row.get("rows") or 0)
    missed = int(row.get("missed_entry_rows") or 0)
    pnl = _float(row.get("oracle_incremental_vs_actual_usd"))
    if family == "SMALL_MOVE_FADE" and rows >= 30 and missed >= 10 and pnl > 0:
        return "promote_to_shadow_small_move_fade"
    if pnl > 0 and rows >= 20:
        return "candidate_watch"
    if rows < 10:
        return "insufficient_sample"
    return "quarantine_or_watch"


def _future_outcome(
    row: dict[str, Any],
    bars: list[Any],
    ts_index: list[float],
    side: str,
    *,
    fee_bps: float,
    notional_usd: float,
) -> dict[str, Any]:
    ts = _float(row.get("market_ts_utc")) or _float(row.get("chunk_end_ts_utc")) or _float(row.get("ts_utc"))
    idx = bisect_left(ts_index, ts)
    if idx >= len(bars):
        return {"status": "pending_no_entry_bar"}
    entry_bar = bars[idx]
    entry_price = _float(row.get("fill_price")) if str(row.get("side") or "").lower() == side else 0.0
    entry_price = entry_price or _side_price(entry_bar, side, entry=True)
    if entry_price <= 0:
        return {"status": "pending_no_entry_price"}
    max_available_min = max(0.0, (_float(getattr(bars[-1], "ts", 0.0)) - _float(getattr(entry_bar, "ts", 0.0))) / 60.0)
    horizon_rows = []
    best: dict[str, Any] | None = None
    for horizon in HORIZONS_MINUTES:
        end_ts = _float(getattr(entry_bar, "ts", 0.0)) + horizon * 60.0
        end_idx = bisect_left(ts_index, end_ts)
        future = bars[idx + 1:min(len(bars), max(idx + 2, end_idx + 1))]
        complete = max_available_min >= horizon
        if not future:
            continue
        if side == "buy":
            exit_bar = max(future, key=lambda b: _side_price(b, side, entry=False))
        else:
            exit_bar = min(future, key=lambda b: _side_price(b, side, entry=False))
        exit_price = _side_price(exit_bar, side, entry=False)
        gross_bps = _signed_bps(side, entry_price, exit_price)
        net_bps = gross_bps - (2.0 * fee_bps)
        net_usd = notional_usd * net_bps / 10000.0
        item = {
            "horizon_minutes": horizon,
            "complete": complete,
            "entry_ts_utc": _float(getattr(entry_bar, "ts", 0.0)),
            "exit_ts_utc": _float(getattr(exit_bar, "ts", 0.0)),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gross_bps": gross_bps,
            "net_bps": net_bps,
            "net_pnl_usd": net_usd,
        }
        horizon_rows.append(item)
        if best is None or (item["net_pnl_usd"], -item["horizon_minutes"]) > (best["net_pnl_usd"], -best["horizon_minutes"]):
            best = item
    if best is None:
        return {
            "status": "pending_insufficient_future",
            "entry_ts_utc": _float(getattr(entry_bar, "ts", 0.0)),
            "entry_price": entry_price,
            "max_available_minutes": max_available_min,
        }
    return {
        "status": "ok",
        "entry_ts_utc": _float(getattr(entry_bar, "ts", 0.0)),
        "entry_price": entry_price,
        "max_available_minutes": max_available_min,
        "best": best,
        "horizons": horizon_rows,
    }


def _summarize_group(rows: list[dict[str, Any]], key: str, limit: int = 25) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "rows": 0,
        "unique": set(),
        "missed_entry_rows": 0,
        "opened_rows": 0,
        "oracle_net_pnl_usd": 0.0,
        "actual_realized_pnl_usd": 0.0,
        "oracle_incremental_vs_actual_usd": 0.0,
    })
    for row in rows:
        name = str(row.get(key) or "")
        item = grouped[name]
        item["rows"] += 1
        item["unique"].add(str(row.get("unique_key") or ""))
        if row.get("decision") == "opened":
            item["opened_rows"] += 1
        else:
            item["missed_entry_rows"] += 1
        item["oracle_net_pnl_usd"] += _float(row.get("oracle_net_pnl_usd"))
        item["actual_realized_pnl_usd"] += _float(row.get("actual_realized_pnl_usd"))
        item["oracle_incremental_vs_actual_usd"] += _float(row.get("oracle_incremental_vs_actual_usd"))
    out = []
    for name, item in grouped.items():
        out.append({
            key: name,
            "rows": item["rows"],
            "unique": len(item["unique"]),
            "missed_entry_rows": item["missed_entry_rows"],
            "opened_rows": item["opened_rows"],
            "oracle_net_pnl_usd": round(item["oracle_net_pnl_usd"], 6),
            "actual_realized_pnl_usd": round(item["actual_realized_pnl_usd"], 6),
            "oracle_incremental_vs_actual_usd": round(item["oracle_incremental_vs_actual_usd"], 6),
        })
    return sorted(out, key=lambda r: (-_float(r.get("oracle_incremental_vs_actual_usd")), -int(r.get("rows") or 0)))[:limit]


def _safe_id(text: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "_" for ch in str(text or "")]
    return "_".join("".join(chars).split("_"))[:160] or "unknown"


def _experiments_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    experiments: list[dict[str, Any]] = []
    pattern_actions = {
        "SMALL_MOVE_FADE": {
            "move_shape": "small_up_sell_fade",
            "action": "evolve_small_move_fade_from_hindsight_misses",
            "priority": "critical",
            "diagnosis": "largest missed-entry pattern family; small upward move repeatedly won as a sell fade",
        },
        "BUY_UP_CONTINUATION": {
            "move_shape": "buy_up_continuation",
            "action": "evolve_buy_up_continuation_build_new_fast_fail_exit",
            "priority": "critical",
            "diagnosis": "buy-side continuation winners are being under-captured despite strong oracle repetition",
            "exit_questions": [
                "All retained buy-up continuation exits are negative; test buy_up_continuation_fast_fail_exits_v1 first.",
                "Can a fast-fail stop, early partial at 9 bps, and 5 bps runner trail turn follow-through into net wins after fees?",
                "If this mutation is still negative, create a stricter entry gate before adding another exit variant.",
            ],
        },
        "BUY_FADE": {
            "move_shape": "extended_down_buy_fade",
            "action": "evolve_buy_fade_exhaustion_entry_and_exit_candidate",
            "priority": "high",
            "diagnosis": "down-move buy fades show oracle opportunity but current live/shadow exits are not profitable enough",
        },
        "SELL_DOWN_CONTINUATION": {
            "move_shape": "sell_down_continuation",
            "action": "evolve_sell_down_continuation_entry_and_exit_candidate",
            "priority": "high",
            "diagnosis": "sell-side continuation winners repeat but current capture is sparse and exit selection is weak",
        },
    }
    for row in summary.get("by_pattern_family") or []:
        family = str(row.get("pattern_family") or "").strip().upper()
        meta = pattern_actions.get(family)
        if not meta:
            continue
        pnl = _float(row.get("oracle_incremental_vs_actual_usd"))
        missed = int(row.get("missed_entry_rows") or 0)
        if pnl <= 0 or missed <= 0:
            continue
        experiments.append({
            "experiment_id": f"hindsight_pattern_gap__{family.lower()}",
            "family": family,
            "source_family": family,
            "pattern_family": family,
            "pattern_category": str(meta["move_shape"]),
            "move_shape_category": str(meta["move_shape"]),
            "action": str(meta["action"]),
            "priority": str(meta["priority"]),
            "source": str(HINDSIGHT_QUEUE),
            "force_learning_trade": True,
            "context_key": "",
            "missed_entry_rows": missed,
            "opened_rows": int(row.get("opened_rows") or 0),
            "oracle_net_pnl_usd": _float(row.get("oracle_net_pnl_usd")),
            "oracle_incremental_vs_actual_usd": pnl,
            "diagnosis": str(meta["diagnosis"]),
            "entry_questions": [
                "Which live-observable move-shape traits identify this pattern before hindsight?",
                "Which platform/session buckets should be sampled or blocked first?",
                "Does the entry side need a forced override when pressure/no-side logic suppresses the pattern?",
            ],
            "exit_questions": [
                *(
                    list(meta.get("exit_questions") or [])
                    if isinstance(meta.get("exit_questions"), list)
                    else [
                        "Is there a clear exit winner for this family, or should the top 3-4 remain shadow candidates?",
                        "If all exits are low-margin, which new exit mutation should evolve create next?",
                    ]
                ),
            ],
            "success_criteria": {
                "min_mock_notional_usd": NOTIONAL_USD,
                "must_reduce_future_missed_count": True,
                "must_improve_family_net_pnl_after_fees": True,
                "must_remain_mock_only_until_promoted": True,
            },
        })
    for row in (summary.get("by_context") or [])[:20]:
        pnl = _float(row.get("oracle_incremental_vs_actual_usd"))
        missed = int(row.get("missed_entry_rows") or 0)
        if pnl <= 0 or missed <= 0:
            continue
        context = str(row.get("context_key") or "")
        parts = context.split("|")
        family = parts[0] if parts else "NO_STRATEGY"
        target_family = family
        pattern_category = ""
        reason = "hindsight_context_gap"
        if family in {"NO_STRATEGY", "NO_TRADE", ""}:
            action = "evolve_directional_entry_recognizer_from_hindsight_misses"
            reason = "no_trade_side_or_no_strategy"
            if len(parts) >= 4 and str(parts[3]).lower() == "sell":
                target_family = "SMALL_MOVE_FADE"
                pattern_category = "small_up_sell_fade_candidate"
                action = "evolve_small_move_fade_from_hindsight_misses"
        else:
            action = "evolve_entry_gate_and_exit_capture_from_hindsight_misses"
        experiments.append({
            "experiment_id": f"hindsight_missed_winner__{_safe_id(context)}",
            "family": target_family,
            "source_family": family,
            "pattern_category": pattern_category,
            "action": action,
            "priority": "critical" if family in {"NO_STRATEGY", "NO_TRADE", ""} else "high",
            "source": str(HINDSIGHT_QUEUE),
            "force_learning_trade": True,
            "context_key": context,
            "missed_entry_rows": missed,
            "opened_rows": int(row.get("opened_rows") or 0),
            "oracle_net_pnl_usd": _float(row.get("oracle_net_pnl_usd")),
            "oracle_incremental_vs_actual_usd": pnl,
            "diagnosis": reason,
            "entry_questions": [
                "Which live traits predict this profitable side before hindsight?",
                "Should no-side rows use fallback directional probes when repeated path evidence appears?",
                "Which blocker is protective versus suppressing edge?",
            ],
            "exit_questions": [
                "Which non-oracle exit rule captures the path after fees?",
                "Should pressure-flip, score-degrade, or fixed-hold exits be changed for this context?",
            ],
            "success_criteria": {
                "min_mock_notional_usd": NOTIONAL_USD,
                "must_reduce_future_missed_count": True,
                "must_improve_closed_actual_weekly_pace": True,
                "must_remain_mock_only_until_promoted": True,
            },
        })
    for row in (summary.get("top_exit_leaks") or [])[:20]:
        inc = _float(row.get("oracle_incremental_vs_actual_usd"))
        if inc <= 0:
            continue
        context = str(row.get("context_key") or "")
        experiments.append({
            "experiment_id": f"hindsight_exit_leak__{_safe_id(context)}__{_safe_id(str(row.get('chunk_id') or ''))}",
            "family": str(row.get("strategy_id") or ""),
            "action": "evolve_live_exit_capture_for_opened_hindsight_winner",
            "priority": "high",
            "source": str(HINDSIGHT_QUEUE),
            "force_learning_trade": False,
            "context_key": context,
            "chunk_id": str(row.get("chunk_id") or ""),
            "actual_realized_pnl_usd": _float(row.get("actual_realized_pnl_usd")),
            "oracle_net_pnl_usd": _float(row.get("oracle_net_pnl_usd")),
            "oracle_incremental_vs_actual_usd": inc,
            "diagnosis": "entry fired but exit failed to capture a post-fee winning path",
            "exit_questions": [
                "What live-observable exit trigger would have held or captured this path?",
                "Does pressure-hold, runner trail, fixed hold, or staged scale-out explain the edge?",
            ],
            "success_criteria": {
                "profit_after_fees": True,
                "must_compare_against_current_exit": True,
                "must_update_exit_profile_or_killlist": True,
            },
        })
    return experiments


def _write_evolve_queue(summary: dict[str, Any]) -> dict[str, Any]:
    experiments = _experiments_from_summary(summary)
    queue_doc = {
        "schema": "hindsight_missed_winner_queue_v1",
        "updated_at": _now_iso(),
        "source": str(DEFAULT_OUT_DIR / "live_hindsight_missed_winner_audit.json"),
        "priority": "critical",
        "policy": {
            "purpose": "Make live evolution optimize the gap between hindsight winner ceiling and actual live mock capture.",
            "mock_only": True,
            "primary_failure_modes": ["no_trade_side", "bucket_paper_only", "exit_missed_or_fee_leak"],
        },
        "summary": {
            "counts": summary.get("counts") or {},
            "pnl": summary.get("pnl") or {},
            "pace": summary.get("pace") or {},
            "top_pattern_families": (summary.get("by_pattern_family") or [])[:10],
            "top_move_shapes": (summary.get("by_move_shape") or [])[:10],
        },
        "candidate_experiments": experiments,
    }
    with _evolution_write_lock(EVOLUTION_DIR):
        HINDSIGHT_QUEUE.write_text(json.dumps(queue_doc, indent=2), encoding="utf-8")
        existing = _read_json(CANDIDATE_EXPERIMENTS)
        merged = merge_candidate_experiments(
            existing,
            experiments,
            source=str(HINDSIGHT_QUEUE),
            run_id="live_hindsight_missed_winner_audit",
        )
        CANDIDATE_EXPERIMENTS.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return {
        "queue": str(HINDSIGHT_QUEUE),
        "candidate_experiments": str(CANDIDATE_EXPERIMENTS),
        "experiments_added_or_updated": len(experiments),
    }


def build(
    *,
    data_dir: Path,
    out_dir: Path,
    fee_bps: float = FEE_BPS,
    notional_usd: float = NOTIONAL_USD,
) -> dict[str, Any]:
    bars_by_key = _load_bars(data_dir)
    ts_by_key = {
        key: [_float(getattr(bar, "ts", 0.0)) for bar in bars]
        for key, bars in bars_by_key.items()
    }
    opportunities = [
        row for row in _read_jsonl(OPPORTUNITY_LOG)
        if str(row.get("source") or "") == "live_mock_trade_replay"
    ]
    trades = _read_jsonl(TRADE_LOG)
    trades_by_key = _trade_lookup(trades)

    audited: list[dict[str, Any]] = []
    pending = 0
    for row in opportunities:
        asset = _norm_asset(row.get("asset"))
        venue = _norm_venue(row.get("venue"))
        bars = bars_by_key.get((asset, venue))
        ts_index = ts_by_key.get((asset, venue))
        if not bars or not ts_index:
            pending += 1
            continue
        raw_side = str(row.get("side") or "").lower()
        sides = [raw_side] if raw_side in {"buy", "sell"} else ["buy", "sell"]
        side_results = []
        for side in sides:
            outcome = _future_outcome(row, bars, ts_index, side, fee_bps=fee_bps, notional_usd=notional_usd)
            if outcome.get("status") == "ok":
                side_results.append((side, outcome))
        if not side_results:
            pending += 1
            continue
        side, outcome = max(side_results, key=lambda item: _float(((item[1].get("best") or {}).get("net_pnl_usd"))))
        best = outcome.get("best") or {}
        move_shape = _move_shape_category(row, side)
        pattern_family = _pattern_family_from_move_shape(move_shape)
        oracle_net = _float(best.get("net_pnl_usd"))
        trade = _nearest_trade(row, trades_by_key) if str(row.get("decision") or "") == "opened" else None
        actual_realized = _float((trade or {}).get("realized_pnl_usd"))
        actual_status = str((trade or {}).get("status") or "")
        unique_key = "|".join([asset, venue, str(row.get("chunk_id") or ""), side])
        is_oracle_winner = oracle_net > 0.0
        decision = str(row.get("decision") or "")
        if not is_oracle_winner:
            miss_type = "not_a_hindsight_winner"
        elif decision != "opened":
            miss_type = "missed_entry"
        elif actual_status == "closed" and actual_realized > 0:
            miss_type = "captured_net_win"
        elif actual_status == "closed":
            miss_type = "exit_missed_or_fee_leak"
        else:
            miss_type = "opened_pending"
        audited.append({
            "schema": "live_hindsight_opportunity_audit_row_v1",
            "unique_key": unique_key,
            "asset": asset,
            "venue": str(row.get("venue") or ""),
            "side": side,
            "logged_side": raw_side,
            "chunk_id": str(row.get("chunk_id") or ""),
            "ts_utc": _float(row.get("ts_utc")),
            "decision": decision,
            "blocker_reason": str(row.get("reason") or ""),
            "miss_type": miss_type,
            "is_oracle_winner_after_fees": is_oracle_winner,
            "oracle_horizon_minutes": int(best.get("horizon_minutes") or 0),
            "oracle_net_pnl_usd": round(oracle_net, 8),
            "oracle_net_bps": round(_float(best.get("net_bps")), 8),
            "oracle_gross_bps": round(_float(best.get("gross_bps")), 8),
            "oracle_entry_ts_utc": _float(best.get("entry_ts_utc")),
            "oracle_exit_ts_utc": _float(best.get("exit_ts_utc")),
            "oracle_entry_price": round(_float(best.get("entry_price")), 8),
            "oracle_exit_price": round(_float(best.get("exit_price")), 8),
            "max_available_minutes": round(_float(outcome.get("max_available_minutes")), 4),
            "actual_trade_status": actual_status,
            "actual_realized_pnl_usd": round(actual_realized, 8),
            "oracle_incremental_vs_actual_usd": round(oracle_net - actual_realized, 8),
            "strategy_id": str(row.get("trade_strategy_id") or "NO_STRATEGY").upper(),
            "strategy_variant_id": str(row.get("trade_strategy_variant_id") or ""),
            "strategy_action": str(row.get("trade_strategy_source_queue_action") or ""),
            "strategy_reasons": list(row.get("trade_strategy_reasons") or []),
            "trade_stage": str(row.get("trade_stage") or ""),
            "trade_option_state": str(row.get("trade_option_state") or ""),
            "pressure_watch_state": str(row.get("pressure_watch_state") or ""),
            "trade_present_score": int(_float(row.get("trade_present_score"))),
            "trade_option_readiness": int(_float(row.get("trade_option_readiness"))),
            "trade_current_chunk_bps": round(_float(row.get("trade_current_chunk_bps")), 8),
            "trade_recent_2chunk_bps": round(_float(row.get("trade_recent_2chunk_bps")), 8),
            "trade_from_onset_bps": round(_float(row.get("trade_from_onset_bps")), 8),
            "mean_dipole": round(_float(row.get("mean_dipole")), 8),
            "dipole_acl1": round(_float(row.get("dipole_acl1")), 8),
            "volume_zscore": round(_float(row.get("volume_zscore")), 8),
            "bucket_session": str(row.get("bucket_session") or ""),
            "move_shape_category": move_shape,
            "pattern_family": pattern_family,
            "context_key": _context_key(row, side),
            "trait_key": _trait_key(row, side),
        })

    winners = [row for row in audited if row["is_oracle_winner_after_fees"]]
    missed_entry = [row for row in winners if row["miss_type"] == "missed_entry"]
    opened_winners = [row for row in winners if row["decision"] == "opened"]
    exit_leaks = [row for row in winners if row["miss_type"] == "exit_missed_or_fee_leak"]
    captured_net = [row for row in winners if row["miss_type"] == "captured_net_win"]
    pending_opened = [row for row in winners if row["miss_type"] == "opened_pending"]
    total_actual_realized = sum(_float(row.get("realized_pnl_usd")) for row in trades if str(row.get("status") or "") == "closed")
    ts_values = [_float(row.get("ts_utc")) for row in audited if _float(row.get("ts_utc")) > 0]
    elapsed_days = ((max(ts_values) - min(ts_values)) / 86400.0) if len(ts_values) >= 2 else 0.0
    oracle_total = sum(_float(row.get("oracle_net_pnl_usd")) for row in winners)
    missed_oracle_total = sum(_float(row.get("oracle_net_pnl_usd")) for row in missed_entry)
    opened_oracle_total = sum(_float(row.get("oracle_net_pnl_usd")) for row in opened_winners)
    summary = {
        "schema": "live_hindsight_missed_winner_audit_v1",
        "created_at": _now_iso(),
        "inputs": {
            "opportunity_log": str(OPPORTUNITY_LOG),
            "trade_log": str(TRADE_LOG),
            "data_dir": str(data_dir),
            "fee_bps_per_side": fee_bps,
            "notional_usd": notional_usd,
            "horizons_minutes": list(HORIZONS_MINUTES),
        },
        "counts": {
            "opportunity_rows": len(opportunities),
            "audited_rows": len(audited),
            "pending_or_unmatched_rows": pending,
            "oracle_winner_rows_after_fees": len(winners),
            "oracle_winner_unique_after_fees": len({row["unique_key"] for row in winners}),
            "missed_entry_rows": len(missed_entry),
            "missed_entry_unique": len({row["unique_key"] for row in missed_entry}),
            "opened_oracle_winner_rows": len(opened_winners),
            "captured_net_win_rows": len(captured_net),
            "exit_missed_or_fee_leak_rows": len(exit_leaks),
            "opened_pending_rows": len(pending_opened),
        },
        "pnl": {
            "closed_actual_realized_pnl_usd": round(total_actual_realized, 8),
            "oracle_winner_net_pnl_usd": round(oracle_total, 8),
            "missed_entry_oracle_net_pnl_usd": round(missed_oracle_total, 8),
            "opened_oracle_winner_net_pnl_usd": round(opened_oracle_total, 8),
            "oracle_incremental_vs_closed_actual_usd": round(oracle_total - total_actual_realized, 8),
        },
        "pace": {
            "audited_elapsed_days": round(elapsed_days, 6),
            "closed_actual_weekly_pace_usd": round((total_actual_realized / elapsed_days) * 7.0, 2) if elapsed_days > 0 else None,
            "oracle_winner_weekly_pace_usd": round((oracle_total / elapsed_days) * 7.0, 2) if elapsed_days > 0 else None,
            "missed_entry_oracle_weekly_pace_usd": round((missed_oracle_total / elapsed_days) * 7.0, 2) if elapsed_days > 0 else None,
        },
        "by_miss_type": dict(Counter(str(row["miss_type"]) for row in winners).most_common()),
        "by_blocker": _summarize_group(winners, "blocker_reason"),
        "by_context": _summarize_group(winners, "context_key"),
        "by_trait": _summarize_group(winners, "trait_key"),
        "by_move_shape": _summarize_group(winners, "move_shape_category"),
        "by_pattern_family": [
            {
                **row,
                "promotion_state": _promotion_state_for_pattern(row),
            }
            for row in _summarize_group(winners, "pattern_family")
        ],
        "by_strategy": _summarize_group(winners, "strategy_id"),
        "top_missed_entries": sorted(
            missed_entry,
            key=lambda row: _float(row.get("oracle_net_pnl_usd")),
            reverse=True,
        )[:50],
        "top_exit_leaks": sorted(
            exit_leaks,
            key=lambda row: _float(row.get("oracle_incremental_vs_actual_usd")),
            reverse=True,
        )[:50],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "live_hindsight_missed_winner_audit.json"
    csv_path = out_dir / "live_hindsight_missed_winner_audit_rows.csv"
    md_path = out_dir / "live_hindsight_missed_winner_audit.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    fieldnames = [
        "unique_key", "miss_type", "is_oracle_winner_after_fees", "oracle_net_pnl_usd",
        "oracle_net_bps", "oracle_horizon_minutes", "decision", "blocker_reason",
        "actual_trade_status", "actual_realized_pnl_usd", "oracle_incremental_vs_actual_usd",
        "strategy_id", "asset", "venue", "side", "bucket_session", "trade_stage",
        "trade_option_state", "pressure_watch_state", "trade_present_score",
        "trade_option_readiness", "trade_current_chunk_bps", "trade_recent_2chunk_bps",
        "trade_from_onset_bps", "mean_dipole", "dipole_acl1", "volume_zscore", "chunk_id", "ts_utc",
        "oracle_entry_ts_utc", "oracle_exit_ts_utc", "oracle_entry_price", "oracle_exit_price",
        "move_shape_category", "pattern_family", "context_key", "trait_key",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(audited, key=lambda row: (_float(row.get("oracle_net_pnl_usd")), row.get("unique_key")), reverse=True))
    md_path.write_text(_markdown(summary), encoding="utf-8")
    evolve_outputs = _write_evolve_queue(summary)
    summary["outputs"] = {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
        **evolve_outputs,
    }
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _markdown(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    pnl = summary["pnl"]
    pace = summary["pace"]
    lines = [
        "# Live Hindsight Missed Winner Audit",
        "",
        f"Created: {summary['created_at']}",
        "",
        "## Counts",
        "",
        f"- Audited opportunity rows: {counts['audited_rows']}",
        f"- Oracle winner rows after fees: {counts['oracle_winner_rows_after_fees']}",
        f"- Missed entry rows: {counts['missed_entry_rows']}",
        f"- Opened oracle winner rows: {counts['opened_oracle_winner_rows']}",
        f"- Captured net win rows: {counts['captured_net_win_rows']}",
        f"- Exit missed / fee leak rows: {counts['exit_missed_or_fee_leak_rows']}",
        f"- Opened pending rows: {counts['opened_pending_rows']}",
        "",
        "## PnL Ceiling",
        "",
        f"- Closed actual realized PnL: ${pnl['closed_actual_realized_pnl_usd']}",
        f"- Oracle winner net PnL: ${pnl['oracle_winner_net_pnl_usd']}",
        f"- Missed entry oracle net PnL: ${pnl['missed_entry_oracle_net_pnl_usd']}",
        f"- Opened oracle winner net PnL: ${pnl['opened_oracle_winner_net_pnl_usd']}",
        f"- Oracle incremental vs closed actual: ${pnl['oracle_incremental_vs_closed_actual_usd']}",
        "",
        "## Pace",
        "",
        f"- Audited elapsed days: {pace['audited_elapsed_days']}",
        f"- Closed actual weekly pace: ${pace['closed_actual_weekly_pace_usd']}",
        f"- Oracle winner weekly pace: ${pace['oracle_winner_weekly_pace_usd']}",
        f"- Missed entry oracle weekly pace: ${pace['missed_entry_oracle_weekly_pace_usd']}",
        "",
        "## Miss Types",
        "",
    ]
    for key, count in summary["by_miss_type"].items():
        lines.append(f"- `{key}`: {count}")
    lines.extend(["", "## Top Blockers", "", "| Blocker | Rows | Missed entries | Oracle PnL | Incremental |", "|---|---:|---:|---:|---:|"])
    for row in summary["by_blocker"][:15]:
        lines.append(
            f"| `{row['blocker_reason']}` | {row['rows']} | {row['missed_entry_rows']} | "
            f"${row['oracle_net_pnl_usd']} | ${row['oracle_incremental_vs_actual_usd']} |"
        )
    lines.extend(["", "## Top Contexts", "", "| Context | Rows | Missed entries | Oracle PnL | Incremental |", "|---|---:|---:|---:|---:|"])
    for row in summary["by_context"][:15]:
        lines.append(
            f"| `{row['context_key']}` | {row['rows']} | {row['missed_entry_rows']} | "
            f"${row['oracle_net_pnl_usd']} | ${row['oracle_incremental_vs_actual_usd']} |"
        )
    lines.extend([
        "",
        "## Oracle Pattern Families",
        "",
        "| Family | State | Rows | Missed entries | Oracle PnL | Incremental |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in summary["by_pattern_family"][:15]:
        lines.append(
            f"| `{row['pattern_family']}` | `{row['promotion_state']}` | {row['rows']} | "
            f"{row['missed_entry_rows']} | ${row['oracle_net_pnl_usd']} | "
            f"${row['oracle_incremental_vs_actual_usd']} |"
        )
    lines.extend([
        "",
        "## Oracle Move Shapes",
        "",
        "| Move shape | Rows | Missed entries | Oracle PnL | Incremental |",
        "|---|---:|---:|---:|---:|",
    ])
    for row in summary["by_move_shape"][:15]:
        lines.append(
            f"| `{row['move_shape_category']}` | {row['rows']} | {row['missed_entry_rows']} | "
            f"${row['oracle_net_pnl_usd']} | ${row['oracle_incremental_vs_actual_usd']} |"
        )
    lines.extend(["", "## Top Missed Entries", "", "| Net $ | Bps | Reason | Context | Stage | State | Pressure |", "|---:|---:|---|---|---|---|---|"])
    for row in summary["top_missed_entries"][:20]:
        lines.append(
            f"| ${row['oracle_net_pnl_usd']} | {row['oracle_net_bps']} | `{row['blocker_reason']}` | "
            f"`{row['context_key']}` | `{row['trade_stage']}` | `{row['trade_option_state']}` | `{row['pressure_watch_state']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit live opportunities for hindsight missed winners.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--fee-bps", type=float, default=FEE_BPS)
    parser.add_argument("--notional-usd", type=float, default=NOTIONAL_USD)
    args = parser.parse_args()
    summary = build(
        data_dir=Path(args.data_dir),
        out_dir=Path(args.out_dir),
        fee_bps=float(args.fee_bps),
        notional_usd=float(args.notional_usd),
    )
    print(json.dumps({
        "schema": summary["schema"],
        "created_at": summary["created_at"],
        "counts": summary["counts"],
        "pnl": summary["pnl"],
        "pace": summary["pace"],
        "outputs": summary["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
