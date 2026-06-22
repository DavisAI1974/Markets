"""odcore/info_dipole.py — signed information-dipole FLOW operator (portable, numpy-only).

The information dipole (davisai.ai/dipole) measures FLOW between two coupled channels and is
naturally signed. In markets the two channels are taker BUY-flow vs SELL-flow, so the dipole
gives a directional (+ buy-pressure / - sell-pressure) read the side-AGNOSTIC 128-dim OD coeff
cannot (coeffs are built from price log-returns, so buy & sell trades on the same chunk get
identical coeffs -- the S35b "bleed"). This operator supplies the missing direction.

Faithful to the paper's primitives:
  - discrete Shannon entropy via histogram binning,  H(X) = -sum p log p
  - mutual information  MI(a,b) = H(a) + H(b) - H(a,b)   (2D histogram)
  - the differential FLOW form  dMI/dt  (early-half vs late-half of the window)
  - the ratio  C = H_self / H_cross

SIGN CONVENTION (option a): direction from the (H_a - H_b) order-flow imbalance; magnitude from
the information-dipole flow. The imbalance says which way flow leans; the dMI/dt flow says how
strongly the coupling is evolving. `mi_flow` is the primary signed feature; `imb_flow` and
`ent_dipole` are sibling signed forms kept because different cells earn lift from different ones
(per-cell selection, never averaged -- averaging would flatten the per-bucket distinctiveness
that is the whole point: `bucket-distinctiveness-is-the-goal`, `deploy-signal-per-cell-not-universal`).

Reusable in multiple stages: pre-window info-gathering AND the per-cell entry fingerprint.
Pure (numpy only); the caller slices the strictly pre-entry order-flow window and passes the
buy/sell arrays in -- this module adds no look-ahead.
"""
from __future__ import annotations

import math

import numpy as np

EPS = 1e-9

# Per-cell candidate map: cell -> (feature, lift_over_base_rate, n) from
# _info_dipole_flow_probe.py (lift >= +5 over base rate on the 05-22..24 test bars), then
# narrowed by the robustness sweep (_info_dipole_flow_robustness.py).
#
# RETAINED (Greg's call — keep the buckets it works in, `deploy-signal-per-cell-not-universal`):
# only the 2 cells whose positive lift REPEATED across the window grid are kept; both are positive
# specifically at the 30m pre-entry window (= FLOW_WINDOW_BARS the fingerprint uses):
#   - eth_bybit_buy  [imb_flow]: positive in 7/9 window x forward grid cells (30m row +8.3/+11.1/+5.6)
#   - btc_kraken_sell[mi_flow] : largest n=140, 30m row +5.7/+8.6, only cell with positive late-OOS (+7.1)
# DROPPED as fragile: btc_coinbase_sell (20m row -21..-39), eth_kraken_sell (grid mostly negative).
#
# STILL PROVISIONAL (DEPLOY_VALIDATED=False): even the 2 keepers have weak temporal OOS on thin
# 1-min/small-N data; the grid positivity is encouraging but a clean out-of-sample edge is NOT yet
# proven. Real confirmation needs the local 1-sec onset-window history (not in git). Until
# DEPLOY_VALIDATED is True, treat cell_signal as a research/stacking input, not a standalone live edge.
DEPLOY_VALIDATED = False
DEPLOY: dict[str, tuple[str, float, int]] = {
    "eth_bybit_buy":   ("imb_flow", 11.1, 72),
    "btc_kraken_sell": ("mi_flow", 8.2, 140),
}

FEATURES = ("imb_level", "ent_dipole", "C_signed", "mi_flow", "imb_flow")


def shannon(x, bins=None) -> float:
    x = np.asarray(x, float)
    if x.size < 2 or np.allclose(x, x[0]):
        return 0.0
    if bins is None:
        bins = max(3, int(round(math.sqrt(x.size))))
    h, _ = np.histogram(x, bins=bins)
    p = h[h > 0] / h.sum()
    return float(-(p * np.log(p)).sum())


def mutual_info(a, b, bins=None) -> float:
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.size < 2:
        return 0.0
    if bins is None:
        bins = max(3, int(round(math.sqrt(a.size))))
    Ha, Hb = shannon(a, bins), shannon(b, bins)
    hab, _, _ = np.histogram2d(a, b, bins=bins)
    p = hab[hab > 0] / hab.sum()
    Hab = float(-(p * np.log(p)).sum())
    return max(0.0, Ha + Hb - Hab)


def signed_flow_features(buy_vol, sell_vol) -> dict | None:
    """Signed information-dipole flow features from one order-flow window.

    buy_vol/sell_vol: equal-length per-bar taker buy/sell volume over the (pre-entry) window,
    time-ordered. Returns the FEATURES dict, or None if the window is too short / empty.
    """
    A = np.asarray(buy_vol, float); S = np.asarray(sell_vol, float)
    n = min(A.size, S.size)
    if n < 6:
        return None
    A, S = A[:n], S[:n]
    sB, sS = A.sum(), S.sum()
    if sB + sS <= 0:
        return None

    imb_level = (sB - sS) / (sB + sS)                 # static order-flow dipole (signed)
    sgn = 1.0 if imb_level >= 0 else -1.0             # option (a): direction from imbalance

    Ha, Hb = shannon(A), shannon(S)
    ent_dipole = (Ha - Hb) / (Ha + Hb + EPS)          # entropy-asymmetry dipole (signed)
    mi = mutual_info(A, S)
    C_signed = sgn * (0.5 * (Ha + Hb)) / (mi + EPS)    # signed C = H_self/H_cross

    mid = n // 2                                       # differential dMI/dt: early vs late half
    mi_e = mutual_info(A[:mid], S[:mid]); mi_l = mutual_info(A[mid:], S[mid:])
    mi_flow = sgn * (mi_l - mi_e)                      # PRIMARY: imbalance-signed MI flow
    def _imb(b, s):
        t = b.sum() + s.sum()
        return (b.sum() - s.sum()) / t if t > 0 else 0.0
    imb_flow = _imb(A[mid:], S[mid:]) - _imb(A[:mid], S[:mid])   # signed imbalance flow

    return {"imb_level": imb_level, "ent_dipole": ent_dipole, "C_signed": C_signed,
            "mi_flow": mi_flow, "imb_flow": imb_flow}


# aligned-flow threshold below which a reversal is high-conviction (validated tier boundary)
DIVERGE_STRONG = -0.20


def divergence(buy_vol, sell_vol, price_drift: float) -> dict | None:
    """Order-flow DIVERGENCE vs the recent price trend -> graded continuation-vs-flip read.

    Following the trend IS following the flow. The info dipole works as a flip detector, not a
    direct direction predictor: a trend FLIPS when flow turns against it (exhaustion). The EDGE is
    graded and asymmetric -- it lives on the divergence side (_info_dipole_trend_flip.py):
      aligned_flow = imb_level * sign(price_drift)   (>0 flow confirms trend; <0 flow opposes it)
      strong divergence (aligned <= -0.20) -> ~65% REVERSAL pooled (n=234), temporally stable
        (early 70% / late 62%) and consistent per cell (btc_bybit_sell 100%, btc_kraken_buy 84%,
        btc_coinbase_buy 67% ... only btc_bybit_buy neutral). Confirmation is NOT a reliable
        continuation signal (strong-confirm ~49% -- very strong with-trend flow is itself exhaustion).
    So use it per cell as a REVERSAL/flip gate, never pooled to deploy. Maps to the 5-state frame
    (flow-opposed move = reversal/EQUILIBRIUM transition).

    price_drift: recent price change over the same pre-entry window (close[-1]-close[0]).
    Returns {imb_level, aligned_flow, confirms, expect, reversal_conviction}, or None if unusable.
    """
    feats = signed_flow_features(buy_vol, sell_vol)
    if feats is None or price_drift == 0:
        return None
    aligned = feats["imb_level"] * (1.0 if price_drift > 0 else -1.0)
    confirms = aligned > 0
    strong_flip = aligned <= DIVERGE_STRONG
    return {"imb_level": feats["imb_level"], "aligned_flow": aligned, "confirms": confirms,
            "expect": "reversal" if strong_flip else ("continue" if confirms else "flip_risk"),
            "reversal_conviction": max(0.0, -aligned)}   # 0..1, grows with opposing-flow strength


def cell_signal(cell: str, buy_vol, sell_vol):
    """Per-cell signed flow signal: the deploy-selected feature for `cell`, else None.

    Returns (value, feature_name) using the cell's candidate feature from DEPLOY, or None if this
    cell is not a candidate. Never blends features; selects one per bucket.

    NOTE: DEPLOY is PROVISIONAL (DEPLOY_VALIDATED is False) — the per-cell lifts failed robustness
    (see module docstring). Use this for research/stacking; gate any LIVE decision on
    DEPLOY_VALIDATED being True.
    """
    if cell not in DEPLOY:
        return None
    feats = signed_flow_features(buy_vol, sell_vol)
    if feats is None:
        return None
    fname = DEPLOY[cell][0]
    return feats[fname], fname
