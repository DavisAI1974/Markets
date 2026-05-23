from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _context_key(trade: dict[str, Any]) -> str:
    session = str(trade.get("bucket_session") or "").strip().lower()
    if not session:
        bucket = str(trade.get("bucket_id") or "")
        parts = bucket.split("|")
        if len(parts) == 5:
            session = parts[4].lower()
    return "|".join([
        str(trade.get("asset") or "").upper(),
        str(trade.get("venue") or "").lower(),
        str(trade.get("side") or "").lower(),
        session,
    ])


def _fmt_hour(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _run_label(root: Path, path: Path) -> dict[str, Any]:
    text = f"{root} {path}".replace("\\", "/")
    cadence = "5m" if "loose5" in text else "15m" if "loose" in text else "unknown"
    root_name = root.name
    continuous = re.search(r"_h(?P<start>\d+(?:\.\d+)?)_(?P<hours>\d+(?:\.\d+)?)h_continuous", root_name)
    if continuous:
        start = float(continuous.group("start"))
        hours = float(continuous.group("hours"))
        return {
            "cadence": cadence,
            "window": f"h{_fmt_hour(start)}-{_fmt_hour(start + hours)}",
            "start_hour": start,
            "hours": hours,
        }
    match = re.search(r"_h(?P<start>\d+(?:\.\d+)?)(?:$|_|/)", root_name)
    if not match:
        match = re.search(r"slice_\d+_h(?P<start>\d+(?:\.\d+)?)(?:$|_)", path.parent.name)
    if not match:
        return {"cadence": cadence, "window": "unknown", "start_hour": None, "hours": None}
    start = float(match.group("start"))
    hours = 6.0
    return {
        "cadence": cadence,
        "window": f"h{_fmt_hour(start)}-{_fmt_hour(start + hours)}",
        "start_hour": start,
        "hours": hours,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "opportunities": 0,
            "wins": 0,
            "win_rate": 0.0,
            "pnl_usd": 0.0,
            "pnl_R": 0.0,
            "best_pnl_R": 0.0,
        }
    pnl_usd = sum(_float(row.get("pnl_usd")) for row in rows)
    pnl_r = sum(_float(row.get("pnl_R")) for row in rows)
    wins = sum(1 for row in rows if _float(row.get("pnl_R")) > 0.0)
    best = max(rows, key=lambda row: _float(row.get("pnl_R")))
    return {
        "opportunities": len(rows),
        "wins": wins,
        "win_rate": round(wins / len(rows), 6),
        "pnl_usd": round(pnl_usd, 6),
        "pnl_R": round(pnl_r, 6),
        "best_pnl_R": round(_float(best.get("pnl_R")), 6),
        "best_strategy": best.get("strategy_id") or "",
        "best_replay_offset_hours": best.get("replay_offset_hours"),
        "best_close_reason": best.get("close_reason") or "",
    }


def build_ledger(
    roots: list[Path],
    output_dir: Path,
    *,
    output_name: str = "opportunity_ledger_h0_h12_loose_and_dense",
    title: str = "Opportunity Ledger: h0-h12 Loose + Dense",
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    opportunities: list[dict[str, Any]] = []
    missing_roots: list[str] = []
    for root in roots:
        if not root.exists():
            missing_roots.append(str(root))
            continue
        for result_path in sorted(root.glob("slice_*/mock_replay_results.json")):
            labels = _run_label(root, result_path)
            data = _load_json(result_path)
            run_dir = str(result_path.parent)
            for account_id, account in (data.get("accounts") or {}).items():
                for index, trade in enumerate((account or {}).get("trades") or [], start=1):
                    context = _context_key(trade)
                    opportunities.append({
                        "id": f"{labels['window']}|{labels['cadence']}|{Path(run_dir).name}|{account_id}|{index}",
                        "window": labels["window"],
                        "cadence": labels["cadence"],
                        "source_start_hour": labels.get("start_hour"),
                        "source_hours": labels.get("hours"),
                        "run_dir": run_dir,
                        "account": str(account_id),
                        "index": index,
                        "context": context,
                        "bucket_id": str(trade.get("bucket_id") or ""),
                        "strategy_id": str(trade.get("trade_strategy_id") or ""),
                        "variant_id": str(trade.get("trade_strategy_variant_id") or ""),
                        "exit_strategy_id": str(trade.get("exit_strategy_id") or ""),
                        "asset": str(trade.get("asset") or ""),
                        "venue": str(trade.get("venue") or ""),
                        "side": str(trade.get("side") or ""),
                        "bucket_session": str(trade.get("bucket_session") or ""),
                        "status": str(trade.get("status") or ""),
                        "replay_offset_hours": _float(trade.get("replay_offset_hours")),
                        "ts_utc": _float(trade.get("ts_utc")),
                        "exit_ts_utc": _float(trade.get("exit_ts_utc")),
                        "hold_minutes": _float(trade.get("hold_minutes")),
                        "entry": _float(trade.get("fill_price")),
                        "exit": _float(trade.get("exit_price")),
                        "notional": _float(trade.get("notional")),
                        "pnl_usd": _float(trade.get("realized_pnl_usd")),
                        "pnl_R": _float(trade.get("profit_R")),
                        "gross_pnl_usd": _float(trade.get("gross_pnl_usd")),
                        "fees_usd": _float(trade.get("fees_usd")),
                        "close_reason": str(trade.get("close_reason") or ""),
                        "forced": bool(trade.get("trade_strategy_forced")),
                        "actual_execution": bool(trade.get("actual_execution")),
                        "trade_present_score": int(trade.get("trade_present_score") or 0),
                        "trade_stage": str(trade.get("trade_stage") or ""),
                        "trade_option_state": str(trade.get("trade_option_state") or ""),
                        "pressure_watch_state": str(trade.get("pressure_watch_state") or ""),
                        "trade_current_chunk_bps": _float(trade.get("trade_current_chunk_bps")),
                        "trade_recent_2chunk_bps": _float(trade.get("trade_recent_2chunk_bps")),
                        "trade_from_onset_bps": _float(trade.get("trade_from_onset_bps")),
                        "mean_dipole": _float(trade.get("mean_dipole")),
                        "dipole_acl1": _float(trade.get("dipole_acl1")),
                        "volume_zscore": _float(trade.get("volume_zscore")),
                        "trade_strategy_confidence": _float(trade.get("trade_strategy_confidence")),
                        "trade_strategy_risk_tags": list(trade.get("trade_strategy_risk_tags") or []),
                        "trade_strategy_reasons": list(trade.get("trade_strategy_reasons") or []),
                        "trade_strategy_source_queue_action": str(trade.get("trade_strategy_source_queue_action") or ""),
                    })

    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_context: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in opportunities:
        by_window[f"{row['window']}|{row['cadence']}"].append(row)
        by_context[str(row["context"])].append(row)
        by_bucket[str(row["bucket_id"])].append(row)
        by_family[str(row["strategy_id"]).lower()].append(row)

    ledger = {
        "schema": "strategy_opportunity_ledger_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_roots": [str(root) for root in roots],
        "missing_roots": missing_roots,
        "run_contract": {
            "rules_file": "OPPORTUNITY_RUN_RULES.md",
            "unit": "one 6-hour block has loose 15m and dense 5m all-family evidence sweeps",
            "families": [
                "MEAN_REVERSION_CHOP",
                "NEWS_BREAKOUT",
                "LIQUIDITY_SQUEEZE",
                "VOL_BREAKOUT",
                "BASIS_DISLOCATION",
                "RELATIVE_STRENGTH",
            ],
            "supplemental_tradable_source": "exact_context_resolver",
        },
        "definition": {
            "opportunity": "one evidence trade opened by a replay account/scenario; these are hypothetical practice trades, not actual execution",
            "context": "asset|venue|side|bucket_session",
            "bucket": "strategy_family|asset|venue|side|bucket_session",
        },
        "totals": {
            "opportunities": len(opportunities),
            "wins": sum(1 for row in opportunities if _float(row.get("pnl_R")) > 0.0),
            "actual_executions": sum(1 for row in opportunities if bool(row.get("actual_execution"))),
        },
        "by_window": {key: _summarize(rows) for key, rows in sorted(by_window.items())},
        "by_context": {key: _summarize(rows) for key, rows in sorted(by_context.items())},
        "by_bucket": {key: _summarize(rows) for key, rows in sorted(by_bucket.items()) if key},
        "by_family": {key: _summarize(rows) for key, rows in sorted(by_family.items()) if key},
        "top_opportunities": sorted(
            opportunities,
            key=lambda row: (_float(row.get("pnl_R")), _float(row.get("pnl_usd"))),
            reverse=True,
        )[:50],
        "opportunities": opportunities,
    }
    json_path = output_dir / f"{output_name}.json"
    json_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    lines = [
        f"# {title}",
        "",
        f"Created: {ledger['created_at']}",
        "",
        f"- Opportunities: {ledger['totals']['opportunities']}",
        f"- Wins: {ledger['totals']['wins']}",
        f"- Actual executions: {ledger['totals']['actual_executions']}",
        f"- Missing roots: {len(missing_roots)}",
        "",
        "## By Window",
        "",
        "| Window | Opportunities | Wins | Win rate | PnL R | PnL USD | Best R | Best strategy |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key, row in ledger["by_window"].items():
        lines.append(
            f"| `{key}` | {row['opportunities']} | {row['wins']} | {row['win_rate']:.1%} | "
            f"{row['pnl_R']:+.2f} | ${row['pnl_usd']:+.2f} | {row['best_pnl_R']:+.2f} | `{row.get('best_strategy') or ''}` |"
        )
    lines.extend([
        "",
        "## By Context",
        "",
        "| Context | Opportunities | Wins | Win rate | PnL R | Best R | Best strategy |",
        "|---|---:|---:|---:|---:|---:|---|",
    ])
    for key, row in sorted(ledger["by_context"].items(), key=lambda item: item[1]["opportunities"], reverse=True):
        lines.append(
            f"| `{key}` | {row['opportunities']} | {row['wins']} | {row['win_rate']:.1%} | "
            f"{row['pnl_R']:+.2f} | {row['best_pnl_R']:+.2f} | `{row.get('best_strategy') or ''}` |"
        )
    lines.extend([
        "",
        "## Top Opportunities",
        "",
        "| # | Window | Context | Strategy | Replay hr | Close | PnL R | PnL USD |",
        "|---:|---|---|---|---:|---|---:|---:|",
    ])
    for idx, row in enumerate(ledger["top_opportunities"][:25], start=1):
        lines.append(
            f"| {idx} | `{row['window']} {row['cadence']}` | `{row['context']}` | `{row['strategy_id']}` | "
            f"{_float(row['replay_offset_hours']):.2f} | `{row['close_reason']}` | "
            f"{_float(row['pnl_R']):+.2f} | ${_float(row['pnl_usd']):+.2f} |"
        )
    md_path = output_dir / f"{output_name}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a trade opportunity ledger from replay result roots.")
    parser.add_argument(
        "--roots",
        nargs="+",
        default=[
            "strategy_evolution_workflow_runs_loose_h0",
            "strategy_evolution_workflow_runs_loose_h6",
            "strategy_evolution_workflow_runs_loose5_h0",
            "strategy_evolution_workflow_runs_loose5_h6",
        ],
    )
    parser.add_argument("--output-dir", default=str(Path("research") / "strategy_evolution"))
    parser.add_argument("--output-name", default="opportunity_ledger_h0_h12_loose_and_dense")
    parser.add_argument("--title", default="Opportunity Ledger: h0-h12 Loose + Dense")
    args = parser.parse_args()
    json_path, md_path = build_ledger(
        [Path(root) for root in args.roots],
        Path(args.output_dir),
        output_name=str(args.output_name),
        title=str(args.title),
    )
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
