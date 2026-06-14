from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from oracle_winner_trade_memory import (
    DEFAULT_ORACLE_WINNER_LIST_PATH,
    oracle_winner_canonical_trade_key,
    oracle_winner_route_keys,
)

DEFAULT_ASSIGNMENTS = REPO_ROOT / "research" / "strategy_evolution" / "_winner_trade_pnl_strategy_assignments_h0_h168.json"
DEFAULT_OPPORTUNITY_LEDGER = REPO_ROOT / "research" / "strategy_evolution" / "opportunity_ledger_h0_h168_loose_and_dense.json"
DEFAULT_LIVE_AUDIT_ROWS = REPO_ROOT / "research" / "strategy_evolution" / "live_mock_replay" / "live_hindsight_missed_winner_audit_rows.csv"
DEFAULT_POLICY_ROWS = REPO_ROOT / "research" / "strategy_evolution" / "live_mock_replay" / "live_counterfactual_exit_policy_rows.csv"
DEFAULT_SUMMARY = REPO_ROOT / "research" / "strategy_evolution" / "oracle_winner_trade_list.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _text(value).upper()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _runtime_exit_class(exit_id: str) -> str:
    exit_id = _text(exit_id)
    if exit_id.startswith("fixed_hold_") and "_after_" in exit_id:
        start = exit_id.split("m_after_", 1)[1] if "m_after_" in exit_id else ""
        return "fixed_hold_after_entry" if start == "entry" else "fixed_hold_after_runtime_exit"
    if exit_id.startswith("actual_exit::"):
        return "actual_exit"
    return "oracle_memory_exit"


def _runtime_exit_horizon(exit_id: str, fallback: int = 0) -> int:
    exit_id = _text(exit_id)
    if exit_id.startswith("fixed_hold_") and "m_after_" in exit_id:
        raw = exit_id.replace("fixed_hold_", "").split("m_after_", 1)[0]
        return _int(raw, fallback)
    return fallback


def _score_band(score: Any) -> str:
    value = _int(score)
    if value <= 0:
        return "none"
    if value < 40:
        return "0_39"
    if value < 55:
        return "40_54"
    if value < 70:
        return "55_69"
    if value < 85:
        return "70_84"
    return "85_100"


def _entry_base(
    *,
    source: str,
    source_id: str,
    strategy_id: str,
    asset: str,
    venue: str,
    side: str,
    bucket_session: str,
    entry_ts_utc: float,
    net_pnl_usd: float,
    net_bps: float,
    runtime_exit_id: str,
    oracle_exit_id: str,
    horizon_minutes: int,
    row: dict[str, Any],
) -> dict[str, Any]:
    normalized_row = {
        **row,
        "strategy_id": _upper(strategy_id),
        "trade_strategy_id": _upper(strategy_id),
        "asset": _upper(asset),
        "venue": _text(venue),
        "side": _lower(side),
        "bucket_session": _text(bucket_session),
    }
    canonical_key = oracle_winner_canonical_trade_key(normalized_row)
    return {
        "schema": "oracle_winner_trade_v1",
        "canonical_trade_key": canonical_key,
        "source": source,
        "source_id": source_id,
        "strategy_id": _upper(strategy_id),
        "trade_strategy_id": _upper(strategy_id),
        "asset": _upper(asset),
        "venue": _text(venue),
        "side": _lower(side),
        "bucket_session": _text(bucket_session),
        "entry_ts_utc": float(entry_ts_utc or 0.0),
        "chunk_id": _text(row.get("chunk_id")),
        "trade_stage": _text(row.get("trade_stage")) or "none",
        "trade_option_state": _text(row.get("trade_option_state")) or "none",
        "pressure_watch_state": _text(row.get("pressure_watch_state")) or "none",
        "trade_present_score": _int(row.get("trade_present_score")),
        "trade_score_band": _text(row.get("trade_score_band")) or _score_band(row.get("trade_present_score")),
        "trade_current_chunk_bps": _float(row.get("trade_current_chunk_bps")),
        "trade_recent_2chunk_bps": _float(row.get("trade_recent_2chunk_bps")),
        "trade_from_onset_bps": _float(row.get("trade_from_onset_bps")),
        "mean_dipole": _float(row.get("mean_dipole")),
        "dipole_acl1": _float(row.get("dipole_acl1")),
        "volume_zscore": _float(row.get("volume_zscore")),
        "net_pnl_usd": round(float(net_pnl_usd), 8),
        "net_bps": round(float(net_bps), 8),
        "runtime_exit_id": _text(runtime_exit_id),
        "runtime_exit_class": _runtime_exit_class(runtime_exit_id),
        "oracle_exit_id": _text(oracle_exit_id),
        "horizon_minutes": int(horizon_minutes or _runtime_exit_horizon(runtime_exit_id)),
    }


def _entries_from_assignments(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("assignments") if isinstance(payload, dict) else []
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        actual_net = _float(row.get("actual_net_pnl_usd"))
        best_exec_net = _float(row.get("best_executable_net_pnl_usd"))
        best_any_net = _float(row.get("best_any_net_pnl_usd"))
        if max(actual_net, best_exec_net, best_any_net) <= 0:
            continue
        runtime_exit_id = _text(row.get("best_executable_pnl_strategy_id"))
        if not runtime_exit_id or best_exec_net <= 0:
            runtime_exit_id = f"actual_exit::{_text(row.get('actual_exit_strategy_id')) or 'runtime_actual'}"
            best_exec_net = actual_net
        oracle_exit_id = _text(row.get("best_any_pnl_strategy_id")) or runtime_exit_id
        horizon = _runtime_exit_horizon(runtime_exit_id)
        if horizon <= 0:
            for candidate in row.get("pnl_strategy_candidates") or []:
                if isinstance(candidate, dict) and _text(candidate.get("pnl_strategy_id")) == runtime_exit_id:
                    horizon = _int(candidate.get("horizon_minutes"))
                    break
        notional = _float(row.get("notional"), 10000.0) or 10000.0
        net_bps = _float(row.get("best_executable_net_bps"))
        if not net_bps:
            net_bps = best_exec_net / notional * 10000.0
        out.append(_entry_base(
            source="winner_trade_pnl_strategy_assignments",
            source_id=f"assignment:{row.get('winner_index', idx)}",
            strategy_id=_text(row.get("entry_strategy_id")),
            asset=_text(row.get("asset")),
            venue=_text(row.get("venue")),
            side=_text(row.get("side")),
            bucket_session=_text(row.get("bucket_session")),
            entry_ts_utc=_float(row.get("entry_ts_utc")),
            net_pnl_usd=best_exec_net,
            net_bps=net_bps,
            runtime_exit_id=runtime_exit_id,
            oracle_exit_id=oracle_exit_id,
            horizon_minutes=horizon,
            row=row,
        ))
    return out


def _entries_from_opportunity_ledger(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("opportunities") if isinstance(payload, dict) else []
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        pnl = _float(row.get("pnl_usd"))
        if pnl <= 0:
            continue
        notional = _float(row.get("notional"), 10000.0) or 10000.0
        net_bps = pnl / notional * 10000.0
        exit_id = f"actual_exit::{_text(row.get('exit_strategy_id')) or 'runtime_actual'}"
        out.append(_entry_base(
            source="opportunity_ledger",
            source_id=_text(row.get("id")) or f"opportunity:{idx}",
            strategy_id=_text(row.get("strategy_id")),
            asset=_text(row.get("asset")),
            venue=_text(row.get("venue")),
            side=_text(row.get("side")),
            bucket_session=_text(row.get("bucket_session")),
            entry_ts_utc=_float(row.get("ts_utc")),
            net_pnl_usd=pnl,
            net_bps=net_bps,
            runtime_exit_id=exit_id,
            oracle_exit_id=exit_id,
            horizon_minutes=_int(row.get("hold_minutes")),
            row=row,
        ))
    return out


def _entries_from_live_audit(path: Path, *, target_notional_usd: float) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for idx, row in enumerate(csv.DictReader(handle)):
            if _lower(row.get("is_oracle_winner_after_fees")) not in {"true", "1", "yes"}:
                continue
            net_bps = _float(row.get("oracle_net_bps"))
            if net_bps <= 0:
                continue
            horizon = _int(row.get("oracle_horizon_minutes"))
            # Prefer ts_utc (real per-row chunk observation time) over
            # oracle_entry_ts_utc (audit snapshot time — uniform across all rows
            # in a given audit run, see 2026-05-28 entry-timestamp investigation).
            # REGRESSION GUARD (S29): a later commit had flipped this precedence,
            # collapsing every win entry_ts to one value, which collapsed every win
            # discovery coefficient vector to one window. Do NOT flip it back.
            entry_ts = _float(row.get("ts_utc") or row.get("oracle_entry_ts_utc"))
            exit_ts = _float(row.get("oracle_exit_ts_utc"))
            exact_elapsed = int(round(max(0.0, exit_ts - entry_ts) / 60.0)) if entry_ts > 0 and exit_ts > 0 else horizon
            runtime_minutes = exact_elapsed if exact_elapsed > 0 else horizon
            runtime_exit_id = f"fixed_hold_{runtime_minutes}m_after_entry" if runtime_minutes > 0 else ""
            oracle_exit_id = f"oracle_best_within_{horizon}m_after_entry" if horizon > 0 else runtime_exit_id
            out.append(_entry_base(
                source="live_hindsight_missed_winner_audit",
                source_id=_text(row.get("unique_key")) or f"live_audit:{idx}",
                strategy_id=_text(row.get("strategy_id")),
                asset=_text(row.get("asset")),
                venue=_text(row.get("venue")),
                side=_text(row.get("side")),
                bucket_session=_text(row.get("bucket_session")),
                entry_ts_utc=entry_ts,
                net_pnl_usd=target_notional_usd * net_bps / 10000.0,
                net_bps=net_bps,
                runtime_exit_id=runtime_exit_id,
                oracle_exit_id=oracle_exit_id,
                horizon_minutes=runtime_minutes,
                row=row,
            ))
    return out


def _entries_from_policy_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for idx, row in enumerate(csv.DictReader(handle)):
            if _lower(row.get("status")) != "closed":
                continue
            runtime_exit_id = _text(row.get("cf_best_runtime_executable_id") or row.get("cf_best_executable_id"))
            net = _float(row.get("cf_best_runtime_executable_net_pnl_usd_at_target_notional"))
            if not net:
                net = _float(row.get("cf_best_executable_net_pnl_usd_at_target_notional"))
            if not runtime_exit_id or net <= 0:
                continue
            notional = _float(row.get("runtime_notional_usd"), 10000.0) or 10000.0
            out.append(_entry_base(
                source="live_counterfactual_exit_policy_rows",
                source_id=_text(row.get("cell_id")) or f"policy:{idx}",
                strategy_id=_text(row.get("family") or row.get("trade_strategy_id")),
                asset=_text(row.get("asset")),
                venue=_text(row.get("venue")),
                side=_text(row.get("side")),
                bucket_session=_text(row.get("bucket_session")),
                entry_ts_utc=_float(row.get("entry_ts_utc")),
                net_pnl_usd=net,
                net_bps=net / notional * 10000.0,
                runtime_exit_id=runtime_exit_id,
                oracle_exit_id=_text(row.get("cf_best_any_oracle_id")) or runtime_exit_id,
                horizon_minutes=_runtime_exit_horizon(runtime_exit_id),
                row=row,
            ))
    return out


def _rank_exit(exit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in exit_rows:
        exit_id = _text(row.get("runtime_exit_id"))
        if not exit_id:
            continue
        item = grouped.setdefault(exit_id, {
            "runtime_exit_id": exit_id,
            "runtime_exit_class": _text(row.get("runtime_exit_class")),
            "horizon_minutes": _int(row.get("horizon_minutes")),
            "count": 0,
            "total_net_pnl_usd": 0.0,
            "total_net_bps": 0.0,
            "best_net_bps": -1e18,
        })
        item["count"] += 1
        item["total_net_pnl_usd"] += _float(row.get("net_pnl_usd"))
        item["total_net_bps"] += _float(row.get("net_bps"))
        item["best_net_bps"] = max(float(item["best_net_bps"]), _float(row.get("net_bps")))
    ranked = []
    for item in grouped.values():
        count = max(1, int(item["count"]))
        ranked.append({
            **item,
            "avg_net_pnl_usd": round(float(item["total_net_pnl_usd"]) / count, 8),
            "avg_net_bps": round(float(item["total_net_bps"]) / count, 8),
            "total_net_pnl_usd": round(float(item["total_net_pnl_usd"]), 8),
            "total_net_bps": round(float(item["total_net_bps"]), 8),
            "best_net_bps": round(float(item["best_net_bps"]), 8),
        })
    ranked.sort(key=lambda r: (_float(r.get("total_net_bps")), _float(r.get("avg_net_bps")), _int(r.get("count"))), reverse=True)
    return {"selected": ranked[0] if ranked else {}, "ranked": ranked}


def _build_indices(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in entries:
        for level, key in oracle_winner_route_keys(row):
            buckets[level][key].append(row)
    indices: dict[str, dict[str, Any]] = {}
    for level, key_rows in buckets.items():
        indices[level] = {}
        for key, rows in key_rows.items():
            exits = _rank_exit(rows)
            count = len(rows)
            total_pnl = sum(_float(row.get("net_pnl_usd")) for row in rows)
            total_bps = sum(_float(row.get("net_bps")) for row in rows)
            indices[level][key] = {
                "count": count,
                "total_net_pnl_usd": round(total_pnl, 8),
                "total_net_bps": round(total_bps, 8),
                "avg_net_pnl_usd": round(total_pnl / count, 8) if count else 0.0,
                "avg_net_bps": round(total_bps / count, 8) if count else 0.0,
                "best_net_bps": round(max((_float(row.get("net_bps")) for row in rows), default=0.0), 8),
                "selected_exit": exits["selected"],
                "top_exits": exits["ranked"][:8],
                "examples": [
                    {
                        "source": row.get("source"),
                        "source_id": row.get("source_id"),
                        "entry_ts_utc": row.get("entry_ts_utc"),
                        "net_bps": row.get("net_bps"),
                        "runtime_exit_id": row.get("runtime_exit_id"),
                    }
                    for row in sorted(rows, key=lambda r: _float(r.get("net_bps")), reverse=True)[:8]
                ],
            }
    return indices


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    counts = payload.get("counts") or {}
    indices = payload.get("indices") or {}
    lines = [
        "# Oracle Winner Trade List",
        "",
        f"- Created: `{payload.get('created_at')}`",
        f"- Entries: `{counts.get('entries', 0)}`",
        "- Runtime admission: exact `canonical_trade_key` membership in `entries`",
        "- Exact timestamps stay in each row as evidence and hold-duration inputs, not as admission keys",
        "- Venue/platform stays in each row as execution context, not as an admission key",
        f"- Trait keys: `{counts.get('trait_keys', 0)}`",
        f"- Shape keys: `{counts.get('shape_keys', 0)}`",
        f"- Context keys: `{counts.get('context_keys', 0)}`",
        f"- Route keys: `{counts.get('route_keys', 0)}`",
        "",
        "| Source | Entries |",
        "|---|---:|",
    ]
    for source, count in sorted((counts.get("by_source") or {}).items(), key=lambda item: item[0]):
        lines.append(f"| `{source}` | {count} |")
    lines.extend(["", "## Research-Only Aggregate Indices", "", "| Level | Key | Count | Avg net bps | Selected exit |", "|---|---|---:|---:|---|"])
    rows = []
    for level in ("trait", "shape", "context", "route"):
        for key, data in (indices.get(level) or {}).items():
            rows.append((level, key, data))
    rows.sort(key=lambda item: (_float(item[2].get("total_net_bps")), _int(item[2].get("count"))), reverse=True)
    for level, key, data in rows[:50]:
        selected = data.get("selected_exit") or {}
        lines.append(
            f"| `{level}` | `{key}` | {data.get('count', 0)} | {_float(data.get('avg_net_bps')):.2f} | `{selected.get('runtime_exit_id', '')}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(args: argparse.Namespace) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    if bool(args.include_assignments) and not args.skip_assignments:
        entries.extend(_entries_from_assignments(Path(args.assignments)))
    if bool(args.include_opportunity_ledger) and not args.skip_opportunity_ledger:
        entries.extend(_entries_from_opportunity_ledger(Path(args.opportunity_ledger)))
    if not args.skip_live_audit:
        entries.extend(_entries_from_live_audit(Path(args.live_audit_rows), target_notional_usd=float(args.target_notional_usd)))
    if bool(args.include_policy_rows) and not args.skip_policy_rows:
        entries.extend(_entries_from_policy_rows(Path(args.policy_rows)))

    deduped: dict[str, dict[str, Any]] = {}
    for row in entries:
        if not row.get("strategy_id") or row.get("side") not in {"buy", "sell"}:
            continue
        if _float(row.get("net_bps")) <= 0:
            continue
        key = _text(row.get("canonical_trade_key"))
        current = deduped.get(key)
        if current is None or _float(row.get("net_bps")) > _float(current.get("net_bps")):
            if current is not None:
                row["merged_duplicate_sources"] = list(current.get("merged_duplicate_sources") or []) + [
                    {
                        "source": current.get("source"),
                        "source_id": current.get("source_id"),
                        "net_bps": current.get("net_bps"),
                        "runtime_exit_id": current.get("runtime_exit_id"),
                    }
                ]
            deduped[key] = row
        elif current is not None:
            current.setdefault("merged_duplicate_sources", []).append({
                "source": row.get("source"),
                "source_id": row.get("source_id"),
                "net_bps": row.get("net_bps"),
                "runtime_exit_id": row.get("runtime_exit_id"),
            })
    entries = sorted(deduped.values(), key=lambda row: (_text(row.get("strategy_id")), _text(row.get("asset")), _text(row.get("venue")), _float(row.get("entry_ts_utc"))))
    indices = _build_indices(entries)
    by_source: dict[str, int] = defaultdict(int)
    for row in entries:
        by_source[_text(row.get("source"))] += 1
    payload = {
        "schema": "oracle_winner_trade_list_v1",
        "created_at": _now_iso(),
        "output_path": str(Path(args.out_json)),
        "policy": {
            "description": "Live hindsight oracle source of truth. Only live hindsight oracle winners are retained by default. Historical assignments, loose opportunity rows, and sidecar policy rows are opt-in only. Runtime admission requires exact canonical_trade_key membership in entries. Timestamps and venue are retained as evidence and execution context, not admission keys.",
            "match_levels": ["entry"],
            "target_notional_usd": float(args.target_notional_usd),
            "include_assignments": bool(args.include_assignments),
            "include_opportunity_ledger": bool(args.include_opportunity_ledger),
            "include_policy_rows": bool(args.include_policy_rows),
        },
        "sources": {
            "assignments": str(Path(args.assignments)),
            "opportunity_ledger": str(Path(args.opportunity_ledger)),
            "live_audit_rows": str(Path(args.live_audit_rows)),
            "policy_rows": str(Path(args.policy_rows)),
        },
        "counts": {
            "entries": len(entries),
            "by_source": dict(sorted(by_source.items())),
            "trait_keys": len(indices.get("trait") or {}),
            "shape_keys": len(indices.get("shape") or {}),
            "context_keys": len(indices.get("context") or {}),
            "route_keys": len(indices.get("route") or {}),
        },
        "indices": indices,
        "entries": entries,
    }
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_json.with_suffix(out_json.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(out_json)
    _write_summary(Path(args.out_md), payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignments", default=str(DEFAULT_ASSIGNMENTS))
    parser.add_argument("--opportunity-ledger", default=str(DEFAULT_OPPORTUNITY_LEDGER))
    parser.add_argument("--live-audit-rows", default=str(DEFAULT_LIVE_AUDIT_ROWS))
    parser.add_argument("--policy-rows", default=str(DEFAULT_POLICY_ROWS))
    parser.add_argument("--out-json", default=str(DEFAULT_ORACLE_WINNER_LIST_PATH))
    parser.add_argument("--out-md", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--target-notional-usd", type=float, default=10000.0)
    parser.add_argument("--include-assignments", action="store_true")
    parser.add_argument("--include-opportunity-ledger", action="store_true")
    parser.add_argument("--include-policy-rows", action="store_true")
    parser.add_argument("--skip-assignments", action="store_true")
    parser.add_argument("--skip-opportunity-ledger", action="store_true")
    parser.add_argument("--skip-live-audit", action="store_true")
    parser.add_argument("--skip-policy-rows", action="store_true")
    return parser.parse_args()


def main() -> None:
    payload = build(parse_args())
    print(json.dumps({"ok": True, "counts": payload.get("counts"), "out": payload.get("output_path")}, indent=2))


if __name__ == "__main__":
    main()
