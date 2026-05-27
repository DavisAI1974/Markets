"""Full-historic spot check: replay 67,728 simulated trades from
_analysis_historical_rt_trade_shapes_20260523/per_trade.csv through wilson and
protective admission strategies, bucketed by every dimension that matters.

This tests whether the protective design (identity-gated K-NN reject override)
holds across the full historic tape, not just the day-1 seed slice.

Implementation note: uses incremental index updates (vocab + vectors built once
per new key, identity bucket lookup is O(1)) and a rolling 500-trade deque for
break-even. O(N) over the replay instead of O(N^2) periodic rebuilds.

Per-bucket pass criterion (general principle):
  - bank_pnl(protective) >= bank_pnl(wilson) - 0.5 bps   (don't regress bank)
  - reject_pnl(protective) <= reject_pnl(wilson) + 1.0   (additional avoided loss)

If both hold on every bucket independently across all venues, all assets,
all strategies, all days — the design generalizes.
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import oracle_winner_evidence as owe
import oracle_winner_trade_memory as owtm
from markets_evidence_knn import (
    _identity_tuple, _key_components, _cosine_sparse, IDENTITY_POSITIONS,
)

CSV_PATH = Path(r"E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv")
N_MIN_FOR_BANK = 10
FEES_BPS = 0.0
MIN_SIMILARITY = 0.5
ROLLING_PAYOFF_WINDOW = 500


class IncrementalIndex:
    """O(1) per-trade incremental update; O(identity-bucket-size) per query."""

    def __init__(self):
        self.vocab: dict[tuple[int, str], int] = {}
        self.vectors_by_key: dict[str, dict[int, float]] = {}
        self.outcomes_by_key: dict[str, list[float]] = defaultdict(list)
        self.keys_by_identity: dict[tuple, list[str]] = defaultdict(list)

    def _key_vector(self, canonical_key: str) -> dict[int, float]:
        out: dict[int, float] = {}
        for pos, val in _key_components(canonical_key):
            key = (pos, val)
            idx = self.vocab.get(key)
            if idx is None:
                idx = len(self.vocab)
                self.vocab[key] = idx
            out[idx] = 1.0
        return out

    def has_key(self, canonical_key: str) -> bool:
        return canonical_key in self.vectors_by_key

    def add_outcome(self, canonical_key: str, net_bps: float) -> None:
        if canonical_key not in self.vectors_by_key:
            self.vectors_by_key[canonical_key] = self._key_vector(canonical_key)
            self.keys_by_identity[_identity_tuple(canonical_key)].append(canonical_key)
        self.outcomes_by_key[canonical_key].append(net_bps)

    def neighbor_posterior(self, canonical_key: str, n_min: int) -> dict:
        if canonical_key not in self.vectors_by_key and not self.vocab:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0,
                    "n_neighbor_keys": 0}
        # Build the query vector using EXISTING vocab only — don't mutate vocab for queries on
        # never-seen keys (would corrupt cosine norms of all stored vectors).
        query_vec: dict[int, float] = {}
        for pos, val in _key_components(canonical_key):
            idx = self.vocab.get((pos, val))
            if idx is not None:
                query_vec[idx] = 1.0
        if not query_vec:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0,
                    "n_neighbor_keys": 0}

        identity = _identity_tuple(canonical_key)
        candidate_keys = self.keys_by_identity.get(identity, [])
        scored: list[tuple[float, str]] = []
        for k2 in candidate_keys:
            sim = _cosine_sparse(query_vec, self.vectors_by_key[k2])
            if sim >= MIN_SIMILARITY:
                scored.append((sim, k2))
        scored.sort(reverse=True)
        k = max(5, round(math.sqrt(len(self.vectors_by_key)))) if self.vectors_by_key else 5
        top = scored[:k]

        sum_w = 0.0
        sum_w_sq = 0.0
        sum_w_wins = 0.0
        for sim, k2 in top:
            for o in self.outcomes_by_key.get(k2, []):
                sum_w += sim
                sum_w_sq += sim * sim
                if o > 0:
                    sum_w_wins += sim
        if sum_w == 0:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0,
                    "n_neighbor_keys": len(top)}
        p_mean = sum_w_wins / sum_w
        eff_n_float = (sum_w * sum_w) / sum_w_sq if sum_w_sq > 0 else 0.0
        eff_n = int(round(eff_n_float))
        eff_wins = int(round(p_mean * eff_n_float))
        p_lb = owe._wilson_lb(eff_wins, eff_n, owe.WILSON_Z_90)
        return {"effective_n": eff_n, "p_win_mean": p_mean, "p_win_lb_90": p_lb,
                "n_neighbor_keys": len(top)}

    def self_posterior(self, canonical_key: str) -> dict:
        outcomes = self.outcomes_by_key.get(canonical_key, [])
        n = len(outcomes)
        wins = sum(1 for o in outcomes if o > 0)
        p_mean = (wins / n) if n else 0.0
        p_lb = owe._wilson_lb(wins, n, owe.WILSON_Z_90)
        return {"n": n, "wins": wins, "p_win_mean": p_mean, "p_win_lb_90": p_lb}


def main():
    if not CSV_PATH.exists():
        print(f"MISSING: {CSV_PATH}", flush=True)
        sys.exit(1)

    print(f"Loading {CSV_PATH} ...", flush=True)
    rows: list[dict] = []
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
                    "asset": r.get("asset") or "",
                    "venue": r.get("venue") or "",
                    "side": r.get("side") or "",
                    "strategy_id": r.get("strategy_id") or "",
                })
            except Exception:
                continue

    rows.sort(key=lambda r: r["ts"])
    print(f"  loaded {len(rows)} usable rows, {len({r['key'] for r in rows})} unique keys", flush=True)
    if not rows:
        sys.exit(1)
    tape_t0 = rows[0]["ts"]
    tape_t1 = rows[-1]["ts"]
    print(f"  tape span: {(tape_t1 - tape_t0) / 86400:.2f} days", flush=True)

    strats = ("wilson", "protective")

    def _empty_bucket():
        return {s: {"bank_pnl": 0.0, "bank_n": 0, "reject_pnl": 0.0, "reject_n": 0,
                    "shadow_pnl": 0.0, "shadow_n": 0, "total_n": 0} for s in strats}

    decision_counts = {s: defaultdict(int) for s in strats}
    per_day: dict[int, dict] = defaultdict(_empty_bucket)
    per_asset: dict[str, dict] = defaultdict(_empty_bucket)
    per_venue: dict[str, dict] = defaultdict(_empty_bucket)
    per_side: dict[str, dict] = defaultdict(_empty_bucket)
    per_strategy: dict[str, dict] = defaultdict(_empty_bucket)

    idx = IncrementalIndex()
    rolling: deque[float] = deque(maxlen=ROLLING_PAYOFF_WINDOW)

    def _break_even() -> float:
        wins = [x for x in rolling if x > 0]
        losses = [abs(x) for x in rolling if x <= 0]
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        return owe.break_even_winrate(avg_w, avg_l, FEES_BPS)

    import time
    t_start = time.time()

    for i, r in enumerate(rows):
        key = r["key"]
        net_bps = r["net_bps"]
        day_idx = int((r["ts"] - tape_t0) // 86400)
        be = _break_even()

        # WILSON
        post = idx.self_posterior(key)
        if post["n"] == 0 or post["n"] < N_MIN_FOR_BANK:
            w_dec = "admit_shadow"
        elif post["p_win_lb_90"] >= be:
            w_dec = "admit_bank"
        elif post["p_win_mean"] >= be:
            w_dec = "admit_shadow"
        else:
            w_dec = "reject"

        # PROTECTIVE: Wilson + KNN reject override on bank/shadow admissions
        if w_dec == "reject":
            p_dec = "reject"
        else:
            knn_post = idx.neighbor_posterior(key, N_MIN_FOR_BANK)
            if (knn_post["effective_n"] >= N_MIN_FOR_BANK
                    and knn_post["p_win_mean"] < be
                    and knn_post["p_win_lb_90"] < be):
                p_dec = "reject"
            else:
                p_dec = w_dec

        for strat, dec in (("wilson", w_dec), ("protective", p_dec)):
            decision_counts[strat][dec] += 1
            for bucket_dict, bucket_key in (
                (per_day, day_idx),
                (per_asset, r["asset"]),
                (per_venue, r["venue"]),
                (per_side, r["side"]),
                (per_strategy, r["strategy_id"]),
            ):
                b = bucket_dict[bucket_key][strat]
                b["total_n"] += 1
                if dec == "admit_bank":
                    b["bank_pnl"] += net_bps
                    b["bank_n"] += 1
                elif dec == "admit_shadow":
                    b["shadow_pnl"] += net_bps
                    b["shadow_n"] += 1
                else:
                    b["reject_pnl"] += net_bps
                    b["reject_n"] += 1

        idx.add_outcome(key, net_bps)
        rolling.append(net_bps)

        if (i + 1) % 10000 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (len(rows) - (i + 1)) / rate
            print(f"  ... {i+1}/{len(rows)} replayed ({rate:.0f} rows/s, eta {eta:.0f}s)", flush=True)

    print(f"\nReplay complete in {time.time()-t_start:.1f}s", flush=True)
    print("\n=== AGGREGATE DECISION DISTRIBUTION ===", flush=True)
    for strat in strats:
        c = dict(decision_counts[strat])
        total = sum(c.values())
        print(f"  {strat:11s} total={total}  bank={c.get('admit_bank',0)}  "
              f"shadow={c.get('admit_shadow',0)}  reject={c.get('reject',0)}", flush=True)

    def _print_bucket(name, bucket_dict, label_width=22, min_n=20):
        print(f"\n=== PER-{name.upper()} BREAKDOWN (n>={min_n}) ===", flush=True)
        header = f"  {name[:label_width]:<{label_width}s} {'n':>6}  {'W_bank':>10} {'P_bank':>10}  {'W_rej':>11} {'P_rej':>11}  {'P-W bank':>10} {'P-W avoided':>12}"
        print(header, flush=True)
        regressions = []
        sorted_keys = sorted(bucket_dict.keys(), key=lambda k: -bucket_dict[k]["wilson"]["total_n"])
        for bk in sorted_keys:
            w_d = bucket_dict[bk]["wilson"]
            p_d = bucket_dict[bk]["protective"]
            n = w_d["total_n"]
            if n < min_n:
                continue
            bank_diff = p_d["bank_pnl"] - w_d["bank_pnl"]
            avoided = w_d["reject_pnl"] - p_d["reject_pnl"]
            label = str(bk)[:label_width]
            marker = "  "
            if bank_diff < -0.5:
                marker = " *"
                regressions.append((bk, "bank_regression", round(bank_diff, 2)))
            elif avoided < -1.0:
                marker = " ~"
                regressions.append((bk, "rejected_winners", round(avoided, 2)))
            print(f"{marker}{label:<{label_width}s} {n:>6}  "
                  f"{w_d['bank_pnl']:>+10.1f} {p_d['bank_pnl']:>+10.1f}  "
                  f"{w_d['reject_pnl']:>+11.1f} {p_d['reject_pnl']:>+11.1f}  "
                  f"{bank_diff:>+10.2f} {avoided:>+12.2f}", flush=True)
        if not regressions:
            shown = sum(1 for bk in bucket_dict if bucket_dict[bk]["wilson"]["total_n"] >= min_n)
            print(f"  GENERALITY OK: protective dominates Wilson on every {name.lower()} bucket ({shown} shown)", flush=True)
        else:
            print(f"  REGRESSIONS: {regressions}", flush=True)

    _print_bucket("Day", per_day, label_width=5, min_n=50)
    _print_bucket("Asset", per_asset, label_width=10, min_n=50)
    _print_bucket("Venue", per_venue, label_width=12, min_n=50)
    _print_bucket("Side", per_side, label_width=10, min_n=50)
    _print_bucket("Strategy", per_strategy, label_width=24, min_n=50)


if __name__ == "__main__":
    main()
