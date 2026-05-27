"""Three-way spot check: wilson / protective_v1 / protective_v2 over 67,728 trades.

Same incremental-index design as replay_spotcheck_full_historic.py. Runs all three
strategies in a single pass and prints per-bucket comparisons.

Strategy definitions (only protective_v2 differs from the baseline file):

  wilson         per-canonical-key Wilson LB vs break_even. Cold start defaults to shadow.

  protective_v1  Wilson + asymmetric K-NN: only demotes (admit_*  -> reject) when
                 identity-gated K-NN evidence is strongly negative
                 (eff_n >= n_min  AND  mean < be  AND  LB < be).

  protective_v2  protective_v1 + symmetric promotion: when Wilson says admit_shadow
                 AND identity-gated K-NN LB >= break_even AND eff_n >= n_min,
                 escalate shadow -> bank. Mirror of v1's demote criterion, using LB
                 (same threshold Wilson uses to admit to bank). Identity gate
                 controls the structural-correlation problem.

Pass criteria for v2 vs v1:
  - reject_pnl unchanged (we don't add new rejections in v2)  =>  total admitted PnL unchanged
  - bank trades promoted from shadow must be net positive in aggregate
  - no per-bucket regression: bank_pnl(v2) must be >= 0 in every bucket where bank_n(v2) > 0
  - MEAN_REVERSION_CHOP bucket flagged explicitly (the prior regression site pre-identity-gate)
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
from markets_evidence_knn import (
    _identity_tuple, _key_components, _cosine_sparse, IDENTITY_POSITIONS,
)

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
        out: dict[int, float] = {}
        for pos, val in _key_components(canonical_key):
            key = (pos, val)
            idx = self.vocab.get(key)
            if idx is None:
                idx = len(self.vocab)
                self.vocab[key] = idx
            out[idx] = 1.0
        return out

    def add_outcome(self, canonical_key: str, net_bps: float) -> None:
        if canonical_key not in self.vectors_by_key:
            self.vectors_by_key[canonical_key] = self._key_vector(canonical_key)
            self.keys_by_identity[_identity_tuple(canonical_key)].append(canonical_key)
        self.outcomes_by_key[canonical_key].append(net_bps)

    def neighbor_posterior(self, canonical_key: str, n_min: int) -> dict:
        if not self.vocab:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0,
                    "n_neighbor_keys": 0, "n_neighbor_trades": 0}
        query_vec: dict[int, float] = {}
        for pos, val in _key_components(canonical_key):
            idx = self.vocab.get((pos, val))
            if idx is not None:
                query_vec[idx] = 1.0
        if not query_vec:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0,
                    "n_neighbor_keys": 0, "n_neighbor_trades": 0}

        identity = _identity_tuple(canonical_key)
        candidate_keys = self.keys_by_identity.get(identity, [])
        scored: list[tuple[float, str]] = []
        for k2 in candidate_keys:
            sim = _cosine_sparse(query_vec, self.vectors_by_key[k2])
            if sim >= MIN_SIMILARITY:
                scored.append((sim, k2))
        scored.sort(reverse=True)
        k = max(5, round(math.sqrt(len(self.vectors_by_key))))
        top = scored[:k]

        sum_w = 0.0
        sum_w_sq = 0.0
        sum_w_wins = 0.0
        n_trades = 0
        for sim, k2 in top:
            for o in self.outcomes_by_key.get(k2, []):
                n_trades += 1
                sum_w += sim
                sum_w_sq += sim * sim
                if o > 0:
                    sum_w_wins += sim
        if sum_w == 0:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0,
                    "n_neighbor_keys": len(top), "n_neighbor_trades": n_trades}
        p_mean = sum_w_wins / sum_w
        eff_n_float = (sum_w * sum_w) / sum_w_sq if sum_w_sq > 0 else 0.0
        eff_n = int(round(eff_n_float))
        eff_wins = int(round(p_mean * eff_n_float))
        p_lb = owe._wilson_lb(eff_wins, eff_n, owe.WILSON_Z_90)
        return {"effective_n": eff_n, "p_win_mean": p_mean, "p_win_lb_90": p_lb,
                "n_neighbor_keys": len(top), "n_neighbor_trades": n_trades}

    def self_posterior(self, canonical_key: str) -> dict:
        outcomes = self.outcomes_by_key.get(canonical_key, [])
        n = len(outcomes)
        wins = sum(1 for o in outcomes if o > 0)
        p_mean = (wins / n) if n else 0.0
        p_lb = owe._wilson_lb(wins, n, owe.WILSON_Z_90)
        return {"n": n, "wins": wins, "p_win_mean": p_mean, "p_win_lb_90": p_lb}


STRATS = ("wilson", "protective_v1", "protective_v2")


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

    def _empty_bucket():
        return {s: {"bank_pnl": 0.0, "bank_n": 0, "reject_pnl": 0.0, "reject_n": 0,
                    "shadow_pnl": 0.0, "shadow_n": 0, "total_n": 0} for s in STRATS}

    decision_counts = {s: defaultdict(int) for s in STRATS}
    per_day: dict[int, dict] = defaultdict(_empty_bucket)
    per_asset: dict[str, dict] = defaultdict(_empty_bucket)
    per_venue: dict[str, dict] = defaultdict(_empty_bucket)
    per_side: dict[str, dict] = defaultdict(_empty_bucket)
    per_strategy: dict[str, dict] = defaultdict(_empty_bucket)

    # Track v2 promotions specifically (Wilson said shadow, v2 said bank).
    v2_promoted = {"n": 0, "pnl": 0.0, "wins": 0, "losses": 0}
    # Track v1 -> v2 movements per (bucket_type, bucket_key).
    movement_log: list[dict] = []

    idx = IncrementalIndex()
    rolling: deque[float] = deque(maxlen=ROLLING_PAYOFF_WINDOW)

    def _break_even() -> float:
        wins = [x for x in rolling if x > 0]
        losses = [abs(x) for x in rolling if x <= 0]
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        return owe.break_even_winrate(avg_w, avg_l, FEES_BPS)

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

        # Only compute K-NN once per row.
        knn_post = None
        def _get_knn():
            nonlocal knn_post
            if knn_post is None:
                knn_post = idx.neighbor_posterior(key, N_MIN_FOR_BANK)
            return knn_post

        # PROTECTIVE_V1: Wilson + K-NN demote-only.
        if w_dec == "reject":
            p1_dec = "reject"
        else:
            k = _get_knn()
            if (k["effective_n"] >= N_MIN_FOR_BANK
                    and k["p_win_mean"] < be
                    and k["p_win_lb_90"] < be):
                p1_dec = "reject"
            else:
                p1_dec = w_dec

        # PROTECTIVE_V2: v1 logic + symmetric promotion (shadow -> bank on positive K-NN).
        if w_dec == "reject":
            p2_dec = "reject"
        else:
            k = _get_knn()
            if (k["effective_n"] >= N_MIN_FOR_BANK
                    and k["p_win_mean"] < be
                    and k["p_win_lb_90"] < be):
                p2_dec = "reject"
            elif (w_dec == "admit_shadow"
                    and k["effective_n"] >= N_MIN_FOR_BANK
                    and k["p_win_lb_90"] >= be):
                p2_dec = "admit_bank"
            else:
                p2_dec = w_dec

        # Track v2 promotions explicitly.
        if p1_dec == "admit_shadow" and p2_dec == "admit_bank":
            v2_promoted["n"] += 1
            v2_promoted["pnl"] += net_bps
            if net_bps > 0:
                v2_promoted["wins"] += 1
            else:
                v2_promoted["losses"] += 1
            movement_log.append({
                "ts": r["ts"], "key": key, "net_bps": net_bps,
                "asset": r["asset"], "venue": r["venue"], "side": r["side"],
                "strategy_id": r["strategy_id"],
                "knn_eff_n": _get_knn()["effective_n"],
                "knn_lb": round(_get_knn()["p_win_lb_90"], 3),
                "knn_mean": round(_get_knn()["p_win_mean"], 3),
                "be": round(be, 3),
            })

        for strat, dec in (("wilson", w_dec), ("protective_v1", p1_dec), ("protective_v2", p2_dec)):
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
    for strat in STRATS:
        c = dict(decision_counts[strat])
        total = sum(c.values())
        print(f"  {strat:14s} total={total}  bank={c.get('admit_bank',0)}  "
              f"shadow={c.get('admit_shadow',0)}  reject={c.get('reject',0)}", flush=True)

    # v2 promotions summary
    print("\n=== V2 PROMOTIONS (shadow -> bank) ===", flush=True)
    n = v2_promoted["n"]
    if n == 0:
        print("  None. K-NN never found enough identity-gated positive evidence to promote.", flush=True)
    else:
        pnl = v2_promoted["pnl"]
        wr = v2_promoted["wins"] / n if n else 0.0
        avg = pnl / n if n else 0.0
        print(f"  promoted_n={n}  total_pnl_bps={pnl:+.1f}  avg_bps={avg:+.2f}  win_rate={wr:.1%}", flush=True)
        if pnl > 0:
            print("  PASS: promotions net positive in aggregate", flush=True)
        else:
            print("  FAIL: promotions net negative — K-NN identity-gated positive signal not reliable for bank-promotion", flush=True)

    def _print_bucket(name, bucket_dict, label_width=22, min_n=20):
        print(f"\n=== PER-{name.upper()} BREAKDOWN (n>={min_n}) ===", flush=True)
        print(f"  Columns: W=wilson, P1=protective_v1, P2=protective_v2", flush=True)
        header = (f"  {name[:label_width]:<{label_width}s} {'n':>6}  "
                  f"{'W_bank':>9} {'P1_bank':>9} {'P2_bank':>9}  "
                  f"{'W_shad':>9} {'P1_shad':>9} {'P2_shad':>9}  "
                  f"{'W_rej':>9} {'P1_rej':>9} {'P2_rej':>9}  "
                  f"{'P2-P1 bank':>11} {'P2-P1 shad':>11}")
        print(header, flush=True)
        regressions = []
        sorted_keys = sorted(bucket_dict.keys(), key=lambda k: -bucket_dict[k]["wilson"]["total_n"])
        for bk in sorted_keys:
            w_d = bucket_dict[bk]["wilson"]
            p1_d = bucket_dict[bk]["protective_v1"]
            p2_d = bucket_dict[bk]["protective_v2"]
            n_b = w_d["total_n"]
            if n_b < min_n:
                continue
            bank_diff = p2_d["bank_pnl"] - p1_d["bank_pnl"]
            shadow_diff = p2_d["shadow_pnl"] - p1_d["shadow_pnl"]
            label = str(bk)[:label_width]
            marker = "  "
            # Regression: v2 has bank trades AND they are net negative for the bucket.
            if p2_d["bank_n"] > 0 and p2_d["bank_pnl"] < 0:
                marker = " *"
                regressions.append((bk, "bank_negative", round(p2_d["bank_pnl"], 2), p2_d["bank_n"]))
            # Movement sanity: total admitted (bank+shadow) PnL must equal v1's, modulo float drift
            v1_admit = p1_d["bank_pnl"] + p1_d["shadow_pnl"]
            v2_admit = p2_d["bank_pnl"] + p2_d["shadow_pnl"]
            if abs(v1_admit - v2_admit) > 0.01:
                marker = " !"
                regressions.append((bk, "admit_total_drift", round(v2_admit - v1_admit, 2)))
            print(f"{marker}{label:<{label_width}s} {n_b:>6}  "
                  f"{w_d['bank_pnl']:>+9.1f} {p1_d['bank_pnl']:>+9.1f} {p2_d['bank_pnl']:>+9.1f}  "
                  f"{w_d['shadow_pnl']:>+9.1f} {p1_d['shadow_pnl']:>+9.1f} {p2_d['shadow_pnl']:>+9.1f}  "
                  f"{w_d['reject_pnl']:>+9.1f} {p1_d['reject_pnl']:>+9.1f} {p2_d['reject_pnl']:>+9.1f}  "
                  f"{bank_diff:>+11.2f} {shadow_diff:>+11.2f}", flush=True)
        if not regressions:
            shown = sum(1 for bk in bucket_dict if bucket_dict[bk]["wilson"]["total_n"] >= min_n)
            print(f"  GENERALITY OK: v2 has no bank-negative or admit-drift regressions on {name.lower()} ({shown} buckets shown)", flush=True)
        else:
            print(f"  REGRESSIONS ({len(regressions)}): {regressions}", flush=True)

    _print_bucket("Day", per_day, label_width=5, min_n=50)
    _print_bucket("Asset", per_asset, label_width=10, min_n=50)
    _print_bucket("Venue", per_venue, label_width=12, min_n=50)
    _print_bucket("Side", per_side, label_width=10, min_n=50)
    _print_bucket("Strategy", per_strategy, label_width=24, min_n=50)

    # Anti-regression check: MEAN_REVERSION_CHOP explicit
    print("\n=== MEAN_REVERSION_CHOP SPOT CHECK ===", flush=True)
    chop_buckets = [bk for bk in per_strategy if "MEAN_REVERSION_CHOP" in str(bk)]
    if not chop_buckets:
        print("  no MEAN_REVERSION_CHOP buckets present", flush=True)
    else:
        for bk in chop_buckets:
            w_d = per_strategy[bk]["wilson"]
            p1_d = per_strategy[bk]["protective_v1"]
            p2_d = per_strategy[bk]["protective_v2"]
            print(f"  {bk}: n={w_d['total_n']}", flush=True)
            print(f"    wilson         bank={w_d['bank_pnl']:+.1f}({w_d['bank_n']}) shadow={w_d['shadow_pnl']:+.1f}({w_d['shadow_n']}) reject={w_d['reject_pnl']:+.1f}({w_d['reject_n']})", flush=True)
            print(f"    protective_v1  bank={p1_d['bank_pnl']:+.1f}({p1_d['bank_n']}) shadow={p1_d['shadow_pnl']:+.1f}({p1_d['shadow_n']}) reject={p1_d['reject_pnl']:+.1f}({p1_d['reject_n']})", flush=True)
            print(f"    protective_v2  bank={p2_d['bank_pnl']:+.1f}({p2_d['bank_n']}) shadow={p2_d['shadow_pnl']:+.1f}({p2_d['shadow_n']}) reject={p2_d['reject_pnl']:+.1f}({p2_d['reject_n']})", flush=True)
            v1_admit = p1_d["bank_pnl"] + p1_d["shadow_pnl"]
            v2_admit = p2_d["bank_pnl"] + p2_d["shadow_pnl"]
            v2_bank = p2_d["bank_pnl"]
            verdict = "PASS"
            if abs(v1_admit - v2_admit) > 0.01:
                verdict = f"FAIL: admit total drift {v2_admit - v1_admit:+.2f}"
            elif p2_d["bank_n"] > 0 and v2_bank < 0:
                verdict = f"FAIL: bank PnL {v2_bank:+.2f} on {p2_d['bank_n']} trades"
            print(f"    -> {verdict}", flush=True)

    # Sample of v2 promotion details (top 10 by bps).
    if movement_log:
        print("\n=== TOP-10 V2 PROMOTIONS BY |bps| ===", flush=True)
        movement_log.sort(key=lambda r: -abs(r["net_bps"]))
        for r in movement_log[:10]:
            print(f"  ts={r['ts']:.0f}  asset={r['asset']} venue={r['venue']} side={r['side']} "
                  f"strat={r['strategy_id'][:30]}  net={r['net_bps']:+.1f}bps  "
                  f"knn_eff_n={r['knn_eff_n']} knn_lb={r['knn_lb']} knn_mean={r['knn_mean']} be={r['be']}", flush=True)


if __name__ == "__main__":
    main()
