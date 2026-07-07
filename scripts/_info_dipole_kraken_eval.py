"""_info_dipole_kraken_eval.py — reproduce the S36 fingerprint/dipole evaluation, UNCHANGED IN METHOD,
on the 42h Kraken BOOKS (5 majors' common ~41.9h window), through the LIVE path.

Same three pieces as S36_NETCOST_BACKTEST_FINDINGS.md, only the DATA SURFACE changes (tape/1-min/bybit
-> Kraken 1-sec BOOK) and the ONSETS come from the LIVE firing (run_kraken_cell legs), not winner_onsets.json:

  A. Divergence + Exhaustion net-of-cost, PER CELL (coin x buy/sell), walk-forward halves + the
     reversal-conviction ladder (opposing+exhausting ... with-trend+strengthening). Costs reported at
     0bp maker (our deploy fee) AND 10bp round-trip (the S36 reference). Policies FLOW/FLOW_2F/FADE_GATE/
     FOLLOW_ALL are imported VERBATIM from _info_dipole_netcost_backtest.
  B. Signed-flow feature lifts (imb_level, ent_dipole, C_signed, mi_flow, imb_flow) per cell vs the
     forward 30-min return sign — the DEPLOY_VALIDATED probe recomputed on the book (method verbatim
     from _info_dipole_flow_probe / odcore.info_dipole.signed_flow_features).
  C. Falsification harness — dipole divergence() FILTER vs the classical OFI champion, same 1-sec timing
     trigger, OOS (tune 60% / score 40%). The harness functions (candidates/filt_*/run_calls/score/
     tune_and_score/zigzag) are imported VERBATIM from _info_dipole_harness; only the series source is the
     Kraken book.

SIM=LIVE: onsets are the LIVE executor's legs (basket_sim run_cell -> run_kraken_cell -> swing_maker),
firing untouched. BOOK not tape: buy/sell are the book's per-second taker volume, price is the book mid.
Pre-entry/no-leakage: the dipole window is strictly [onset-WIN, onset] (<= onset only); proven with
odcore.leakage.assert_no_leakage. Costs are the audit price-return convention (dir*ret - cost), reported at
0 and 10 bps, exactly as the original.

CAVEAT (unchanged, load-bearing): ONE 42h low-edge window = current conditions, thin per-leg edge; a FIRST
CUT on this surface, not deploy-grade. Report per cell ("clears on {X}, not {Y}"), never "failed".

Run: python scripts/_info_dipole_kraken_eval.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basket_sim_kraken import load_book, run_cell, CELLS                      # LIVE book loader + firing
from odcore.info_dipole import (divergence, DIVERGE_STRONG,                    # the dipole operators (verbatim)
                                signed_flow_features, FEATURES as FEATS)
from odcore.leakage import assert_no_leakage                                   # mandatory pre-entry check
# original method functions, imported VERBATIM (no reimplementation):
from _info_dipole_netcost_backtest import (pol_flow, pol_flow_2f, pol_fade_gate, pol_follow_all,
                                           apply, summ, fmt)
import _info_dipole_harness as H

WIN_S = 1800     # pre-entry order-flow window (30 min = 1800 s on the 1-sec book grid) — matches original
FWD_S = 1800     # forward window for the piece-B validation target (look-ahead; validation only)


# ======================================================================================================
# load the 5 books, clip to the common ~41.9h overlap (the window pool_book_kraken used)
# ======================================================================================================
def load_clipped():
    books = {}
    for cell in CELLS:
        if not cell["active"]:
            continue
        bk = load_book(cell["coin"])
        if bk is not None:
            books[cell["coin"]] = bk
    ov0 = max(bk["t0"] for bk in books.values())
    ov1 = min(bk["t0"] + bk["n"] - 1 for bk in books.values())
    ov_sec = ov1 - ov0 + 1
    clips = {}
    for cell in CELLS:
        if not cell["active"] or cell["coin"] not in books:
            continue
        c = cell["coin"]; bk = books[c]; s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        clip["hs"] = bk["hs"]
        clips[c] = clip
    return clips, ov_sec


# ======================================================================================================
# PIECE A — build onset records from the LIVE firing legs; grade net-of-cost per cell
# ======================================================================================================
def build_records(cell, clip):
    """One record per LIVE-firing onset (leg) where the dipole is evaluable. cell = coin_kraken_{buy|sell}
    per LEG side. Pre-entry dipole on [open-WIN, open] (<= onset); forward return over the leg's OWN hold
    (the executor's exit -> SIM=LIVE). Fields match _info_dipole_netcost_backtest.build_trades output."""
    coin = cell["coin"]
    mid = clip["mid"]; buy = clip["buy"]; sell = clip["sell"]
    _, res = run_cell(cell, clip, fill_model="front")                 # LIVE firing -> legs (onsets)
    out = []
    for l in res.legs:
        o = int(l.open_idx); x = int(l.close_idx)
        if x <= o:
            continue
        lo = max(0, o - WIN_S)
        if o - lo < 6:
            continue
        p_entry = float(mid[o]); p_exit = float(mid[x])
        pre_drift = float(mid[o] - mid[lo])
        if pre_drift == 0 or p_entry <= 0:
            continue
        dv = divergence(buy[lo:o + 1], sell[lo:o + 1], pre_drift)     # strictly pre-entry (<= onset)
        if dv is None:
            continue
        side = "buy" if int(l.side) > 0 else "sell"
        ret_bps = (p_exit / p_entry - 1.0) * 1e4
        pre_sign = 1.0 if pre_drift > 0 else -1.0
        out.append({
            "cell": f"{coin}_kraken_{side}", "ts": o, "side": side,
            "confirms": dv["confirms"], "opposing": dv["opposing"], "exhausting": dv["exhausting"],
            "expect": dv["expect"], "strong": (dv["aligned_flow"] <= DIVERGE_STRONG),
            "aligned": dv["aligned_flow"], "conviction": dv["reversal_conviction"],
            "pre_sign": pre_sign, "ret_bps": ret_bps,
            "reversal": (np.sign(ret_bps) != pre_sign and ret_bps != 0),
            "hold_s": x - o,
        })
    return out


def conviction_ladder(records):
    """Reversal RATE by the 4 flow-states (the S36 monotonic stack: opposing+exhausting ~64% ...
    with-trend+strengthening ~49%). A 'reversal' = forward-return sign != pre-entry drift sign."""
    buckets = {"opp+exh": [], "opp+str": [], "trend+weak": [], "trend+str": []}
    for r in records:
        opp = r["opposing"]; exh = r["exhausting"]
        key = ("opp" if opp else "trend") + ("+exh" if exh else "+str") if opp else \
              ("trend" + ("+weak" if exh else "+str"))
        # explicit mapping to the 4 canonical labels
        if opp and exh:
            key = "opp+exh"
        elif opp and not exh:
            key = "opp+str"
        elif (not opp) and exh:
            key = "trend+weak"
        else:
            key = "trend+str"
        buckets[key].append(1.0 if r["reversal"] else 0.0)
    out = {}
    for k, v in buckets.items():
        out[k] = {"n": len(v), "reversal_rate": round(100 * float(np.mean(v)), 1) if v else None}
    return out


# ======================================================================================================
# PIECE B — signed-flow feature lift over base rate, per cell (verbatim method)
# ======================================================================================================
def flow_probe(clips):
    per_cell = defaultdict(lambda: {f: [0, 0] for f in FEATS})     # cell -> feat -> [correct, n]
    cell_fwd = defaultdict(lambda: [0, 0])                         # cell -> [n_up, n_down]
    overall = {f: [0, 0] for f in FEATS}
    for cell in CELLS:
        if not cell["active"]:
            continue
        coin = cell["coin"]; clip = clips[coin]
        mid = clip["mid"]; buy = clip["buy"]; sell = clip["sell"]
        _, res = run_cell(cell, clip, fill_model="front")
        for l in res.legs:
            o = int(l.open_idx)
            lo = max(0, o - WIN_S)
            if o - lo < 6:
                continue
            fv = signed_flow_features(buy[lo:o + 1], sell[lo:o + 1])
            if fv is None:
                continue
            f_end = min(len(mid) - 1, o + FWD_S)
            if f_end <= o:
                continue
            d = float(mid[f_end] - mid[o])
            tgt = 0 if d == 0 else (1 if d > 0 else -1)
            if not tgt:
                continue
            side = "buy" if int(l.side) > 0 else "sell"
            cellname = f"{coin}_kraken_{side}"
            cell_fwd[cellname][0 if tgt > 0 else 1] += 1
            for f in FEATS:
                s = fv[f]
                if s == 0:
                    continue
                ok = (1 if s > 0 else -1) == tgt
                per_cell[cellname][f][0] += ok; per_cell[cellname][f][1] += 1
                overall[f][0] += ok; overall[f][1] += 1

    def base_rate(cell):
        up, dn = cell_fwd[cell]
        return 100 * max(up, dn) / (up + dn) if up + dn else 0.0

    return per_cell, cell_fwd, overall, base_rate


# ======================================================================================================
# PIECE C — harness: dipole filter vs OFI champion on the Kraken 1-sec book (verbatim harness funcs)
# ======================================================================================================
def kraken_series(clips, ov_sec):
    """{coin_kraken: (ts, mid, buy, sell)} on the clipped 1-sec grid — the series the harness consumes."""
    out = {}
    for coin, clip in clips.items():
        n = ov_sec
        ts = np.arange(n, dtype=float)
        p = clip["mid"][:n].astype(float)
        bv = clip["buy"][:n].astype(float); sv = clip["sell"][:n].astype(float)
        ok = p > 0
        out[f"{coin}_kraken"] = (ts[ok], p[ok], bv[ok], sv[ok])
    return out


def run_harness(series):
    champ_grid = [(R / 1e4, W, T) for R in (5, 8, 12) for W in (60, 300) for T in (0.05, 0.10, 0.20)]
    chall_grid = [(R / 1e4, W, C) for R in (5, 8, 12) for W in (300, 900, 1800) for C in (0.0, 0.15, 0.30, 0.50)]
    print(f"\n{'venue':16s} {'detector':10s} {'calls':>6s} {'recall':>7s} {'prec':>6s} "
          f"{'bps2turn':>9s} {'net@10tk':>9s} {'net@4mk':>9s}")
    print("-" * 82)
    agg = {"CHAMPION": [], "CHALLENGER": []}
    out = {}
    for s in sorted(series):
        ts, p, bv, sv = series[s]
        cut = int(len(p) * H.IS_FRAC)
        seg_is = (ts[:cut], p[:cut], bv[:cut], sv[:cut])
        seg_oos = (ts[cut:], p[cut:], bv[cut:], sv[cut:])
        champ = H.tune_and_score("CHAMPION", H.filt_champion, champ_grid, seg_is, seg_oos)
        chall = H.tune_and_score("CHALLENGER", H.filt_dipole, chall_grid, seg_is, seg_oos)
        out[s] = {"champion": champ, "challenger": chall}
        for tag, r in [("CHAMPION", champ), ("CHALLENGER", chall)]:
            agg[tag].append(r)
            print(f"{s if tag=='CHAMPION' else '':16s} {tag:10s} {r['n_calls']:>6d} "
                  f"{r['recall']:>7.3f} {str(r['precision']):>6s} {str(r['bps_to_turn']):>9s} "
                  f"{r['net_oos']:>+8.0f} {r['net_oos_maker']:>+8.0f}")
        print("-" * 82)
    print("POOLED OOS (mean over venues):")
    pooled = {}
    for tag in ("CHAMPION", "CHALLENGER"):
        rs = agg[tag]
        mr = float(np.mean([r["recall"] for r in rs]))
        mp = float(np.mean([r["precision"] for r in rs if r["precision"] is not None])) if any(r["precision"] is not None for r in rs) else None
        mb = float(np.mean([r["bps_to_turn"] for r in rs if r["bps_to_turn"] is not None])) if any(r["bps_to_turn"] is not None for r in rs) else None
        nt = float(np.sum([r["net_oos"] for r in rs]))
        ntm = float(np.sum([r["net_oos_maker"] for r in rs]))
        nw = int(np.sum([1 for r in rs if r["net_oos"] > 0])); nwm = int(np.sum([1 for r in rs if r["net_oos_maker"] > 0]))
        pooled[tag] = dict(recall=round(mr, 3), precision=round(mp, 3) if mp else None,
                           bps_to_turn=round(mb, 1) if mb else None, net_taker=round(nt), net_maker=round(ntm),
                           venues_pos_taker=nw, venues_pos_maker=nwm, n_venues=len(rs))
        print(f"   {tag:10s} recall={mr:.3f}  precision={mp if mp is None else round(mp,3)}  "
              f"bps_to_turn={mb if mb is None else round(mb,1)}  net@10taker={nt:+.0f} ({nw}/{len(rs)}+)  "
              f"net@4maker={ntm:+.0f} ({nwm}/{len(rs)}+)")
    return out, pooled


def main():
    print("=" * 98)
    print("S36 DIPOLE EVAL — reproduced on the 42h KRAKEN BOOKS (LIVE firing onsets, book buy/sell + mid)")
    print("=" * 98)
    clips, ov_sec = load_clipped()
    hours = ov_sec / 3600.0
    print(f"common book window {ov_sec}s = {hours:.1f}h across {len(clips)} coins; pre-entry win={WIN_S//60}m\n")

    # ---------- PIECE A ----------
    records = []
    for cell in CELLS:
        if not cell["active"] or cell["coin"] not in clips:
            continue
        records += build_records(cell, clips[cell["coin"]])
    cells = sorted({r["cell"] for r in records})
    print(f"Evaluable onsets (LIVE legs w/ dipole + forward exit): {len(records)} across {len(cells)} cells\n")

    # leakage proof on the divergence read
    coin0 = next(iter(clips)); c0 = clips[coin0]
    def sig_at(i, ts, p, bv, sv):
        lo = max(0, i - WIN_S)
        if i - lo < 6:
            return None
        dv = divergence(bv[lo:i + 1], sv[lo:i + 1], float(p[i] - p[lo]))
        return None if dv is None else dv["expect"]
    n0 = len(c0["mid"]); idxs = list(range(2000, min(n0, 60000), 4000))
    passed, fails = assert_no_leakage(sig_at, np.arange(n0, dtype=float), c0["mid"].astype(float),
                                      c0["buy"].astype(float), c0["sell"].astype(float), idxs)
    print(f"[leakage] divergence() strictly pre-entry on {coin0}: "
          f"{'PASS' if passed else 'FAIL'} ({len(idxs)-len(fails)}/{len(idxs)} indices invariant to post-onset data)\n")

    rt_refs = [0, 10]
    policies = [("FLOW (follow|fade)", pol_flow), ("FLOW_2F (healthy)", pol_flow_2f),
                ("FADE_GATE (reversal)", pol_fade_gate), ("FOLLOW_ALL (base)", pol_follow_all)]
    print("=" * 98); print("A. POOLED net-of-cost (dir*ret - cost), all policies, at 0bp maker & 10bp round-trip")
    print("=" * 98)
    pooled_out = {}
    for rt in rt_refs:
        print(f"  -- round-trip {rt} bps --")
        pooled_out[str(rt)] = {}
        for name, p in policies:
            s = summ(apply(records, p, rt))
            pooled_out[str(rt)][name] = s
            print("    ", fmt(name, s))

    print("\n" + "=" * 98)
    print("A. CONVICTION LADDER — reversal rate by flow-state (does opp+exh > ... > trend+str hold on book?)")
    print("=" * 98)
    lad = conviction_ladder(records)
    for k in ("opp+exh", "opp+str", "trend+weak", "trend+str"):
        d = lad[k]
        print(f"   {k:12s} reversal={str(d['reversal_rate'])+'%':>7s}  (n={d['n']})")

    print("\n" + "=" * 98)
    print("A. PER CELL — FLOW & FADE_GATE, net bps/trade at 0bp maker and [10bp]; n>=20")
    print("=" * 98)
    per_cell = {}
    for c in cells:
        recs = [r for r in records if r["cell"] == c]
        if len(recs) < 20:
            continue
        row = {}
        for pol_name, pol in (("FLOW", pol_flow), ("FADE_GATE", pol_fade_gate)):
            row[pol_name] = {str(rt): summ(apply(recs, pol, rt)) for rt in rt_refs}
        per_cell[c] = row
        f0 = row["FLOW"]["0"]; f10 = row["FLOW"]["10"]; g0 = row["FADE_GATE"]["0"]; g10 = row["FADE_GATE"]["10"]
        clr0 = " CLR@0" if f0 and f0["net_bps"] > 0 else ""
        print(f"   {c:20s} FLOW n={f0['n']:>4d} net@0={f0['net_bps']:>+7.2f} [10={f10['net_bps']:>+7.2f}] "
              f"win%={f0['win_rate']:>4.1f}  | FADE n={g0['n'] if g0 else 0:>4d} "
              f"net@0={g0['net_bps'] if g0 else float('nan'):>+7.2f}{clr0}")

    print("\n" + "=" * 98)
    print("A. WALK-FORWARD (FLOW, early/late split; net@0bp maker) — robust = BOTH halves positive")
    print("=" * 98)
    wf = {}
    for c in cells:
        cr = sorted([r for r in records if r["cell"] == c], key=lambda r: r["ts"])
        if len(cr) < 20:
            continue
        h = len(cr) // 2
        se = summ(apply(cr[:h], pol_flow, 0)); sl = summ(apply(cr[h:], pol_flow, 0))
        both = "  BOTH+" if (se and sl and se["net_bps"] > 0 and sl["net_bps"] > 0) else ""
        wf[c] = {"early": se, "late": sl, "both_pos": bool(both)}
        print(f"   {c:20s} early net@0={se['net_bps']:>+8.2f} (n={se['n']:>3d})   "
              f"late net@0={sl['net_bps']:>+8.2f} (n={sl['n']:>3d}){both}")

    # ---------- PIECE B ----------
    print("\n" + "=" * 98)
    print("B. SIGNED-FLOW FEATURE LIFT over base rate (feature sign vs forward 30-min return sign), per cell")
    print("=" * 98)
    per_cell_feat, cell_fwd, overall, base_rate = flow_probe(clips)
    print(f"   {'feature':12s} {'overall acc':>12s}   best per-cell LIFT (n>=40)")
    featB = {"overall": {}, "per_cell": {}}
    for f in FEATS:
        c_, n_ = overall[f]
        acc = 100 * c_ / n_ if n_ else 0.0
        featB["overall"][f] = {"acc": round(acc, 1), "n": n_}
        rows = []
        for cell, d in per_cell_feat.items():
            cc, cn = d[f]
            if cn >= 40:
                a_ = 100 * cc / cn; b_ = base_rate(cell)
                rows.append((cell, a_, b_, a_ - b_, cn))
        rows.sort(key=lambda t: -t[3])
        top = "  ".join(f"{cell.replace('_kraken','')}:{lift:+.0f}(n{cn})" for cell, _, _, lift, cn in rows[:4])
        print(f"   {f:12s} {acc:>10.1f}%    {top}")
        featB["per_cell"][f] = {cell: {"acc": round(a_, 1), "base": round(b_, 1), "lift": round(lf, 1), "n": cn}
                                for cell, a_, b_, lf, cn in rows}
    print("\n   DEPLOY CANDIDATES (best feature lift >= +5 over base, n>=40):")
    deploy_hits = {}
    for cell in sorted(per_cell_feat):
        cands = [(f, 100 * per_cell_feat[cell][f][0] / per_cell_feat[cell][f][1], base_rate(cell),
                  per_cell_feat[cell][f][1]) for f in FEATS if per_cell_feat[cell][f][1] >= 40]
        if not cands:
            continue
        best = max(cands, key=lambda t: t[1] - t[2])
        if best[1] - best[2] >= 5:
            deploy_hits[cell] = {"feature": best[0], "acc": round(best[1], 1), "base": round(best[2], 1),
                                 "lift": round(best[1] - best[2], 1), "n": best[3]}
            print(f"      {cell:20s} {best[0]:10s} acc={best[1]:.0f}% base={best[2]:.0f}% "
                  f"lift={best[1]-best[2]:+.1f} (n={best[3]})")
    if not deploy_hits:
        print("      (none clear lift>=+5 at n>=40 on this window)")

    # ---------- PIECE C ----------
    print("\n" + "=" * 98)
    print("C. FALSIFICATION HARNESS — dipole divergence() FILTER vs classical OFI champion (same 1-sec timing)")
    print(f"    frozen Kraken 1-sec book, OOS (tune {int(H.IS_FRAC*100)}% / score {int((1-H.IS_FRAC)*100)}%), "
          f"true turns = {H.SWING_THETA*1e4:.0f}bp swings, fee {H.FEE_RT}bp taker / {H.FEE_MAKER}bp maker")
    print("=" * 98)
    series = kraken_series(clips, ov_sec)
    harness_out, harness_pooled = run_harness(series)

    # ---------- persist ----------
    res = {
        "window": {"seconds": ov_sec, "hours": round(hours, 2), "coins": list(clips), "pre_win_s": WIN_S,
                   "surface": "kraken L2 book, 1-sec grid, book buy/sell + mid", "onsets": "LIVE run_kraken_cell legs"},
        "leakage_pass": bool(passed),
        "A_pooled_netcost": pooled_out,
        "A_conviction_ladder": lad,
        "A_per_cell": per_cell,
        "A_walkforward_FLOW_0bp": {c: {"early": v["early"], "late": v["late"], "both_pos": v["both_pos"]}
                                   for c, v in wf.items()},
        "B_feature_lift": featB,
        "B_deploy_candidates": deploy_hits,
        "C_harness_per_venue": harness_out,
        "C_harness_pooled": harness_pooled,
        "caveat": "ONE 42h low-edge Kraken book window = current conditions; first cut, not deploy-grade",
    }
    with open("_info_dipole_kraken_eval_results.json", "w") as f:
        json.dump(res, f, indent=2, default=lambda o: None)
    print("\nwrote _info_dipole_kraken_eval_results.json")


if __name__ == "__main__":
    main()
