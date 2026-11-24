from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.paths import DISCOVERIES_DIR
from refrag_discovery.registry import build_default_operator_query


# Arch §4 ("index.json is the master query point ... maps discovery_id to
# file path") + Rule 8 ("Every Discovery Persists Immediately"). This module
# previously shipped with a hardcoded ``_DOMAIN_SUMMARY_PATHS`` dict pointing
# at ``E:\Markets\...`` and ``E:\refrag\_full_pipeline_quantum\...``. That
# bypassed the registry, hardcoded environment-specific absolute paths, and
# violated the arch-doc lookup contract.
#
# The loader now queries ``discoveries/index.json`` first, then falls back to a
# glob over ``discoveries/operator_discoveries/<domain>/`` on cold start. The
# ``summary_paths_by_domain`` knob is preserved as a caller-supplied override
# so adapters that maintain a richer per-bucket ``summary.json`` (with
# asset/venue/side metadata the bare discovery payload doesn't carry) can
# still feed those fields through — it is checked AFTER the index path so
# the registry stays the source of truth and the sidecar is purely additive.
_OPERATOR_DISCOVERIES_SUBDIR = "operator_discoveries"


def _project_discoveries_root() -> Path:
    """Resolve the on-disk discoveries root used by the orchestrator's writes."""
    return DISCOVERIES_DIR


def _load_index(discoveries_root: Path) -> dict[str, Any]:
    """Load ``discoveries_root/index.json`` per arch §4. Empty dict on miss."""
    index_path = discoveries_root / "index.json"
    if not index_path.exists():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _discovery_paths_for_domain(
    domain: str,
    discoveries_root: Path | None = None,
) -> list[Path]:
    """Return per-trade discovery file paths for a domain.

    Resolution order, per arch §4:
      1. ``discoveries/index.json`` — master query point. ``by_domain`` is the
         canonical map; ``discoveries.<id>.path`` gives the repo-relative
         path. We prefer ``discoveries.<id>`` when available since it carries
         richer per-entry metadata, falling back to ``by_domain`` otherwise.
      2. Glob over ``discoveries/operator_discoveries/<domain>/*.json`` —
         cold-start fallback when the index has not been built (Rule 8: the
         directory is the ground truth, index.json is a derived cache).

    Returns an empty list when neither source yields paths.
    """
    root = discoveries_root or _project_discoveries_root()
    key = domain.lower()
    index = _load_index(root)

    found: list[Path] = []
    discoveries_map = index.get("discoveries", {}) if isinstance(index, dict) else {}
    by_domain = index.get("by_domain", {}) if isinstance(index, dict) else {}

    if isinstance(discoveries_map, dict) and discoveries_map:
        for discovery_id, entry in discoveries_map.items():
            if not isinstance(entry, dict):
                continue
            entry_domain = str(entry.get("domain", "")).lower()
            if entry_domain != key:
                continue
            rel = entry.get("path")
            if not rel:
                continue
            found.append((root / rel).resolve())

    if not found and isinstance(by_domain, dict):
        ids = by_domain.get(domain) or by_domain.get(key)
        if isinstance(ids, list):
            for did in ids:
                found.append(
                    (root / _OPERATOR_DISCOVERIES_SUBDIR / domain / f"{did}.json")
                )

    if not found:
        # Cold-start fallback: glob the per-domain subdir. The directory is
        # the source of truth per Rule 8; we don't require the index to exist.
        domain_dir = root / _OPERATOR_DISCOVERIES_SUBDIR / domain
        if domain_dir.is_dir():
            found = sorted(domain_dir.glob("*.json"))

    # De-duplicate while preserving order (some indexes carry an id in both
    # ``discoveries`` and ``by_domain``).
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in found:
        if p in seen:
            continue
        seen.add(p)
        unique.append(p)
    return unique


def detect_cross_domain_transfer(
    *,
    source_domain: str,
    target_domain: str,
    comparison_mode: str = "full",
    similarity_threshold: float = 0.7,
    operator_ids: list[str] | None = None,
    summary_paths_by_domain: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Detect cross-domain transfer candidates.

    Two implemented modes per the v2.1 manifest's
    comparison_mode enum:
      - "capability_jaccard" / "full" (default, legacy): Jaccard similarity over
        registered operator MANIFEST capability tags. Compares operator
        definitions, not discovered outputs. Useful for "are these operators
        related conceptually?" Coarse.
      - "spectral_similarity": cosine similarity over per-trade
        operator_coefficients VECTORS produced by the runtime pipeline. This
        is what the manifest description means by spectral_similarity. Useful
        for "did the pipeline recover comparable mathematical structure across
        domains?" Fine-grained, doc-aligned with rule 7 (refrag-core
        FaissIndex used unmodified).
    """
    if comparison_mode == "spectral_similarity":
        return _spectral_similarity_mode(
            source_domain=source_domain,
            target_domain=target_domain,
            similarity_threshold=similarity_threshold,
            summary_paths_by_domain=summary_paths_by_domain,
        )

    # Legacy capability-Jaccard path (default / "full").
    query = build_default_operator_query()
    manifests = [query.get_manifest(operator_id) for operator_id in operator_ids] if operator_ids else query.list_manifests()
    source_manifests = [manifest for manifest in manifests if str(manifest.get("domain", "")).lower() == source_domain.lower()]
    target_manifests = [manifest for manifest in manifests if str(manifest.get("domain", "")).lower() == target_domain.lower()]

    transfer_candidates = []
    structural_mappings = []
    transport_plans = []
    confidence: list[float] = []
    novel_predictions: list[str] = []

    for source in source_manifests:
        source_caps = {str(item).lower() for item in source.get("capabilities", [])}
        for target in target_manifests:
            target_caps = {str(item).lower() for item in target.get("capabilities", [])}
            overlap = len(source_caps & target_caps)
            union = max(1, len(source_caps | target_caps))
            score = round(overlap / union, 4)
            if score < similarity_threshold:
                continue
            transfer_candidates.append(
                {
                    "source_operator_id": source["operator_id"],
                    "target_operator_id": target["operator_id"],
                    "score": score,
                    "comparison_mode": comparison_mode,
                }
            )
            structural_mappings.append(
                {
                    "source_operator_id": source["operator_id"],
                    "target_operator_id": target["operator_id"],
                    "shared_capabilities": sorted(source_caps & target_caps),
                }
            )
            transport_plans.append(
                {
                    "source_operator_id": source["operator_id"],
                    "target_operator_id": target["operator_id"],
                    "mass_mapping": {
                        capability: round(1.0 / max(1, overlap), 4)
                        for capability in sorted(source_caps & target_caps)
                    },
                }
            )
            confidence.append(score)
            novel_predictions.append(
                f"{source['operator_id']} may transfer to {target['operator_id']} in {target_domain}"
            )

    readiness = {
        "effect_size": round(sum(confidence) / max(1, len(confidence)), 4) if confidence else 0.0,
        "significance": "candidate" if confidence else "insufficient_signal",
        "replication_potential": "high" if len(transfer_candidates) >= 2 else "medium" if transfer_candidates else "low",
    }

    return with_production_readiness(
        "cross_domain_transfer_detector",
        {
            "transfer_candidates": transfer_candidates,
            "structural_mappings": structural_mappings,
            "transport_plans": transport_plans,
            "confidence": confidence,
            "novel_predictions": novel_predictions,
            "publication_readiness": readiness,
        },
    )


# ---------------------------------------------------------------------------
# spectral_similarity mode (over per-trade operator_coefficients vectors)
# ---------------------------------------------------------------------------

def _l2_normalize(v: list[float]) -> list[float] | None:
    n = math.sqrt(sum(x * x for x in v))
    if n == 0.0:
        return None
    return [x / n for x in v]


def _load_summary_metadata(
    domain: str,
    summary_paths_by_domain: dict[str, str] | None,
) -> dict[str, dict[str, Any]]:
    """Optional sidecar metadata, keyed by run_id.

    Adapters that maintain a per-bucket ``summary.json`` with richer
    per-trade fields (asset/venue/side/net_bps/etc.) can pass
    ``summary_paths_by_domain={"<domain>": "<path>"}`` to feed those through
    to the cross-domain report. The arch §4 ``index.json`` remains the
    authoritative source of WHICH discoveries belong to the domain; this map
    only enriches WHAT is reported about each one.
    """
    if not summary_paths_by_domain:
        return {}
    key = domain.lower()
    summary_path: str | None = None
    for k, v in summary_paths_by_domain.items():
        if k.lower() == key:
            summary_path = v
            break
    if not summary_path:
        return {}
    p = Path(summary_path)
    if not p.exists():
        return {}
    try:
        summary = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    metadata_by_run: dict[str, dict[str, Any]] = {}
    for r in summary.get("results", []):
        run_id = r.get("run_id")
        if not run_id:
            continue
        metadata_by_run[str(run_id)] = r
    return metadata_by_run


def _extract_source_id_from_payload(payload: dict[str, Any]) -> str | None:
    """Pull the trade source_id from the discovery's evidence graph if
    available. Falls back to ``None`` — caller uses ``run_id`` then."""
    eg = payload.get("result", {}).get("evidence_graph", {}) if isinstance(payload, dict) else {}
    for node in eg.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        if node.get("type") != "document":
            continue
        md = node.get("metadata") or {}
        sid = md.get("source_id")
        if sid:
            return str(sid)
        # Fallback: many docs encode source_id directly in the text field.
        text = node.get("text")
        if text:
            return str(text)
    return None


def _load_domain_vectors(
    domain: str,
    summary_paths_by_domain: dict[str, str] | None = None,
    discoveries_root: Path | None = None,
) -> list[dict]:
    """Load per-trade operator_coefficients vectors for a domain.

    Arch §4: ``discoveries/index.json`` is the master query point. We list the
    domain's discoveries via :func:`_discovery_paths_for_domain` (index-first,
    glob-fallback), read each per-trade payload, extract
    ``result.operator_coefficients``, and L2-normalize for cosine. The
    optional ``summary_paths_by_domain`` knob enriches the per-record metadata
    with adapter-specific fields (asset/venue/side/etc.) when supplied.
    """
    paths = _discovery_paths_for_domain(domain, discoveries_root=discoveries_root)
    if not paths:
        return []

    metadata_by_run = _load_summary_metadata(domain, summary_paths_by_domain)
    domain_key = domain.lower()
    out: list[dict] = []
    for disc_path in paths:
        if not disc_path.exists():
            continue
        try:
            with disc_path.open(encoding="utf-8") as f:
                disc = json.load(f)
            coeffs = list(disc["result"]["operator_coefficients"])
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            continue
        normed = _l2_normalize(coeffs)
        if normed is None:
            continue

        run_id = str(disc.get("run_id") or disc_path.stem)
        sidecar = metadata_by_run.get(run_id, {})
        sid = (
            sidecar.get("trade_source_id")
            or sidecar.get("source_id")
            or _extract_source_id_from_payload(disc)
            or run_id
        )
        meta = {
            "id": sid,
            "domain": domain_key,
            "run_id": run_id,
            "vector_dim": len(normed),
            "validity_probability": sidecar.get("validity_probability"),
        }
        for k in (
            "asset", "venue", "side", "strategy_id", "net_bps", "canonical_trade_key",
            "source_kind", "epsilon", "Delta", "lambda", "gamma", "beta",
            "T_avg", "delta_T", "initial",
        ):
            if k in sidecar:
                meta[k] = sidecar[k]
        out.append({"vector": normed, "meta": meta})
    return out


def _spectral_similarity_mode(
    *,
    source_domain: str,
    target_domain: str,
    similarity_threshold: float,
    summary_paths_by_domain: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Cosine similarity over per-trade operator_coefficients via FaissIndex.

    For each source-domain vector, find target-domain vectors above threshold.
    Rule-7 safe: uses refrag-core FaissIndex unmodified.
    """
    # Lazy import — only this mode pulls refrag-core
    import sys
    refrag_root = r"E:\refrag"
    if refrag_root not in sys.path:
        sys.path.insert(0, refrag_root)
    from refrag_core import FaissIndex  # type: ignore

    source_records = _load_domain_vectors(source_domain, summary_paths_by_domain)
    target_records = _load_domain_vectors(target_domain, summary_paths_by_domain)

    transfer_candidates: list[dict] = []
    structural_mappings: list[dict] = []
    confidence: list[float] = []
    novel_predictions: list[str] = []

    if not source_records or not target_records:
        return with_production_readiness(
            "cross_domain_transfer_detector",
            {
                "comparison_mode": "spectral_similarity",
                "source_domain": source_domain,
                "target_domain": target_domain,
                "source_n": len(source_records),
                "target_n": len(target_records),
                "transfer_candidates": transfer_candidates,
                "structural_mappings": structural_mappings,
                "transport_plans": [],
                "confidence": confidence,
                "novel_predictions": novel_predictions,
                "publication_readiness": {
                    "effect_size": 0.0,
                    "significance": "insufficient_signal",
                    "replication_potential": "low",
                },
            },
        )

    dim = len(source_records[0]["vector"])
    # Sanity: dims must match (same pipeline must have produced both).
    if dim != len(target_records[0]["vector"]):
        return with_production_readiness(
            "cross_domain_transfer_detector",
            {
                "comparison_mode": "spectral_similarity",
                "error": (
                    f"vector_dim_mismatch: source={dim} target={len(target_records[0]['vector'])}. "
                    "Both domains must be produced by the same pipeline (od_spectral_retrieval_pipeline)."
                ),
                "source_n": len(source_records),
                "target_n": len(target_records),
            },
        )

    # Build FAISS index over TARGET domain (the larger side wins efficiency
    # by being indexed once and queried many times)
    index = FaissIndex(dim=dim, backend="auto")
    index.add([r["vector"] for r in target_records])

    top_k = 8  # inherited from the pipeline's own query top_k (not a tuned knob)
    for src in source_records:
        hits = index.search(src["vector"], top_k)
        for h in hits:
            if h.idx < 0 or h.idx >= len(target_records):
                continue
            sim = float(h.score)  # cosine on L2-normalized vectors
            if sim < similarity_threshold:
                continue
            tgt = target_records[h.idx]
            transfer_candidates.append(
                {
                    "source_id": src["meta"]["id"],
                    "target_id": tgt["meta"]["id"],
                    "score": round(sim, 4),
                    "comparison_mode": "spectral_similarity",
                }
            )
            structural_mappings.append(
                {
                    "source_id": src["meta"]["id"],
                    "target_id": tgt["meta"]["id"],
                    "source_meta": src["meta"],
                    "target_meta": tgt["meta"],
                }
            )
            confidence.append(sim)
            novel_predictions.append(
                f"{source_domain}:{src['meta']['id']} ~ {target_domain}:{tgt['meta']['id']} (cos={sim:.3f})"
            )

    readiness = {
        "effect_size": round(sum(confidence) / max(1, len(confidence)), 4) if confidence else 0.0,
        "significance": "candidate" if confidence else "insufficient_signal",
        "replication_potential": "high" if len(transfer_candidates) >= 10 else "medium" if transfer_candidates else "low",
    }

    return with_production_readiness(
        "cross_domain_transfer_detector",
        {
            "comparison_mode": "spectral_similarity",
            "source_domain": source_domain,
            "target_domain": target_domain,
            "source_n": len(source_records),
            "target_n": len(target_records),
            "vector_dim": dim,
            "similarity_threshold": similarity_threshold,
            "top_k_per_source": top_k,
            "transfer_candidates": transfer_candidates,
            "structural_mappings": structural_mappings,
            "transport_plans": [],  # OT plans not implemented in spectral mode
            "confidence": confidence,
            "novel_predictions": novel_predictions,
            "publication_readiness": readiness,
        },
    )
