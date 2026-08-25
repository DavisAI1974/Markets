#!/usr/bin/env python3
"""Production source-spec builder for the corrected October knowledge plane.

The checked-in curated inventory is the routing authority.  This module turns
every concrete path in sections A-M into an explicit, fail-closed SourceSpec;
the KnowledgePlane subsequently hashes every byte and proves complete chunk
coverage.  Tests and obsolete transports are catalogued as denied sources so
their existence can never make them silently servable.
"""
from __future__ import annotations

import re
from pathlib import Path

from research.kalshi.frankie_authority_knowledge_plane_20260824 import (
    AccessPolicy,
    AuthorityClass,
    KnowledgeCatalogError,
    SourceSpec,
    TargetRelationship,
)


INVENTORY_PATH = "research/kalshi/NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md"
_SECTION_RE = re.compile(r"^## ([A-M])\.")
_PATH_RE = re.compile(r"`((?:research|\.github)/[^`]+)`")

_CORRECTED_HANDOFF = (
    "research/kalshi/NG_EXHAUSTION_FRANKIE_FULL_STACK_OCTOBER_NEXT_CHAT_HANDOFF_20260824.md"
)
_OLDER_HANDOFF = "research/kalshi/NG_EXHAUSTION_OCTOBER_SHARDED_HANDOFF_20260824.md"
_CURRENT_BRAIN = "research/kalshi/knowledge/ng_brain.json"
_CLEAN_PROPOSAL = "research/NG_EXHAUSTION_V4_BRAIN_TRADE_PROPOSAL_CLEAN_SOURCE_CURRENT_20260820.md"
_OLDER_PROPOSALS = (
    "research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_ADDENDUM_20260820.md",
    "research/NG_EXHAUSTION_V3_V4_BRAIN_TRADE_PROPOSAL_FINAL_ADDENDUM_20260820.md",
)

# The curated document is the governing map, but its runtime-manifest references
# expose additional S137/P0 implementation dependencies.  The handoff requires
# discovery of renamed/later sources rather than silently stopping at the map.
_DISCOVERED_PROVISIONAL_PATHS = (
    "research/kalshi/frankie_cognition.py",
    "research/kalshi/frankie_cognitive_candidates.py",
    "research/kalshi/frankie_cognitive_experiment_row_schema.json",
    "research/kalshi/frankie_cognitive_experiments.py",
    "research/kalshi/frankie_cognitive_p0_loops.py",
    "research/kalshi/frankie_gdl_p0_controls.py",
    "research/kalshi/frankie_market_p0_controls.py",
    "research/kalshi/frankie_microstructure_p0_baselines.py",
    "research/kalshi/frankie_p0_real_evidence_plan.py",
    "research/kalshi/frankie_p0_registry.py",
    "research/kalshi/frankie_progress_compress_p0.py",
    "research/kalshi/frankie_temporal_p0_controls.py",
)


def _inventory_rows(root: Path) -> tuple[tuple[str, str], ...]:
    source = root / INVENTORY_PATH
    if not source.is_file():
        raise KnowledgeCatalogError(f"curated source inventory is missing: {INVENTORY_PATH}")
    section: str | None = None
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        match = _SECTION_RE.match(line)
        if match:
            section = match.group(1)
        if section is None:
            continue
        for path_match in _PATH_RE.finditer(line):
            path = path_match.group(1)
            if "*" in path:
                continue
            if path in seen:
                continue
            if not (root / path).is_file():
                raise KnowledgeCatalogError(f"inventoried source is missing: {path}")
            seen.add(path)
            rows.append((section, path))
    if not rows:
        raise KnowledgeCatalogError("curated source inventory has no concrete paths")
    return tuple(rows)


def _classification(section: str, path: str) -> tuple[AuthorityClass, AccessPolicy]:
    if section == "A":
        if path == _OLDER_HANDOFF:
            return AuthorityClass.ARCHIVE_NOT_SERVABLE, AccessPolicy.DENY
        return AuthorityClass.BINDING_CURRENT, AccessPolicy.SERVE
    if section == "B":
        if "/tests/" in path:
            return AuthorityClass.ARCHIVE_NOT_SERVABLE, AccessPolicy.DENY
        if path == _CURRENT_BRAIN:
            return AuthorityClass.CURRENT_BRAIN, AccessPolicy.SERVE
        return AuthorityClass.BINDING_CURRENT, AccessPolicy.SERVE
    if section in {"C", "D"}:
        return AuthorityClass.FROZEN_LEARNED_KNOWLEDGE, AccessPolicy.SERVE
    if section == "E":
        return AuthorityClass.BINDING_CURRENT, AccessPolicy.SERVE
    if section == "F":
        return AuthorityClass.EXTRA_AGENT_CARRYFORWARD, AccessPolicy.SERVE
    if section == "G":
        if Path(path).name.startswith("test_"):
            return AuthorityClass.ARCHIVE_NOT_SERVABLE, AccessPolicy.DENY
        return AuthorityClass.BINDING_CURRENT, AccessPolicy.SERVE
    if section in {"H", "I"}:
        return AuthorityClass.BINDING_CURRENT, AccessPolicy.SERVE
    if section == "J":
        return AuthorityClass.PROVISIONAL_SHADOW, AccessPolicy.SHADOW_ONLY
    if section == "K":
        return AuthorityClass.SEALED_TARGET_ANSWER, AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE
    if section in {"L", "M"}:
        return AuthorityClass.ARCHIVE_NOT_SERVABLE, AccessPolicy.DENY
    raise KnowledgeCatalogError(f"unclassified inventory section {section!r} for {path}")


def production_source_specs(root: str | Path) -> tuple[SourceSpec, ...]:
    """Classify every concrete curated path without reading sealed semantics."""
    root_path = Path(root).resolve()
    specs: list[SourceSpec] = []
    for section, path in _inventory_rows(root_path):
        authority, policy = _classification(section, path)
        target = TargetRelationship.GENERAL
        if section == "K":
            target = TargetRelationship.OCTOBER_STEP1_ANSWER
        elif section in {"L"} or path == _OLDER_HANDOFF:
            target = TargetRelationship.OCTOBER_TARGET_PERIOD
        supersedes: tuple[str, ...] = ()
        if path == _CORRECTED_HANDOFF:
            supersedes = (_OLDER_HANDOFF,)
        elif path == _CLEAN_PROPOSAL:
            supersedes = _OLDER_PROPOSALS
        specs.append(
            SourceSpec(
                path=path,
                authority=authority,
                supersedes=supersedes,
                target_relationship=target,
                access_policy=policy,
            )
        )
    catalogued = {item.path for item in specs}
    for path in _DISCOVERED_PROVISIONAL_PATHS:
        if path in catalogued:
            continue
        if not (root_path / path).is_file():
            raise KnowledgeCatalogError(f"discovered provisional dependency is missing: {path}")
        specs.append(
            SourceSpec(
                path=path,
                authority=AuthorityClass.PROVISIONAL_SHADOW,
                access_policy=AccessPolicy.SHADOW_ONLY,
            )
        )
    return tuple(specs)


__all__ = ["INVENTORY_PATH", "production_source_specs"]
