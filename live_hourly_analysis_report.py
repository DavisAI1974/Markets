from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
LIVE_DIR = EVOLUTION_DIR / "live_mock_replay"
OUT_JSON = LIVE_DIR / "live_hourly_analysis.json"
OUT_MD = LIVE_DIR / "live_hourly_analysis.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _run_step(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "value": fn(), "error": ""}
    except Exception as exc:
        return {"ok": False, "value": {}, "error": f"{type(exc).__name__}: {exc}"}


def _money(value: Any) -> str:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        number = 0.0
    return f"${number:+.2f}"


def _pct(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return ""


def _top_rows(rows: Any, limit: int = 8) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)][:limit]


def _render_allocation(summary: dict[str, Any]) -> list[str]:
    lines = ["## Bank Allocation", ""]
    candidates = summary.get("current_open_candidates") if isinstance(summary.get("current_open_candidates"), dict) else {}
    lines.append(f"- Open answer-backed candidates: {candidates.get('count', 0)}")
    runtime = summary.get("runtime_embedded_allocation") if isinstance(summary.get("runtime_embedded_allocation"), dict) else {}
    lines.append(f"- Runtime embedded model: `{runtime.get('model') or ''}`")
    lines.append("")
    models = summary.get("allocation_models") if isinstance(summary.get("allocation_models"), list) else []
    if models:
        lines.extend(["| Model | Slots | Max weight | Est open PnL | Weighted net bps |", "|---|---:|---:|---:|---:|"])
        for model in models[:7]:
            lines.append(
                f"| `{model.get('model')}` | {model.get('slots_used')} | {model.get('max_position_weight_pct')}% | "
                f"{_money(model.get('estimated_open_net_pnl_usd_after_fees'))} | {model.get('weighted_net_unrealized_bps_after_fees')} |"
            )
        lines.append("")
    quality = summary.get("selection_quality") if isinstance(summary.get("selection_quality"), dict) else {}
    history = quality.get("all_matched_history") if isinstance(quality.get("all_matched_history"), dict) else {}
    if history:
        lines.extend(
            [
                f"- 100% on one top-score exact oracle-best hit rate: {_pct(history.get('single_best_score_exact_hit_pct'))}",
                f"- Oracle-best inside top 5 score-ranked candidates: {_pct(history.get('oracle_best_in_top5_score_pct'))}",
                f"- Single-trade oracle capture: {_pct(history.get('single_best_score_capture_pct'))}",
                "",
            ]
        )
    return lines


def _render_hindsight(summary: dict[str, Any]) -> list[str]:
    counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else {}
    pnl = summary.get("pnl") if isinstance(summary.get("pnl"), dict) else {}
    pace = summary.get("pace") if isinstance(summary.get("pace"), dict) else {}
    lines = [
        "## Hindsight Oracle Audit",
        "",
        f"- Audited rows: {counts.get('audited_rows')}",
        f"- Oracle winner rows after fees: {counts.get('oracle_winner_rows_after_fees')}",
        f"- Missed entry rows: {counts.get('missed_entry_rows')}",
        f"- Exit missed / fee leak rows: {counts.get('exit_missed_or_fee_leak_rows')}",
        f"- Closed actual realized PnL: {_money(pnl.get('closed_actual_realized_pnl_usd'))}",
        f"- Oracle winner net PnL: {_money(pnl.get('oracle_winner_net_pnl_usd'))}",
        f"- Oracle winner weekly pace: {_money(pace.get('oracle_winner_weekly_pace_usd'))}",
        "",
    ]
    rows = _top_rows(summary.get("by_pattern_family"), 8)
    if rows:
        lines.extend(["| Pattern family | State | Rows | Missed | Oracle PnL | Incremental |", "|---|---|---:|---:|---:|---:|"])
        for row in rows:
            lines.append(
                f"| `{row.get('pattern_family')}` | `{row.get('promotion_state')}` | {row.get('rows')} | "
                f"{row.get('missed_entry_rows')} | {_money(row.get('oracle_net_pnl_usd'))} | "
                f"{_money(row.get('oracle_incremental_vs_actual_usd'))} |"
            )
        lines.append("")
    return lines


def _render_epoch(summary: dict[str, Any]) -> list[str]:
    active = summary.get("active_policy_epoch") if isinstance(summary.get("active_policy_epoch"), dict) else {}
    trades = summary.get("answer_backed_trades") if isinstance(summary.get("answer_backed_trades"), dict) else {}
    opps = summary.get("answer_backed_opportunities") if isinstance(summary.get("answer_backed_opportunities"), dict) else {}
    lines = [
        "## Oracle Epoch",
        "",
        f"- Active epoch: `{active.get('policy_epoch_id') or ''}`",
        f"- Version: `{active.get('policy_epoch_version') or ''}`",
        f"- Answer-backed opportunities opened: {opps.get('opened', 0)}",
        f"- Answer-backed opportunities rotated: {opps.get('rotated', 0)}",
        f"- Answer-backed trades open/closed: {trades.get('open', 0)} / {trades.get('closed', 0)}",
        f"- Answer-backed closed PnL after fees: {_money(trades.get('closed_realized_pnl_usd_after_fees'))}",
        "",
    ]
    rows = _top_rows(trades.get("closed_by_strategy"), 8)
    if rows:
        lines.extend(["| Strategy | Closed | Net PnL | Fees |", "|---|---:|---:|---:|"])
        for row in rows:
            lines.append(
                f"| `{row.get('key')}` | {row.get('count')} | {_money(row.get('realized_pnl_usd'))} | {_money(row.get('fees_usd'))} |"
            )
        lines.append("")
    return lines


def _render_trait_ledger(summary: dict[str, Any]) -> list[str]:
    if not summary:
        return ["## Trait Ledger", "", "- No trait ledger available yet.", ""]
    counts = summary.get("record_counts") if isinstance(summary.get("record_counts"), dict) else {}
    rankings = summary.get("rankings") if isinstance(summary.get("rankings"), dict) else {}
    lines = [
        "## Trait Ledger",
        "",
        f"- Main trades: {counts.get('main_trades')}",
        f"- Compare runs included: {counts.get('compare_runs')}",
        f"- Closed trades: {counts.get('closed_trades')}",
        "",
    ]
    rows = _top_rows(rankings.get("best_family_exit_pairs"), 8)
    if rows:
        lines.extend(["| Best family x exit | Closed | Win rate | Net PnL |", "|---|---:|---:|---:|"])
        for row in rows:
            win_rate = row.get("win_rate_after_fees")
            win_text = "" if win_rate is None else f"{float(win_rate):.1%}"
            lines.append(
                f"| `{row.get('key')}` | {row.get('closed_trades')} | {win_text} | {_money(row.get('realized_pnl_usd_after_fees'))} |"
            )
        lines.append("")
    return lines


def _render_sidecar_restatement(summary: dict[str, Any]) -> list[str]:
    if not summary:
        return ["## Sidecar Exit Restatement", "", "- No sidecar exit restatement available yet.", ""]
    stats = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
    lines = [
        "## Sidecar Exit Restatement",
        "",
        f"- Target notional: `${float(summary.get('target_notional_usd') or 0.0):,.2f}`",
        f"- Main closed trades restated: {stats.get('main_closed_trades')}",
        f"- Runtime net PnL at target: {_money(stats.get('runtime_net_pnl_usd_at_target_notional'))}",
        f"- Best executable counterfactual at target: {_money(stats.get('counterfactual_best_executable_net_pnl_usd_at_target_notional'))}",
        f"- Best executable incremental: {_money(stats.get('counterfactual_best_executable_incremental_usd_at_target_notional'))}",
        f"- Best any/oracle counterfactual at target: {_money(stats.get('counterfactual_best_any_oracle_net_pnl_usd_at_target_notional'))}",
        f"- Best any/oracle incremental: {_money(stats.get('counterfactual_best_any_oracle_incremental_usd_at_target_notional'))}",
        "",
    ]
    candidates = summary.get("sidecar_pairing_candidates") if isinstance(summary.get("sidecar_pairing_candidates"), dict) else {}
    if candidates:
        lines.extend(["| Family | Top sidecar candidate | Closed | Net at target |", "|---|---|---:|---:|"])
        for family, rows in list(candidates.items())[:8]:
            row = (rows or [{}])[0] if isinstance(rows, list) else {}
            evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
            lines.append(
                f"| `{family}` | `{row.get('id') or ''}` | {evidence.get('closed_trades', 0)} | "
                f"{_money(evidence.get('net_pnl_usd_at_target_notional'))} |"
            )
        lines.append("")
    return lines


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Live Hourly Analysis",
        "",
        f"Created: {report['created_at']}",
        "",
        "This is the local restart-proof hourly analysis doc for the live mock stack. It does not stop trading.",
        "",
    ]
    errors = {name: step["error"] for name, step in report.get("steps", {}).items() if not step.get("ok")}
    if errors:
        lines.extend(["## Step Warnings", ""])
        for name, error in errors.items():
            lines.append(f"- `{name}`: {error}")
        lines.append("")
    lines.extend(_render_epoch(report.get("oracle_policy_epoch") or {}))
    lines.extend(_render_allocation(report.get("bank_allocation") or {}))
    lines.extend(_render_hindsight(report.get("hindsight_audit") or {}))
    lines.extend(_render_sidecar_restatement(report.get("sidecar_exit_restatement") or {}))
    lines.extend(_render_trait_ledger(report.get("trait_ledger") or {}))
    lines.extend(
        [
            "## Outputs",
            "",
            f"- JSON: `{OUT_JSON}`",
            f"- Markdown: `{OUT_MD}`",
            f"- Replay checkpoint: `{LIVE_DIR / 'live_mock_replay_report.md'}`",
            f"- Health: `{LIVE_DIR / 'live_stack_health.md'}`",
            "",
        ]
    )
    return "\n".join(lines)


def build_report() -> dict[str, Any]:
    from build_live_trade_trait_ledger import (
        DEFAULT_COMPARE_ROOT,
        DEFAULT_OPPORTUNITY_LOG,
        DEFAULT_OUT_JSON,
        DEFAULT_OUT_MD,
        DEFAULT_TRADE_LOG,
        build_trait_ledger,
    )
    from summarize_live_bank_allocation_shadow import summarize as summarize_allocation
    from summarize_live_mock_winners import summarize as summarize_winners
    from summarize_live_oracle_policy_epoch import summarize as summarize_epoch

    steps = {
        "oracle_policy_epoch": _run_step("oracle_policy_epoch", summarize_epoch),
        "bank_allocation": _run_step("bank_allocation", summarize_allocation),
        "winning_routes": _run_step("winning_routes", summarize_winners),
        "trait_ledger": _run_step(
            "trait_ledger",
            lambda: build_trait_ledger(
                DEFAULT_OPPORTUNITY_LOG,
                DEFAULT_TRADE_LOG,
                DEFAULT_COMPARE_ROOT,
                DEFAULT_OUT_JSON,
                DEFAULT_OUT_MD,
                compare_run_limit=5,
            ),
        ),
    }
    report = {
        "schema": "live_hourly_analysis_v1",
        "created_at": _now_iso(),
        "steps": steps,
        "oracle_policy_epoch": steps["oracle_policy_epoch"]["value"] if steps["oracle_policy_epoch"]["ok"] else {},
        "bank_allocation": steps["bank_allocation"]["value"] if steps["bank_allocation"]["ok"] else {},
        "winning_routes": steps["winning_routes"]["value"] if steps["winning_routes"]["ok"] else {},
        "hindsight_audit": _read_json(LIVE_DIR / "live_hindsight_missed_winner_audit.json"),
        "sidecar_exit_restatement": _read_json(LIVE_DIR / "live_sidecar_exit_restatement.json"),
        "trait_ledger": steps["trait_ledger"]["value"] if steps["trait_ledger"]["ok"] else _read_json(LIVE_DIR / "live_trade_trait_ledger.json"),
        "outputs": {
            "json": str(OUT_JSON),
            "markdown": str(OUT_MD),
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the restart-proof hourly live mock analysis report.")
    parser.add_argument("--print-md", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.print_md:
        print(OUT_MD.read_text(encoding="utf-8"))
    else:
        print(json.dumps({
            "schema": report["schema"],
            "created_at": report["created_at"],
            "step_ok": {name: step["ok"] for name, step in report["steps"].items()},
            "outputs": report["outputs"],
        }, indent=2))


if __name__ == "__main__":
    main()
