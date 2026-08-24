#!/usr/bin/env python3
"""Cross-reference the pushed 148-path Frankie inventory against live wiring.

The source inventory is a governing list, but not every listed file is supposed
to enter a pre-reveal provider request.  This audit distinguishes active base
evidence, executed shadow inputs, lawful deferrals, superseded material, sealed
answers, and denied archives.  It also accounts for provisional dependencies
discovered after the original list was committed.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from research.kalshi.frankie_authority_knowledge_plane_20260824 import (
    AuthorityClass,
    KnowledgePlane,
    october_full_stack_completeness_contract,
)
from research.kalshi.frankie_full_stack_provisional_combined_pipeline_20260824 import (
    ACTIVE_COMPONENT_IDS,
    EXECUTION_APIS,
)
from research.kalshi.frankie_lane_aware_context_router_20260824 import (
    ContextVariant,
    FrankieLaneAwareContextRouter,
)
from research.kalshi.frankie_october_knowledge_inventory_20260824 import (
    production_source_specs,
    sealed_step1_external_descriptors,
)
from research.kalshi.ng_exhaustion_frankie_fullstack_october_20260824 import (
    _base_knowledge,
    paired_component_id,
    production_provisional_components,
)


SCHEMA = "FRANKIE_SOURCE_INVENTORY_CROSS_REFERENCE_V1_20260824"
INVENTORY_PATH = Path(
    "research/kalshi/NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md"
)
EXPECTED_LISTED_SOURCES = 148
EXPECTED_DISCOVERED_DEPENDENCIES = 12
EXPECTED_ADDITIONAL_LOCAL_SEALED_GOVERNING_IDENTITIES = 1
EXPECTED_LOCAL_CATALOG_SOURCES = 161
EXPECTED_EXTERNAL_SEALED_DESCRIPTORS = 13
EXPECTED_TOTAL_MANIFEST_IDENTITIES = 174
EXPECTED_DISPOSITIONS = {
    "BASE_PROVIDER_ACTIVE": 117,
    "PROVISIONAL_EXECUTED": 8,
    "META_LOOP_DEFERRED": 2,
    # The two obsolete V3 proposal addenda plus the older October-sharded
    # handoff are explicitly superseded.  The latter was easy to miscount as
    # generic archive material; preserve the executable catalog's stronger,
    # path-specific disposition here.
    "SUPERSEDED_BY_CURRENT": 3,
    "ARCHIVE_DENIED": 14,
    "SEALED_TARGET_ANSWER": 4,
}


class InventoryCrossReferenceError(ValueError):
    """The pushed inventory and the executable wiring no longer agree."""


@dataclass(frozen=True)
class InventoryCrossReferenceRow:
    path: str
    section: str
    authority: str
    access_policy: str
    disposition: str
    component_id: str | None
    replacement_paths: tuple[str, ...]


def _hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _listed_paths(repo_root: Path) -> tuple[tuple[str, str], ...]:
    text = (repo_root / INVENTORY_PATH).read_text(encoding="utf-8")
    section = "UNSECTIONED"
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^## ([A-M])\. (.+)$", line)
        if match:
            section = f"{match.group(1)}. {match.group(2)}"
            continue
        path_match = re.match(r"^- `([^`]+)`", line)
        if path_match:
            rows.append((path_match.group(1), section))
    paths = [path for path, _section in rows]
    if len(paths) != EXPECTED_LISTED_SOURCES or len(set(paths)) != len(paths):
        raise InventoryCrossReferenceError("pushed 148-path inventory identity drift")
    return tuple(rows)


def build_source_inventory_cross_reference(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    listed = _listed_paths(root)
    specs = production_source_specs(root)
    spec_by_path = {item.path: item for item in specs}
    if len(specs) != EXPECTED_LOCAL_CATALOG_SOURCES:
        raise InventoryCrossReferenceError("local catalog source count drift")
    listed_paths = {path for path, _section in listed}
    missing_catalog = sorted(listed_paths - spec_by_path.keys())
    if missing_catalog:
        raise InventoryCrossReferenceError(
            f"listed sources absent from executable catalog: {missing_catalog}"
        )

    external_descriptors = sealed_step1_external_descriptors(root)
    if len(external_descriptors) != EXPECTED_EXTERNAL_SEALED_DESCRIPTORS:
        raise InventoryCrossReferenceError("external sealed descriptor count drift")
    plane = KnowledgePlane.build(
        root,
        specs,
        contract=october_full_stack_completeness_contract(),
        manifest_version=SCHEMA,
        external_descriptors=external_descriptors,
    )
    router = FrankieLaneAwareContextRouter(
        plane, production_provisional_components(plane)
    )
    bundle = router.build_routes(run_id="inventory-cross-reference", state_prefix_hash="0" * 64)
    combined = bundle.routes[ContextVariant.FULL_PROVISIONAL_COMBINED]
    base_paths = {item.path for item in combined.base_sources}
    active_paths = {item.path for item in combined.augmentation_sources}
    deferred_paths = {item.path for item in combined.withheld_sources}

    provider_excerpts = _base_knowledge(router, bundle)
    excerpt_source_ids = {item.source_id for item in provider_excerpts}
    if excerpt_source_ids != {item.source_id for item in combined.base_sources}:
        raise InventoryCrossReferenceError("not every routed base source reaches providers")

    rows: list[InventoryCrossReferenceRow] = []
    for path, section in listed:
        spec = spec_by_path[path]
        entry = plane.entry(path)
        component_id: str | None = None
        if path in base_paths:
            disposition = "BASE_PROVIDER_ACTIVE"
        elif path in active_paths:
            disposition = "PROVISIONAL_EXECUTED"
            component_id = paired_component_id(path)
            if component_id not in ACTIVE_COMPONENT_IDS or component_id not in EXECUTION_APIS:
                raise InventoryCrossReferenceError(
                    f"active provisional source has no executed ability: {path}"
                )
        elif path in deferred_paths:
            disposition = "META_LOOP_DEFERRED"
            component_id = paired_component_id(path)
            if component_id != "META_LOOP":
                raise InventoryCrossReferenceError(f"non-meta source was deferred: {path}")
        elif entry.superseded_by:
            disposition = "SUPERSEDED_BY_CURRENT"
            if not set(entry.superseded_by) <= base_paths:
                raise InventoryCrossReferenceError(
                    f"superseding source is not provider active: {path}"
                )
        elif spec.authority is AuthorityClass.ARCHIVE_NOT_SERVABLE:
            disposition = "ARCHIVE_DENIED"
        elif spec.authority is AuthorityClass.SEALED_TARGET_ANSWER:
            disposition = "SEALED_TARGET_ANSWER"
        else:
            raise InventoryCrossReferenceError(f"listed source is unaccounted for: {path}")
        rows.append(
            InventoryCrossReferenceRow(
                path=path,
                section=section,
                authority=spec.authority.value,
                access_policy=spec.access_policy.value,
                disposition=disposition,
                component_id=component_id,
                replacement_paths=tuple(entry.superseded_by),
            )
        )

    counts = dict(sorted(Counter(item.disposition for item in rows).items()))
    if counts != EXPECTED_DISPOSITIONS:
        raise InventoryCrossReferenceError(
            f"pushed inventory disposition drift: {counts}"
        )

    additional_local_paths = set(spec_by_path) - listed_paths
    discovered = tuple(
        sorted(
            path
            for path in additional_local_paths
            if spec_by_path[path].authority is AuthorityClass.PROVISIONAL_SHADOW
        )
    )
    if len(discovered) != EXPECTED_DISCOVERED_DEPENDENCIES:
        raise InventoryCrossReferenceError("discovered dependency count drift")
    local_sealed_governors = tuple(
        sorted(
            path
            for path in additional_local_paths
            if spec_by_path[path].authority is AuthorityClass.SEALED_TARGET_ANSWER
        )
    )
    if (
        len(local_sealed_governors)
        != EXPECTED_ADDITIONAL_LOCAL_SEALED_GOVERNING_IDENTITIES
        or set(discovered) | set(local_sealed_governors) != additional_local_paths
    ):
        raise InventoryCrossReferenceError(
            "additional local catalog identities are not exactly provisional dependencies plus sealed governors"
        )
    discovered_components: dict[str, str] = {}
    for path in discovered:
        if path not in active_paths:
            raise InventoryCrossReferenceError(
                f"discovered dependency is not in the active combined lane: {path}"
            )
        component_id = paired_component_id(path)
        if component_id not in ACTIVE_COMPONENT_IDS or component_id not in EXECUTION_APIS:
            raise InventoryCrossReferenceError(
                f"discovered dependency has no executed ability: {path}"
            )
        discovered_components[path] = component_id

    sealed_governor_rows: dict[str, dict[str, Any]] = {}
    for path in local_sealed_governors:
        entry = plane.entry(path)
        sealed_governor_rows[path] = {
            "source_id": entry.source_id,
            "source_sha256": entry.sha256,
            "byte_length": entry.byte_length,
            "authority": entry.authority.value,
            "access_policy": entry.access_policy.value,
            "target_relationship": entry.target_relationship.value,
        }

    external_rows = tuple(
        {
            **descriptor.identity_payload(),
            "descriptor_sha256": descriptor.descriptor_sha256,
        }
        for descriptor in plane.external_descriptors
    )
    if any(
        item["governing_source_path"] not in sealed_governor_rows
        or item["content_accessed"] is not False
        or item["content_sha256"] is not None
        or item["local_path"] is not None
        for item in external_rows
    ):
        raise InventoryCrossReferenceError(
            "external sealed descriptors crossed the pre-freeze answer wall"
        )
    total_manifest_identities = len(specs) + len(external_rows)
    if total_manifest_identities != EXPECTED_TOTAL_MANIFEST_IDENTITIES:
        raise InventoryCrossReferenceError("total manifest identity count drift")

    row_payload = [asdict(item) for item in rows]
    core = {
        "schema": SCHEMA,
        "listed_source_count": len(rows),
        "catalogued_source_count": len(specs),
        "discovered_dependency_count": len(discovered),
        "additional_local_sealed_governing_identity_count": len(local_sealed_governors),
        "external_sealed_descriptor_count": len(external_rows),
        "total_manifest_identity_count": total_manifest_identities,
        "disposition_counts": counts,
        "provider_visible_base_source_count": len(provider_excerpts),
        "combined_active_source_count": len(active_paths),
        "combined_active_components": list(ACTIVE_COMPONENT_IDS),
        "meta_loop_deferred_source_count": len(deferred_paths),
        "knowledge_manifest_hash": plane.manifest_hash,
        "all_listed_sources_accounted_for": True,
        "all_discovered_dependencies_accounted_for": True,
        "all_external_sealed_descriptors_accounted_for": True,
        "rows": row_payload,
        "discovered_dependencies": discovered_components,
        "additional_local_sealed_governing_identities": sealed_governor_rows,
        "external_sealed_descriptors": external_rows,
    }
    return {**core, "report_hash": _hash(core)}


__all__ = [
    "EXPECTED_ADDITIONAL_LOCAL_SEALED_GOVERNING_IDENTITIES",
    "EXPECTED_DISCOVERED_DEPENDENCIES",
    "EXPECTED_DISPOSITIONS",
    "EXPECTED_EXTERNAL_SEALED_DESCRIPTORS",
    "EXPECTED_LISTED_SOURCES",
    "EXPECTED_LOCAL_CATALOG_SOURCES",
    "EXPECTED_TOTAL_MANIFEST_IDENTITIES",
    "INVENTORY_PATH",
    "InventoryCrossReferenceError",
    "InventoryCrossReferenceRow",
    "SCHEMA",
    "build_source_inventory_cross_reference",
]
