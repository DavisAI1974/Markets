"""odcore/fingerprint_predictor.py — per-cell DISTINCTIVE winner fingerprint (the S35 goal).

NOT a win/lose classifier. Per the standing principle (bucket-distinctiveness-is-the-goal,
tools-are-complementary-not-competing): we characterize each cell's WINNERS by their DISTINCTIVE
fingerprint — the STACK of the 128-dim OD coeff + the 6 onset micros + the 5 flow features — per cell,
never pooled, never class-balanced, never graded by win-vs-lose separation (AUC / perm-null z). A winning
trade is predicted by how well its fingerprint MATCHES its cell's winner signature. Distinctiveness IS
the metric.

Why the STACK (and why it must be per cell): the 128-dim coeff is built from price log-returns only, so
it is side-AGNOSTIC — it captures the coin/venue market state but cannot tell buy from sell. The micros /
flow features are directional and supply the side. So coeff -> coin/venue, micros -> side; the stack is
the full distinctive fingerprint. This module measures exactly that.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# fixed feature order (stable across builds)
MICRO_KEYS = ["trade_current_chunk_bps", "trade_recent_2chunk_bps", "trade_from_onset_bps",
              "mean_dipole", "dipole_acl1", "volume_zscore"]
FLOW_KEYS = ["imb_level", "ent_dipole", "C_signed", "mi_flow", "imb_flow"]


def _l2(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


@dataclass
class CellSignature:
    """The distinctive winner fingerprint of one cell (asset x venue x side).

    The coeff signature lives in the RESIDUAL after removing the shared common shape: the deterministic
    decoder makes ~91% of every coeff one common direction, so raw coeffs sit at ~0.99 cosine ("merged").
    Centering by `global_mean` exposes the distinctive ~9% — where buy/sell are mirror images and the
    cells separate (diagnosed in _diag_coeff_merge.py)."""
    cell: str
    n: int
    coeff_centroid: list   # 128-dim, L2-normalized CENTERED-residual centroid (coeff - global_mean)
    micro_mean: list
    micro_std: list
    flow_mean: list
    flow_std: list
    cohesion: float        # mean cosine of centered member residuals to the centroid (intra-cell tightness)
    global_mean: list      # 128-dim shared common shape removed before the cosine (same for all cells)


# --------------------------------------------------------------------------------------
# assemble: JOIN coeffs (by source_id) with the winner_onsets micros + flow, per cell
# --------------------------------------------------------------------------------------
def assemble(coeff_index_path: str, labels_dir: str) -> dict:
    idx = json.load(gzip.open(coeff_index_path, "rt"))["by_source_id"]
    labels_dir = Path(labels_dir)
    micros_by_sid, flow_by_sid = {}, {}
    for fp in labels_dir.glob("*_winner_onsets.json"):
        for r in json.load(open(fp)):
            sid = r["source_id"]
            om = r.get("onset_micros") or {}
            ff = r.get("flow_features") or {}
            micros_by_sid[sid] = [float(om.get(k, 0.0)) for k in MICRO_KEYS]
            flow_by_sid[sid] = [float(ff.get(k, 0.0)) for k in FLOW_KEYS]
    per_cell: dict = {}
    for sid, rec in idx.items():
        if sid not in micros_by_sid:          # only keep records we have ALL parts for
            continue
        per_cell.setdefault(rec["cell"], []).append({
            "source_id": sid,
            "coeff": [float(x) for x in rec["coef"]],
            "micros": micros_by_sid[sid],
            "flow": flow_by_sid.get(sid, [0.0] * len(FLOW_KEYS)),
            "net_bps": rec.get("net_bps"),
        })
    return per_cell


def global_mean_coeff(per_cell: dict) -> np.ndarray:
    """The shared common shape across ALL cells' winner coeffs (removed before the coeff cosine)."""
    allC = np.vstack([np.array([r["coeff"] for r in recs], float) for recs in per_cell.values()])
    return allC.mean(0)


def _signature_from(cell: str, C: np.ndarray, M: np.ndarray, F: np.ndarray, g: np.ndarray) -> CellSignature:
    R = C - g                                              # centered residual (the distinctive part)
    centroid = _l2(R.mean(0))
    cohesion = float(np.mean([float(_l2(r) @ centroid) for r in R])) if len(R) else 0.0
    return CellSignature(cell, len(C), centroid.tolist(),
                         M.mean(0).tolist(), (M.std(0) + 1e-9).tolist(),
                         F.mean(0).tolist(), (F.std(0) + 1e-9).tolist(), cohesion, g.tolist())


def build_signatures(per_cell: dict, g: np.ndarray = None) -> dict:
    if g is None:
        g = global_mean_coeff(per_cell)
    sigs = {}
    for cell, recs in per_cell.items():
        C = np.array([r["coeff"] for r in recs], float)
        M = np.array([r["micros"] for r in recs], float)
        F = np.array([r["flow"] for r in recs], float)
        sigs[cell] = _signature_from(cell, C, M, F, g)
    return sigs


# --------------------------------------------------------------------------------------
# match scores: how well a candidate fingerprint matches a cell's winner signature
# --------------------------------------------------------------------------------------
def coeff_sim(sig: CellSignature, coeff) -> float:
    r = _l2(np.asarray(coeff, float) - np.asarray(sig.global_mean))    # center -> distinctive residual
    return float(r @ np.asarray(sig.coeff_centroid))                   # cosine in [-1,1]


def _z_sim(x, mean, std) -> float:
    z = (np.asarray(x, float) - np.asarray(mean)) / np.asarray(std)
    return float(np.exp(-np.mean(np.abs(z))))                           # (0,1], 1 = on the mean


def micro_sim(sig: CellSignature, micros) -> float:
    return _z_sim(micros, sig.micro_mean, sig.micro_std)


def flow_sim(sig: CellSignature, flow) -> float:
    return _z_sim(flow, sig.flow_mean, sig.flow_std)


def stack_score(sig: CellSignature, coeff, micros, flow, w=(1.0, 1.0, 1.0)) -> float:
    return (w[0] * coeff_sim(sig, coeff) + w[1] * micro_sim(sig, micros) + w[2] * flow_sim(sig, flow))


def assign(signatures: dict, coeff, micros, flow, w=(1.0, 1.0, 1.0)):
    """Return (best_cell, {cell: stack_score}) — which cell's winner fingerprint this best matches."""
    scores = {c: stack_score(s, coeff, micros, flow, w) for c, s in signatures.items()}
    return max(scores, key=scores.get), scores


def save_signatures(signatures: dict, out_path: str) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = {"schema": "cell_fingerprint_signatures_v1",
            "micro_keys": MICRO_KEYS, "flow_keys": FLOW_KEYS,
            "by_cell": {c: s.__dict__ for c, s in signatures.items()}}
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(blob, f)


def load_signatures(path: str) -> dict:
    blob = json.load(gzip.open(path, "rt"))
    return {c: CellSignature(**d) for c, d in blob["by_cell"].items()}
