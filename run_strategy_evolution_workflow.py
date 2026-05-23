from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTIVE_STRATEGIES = [
    "MEAN_REVERSION_CHOP",
    "NEWS_BREAKOUT",
    "LIQUIDITY_SQUEEZE",
    "VOL_BREAKOUT",
    "BASIS_DISLOCATION",
    "RELATIVE_STRENGTH",
]

QUEUE_PATH = Path("research") / "strategy_evolution" / "_queue.json"
ROUTING_PATH = Path("research") / "strategy_evolution" / "_routing.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _top_queue_family() -> str:
    queue = _load_json(QUEUE_PATH)
    for row in queue.get("items") or []:
        family = str(row.get("family") or "").strip().upper()
        if family:
            return family
    return ""


def _run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def _summarize_run(output_dir: Path) -> dict[str, Any]:
    results = _load_json(output_dir / "mock_replay_results.json")
    relay = results.get("refrag_relay") or {}
    family_reports = relay.get("family_reports") or {}
    strategies = results.get("strategy_summaries") or []
    queue = _load_json(output_dir / "evolved_families" / "_queue.json")
    experiments = _load_json(output_dir / "evolved_families" / "_candidate_experiments.json")
    attempts_path = output_dir / "evolved_families" / "_attempts.jsonl"
    attempt_count = 0
    if attempts_path.exists():
        attempt_count = sum(1 for line in attempts_path.read_text(encoding="utf-8").splitlines() if line.strip())
    mock_trades: list[dict[str, Any]] = []
    for account_id, account in (results.get("accounts") or {}).items():
        for index, trade in enumerate((account or {}).get("trades") or [], start=1):
            mock_trades.append({
                "account": str(account_id),
                "index": index,
                "strategy_id": str(trade.get("trade_strategy_id") or ""),
                "variant_id": str(trade.get("trade_strategy_variant_id") or ""),
                "exit_strategy_id": str(trade.get("exit_strategy_id") or trade.get("exit_management_model") or ""),
                "exit_strategy_label": str(trade.get("exit_strategy_label") or ""),
                "suggested_exit_strategy_id": str(trade.get("suggested_exit_strategy_id") or ""),
                "exit_tp1_bps": float(trade.get("exit_tp1_bps") or 0.0),
                "exit_scale_out_fraction": float(trade.get("exit_scale_out_fraction") or 0.0),
                "exit_runner_trail_bps": float(trade.get("exit_runner_trail_bps") or 0.0),
                "exit_max_hold_minutes": float(trade.get("exit_max_hold_minutes") or 0.0),
                "scale_out_count": int(trade.get("scale_out_count") or 0),
                "scale_out_fraction_realized": float(trade.get("scale_out_fraction_realized") or 0.0),
                "scale_out_tp1_bps": float(trade.get("scale_out_tp1_bps") or 0.0),
                "runner_exit_reason": str(trade.get("runner_exit_reason") or ""),
                "exit_legs": list(trade.get("exit_legs") or []),
                "exit_decision": dict(trade.get("exit_decision") or {}),
                "last_exit_decision": dict(trade.get("last_exit_decision") or {}),
                "deferred_exit_signals": list(trade.get("deferred_exit_signals") or []),
                "asset": str(trade.get("asset") or ""),
                "venue": str(trade.get("venue") or ""),
                "side": str(trade.get("side") or ""),
                "bucket_session": str(trade.get("bucket_session") or ""),
                "status": str(trade.get("status") or ""),
                "replay_offset_hours": float(trade.get("replay_offset_hours") or 0.0),
                "hold_minutes": float(trade.get("hold_minutes") or 0.0),
                "qty": float(trade.get("qty") or 0.0),
                "entry": float(trade.get("fill_price") or 0.0),
                "exit": float(trade.get("exit_price") or 0.0),
                "hypothetical_notional": float(trade.get("hypothetical_notional") or trade.get("notional") or 0.0),
                "actual_execution": bool(trade.get("actual_execution")),
                "actual_notional": float(trade.get("actual_notional") or 0.0),
                "gross_pnl_usd": float(trade.get("gross_pnl_usd") or 0.0),
                "fees_usd": float(trade.get("fees_usd") or 0.0),
                "pnl_usd": float(trade.get("realized_pnl_usd") or 0.0),
                "pnl_R": float(trade.get("profit_R") or 0.0),
                "close_reason": str(trade.get("close_reason") or ""),
                "bucket_id": str(trade.get("bucket_id") or ""),
                "learning_capital_model": str(trade.get("learning_capital_model") or ""),
                "counterfactual_exit_audit": dict(trade.get("counterfactual_exit_audit") or {}),
            })
    return {
        "output_dir": str(output_dir),
        "status_count": int(results.get("status_count") or 0),
        "trade_count": int(relay.get("trade_count") or 0),
        "mock_trades": mock_trades,
        "strategy_summaries": strategies,
        "family_reports": family_reports,
        "next_queue_family": str(((queue.get("items") or [{}])[0]).get("family") or ""),
        "candidate_experiment_count": len(experiments.get("experiments") or []),
        "attempt_count": attempt_count,
    }


def _bucket_context(bucket_id: str) -> str:
    parts = [str(x or "").strip() for x in str(bucket_id or "").split("|")]
    if len(parts) != 5:
        return ""
    _, asset, venue, side, session = parts
    return "|".join([asset.upper(), venue.lower(), side.lower(), session.lower()])


def _winner_hit(
    run_summary: dict[str, Any],
    *,
    min_family_samples: int,
    pnl_r_floor: float,
    min_trades: int,
) -> dict[str, Any]:
    routing = _load_json(ROUTING_PATH)
    context_profiles = routing.get("context_profiles") or {}
    best_seen: dict[str, Any] = {}
    family_reports = run_summary.get("family_reports") or {}
    for family, report in family_reports.items():
        family = str(family or "").strip().lower()
        if int((report or {}).get("trades") or 0) <= 0:
            continue
        buckets = list((report or {}).get("best_buckets") or []) + list((report or {}).get("worst_buckets") or [])
        seen_bucket_ids: set[str] = set()
        for bucket in buckets:
            bucket_id = str(bucket.get("bucket_id") or "")
            if not bucket_id or bucket_id in seen_bucket_ids:
                continue
            seen_bucket_ids.add(bucket_id)
            context = _bucket_context(bucket_id)
            if not context:
                continue
            pnl_r = float(bucket.get("pnl_R") or 0.0)
            trades = int(bucket.get("trades") or 0)
            profile = dict(context_profiles.get(context) or {})
            tested = int(profile.get("tested_family_count") or 0)
            score = float(profile.get("best_fit_score") or 0.0)
            if score > float(best_seen.get("best_fit_score") or -1.0):
                best_seen = dict(profile)
            if pnl_r <= pnl_r_floor or trades < min_trades or tested < min_family_samples:
                continue
            best_family = str(profile.get("best_family") or "").strip().lower()
            if best_family and best_family != family:
                continue
            return {
                "hit": True,
                "stop_reason": "current_pass_winner",
                "context": context,
                "winning_family": family,
                "winner_pnl_R": pnl_r,
                "winner_trades": trades,
                "best_fit_score": score,
                "tested_family_count": tested,
                "min_family_samples": min_family_samples,
                "pnl_R_floor": pnl_r_floor,
                "profile": profile,
                "bucket": bucket,
            }
    return {
        "hit": False,
        "min_family_samples": min_family_samples,
        "pnl_R_floor": pnl_r_floor,
        "min_trades": min_trades,
        "best_seen": best_seen,
    }


def _run_replay_and_research(
    *,
    data_dir: str,
    output_dir: Path,
    start_hour: float,
    hours: float,
    stride_minutes: int,
    allowed_strategies: str,
    disable_news_context: bool,
    exit_params: str,
    allow_context_probes: bool = False,
    allow_promoted_context_rerun: bool = False,
) -> None:
    replay_cmd = [
        sys.executable,
        "mock_trade_replay.py",
        "--data-dir",
        str(data_dir),
        "--output-dir",
        str(output_dir),
        "--start-hour",
        str(start_hour),
        "--hours",
        str(hours),
        "--stride-minutes",
        str(stride_minutes),
        "--checkpoint-hours",
        "0",
        "--no-enforce-bucket-health",
        "--no-enforce-daily-limits",
        "--allowed-strategies",
        str(allowed_strategies),
        "--exit-params",
        str(exit_params),
    ]
    if disable_news_context:
        replay_cmd.append("--disable-news-context")
    if allow_context_probes:
        replay_cmd.append("--allow-context-probes")
    if allow_promoted_context_rerun:
        replay_cmd.append("--allow-promoted-context-rerun")
    _run(replay_cmd)

    autoresearch_cmd = [
        sys.executable,
        "market_strategy_autoresearch.py",
        "--replay-results",
        str(output_dir / "mock_replay_results.json"),
        "--output-path",
        str(output_dir / "market_strategy_autoresearch_all_results.json"),
        "--strategies",
        "ALL",
    ]
    _run(autoresearch_cmd)


def _fmt_money(value: float) -> str:
    return f"${value:+.2f}"


def _fmt_r(value: float) -> str:
    return f"{value:+.2f}R"


def _positive_counterfactual_usd(trade: dict[str, Any], horizon: str) -> float:
    audit = trade.get("counterfactual_exit_audit") or {}
    value = ((audit.get("horizons") or {}).get(horizon) or {}).get("best_incremental_vs_actual_usd")
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _append_exit_strategy_summary(lines: list[str], listed_trades: list[tuple[dict[str, Any], dict[str, Any]]]) -> None:
    if not listed_trades:
        return
    grouped: dict[str, dict[str, Any]] = {}
    total_scale_outs = 0
    total_left_30 = 0.0
    total_left_60 = 0.0
    winner_left_30 = 0.0
    winner_left_60 = 0.0
    for _run, trade in listed_trades:
        profile = str(trade.get("exit_strategy_id") or "unknown")
        row = grouped.setdefault(profile, {
            "trades": 0,
            "wins": 0,
            "pnl_usd": 0.0,
            "pnl_R": 0.0,
            "scale_outs": 0,
            "trailing_stops": 0,
            "left_30": 0.0,
            "left_60": 0.0,
        })
        pnl_usd = float(trade.get("pnl_usd") or 0.0)
        pnl_r = float(trade.get("pnl_R") or 0.0)
        scale_outs = int(trade.get("scale_out_count") or 0)
        left_30 = _positive_counterfactual_usd(trade, "30m")
        left_60 = _positive_counterfactual_usd(trade, "60m")
        row["trades"] += 1
        row["wins"] += int(pnl_usd > 0)
        row["pnl_usd"] += pnl_usd
        row["pnl_R"] += pnl_r
        row["scale_outs"] += scale_outs
        row["trailing_stops"] += int(str(trade.get("runner_exit_reason") or trade.get("close_reason") or "") == "trailing_stop")
        row["left_30"] += left_30
        row["left_60"] += left_60
        total_scale_outs += scale_outs
        total_left_30 += left_30
        total_left_60 += left_60
        if pnl_usd > 0:
            winner_left_30 += left_30
            winner_left_60 += left_60

    lines.extend([
        "",
        "### Exit Strategy Summary",
        "",
        f"- Scale-outs recorded: {total_scale_outs}",
        f"- Winner clipping evidence: {_fmt_money(winner_left_30)} left within 30m, {_fmt_money(winner_left_60)} within 60m",
        f"- All-trade counterfactual opportunity, including losers that could have recovered: {_fmt_money(total_left_30)} within 30m, {_fmt_money(total_left_60)} within 60m",
        "",
        "| Exit profile | Trades | Wins | Net PnL | R | Scale-outs | Trailing exits | +30m left | +60m left |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for profile, row in sorted(grouped.items(), key=lambda item: float(item[1]["pnl_R"]), reverse=True):
        lines.append(
            f"| `{profile}` | {int(row['trades'])} | {int(row['wins'])} | "
            f"{_fmt_money(float(row['pnl_usd']))} | {_fmt_r(float(row['pnl_R']))} | "
            f"{int(row['scale_outs'])} | {int(row['trailing_stops'])} | "
            f"{_fmt_money(float(row['left_30']))} | {_fmt_money(float(row['left_60']))} |"
        )


def _write_analysis_paper(summary_path: Path, payload: dict[str, Any]) -> Path:
    paper_path = summary_path.with_name(summary_path.stem.replace("workflow_summary_", "analysis_paper_") + ".md")
    lines: list[str] = [
        "# Refrag 6-Hour Evolution Analysis",
        "",
        f"Source summary: `{summary_path.name}`",
        f"Created: {payload.get('created_at') or ''}",
        "",
    ]
    total_evidence_usd = 0.0
    total_evidence_r = 0.0
    total_winner_usd = 0.0
    total_winner_r = 0.0
    total_trades = 0
    for summary in payload.get("summaries") or []:
        start = float(summary.get("start_hour") or 0.0)
        hours = float(summary.get("hours") or 0.0)
        hit = summary.get("hit") or {}
        lines.extend([
            f"## Hours {start:g}-{start + hours:g}",
            "",
        ])
        passes = list(summary.get("passes") or [])
        if not passes and summary.get("output_dir"):
            passes = [summary]
        first_sweep = [p for p in passes if int(p.get("pass_number") or 1) == 1]
        if not first_sweep:
            first_sweep = passes
        evidence_usd = 0.0
        evidence_r = 0.0
        trades = 0
        family_rows = []
        for run in first_sweep:
            family = str(run.get("allowed_strategy") or "")
            run_trades = int(run.get("trade_count") or 0)
            trades += run_trades
            family_usd = 0.0
            family_r = 0.0
            for report in (run.get("family_reports") or {}).values():
                family_usd += float(report.get("pnl_usd") or 0.0)
                family_r += float(report.get("pnl_R") or 0.0)
            evidence_usd += family_usd
            evidence_r += family_r
            family_rows.append((family, run_trades, family_usd, family_r, int(run.get("attempt_count") or 0), int(run.get("candidate_experiment_count") or 0)))
        total_evidence_usd += evidence_usd
        total_evidence_r += evidence_r
        total_trades += trades

        winner_usd = 0.0
        winner_r = 0.0
        winner = "none"
        context = "none"
        if hit.get("hit"):
            winner = str(hit.get("winning_family") or "none")
            context = str(hit.get("context") or "none")
            winner_bucket_id = str(((hit.get("bucket") or {}).get("bucket_id")) or "")
            for run in first_sweep:
                rh = run.get("routing_hit") or {}
                if rh.get("hit") and str(rh.get("winning_family") or "") == winner and str(rh.get("context") or "") == context:
                    winner_r = float(rh.get("winner_pnl_R") or 0.0)
                    bucket_trades = [
                        trade
                        for trade in (run.get("mock_trades") or [])
                        if str(trade.get("bucket_id") or "") == winner_bucket_id
                    ]
                    if bucket_trades:
                        winner_usd = sum(float(trade.get("pnl_usd") or 0.0) for trade in bucket_trades)
                        winner_r = sum(float(trade.get("pnl_R") or 0.0) for trade in bucket_trades)
                    else:
                        winner_usd = float(((run.get("family_reports") or {}).get(winner) or {}).get("pnl_usd") or 0.0)
                    break
        total_winner_usd += winner_usd
        total_winner_r += winner_r

        lines.extend([
            f"- Winner route: `{winner}` on `{context}`",
            f"- Qualified mock route PnL: {_fmt_money(winner_usd)} / {_fmt_r(winner_r)}",
            f"- Research evidence outcome, not booked PnL: {_fmt_money(evidence_usd)} / {_fmt_r(evidence_r)}",
            "- External fees/costs booked to PnL: $+0.00 unless a broker/exchange/platform fee is actually charged.",
            f"- Evidence trades simulated in first sweep: {trades}",
            "",
            "| Family run | Evidence trades | Evidence USD | Evidence R | Attempts JSON | Candidate experiments |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for family, run_trades, family_usd, family_r, attempts, experiments in family_rows:
            lines.append(f"| `{family}` | {run_trades} | {_fmt_money(family_usd)} | {_fmt_r(family_r)} | {attempts} | {experiments} |")
        listed_trades = [
            (run, trade)
            for run in first_sweep
            for trade in (run.get("mock_trades") or [])
        ]
        if listed_trades:
            lines.extend([
                "",
                "### Mock Trades Opened",
                "",
                "These are replay/evidence trades. `actual_execution` shows whether anything was really bought or sold.",
                "",
                "| # | Family | Exit profile | Close reason | Scale-outs | Runner reason | Asset | Venue | Side | Replay hr | Qty | Entry | Exit | Gross PnL | Fees | Net PnL | R | Best +30m vs exit | Actual execution | Bucket |",
                "|---:|---|---|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
            ])
            for number, (run, trade) in enumerate(listed_trades, start=1):
                family = str(trade.get("strategy_id") or run.get("allowed_strategy") or "")
                exit_profile = str(trade.get("exit_strategy_id") or "")
                close_reason = str(trade.get("close_reason") or "")
                scale_outs = int(trade.get("scale_out_count") or 0)
                runner_reason = str(trade.get("runner_exit_reason") or "")
                actual_execution = "yes" if bool(trade.get("actual_execution")) else "no"
                exit_audit = trade.get("counterfactual_exit_audit") or {}
                plus_30 = ((exit_audit.get("horizons") or {}).get("30m") or {}).get("best_incremental_vs_actual_usd")
                lines.append(
                    "| "
                    f"{number} | `{family}` | `{exit_profile}` | `{close_reason}` | {scale_outs} | `{runner_reason}` | `{trade.get('asset') or ''}` | `{trade.get('venue') or ''}` | `{trade.get('side') or ''}` | "
                    f"{float(trade.get('replay_offset_hours') or 0.0):.2f} | "
                    f"{float(trade.get('qty') or 0.0):.6f} | "
                    f"{float(trade.get('entry') or 0.0):.2f} | "
                    f"{float(trade.get('exit') or 0.0):.2f} | "
                    f"{_fmt_money(float(trade.get('gross_pnl_usd') or 0.0))} | "
                    f"{_fmt_money(float(trade.get('fees_usd') or 0.0))} | "
                    f"{_fmt_money(float(trade.get('pnl_usd') or 0.0))} | "
                    f"{_fmt_r(float(trade.get('pnl_R') or 0.0))} | "
                    f"{_fmt_money(float(plus_30 or 0.0)) if plus_30 is not None else ''} | "
                    f"{actual_execution} | `{trade.get('bucket_id') or ''}` |"
                )
            _append_exit_strategy_summary(lines, listed_trades)
        lines.extend([
            "",
            "### Carry Forward",
            "",
        ])
        if winner_r > 0:
            lines.append(f"- Keep `{winner}` callable only for exact context `{context}` unless later evidence changes it.")
        else:
            lines.append("- No positive-PnL exact-context winner. Treat this slice as no-trade/failed-attempt evidence and generate variants before calling similar contexts again.")
        lines.append("- Preserve no-trade records as strategy-generation input; do not discard quiet windows.")
        lines.append("")

    lines.extend([
        "## Running Totals",
        "",
        f"- Qualified mock route PnL: {_fmt_money(total_winner_usd)} / {_fmt_r(total_winner_r)}",
        f"- Research evidence outcome, not booked PnL: {_fmt_money(total_evidence_usd)} / {_fmt_r(total_evidence_r)}",
        "- External fees/costs booked to PnL: $+0.00 unless a broker/exchange/platform fee is actually charged.",
        f"- Evidence trades simulated: {total_trades}",
        "",
    ])
    paper_path.write_text("\n".join(lines), encoding="utf-8")
    return paper_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run unattended Refrag self-evolving practice replay slices."
    )
    parser.add_argument("--data-dir", default=".")
    parser.add_argument("--output-root", default="strategy_evolution_workflow_runs")
    parser.add_argument("--start-hour", type=float, default=0.0)
    parser.add_argument("--hours", type=float, default=6.0)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--stride-minutes", type=int, default=15)
    parser.add_argument("--disable-news-context", action="store_true")
    parser.add_argument(
        "--all-families-until-hit",
        action="store_true",
        help="For each 6h window, run active strategies as passes until the current pass produces a winning exact context.",
    )
    parser.add_argument(
        "--passes-per-family",
        type=int,
        default=1,
        help="Safety cap for calibration cycles; winner detection, not this number, is the stop condition.",
    )
    parser.add_argument("--fit-threshold", type=float, default=85.0, help=argparse.SUPPRESS)
    parser.add_argument("--min-context-family-samples", type=int, default=1)
    parser.add_argument("--winner-pnl-r-floor", type=float, default=0.0)
    parser.add_argument("--winner-min-trades", type=int, default=1)
    parser.add_argument("--exit-params", default="exit_params.json")
    parser.add_argument(
        "--allow-promoted-context-rerun",
        action="store_true",
        help="For evidence-mining runs only, re-sample already promoted contexts instead of standing down.",
    )
    parser.add_argument(
        "--allowed-strategies",
        default=",".join(ACTIVE_STRATEGIES),
        help="Comma-separated strategy ids available to the learning loop.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summaries: list[dict[str, Any]] = []

    for idx in range(max(0, int(args.iterations))):
        start_hour = float(args.start_hour) + idx * float(args.hours)
        if args.all_families_until_hit:
            family_order = [
                family.strip().upper()
                for family in str(args.allowed_strategies).split(",")
                if family.strip()
            ] or list(ACTIVE_STRATEGIES)
            calibration_summary = {
                "mode": "all_families_until_hit",
                "start_hour": start_hour,
                "hours": float(args.hours),
                "stop_condition": "current_pass_positive_pnl_exact_instance",
                "min_context_family_samples": int(args.min_context_family_samples),
                "winner_pnl_R_floor": float(args.winner_pnl_r_floor),
                "winner_min_trades": int(args.winner_min_trades),
                "safety_cycles_per_family": int(args.passes_per_family),
                "passes": [],
                "hit": None,
            }
            for pass_idx in range(max(1, int(args.passes_per_family))):
                for family in family_order:
                    output_dir = output_root / (
                        f"slice_{idx + 1:02d}_h{start_hour:g}_pass{pass_idx + 1:02d}_{family.lower()}_{run_stamp}"
                    )
                    _run_replay_and_research(
                        data_dir=str(args.data_dir),
                        output_dir=output_dir,
                        start_hour=start_hour,
                        hours=float(args.hours),
                        stride_minutes=int(args.stride_minutes),
                        allowed_strategies=family,
                        disable_news_context=bool(args.disable_news_context),
                        exit_params=str(args.exit_params),
                        allow_context_probes=True,
                        allow_promoted_context_rerun=bool(args.allow_promoted_context_rerun),
                    )
                    run_summary = _summarize_run(output_dir)
                    hit = _winner_hit(
                        run_summary,
                        min_family_samples=int(args.min_context_family_samples),
                        pnl_r_floor=float(args.winner_pnl_r_floor),
                        min_trades=int(args.winner_min_trades),
                    )
                    run_summary.update({
                        "pass_number": pass_idx + 1,
                        "allowed_strategy": family,
                        "routing_hit": hit,
                    })
                    calibration_summary["passes"].append(run_summary)
                    if hit.get("hit") and not calibration_summary.get("hit"):
                        calibration_summary["hit"] = hit
                if calibration_summary.get("hit"):
                    summaries.append(calibration_summary)
                    break
            if not calibration_summary.get("hit"):
                calibration_summary["hit"] = _winner_hit(
                    calibration_summary["passes"][-1] if calibration_summary["passes"] else {},
                    min_family_samples=int(args.min_context_family_samples),
                    pnl_r_floor=float(args.winner_pnl_r_floor),
                    min_trades=int(args.winner_min_trades),
                )
                summaries.append(calibration_summary)
        else:
            queue_family = _top_queue_family() or "default"
            output_dir = output_root / f"slice_{idx + 1:02d}_h{start_hour:g}_{queue_family.lower()}_{run_stamp}"
            _run_replay_and_research(
                data_dir=str(args.data_dir),
                output_dir=output_dir,
                start_hour=start_hour,
                hours=float(args.hours),
                stride_minutes=int(args.stride_minutes),
                allowed_strategies=str(args.allowed_strategies),
                disable_news_context=bool(args.disable_news_context),
                exit_params=str(args.exit_params),
                allow_context_probes=True,
                allow_promoted_context_rerun=bool(args.allow_promoted_context_rerun),
            )
            run_summary = _summarize_run(output_dir)
            run_summary.update({
                "start_hour": start_hour,
                "hours": float(args.hours),
                "pass_number": 1,
                "allowed_strategy": str(args.allowed_strategies),
                "routing_hit": _winner_hit(
                    run_summary,
                    min_family_samples=int(args.min_context_family_samples),
                    pnl_r_floor=float(args.winner_pnl_r_floor),
                    min_trades=int(args.winner_min_trades),
                ),
            })
            run_summary["hit"] = run_summary["routing_hit"]
            summaries.append(run_summary)

    summary_path = output_root / f"workflow_summary_{run_stamp}.json"
    payload = {
        "schema": "strategy_evolution_workflow_summary_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "iterations": int(args.iterations),
        "hours_per_iteration": float(args.hours),
        "mode": "all_families_until_hit" if args.all_families_until_hit else "queue",
        "summaries": summaries,
    }
    paper_path = summary_path.with_name(
        summary_path.stem.replace("workflow_summary_", "analysis_paper_") + ".md"
    )
    payload["analysis_paper"] = str(paper_path)
    for summary in summaries:
        summary["analysis_paper"] = str(paper_path)
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    paper_path = _write_analysis_paper(summary_path, payload)
    print(f"wrote {summary_path}", flush=True)
    print(f"wrote {paper_path}", flush=True)


if __name__ == "__main__":
    main()
