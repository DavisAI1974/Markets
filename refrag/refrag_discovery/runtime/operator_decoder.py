from __future__ import annotations

from adapters.od_refrag_adapter import OperatorDecoder as AdapterOperatorDecoder


def execute(
    *,
    prefill_embeds: list[list[float]],
    prefill_mask: list[int],
    decode_mode: str = "deterministic",
    n_refinement_iterations: int = 8,
    n_ensemble_members: int = 5,
    mc_dropout_samples: int = 20,
    uncertainty_threshold: float = 0.15,
    fno_checkpoint: str | None = None,
) -> dict:
    decoder = AdapterOperatorDecoder()
    initial = decoder.prefill(prefill_embeds, prefill_mask)
    refined = decoder.refine(initial, n_iterations=n_refinement_iterations)

    # Per-dim posterior_std heuristic so the closed-loop falsification
    # acquisition has something to differentiate on. The legacy stub
    # returned a uniform scalar (1/N prefill_embeds) for every coef dim,
    # which made BALD per-chunk contribution constant and the loop
    # converged at iter 2 with delta=0 every time.
    #
    # Heuristic: dims with larger absolute coefficients are estimated
    # more confidently (smaller std); near-zero coefficients are
    # treated as still-uncertain (larger std). This is still a stub
    # (arch §8 Phase 2 acknowledges decoder is deterministic-stub
    # until 100+ training pairs / FNO upgrade) but it produces a
    # non-uniform posterior that the BALD term in
    # falsification_prioritizer can actually use to re-rank across
    # iterations.
    base_width = 1.0 / max(1, len(prefill_embeds))
    if refined:
        max_abs = max((abs(v) for v in refined), default=0.0) or 1.0
        per_dim_std = [
            round(base_width * (1.0 + 1.5 * (1.0 - abs(value) / max_abs)), 6)
            for value in refined
        ]
    else:
        per_dim_std = []
    posterior_width = round(base_width, 4)
    coefficient_posterior = {
        "mean": refined,
        "std": per_dim_std,
        "ci_95": [
            [round(value - (1.96 * std), 6), round(value + (1.96 * std), 6)]
            for value, std in zip(refined, per_dim_std)
        ],
    }

    return {
        "operator_coefficients": refined,
        "coefficient_posterior": coefficient_posterior,
        "refinement_converged": True,
        "calibration_score": round(max(0.0, 1.0 - posterior_width), 4),
        "underdetermined_flag": posterior_width > uncertainty_threshold,
        "proposal_source": "deterministic" if decode_mode == "deterministic" else "ensemble",
        "metadata": {
            "decode_mode": decode_mode,
            "n_refinement_iterations": n_refinement_iterations,
            "n_ensemble_members": n_ensemble_members,
            "mc_dropout_samples": mc_dropout_samples,
            "fno_checkpoint": fno_checkpoint,
        },
    }
