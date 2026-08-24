#!/usr/bin/env python3
"""Production source-spec builder for the corrected October knowledge plane.

The checked-in curated inventory is the routing authority.  This module turns
every concrete path in sections A-M into an explicit, fail-closed SourceSpec;
the KnowledgePlane subsequently hashes every byte and proves complete chunk
coverage.  Tests and obsolete transports are catalogued as denied sources so
their existence can never make them silently servable.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from pathlib import Path

from research.kalshi.frankie_authority_knowledge_plane_20260824 import (
    AccessPolicy,
    AuthorityClass,
    ExternalSourceDescriptor,
    KnowledgeCatalogError,
    SourceSpec,
    TargetRelationship,
)
from research.kalshi.ng_exhaustion_step1_completion_gate import FINAL_OUTPUT_NAMES


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
_DISCOVERED_SEALED_MANIFEST_PATHS = (
    "research/kalshi/NG_EXHAUSTION_MBO_5Y_STEP1_LAUNCH_20260822.json",
)


class ProvisionalSourceDisposition(str, Enum):
    EXECUTABLE_MODULE_BINDING = "EXECUTABLE_MODULE_BINDING"
    CONTEXT_ONLY_GOVERNANCE = "CONTEXT_ONLY_GOVERNANCE"
    DEFERRED_POST_EVIDENCE = "DEFERRED_POST_EVIDENCE"


@dataclass(frozen=True)
class ProvisionalSourceBinding:
    component_id: str
    disposition: ProvisionalSourceDisposition
    module_name: str | None = None
    required_symbol: str | None = None


def _module(component_id: str, module_name: str, required_symbol: str) -> ProvisionalSourceBinding:
    return ProvisionalSourceBinding(
        component_id,
        ProvisionalSourceDisposition.EXECUTABLE_MODULE_BINDING,
        module_name,
        required_symbol,
    )


def _context(component_id: str) -> ProvisionalSourceBinding:
    return ProvisionalSourceBinding(
        component_id, ProvisionalSourceDisposition.CONTEXT_ONLY_GOVERNANCE
    )


_META = ProvisionalSourceBinding(
    "META_LOOP", ProvisionalSourceDisposition.DEFERRED_POST_EVIDENCE
)

# Every provisional path is an explicit security/authority decision.  There is
# deliberately no filename fallback: a newly discovered source must be reviewed
# and added here before the production router will construct.
PROVISIONAL_SOURCE_DISPOSITIONS: dict[str, ProvisionalSourceBinding] = {
    "research/kalshi/FRANKIE_P0_GAP_CLOSURE_PROVISIONAL_20260820.md": _context(
        "PROVISIONAL_V4_ENGINEERING_CANDIDATE"
    ),
    "research/kalshi/FRANKIE_P0_GAP_CLOSURE_PROVISIONAL_MANIFEST_20260820.json": _context(
        "PROVISIONAL_V4_ENGINEERING_CANDIDATE"
    ),
    "research/kalshi/NG_EXHAUSTION_V4_PROVISIONAL_READINESS_20260821.json": _context(
        "PROVISIONAL_V4_ENGINEERING_CANDIDATE"
    ),
    "research/kalshi/frankie_s137_cognitive_runtime.py": _module(
        "S137_COGNITIVE_RUNTIME", "frankie_s137_cognitive_runtime", "runtime_for"
    ),
    "research/kalshi/frankie_s137_cognitive_experiment_runner.py": _module(
        "S137_COGNITIVE_RUNTIME", "frankie_s137_cognitive_experiment_runner", "run_paired_case"
    ),
    "research/kalshi/frankie_temporal_graph_p0_adapter.py": _module(
        "TEMPORAL_GRAPH", "frankie_temporal_graph_p0_adapter", "run_temporal_graph_shadow_adapter"
    ),
    "research/kalshi/frankie_hipporag_p0_retrieval.py": _module(
        "HIPPORAG_RETRIEVAL", "frankie_hipporag_p0_retrieval", "run_hipporag_shadow_pipeline"
    ),
    "research/kalshi/frankie_lats_p0_search.py": _module(
        "LATS_BOUNDED_SEARCH", "frankie_lats_p0_search", "run_bounded_lats_search"
    ),
    "research/kalshi/frankie_meta_loop_s138.py": _META,
    "research/kalshi/frankie_meta_loop_coordinator_s138.py": _META,
    "research/kalshi/frankie_cognition.py": _module(
        "S137_COGNITIVE_RUNTIME", "frankie_cognition", "sha256_json"
    ),
    "research/kalshi/frankie_cognitive_candidates.py": _module(
        "S137_COGNITIVE_RUNTIME", "frankie_cognitive_candidates", "coala_architecture_map"
    ),
    "research/kalshi/frankie_cognitive_experiment_row_schema.json": _context(
        "S137_COGNITIVE_RUNTIME"
    ),
    "research/kalshi/frankie_cognitive_experiments.py": _module(
        "S137_COGNITIVE_RUNTIME", "frankie_cognitive_experiments", "experiment_manifest"
    ),
    "research/kalshi/frankie_cognitive_p0_loops.py": _module(
        "WORKING_MEMORY", "frankie_cognitive_p0_loops", "run_state_aware_working_memory"
    ),
    "research/kalshi/frankie_gdl_p0_controls.py": _module(
        "TEMPORAL_GRAPH", "frankie_gdl_p0_controls", "audit_causal_prefix"
    ),
    "research/kalshi/frankie_market_p0_controls.py": _module(
        "PROVISIONAL_V4_ENGINEERING_CANDIDATE",
        "frankie_market_p0_controls",
        "score_open_stream_events",
    ),
    "research/kalshi/frankie_microstructure_p0_baselines.py": _module(
        "PROVISIONAL_V4_ENGINEERING_CANDIDATE",
        "frankie_microstructure_p0_baselines",
        "compute_level1_ofi_events",
    ),
    "research/kalshi/frankie_p0_real_evidence_plan.py": _module(
        "PROVISIONAL_V4_ENGINEERING_CANDIDATE",
        "frankie_p0_real_evidence_plan",
        "validate_receipt_bundle",
    ),
    "research/kalshi/frankie_p0_registry.py": _module(
        "PROVISIONAL_V4_ENGINEERING_CANDIDATE", "frankie_p0_registry", "audit_p0_registry"
    ),
    "research/kalshi/frankie_progress_compress_p0.py": _module(
        "PROGRESS_COMPRESSION", "frankie_progress_compress_p0", "run_progress_compress_shadow"
    ),
    "research/kalshi/frankie_temporal_p0_controls.py": _module(
        "TEMPORAL_GRAPH", "frankie_temporal_p0_controls", "audit_planted_null_first_locks"
    ),
}

_STEP1_OUTPUT_NAMES = (
    ("STEP1_DUAL_CENSUS_RECEIPT.json", "RECEIPT"),
    ("LEGACY_CONTROL_OVERLAP_EQUIVALENCE.json", "RECONCILIATION"),
    *((name, "GOVERNED_FINAL_OUTPUT") for name in FINAL_OUTPUT_NAMES),
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
    for path in _DISCOVERED_SEALED_MANIFEST_PATHS:
        if path in catalogued:
            continue
        if not (root_path / path).is_file():
            raise KnowledgeCatalogError(f"discovered sealed manifest is missing: {path}")
        specs.append(
            SourceSpec(
                path=path,
                authority=AuthorityClass.SEALED_TARGET_ANSWER,
                target_relationship=TargetRelationship.OCTOBER_STEP1_ANSWER,
                access_policy=AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE,
            )
        )
    provisional_paths = {
        item.path for item in specs if item.authority is AuthorityClass.PROVISIONAL_SHADOW
    }
    if provisional_paths != set(PROVISIONAL_SOURCE_DISPOSITIONS):
        raise KnowledgeCatalogError(
            "explicit provisional source disposition table is incomplete"
        )
    return tuple(specs)


def _external_descriptor(
    *,
    descriptor_id: str,
    external_uri: str,
    object_kind: str,
    governing_source_path: str,
    governing_source_sha256: str,
) -> ExternalSourceDescriptor:
    core = {
        "descriptor_id": descriptor_id,
        "external_uri": external_uri,
        "object_kind": object_kind,
        "governing_source_path": governing_source_path,
        "governing_source_sha256": governing_source_sha256,
        "content_sha256": None,
        "byte_length": None,
        "local_path": None,
        "authority": AuthorityClass.SEALED_TARGET_ANSWER.value,
        "target_relationship": TargetRelationship.OCTOBER_STEP1_ANSWER.value,
        "access_policy": AccessPolicy.SEALED_UNTIL_PRIMARY_FREEZE.value,
        "content_accessed": False,
    }
    descriptor_sha256 = hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return ExternalSourceDescriptor(
        descriptor_sha256=descriptor_sha256,
        **{
            key: core[key]
            for key in (
                "descriptor_id",
                "external_uri",
                "object_kind",
                "governing_source_path",
                "governing_source_sha256",
            )
        },
    )


def sealed_step1_external_descriptors(
    root: str | Path,
) -> tuple[ExternalSourceDescriptor, ...]:
    """Expand known Step-1 result identities without opening any result object."""
    root_path = Path(root).resolve()
    governor_path = _DISCOVERED_SEALED_MANIFEST_PATHS[0]
    governor_bytes = (root_path / governor_path).read_bytes()
    try:
        governor = json.loads(governor_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KnowledgeCatalogError("Step-1 launch receipt is not valid UTF-8 JSON metadata") from exc
    candidate = str(governor.get("candidate_commit") or "")
    prefix = str(governor.get("result_prefix") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", candidate):
        raise KnowledgeCatalogError("Step-1 launch receipt candidate identity is invalid")
    if (
        not prefix.startswith("s3://")
        or candidate not in prefix
        or any(char.isspace() for char in prefix)
    ):
        raise KnowledgeCatalogError("Step-1 result prefix identity is invalid")
    prefix = prefix.rstrip("/") + "/"
    governor_sha = hashlib.sha256(governor_bytes).hexdigest()
    descriptors = [
        _external_descriptor(
            descriptor_id="step1:result-prefix",
            external_uri=prefix,
            object_kind="RESULT_PREFIX",
            governing_source_path=governor_path,
            governing_source_sha256=governor_sha,
        )
    ]
    for name, kind in _STEP1_OUTPUT_NAMES:
        descriptors.append(
            _external_descriptor(
                descriptor_id=f"step1:{name}",
                external_uri=f"{prefix}results/{name}",
                object_kind=kind,
                governing_source_path=governor_path,
                governing_source_sha256=governor_sha,
            )
        )
    return tuple(descriptors)


__all__ = [
    "INVENTORY_PATH",
    "PROVISIONAL_SOURCE_DISPOSITIONS",
    "ProvisionalSourceBinding",
    "ProvisionalSourceDisposition",
    "production_source_specs",
    "sealed_step1_external_descriptors",
]
