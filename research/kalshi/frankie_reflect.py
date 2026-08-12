"""Scheduled reflection over resolved Frankie evidence.

This module discovers immutable decision envelopes with immutable outcome sidecars and asks
Frankie's bounded improvement pipeline for at most one proposal. It never edits source code,
opens a PR, promotes a candidate, or changes execution authority.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from frankie_backends import ReasoningBackend
from frankie_core import FrankieConfig, GateStop, load_json
from frankie_improve import propose_improvement


def resolved_evidence_paths(config: FrankieConfig, *, limit: int = 50) -> list[Path]:
    if limit < 1 or limit > 100:
        raise GateStop("reflection limit must be between 1 and 100")
    if not config.evidence_root.exists():
        return []
    candidates = sorted(
        config.evidence_root.rglob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    resolved: list[Path] = []
    for path in candidates:
        raw = load_json(path)
        decision = raw.get("decision") if isinstance(raw, dict) else None
        if not isinstance(decision, dict):
            continue
        decision_hash = str(decision.get("decision_hash") or "")
        if not decision_hash:
            continue
        outcome = config.evidence_root.parent / "outcomes" / f"{decision_hash}.json"
        if outcome.is_file():
            resolved.append(path)
        if len(resolved) >= limit:
            break
    return resolved


def reflect(
    *,
    config: FrankieConfig,
    proposer: ReasoningBackend,
    critic: ReasoningBackend,
    limit: int = 50,
    min_resolved: int = 5,
) -> dict[str, Any]:
    paths = resolved_evidence_paths(config, limit=limit)
    if len(paths) < min_resolved:
        raise GateStop(
            f"reflection requires at least {min_resolved} resolved evidence records; found {len(paths)}"
        )
    result = propose_improvement(
        evidence_paths=paths,
        proposer=proposer,
        critic=critic,
        config=config,
    )
    result["reflection"] = {
        "resolved_records_used": len(paths),
        "limit": limit,
        "min_resolved": min_resolved,
        "automatic_apply": False,
    }
    return result
