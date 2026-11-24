from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from refrag_discovery.registry.manifest_validator import (
    DEFAULT_MANIFESTS_DIR,
    DEFAULT_OPERATOR_SCHEMA_PATH,
    validate_manifests,
)
from refrag_discovery.registry.models import ManifestRecord, ManifestValidationResult


# Arch §3.1: the dependency graph stores both adjacency-list JSON *and* a
# SQLite mirror for SQL-style queries (transitive deps, cycle detection).
# The SQLite mirror is built from the existing JSON so we keep a single source
# of truth on disk; this import is lazy inside the bootstrap call site so
# environments that only need the in-memory ``ManifestRegistry`` (e.g. import
# during module collection) don't pay the SQLite cost.


@dataclass(frozen=True)
class ManifestRegistry:
    records_by_id: dict[str, ManifestRecord]
    by_execution_class: dict[str, tuple[str, ...]]
    by_operator_type: dict[str, tuple[str, ...]]
    capability_index: dict[str, tuple[str, ...]]
    dependency_graph: dict[str, tuple[str, ...]]


def _search_text(manifest: dict) -> str:
    fields: list[str] = [
        str(manifest.get("operator_id", "")),
        str(manifest.get("operator_name", "")),
        str(manifest.get("description", "")),
    ]
    fields.extend(manifest.get("tags", []))
    fields.extend(manifest.get("capabilities", []))
    for item in manifest.get("inputs", []):
        fields.append(str(item.get("name", "")))
        fields.append(str(item.get("type", "")))
    for item in manifest.get("outputs", []):
        fields.append(str(item.get("name", "")))
        fields.append(str(item.get("type", "")))
    return " ".join(part for part in fields if part).lower()


def _build_record(result: ManifestValidationResult) -> ManifestRecord:
    manifest = result.normalized_manifest
    capabilities = tuple(str(item) for item in manifest.get("capabilities", []))
    dependencies = tuple(
        str(item.get("operator_id"))
        for item in manifest.get("dependencies", [])
        if item.get("operator_id")
    )
    return ManifestRecord(
        operator_id=str(manifest["operator_id"]),
        manifest=manifest,
        path=result.path,
        search_text=_search_text(manifest),
        capabilities=capabilities,
        dependencies=dependencies,
        execution_class=str(manifest.get("execution_class", "")),
        operator_type=str(manifest.get("operator_type", "")),
    )


def bootstrap_registry(
    manifests_dir: Path = DEFAULT_MANIFESTS_DIR,
    schema_path: Path = DEFAULT_OPERATOR_SCHEMA_PATH,
    *,
    repair: bool = False,
    sync_dependency_graph_sqlite: bool = True,
) -> ManifestRegistry:
    results = validate_manifests(manifests_dir, schema_path, repair=repair)
    invalid = [result for result in results if not result.valid]
    if invalid:
        messages = "\n".join(
            f"{result.path.name}: {'; '.join(result.errors)}" for result in invalid
        )
        raise ValueError(f"Manifest validation failed:\n{messages}")

    records_by_id: dict[str, ManifestRecord] = {}
    by_execution_class: defaultdict[str, list[str]] = defaultdict(list)
    by_operator_type: defaultdict[str, list[str]] = defaultdict(list)
    capability_index: defaultdict[str, list[str]] = defaultdict(list)
    dependency_graph: dict[str, tuple[str, ...]] = {}

    for result in results:
        record = _build_record(result)
        records_by_id[record.operator_id] = record
        by_execution_class[record.execution_class].append(record.operator_id)
        by_operator_type[record.operator_type].append(record.operator_id)
        for capability in record.capabilities:
            capability_index[capability].append(record.operator_id)
        dependency_graph[record.operator_id] = record.dependencies

    # Arch §3.1 mandates a SQLite mirror of the dep graph alongside graph.json.
    # The mirror is built from the existing JSON (which is itself materialised
    # by ``scripts/build_registry_indexes.py``) so it stays consistent with the
    # canonical source. Failures are non-fatal — they only mean the SQL-style
    # query API in ``dependency_graph_store`` won't return up-to-date results;
    # the in-memory ``ManifestRegistry`` returned here is unaffected, so we
    # keep the legacy import contract intact.
    if sync_dependency_graph_sqlite:
        _sync_dependency_graph_sqlite()

    return ManifestRegistry(
        records_by_id=records_by_id,
        by_execution_class={key: tuple(value) for key, value in by_execution_class.items()},
        by_operator_type={key: tuple(value) for key, value in by_operator_type.items()},
        capability_index={key: tuple(value) for key, value in capability_index.items()},
        dependency_graph=dependency_graph,
    )


def _sync_dependency_graph_sqlite() -> None:
    """Refresh ``registry/dependency_graph/graph.sqlite`` from the JSON (arch §3.1).

    Idempotent: the underlying ``bootstrap_sqlite_from_json`` uses
    ``CREATE TABLE IF NOT EXISTS`` + ``INSERT OR REPLACE`` so repeated calls
    leave the same SQLite contents.

    Silent on filesystems where either JSON file is missing (e.g. fresh
    checkouts before ``scripts/build_registry_indexes.py`` has run). The
    Phase 1 registry tests assert both JSON files exist for any real run, so
    this branch is only reached in malformed environments where the SQLite
    sync would have failed regardless.
    """
    # Lazy import — keeps test collection cheap when SQLite isn't needed and
    # avoids a circular import via ``refrag_discovery.paths``.
    from refrag_discovery.registry.dependency_graph_store import (
        DEFAULT_GRAPH_JSON_PATH,
        DEFAULT_SQLITE_PATH,
        DEFAULT_TOPO_JSON_PATH,
        bootstrap_sqlite_from_json,
    )

    if not DEFAULT_GRAPH_JSON_PATH.exists():
        return
    if not DEFAULT_TOPO_JSON_PATH.exists():
        return
    bootstrap_sqlite_from_json(
        graph_json_path=DEFAULT_GRAPH_JSON_PATH,
        topo_json_path=DEFAULT_TOPO_JSON_PATH,
        sqlite_path=DEFAULT_SQLITE_PATH,
    )
