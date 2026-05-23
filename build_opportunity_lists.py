from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EVOLUTION_DIR = Path("research") / "strategy_evolution"


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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _setup_signature(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": row.get("context") or "",
        "strategy_id": row.get("strategy_id") or row.get("callable_strategy_id") or "",
        "side": row.get("side") or "",
        "bucket_session": row.get("bucket_session") or "",
        "replay_offset_hours": row.get("replay_offset_hours"),
        "trade_present_score": row.get("trade_present_score"),
        "trade_stage": row.get("trade_stage") or "",
        "trade_option_state": row.get("trade_option_state") or "",
        "pressure_watch_state": row.get("pressure_watch_state") or "",
        "trade_current_chunk_bps": row.get("trade_current_chunk_bps"),
        "trade_recent_2chunk_bps": row.get("trade_recent_2chunk_bps"),
        "trade_from_onset_bps": row.get("trade_from_onset_bps"),
        "mean_dipole": row.get("mean_dipole"),
        "dipole_acl1": row.get("dipole_acl1"),
        "volume_zscore": row.get("volume_zscore"),
        "trade_strategy_confidence": row.get("trade_strategy_confidence"),
        "risk_tags": list(row.get("trade_strategy_risk_tags") or []),
    }


def _tradable_from_ledger(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id") or "",
        "source": "opportunity_ledger",
        "action": "trade_when_live_setup_matches_this_winner",
        "context": row.get("context") or "",
        "bucket_id": row.get("bucket_id") or "",
        "strategy_id": row.get("strategy_id") or "",
        "variant_id": row.get("variant_id") or "",
        "exit_strategy_id": row.get("exit_strategy_id") or "",
        "performance": {
            "pnl_R": _float(row.get("pnl_R")),
            "pnl_usd": _float(row.get("pnl_usd")),
            "gross_pnl_usd": _float(row.get("gross_pnl_usd")),
            "fees_usd": _float(row.get("fees_usd")),
            "close_reason": row.get("close_reason") or "",
        },
        "setup": _setup_signature(row),
        "provenance": {
            "window": row.get("window") or "",
            "cadence": row.get("cadence") or "",
            "run_dir": row.get("run_dir") or "",
            "account": row.get("account") or "",
            "index": row.get("index"),
            "actual_execution": bool(row.get("actual_execution")),
        },
    }


def _negative_from_ledger(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id") or "",
        "source": "opportunity_ledger",
        "action": "negative_evidence_for_mutation_not_an_opportunity",
        "context": row.get("context") or "",
        "bucket_id": row.get("bucket_id") or "",
        "strategy_id": row.get("strategy_id") or "",
        "performance": {
            "pnl_R": _float(row.get("pnl_R")),
            "pnl_usd": _float(row.get("pnl_usd")),
            "close_reason": row.get("close_reason") or "",
        },
        "setup": _setup_signature(row),
        "provenance": {
            "window": row.get("window") or "",
            "cadence": row.get("cadence") or "",
            "run_dir": row.get("run_dir") or "",
            "account": row.get("account") or "",
            "index": row.get("index"),
        },
    }


def _resolver_opportunities(routing: dict[str, Any], existing_winner_ids: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, route in sorted((routing.get("routes") or {}).items()):
        evidence = dict(route.get("resolver_evidence") or {})
        if not evidence:
            continue
        pnl_r = _float(route.get("pnl_R"))
        if pnl_r <= 0.0:
            continue
        context = "|".join([
            str(route.get("asset") or "").upper(),
            str(route.get("venue") or "").lower(),
            str(route.get("side") or "").lower(),
            str(route.get("session") or "").lower(),
        ])
        resolver_id = f"resolver|{key}|{evidence.get('entry_ts_utc') or ''}"
        if resolver_id in existing_winner_ids:
            continue
        out.append({
            "id": resolver_id,
            "source": "exact_context_resolver",
            "action": "trade_when_live_setup_matches_this_resolver_winner",
            "context": context,
            "bucket_id": route.get("bucket_id") or key,
            "strategy_id": route.get("callable_strategy_id") or str(route.get("family") or "").upper(),
            "variant_id": "exact_context_resolver",
            "exit_strategy_id": "",
            "performance": {
                "pnl_R": pnl_r,
                "pnl_usd": _float(evidence.get("pnl_usd")),
                "gross_pnl_usd": _float(evidence.get("pnl_usd")),
                "fees_usd": 0.0,
                "close_reason": "resolver_positive_entry",
            },
            "setup": {
                "context": context,
                "strategy_id": route.get("callable_strategy_id") or str(route.get("family") or "").upper(),
                "side": route.get("side") or "",
                "bucket_session": route.get("session") or "",
                "entry_hour_in_series": evidence.get("entry_hour_in_series"),
                "exit_hour_in_series": evidence.get("exit_hour_in_series"),
                "entry_price": evidence.get("entry_price"),
                "exit_price": evidence.get("exit_price"),
                "net_bps": evidence.get("net_bps"),
                "stop_bps": evidence.get("stop_bps"),
                "hold_minutes": evidence.get("hold_minutes"),
                "resolver_policy": evidence.get("policy") or "",
            },
            "provenance": {
                "window": "resolver",
                "cadence": "series_relative_scan",
                "run_dir": "research/strategy_evolution/_routing.json",
                "actual_execution": False,
            },
        })
    return out


def _context_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"tradable_opportunities": 0, "best_pnl_R": 0.0, "strategies": []}
    best = max(rows, key=lambda row: _float((row.get("performance") or {}).get("pnl_R")))
    strategies = sorted({str(row.get("strategy_id") or "") for row in rows if str(row.get("strategy_id") or "")})
    return {
        "tradable_opportunities": len(rows),
        "best_pnl_R": round(_float((best.get("performance") or {}).get("pnl_R")), 6),
        "best_strategy": best.get("strategy_id") or "",
        "strategies": strategies,
    }


def _avg(rows: list[dict[str, Any]], getter) -> float:
    if not rows:
        return 0.0
    return sum(_float(getter(row)) for row in rows) / len(rows)


def _negative_rule_key(row: dict[str, Any]) -> str:
    setup = row.get("setup") or {}
    perf = row.get("performance") or {}
    context = str(row.get("context") or "")
    strategy = str(row.get("strategy_id") or "")
    close_reason = str(perf.get("close_reason") or "unknown")
    stage = str(setup.get("trade_stage") or "unknown")
    state = str(setup.get("trade_option_state") or "unknown")
    pressure = str(setup.get("pressure_watch_state") or "unknown")
    return "|".join([context, strategy, close_reason, stage, state, pressure])


def _negative_rule(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0] if rows else {}
    setup = first.get("setup") or {}
    perf = first.get("performance") or {}
    worst = min(rows, key=lambda row: _float((row.get("performance") or {}).get("pnl_R"))) if rows else {}
    risk_tags = sorted({
        str(tag)
        for row in rows
        for tag in ((row.get("setup") or {}).get("risk_tags") or [])
        if str(tag)
    })
    return {
        "rule_id": _negative_rule_key(first),
        "action": "block_or_mutate_matching_setup",
        "context": first.get("context") or "",
        "strategy_id": first.get("strategy_id") or "",
        "close_reason": perf.get("close_reason") or "",
        "trade_stage": setup.get("trade_stage") or "",
        "trade_option_state": setup.get("trade_option_state") or "",
        "pressure_watch_state": setup.get("pressure_watch_state") or "",
        "matches": len(rows),
        "total_pnl_R": round(sum(_float((row.get("performance") or {}).get("pnl_R")) for row in rows), 6),
        "total_pnl_usd": round(sum(_float((row.get("performance") or {}).get("pnl_usd")) for row in rows), 6),
        "avg_pnl_R": round(_avg(rows, lambda row: (row.get("performance") or {}).get("pnl_R")), 6),
        "worst_pnl_R": round(_float((worst.get("performance") or {}).get("pnl_R")), 6),
        "avg_trade_present_score": round(_avg(rows, lambda row: (row.get("setup") or {}).get("trade_present_score")), 3),
        "avg_current_chunk_bps": round(_avg(rows, lambda row: (row.get("setup") or {}).get("trade_current_chunk_bps")), 6),
        "avg_recent_2chunk_bps": round(_avg(rows, lambda row: (row.get("setup") or {}).get("trade_recent_2chunk_bps")), 6),
        "avg_from_onset_bps": round(_avg(rows, lambda row: (row.get("setup") or {}).get("trade_from_onset_bps")), 6),
        "avg_mean_dipole": round(_avg(rows, lambda row: (row.get("setup") or {}).get("mean_dipole")), 6),
        "avg_volume_zscore": round(_avg(rows, lambda row: (row.get("setup") or {}).get("volume_zscore")), 6),
        "risk_tags": risk_tags,
        "example_ids": [str(row.get("id") or "") for row in rows[:5]],
    }


def _negative_context_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"negative_evidence_rows": 0, "total_pnl_R": 0.0}
    strategies = sorted({str(row.get("strategy_id") or "") for row in rows if str(row.get("strategy_id") or "")})
    close_reasons = defaultdict(int)
    for row in rows:
        close_reasons[str((row.get("performance") or {}).get("close_reason") or "unknown")] += 1
    worst = min(rows, key=lambda row: _float((row.get("performance") or {}).get("pnl_R")))
    return {
        "negative_evidence_rows": len(rows),
        "total_pnl_R": round(sum(_float((row.get("performance") or {}).get("pnl_R")) for row in rows), 6),
        "avg_pnl_R": round(_avg(rows, lambda row: (row.get("performance") or {}).get("pnl_R")), 6),
        "worst_pnl_R": round(_float((worst.get("performance") or {}).get("pnl_R")), 6),
        "worst_strategy": worst.get("strategy_id") or "",
        "strategies": strategies,
        "top_close_reasons": dict(sorted(close_reasons.items(), key=lambda item: item[1], reverse=True)[:5]),
    }


def _mutation_side(side: str, close_reason: str) -> str:
    side = str(side or "").lower()
    close_reason = str(close_reason or "").lower()
    if close_reason in {"pressure_flipped", "stop_loss"}:
        return "sell" if side == "buy" else "buy" if side == "sell" else side
    return side


def _mutation_family(strategy_id: str, close_reason: str) -> str:
    sid = str(strategy_id or "").upper()
    close_reason = str(close_reason or "").lower()
    if close_reason == "pressure_flipped":
        if sid in {"MEAN_REVERSION_CHOP", "LIQUIDITY_SQUEEZE"}:
            return "VOL_BREAKOUT"
        return "MEAN_REVERSION_CHOP"
    if close_reason == "stop_loss":
        if sid in {"VOL_BREAKOUT", "NEWS_BREAKOUT"}:
            return "LIQUIDITY_SQUEEZE"
        return "RELATIVE_STRENGTH"
    if close_reason.startswith("news_"):
        return "NEWS_BREAKOUT"
    return sid or "MEAN_REVERSION_CHOP"


def _mutation_rule_from_negative_rule(rule: dict[str, Any]) -> dict[str, Any]:
    side = ""
    context_parts = str(rule.get("context") or "").split("|")
    if len(context_parts) == 4:
        side = context_parts[2]
        mutated_context = "|".join([context_parts[0], context_parts[1], _mutation_side(side, rule.get("close_reason")), context_parts[3]])
    else:
        mutated_context = str(rule.get("context") or "")
    close_reason = str(rule.get("close_reason") or "")
    source_strategy = str(rule.get("strategy_id") or "")
    mutated_strategy = _mutation_family(source_strategy, close_reason)
    action = "test_mutated_opportunity_before_trading_live"
    if close_reason == "pressure_flipped":
        mutation = "flip_side_or_wait_for_flip_confirmation"
    elif close_reason == "stop_loss":
        mutation = "switch_family_or_delay_entry_until_extension_exhausts"
    elif close_reason.startswith("news_"):
        mutation = "require_news_alignment_or_switch_to_news_breakout"
    elif close_reason in {"present_score_degraded", "present_score_dropped_from_entry"}:
        mutation = "delay_entry_until_score_recovers_or_skip"
    else:
        mutation = "tighten_context_and_retest"
    return {
        "source_rule_id": rule.get("rule_id") or "",
        "action": action,
        "mutation": mutation,
        "source_context": rule.get("context") or "",
        "candidate_context": mutated_context,
        "source_strategy_id": source_strategy,
        "candidate_strategy_id": mutated_strategy,
        "source_close_reason": close_reason,
        "evidence_matches": int(rule.get("matches") or 0),
        "source_total_pnl_R": _float(rule.get("total_pnl_R")),
        "source_avg_pnl_R": _float(rule.get("avg_pnl_R")),
        "source_worst_pnl_R": _float(rule.get("worst_pnl_R")),
        "success_criteria": {
            "must_promote_positive_pnl_R": True,
            "min_trades": 1,
            "unresolved_opportunities_allowed": False,
        },
        "constraints": {
            "do_not_trade_live_until_positive": True,
            "do_not_increase_trade_count_for_volume": True,
            "use_as_quality_search_not_trade_backlog": True,
        },
    }


def _write_negative_evidence_memory(
    *,
    negative: list[dict[str, Any]],
    output_dir: Path,
    source_ledger: Path,
) -> tuple[Path, Path]:
    grouped_rules: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_context: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in negative:
        grouped_rules[_negative_rule_key(row)].append(row)
        by_context[str(row.get("context") or "")].append(row)
        by_strategy[str(row.get("strategy_id") or "")].append(row)
    negative_rules = [_negative_rule(rows) for rows in grouped_rules.values()]
    negative_rules.sort(key=lambda row: (int(row.get("matches") or 0), -_float(row.get("avg_pnl_R"))), reverse=True)
    negative_sorted = sorted(
        negative,
        key=lambda row: (
            _float((row.get("performance") or {}).get("pnl_R")),
            _float((row.get("performance") or {}).get("pnl_usd")),
        ),
    )
    payload = {
        "schema": "strategy_negative_evidence_memory_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_ledger": str(source_ledger),
        "policy": {
            "trade_unit": "individual_opportunity",
            "action": "block_or_mutate_matching_setups_before_live_trading",
            "no_unresolved_trade_opportunities": True,
            "classification": "nonpositive evidence rows are negative evidence, not opportunities and not a backlog list",
        },
        "counts": {
            "negative_evidence_rows": len(negative),
            "negative_evidence_rules": len(negative_rules),
            "unresolved_opportunities": 0,
        },
        "by_context": {key: _negative_context_summary(rows) for key, rows in sorted(by_context.items()) if key},
        "by_strategy": {key: _negative_context_summary(rows) for key, rows in sorted(by_strategy.items()) if key},
        "negative_evidence_rules": negative_rules,
        "worst_negative_evidence": negative_sorted[:100],
        "unresolved_opportunities": [],
    }
    json_path = output_dir / "_negative_evidence_memory.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Negative Evidence Memory",
        "",
        f"Created: {payload['created_at']}",
        "",
        f"- Negative evidence rows: {payload['counts']['negative_evidence_rows']}",
        f"- Negative evidence rules: {payload['counts']['negative_evidence_rules']}",
        f"- Unresolved opportunities: {payload['counts']['unresolved_opportunities']}",
        "",
        "## Largest Blocking/Mutation Rules",
        "",
        "| # | Context | Strategy | Close | Stage | State | Matches | Avg R | Total R | Worst R |",
        "|---:|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(negative_rules[:40], start=1):
        lines.append(
            f"| {idx} | `{row.get('context') or ''}` | `{row.get('strategy_id') or ''}` | "
            f"`{row.get('close_reason') or ''}` | `{row.get('trade_stage') or ''}` | "
            f"`{row.get('trade_option_state') or ''}/{row.get('pressure_watch_state') or ''}` | "
            f"{int(row.get('matches') or 0)} | {_float(row.get('avg_pnl_R')):+.2f} | "
            f"{_float(row.get('total_pnl_R')):+.2f} | {_float(row.get('worst_pnl_R')):+.2f} |"
        )
    lines.extend([
        "",
        "## By Context",
        "",
        "| Context | Evidence rows | Avg R | Total R | Worst R | Worst strategy | Top close reasons |",
        "|---|---:|---:|---:|---:|---|---|",
    ])
    for context, row in sorted(payload["by_context"].items(), key=lambda item: item[1]["negative_evidence_rows"], reverse=True):
        reasons = ", ".join(f"{k}={v}" for k, v in (row.get("top_close_reasons") or {}).items())
        lines.append(
            f"| `{context}` | {int(row.get('negative_evidence_rows') or 0)} | "
            f"{_float(row.get('avg_pnl_R')):+.2f} | {_float(row.get('total_pnl_R')):+.2f} | "
            f"{_float(row.get('worst_pnl_R')):+.2f} | `{row.get('worst_strategy') or ''}` | {reasons} |"
        )
    lines.extend([
        "",
        "## Worst Individual Negative Evidence",
        "",
        "| # | Context | Strategy | Close | Replay hr | PnL R | PnL USD |",
        "|---:|---|---|---|---:|---:|---:|",
    ])
    for idx, row in enumerate(negative_sorted[:40], start=1):
        setup = row.get("setup") or {}
        perf = row.get("performance") or {}
        lines.append(
            f"| {idx} | `{row.get('context') or ''}` | `{row.get('strategy_id') or ''}` | "
            f"`{perf.get('close_reason') or ''}` | {_float(setup.get('replay_offset_hours')):.2f} | "
            f"{_float(perf.get('pnl_R')):+.2f} | ${_float(perf.get('pnl_usd')):+.2f} |"
        )
    md_path = output_dir / "_negative_evidence_memory.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def _write_mutation_workbench(
    *,
    negative_memory: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    rules = list(negative_memory.get("negative_evidence_rules") or [])
    # Use the strongest repeated failures first; this is a quality queue, not a demand to trade more.
    selected = [
        rule
        for rule in rules
        if int(rule.get("matches") or 0) >= 2
    ]
    candidates = [_mutation_rule_from_negative_rule(rule) for rule in selected]
    candidates.sort(
        key=lambda row: (
            int(row.get("evidence_matches") or 0),
            abs(_float(row.get("source_total_pnl_R"))),
            abs(_float(row.get("source_avg_pnl_R"))),
        ),
        reverse=True,
    )
    payload = {
        "schema": "strategy_opportunity_mutation_workbench_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_negative_memory": str(output_dir / "_negative_evidence_memory.json"),
        "policy": {
            "purpose": "Use negative evidence to create better candidate trade opportunities, not to increase trade volume.",
            "trade_unit": "individual_opportunity",
            "unresolved_opportunities": 0,
            "live_trading_rule": "mutation candidates are not tradable until a positive replay/resolver result promotes them",
        },
        "counts": {
            "mutation_candidates": len(candidates),
            "unresolved_opportunities": 0,
        },
        "mutation_candidates": candidates,
        "unresolved_opportunities": [],
    }
    json_path = output_dir / "_opportunity_mutation_workbench.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# Opportunity Mutation Workbench",
        "",
        f"Created: {payload['created_at']}",
        "",
        f"- Mutation candidates: {payload['counts']['mutation_candidates']}",
        f"- Unresolved opportunities: {payload['counts']['unresolved_opportunities']}",
        "",
        "These candidates are not live trades. They are negative-evidence mutations that must earn promotion through positive replay/resolver evidence.",
        "",
        "| # | Source context | Candidate context | Source strategy | Candidate strategy | Mutation | Matches | Source total R |",
        "|---:|---|---|---|---|---|---:|---:|",
    ]
    for idx, row in enumerate(candidates[:80], start=1):
        lines.append(
            f"| {idx} | `{row.get('source_context') or ''}` | `{row.get('candidate_context') or ''}` | "
            f"`{row.get('source_strategy_id') or ''}` | `{row.get('candidate_strategy_id') or ''}` | "
            f"`{row.get('mutation') or ''}` | {int(row.get('evidence_matches') or 0)} | "
            f"{_float(row.get('source_total_pnl_R')):+.2f} |"
        )
    md_path = output_dir / "_opportunity_mutation_workbench.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path



def build_opportunity_lists(ledger_path: Path, routing_path: Path, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = _load_json(ledger_path)
    routing = _load_json(routing_path)
    raw = list(ledger.get("opportunities") or [])
    tradable = [
        _tradable_from_ledger(row)
        for row in raw
        if _float(row.get("pnl_R")) > 0.0
    ]
    negative = [
        _negative_from_ledger(row)
        for row in raw
        if _float(row.get("pnl_R")) <= 0.0
    ]
    existing_ids = {str(row.get("id") or "") for row in tradable}
    tradable.extend(_resolver_opportunities(routing, existing_ids))
    tradable.sort(
        key=lambda row: (
            _float((row.get("performance") or {}).get("pnl_R")),
            _float((row.get("performance") or {}).get("pnl_usd")),
        ),
        reverse=True,
    )

    by_context: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in tradable:
        by_context[str(row.get("context") or "")].append(row)

    negative_json_path, negative_md_path = _write_negative_evidence_memory(
        negative=negative,
        output_dir=output_dir,
        source_ledger=ledger_path,
    )
    negative_memory = _load_json(negative_json_path)
    mutation_json_path, mutation_md_path = _write_mutation_workbench(
        negative_memory=negative_memory,
        output_dir=output_dir,
    )

    resolver_count = sum(1 for row in tradable if row.get("source") == "exact_context_resolver")
    payload = {
        "schema": "strategy_opportunity_lists_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_ledger": str(ledger_path),
        "source_routing": str(routing_path),
        "policy": {
            "trade_unit": "individual_opportunity",
            "context_role": "permission_and_family_filter_only",
            "no_unresolved_trade_opportunities": True,
            "classification": {
                "tradable_opportunities": "positive-PnL evidence rows and resolver-mined positive entry rows",
                "negative_evidence": "nonpositive evidence rows; block/mutate but do not carry as opportunities",
                "unresolved_opportunities": "must stay empty; new evidence is immediately classified tradable or negative evidence",
            },
            "supplemental_tradable_sources": ["exact_context_resolver"],
        },
        "tradable_opportunity_count": len(tradable),
        "unresolved_opportunity_count": 0,
        "ledger_opportunities": len(raw),
        "resolver_tradable_opportunities": resolver_count,
        "counts": {
            "tradable_opportunities": len(tradable),
            "unresolved_opportunities": 0,
            "ledger_opportunities": len(raw),
            "resolver_tradable_opportunities": resolver_count,
        },
        "by_context": {key: _context_summary(rows) for key, rows in sorted(by_context.items()) if key},
        "tradable_opportunities": tradable,
        "negative_evidence_memory": str(output_dir / "_negative_evidence_memory.json"),
        "opportunity_mutation_workbench": str(output_dir / "_opportunity_mutation_workbench.json"),
        "unresolved_opportunities": [],
    }
    json_path = output_dir / "_opportunity_lists.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Opportunity Lists",
        "",
        f"Created: {payload['created_at']}",
        "",
        f"- Tradable opportunities: {payload['counts']['tradable_opportunities']}",
        f"- Unresolved opportunities: {payload['counts']['unresolved_opportunities']}",
        f"- Resolver tradable opportunities: {payload['counts']['resolver_tradable_opportunities']}",
        f"- Negative evidence memory: `{payload['negative_evidence_memory']}`",
        f"- Opportunity mutation workbench: `{payload['opportunity_mutation_workbench']}`",
        "",
        "## Top Tradable",
        "",
        "| # | Context | Strategy | Source | PnL R | PnL USD | Replay hr |",
        "|---:|---|---|---|---:|---:|---:|",
    ]
    for idx, row in enumerate(tradable[:30], start=1):
        perf = row.get("performance") or {}
        setup = row.get("setup") or {}
        replay_hr = setup.get("replay_offset_hours", setup.get("entry_hour_in_series", ""))
        replay_text = f"{_float(replay_hr):.2f}" if replay_hr != "" and replay_hr is not None else ""
        lines.append(
            f"| {idx} | `{row.get('context') or ''}` | `{row.get('strategy_id') or ''}` | `{row.get('source') or ''}` | "
            f"{_float(perf.get('pnl_R')):+.2f} | ${_float(perf.get('pnl_usd')):+.2f} | {replay_text} |"
        )
    lines.extend([
        "",
        "## By Context",
        "",
        "| Context | Tradable | Best R | Best strategy | Strategies |",
        "|---|---:|---:|---|---|",
    ])
    for context, row in sorted(payload["by_context"].items()):
        lines.append(
            f"| `{context}` | {row['tradable_opportunities']} | {row['best_pnl_R']:+.2f} | "
            f"`{row.get('best_strategy') or ''}` | `{', '.join(row.get('strategies') or [])}` |"
        )
    md_path = output_dir / "_opportunity_lists.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {negative_json_path}")
    print(f"wrote {negative_md_path}")
    print(f"wrote {mutation_json_path}")
    print(f"wrote {mutation_md_path}")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tradable opportunity lists and negative evidence memory.")
    parser.add_argument(
        "--ledger",
        default=str(DEFAULT_EVOLUTION_DIR / "opportunity_ledger_h0_h12_loose_and_dense.json"),
    )
    parser.add_argument("--routing", default=str(DEFAULT_EVOLUTION_DIR / "_routing.json"))
    parser.add_argument("--output-dir", default=str(DEFAULT_EVOLUTION_DIR))
    args = parser.parse_args()
    json_path, md_path = build_opportunity_lists(Path(args.ledger), Path(args.routing), Path(args.output_dir))
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
