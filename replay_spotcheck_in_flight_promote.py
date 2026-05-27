"""Three-way spot check: wilson / protective_v1 / in_flight_promote over 67,728 trades.

In-flight promotion fires when a protective-shadow trade exhibits a winning shape
in flight (post-hoc proxied from per_trade.csv path metrics):

  Signal A  reached_20bps_within_30m  68% precision  8.2x lift
            fires when tte_20bps_min <= 30. At that moment net_bps = 20 by
            definition, so quality = 20 / tte_20bps_min >= 0.67 (passes the
            net_bps_per_min >= 0.3 gate trivially).

  Signal B  hold_min_ge_runners @ 60  86% precision  10.3x lift
            fires when hold_min >= 60 AND net_bps_per_min >= 0.3.
            Using final net_bps_per_min as the quality proxy at the 60-min
            check. This is conservative: a trade that ramped to +40 bps and
            faded would proxy as failing-quality even though it passed at
            minute 60. The live per-tick engine will have ground truth.

If a shadow promotes, the trade's FULL final net_bps attributes to bank.

Pass criteria for in_flight_promote vs protective_v1:
  - promoted trades net positive in AGGREGATE
  - no per-strategy bucket where promoted bank PnL is net negative
  - no per-venue bucket where promoted bank PnL is net negative (platform sanity)
  - promotions distributed across multiple venues (no single venue >70%)
  - reject_pnl unchanged vs protective_v1 (in-flight never rejects more)
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
from markets_in_flight_promote import (
    HOLD_MIN_PROMOTE_THRESHOLD, REACHED_NET_BPS_THRESHOLD, REACHED_WITHIN_MINUTES,
    NET_BPS_PER_MIN_QUALITY_FLOOR,
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

    def self_posterior(self, canonical_key: str) -> dict:
        outcomes = self.outcomes_by_key.get(canonical_key, [])
        n = len(outcomes)
        wins = sum(1 for o in outcomes if o > 0)
        p_mean = (wins / n) if n else 0.0
        p_lb = owe._wilson_lb(wins, n, owe.WILSON_Z_90)
        return {"n": n, "wins": wins, "p_win_mean": p_mean, "p_win_lb_90": p_lb}

    def neighbor_posterior(self, canonical_key: str) -> dict:
        if not self.vocab:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0}
        query_vec: dict[int, float] = {}
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


def _parse_float(v: str) -> float | None:
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _should_in_flight_promote(r: dict) -> tuple[bool, str | None]:
    """Post-hoc proxy for in-flight promotion from per_trade.csv path metrics.

    Returns (fired, signal_name).

    Signal A: tte_20bps_min <= 30
              quality at fire time = 20 / tte_20bps_min >= 0.67 (always passes)

    Signal B: hold_min >= 60 AND net_bps_per_min >= 0.3
              uses final net_bps_per_min as conservative proxy
    """
    # Signal A: reached_20bps_within_30m
    tte_20 = _parse_float(r.get("tte_20bps_min", ""))
    if tte_20 is not None and tte_20 <= REACHED_WITHIN_MINUTES:
        # Quality at fire time = 20 / tte_20 which is >= 20/30 = 0.67 > 0.3
        return True, "reached_20bps_within_30m"

    # Signal B: hold_min_ge_runners @ 60 (quality-gated)
    hold_min = _parse_float(r.get("hold_min", ""))
    net_bps_per_min = _parse_float(r.get("net_bps_per_min", ""))
    if (hold_min is not None and hold_min >= HOLD_MIN_PROMOTE_THRESHOLD
            and net_bps_per_min is not None
            and net_bps_per_min >= NET_BPS_PER_MIN_QUALITY_FLOOR):
        return True, "hold_min_ge_60"

    return False, None


STRATS = ("wilson", "protective_v1", "in_flight_promote")


def main():
    if not CSV_PATH.exists():
        print(f"MISSING: {CSV_PATH}", flush=True)
        sys.exit(1)

    print(f"Loading {CSV_PATH} ...", flush=True)
    print(f"  signal thresholds: hold_min_ge_{HOLD_MIN_PROMOTE_THRESHOLD:.0f}  "
          f"reached_{REACHED_NET_BPS_THRESHOLD:.0f}bps_within_{REACHED_WITHIN_MINUTES:.0f}m  "
          f"quality_floor_{NET_BPS_PER_MIN_QUALITY_FLOOR:.2f}bps/min", flush=True)

    rows: list[dict] = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for raw in rdr:
            try:
                key = owtm.oracle_winner_canonical_trade_key(raw)
                ts = _parse_float(raw.get("exit_ts") or raw.get("entry_ts"))
                net_bps = _parse_float(raw.get("net_bps"))
                if not key or ts is None or ts == 0.0 or net_bps is None:
                    continue
                rows.append({
                    "ts": ts, "key": key, "net_bps": net_bps,
                    "asset": raw.get("asset") or "",
                    "venue": raw.get("venue") or "",
                    "side": raw.get("side") or "",
                    "strategy_id": raw.get("strategy_id") or "",
                    "tte_20bps_min": raw.get("tte_20bps_min", ""),
                    "hold_min": raw.get("hold_min", ""),
                    "net_bps_per_min": raw.get("net_bps_per_min", ""),
                })
            except Exception:
                continue
    rows.sort(key=lambda r: r["ts"])
    print(f"  loaded {len(rows)} usable rows, {len({r['key'] for r in rows})} unique keys", flush=True)
    if not rows:
        sys.exit(1)
    tape_t0 = rows[0]["ts"]

    def _empty_bucket():
        return {s: {"bank_pnl": 0.0, "bank_n": 0, "reject_pnl": 0.0, "reject_n": 0,
                    "shadow_pnl": 0.0, "shadow_n": 0, "total_n": 0} for s in STRATS}

    decision_counts = {s: defaultdict(int) for s in STRATS}
    per_day = defaultdict(_empty_bucket)
    per_asset = defaultdict(_empty_bucket)
    per_venue = defaultdict(_empty_bucket)
    per_side = defaultdict(_empty_bucket)
    per_strategy = defaultdict(_empty_bucket)

    # Promotion-specific tracking
    promotions = {
        "n": 0, "pnl": 0.0, "wins": 0, "losses": 0,
        "max_win": 0.0, "max_loss": 0.0,
        "by_signal": defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0}),
        "by_venue": defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0}),
    }
    promotion_log: list[dict] = []

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

        # PROTECTIVE_V1
        if w_dec == "reject":
            p1_dec = "reject"
        else:
            knn = idx.neighbor_posterior(key)
            if (knn["effective_n"] >= N_MIN_FOR_BANK
                    and knn["p_win_mean"] < be
                    and knn["p_win_lb_90"] < be):
                p1_dec = "reject"
            else:
                p1_dec = w_dec

        # IN_FLIGHT_PROMOTE — only intervenes on protective-shadow
        if p1_dec == "admit_shadow":
            fired, signal_name = _should_in_flight_promote(r)
            if fired:
                ifp_dec = "admit_bank"
                promotions["n"] += 1
                promotions["pnl"] += net_bps
                promotions["by_signal"][signal_name]["n"] += 1
                promotions["by_signal"][signal_name]["pnl"] += net_bps
                promotions["by_venue"][r["venue"]]["n"] += 1
                promotions["by_venue"][r["venue"]]["pnl"] += net_bps
                if net_bps > 0:
                    promotions["wins"] += 1
                    promotions["by_signal"][signal_name]["wins"] += 1
                    promotions["by_venue"][r["venue"]]["wins"] += 1
                    promotions["max_win"] = max(promotions["max_win"], net_bps)
                else:
                    promotions["losses"] += 1
                    promotions["max_loss"] = min(promotions["max_loss"], net_bps)
                if len(promotion_log) < 5000:
                    promotion_log.append({
                        "ts": r["ts"], "key": key, "net_bps": net_bps,
                        "asset": r["asset"], "venue": r["venue"], "side": r["side"],
                        "strategy_id": r["strategy_id"],
                        "signal": signal_name,
                        "tte_20bps_min": r["tte_20bps_min"],
                        "hold_min": r["hold_min"],
                        "net_bps_per_min": r["net_bps_per_min"],
                    })
            else:
                ifp_dec = "admit_shadow"
        else:
            ifp_dec = p1_dec  # reject or admit_bank passes through

        for strat, dec in (("wilson", w_dec), ("protective_v1", p1_dec), ("in_flight_promote", ifp_dec)):
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
                  f"promoted={promotions['n']}", flush=True)

    print(f"\nReplay complete in {time.time()-t_start:.1f}s", flush=True)

    print("\n=== AGGREGATE DECISION DISTRIBUTION ===", flush=True)
    for strat in STRATS:
        c = dict(decision_counts[strat])
        total = sum(c.values())
        print(f"  {strat:18s} total={total}  bank={c.get('admit_bank',0)}  "
              f"shadow={c.get('admit_shadow',0)}  reject={c.get('reject',0)}", flush=True)

    print("\n=== TRAJECTORY (bank PnL in bps over $10k notional) ===", flush=True)
    bps_to_dollars = lambda b: b * 10000.0 / 10000.0  # 1 bps on $10k = $1
    for strat in STRATS:
        # Total bank PnL across all buckets (per-day sums)
        bank_pnl = sum(per_day[d][strat]["bank_pnl"] for d in per_day)
        bank_n = sum(per_day[d][strat]["bank_n"] for d in per_day)
        shadow_pnl = sum(per_day[d][strat]["shadow_pnl"] for d in per_day)
        shadow_n = sum(per_day[d][strat]["shadow_n"] for d in per_day)
        all_pnl = bank_pnl + shadow_pnl
        ungated_pnl = bank_pnl + shadow_pnl + sum(per_day[d][strat]["reject_pnl"] for d in per_day)
        print(f"  {strat:18s}  bank_pnl={bps_to_dollars(bank_pnl):>+12.0f}$  "
              f"bank_n={bank_n:>5}  shadow_pnl={bps_to_dollars(shadow_pnl):>+12.0f}$  "
              f"shadow_n={shadow_n:>5}  all_admitted={bps_to_dollars(all_pnl):>+12.0f}$", flush=True)
        print(f"  {'':>18s}  if_ungated_would_be={bps_to_dollars(ungated_pnl):>+12.0f}$  "
              f"(this strategy's saved-loss vs ungated)", flush=True)

    print("\n=== IN-FLIGHT PROMOTION SUMMARY ===", flush=True)
    n = promotions["n"]
    if n == 0:
        print("  NO PROMOTIONS. Either no shadow trades fired the signals, or all "
              "fired trades were rejected by protective.", flush=True)
    else:
        pnl = promotions["pnl"]
        wr = promotions["wins"] / n
        avg = pnl / n
        print(f"  promoted_n={n}  total_pnl_bps={pnl:+.1f}  total_pnl_$={bps_to_dollars(pnl):+.0f}",
              flush=True)
        print(f"  avg_bps={avg:+.2f}  win_rate={wr:.1%}  "
              f"max_win={promotions['max_win']:+.1f}bps  max_loss={promotions['max_loss']:+.1f}bps",
              flush=True)
        if pnl > 0:
            print(f"  PASS: promotions net positive (+{bps_to_dollars(pnl):.0f}$)", flush=True)
        else:
            print(f"  FAIL: promotions net negative ({bps_to_dollars(pnl):+.0f}$)", flush=True)

        print("\n  By signal:", flush=True)
        for sig, s in promotions["by_signal"].items():
            wr_s = s["wins"] / s["n"] if s["n"] else 0.0
            print(f"    {sig:30s} n={s['n']:>4}  pnl_bps={s['pnl']:+8.1f}  "
                  f"win_rate={wr_s:.1%}  pnl_$={bps_to_dollars(s['pnl']):+.0f}", flush=True)

        print("\n  By venue:", flush=True)
        total_promoted = sum(s["n"] for s in promotions["by_venue"].values())
        for venue, s in promotions["by_venue"].items():
            wr_v = s["wins"] / s["n"] if s["n"] else 0.0
            pct = (s["n"] / total_promoted * 100) if total_promoted else 0.0
            marker = " *" if pct > 70.0 else "  "
            print(f"  {marker}{venue:12s} n={s['n']:>4}({pct:5.1f}%)  pnl_bps={s['pnl']:+8.1f}  "
                  f"win_rate={wr_v:.1%}  pnl_$={bps_to_dollars(s['pnl']):+.0f}", flush=True)

    def _print_bucket(name, bucket_dict, label_width=24, min_n=50, focus_strat="in_flight_promote"):
        print(f"\n=== PER-{name.upper()} BREAKDOWN (n>={min_n}, focus={focus_strat}) ===", flush=True)
        header = (f"  {name[:label_width]:<{label_width}s} {'n':>6}  "
                  f"{'W_bank':>9} {'P1_bank':>9} {'IFP_bank':>9}  "
                  f"{'IFP_bank_n':>10} {'IFP-P1_$':>10}")
        print(header, flush=True)
        regressions = []
        sorted_keys = sorted(bucket_dict.keys(), key=lambda k: -bucket_dict[k]["wilson"]["total_n"])
        for bk in sorted_keys:
            w_d = bucket_dict[bk]["wilson"]
            p1_d = bucket_dict[bk]["protective_v1"]
            ifp_d = bucket_dict[bk]["in_flight_promote"]
            n_b = w_d["total_n"]
            if n_b < min_n:
                continue
            diff = ifp_d["bank_pnl"] - p1_d["bank_pnl"]
            marker = "  "
            if ifp_d["bank_n"] > 0 and ifp_d["bank_pnl"] < 0:
                marker = " *"
                regressions.append((bk, "bank_negative",
                                    round(ifp_d["bank_pnl"], 1), ifp_d["bank_n"]))
            label = str(bk)[:label_width]
            print(f"{marker}{label:<{label_width}s} {n_b:>6}  "
                  f"{w_d['bank_pnl']:>+9.1f} {p1_d['bank_pnl']:>+9.1f} {ifp_d['bank_pnl']:>+9.1f}  "
                  f"{ifp_d['bank_n']:>10d} {diff:>+10.1f}", flush=True)
        if not regressions:
            shown = sum(1 for bk in bucket_dict if bucket_dict[bk]["wilson"]["total_n"] >= min_n)
            print(f"  GENERALITY OK: in_flight_promote bank PnL non-negative across all "
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
            print(f"  {r['asset']}/{r['venue']}/{r['side']:4s} {r['strategy_id'][:24]:<24s} "
                  f"signal={r['signal']:<28s} net={r['net_bps']:+.1f}  "
                  f"tte_20={r['tte_20bps_min']:>6s}  hold={r['hold_min']:>6s}  "
                  f"bps/min={r['net_bps_per_min']:>6s}", flush=True)


if __name__ == "__main__":
    main()
