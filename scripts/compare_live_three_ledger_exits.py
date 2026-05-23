#!/usr/bin/env python3
"""Compare runtime, executable counterfactual, and oracle exit ledgers.

This is intentionally read-only. It consumes the restatement rows produced by
build_live_sidecar_exit_restatement.py and writes a compact closed-trade table.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_ROWS = Path(
    r"E:\Markets\research\strategy_evolution\live_mock_replay\live_sidecar_exit_restatement_rows.csv"
)
DEFAULT_OUT_CSV = Path(
    r"E:\Markets\research\strategy_evolution\live_mock_replay\three_ledger_exit_comparison.csv"
)
DEFAULT_OUT_MD = Path(
    r"E:\Markets\research\strategy_evolution\live_mock_replay\three_ledger_exit_comparison.md"
)


def _money(raw: str) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _fmt_money(raw: str) -> str:
    return f"${_money(raw):+,.2f}"


def _best_exec_id(row: dict[str, str]) -> str:
    return row.get("cf_best_runtime_executable_id") or row.get("cf_best_executable_id") or ""


def _best_exec_pnl(row: dict[str, str]) -> str:
    return (
        row.get("cf_best_runtime_executable_net_pnl_usd_at_target_notional")
        or row.get("cf_best_executable_net_pnl_usd_at_target_notional")
        or ""
    )


def _divergence_cause(row: dict[str, str]) -> tuple[str, str]:
    runtime_reason = row.get("runtime_close_reason") or ""
    exec_id = _best_exec_id(row)
    oracle_id = row.get("cf_best_any_oracle_id") or ""
    exec_gap = _money(row.get("cf_best_runtime_executable_incremental_vs_runtime_usd_at_target_notional"))
    oracle_gap = _money(row.get("cf_best_any_oracle_incremental_vs_runtime_usd_at_target_notional"))

    if not exec_id and not oracle_id:
        return (
            "no counterfactual candidates for this closed trade",
            "build_live_sidecar_exit_restatement.py counterfactual candidate generation",
        )
    if abs(exec_gap) < 1e-9 and abs(oracle_gap) < 1e-9:
        return ("no material divergence", "")
    if exec_id.startswith("fixed_hold_") and runtime_reason:
        if runtime_reason.startswith("runtime_counterfactual_fixed_hold_"):
            return (
                f"runtime selector forced `{runtime_reason}`; executable table preferred `{exec_id}` and oracle preferred `{oracle_id}`",
                (
                    r"E:\Markets\trade_exit_strategy.py:1051 applies the runtime selector; "
                    r"old bad-epoch closes reached E:\Markets\trade_exit_strategy.py:1127 "
                    r"before the current E:\Markets\trade_exit_strategy.py:1103 "
                    r"non-negative close floor protected red fixed-hold exits"
                ),
            )
        if "after_runtime_exit" in exec_id:
            return (
                f"runtime closed on `{runtime_reason}`; executable path would defer that first runtime exit signal via `{exec_id}`",
                (
                    r"E:\Markets\mock_trade_replay.py:887 checks for a stamped "
                    r"`runtime_counterfactual_exit_selection`; when absent, base exit decision "
                    r"from E:\Markets\trade_exit_strategy.py:1511 reaches close_trade at "
                    r"E:\Markets\mock_trade_replay.py:904"
                ),
            )
        if "after_entry" in exec_id:
            return (
                f"runtime closed on `{runtime_reason}` before the executable entry-hold answer `{exec_id}`",
                (
                    r"E:\Markets\mock_trade_replay.py:887 checks for a stamped "
                    r"`runtime_counterfactual_exit_selection`; when absent, base exit decision "
                    r"from E:\Markets\trade_exit_strategy.py:1511 reaches close_trade at "
                    r"E:\Markets\mock_trade_replay.py:904"
                ),
            )
    return (
        f"runtime `{runtime_reason}` differs from executable `{exec_id}` and oracle `{oracle_id}`",
        r"E:\Markets\mock_trade_replay.py:887 / E:\Markets\trade_exit_strategy.py:1051",
    )


def _trade_id(row: dict[str, str]) -> str:
    return row.get("cell_id") or "|".join(
        [
            row.get("asset", ""),
            row.get("venue", ""),
            row.get("side", ""),
            row.get("family", ""),
            str(int(float(row.get("entry_ts_utc") or 0))),
        ]
    )


def build(rows_path: Path, out_csv: Path, out_md: Path, epoch: str = "") -> list[dict[str, str]]:
    with rows_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    closed = [r for r in rows if (r.get("status") or "").lower() == "closed"]
    if epoch:
        closed = [r for r in closed if r.get("policy_epoch_id") == epoch]

    table: list[dict[str, str]] = []
    for row in sorted(closed, key=lambda r: (float(r.get("entry_ts_utc") or 0), _trade_id(r))):
        cause, first_divergence = _divergence_cause(row)
        table.append(
            {
                "trade_id": _trade_id(row),
                "entry_ts_utc": row.get("entry_ts_utc") or "",
                "runtime_close_reason": row.get("runtime_close_reason") or "",
                "runtime_pnl_at_10000": _fmt_money(row.get("runtime_net_pnl_usd_at_target_notional")),
                "executable_best_id": _best_exec_id(row),
                "executable_best_pnl_at_10000": _fmt_money(_best_exec_pnl(row)),
                "oracle_best_id": row.get("cf_best_any_oracle_id") or "",
                "oracle_best_pnl_at_10000": _fmt_money(
                    row.get("cf_best_any_oracle_net_pnl_usd_at_target_notional")
                ),
                "rt_ledger_memory_selected_id": row.get("rt_ledger_memory_selected_id") or "",
                "rt_ledger_best_id": row.get("rt_ledger_best_executable_id") or "",
                "rt_ledger_best_pnl_at_10000": _fmt_money(
                    row.get("rt_ledger_best_executable_net_pnl_usd_at_target_notional")
                ) if row.get("rt_ledger_best_executable_net_pnl_usd_at_target_notional") not in {None, ""} else "",
                "divergence_cause": cause,
                "first_divergence_line_function": first_divergence,
            }
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0].keys()) if table else [
            "trade_id",
            "entry_ts_utc",
            "runtime_close_reason",
            "runtime_pnl_at_10000",
            "executable_best_id",
            "executable_best_pnl_at_10000",
            "oracle_best_id",
            "oracle_best_pnl_at_10000",
            "rt_ledger_memory_selected_id",
            "rt_ledger_best_id",
            "rt_ledger_best_pnl_at_10000",
            "divergence_cause",
            "first_divergence_line_function",
        ])
        writer.writeheader()
        writer.writerows(table)

    lines = [
        "# Three-Ledger Exit Comparison",
        "",
        f"Source: `{rows_path}`",
        f"Policy epoch filter: `{epoch or 'all closed rows'}`",
        f"Closed trades compared: `{len(table)}`",
        "",
        "| Trade id | Entry ts | Runtime reason | Runtime PnL | RT memory pick | RT ledger best | RT ledger PnL | Offline exec best | Offline exec PnL | Oracle best | Oracle PnL | Divergence cause |",
        "|---|---:|---|---:|---|---|---:|---|---:|---|---:|---|",
    ]
    for r in table:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{r['trade_id']}`",
                    r["entry_ts_utc"],
                    f"`{r['runtime_close_reason']}`",
                    r["runtime_pnl_at_10000"],
                    f"`{r['rt_ledger_memory_selected_id']}`",
                    f"`{r['rt_ledger_best_id']}`",
                    r["rt_ledger_best_pnl_at_10000"],
                    f"`{r['executable_best_id']}`",
                    r["executable_best_pnl_at_10000"],
                    f"`{r['oracle_best_id']}`",
                    r["oracle_best_pnl_at_10000"],
                    r["divergence_cause"],
                ]
            )
            + " |"
        )
    lines.extend(["", "## First Divergence Lines", ""])
    for r in table:
        lines.append(f"- `{r['trade_id']}`: {r['first_divergence_line_function'] or 'n/a'}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return table


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument("--epoch", default="")
    args = parser.parse_args()
    table = build(args.rows, args.out_csv, args.out_md, args.epoch)
    print(f"wrote {len(table)} closed-trade comparisons")
    print(args.out_csv)
    print(args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
