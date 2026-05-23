"""Historical RT run 2.

Replays the May 4-14 historical bin tape through the current live RT engine
(live_mock_trade_replay + mock_trade_replay + trade_exit_strategy) with the
current scenarios unchanged. The current oracle_winner_trade_list.json is
treated as the admission list as-is ("act like the trades were mapped"), which
is hindsight-derived; this run measures what current RT rules do when fed the
historic tape, not future PnL.

Each simulated step exposes only bars with ts <= sim_ts, so chunk windows in
current_status_from_visible cannot see future bars.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import live_mock_trade_replay as live_rt
from mock_trade_replay import (
    close_open_for_status,
    current_status_from_visible,
    load_bars,
    session_from_offset_hours,
    summarize_account,
    write_replay_outputs,
)
from strategy_library import reset_strategy_debug


ROOT = Path(__file__).resolve().parent
DEFAULT_EXIT_PARAMS = ROOT / "research" / "strategy_evolution" / "exit_params_h0_h168_v2_promoted_min5.json"
DEFAULT_OUT_ROOT = ROOT / "research" / "strategy_evolution" / "historical_rt_run2"
DEFAULT_BINS = {
    ("BTC", "Coinbase"): ROOT / "btc_coinbase_bins.json",
    ("BTC", "Kraken"): ROOT / "btc_kraken_bins.json",
    ("BTC", "Bybit"): ROOT / "btc_bybit_perp_bins.json",
    ("ETH", "Coinbase"): ROOT / "eth_coinbase_bins.json",
    ("ETH", "Kraken"): ROOT / "eth_kraken_bins.json",
    ("ETH", "Bybit"): ROOT / "eth_bybit_perp_bins.json",
}


def _json_default(value: Any) -> str:
    return str(value)


def _bars_up_to(bars: list[Any], end_index: int) -> list[Any]:
    return bars[: end_index + 1]


def _advance_index(bars: list[Any], sim_ts: float, previous: int) -> int:
    idx = previous
    while idx + 1 < len(bars) and float(getattr(bars[idx + 1], "ts", 0.0) or 0.0) <= sim_ts:
        idx += 1
    return idx


def _account_summary(accounts: dict[str, dict[str, Any]], settings: dict[str, Any]) -> dict[str, Any]:
    summaries = {aid: summarize_account(acc, settings) for aid, acc in accounts.items()}
    totals = {
        "trades": 0,
        "open": 0,
        "closed": 0,
        "realized_pnl_usd": 0.0,
        "closed_fees_usd": 0.0,
        "bank_open": 0,
        "bank_closed": 0,
        "bank_realized_pnl_usd": 0.0,
        "oracle_shadow_open": 0,
        "oracle_shadow_closed": 0,
        "oracle_shadow_realized_pnl_usd": 0.0,
    }
    shadow_reasons: dict[str, int] = {}
    close_reasons: dict[str, int] = {}
    strategies: dict[str, int] = {}
    sides: dict[str, int] = {}
    for account in accounts.values():
        for trade in account.get("trades") or []:
            totals["trades"] += 1
            status = str(trade.get("status") or "")
            role = str(trade.get("pnl_accounting_role") or "")
            realized = float(trade.get("realized_pnl_usd") or 0.0)
            if status == "open":
                totals["open"] += 1
            if status == "closed":
                totals["closed"] += 1
                totals["realized_pnl_usd"] += realized
                totals["closed_fees_usd"] += float(trade.get("fees_usd") or 0.0)
                reason = str(trade.get("close_reason") or trade.get("runner_exit_reason") or "")
                close_reasons[reason] = close_reasons.get(reason, 0) + 1
            if role == "bank_allocated":
                if status == "open":
                    totals["bank_open"] += 1
                if status == "closed":
                    totals["bank_closed"] += 1
                    totals["bank_realized_pnl_usd"] += live_rt.bank_realized_pnl_for_trade(trade)
            if role == "oracle_shadow":
                if status == "open":
                    totals["oracle_shadow_open"] += 1
                if status == "closed":
                    totals["oracle_shadow_closed"] += 1
                    totals["oracle_shadow_realized_pnl_usd"] += realized
                reason = str(trade.get("bank_allocation_reason") or trade.get("bank_entry_shadow_reason") or "oracle_shadow")
                shadow_reasons[reason] = shadow_reasons.get(reason, 0) + 1
            strategies[str(trade.get("trade_strategy_id") or "")] = strategies.get(str(trade.get("trade_strategy_id") or ""), 0) + 1
            sides[str(trade.get("side") or "")] = sides.get(str(trade.get("side") or ""), 0) + 1
    for key in ("realized_pnl_usd", "closed_fees_usd", "bank_realized_pnl_usd", "oracle_shadow_realized_pnl_usd"):
        totals[key] = round(float(totals[key]), 8)
    return {
        "accounts": summaries,
        "totals": totals,
        "shadow_reasons": sorted(shadow_reasons.items(), key=lambda row: (-row[1], row[0])),
        "close_reasons": sorted(close_reasons.items(), key=lambda row: (-row[1], row[0])),
        "strategies": sorted(strategies.items(), key=lambda row: (-row[1], row[0])),
        "sides": sorted(sides.items(), key=lambda row: (-row[1], row[0])),
    }


def run(args: argparse.Namespace) -> None:
    reset_strategy_debug()
    run_id = args.run_id or f"historical_rt_run2_{time.strftime('%Y%m%d_%H%M%S_utc', time.gmtime())}"
    out_dir = Path(args.output_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    live_rt.OPPORTUNITY_LOG = out_dir / "historical_rt_run2_opportunities.jsonl"
    live_rt.TRADE_SNAPSHOT = out_dir / "historical_rt_run2_trades.jsonl"

    bins = {key: load_bars(str(path)) for key, path in DEFAULT_BINS.items() if path.exists()}
    bins = {key: bars for key, bars in bins.items() if bars}
    if not bins:
        raise SystemExit("no historical bins found")
    all_ts = sorted({float(getattr(bar, "ts", 0.0) or 0.0) for bars in bins.values() for bar in bars})
    if not all_ts:
        raise SystemExit("no bar timestamps in historical bins")
    global_start = min(all_ts)

    settings = live_rt._prepare_settings(Path(args.exit_params))
    # No scenario overrides. Historical RT uses the same admission (current oracle_winner_trade_list.json)
    # and the same exit rules as live RT — only the data feed differs (historical bins vs live tape).

    state: dict[str, Any] = {
        "schema": "historical_rt_run2_state_v2",
        "run_id": run_id,
        "mode": "historical_rt_chronological_no_lookahead",
        "source_bins": {f"{asset}|{venue}": str(DEFAULT_BINS[(asset, venue)]) for asset, venue in bins},
        "accounts": {scenario["id"]: {"scenario": scenario, "trades": []} for scenario in settings["scenarios"]},
        "seen_chunks": [],
        "quotes": {},
        "global_start": global_start,
        "status_count": 0,
        "started_wall_utc": time.time(),
    }
    epoch = live_rt._start_policy_epoch(settings, state)
    accounts = state["accounts"]
    account_ids = [str(scenario.get("id") or "") for scenario in settings["scenarios"]]
    trackers: dict[str, dict[tuple[str, str], dict[str, Any]]] = {aid: {} for aid in account_ids}
    quotes: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    seen_chunks: set[str] = set()
    latest_indices = {key: -1 for key in bins}
    status_count = 0
    last_save = time.time()

    state_path = out_dir / "historical_rt_run2_state.json"
    print(f"[historical-rt-run2] run_id={run_id}", flush=True)
    print(f"[historical-rt-run2] simulated_minutes={len(all_ts)} venue_bins={len(bins)}", flush=True)
    print(f"[historical-rt-run2] policy_epoch={epoch['policy_epoch_id']}", flush=True)
    print(f"[historical-rt-run2] scenarios={[str(s.get('id') or '') for s in settings['scenarios']]}", flush=True)
    print(f"[historical-rt-run2] tape_start_utc={global_start} tape_end_utc={max(all_ts)} hours={round((max(all_ts)-global_start)/3600.0,2)}", flush=True)

    for step, sim_ts in enumerate(all_ts, start=1):
        changed = False
        processed = 0
        for (asset, venue), bars in bins.items():
            previous_idx = latest_indices[(asset, venue)]
            idx = _advance_index(bars, sim_ts, previous_idx)
            if idx <= previous_idx:
                continue
            latest_indices[(asset, venue)] = idx
            visible_bars = live_rt._recent_tail_bars(_bars_up_to(bars, idx))
            if not visible_bars:
                continue
            scenario_statuses = []
            bucket_session = session_from_offset_hours((float(visible_bars[-1].ts) - global_start) / 3600.0)
            for scenario in settings["scenarios"]:
                account_id = str(scenario.get("id") or "")
                status, inputs = current_status_from_visible(
                    asset,
                    venue,
                    visible_bars,
                    trackers.setdefault(account_id, {}),
                    float(args.synthetic_spread_bps),
                    bucket_session,
                    list(scenario.get("requested_strategy_families") or []),
                    bool(scenario.get("allow_context_probes")),
                    bool(scenario.get("allow_promoted_context_rerun")),
                    live_rt._strategy_runtime_flags(scenario),
                )
                if status is None:
                    continue
                inputs["bucket_session"] = session_from_offset_hours((float(status.last_update_utc) - global_start) / 3600.0)
                bid = float(status.current_bid or status.current_price or 0.0)
                ask = float(status.current_ask or status.current_price or 0.0)
                mid = float(status.current_price or ((bid + ask) / 2.0) or 0.0)
                quote = (bid, ask, mid, float(status.last_update_utc))
                scenario_statuses.append((account_id, scenario, status, inputs, quote))
            if not scenario_statuses:
                continue
            first_status = scenario_statuses[0][2]
            first_inputs = scenario_statuses[0][3]
            dedupe = live_rt._chunk_dedupe_key(asset, venue, first_inputs)
            if not dedupe or dedupe in seen_chunks:
                continue
            seen_chunks.add(dedupe)
            status_count += 1
            processed += 1
            quotes[(asset, venue)] = scenario_statuses[0][4]
            settings["current_replay_offset_hours"] = (float(first_status.last_update_utc) - global_start) / 3600.0
            for account_id, scenario, status, inputs, quote in scenario_statuses:
                account = accounts[account_id]
                before = json.dumps(account["trades"], sort_keys=True, default=_json_default)
                close_open_for_status(account, scenario, status, quote)
                opened = live_rt._maybe_log_and_open(
                    account=account,
                    scenario=scenario,
                    status=status,
                    settings=settings,
                    quote=quote,
                    quotes=quotes,
                    inputs=inputs,
                )
                after = json.dumps(account["trades"], sort_keys=True, default=_json_default)
                changed = changed or opened or before != after
        if processed or changed:
            state["accounts"] = accounts
            state["trackers"] = live_rt._dump_account_trackers(trackers)
            state["quotes"] = live_rt._quotes_to_string_keys(quotes)
            state["seen_chunks"] = sorted(seen_chunks)
            state["status_count"] = status_count
            state["simulated_ts_utc"] = sim_ts
            state["bank_allocation"] = live_rt._apply_bank_allocation(accounts, quotes, settings)
        if time.time() - last_save >= float(args.save_seconds):
            live_rt._save_state(state_path, state)
            live_rt._rewrite_trade_snapshot(accounts)
            last_save = time.time()
            pct = round(100.0 * step / len(all_ts), 2)
            print(f"[historical-rt-run2] step={step}/{len(all_ts)} ({pct}%) status_count={status_count}", flush=True)

    state["finished_wall_utc"] = time.time()
    state["completed"] = True
    state["bank_allocation"] = live_rt._apply_bank_allocation(accounts, quotes, settings)
    state["summary"] = _account_summary(accounts, settings)
    live_rt._save_state(state_path, state)
    live_rt._rewrite_trade_snapshot(accounts)
    write_replay_outputs(
        out_dir,
        settings,
        accounts,
        requested_hours=max(0.0, (max(all_ts) - global_start) / 3600.0),
        completed_hours=max(0.0, (max(all_ts) - global_start) / 3600.0),
        stride_minutes=int(args.stride_minutes),
        status_count=status_count,
        file_stem="historical_rt_run2",
        checkpoint=True,
    )
    (out_dir / "historical_rt_run2_summary.json").write_text(
        json.dumps(state["summary"], indent=2, default=_json_default),
        encoding="utf-8",
    )
    print(f"[historical-rt-run2] completed status_count={status_count} out={out_dir}", flush=True)
    print("[historical-rt-run2] totals:", flush=True)
    print(json.dumps(state["summary"]["totals"], indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Historical RT run 2: replay May 4-14 historical bins through current live RT engine, exact rules, chronological clock, no lookahead.",
    )
    parser.add_argument("--output-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--exit-params", default=str(DEFAULT_EXIT_PARAMS))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--synthetic-spread-bps", type=float, default=2.0)
    parser.add_argument("--stride-minutes", type=int, default=15)
    parser.add_argument("--save-seconds", type=float, default=30.0)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
