"""_s68_drive.py — staged per-coin driver on top of _s68_tune_kraken (live path). Findings only."""
from __future__ import annotations
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import scripts._s68_tune_kraken as T

REV_COARSE = [0.08, 0.10, 0.13, 0.16, 0.20, 0.25, 0.30, 0.40]
EPS_GRID = [None, 3, 5, 10, 15, 20]
BAIL_GRID = [None, 60, 80, 100, 150]
GRACE_GRID = [200, 300, 600]
NSHIFT = 15

# current deployed configs (28d re-verify baseline). side,rev,eps,bail,grace,improve
DEPLOYED = {
    "eth": dict(side=+1, rev=0.10, eps=10, bail=100, grace=300, improve=0.5),
    "btc": dict(side=+1, rev=0.10, eps=5, bail=80, grace=300, improve=0.5),
    "sol": dict(side=+1, rev=0.10, eps=None, bail=None, grace=300, improve=0.5),
    "doge": dict(side=+1, rev=0.30, eps=None, bail=None, grace=600, improve=0.5),
    "xrp": dict(side=+1, rev=0.13, eps=None, bail=None, grace=300, improve=0.5),
    "ltc": dict(side=-1, rev=0.30, eps=None, bail=None, grace=300, improve=0.5),
    "avax": dict(side=+1, rev=0.13, eps=None, bail=None, grace=300, improve=0.5),
    "ada": dict(side=+1, rev=0.10, eps=None, bail=None, grace=300, improve=0.5),
    "sui": dict(side=-1, rev=0.30, eps=None, bail=None, grace=300, improve=0.5),
}


def tune_bk(bk, coin, deployed, log, tag):
    """Staged tune on a given bk (full or recent-clipped). Returns (best dict, best_dph, gate dict)."""
    hrs = bk["hours"]
    R = {}

    def go(side, rev, eps=None, bail=None, grace=300, improve=0.5):
        key = (side, rev, eps, bail, grace, improve)
        if key not in R:
            R[key] = T.dph(T.run_cfg(bk, side, rev, eps=eps, bail=bail, grace=grace, improve=improve), hrs)
        return R[key]

    dep_dph = go(**deployed)
    s1 = {}
    for side in (+1, -1):
        for rev in REV_COARSE:
            s1[(side, rev)] = go(side, rev)
    (bs, brev), b1 = max(s1.items(), key=lambda kv: kv[1])
    wrong = max(s1[(-bs, r)] for r in REV_COARSE)
    best = dict(side=bs, rev=brev, eps=None, bail=None, grace=300, improve=0.5)
    bdph = b1
    for eps in EPS_GRID:
        v = go(bs, brev, eps=eps)
        if v > bdph:
            bdph, best["eps"] = v, eps
    for bail in BAIL_GRID:
        v = go(bs, brev, eps=best["eps"], bail=bail)
        if v > bdph:
            bdph, best["bail"] = v, bail
    for grace in GRACE_GRID:
        v = go(bs, brev, eps=best["eps"], bail=best["bail"], grace=grace)
        if v > bdph:
            bdph, best["grace"] = v, grace
    for rev in REV_COARSE:
        v = go(bs, rev, eps=best["eps"], bail=best["bail"], grace=best["grace"])
        if v > bdph:
            bdph, best["rev"] = v, rev
    # gate
    nulld = T.shift_null(bk, best["side"], best["rev"], best["eps"], best["bail"],
                         best["grace"], best["improve"], NSHIFT)
    floor = float(nulld.mean() + 2 * nulld.std())
    wins = T.per_window(bk, best["side"], best["rev"], best["eps"], best["bail"],
                        best["grace"], best["improve"])
    frac_pos = float(np.mean(wins > 0))
    h1, h2 = T.halves(bk, best["side"], best["rev"], best["eps"], best["bail"],
                      best["grace"], best["improve"])
    seat = (bdph > 0) and (bdph > wrong) and (bdph > floor) and (frac_pos >= 0.6)
    verdict = "SEAT" if seat else ("MARGINAL" if (bdph > 0 and bdph > wrong) else "REJECT")
    gate = dict(dep_dph=dep_dph, wrong_dph=wrong, null_mean=float(nulld.mean()),
                null_floor=floor, frac_pos=frac_pos, wins=[round(float(x), 2) for x in wins],
                h1=h1, h2=h2, verdict=verdict, hours=hrs, n=bk["n"])
    log(f"[{coin}/{tag}] best {best} -> {bdph:+.3f} (dep {dep_dph:+.3f}) floor{floor:+.3f} "
        f"win%{100*frac_pos:.0f} halves[{h1:+.2f},{h2:+.2f}] {verdict}")
    return best, bdph, gate


def drive(coin, log=print, recent_days=9.0):
    bk = T.load_coin(coin)
    if bk is None:
        return dict(coin=coin, verdict="NO TAPE")
    t0 = time.time()
    d = DEPLOYED[coin]
    # full 28d
    fbest, fdph, fg = tune_bk(bk, coin, d, log, "28d")
    # recent window
    rbk = T.clip_recent(bk, recent_days)
    rbest, rdph, rg = tune_bk(rbk, coin, d, log, f"{recent_days:.0f}d")
    # cross-evaluate: how does the 28d-best config do on the recent window, and vice-versa
    f_on_recent = T.dph(T.run_cfg(rbk, fbest["side"], fbest["rev"], eps=fbest["eps"],
                                  bail=fbest["bail"], grace=fbest["grace"], improve=fbest["improve"]),
                        rbk["hours"])
    r_on_full = T.dph(T.run_cfg(bk, rbest["side"], rbest["rev"], eps=rbest["eps"],
                                bail=rbest["bail"], grace=rbest["grace"], improve=rbest["improve"]),
                      bk["hours"])
    diverge = (fbest["side"] != rbest["side"]) or (abs(fbest["rev"] - rbest["rev"]) > 1e-9) \
        or (fbest["eps"] != rbest["eps"])
    out = dict(coin=coin, deployed=d, recent_days=recent_days,
               full=dict(best=fbest, best_dph=fdph, **fg),
               recent=dict(best=rbest, best_dph=rdph, **rg),
               full_best_on_recent=f_on_recent, recent_best_on_full=r_on_full,
               diverge=bool(diverge), secs=time.time() - t0)
    log(f"[{coin}] DIVERGE={diverge}  28d-best->recent {f_on_recent:+.2f}  recent-best->28d {r_on_full:+.2f}  "
        f"({out['secs']:.0f}s)")
    return out


def _legacy_drive_body(coin, log, bk, t0, hrs):
    R = {}
    R = {}  # cache (side,rev,eps,bail,grace) -> dph

    def go(side, rev, eps=None, bail=None, grace=300, improve=0.5):
        key = (side, rev, eps, bail, grace, improve)
        if key not in R:
            R[key] = T.dph(T.run_cfg(bk, side, rev, eps=eps, bail=bail, grace=grace, improve=improve), hrs)
        return R[key]

    # ---- deployed baseline on 28d ----
    d = DEPLOYED[coin]
    dep_dph = go(**d)
    log(f"[{coin}] deployed {d} -> {dep_dph:+.3f} $/hr")

    # ---- stage 1: side x coarse rev, base stack ----
    s1 = {}
    for side in (+1, -1):
        for rev in REV_COARSE:
            s1[(side, rev)] = go(side, rev)
    (bs, brev), b1 = max(s1.items(), key=lambda kv: kv[1])
    wrong = max(s1[(-bs, r)] for r in REV_COARSE)
    log(f"[{coin}] stage1 best base: side{bs:+d} rev{brev} -> {b1:+.3f} (wrong-side best {wrong:+.3f})")

    # ---- stage 2a: eps at best side/rev ----
    best = dict(side=bs, rev=brev, eps=None, bail=None, grace=300, improve=0.5)
    bdph = b1
    for eps in EPS_GRID:
        v = go(bs, brev, eps=eps)
        if v > bdph:
            bdph, best["eps"] = v, eps
    log(f"[{coin}] stage2a eps -> eps={best['eps']} {bdph:+.3f}")
    # ---- stage 2b: bail ----
    for bail in BAIL_GRID:
        v = go(bs, brev, eps=best["eps"], bail=bail)
        if v > bdph:
            bdph, best["bail"] = v, bail
    log(f"[{coin}] stage2b bail -> bail={best['bail']} {bdph:+.3f}")
    # ---- stage 2c: grace ----
    for grace in GRACE_GRID:
        v = go(bs, brev, eps=best["eps"], bail=best["bail"], grace=grace)
        if v > bdph:
            bdph, best["grace"] = v, grace
    log(f"[{coin}] stage2c grace -> grace={best['grace']} {bdph:+.3f}")
    # ---- stage 2d: revisit rev fine around brev WITH the chosen eps/bail/grace ----
    for rev in REV_COARSE:
        v = go(bs, rev, eps=best["eps"], bail=best["bail"], grace=best["grace"])
        if v > bdph:
            bdph, best["rev"] = v, rev
    log(f"[{coin}] stage2d rev-revisit -> rev={best['rev']} {bdph:+.3f}")
    best_dph = bdph

    # ---- gate the FINAL config ----
    nulld = T.shift_null(bk, best["side"], best["rev"], best["eps"], best["bail"],
                         best["grace"], best["improve"], NSHIFT)
    floor = float(nulld.mean() + 2 * nulld.std())
    wins = T.per_window(bk, best["side"], best["rev"], best["eps"], best["bail"],
                        best["grace"], best["improve"])
    frac_pos = float(np.mean(wins > 0))
    h1, h2 = T.halves(bk, best["side"], best["rev"], best["eps"], best["bail"],
                      best["grace"], best["improve"])
    # wrong-side best (with same stack knobs at best rev) for direction premium
    wrong_dph = wrong

    # verdict
    clears_floor = best_dph > floor
    beats_wrong = best_dph > wrong_dph
    seat = (best_dph > 0) and beats_wrong and clears_floor and (frac_pos >= 0.6)
    verdict = "SEAT" if seat else ("MARGINAL" if (best_dph > 0 and beats_wrong) else "REJECT")

    out = dict(coin=coin, hours=hrs, n=bk["n"], deployed=d, dep_dph=dep_dph,
               best=best, best_dph=best_dph, wrong_dph=wrong_dph,
               null_mean=float(nulld.mean()), null_floor=floor,
               frac_pos=frac_pos, wins=[round(float(x), 2) for x in wins],
               h1=h1, h2=h2, delta=best_dph - dep_dph, verdict=verdict,
               secs=time.time() - t0)
    log(f"[{coin}] FINAL {best} -> {best_dph:+.3f} (dep {dep_dph:+.3f}, d{best_dph-dep_dph:+.3f}) "
        f"floor{floor:+.3f} win%{100*frac_pos:.0f} halves[{h1:+.2f},{h2:+.2f}] {verdict} ({out['secs']:.0f}s)")
    return out


if __name__ == "__main__":
    coins = sys.argv[1:] or ["btc", "eth"]
    results = []
    for c in coins:
        r = drive(c)
        results.append(r)
        with open(os.path.join(T.ROOT, "scripts", "_s68_results.json"), "a") as f:
            f.write(json.dumps(r, default=str) + "\n")
    print("DONE", [r["coin"] for r in results])
