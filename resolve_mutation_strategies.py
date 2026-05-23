from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase1_5_evaluator import load_bars
from strategy_switcher import STRATEGY_SPECS


DATA_FILES = {
    ("BTC", "coinbase"): "btc_coinbase_bins.json",
    ("BTC", "kraken"): "btc_kraken_bins.json",
    ("BTC", "bybit"): "btc_bybit_perp_bins.json",
    ("ETH", "coinbase"): "eth_coinbase_bins.json",
    ("ETH", "kraken"): "eth_kraken_bins.json",
    ("ETH", "bybit"): "eth_bybit_perp_bins.json",
}
FEE_BPS = 5.0
NOTIONAL = 1000.0


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


def _context_parts(context: str) -> tuple[str, str, str, str] | None:
    parts = [str(x or "").strip() for x in str(context or "").split("|")]
    if len(parts) != 4 or not all(parts):
        return None
    return parts[0].upper(), parts[1].lower(), parts[2].lower(), parts[3].lower()


def _context_window(bars: list[Any], session: str) -> tuple[float, float]:
    start = float(bars[0].ts)
    if session == "first6h":
        return start, start + 6 * 3600
    return start + 6 * 3600, min(float(bars[-1].ts), start + 24 * 3600)


def _entry_price(bar: Any, side: str) -> float:
    return float(bar.ask or bar.close) if side == "buy" else float(bar.bid or bar.close)


def _best_exit_price(rows: list[Any], side: str) -> tuple[Any, float]:
    if side == "buy":
        bar = max(rows, key=lambda item: float(item.high or item.close))
        return bar, float(bar.high or bar.close)
    bar = min(rows, key=lambda item: float(item.low or item.close))
    return bar, float(bar.low or bar.close)


def _pnl(side: str, entry: float, exit_price: float, stop_bps: float) -> tuple[float, float, float]:
    gross_bps = ((exit_price - entry) / entry * 10000.0) if side == "buy" else ((entry - exit_price) / entry * 10000.0)
    net_bps = gross_bps - (2 * FEE_BPS)
    pnl_usd = NOTIONAL * net_bps / 10000.0
    pnl_r = net_bps / max(0.01, stop_bps)
    return pnl_r, pnl_usd, net_bps


def _resolve_candidate(candidate: dict[str, Any], bars_by_key: dict[tuple[str, str], list[Any]]) -> dict[str, Any]:
    context = str(candidate.get("candidate_context") or "")
    parts = _context_parts(context)
    strategy_id = str(candidate.get("candidate_strategy_id") or "").upper()
    if parts is None:
        return {"status": "negative_mutation_evidence", "reason": "invalid_candidate_context"}
    asset, venue, side, session = parts
    bars = bars_by_key.get((asset, venue)) or []
    if not bars:
        return {"status": "negative_mutation_evidence", "reason": "no_bars_for_context"}
    spec = STRATEGY_SPECS.get(strategy_id)
    if spec is None:
        return {"status": "negative_mutation_evidence", "reason": "unknown_strategy"}
    start, end = _context_window(bars, session)
    window = [bar for bar in bars if start <= float(bar.ts) <= end]
    if len(window) < 2:
        return {"status": "negative_mutation_evidence", "reason": "no_bars_in_session_window"}

    stop_bps = float(spec.stop_loss_bps)
    horizons = sorted({int(spec.hold_minutes), 15, 30, 60, 120, 240})
    best: tuple[float, float, float, float, float, float, float, int] | None = None
    for hold in horizons:
        horizon_s = max(1, int(hold)) * 60
        for idx, bar in enumerate(window[:-1]):
            entry = _entry_price(bar, side)
            if entry <= 0:
                continue
            future: list[Any] = []
            pos = idx + 1
            while pos < len(window) and float(window[pos].ts) <= float(bar.ts) + horizon_s:
                future.append(window[pos])
                pos += 1
            if not future:
                continue
            exit_bar, exit_price = _best_exit_price(future, side)
            pnl_r, pnl_usd, net_bps = _pnl(side, entry, exit_price, stop_bps)
            row = (
                pnl_r,
                pnl_usd,
                net_bps,
                float(bar.ts),
                float(exit_bar.ts),
                entry,
                exit_price,
                hold,
            )
            if best is None or (row[0], -row[7]) > (best[0], -best[7]):
                best = row

    if best is None:
        return {"status": "negative_mutation_evidence", "reason": "no_entry_scan_rows"}
    pnl_r, pnl_usd, net_bps, entry_ts, exit_ts, entry, exit_price, hold = best
    status = "promoted_mutation_opportunity" if pnl_r > 0.0 else "negative_mutation_evidence"
    return {
        "status": status,
        "reason": "positive_mutation_strategy" if pnl_r > 0.0 else "nonpositive_best_mutation",
        "context": context,
        "strategy_id": strategy_id,
        "pnl_R": round(pnl_r, 6),
        "pnl_usd": round(pnl_usd, 6),
        "net_bps": round(net_bps, 6),
        "entry_ts_utc": entry_ts,
        "exit_ts_utc": exit_ts,
        "entry_hour_in_series": round((entry_ts - float(bars[0].ts)) / 3600.0, 6),
        "exit_hour_in_series": round((exit_ts - float(bars[0].ts)) / 3600.0, 6),
        "entry_price": round(entry, 8),
        "exit_price": round(exit_price, 8),
        "hold_minutes": int(hold),
        "stop_bps": stop_bps,
    }


def resolve_mutations(workbench_path: Path, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    workbench = _load_json(workbench_path)
    candidates = list(workbench.get("mutation_candidates") or [])
    bars_by_key = {
        key: load_bars(filename)
        for key, filename in DATA_FILES.items()
        if Path(filename).exists()
    }
    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        result = _resolve_candidate(candidate, bars_by_key)
        rows.append({
            "id": f"mutation_strategy|{index}",
            "source_candidate": candidate,
            "result": result,
            "unresolved": False,
        })

    promoted = [row for row in rows if str((row.get("result") or {}).get("status") or "") == "promoted_mutation_opportunity"]
    negative = [row for row in rows if str((row.get("result") or {}).get("status") or "") != "promoted_mutation_opportunity"]
    promoted.sort(key=lambda row: _float((row.get("result") or {}).get("pnl_R")), reverse=True)
    negative.sort(key=lambda row: _float((row.get("result") or {}).get("pnl_R")))

    unique: dict[str, dict[str, Any]] = {}
    for row in promoted:
        result = row.get("result") or {}
        source = row.get("source_candidate") or {}
        key = "|".join([
            str(result.get("context") or ""),
            str(result.get("strategy_id") or ""),
            str(source.get("mutation") or ""),
        ])
        current = unique.get(key)
        if current is None:
            current = {
                "key": key,
                "context": result.get("context") or "",
                "strategy_id": result.get("strategy_id") or "",
                "mutation": source.get("mutation") or "",
                "pnl_R": _float(result.get("pnl_R")),
                "pnl_usd": _float(result.get("pnl_usd")),
                "entry_hour_in_series": result.get("entry_hour_in_series"),
                "exit_hour_in_series": result.get("exit_hour_in_series"),
                "entry_price": result.get("entry_price"),
                "exit_price": result.get("exit_price"),
                "hold_minutes": result.get("hold_minutes"),
                "stop_bps": result.get("stop_bps"),
                "supporting_candidates": 0,
                "source_total_pnl_R": 0.0,
                "source_rule_ids": [],
            }
            unique[key] = current
        if _float(result.get("pnl_R")) > _float(current.get("pnl_R")):
            current.update({
                "pnl_R": _float(result.get("pnl_R")),
                "pnl_usd": _float(result.get("pnl_usd")),
                "entry_hour_in_series": result.get("entry_hour_in_series"),
                "exit_hour_in_series": result.get("exit_hour_in_series"),
                "entry_price": result.get("entry_price"),
                "exit_price": result.get("exit_price"),
                "hold_minutes": result.get("hold_minutes"),
                "stop_bps": result.get("stop_bps"),
            })
        current["supporting_candidates"] = int(current.get("supporting_candidates") or 0) + 1
        current["source_total_pnl_R"] = _float(current.get("source_total_pnl_R")) + _float(source.get("source_total_pnl_R"))
        current["source_rule_ids"].append(str(source.get("source_rule_id") or ""))
    unique_promoted = list(unique.values())
    unique_promoted.sort(
        key=lambda row: (
            _float(row.get("pnl_R")),
            int(row.get("supporting_candidates") or 0),
            abs(_float(row.get("source_total_pnl_R"))),
        ),
        reverse=True,
    )

    by_strategy: dict[str, dict[str, Any]] = {}
    for row in unique_promoted:
        sid = str(row.get("strategy_id") or "")
        item = by_strategy.setdefault(sid, {"strategy_id": sid, "promoted_mutations": 0, "best_pnl_R": 0.0, "contexts": set()})
        item["promoted_mutations"] += 1
        item["best_pnl_R"] = max(_float(item.get("best_pnl_R")), _float(row.get("pnl_R")))
        item["contexts"].add(str(row.get("context") or ""))
    by_strategy_out = []
    for item in by_strategy.values():
        item["contexts"] = sorted(item["contexts"])
        by_strategy_out.append(item)
    by_strategy_out.sort(key=lambda row: (_float(row.get("best_pnl_R")), int(row.get("promoted_mutations") or 0)), reverse=True)

    payload = {
        "schema": "strategy_mutation_resolution_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_workbench": str(workbench_path),
        "policy": {
            "purpose": "Resolve mutation candidates into promoted strategy opportunities or negative mutation evidence.",
            "do_not_trade_live_until_positive": True,
            "do_not_increase_trade_count_for_volume": True,
            "unresolved_opportunities": 0,
        },
        "counts": {
            "mutation_candidates": len(candidates),
            "promoted_mutation_opportunities": len(promoted),
            "unique_promoted_mutation_strategies": len(unique_promoted),
            "negative_mutation_evidence": len(negative),
            "unresolved_opportunities": 0,
        },
        "by_strategy": by_strategy_out,
        "unique_promoted_mutation_strategies": unique_promoted,
        "promoted_mutation_opportunities": promoted,
        "negative_mutation_evidence": negative,
        "unresolved_opportunities": [],
    }
    json_path = output_dir / "_mutation_strategy_resolution.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Mutation Strategy Resolution",
        "",
        f"Created: {payload['created_at']}",
        "",
        f"- Mutation candidates: {payload['counts']['mutation_candidates']}",
        f"- Promoted mutation opportunities: {payload['counts']['promoted_mutation_opportunities']}",
        f"- Unique promoted mutation strategies: {payload['counts']['unique_promoted_mutation_strategies']}",
        f"- Negative mutation evidence: {payload['counts']['negative_mutation_evidence']}",
        f"- Unresolved opportunities: {payload['counts']['unresolved_opportunities']}",
        "",
        "## Top Strategies",
        "",
        "| Strategy | Promoted mutations | Best R | Contexts |",
        "|---|---:|---:|---|",
    ]
    for row in by_strategy_out:
        lines.append(
            f"| `{row.get('strategy_id') or ''}` | {int(row.get('promoted_mutations') or 0)} | "
            f"{_float(row.get('best_pnl_R')):+.2f} | `{', '.join(row.get('contexts') or [])}` |"
        )
    lines.extend([
        "",
        "## Top Promoted Mutations",
        "",
        "| # | Source context | Candidate context | Strategy | Mutation | PnL R | Entry hr |",
        "|---:|---|---|---|---|---:|---:|",
    ])
    for idx, row in enumerate(unique_promoted[:80], start=1):
        lines.append(
            f"| {idx} | `{', '.join(str(x).split('|')[0] for x in row.get('source_rule_ids', [])[:2])}` | `{row.get('context') or ''}` | "
            f"`{row.get('strategy_id') or ''}` | `{row.get('mutation') or ''}` | "
            f"{_float(row.get('pnl_R')):+.2f} | {_float(row.get('entry_hour_in_series')):.2f} |"
        )
    md_path = output_dir / "_mutation_strategy_resolution.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve mutation candidates into strategy opportunities.")
    parser.add_argument("--workbench", default=str(Path("research") / "strategy_evolution" / "_opportunity_mutation_workbench.json"))
    parser.add_argument("--output-dir", default=str(Path("research") / "strategy_evolution"))
    args = parser.parse_args()
    json_path, md_path = resolve_mutations(Path(args.workbench), Path(args.output_dir))
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
