from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Registry layout per architecture_spec_v21.docx §3.1. The registry is the
# central nervous system: every read routes through ``operator_query`` which
# loads from these subdirectories.
REGISTRY_DIR = PROJECT_ROOT / "registry"
MANIFESTS_DIR = REGISTRY_DIR / "manifests"
EMBEDDINGS_DIR = REGISTRY_DIR / "embeddings"
CAPABILITY_INDEX_DIR = REGISTRY_DIR / "capability_index"
DEPENDENCY_GRAPH_DIR = REGISTRY_DIR / "dependency_graph"
LINEAGE_DIR = REGISTRY_DIR / "lineage"

# Data-shape schemas (SpectralChunk, OperatorCandidate, EvidenceGraph, plus the
# operator manifest meta-schema). Outside ``registry/`` because they govern the
# wire/contract layer rather than the operator registry.
SCHEMA_DIR = PROJECT_ROOT / "schema"

# Scratch space for non-registry control-plane state (benchmarks, lifecycle,
# optimizations, exploration, meta_learner) and runtime artefacts (execution
# traces, evidence graphs, retrieval policy history). The ``discoveries/``
# directory at the project root is the canonical store for validated operator
# recoveries per arch §4 and is NOT under ``artifacts/``.
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
DISCOVERIES_DIR = PROJECT_ROOT / "discoveries"
