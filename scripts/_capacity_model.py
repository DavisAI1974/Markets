"""_capacity_model.py — per-cell DOLLAR-capacity + fill model + REBATE/spread sweep (S50 base, S51 rebate).

Turns the illustrative "$/hr" back-of-envelope into an honest, data-bounded number. Reuses the EXACT
deployable pipeline (build_channels -> detect_flips -> simulate_swing_maker with cover-grace) to get the real
swing legs, then overlays a SIZE-dependent fill bounded by the ACTUAL opposing trade flow available at our
resting quote over each leg. No fabricated depth: a passive quote of size S fills only as much as the real
opposing $ that trades through it before the turn.

Per leg (side=+1 long/bid, -1 short/ask):
  entry fill is lifted by OPPOSING trades from open_idx forward (long bid <- SELL flow; short ask <- BUY flow),
  capped at the leg close. exit is at the next turn (typically a ~2x volume climax, S40) so entry is the tighter
  constraint -> we bound leg capacity by the ENTRY-side opposing $ flow over the hold (conservative).
  At deploy size S:  filled$ = min(S, leg_cap$);  pnl$ = (net_bps/1e4) * filled$   (full net_bps on the fill,
  same optimism as the executor's own model -- flagged).

S51 REBATE SWEEP (Greg S50 decision — pivot to a rebate venue; quantify the lever FIRST). The single biggest
magnitude lever is a maker REBATE (paid, not charged) + a WIDER-spread book. A leg's open/close CELL INDICES are
determined ONLY by opposing trade volume (`_next_positive`) — they do NOT depend on fees or the half-spread — so
the real swing legs (and their flow-bounded caps + conviction-sizing features) are IDENTICAL across scenarios;
only each leg's net_bps changes. We therefore build channels ONCE per cell and re-run the (cheap) executor per
scenario = (maker_fee_bps, spread_mult):
  - maker_fee_bps NEGATIVE = rebate (paid per maker leg). A -1 bp rebate adds +2 bps/round-trip (open+close maker).
  - spread_mult scales the half-spread we capture (a WIDER-spread venue book => more half-spread per maker leg).
And we report FLAT vs SIZED (odcore.swing_maker.size_legs, leakage-clean) at each scenario so the conviction-
sizing lift stays visible AND we can read the rebate x sizing INTERACTION: a rebate adds +2 bps to every leg,
cushioning the wrong-tail the sizing loads into, so the sizing lift (%) should GROW as the rebate deepens.

CAVEATS (v1 fill): (1) full net_bps captured on the filled portion (executor optimism, same as production);
(2) no price-impact / walk-the-book markdown for resting deeper than top-of-book (a v2 adverse-selection
refinement); (3) exit assumed >= entry capacity (climax volume at turns); (4) spread_mult is an ASSUMED wider
book, not a measured venue — Job 3 measures the real venue book. So these are an UPPER bound on capacity-limited
$/hr, bounded by REAL flow (not fabricated) -> a fair per-cell / per-scenario ranking.
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker, size_legs

FLOW_W, WFLIP, REV, DIVW = 20, 600, 0.1, 600
FILL_W = 10   # cells (1.0s) — a FIXED per-turn position fills near the turn (S40 climax volume), it does NOT
              # keep scaling into the whole adverse leg. Bounding fill to this entry window (not the whole hold)
              # removes the whole-hold-accumulation artifact that made the S->inf ceiling spuriously negative
              # (Greg S50: "the wrong tail issue sounds like a coding issue" — confirmed, whole-hold was wrong).
CELLS = [("sol", 1), ("doge", 1), ("xrp", 1), ("eth", 1), ("btc", 10)]
GRACE = {"sol": 300, "doge": 600, "xrp": 300, "eth": 300, "btc": 300}
SIZES = [100.0, 250.0, 500.0, 1_000.0, 2_500.0, 5_000.0, 10_000.0, 25_000.0, 50_000.0, 1e12]  # $ per leg; last = inf
REP_S = 1_000.0   # representative deploy size for the headline scenario table
# scenarios = (label, maker_fee_bps, spread_mult). maker<0 = REBATE; spread_mult scales the captured half-spread.
SCEN = [("mk0  ·1.0x", 0.0, 1.0), ("mk-1 ·1.0x", -1.0, 1.0), ("mk-2 ·1.0x", -2.0, 1.0),
        ("mk-1 ·1.5x", -1.0, 1.5), ("mk-2 ·1.5x", -2.0, 1.5)]


def _leg_features(legs, mid, sret, buy, sell, lean, piv):
    """Per-leg CAUSAL conviction features at the flip cell — IDENTICAL to paper_trade.cell_trades (clmx quality
    axis + crude size proxy). Leg indices are fee/spread-independent so these are the same across scenarios."""
    vol = buy + sell
    cvol = np.concatenate([[0.0], np.cumsum(vol)])
    vm = lambda t, w: (cvol[t + 1] - cvol[max(0, t + 1 - w)]) / (t + 1 - max(0, t + 1 - w))
    clmx, size_score = [], []
    for l in legs:
        ci = int(l.flip_idx); p = piv.get(ci, ci); lo = max(0, ci - DIVW)
        cx = vm(ci, 60) / (vm(ci, 600) + 1e-12)
        v60 = vm(ci, 60); vlt = float(np.std(sret[max(0, ci - 120):ci + 1])) * 1e4
        rnp = abs(mid[ci] - mid[lo]) / mid[lo] * 1e4; dp = abs(lean[p])
        clmx.append(cx); size_score.append(v60 + vlt + rnp + dp)
    return clmx, size_score


def _leg_caps(legs, mid, buy, sell, bb, ba, queue_frac=1.0, window=FILL_W, price_eligible=True):
    """flow-bounded $ capacity per leg (entry-window opposing flow) — fee/spread independent.
    Returns (v1, v2):
      v1 = opposing $ flow in the entry window that can actually reach our FIXED limit (see eligibility).
      v2 = QUEUE-HONEST (Job 4, odcore.maker_book discipline): we join the BACK of the best level at the
           post cell, so the size already resting AHEAD of us (best-level size x queue_frac) must trade
           through before our first unit fills -> fillable$ = max(0, window_opp_flow - queue_ahead) x px.
    window: cells after the fill cell the order stays working (a TIF / cancel-remainder policy);
            None = rest until the leg close (the executor's actual no-window design).
    price_eligible (S52 correction): a fixed limit at the post cell only fills in cells where the venue's
    best is at-or-through it (long: mid[t] <= mid[flip]; short: mid[t] >= mid[flip]). The old model summed
    ALL window flow — crediting winners with flow that traded after price had left the limit. That
    overstated mk0 $/hr on every cell (S52 fill-window audit); eligibility is now the default.
    Exit side stays un-marked (turns are ~2x volume climaxes, S40) — flagged, same as v1."""
    v1, v2 = [], []
    W = window
    for l in legs:
        o, c, ci = int(l.open_idx), int(l.close_idx), int(l.flip_idx)
        if c <= o:
            v1.append(0.0); v2.append(0.0); continue
        end = c if W is None else min(c, o + W)
        seg = slice(o, end + 1)
        opp_arr = (sell if l.side > 0 else buy)[seg]
        if price_eligible:
            m = mid[seg]
            ok = (m <= mid[ci]) if l.side > 0 else (m >= mid[ci])
            opp = float(np.sum(opp_arr[ok]))
        else:
            opp = float(np.sum(opp_arr))                                          # coin units
        qa = float((bb if l.side > 0 else ba)[o]) * queue_frac                    # resting ahead of us
        px = float(mid[o])
        v1.append(opp * px)
        v2.append(max(0.0, opp - qa) * px)
    return np.asarray(v1), np.asarray(v2)


def _dollars(nets, sizes, caps, hrs, S):
    """$/hr at deploy size S — flat (sizes=1) and sized share the same flow-bounded fill; sizing scales the
    per-leg NOTIONAL (size*S capped by the same real flow), so conviction concentrates capital on high-legs."""
    filled = np.minimum(S * sizes, caps)
    return float(np.sum(nets / 1e4 * filled)) / hrs


def cell_scenarios(coin, K, grace):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(path):
        return None
    raw = load_book(path)                                    # parse the gzip ONCE; reuse for every consumer
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    sret = ch["signed_ret"]
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    piv = {int(c): int(p) for (c, p, s) in allf}

    scen_out = []
    caps = caps2 = feats = None
    for label, mk, smul in SCEN:
        res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs * smul,
                                   maker_fee_bps=mk, taker_fee_bps=5.0, cover_grace=grace)
        legs = res.legs
        if caps is None:                       # leg indices are scenario-independent — compute caps/feats once
            caps, caps2 = _leg_caps(legs, mid, buy, sell, bb, ba)
            feats = _leg_features(legs, mid, sret, buy, sell, lean, piv)
        nets = np.asarray([float(l.net_bps) for l in legs])
        # conviction sizing (sets leg.size in place, leakage-clean) — same features across scenarios
        size_legs(legs, feats[0], feats[1], alpha=1.0, roll=200)
        sizes = np.asarray([float(l.size) for l in legs])
        ones = np.ones_like(sizes)
        flat_rep = _dollars(nets, ones, caps, hrs, REP_S)
        sized_rep = _dollars(nets, sizes, caps, hrs, REP_S)
        flat_ceil = _dollars(nets, ones, caps, hrs, 1e12)
        sized_ceil = _dollars(nets, sizes, caps, hrs, 1e12)
        # v2 queue-honest (Job 4): the same policy marked down by the size resting ahead of us
        flat_rep2 = _dollars(nets, ones, caps2, hrs, REP_S)
        sized_rep2 = _dollars(nets, sizes, caps2, hrs, REP_S)
        flat_ceil2 = _dollars(nets, ones, caps2, hrs, 1e12)
        lift = (sized_rep - flat_rep) / abs(flat_rep) * 100 if flat_rep else float("nan")
        scen_out.append(dict(label=label, maker=mk, spread_mult=smul, mean_net=float(nets.mean()),
                             flat_rep=flat_rep, sized_rep=sized_rep, flat_ceil=flat_ceil,
                             sized_ceil=sized_ceil, sizing_lift_pct=lift,
                             v2_flat_rep=flat_rep2, v2_sized_rep=sized_rep2, v2_flat_ceil=flat_ceil2))
    return dict(coin=coin, hrs=hrs, n_legs=len(caps), turns_hr=len(caps) / hrs,
                med_cap=float(np.median(caps)), med_cap_v2=float(np.median(caps2)),
                fillable_leg_frac_v2=float(np.mean(caps2 > 0)), scen=scen_out)


def main():
    print(f"=== per-cell DOLLAR-capacity + REBATE/spread sweep (Coinbase books, tk5, cover-grace) ===")
    print(f"    rep size ${REP_S:,.0f}/leg; ceiling = all available opposing flow captured; flat vs SIZED\n")
    results = []
    for coin, K in CELLS:
        r = cell_scenarios(coin, K, GRACE[coin])
        if r is None:
            print(f"[{coin}] no book\n"); continue
        results.append(r)
        print(f"[{coin.upper()}]  {r['hrs']:.1f}h  turns/hr={r['turns_hr']:.1f}  med leg-cap ${r['med_cap']:,.0f}"
              f"  | v2 queue-honest: med ${r['med_cap_v2']:,.0f}, {r['fillable_leg_frac_v2']*100:.0f}% legs fillable")
        print(f"   {'scenario':11s}{'net/leg':>9}{'flat $/hr':>11}{'sized $/hr':>12}{'lift%':>7}"
              f"{'flat ceil':>11}{'sized ceil':>12}{'v2 flat':>9}{'v2 sized':>10}{'v2 ceil':>9}")
        for s in r["scen"]:
            print(f"   {s['label']:11s}{s['mean_net']:>+8.2f}b{s['flat_rep']:>+11,.0f}{s['sized_rep']:>+12,.0f}"
                  f"{s['sizing_lift_pct']:>+6.0f}%{s['flat_ceil']:>+11,.0f}{s['sized_ceil']:>+12,.0f}"
                  f"{s['v2_flat_rep']:>+9,.0f}{s['v2_sized_rep']:>+10,.0f}{s['v2_flat_ceil']:>+9,.0f}")
        print()
    # SOL rebate summary (the focus cell) — how much a rebate + wider book buys, and the sizing interaction
    sol = next((r for r in results if r["coin"] == "sol"), None)
    if sol:
        base = sol["scen"][0]["sized_ceil"]
        print("=== SOL rebate lever (sized ceiling $/hr vs the mk0 baseline) + sizing interaction ===")
        for s in sol["scen"]:
            mult = s["sized_ceil"] / base if base else float("nan")
            print(f"   {s['label']:11s}  net/leg {s['mean_net']:>+6.2f}bps  sized ceil {s['sized_ceil']:>+8,.0f} $/hr"
                  f"  ({mult:.2f}x baseline)   sizing lift {s['sizing_lift_pct']:>+5.0f}%")
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_capacity_model_results.json"), "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
