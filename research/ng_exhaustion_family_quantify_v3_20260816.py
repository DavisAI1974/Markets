#!/usr/bin/env python3
"""V3 runner: retain v2 geometry-balanced audit, but stratify event silhouette samples.

The family fit itself is unchanged. This only prevents a random diagnostic sample from
omitting rare pre-flip families when the saturated plateau family is overwhelmingly common.
"""
from __future__ import annotations

import sys
import numpy as np
import ng_exhaustion_family_quantify_v2_20260816 as v2

_ORIG = v2.silhouette_score


def stratified_silhouette(X, labels, *args, sample_size=None, random_state=None, **kwargs):
    labels = np.asarray(labels)
    classes = np.unique(labels)
    if sample_size is None:
        return _ORIG(X, labels, *args, **kwargs)
    if len(classes) < 2:
        return float('nan')
    rng = np.random.default_rng(random_state if random_state is not None else v2.SEED)
    target = min(int(sample_size), len(labels))
    # Guarantee every family is present, then fill remaining slots proportionally from the rest.
    chosen = []
    per = max(1, target // max(1, len(classes) * 3))
    for c in classes:
        idx = np.flatnonzero(labels == c)
        take = min(len(idx), per)
        chosen.extend(rng.choice(idx, size=take, replace=False).tolist())
    chosen = list(dict.fromkeys(chosen))
    if len(chosen) < target:
        remaining = np.setdiff1d(np.arange(len(labels)), np.asarray(chosen, dtype=int), assume_unique=False)
        take = min(target - len(chosen), len(remaining))
        if take:
            chosen.extend(rng.choice(remaining, size=take, replace=False).tolist())
    idx = np.asarray(chosen, dtype=int)
    labs = labels[idx]
    if len(np.unique(labs)) < 2 or len(idx) <= len(np.unique(labs)):
        return float('nan')
    return _ORIG(np.asarray(X)[idx], labs, *args, **kwargs)


v2.silhouette_score = stratified_silhouette

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: ng_exhaustion_family_quantify_v3_20260816.py DAY.jsonl.gz ...')
    v2.main(sys.argv[1:])
