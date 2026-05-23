from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Any

from strategy_refrag_relay import build_refrag_relay
from strategy_family_evolution import write_evolved_family_jsons


@dataclass
class CandidateRule:
    name: str
    description: str
    predicate: Callable[[dict[str, Any]], bool]


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return default


def _load_closed_trades(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for scenario_id, account in (obj.get("accounts") or {}).items():
        for trade in account.get("trades") or []:
            if trade.get("status") != "closed":
                continue
            row = dict(trade)
            row["scenario_id"] = scenario_id
            rows.append(row)
    rows.sort(key=lambda r: float(r.get("ts_utc") or 0.0))
    return rows


def _load_replay_payload(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _score(rows: list[dict[str, Any]], rule: CandidateRule) -> dict[str, Any]:
    kept = [r for r in rows if rule.predicate(r)]
    removed = [r for r in rows if not rule.predicate(r)]
    pnl_all = sum(_num(r, "realized_pnl_usd") for r in rows)
    pnl_kept = sum(_num(r, "realized_pnl_usd") for r in kept)
    pnl_removed = sum(_num(r, "realized_pnl_usd") for r in removed)
    wins = sum(1 for r in kept if _num(r, "realized_pnl_usd") > 0)
    return {
        "n_all": len(rows),
        "n_kept": len(kept),
        "n_removed": len(removed),
        "kept_fraction": round(len(kept) / len(rows), 4) if rows else 0.0,
        "pnl_all": round(pnl_all, 4),
        "pnl_kept": round(pnl_kept, 4),
        "pnl_removed": round(pnl_removed, 4),
        "pnl_improvement_vs_all": round(pnl_kept - pnl_all, 4),
        "win_rate_kept": round(wins / len(kept), 4) if kept else None,
        "avg_pnl_kept": round(pnl_kept / len(kept), 4) if kept else None,
    }


def _self_audit(train: dict[str, Any], test: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    verdict = "keep"
    if train["n_kept"] < 4:
        warnings.append("low train coverage")
    if test["n_kept"] < 4:
        warnings.append("low holdout coverage")
    if train["kept_fraction"] < 0.20 or test["kept_fraction"] < 0.20:
        warnings.append("rule removes most trades")
    if train["pnl_improvement_vs_all"] > 0 and test["pnl_improvement_vs_all"] <= 0:
        warnings.append("train improvement failed holdout")
    if test["pnl_kept"] < 0:
        warnings.append("holdout remains negative")
    if warnings:
        verdict = "review"
    if "train improvement failed holdout" in warnings:
        verdict = "discard"
    return {
        "verdict": verdict,
        "warnings": warnings,
    }


def _candidate_rules() -> list[CandidateRule]:
    rules: list[CandidateRule] = [
        CandidateRule("baseline_no_filter", "Keep all current trades", lambda r: True),
    ]
    for threshold in (60, 65, 68, 70, 72):
        rules.append(CandidateRule(
            f"present_score_ge_{threshold}",
            f"Require entry present score >= {threshold}",
            lambda r, threshold=threshold: _num(r, "trade_present_score") >= threshold,
        ))
    for threshold in (0.70, 0.75, 0.80, 0.85):
        rules.append(CandidateRule(
            f"strategy_confidence_ge_{threshold:.2f}",
            f"Require strategy confidence >= {threshold:.2f}",
            lambda r, threshold=threshold: _num(r, "trade_strategy_confidence") >= threshold,
        ))
    for threshold in (0.0, 1.0, 2.0, 4.0):
        rules.append(CandidateRule(
            f"current_chunk_bps_gt_{threshold:g}",
            f"Require current chunk movement in trade direction > {threshold:g} bps",
            lambda r, threshold=threshold: _num(r, "trade_current_chunk_bps") > threshold,
        ))
        rules.append(CandidateRule(
            f"recent_2chunk_bps_gt_{threshold:g}",
            f"Require recent 2-chunk movement in trade direction > {threshold:g} bps",
            lambda r, threshold=threshold: _num(r, "trade_recent_2chunk_bps") > threshold,
        ))
    for threshold in (0.0, 2.0, 5.0, 8.0):
        rules.append(CandidateRule(
            f"from_onset_bps_ge_{threshold:g}",
            f"Require move from setup onset in trade direction >= {threshold:g} bps",
            lambda r, threshold=threshold: _num(r, "trade_from_onset_bps") >= threshold,
        ))
    rules.extend([
        CandidateRule(
            "fresh_onset_only",
            "Require pressure-continuation entries to be onset only",
            lambda r: str(r.get("trade_stage") or "") == "onset",
        ),
        CandidateRule(
            "positive_current_and_recent",
            "Require current chunk and recent 2-chunk movement to both agree with the trade",
            lambda r: _num(r, "trade_current_chunk_bps") > 0 and _num(r, "trade_recent_2chunk_bps") > 0,
        ),
        CandidateRule(
            "positive_from_onset_and_recent",
            "Require from-onset and recent 2-chunk movement to both agree with the trade",
            lambda r: _num(r, "trade_from_onset_bps") >= 0 and _num(r, "trade_recent_2chunk_bps") > 0,
        ),
        CandidateRule(
            "score68_positive_recent",
            "Require score >= 68 and recent 2-chunk movement in trade direction",
            lambda r: _num(r, "trade_present_score") >= 68 and _num(r, "trade_recent_2chunk_bps") > 0,
        ),
        CandidateRule(
            "score70_or_positive_recent",
            "Allow score >= 70, otherwise require recent 2-chunk movement in trade direction",
            lambda r: _num(r, "trade_present_score") >= 70 or _num(r, "trade_recent_2chunk_bps") > 0,
        ),
    ])
    return rules


def _strategy_allowed(strategy_id: str, strategies: set[str]) -> bool:
    sid = str(strategy_id or "").upper()
    return not strategies or sid in strategies


def run_autoresearch(path: Path, train_frac: float = 0.60, strategies: set[str] | None = None) -> dict[str, Any]:
    if strategies is None:
        strategies = set()
    replay_payload = _load_replay_payload(path)
    trades = [
        r for r in _load_closed_trades(path)
        if _strategy_allowed(str(r.get("trade_strategy_id") or ""), strategies)
    ]
    cut = max(1, min(len(trades) - 1, int(len(trades) * train_frac))) if len(trades) >= 2 else len(trades)
    train = trades[:cut]
    test = trades[cut:]
    results = []
    for rule in _candidate_rules():
        train_score = _score(train, rule)
        test_score = _score(test, rule)
        audit = _self_audit(train_score, test_score)
        results.append({
            "rule": rule.name,
            "description": rule.description,
            "train": train_score,
            "holdout": test_score,
            "self_audit": audit,
        })
    results.sort(
        key=lambda r: (
            r["self_audit"]["verdict"] == "keep",
            r["holdout"]["pnl_improvement_vs_all"],
            r["train"]["pnl_improvement_vs_all"],
            r["holdout"]["n_kept"],
        ),
        reverse=True,
    )
    baseline = next(r for r in results if r["rule"] == "baseline_no_filter")
    relay = build_refrag_relay(trades, ranked_rules=results)
    if not trades and replay_payload.get("refrag_relay"):
        relay = dict(replay_payload.get("refrag_relay") or {})
        relay["top_autoresearch_rules"] = [
            {
                "rule": row.get("rule"),
                "verdict": ((row.get("self_audit") or {}).get("verdict")),
                "warnings": list((row.get("self_audit") or {}).get("warnings") or []),
                "holdout_pnl": ((row.get("holdout") or {}).get("pnl_kept")),
                "holdout_kept": ((row.get("holdout") or {}).get("n_kept")),
            }
            for row in results[:5]
        ]
    return {
        "source": str(path),
        "strategy": ",".join(sorted(strategies)) if strategies else "ALL",
        "n_trades": len(trades),
        "train_n": len(train),
        "holdout_n": len(test),
        "baseline": baseline,
        "ranked_rules": results,
        "refrag_relay": relay,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--replay-results", required=True)
    p.add_argument("--output-path", default="market_strategy_autoresearch_results.json")
    p.add_argument("--train-frac", type=float, default=0.60)
    p.add_argument(
        "--strategies",
        default="ALL",
        help="Comma-separated strategy ids to include, or ALL.",
    )
    args = p.parse_args()

    raw_strategies = {s.strip().upper() for s in args.strategies.split(",") if s.strip()}
    strategies = set() if "ALL" in raw_strategies else raw_strategies
    payload = run_autoresearch(Path(args.replay_results), train_frac=args.train_frac, strategies=strategies)
    out = Path(args.output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload["strategy_family_evolution"] = write_evolved_family_jsons(
        payload.get("refrag_relay") or {},
        run_dir=out.parent,
        source=str(out),
        run_id=out.stem,
    )
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"wrote {out}")
    print(f"strategy={payload['strategy']} n={payload['n_trades']} train={payload['train_n']} holdout={payload['holdout_n']}")
    print("top rules:")
    for row in payload["ranked_rules"][:8]:
        print(
            f"  {row['rule']:<32} verdict={row['self_audit']['verdict']:<7} "
            f"train_improve={row['train']['pnl_improvement_vs_all']:+.2f} "
            f"holdout_improve={row['holdout']['pnl_improvement_vs_all']:+.2f} "
            f"holdout_pnl={row['holdout']['pnl_kept']:+.2f} "
            f"kept={row['holdout']['n_kept']}/{row['holdout']['n_all']} "
            f"warnings={','.join(row['self_audit']['warnings']) or 'none'}"
        )


if __name__ == "__main__":
    main()
