"""
metrics.py — OD-BOOK scoring (frozen per KILL_GATE.md).

Three things, matching the pre-registered gate:

1. forecast_skill  — OOS R² per component at each horizon. For the price/`mid`
   component specifically we reconstruct the predicted PRICE path (by integrating
   predicted mid_ret) and score against the *persistence-of-price* baseline
   (mid(t+h)=mid(t)) — the honest bar, not persistence-of-return (which a
   predict-zero model beats trivially).

2. turn_as_consequence — the ONLY money metric. Derive a swing position from each
   forecaster's predicted forward mid move, simulate flip-at-each-turn trading,
   and report PnL **net of the 22 bps round-trip fee floor**, plus turn-timing
   slippage (bps from each flip to the nearest true extreme) and FN-rate (missed
   tradeable turns) — challenger vs champion, matched FP.

3. spectrum_stability — does the recovered DMD operator keep getting recovered
   across walk-forward windows, or does it wander? Wander = KILL.

True turns are labelled by a zigzag on the realized mid at a reversal threshold
>= the fee floor (only swings worth trading count).
"""

from __future__ import annotations

import numpy as np

import champion


# ----------------------------------------------------------------------------- #
# 1. forecast skill (price path reconstructed honestly)
# ----------------------------------------------------------------------------- #
def predict_fwd_logret(model, hist: np.ndarray, horizon: int, mid_ret_idx: int) -> float:
    """Iterate the operator `horizon` steps, summing predicted mid_ret =
    predicted cumulative forward log-return over the horizon."""
    Z = model._z(hist)
    buf = [Z[-k] for k in range(1, model.p + 1)]
    total = 0.0
    for _ in range(horizon):
        lags = np.concatenate(buf)
        pred_z = model.A @ lags + model.c
        # de-standardize just the mid_ret component to accumulate a real return
        total += pred_z[mid_ret_idx] * model.sd[mid_ret_idx] + model.mu[mid_ret_idx]
        buf = [pred_z] + buf[:-1]
    # A predicted cumulative log-return beyond ~10% over <=1s is a broken
    # (unstable-operator) prediction; clip so it can't overflow exp() downstream
    # and can't masquerade as skill.
    return float(np.clip(total, -0.1, 0.1))


def mid_path_skill(model, X: np.ndarray, mid: np.ndarray, horizon: int,
                   mid_ret_idx: int) -> float:
    """OOS R² of the predicted mid price at t+h vs persistence-of-price."""
    n = X.shape[0]
    err_model, err_base = 0.0, 0.0
    cnt = 0
    for t in range(model.p - 1, n - horizon):
        hist = X[max(0, t - model.p + 1): t + 1]
        if hist.shape[0] < model.p:
            continue
        fwd = predict_fwd_logret(model, hist, horizon, mid_ret_idx)
        pred_mid = mid[t] * np.exp(fwd)
        true_mid = mid[t + horizon]
        err_model += (true_mid - pred_mid) ** 2
        err_base += (true_mid - mid[t]) ** 2          # persistence of price
        cnt += 1
    if cnt == 0 or err_base == 0:
        return float("nan")
    return 1.0 - err_model / err_base


def forecast_skill(model, X: np.ndarray, mid: np.ndarray, cols: list[str],
                   horizons: list[int]) -> dict:
    mid_ret_idx = cols.index("mid_ret")
    out = {}
    for h in horizons:
        comp = champion.oos_r2(model, X, h, cols)
        comp["mid_price"] = mid_path_skill(model, X, mid, h, mid_ret_idx)
        out[h] = comp
    return out


# ----------------------------------------------------------------------------- #
# 2. turn-as-consequence (the money metric)
# ----------------------------------------------------------------------------- #
def label_turns(mid: np.ndarray, theta_bps: float = 22.0):
    """Zigzag turning points: a turn confirms when mid reverses by >= theta_bps
    from the running extreme. Returns list of (index, kind, price), kind in
    {'peak','valley'}. Only swings >= theta (>= the fee floor) are labelled."""
    if len(mid) == 0:
        return []
    theta = theta_bps / 1e4
    turns = []
    last_ext_i = 0
    last_ext_p = mid[0]
    direction = 0  # +1 rising leg, -1 falling leg, 0 unknown
    for i in range(1, len(mid)):
        p = mid[i]
        if direction >= 0 and p > last_ext_p:
            last_ext_p, last_ext_i = p, i
        elif direction <= 0 and p < last_ext_p:
            last_ext_p, last_ext_i = p, i
        # reversal check
        if direction >= 0 and p <= last_ext_p * (1 - theta):
            turns.append((last_ext_i, "peak", last_ext_p))
            direction = -1
            last_ext_p, last_ext_i = p, i
        elif direction <= 0 and p >= last_ext_p * (1 + theta):
            turns.append((last_ext_i, "valley", last_ext_p))
            direction = +1
            last_ext_p, last_ext_i = p, i
    return turns


def swing_positions(model, X: np.ndarray, horizon: int, mid_ret_idx: int,
                    deadband_bps: float = 0.0) -> np.ndarray:
    """Position in {-1,0,+1} from sign of predicted forward log-return, with an
    optional deadband (predicted move must exceed deadband_bps to take a side)."""
    n = X.shape[0]
    pos = np.zeros(n)
    db = deadband_bps / 1e4
    for t in range(model.p - 1, n - horizon):
        hist = X[max(0, t - model.p + 1): t + 1]
        if hist.shape[0] < model.p:
            continue
        fwd = predict_fwd_logret(model, hist, horizon, mid_ret_idx)
        pos[t] = 1.0 if fwd > db else (-1.0 if fwd < -db else 0.0)
    return pos


def swing_pnl(positions: np.ndarray, mid: np.ndarray, fee_bps: float = 22.0) -> dict:
    """Sign-following swing PnL net of fee_bps per flip (round-trip floor).
    PnL(t) = position(t) * realized step log-return(t->t+1)."""
    n = min(len(positions), len(mid))
    r = np.diff(np.log(mid[:n]))               # step returns
    pos = positions[:n - 1]
    gross = float(np.sum(pos * r) * 1e4)        # bps
    flips = int(np.sum(np.abs(np.diff(np.concatenate([[0.0], pos]))) > 0))
    fee = flips * fee_bps
    return {
        "gross_bps": gross,
        "n_flips": flips,
        "fee_bps_total": fee,
        "net_bps": gross - fee,
        "net_bps_per_flip": (gross - fee) / flips if flips else 0.0,
    }


def turn_timing(positions: np.ndarray, mid: np.ndarray, turns) -> dict:
    """For each flip, bps distance from the flip price to the nearest true
    extreme; and FN-rate = fraction of true turns with no flip within a small
    neighbourhood. Lower slippage + lower FN = better timing."""
    flips = np.where(np.abs(np.diff(np.concatenate([[0.0], positions]))) > 0)[0]
    if len(turns) == 0:
        return {"mean_slippage_bps": float("nan"), "fn_rate": float("nan"),
                "n_turns": 0, "n_flips": int(len(flips))}
    turn_idx = np.array([t[0] for t in turns])
    turn_px = np.array([t[2] for t in turns])
    # slippage: each flip -> nearest true turn (in price bps)
    slips = []
    for f in flips:
        j = int(np.argmin(np.abs(turn_idx - f)))
        slips.append(abs(mid[f] / turn_px[j] - 1.0) * 1e4)
    # FN: true turns with no flip within +/- win steps
    win = 10
    detected = 0
    for ti in turn_idx:
        if np.any(np.abs(flips - ti) <= win):
            detected += 1
    return {
        "mean_slippage_bps": float(np.mean(slips)) if slips else float("nan"),
        "median_slippage_bps": float(np.median(slips)) if slips else float("nan"),
        "fn_rate": 1.0 - detected / len(turn_idx),
        "n_turns": int(len(turn_idx)),
        "n_flips": int(len(flips)),
    }


def turn_as_consequence(model, X: np.ndarray, mid: np.ndarray, cols: list[str],
                        horizon: int, fee_bps: float = 22.0,
                        theta_bps: float = 22.0, deadband_bps: float = 0.0) -> dict:
    mid_ret_idx = cols.index("mid_ret")
    pos = swing_positions(model, X, horizon, mid_ret_idx, deadband_bps)
    turns = label_turns(mid, theta_bps)
    pnl = swing_pnl(pos, mid, fee_bps)
    tim = turn_timing(pos, mid, turns)
    return {"horizon": horizon, "fee_bps": fee_bps, "theta_bps": theta_bps,
            **{f"pnl_{k}": v for k, v in pnl.items()},
            **{f"turn_{k}": v for k, v in tim.items()}}


# ----------------------------------------------------------------------------- #
# 3. spectrum stability across walk-forward windows
# ----------------------------------------------------------------------------- #
def spectrum_stability(eigs_list: list[np.ndarray]) -> dict:
    """Given DMD eigenvalue arrays from successive walk-forward windows, measure
    how much the dominant spectrum moves. Stable operator => small drift."""
    if len(eigs_list) < 2:
        return {"n_windows": len(eigs_list), "radius_std": float("nan")}
    radii = [float(np.abs(e).max()) for e in eigs_list]
    # compare the sorted top-k moduli window-to-window
    k = min(min(len(e) for e in eigs_list), 5)
    tops = [np.sort(np.abs(e))[-k:] for e in eigs_list]
    drift = [float(np.mean(np.abs(tops[i] - tops[i - 1]))) for i in range(1, len(tops))]
    return {
        "n_windows": len(eigs_list),
        "radius_mean": float(np.mean(radii)),
        "radius_std": float(np.std(radii)),
        "topk_drift_mean": float(np.mean(drift)),
        "topk_drift_max": float(np.max(drift)),
    }
