#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import numpy as np

import ng_exhaustion_d1_d5_chain_birth_agents_20260819 as base


PRICE_STRUCTURE_MODE = "PER_OCCURRENCE_CAUSAL_ONE_SECOND_PATH_PREFIX"


def causal_second_path(cache, week, event, h):
    """Return [polarity, signed cumulative price at second 1..H].

    Baseline is the last trade known at or before frozen detector confirmation.
    Each second s uses only the last trade known by confirmation+s.  A path at H
    is therefore exactly the causal prefix 1..H; no interpolation from future
    prices and no post-H observation is permitted.
    """
    c = base.event_confirm(event)
    if c is None or h <= 0:
        return None
    times = cache["times"][week]
    prices = cache["prices"][week]
    if len(times) == 0:
        raise RuntimeError(f"authoritative raw price tape missing for week={week}")

    key = (week, int(event["sequence_index"]))
    states = cache.setdefault("second_path_state", {})
    state = states.get(key)
    if state is None:
        j0 = int(np.searchsorted(times, float(c), side="right")) - 1
        if j0 < 0:
            raise RuntimeError(
                f"no causal baseline trade at/before confirmation week={week} "
                f"seq={event['sequence_index']} confirm={c}"
            )
        state = {
            "built_h": 0,
            "p0": float(prices[j0]),
            "values": [],
        }
        states[key] = state

    pol = float(event["polarity"])
    for s in range(int(state["built_h"]) + 1, int(h) + 1):
        k = int(np.searchsorted(times, float(c + s), side="right")) - 1
        if k < 0:
            raise RuntimeError(
                f"no causal price known by second={s} week={week} "
                f"seq={event['sequence_index']}"
            )
        px = float(prices[k])
        signed_ticks = pol * (px - float(state["p0"])) / base.TICK
        state["values"].append(math.asinh(signed_ticks))
    state["built_h"] = max(int(state["built_h"]), int(h))

    # One cumulative value per elapsed second fully determines the one-second
    # changes as adjacent differences; do not duplicate the same information.
    return np.asarray([pol] + state["values"][: int(h)], float)


# The original feature_pair already preserves each predecessor occurrence as a
# separate ordered part and concatenates them.  Replacing cache_snapshot makes
# D2 carry two distinct 1..H paths, D3 three, etc.
base.cache_snapshot = causal_second_path


_orig_run_stage = base.run_stage


def _write_sparse_price_paths(stage, cases, cache, out_path):
    """Persist full per-occurrence price prefixes for low-support D4/D5 cases.

    Earlier H values are exact prefixes of max_prior_H, so one stored path per
    predecessor occurrence preserves every dense-clock price structure without
    duplicating 1..H arrays at every checkpoint.
    """
    rows = []
    for case in cases:
        tt = int(case["target"]["t0_idx"])
        eligible_h = []
        for h in base.HGRID:
            cs = [base.event_confirm(e) for e in case["preds"]]
            if all(c is not None for c in cs) and max(int(c) + int(h) for c in cs) <= tt:
                eligible_h.append(int(h))
        if not eligible_h:
            continue
        hmax = max(eligible_h)
        for ordinal, event in enumerate(case["preds"], start=1):
            path = causal_second_path(cache, case["week"], event, hmax)
            rows.append({
                "case_id": case["id"],
                "stage": int(stage),
                "birth_label": int(case["y"]),
                "week": case["week"],
                "predecessor_ordinal": int(ordinal),
                "predecessor_sequence_index": int(event["sequence_index"]),
                "predecessor_event_id": event["event_id"],
                "max_prior_H_seconds": int(hmax),
                "polarity": int(event["polarity"]),
                "signed_cumulative_price_path_asinh_ticks_1s": [float(x) for x in path[1:]],
                "availability_is_feature": False,
            })
    with gzip.open(out_path, "wt") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    return len(rows)


def run_stage_v2(stage, events, lineage, raw_dir):
    if stage < 4:
        result = _orig_run_stage(stage, events, lineage, raw_dir)
        result["price_structure_mode"] = PRICE_STRUCTURE_MODE
        result["price_structure_per_occurrence"] = True
        result["price_structure_seconds_visible_at_H"] = "ALL_SECONDS_1_THROUGH_H_ONLY"
        result["price_structure_availability_used_as_feature"] = False
        result["price_structure_missingness_policy"] = "FAIL_CLOSED_DATA_INTEGRITY_NOT_MODEL_SIGNAL"
        return result

    cases, censored = base.birth_cases(events, lineage, stage)
    pos = sum(c["y"] for c in cases)
    neg = len(cases) - pos
    weeks = sorted({c["week"] for c in cases})
    cache = {"times": {}, "prices": {}, "snap": {}}
    for w in weeks:
        cache["times"][w], cache["prices"][w] = base.load_week_prices(raw_dir, w)
        if len(cache["times"][w]) == 0:
            raise RuntimeError(f"authoritative raw price tape missing for sparse stage D{stage} week={w}")

    counts = {b: {"positive": 0, "negative": 0} for b in set(base.FOLD_BLOCK.values())}
    for c in cases:
        counts[c["block"]]["positive" if c["y"] else "negative"] += 1

    # The main JSON remains compact.  Full second-level paths are written to a
    # companion gzip file and referenced here.
    companion = Path(base._ACTIVE_OUTPUT_PATH).with_suffix("")
    companion = companion.parent / f"NG_EXHAUSTION_CHAIN_BIRTH_D{stage}_SPARSE_PRICE_PATHS_20260819.jsonl.gz"
    path_rows = _write_sparse_price_paths(stage, cases, cache, companion)

    return {
        "status": "CHAIN_BIRTH_AGENT_COMPLETE_LOW_SUPPORT_PRESERVED",
        "stage": int(stage),
        "positive_n": int(pos),
        "negative_n": int(neg),
        "censored_n": int(len(censored)),
        "block_counts": counts,
        "H_grid": list(base.HGRID),
        "sparse_cases": base.sparse_report(cases, stage),
        "censored": censored,
        "price_structure_mode": PRICE_STRUCTURE_MODE,
        "price_structure_per_occurrence": True,
        "price_structure_seconds_visible_at_H": "ALL_SECONDS_1_THROUGH_H_ONLY",
        "price_structure_availability_used_as_feature": False,
        "price_structure_missingness_policy": "FAIL_CLOSED_DATA_INTEGRITY_NOT_MODEL_SIGNAL",
        "sparse_price_path_artifact": str(companion),
        "sparse_price_path_rows": int(path_rows),
        "promotion_performed": False,
    }


base.run_stage = run_stage_v2


# base.main does not expose the output path to run_stage.  Set it before calling
# main by deriving the --out argument without changing the original CLI.
def _set_active_output_path_from_argv():
    import sys

    try:
        i = sys.argv.index("--out")
        base._ACTIVE_OUTPUT_PATH = sys.argv[i + 1]
    except Exception as exc:
        raise SystemExit("--out is required for v2 sparse price-path artifact") from exc


if __name__ == "__main__":
    _set_active_output_path_from_argv()
    base.main()
