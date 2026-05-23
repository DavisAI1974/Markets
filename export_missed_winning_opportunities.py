from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_family_evolution import _evolution_write_lock, merge_candidate_experiments


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
COMPARE_ROOT = EVOLUTION_DIR / "live_family_registry_compare"
SHARED_JSONL = EVOLUTION_DIR / "_live_missed_winning_opportunities.jsonl"
SHARED_QUEUE = EVOLUTION_DIR / "_missed_winning_opportunities_queue.json"
SHARED_EXPERIMENTS = EVOLUTION_DIR / "_candidate_experiments.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _latest_run_dir() -> Path:
    candidates = [
        path for path in COMPARE_ROOT.iterdir()
        if path.is_dir() and (path / "family_registry_opportunities.jsonl").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"No compare runs with opportunities found under {COMPARE_ROOT}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


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


def _context_key(row: dict[str, Any]) -> str:
    return "|".join([
        str(row.get("asset") or "").upper(),
        str(row.get("venue") or "").lower(),
        str(row.get("side") or "").lower(),
        str(row.get("bucket_session") or "").lower(),
    ])


def _missed_winner(row: dict[str, Any]) -> bool:
    if str(row.get("decision") or "") == "opened":
        return False
    if str(row.get("resolver_id") or "") != "EXACT_CONTEXT_RESOLVER":
        return False
    if not str(row.get("resolver_action") or "").startswith("context_routing_exact"):
        return False
    family = str(row.get("resolved_strategy_family") or row.get("trade_strategy_id") or "")
    if family in {"", "NO_TRADE"}:
        return False
    return True


def _group_missed(rows: list[dict[str, Any]], run_id: str, source: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _missed_winner(row):
            key = (
                _context_key(row),
                str(row.get("resolved_strategy_family") or row.get("trade_strategy_id") or ""),
                str(row.get("reason") or ""),
            )
            grouped[key].append(row)

    out: list[dict[str, Any]] = []
    for (context, family, reason), bucket in sorted(grouped.items()):
        bucket.sort(key=lambda r: float(r.get("ts_utc") or 0.0))
        first = bucket[0]
        evidence_reason = " ".join(str(x) for x in first.get("trade_strategy_reasons") or [])
        out.append({
            "schema": "missed_winning_live_opportunity_v1",
            "updated_at": _now_iso(),
            "source": source,
            "run_id": run_id,
            "context": context,
            "asset": str(first.get("asset") or "").upper(),
            "venue": str(first.get("venue") or ""),
            "side": str(first.get("side") or ""),
            "session": str(first.get("bucket_session") or ""),
            "family": family,
            "bucket_id": str(first.get("trade_strategy_variant_id") or ""),
            "resolver_id": "EXACT_CONTEXT_RESOLVER",
            "resolver_action": str(first.get("resolver_action") or ""),
            "blocked_reason": reason,
            "blocked_count": len(bucket),
            "account_ids": sorted({str(r.get("account_id") or "") for r in bucket if str(r.get("account_id") or "")}),
            "route_evidence": evidence_reason,
            "trade_state": str(first.get("trade_option_state") or ""),
            "pressure_state": str(first.get("pressure_watch_state") or ""),
            "trade_stage": str(first.get("trade_stage") or ""),
            "present_score": int(first.get("trade_present_score") or 0),
            "readiness": int(first.get("trade_option_readiness") or 0),
            "regime": str(first.get("regime") or ""),
            "mean_dipole": float(first.get("mean_dipole") or 0.0),
            "current_chunk_bps": float(first.get("trade_current_chunk_bps") or 0.0),
            "recent_2chunk_bps": float(first.get("trade_recent_2chunk_bps") or 0.0),
            "planned_notional_usd": float(first.get("planned_notional_usd") or 1000.0),
            "actual_execution": False,
            "actual_notional": 0.0,
            "evolution_instruction": (
                "Find the entry/exit contract that would have allowed this positive exact-context "
                "route to execute profitably in live replay, or explicitly mark the blocker as protective."
            ),
        })
    return out


def _experiments_from_missed(missed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    experiments = []
    for row in missed:
        experiment_id = "|".join([
            "missed_winner",
            str(row.get("context") or ""),
            str(row.get("family") or ""),
            str(row.get("blocked_reason") or ""),
        ])
        experiments.append({
            "experiment_id": experiment_id,
            "family": str(row.get("family") or "").upper(),
            "action": "resolve_missed_winning_live_opportunity_entry_exit",
            "priority": "high",
            "source_variant_id": str(row.get("bucket_id") or experiment_id),
            "force_learning_trade": True,
            "requested_strategy_families": [str(row.get("family") or "").upper()],
            "exact_context": {
                "asset": row.get("asset"),
                "venue": row.get("venue"),
                "side": row.get("side"),
                "session": row.get("session"),
            },
            "blocked_reason": row.get("blocked_reason"),
            "route_evidence": row.get("route_evidence"),
            "entry_questions": [
                "Should this context bypass the blocker for $1000 mock execution?",
                "Which entry confirmation fields separate profitable from losing live instances?",
                "Should this context be promoted, paper_only, quarantined, or avoid_context?",
            ],
            "exit_questions": [
                "Which exit profile maximizes realized PnL for this exact context?",
                "Should scalp, runner, hard TP/SL, or family-specific exits be preferred?",
                "What structure features select the best exit profile?",
            ],
            "success_criteria": {
                "min_mock_notional_usd": 1000.0,
                "profit_R_floor": 0.0,
                "must_compare_all_exit_variants": True,
                "must_update_family_memory_json": True,
                "must_update_routing_status": True,
            },
        })
    return experiments


def export(run_dir: Path) -> dict[str, Any]:
    run_id = run_dir.name
    source = str(run_dir / "family_registry_opportunities.jsonl")
    rows = _read_jsonl(run_dir / "family_registry_opportunities.jsonl")
    missed = _group_missed(rows, run_id, source)
    experiments = _experiments_from_missed(missed)

    run_missed = run_dir / "missed_winning_opportunities.json"
    run_jsonl = run_dir / "missed_winning_opportunities.jsonl"
    run_experiments = run_dir / "missed_winning_candidate_experiments.json"
    payload = {
        "schema": "missed_winning_live_opportunities_batch_v1",
        "updated_at": _now_iso(),
        "source": source,
        "run_id": run_id,
        "missed_count": len(missed),
        "missed_opportunities": missed,
        "candidate_experiments": experiments,
    }
    run_missed.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    run_experiments.write_text(json.dumps({
        "schema": "strategy_candidate_experiments_v1",
        "updated_at": _now_iso(),
        "source": source,
        "run_id": run_id,
        "experiments": experiments,
    }, indent=2), encoding="utf-8")
    with run_jsonl.open("w", encoding="utf-8") as f:
        for row in missed:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    with _evolution_write_lock(EVOLUTION_DIR):
        queue_doc = {
            "schema": "missed_winning_opportunities_queue_v1",
            "updated_at": _now_iso(),
            "source": source,
            "run_id": run_id,
            "policy": {
                "purpose": "Send positive exact-context opportunities blocked in live mock to evolution for entry/exit resolution.",
                "mock_notional_usd": 1000.0,
                "rank_by": ["realized_pnl_usd", "mark_to_market_pnl_usd", "closed_trade_count", "opened_trade_count"],
            },
            "items": missed,
        }
        SHARED_QUEUE.write_text(json.dumps(queue_doc, indent=2), encoding="utf-8")
        existing_experiments = _load_json(SHARED_EXPERIMENTS)
        merged_experiments = merge_candidate_experiments(
            existing_experiments,
            experiments,
            source=source,
            run_id=run_id,
        )
        SHARED_EXPERIMENTS.write_text(json.dumps(merged_experiments, indent=2), encoding="utf-8")
        existing_keys = {
            "|".join([
                str(r.get("run_id") or ""),
                str(r.get("context") or ""),
                str(r.get("family") or ""),
                str(r.get("blocked_reason") or ""),
            ])
            for r in _read_jsonl(SHARED_JSONL)
        }
        with SHARED_JSONL.open("a", encoding="utf-8") as f:
            for row in missed:
                key = "|".join([
                    str(row.get("run_id") or ""),
                    str(row.get("context") or ""),
                    str(row.get("family") or ""),
                    str(row.get("blocked_reason") or ""),
                ])
                if key not in existing_keys:
                    f.write(json.dumps(row, sort_keys=True) + "\n")

    return {
        "run_id": run_id,
        "missed_count": len(missed),
        "candidate_experiments": len(experiments),
        "run_missed_path": str(run_missed),
        "shared_queue_path": str(SHARED_QUEUE),
        "shared_jsonl_path": str(SHARED_JSONL),
        "shared_candidate_experiments_path": str(SHARED_EXPERIMENTS),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default="")
    args = parser.parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else _latest_run_dir()
    result = export(run_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
