from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


NEXT_FAMILY_MAP = {
    "mean_reversion_chop": ["vol_breakout", "liquidity_squeeze", "basis_dislocation", "news_breakout"],
    "liquidity_squeeze": ["mean_reversion_chop", "vol_breakout", "basis_dislocation"],
    "news_breakout": ["mean_reversion_chop", "liquidity_squeeze", "relative_strength"],
    "vol_breakout": ["basis_dislocation", "relative_strength", "news_breakout"],
    "basis_dislocation": ["relative_strength", "vol_breakout", "news_breakout"],
    "relative_strength": ["news_breakout", "vol_breakout", "basis_dislocation"],
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _family(strategy_id: Any) -> str:
    return str(strategy_id or "unknown").strip().lower() or "unknown"


def _bucket(trade: dict[str, Any]) -> str:
    return str(trade.get("bucket_id") or "").strip()


def _win_rate(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    return sum(1 for row in rows if _float(row.get("realized_pnl_usd")) > 0.0) / len(rows)


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return sum(_float(row.get(key)) for row in rows) / len(rows)


def _top_counter(counter: Counter[str], limit: int = 5) -> dict[str, int]:
    return {key: int(value) for key, value in counter.most_common(limit)}


def _queue_item(family: str, report: dict[str, Any]) -> dict[str, Any] | None:
    trades = int(report.get("trades") or 0)
    pnl_r = _float(report.get("pnl_R"))
    skips = list(report.get("skip_diagnostics") or [])
    next_families = list(report.get("next_family_candidates") or [])

    if trades == 0:
        blocked_bad_bucket = any("blocked_bad_handoff_bucket" in str(skip) for skip in skips)
        return {
            "family": family,
            "action": "retry_on_new_slice" if blocked_bad_bucket else "evolve_or_retry",
            "priority": "high" if blocked_bad_bucket else "medium",
            "reason": (
                "Family stood down only because the current slice was a known-bad bucket; "
                "keep it queued for later sessions and assets."
                if blocked_bad_bucket
                else "Family opened no practice trades; keep it queued for mutation or a better-matched slice."
            ),
            "skip_diagnostics": skips,
            "next_family_candidates": next_families,
        }

    if pnl_r <= 0.0:
        target_family = str(next_families[0]) if next_families else family
        return {
            "family": target_family,
            "source_family": family,
            "action": "evolve_from_failed_attempt",
            "priority": "high",
            "reason": f"{family} produced negative practice evidence ({pnl_r:.2f}R); pass handoff to {target_family}.",
            "skip_diagnostics": skips,
            "next_family_candidates": next_families,
        }

    return None


def _candidate_experiment(item: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    family = _family(item.get("family"))
    action = str(item.get("action") or "evolve_or_retry")
    skips = list(item.get("skip_diagnostics") or [])
    avoid_buckets: list[str] = []
    required_context: list[str] = []
    mutation_notes: list[str] = []

    if any("blocked_bad_handoff_bucket" in str(skip) for skip in skips):
        avoid_buckets.extend([
            f"{family}|ETH|coinbase|buy|first6h",
            f"{family}|ETH|coinbase|sell|first6h",
            f"{family}|ETH|kraken|buy|first6h",
            f"{family}|ETH|kraken|sell|first6h",
        ])
        mutation_notes.append("Retry outside the blocked ETH spot first6h buckets before loosening entry rules.")
    if any("volume_not_confirmed" in str(skip) for skip in skips):
        required_context.append("volume_zscore >= 0.7 or explicit thinness proxy")
        mutation_notes.append("If no volume-confirmed contexts appear, hand off to basis_dislocation or relative_strength.")
    if any("no_news_bias" in str(skip) for skip in skips):
        required_context.append("daily news context enabled")
    if any("wrong_regime" in str(skip) for skip in skips):
        required_context.append("HERD/WHALE or nascent directional regime")
    if action == "evolve_variant":
        mutation_notes.extend(report.get("missing_or_misleading_features") or [])

    return {
        "family": family,
        "action": action,
        "priority": item.get("priority") or "medium",
        "requested_strategy_families": [family.upper()],
        "avoid_buckets": avoid_buckets,
        "required_context": required_context,
        "mutation_notes": mutation_notes or [str(item.get("reason") or "Retry and collect fit diagnostics.")],
        "success_criteria": {
            "min_closed_trades": 1,
            "must_not_open_blocked_buckets": bool(avoid_buckets),
            "profit_R_floor": 0.0,
        },
        "handoff_targets": list(item.get("next_family_candidates") or []),
    }


def _feature_notes(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    useful: list[str] = []
    missing: list[str] = []
    avg_abs_dipole = sum(abs(_float(row.get("mean_dipole"))) for row in rows) / len(rows) if rows else 0.0
    avg_volume_z = _avg(rows, "volume_zscore")
    avg_recent = _avg(rows, "trade_recent_2chunk_bps")
    avg_current = _avg(rows, "trade_current_chunk_bps")

    if avg_abs_dipole >= 0.20:
        useful.append(f"market dipole was visible on average ({avg_abs_dipole:.3f})")
    else:
        missing.append("market dipole was weak; require stronger pressure or use a non-dipole trigger")
    if avg_volume_z >= 0.7:
        useful.append(f"volume/thinness proxy was elevated (avg z={avg_volume_z:.2f})")
    else:
        missing.append("volume/thinness proxy was muted; avoid squeeze logic unless volume confirms")
    if avg_recent > 0.0 and avg_current > 0.0:
        useful.append("recent and current movement still agreed with entry direction")
    elif avg_recent <= 0.0:
        missing.append("recent follow-through was absent; consider fade/exhaustion families")

    if not any(isinstance(row.get("onchain_features"), dict) and row.get("onchain_features") for row in rows):
        missing.append("on-chain context was unavailable; next variants should test on-chain gates when present")
    if not any(isinstance(row.get("daily_news_context"), dict) and row.get("daily_news_context") for row in rows):
        missing.append("news context was unavailable; news-breakout cannot be evaluated fairly in this slice")
    return useful, missing


def _family_report(family: str, rows: list[dict[str, Any]], strategy_debug: dict[str, dict[str, int]]) -> dict[str, Any]:
    pnl_usd = sum(_float(row.get("realized_pnl_usd")) for row in rows)
    pnl_r = sum(_float(row.get("profit_R")) for row in rows)
    win_rate = _win_rate(rows)
    close_reasons = Counter(str(row.get("close_reason") or "unknown") for row in rows)
    sides = Counter(str(row.get("side") or "unknown") for row in rows)
    forced_trades = sum(1 for row in rows if bool(row.get("trade_strategy_forced")))
    risk_tags = Counter(
        str(tag)
        for row in rows
        for tag in (row.get("trade_strategy_risk_tags") or [])
        if str(tag)
    )
    buckets: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _bucket(row):
            buckets[_bucket(row)].append(row)
    bucket_scores = []
    for bid, bucket_rows in buckets.items():
        bucket_scores.append({
            "bucket_id": bid,
            "trades": len(bucket_rows),
            "pnl_R": round(sum(_float(row.get("profit_R")) for row in bucket_rows), 6),
            "win_rate": round(_win_rate(bucket_rows) or 0.0, 6),
        })
    bucket_scores.sort(key=lambda row: (row["pnl_R"], row["trades"]), reverse=True)

    useful, missing = _feature_notes(rows)
    poor_fit: list[str] = []
    if rows and pnl_r <= 0.0:
        poor_fit.append(f"family lost {pnl_r:.2f}R across {len(rows)} practice trades")
    if win_rate is not None and win_rate < 0.45:
        poor_fit.append(f"win rate was weak ({win_rate:.1%})")
    if close_reasons:
        poor_fit.append(f"dominant exits: {', '.join(f'{k}={v}' for k, v in close_reasons.most_common(3))}")

    debug_key = family.upper()
    debug = strategy_debug.get(debug_key) or strategy_debug.get(family) or {}
    skip_notes = [
        f"{key}={value}"
        for key, value in sorted(debug.items(), key=lambda item: int(item[1]), reverse=True)
        if key != "signals"
    ][:4]

    next_families = NEXT_FAMILY_MAP.get(family, ["mean_reversion_chop", "liquidity_squeeze", "news_breakout"])
    handoff = (
        f"{family} saw {len(rows)} trades, pnl_R={pnl_r:.2f}, "
        f"win_rate={'n/a' if win_rate is None else f'{win_rate:.1%}'}. "
        f"Next families should preserve useful features ({'; '.join(useful[:2]) or 'none yet'}) "
        f"and correct gaps ({'; '.join(missing[:2]) or 'none observed'})."
    )
    return {
        "family": family,
        "trades": len(rows),
        "win_rate": round(win_rate, 6) if win_rate is not None else None,
        "pnl_usd": round(pnl_usd, 6),
        "pnl_R": round(pnl_r, 6),
        "avg_R": round(pnl_r / len(rows), 6) if rows else 0.0,
        "side_counts": _top_counter(sides),
        "close_reasons": _top_counter(close_reasons),
        "forced_trades": forced_trades,
        "risk_tags": _top_counter(risk_tags),
        "best_buckets": bucket_scores[:3],
        "worst_buckets": list(reversed(bucket_scores[-3:])),
        "poor_fit_reasons": poor_fit,
        "useful_features": useful,
        "missing_or_misleading_features": missing,
        "skip_diagnostics": skip_notes,
        "next_family_candidates": next_families,
        "handoff_note": handoff,
    }


def _attempt_records(trades: list[dict[str, Any]], family_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        family = _family(trade.get("trade_strategy_id"))
        variant = str(trade.get("trade_strategy_variant_id") or f"{family}__legacy")
        grouped[(family, variant)].append(trade)

    attempts: list[dict[str, Any]] = []
    for (family, variant), rows in sorted(grouped.items()):
        report = family_reports.get(family) or {}
        first = rows[0] if rows else {}
        forced = any(bool(row.get("trade_strategy_forced")) for row in rows)
        risk_tags = sorted({
            str(tag)
            for row in rows
            for tag in (row.get("trade_strategy_risk_tags") or [])
            if str(tag)
        })
        close_reasons = Counter(str(row.get("close_reason") or "unknown") for row in rows)
        pnl_r = sum(_float(row.get("profit_R")) for row in rows)
        win_rate = _win_rate(rows)
        next_family = str((report.get("next_family_candidates") or [""])[0] or "")
        attempts.append({
            "schema": "strategy_attempt_v1",
            "family": family,
            "variant_id": variant,
            "mode": str(first.get("trade_strategy_mode") or first.get("kind") or "practice"),
            "forced_exploration": forced,
            "entry_logic": {
                "side_policy": "follow_pressure" if family in {"vol_breakout", "news_breakout"} else "fade_pressure",
                "required_context": [],
                "risk_tags": risk_tags,
                "allowed_to_trade_bad_bucket": "known_bad_bucket" in risk_tags,
                "source_queue_action": str(first.get("trade_strategy_source_queue_action") or ""),
            },
            "observed_context": {
                "asset": first.get("asset"),
                "venue": first.get("venue"),
                "session": first.get("bucket_session"),
                "side": first.get("side"),
                "regime": first.get("regime") or ((first.get("high_conviction_ticket") or {}).get("regime")),
                "volume_zscore": _float(first.get("volume_zscore")),
                "mean_dipole": _float(first.get("mean_dipole")),
                "recent_bps": _float(first.get("trade_recent_2chunk_bps")),
                "current_bps": _float(first.get("trade_current_chunk_bps")),
                "from_onset_bps": _float(first.get("trade_from_onset_bps")),
            },
            "outcome": {
                "closed_trades": len(rows),
                "pnl_R": round(pnl_r, 6),
                "win_rate": round(win_rate, 6) if win_rate is not None else None,
                "close_reasons": _top_counter(close_reasons),
            },
            "learning": {
                "what_it_saw": list(report.get("useful_features") or []),
                "why_it_failed_or_worked": list(report.get("poor_fit_reasons") or []),
                "features_to_preserve": list(report.get("useful_features") or []),
                "features_to_mutate": list(report.get("missing_or_misleading_features") or []),
                "next_family": next_family,
                "next_variant_hint": str(first.get("trade_strategy_handoff_hint") or report.get("handoff_note") or ""),
            },
        })
    return attempts


def _no_trade_attempt_records(family_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for family, report in sorted(family_reports.items()):
        family = _family(family)
        if int((report or {}).get("trades") or 0) > 0:
            continue
        next_candidates = list((report or {}).get("next_family_candidates") or [])
        next_family = str(next_candidates[0] or "") if next_candidates else ""
        skips = list((report or {}).get("skip_diagnostics") or [])
        attempts.append({
            "schema": "strategy_attempt_v1",
            "family": family,
            "variant_id": f"{family}__no_trade_observed",
            "mode": "practice",
            "forced_exploration": False,
            "entry_logic": {
                "side_policy": "unknown_no_entry",
                "required_context": [],
                "risk_tags": ["no_trade_observed"],
                "allowed_to_trade_bad_bucket": False,
                "source_queue_action": "no_trade_logged_for_strategy_generation",
            },
            "observed_context": {
                "asset": "unknown",
                "venue": "unknown",
                "session": "current_slice",
                "side": "unknown",
                "skip_diagnostics": skips,
            },
            "outcome": {
                "status": "no_trade",
                "closed_trades": 0,
                "pnl_R": 0.0,
                "win_rate": None,
                "close_reasons": {},
                "failure_reason": "family produced no executable trade in this slice",
            },
            "learning": {
                "what_it_saw": [],
                "why_it_failed_or_worked": list((report or {}).get("poor_fit_reasons") or ["no practice trades opened"]),
                "features_to_preserve": list((report or {}).get("useful_features") or []),
                "features_to_mutate": (
                    list((report or {}).get("missing_or_misleading_features") or [])
                    or skips
                    or ["generate a new variant that can explain this no-trade slice"]
                ),
                "next_family": next_family,
                "next_variant_hint": str((report or {}).get("handoff_note") or "Generate a new strategy variant for this no-trade slice."),
            },
        })
    return attempts


def _experiment_from_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    family = _family(attempt.get("family"))
    outcome = attempt.get("outcome") or {}
    learning = attempt.get("learning") or {}
    entry = attempt.get("entry_logic") or {}
    risk_tags = list(entry.get("risk_tags") or [])
    pnl_r = _float(outcome.get("pnl_R"))
    next_family = str(learning.get("next_family") or "")
    outcome_status = str(outcome.get("status") or "")
    action = (
        "refine_winner"
        if pnl_r > 0.0
        else "generate_variant_from_no_trade"
        if outcome_status == "no_trade"
        else "evolve_from_failed_attempt"
    )
    target_family = family if action == "refine_winner" else (next_family or family)
    return {
        "family": target_family,
        "source_family": family,
        "source_variant_id": attempt.get("variant_id"),
        "action": action,
        "priority": "high",
        "force_learning_trade": True,
        "requested_strategy_families": [target_family.upper()],
        "risk_tags_to_watch": risk_tags,
        "mutation_notes": list(learning.get("features_to_mutate") or []) or [str(learning.get("next_variant_hint") or "Mutate from latest attempt.")],
        "success_criteria": {
            "min_closed_trades": 1,
            "profit_R_floor": 0.0,
            "must_record_attempt_json": True,
            "zero_trade_slices_must_generate_variant": outcome_status == "no_trade",
        },
        "handoff_targets": [x for x in [next_family] if x],
    }


def build_refrag_relay(
    trades: list[dict[str, Any]],
    *,
    strategy_debug: dict[str, dict[str, int]] | None = None,
    ranked_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    strategy_debug = strategy_debug or {}
    by_family: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_family[_family(trade.get("trade_strategy_id"))].append(trade)

    family_reports = {
        family: _family_report(family, rows, strategy_debug)
        for family, rows in sorted(by_family.items())
    }
    for sid, counters in strategy_debug.items():
        family = _family(sid)
        if family not in family_reports:
            skips = [
                f"{key}={value}"
                for key, value in sorted(counters.items(), key=lambda item: int(item[1]), reverse=True)
                if key != "signals"
            ][:4]
            family_reports[family] = {
                "family": family,
                "trades": 0,
                "win_rate": None,
                "pnl_usd": 0.0,
                "pnl_R": 0.0,
                "avg_R": 0.0,
                "side_counts": {},
                "close_reasons": {},
                "best_buckets": [],
                "worst_buckets": [],
                "poor_fit_reasons": ["no practice trades opened"],
                "useful_features": [],
                "missing_or_misleading_features": ["strategy conditions did not match enough replay contexts"],
                "skip_diagnostics": skips,
                "next_family_candidates": NEXT_FAMILY_MAP.get(family, ["mean_reversion_chop", "liquidity_squeeze", "news_breakout"]),
                "handoff_note": f"{family} opened no trades. Next family should inspect skip diagnostics: {', '.join(skips) or 'none'}.",
            }

    handoffs: list[dict[str, Any]] = []
    for family, report in family_reports.items():
        for target in report.get("next_family_candidates") or []:
            handoffs.append({
                "from_family": family,
                "to_family": target,
                "message": report.get("handoff_note") or "",
                "must_fix": list(report.get("missing_or_misleading_features") or [])[:4],
                "preserve": list(report.get("useful_features") or [])[:4],
            })

    strategy_attempts = _attempt_records(trades, family_reports)
    strategy_attempts.extend(_no_trade_attempt_records(family_reports))

    evolution_queue = [
        item
        for family, report in sorted(family_reports.items())
        for item in [_queue_item(family, report)]
        if item is not None
    ]
    candidate_experiments = [_experiment_from_attempt(attempt) for attempt in strategy_attempts]

    top_rules = []
    for row in (ranked_rules or [])[:5]:
        top_rules.append({
            "rule": row.get("rule"),
            "verdict": ((row.get("self_audit") or {}).get("verdict")),
            "warnings": list((row.get("self_audit") or {}).get("warnings") or []),
            "holdout_pnl": ((row.get("holdout") or {}).get("pnl_kept")),
            "holdout_kept": ((row.get("holdout") or {}).get("n_kept")),
        })

    return {
        "schema": "refrag_strategy_relay_v1",
        "purpose": "Pass family fit diagnostics forward so later strategy candidates evolve instead of starting from scratch.",
        "trade_count": len(trades),
        "family_reports": family_reports,
        "strategy_attempts": strategy_attempts,
        "handoffs": handoffs,
        "evolution_queue": evolution_queue,
        "candidate_experiments": candidate_experiments,
        "top_autoresearch_rules": top_rules,
    }
