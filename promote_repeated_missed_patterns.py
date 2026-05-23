from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
EVOLUTION_DIR = REPO_ROOT / "research" / "strategy_evolution"
MISSED_JSONL = EVOLUTION_DIR / "_live_missed_winning_opportunities.jsonl"
PROMOTIONS_PATH = EVOLUTION_DIR / "_promoted_missed_patterns.json"
EXPERIMENTS_PATH = EVOLUTION_DIR / "_candidate_experiments.json"
MIN_REPEATS = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe(value: Any) -> str:
    text = str(value or "").strip().lower()
    out = []
    for ch in text:
        out.append(ch if ch.isalnum() else "_")
    return "_".join("".join(out).split("_")) or "unknown"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


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


def _write_candidate_experiments(experiments: list[dict[str, Any]]) -> None:
    existing = _read_json(EXPERIMENTS_PATH)
    rows_by_id = {
        str(row.get("experiment_id") or ""): dict(row)
        for row in existing.get("experiments") or []
        if isinstance(row, dict) and str(row.get("experiment_id") or "")
    }
    for row in experiments:
        rows_by_id[str(row["experiment_id"])] = row
    payload = {
        "schema": "strategy_candidate_experiments_v1",
        "updated_at": _now_iso(),
        "source": str(PROMOTIONS_PATH),
        "run_id": "promote_repeated_missed_patterns",
        "experiments": sorted(
            rows_by_id.values(),
            key=lambda row: (
                {"high": 0, "medium": 1, "low": 2}.get(str(row.get("priority") or "medium"), 1),
                str(row.get("experiment_id") or ""),
            ),
        )[-300:],
    }
    if existing.get("created_at"):
        payload["created_at"] = existing["created_at"]
    EXPERIMENTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def promote() -> dict[str, Any]:
    rows = _read_jsonl(MISSED_JSONL)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        context = str(row.get("context") or "")
        family = str(row.get("family") or "").upper()
        reason = str(row.get("blocked_reason") or "")
        if not context or not family:
            continue
        grouped[(context, family, reason)].append(row)

    promotions = []
    experiments = []
    for (context, family, reason), bucket in sorted(grouped.items()):
        if len(bucket) < MIN_REPEATS:
            continue
        first = bucket[0]
        family_slug = _safe(family)
        context_slug = _safe(context)
        reason_slug = _safe(reason)
        synthetic_family = f"{family_slug}__missed_{reason_slug}__{context_slug}"
        contexts = [str(row.get("context") or "") for row in bucket]
        pressure_states = Counter(str(row.get("pressure_state") or "") for row in bucket).most_common()
        promotion = {
            "schema": "promoted_missed_pattern_v1",
            "updated_at": _now_iso(),
            "pattern_id": synthetic_family,
            "candidate_family_id": synthetic_family.upper(),
            "base_family": family,
            "context": context,
            "blocked_reason": reason,
            "repeat_count": len(bucket),
            "pressure_states": pressure_states,
            "route_evidence": first.get("route_evidence"),
            "promotion_rule": f"missed positive route repeated >= {MIN_REPEATS}; test as first-class hybrid/new-family candidate",
            "exact_context": {
                "asset": first.get("asset"),
                "venue": first.get("venue"),
                "side": first.get("side"),
                "session": first.get("session"),
            },
            "source_contexts": contexts,
        }
        promotions.append(promotion)
        experiments.append({
            "experiment_id": f"{synthetic_family}__promotion_candidate",
            "family": family,
            "candidate_family_id": synthetic_family.upper(),
            "action": "promote_repeated_missed_pattern_to_hybrid_or_new_family",
            "priority": "high",
            "force_learning_trade": True,
            "requested_strategy_families": [family],
            "exact_context": promotion["exact_context"],
            "blocked_reason": reason,
            "repeat_count": len(bucket),
            "entry_hypothesis": (
                f"{family} at {context} repeatedly appeared as a positive route but was missed by {reason}; "
                "create a direct recognizer or hybrid that surfaces it before the generic gate blocks it."
            ),
            "exit_hypothesis": "Test all exit variants and require net-after-fee profitability before promotion.",
            "success_criteria": {
                "min_repeats": MIN_REPEATS,
                "profit_after_fees": True,
                "must_reduce_future_missed_count": True,
                "must_update_routing_or_family_memory": True,
            },
        })

    payload = {
        "schema": "promoted_missed_patterns_v1",
        "updated_at": _now_iso(),
        "min_repeats": MIN_REPEATS,
        "source": str(MISSED_JSONL),
        "promotions": promotions,
    }
    PROMOTIONS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if experiments:
        _write_candidate_experiments(experiments)
    return {
        "missed_rows": len(rows),
        "promotions": len(promotions),
        "promotion_path": str(PROMOTIONS_PATH),
        "candidate_experiments_added": len(experiments),
    }


if __name__ == "__main__":
    print(json.dumps(promote(), indent=2))
