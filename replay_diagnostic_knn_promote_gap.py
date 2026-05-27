"""Diagnostic: why doesn't K-NN-based promotion fire on the 67k tape?

Hypothesis: K-NN identity-gated LB never reaches global break_even because the base
win rate (8.3%) is much lower than break_even (typically 0.4-0.6 given avg_win/avg_loss
geometry). So even the "best" identity-gated neighborhoods stay well below the global
threshold.

Captures distribution stats for Wilson=shadow events where K-NN eff_n >= n_min:
  - break_even values seen
  - K-NN p_win_mean values
  - K-NN p_win_lb_90 values
  - gap: knn_lb - break_even (negative means below threshold)
  - per-strategy max knn_lb / max (knn_lb - be)
"""

from __future__ import annotations

import csv
import math
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

import oracle_winner_evidence as owe
import oracle_winner_trade_memory as owtm
from markets_evidence_knn import _identity_tuple, _key_components, _cosine_sparse

CSV_PATH = Path(r"E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv")
N_MIN_FOR_BANK = 10
FEES_BPS = 0.0
MIN_SIMILARITY = 0.5
ROLLING_PAYOFF_WINDOW = 500


class IncrementalIndex:
    def __init__(self):
        self.vocab: dict[tuple[int, str], int] = {}
        self.vectors_by_key: dict[str, dict[int, float]] = {}
        self.outcomes_by_key: dict[str, list[float]] = defaultdict(list)
        self.keys_by_identity: dict[tuple, list[str]] = defaultdict(list)

    def _key_vector(self, canonical_key: str) -> dict[int, float]:
        out = {}
        for pos, val in _key_components(canonical_key):
            key = (pos, val)
            idx = self.vocab.get(key)
            if idx is None:
                idx = len(self.vocab)
                self.vocab[key] = idx
            out[idx] = 1.0
        return out

    def add_outcome(self, canonical_key, net_bps):
        if canonical_key not in self.vectors_by_key:
            self.vectors_by_key[canonical_key] = self._key_vector(canonical_key)
            self.keys_by_identity[_identity_tuple(canonical_key)].append(canonical_key)
        self.outcomes_by_key[canonical_key].append(net_bps)

    def neighbor_posterior(self, canonical_key):
        if not self.vocab:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0}
        query_vec = {}
        for pos, val in _key_components(canonical_key):
            idx = self.vocab.get((pos, val))
            if idx is not None:
                query_vec[idx] = 1.0
        if not query_vec:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0}
        identity = _identity_tuple(canonical_key)
        candidate_keys = self.keys_by_identity.get(identity, [])
        scored = []
        for k2 in candidate_keys:
            sim = _cosine_sparse(query_vec, self.vectors_by_key[k2])
            if sim >= MIN_SIMILARITY:
                scored.append((sim, k2))
        scored.sort(reverse=True)
        k = max(5, round(math.sqrt(len(self.vectors_by_key))))
        top = scored[:k]
        sum_w = sum_w_sq = sum_w_wins = 0.0
        for sim, k2 in top:
            for o in self.outcomes_by_key.get(k2, []):
                sum_w += sim
                sum_w_sq += sim * sim
                if o > 0:
                    sum_w_wins += sim
        if sum_w == 0:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0}
        p_mean = sum_w_wins / sum_w
        eff_n_float = (sum_w * sum_w) / sum_w_sq if sum_w_sq > 0 else 0.0
        eff_n = int(round(eff_n_float))
        eff_wins = int(round(p_mean * eff_n_float))
        p_lb = owe._wilson_lb(eff_wins, eff_n, owe.WILSON_Z_90)
        return {"effective_n": eff_n, "p_win_mean": p_mean, "p_win_lb_90": p_lb}

    def self_posterior(self, canonical_key):
        outcomes = self.outcomes_by_key.get(canonical_key, [])
        n = len(outcomes)
        wins = sum(1 for o in outcomes if o > 0)
        p_mean = (wins / n) if n else 0.0
        p_lb = owe._wilson_lb(wins, n, owe.WILSON_Z_90)
        return {"n": n, "wins": wins, "p_win_mean": p_mean, "p_win_lb_90": p_lb}


def quantile(xs, q):
    if not xs:
        return None
    sxs = sorted(xs)
    pos = q * (len(sxs) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sxs[lo]
    return sxs[lo] + (sxs[hi] - sxs[lo]) * (pos - lo)


def main():
    print(f"Loading {CSV_PATH} ...", flush=True)
    rows = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                key = owtm.oracle_winner_canonical_trade_key(r)
                ts = float(r.get("exit_ts") or r.get("entry_ts") or 0.0)
                net_bps = float(r.get("net_bps") or 0.0)
                if not key or ts == 0.0:
                    continue
                rows.append({
                    "ts": ts, "key": key, "net_bps": net_bps,
                    "asset": r.get("asset") or "", "venue": r.get("venue") or "",
                    "side": r.get("side") or "", "strategy_id": r.get("strategy_id") or "",
                })
            except Exception:
                continue
    rows.sort(key=lambda r: r["ts"])
    print(f"  loaded {len(rows)} rows", flush=True)

    idx = IncrementalIndex()
    rolling = deque(maxlen=ROLLING_PAYOFF_WINDOW)

    # Stats buckets
    be_values = []
    knn_lb_at_shadow_with_evidence = []
    knn_mean_at_shadow_with_evidence = []
    gap_lb_minus_be = []
    per_strategy_max_lb = defaultdict(float)
    per_strategy_max_gap = defaultdict(lambda: -10.0)
    promote_would_fire = 0
    shadow_events_with_knn_evidence = 0
    eff_n_dist = []

    t0 = time.time()
    for i, r in enumerate(rows):
        key = r["key"]
        net_bps = r["net_bps"]
        wins = [x for x in rolling if x > 0]
        losses = [abs(x) for x in rolling if x <= 0]
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        be = owe.break_even_winrate(avg_w, avg_l, FEES_BPS)
        be_values.append(be)

        post = idx.self_posterior(key)
        if post["n"] == 0 or post["n"] < N_MIN_FOR_BANK:
            w_dec = "admit_shadow"
        elif post["p_win_lb_90"] >= be:
            w_dec = "admit_bank"
        elif post["p_win_mean"] >= be:
            w_dec = "admit_shadow"
        else:
            w_dec = "reject"

        if w_dec == "admit_shadow":
            k = idx.neighbor_posterior(key)
            if k["effective_n"] >= N_MIN_FOR_BANK:
                shadow_events_with_knn_evidence += 1
                knn_lb_at_shadow_with_evidence.append(k["p_win_lb_90"])
                knn_mean_at_shadow_with_evidence.append(k["p_win_mean"])
                gap_lb_minus_be.append(k["p_win_lb_90"] - be)
                eff_n_dist.append(k["effective_n"])
                if k["p_win_lb_90"] > per_strategy_max_lb[r["strategy_id"]]:
                    per_strategy_max_lb[r["strategy_id"]] = k["p_win_lb_90"]
                gap = k["p_win_lb_90"] - be
                if gap > per_strategy_max_gap[r["strategy_id"]]:
                    per_strategy_max_gap[r["strategy_id"]] = gap
                if k["p_win_lb_90"] >= be:
                    promote_would_fire += 1

        idx.add_outcome(key, net_bps)
        rolling.append(net_bps)

        if (i + 1) % 20000 == 0:
            print(f"  ... {i+1}/{len(rows)}  rate {(i+1)/(time.time()-t0):.0f}/s", flush=True)

    print(f"\nDiagnostic complete in {time.time()-t0:.1f}s\n", flush=True)

    print("=== BREAK_EVEN DISTRIBUTION (rolling, all 67k rows) ===", flush=True)
    print(f"  min={min(be_values):.3f}  q25={quantile(be_values, 0.25):.3f}  "
          f"median={quantile(be_values, 0.5):.3f}  q75={quantile(be_values, 0.75):.3f}  "
          f"max={max(be_values):.3f}", flush=True)
    print(f"  mean={sum(be_values)/len(be_values):.3f}", flush=True)

    print(f"\n=== WILSON=SHADOW EVENTS WITH K-NN eff_n>=10 ===", flush=True)
    print(f"  count: {shadow_events_with_knn_evidence}", flush=True)
    if shadow_events_with_knn_evidence > 0:
        print(f"  K-NN eff_n  median={quantile(eff_n_dist, 0.5):.0f}  q95={quantile(eff_n_dist, 0.95):.0f}  max={max(eff_n_dist)}", flush=True)
        print(f"  K-NN p_win_mean  median={quantile(knn_mean_at_shadow_with_evidence, 0.5):.3f}  "
              f"q95={quantile(knn_mean_at_shadow_with_evidence, 0.95):.3f}  "
              f"max={max(knn_mean_at_shadow_with_evidence):.3f}", flush=True)
        print(f"  K-NN p_win_lb_90  median={quantile(knn_lb_at_shadow_with_evidence, 0.5):.3f}  "
              f"q95={quantile(knn_lb_at_shadow_with_evidence, 0.95):.3f}  "
              f"max={max(knn_lb_at_shadow_with_evidence):.3f}", flush=True)
        print(f"  gap (LB - BE)  median={quantile(gap_lb_minus_be, 0.5):+.3f}  "
              f"q95={quantile(gap_lb_minus_be, 0.95):+.3f}  "
              f"max={max(gap_lb_minus_be):+.3f}", flush=True)
        print(f"  promote_would_fire (LB >= BE): {promote_would_fire} of {shadow_events_with_knn_evidence}", flush=True)

    print(f"\n=== PER-STRATEGY MAX K-NN LB AND MAX GAP ===", flush=True)
    for sid in sorted(per_strategy_max_lb.keys()):
        print(f"  {sid:30s} max_lb={per_strategy_max_lb[sid]:.3f}  max_gap={per_strategy_max_gap[sid]:+.3f}", flush=True)


if __name__ == "__main__":
    main()
