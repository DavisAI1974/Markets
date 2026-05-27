"""Three-way spot check: wilson / protective / allowlist (= protective + allowlist upgrade).

Phase 2 layer: when wilson + protective say admit_shadow AND the candidate's
(asset, venue, side, session, family) matches a high-conviction entry from
_study_list.json, upgrade to admit_bank.

Uses per_trade.csv's bucket_session column directly (already computed by the
strategy_evolution worker). Family = strategy_id mapped to lowercase.

Pass criteria for allowlist vs protective:
  - allowlist-upgraded trades net positive in AGGREGATE
  - no per-strategy bucket where upgraded bank PnL is net negative
  - no per-venue bucket where upgraded bank PnL is net negative
  - reject_pnl unchanged vs protective (allowlist only upgrades, never rejects)
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
    _identity_tuple, _key_components, _cosine_sparse,
)
from markets_allowlist import (
    apply_allowlist_pre_protective, allowlist_summary,
)

CSV_PATH = Path(r"E:\Markets\_analysis_historical_rt_trade_shapes_20260523\per_trade.csv")
N_MIN_FOR_BANK = 10
FEES_BPS = 0.0
MIN_SIMILARITY = 0.5
ROLLING_PAYOFF_WINDOW = 500


class IncrementalIndex:
    """K-NN index + Wilson posterior — same as the other spot-checks."""

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


STRATS = ("wilson", "protective_v1", "allowlist")


def main():
    if not CSV_PATH.exists():
        print(f"MISSING: {CSV_PATH}", flush=True)
        sys.exit(1)

    summary = allowlist_summary()
    print(f"Allowlist loaded: {summary['count']} entries "
          f"(pnl_R >= {summary['min_pnl_r']}, trades >= {summary['min_trades']})", flush=True)
    for e in summary["entries"]:
        print(f"  {e['context']:<30s} x {e['family']:<28s}  "
              f"pnl_R={e['pnl_R']:>7.1f}  n={e['trades']:>4d}  wr={e['win_rate']:.2f}",
              flush=True)

    print(f"\nLoading {CSV_PATH} ...", flush=True)
    rows = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            try:
                key = owtm.oracle_winner_canonical_trade_key(r)
                ts = float(r.get("exit_ts") or r.get("entry_ts") or 0.0)
                net_bps_str = r.get("net_bps", "")
                if not key or ts == 0.0 or not net_bps_str:
                    continue
                net_bps = float(net_bps_str)
                rows.append({
                    "ts": ts, "key": key, "net_bps": net_bps,
                    "asset": r.get("asset") or "",
                    "venue": r.get("venue") or "",
                    "side": r.get("side") or "",
                    "strategy_id": r.get("strategy_id") or "",
                    "bucket_session": r.get("bucket_session") or "",
                })
            except Exception:
                continue
    rows.sort(key=lambda r: r["ts"])
    print(f"  loaded {len(rows)} usable rows", flush=True)
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
    per_session = defaultdict(_empty_bucket)

    upgrades = {"n": 0, "pnl": 0.0, "wins": 0, "losses": 0,
                 "max_win": 0.0, "max_loss": 0.0,
                 "by_context": defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0}),
                 "by_venue": defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0})}
    upgrade_log = []
    upgrade_attempt_misses = 0  # protective=admit_shadow but not in allowlist

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

        # ALLOWLIST v2: apply BEFORE K-NN demote. Allowlist trusted context
        # overrides per-key cold-start shadow; protective only demotes
        # non-allowlisted candidates.
        pre_al_dec, al_reason, al_entry = apply_allowlist_pre_protective(
            w_dec, r["asset"], r["venue"], r["side"], r["bucket_session"], r["strategy_id"],
        )
        if pre_al_dec == "admit_bank" and w_dec == "admit_shadow":
            # Allowlist promoted before protective could demote — bypass K-NN demote.
            al_dec = "admit_bank"
        elif pre_al_dec == w_dec:
            # No allowlist override — apply protective K-NN demote normally.
            al_dec = p1_dec
        else:
            al_dec = pre_al_dec

        if al_dec == "admit_bank" and w_dec == "admit_shadow":
            upgrades["n"] += 1
            upgrades["pnl"] += net_bps
            ctx_key = f"{r['asset']}|{r['venue']}|{r['side']}|{r['bucket_session']}|{r['strategy_id']}"
            upgrades["by_context"][ctx_key]["n"] += 1
            upgrades["by_context"][ctx_key]["pnl"] += net_bps
            upgrades["by_venue"][r["venue"]]["n"] += 1
            upgrades["by_venue"][r["venue"]]["pnl"] += net_bps
            if net_bps > 0:
                upgrades["wins"] += 1
                upgrades["by_context"][ctx_key]["wins"] += 1
                upgrades["by_venue"][r["venue"]]["wins"] += 1
                upgrades["max_win"] = max(upgrades["max_win"], net_bps)
            else:
                upgrades["losses"] += 1
                upgrades["max_loss"] = min(upgrades["max_loss"], net_bps)
            if len(upgrade_log) < 5000:
                upgrade_log.append({
                    "ts": r["ts"], "key": key, "net_bps": net_bps,
                    "asset": r["asset"], "venue": r["venue"], "side": r["side"],
                    "session": r["bucket_session"],
                    "strategy_id": r["strategy_id"],
                    "pnl_R": al_entry["pnl_R"], "n_seed": al_entry["trades"],
                    "wr_seed": al_entry["win_rate"],
                })
        elif p1_dec == "admit_shadow":
            upgrade_attempt_misses += 1

        for strat, dec in (("wilson", w_dec), ("protective_v1", p1_dec), ("allowlist", al_dec)):
            decision_counts[strat][dec] += 1
            for bucket_dict, bucket_key in (
                (per_day, day_idx),
                (per_asset, r["asset"]),
                (per_venue, r["venue"]),
                (per_side, r["side"]),
                (per_strategy, r["strategy_id"]),
                (per_session, r["bucket_session"]),
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
                  f"upgraded={upgrades['n']}", flush=True)

    print(f"\nReplay complete in {time.time()-t_start:.1f}s", flush=True)
    print("\n=== AGGREGATE DECISION DISTRIBUTION ===", flush=True)
    for strat in STRATS:
        c = dict(decision_counts[strat])
        total = sum(c.values())
        print(f"  {strat:14s} total={total}  bank={c.get('admit_bank',0)}  "
              f"shadow={c.get('admit_shadow',0)}  reject={c.get('reject',0)}", flush=True)

    print("\n=== ALLOWLIST UPGRADE SUMMARY ===", flush=True)
    n = upgrades["n"]
    print(f"  shadow candidates checked: {n + upgrade_attempt_misses}", flush=True)
    print(f"  upgraded shadow -> bank:   {n}", flush=True)
    print(f"  not on allowlist:          {upgrade_attempt_misses}", flush=True)
    if n > 0:
        pnl = upgrades["pnl"]
        wr = upgrades["wins"] / n
        avg = pnl / n
        print(f"\n  Aggregate upgraded PnL: {pnl:+.1f} bps  (${pnl:+.0f} at $10k notional)", flush=True)
        print(f"  avg per upgrade:        {avg:+.2f} bps  win_rate={wr:.1%}", flush=True)
        print(f"  max_win={upgrades['max_win']:+.1f}bps  max_loss={upgrades['max_loss']:+.1f}bps",
              flush=True)
        verdict = "PASS" if pnl > 0 else "FAIL"
        print(f"  {verdict}: upgraded trades net {'positive' if pnl > 0 else 'NEGATIVE'} (${pnl:+.0f})",
              flush=True)
        print("\n  By context:", flush=True)
        rows_sorted = sorted(upgrades["by_context"].items(), key=lambda kv: -kv[1]["pnl"])
        for ctx, s in rows_sorted:
            wrc = s["wins"] / s["n"] if s["n"] else 0.0
            print(f"    {ctx:<55s}  n={s['n']:>4}  pnl_bps={s['pnl']:>+8.1f}  wr={wrc:.1%}",
                  flush=True)
        print("\n  By venue:", flush=True)
        for v, s in upgrades["by_venue"].items():
            wrv = s["wins"] / s["n"] if s["n"] else 0.0
            print(f"    {v:12s} n={s['n']:>4}  pnl_bps={s['pnl']:>+8.1f}  wr={wrv:.1%}",
                  flush=True)

    def _print_bucket(name, bucket_dict, label_width=24, min_n=50, focus="allowlist"):
        print(f"\n=== PER-{name.upper()} BREAKDOWN (n>={min_n}, focus={focus}) ===", flush=True)
        header = (f"  {name[:label_width]:<{label_width}s} {'n':>6}  "
                  f"{'W_bank':>9} {'P1_bank':>9} {'AL_bank':>9}  "
                  f"{'AL_bank_n':>10} {'AL-P1_$':>10}")
        print(header, flush=True)
        regressions = []
        sorted_keys = sorted(bucket_dict.keys(), key=lambda k: -bucket_dict[k]["wilson"]["total_n"])
        for bk in sorted_keys:
            w_d = bucket_dict[bk]["wilson"]
            p1_d = bucket_dict[bk]["protective_v1"]
            al_d = bucket_dict[bk]["allowlist"]
            n_b = w_d["total_n"]
            if n_b < min_n:
                continue
            diff = al_d["bank_pnl"] - p1_d["bank_pnl"]
            marker = "  "
            if al_d["bank_n"] > 0 and al_d["bank_pnl"] < 0:
                marker = " *"
                regressions.append((bk, "bank_negative",
                                    round(al_d["bank_pnl"], 1), al_d["bank_n"]))
            label = str(bk)[:label_width]
            print(f"{marker}{label:<{label_width}s} {n_b:>6}  "
                  f"{w_d['bank_pnl']:>+9.1f} {p1_d['bank_pnl']:>+9.1f} {al_d['bank_pnl']:>+9.1f}  "
                  f"{al_d['bank_n']:>10d} {diff:>+10.1f}", flush=True)
        if not regressions:
            shown = sum(1 for bk in bucket_dict if bucket_dict[bk]["wilson"]["total_n"] >= min_n)
            print(f"  GENERALITY OK: allowlist bank PnL non-negative across all "
                  f"{name.lower()} buckets ({shown} shown)", flush=True)
        else:
            print(f"  REGRESSIONS ({len(regressions)}): {regressions}", flush=True)

    _print_bucket("Day", per_day, label_width=5)
    _print_bucket("Asset", per_asset, label_width=10)
    _print_bucket("Venue", per_venue, label_width=12)
    _print_bucket("Side", per_side, label_width=10)
    _print_bucket("Session", per_session, label_width=16)
    _print_bucket("Strategy", per_strategy, label_width=24)

    if upgrade_log:
        upgrade_log.sort(key=lambda r: -abs(r["net_bps"]))
        print(f"\n=== TOP-15 ALLOWLIST UPGRADES BY |bps| ===", flush=True)
        for r in upgrade_log[:15]:
            print(f"  {r['asset']}/{r['venue']:8s}/{r['side']:4s}/{r['session']:<13s} "
                  f"{r['strategy_id'][:22]:<22s}  net={r['net_bps']:+7.1f}  "
                  f"(seed: pnl_R={r['pnl_R']:.1f} n={r['n_seed']} wr={r['wr_seed']:.2f})",
                  flush=True)


if __name__ == "__main__":
    main()
