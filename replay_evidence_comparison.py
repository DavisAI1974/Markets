"""Offline replay: score every closed trade in the evidence ledger against three admission
strategies using ONLY the evidence available at that trade's timestamp.

Strategies compared:
  - wilson  : per-key Wilson LB (v1, current production gate)
  - knn     : K-NN-weighted Wilson over structurally similar keys
  - hybrid  : Wilson when self-N >= n_min, else K-NN

For each row, we record:
  - The key + ts + outcome (net_bps)
  - Each strategy's decision: admit_bank | admit_shadow | reject

Aggregated:
  - Decision distribution per strategy
  - Realized "bank PnL" per strategy = sum(net_bps for rows where that strategy said admit_bank)
  - Reject impact per strategy = sum(net_bps the strategy avoided by rejecting)
  - Disagreement matrix: rows where strategies diverged

The replay is window-agnostic — we're not tuning anything. We are measuring whether the
K-NN structure recovers signal the per-key Wilson misses (cold-start, sparse keys).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import oracle_winner_evidence as owe
import markets_evidence_knn as knn

LEDGER_PATH = Path(__file__).parent / "research" / "strategy_evolution" / "oracle_winner_evidence_ledger.jsonl"
N_MIN_FOR_BANK = 10
FEES_BPS = 0.0


def _wilson_decide_from_snapshot(canonical_key, ledger_snapshot, n_min, fees):
    rows = ledger_snapshot.get(canonical_key, [])
    n = len(rows)
    wins = sum(1 for r in rows if float(r.get("net_bps") or 0.0) > 0)
    p_mean = (wins / n) if n else 0.0
    p_lb = owe._wilson_lb(wins, n, owe.WILSON_Z_90)

    all_rows = [r for k_rows in ledger_snapshot.values() for r in k_rows]
    all_rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    recent = all_rows[:500]
    w = [float(r["net_bps"]) for r in recent if float(r.get("net_bps") or 0.0) > 0]
    l = [abs(float(r["net_bps"])) for r in recent if float(r.get("net_bps") or 0.0) <= 0]
    avg_win = (sum(w) / len(w)) if w else 0.0
    avg_loss = (sum(l) / len(l)) if l else 0.0
    break_even = owe.break_even_winrate(avg_win, avg_loss, fees)

    if n == 0:
        return "admit_shadow", "cold_start"
    if n < n_min:
        return "admit_shadow", f"insufficient_n_{n}"
    if p_lb >= break_even:
        return "admit_bank", f"lb_{p_lb:.3f}_ge_be_{break_even:.3f}"
    if p_mean >= break_even:
        return "admit_shadow", f"mean_{p_mean:.3f}_ge_be_{break_even:.3f}_lb_below"
    return "reject", f"mean_{p_mean:.3f}_lt_be_{break_even:.3f}"


def replay():
    if not LEDGER_PATH.exists():
        print(f"Ledger not found at {LEDGER_PATH}", file=sys.stderr)
        sys.exit(1)

    rows: list[dict] = []
    with LEDGER_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if r.get("key"):
                    rows.append(r)
            except json.JSONDecodeError:
                continue

    rows.sort(key=lambda r: float(r.get("ts") or 0.0))
    print(f"Loaded {len(rows)} ledger rows, {len({r['key'] for r in rows})} unique keys")

    strats = ("wilson", "knn", "hybrid", "protective")
    snapshot: dict[str, list[dict]] = defaultdict(list)
    decision_counts = {s: defaultdict(int) for s in strats}
    bank_pnl = {s: 0.0 for s in strats}
    bank_trades = {s: 0 for s in strats}
    shadow_pnl = {s: 0.0 for s in strats}
    reject_pnl = {s: 0.0 for s in strats}
    reject_count = {s: 0 for s in strats}

    # Per-bucket spot checks: tests whether the protective signal holds across
    # structurally different slices (assets, strategies, time-of-day), not just
    # in aggregate. If protective dominates Wilson on every bucket independently,
    # the design generalizes.
    def _empty_bucket():
        return {s: {"bank_pnl": 0.0, "bank_n": 0, "reject_pnl": 0.0, "reject_n": 0,
                    "shadow_pnl": 0.0, "shadow_n": 0, "total_n": 0} for s in strats}

    per_day: dict[int, dict] = defaultdict(_empty_bucket)
    per_asset: dict[str, dict] = defaultdict(_empty_bucket)
    per_strategy: dict[str, dict] = defaultdict(_empty_bucket)
    per_side: dict[str, dict] = defaultdict(_empty_bucket)
    tape_t0 = float(rows[0].get("ts") or 0.0) if rows else 0.0

    # Disagreement tracking
    disagreement_examples: list[dict] = []
    rebuild_every = 25  # rebuild K-NN index every N rows for speed; small enough to stay accurate
    index = None
    rows_since_rebuild = 0

    for i, r in enumerate(rows):
        key = r["key"]
        net_bps = float(r["net_bps"])

        if index is None or rows_since_rebuild >= rebuild_every:
            index = knn.build_index_from_ledger(snapshot)
            rows_since_rebuild = 0

        w_dec, w_reason = _wilson_decide_from_snapshot(key, snapshot, N_MIN_FOR_BANK, FEES_BPS)
        k_result = knn.decide_admission_knn(
            canonical_key=key,
            n_min_for_bank=N_MIN_FOR_BANK,
            fees_bps=FEES_BPS,
            index=index,
            ledger_snapshot=snapshot,
        )
        h_result = knn.decide_admission_hybrid(
            canonical_key=key,
            n_min_for_bank=N_MIN_FOR_BANK,
            fees_bps=FEES_BPS,
            index=index,
            ledger_snapshot=snapshot,
        )
        p_result = knn.decide_admission_protective(
            canonical_key=key,
            n_min_for_bank=N_MIN_FOR_BANK,
            fees_bps=FEES_BPS,
            index=index,
            ledger_snapshot=snapshot,
        )
        k_dec = k_result["decision"]
        h_dec = h_result["decision"]
        p_dec = p_result["decision"]

        day_idx = int((float(r.get("ts") or 0.0) - tape_t0) // 86400) if tape_t0 > 0 else 0
        # Parse asset, side, strategy out of the canonical key.
        # Format: STRATEGY|ASSET|SIDE|trade_option_state|score_band|...
        parts = key.split("|")
        strategy_id = parts[0] if len(parts) > 0 else "UNKNOWN"
        asset_id = parts[1] if len(parts) > 1 else "UNKNOWN"
        side_id = parts[2] if len(parts) > 2 else "UNKNOWN"

        for strat, dec in (("wilson", w_dec), ("knn", k_dec), ("hybrid", h_dec), ("protective", p_dec)):
            decision_counts[strat][dec] += 1
            for bucket_dict, bucket_key in (
                (per_day, day_idx),
                (per_asset, asset_id),
                (per_strategy, strategy_id),
                (per_side, side_id),
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
            if dec == "admit_bank":
                bank_pnl[strat] += net_bps
                bank_trades[strat] += 1
            elif dec == "admit_shadow":
                shadow_pnl[strat] += net_bps
            else:
                reject_pnl[strat] += net_bps
                reject_count[strat] += 1

        # Track examples where protective DIFFERS from wilson (the actionable insight)
        if p_dec != w_dec and len(disagreement_examples) < 25:
            disagreement_examples.append({
                "key": key,
                "net_bps": round(net_bps, 2),
                "wilson": w_dec,
                "knn": k_dec,
                "hybrid": h_dec,
                "protective": p_dec,
                "self_n_before": len(snapshot.get(key, [])),
                "knn_neighbors": k_result["posterior"]["n_neighbor_keys"],
                "knn_eff_n": k_result["posterior"]["effective_n"],
                "knn_p_lb": round(k_result["posterior"]["p_win_lb_90"], 3),
                "knn_p_mean": round(k_result["posterior"]["p_win_mean"], 3),
            })

        snapshot[key].append(r)
        rows_since_rebuild += 1

        if (i + 1) % 200 == 0:
            print(f"  ... {i+1}/{len(rows)} replayed", flush=True)

    print("\n=== DECISION DISTRIBUTION ===")
    for strat in strats:
        counts = dict(decision_counts[strat])
        total = sum(counts.values())
        print(f"  {strat:11s} total={total}  bank={counts.get('admit_bank',0)}  "
              f"shadow={counts.get('admit_shadow',0)}  reject={counts.get('reject',0)}")

    print("\n=== REALIZED PNL (if these decisions had run live) ===")
    print(f"  {'strategy':<12s} {'bank_trades':>12s} {'bank_pnl_bps':>14s} {'shadow_pnl_bps':>16s} {'reject_pnl_bps':>16s}")
    for strat in strats:
        print(f"  {strat:<12s} {bank_trades[strat]:>12d} {bank_pnl[strat]:>14.2f} "
              f"{shadow_pnl[strat]:>16.2f} {reject_pnl[strat]:>16.2f}")

    print("\n  Interpretation:")
    print("    bank_pnl_bps   = realized PnL of trades each strategy would have placed as bank")
    print("    reject_pnl_bps = realized PnL of trades each strategy avoided")
    print("                     (NEGATIVE reject_pnl = money saved by rejecting losers; POSITIVE = missed winners)")

    print("\n=== EXAMPLES WHERE PROTECTIVE DIFFERED FROM WILSON ===")
    if not disagreement_examples:
        print("  (none — protective never overrode wilson)")
    else:
        for ex in disagreement_examples[:15]:
            print(f"  net_bps={ex['net_bps']:+8.2f}  self_n={ex['self_n_before']:3d}  "
                  f"knn_n={ex['knn_neighbors']:2d} eff={ex['knn_eff_n']:3d} "
                  f"lb={ex['knn_p_lb']:.2f} mean={ex['knn_p_mean']:.2f}  "
                  f"W={ex['wilson'][:6]:6s}  P={ex['protective'][:6]:6s}")
            print(f"      key={ex['key']}")

    # Was protective right when it overrode? Add the verdict.
    saved_bps = 0.0
    missed_bps = 0.0
    overrides = 0
    for ex in disagreement_examples:
        if ex['protective'] == 'reject' and ex['wilson'] in ('admit_bank', 'admit_shadow'):
            overrides += 1
            if ex['net_bps'] <= 0:
                saved_bps += abs(ex['net_bps'])  # money saved
            else:
                missed_bps += ex['net_bps']  # missed winner
    if overrides:
        print(f"\n  Of {overrides} protective overrides shown:")
        print(f"    money saved (rejected losers): {saved_bps:.1f} bps")
        print(f"    money missed (rejected winners): {missed_bps:.1f} bps")
        print(f"    net gain from override:         {saved_bps - missed_bps:+.1f} bps")

    def _print_bucket(name: str, bucket_dict: dict, label_width: int = 22):
        print(f"\n=== PER-{name.upper()} BREAKDOWN (does protective hold up in every {name.lower()} bucket?) ===")
        header = f"  {name[:label_width]:<{label_width}s} {'n':>5}  {'W_bank':>9} {'P_bank':>9}  {'W_rej':>9} {'P_rej':>9}  {'P-W bank':>10} {'P-W net':>10}"
        print(header)
        regressions = []
        sorted_keys = sorted(bucket_dict.keys(), key=lambda k: -bucket_dict[k]["wilson"]["total_n"])
        for bk in sorted_keys:
            w_d = bucket_dict[bk]["wilson"]
            p_d = bucket_dict[bk]["protective"]
            n = w_d["total_n"]
            if n < 5:
                continue  # skip tiny buckets — noise
            bank_diff = p_d["bank_pnl"] - w_d["bank_pnl"]
            net_diff = w_d["reject_pnl"] - p_d["reject_pnl"]
            label = str(bk)[:label_width]
            marker = "  "
            if bank_diff < -0.5:
                marker = " *"
                regressions.append((bk, "bank", bank_diff))
            elif net_diff < -1.0:
                marker = " ~"
                regressions.append((bk, "net", net_diff))
            print(f"{marker}{label:<{label_width}s} {n:>5}  "
                  f"{w_d['bank_pnl']:>+9.1f} {p_d['bank_pnl']:>+9.1f}  "
                  f"{w_d['reject_pnl']:>+9.1f} {p_d['reject_pnl']:>+9.1f}  "
                  f"{bank_diff:>+10.2f} {net_diff:>+10.2f}")
        if not regressions:
            n_ok = sum(1 for bk in bucket_dict if bucket_dict[bk]["wilson"]["total_n"] >= 5)
            print(f"  GENERALITY OK: protective dominates Wilson on every non-trivial bucket ({n_ok} buckets shown)")
        else:
            print(f"  REGRESSIONS: {regressions}")

    _print_bucket("Day", per_day, label_width=5)
    _print_bucket("Asset", per_asset, label_width=10)
    _print_bucket("Side", per_side, label_width=10)
    _print_bucket("Strategy", per_strategy, label_width=22)


if __name__ == "__main__":
    replay()
