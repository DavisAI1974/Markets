from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
COMPARE_ROOT = EVOLUTION_DIR / "live_family_registry_compare"
KILLLIST_PATH = EVOLUTION_DIR / "_live_family_killlist.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _latest_run_dir() -> Path:
    runs = [
        path for path in COMPARE_ROOT.iterdir()
        if path.is_dir() and (path / "family_registry_trades.jsonl").exists()
    ]
    if not runs:
        raise FileNotFoundError(f"No compare runs found under {COMPARE_ROOT}")
    return max(runs, key=lambda p: p.stat().st_mtime)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _context_for_trade(trade: dict[str, Any]) -> str:
    return "|".join([
        str(trade.get("asset") or "").upper(),
        str(trade.get("venue") or "").lower(),
        str(trade.get("side") or "").lower(),
        str(trade.get("bucket_session") or "").lower(),
    ])


def update(run_dir: Path, *, min_closed: int, loss_floor_usd: float) -> dict[str, Any]:
    trades = _read_jsonl(run_dir / "family_registry_trades.jsonl")
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {
        "closed": 0,
        "opened": 0,
        "realized_pnl_usd": 0.0,
        "mark_to_market_pnl_usd": 0.0,
        "wins": 0,
        "examples": [],
    })
    for trade in trades:
        family = str(trade.get("trade_strategy_id") or "").upper()
        if not family or family == "NO_TRADE":
            continue
        context = _context_for_trade(trade)
        key = (family, context)
        row = grouped[key]
        row["opened"] += 1
        if str(trade.get("status") or "") == "closed":
            pnl = float(trade.get("realized_pnl_usd") or 0.0)
            row["closed"] += 1
            row["realized_pnl_usd"] += pnl
            row["wins"] += 1 if pnl > 0 else 0
        row["mark_to_market_pnl_usd"] += float(trade.get("mark_to_market_pnl_usd") or trade.get("realized_pnl_usd") or 0.0)
        if len(row["examples"]) < 3:
            row["examples"].append({
                "account": trade.get("compare_account_id"),
                "exit_strategy_id": trade.get("exit_strategy_id"),
                "status": trade.get("status"),
                "realized_pnl_usd": trade.get("realized_pnl_usd"),
                "mark_to_market_pnl_usd": trade.get("mark_to_market_pnl_usd"),
            })

    kills: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (family, context), stats in sorted(grouped.items()):
        if int(stats["closed"]) < min_closed:
            continue
        if float(stats["realized_pnl_usd"]) > float(loss_floor_usd):
            continue
        kills[family].append({
            "context": context,
            "reason": (
                f"live compare closed={stats['closed']} pnl=${stats['realized_pnl_usd']:.2f}; "
                "quarantine exact context until evolution repairs entry/exit"
            ),
            "run_id": run_dir.name,
            "closed": int(stats["closed"]),
            "opened": int(stats["opened"]),
            "wins": int(stats["wins"]),
            "realized_pnl_usd": round(float(stats["realized_pnl_usd"]), 6),
            "mark_to_market_pnl_usd": round(float(stats["mark_to_market_pnl_usd"]), 6),
            "examples": stats["examples"],
        })

    doc = _load_json(KILLLIST_PATH)
    if not doc:
        doc = {
            "schema": "live_family_killlist_v1",
            "policy": {
                "purpose": "Prevent the resolver from calling families or exact contexts that live mock evidence shows are hurting PnL.",
                "default_scope": "context_first_global_only_after_broad_underperformance",
                "mock_only": True,
            },
            "disabled_families": [],
            "avoid_contexts": {},
        }
    avoid = doc.get("avoid_contexts") if isinstance(doc.get("avoid_contexts"), dict) else {}
    for family, rows in kills.items():
        existing = {
            str(row.get("context") or ""): dict(row)
            for row in avoid.get(family, [])
            if isinstance(row, dict)
        }
        for row in rows:
            existing[str(row["context"])] = row
        avoid[family] = sorted(existing.values(), key=lambda r: str(r.get("context") or ""))
    doc["avoid_contexts"] = avoid
    doc["updated_at"] = _now_iso()
    doc["last_source_run"] = run_dir.name
    KILLLIST_PATH.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return {
        "run_id": run_dir.name,
        "min_closed": min_closed,
        "loss_floor_usd": loss_floor_usd,
        "killed_contexts_added": sum(len(v) for v in kills.values()),
        "families": {k: len(v) for k, v in kills.items()},
        "killlist_path": str(KILLLIST_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--min-closed", type=int, default=3)
    parser.add_argument("--loss-floor-usd", type=float, default=-3.0)
    args = parser.parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else _latest_run_dir()
    print(json.dumps(update(run_dir, min_closed=args.min_closed, loss_floor_usd=args.loss_floor_usd), indent=2))


if __name__ == "__main__":
    main()
