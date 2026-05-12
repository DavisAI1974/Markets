"""Module D.2: Sensitivity Engine -- Finite-difference Jacobian analysis.

Computes sensitivity of an operator atlas (69-dim vector) to perturbation
parameters (8-dim) using central finite-difference Jacobians.

The FNO surrogate approach was attempted and abandoned because 18 discontinuous
argmax operators break the continuity assumption required by neural surrogates.
This module uses pure numpy finite differences instead, which correctly captures
both continuous and discontinuous operator responses.

Usage::

    import sys
    sys.path.insert(0, r"E:\\operator_discovery")
    from core.config import SensitivityConfig
    from modules.sensitivity_engine import SensitivityEngine

    config = SensitivityConfig()
    engine = SensitivityEngine(config, extract_fn=my_operator_extractor)
    J = engine.compute_jacobian(signal, theta)
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import linregress


# ===== Inlined config (originally from operator_discovery/core/config.py) =====
# Cloned from operator_discovery/modules/sensitivity_engine.py and adapted
# for Markets standalone use (removed sys.path hack, inlined SensitivityConfig).
@dataclass
class SensitivityConfig:
    """D.2 Sensitivity Engine config (inlined for Markets standalone)."""
    operator_dim: int = 69
    n_continuous_ops: int = 51
    n_discontinuous_ops: int = 18
    n_perturbations: int = 8
    perturbation_names: List[str] = field(default_factory=lambda: [
        "stride_frequency", "stride_amplitude", "arm_swing",
        "gait_asymmetry", "posture_lean", "movement_smoothness",
        "speed_scaling", "vertical_bounce",
    ])
    epsilon: float = 0.01
    perturbation_scale: float = 0.1
    linearity_threshold: float = 0.95
    n_linearity_samples: int = 10
    discontinuity_threshold: float = 5.0
    data_dir: str = r"E:\operator_discovery\data"
    results_dir: str = r"E:\operator_discovery\results\sensitivity"


class SensitivityEngine:
    """Finite-difference Jacobian engine for operator atlas sensitivity.

    Computes how each of the 69 operator atlas dimensions responds to
    perturbations in each of the 8 perturbation parameters. Uses central
    finite differences for accuracy, with special handling for the 18
    discontinuous (argmax-based) operators.

    Parameters
    ----------
    config : SensitivityConfig
        Configuration dataclass with epsilon, thresholds, and dimensions.
    extract_fn : callable
        Function with signature ``(signal: np.ndarray, theta: np.ndarray) -> np.ndarray``
        that returns a (69,) operator atlas vector given a signal and perturbation
        parameter vector theta.
    """

    def __init__(self, config: SensitivityConfig, extract_fn: Callable) -> None:
        self.config = config
        self.extract_fn = extract_fn
        self.operator_dim = config.operator_dim
        self.n_perturbations = config.n_perturbations
        self.epsilon = config.epsilon

    def compute_jacobian(
        self, signal: np.ndarray, theta: np.ndarray
    ) -> np.ndarray:
        """Compute the (69, 8) Jacobian via central finite differences.

        For each perturbation dimension k, perturbs theta[k] by +/- epsilon,
        calls extract_fn on the perturbed signal, and computes the central
        difference approximation:

            J[:, k] = (f(theta + eps_k) - f(theta - eps_k)) / (2 * eps)

        Parameters
        ----------
        signal : np.ndarray
            Input signal array passed to extract_fn. Shape depends on domain
            (e.g. (channels, length) or (length,)).
        theta : np.ndarray
            Perturbation parameter vector of shape (8,).

        Returns
        -------
        np.ndarray
            Jacobian matrix of shape (69, 8).
        """
        theta = np.asarray(theta, dtype=np.float64)
        eps = self.epsilon
        J = np.zeros((self.operator_dim, self.n_perturbations), dtype=np.float64)

        for k in range(self.n_perturbations):
            theta_plus = theta.copy()
            theta_minus = theta.copy()
            theta_plus[k] += eps
            theta_minus[k] -= eps

            atlas_plus = np.asarray(
                self.extract_fn(signal, theta_plus), dtype=np.float64
            )
            atlas_minus = np.asarray(
                self.extract_fn(signal, theta_minus), dtype=np.float64
            )

            J[:, k] = (atlas_plus - atlas_minus) / (2.0 * eps)

        return J

    def compute_jacobian_batch(
        self, signals: np.ndarray, thetas: np.ndarray
    ) -> np.ndarray:
        """Compute Jacobians for a batch of (signal, theta) pairs.

        Parameters
        ----------
        signals : np.ndarray
            Batch of signals. First dimension is batch size N.
            Shape: (N, ...) where ... matches the signal shape expected by extract_fn.
        thetas : np.ndarray
            Batch of perturbation vectors, shape (N, 8).

        Returns
        -------
        np.ndarray
            Batch of Jacobian matrices, shape (N, 69, 8).
        """
        N = signals.shape[0]
        J_batch = np.zeros(
            (N, self.operator_dim, self.n_perturbations), dtype=np.float64
        )

        for i in range(N):
            J_batch[i] = self.compute_jacobian(signals[i], thetas[i])

        return J_batch

    def detect_linearity(
        self,
        signal: np.ndarray,
        theta: np.ndarray,
        perturbation_idx: int,
    ) -> Dict:
        """Test if operator response is linear w.r.t. a single perturbation.

        Samples n_linearity_samples points along the perturbation axis
        (centered at theta[perturbation_idx], spanning +/- perturbation_scale),
        evaluates the operator atlas at each point, fits a linear model per
        operator dimension, and reports R-squared and slope.

        Parameters
        ----------
        signal : np.ndarray
            Input signal array.
        theta : np.ndarray
            Base perturbation parameter vector, shape (8,).
        perturbation_idx : int
            Which perturbation dimension (0..7) to test for linearity.

        Returns
        -------
        dict
            Keys:
            - 'r_squared': np.ndarray of shape (69,) with R^2 per operator.
            - 'slopes': np.ndarray of shape (69,) with linear slope per operator.
            - 'intercepts': np.ndarray of shape (69,) with intercept per operator.
            - 'is_linear': np.ndarray of shape (69,) bool, True if R^2 >= threshold.
            - 'n_linear': int, count of linear operators.
            - 'perturbation_idx': int, which perturbation was tested.
            - 'perturbation_name': str, name of the perturbation tested.
        """
        theta = np.asarray(theta, dtype=np.float64)
        n_samples = self.config.n_linearity_samples
        scale = self.config.perturbation_scale
        k = perturbation_idx

        # Sample points along perturbation axis
        offsets = np.linspace(-scale, scale, n_samples)
        atlases = np.zeros((n_samples, self.operator_dim), dtype=np.float64)

        for i, offset in enumerate(offsets):
            theta_i = theta.copy()
            theta_i[k] += offset
            atlases[i] = np.asarray(
                self.extract_fn(signal, theta_i), dtype=np.float64
            )

        # Fit linear model per operator dimension
        r_squared = np.zeros(self.operator_dim, dtype=np.float64)
        slopes = np.zeros(self.operator_dim, dtype=np.float64)
        intercepts = np.zeros(self.operator_dim, dtype=np.float64)

        for d in range(self.operator_dim):
            y = atlases[:, d]
            # If all values are identical, R^2 is undefined; treat as perfectly
            # linear (zero slope, perfect fit to constant).
            if np.ptp(y) < 1e-15:
                r_squared[d] = 1.0
                slopes[d] = 0.0
                intercepts[d] = y[0]
            else:
                result = linregress(offsets, y)
                r_squared[d] = result.rvalue ** 2
                slopes[d] = result.slope
                intercepts[d] = result.intercept

        is_linear = r_squared >= self.config.linearity_threshold

        return {
            "r_squared": r_squared,
            "slopes": slopes,
            "intercepts": intercepts,
            "is_linear": is_linear,
            "n_linear": int(np.sum(is_linear)),
            "perturbation_idx": k,
            "perturbation_name": self.config.perturbation_names[k],
        }

    def detect_discontinuities(
        self, signal: np.ndarray, theta: np.ndarray
    ) -> Dict:
        """Find operators with discontinuous responses to perturbations.

        Computes the Jacobian at multiple theta values along each perturbation
        axis. Operators where the gradient jumps by more than
        ``discontinuity_threshold`` times the median gradient are flagged as
        discontinuous.

        Parameters
        ----------
        signal : np.ndarray
            Input signal array.
        theta : np.ndarray
            Base perturbation parameter vector, shape (8,).

        Returns
        -------
        dict
            Keys:
            - 'discontinuous_ops': np.ndarray of unique operator indices flagged.
            - 'gradient_ratios': np.ndarray of shape (69, 8) with max gradient
              jump ratio per (operator, perturbation) pair.
            - 'n_discontinuous': int, count of discontinuous operators.
            - 'flags_per_perturbation': np.ndarray of shape (8,) counting how
              many operators are discontinuous per perturbation.
        """
        theta = np.asarray(theta, dtype=np.float64)
        scale = self.config.perturbation_scale
        n_samples = self.config.n_linearity_samples
        threshold = self.config.discontinuity_threshold

        gradient_ratios = np.zeros(
            (self.operator_dim, self.n_perturbations), dtype=np.float64
        )

        for k in range(self.n_perturbations):
            # Evaluate Jacobian at multiple points along perturbation axis k
            offsets = np.linspace(-scale, scale, n_samples)
            jacobians_k = np.zeros(
                (n_samples, self.operator_dim), dtype=np.float64
            )

            for i, offset in enumerate(offsets):
                theta_shifted = theta.copy()
                theta_shifted[k] += offset
                J_local = self.compute_jacobian(signal, theta_shifted)
                jacobians_k[i] = J_local[:, k]

            # For each operator, compute the max gradient jump ratio
            for d in range(self.operator_dim):
                grad_values = jacobians_k[:, d]
                abs_diffs = np.abs(np.diff(grad_values))
                median_grad = np.median(np.abs(grad_values))

                if median_grad < 1e-15:
                    # Near-zero gradients everywhere: check if any diff is large
                    max_diff = np.max(abs_diffs) if abs_diffs.size > 0 else 0.0
                    # Use absolute jump vs epsilon as fallback
                    gradient_ratios[d, k] = (
                        max_diff / self.epsilon if max_diff > 1e-15 else 0.0
                    )
                else:
                    gradient_ratios[d, k] = (
                        np.max(abs_diffs) / median_grad
                        if abs_diffs.size > 0
                        else 0.0
                    )

        # Flag operators where any perturbation shows a jump above threshold
        is_discontinuous = np.any(gradient_ratios > threshold, axis=1)
        discontinuous_ops = np.where(is_discontinuous)[0]

        flags_per_perturbation = np.sum(gradient_ratios > threshold, axis=0)

        return {
            "discontinuous_ops": discontinuous_ops,
            "gradient_ratios": gradient_ratios,
            "n_discontinuous": int(discontinuous_ops.shape[0]),
            "flags_per_perturbation": flags_per_perturbation,
        }

    def sensitivity_profile(
        self, signals: np.ndarray, thetas: np.ndarray
    ) -> Dict:
        """Full sensitivity analysis over a batch of signals.

        Computes the batch Jacobian, then derives:
        - Mean and std sensitivity per operator across the batch
        - Linearity scores for each (perturbation) on the first signal
        - Discontinuity flags on the first signal

        Parameters
        ----------
        signals : np.ndarray
            Batch of signals, shape (N, ...).
        thetas : np.ndarray
            Batch of perturbation vectors, shape (N, 8).

        Returns
        -------
        dict
            Keys:
            - 'jacobian_batch': np.ndarray, shape (N, 69, 8).
            - 'mean_sensitivity': np.ndarray, shape (69, 8). Mean |J| over batch.
            - 'std_sensitivity': np.ndarray, shape (69, 8). Std |J| over batch.
            - 'operator_total_sensitivity': np.ndarray, shape (69,). Sum across
              perturbations of mean |J|.
            - 'perturbation_total_sensitivity': np.ndarray, shape (8,). Sum across
              operators of mean |J|.
            - 'linearity': list of dicts, one per perturbation dimension.
            - 'discontinuities': dict from detect_discontinuities.
            - 'top_sensitive_operators': np.ndarray, operator indices sorted by
              total sensitivity (descending).
            - 'top_sensitive_perturbations': np.ndarray, perturbation indices
              sorted by total impact (descending).
        """
        # Batch Jacobian
        J_batch = self.compute_jacobian_batch(signals, thetas)
        abs_J = np.abs(J_batch)

        mean_sensitivity = np.mean(abs_J, axis=0)  # (69, 8)
        std_sensitivity = np.std(abs_J, axis=0)  # (69, 8)

        operator_total = np.sum(mean_sensitivity, axis=1)  # (69,)
        perturbation_total = np.sum(mean_sensitivity, axis=0)  # (8,)

        # Linearity analysis on the first sample
        linearity_results = []
        for k in range(self.n_perturbations):
            lin = self.detect_linearity(signals[0], thetas[0], k)
            linearity_results.append(lin)

        # Discontinuity analysis on the first sample
        disc_results = self.detect_discontinuities(signals[0], thetas[0])

        return {
            "jacobian_batch": J_batch,
            "mean_sensitivity": mean_sensitivity,
            "std_sensitivity": std_sensitivity,
            "operator_total_sensitivity": operator_total,
            "perturbation_total_sensitivity": perturbation_total,
            "linearity": linearity_results,
            "discontinuities": disc_results,
            "top_sensitive_operators": np.argsort(operator_total)[::-1],
            "top_sensitive_perturbations": np.argsort(perturbation_total)[::-1],
        }


# =============================================
#  Standalone utility functions
# =============================================


def compute_normalized_jacobian(
    J: np.ndarray,
    operator_atlas: np.ndarray,
    labels: np.ndarray,
) -> np.ndarray:
    """Normalize Jacobian by within-class natural operator variation.

    For each class and each operator dimension, computes the standard deviation
    of that operator across samples in the class. Each Jacobian entry is then
    divided by the corresponding per-class per-operator std, so that sensitivity
    is measured in units of "natural variation."

    Operators with zero variance within a class (constant across all samples in
    that class) receive zero normalized sensitivity, since any perturbation
    effect on a zero-variance operator is undetermined relative to its natural
    variation.

    Parameters
    ----------
    J : np.ndarray
        Jacobian batch, shape (N, 69, 8).
    operator_atlas : np.ndarray
        Operator atlas values, shape (N, 69).
    labels : np.ndarray
        Integer class labels, shape (N,).

    Returns
    -------
    np.ndarray
        Normalized Jacobian, shape (N, 69, 8).
    """
    J = np.asarray(J, dtype=np.float64)
    operator_atlas = np.asarray(operator_atlas, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)

    N, op_dim, n_pert = J.shape
    J_norm = np.zeros_like(J)

    unique_labels = np.unique(labels)

    # Precompute per-class, per-operator standard deviations
    class_std = np.zeros((len(unique_labels), op_dim), dtype=np.float64)
    label_to_idx = {}
    for idx, c in enumerate(unique_labels):
        label_to_idx[int(c)] = idx
        mask = labels == c
        if np.sum(mask) > 1:
            class_std[idx] = np.std(operator_atlas[mask], axis=0, ddof=0)
        # else: remains 0 (single sample => zero variance)

    # Normalize each sample's Jacobian row
    for i in range(N):
        c_idx = label_to_idx[int(labels[i])]
        std_vec = class_std[c_idx]  # (op_dim,)
        for d in range(op_dim):
            if std_vec[d] > 1e-15:
                J_norm[i, d, :] = J[i, d, :] / std_vec[d]
            # else: zero-variance operator => J_norm stays 0

    return J_norm


def rank_perturbations(jacobian: np.ndarray) -> Dict:
    """Rank the 8 perturbation dimensions by total impact on the operator atlas.

    Impact is measured as the mean absolute Jacobian entry summed across all
    operators for each perturbation.

    Parameters
    ----------
    jacobian : np.ndarray
        Jacobian batch, shape (N, 69, 8).

    Returns
    -------
    dict
        Keys:
        - 'ranking': np.ndarray of shape (8,), perturbation indices sorted
          by decreasing total impact.
        - 'scores': np.ndarray of shape (8,), total impact score per perturbation
          (sorted in the same order as the original perturbation indices, not
          by ranking).
        - 'per_operator_ranking': np.ndarray of shape (69, 8), for each operator,
          the perturbation indices sorted by decreasing impact on that operator.
    """
    jacobian = np.asarray(jacobian, dtype=np.float64)

    # Mean absolute Jacobian across the batch => (69, 8)
    mean_abs = np.mean(np.abs(jacobian), axis=0)

    # Total impact per perturbation: sum across operators => (8,)
    scores = np.sum(mean_abs, axis=0)

    # Global ranking: sort perturbation indices by descending score
    ranking = np.argsort(scores)[::-1]

    # Per-operator ranking: for each operator, sort perturbations by impact
    per_operator_ranking = np.zeros(
        (mean_abs.shape[0], mean_abs.shape[1]), dtype=np.int64
    )
    for d in range(mean_abs.shape[0]):
        per_operator_ranking[d] = np.argsort(mean_abs[d])[::-1]

    return {
        "ranking": ranking,
        "scores": scores,
        "per_operator_ranking": per_operator_ranking,
    }
