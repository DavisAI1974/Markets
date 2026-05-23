"""
Exit-rule validation against the proven oracle-winner JSON universe (read-only).

Source of truth (LABELS):
  E:/Markets/research/strategy_evolution/oracle_winner_trade_list.json
  -> 1,316 unique entries (note: user-quoted 2,619 likely counts merged
     duplicate source rows -- merged_duplicate_sources adds up to 6,272;
     the canonical unique entries number is 1,316 per JSON entries[]).
  Policy says: target_notional_usd = $10,000, runtime admission requires
  exact canonical_trade_key membership, timestamps and venue are evidence
  and execution context only -- NOT admission keys.

Join source (EVIDENCE for entry/exit ts + prices):
  E:/Markets/research/strategy_evolution/live_mock_replay/live_hindsight_missed_winner_audit_rows.csv
  Join key: JSON.source_id == audit.unique_key (100% match rate verified).

Path source (TRADE SHAPE):
  E:/Markets/live_data/{asset_lc}_{venue_lc}_bins.json
  (rolling tick-bin buffer; current window covers the JSON winner timestamps).

Per trade:
  1. Get entry_px, oracle_entry_ts, oracle_exit_ts from audit row.
  2. Slice bins to [entry_ts, exit_ts], drop empty bars.
  3. Apply fee_bps assumption per venue (Bybit 10, Kraken 16, Coinbase 50).
  4. For each bar compute:
       fav_bps_net = ((entry_px - bar.low)/entry_px*1e4 - fee_bps)   for sells
                  or ((bar.high - entry_px)/entry_px*1e4 - fee_bps)  for buys
       cur_bps_net = ((entry_px - bar.mid)/entry_px*1e4 - fee_bps)   for sells
                  or ((bar.mid - entry_px)/entry_px*1e4 - fee_bps)  for buys
  5. Track max_net_bps as running max of fav_bps_net since entry.
  6. Apply candidate trailing-exit rule:
       arm when max_net_bps >= ARM_BPS
       once armed, giveback = max(GIVEBACK_FLOOR, GIVEBACK_FRAC * max_net_bps)
       exit when cur_net_bps <= max_net_bps - giveback
     Apply weak-trade cuts:
       at 15m: cut if cur_net_bps < 0 (fees not covered)
       at 15m: cut if cur_net_bps/15 < 0.10 (low bps/min)
  7. If never triggered, exit at oracle_exit_ts using cur_net_bps at that bar.
  8. Tag with bank-start gate (expected_oracle_net_bps_per_min >= 0.30 -> bank,
     else shadow-only).

Outputs (overwritten):
  per_trade.csv           - one row per JSON winner with simulated exit metrics
  threshold_sweep.csv     - per (arm, floor, frac) tuple aggregate metrics
  summary.json            - grouped aggregates by side/asset/duration/gate
  EXIT_RULE_VALIDATION.md - written report

Does NOT modify production code, runtime rules, or oracle_winner_trade_list.json.
"""
from __future__ import annotations
import json, csv, math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path
from statistics import median, mean, pstdev

ROOT = Path("E:/Markets")
OUT  = Path("E:/Markets/_analysis_exit_rule_validation_20260523")

JSON_PATH = ROOT / "research/strategy_evolution/oracle_winner_trade_list.json"
AUDIT_PATH = ROOT / "research/strategy_evolution/live_mock_replay/live_hindsight_missed_winner_audit_rows.csv"

VENUE_BINS = {
    ("BTC", "Coinbase"): ROOT / "live_data/btc_coinbase_bins.json",
    ("BTC", "Kraken"):   ROOT / "live_data/btc_kraken_bins.json",
    ("BTC", "Bybit"):    ROOT / "live_data/btc_bybit_perp_bins.json",
    ("ETH", "Coinbase"): ROOT / "live_data/eth_coinbase_bins.json",
    ("ETH", "Kraken"):   ROOT / "live_data/eth_kraken_bins.json",
    ("ETH", "Bybit"):    ROOT / "live_data/eth_bybit_perp_bins.json",
}

FEES_BPS = {"Coinbase": 50.0, "Kraken": 16.0, "Bybit": 10.0}
NOTIONAL = 10_000.0
BANK_GATE_BPS_PER_MIN = 0.30


def _safe(d, k, default=0.0):
    if not d: return default
    v = d.get(k, default)
    return v if v is not None else default

def _bar_ok(b):
    return ((b.get("n_trades") or 0) > 0
            and (b.get("low") or 0) > 0
            and (b.get("high") or 0) > 0
            and (b.get("mid") or 0) > 0)

def _stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs: return {"n": 0}
    xs_s = sorted(xs)
    n = len(xs_s)
    def q(p): return xs_s[max(0, min(n-1, int(p*n)))]
    return {"n": n, "median": median(xs_s), "mean": mean(xs_s),
            "p10": q(0.10), "p25": q(0.25), "p75": q(0.75), "p90": q(0.90),
            "min": xs_s[0], "max": xs_s[-1],
            "stdev": pstdev(xs_s) if n > 1 else 0.0}

def _share(xs):
    xs = [x for x in xs if x is not None]
    if not xs: return None
    return sum(1 for x in xs if x) / len(xs)

def _bucket_duration(m):
    try: m = float(m)
    except: return "unknown"
    if m < 15: return "00-15m"
    if m < 60: return "15-60m"
    if m < 180: return "60-180m"
    return "180m+"


def _load_bins(asset, venue, cache):
    key = (asset, venue)
    if key in cache: return cache[key]
    p = VENUE_BINS.get(key)
    if p is None or not p.exists():
        cache[key] = (None, None); return cache[key]
    d = json.load(open(p))
    items = sorted(((float(ts), bar) for ts, bar in d.items()), key=lambda x: x[0])
    ts_list = [t for t,_ in items]; bar_list = [b for _,b in items]
    cache[key] = (ts_list, bar_list)
    print(f"  loaded {key}: {len(ts_list):,} bars  [{ts_list[0]:.0f}..{ts_list[-1]:.0f}]")
    return cache[key]


def simulate_exit(entry_px, side, fee_bps, ts_list, bar_list,
                  entry_ts, exit_ts, arm_bps, gb_floor, gb_frac,
                  apply_weak_cuts=True):
    """Return per-trade simulation result dict, or None if cannot simulate."""
    if ts_list is None: return None
    if exit_ts <= entry_ts: return None
    # clamp to bin coverage
    t0 = max(entry_ts, ts_list[0])
    t1 = min(exit_ts,  ts_list[-1])
    if t0 >= t1: return None
    clamped = (entry_ts < ts_list[0]) or (exit_ts > ts_list[-1])
    lo = bisect_left(ts_list, t0); hi = bisect_right(ts_list, t1)
    win = [(ts_list[i], bar_list[i]) for i in range(lo, hi) if _bar_ok(bar_list[i])]
    if not win: return None

    max_net = -1e9
    max_net_ts = None
    armed = False
    sim_exit_net = None
    sim_exit_ts  = None
    sim_exit_reason = None
    cur_at_15m = None
    fav_at_15m = None

    for ts, b in win:
        # favorable execution-side prices (best possible exit at this bar)
        fav_px = b["low"] if side == "sell" else b["high"]
        cur_px = b["mid"]
        if side == "sell":
            fav_net = (entry_px - fav_px) / entry_px * 1e4 - fee_bps
            cur_net = (entry_px - cur_px) / entry_px * 1e4 - fee_bps
        else:
            fav_net = (fav_px - entry_px) / entry_px * 1e4 - fee_bps
            cur_net = (cur_px - entry_px) / entry_px * 1e4 - fee_bps
        if fav_net > max_net:
            max_net = fav_net; max_net_ts = ts

        # weak-trade cut at 15m
        min_from_entry = (ts - entry_ts) / 60.0
        if apply_weak_cuts and cur_at_15m is None and min_from_entry >= 15.0:
            cur_at_15m = cur_net
            fav_at_15m = max_net
            if cur_net < 0:
                sim_exit_net = cur_net; sim_exit_ts = ts; sim_exit_reason = "weak_cut_no_fee_cover_15m"; break
            if cur_net / 15.0 < 0.10:
                sim_exit_net = cur_net; sim_exit_ts = ts; sim_exit_reason = "weak_cut_low_bps_per_min_15m"; break

        if not armed and max_net >= arm_bps:
            armed = True

        if armed:
            giveback = max(gb_floor, gb_frac * max_net)
            if cur_net <= max_net - giveback:
                sim_exit_net = cur_net; sim_exit_ts = ts; sim_exit_reason = "trailing_giveback"; break

    if sim_exit_net is None:
        # never exited -- run to oracle exit (last bar in window)
        ts_last, b_last = win[-1]
        cur_px = b_last["mid"]
        if side == "sell":
            sim_exit_net = (entry_px - cur_px) / entry_px * 1e4 - fee_bps
        else:
            sim_exit_net = (cur_px - entry_px) / entry_px * 1e4 - fee_bps
        sim_exit_ts = ts_last; sim_exit_reason = "ran_to_oracle_exit"

    # diagnostics
    mfe_net = max_net
    capture_pct = (sim_exit_net / mfe_net) if mfe_net > 0 else None
    armed_flag = mfe_net >= arm_bps
    profitable = sim_exit_net > 0
    held_min = (sim_exit_ts - entry_ts) / 60.0 if sim_exit_ts and entry_ts else None

    return {
        "sim_exit_net_bps": sim_exit_net,
        "sim_exit_ts": sim_exit_ts,
        "sim_exit_reason": sim_exit_reason,
        "sim_held_min": held_min,
        "mfe_net_bps": mfe_net,
        "mfe_ts": max_net_ts,
        "armed": armed_flag,
        "profitable_after_fees": profitable,
        "capture_pct_of_mfe": capture_pct,
        "cur_at_15m_net_bps": cur_at_15m,
        "fav_at_15m_net_bps": fav_at_15m,
        "clamped_to_bin_coverage": clamped,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) Load JSON winners
    print("loading oracle winner JSON ...")
    j = json.load(open(JSON_PATH))
    entries = j.get("entries", [])
    print(f"  JSON unique entries: {len(entries):,}")
    print(f"  policy.target_notional_usd: ${j.get('policy',{}).get('target_notional_usd')}")

    # 2) Load audit CSV, build source_id lookup (winners only)
    print("loading audit CSV ...")
    audit = {}
    audit_n = audit_winners = 0
    with open(AUDIT_PATH) as f:
        for row in csv.DictReader(f):
            audit_n += 1
            if row.get("is_oracle_winner_after_fees") != "True":
                continue
            audit_winners += 1
            audit[row["unique_key"]] = row
    print(f"  audit rows: {audit_n:,}")
    print(f"  audit oracle-winner rows: {audit_winners:,}")

    # 3) Join JSON -> audit
    joined = []
    miss_audit = 0
    for e in entries:
        a = audit.get(e["source_id"])
        if not a:
            miss_audit += 1; continue
        try:
            ets = float(a["oracle_entry_ts_utc"])
            xts = float(a["oracle_exit_ts_utc"])
            epx = float(a["oracle_entry_price"])
            xpx = float(a["oracle_exit_price"])
            hzn = float(a.get("oracle_horizon_minutes") or 0)
            onb = float(a.get("oracle_net_bps") or 0)
            opn = float(a.get("oracle_net_pnl_usd") or 0)
        except Exception:
            continue
        joined.append({
            "json_source_id": e["source_id"],
            "canonical_trade_key": e["canonical_trade_key"],
            "side": e["side"], "asset": e["asset"], "venue": e["venue"],
            "strategy_id": e["strategy_id"],
            "bucket_session": e.get("bucket_session"),
            "trade_stage": e.get("trade_stage"),
            "trade_option_state": e.get("trade_option_state"),
            "pressure_watch_state": e.get("pressure_watch_state"),
            "trade_present_score": e.get("trade_present_score"),
            "mean_dipole": e.get("mean_dipole"),
            "dipole_acl1": e.get("dipole_acl1"),
            "volume_zscore": e.get("volume_zscore"),
            "entry_ts": ets, "exit_ts": xts,
            "entry_px": epx, "exit_px": xpx,
            "oracle_horizon_min": hzn,
            "oracle_net_bps": onb,
            "oracle_net_pnl_usd": opn,
            "oracle_net_bps_per_min": (onb / hzn) if hzn > 0 else None,
            "duration_bucket": _bucket_duration(hzn),
            "fee_bps": FEES_BPS.get(e["venue"], 25.0),
        })
    print(f"  joined JSON->audit: {len(joined):,}  (missing audit row: {miss_audit:,})")

    # 4) Tag bank-start gate
    for t in joined:
        bps_per_min = t.get("oracle_net_bps_per_min") or 0.0
        t["bank_gate_pass"] = bps_per_min >= BANK_GATE_BPS_PER_MIN

    n_bank = sum(1 for t in joined if t["bank_gate_pass"])
    n_shadow = len(joined) - n_bank
    print(f"  bank-gate (oracle_net_bps_per_min >= {BANK_GATE_BPS_PER_MIN}): bank={n_bank:,}  shadow={n_shadow:,}")

    # 5) Define rule grid + simulate
    print("\nrunning candidate rule sweep ...")
    bins_cache = {}
    # primary rule
    PRIMARY = ("arm=20", "floor=12", "frac=0.25", 20, 12, 0.25)
    arm_grid = [15, 20, 25, 30]
    floor_grid = [8, 12, 16]
    frac_grid = [0.20, 0.25, 0.33]
    rule_combos = []
    for a in arm_grid:
        for fl in floor_grid:
            for fr in frac_grid:
                rule_combos.append((a, fl, fr))
    # include primary explicitly first
    print(f"  combos to test: {len(rule_combos)} x {len(joined):,} trades")

    # Pre-load all bins once
    for (a, v) in VENUE_BINS:
        _load_bins(a, v, bins_cache)

    # Per-trade primary simulation (with primary rule) for per_trade.csv
    print(f"\nsimulating primary rule {PRIMARY} per trade ...")
    primary_results = []
    no_bins = no_sim = 0
    for t in joined:
        ts_list, bar_list = bins_cache.get((t["asset"], t["venue"]), (None, None))
        if ts_list is None:
            no_bins += 1; continue
        r = simulate_exit(t["entry_px"], t["side"], t["fee_bps"], ts_list, bar_list,
                          t["entry_ts"], t["exit_ts"], 20, 12, 0.25, apply_weak_cuts=True)
        if r is None:
            no_sim += 1; continue
        rr = dict(t); rr.update(r)
        primary_results.append(rr)
    print(f"  primary simulated: {len(primary_results):,}  no_bins: {no_bins:,}  no_sim: {no_sim:,}")

    # Threshold sweep (computes aggregate metrics across combos)
    print("\nrunning threshold sweep across combinations ...")
    sweep_rows = []
    for arm, floor, frac in rule_combos:
        sim_results = []
        for t in joined:
            ts_list, bar_list = bins_cache.get((t["asset"], t["venue"]), (None, None))
            if ts_list is None: continue
            r = simulate_exit(t["entry_px"], t["side"], t["fee_bps"], ts_list, bar_list,
                              t["entry_ts"], t["exit_ts"], arm, floor, frac, apply_weak_cuts=True)
            if r is None: continue
            sim_results.append({**t, **r})

        def _summarize(rows, label):
            if not rows: return None
            net = [r["sim_exit_net_bps"] for r in rows]
            mfe = [r["mfe_net_bps"] for r in rows]
            cap = [r["capture_pct_of_mfe"] for r in rows if r["capture_pct_of_mfe"] is not None and r["mfe_net_bps"] > 0]
            held = [r["sim_held_min"] for r in rows if r["sim_held_min"] is not None]
            n_prof = sum(1 for r in rows if r["profitable_after_fees"])
            n_armed = sum(1 for r in rows if r["armed"])
            # how often does exit trigger before MFE? (i.e., MFE_ts > exit_ts -> wait, we exit at exit_ts; if there's still upside after we exit, that's "too early")
            # we approximate: rows where MFE happens AFTER sim_exit_ts -> exited too early
            n_early = sum(1 for r in rows if (r["mfe_ts"] and r["sim_exit_ts"] and r["mfe_ts"] > r["sim_exit_ts"]))
            n_trail = sum(1 for r in rows if r["sim_exit_reason"] == "trailing_giveback")
            n_weak  = sum(1 for r in rows if r["sim_exit_reason"] and r["sim_exit_reason"].startswith("weak_cut"))
            n_ran   = sum(1 for r in rows if r["sim_exit_reason"] == "ran_to_oracle_exit")
            return {
                "subset": label, "n": len(rows),
                "n_armed": n_armed, "armed_pct": n_armed/len(rows),
                "n_profitable": n_prof, "profitable_pct": n_prof/len(rows),
                "n_too_early": n_early, "too_early_pct": n_early/len(rows),
                "n_exit_trailing": n_trail, "n_exit_weak_cut": n_weak, "n_exit_ran": n_ran,
                "median_sim_exit_net_bps": median(net),
                "mean_sim_exit_net_bps": mean(net),
                "median_mfe_net_bps": median(mfe),
                "median_capture_pct_of_mfe": median(cap) if cap else None,
                "mean_capture_pct_of_mfe": mean(cap) if cap else None,
                "median_held_min": median(held) if held else None,
                "total_sim_pnl_usd": sum(r["sim_exit_net_bps"]/1e4*NOTIONAL for r in rows),
                "total_oracle_pnl_usd": sum(r["oracle_net_pnl_usd"] for r in rows),
            }

        sub = {
            "all":    _summarize(sim_results, "all"),
            "bank":   _summarize([r for r in sim_results if r["bank_gate_pass"]], "bank"),
            "shadow": _summarize([r for r in sim_results if not r["bank_gate_pass"]], "shadow"),
            "buy":    _summarize([r for r in sim_results if r["side"]=="buy"], "buy"),
            "sell":   _summarize([r for r in sim_results if r["side"]=="sell"], "sell"),
            "BTC":    _summarize([r for r in sim_results if r["asset"]=="BTC"], "BTC"),
            "ETH":    _summarize([r for r in sim_results if r["asset"]=="ETH"], "ETH"),
            "dur_00-15m":  _summarize([r for r in sim_results if r["duration_bucket"]=="00-15m"], "dur_00-15m"),
            "dur_15-60m":  _summarize([r for r in sim_results if r["duration_bucket"]=="15-60m"], "dur_15-60m"),
            "dur_60-180m": _summarize([r for r in sim_results if r["duration_bucket"]=="60-180m"], "dur_60-180m"),
            "dur_180m+":   _summarize([r for r in sim_results if r["duration_bucket"]=="180m+"], "dur_180m+"),
        }
        for sub_label, s in sub.items():
            if s is None: continue
            sweep_rows.append({"arm_bps": arm, "giveback_floor_bps": floor, "giveback_frac": frac, **s})
    print(f"  sweep rows: {len(sweep_rows):,}")

    # ----- write outputs -----
    # per_trade.csv (primary rule)
    if primary_results:
        headers = list(primary_results[0].keys())
        with open(OUT / "per_trade.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for r in primary_results:
                w.writerow([r.get(h) for h in headers])
        print(f"  wrote per_trade.csv  ({len(primary_results):,} rows)")

    # threshold_sweep.csv
    if sweep_rows:
        headers = list(sweep_rows[0].keys())
        with open(OUT / "threshold_sweep.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for r in sweep_rows:
                w.writerow([r.get(h) for h in headers])
        print(f"  wrote threshold_sweep.csv  ({len(sweep_rows):,} rows)")

    summary = {
        "source_json": str(JSON_PATH),
        "source_audit": str(AUDIT_PATH),
        "n_json_entries": len(entries),
        "n_joined": len(joined),
        "n_primary_simulated": len(primary_results),
        "n_bank_gate_pass": n_bank,
        "n_shadow_gate_only": n_shadow,
        "bank_gate_bps_per_min_threshold": BANK_GATE_BPS_PER_MIN,
        "venue_fees_bps": FEES_BPS,
        "primary_rule": "arm=20bps, giveback=max(12,25%) of peak, weak-cuts at 15m",
        "note": ("Path simulation uses live_data rolling bin buffer. "
                 "Clamped trades have entry_ts a few minutes before bin coverage starts; "
                 "their armed/exit decisions effectively use the visible portion of the trade. "
                 "fee_bps is a static venue assumption (Bybit 10, Kraken 16, Coinbase 50); "
                 "oracle_net_bps in the JSON is already net of fees per the strategy_evolution pipeline. "
                 "current_net_bps in the simulator uses bar.mid; fav_net_bps uses bar.low (sells) "
                 "or bar.high (buys). Real fills would be at bid/ask -> add 1-3 bps slippage to read.")
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"  wrote summary.json")


if __name__ == "__main__":
    main()
