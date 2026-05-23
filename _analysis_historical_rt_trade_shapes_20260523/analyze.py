"""
Historical RT trade-shape simulator (read-only).

Source of labels:
  E:/Markets/research/strategy_evolution/opportunity_ledger_h0_h168_loose_and_dense.json
  (68,584 opportunities; pnl_usd is already NET of fees per gross_pnl_usd - fees_usd)

Source of price path:
  E:/Markets/{btc|eth}_{coinbase|kraken|bybit_perp}_bins.json
  (static archive, May 4-14 2026 depending on venue)

Per trade: slice bin tape from ts_utc to exit_ts_utc, drop empty bars, then compute:
  - path metrics (MFE/MAE, time-to-thresholds, ever-underwater, missed-bps)
  - pre-entry observables (5-bar / 30-bar lookback: vol, agg flow, imb, spread)
  - intra-trade observables (did we reach fee-cover by 15/30/60m?)
  - extreme-bar microstructure

Aggregations:
  - winners vs non-winners (winner := pnl_usd > 0; already net of fees)
  - by side, asset, venue, strategy_id, duration bucket, window (h0-6, h6-12, ...)
  - precision/recall sweep per candidate signal threshold

Outputs (overwritten in this folder):
  summary.json
  per_trade.csv
  signal_thresholds.csv

This script DOES NOT modify any production code, runtime rules, or
oracle_winner_trade_list.json. All findings are historical research only.
"""
from __future__ import annotations
import json, csv, math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path
from statistics import median, mean, pstdev

ROOT = Path("E:/Markets")
OUT  = Path("E:/Markets/_analysis_historical_rt_trade_shapes_20260523")

LEDGER = ROOT / "research/strategy_evolution/opportunity_ledger_h0_h168_loose_and_dense.json"

VENUE_BINS = {
    ("BTC", "Coinbase"): ROOT / "btc_coinbase_bins.json",
    ("BTC", "Kraken"):   ROOT / "btc_kraken_bins.json",
    ("BTC", "Bybit"):    ROOT / "btc_bybit_perp_bins.json",
    ("ETH", "Coinbase"): ROOT / "eth_coinbase_bins.json",
    ("ETH", "Kraken"):   ROOT / "eth_kraken_bins.json",
    ("ETH", "Bybit"):    ROOT / "eth_bybit_perp_bins.json",
}

# ---------- helpers ----------

def _safe(d, k, default=0.0):
    if not d: return default
    v = d.get(k, default)
    return v if v is not None else default

def _bar_ok(b):
    return ((b.get("n_trades") or 0) > 0
            and (b.get("low") or 0) > 0
            and (b.get("high") or 0) > 0)

def _stats(xs, drop_none=True):
    if drop_none:
        xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0}
    xs_s = sorted(xs)
    n = len(xs_s)
    def q(p):
        idx = max(0, min(n - 1, int(p * n)))
        return xs_s[idx]
    return {
        "n": n, "median": median(xs_s), "mean": mean(xs_s),
        "p10": q(0.10), "p25": q(0.25), "p75": q(0.75), "p90": q(0.90),
        "min": xs_s[0], "max": xs_s[-1],
        "stdev": pstdev(xs_s) if n > 1 else 0.0,
    }

def _share(xs):
    xs = [x for x in xs if x is not None]
    if not xs: return None
    return sum(1 for x in xs if x) / len(xs)

def _bucket_duration(m):
    try:
        m = float(m)
    except Exception:
        return "unknown"
    if m < 15:  return "00-15m"
    if m < 60:  return "15-60m"
    if m < 180: return "60-180m"
    return "180m+"


def _load_bins_for(asset, venue, cache):
    key = (asset, venue)
    if key in cache:
        return cache[key]
    path = VENUE_BINS.get(key)
    if path is None or not path.exists():
        cache[key] = (None, None)
        return cache[key]
    d = json.load(open(path))
    items = sorted(((float(ts), bar) for ts, bar in d.items()), key=lambda x: x[0])
    ts_list  = [t for t, _ in items]
    bar_list = [b for _, b in items]
    cache[key] = (ts_list, bar_list)
    print(f"  loaded {key}: {len(ts_list):,} bars  [{ts_list[0]:.0f} .. {ts_list[-1]:.0f}]")
    return cache[key]


def _windowed(ts_list, bar_list, t0, t1):
    """Return (ts_slice, bar_slice) for bars with ts in [t0, t1]."""
    lo = bisect_left(ts_list, t0)
    hi = bisect_right(ts_list, t1)
    return ts_list[lo:hi], bar_list[lo:hi]


def _pre_bars(ts_list, bar_list, t_entry, n_bars):
    """Return up to n_bars NON-empty bars whose ts < t_entry, in chronological order."""
    lo_idx = bisect_left(ts_list, t_entry)
    out = []
    i = lo_idx - 1
    while i >= 0 and len(out) < n_bars:
        b = bar_list[i]
        if _bar_ok(b):
            out.append((ts_list[i], b))
        i -= 1
    out.reverse()
    return out


# ---------- per-trade simulator ----------

def simulate_trade(t, ts_list, bar_list):
    """Return a dict of metrics for this trade, or None if not joinable."""
    if ts_list is None:
        return None
    entry_ts = t.get("ts_utc"); exit_ts = t.get("exit_ts_utc")
    if entry_ts is None or exit_ts is None or exit_ts <= entry_ts:
        return None
    if ts_list[-1] < entry_ts or ts_list[0] > exit_ts:
        return None
    # clamp if needed (note flag)
    clamped = False
    t0 = entry_ts; t1 = exit_ts
    if t0 < ts_list[0]:  t0 = ts_list[0]; clamped = True
    if t1 > ts_list[-1]: t1 = ts_list[-1]; clamped = True
    win_ts, win_bars = _windowed(ts_list, bar_list, t0, t1)
    kept = [(ts, b) for ts, b in zip(win_ts, win_bars) if _bar_ok(b)]
    if not kept:
        return None

    entry_px = float(t["entry"])
    exit_px  = float(t["exit"])
    notional = float(t.get("notional") or 10000.0)
    fees_usd = float(t.get("fees_usd") or 0.0)
    fee_bps  = (fees_usd / notional * 1e4) if notional > 0 else 0.0
    pnl_usd  = float(t.get("pnl_usd") or 0.0)
    is_winner = pnl_usd > 0.0  # already net of fees

    side = t["side"]

    # walking PnL across the window
    # for each bar compute the BAR-BPS = (entry_px - bar_low)/entry_px*1e4 (sell)
    # or (bar_high - entry_px)/entry_px*1e4 (buy)
    fav_bps_series = []  # favorable excursion at each bar
    adv_bps_series = []  # adverse excursion at each bar
    for ts, b in kept:
        hi = b["high"]; lo = b["low"]
        if side == "sell":
            fav = (entry_px - lo) / entry_px * 1e4   # how low it dipped (good for short)
            adv = (entry_px - hi) / entry_px * 1e4   # how high it spiked (bad for short, negative)
        else:
            fav = (hi - entry_px) / entry_px * 1e4
            adv = (lo - entry_px) / entry_px * 1e4
        fav_bps_series.append((ts, fav))
        adv_bps_series.append((ts, adv))

    mfe_ts, mfe_bps = max(fav_bps_series, key=lambda x: x[1])
    mae_ts, mae_bps = min(adv_bps_series, key=lambda x: x[1])  # most negative

    # actual exit bps pre-fee, vs MFE
    if side == "sell":
        actual_bps_pre_fee = (entry_px - exit_px) / entry_px * 1e4
    else:
        actual_bps_pre_fee = (exit_px - entry_px) / entry_px * 1e4
    net_bps = actual_bps_pre_fee - fee_bps
    missed_bps = mfe_bps - actual_bps_pre_fee

    # time-to-first-threshold (using favorable series, looking for first crossing)
    def first_cross_ts(thresh_bps):
        for ts, v in fav_bps_series:
            if v >= thresh_bps:
                return ts
        return None
    t_fee_cover = first_cross_ts(fee_bps)
    t_12bps     = first_cross_ts(12.0)
    t_20bps     = first_cross_ts(20.0)
    t_mfe       = mfe_ts

    def _min_from_entry(ts):
        if ts is None: return None
        return (ts - entry_ts) / 60.0

    # was it ever underwater (negative favorable) at any point?
    ever_under_fav = any(v < 0 for _, v in fav_bps_series)
    # did it reach fee-cover by t-minute checkpoints?
    def did_cover_by(min_after_entry):
        cutoff_ts = entry_ts + min_after_entry * 60
        for ts, v in fav_bps_series:
            if ts > cutoff_ts: break
            if v >= fee_bps:
                return True
        return False
    cover_15m = did_cover_by(15.0)
    cover_30m = did_cover_by(30.0)
    cover_60m = did_cover_by(60.0)

    # pre-entry observables (looking BACK at completed bars)
    pre5  = _pre_bars(ts_list, bar_list, entry_ts, 5)
    pre30 = _pre_bars(ts_list, bar_list, entry_ts, 30)

    def _avg_imb(bars):
        vals = []
        for _, b in bars:
            bq = _safe(b, "bid_qty"); aq = _safe(b, "ask_qty")
            if (bq + aq) > 0: vals.append((bq - aq)/(bq + aq))
        return mean(vals) if vals else None
    def _agg_buy_share(bars):
        if not bars: return None
        return sum(1 for _, b in bars if (b.get("last_aggressor") or "")=="buy") / len(bars)
    def _buyvol_share(bars):
        bv = sum(_safe(b, "buy")  for _, b in bars)
        sv = sum(_safe(b, "sell") for _, b in bars)
        return (bv / (bv + sv)) if (bv + sv) > 0 else None
    def _mean_n_trades(bars):
        if not bars: return None
        return mean(_safe(b, "n_trades") for _, b in bars)

    pre5_buyvol  = _buyvol_share(pre5)
    pre30_buyvol = _buyvol_share(pre30)
    pre5_aggbuy  = _agg_buy_share(pre5)
    pre30_aggbuy = _agg_buy_share(pre30)
    pre5_imb     = _avg_imb(pre5)
    pre30_imb    = _avg_imb(pre30)
    pre5_nt_mean = _mean_n_trades(pre5)
    pre30_nt_mean = _mean_n_trades(pre30)

    # entry-bar microstructure (the bar at-or-just-after entry_ts)
    entry_bar = None
    for ts, b in kept:
        if ts >= entry_ts:
            entry_bar = b; break
    if entry_bar is None:
        entry_bar = kept[0][1]
    e_bq = _safe(entry_bar, "bid_qty"); e_aq = _safe(entry_bar, "ask_qty")
    entry_imb = ((e_bq - e_aq)/(e_bq + e_aq)) if (e_bq + e_aq) > 0 else None
    e_bid = _safe(entry_bar, "bid"); e_ask = _safe(entry_bar, "ask")
    entry_spread_bps = ((e_ask - e_bid)/e_bid * 1e4) if (e_bid > 0 and e_ask > 0) else None

    # entry-bar vs pre5 volume z-equiv: simple ratio
    entry_nt = _safe(entry_bar, "n_trades")
    nt_ratio_entry_vs_pre5  = (entry_nt / pre5_nt_mean) if (pre5_nt_mean and pre5_nt_mean > 0) else None
    nt_ratio_entry_vs_pre30 = (entry_nt / pre30_nt_mean) if (pre30_nt_mean and pre30_nt_mean > 0) else None

    # extreme-bar (MFE bar) microstructure
    mfe_idx_in_kept = max(range(len(kept)), key=lambda i: fav_bps_series[i][1])
    mfe_bar = kept[mfe_idx_in_kept][1]
    # neighbour bars from full ts_list
    full_idx = bisect_left(ts_list, mfe_ts)
    if full_idx >= len(ts_list) or ts_list[full_idx] != mfe_ts:
        full_idx = max(0, min(len(ts_list)-1, full_idx))
    prev_bar = bar_list[full_idx-1] if full_idx > 0 else None
    next_bar = bar_list[full_idx+1] if full_idx+1 < len(ts_list) else None
    agg_at  = mfe_bar.get("last_aggressor") or ""
    agg_pre = (prev_bar.get("last_aggressor") if prev_bar else "") or ""
    agg_nxt = (next_bar.get("last_aggressor") if next_bar else "") or ""
    mfe_bq = _safe(mfe_bar, "bid_qty"); mfe_aq = _safe(mfe_bar, "ask_qty")
    mfe_imb = ((mfe_bq - mfe_aq)/(mfe_bq + mfe_aq)) if (mfe_bq + mfe_aq) > 0 else None
    lb5_start = max(0, full_idx-5)
    lb5_bars = bar_list[lb5_start:full_idx]
    nt_lb5 = mean([_safe(b, "n_trades") for b in lb5_bars]) if lb5_bars else 0.0
    nt_ratio_mfe = (_safe(mfe_bar, "n_trades") / nt_lb5) if nt_lb5 > 0 else None

    return {
        "id": t["id"],
        "is_winner": is_winner,
        "side": side, "asset": t["asset"], "venue": t["venue"],
        "strategy_id": t.get("strategy_id"), "exit_strategy_id": t.get("exit_strategy_id"),
        "bucket_session": t.get("bucket_session"), "window": t.get("window"),
        "close_reason": t.get("close_reason"),
        "forced": t.get("forced"),
        "context": t.get("context"),
        # timing
        "entry_ts": entry_ts, "exit_ts": exit_ts,
        "mfe_ts": mfe_ts, "mae_ts": mae_ts,
        "hold_min": (exit_ts - entry_ts) / 60.0,
        "duration_bucket": _bucket_duration((exit_ts - entry_ts) / 60.0),
        # prices
        "entry_px": entry_px, "exit_px": exit_px,
        "best_favorable_px": (entry_px - mfe_bps/1e4*entry_px) if side=="sell" else (entry_px + mfe_bps/1e4*entry_px),
        "worst_adverse_px": (entry_px - mae_bps/1e4*entry_px) if side=="sell" else (entry_px + mae_bps/1e4*entry_px),
        # bps
        "fee_bps": fee_bps,
        "mfe_bps": mfe_bps, "mae_bps": mae_bps,
        "actual_bps_pre_fee": actual_bps_pre_fee, "net_bps": net_bps,
        "missed_bps": missed_bps,
        "pnl_usd": pnl_usd, "notional": notional,
        "net_bps_per_min": (net_bps / ((exit_ts - entry_ts)/60.0)) if (exit_ts > entry_ts) else None,
        # time-to-threshold (minutes from entry)
        "tte_mfe_min": _min_from_entry(t_mfe),
        "tte_fee_cover_min": _min_from_entry(t_fee_cover),
        "tte_12bps_min": _min_from_entry(t_12bps),
        "tte_20bps_min": _min_from_entry(t_20bps),
        "ever_underwater": ever_under_fav,
        "cover_by_15m": cover_15m, "cover_by_30m": cover_30m, "cover_by_60m": cover_60m,
        # pre-entry observables
        "pre5_buyvol_share":  pre5_buyvol,  "pre30_buyvol_share":  pre30_buyvol,
        "pre5_aggbuy_share":  pre5_aggbuy,  "pre30_aggbuy_share":  pre30_aggbuy,
        "pre5_imb_mean":      pre5_imb,     "pre30_imb_mean":      pre30_imb,
        "pre5_nt_mean":       pre5_nt_mean, "pre30_nt_mean":       pre30_nt_mean,
        "entry_imb":          entry_imb,    "entry_spread_bps":    entry_spread_bps,
        "entry_n_trades":     entry_nt,
        "nt_ratio_entry_vs_pre5":  nt_ratio_entry_vs_pre5,
        "nt_ratio_entry_vs_pre30": nt_ratio_entry_vs_pre30,
        # ledger entry-side features
        "trade_present_score":   t.get("trade_present_score"),
        "trade_option_state":    t.get("trade_option_state"),
        "trade_stage":           t.get("trade_stage"),
        "pressure_watch_state":  t.get("pressure_watch_state"),
        "volume_zscore":         t.get("volume_zscore"),
        "mean_dipole":           t.get("mean_dipole"),
        "dipole_acl1":           t.get("dipole_acl1"),
        # MFE-bar microstructure
        "agg_at_mfe":   agg_at,
        "agg_prev_mfe": agg_pre,
        "agg_next_mfe": agg_nxt,
        "mfe_bidask_imb": mfe_imb,
        "nt_ratio_mfe_vs_lb5": nt_ratio_mfe,
        "clamped_to_bin_coverage": clamped,
    }


# ---------- main ----------

def main():
    print("loading ledger ...")
    raw = json.load(open(LEDGER))
    opps = raw.get("opportunities", [])
    print(f"  ledger rows: {len(opps):,}")

    bins_cache = {}
    print("\nsimulating trades ...")
    per_trade = []
    no_bins = no_join = bad_record = 0
    for i, t in enumerate(opps):
        if i % 5000 == 0 and i > 0:
            print(f"  {i:>6,} / {len(opps):,}  (joined={len(per_trade):,})")
        asset = t.get("asset"); venue = t.get("venue")
        if asset not in ("BTC","ETH") or venue not in ("Coinbase","Kraken","Bybit"):
            bad_record += 1; continue
        ts_list, bar_list = _load_bins_for(asset, venue, bins_cache)
        if ts_list is None:
            no_bins += 1; continue
        r = simulate_trade(t, ts_list, bar_list)
        if r is None:
            no_join += 1; continue
        per_trade.append(r)
    print(f"  joined: {len(per_trade):,}")
    print(f"  no_bins: {no_bins:,}   no_join_window: {no_join:,}   bad_record: {bad_record:,}")

    # winners
    n_win = sum(1 for r in per_trade if r["is_winner"])
    n_loss = len(per_trade) - n_win
    print(f"  winners: {n_win:,}   losers: {n_loss:,}   win_rate: {n_win/len(per_trade)*100:.2f}%")

    # ----- save per-trade CSV -----
    headers = list(per_trade[0].keys())
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "per_trade.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in per_trade:
            w.writerow([r.get(h) for h in headers])
    print(f"  wrote per_trade.csv  ({len(per_trade):,} rows)")

    # ----- group aggregates -----
    def _g_stats(rows):
        if not rows: return {"n": 0}
        wins = [r for r in rows if r["is_winner"]]
        losses = [r for r in rows if not r["is_winner"]]
        # core
        def col(rs, k): return [r.get(k) for r in rs]
        agg = {
            "n": len(rows),
            "n_win": len(wins), "n_loss": len(losses),
            "win_rate": len(wins)/len(rows) if rows else 0.0,
            "winner": {
                "mfe_bps":       _stats(col(wins, "mfe_bps")),
                "mae_bps":       _stats(col(wins, "mae_bps")),
                "net_bps":       _stats(col(wins, "net_bps")),
                "missed_bps":    _stats(col(wins, "missed_bps")),
                "hold_min":      _stats(col(wins, "hold_min")),
                "tte_mfe_min":   _stats(col(wins, "tte_mfe_min")),
                "tte_fee_cover_min": _stats(col(wins, "tte_fee_cover_min")),
                "tte_12bps_min": _stats(col(wins, "tte_12bps_min")),
                "tte_20bps_min": _stats(col(wins, "tte_20bps_min")),
                "net_bps_per_min": _stats(col(wins, "net_bps_per_min")),
                "fee_bps":       _stats(col(wins, "fee_bps")),
                "cover_by_15m_share": _share(col(wins, "cover_by_15m")),
                "cover_by_30m_share": _share(col(wins, "cover_by_30m")),
                "cover_by_60m_share": _share(col(wins, "cover_by_60m")),
                "ever_underwater_share": _share(col(wins, "ever_underwater")),
                # entry observables
                "pre5_buyvol_share": _stats(col(wins, "pre5_buyvol_share")),
                "pre30_buyvol_share": _stats(col(wins, "pre30_buyvol_share")),
                "pre5_aggbuy_share": _stats(col(wins, "pre5_aggbuy_share")),
                "pre30_aggbuy_share": _stats(col(wins, "pre30_aggbuy_share")),
                "pre5_imb_mean":     _stats(col(wins, "pre5_imb_mean")),
                "pre30_imb_mean":    _stats(col(wins, "pre30_imb_mean")),
                "nt_ratio_entry_vs_pre30": _stats(col(wins, "nt_ratio_entry_vs_pre30")),
                "entry_imb":         _stats(col(wins, "entry_imb")),
                "entry_spread_bps":  _stats(col(wins, "entry_spread_bps")),
                "volume_zscore":     _stats(col(wins, "volume_zscore")),
                # MFE bar
                "mfe_bidask_imb":    _stats(col(wins, "mfe_bidask_imb")),
                "nt_ratio_mfe_vs_lb5": _stats(col(wins, "nt_ratio_mfe_vs_lb5")),
            },
            "loser": {
                "mfe_bps":       _stats(col(losses, "mfe_bps")),
                "mae_bps":       _stats(col(losses, "mae_bps")),
                "net_bps":       _stats(col(losses, "net_bps")),
                "hold_min":      _stats(col(losses, "hold_min")),
                "tte_mfe_min":   _stats(col(losses, "tte_mfe_min")),
                "tte_fee_cover_min": _stats(col(losses, "tte_fee_cover_min")),
                "tte_12bps_min": _stats(col(losses, "tte_12bps_min")),
                "fee_bps":       _stats(col(losses, "fee_bps")),
                "cover_by_15m_share": _share(col(losses, "cover_by_15m")),
                "cover_by_30m_share": _share(col(losses, "cover_by_30m")),
                "cover_by_60m_share": _share(col(losses, "cover_by_60m")),
                "ever_underwater_share": _share(col(losses, "ever_underwater")),
                # entry observables
                "pre5_buyvol_share": _stats(col(losses, "pre5_buyvol_share")),
                "pre30_buyvol_share": _stats(col(losses, "pre30_buyvol_share")),
                "pre5_aggbuy_share": _stats(col(losses, "pre5_aggbuy_share")),
                "pre30_aggbuy_share": _stats(col(losses, "pre30_aggbuy_share")),
                "pre5_imb_mean":     _stats(col(losses, "pre5_imb_mean")),
                "pre30_imb_mean":    _stats(col(losses, "pre30_imb_mean")),
                "nt_ratio_entry_vs_pre30": _stats(col(losses, "nt_ratio_entry_vs_pre30")),
                "entry_imb":         _stats(col(losses, "entry_imb")),
                "entry_spread_bps":  _stats(col(losses, "entry_spread_bps")),
                "volume_zscore":     _stats(col(losses, "volume_zscore")),
            },
        }
        return agg

    def _group_by(rows, fn):
        out = defaultdict(list)
        for r in rows:
            out[fn(r)].append(r)
        return out

    summary = {
        "source_ledger": str(LEDGER),
        "n_input": len(opps), "n_joined": len(per_trade),
        "n_winner": n_win, "n_loser": n_loss,
        "win_rate_overall": n_win / len(per_trade) if per_trade else 0.0,
        "note": ("Winner := pnl_usd > 0 from ledger; ledger pnl is already net of fees "
                 "(gross_pnl_usd - fees_usd). Path metrics computed from venue bin tape; "
                 "tape's bar.low/high may not match the strategy_evolution counterfactual "
                 "exit price (different price reference). MFE/MAE here is the "
                 "venue-observable extreme."),
        "by_side":          {k: _g_stats(v) for k, v in _group_by(per_trade, lambda r: r["side"]).items()},
        "by_asset":         {k: _g_stats(v) for k, v in _group_by(per_trade, lambda r: r["asset"]).items()},
        "by_venue":         {k: _g_stats(v) for k, v in _group_by(per_trade, lambda r: r["venue"]).items()},
        "by_strategy_id":   {k: _g_stats(v) for k, v in _group_by(per_trade, lambda r: r["strategy_id"]).items()},
        "by_duration":      {k: _g_stats(v) for k, v in _group_by(per_trade, lambda r: r["duration_bucket"]).items()},
        "by_window":        {k: _g_stats(v) for k, v in _group_by(per_trade, lambda r: r["window"]).items()},
        "by_side_asset":    {f"{a}_{b}": _g_stats(v) for (a,b),v in _group_by(per_trade, lambda r: (r["side"],r["asset"])).items()},
        "by_side_duration": {f"{a}_{b}": _g_stats(v) for (a,b),v in _group_by(per_trade, lambda r: (r["side"],r["duration_bucket"])).items()},
        "by_side_window":   {f"{a}_{b}": _g_stats(v) for (a,b),v in _group_by(per_trade, lambda r: (r["side"],r["window"])).items()},
        "by_side_strategy": {f"{a}_{b}": _g_stats(v) for (a,b),v in _group_by(per_trade, lambda r: (r["side"],r["strategy_id"])).items()},
    }

    # ----- precision/recall sweep -----
    # Each candidate rule: a boolean predicate or threshold on per-trade fields.
    # Definitions:
    #   precision = P(winner | signal_fires)
    #   recall    = P(signal_fires | winner)
    #   lift      = precision / base_win_rate
    # Reported per (population_filter, signal_label, threshold_or_value).

    def _eval_rule(rows, predicate, label, threshold):
        n = len(rows)
        if n == 0: return None
        wins = [r for r in rows if r["is_winner"]]
        fired = [r for r in rows if predicate(r) is True]
        if not fired:
            return {"label": label, "threshold": threshold, "n_population": n,
                    "n_winner_pop": len(wins), "base_win_rate": len(wins)/n,
                    "n_fired": 0, "precision": None, "recall": 0.0, "lift": None,
                    "n_fired_winners": 0,
                    "mean_net_bps_fired": None, "median_net_bps_fired": None,
                    "median_net_bps_pop": median([r["net_bps"] for r in rows])}
        wins_fired = [r for r in fired if r["is_winner"]]
        prec = len(wins_fired) / len(fired)
        rec  = len(wins_fired) / len(wins) if wins else 0.0
        base = len(wins) / n
        lift = (prec / base) if base > 0 else None
        net_fired = [r["net_bps"] for r in fired]
        net_pop   = [r["net_bps"] for r in rows]
        return {
            "label": label, "threshold": threshold,
            "n_population": n, "n_winner_pop": len(wins),
            "base_win_rate": base,
            "n_fired": len(fired), "n_fired_winners": len(wins_fired),
            "precision": prec, "recall": rec, "lift": lift,
            "mean_net_bps_fired": mean(net_fired), "median_net_bps_fired": median(net_fired),
            "median_net_bps_pop": median(net_pop),
        }

    # candidate signals
    # each is (label, fn(row, threshold)->bool, list of thresholds)
    candidates = [
        ("cover_by_15m_TRUE",      lambda r,th: r["cover_by_15m"] is True, [True]),
        ("cover_by_30m_TRUE",      lambda r,th: r["cover_by_30m"] is True, [True]),
        ("cover_by_60m_TRUE",      lambda r,th: r["cover_by_60m"] is True, [True]),
        ("ever_underwater_FALSE",  lambda r,th: r["ever_underwater"] is False, [True]),
        ("reached_12bps_within_15m",lambda r,th: r["tte_12bps_min"] is not None and r["tte_12bps_min"] <= 15, [True]),
        ("reached_12bps_within_30m",lambda r,th: r["tte_12bps_min"] is not None and r["tte_12bps_min"] <= 30, [True]),
        ("reached_20bps_within_30m",lambda r,th: r["tte_20bps_min"] is not None and r["tte_20bps_min"] <= 30, [True]),
        ("reached_20bps_within_60m",lambda r,th: r["tte_20bps_min"] is not None and r["tte_20bps_min"] <= 60, [True]),
        ("volume_zscore_le",       lambda r,th: r.get("volume_zscore") is not None and r["volume_zscore"] <= th, [-0.5, -0.25, 0.0, 0.25, 0.5]),
        ("nt_ratio_entry_vs_pre30_ge", lambda r,th: r.get("nt_ratio_entry_vs_pre30") is not None and r["nt_ratio_entry_vs_pre30"] >= th, [1.0, 1.5, 2.0, 3.0]),
        ("entry_imb_long_bid_ge",  lambda r,th: r["side"]=="buy" and r.get("entry_imb") is not None and r["entry_imb"] >= th, [-0.2, 0.0, 0.2, 0.5]),
        ("entry_imb_short_ask_le", lambda r,th: r["side"]=="sell" and r.get("entry_imb") is not None and r["entry_imb"] <= th, [0.2, 0.0, -0.2, -0.5]),
        ("pre5_buyvol_long_ge",    lambda r,th: r["side"]=="buy" and r.get("pre5_buyvol_share") is not None and r["pre5_buyvol_share"] >= th, [0.5, 0.7, 0.9]),
        ("pre5_buyvol_short_le",   lambda r,th: r["side"]=="sell" and r.get("pre5_buyvol_share") is not None and r["pre5_buyvol_share"] <= th, [0.5, 0.3, 0.1]),
        ("trade_present_score_ge", lambda r,th: r.get("trade_present_score") is not None and r["trade_present_score"] >= th, [25, 40, 55, 70]),
        ("dipole_long_pos_ge",     lambda r,th: r["side"]=="buy" and r.get("mean_dipole") is not None and r["mean_dipole"] >= th, [0.0, 0.1, 0.2]),
        ("dipole_short_neg_le",    lambda r,th: r["side"]=="sell" and r.get("mean_dipole") is not None and r["mean_dipole"] <= th, [0.0, -0.1, -0.2]),
        ("hold_min_le_avoid_chop", lambda r,th: r["hold_min"] is not None and r["hold_min"] <= th, [15, 30, 60]),
        ("hold_min_ge_runners",    lambda r,th: r["hold_min"] is not None and r["hold_min"] >= th, [60, 120]),
        ("fast_winner_pattern",    lambda r,th: (r["cover_by_15m"] is True) and (r.get("ever_underwater") is False), [True]),
        ("clean_no_underwater_30m_cover", lambda r,th: (r["cover_by_30m"] is True) and (r.get("ever_underwater") is False), [True]),
        ("net_bps_per_min_floor",  lambda r,th: r.get("net_bps_per_min") is not None and r["net_bps_per_min"] >= th, [0.05, 0.10, 0.20, 0.50]),
    ]

    # populations to evaluate over
    populations = [
        ("ALL", per_trade),
        ("side=buy", [r for r in per_trade if r["side"]=="buy"]),
        ("side=sell", [r for r in per_trade if r["side"]=="sell"]),
        ("BTC", [r for r in per_trade if r["asset"]=="BTC"]),
        ("ETH", [r for r in per_trade if r["asset"]=="ETH"]),
        ("dur_00-15m", [r for r in per_trade if r["duration_bucket"]=="00-15m"]),
        ("dur_15-60m", [r for r in per_trade if r["duration_bucket"]=="15-60m"]),
        ("dur_60-180m",[r for r in per_trade if r["duration_bucket"]=="60-180m"]),
        ("dur_180m+",  [r for r in per_trade if r["duration_bucket"]=="180m+"]),
    ]

    threshold_rows = []
    for pop_label, pop in populations:
        for label, predicate, ths in candidates:
            for th in ths:
                rec = _eval_rule(pop, lambda r, _th=th, _p=predicate: _p(r,_th), label, th)
                if rec is None: continue
                rec["population"] = pop_label
                threshold_rows.append(rec)

    # per-window time-of-day analysis
    for window in sorted({r["window"] for r in per_trade if r.get("window")}):
        pop = [r for r in per_trade if r.get("window")==window]
        for label, predicate, ths in candidates:
            for th in ths:
                rec = _eval_rule(pop, lambda r, _th=th, _p=predicate: _p(r,_th), label, th)
                if rec is None: continue
                rec["population"] = f"window={window}"
                threshold_rows.append(rec)

    # write thresholds CSV
    t_headers = ["population","label","threshold",
                 "n_population","n_winner_pop","base_win_rate",
                 "n_fired","n_fired_winners","precision","recall","lift",
                 "mean_net_bps_fired","median_net_bps_fired","median_net_bps_pop"]
    with open(OUT / "signal_thresholds.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(t_headers)
        for r in threshold_rows:
            w.writerow([r.get(h) for h in t_headers])
    print(f"  wrote signal_thresholds.csv  ({len(threshold_rows):,} rows)")

    summary["n_threshold_rows"] = len(threshold_rows)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"  wrote summary.json")


if __name__ == "__main__":
    main()
