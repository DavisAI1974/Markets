from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EVOLUTION_DIR = Path("research") / "strategy_evolution"
MIN_CONTEXT_FAMILY_SAMPLES = 3


@contextmanager
def _evolution_write_lock(evolution_dir: Path, *, timeout_s: float = 300.0):
    lock_path = evolution_dir / "._write.lock"
    deadline = time.time() + timeout_s
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.time() >= deadline:
                raise TimeoutError(f"Timed out waiting for evolution write lock: {lock_path}")
            time.sleep(0.25)
    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _safe_name(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    out = []
    for ch in text:
        if ch.isalnum() or ch in {"_", "-"}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_") or "unknown"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _bucket_parts(bucket_id: str) -> tuple[str, str, str, str, str] | None:
    parts = [str(x or "").strip() for x in str(bucket_id or "").split("|")]
    if len(parts) != 5 or not all(parts):
        return None
    family, asset, venue, side, session = parts
    return (
        _safe_name(family),
        asset.upper(),
        venue.lower(),
        side.lower(),
        session.lower(),
    )


def _fit_score(*, trades: int, pnl_r: float, win_rate: float) -> float:
    avg_r = pnl_r / max(1, trades)
    sample_bonus = min(10.0, trades / 2.0)
    return round(_clamp(50.0 + (avg_r * 22.0) + ((win_rate - 0.50) * 35.0) + sample_bonus, 0.0, 100.0), 2)


def _migration_status(score: float, trades: int, pnl_r: float) -> tuple[str, str]:
    if trades <= 0:
        return "learning", "keep_sampling"
    if pnl_r <= 0.0:
        return "avoid_context", "do_not_call_this_family_for_this_exact_context"
    if score >= 70.0:
        return "proven_instance", "call_strategy_only_for_this_exact_context"
    return "trial_instance", "positive_pnl_but_keep_sampling_this_exact_context"


def _family_profiles(routes: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for route in routes.values():
        family = _safe_name(route.get("family"))
        grouped.setdefault(family, []).append(dict(route))

    profiles: dict[str, Any] = {}
    for family, rows in sorted(grouped.items()):
        strong = [row for row in rows if str(row.get("status") or "") == "proven_instance"]
        exploratory = [row for row in rows if str(row.get("status") or "") == "trial_instance"]
        avoid = [row for row in rows if str(row.get("status") or "") == "avoid_context"]
        tradable = strong + exploratory
        venues = {str(row.get("venue") or "") for row in tradable}
        sides = {str(row.get("side") or "") for row in tradable}
        sessions = {str(row.get("session") or "") for row in tradable}
        avg_score = (
            sum(float(row.get("fit_score") or 0.0) for row in tradable) / len(tradable)
            if tradable else 0.0
        )
        max_rounds = max((len(row.get("history") or []) for row in rows), default=0)
        if max_rounds < MIN_CONTEXT_FAMILY_SAMPLES:
            role_title = "calibration"
        elif strong and len(tradable) >= 4 and len(venues) >= 2 and len(sides) >= 2 and avg_score >= 65.0:
            role_title = "generalist_candidate"
        elif len(tradable) >= 2 and avg_score >= 58.0:
            role_title = "hybrid_candidate"
        elif tradable:
            role_title = "specialist_candidate"
        elif avoid and len(avoid) == len(rows):
            role_title = "avoid_until_mutated"
        else:
            role_title = "learning"
        profiles[family] = {
            "family": family,
            "role_title": role_title,
            "callable_strategy_id": family.upper(),
            "call_rule": "never call by role_title; call only by a listed callable_instance exact context",
            "tradable_contexts": len(tradable),
            "proven_instances": len(strong),
            "exploratory_contexts": len(exploratory),
            "avoid_contexts": len(avoid),
            "avg_tradable_fit_score": round(avg_score, 2),
            "min_random_rounds_before_migration": MIN_CONTEXT_FAMILY_SAMPLES,
            "max_observed_rounds": max_rounds,
            "callable_instances": sorted(
                [
                    {
                        "bucket_id": row.get("bucket_id"),
                        "exact_context": {
                            "asset": row.get("asset"),
                            "venue": row.get("venue"),
                            "side": row.get("side"),
                            "session": row.get("session"),
                        },
                        "fit_score": row.get("fit_score"),
                        "status": row.get("status"),
                        "migration_action": row.get("migration_action"),
                    }
                    for row in tradable
                ],
                key=lambda row: float(row.get("fit_score") or 0.0),
                reverse=True,
            )[:8],
        }
    return profiles


def _context_profiles(routes: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for route in routes.values():
        key = "|".join([
            str(route.get("asset") or "").upper(),
            str(route.get("venue") or "").lower(),
            str(route.get("side") or "").lower(),
            str(route.get("session") or "").lower(),
        ])
        grouped.setdefault(key, []).append(dict(route))

    profiles: dict[str, Any] = {}
    for key, rows in sorted(grouped.items()):
        tested = sorted({_safe_name(row.get("family")) for row in rows})
        ranked = sorted(
            rows,
            key=lambda row: (
                float(row.get("pnl_R") or 0.0) > 0.0,
                float(row.get("pnl_R") or 0.0),
                float(row.get("fit_score") or 0.0),
                int(row.get("trades") or 0),
            ),
            reverse=True,
        )
        status = "migration_ready" if len(tested) >= MIN_CONTEXT_FAMILY_SAMPLES else "random_calibration"
        profiles[key] = {
            "context": key,
            "status": status,
            "tested_family_count": len(tested),
            "min_family_count_before_migration": MIN_CONTEXT_FAMILY_SAMPLES,
            "tested_families": tested,
            "unseen_family_slots_remaining": max(0, MIN_CONTEXT_FAMILY_SAMPLES - len(tested)),
            "best_family": ranked[0].get("family") if ranked else "",
            "best_fit_score": ranked[0].get("fit_score") if ranked else 0.0,
            "callable_instances": [
                {
                    "family": row.get("family"),
                    "bucket_id": row.get("bucket_id"),
                    "callable_strategy_id": str(row.get("family") or "").upper(),
                    "exact_context": {
                        "asset": row.get("asset"),
                        "venue": row.get("venue"),
                        "side": row.get("side"),
                        "session": row.get("session"),
                    },
                    "fit_score": row.get("fit_score"),
                    "status": row.get("status"),
                    "trades": row.get("trades"),
                    "pnl_R": row.get("pnl_R"),
                    "win_rate": row.get("win_rate"),
                }
                for row in ranked
            ],
        }
    return profiles


def build_study_list(routing_doc: dict[str, Any], *, source: str, run_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    promoted: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for context, profile in sorted((routing_doc.get("context_profiles") or {}).items()):
        instances = list((profile or {}).get("callable_instances") or [])
        positives = [
            dict(row)
            for row in instances
            if float(row.get("pnl_R") or 0.0) > 0.0
            and str(row.get("status") or "") != "avoid_context"
        ]
        if positives:
            positives.sort(
                key=lambda row: (
                    float(row.get("pnl_R") or 0.0),
                    float(row.get("fit_score") or 0.0),
                    int(row.get("trades") or 0),
                ),
                reverse=True,
            )
            best = positives[0]
            promoted.append({
                "context": context,
                "action": "execute_best_known_then_refine",
                "family": best.get("family"),
                "bucket_id": best.get("bucket_id"),
                "pnl_R": best.get("pnl_R"),
                "fit_score": best.get("fit_score"),
                "trades": best.get("trades"),
                "win_rate": best.get("win_rate"),
                "source": source,
                "run_id": run_id,
            })
        else:
            unresolved.append({
                "context": context,
                "action": "background_mine_winner_before_next_slice",
                "status": profile.get("status") or "unresolved",
                "tested_family_count": int(profile.get("tested_family_count") or 0),
                "tested_families": list(profile.get("tested_families") or []),
                "best_family_so_far": profile.get("best_family") or "",
                "best_fit_score_so_far": profile.get("best_fit_score") or 0.0,
                "candidate_instances": instances,
                "required_next_step": (
                    "Replay/mutate active families and exit profiles against this exact context, "
                    "then promote the best positive route before the next 6-hour slice."
                ),
                "source": source,
                "run_id": run_id,
            })
    return {
        "schema": "strategy_context_study_list_v1",
        "updated_at": now,
        "source": source,
        "run_id": run_id,
        "policy": {
            "purpose": "Resolve missed/no-winner contexts after the trade window has passed so later slices execute learned routes.",
            "execution_bias": "loosen_after_each_run",
            "do_not_treat_unresolved_as_no_trade": True,
            "promote_positive_exact_contexts_before_next_slice": True,
        },
        "promoted_contexts": promoted,
        "unresolved_contexts": unresolved,
    }


def merge_strategy_routing(existing: dict[str, Any], relay: dict[str, Any], *, source: str, run_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not existing:
        existing = {
            "schema": "strategy_context_routing_v1",
            "created_at": now,
            "routes": {},
        }
    routes = dict(existing.get("routes") or {})
    for family, report in (relay.get("family_reports") or {}).items():
        family = _safe_name(family)
        buckets = list((report or {}).get("best_buckets") or []) + list((report or {}).get("worst_buckets") or [])
        seen_buckets: set[str] = set()
        for bucket in buckets:
            raw_bucket_id = str(bucket.get("bucket_id") or "")
            if raw_bucket_id in seen_buckets:
                continue
            seen_buckets.add(raw_bucket_id)
            parts = _bucket_parts(str(bucket.get("bucket_id") or ""))
            if parts is None:
                continue
            bucket_family, asset, venue, side, session = parts
            if bucket_family != family:
                continue
            trades = int(bucket.get("trades") or 0)
            pnl_r = float(bucket.get("pnl_R") or 0.0)
            win_rate = float(bucket.get("win_rate") or 0.0)
            score = _fit_score(trades=trades, pnl_r=pnl_r, win_rate=win_rate)
            status, action = _migration_status(score, trades, pnl_r)
            route_key = "|".join([family, asset, venue, side, session])
            previous = dict(routes.get(route_key) or {})
            history = list(previous.get("history") or [])
            history.append({
                "updated_at": now,
                "source": source,
                "run_id": run_id,
                "trades": trades,
                "pnl_R": round(pnl_r, 6),
                "pnl_positive": bool(pnl_r > 0.0),
                "win_rate": round(win_rate, 6),
                "fit_score": score,
            })
            history = history[-20:]
            previous_pnl_r = float(previous.get("pnl_R") or 0.0)
            previous_trades = int(previous.get("trades") or 0)
            previous_positive = (
                previous_pnl_r > 0.0
                and previous_trades > 0
                and str(previous.get("status") or "") != "avoid_context"
            )
            if previous_positive and pnl_r <= previous_pnl_r:
                preserved = dict(previous)
                preserved["history"] = history
                preserved["last_non_promoting_probe"] = {
                    "updated_at": now,
                    "source": source,
                    "run_id": run_id,
                    "trades": trades,
                    "pnl_R": round(pnl_r, 6),
                    "win_rate": round(win_rate, 6),
                    "fit_score": score,
                    "reason": "existing positive exact-context winner preserved",
                }
                routes[route_key] = preserved
                continue
            routes[route_key] = {
                "family": family,
                "callable_strategy_id": family.upper(),
                "asset": asset,
                "venue": venue,
                "side": side,
                "session": session,
                "bucket_id": route_key,
                "exact_context": {
                    "asset": asset,
                    "venue": venue,
                    "side": side,
                    "session": session,
                },
                "fit_score": score,
                "status": status,
                "migration_action": action,
                "call_rule": "call this strategy only when the exact context matches; do not call a generic specialist",
                "trades": trades,
                "pnl_R": round(pnl_r, 6),
                "win_rate": round(win_rate, 6),
                "updated_at": now,
                "source": source,
                "run_id": run_id,
                "history": history,
            }
    existing.update({
        "schema": "strategy_context_routing_v1",
        "updated_at": now,
        "min_context_family_samples_before_migration": MIN_CONTEXT_FAMILY_SAMPLES,
        "routes": dict(sorted(routes.items())),
        "family_profiles": _family_profiles(routes),
        "context_profiles": _context_profiles(routes),
    })
    return existing


def family_memory_doc(
    family: str,
    family_report: dict[str, Any],
    relay: dict[str, Any],
    *,
    source: str,
    run_id: str,
) -> dict[str, Any]:
    family = _safe_name(family)
    handoffs = [
        row for row in relay.get("handoffs") or []
        if _safe_name(row.get("from_family")) == family or _safe_name(row.get("to_family")) == family
    ]
    queue = [
        row for row in relay.get("evolution_queue") or []
        if _safe_name(row.get("family")) == family
    ]
    candidate_experiments = [
        row for row in relay.get("candidate_experiments") or []
        if _safe_name(row.get("family")) == family
    ]
    attempts = [
        row for row in relay.get("strategy_attempts") or []
        if _safe_name(row.get("family")) == family
    ]
    return {
        "schema": "strategy_family_evolution_v1",
        "family": family,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
        "run_id": run_id,
        "latest_report": family_report,
        "handoffs": handoffs,
        "queue": queue,
        "candidate_experiments": candidate_experiments,
        "attempts": attempts,
        "training_targets": {
            "preserve_features": list(family_report.get("useful_features") or []),
            "fix_features": list(family_report.get("missing_or_misleading_features") or []),
            "avoid_reasons": list(family_report.get("poor_fit_reasons") or []),
            "next_family_candidates": list(family_report.get("next_family_candidates") or []),
        },
    }


def merge_family_memory(existing: dict[str, Any], new_doc: dict[str, Any], *, max_history: int = 50) -> dict[str, Any]:
    if not existing:
        existing = {
            "schema": "strategy_family_evolution_memory_v1",
            "family": new_doc["family"],
            "created_at": new_doc["updated_at"],
            "history": [],
        }
    history = list(existing.get("history") or [])
    history.append(new_doc)
    history = history[-max_history:]
    existing.update({
        "schema": "strategy_family_evolution_memory_v1",
        "family": new_doc["family"],
        "updated_at": new_doc["updated_at"],
        "latest_report": new_doc.get("latest_report") or {},
        "latest_training_targets": new_doc.get("training_targets") or {},
        "latest_handoffs": new_doc.get("handoffs") or [],
        "latest_queue": new_doc.get("queue") or [],
        "latest_candidate_experiments": new_doc.get("candidate_experiments") or [],
        "latest_attempts": new_doc.get("attempts") or [],
        "history": history,
    })
    return existing


def merge_evolution_queue(existing: dict[str, Any], relay: dict[str, Any], *, source: str, run_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not existing:
        existing = {
            "schema": "strategy_evolution_queue_v1",
            "created_at": now,
            "items": [],
        }

    rows_by_family = {
        _safe_name(row.get("family")): dict(row)
        for row in existing.get("items") or []
        if _safe_name(row.get("family"))
    }
    for row in relay.get("evolution_queue") or []:
        family = _safe_name(row.get("family"))
        if not family:
            continue
        source_family = _safe_name(row.get("source_family"))
        if source_family and source_family != family:
            rows_by_family.pop(source_family, None)
        merged = dict(rows_by_family.get(family) or {})
        merged.update(row)
        merged.update({
            "family": family,
            "updated_at": now,
            "source": source,
            "run_id": run_id,
            "status": "queued",
        })
        rows_by_family[family] = merged

    priority_order = {"high": 0, "medium": 1, "low": 2}
    items = sorted(
        rows_by_family.values(),
        key=lambda row: (priority_order.get(str(row.get("priority") or "medium"), 1), str(row.get("family") or "")),
    )
    existing.update({
        "schema": "strategy_evolution_queue_v1",
        "updated_at": now,
        "items": items,
    })
    return existing


def write_candidate_experiments(path: Path, relay: dict[str, Any], *, source: str, run_id: str) -> dict[str, Any]:
    payload = {
        "schema": "strategy_candidate_experiments_v1",
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
        "run_id": run_id,
        "experiments": list(relay.get("candidate_experiments") or []),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def merge_candidate_experiments(
    existing: dict[str, Any],
    experiments: list[dict[str, Any]],
    *,
    source: str,
    run_id: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not existing:
        existing = {
            "schema": "strategy_candidate_experiments_v1",
            "created_at": now,
            "experiments": [],
        }
    rows_by_key: dict[str, dict[str, Any]] = {}
    for row in existing.get("experiments") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("experiment_id") or row.get("source_variant_id") or row.get("variant_id") or "")
        if not key:
            key = "|".join([_safe_name(row.get("family")), str(row.get("action") or ""), str(row.get("source_family") or "")])
        rows_by_key[key] = dict(row)
    for row in experiments:
        if not isinstance(row, dict):
            continue
        key = str(row.get("experiment_id") or row.get("source_variant_id") or row.get("variant_id") or "")
        if not key:
            key = "|".join([_safe_name(row.get("family")), str(row.get("action") or ""), str(row.get("source_family") or "")])
        merged = dict(rows_by_key.get(key) or {})
        merged.update(row)
        merged.update({
            "updated_at": now,
            "source": source,
            "run_id": run_id,
        })
        rows_by_key[key] = merged
    existing.update({
        "schema": "strategy_candidate_experiments_v1",
        "updated_at": now,
        "source": source,
        "run_id": run_id,
        "experiments": sorted(
            rows_by_key.values(),
            key=lambda row: (
                {"high": 0, "medium": 1, "low": 2}.get(str(row.get("priority") or "medium"), 1),
                str(row.get("updated_at") or ""),
                str(row.get("family") or ""),
            ),
        )[-200:],
    })
    return existing


def write_attempts_jsonl(path: Path, attempts: list[dict[str, Any]], *, source: str, run_id: str, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as handle:
        for attempt in attempts:
            row = dict(attempt)
            row["source"] = source
            row["run_id"] = run_id
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def strategy_attempt_from_trade_open(trade: dict[str, Any]) -> dict[str, Any] | None:
    family = _safe_name(trade.get("trade_strategy_id"))
    if not family or family in {"no_trade", "unknown"}:
        return None
    mode = str(trade.get("trade_strategy_mode") or trade.get("kind") or "practice")
    if mode == "product":
        return None
    variant_id = str(trade.get("trade_strategy_variant_id") or f"{family}__open")
    risk_tags = [
        str(tag)
        for tag in (trade.get("trade_strategy_risk_tags") or [])
        if str(tag)
    ]
    if bool(trade.get("trade_strategy_forced")) and "forced_exploration" not in risk_tags:
        risk_tags.append("forced_exploration")
    side_policy = "fade_pressure" if family in {"mean_reversion_chop", "liquidity_squeeze"} else "follow_pressure"
    return {
        "schema": "strategy_attempt_v1",
        "family": family,
        "variant_id": variant_id,
        "mode": mode,
        "forced_exploration": bool(trade.get("trade_strategy_forced")),
        "entry_logic": {
            "side_policy": side_policy,
            "required_context": [],
            "risk_tags": sorted(dict.fromkeys(risk_tags)),
            "allowed_to_trade_bad_bucket": "known_bad_bucket" in set(risk_tags),
            "source_queue_action": str(trade.get("trade_strategy_source_queue_action") or ""),
        },
        "observed_context": {
            "asset": trade.get("asset"),
            "venue": trade.get("venue"),
            "session": trade.get("bucket_session"),
            "side": trade.get("side"),
            "regime": trade.get("regime") or ((trade.get("high_conviction_ticket") or {}).get("regime")),
            "volume_zscore": float(trade.get("volume_zscore") or 0.0),
            "mean_dipole": float(trade.get("mean_dipole") or 0.0),
            "recent_bps": float(trade.get("trade_recent_2chunk_bps") or 0.0),
            "current_bps": float(trade.get("trade_current_chunk_bps") or 0.0),
            "from_onset_bps": float(trade.get("trade_from_onset_bps") or 0.0),
            "present_score": int(trade.get("trade_present_score") or 0),
            "opened_at_utc": float(trade.get("ts_utc") or 0.0),
            "cell_id": trade.get("cell_id"),
        },
        "outcome": {
            "status": "opened",
            "closed_trades": 0,
            "pnl_R": 0.0,
            "win_rate": None,
            "close_reasons": [],
        },
        "learning": {
            "what_it_saw": list(trade.get("trade_strategy_reasons") or []),
            "why_it_failed_or_worked": ["opened; awaiting close/outcome scoring"],
            "features_to_preserve": list(trade.get("trade_strategy_reasons") or []),
            "features_to_mutate": list(trade.get("trade_strategy_blockers") or []),
            "next_family": "",
            "next_variant_hint": str(trade.get("trade_strategy_handoff_hint") or ""),
        },
    }


def _open_attempt_queue_item(attempt: dict[str, Any]) -> dict[str, Any]:
    family = _safe_name(attempt.get("family"))
    learning = dict(attempt.get("learning") or {})
    entry = dict(attempt.get("entry_logic") or {})
    return {
        "family": family,
        "source_family": family,
        "source_variant_id": attempt.get("variant_id"),
        "action": "score_open_attempt_then_mutate",
        "priority": "high",
        "reason": "Trade attempt opened; keep this family in the learning queue until the closed outcome refines or rejects the exact context.",
        "force_learning_trade": False,
        "requested_strategy_families": [family.upper()],
        "risk_tags_to_watch": list(entry.get("risk_tags") or []),
        "mutation_notes": list(learning.get("features_to_mutate") or []) or [str(learning.get("next_variant_hint") or "Score this open attempt before promoting or mutating.")],
        "success_criteria": {
            "min_closed_trades": 1,
            "profit_R_floor": 0.0,
            "must_record_attempt_json": True,
            "only_positive_pnl_exact_contexts_execute": True,
        },
    }


def _open_attempt_candidate_experiment(attempt: dict[str, Any]) -> dict[str, Any]:
    family = _safe_name(attempt.get("family"))
    context = dict(attempt.get("observed_context") or {})
    entry = dict(attempt.get("entry_logic") or {})
    learning = dict(attempt.get("learning") or {})
    variant_id = str(attempt.get("variant_id") or "")
    return {
        "experiment_id": f"{variant_id}__open_attempt",
        "family": family,
        "source_family": family,
        "source_variant_id": variant_id,
        "action": "observe_then_route_by_positive_pnl",
        "priority": "high",
        "force_learning_trade": False,
        "requested_strategy_families": [family.upper()],
        "exact_context": {
            "asset": context.get("asset"),
            "venue": context.get("venue"),
            "side": context.get("side"),
            "session": context.get("session"),
        },
        "entry_logic": entry,
        "mutation_notes": list(learning.get("features_to_mutate") or []) or [str(learning.get("next_variant_hint") or "Await close, then refine if PnL positive or mutate away if not.")],
        "success_criteria": {
            "min_closed_trades": 1,
            "profit_R_floor": 0.0,
            "promote_only_if_pnl_positive": True,
            "avoid_exact_context_if_pnl_non_positive": True,
            "must_record_attempt_json": True,
        },
    }


def record_trade_attempt_open_json(
    trade: dict[str, Any],
    *,
    source: str,
    run_id: str,
    run_dir: str | Path | None = None,
    evolution_dir: str | Path = DEFAULT_EVOLUTION_DIR,
) -> dict[str, Any] | None:
    attempt = strategy_attempt_from_trade_open(trade)
    if attempt is None:
        return None
    evolution_dir = Path(evolution_dir)
    evolution_dir.mkdir(parents=True, exist_ok=True)
    source = str(source or "trade_open")
    run_id = str(run_id or trade.get("cell_id") or trade.get("intent_id") or "trade_open")

    shared_attempts_path = evolution_dir / "_attempts.jsonl"
    write_attempts_jsonl(shared_attempts_path, [attempt], source=source, run_id=run_id, append=True)

    shared_variants_path = evolution_dir / "_variants.json"
    variants_doc = merge_variants(_load_json(shared_variants_path), [attempt], source=source, run_id=run_id)
    shared_variants_path.write_text(json.dumps(variants_doc, indent=2), encoding="utf-8")

    relay = {
        "evolution_queue": [_open_attempt_queue_item(attempt)],
        "candidate_experiments": [_open_attempt_candidate_experiment(attempt)],
    }
    shared_queue_path = evolution_dir / "_queue.json"
    queue_doc = merge_evolution_queue(_load_json(shared_queue_path), relay, source=source, run_id=run_id)
    shared_queue_path.write_text(json.dumps(queue_doc, indent=2), encoding="utf-8")

    shared_experiments_path = evolution_dir / "_candidate_experiments.json"
    experiments_doc = merge_candidate_experiments(
        _load_json(shared_experiments_path),
        list(relay.get("candidate_experiments") or []),
        source=source,
        run_id=run_id,
    )
    shared_experiments_path.write_text(json.dumps(experiments_doc, indent=2), encoding="utf-8")

    written = {
        "attempt": attempt,
        "shared_attempts_path": str(shared_attempts_path),
        "shared_variants_path": str(shared_variants_path),
        "shared_queue_path": str(shared_queue_path),
        "shared_candidate_experiments_path": str(shared_experiments_path),
    }
    if run_dir:
        run_family_dir = Path(run_dir) / "evolved_families"
        run_attempts_path = run_family_dir / "_attempts.jsonl"
        run_variants_path = run_family_dir / "_variants.json"
        run_queue_path = run_family_dir / "_queue.json"
        run_experiments_path = run_family_dir / "_candidate_experiments.json"
        write_attempts_jsonl(run_attempts_path, [attempt], source=source, run_id=run_id, append=True)
        run_variants_doc = merge_variants(_load_json(run_variants_path), [attempt], source=source, run_id=run_id)
        run_variants_path.write_text(json.dumps(run_variants_doc, indent=2), encoding="utf-8")
        run_queue_doc = merge_evolution_queue(_load_json(run_queue_path), relay, source=source, run_id=run_id)
        run_queue_path.write_text(json.dumps(run_queue_doc, indent=2), encoding="utf-8")
        run_experiments_doc = merge_candidate_experiments(
            _load_json(run_experiments_path),
            list(relay.get("candidate_experiments") or []),
            source=source,
            run_id=run_id,
        )
        run_experiments_path.write_text(json.dumps(run_experiments_doc, indent=2), encoding="utf-8")
        written.update({
            "run_attempts_path": str(run_attempts_path),
            "run_variants_path": str(run_variants_path),
            "run_queue_path": str(run_queue_path),
            "run_candidate_experiments_path": str(run_experiments_path),
        })
    return written


def merge_variants(existing: dict[str, Any], attempts: list[dict[str, Any]], *, source: str, run_id: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not existing:
        existing = {
            "schema": "strategy_variants_v1",
            "created_at": now,
            "variants": {},
        }
    variants = dict(existing.get("variants") or {})
    for attempt in attempts:
        variant_id = str(attempt.get("variant_id") or "")
        if not variant_id:
            continue
        variants[variant_id] = {
            "family": _safe_name(attempt.get("family")),
            "variant_id": variant_id,
            "updated_at": now,
            "source": source,
            "run_id": run_id,
            "forced_exploration": bool(attempt.get("forced_exploration")),
            "entry_logic": dict(attempt.get("entry_logic") or {}),
            "latest_outcome": dict(attempt.get("outcome") or {}),
            "latest_learning": dict(attempt.get("learning") or {}),
        }
    existing.update({
        "schema": "strategy_variants_v1",
        "updated_at": now,
        "variants": variants,
    })
    return existing


def write_evolved_family_jsons(
    relay: dict[str, Any],
    *,
    run_dir: str | Path,
    source: str,
    run_id: str,
    evolution_dir: str | Path = DEFAULT_EVOLUTION_DIR,
) -> dict[str, Any]:
    family_reports = relay.get("family_reports") or {}
    run_dir = Path(run_dir)
    evolution_dir = Path(evolution_dir)
    run_family_dir = run_dir / "evolved_families"
    run_family_dir.mkdir(parents=True, exist_ok=True)
    evolution_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = run_family_dir / "_manifest.json"
    run_queue_path = run_family_dir / "_queue.json"
    run_experiments_path = run_family_dir / "_candidate_experiments.json"
    run_attempts_path = run_family_dir / "_attempts.jsonl"
    run_variants_path = run_family_dir / "_variants.json"
    run_routing_path = run_family_dir / "_routing.json"
    run_study_path = run_family_dir / "_study_list.json"
    shared_queue_path = evolution_dir / "_queue.json"
    shared_experiments_path = evolution_dir / "_candidate_experiments.json"
    shared_attempts_path = evolution_dir / "_attempts.jsonl"
    shared_variants_path = evolution_dir / "_variants.json"
    shared_routing_path = evolution_dir / "_routing.json"
    shared_study_path = evolution_dir / "_study_list.json"
    previous = _load_json(manifest_path)
    previous_families = dict(previous.get("families") or {})
    written: dict[str, Any] = {
        "schema": "strategy_family_evolution_write_v1",
        "run_dir": str(run_dir),
        "evolution_dir": str(evolution_dir),
        "families": previous_families,
    }
    for raw_family, report in sorted(family_reports.items()):
        family = _safe_name(raw_family)
        doc = family_memory_doc(family, dict(report or {}), relay, source=source, run_id=run_id)

        run_path = run_family_dir / f"{family}.json"
        run_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

        memory_path = evolution_dir / f"{family}.json"
        merged = merge_family_memory(_load_json(memory_path), doc)
        memory_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

        written["families"][family] = {
            "run_path": str(run_path),
            "memory_path": str(memory_path),
            "trades": int((report or {}).get("trades") or 0),
            "pnl_R": float((report or {}).get("pnl_R") or 0.0),
        }

    experiments = list(relay.get("candidate_experiments") or [])
    attempts = list(relay.get("strategy_attempts") or [])
    write_attempts_jsonl(run_attempts_path, attempts, source=source, run_id=run_id, append=False)
    experiments_doc = merge_candidate_experiments(
        _load_json(run_experiments_path),
        experiments,
        source=source,
        run_id=run_id,
    )
    run_experiments_path.write_text(json.dumps(experiments_doc, indent=2), encoding="utf-8")

    with _evolution_write_lock(evolution_dir):
        queue_doc = merge_evolution_queue(_load_json(shared_queue_path), relay, source=source, run_id=run_id)
        run_queue_path.write_text(json.dumps(queue_doc, indent=2), encoding="utf-8")
        shared_queue_path.write_text(json.dumps(queue_doc, indent=2), encoding="utf-8")
        shared_experiments_doc = merge_candidate_experiments(
            _load_json(shared_experiments_path),
            experiments,
            source=source,
            run_id=run_id,
        )
        shared_experiments_path.write_text(json.dumps(shared_experiments_doc, indent=2), encoding="utf-8")
        write_attempts_jsonl(shared_attempts_path, attempts, source=source, run_id=run_id, append=True)
        variants_doc = merge_variants(_load_json(shared_variants_path), attempts, source=source, run_id=run_id)
        run_variants_path.write_text(json.dumps(variants_doc, indent=2), encoding="utf-8")
        shared_variants_path.write_text(json.dumps(variants_doc, indent=2), encoding="utf-8")
        routing_doc = merge_strategy_routing(_load_json(shared_routing_path), relay, source=source, run_id=run_id)
        run_routing_path.write_text(json.dumps(routing_doc, indent=2), encoding="utf-8")
        shared_routing_path.write_text(json.dumps(routing_doc, indent=2), encoding="utf-8")
        study_doc = build_study_list(routing_doc, source=source, run_id=run_id)
        run_study_path.write_text(json.dumps(study_doc, indent=2), encoding="utf-8")
        shared_study_path.write_text(json.dumps(study_doc, indent=2), encoding="utf-8")
    written["queue_path"] = str(run_queue_path)
    written["shared_queue_path"] = str(shared_queue_path)
    written["candidate_experiments_path"] = str(run_experiments_path)
    written["shared_candidate_experiments_path"] = str(shared_experiments_path)
    written["attempts_path"] = str(run_attempts_path)
    written["shared_attempts_path"] = str(shared_attempts_path)
    written["variants_path"] = str(run_variants_path)
    written["shared_variants_path"] = str(shared_variants_path)
    written["routing_path"] = str(run_routing_path)
    written["shared_routing_path"] = str(shared_routing_path)
    written["study_list_path"] = str(run_study_path)
    written["shared_study_list_path"] = str(shared_study_path)

    manifest_path.write_text(json.dumps(written, indent=2), encoding="utf-8")
    written["manifest_path"] = str(manifest_path)
    return written
