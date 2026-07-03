"""_s56_armed_gate.py — S56 JOB 1: the FULL GATE on the S55 arming rule (armed_fine_zigzag).

Round 1 (--grid): widen the leg count. ARM x FINE grid on 30d x 5 Bybit bins, flat $5k taker
rt11 through the platform executor (identical mechanics to the S55 first pass), REVERSED column
per cell. Purpose: find where n is thick enough for per-week z-stats; check the S55 20/20
positivity on a finer grid. Report the grid, not the best cell (never tune off one window).

Round 2 (--gate): S54-style full gate on the grid — shuffle (permuted log-returns re-run through
the whole pipeline; flow irrelevant under fill_mode="taker") + per-week splits + z-stats.

Usage:
  python scripts/_s56_armed_gate.py --grid
  python scripts/_s56_armed_gate.py --gate
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS            # noqa: E402
from _s55_armed_zigzag_probe import armed_fine_zigzag        # noqa: E402
from odcore.swing_maker import simulate_swing_maker          # noqa: E402

RT = 11.0
CAP = 5000.0
ARMS = (40.0, 50.0, 60.0, 75.0, 100.0, 125.0, 150.0)
FINES = (15.0, 25.0, 35.0)
N_SHUF = 5
WEEK_S = 7 * 24 * 3600
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_s56_armed_gate_results.json")


def armed_fine_zigzag_v2(mid, arm_bp, fine_bp):
    """S56 round 2 — v2 arming: extremes anchored SINCE THE LAST FLIP, symmetric watch.

    v1's measured flaw (S56 round 1 instrumentation): arm referenced to the last PIVOT PRICE +
    one-sided watch -> 98% of tape stranded in a stale leg (max 289h), max adverse ride 1905bp,
    3.9 legs/day vs oracle 28-60 at the same scale. v2:
      - peak flip ARMS when running-high >= running-low*(1+ARM) (the up-leg extended ARM from its
        actual start); first fine_bp dip off the high CONFIRMS (cheap, at the turn);
      - TRAILING FALLBACK (the symmetric watch): holding a position, price moving ARM against the
        running favorable extreme without ever arming flips at that extreme anyway — plain
        zigzag theta=ARM behavior; bounds the loss at ~ARM by construction.
    Net: the theta=ARM zigzag, accelerated by fine confirms wherever legs extend (Greg's
    "zigzag scaled up, firing slower, merged trends")."""
    a, f = arm_bp / 1e4, fine_bp / 1e4
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    mode = 0
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0:
            armed = mid[hi_i] >= mid[lo_i] * (1 + a)
            if armed and m <= mid[hi_i] * (1 - f):          # fine confirm at the peak
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
            if mode == 1 and m <= mid[hi_i] * (1 - a):      # trailing fallback (bounded loss)
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
        if mode <= 0:
            armed = mid[lo_i] <= mid[hi_i] * (1 - a)
            if armed and m >= mid[lo_i] * (1 + f):          # fine confirm at the valley
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                continue
            if mode == -1 and m >= mid[lo_i] * (1 + a):     # trailing fallback
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
    return flips


def armed_fine_zigzag_v2_gated(mid, buy, sell, arm_bp, fine_bp, divw=600, mode_gate="reversal"):
    """Round 3 (JOB 1b): v2 with the R4 dipole VETO on fine confirms.

    A fine 25bp dip only confirms the flip when the causal S36 divergence() read at the pivot
    candidate (window [pivot-divw, pivot], flow vs drift) says expect=="reversal" — the only
    positive descriptor class at zz150 (S55 R4: +30.2/leg, 4/5 coins). Vetoed dip -> keep
    riding; a NEW extreme re-tests; the trailing ARM fallback still bounds loss (never vetoed).
    mode_gate: "reversal" (class veto) or "opposing" (weaker: any flow-opposes-price read).
    """
    from odcore.info_dipole import divergence
    a, f = arm_bp / 1e4, fine_bp / 1e4
    n = len(mid)
    cb = np.concatenate([[0.0], np.cumsum(buy)])
    cs = np.concatenate([[0.0], np.cumsum(sell)])
    cache = {}

    def gate_ok(pi):
        if pi in cache:
            return cache[pi]
        lo = max(0, pi - divw)
        dv = None
        if pi - lo >= 12:
            dv = divergence(buy[lo:pi + 1], sell[lo:pi + 1], float(mid[pi] - mid[lo]))
        if mode_gate == "reversal":        # tight: require the R4 positive class
            ok = bool(dv) and dv["expect"] == "reversal"
        elif mode_gate == "opposing":      # medium: any flow-opposes-price read
            ok = bool(dv) and bool(dv["opposing"])
        else:                              # "not_continue" loose: veto only the known-worst
            ok = (dv is None) or dv["expect"] != "continue"
        cache[pi] = ok
        return ok

    flips = []
    lo_i = hi_i = 0
    mode = 0
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0:
            armed = mid[hi_i] >= mid[lo_i] * (1 + a)
            if armed and m <= mid[hi_i] * (1 - f) and gate_ok(hi_i):
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
            if mode == 1 and m <= mid[hi_i] * (1 - a):      # fallback: never vetoed
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
        if mode <= 0:
            armed = mid[lo_i] <= mid[hi_i] * (1 - a)
            if armed and m >= mid[lo_i] * (1 + f) and gate_ok(lo_i):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                continue
            if mode == -1 and m >= mid[lo_i] * (1 + a):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
    return flips


def armed_zigzag_flips(mid, buy, sell, arm_bp, lean_w=60, rev=0.1):
    """S56 v3 (Greg: "use the enter and exit strategy from zig zag"): the DEPLOYED fine flip
    detector (odcore.flip_detector lean retrace — the validated enter/exit on all 5 live cells)
    does ALL entries/exits; the coarse ARM extension only selects WHICH fine flips to act on
    (the chop filter — S54 close: "scale it up and eliminate the chop in between").

    Machine: running extremes since the last TAKEN flip; when the leg has extended >= ARM in a
    direction, the next fine flip AGAINST that direction (the flow-death turn call) is taken as
    the confirm; extremes reset. Alternation enforced; no price-dip confirm; no trading fallback
    (once an adverse move reaches ARM it arms the opposite side and the next agreeing fine flip
    takes it — bounded without ever trading at the trough)."""
    from odcore.flip_detector import lean_series, detect_flips
    a = arm_bp / 1e4
    if isinstance(buy, list) and buy and isinstance(buy[0], tuple):
        fine = buy                                   # precomputed fine flips (grid efficiency)
    else:
        lean = lean_series(np.asarray(buy, float), np.asarray(sell, float), lean_w)
        fine, _ = detect_flips(lean, rev)
        fine = [(int(c), int(p), int(s)) for (c, p, s) in fine]
    n = len(mid)
    out = []
    lo_i = hi_i = 0
    last_side = 0
    fi = 0
    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        while fi < len(fine) and fine[fi][0] == t:
            c, p, s = fine[fi]
            fi += 1
            if s == last_side:
                continue
            if s < 0 and last_side <= 0 and last_side != 0:
                continue  # alternation: only opposite side (redundant guard)
            if s < 0:     # fine says PEAK: need the up-leg extended >= ARM
                if mid[hi_i] >= mid[lo_i] * (1 + a):
                    out.append((c, p, s)); last_side = s; lo_i = hi_i = t
            else:         # fine says VALLEY: need the down-leg extended >= ARM
                if mid[lo_i] <= mid[hi_i] * (1 - a):
                    out.append((c, p, s)); last_side = s; lo_i = hi_i = t
    return out


# fee tiers (Greg S56): score every run at the 10%-taker blend — each side pays
# 0.9*maker + 0.1*taker. Executor runs at taker rt11; tiers are linear per-leg arithmetic.
TIERS = {
    "taker11": 11.0,                                # no-MM floor (reference)
    "std_bl": 2 * (0.9 * 2.0 + 0.1 * 5.5),          # Bybit standard maker +2  -> rt 4.70
    "mm3_bl": 2 * (0.9 * -1.25 + 0.1 * 5.5),        # Bybit MM3 -1.25          -> rt -1.15
}


def tier_row(res, hrs):
    """gross/leg + net/leg + $/hr per fee tier from one taker-rt11 executor run."""
    gross = res.net_per_leg_bps + RT
    out = dict(n=int(res.n_legs), gross_leg=float(gross))
    for name, rt in TIERS.items():
        nl = gross - rt
        out[name] = dict(net_leg=float(nl),
                         dhr=float(nl * res.n_legs * CAP / 1e4 / hrs))
    return out


def run_armed(mid, buy, sell, arm, fine, reverse=False, fn=armed_fine_zigzag):
    """Flips + platform executor at S55 first-pass mechanics (flat taker rt11)."""
    fl = fn(mid, arm, fine)
    if reverse:
        fl = [(c, p, -s) for (c, p, s) in fl]
    z = np.zeros(len(mid))
    res = simulate_swing_maker(mid, z, z, buy, sell, fl, half_spread_bps=0.0,
                               maker_fee_bps=5.5, taker_fee_bps=5.5, fill_mode="taker")
    return res


def load_all():
    data = {}
    for (coin, sym) in COINS:
        p = f"/tmp/backfill/{sym}_30d_bins.json"
        if not os.path.exists(p):
            print(f"[{coin}] MISSING bins at {p}")
            continue
        mid, buy, sell, cov, hrs = load_bins(p)
        data[coin] = (np.asarray(mid, float), np.asarray(buy, float),
                      np.asarray(sell, float), hrs)
        print(f"[{coin}] {len(mid)} s ({hrs:.1f}h) coverage {cov:.3f}")
    return data


def grid(data, fn=armed_fine_zigzag, key="grid"):
    print(f"\nGRID [{key}] — 30d x 5, flat $5k taker rt11, platform executor")
    print("per cell: n legs | net/leg bp | $/hr  (REV = reversed $/hr)")
    rows = {}
    for fine in FINES:
        print(f"\n== FINE {fine:.0f}bp ==")
        hdr = f"{'ARM':>5} | " + "".join(f"{c:>26}" for c in data) + f" | {'TOT$/h':>8}{'REV$/h':>8}"
        print(hdr)
        for arm in ARMS:
            row = f"{arm:>5.0f} | "
            tot = rtot = 0.0
            cells = {}
            for coin, (mid, buy, sell, hrs) in data.items():
                res = run_armed(mid, buy, sell, arm, fine, fn=fn)
                rres = run_armed(mid, buy, sell, arm, fine, reverse=True, fn=fn)
                dhr = res.total_net_bps * CAP / 1e4 / hrs
                rdhr = rres.total_net_bps * CAP / 1e4 / hrs
                tot += dhr; rtot += rdhr
                row += f"{res.n_legs:>6}n {res.net_per_leg_bps:>+7.1f} {dhr:>+8.2f}"
                cells[coin] = dict(n=int(res.n_legs), net_leg=float(res.net_per_leg_bps),
                                   dhr=float(dhr), dhr_rev=float(rdhr),
                                   legs_day=float(res.n_legs / hrs * 24.0))
            print(row + f" | {tot:>+8.2f}{rtot:>+8.2f}")
            rows[f"a{arm:.0f}_f{fine:.0f}"] = cells
    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            prev = json.load(f)
    prev[key] = rows
    with open(OUT, "w") as f:
        json.dump(prev, f, indent=1)
    print(f"\nsaved -> {OUT}")


def grid_gated(data, fines=(25.0,), key="grid_v3", mode_gate="reversal"):
    """Round 3: dipole-vetoed v2 grid. NO-GATES judging — print gated cells with gross/leg +
    all fee tiers; v2-ungated comparison read from the saved JSON."""
    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            prev = json.load(f)
    v2 = prev.get("grid_v2", {})
    rows = {}
    for fine in fines:
        print(f"\n== ROUND 3 GATED (dipole veto: {mode_gate}) — FINE {fine:.0f}bp ==")
        print(f"{'ARM':>5} | per coin: n gross $/hr@mm3 | totals: taker/std/mm3 (v2 ungated mm3)")
        for arm in ARMS:
            row = f"{arm:>5.0f} | "
            tots = {k: 0.0 for k in TIERS}
            rtot_mm3 = 0.0
            cells = {}
            for coin, (mid, buy, sell, hrs) in data.items():
                fl = armed_fine_zigzag_v2_gated(mid, buy, sell, arm, fine,
                                                mode_gate=mode_gate)
                z = np.zeros(len(mid))
                res = simulate_swing_maker(mid, z, z, buy, sell, fl, half_spread_bps=0.0,
                                           maker_fee_bps=5.5, taker_fee_bps=5.5,
                                           fill_mode="taker")
                rfl = [(c, p, -s) for (c, p, s) in fl]
                rres = simulate_swing_maker(mid, z, z, buy, sell, rfl, half_spread_bps=0.0,
                                            maker_fee_bps=5.5, taker_fee_bps=5.5,
                                            fill_mode="taker")
                tr = tier_row(res, hrs)
                rtr = tier_row(rres, hrs)
                for k in TIERS:
                    tots[k] += tr[k]["dhr"]
                rtot_mm3 += rtr["mm3_bl"]["dhr"]
                row += f"{tr['n']:>6}n {tr['gross_leg']:>+6.1f} {tr['mm3_bl']['dhr']:>+7.2f}"
                cells[coin] = dict(tr, rev_mm3_dhr=rtr["mm3_bl"]["dhr"],
                                   legs_day=float(tr["n"] / hrs * 24.0))
            v2tot = ""
            k2 = f"a{arm:.0f}_f{fine:.0f}"
            if k2 in v2:
                v2mm3 = sum((c["net_leg"] + RT - TIERS["mm3_bl"]) * c["n"] * CAP / 1e4 / 720.0
                            for c in v2[k2].values())
                v2tot = f" (v2 {v2mm3:+.2f})"
            print(row + f" | {tots['taker11']:>+8.2f}/{tots['std_bl']:>+8.2f}/"
                        f"{tots['mm3_bl']:>+8.2f} rev_mm3 {rtot_mm3:+.2f}{v2tot}")
            rows[k2] = cells
    prev[key] = rows
    with open(OUT, "w") as f:
        json.dump(prev, f, indent=1)
    print(f"\nsaved -> {OUT}")


def grid_v3z(data, key="grid_v3z"):
    """v3 grid: deployed-flip-detector confirms, ARM chop filter. gross + all fee tiers."""
    from odcore.flip_detector import lean_series, detect_flips
    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            prev = json.load(f)
    rows = {}
    print("\nV3 GRID — armed zigzag-flip confirm (deployed detector), tiers per Greg blend")
    print(f"{'ARM':>5} | per coin: n gross $/hr@mm3 | totals taker/std/mm3  rev_mm3")
    fine_by_coin = {}
    for coin, (mid, buy, sell, hrs) in data.items():
        lean = lean_series(buy, sell, 60)
        ff, _ = detect_flips(lean, 0.1)
        fine_by_coin[coin] = [(int(c), int(p), int(s)) for (c, p, s) in ff]
    for arm in (0.0,) + ARMS:
        row = f"{arm:>5.0f} | "
        tots = {k: 0.0 for k in TIERS}
        rtot = 0.0
        cells = {}
        for coin, (mid, buy, sell, hrs) in data.items():
            fl = armed_zigzag_flips(mid, fine_by_coin[coin], None, arm)
            z = np.zeros(len(mid))
            res = simulate_swing_maker(mid, z, z, buy, sell, fl, half_spread_bps=0.0,
                                       maker_fee_bps=5.5, taker_fee_bps=5.5, fill_mode="taker")
            rfl = [(c, p, -s) for (c, p, s) in fl]
            rres = simulate_swing_maker(mid, z, z, buy, sell, rfl, half_spread_bps=0.0,
                                        maker_fee_bps=5.5, taker_fee_bps=5.5, fill_mode="taker")
            tr = tier_row(res, hrs)
            rtr = tier_row(rres, hrs)
            for k in TIERS:
                tots[k] += tr[k]["dhr"]
            rtot += rtr["mm3_bl"]["dhr"]
            row += f"{tr['n']:>6}n {tr['gross_leg']:>+6.2f} {tr['mm3_bl']['dhr']:>+7.2f}"
            cells[coin] = dict(tr, rev_mm3_dhr=rtr["mm3_bl"]["dhr"],
                               legs_day=float(tr["n"] / hrs * 24.0))
        print(row + f" | {tots['taker11']:>+9.2f}/{tots['std_bl']:>+8.2f}/"
                    f"{tots['mm3_bl']:>+8.2f}  rev {rtot:+.2f}")
        rows[f"a{arm:.0f}"] = cells
    prev[key] = rows
    with open(OUT, "w") as f:
        json.dump(prev, f, indent=1)
    print(f"\nsaved -> {OUT}")


def shuffle_mid(mid, seed):
    rng = np.random.default_rng(2000 + seed)
    r = np.diff(np.log(mid))
    return float(mid[0]) * np.exp(np.concatenate([[0.0], np.cumsum(rng.permutation(r))]))


def shuffle_joint(mid, buy, sell, seed):
    """Joint price+flow shuffle: one permutation on (return, buy, sell) rows — kills temporal
    structure, preserves marginals AND the contemporaneous price-flow link (v3's confirm is
    flow-based, so flow must shuffle WITH price)."""
    rng = np.random.default_rng(2000 + seed)
    r = np.diff(np.log(mid))
    perm = rng.permutation(len(r))
    m2 = float(mid[0]) * np.exp(np.concatenate([[0.0], np.cumsum(r[perm])]))
    b2 = np.concatenate([[buy[0]], buy[1:][perm]])
    s2 = np.concatenate([[sell[0]], sell[1:][perm]])
    return m2, b2, s2


def gate_v3z(data, arms=(40.0, 50.0, 60.0), key="gate_v3z"):
    """S54-style full gate on the v3 machine: joint shuffle x N_SHUF + per-week + z, per cell.
    Scored at the Greg blend (mm3) with taker as reference."""
    from odcore.flip_detector import lean_series, detect_flips

    def run(mid, buy, sell, arm, rev_=False):
        lean = lean_series(buy, sell, 60)
        ff, _ = detect_flips(lean, 0.1)
        ff = [(int(c), int(p), int(s)) for (c, p, s) in ff]
        fl = armed_zigzag_flips(mid, ff, None, arm)
        if rev_:
            fl = [(c, p, -s) for (c, p, s) in fl]
        z = np.zeros(len(mid))
        return simulate_swing_maker(mid, z, z, buy, sell, fl, half_spread_bps=0.0,
                                    maker_fee_bps=5.5, taker_fee_bps=5.5, fill_mode="taker")

    res_all = {}
    for arm in arms:
        print(f"\n== V3 GATE ARM {arm:.0f} (mm3 blend $/hr) ==")
        print(f"{'coin':>6} {'n':>6} {'fwd':>8} {'rev':>8} {'shuf_mu':>8} {'shuf_sd':>7} "
              f"{'z':>6}  weeks")
        for coin, (mid, buy, sell, hrs) in data.items():
            def mm3(r, h):
                return (r.net_per_leg_bps + RT - TIERS["mm3_bl"]) * r.n_legs * CAP / 1e4 / h
            r = run(mid, buy, sell, arm)
            dv = mm3(r, hrs)
            rv = mm3(run(mid, buy, sell, arm, rev_=True), hrs)
            svals = []
            for sd in range(N_SHUF):
                m2, b2, s2 = shuffle_joint(mid, buy, sell, sd)
                svals.append(mm3(run(m2, b2, s2, arm), hrs))
            smu, ssd = float(np.mean(svals)), float(np.std(svals))
            zz = (dv - smu) / ssd if ssd > 1e-9 else float("nan")
            wk = []
            nW = max(1, int(len(mid) // WEEK_S))
            for w in range(nW):
                sl = slice(w * WEEK_S, min(len(mid), (w + 1) * WEEK_S))
                if sl.stop - sl.start < 12 * 3600:
                    continue
                h_w = (sl.stop - sl.start) / 3600.0
                wk.append(float(mm3(run(mid[sl], buy[sl], sell[sl], arm), h_w)))
            print(f"{coin:>6} {r.n_legs:>6} {dv:>+8.2f} {rv:>+8.2f} {smu:>+8.2f} {ssd:>7.2f} "
                  f"{zz:>6.2f}  " + " ".join(f"{v:+.2f}" for v in wk))
            res_all[f"{coin}_a{arm:.0f}"] = dict(n=int(r.n_legs), dhr_mm3=float(dv),
                                                 rev_mm3=float(rv), shuf_mu=smu, shuf_sd=ssd,
                                                 z=float(zz), weeks=wk)
    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            prev = json.load(f)
    prev[key] = res_all
    with open(OUT, "w") as f:
        json.dump(prev, f, indent=1)
    print(f"\nsaved -> {OUT}")


def gate(data, arms, fines):
    """Round 2: shuffle + per-week + z per cell on the (given) grid subset."""
    print("\nROUND 2 GATE — shuffle x%d + per-week splits + z" % N_SHUF)
    res_all = {}
    for fine in fines:
        for arm in arms:
            print(f"\n== ARM {arm:.0f} / FINE {fine:.0f} ==")
            print(f"{'coin':>6} {'n':>5} {'$/hr':>8} {'rev':>8} {'shuf_mu':>8} {'shuf_sd':>7} "
                  f"{'z':>6}  weeks $/hr")
            for coin, (mid, buy, sell, hrs) in data.items():
                res = run_armed(mid, buy, sell, arm, fine)
                dhr = res.total_net_bps * CAP / 1e4 / hrs
                rres = run_armed(mid, buy, sell, arm, fine, reverse=True)
                rdhr = rres.total_net_bps * CAP / 1e4 / hrs
                svals = []
                for s in range(N_SHUF):
                    m2 = shuffle_mid(mid, s)
                    sres = run_armed(m2, buy, sell, arm, fine)
                    svals.append(sres.total_net_bps * CAP / 1e4 / hrs)
                smu, ssd = float(np.mean(svals)), float(np.std(svals))
                zz = (dhr - smu) / ssd if ssd > 1e-9 else float("nan")
                wk = []
                nW = max(1, int(len(mid) // WEEK_S))
                for w in range(nW):
                    sl = slice(w * WEEK_S, min(len(mid), (w + 1) * WEEK_S))
                    m_w = mid[sl]
                    if len(m_w) < 12 * 3600:
                        continue
                    h_w = len(m_w) / 3600.0
                    wres = run_armed(m_w, buy[sl], sell[sl], arm, fine)
                    wk.append(float(wres.total_net_bps * CAP / 1e4 / h_w))
                print(f"{coin:>6} {res.n_legs:>5} {dhr:>+8.2f} {rdhr:>+8.2f} {smu:>+8.2f} "
                      f"{ssd:>7.2f} {zz:>6.2f}  " + " ".join(f"{v:+.2f}" for v in wk))
                res_all[f"{coin}_a{arm:.0f}_f{fine:.0f}"] = dict(
                    n=int(res.n_legs), dhr=float(dhr), dhr_rev=float(rdhr),
                    shuf_mu=smu, shuf_sd=ssd, z=float(zz), weeks=wk)
    key = "gate"
    prev = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            prev = json.load(f)
    prev[key] = res_all
    with open(OUT, "w") as f:
        json.dump(prev, f, indent=1)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    d = load_all()
    if "--gate" in sys.argv:
        import argparse
        pa = argparse.ArgumentParser()
        pa.add_argument("--gate", action="store_true")
        pa.add_argument("--arms", default="50,75,100,150")
        pa.add_argument("--fines", default="25")
        a = pa.parse_args()
        gate(d, [float(x) for x in a.arms.split(",")],
             [float(x) for x in a.fines.split(",")])
    elif "--v2" in sys.argv:
        grid(d, fn=armed_fine_zigzag_v2, key="grid_v2")
    elif "--gate-arm0" in sys.argv:
        gate_v3z(d, arms=(0.0,), key="gate_v3z_arm0")
    elif "--gate-v3z" in sys.argv:
        gate_v3z(d)
    elif "--v3z" in sys.argv:
        grid_v3z(d)
    elif "--v3" in sys.argv:
        for mg in ("reversal", "not_continue"):
            grid_gated(d, fines=(25.0,) if "--all-fines" not in sys.argv else FINES,
                       key=f"grid_v3_{mg}", mode_gate=mg)
    else:
        grid(d)
