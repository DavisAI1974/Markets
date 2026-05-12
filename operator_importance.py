"""F.1 Operator Importance Scoring -- Permutation importance with cross-architecture aggregation.

Computes operator importance via permutation importance across multiple
architectures (Conv, Recurrent, Attention, Tree, Hybrid). Cross-architecture
aggregation identifies universally important vs architecture-specific operators.

The 69-dim operator atlas has 51 continuous operators (indices 0-50) and
18 discontinuous argmax-based operators (indices 51-68). In HAR, all 18
discontinuous operators landed at importance weight = 0.10 (the floor),
confirming they were useless.

Pure numpy module -- no PyTorch dependency.

Usage:
    import sys
    sys.path.insert(0, r"E:\\operator_discovery")
    from modules.operator_importance import score_operators, score_operators_multi
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np


# ===== Inlined config (originally from operator_discovery/core/config.py) =====
# Cloned from operator_discovery/modules/operator_importance.py and adapted
# for Markets standalone use (removed sys.path hack, inlined ImportanceConfig).
@dataclass
class ImportanceConfig:
    """F.1 Operator Importance Scoring config (inlined for Markets standalone)."""
    operator_dim: int = 69
    n_continuous_ops: int = 51
    n_discontinuous_ops: int = 18
    n_permutations: int = 30
    n_architectures: int = 5
    architecture_names: List[str] = field(default_factory=lambda: [
        "Conv", "Recurrent", "Attention", "Tree", "Hybrid",
    ])
    importance_floor: float = 0.10
    consistency_threshold: float = 0.5
    universal_threshold: float = 0.8
    aggregation: str = "mean"
    data_dir: str = r"E:\operator_discovery\data"
    results_dir: str = r"E:\operator_discovery\results\importance"


# ---------------------------------------------------------------------------
#  Default metric
# ---------------------------------------------------------------------------

def _default_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Classification accuracy metric."""
    return float(np.mean(y_true == y_pred))


# =============================================
#  PermutationImportance
# =============================================

class PermutationImportance:
    """Permutation importance for operator atlas columns.

    For each of the 69 operator dimensions, the column is permuted
    ``n_permutations`` times, and the resulting accuracy drop relative
    to the baseline is recorded. The mean drop is the importance score.

    Supports single-architecture and multi-architecture evaluation.
    """

    def __init__(self, config: ImportanceConfig) -> None:
        self.config = config

    # -----------------------------------------------------------------
    #  Single architecture
    # -----------------------------------------------------------------

    def compute_single(
        self,
        operator_atlas: np.ndarray,
        labels: np.ndarray,
        predict_fn: Callable[[np.ndarray], np.ndarray],
        metric_fn: Optional[Callable[[np.ndarray, np.ndarray], float]] = None,
    ) -> np.ndarray:
        """Compute permutation importance for a single architecture.

        Parameters
        ----------
        operator_atlas : np.ndarray, shape (N, 69)
            Operator atlas feature matrix.
        labels : np.ndarray, shape (N,)
            Ground-truth labels.
        predict_fn : callable
            Takes (N, 69) array and returns predictions of shape (N,).
        metric_fn : callable or None
            Takes (y_true, y_pred) -> float. Higher is better.
            Defaults to classification accuracy.

        Returns
        -------
        importance : np.ndarray, shape (69,)
            Per-operator importance scores (baseline_metric - permuted_metric).
            Values are floored at ``config.importance_floor`` minimum of zero.
        """
        if metric_fn is None:
            metric_fn = _default_accuracy

        operator_atlas = np.asarray(operator_atlas, dtype=np.float64)
        labels = np.asarray(labels)
        n_samples, n_ops = operator_atlas.shape
        assert n_ops == self.config.operator_dim, (
            f"Expected {self.config.operator_dim} operator dims, got {n_ops}"
        )

        # Baseline score
        baseline_preds = predict_fn(operator_atlas)
        baseline_score = metric_fn(labels, baseline_preds)

        rng = np.random.default_rng()
        importance = np.zeros(n_ops, dtype=np.float64)

        for op_idx in range(n_ops):
            drops = np.zeros(self.config.n_permutations, dtype=np.float64)
            for perm_i in range(self.config.n_permutations):
                atlas_permuted = operator_atlas.copy()
                atlas_permuted[:, op_idx] = rng.permutation(atlas_permuted[:, op_idx])
                perm_preds = predict_fn(atlas_permuted)
                perm_score = metric_fn(labels, perm_preds)
                drops[perm_i] = baseline_score - perm_score
            importance[op_idx] = np.mean(drops)

        # Floor at zero -- negative importance means noise
        importance = np.maximum(importance, 0.0)

        return importance

    # -----------------------------------------------------------------
    #  Multi-architecture
    # -----------------------------------------------------------------

    def compute_multi_architecture(
        self,
        operator_atlas: np.ndarray,
        labels: np.ndarray,
        predict_fns: List[Callable[[np.ndarray], np.ndarray]],
        metric_fn: Optional[Callable[[np.ndarray, np.ndarray], float]] = None,
    ) -> Dict:
        """Compute importance across multiple architectures and aggregate.

        Parameters
        ----------
        operator_atlas : np.ndarray, shape (N, 69)
            Operator atlas feature matrix.
        labels : np.ndarray, shape (N,)
            Ground-truth labels.
        predict_fns : list of callable
            One predict_fn per architecture. Length should match
            ``config.n_architectures`` (or is used as-is).
        metric_fn : callable or None
            Shared metric across all architectures.

        Returns
        -------
        result : dict
            'per_architecture' : np.ndarray, shape (n_architectures, 69)
            'aggregated'       : np.ndarray, shape (69,)
            'consistency'      : np.ndarray, shape (69,)
            'universal_ops'    : list of int
            'architecture_specific' : dict mapping arch name -> list of int
        """
        n_archs = len(predict_fns)

        # Compute per-architecture importance
        per_arch = np.zeros((n_archs, self.config.operator_dim), dtype=np.float64)
        for arch_idx, pfn in enumerate(predict_fns):
            per_arch[arch_idx] = self.compute_single(
                operator_atlas, labels, pfn, metric_fn
            )

        # Aggregate across architectures
        aggregated = self._aggregate(per_arch)

        # Consistency scoring
        scorer = ConsistencyScorer(self.config)
        consistency = scorer.score(per_arch)

        # Classification
        classification = scorer.classify(aggregated, consistency)

        # Extract universal operators
        universal_ops = sorted([
            idx for idx, cls in classification.items()
            if cls == "universal"
        ])

        # Extract architecture-specific operators
        # An operator is architecture-specific for arch A if:
        #   - It is above the importance floor for arch A
        #   - Its cross-architecture consistency is below the consistency threshold
        #   - It is classified as 'architecture_specific'
        arch_specific_indices = sorted([
            idx for idx, cls in classification.items()
            if cls == "architecture_specific"
        ])

        architecture_specific: Dict[str, List[int]] = {}
        arch_names = self.config.architecture_names[:n_archs]
        for arch_idx, arch_name in enumerate(arch_names):
            specific_for_this_arch = []
            for op_idx in arch_specific_indices:
                # Only attribute to this arch if its importance is notably above floor
                if per_arch[arch_idx, op_idx] > self.config.importance_floor * 1.5:
                    specific_for_this_arch.append(op_idx)
            if specific_for_this_arch:
                architecture_specific[arch_name] = sorted(specific_for_this_arch)

        return {
            "per_architecture": per_arch,
            "aggregated": aggregated,
            "consistency": consistency,
            "universal_ops": universal_ops,
            "architecture_specific": architecture_specific,
        }

    # -----------------------------------------------------------------
    #  Aggregation helper
    # -----------------------------------------------------------------

    def _aggregate(self, per_arch: np.ndarray) -> np.ndarray:
        """Aggregate importance across architectures.

        Parameters
        ----------
        per_arch : np.ndarray, shape (n_architectures, 69)

        Returns
        -------
        aggregated : np.ndarray, shape (69,)
        """
        method = self.config.aggregation
        if method == "mean":
            return np.mean(per_arch, axis=0)
        elif method == "median":
            return np.median(per_arch, axis=0)
        elif method == "min":
            return np.min(per_arch, axis=0)
        else:
            raise ValueError(
                f"Unknown aggregation method '{method}'. "
                f"Expected 'mean', 'median', or 'min'."
            )


# =============================================
#  ConsistencyScorer
# =============================================

class ConsistencyScorer:
    """Cross-architecture consistency scoring for operator importance.

    Uses inverted coefficient of variation (CV) to measure agreement:
        consistency = 1 - CV = 1 - (std / mean)
    clamped to [0, 1]. High consistency means the operator has similar
    importance across all architectures.
    """

    def __init__(self, config: ImportanceConfig) -> None:
        self.config = config

    def score(self, importance_matrix: np.ndarray) -> np.ndarray:
        """Compute cross-architecture consistency for each operator.

        Parameters
        ----------
        importance_matrix : np.ndarray, shape (n_architectures, 69)
            Per-architecture importance scores.

        Returns
        -------
        consistency : np.ndarray, shape (69,)
            Consistency scores in [0, 1]. Higher = more consistent.
        """
        importance_matrix = np.asarray(importance_matrix, dtype=np.float64)
        n_arch, n_ops = importance_matrix.shape
        assert n_ops == self.config.operator_dim, (
            f"Expected {self.config.operator_dim} operator dims, got {n_ops}"
        )

        means = np.mean(importance_matrix, axis=0)
        stds = np.std(importance_matrix, axis=0, ddof=0)

        consistency = np.ones(n_ops, dtype=np.float64)
        # Where mean > 0, compute CV-based consistency
        nonzero = means > 1e-12
        cv = np.zeros(n_ops, dtype=np.float64)
        cv[nonzero] = stds[nonzero] / means[nonzero]
        consistency = 1.0 - cv

        # Clamp to [0, 1]
        consistency = np.clip(consistency, 0.0, 1.0)

        # For operators where all architectures give zero importance,
        # consistency is meaningless -- set to 0 (they are dead)
        all_zero = means < 1e-12
        consistency[all_zero] = 0.0

        return consistency

    def classify(
        self,
        importance: np.ndarray,
        consistency: np.ndarray,
    ) -> Dict[int, str]:
        """Classify each operator as 'universal', 'architecture_specific', or 'dead'.

        Parameters
        ----------
        importance : np.ndarray, shape (69,)
            Aggregated importance scores.
        consistency : np.ndarray, shape (69,)
            Cross-architecture consistency scores.

        Returns
        -------
        classification : dict
            Maps operator index (int) -> one of:
            - 'universal' : high importance AND high consistency
            - 'architecture_specific' : above importance floor but inconsistent
            - 'dead' : below importance floor
        """
        importance = np.asarray(importance, dtype=np.float64)
        consistency = np.asarray(consistency, dtype=np.float64)
        n_ops = len(importance)

        classification: Dict[int, str] = {}
        for idx in range(n_ops):
            if importance[idx] <= self.config.importance_floor:
                classification[idx] = "dead"
            elif consistency[idx] >= self.config.universal_threshold:
                classification[idx] = "universal"
            else:
                classification[idx] = "architecture_specific"

        return classification


# =============================================
#  ImportanceReport
# =============================================

class ImportanceReport:
    """Full importance analysis report generator.

    Orchestrates PermutationImportance and ConsistencyScorer to produce
    a comprehensive report of operator importance, consistency, ranking,
    and classification across continuous and discontinuous operator groups.
    """

    def __init__(self, config: ImportanceConfig) -> None:
        self.config = config
        self._pi = PermutationImportance(config)
        self._cs = ConsistencyScorer(config)

    def generate(
        self,
        operator_atlas: np.ndarray,
        labels: np.ndarray,
        predict_fns: List[Callable[[np.ndarray], np.ndarray]],
        metric_fn: Optional[Callable[[np.ndarray, np.ndarray], float]] = None,
    ) -> Dict:
        """Generate a full importance analysis report.

        Parameters
        ----------
        operator_atlas : np.ndarray, shape (N, 69)
        labels : np.ndarray, shape (N,)
        predict_fns : list of callable
            One per architecture.
        metric_fn : callable or None

        Returns
        -------
        report : dict
            'importance_scores'          : np.ndarray (69,) -- aggregated importance
            'consistency_scores'         : np.ndarray (69,) -- cross-arch consistency
            'ranking'                    : np.ndarray (69,) -- op indices sorted by importance desc
            'dead_operators'             : list of int -- indices below importance floor
            'continuous_importance'      : np.ndarray (51,) -- importance for ops 0-50
            'discontinuous_importance'   : np.ndarray (18,) -- importance for ops 51-68
            'classification'             : dict int -> str -- per-operator classification
            'per_architecture'           : np.ndarray (n_arch, 69)
            'universal_ops'              : list of int
            'architecture_specific'      : dict str -> list of int
        """
        # Run multi-architecture analysis
        multi_result = self._pi.compute_multi_architecture(
            operator_atlas, labels, predict_fns, metric_fn
        )

        importance_scores = multi_result["aggregated"]
        consistency_scores = multi_result["consistency"]

        # Ranking: sort by importance descending
        ranking = np.argsort(-importance_scores)

        # Dead operators: below importance floor
        dead_operators = sorted([
            int(idx) for idx in range(self.config.operator_dim)
            if importance_scores[idx] <= self.config.importance_floor
        ])

        # Split continuous vs discontinuous
        n_cont = self.config.n_continuous_ops
        continuous_importance = importance_scores[:n_cont].copy()
        discontinuous_importance = importance_scores[n_cont:].copy()

        # Classification
        classification = self._cs.classify(importance_scores, consistency_scores)

        return {
            "importance_scores": importance_scores,
            "consistency_scores": consistency_scores,
            "ranking": ranking,
            "dead_operators": dead_operators,
            "continuous_importance": continuous_importance,
            "discontinuous_importance": discontinuous_importance,
            "classification": classification,
            "per_architecture": multi_result["per_architecture"],
            "universal_ops": multi_result["universal_ops"],
            "architecture_specific": multi_result["architecture_specific"],
        }


# =============================================
#  Numpy boundary convenience functions
# =============================================

def score_operators(
    operator_atlas: np.ndarray,
    labels: np.ndarray,
    predict_fn: Callable[[np.ndarray], np.ndarray],
    config: Optional[ImportanceConfig] = None,
) -> Dict:
    """Score operator importance for a single architecture.

    Numpy boundary convenience function.

    Parameters
    ----------
    operator_atlas : np.ndarray, shape (N, 69)
    labels : np.ndarray, shape (N,)
    predict_fn : callable
        (N, 69) -> predictions (N,)
    config : ImportanceConfig or None
        Uses defaults if None.

    Returns
    -------
    result : dict
        'importance' : np.ndarray (69,)
        'ranking'    : np.ndarray -- sorted operator indices (most important first)
        'dead_operators' : list of int -- indices at or below importance floor
    """
    if config is None:
        config = ImportanceConfig()

    pi = PermutationImportance(config)
    importance = pi.compute_single(operator_atlas, labels, predict_fn)

    ranking = np.argsort(-importance)
    dead_operators = sorted([
        int(idx) for idx in range(config.operator_dim)
        if importance[idx] <= config.importance_floor
    ])

    return {
        "importance": importance,
        "ranking": ranking,
        "dead_operators": dead_operators,
    }


def score_operators_multi(
    operator_atlas: np.ndarray,
    labels: np.ndarray,
    predict_fns: List[Callable[[np.ndarray], np.ndarray]],
    config: Optional[ImportanceConfig] = None,
) -> Dict:
    """Score operator importance across multiple architectures.

    Numpy boundary convenience function. Returns the full analysis.

    Parameters
    ----------
    operator_atlas : np.ndarray, shape (N, 69)
    labels : np.ndarray, shape (N,)
    predict_fns : list of callable
        One predict_fn per architecture.
    config : ImportanceConfig or None
        Uses defaults if None.

    Returns
    -------
    result : dict
        Full analysis including:
        'importance_scores', 'consistency_scores', 'ranking',
        'dead_operators', 'continuous_importance',
        'discontinuous_importance', 'classification',
        'per_architecture', 'universal_ops', 'architecture_specific'
    """
    if config is None:
        config = ImportanceConfig()

    report = ImportanceReport(config)
    return report.generate(operator_atlas, labels, predict_fns)
