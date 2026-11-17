"""Markets estimator bridge: the SAME RawFrames through declared estimators.

Review section 6 / tests-remaining "Estimators": Markets uses continuous
estimators (Vasicek m-spacing entropy, KSG-1 mutual information, odcore/operators.py)
where the imported package uses frozen discrete bins (adaptive_locality/information.py).
Neither replaces the other. This module derives InfoFrames with BOTH, under a
calibration identity that names the estimator, so a fit can never silently mix
them and every archived result says which estimator produced it.

Rules: the admission checks are identical for both estimators (same frozen bins,
same out-of-range / unaligned / duplicate review), so the two InfoFrame series
cover exactly the same admitted frames. The Fisher-like term is the frozen-bin
location-Fisher plug-in in both cases and is labelled as such. No raw value is
altered; a REVIEW_REQUIRED frame stays REVIEW_REQUIRED under every estimator.

This file is Markets-owned and imports odcore (numpy/scipy). The standalone
package stays standard-library only.
"""
from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from typing import Sequence

import numpy as np

from adaptive_locality.core import LocalityError, _digest
from adaptive_locality.information import (RawFrame, FixedBins, InfoFrame,
                                           derive_information)
from odcore.operators import vasicek_entropy, ksg_mi

ESTIMATORS = ("frozen-bin", "vasicek-ksg")


def estimator_identity(bins: FixedBins, estimator: str, *, k: int = 4,
                       seed: int = 0) -> str:
    """Calibration identity that names the estimator and its parameters."""
    if estimator not in ESTIMATORS:
        raise LocalityError("unknown estimator declaration")
    if estimator == "frozen-bin":
        return bins.identity()
    return _digest({"estimator": estimator, "bins": bins.identity(), "k": k, "seed": seed,
                    "entropy": "vasicek-m-spacing", "mi": "ksg-1-chebyshev",
                    "fisher": "frozen-bin-location-plugin"})


def derive_information_continuous(raw: RawFrame, bins: FixedBins, *, k: int = 4,
                                  seed: int = 0) -> InfoFrame:
    """Vasicek entropy + KSG-1 MI on the aligned member values, frozen-bin Fisher proxy.

    Admission is delegated to the discrete deriver so both estimators agree on
    which frames are READY. Entropies are differential (nats) and can be
    negative; the ratio library in coupling.py is unit-aware only through the
    calibration identity, which is why that identity names the estimator.
    """
    discrete = derive_information(raw, bins)
    identity = estimator_identity(bins, "vasicek-ksg", k=k, seed=seed)
    if discrete.status != "READY":
        return replace(discrete, calibration_identity=identity)
    nodes = tuple(sorted(dict(bins.edges)))
    values = {node: {} for node in nodes}
    for sample in raw.samples:
        values[sample.node][sample.member_id] = sample.value
    members = sorted(values[nodes[0]])
    arrays = {node: np.array([values[node][m] for m in members], dtype=float) for node in nodes}
    if any(len(arr) < 4 for arr in arrays.values()):
        return replace(discrete, calibration_identity=identity, entropy=(), fisher_proxy=(),
                       mi=(), status="REVIEW_REQUIRED",
                       review_reasons=("CONTINUOUS_ESTIMATOR_NEEDS_AT_LEAST_4_MEMBERS",))
    rng = np.random.default_rng(seed)
    entropy = tuple((node, float(vasicek_entropy(arrays[node]))) for node in nodes)
    mutual = tuple((a, b, float(ksg_mi(arrays[a], arrays[b], k=k, rng=rng)))
                   for a, b in combinations(nodes, 2))
    if any(not np.isfinite(v) for _, v in entropy) or any(not np.isfinite(v) for *_, v in mutual):
        return replace(discrete, calibration_identity=identity, entropy=(), fisher_proxy=(),
                       mi=(), status="REVIEW_REQUIRED",
                       review_reasons=("CONTINUOUS_ESTIMATOR_NONFINITE",))
    return replace(discrete, calibration_identity=identity, entropy=entropy, mi=mutual)


def estimator_bridge(raw_frames: Sequence[RawFrame], bins: FixedBins, *, k: int = 4,
                     seed: int = 0) -> dict:
    """Derive every admitted frame under every declared estimator.

    Returns {"frozen-bin": frames, "vasicek-ksg": frames, "identities": {...},
    "ready_clocks_agree": bool}. Callers archive each series with its own
    calibration identity; nothing here persists or fits.
    """
    raw = tuple(raw_frames)
    if not raw or any(not isinstance(r, RawFrame) for r in raw):
        raise LocalityError("complete RawFrame series required")
    discrete = tuple(derive_information(r, bins) for r in raw)
    continuous = tuple(derive_information_continuous(r, bins, k=k, seed=seed) for r in raw)
    ready_d = tuple(f.clock for f in discrete if f.status == "READY")
    ready_c = tuple(f.clock for f in continuous if f.status == "READY")
    return {"frozen-bin": discrete, "vasicek-ksg": continuous,
            "identities": {"frozen-bin": estimator_identity(bins, "frozen-bin"),
                           "vasicek-ksg": estimator_identity(bins, "vasicek-ksg", k=k, seed=seed)},
            "ready_clocks_agree": ready_d == ready_c,
            "frames": len(raw), "scientific_jobs_eliminated": 0,
            "note": "Two estimators, two series, two identities; neither replaces the other."}
