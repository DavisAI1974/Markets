"""
One-off hindsight analysis (read-only).

Source of truth:
  E:/Markets/research/strategy_evolution/live_mock_replay/live_hindsight_missed_winner_audit_rows.csv

Filter: is_oracle_winner_after_fees == 'True'

For each winner:
  - side == 'sell'  -> short.  Best cover  = LOWEST  bar.low  in [oracle_entry_ts_utc, oracle_exit_ts_utc]
  - side == 'buy'   -> long.   Best sell   = HIGHEST bar.high in [oracle_entry_ts_utc, oracle_exit_ts_utc]
Empty bars (n_trades==0 / zero low/high) are dropped from the window before locating the extreme.

Microstructure signals computed at the extreme bar (and prev/next bar):
  last_aggressor, bid/ask imbalance, spread bps, n_trades vs 5-bar mean,
  buy/sell vol share at extreme and over 5-bar lookback.

Grouping: by side, asset, venue, strategy_id, pattern_family, miss_type.

Outputs (overwritten in this folder):
  summary.json   - all grouped statistics
  per_trade.csv  - one row per winner with extreme, captured/actual/missed bps, snapshot fields
"""
from __future__ import annotations
import csv, json, math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev

ROOT = Path("E:/Markets")
OUT  = Path("E:/Markets/_analysis_winner_extrema_20260523")
AUDIT = ROOT / "research/strategy_evolution/live_mock_replay/live_hindsight_missed_winner_audit_rows.csv"

VENUE_BINS = {
    ("BTC", "Coinbase"): ROOT / "live_data/btc_coinbase_bins.json",
    ("BTC", "Kraken"):   ROOT / "live_data/btc_kraken_bins.json",
    ("BTC", "Bybit"):    ROOT / "live_data/btc_bybit_perp_bins.json",
    ("ETH", "Coinbase"): ROOT / "live_data/eth_coinbase_bins.json",
    ("ETH", "Kraken"):   ROOT / "live_data/eth_kraken_bins.json",
    ("ETH", "Bybit"):    ROOT / "live_data/eth_bybit_perp_bins.json",
}


def _load_bins():
    """Returns {(asset,venue): (sorted_ts_list, sorted_bars_list)}."""
    out = {}
    for k, p in VENUE_BINS.items():
        if not p.exists():
            print(f"  [warn] missing {p}")
            continue
        try:
            d = json.load(open(p))
        except Exception as e:
            print(f"  [warn] failed to load {p}: {e}")
            continue
        items = sorted(((float(ts), bar) for ts, bar in d.items()), key=lambda x: x[0])
        ts_list  = [t for t, _ in items]
        bar_list = [b for _, b in items]
        out[k] = (ts_list, bar_list)
        if ts_list:
            print(f"  bins {k}: {len(ts_list):>6} bars  [{ts_list[0]:.0f} .. {ts_list[-1]:.0f}]")
    return out


def _slice_window(ts_list, bar_list, t0, t1):
    lo = bisect_left(ts_list, t0)
    hi = bisect_right(ts_list, t1)
    return ts_list[lo:hi], bar_list[lo:hi]


def _stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0}
    xs_s = sorted(xs)
    n = len(xs_s)
    def q(p):
        idx = max(0, min(n - 1, int(p * n)))
        return xs_s[idx]
    return {
        "n": n,
        "median": median(xs_s),
        "mean":   mean(xs_s),
        "p10": q(0.10), "p25": q(0.25),
        "p75": q(0.75), "p90": q(0.90),
        "min": xs_s[0], "max": xs_s[-1],
        "stdev": pstdev(xs_s) if n > 1 else 0.0,
    }


def _sign_ratio(xs):
    if not xs:
        return None
    n = len(xs)
    pos = sum(1 for x in xs if x > 0)
    neg = sum(1 for x in xs if x < 0)
    zer = n - pos - neg
    return {"n": n, "pos_frac": pos/n, "neg_frac": neg/n, "zero_frac": zer/n,
            "median_delta": median(xs), "mean_delta": mean(xs)}


def _to_float(s, default=None):
    if s is None or s == "":
        return default
    try:
        return float(s)
    except Exception:
        return default


def _safe(d, k, default=0.0):
    if not d:
        return default
    v = d.get(k, default)
    return v if v is not None else default


def main():
    print("loading price bins ...")
    bins = _load_bins()

    print(f"\nloading audit rows from {AUDIT} ...")
    winners = []
    total = 0
    skipped_not_winner = 0
    with open(AUDIT) as f:
        for r in csv.DictReader(f):
            total += 1
            if r.get("is_oracle_winner_after_fees") != "True":
                skipped_not_winner += 1
                continue
            r["_entry_ts"] = _to_float(r.get("oracle_entry_ts_utc"))
            r["_exit_ts"]  = _to_float(r.get("oracle_exit_ts_utc"))
            r["_entry_px"] = _to_float(r.get("oracle_entry_price"))
            r["_exit_px"]  = _to_float(r.get("oracle_exit_price"))
            r["_net_pnl_usd"] = _to_float(r.get("oracle_net_pnl_usd"), 0.0)
            r["_net_bps"]     = _to_float(r.get("oracle_net_bps"), 0.0)
            r["_horizon_min"] = _to_float(r.get("oracle_horizon_minutes"), 0.0)
            r["_mean_dipole"] = _to_float(r.get("mean_dipole"))
            r["_dipole_acl1"] = _to_float(r.get("dipole_acl1"))
            r["_volz"]        = _to_float(r.get("volume_zscore"))
            r["_present"]     = _to_float(r.get("trade_present_score"))
            r["_readiness"]   = _to_float(r.get("trade_option_readiness"))
            r["_curchunk_bps"]= _to_float(r.get("trade_current_chunk_bps"))
            r["_recent2_bps"] = _to_float(r.get("trade_recent_2chunk_bps"))
            r["_onset_bps"]   = _to_float(r.get("trade_from_onset_bps"))
            if (r["_entry_ts"] is None or r["_exit_ts"] is None
                or r["_exit_ts"] <= r["_entry_ts"]
                or r["_entry_px"] is None):
                continue
            if r["side"] not in ("buy", "sell"):
                continue
            if r["asset"] not in ("BTC", "ETH"):
                continue
            winners.append(r)
    print(f"  total audit rows: {total}")
    print(f"  non-winners skipped: {skipped_not_winner}")
    print(f"  winners w/ valid window: {len(winners)}")

    # ----- per-trade extreme + microstructure -----
    per_trade = []
    no_bins = 0
    empty_window = 0
    bins_clamped = 0

    for w in winners:
        key = (w["asset"], w["venue"])
        if key not in bins:
            no_bins += 1; continue
        ts_list, bar_list = bins[key]
        t0, t1 = w["_entry_ts"], w["_exit_ts"]
        # clamp to bin coverage so partial overlap still produces data
        bin_lo = ts_list[0] if ts_list else None
        bin_hi = ts_list[-1] if ts_list else None
        clamped = False
        if bin_lo is None or t0 > bin_hi or t1 < bin_lo:
            no_bins += 1; continue
        if t1 > bin_hi:
            t1 = bin_hi; clamped = True
        if t0 < bin_lo:
            t0 = bin_lo; clamped = True
        if clamped:
            bins_clamped += 1
        win_ts, win_bars = _slice_window(ts_list, bar_list, t0, t1)
        # drop empty bars
        kept = [(t, b) for t, b in zip(win_ts, win_bars)
                if (b.get("n_trades") or 0) > 0
                and (b.get("low") or 0) > 0
                and (b.get("high") or 0) > 0]
        if not kept:
            empty_window += 1; continue

        entry_px = w["_entry_px"]
        exit_px  = w["_exit_px"] if w["_exit_px"] is not None else entry_px

        if w["side"] == "sell":  # short -> cover at LOWEST
            ext_idx_in_kept = min(range(len(kept)), key=lambda i: kept[i][1]["low"])
            ext_ts = kept[ext_idx_in_kept][0]
            ext_bar = kept[ext_idx_in_kept][1]
            ext_price = ext_bar["low"]
            captured_bps = (entry_px - ext_price) / entry_px * 1e4
            actual_bps   = (entry_px - exit_px)  / entry_px * 1e4 if exit_px else 0.0
        else:  # buy / long -> sell at HIGHEST
            ext_idx_in_kept = max(range(len(kept)), key=lambda i: kept[i][1]["high"])
            ext_ts = kept[ext_idx_in_kept][0]
            ext_bar = kept[ext_idx_in_kept][1]
            ext_price = ext_bar["high"]
            captured_bps = (ext_price - entry_px) / entry_px * 1e4
            actual_bps   = (exit_px - entry_px)  / entry_px * 1e4 if exit_px else 0.0

        missed_bps = captured_bps - actual_bps
        trade_dur_min = (w["_exit_ts"] - w["_entry_ts"]) / 60.0
        tte_min       = (ext_ts - w["_entry_ts"]) / 60.0
        ext_pos_pct   = (tte_min / trade_dur_min) if trade_dur_min > 0 else 0.0

        # microstructure at extreme bar and neighbours from full bar list (so we can see across the kept-skip gap)
        full_idx = bisect_left(ts_list, ext_ts)
        if full_idx >= len(ts_list) or ts_list[full_idx] != ext_ts:
            # fallback: nearest
            full_idx = max(0, min(len(ts_list) - 1, full_idx))
        prev_bar = bar_list[full_idx - 1] if full_idx > 0 else None
        next_bar = bar_list[full_idx + 1] if (full_idx + 1) < len(ts_list) else None
        lb_start = max(0, full_idx - 5)
        lb_bars  = bar_list[lb_start:full_idx]

        agg_at   = ext_bar.get("last_aggressor") or ""
        agg_prev = (prev_bar.get("last_aggressor") if prev_bar else "") or ""
        agg_next = (next_bar.get("last_aggressor") if next_bar else "") or ""

        bq = _safe(ext_bar, "bid_qty"); aq = _safe(ext_bar, "ask_qty")
        imb = ((bq - aq) / (bq + aq)) if (bq + aq) > 0 else None
        bid = _safe(ext_bar, "bid");   ask = _safe(ext_bar, "ask")
        spread_bps = ((ask - bid) / bid * 1e4) if (bid > 0 and ask > 0) else None

        nt_at = _safe(ext_bar, "n_trades")
        nt_lb_mean = mean([_safe(b, "n_trades") for b in lb_bars]) if lb_bars else 0.0
        nt_ratio = (nt_at / nt_lb_mean) if nt_lb_mean > 0 else None

        bv_at = _safe(ext_bar, "buy"); sv_at = _safe(ext_bar, "sell")
        bvshare_at = (bv_at / (bv_at + sv_at)) if (bv_at + sv_at) > 0 else None
        bv_lb = sum(_safe(b, "buy")  for b in lb_bars)
        sv_lb = sum(_safe(b, "sell") for b in lb_bars)
        bvshare_lb = (bv_lb / (bv_lb + sv_lb)) if (bv_lb + sv_lb) > 0 else None

        per_trade.append({
            "unique_key": w["unique_key"],
            "asset": w["asset"], "venue": w["venue"], "side": w["side"],
            "strategy_id": w["strategy_id"], "pattern_family": w["pattern_family"],
            "miss_type": w["miss_type"], "bucket_session": w["bucket_session"],
            "decision": w["decision"], "blocker_reason": w["blocker_reason"],
            "move_shape_category": w["move_shape_category"],
            # window
            "entry_ts": w["_entry_ts"], "exit_ts": w["_exit_ts"], "extreme_ts": ext_ts,
            "entry_px": entry_px, "exit_px": exit_px, "extreme_px": ext_price,
            "horizon_min": w["_horizon_min"],
            "trade_dur_min": trade_dur_min, "tte_min": tte_min, "ext_pos_pct": ext_pos_pct,
            # pnl
            "oracle_net_pnl_usd": w["_net_pnl_usd"], "oracle_net_bps": w["_net_bps"],
            "captured_bps": captured_bps, "actual_bps": actual_bps, "missed_bps": missed_bps,
            # entry-side features (already in audit CSV)
            "trade_present_score": w["_present"],
            "trade_option_readiness": w["_readiness"],
            "trade_current_chunk_bps": w["_curchunk_bps"],
            "trade_recent_2chunk_bps": w["_recent2_bps"],
            "trade_from_onset_bps": w["_onset_bps"],
            "mean_dipole_at_entry": w["_mean_dipole"],
            "dipole_acl1_at_entry": w["_dipole_acl1"],
            "volume_zscore_at_entry": w["_volz"],
            "trade_stage": w["trade_stage"],
            "trade_option_state": w["trade_option_state"],
            "pressure_watch_state": w["pressure_watch_state"],
            # microstructure at extreme
            "aggressor_at_extreme":   agg_at,
            "aggressor_prev_extreme": agg_prev,
            "aggressor_next_extreme": agg_next,
            "bidask_imb_extreme":     imb,
            "spread_bps_extreme":     spread_bps,
            "n_trades_ratio_lb5":     nt_ratio,
            "buyvol_share_extreme":   bvshare_at,
            "buyvol_share_lb5":       bvshare_lb,
            "bins_clamped":           clamped,
        })

    print(f"\n  joined to price bars: {len(per_trade)}")
    print(f"  no bins for (asset,venue):  {no_bins}")
    print(f"  empty window (all bars zero): {empty_window}")
    print(f"  trades whose window was clamped to bin coverage: {bins_clamped}")

    # Cross-check: how often does the venue-tape bar.low beat or match the oracle's chosen exit?
    # If oracle uses a richer price reference (tick-level / cross-venue / bid-side),
    # bar.low may not reach oracle_exit_price -> captured_bps < actual_bps frequently.
    n_unclamped = sum(1 for r in per_trade if not r["bins_clamped"])
    n_unc_cap_ge_act = sum(1 for r in per_trade
                           if not r["bins_clamped"] and r["captured_bps"] >= r["actual_bps"])
    if n_unclamped:
        print(f"  unclamped trades: {n_unclamped}")
        print(f"  ... of which venue bar.low captured >= oracle actual_bps: "
              f"{n_unc_cap_ge_act} ({n_unc_cap_ge_act/n_unclamped*100:.1f}%)")
    # for the primary stats we use UNCLAMPED ONLY so the window is honest.
    per_trade_primary = [r for r in per_trade if not r["bins_clamped"]]
    print(f"  primary aggregates computed on UNCLAMPED-only subset: n={len(per_trade_primary)}")

    # ----- aggregates -----
    def _group_stats(rows):
        if not rows: return {"n": 0}
        g = {"n": len(rows),
             "tte_min":           _stats([r["tte_min"] for r in rows]),
             "trade_dur_min":     _stats([r["trade_dur_min"] for r in rows]),
             "ext_pos_pct":       _stats([r["ext_pos_pct"] for r in rows]),
             "captured_bps":      _stats([r["captured_bps"] for r in rows]),
             "actual_bps":        _stats([r["actual_bps"] for r in rows]),
             "missed_bps":        _stats([r["missed_bps"] for r in rows]),
             "oracle_net_pnl_usd":_stats([r["oracle_net_pnl_usd"] for r in rows]),
             "oracle_net_bps":    _stats([r["oracle_net_bps"] for r in rows]),
             "horizon_min":       _stats([r["horizon_min"] for r in rows]),
             # microstructure aggregates
             "aggressor_at_is_buy":   _stats([1 if r["aggressor_at_extreme"]=="buy" else 0 for r in rows]),
             "aggressor_at_is_sell":  _stats([1 if r["aggressor_at_extreme"]=="sell" else 0 for r in rows]),
             "aggressor_next_is_buy": _stats([1 if r["aggressor_next_extreme"]=="buy" else 0 for r in rows]),
             "aggressor_next_is_sell":_stats([1 if r["aggressor_next_extreme"]=="sell" else 0 for r in rows]),
             "aggressor_prev_is_buy": _stats([1 if r["aggressor_prev_extreme"]=="buy" else 0 for r in rows]),
             "aggressor_flip_sell_to_buy_next":  # short-cover flip
                _stats([1 if (r["aggressor_at_extreme"]=="sell" and r["aggressor_next_extreme"]=="buy") else 0 for r in rows]),
             "aggressor_flip_buy_to_sell_next":  # long-sell flip
                _stats([1 if (r["aggressor_at_extreme"]=="buy" and r["aggressor_next_extreme"]=="sell") else 0 for r in rows]),
             "bidask_imb_extreme":   _stats([r["bidask_imb_extreme"] for r in rows]),
             "spread_bps_extreme":   _stats([r["spread_bps_extreme"] for r in rows]),
             "n_trades_ratio_lb5":   _stats([r["n_trades_ratio_lb5"] for r in rows]),
             "buyvol_share_extreme": _stats([r["buyvol_share_extreme"] for r in rows]),
             "buyvol_share_lb5":     _stats([r["buyvol_share_lb5"] for r in rows]),
             # entry features
             "mean_dipole_at_entry":   _stats([r["mean_dipole_at_entry"] for r in rows]),
             "dipole_acl1_at_entry":   _stats([r["dipole_acl1_at_entry"] for r in rows]),
             "volume_zscore_at_entry": _stats([r["volume_zscore_at_entry"] for r in rows]),
             "trade_present_score":    _stats([r["trade_present_score"] for r in rows]),
             "trade_option_readiness": _stats([r["trade_option_readiness"] for r in rows]),
        }
        buckets = defaultdict(int)
        for r in rows:
            p = r["ext_pos_pct"]
            if p < 0.10: buckets["0-10%"] += 1
            elif p < 0.25: buckets["10-25%"] += 1
            elif p < 0.50: buckets["25-50%"] += 1
            elif p < 0.75: buckets["50-75%"] += 1
            elif p < 0.95: buckets["75-95%"] += 1
            else:          buckets["95-100%"] += 1
        g["ext_pos_buckets"] = dict(buckets)
        # totals
        g["sum_oracle_net_pnl_usd"] = sum(r["oracle_net_pnl_usd"] for r in rows)
        return g

    def _group_by(rows, fn):
        out = defaultdict(list)
        for r in rows:
            out[fn(r)].append(r)
        return out

    # Use unclamped-only subset for primary aggregates.
    rows = per_trade_primary
    summary = {
        "source_csv": str(AUDIT),
        "n_total_winners_input": len(winners),
        "n_joined_to_bars": len(per_trade),
        "n_no_bins": no_bins,
        "n_empty_window": empty_window,
        "n_bins_clamped": bins_clamped,
        "n_primary_subset_unclamped": len(per_trade_primary),
        "n_unclamped_bar_low_beats_or_matches_oracle": n_unc_cap_ge_act,
        "note": ("Primary aggregates use UNCLAMPED trades only. Oracle reference price "
                 "appears tighter than venue tape bar.low/high (likely tick-level or "
                 "cross-venue / bid-ask side); captured_bps from bar.low may underestimate "
                 "oracle_net_bps even on unclamped windows. The extreme-bar microstructure "
                 "stats describe the visible-on-venue-tape extreme bar, which is what "
                 "you'd actually observe live."),
        "by_side":         {k: _group_stats(v) for k, v in _group_by(rows, lambda r: r["side"]).items()},
        "by_asset":        {k: _group_stats(v) for k, v in _group_by(rows, lambda r: r["asset"]).items()},
        "by_venue":        {k: _group_stats(v) for k, v in _group_by(rows, lambda r: r["venue"]).items()},
        "by_strategy_id":  {k: _group_stats(v) for k, v in _group_by(rows, lambda r: r["strategy_id"]).items()},
        "by_pattern_family":{k: _group_stats(v) for k, v in _group_by(rows, lambda r: r["pattern_family"]).items()},
        "by_miss_type":    {k: _group_stats(v) for k, v in _group_by(rows, lambda r: r["miss_type"]).items()},
        "by_side_asset":   {f"{a}_{b}": _group_stats(v) for (a,b), v in _group_by(rows, lambda r: (r["side"], r["asset"])).items()},
        "by_side_asset_venue":   {f"{a}_{b}_{c}": _group_stats(v) for (a,b,c), v in _group_by(rows, lambda r: (r["side"], r["asset"], r["venue"])).items()},
        "by_side_strategy":      {f"{a}_{b}": _group_stats(v) for (a,b), v in _group_by(rows, lambda r: (r["side"], r["strategy_id"])).items()},
        "by_side_pattern_family":{f"{a}_{b}": _group_stats(v) for (a,b), v in _group_by(rows, lambda r: (r["side"], r["pattern_family"])).items()},
        "by_side_miss_type":     {f"{a}_{b}": _group_stats(v) for (a,b), v in _group_by(rows, lambda r: (r["side"], r["miss_type"])).items()},
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    # per-trade CSV
    csv_headers = ["unique_key","asset","venue","side","strategy_id","pattern_family","miss_type",
                   "bucket_session","decision","blocker_reason","move_shape_category",
                   "entry_ts","extreme_ts","exit_ts","entry_px","extreme_px","exit_px",
                   "horizon_min","trade_dur_min","tte_min","ext_pos_pct",
                   "oracle_net_pnl_usd","oracle_net_bps",
                   "captured_bps","actual_bps","missed_bps",
                   "trade_stage","trade_option_state","pressure_watch_state",
                   "trade_present_score","trade_option_readiness",
                   "trade_current_chunk_bps","trade_recent_2chunk_bps","trade_from_onset_bps",
                   "mean_dipole_at_entry","dipole_acl1_at_entry","volume_zscore_at_entry",
                   "aggressor_prev_extreme","aggressor_at_extreme","aggressor_next_extreme",
                   "bidask_imb_extreme","spread_bps_extreme","n_trades_ratio_lb5",
                   "buyvol_share_extreme","buyvol_share_lb5","bins_clamped"]
    with open(OUT / "per_trade.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(csv_headers)
        for r in per_trade:
            w.writerow([r.get(h) for h in csv_headers])

    print(f"\nwrote {OUT/'summary.json'} and {OUT/'per_trade.csv'}")


if __name__ == "__main__":
    main()
