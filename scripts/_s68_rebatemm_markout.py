"""
_s68_rebatemm_markout.py  --  HONEST rebate-farming markout engine (S68 thesis test).

Question (Greg): on Kraken rebate-eligible alt pairs (maker fee = -2bp = a REBATE),
can we "get paid to churn" -- rest passive maker quotes purely to collect the rebate,
NOT to time turns? The swing sim's circular-shift FLOOR says yes, but that floor is a
KNOWN INFLATION because it under-charges ADVERSE SELECTION (S56: never cite the floor
as edge). This engine charges adverse selection HONESTLY via MARKOUT.

--------------------------------------------------------------------------------------
CRITICAL MEASUREMENT NOTE (why a naive markout is ALSO inflated):
  The tape "mid" is the LAST TRADE PRICE (load_bins: "mid = last trade"), NOT a true mid.
  On a SELL cell it sits near the BID; on a BUY cell near the ASK. If you fill a resting
  bid at that (depressed) sell-cell price and mark forward to a mix of later trade prices,
  you recover the BID-ASK BOUNCE as fake favorable markout -- the classic MM-backtest lie.
  Pairs with a wide spread show a large spurious POSITIVE markout for exactly this reason.

  FIX: build a BOUNCE-FREE SYNTHETIC MID = geo-mean(last buy-cell px, last sell-cell px),
  which brackets the true mid. Then:
    spread_capture_bps = distance from our (touch) fill price to the synthetic mid   [REAL, earned]
    markout_bps(dt)    = FAVORABLE-signed move of the SYNTHETIC MID over dt           [true adverse sel]
  These do NOT double count. net = rebate + spread_capture + markout.
--------------------------------------------------------------------------------------

Per passive fill (resting BID filled by a sell-taker => we BUY; resting ASK filled by a
buy-taker => we SELL):

    net_bps(fill, dt) = spread_capture_bps + rebate_bps + markout_bps(dt)
    rebate_bps  = +2.0                      (Kraken maker rebate, per passive fill)
    markout_bps = BUY:  (synth[t+dt]-synth[t])/synth[t]*1e4
                  SELL: (synth[t]-synth[t+dt])/synth[t]*1e4    (NEGATIVE == adverse/pick-off)

Fill model (tape, no book depth): FRONT-OF-LINE proxy -- every taker print fills our
opposing resting quote up to min(clip, print_notional). Best-case queue (most favorable
to the thesis); adverse-selection SIGN is queue-independent so the verdict is robust.
Book-depth majors validate this proxy separately (_s68_rebatemm_book.py).

Circular-shift null: rotate the synthetic-mid series vs the fill times -> destroys the
fill-timing<->adverse coupling, leaving rebate + structureless (~0) markout. The gap
(shuffle_markout - real_markout) == the adverse-selection cost the swing FLOOR omits.

Pure numpy. Causal. Tape-only.
"""
from __future__ import annotations
import json, sys, os
import numpy as np

REBATE_BPS = 2.0
CLIP_USD   = 5000.0
HORIZONS   = [1, 5, 30, 60]


def load_tape(path):
    d = json.load(open(path))
    keys = sorted(d.keys(), key=float)
    t   = np.array([float(k) for k in keys])
    mid = np.array([d[k]["mid"]  for k in keys], float)
    buy = np.array([d[k].get("buy", 0.0)  for k in keys], float)
    sell= np.array([d[k].get("sell", 0.0) for k in keys], float)
    good = np.isfinite(mid) & (mid > 0)
    return t[good], mid[good], buy[good], sell[good]


def build_synth_mid(t, mid, buy, sell):
    """Bounce-free synthetic mid = geo-mean of the most-recent buy-cell (~ask) and
    sell-cell (~bid) trade prices, carried forward. Undefined until both sides seen."""
    n = len(t)
    last_ask = np.full(n, np.nan)   # last buy-cell price (taker lifted the ask)
    last_bid = np.full(n, np.nan)   # last sell-cell price (taker hit the bid)
    a = np.nan; b = np.nan
    for i in range(n):
        if buy[i] > 0 and sell[i] > 0:
            # two-sided cell: high~ask low~bid unavailable here; use mid for both
            a = mid[i]; b = mid[i]
        elif buy[i] > 0:
            a = mid[i]
        elif sell[i] > 0:
            b = mid[i]
        last_ask[i] = a; last_bid[i] = b
    synth = np.sqrt(last_ask * last_bid)
    # forward/back fill any leading nans with raw mid so lookups never break
    synth = np.where(np.isfinite(synth), synth, mid)
    return synth


def val_at(t, series, query_t):
    idx = np.searchsorted(t, query_t, side="right") - 1
    idx = np.clip(idx, 0, len(series) - 1)
    return series[idx]


def simulate(path, pair):
    t, mid, buy, sell = load_tape(path)
    n = len(t)
    span_hr = (t[-1] - t[0]) / 3600.0
    synth = build_synth_mid(t, mid, buy, sell)

    # BID fills (we BUY) on sell-taker cells; ASK fills (we SELL) on buy-taker cells
    bidmask = sell > 0
    askmask = buy > 0
    ti_b, pi_b, sy_b = t[bidmask], mid[bidmask], synth[bidmask]
    ti_a, pi_a, sy_a = t[askmask], mid[askmask], synth[askmask]
    fillnot_b = np.minimum(sell[bidmask] * mid[bidmask], CLIP_USD)
    fillnot_a = np.minimum(buy[askmask]  * mid[askmask], CLIP_USD)

    # spread capture: distance from our touch fill price to synthetic mid (bps), clipped >=0
    # BUY at bid ~ pi_b <= synth => capture = (synth - pi_b)/synth ; SELL at ask => (pi_a - synth)/synth
    sc_b = np.clip((sy_b - pi_b) / sy_b * 1e4, 0, None)
    sc_a = np.clip((pi_a - sy_a) / sy_a * 1e4, 0, None)
    spread_cap = np.concatenate([sc_b, sc_a])
    wnot       = np.concatenate([fillnot_b, fillnot_a])
    wsum       = wnot.sum()

    out = {"pair": pair, "n_cells": n, "span_hr": round(span_hr, 1),
           "n_bid_fills": int(bidmask.sum()), "n_ask_fills": int(askmask.sum()),
           "gross_notional_usd": round(float(wsum), 1),
           "mean_spread_capture_bps": round(float(np.average(spread_cap, weights=wnot)), 3),
           "horizons": {}}

    for dt in HORIZONS:
        sb = val_at(t, synth, ti_b + dt)
        sa = val_at(t, synth, ti_a + dt)
        mk_b = (sb - sy_b) / sy_b * 1e4               # BUY favorable
        mk_a = (sy_a - sa) / sy_a * 1e4               # SELL favorable
        mk   = np.concatenate([mk_b, mk_a])
        mean_mk = float(np.average(mk, weights=wnot))
        med_mk  = float(np.median(mk))

        # REALISTIC bracket: fill at the TOUCH (traded price) and mark to the TAPE'S OWN
        # future mid. The tape bounce = the REAL spread the pair expresses, so this raw
        # markout already contains genuine spread capture (entry systematically on the
        # favorable side) + true drift. net_raw = rebate + raw_markout, no extra spread.
        rb = val_at(t, mid, ti_b + dt)
        ra = val_at(t, mid, ti_a + dt)
        rmk_b = (rb - pi_b) / pi_b * 1e4
        rmk_a = (pi_a - ra) / pi_a * 1e4
        rmk = np.concatenate([rmk_b, rmk_a])
        raw_mk   = float(np.average(rmk, weights=wnot))
        net_raw  = REBATE_BPS + rmk
        npf_raw  = float(np.average(net_raw, weights=wnot))
        hr_raw   = float((net_raw / 1e4 * wnot).sum()) / span_hr if span_hr > 0 else 0.0

        # honest net per fill (spread capture is REAL & separate; no double count)
        net_no_spread = REBATE_BPS + mk                       # rebate alone vs adverse sel
        net_full      = spread_cap + REBATE_BPS + mk          # + earned half-spread
        npf0 = float(np.average(net_no_spread, weights=wnot))
        npfF = float(np.average(net_full,      weights=wnot))
        hr0  = float((net_no_spread / 1e4 * wnot).sum()) / span_hr if span_hr > 0 else 0.0
        hrF  = float((net_full      / 1e4 * wnot).sum()) / span_hr if span_hr > 0 else 0.0

        # circular-shift null on synth
        synth_s = np.roll(synth, n // 2)
        sb_s = val_at(t, synth_s, ti_b + dt); sy_b_s = val_at(t, synth_s, ti_b)
        sa_s = val_at(t, synth_s, ti_a + dt); sy_a_s = val_at(t, synth_s, ti_a)
        mk_s = np.concatenate([(sb_s - sy_b_s)/sy_b_s*1e4, (sy_a_s - sa_s)/sy_a_s*1e4])
        shuf_mk = float(np.average(mk_s, weights=wnot))

        out["horizons"][dt] = {
            "mean_markout_bps": round(mean_mk, 3),          # synth-mid adverse drift (strict)
            "median_markout_bps": round(med_mk, 3),
            "raw_markout_bps": round(raw_mk, 3),            # tape-mid (incl. real spread bounce)
            "net_pf_bps_rebate_only": round(npf0, 3),       # STRICT: rebate vs adverse drift, 0 spread
            "net_pf_bps_realistic": round(npf_raw, 3),      # REALISTIC: touch fill, tape mark
            "net_pf_bps_with_spread": round(npfF, 3),       # OPTIMISTIC (synth spread overstates)
            "usd_per_hr_rebate_only": round(hr0, 2),
            "usd_per_hr_realistic": round(hr_raw, 2),
            "usd_per_hr_with_spread": round(hrF, 2),
            "shuffle_markout_bps": round(shuf_mk, 3),
            "adverse_cost_bps": round(shuf_mk - mean_mk, 3),
            "SEAT_strict": bool(npf0 > 0),
            "SEAT_realistic": bool(npf_raw > 0),
        }
    return out


if __name__ == "__main__":
    pairs = sys.argv[1:] or ["CAPUSD","HYPEUSD","SYNUSD","MONUSD","XPLUSD","SLXUSD","CCUSD","NIGHTUSD"]
    results = {}
    for pair in pairs:
        path = f"/tmp/sc/{pair}.json"
        if not os.path.exists(path):
            print(f"SKIP {pair}"); continue
        r = simulate(path, pair); results[pair] = r
        h5, h30 = r["horizons"][5], r["horizons"][30]
        print(f"{pair:9s} span={r['span_hr']:6.0f}h fills={r['n_bid_fills']+r['n_ask_fills']:7d} | "
              f"5s: adv_mk={h5['mean_markout_bps']:+6.2f} "
              f"STRICT(net0={h5['net_pf_bps_rebate_only']:+6.2f} S={str(h5['SEAT_strict'])[0]}) "
              f"REAL(net={h5['net_pf_bps_realistic']:+6.2f} $/hr={h5['usd_per_hr_realistic']:+7.1f} S={str(h5['SEAT_realistic'])[0]}) "
              f"| 30s: adv_mk={h30['mean_markout_bps']:+7.2f} net0={h30['net_pf_bps_rebate_only']:+6.2f}")
    json.dump(results, open("/tmp/sc/_s68_markout_results.json","w"), indent=2)
    print("\nwrote /tmp/sc/_s68_markout_results.json")
