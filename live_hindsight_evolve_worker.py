from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_family_evolution import _evolution_write_lock, merge_evolution_queue


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
HINDSIGHT_QUEUE = EVOLUTION_DIR / "_hindsight_missed_winner_queue.json"
EVOLUTION_QUEUE = EVOLUTION_DIR / "_queue.json"
STATUS_PATH = EVOLUTION_DIR / "_live_hindsight_evolve_worker_status.json"
AUDIT_SCRIPT = REPO_ROOT / "build_live_hindsight_missed_winner_audit.py"
WINNER_LIST_SCRIPT = REPO_ROOT / "scripts" / "build_oracle_winner_trade_list.py"
AUDIT_ROWS = EVOLUTION_DIR / "live_mock_replay" / "live_hindsight_missed_winner_audit_rows.csv"
WINNER_LIST = EVOLUTION_DIR / "oracle_winner_trade_list.json"

ACTIVE_FAMILIES = [
    "SMALL_MOVE_FADE",
    "BUY_UP_CONTINUATION",
    "BUY_FADE",
    "SELL_DOWN_CONTINUATION",
    "MEAN_REVERSION_CHOP",
    "LIQUIDITY_SQUEEZE",
    "VOL_BREAKOUT",
    "BASIS_DISLOCATION",
    "RELATIVE_STRENGTH",
    "NEWS_BREAKOUT",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_family(value: Any) -> str:
    family = str(value or "").strip().upper()
    return family if family in ACTIVE_FAMILIES else ""


def _context_parts(context_key: str) -> dict[str, str]:
    parts = str(context_key or "").split("|")
    if len(parts) != 5:
        return {}
    return {
        "family": parts[0],
        "asset": parts[1],
        "venue": parts[2],
        "side": parts[3],
        "session": parts[4],
    }


def _candidate_to_queue_rows(candidate: dict[str, Any], *, family_budget: int) -> list[dict[str, Any]]:
    priority = str(candidate.get("priority") or "").lower()
    if priority not in {"critical", "high"}:
        return []
    raw_family = str(candidate.get("family") or "").strip().upper()
    context_key = str(candidate.get("context_key") or "")
    context = _context_parts(context_key)
    families = [_safe_family(raw_family)]
    if not families[0]:
        if context.get("side") == "sell":
            families = ["SMALL_MOVE_FADE", *[family for family in ACTIVE_FAMILIES if family != "SMALL_MOVE_FADE"]]
            families = families[:max(1, family_budget)]
        else:
            families = ACTIVE_FAMILIES[:max(1, family_budget)]
    rows: list[dict[str, Any]] = []
    mutation_notes = [
        *list(candidate.get("entry_questions") or [])[:2],
        *list(candidate.get("exit_questions") or [])[:3],
    ]
    for family in families:
        rows.append({
            "family": family.lower(),
            "source_family": family.lower(),
            "source_variant_id": f"hindsight|{family.lower()}|{context_key or candidate.get('experiment_id')}",
            "action": str(candidate.get("action") or "hindsight_missed_winner_probe"),
            "priority": priority,
            "reason": (
                "Live hindsight found missed post-fee winners in this context; "
                "force a mock-only probe so routing can collect executable evidence."
            ),
            "force_learning_trade": True,
            "requested_strategy_families": [family],
            "exact_context": {
                "asset": context.get("asset", ""),
                "venue": context.get("venue", ""),
                "side": context.get("side", ""),
                "session": context.get("session", ""),
            },
            "hindsight_experiment_id": str(candidate.get("experiment_id") or ""),
            "hindsight_context_key": context_key,
            "hindsight_oracle_net_pnl_usd": float(candidate.get("oracle_net_pnl_usd") or 0.0),
            "hindsight_missed_entry_rows": int(candidate.get("missed_entry_rows") or 0),
            "risk_tags_to_watch": ["hindsight_missed_winner", "forced_exploration", "context_routed"],
            "mutation_notes": mutation_notes[:5],
            "success_criteria": {
                "min_closed_trades": 1,
                "profit_R_floor": 0.0,
                "must_reduce_future_missed_count": True,
                "must_record_attempt_json": True,
                "mock_only_until_promoted": True,
            },
        })
    return rows


def promote_hindsight_queue(*, max_candidates: int, family_budget: int) -> dict[str, Any]:
    payload = _load_json(HINDSIGHT_QUEUE)
    candidates = [
        row for row in payload.get("candidate_experiments") or []
        if isinstance(row, dict)
    ][:max(1, max_candidates)]
    relay_rows: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for candidate in candidates:
        for row in _candidate_to_queue_rows(candidate, family_budget=family_budget):
            family = str(row.get("family") or "")
            if not family or family in seen_families:
                continue
            relay_rows.append(row)
            seen_families.add(family)
    relay = {"evolution_queue": relay_rows}
    with _evolution_write_lock(EVOLUTION_DIR):
        queue_doc = merge_evolution_queue(
            _load_json(EVOLUTION_QUEUE),
            relay,
            source="live_hindsight_evolve_worker",
            run_id="live_hindsight",
        )
        EVOLUTION_QUEUE.write_text(json.dumps(queue_doc, indent=2), encoding="utf-8")
    status = {
        "schema": "live_hindsight_evolve_worker_status_v1",
        "updated_at": _now(),
        "hindsight_queue": str(HINDSIGHT_QUEUE),
        "evolution_queue": str(EVOLUTION_QUEUE),
        "candidate_count": len(candidates),
        "promoted_queue_rows": len(relay_rows),
        "top_contexts": [str(row.get("context_key") or "") for row in candidates[:10]],
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def run_audit() -> int:
    if not AUDIT_SCRIPT.exists():
        return 0
    proc = subprocess.run([sys.executable, str(AUDIT_SCRIPT)], cwd=str(REPO_ROOT), check=False)
    return int(proc.returncode)


def rebuild_winner_list_if_needed() -> dict[str, Any]:
    if not WINNER_LIST_SCRIPT.exists() or not AUDIT_ROWS.exists():
        return {"ran": False, "reason": "missing_script_or_audit_rows"}
    try:
        audit_mtime = AUDIT_ROWS.stat().st_mtime
        winner_mtime = WINNER_LIST.stat().st_mtime if WINNER_LIST.exists() else 0.0
    except OSError:
        return {"ran": False, "reason": "stat_failed"}
    if winner_mtime >= audit_mtime:
        return {"ran": False, "reason": "winner_list_current"}
    proc = subprocess.run([sys.executable, str(WINNER_LIST_SCRIPT)], cwd=str(REPO_ROOT), check=False)
    return {
        "ran": True,
        "return_code": int(proc.returncode),
        "audit_rows_mtime": audit_mtime,
        "previous_winner_list_mtime": winner_mtime,
    }


def run(args: argparse.Namespace) -> None:
    while True:
        audit_rc = run_audit() if bool(args.run_audit) else 0
        status = promote_hindsight_queue(
            max_candidates=int(args.max_candidates),
            family_budget=int(args.family_budget),
        )
        status["audit_return_code"] = audit_rc
        status["winner_list_rebuild"] = rebuild_winner_list_if_needed()
        STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")
        print(json.dumps(status, indent=2), flush=True)
        if bool(args.once):
            return
        time.sleep(float(args.interval_seconds))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--family-budget", type=int, default=7)
    parser.add_argument("--run-audit", action="store_true")
    parser.add_argument("--once", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
