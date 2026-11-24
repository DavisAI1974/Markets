from __future__ import annotations

from refrag_discovery.runtime.operator_orchestrator import OperatorOrchestrator


def execute_pipeline(
    *,
    sources: dict[str, list[float]],
    query_mode: str,
    candidate: dict | None = None,
    target_frequencies: list[float] | None = None,
    target_energy: float = 1.0,
    top_k: int = 8,
    expand_budget: int = 4,
    orchestrator: OperatorOrchestrator | None = None,
    termination_config: dict | None = None,
    domain: str = "unknown",
) -> dict:
    orchestrator = orchestrator or OperatorOrchestrator()
    return orchestrator.execute(
        pipeline_id="od_spectral_retrieval_pipeline",
        data_sources=sources,
        query={
            "query_mode": query_mode,
            "candidate": candidate,
            "target_frequencies": target_frequencies or [],
            "target_energy": target_energy,
            "top_k": top_k,
            "expand_budget": expand_budget,
        },
        termination_config=termination_config,
        domain=domain,
    )
