"""Deterministic, conservative adaptive locality research engine."""
from .core import (Observation, MetricContract, LocalityConfig, LocalityEngine,
                   Decision, Diagnostic, LocalityError, finite_cauchy,
                   gaussian_kernel, graph_neumann_residual)
from .ledger import DecisionLedger, ScientificGate, JobReceipt
__all__ = ["Observation","MetricContract","LocalityConfig","LocalityEngine",
           "Decision","Diagnostic","LocalityError","finite_cauchy",
           "gaussian_kernel","graph_neumann_residual","DecisionLedger",
           "ScientificGate","JobReceipt"]
