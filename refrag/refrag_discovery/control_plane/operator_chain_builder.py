from __future__ import annotations

from typing import Any

from refrag_discovery.control_plane.production_readiness import with_production_readiness
from refrag_discovery.control_plane.operator_composability_scorer import score_operator_composability
from refrag_discovery.control_plane.operator_gap_finder import analyze_operator_gaps
from refrag_discovery.registry import build_default_operator_query


def _benchmark_summary_score(record: dict[str, Any]) -> float:
    """Pick the overall_score (or health_score fallback) from a lineage
    version record's persisted performance_benchmark.summary block.

    Lineage records are written by ``track_operator_lineage`` and store the
    benchmark passed in at registration time. We use those scores to decide
    which version is "best for production" for each chain stage.
    """
    bench = record.get("performance_benchmark") or {}
    summary = bench.get("summary") or {}
    for key in ("overall_score", "health_score"):
        value = summary.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _lineage_summary_for_step(lineage_state: dict[str, Any] | None) -> dict[str, Any]:
    """Extract per-stage version info from a lineage state snapshot.

    Honors arch §6's declared dep on operator_lineage_tracker: chain_builder
    surfaces ``latest_version`` and ``current_best_version`` per stage so a
    downstream orchestrator (arch §2: "queries the lineage tracker for best
    version per slot") doesn't have to re-derive them.

    ``lineage_state`` is the on-disk record produced by
    ``track_operator_lineage`` (``{operator_id, versions, history,
    latest_version}``). Returns the empty-baseline dict when no lineage is
    known so chain_builder degrades gracefully on first-ever runs.
    """
    if not lineage_state:
        return {
            "latest_version": None,
            "current_best_version": None,
            "lineage_known": False,
        }
    latest_version = lineage_state.get("latest_version")
    versions = dict(lineage_state.get("versions") or {})
    best_version = (
        max(versions, key=lambda v: _benchmark_summary_score(versions[v]))
        if versions
        else None
    )
    return {
        "latest_version": latest_version,
        "current_best_version": best_version or latest_version,
        "lineage_known": bool(latest_version or versions),
    }


def build_operator_chain(
    *,
    task_objective: str,
    available_operators: list[str] | None = None,
    constraints: dict[str, Any] | None = None,
    optimization_target: str = "accuracy",
    search_mode: str = "mcts",
    mcts_simulations: int = 200,
    lineage_snapshot: dict[str, dict[str, Any]] | None = None,
    task_meta_learner_recommendation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan a multi-step operator chain for the given task objective.

    Per arch §6 dependency table this operator depends on:
      - ``operator_composability_scorer`` — called per adjacent pair below
      - ``operator_gap_finder`` — called when ``constraints.required_operators``
        names ops not present in the resolved chain
      - ``operator_lineage_tracker`` — consumed via the ``lineage_snapshot``
        kwarg; per-stage version info is attached to each chain step so the
        orchestrator can prefer the production-best version per slot

    Per arch §6 ``feeds-in`` table, ``task_meta_learner`` feeds this operator.
    Its recommendation (``recommended_configuration`` + ``confidence``) rides
    along via ``task_meta_learner_recommendation`` and is surfaced both as
    metadata and as a confidence-modulated ``task_meta_learner_modulated_score``
    next to the raw composability-derived ``chain_score``.

    Both new kwargs are optional. Passing ``None`` keeps the legacy behavior;
    passing the snapshots makes the arch-§6 deps explicit and observable.
    """
    query = build_default_operator_query()
    constraints = dict(constraints or {})
    available = available_operators or [manifest["operator_id"] for manifest in query.list_manifests()]
    lineage_snapshot = dict(lineage_snapshot or {})

    search_results = query.search(text=task_objective, top_k=max(5, len(available)))
    selected = [item.operator_id for item in search_results if item.operator_id in available]
    chain_ids: list[str]
    if "od_spectral_retrieval_pipeline" in selected or "discovery" in task_objective.lower():
        chain_ids = query.resolve_pipeline_stages("od_spectral_retrieval_pipeline")
    else:
        max_chain_length = int(constraints.get("max_chain_length", 4))
        chain_ids = selected[:max_chain_length]

    required = [str(item) for item in constraints.get("required_operators", [])]
    forbidden = {str(item) for item in constraints.get("forbidden_operators", [])}
    missing_capabilities = [operator_id for operator_id in required if operator_id not in chain_ids]
    chain_ids = [operator_id for operator_id in chain_ids if operator_id not in forbidden]

    chain = []
    pair_scores: list[float] = []
    for index, operator_id in enumerate(chain_ids, start=1):
        manifest = query.get_manifest(operator_id)
        step = {
            "stage": index,
            "operator_id": operator_id,
            "execution_class": manifest.get("execution_class"),
            "operator_type": manifest.get("operator_type"),
            "inputs": [item.get("type") for item in manifest.get("inputs", [])],
            "outputs": [item.get("type") for item in manifest.get("outputs", [])],
            "lineage": _lineage_summary_for_step(lineage_snapshot.get(operator_id)),
        }
        if chain:
            score = score_operator_composability(operator_a=chain[-1]["operator_id"], operator_b=operator_id)
            step["incoming_score"] = score["composability_score"]
            pair_scores.append(score["composability_score"])
        chain.append(step)

    chain_score = round(sum(pair_scores) / max(1, len(pair_scores)), 4) if pair_scores else 0.75
    if optimization_target == "speed":
        chain_score = round(max(0.0, chain_score - 0.05), 4)
    elif optimization_target == "coverage":
        chain_score = round(min(1.0, chain_score + 0.05), 4)

    # Honor arch §6 ``task_meta_learner → chain_builder`` feed: blend the
    # composability-derived ``chain_score`` with the meta-learner's
    # ``confidence`` toward a neutral 0.5 baseline. High confidence (→1.0)
    # leaves chain_score unchanged; low confidence (→0.0) regresses it toward
    # 0.5, signalling that the meta-learner has no learned guidance yet
    # (Rule 5 deterministic baseline). The raw ``chain_score`` is preserved
    # for audit; consumers can pick which to use.
    meta_input: dict[str, Any] = {}
    modulated_score = chain_score
    if task_meta_learner_recommendation:
        meta_input = dict(task_meta_learner_recommendation)
        rec = dict(meta_input.get("recommended_configuration") or {})
        confidence = rec.get("confidence")
        if isinstance(confidence, (int, float)) and 0.0 <= float(confidence) <= 1.0:
            c = float(confidence)
            modulated_score = round(chain_score * c + 0.5 * (1.0 - c), 4)

    alternatives = []
    for candidate in search_results[:3]:
        if candidate.operator_id not in chain_ids and candidate.operator_id in available:
            alternatives.append(
                {
                    "chain": [{"operator_id": candidate.operator_id}],
                    "score": round(candidate.score, 4),
                }
            )

    if missing_capabilities:
        gap_report = analyze_operator_gaps(
            registry_snapshot=[query.get_manifest(operator_id) for operator_id in available],
            known_tasks=[task_objective],
        )
        missing_capabilities.extend(item["operator_id"] for item in gap_report.get("recommendations", []))

    stages_with_lineage = sum(1 for step in chain if step["lineage"]["lineage_known"])

    return with_production_readiness(
        "operator_chain_builder",
        {
            "chain": chain,
            "chain_score": chain_score,
            "task_meta_learner_modulated_score": modulated_score,
            "alternative_chains": alternatives,
            "missing_capabilities": missing_capabilities,
            "search_metadata": {
                "search_mode": search_mode,
                "mcts_simulations": mcts_simulations,
                "optimization_target": optimization_target,
            },
            "lineage_summary": {
                "stages_with_lineage": stages_with_lineage,
                "total_stages": len(chain),
            },
            "task_meta_learner_input": meta_input,
        },
    )
