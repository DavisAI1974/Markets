"""Post-phase analyzer: surfaces sidelined winners and losses for each evidence mode.

Designed to run after EVERY phase ships, against the 67k spot-check tape. Same
input data, different cohort views, so we can quantify what each phase improved
and what's still leaking.

Cohorts surfaced per evidence mode (wilson / protective / in_flight_promote):

  1. SIDELINED BIG WINNERS  - decisions other than admit_bank, but net_bps was
                              substantial (>= BIG_WINNER_BPS_THRESHOLD).
                              These are PnL the mode left on the table.
                              Split into:
                              a. Rejected winners (decision=reject)
                              b. Shadow winners (decision=admit_shadow)

  2. ADMITTED LOSERS       - decisions to admit_bank but net_bps was negative.
                              These are PnL the mode actively lost.
                              Subset flagged:
                              a. FAKEOUTS - promoted via Signal A (reached_20bps_
                                 within_30m) with tte_20bps_min < 3 min (fast
                                 spike that reversed). Top failure pattern of
                                 Phase 1.

  3. ADMITTED WINNERS (CONTEXT) - decision=admit_bank AND net_bps > 0.
                              Per-strategy/venue/side breakdown so we can see
                              whether the mode found the right cohort.

For each cohort the report surfaces:
  - Total count and total $ impact (at $10k notional, 1 bps = $1)
  - Per-strategy / per-venue / per-side breakdowns
  - Top N examples with key path metrics
  - Suggested fix category

Usage:
    python analyze_sidelined_and_losses.py            # all modes
    python analyze_sidelined_and_losses.py --mode in_flight_promote
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import oracle_winner_evidence as owe
import oracle_winner_trade_memory as owtm
from markets_evidence_knn import (
    _identity_tuple, _key_components, _cosine_sparse,
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

# Cohort thresholds — economic, not tape-tuned.
BIG_WINNER_BPS_THRESHOLD = 15.0   # "big winner" >= 15 bps net (above-median)
BIG_LOSER_BPS_THRESHOLD = -15.0   # significant loss (top decile of losers)
FAKEOUT_TTE_20_MAX_MIN = 3.0      # Signal A firing this fast = likely fakeout
TOP_N_EXAMPLES = 10


def _parse_float(v):
    if v is None or v == "" or v == "None":
        return None
    try:
        return float(v)
    except ValueError:
        return None


class IncrementalIndex:
    """K-NN index + Wilson posterior tracker — same as the spot-checks."""

    def __init__(self):
        self.vocab = {}
        self.vectors_by_key = {}
        self.outcomes_by_key = defaultdict(list)
        self.keys_by_identity = defaultdict(list)

    def _key_vector(self, k):
        out = {}
        for pos, val in _key_components(k):
            key = (pos, val)
            idx = self.vocab.get(key)
            if idx is None:
                idx = len(self.vocab)
                self.vocab[key] = idx
            out[idx] = 1.0
        return out

    def add_outcome(self, k, net_bps):
        if k not in self.vectors_by_key:
            self.vectors_by_key[k] = self._key_vector(k)
            self.keys_by_identity[_identity_tuple(k)].append(k)
        self.outcomes_by_key[k].append(net_bps)

    def self_posterior(self, k):
        outcomes = self.outcomes_by_key.get(k, [])
        n = len(outcomes)
        wins = sum(1 for o in outcomes if o > 0)
        return {"n": n, "wins": wins,
                "p_win_mean": wins / n if n else 0.0,
                "p_win_lb_90": owe._wilson_lb(wins, n, owe.WILSON_Z_90)}

    def neighbor_posterior(self, k):
        if not self.vocab:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0}
        qv = {}
        for pos, val in _key_components(k):
            i = self.vocab.get((pos, val))
            if i is not None:
                qv[i] = 1.0
        if not qv:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0}
        ident = _identity_tuple(k)
        scored = []
        for k2 in self.keys_by_identity.get(ident, []):
            sim = _cosine_sparse(qv, self.vectors_by_key[k2])
            if sim >= MIN_SIMILARITY:
                scored.append((sim, k2))
        scored.sort(reverse=True)
        top = scored[:max(5, round(math.sqrt(len(self.vectors_by_key))))]
        sw = swsq = sww = 0.0
        for sim, k2 in top:
            for o in self.outcomes_by_key.get(k2, []):
                sw += sim
                swsq += sim * sim
                if o > 0:
                    sww += sim
        if sw == 0:
            return {"effective_n": 0, "p_win_mean": 0.0, "p_win_lb_90": 0.0}
        p_mean = sww / sw
        eff_n = int(round((sw * sw) / swsq)) if swsq > 0 else 0
        eff_wins = int(round(p_mean * eff_n))
        return {"effective_n": eff_n, "p_win_mean": p_mean,
                "p_win_lb_90": owe._wilson_lb(eff_wins, eff_n, owe.WILSON_Z_90)}


def _decide_wilson(post, be):
    if post["n"] == 0 or post["n"] < N_MIN_FOR_BANK:
        return "admit_shadow"
    if post["p_win_lb_90"] >= be:
        return "admit_bank"
    if post["p_win_mean"] >= be:
        return "admit_shadow"
    return "reject"


def _decide_protective(w_dec, knn, be):
    if w_dec == "reject":
        return "reject"
    if (knn["effective_n"] >= N_MIN_FOR_BANK
            and knn["p_win_mean"] < be
            and knn["p_win_lb_90"] < be):
        return "reject"
    return w_dec


def _should_in_flight_promote(r):
    """Post-hoc proxy for in-flight promotion (same as replay_spotcheck_in_flight_promote)."""
    tte_20 = _parse_float(r.get("tte_20bps_min", ""))
    if tte_20 is not None and tte_20 <= REACHED_WITHIN_MINUTES:
        return True, "reached_20bps_within_30m", tte_20
    hold_min = _parse_float(r.get("hold_min", ""))
    net_bps_per_min = _parse_float(r.get("net_bps_per_min", ""))
    if (hold_min is not None and hold_min >= HOLD_MIN_PROMOTE_THRESHOLD
            and net_bps_per_min is not None
            and net_bps_per_min >= NET_BPS_PER_MIN_QUALITY_FLOOR):
        return True, "hold_min_ge_60", None
    return False, None, None


def _replay(rows):
    """Single pass over all rows. Returns list of per-trade dicts with decisions
    for each mode + path metrics + outcome."""
    idx = IncrementalIndex()
    rolling = deque(maxlen=ROLLING_PAYOFF_WINDOW)
    out = []
    for r in rows:
        wins = [x for x in rolling if x > 0]
        losses = [abs(x) for x in rolling if x <= 0]
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        be = owe.break_even_winrate(avg_w, avg_l, FEES_BPS)

        post = idx.self_posterior(r["key"])
        w_dec = _decide_wilson(post, be)
        knn = idx.neighbor_posterior(r["key"]) if w_dec != "reject" else None
        p1_dec = _decide_protective(w_dec, knn, be) if knn is not None else "reject"

        if p1_dec == "admit_shadow":
            fired, signal_name, tte_at_fire = _should_in_flight_promote(r)
            if fired:
                ifp_dec = "admit_bank"
            else:
                ifp_dec = "admit_shadow"
        else:
            ifp_dec = p1_dec
            fired, signal_name, tte_at_fire = False, None, None

        out.append({
            **r,
            "self_n": post["n"],
            "wilson_dec": w_dec,
            "protective_dec": p1_dec,
            "in_flight_promote_dec": ifp_dec,
            "in_flight_signal": signal_name if fired else None,
            "in_flight_tte_at_fire": tte_at_fire,
        })
        idx.add_outcome(r["key"], r["net_bps"])
        rolling.append(r["net_bps"])
    return out


def _print_breakdown(label, records, key_fn, value_key="net_bps", min_count=1):
    """Per-bucket aggregation: count, total $, mean."""
    buckets = defaultdict(lambda: {"n": 0, "sum": 0.0, "wins": 0})
    for rec in records:
        b = key_fn(rec)
        buckets[b]["n"] += 1
        buckets[b]["sum"] += rec[value_key]
        if rec[value_key] > 0:
            buckets[b]["wins"] += 1
    print(f"\n  By {label}:", flush=True)
    rows = sorted(buckets.items(), key=lambda kv: -abs(kv[1]["sum"]))
    for bk, b in rows:
        if b["n"] < min_count:
            continue
        wr = b["wins"] / b["n"] * 100.0 if b["n"] else 0.0
        avg = b["sum"] / b["n"] if b["n"] else 0.0
        print(f"    {str(bk)[:30]:<30s}  n={b['n']:>5}  total=${b['sum']:+8.0f}  "
              f"avg=${avg:+6.1f}  wr={wr:5.1f}%", flush=True)


def _print_top_examples(records, top_n=TOP_N_EXAMPLES, fakeout_flag=False):
    if not records:
        return
    records = sorted(records, key=lambda r: -abs(r["net_bps"]))
    print(f"\n  Top {min(top_n, len(records))} by |net_bps|:", flush=True)
    for rec in records[:top_n]:
        tte_20 = _parse_float(rec.get("tte_20bps_min", ""))
        hold_min = _parse_float(rec.get("hold_min", ""))
        bpm = _parse_float(rec.get("net_bps_per_min", ""))
        tte_str = f"{tte_20:.1f}" if tte_20 is not None else "  -- "
        hold_str = f"{hold_min:.0f}" if hold_min is not None else "  -- "
        bpm_str = f"{bpm:+.2f}" if bpm is not None else "  ---- "
        fakeout_mark = ""
        if fakeout_flag and tte_20 is not None and tte_20 < FAKEOUT_TTE_20_MAX_MIN:
            fakeout_mark = " <-- FAKEOUT"
        signal_str = rec.get("in_flight_signal") or "-"
        print(f"    {rec['asset']:>3}/{rec['venue']:8s}/{rec['side']:4s}  "
              f"{rec['strategy_id'][:22]:<22s}  net={rec['net_bps']:+7.1f}  "
              f"tte_20={tte_str:>5s}m  hold={hold_str:>3s}m  bps/min={bpm_str:>7s}  "
              f"signal={signal_str:<24s}  self_n={rec['self_n']:>3}{fakeout_mark}",
              flush=True)


def analyze_mode(replayed, mode_name, decision_field):
    print("\n" + "=" * 100, flush=True)
    print(f"ANALYSIS: {mode_name.upper()}", flush=True)
    print("=" * 100, flush=True)

    # Aggregate decision counts
    counts = defaultdict(int)
    pnl = defaultdict(float)
    for r in replayed:
        d = r[decision_field]
        counts[d] += 1
        pnl[d] += r["net_bps"]
    print(f"\n  Decisions: bank={counts['admit_bank']}(${pnl['admit_bank']:+.0f})  "
          f"shadow={counts['admit_shadow']}(${pnl['admit_shadow']:+.0f})  "
          f"reject={counts['reject']}(${pnl['reject']:+.0f})", flush=True)

    # ---- COHORT 1: SIDELINED BIG WINNERS ----
    rejected_winners = [r for r in replayed
                        if r[decision_field] == "reject"
                        and r["net_bps"] >= BIG_WINNER_BPS_THRESHOLD]
    shadow_winners = [r for r in replayed
                      if r[decision_field] == "admit_shadow"
                      and r["net_bps"] >= BIG_WINNER_BPS_THRESHOLD]

    print(f"\n--- COHORT 1: SIDELINED BIG WINNERS (net_bps >= +{BIG_WINNER_BPS_THRESHOLD:.0f}) ---", flush=True)
    print(f"  Rejected winners: {len(rejected_winners)}  total left on table = "
          f"${sum(r['net_bps'] for r in rejected_winners):+.0f}", flush=True)
    print(f"  Shadow winners:   {len(shadow_winners)}  total left on table = "
          f"${sum(r['net_bps'] for r in shadow_winners):+.0f}", flush=True)
    total_sidelined = (sum(r['net_bps'] for r in rejected_winners)
                       + sum(r['net_bps'] for r in shadow_winners))
    print(f"  TOTAL SIDELINED $ = ${total_sidelined:+.0f}", flush=True)

    if rejected_winners:
        print("\n  >> Rejected winners breakdown:", flush=True)
        _print_breakdown("strategy", rejected_winners,
                         lambda r: r["strategy_id"], min_count=2)
        _print_breakdown("venue", rejected_winners, lambda r: r["venue"])
        _print_breakdown("side", rejected_winners, lambda r: r["side"])
        _print_top_examples(rejected_winners)

    if shadow_winners:
        print("\n  >> Shadow winners breakdown:", flush=True)
        _print_breakdown("strategy", shadow_winners,
                         lambda r: r["strategy_id"], min_count=2)
        _print_breakdown("venue", shadow_winners, lambda r: r["venue"])
        _print_breakdown("side", shadow_winners, lambda r: r["side"])
        _print_top_examples(shadow_winners)

    # ---- COHORT 2: ADMITTED LOSERS ----
    admitted_losers = [r for r in replayed
                       if r[decision_field] == "admit_bank"
                       and r["net_bps"] < 0]
    big_admitted_losers = [r for r in admitted_losers
                           if r["net_bps"] <= BIG_LOSER_BPS_THRESHOLD]

    print(f"\n--- COHORT 2: ADMITTED LOSERS (decision=admit_bank, net_bps < 0) ---", flush=True)
    print(f"  All admitted losers: {len(admitted_losers)}  total lost = "
          f"${sum(r['net_bps'] for r in admitted_losers):+.0f}", flush=True)
    print(f"  Big losers (net <= ${BIG_LOSER_BPS_THRESHOLD:.0f}): {len(big_admitted_losers)}  "
          f"total = ${sum(r['net_bps'] for r in big_admitted_losers):+.0f}", flush=True)

    # FAKEOUT subset
    fakeouts = [r for r in admitted_losers
                if r.get("in_flight_signal") == "reached_20bps_within_30m"
                and r.get("in_flight_tte_at_fire") is not None
                and r["in_flight_tte_at_fire"] < FAKEOUT_TTE_20_MAX_MIN]
    print(f"\n  >> FAKEOUTS (Signal A fired with tte_20bps_min < {FAKEOUT_TTE_20_MAX_MIN:.0f}m): "
          f"{len(fakeouts)} trades, total lost = ${sum(r['net_bps'] for r in fakeouts):+.0f}",
          flush=True)
    if fakeouts:
        _print_breakdown("strategy", fakeouts, lambda r: r["strategy_id"])
        _print_breakdown("venue", fakeouts, lambda r: r["venue"])
        _print_top_examples(fakeouts, fakeout_flag=True)

    if admitted_losers:
        print("\n  >> All admitted-loser breakdown:", flush=True)
        _print_breakdown("strategy", admitted_losers,
                         lambda r: r["strategy_id"], min_count=2)
        _print_breakdown("venue", admitted_losers, lambda r: r["venue"])
        _print_breakdown("side", admitted_losers, lambda r: r["side"])
        if not fakeouts:  # only show top if we didn't already (fakeouts subset)
            _print_top_examples(admitted_losers)

    # ---- COHORT 3: ADMITTED WINNERS (context) ----
    admitted_winners = [r for r in replayed
                        if r[decision_field] == "admit_bank"
                        and r["net_bps"] > 0]
    print(f"\n--- COHORT 3: ADMITTED WINNERS (context) ---", flush=True)
    print(f"  Admitted winners: {len(admitted_winners)}  total won = "
          f"${sum(r['net_bps'] for r in admitted_winners):+.0f}", flush=True)
    if admitted_winners:
        _print_breakdown("strategy", admitted_winners,
                         lambda r: r["strategy_id"], min_count=2)
        _print_breakdown("venue", admitted_winners, lambda r: r["venue"])
        _print_breakdown("side", admitted_winners, lambda r: r["side"])

    # ---- FIX SUGGESTIONS ----
    print(f"\n--- FIX SUGGESTIONS for {mode_name} ---", flush=True)

    if fakeouts:
        fakeout_loss = sum(r["net_bps"] for r in fakeouts)
        print(f"  [F1] FAKEOUT GATE: require tte_20bps_min >= {FAKEOUT_TTE_20_MAX_MIN:.0f}m before "
              f"Signal A promotes. Expected save: ${-fakeout_loss:+.0f}", flush=True)

    # Per-strategy negative bank PnL detection (Phase 1.5 candidate)
    strat_bank_pnl = defaultdict(float)
    strat_bank_n = defaultdict(int)
    for r in replayed:
        if r[decision_field] == "admit_bank":
            strat_bank_pnl[r["strategy_id"]] += r["net_bps"]
            strat_bank_n[r["strategy_id"]] += 1
    neg_strats = [(s, p, strat_bank_n[s]) for s, p in strat_bank_pnl.items() if p < 0]
    if neg_strats:
        neg_strats.sort(key=lambda x: x[1])
        total_neg = sum(p for _, p, _ in neg_strats)
        print(f"  [F2] STRATEGY-FAMILY FILTER: skip promotion for these net-negative "
              f"strategies. Expected save: ${-total_neg:+.0f}", flush=True)
        for s, p, n in neg_strats:
            print(f"        - {s}: n={n} bank_pnl=${p:+.0f}", flush=True)

    # Sidelined-big-winner concentration (Phase 2 allowlist target)
    if rejected_winners or shadow_winners:
        side_concentrations = defaultdict(float)
        for r in rejected_winners + shadow_winners:
            ctx = f"{r['asset']}|{r['venue']}|{r['side']}"
            side_concentrations[ctx] += r["net_bps"]
        top_sidelined_ctx = sorted(side_concentrations.items(),
                                    key=lambda kv: -kv[1])[:5]
        print(f"  [F3] ALLOWLIST UPGRADE: top 5 (asset|venue|side) by sidelined $:", flush=True)
        for ctx, total in top_sidelined_ctx:
            print(f"        - {ctx:25s}: ${total:+.0f}", flush=True)

    # Cover-by-15m exit check (hard negative gate from policy ground truth)
    not_covered_15m_losers = [r for r in admitted_losers
                              if r.get("cover_by_15m", "").lower() in ("false", "0", "")]
    if not_covered_15m_losers and len(not_covered_15m_losers) > 5:
        cv_loss = sum(r["net_bps"] for r in not_covered_15m_losers)
        print(f"  [F4] COVER-BY-15M EXIT: {len(not_covered_15m_losers)} admitted losers "
              f"never covered fees in 15m. Expected save if cut at 15m: ${-cv_loss:+.0f}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("all", "wilson", "protective", "in_flight_promote"),
                        default="all")
    args = parser.parse_args()

    if not CSV_PATH.exists():
        print(f"MISSING: {CSV_PATH}", flush=True)
        sys.exit(1)

    print(f"Loading {CSV_PATH} ...", flush=True)
    rows = []
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
                    "cover_by_15m": raw.get("cover_by_15m", ""),
                })
            except Exception:
                continue
    rows.sort(key=lambda r: r["ts"])
    print(f"  loaded {len(rows)} usable rows, {len({r['key'] for r in rows})} unique keys",
          flush=True)

    print("\nReplaying decisions (this takes ~30-60s) ...", flush=True)
    replayed = _replay(rows)
    print(f"  replayed {len(replayed)} trades", flush=True)

    modes_to_analyze = []
    if args.mode == "all":
        modes_to_analyze = [
            ("wilson", "wilson_dec"),
            ("protective", "protective_dec"),
            ("in_flight_promote", "in_flight_promote_dec"),
        ]
    else:
        modes_to_analyze = [(args.mode, f"{args.mode}_dec")]

    for mode_name, dec_field in modes_to_analyze:
        analyze_mode(replayed, mode_name, dec_field)

    print("\n" + "=" * 100, flush=True)
    print("END OF ANALYSIS", flush=True)
    print("=" * 100, flush=True)


if __name__ == "__main__":
    main()
