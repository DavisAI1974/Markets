"""Manifest-backed registry for discovery operators."""

from refrag_discovery.registry import dependency_graph_store, trace_store
from refrag_discovery.registry.bootstrap import ManifestRegistry, bootstrap_registry
from refrag_discovery.registry.discovery_index_writer import append_discovery
from refrag_discovery.registry.manifest_validator import (
    DEFAULT_EVIDENCE_SCHEMA_PATH,
    DEFAULT_MANIFESTS_DIR,
    DEFAULT_OPERATOR_SCHEMA_PATH,
    validate_evidence_graph,
    validate_manifests,
)
from refrag_discovery.registry.operator_query import (
    OperatorQueryService,
    build_default_operator_query,
)
from refrag_discovery.registry.registry_writer import (
    AUDIT_LOG_PATH,
    write_registry,
)

__all__ = [
    "AUDIT_LOG_PATH",
    "DEFAULT_EVIDENCE_SCHEMA_PATH",
    "DEFAULT_MANIFESTS_DIR",
    "DEFAULT_OPERATOR_SCHEMA_PATH",
    "ManifestRegistry",
    "OperatorQueryService",
    "append_discovery",
    "bootstrap_registry",
    "build_default_operator_query",
    "dependency_graph_store",
    "trace_store",
    "validate_evidence_graph",
    "validate_manifests",
    "write_registry",
]
