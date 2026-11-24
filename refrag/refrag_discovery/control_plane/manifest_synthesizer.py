from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.control_plane.storage import save_json
from refrag_discovery.paths import MANIFESTS_DIR
from refrag_discovery.registry import build_default_operator_query


# Arch §5 Discovery Loop (gap_finder → manifest_synthesizer → new manifests →
# gap_finder). The loop only closes if synthesized drafts actually land in the
# registry where ``operator_query`` and downstream operators can see them.
# Per arch §3.3 (Registry Write Access) the synthesizer is one of the
# authorised writers, alongside ``registry_writer``-mediated validation —
# until ``registry_writer`` ships we use the atomic ``save_json`` helper from
# the storage module (same atomicity guarantees: tempfile + ``os.replace``).
_DRAFT_VERSION = "0.1.0"


def _persist_proposed_manifest(
    manifest: dict[str, Any], *, manifests_dir: Path | None = None
) -> Path:
    """Write a synthesized draft manifest atomically under ``registry/manifests/proposed/``.

    Filename pattern mirrors the existing manifests: ``<operator>.v<version>.json``.
    The first version of a draft is ``0.1.0`` (pre-beta per arch Rule 5
    "Deterministic first, learned later"). Callers can bump via the
    manifest's own ``version`` field; absent that, ``_DRAFT_VERSION`` is used.

    Drafts land in a ``proposed/`` subdirectory rather than directly in
    ``manifests/`` because ``bootstrap_registry`` validates every ``*.json``
    in the top-level ``manifests/`` against the production manifest schema.
    Synthesized drafts are intentionally a subset of that schema (arch §5
    Discovery Loop: the synthesizer proposes, the manifest_validator /
    manual review process promotes to ``manifests/`` after vetting). Keeping
    drafts in a sibling directory keeps the loop closed without breaking
    registry bootstrap.
    """
    target_dir = (manifests_dir or MANIFESTS_DIR) / "proposed"
    op_id = str(manifest.get("operator_id") or "unnamed_draft")
    version = str(manifest.get("version") or _DRAFT_VERSION)
    # Mirror existing naming: ``spectral_chunker.v2.json`` uses the MAJOR
    # only. Draft manifests carry a full semver tag so multiple iterations of
    # the same composite don't overwrite each other.
    path = target_dir / f"{op_id}.v{version}.json"
    # Fix D / arch §3.3: route the registry write through ``registry_writer``
    # so each synthesized-manifest promotion lands in the audit log. ``kind``
    # is the manifests subdir tail so ``operator_state_path`` doesn't try to
    # apply its registry-vs-control-plane routing (proposed manifests live
    # under MANIFESTS_DIR/proposed/, a hand-built path that the writer
    # respects via the explicit ``target_dir`` resolution above). Local
    # import keeps the circular-dep risk contained.
    from refrag_discovery.registry.registry_writer import (
        _append_audit_entry,
        _sha256_hex,
        _utc_now_iso,
    )
    save_json(path, manifest)
    _append_audit_entry(
        {
            "ts": _utc_now_iso(),
            "kind": "manifests/proposed",
            "operator_id": op_id,
            "path": str(path),
            "payload_hash": _sha256_hex(manifest),
            "schema_validated": False,
            "schema_id": None,
            "intent": "manifest_synthesis_draft",
        }
    )
    return path


def synthesize_manifests(
    *,
    execution_logs: list[dict[str, Any]],
    min_occurrences: int = 5,
    min_success_rate: float = 0.9,
    synthesis_mode: str = "hybrid",
    n_vae_samples: int = 10,
    persist_drafts: bool = True,
    manifests_dir: Path | None = None,
) -> dict[str, Any]:
    query = build_default_operator_query()
    successful_sequences: list[tuple[str, ...]] = []
    pattern_evidence: list[dict[str, Any]] = []
    for log in execution_logs:
        stages = tuple(stage.get("operator_id") for stage in log.get("stages", []) if stage.get("operator_id"))
        if not stages:
            continue
        success_rate = 1.0 if log.get("discovery_recorded", True) else 0.0
        if success_rate >= min_success_rate:
            successful_sequences.append(stages)
            pattern_evidence.append(
                {
                    "run_id": log.get("run_id"),
                    "stages": list(stages),
                    "success_rate": success_rate,
                }
            )

    counts = Counter(successful_sequences)
    proposed_manifests = []
    confidence_per_proposal: list[float] = []
    inferred_contracts = []
    persisted_paths: list[str] = []
    for sequence, count in counts.items():
        if count < min_occurrences:
            continue
        operator_id = "_".join(sequence[:3])[:48] + "_composite"
        first_manifest = query.get_manifest(sequence[0])
        last_manifest = query.get_manifest(sequence[-1])
        confidence = round(min(0.99, count / max(min_occurrences, count)), 4)
        manifest = {
            "operator_id": operator_id,
            "operator_name": f"Synthesized {' '.join(sequence[:2]).title()} Chain",
            "description": f"Draft composite operator synthesized from repeated successful sequence: {' -> '.join(sequence)}.",
            "execution_class": first_manifest.get("execution_class", "runtime"),
            "operator_type": "template",
            "dependencies": [{"operator_id": stage_id, "required": True} for stage_id in sequence],
            # Stamp the draft version + maturity so consumers can tell drafts
            # apart from production manifests in the same directory.
            "version": _DRAFT_VERSION,
            "maturity": "experimental",
            "visibility": "internal",
            # Arch §7 minimum schema: inputs/outputs must be present even on
            # drafts. We copy from the head/tail of the sequence so the
            # gap_finder → synthesizer → gap_finder loop sees a well-formed
            # contract rather than a stub.
            "inputs": first_manifest.get("inputs", []),
            "outputs": last_manifest.get("outputs", []),
        }
        proposed_manifests.append(manifest)
        # Arch §5 Discovery Loop: writing the draft back to the registry is
        # how the loop closes. ``gap_finder`` re-reads ``registry/manifests/``
        # on its next pass and now sees the newly proposed coverage. The
        # ``persist_drafts=False`` knob lets tests exercise the synthesis
        # logic in isolation without leaving artefacts in the shared registry.
        if persist_drafts:
            try:
                persisted = _persist_proposed_manifest(manifest, manifests_dir=manifests_dir)
                persisted_paths.append(str(persisted))
            except OSError:
                # Persistence is best-effort: if the registry filesystem is
                # unavailable we still surface the proposal in the response so
                # callers see the result, but flag it so the loop doesn't
                # silently think it closed.
                persisted_paths.append("")
        else:
            persisted_paths.append("")
        confidence_per_proposal.append(confidence)
        inferred_contracts.append(
            {
                "operator_id": operator_id,
                "inputs": first_manifest.get("inputs", []),
                "outputs": last_manifest.get("outputs", []),
            }
        )

    vae_generated_compositions = []
    baseline_sequences = list(counts.keys()) or [("spectral_chunker", "spectral_chunk_encode", "operator_decoder")]
    for index in range(min(n_vae_samples, len(baseline_sequences))):
        seed = baseline_sequences[index % len(baseline_sequences)]
        vae_generated_compositions.append(
            {
                "seed_sequence": list(seed),
                "generated_sequence": list(seed[::-1] if synthesis_mode == "vae_generation" else seed),
            }
        )

    return with_production_readiness(
        "manifest_synthesizer",
        {
            "proposed_manifests": proposed_manifests,
            "pattern_evidence": pattern_evidence,
            "confidence_per_proposal": confidence_per_proposal,
            "vae_generated_compositions": vae_generated_compositions,
            "inferred_contracts": inferred_contracts,
            # Arch §5 Discovery Loop closure: paths of the drafts that were
            # persisted into ``registry/manifests/``. Empty string entries
            # indicate persistence-failed proposals so callers can flag the
            # loop as half-open.
            "persisted_manifest_paths": persisted_paths,
        },
    )
