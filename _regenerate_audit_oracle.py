"""
_regenerate_audit_oracle.py (S31 DATAFIX) — regenerate the hindsight-audit oracle
columns PER ROW from the append-only history archive, fixing the snapshot-clamp bug.

Root cause (S30): the original generator read oracle EXITS from E:\\Markets\\live_data
(the ~6h LRU snapshot). The audit ran 05-28 while every trade entered 05-23/24, so
every oracle exit clamped to the 05-28 snapshot window — exit_price/exit_ts were a
single constant per venue, and oracle_net_bps was computed against that stale exit.
The oracle ENTRY price was already real and per-row (bar@ts_utc); only the EXIT was
broken. [[markets-oracle-audit-snapshot-clamp]]

Approach (Greg-approved 2026-06-21: per-row ts_utc, uniform):
  Each audit row is an independent decision point keyed ASSET|venue|chunk|side at its
  OWN ts_utc. A chunk pattern recurs at many distinct times, so a single per-chunk
  label is the wrong granularity for this CSV (it mis-anchored 41.7% of matched rows).
  Instead, anchor EVERY row on its own ts_utc and recompute from the history archive:
    entry      = nearest archive close to ts_utc (== the generator's bar@ts_utc)
    horizon    = oracle_horizon_minutes (real per-row config; kept verbatim)
    best exit  = best-FAVORABLE close within (ts_utc, ts_utc + horizon*60]
                   buy : max close   sell : min close
    exit_ts    = the timestamp of that argmax/argmin bar  (fills the blank — gap A)
    net_bps    = sign*(exit/entry - 1)*1e4 - FEE_BPS      (buy sign +1 / sell -1)
    win        = net_bps > 0
  Same path for ALL 21,184 rows — no relabel-pool join, no per-chunk broadcast. The
  dipole relabel pool (_relabel_true_horizon_results.json) is a SEPARATE artifact for
  the coefficient analysis and is left untouched, so the S30 dipole verdict stands.

Guardrail (do not reintroduce the bug): exits come ONLY from the history archive via
markets_bar_loader.load_closes, bounded per trade by [entry, entry+horizon]. We load
with use_live_snapshot=False and an explicit global t_max so the current (06-21) live
snapshot can never leak a far-future "exit."

Inputs : research/strategy_evolution/live_mock_replay/live_hindsight_missed_winner_audit_rows.csv  (untouched)
Outputs: ...live_hindsight_missed_winner_audit_rows.corrected.csv   (every row recomputed)
         _regenerate_audit_oracle_results.json                       (run summary + verification)
"""
from __future__ import annotations

import bisect
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, r"E:\refrag\adapters")
from markets_bar_loader import load_closes  # noqa: E402

MARKETS = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(MARKETS, "research", "strategy_evolution", "live_mock_replay",
                     "live_hindsight_missed_winner_audit_rows.csv")
OUT = os.path.join(MARKETS, "research", "strategy_evolution", "live_mock_replay",
                   "live_hindsight_missed_winner_audit_rows.corrected.csv")
SUMMARY = os.path.join(MARKETS, "_regenerate_audit_oracle_results.json")

FEE_BPS = 10.0       # 5 bps/side round trip (audit inputs.fee_bps_per_side = 5)
NOTIONAL_USD = 1000.0
ENTRY_GAP_MAX_S = 120.0  # max acceptable gap between ts_utc and nearest archive bar


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    t0 = time.time()
    # --- read full audit ---
    with open(AUDIT, newline="") as f:
        rdr = csv.DictReader(f)
        cols = list(rdr.fieldnames)
        rows = list(rdr)
    if "oracle_relabel_status" not in cols:
        cols.append("oracle_relabel_status")
    print(f"audit rows: {len(rows)}  cols: {len(cols)}")

    # --- collect (asset,venue) pairs + global time bounds ---
    pairs = set()
    ts_vals, h_vals = [], []
    for r in rows:
        pairs.add((r["asset"], r["venue"]))
        try:
            ts_vals.append(float(r["ts_utc"]))
            h_vals.append(float(r["oracle_horizon_minutes"]))
        except (TypeError, ValueError):
            pass
    g_min, g_max = min(ts_vals), max(ts_vals)
    g_hmax = max(h_vals)
    print(f"ts_utc range: {_utc(g_min)} -> {_utc(g_max)}   max horizon: {g_hmax:.0f} min")
    print(f"(asset,venue) pairs: {sorted(pairs)}")

    # --- preload archive closes per pair ONCE (no live snapshot; bounded t_max) ---
    t_max = g_max + g_hmax * 60 + 120
    series = {}
    for a, v in sorted(pairs):
        cl = load_closes(asset=a, venue=v, t_min=g_min - 120, t_max=t_max,
                         use_live_snapshot=False)
        series[(a, v)] = ([c.ts for c in cl], [c.close for c in cl])
        cov = f"{_utc(cl[0].ts)} -> {_utc(cl[-1].ts)}" if cl else "NO BARS"
        print(f"  archive {a}/{v}: {len(cl)} bars   {cov}")

    def nearest(a, v, t):
        tsl, csl = series[(a, v)]
        if not tsl:
            return None, None
        i = bisect.bisect_left(tsl, t)
        cands = [j for j in (i - 1, i) if 0 <= j < len(tsl)]
        if not cands:
            return None, None
        j = min(cands, key=lambda k: abs(tsl[k] - t))
        return csl[j], tsl[j]

    # --- per-row recompute ---
    win_before = win_after = 0
    flips = w2l = l2w = 0
    n_corr = n_trunc = n_nobar = n_noentry = 0
    new_split = Counter()
    by_as = defaultdict(Counter)
    hold_new, hold_old = [], []          # corrected hold vs original (clamped) hold, seconds
    entry_gap_max = 0.0
    samples = []

    for r in rows:
        if str(r.get("is_oracle_winner_after_fees")).strip().lower() == "true":
            win_before += 1
        a, v, side = r["asset"], r["venue"], r["side"]
        try:
            ts = float(r["ts_utc"]); H = float(r["oracle_horizon_minutes"])
        except (TypeError, ValueError):
            ts = H = None
        if ts is None or H is None or H <= 0 or (a, v) not in series:
            r["oracle_relabel_status"] = "no_entry_bar"; n_noentry += 1
            continue

        old_exit_ts_raw = r.get("oracle_exit_ts_utc")  # capture before overwrite (for verification sample)
        entry, entry_ts = nearest(a, v, ts)
        if entry is None or entry <= 0 or abs(entry_ts - ts) > ENTRY_GAP_MAX_S:
            r["oracle_relabel_status"] = "no_entry_bar"; n_noentry += 1
            continue
        entry_gap_max = max(entry_gap_max, abs(entry_ts - ts))

        tsl, csl = series[(a, v)]
        i0 = bisect.bisect_right(tsl, ts)            # strictly after entry
        i1 = bisect.bisect_right(tsl, ts + H * 60)
        seg, seg_ts = csl[i0:i1], tsl[i0:i1]
        if not seg:
            r["oracle_relabel_status"] = "no_forward_bars"; n_nobar += 1
            continue

        if side == "buy":
            j = max(range(len(seg)), key=lambda k: seg[k])
            best = seg[j]; net = (best / entry - 1) * 1e4 - FEE_BPS
        else:
            j = min(range(len(seg)), key=lambda k: seg[k])
            best = seg[j]; net = (entry / best - 1) * 1e4 - FEE_BPS
        exit_ts = seg_ts[j]
        covered = tsl[-1] >= ts + H * 60
        is_win = net > 0
        new_split["win" if is_win else "lose"] += 1
        by_as[(a, side)]["win" if is_win else "lose"] += 1
        if is_win:
            win_after += 1
        # flip vs ORIGINAL label
        was_win = str(r.get("is_oracle_winner_after_fees")).strip().lower() == "true"
        if was_win != is_win:
            flips += 1
            if was_win:
                w2l += 1
            else:
                l2w += 1
        # verification: corrected hold vs original clamped hold
        try:
            hold_old.append(float(r["oracle_exit_ts_utc"]) - ts)
        except (TypeError, ValueError):
            pass
        hold_new.append(exit_ts - ts)

        pnl = net * NOTIONAL_USD / 1e4
        try:
            actual = float(r["actual_realized_pnl_usd"] or 0.0)
        except (TypeError, ValueError):
            actual = 0.0
        r["oracle_net_bps"] = f"{net:.8f}"
        r["oracle_net_pnl_usd"] = f"{pnl:.8f}"
        r["oracle_incremental_vs_actual_usd"] = f"{pnl - actual:.8f}"
        r["is_oracle_winner_after_fees"] = "True" if is_win else "False"
        r["oracle_entry_ts_utc"] = f"{ts:.7f}"
        r["oracle_entry_price"] = f"{entry:.8f}"
        r["oracle_exit_ts_utc"] = f"{exit_ts:.7f}"
        r["oracle_exit_price"] = f"{best:.8f}"
        r["oracle_horizon_minutes"] = r["oracle_horizon_minutes"]
        r["oracle_relabel_status"] = "corrected" if covered else "corrected_horizon_truncated"
        n_corr += 1
        if not covered:
            n_trunc += 1
        if len(samples) < 6:
            samples.append({
                "unique_key": r["unique_key"], "side": side, "ts_utc": ts,
                "entry_price": round(entry, 4), "exit_ts": exit_ts,
                "exit_price": round(best, 4), "net_bps": round(net, 4),
                "hold_min_new": round((exit_ts - ts) / 60, 2),
                "old_exit_ts_utc": old_exit_ts_raw,
                "old_exit_utc": _utc(old_exit_ts_raw) if old_exit_ts_raw else None,
                "new_exit_utc": _utc(exit_ts),
                "old_hold_days": round((float(old_exit_ts_raw) - ts) / 86400, 2) if old_exit_ts_raw else None,
            })

    # --- reconcile miss_type to the corrected winner flag ---
    # Rule recovered from the original CSV (reproduces it 21184/21184, 0 mismatch):
    #   winner + decision==opened -> exit_missed_or_fee_leak
    #   winner + skipped          -> missed_entry
    #   non-winner                -> not_a_hindsight_winner
    # decision/blocker_reason are historical system facts (oracle-independent) and kept.
    mt_before = Counter(r.get("miss_type", "") for r in rows)
    mt_changed = 0
    for r in rows:
        is_win = str(r.get("is_oracle_winner_after_fees")).strip().lower() == "true"
        new_mt = ("exit_missed_or_fee_leak" if r.get("decision") == "opened" else "missed_entry") \
            if is_win else "not_a_hindsight_winner"
        if r.get("miss_type") != new_mt:
            mt_changed += 1
        r["miss_type"] = new_mt
    mt_after = Counter(r.get("miss_type", "") for r in rows)

    # --- write corrected CSV ---
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    def stats(xs):
        if not xs:
            return None
        xs = sorted(xs)
        n = len(xs)
        return {"n": n, "min": round(xs[0], 1), "p50": round(xs[n // 2], 1),
                "max": round(xs[-1], 1), "mean": round(sum(xs) / n, 1)}

    summary = {
        "schema": "regenerate_audit_oracle_v1",
        "approach": "per-row ts_utc anchor; best-favorable exit within oracle_horizon_minutes from history archive; fee 10bps",
        "fee_bps": FEE_BPS, "notional_usd": NOTIONAL_USD,
        "source": os.path.basename(AUDIT), "output": os.path.basename(OUT),
        "rows_total": len(rows),
        "rows_corrected": n_corr, "rows_horizon_truncated": n_trunc,
        "rows_no_forward_bars": n_nobar, "rows_no_entry_bar": n_noentry,
        "new_split": dict(new_split),
        "win_before": win_before, "win_after": win_after,
        "flips": flips, "was_win_now_lose": w2l, "was_lose_now_win": l2w,
        "miss_type_reconciled": True, "miss_type_rows_changed": mt_changed,
        "miss_type_before": dict(mt_before), "miss_type_after": dict(mt_after),
        "entry_gap_max_s": round(entry_gap_max, 3),
        "hold_seconds_corrected": stats(hold_new),
        "hold_seconds_original_clamped": stats(hold_old),
        "per_asset_side_split": {f"{a}|{s}": dict(c) for (a, s), c in sorted(by_as.items())},
        "samples": samples,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(SUMMARY, "w") as f:
        json.dump(summary, f, indent=2)

    # --- report ---
    print(f"\ncorrected={n_corr}  horizon_truncated={n_trunc}  no_forward_bars={n_nobar}  no_entry_bar={n_noentry}")
    print(f"NEW split: {dict(new_split)}  ({100*new_split['win']/max(n_corr,1):.1f}% win)")
    print(f"oracle-winner rows: before={win_before}  after={win_after}   flips={flips} (w->l {w2l}, l->w {l2w})")
    print(f"miss_type reconciled: {mt_changed} rows changed   {dict(mt_before)} -> {dict(mt_after)}")
    print(f"entry_gap_max: {entry_gap_max:.2f}s (<= {ENTRY_GAP_MAX_S}s required)")
    print(f"hold (corrected) sec: {stats(hold_new)}")
    print(f"hold (original/clamped) sec: {stats(hold_old)}")
    print(f"\nwrote {OUT}\nwrote {SUMMARY}\nelapsed {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
