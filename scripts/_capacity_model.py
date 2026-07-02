"""_capacity_model.py — per-cell DOLLAR-capacity + fill model (S50, Coinbase-first).

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

Sweeps S over a log grid and reports, per cell: turns/hr, median/mean leg capacity $, the $/hr at each S, the
SATURATION size (largest S with mean fill-fraction >= 0.90 = the "linear" region where $ scales with size), and
the asymptotic $/hr ceiling (S -> inf = capture all available opposing flow). This is the honest capacity curve.

CAVEATS (v1): (1) full net_bps captured on the filled portion (executor optimism, same as production);
(2) no price-impact / walk-the-book markdown for resting deeper than top-of-book (a v2 adverse-selection
refinement); (3) exit assumed >= entry capacity (climax volume at turns). So these are an UPPER bound on
capacity-limited $/hr, but bounded by REAL flow (not fabricated) -> a fair per-cell ranking.
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker

FLOW_W, WFLIP, REV = 20, 600, 0.1
FILL_W = 10   # cells (1.0s) — a FIXED per-turn position fills near the turn (S40 climax volume), it does NOT
              # keep scaling into the whole adverse leg. Bounding fill to this entry window (not the whole hold)
              # removes the whole-hold-accumulation artifact that made the S->inf ceiling spuriously negative
              # (Greg S50: "the wrong tail issue sounds like a coding issue" — confirmed, whole-hold was wrong).
CELLS = [("sol", 1), ("doge", 1), ("xrp", 1), ("eth", 1), ("btc", 10)]
GRACE = {"sol": 300, "doge": 600, "xrp": 300, "eth": 300, "btc": 300}
SIZES = [100.0, 250.0, 500.0, 1_000.0, 2_500.0, 5_000.0, 10_000.0, 25_000.0, 50_000.0, 1e12]  # $ per leg; last = inf


def cell_capacity(coin, K, grace):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(path):
        return None
    ch, g = build_channels(path, K, FLOW_W)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    hs = median_spread_bps(path) / 2.0
    d = load_book(path); hrs = (d["ts"][-1] - d["ts"][0]) / 3600.0
    allf = detect_flips(lean_series(buy, sell, WFLIP), REV)[0]
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=0.0, taker_fee_bps=5.0, cover_grace=grace)
    # opposing $ flow available to fill each leg's fixed-size ENTRY, over a realistic entry window near the
    # turn (NOT the whole hold — that overstated capacity on losing legs where price runs against us and
    # opposing flow floods for the whole leg; a fixed per-turn position fills near the turn and holds).
    caps, nets = [], []
    for l in res.legs:
        o, c = int(l.open_idx), int(l.close_idx)
        if c <= o:
            continue
        end = min(c, o + FILL_W)
        # long (side+1) rests a BID -> lifted by SELL flow; short (side-1) rests an ASK -> lifted by BUY flow.
        opp = sell[o:end + 1] if l.side > 0 else buy[o:end + 1]
        cap_usd = float(np.sum(opp)) * float(mid[o])     # coin units * price = $ fillable at our quote
        caps.append(cap_usd); nets.append(float(l.net_bps))
    caps = np.asarray(caps); nets = np.asarray(nets)
    n_legs = len(caps)
    # $/hr and mean fill-fraction at each deploy size S
    rows = []
    for S in SIZES:
        filled = np.minimum(S, caps)
        pnl_usd = float(np.sum(nets / 1e4 * filled))
        fillfrac = float(np.mean(np.minimum(1.0, caps / S))) if S < 1e11 else float("nan")
        rows.append((S, pnl_usd / hrs, fillfrac))
    # saturation size = largest S in the finite grid with mean fill-fraction >= 0.90
    sat = 0.0
    for S, _, ff in rows:
        if S < 1e11 and ff >= 0.90:
            sat = S
    ceiling = rows[-1][1]  # S=inf $/hr = all available opposing flow captured
    return dict(coin=coin, hrs=hrs, n_legs=n_legs, turns_hr=n_legs / hrs,
                med_cap=float(np.median(caps)), mean_cap=float(np.mean(caps)),
                mean_net=float(np.mean(nets)), sat=sat, ceiling=ceiling, rows=rows)


def main():
    print("=== per-cell DOLLAR-capacity model (Coinbase, mk0/tk5, cover-grace, sized off) ===\n")
    results = []
    for coin, K in CELLS:
        r = cell_capacity(coin, K, GRACE[coin])
        if r is None:
            print(f"[{coin}] no book\n"); continue
        results.append(r)
        print(f"[{coin.upper()}]  {r['hrs']:.1f}h  turns/hr={r['turns_hr']:.1f}  net/leg={r['mean_net']:+.2f}bps  "
              f"leg-cap $: med={r['med_cap']:,.0f} mean={r['mean_cap']:,.0f}")
        print(f"      $/hr by deploy size (per leg):")
        for S, phr, ff in r["rows"]:
            tag = "  (=ceiling, all flow)" if S >= 1e11 else f"  fill={ff*100:4.0f}%"
            slab = "inf" if S >= 1e11 else f"${S:,.0f}"
            print(f"        {slab:>10}: {phr:>+10,.0f} $/hr{tag}")
        print(f"      -> saturation (fill>=90%) at ~${r['sat']:,.0f}/leg ; ceiling {r['ceiling']:+,.0f} $/hr\n")
    # ranking by ceiling $/hr
    results.sort(key=lambda x: -x["ceiling"])
    print("=== RANK by capacity-ceiling $/hr (all available flow captured, mk0) ===")
    for r in results:
        print(f"  {r['coin'].upper():5s}  ceiling {r['ceiling']:>+10,.0f} $/hr   saturates ~${r['sat']:>8,.0f}/leg   "
              f"net/leg {r['mean_net']:+.2f}bps")
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_capacity_model_results.json"), "w") as f:
        json.dump([{k: v for k, v in r.items() if k != "rows"} | {"rows": r["rows"]} for r in results], f, indent=2)


if __name__ == "__main__":
    main()
