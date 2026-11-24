"""Runtime operators that execute manifest-driven discovery pipelines."""

__all__ = ["OperatorOrchestrator", "execute_pipeline"]


def __getattr__(name: str):
    if name == "OperatorOrchestrator":
        from refrag_discovery.runtime.operator_orchestrator import OperatorOrchestrator

        return OperatorOrchestrator
    if name == "execute_pipeline":
        from refrag_discovery.runtime.od_spectral_retrieval_pipeline import execute_pipeline

        return execute_pipeline
    raise AttributeError(name)
