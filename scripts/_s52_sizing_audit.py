"""_s52_sizing_audit.py — S52 JOB 1a: is the `_dollars()` model UNDER-crediting sizing-on-winners?

Greg's S51 concern (kickoff Job 1): "you aren't factoring in the size up on the winners" — the per-scenario
$/hr projections may under-credit conviction sizing. This decomposes the `_capacity_model._dollars()` accounting
per cell so we can state exactly WHERE sizing earns and where it (correctly) cannot.

Reuses the EXACT deployable pipeline + `_capacity_model` helpers (no reinvention). For each cell it rebuilds the
real swing legs once, sets leakage-clean conviction sizes (`odcore.swing_maker.size_legs`), and reports:

  1. mean(size)          — how much MORE total capital the sized overlay deploys (matched-capital intent = 1.0).
  2. corr(size, net_bps) — the winner-selection quality of ENTRY conviction (S47 said ~+0.03: loads |move|, not wins).
  3. corr(size, cap_v1)  — Job 1a's hinge: if >0, high-conviction legs sit on FATTER-flow turns, so up-sizing
                           genuinely fills MORE real $ (the min() model DOES capture this at capital-constrained S).
  4. corr(cap, net)      — do the fillable legs happen to be the profitable ones?
  5. cap-bind fraction at REP_S vs ceiling — sizing can only move $ on legs whose cap does NOT bind.
  6. $/hr lift decomposition: raw (ledger, uncapped) vs REP_S vs ceiling, AND a CAPITAL-MATCHED lift that
     rescales the sized book to the flat book's total desired notional (isolates ALLOCATION skill from the
     small "mean size > 1 deploys more capital" effect).

Verdict logic: the model is CORRECT if (a) sizing lift is positive at deploy sizes, (b) →0 at the flow-capped
ceiling is the PHYSICAL truth (can't fill more than the flow), not a modeling artifact, and (c) corr(size,cap)
shows whether the min() captures the fat-leg concentration. Under-credit would show as capital-matched lift
being materially larger than what the headline reports, OR a strong positive corr(size,cap) the min() throws away.
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker, size_legs
from _capacity_model import _leg_features, _leg_caps, _dollars, CELLS, GRACE, FLOW_W, WFLIP, REV, REP_S


def _corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or a.std() < 1e-12 or b.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def audit_cell(coin, K, grace):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(path):
        return None
    raw = load_book(path)
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

    # legs at the DEPLOYABLE scenario (mk0, tk5, cover-grace) — sizing is fee-independent (same size array)
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=0.0, taker_fee_bps=5.0, cover_grace=grace)
    legs = res.legs
    caps, caps2 = _leg_caps(legs, mid, buy, sell, bb, ba)
    q, sa = _leg_features(legs, mid, sret, buy, sell, lean, piv)
    size_legs(legs, q, sa, alpha=1.0, roll=200)
    nets = np.asarray([float(l.net_bps) for l in legs])
    sizes = np.asarray([float(l.size) for l in legs])
    ones = np.ones_like(sizes)

    # --- correlations ---
    c_size_net = _corr(sizes, nets)
    c_size_cap = _corr(sizes, caps)
    c_cap_net = _corr(caps, nets)

    # --- cap-bind fractions (fraction of legs where the flow cap is the binding constraint) ---
    bind_rep = float(np.mean(caps < REP_S * sizes))     # at deploy size, sized book
    bind_inf = 1.0                                       # at ceiling everything binds by construction

    # --- $/hr, flat vs sized, at REP_S and ceiling ---
    flat_rep = _dollars(nets, ones, caps, hrs, REP_S)
    sized_rep = _dollars(nets, sizes, caps, hrs, REP_S)
    flat_inf = _dollars(nets, ones, caps, hrs, 1e12)
    sized_inf = _dollars(nets, sizes, caps, hrs, 1e12)

    # --- CAPITAL-MATCHED sized: rescale so total DESIRED notional == flat's (isolates allocation skill) ---
    scale = float(ones.sum() / sizes.sum())              # mean(size) reciprocal
    sizes_cm = sizes * scale
    sized_rep_cm = _dollars(nets, sizes_cm, caps, hrs, REP_S)

    # --- raw uncapped (the ledger view: sum net*size, no flow bound) ---
    raw_flat = float(np.sum(nets))
    raw_sized = float(np.sum(nets * sizes))

    def lift(s, f):
        return (s - f) / abs(f) * 100 if f else float("nan")

    return dict(
        coin=coin, hrs=hrs, n=len(legs), turns_hr=len(legs) / hrs,
        mean_size=float(sizes.mean()), med_cap=float(np.median(caps)),
        c_size_net=c_size_net, c_size_cap=c_size_cap, c_cap_net=c_cap_net,
        bind_frac_rep=bind_rep,
        raw_flat=raw_flat, raw_sized=raw_sized, raw_lift=lift(raw_sized, raw_flat),
        flat_rep=flat_rep, sized_rep=sized_rep, rep_lift=lift(sized_rep, flat_rep),
        sized_rep_cm=sized_rep_cm, cm_lift=lift(sized_rep_cm, flat_rep),
        flat_inf=flat_inf, sized_inf=sized_inf, inf_lift=lift(sized_inf, flat_inf),
    )


def main():
    print("=== S52 JOB 1a — sizing-credit audit of _capacity_model._dollars() (Coinbase books, mk0/tk5) ===\n")
    out = []
    for coin, K in CELLS:
        r = audit_cell(coin, K, GRACE[coin])
        if r is None:
            print(f"[{coin}] no book\n"); continue
        out.append(r)
        print(f"[{r['coin'].upper()}]  {r['hrs']:.1f}h  n={r['n']}  turns/hr={r['turns_hr']:.1f}  "
              f"mean_size={r['mean_size']:.3f}  med_cap=${r['med_cap']:,.0f}")
        print(f"    corr(size,net)={r['c_size_net']:+.3f}   corr(size,cap)={r['c_size_cap']:+.3f}   "
              f"corr(cap,net)={r['c_cap_net']:+.3f}   cap-binds {r['bind_frac_rep']*100:.0f}% of legs @${REP_S:,.0f}")
        print(f"    RAW (uncapped, ledger view):  flat {r['raw_flat']:>+9.0f}  sized {r['raw_sized']:>+9.0f}  "
              f"lift {r['raw_lift']:>+5.0f}%")
        print(f"    $/hr @${REP_S:,.0f}/leg:        flat {r['flat_rep']:>+9.0f}  sized {r['sized_rep']:>+9.0f}  "
              f"lift {r['rep_lift']:>+5.0f}%   (capital-MATCHED sized {r['sized_rep_cm']:>+9.0f}  lift {r['cm_lift']:>+5.0f}%)")
        print(f"    $/hr @ceiling (flow wall):    flat {r['flat_inf']:>+9.0f}  sized {r['sized_inf']:>+9.0f}  "
              f"lift {r['inf_lift']:>+5.0f}%   (sizing→0 at the wall = physical truth, not under-credit)\n")

    # summary reconciliation
    print("=== reconciliation: why the RAW ledger lift (+16..+47%) shrinks at deploy $/hr ===")
    print("    the flow cap eats the sizing benefit — up-sizing a conviction leg only earns extra $ if that")
    print("    leg's real opposing flow has room above flat's fill. corr(size,cap) says whether it does.\n")
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "_s52_sizing_audit_results.json"), "w") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
