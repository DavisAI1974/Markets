"""
OD Recovery Engine — READ-ONLY during autoresearch experiments.

Recovers the Lindblad generator (Liouvillian) L from 2-level quantum system
density matrix trajectories. The discovered L satisfies:

    rho(t) = unvec( expm(L * t) @ vec(rho(0)) )

Model: 4x4 complex Liouvillian for a 2x2 density matrix (spin-boson system).
Method: Matrix logarithm with multi-timestep averaging, or least-squares.

All tunable parameters are read from od_config.py.
"""

import numpy as np
from scipy.linalg import expm, logm, norm
import od_config as cfg


N_SITES = 2
N2 = N_SITES ** 2  # 4


def vec(rho):
    """Vectorize density matrix (column-major)."""
    return rho.flatten(order='F')


def unvec(v, n=N_SITES):
    """Reshape vector back to density matrix."""
    return v.reshape((n, n), order='F')


def _discover_matrix_log(rho_traj, times):
    """
    Matrix logarithm method: estimate propagator P from multiple time steps,
    then L = logm(P) / dt.

    Config knobs:
        - ml_time_steps: list of time step sizes to try
        - ml_max_eigenvalue: reject L if max real eigenvalue exceeds this
        - ml_min_samples: minimum samples needed per time step
    """
    n_t = len(times)
    time_steps = cfg.ml_time_steps
    max_ev = cfg.ml_max_eigenvalue
    min_samples = cfg.ml_min_samples

    L_estimates = []
    weights = []

    for step in time_steps:
        if step >= n_t // 3:
            continue

        vi, vo = [], []
        for i in range(0, n_t - step, max(1, step)):
            j = i + step
            if j >= n_t:
                break
            vi.append(vec(rho_traj[i]))
            vo.append(vec(rho_traj[j]))

        if len(vi) < max(N2 + 2, min_samples):
            continue

        dt = times[step] - times[0]
        if dt <= 0:
            continue

        Vi = np.column_stack(vi)
        Vo = np.column_stack(vo)

        # Regularized pseudoinverse
        reg = cfg.ml_regularization
        if reg > 0:
            P = Vo @ Vi.T @ np.linalg.inv(Vi @ Vi.T + reg * np.eye(N2))
        else:
            P = Vo @ np.linalg.pinv(Vi)

        try:
            L_candidate = logm(P) / dt
            ev_real = np.max(np.real(np.linalg.eigvals(L_candidate)))
            if ev_real < max_ev:
                # Weight by inverse error (prefer cleaner estimates)
                v0 = vec(rho_traj[0])
                mid_idx = min(n_t // 2, n_t - 1)
                v_pred = expm(L_candidate * times[mid_idx]) @ v0
                err = norm(v_pred - vec(rho_traj[mid_idx]))
                weight = 1.0 / (err + 1e-12)
                L_estimates.append(L_candidate)
                weights.append(weight)
        except Exception:
            continue

    if not L_estimates:
        # Fallback: single-step propagator
        dt = times[1] - times[0]
        vi = [vec(rho_traj[i]) for i in range(n_t - 1)]
        vo = [vec(rho_traj[i + 1]) for i in range(n_t - 1)]
        P = np.column_stack(vo) @ np.linalg.pinv(np.column_stack(vi))
        return logm(P) / dt

    # Weighted or simple average
    if cfg.ml_weighted_average:
        weights = np.array(weights)
        weights /= weights.sum()
        L = sum(w * L for w, L in zip(weights, L_estimates))
    else:
        L = np.mean(L_estimates, axis=0)

    return L


def _discover_least_squares(rho_traj, times):
    """
    Least-squares method: finite differences to get dv/dt, then solve L @ v = dv/dt.

    Config knobs:
        - ls_margin_frac: fraction of trajectory to skip at edges
        - ls_diff_order: 1 (forward) or 2 (central differences)
        - ls_regularization: Tikhonov regularization strength
    """
    n_t = len(times)
    vecs = np.array([vec(rho_traj[i]) for i in range(n_t)])

    diff_order = cfg.ls_diff_order

    if diff_order == 2:
        # Central differences
        dv = np.zeros_like(vecs)
        for i in range(1, n_t - 1):
            dv[i] = (vecs[i + 1] - vecs[i - 1]) / (times[i + 1] - times[i - 1])
        dv[0] = (vecs[1] - vecs[0]) / (times[1] - times[0])
        dv[-1] = (vecs[-1] - vecs[-2]) / (times[-1] - times[-2])
    else:
        # Forward differences
        dv = np.zeros_like(vecs)
        for i in range(n_t - 1):
            dv[i] = (vecs[i + 1] - vecs[i]) / (times[i + 1] - times[i])
        dv[-1] = dv[-2]

    margin = max(2, int(n_t * cfg.ls_margin_frac))

    V = vecs[margin:-margin].T  # (4, n_samples)
    DV = dv[margin:-margin].T   # (4, n_samples)

    reg = cfg.ls_regularization
    if reg > 0:
        L = DV @ V.T @ np.linalg.inv(V @ V.T + reg * np.eye(N2))
    else:
        L = DV @ np.linalg.pinv(V)

    return L


def recover(t, x):
    """
    Run Liouvillian recovery on density matrix trajectory.

    Parameters
    ----------
    t : np.ndarray
        Time points, shape (n_t,)
    x : np.ndarray
        Density matrix trajectory, shape (n_t, 5) where col 0 = time,
        cols 1-4 = rho elements. OR shape (n_t, 2, 2) if already parsed.

    Returns
    -------
    dict with keys:
        - operator: str description
        - coefficients: dict of Liouvillian properties
        - x_predicted: np.ndarray of reconstructed trajectory (n_t, 5)
        - metadata: dict
    """
    times = np.asarray(t, dtype=np.float64)
    x = np.asarray(x)

    # Parse input format
    if x.ndim == 2 and x.shape[1] == 5:
        # Raw format: col 0 = time (redundant with t), cols 1-4 = rho
        rho_traj = np.zeros((len(times), 2, 2), dtype=complex)
        rho_traj[:, 0, 0] = x[:, 1]
        rho_traj[:, 0, 1] = x[:, 2]
        rho_traj[:, 1, 0] = x[:, 3]
        rho_traj[:, 1, 1] = x[:, 4]
    elif x.ndim == 3 and x.shape[1:] == (2, 2):
        rho_traj = x.astype(complex)
    else:
        raise ValueError(f"Unexpected data shape: {x.shape}. Expected (n_t, 5) or (n_t, 2, 2)")

    n_t = len(times)
    n_segments = getattr(cfg, 'n_segments', 1)

    if n_segments > 1:
        return _recover_piecewise(rho_traj, times, n_segments)

    # Single Liouvillian recovery
    L_best, best_method = _recover_single(rho_traj, times)

    # Reconstruct trajectory
    v0 = vec(rho_traj[0])
    x_predicted = np.zeros((n_t, 5), dtype=complex)
    x_predicted[:, 0] = times

    for i in range(n_t):
        v_pred = expm(L_best * times[i]) @ v0
        rho_pred = unvec(v_pred)
        x_predicted[i, 1] = rho_pred[0, 0]
        x_predicted[i, 2] = rho_pred[0, 1]
        x_predicted[i, 3] = rho_pred[1, 0]
        x_predicted[i, 4] = rho_pred[1, 1]

    # Extract Liouvillian properties
    eigenvalues = np.linalg.eigvals(L_best)
    sorted_ev = sorted(eigenvalues, key=lambda e: abs(e.real))
    rates = [-e.real for e in eigenvalues]
    nonzero_rates = sorted([abs(r) for r in rates if abs(r) > 1e-10])
    primary_rate = nonzero_rates[-1] if nonzero_rates else 0.0

    coefficients = {
        "eigenvalues_real": [float(e.real) for e in sorted_ev],
        "eigenvalues_imag": [float(e.imag) for e in sorted_ev],
        "primary_decoherence_rate": float(primary_rate),
        "method": best_method,
        "L_norm": float(norm(L_best)),
    }

    return {
        "operator": f"4x4 Liouvillian ({best_method})",
        "coefficients": coefficients,
        "x_predicted": x_predicted,
        "L": L_best,
        "metadata": {
            "method": best_method,
            "recovery_method_config": cfg.recovery_method,
            "n_segments": 1,
            "ls_margin_frac": cfg.ls_margin_frac,
            "ls_diff_order": cfg.ls_diff_order,
            "ls_regularization": cfg.ls_regularization,
        },
    }


def _recover_single(rho_traj, times):
    """Recover a single Liouvillian using configured method."""
    method = cfg.recovery_method
    L_best = None
    best_method = None

    if method in ('matrix_log', 'both'):
        try:
            L_ml = _discover_matrix_log(rho_traj, times)
            L_best = L_ml
            best_method = 'matrix_log'
        except Exception:
            pass

    if method in ('least_squares', 'both'):
        try:
            L_ls = _discover_least_squares(rho_traj, times)
            if L_best is None:
                L_best = L_ls
                best_method = 'least_squares'
            else:
                err_ml = _trajectory_error(L_best, rho_traj, times)
                err_ls = _trajectory_error(L_ls, rho_traj, times)
                if err_ls < err_ml:
                    L_best = L_ls
                    best_method = 'least_squares'
        except Exception:
            if L_best is None:
                raise RuntimeError("Both recovery methods failed")

    if L_best is None:
        raise RuntimeError("Recovery failed")

    return L_best, best_method


def _recover_piecewise(rho_traj, times, n_segments):
    """
    Piecewise Liouvillian: split trajectory into segments, recover L per segment,
    reconstruct by propagating sequentially through segments.
    """
    n_t = len(times)
    seg_size = n_t // n_segments
    overlap = getattr(cfg, 'segment_overlap', 0)

    L_list = []
    boundaries = []

    for seg in range(n_segments):
        start = max(0, seg * seg_size - overlap)
        end = min(n_t, (seg + 1) * seg_size + overlap) if seg < n_segments - 1 else n_t
        boundaries.append((start, end))

        seg_rho = rho_traj[start:end]
        seg_times = times[start:end] - times[start]  # Local time

        try:
            L_seg, _ = _recover_single(seg_rho, seg_times)
        except Exception:
            # Fallback: use previous segment's L
            L_seg = L_list[-1] if L_list else np.zeros((N2, N2), dtype=complex)

        L_list.append(L_seg)

    # Reconstruct piecewise
    x_predicted = np.zeros((n_t, 5), dtype=complex)
    x_predicted[:, 0] = times

    for seg in range(n_segments):
        start = seg * seg_size
        end = (seg + 1) * seg_size if seg < n_segments - 1 else n_t
        v_start = vec(rho_traj[start])
        L_seg = L_list[seg]
        t_start = times[start]

        for i in range(start, end):
            dt = times[i] - t_start
            v_pred = expm(L_seg * dt) @ v_start
            rho_pred = unvec(v_pred)
            x_predicted[i, 1] = rho_pred[0, 0]
            x_predicted[i, 2] = rho_pred[0, 1]
            x_predicted[i, 3] = rho_pred[1, 0]
            x_predicted[i, 4] = rho_pred[1, 1]

    # Use first segment's L for coefficients
    eigenvalues = np.linalg.eigvals(L_list[0])
    sorted_ev = sorted(eigenvalues, key=lambda e: abs(e.real))
    rates = [-e.real for e in eigenvalues]
    nonzero_rates = sorted([abs(r) for r in rates if abs(r) > 1e-10])
    primary_rate = nonzero_rates[-1] if nonzero_rates else 0.0

    return {
        "operator": f"Piecewise Liouvillian ({n_segments} segments)",
        "coefficients": {
            "eigenvalues_real": [float(e.real) for e in sorted_ev],
            "eigenvalues_imag": [float(e.imag) for e in sorted_ev],
            "primary_decoherence_rate": float(primary_rate),
            "method": cfg.recovery_method,
            "n_segments": n_segments,
            "L_norms": [float(norm(L)) for L in L_list],
        },
        "x_predicted": x_predicted,
        "L": L_list,
        "metadata": {
            "method": f"piecewise_{cfg.recovery_method}",
            "n_segments": n_segments,
            "segment_overlap": overlap,
            "ls_margin_frac": cfg.ls_margin_frac,
            "ls_diff_order": cfg.ls_diff_order,
        },
    }


def _trajectory_error(L, rho_traj, times):
    """Mean Frobenius error over trajectory."""
    v0 = vec(rho_traj[0])
    n_t = len(times)
    n_check = min(50, n_t)
    idx = np.linspace(0, n_t - 1, n_check).astype(int)

    errs = []
    for i in idx:
        v_pred = expm(L * times[i]) @ v0
        rho_pred = unvec(v_pred)
        errs.append(norm(rho_pred - rho_traj[i], 'fro'))

    return np.mean(errs)
