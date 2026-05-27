"""Three-way spot check: wilson / protective_v1 / ev_ranker over 67,728 trades.

EV-ranker promotes admit_shadow -> admit_bank when:
  - protective said admit_shadow (wilson didn't reject AND K-NN didn't demote)
  - self_n >= n_min_for_bank
  - per-identity EV_LB >= meaningful_floor_bps

This spot-check uses an incremental per-identity payoff tracker so each trade's
ev_ranker decision sees ONLY ledger entries from trades that closed BEFORE it
in the same identity (causal replay).

Pass criteria for ev_ranker vs protective_v1:
  - ev_ranker promoted trades net positive in aggregate
  - no per-strategy bucket where ev_ranker bank trades are net negative
  - reject_pnl unchanged (ev_ranker only promotes, never rejects more)
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
from markets_ev_ranker import (
    expected_value_bps, IDENTITY_MIN_FOR_PAYOFF, DEFAULT_MEANINGFUL_FLOOR_BPS,
)

CSV_PATH = Path(r"E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv")
N_MIN_FOR_BANK = 10
FEES_BPS = 0.0
MIN_SIMILARITY = 0.5
ROLLING_PAYOFF_WINDOW = 500
MEANINGFUL_FLOOR_BPS = DEFAULT_MEANINGFUL_FLOOR_BPS


class IncrementalIndex:
    """Tracks both the K-NN index (for protective demote) and per-identity payoff
    (for ev_ranker promote)."""

    def __init__(self):
        self.vocab: dict[tuple[int, str], int] = {}
        self.vectors_by_key: dict[str, dict[int, float]] = {}
        self.outcomes_by_key: dict[str, list[float]] = defaultdict(list)
        self.keys_by_identity: dict[tuple, list[str]] = defaultdict(list)
        # Per-identity payoff running stats
        self.identity_wins: dict[tuple, list[float]] = defaultdict(list)
        self.identity_losses: dict[tuple, list[float]] = defaultdict(list)

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
        ident = _identity_tuple(canonical_key)
        if net_bps > 0:
            self.identity_wins[ident].append(net_bps)
        else:
            self.identity_losses[ident].append(abs(net_bps))

    def self_posterior(self, canonical_key: str) -> dict:
        outcomes = self.outcomes_by_key.get(canonical_key, [])
        n = len(outcomes)
        wins = sum(1 for o in outcomes if o > 0)
        p_mean = (wins / n) if n else 0.0
        p_lb = owe._wilson_lb(wins, n, owe.WILSON_Z_90)
        return {"n": n, "wins": wins, "p_win_mean": p_mean, "p_win_lb_90": p_lb}

    def neighbor_posterior(self, canonical_key: str) -> dict:
        if not self.vocab:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0,
                    "n_neighbor_keys": 0}
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
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0,
                    "n_neighbor_keys": len(top)}
        p_mean = sum_w_wins / sum_w
        eff_n_float = (sum_w * sum_w) / sum_w_sq if sum_w_sq > 0 else 0.0
        eff_n = int(round(eff_n_float))
        eff_wins = int(round(p_mean * eff_n_float))
        p_lb = owe._wilson_lb(eff_wins, eff_n, owe.WILSON_Z_90)
        return {"effective_n": eff_n, "p_win_mean": p_mean, "p_win_lb_90": p_lb,
                "n_neighbor_keys": len(top)}

    def identity_payoff(self, canonical_key: str, rolling_window: deque,
                        identity_min: int = IDENTITY_MIN_FOR_PAYOFF) -> dict:
        ident = _identity_tuple(canonical_key)
        wins = self.identity_wins.get(ident, [])
        losses = self.identity_losses.get(ident, [])
        n = len(wins) + len(losses)
        if n >= identity_min:
            return {
                "n": n,
                "n_wins": len(wins),
                "n_losses": len(losses),
                "avg_win_bps": (sum(wins) / len(wins)) if wins else 0.0,
                "avg_loss_bps": (sum(losses) / len(losses)) if losses else 0.0,
                "source": "identity",
                "identity": ident,
            }
        # Fallback to global rolling window
        rw = list(rolling_window)
        w = [x for x in rw if x > 0]
        l = [abs(x) for x in rw if x <= 0]
        return {
            "n": len(rw),
            "n_wins": len(w),
            "n_losses": len(l),
            "avg_win_bps": (sum(w) / len(w)) if w else 0.0,
            "avg_loss_bps": (sum(l) / len(l)) if l else 0.0,
            "source": "global_fallback",
            "identity": ident,
        }


STRATS = ("wilson", "protective_v1", "ev_ranker")


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
    print(f"  meaningful_floor_bps = {MEANINGFUL_FLOOR_BPS:.2f}", flush=True)
    print(f"  identity_min_for_payoff = {IDENTITY_MIN_FOR_PAYOFF}", flush=True)

    def _empty_bucket():
        return {s: {"bank_pnl": 0.0, "bank_n": 0, "reject_pnl": 0.0, "reject_n": 0,
                    "shadow_pnl": 0.0, "shadow_n": 0, "total_n": 0} for s in STRATS}

    decision_counts = {s: defaultdict(int) for s in STRATS}
    per_day: dict[int, dict] = defaultdict(_empty_bucket)
    per_asset: dict[str, dict] = defaultdict(_empty_bucket)
    per_venue: dict[str, dict] = defaultdict(_empty_bucket)
    per_side: dict[str, dict] = defaultdict(_empty_bucket)
    per_strategy: dict[str, dict] = defaultdict(_empty_bucket)

    ev_promoted: dict = {"n": 0, "pnl": 0.0, "wins": 0, "losses": 0,
                          "max_win": 0.0, "max_loss": 0.0,
                          "from_self": 0, "from_identity": 0}
    promotion_log: list[dict] = []
    ev_skipped_no_evidence = 0
    ev_below_floor = 0
    ev_floor_distribution_self: list[float] = []   # ev_lb when using self LB
    ev_floor_distribution_identity: list[float] = []  # ev_lb when using identity LB

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

        knn = None
        def _get_knn():
            nonlocal knn
            if knn is None:
                knn = idx.neighbor_posterior(key)
            return knn

        # PROTECTIVE_V1: K-NN demote-only
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

        # EV_RANKER: protective + EV-based promotion (self LB OR identity LB fallback)
        if p1_dec != "admit_shadow":
            ev_dec = p1_dec
        else:
            payoff = idx.identity_payoff(key, rolling)
            p_lb = None
            p_mean = None
            p_src = None
            if post["n"] >= N_MIN_FOR_BANK:
                p_lb = post["p_win_lb_90"]
                p_mean = post["p_win_mean"]
                p_src = "self"
            elif payoff["source"] == "identity" and payoff["n_wins"] >= 0:
                p_lb = owe._wilson_lb(payoff["n_wins"], payoff["n"], owe.WILSON_Z_90)
                p_mean = payoff["n_wins"] / payoff["n"] if payoff["n"] else 0.0
                p_src = "identity"

            if p_lb is None:
                ev_dec = "admit_shadow"
                ev_skipped_no_evidence += 1
            else:
                ev_lb = expected_value_bps(p_lb, payoff["avg_win_bps"], payoff["avg_loss_bps"], FEES_BPS)
                ev_mean = expected_value_bps(p_mean, payoff["avg_win_bps"], payoff["avg_loss_bps"], FEES_BPS)
                if p_src == "self":
                    ev_floor_distribution_self.append(ev_lb)
                else:
                    ev_floor_distribution_identity.append(ev_lb)

                if ev_lb >= MEANINGFUL_FLOOR_BPS:
                    ev_dec = "admit_bank"
                    ev_promoted["n"] += 1
                    ev_promoted["pnl"] += net_bps
                    ev_promoted[f"from_{p_src}"] += 1
                    if net_bps > 0:
                        ev_promoted["wins"] += 1
                        ev_promoted["max_win"] = max(ev_promoted["max_win"], net_bps)
                    else:
                        ev_promoted["losses"] += 1
                        ev_promoted["max_loss"] = min(ev_promoted["max_loss"], net_bps)
                    if len(promotion_log) < 5000:
                        promotion_log.append({
                            "ts": r["ts"], "key": key, "net_bps": net_bps,
                            "asset": r["asset"], "venue": r["venue"], "side": r["side"],
                            "strategy_id": r["strategy_id"],
                            "p_lb": round(p_lb, 3), "p_mean": round(p_mean, 3),
                            "p_src": p_src, "self_n": post["n"],
                            "avg_win_bps": round(payoff["avg_win_bps"], 1),
                            "avg_loss_bps": round(payoff["avg_loss_bps"], 1),
                            "ev_lb": round(ev_lb, 2), "ev_mean": round(ev_mean, 2),
                            "payoff_n": payoff["n"], "payoff_src": payoff["source"],
                        })
                else:
                    ev_dec = "admit_shadow"
                    ev_below_floor += 1

        for strat, dec in (("wilson", w_dec), ("protective_v1", p1_dec), ("ev_ranker", ev_dec)):
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
            rate = (i + 1) / (time.time() - t_start)
            eta = (len(rows) - (i + 1)) / rate
            print(f"  ... {i+1}/{len(rows)}  rate {rate:.0f}/s  eta {eta:.0f}s  "
                  f"ev_promoted={ev_promoted['n']}", flush=True)

    print(f"\nReplay complete in {time.time()-t_start:.1f}s", flush=True)
    print("\n=== AGGREGATE DECISION DISTRIBUTION ===", flush=True)
    for strat in STRATS:
        c = dict(decision_counts[strat])
        total = sum(c.values())
        print(f"  {strat:14s} total={total}  bank={c.get('admit_bank',0)}  "
              f"shadow={c.get('admit_shadow',0)}  reject={c.get('reject',0)}", flush=True)

    print("\n=== EV-RANKER PROMOTION SUMMARY ===", flush=True)
    print(f"  candidates_self_LB     (self_n >= {N_MIN_FOR_BANK}):     "
          f"{len(ev_floor_distribution_self)}", flush=True)
    print(f"  candidates_identity_LB (self_n < {N_MIN_FOR_BANK}, ident >= {IDENTITY_MIN_FOR_PAYOFF}): "
          f"{len(ev_floor_distribution_identity)}", flush=True)
    print(f"  skipped_no_evidence: {ev_skipped_no_evidence}", flush=True)
    n = ev_promoted["n"]
    if n == 0:
        print("  NO PROMOTIONS.", flush=True)
        for label, dist in [("self", ev_floor_distribution_self),
                            ("identity", ev_floor_distribution_identity)]:
            if dist:
                sd = sorted(dist)
                print(f"  EV_LB ({label})  n={len(sd)}  "
                      f"median={sd[len(sd)//2]:+.2f}  "
                      f"q90={sd[int(0.9*(len(sd)-1))]:+.2f}  "
                      f"q99={sd[int(0.99*(len(sd)-1))]:+.2f}  "
                      f"max={sd[-1]:+.2f}  floor={MEANINGFUL_FLOOR_BPS:.2f}", flush=True)
    else:
        pnl = ev_promoted["pnl"]
        wr = ev_promoted["wins"] / n
        avg = pnl / n
        print(f"  promoted_n={n}  total_pnl_bps={pnl:+.1f}  avg_bps={avg:+.2f}  "
              f"win_rate={wr:.1%}", flush=True)
        print(f"  from_self={ev_promoted['from_self']}  from_identity={ev_promoted['from_identity']}",
              flush=True)
        print(f"  max_win={ev_promoted['max_win']:+.1f}  max_loss={ev_promoted['max_loss']:+.1f}",
              flush=True)
        print(f"  below_floor (not promoted): {ev_below_floor}", flush=True)
        if pnl > 0:
            print(f"  PASS: ev_ranker promotions net positive (+{pnl:.1f} bps)", flush=True)
        else:
            print(f"  FAIL: ev_ranker promotions net negative ({pnl:+.1f} bps)", flush=True)

    def _print_bucket(name, bucket_dict, label_width=24, min_n=50):
        print(f"\n=== PER-{name.upper()} BREAKDOWN (n>={min_n}) ===", flush=True)
        print(f"  Columns: W=wilson, P1=protective_v1, EV=ev_ranker", flush=True)
        header = (f"  {name[:label_width]:<{label_width}s} {'n':>6}  "
                  f"{'W_bank':>8} {'P1_bank':>8} {'EV_bank':>8}  "
                  f"{'W_shad':>8} {'P1_shad':>8} {'EV_shad':>8}  "
                  f"{'W_rej':>8} {'P1_rej':>8} {'EV_rej':>8}  "
                  f"{'EV_bank_n':>10}")
        print(header, flush=True)
        regressions = []
        sorted_keys = sorted(bucket_dict.keys(), key=lambda k: -bucket_dict[k]["wilson"]["total_n"])
        for bk in sorted_keys:
            w_d = bucket_dict[bk]["wilson"]
            p1_d = bucket_dict[bk]["protective_v1"]
            ev_d = bucket_dict[bk]["ev_ranker"]
            n_b = w_d["total_n"]
            if n_b < min_n:
                continue
            marker = "  "
            if ev_d["bank_n"] > 0 and ev_d["bank_pnl"] < 0:
                marker = " *"
                regressions.append((bk, "bank_negative",
                                    round(ev_d["bank_pnl"], 2), ev_d["bank_n"]))
            # Total admitted (bank+shadow) drift between p1 and ev_ranker should be 0
            p1_admit = p1_d["bank_pnl"] + p1_d["shadow_pnl"]
            ev_admit = ev_d["bank_pnl"] + ev_d["shadow_pnl"]
            if abs(p1_admit - ev_admit) > 0.01:
                marker = " !"
                regressions.append((bk, "admit_drift", round(ev_admit - p1_admit, 2)))
            label = str(bk)[:label_width]
            print(f"{marker}{label:<{label_width}s} {n_b:>6}  "
                  f"{w_d['bank_pnl']:>+8.1f} {p1_d['bank_pnl']:>+8.1f} {ev_d['bank_pnl']:>+8.1f}  "
                  f"{w_d['shadow_pnl']:>+8.1f} {p1_d['shadow_pnl']:>+8.1f} {ev_d['shadow_pnl']:>+8.1f}  "
                  f"{w_d['reject_pnl']:>+8.1f} {p1_d['reject_pnl']:>+8.1f} {ev_d['reject_pnl']:>+8.1f}  "
                  f"{ev_d['bank_n']:>10d}", flush=True)
        if not regressions:
            shown = sum(1 for bk in bucket_dict if bucket_dict[bk]["wilson"]["total_n"] >= min_n)
            print(f"  GENERALITY OK: ev_ranker bank PnL non-negative across all "
                  f"{name.lower()} buckets ({shown} shown)", flush=True)
        else:
            print(f"  REGRESSIONS ({len(regressions)}): {regressions}", flush=True)

    _print_bucket("Day", per_day, label_width=5, min_n=50)
    _print_bucket("Asset", per_asset, label_width=10, min_n=50)
    _print_bucket("Venue", per_venue, label_width=12, min_n=50)
    _print_bucket("Side", per_side, label_width=10, min_n=50)
    _print_bucket("Strategy", per_strategy, label_width=24, min_n=50)

    if promotion_log:
        promotion_log.sort(key=lambda r: -abs(r["net_bps"]))
        print(f"\n=== TOP-15 PROMOTIONS BY |bps| ===", flush=True)
        for r in promotion_log[:15]:
            print(f"  ts={r['ts']:.0f}  {r['asset']}/{r['venue']}/{r['side']}  "
                  f"strat={r['strategy_id'][:24]:<24s}  "
                  f"net={r['net_bps']:+.1f}  "
                  f"p_lb={r['p_lb']:.3f}/{r['p_src']}(self_n={r['self_n']})  "
                  f"w={r['avg_win_bps']:.1f} l={r['avg_loss_bps']:.1f}  "
                  f"ev_lb={r['ev_lb']:+.2f}  ev_mean={r['ev_mean']:+.2f}  "
                  f"payoff_src={r['payoff_src']}",
                  flush=True)


if __name__ == "__main__":
    main()
