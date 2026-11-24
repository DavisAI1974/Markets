from __future__ import annotations

import math

from refrag_discovery.runtime.types import RetrievedChunk


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _downsample_to(values: list[float], target_len: int) -> list[float]:
    """Average-pool a longer list down to ``target_len`` so dim-mismatched
    posteriors can be aligned with chunk embeddings without throwing away
    structure."""
    n = len(values)
    if n == 0 or target_len <= 0:
        return [0.0] * target_len
    if n == target_len:
        return list(values)
    if n < target_len:
        return list(values) + [0.0] * (target_len - n)
    out: list[float] = []
    span = n / target_len
    for i in range(target_len):
        lo = int(i * span)
        hi = max(lo + 1, int((i + 1) * span))
        segment = values[lo:hi]
        if not segment:
            out.append(0.0)
        else:
            out.append(sum(segment) / len(segment))
    return out


def _bald_posterior_contribution(
    chunk_embedding: list[float],
    operator_posterior: dict | None,
) -> float:
    """BALD-style per-chunk posterior-uncertainty alignment.

    For a given chunk's embedding ``e`` and the decoder's coefficient
    posterior ``std`` vector ``s`` (one entry per coefficient dim), the
    contribution is the dot product of ``|e|`` against ``s`` projected to
    ``len(e)``. Chunks whose embedding components fall on coefficient
    dimensions where the posterior is widest get the highest contribution,
    matching the v2 manifest's ``acquisition_function='bald'`` intent.

    Returns 0.0 on the first closed-loop iteration where the posterior has
    not yet been computed — falsification falls back to divergence ranking
    per arch §8 Phase 2 ('Divergence ranking first. MINE/BALD after
    Bayesian decoder.').
    """
    if not operator_posterior or not chunk_embedding:
        return 0.0
    stds = list(operator_posterior.get("std") or [])
    if not stds:
        return 0.0
    projected_stds = _downsample_to(stds, len(chunk_embedding))
    raw = sum(abs(e) * s for e, s in zip(chunk_embedding, projected_stds))
    # Normalize to a comparable scale with the existing variance/signature
    # terms (which are bounded around [0, 0.35] and [0, 1]). Average-divide
    # by the embedding length so this stays in the same magnitude band.
    return raw / max(1, len(chunk_embedding))


def execute(
    *,
    candidate_operator: dict,
    dataset_chunks: list[RetrievedChunk],
    falsification_mode: str = "info_theoretic",
    operator_posterior: dict | None = None,
    top_k: int = 10,
    acquisition_function: str = "bald",
) -> dict:
    signature = [float(value) for value in candidate_operator.get("spectral_signature", [])]
    ranked: list[RetrievedChunk] = []
    contractions: list[float] = []

    for rank, hit in enumerate(dataset_chunks):
        variance = _variance(hit.chunk.values)
        signature_match = 0.0
        if signature:
            signature_match = sum(
                abs(left * right)
                for left, right in zip(signature[: len(hit.embedding)], hit.embedding[: len(signature)])
            ) / max(1, min(len(signature), len(hit.embedding)))
        # BALD acquisition: when the decoder's coefficient posterior is
        # available (iteration N+1 of the closed loop), weight each chunk
        # by how much it overlaps the high-uncertainty coefficient dims.
        # This is what makes the Falsification Loop converge to different
        # rankings across iterations instead of producing the same prefill
        # forever.
        #
        # TODO(post-FNO-upgrade): the 0.20 weight was sized against the
        # deterministic stub decoder (arch §8 "deterministic first; FNO after
        # 100+ training pairs"). With the stub, posterior_contribution is
        # typically ~0.04 per chunk, so the BALD term contributes only ~0.008
        # — variance (capped at 0.35) dominates ranking 40×. Once the FNO
        # decoder is online (per the arch §8 Phase 2 upgrade plan), recalibrate
        # this weight against real posterior variance. Until then the loop
        # IS closed (arch §5) but the BALD term's effective magnitude is
        # decorative. Tracked in BUGS_DEFERRED_FOR_DISCUSSION_20260525.md
        # item G.
        posterior_contribution = _bald_posterior_contribution(
            hit.embedding, operator_posterior
        )
        info_gain = round(
            hit.score
            + min(0.35, variance)
            + (0.15 * signature_match)
            + (0.20 * posterior_contribution),
            4,
        )
        ranked.append(
            RetrievedChunk(
                chunk=hit.chunk,
                embedding=hit.embedding,
                score=hit.score,
                rank=rank,
                information_gain=info_gain,
            )
        )
        contractions.append(round(min(1.0, info_gain / 2.0), 4))

    ranked.sort(key=lambda item: item.information_gain, reverse=True)
    top_ranked = ranked[:top_k]
    avg_gain = sum(item.information_gain for item in top_ranked) / max(1, len(top_ranked))

    return {
        "falsification_targets": [
            {
                "chunk_id": item.chunk.chunk_id,
                "source_id": item.chunk.source_id,
                "score": item.score,
                "information_gain": item.information_gain,
            }
            for item in top_ranked
        ],
        "expected_posterior_contraction": contractions[: len(top_ranked)],
        "priority_validation_plan": [
            f"Inspect {item.chunk.source_id}:{item.chunk.window_start}-{item.chunk.window_end}"
            for item in top_ranked
        ],
        "estimated_chunks_to_resolution": max(1, math.ceil(1.0 / max(0.05, avg_gain))),
        "estimated_falsification_probability": round(max(0.0, 1.0 - avg_gain / 2.0), 4),
        "ranked_chunks": top_ranked,
        "metadata": {
            "falsification_mode": falsification_mode,
            "acquisition_function": acquisition_function,
            "posterior_available": operator_posterior is not None,
        },
    }
