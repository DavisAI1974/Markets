#!/usr/bin/env python3
"""
condition_rate_experiment.py - DERIVE the condition-health thresholds instead of asserting them.
(S111, on Greg's "i'm going to let you make the decision on that and we might just have to test
different things". Testing is the right instinct: the numbers below are measured, not chosen.)

Q0 CAME FIRST AND IT IS THE BIGGEST ONE (found by the canary, not planned).
  Before asking what BAR to put on a quantity, ask whether the quantity VARIES AT ALL inside the
  ten-day block a specialist is standing in. Six of the first six quantities tested were
  BLOCK-CONSTANT - one value for the whole block - so every possible bar on them fires 10/10 or
  0/10 and no bar can ever be fixed. A weekly storage print, a Friday COT report and a monthly
  STEO vintage cannot vary within a Sunday-to-second-Friday window; they are BLOCK CONTEXT, not
  day-level signal. A play keyed to one of them is a block-lean play however its bar is written,
  and no reformulation of the bar can change that.
  THE MATHEMATICAL CONSEQUENCE, which is why this is not merely a nuisance: for a block-degenerate
  condition the WITHIN-BLOCK permutation null has EXACTLY ZERO VARIANCE - shuffling outcomes
  inside a block cannot move a split that never happens inside a block. So its apparent
  separation is 100% block lean, by construction rather than by measurement. Those cells are
  counted and reported separately, never averaged into the information tables.

THREE FURTHER QUESTIONS, ONE RIG
  Q1  Does a condition's FIRE RATE predict how much information it carries?
      (D28 measured that degenerate conditions cannot discriminate. That is necessary, not
      sufficient: a condition that splits 50/50 at random also carries nothing. This asks
      whether the rate band we would gate on is worth gating on.)
  Q2  What REFERENCE WINDOW should a relative condition measure against? Four variants are run
      on the identical quantities and scored identically:
        FIXED    a fixed absolute bar at a percentile of the WHOLE corpus, frozen once
                 (what the brain does today - the transfer-fragile form)
        POOLED   the bar recomputed as a percentile of the whole corpus (uses the future -
                 NOT blind-legal, carried only as a diagnostic ceiling)
        TRAIL    the bar = percentile of that quantity's own PRIOR W sessions, strictly before
                 the decision day (blind-legal; the form I recommended to Greg)
        BLOCK    the bar = percentile within the day's own block (uses the block's future -
                 NOT blind-legal, carried as a second ceiling)
      TRAIL vs FIXED is the real decision. POOLED and BLOCK are ceilings that say how much is
      available at all, and they are labelled ILLEGAL in the output so no one banks them.
  Q3  Does separation peak near the CENTRE of the distribution, as D28's central-vs-extreme
      reading predicts?

DISCIPLINE (this is the part that matters)
  - The unit of analysis is the POPULATION of (quantity, percentile, variant) cells, binned.
    We never name a best bar. Sweeping ~50 quantities x 9 percentiles x 4 variants is ~1,800
    tests; the maximum of 1,800 noisy statistics is noise by construction, and reporting it
    would be the tent-widening this program forbids.
  - Every statistic is scored against a WITHIN-BLOCK PERMUTATION NULL (outcomes shuffled inside
    each block, so block-level lean - the walk's dominant structure - is preserved and cannot
    manufacture the effect). z is against that null, never against a normal assumption.
  - LEAVE-ONE-BLOCK-OUT: the relationship is measured on 6 blocks and checked on the 7th, every
    way round. An in-sample-only result is reported as in-sample-only.
  - Alignment is leak-free by construction: the state block for day X carries the PRIOR
    session's tape (`tape_conditions.asof_prior_session`) and is scored against day X's own
    realized `day_move_usd`. Same alignment a specialist runs under (D3).
  - n is small (70 outcome days, 7 blocks). Power is reported, not hidden. Where the honest
    answer is "cannot tell from this corpus", the tool says so.

REPORT-ONLY. Writes nothing but its own report/JSON. Exits 0.
"""

import argparse
import json
import os
import random
import re
import sys
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "renders", "ng_refine_s95")

# every staged block, oldest first - the early ones carry no actuals but DO serve as trailing
# history for the blind-legal TRAIL variant (past data only).
ALL_GROUPS = ["grp6", "grp7", "grp8", "grp9", "grp10", "grp11", "grp12", "grp13", "grp14",
              "grp15", "grp16", "grp17", "grp18", "grp19", "grp20", "grp21", "grp22", "grp23"]

PCTS = [10, 20, 30, 40, 50, 60, 70, 80, 90]
VARIANTS = ["FIXED", "POOLED", "TRAIL", "BLOCK"]
ILLEGAL = {"POOLED", "BLOCK"}          # use data from at or after the decision day
TRAIL_W = 30                            # sessions of trailing history for the TRAIL variant
MIN_TRAIL = 15                          # below this the trailing bar is not defined
MIN_COVER = 40                          # a quantity needs this many scored days to enter
MIN_SIDE = 8                            # each side of a split needs this many days to be scored
NPERM = 2000
SEED = 20260804                         # fixed: Math.random-style nondeterminism has no place here


# ----------------------------------------------------------------------------- data loading
def walk_scalars(o, prefix, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k.startswith("_") or k in ("note",):
                continue
            walk_scalars(v, (prefix + "." + k) if prefix else k, acc)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                acc["%s[%d]" % (prefix, i)] = float(v)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        acc[prefix] = float(o)


def load():
    """-> days[(gid, ymd)] = {quantity: value}, outcomes[(gid, ymd)] = day_move_usd"""
    days, outcomes = OrderedDict(), {}
    for g in ALL_GROUPS:
        f = os.path.join(STATE_DIR, g + "_state.json")
        if not os.path.exists(f):
            continue
        try:
            s = json.load(open(f))
        except Exception as e:
            print("  WARN unreadable %s: %s" % (g, e))
            continue
        for d in sorted(k for k in s if k.isdigit() and isinstance(s[k], dict)):
            acc = {}
            walk_scalars(s[d], "", acc)
            days[(g, d)] = acc
        af = os.path.join(STATE_DIR, g.replace("grp", "g") + "_actual.json")
        if os.path.exists(af):
            a = json.load(open(af))
            for rec in a.get("days", []):
                mv = rec.get("day_move_usd")
                if mv is not None:
                    outcomes[(g, str(rec["date"]))] = float(mv)
    return days, outcomes


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    i = (len(sorted_vals) - 1) * (p / 100.0)
    lo, hi = int(i), min(int(i) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def median(v):
    if not v:
        return None
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


# ----------------------------------------------------------------------------- statistics
def stats(fired, notf):
    """directional separation and magnitude ratio for one split."""
    if len(fired) < MIN_SIDE or len(notf) < MIN_SIDE:
        return None
    up_f = sum(1 for m in fired if m > 0) / float(len(fired))
    up_n = sum(1 for m in notf if m > 0) / float(len(notf))
    mf, mn = median([abs(m) for m in fired]), median([abs(m) for m in notf])
    return dict(dir_sep=up_f - up_n,
                mag_ratio=(mf / mn) if mn else None,
                n_fired=len(fired), n_not=len(notf),
                up_fired=up_f, up_not=up_n)


def perm_null(keys, mask, outcomes, blocks, stat_key, rng):
    """within-block shuffle of outcomes; preserves block lean, breaks the condition link."""
    by_blk = defaultdict(list)
    for i, k in enumerate(keys):
        by_blk[blocks[i]].append(i)
    draws = []
    vals = [outcomes[k] for k in keys]
    for _ in range(NPERM):
        shuf = list(vals)
        for idxs in by_blk.values():
            pool = [vals[i] for i in idxs]
            rng.shuffle(pool)
            for i, v in zip(idxs, pool):
                shuf[i] = v
        f = [shuf[i] for i in range(len(keys)) if mask[i]]
        n = [shuf[i] for i in range(len(keys)) if not mask[i]]
        st = stats(f, n)
        if st and st[stat_key] is not None:
            draws.append(st[stat_key])
    return draws


def spearman(xs, ys):
    """rank correlation; ties averaged. Returns None below n=8."""
    n = len(xs)
    if n < 8:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return (num / (dx * dy)) if dx > 1e-12 and dy > 1e-12 else None


def recompute_dropping(c, outcomes, drop_block):
    """cell statistics with one block held out - the LOBO unit."""
    f, n = [], []
    for i, k in enumerate(c["keys"]):
        if c["blks"][i] == drop_block:
            continue
        (f if c["mask"][i] else n).append(outcomes[k])
    return stats(f, n)


def z_against(obs, draws):
    if len(draws) < 50 or obs is None:
        return None, None
    m = sum(draws) / len(draws)
    var = sum((d - m) ** 2 for d in draws) / (len(draws) - 1)
    sd = var ** 0.5
    z = (obs - m) / sd if sd > 1e-12 else None
    # two-sided empirical p on |deviation|
    p = sum(1 for d in draws if abs(d - m) >= abs(obs - m)) / float(len(draws))
    return z, p


# ----------------------------------------------------------------------------- the sweep
def build_bar(variant, q, gid, ymd, hist_vals, corpus_sorted, block_sorted, p):
    if variant in ("FIXED", "POOLED"):
        return pct(corpus_sorted, p)
    if variant == "BLOCK":
        return pct(block_sorted, p)
    if variant == "TRAIL":
        if len(hist_vals) < MIN_TRAIL:
            return None
        return pct(sorted(hist_vals[-TRAIL_W:]), p)
    return None


def run(args):
    rng = random.Random(SEED)
    days, outcomes = load()
    scored = [k for k in days if k in outcomes]
    blocks_present = sorted({g for g, _ in scored})
    print("=" * 88)
    print("CONDITION RATE EXPERIMENT - deriving the thresholds (report-only)")
    print("state day-blocks %d | scored days %d | blocks with outcomes %d %s"
          % (len(days), len(scored), len(blocks_present),
             [b.replace("grp", "g") for b in blocks_present]))
    print("perm null %d draws, within-block | seed %d | trailing window %d sessions"
          % (NPERM, SEED, TRAIL_W))
    print("=" * 88)

    # quantities with enough scored coverage
    cover = defaultdict(int)
    for k in scored:
        for q in days[k]:
            cover[q] += 1
    quants = sorted(q for q, c in cover.items() if c >= MIN_COVER)
    print("quantities with coverage >= %d scored days: %d" % (MIN_COVER, len(quants)))

    # ------------------------------------------------------------------ Q0 quantity triage
    triage, day_varying = {}, []
    for q in quants:
        nb = vb = 0
        for g in blocks_present:
            vals = [days[k][q] for k in scored if k[0] == g and q in days[k]]
            if len(vals) < 5:
                continue
            nb += 1
            if len(set(vals)) > 1:
                vb += 1
        share = (vb / float(nb)) if nb else 0.0
        cls = ("BLOCK_CONSTANT" if vb == 0 else
               "PARTLY_VARYING" if share < 0.75 else "DAY_VARYING")
        triage[q] = dict(varies_in=vb, blocks=nb, share=share, cls=cls)
        if vb > 0:
            day_varying.append(q)

    tc = defaultdict(list)
    for q, t in triage.items():
        tc[t["cls"]].append(q)
    print("\n" + "-" * 88)
    print("Q0  CAN THE SERVED QUANTITY VARY INSIDE A BLOCK AT ALL?  (before any bar is chosen)")
    print("-" * 88)
    for cls in ("BLOCK_CONSTANT", "PARTLY_VARYING", "DAY_VARYING"):
        n = len(tc[cls])
        print("  %-16s %3d of %3d quantities  (%4.1f%%)"
              % (cls, n, len(quants), 100.0 * n / max(1, len(quants))))
    if tc["BLOCK_CONSTANT"]:
        print("\n  BLOCK_CONSTANT means one value for the whole ten-day block: every bar on it")
        print("  fires 10/10 or 0/10 and NO reformulation of the bar can fix that. Examples:")
        for q in sorted(tc["BLOCK_CONSTANT"])[:10]:
            print("     %s" % q)
        if len(tc["BLOCK_CONSTANT"]) > 10:
            print("     ... and %d more" % (len(tc["BLOCK_CONSTANT"]) - 10))
    print("\n  the sweep below runs ONLY on the %d quantities that vary within at least one block"
          % len(day_varying))

    quants = day_varying
    if args.limit:
        quants = quants[:args.limit]
    print("  quantities under test: %d\n" % len(quants))

    # chronological series per quantity across ALL states (trailing history may predate outcomes)
    chrono = sorted(days.keys(), key=lambda k: (k[1], k[0]))
    cells = []
    for q in quants:
        series = [(k, days[k][q]) for k in chrono if q in days[k]]
        corpus_sorted = sorted(v for _, v in series)
        blk_sorted = {}
        for g in blocks_present:
            vs = sorted(days[k][q] for k in days if k[0] == g and q in days[k])
            if vs:
                blk_sorted[g] = vs
        hist_at = {}
        acc = []
        for k, v in series:
            hist_at[k] = list(acc)
            acc.append(v)
        for variant in VARIANTS:
            for p in PCTS:
                keys, mask, blks = [], [], []
                for k in scored:
                    if q not in days[k]:
                        continue
                    bar = build_bar(variant, q, k[0], k[1], hist_at.get(k, []),
                                    corpus_sorted, blk_sorted.get(k[0], []), p)
                    if bar is None:
                        continue
                    keys.append(k)
                    mask.append(days[k][q] >= bar)
                    blks.append(k[0])
                if len(keys) < MIN_COVER:
                    continue
                fired = [outcomes[k] for i, k in enumerate(keys) if mask[i]]
                notf = [outcomes[k] for i, k in enumerate(keys) if not mask[i]]
                st = stats(fired, notf)
                if not st:
                    continue
                rate = len(fired) / float(len(keys))
                # degenerate-block share, the D28 measure
                degen = tot = 0
                for g in blocks_present:
                    idx = [i for i in range(len(keys)) if blks[i] == g]
                    if len(idx) < 5:
                        continue
                    tot += 1
                    h = sum(1 for i in idx if mask[i])
                    if h == 0 or h == len(idx):
                        degen += 1
                cells.append(dict(q=q, variant=variant, p=p, rate=rate,
                                  degen_share=(degen / float(tot)) if tot else None,
                                  keys=keys, mask=mask, blks=blks, **st))
    print("cells built: %d\n" % len(cells))
    if not cells:
        print("no cells - nothing to report")
        return 0

    # ---- null-score a bounded random sample (permutation is the expensive step) -------------
    samp = cells if len(cells) <= args.nperm_cells else rng.sample(cells, args.nperm_cells)
    print("permutation-scoring %d of %d cells (sampled uniformly, seed-fixed)\n"
          % (len(samp), len(cells)))
    nozero = 0
    for c in samp:
        draws = perm_null(c["keys"], c["mask"], outcomes, c["blks"], "dir_sep", rng)
        c["z"], c["p_emp"] = z_against(c["dir_sep"], draws)
        # a null with no spread means the within-block shuffle cannot move the split:
        # the condition carries ZERO within-block information, mathematically not statistically
        c["null_spread"] = (max(draws) - min(draws)) if draws else 0.0
        if c["null_spread"] <= 1e-12:
            c["no_within_block_info"] = True
            nozero += 1
    if nozero:
        print("  %d of %d permutation-scored cells have a ZERO-VARIANCE null: the within-block"
              % (nozero, len(samp)))
        print("  shuffle cannot move their split, so their apparent separation is 100%% block")
        print("  lean by construction. Excluded from every information table below.\n")
    live = [c for c in samp if not c.get("no_within_block_info")]

    # ---------------------------------------------------------------- Q3 central vs extreme
    print("-" * 88)
    print("Q3  DOES SEPARATION PEAK AT THE CENTRE?  (all cells, binned by realized fire rate)")
    print("-" * 88)
    bins = [(0.0, .15), (.15, .30), (.30, .45), (.45, .55), (.55, .70), (.70, .85), (.85, 1.01)]
    print("%-14s %6s %10s %10s %12s %10s" %
          ("fire rate", "cells", "mean|dsep|", "med|dsep|", "mean degen", "mean|z|"))
    for lo, hi in bins:
        sel = [c for c in live if lo <= c["rate"] < hi]
        if not sel:
            continue
        ds = [abs(c["dir_sep"]) for c in sel]
        dg = [c["degen_share"] for c in sel if c["degen_share"] is not None]
        zs = [abs(c["z"]) for c in sel if c.get("z") is not None]
        print("%-14s %6d %10.3f %10.3f %12.2f %10s"
              % ("%.2f-%.2f" % (lo, hi), len(sel), sum(ds) / len(ds), median(ds),
                 (sum(dg) / len(dg)) if dg else float("nan"),
                 ("%.2f" % (sum(zs) / len(zs))) if zs else "-"))

    # ---------------------------------------------------------------- Q1 rate vs information
    print("\n" + "-" * 88)
    print("Q1  DOES THE DEGENERATE-BLOCK SHARE PREDICT INFORMATION?  (binned by degen share)")
    print("-" * 88)
    print("%-14s %6s %10s %12s %10s" % ("degen share", "cells", "mean|dsep|", "mean rate", "mean|z|"))
    for lo, hi in [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]:
        sel = [c for c in live if c["degen_share"] is not None and lo <= c["degen_share"] < hi]
        if not sel:
            continue
        ds = [abs(c["dir_sep"]) for c in sel]
        zs = [abs(c["z"]) for c in sel if c.get("z") is not None]
        print("%-14s %6d %10.3f %12.2f %10s"
              % ("%.1f-%.1f" % (lo, hi), len(sel), sum(ds) / len(ds),
                 sum(c["rate"] for c in sel) / len(sel),
                 ("%.2f" % (sum(zs) / len(zs))) if zs else "-"))

    # ---------------------------------------------------------------- Q2 reference window
    print("\n" + "-" * 88)
    print("Q2  REFERENCE WINDOW - identical quantities, identical scoring")
    print("-" * 88)
    print("%-8s %-9s %6s %10s %12s %10s %10s"
          % ("variant", "legality", "cells", "mean|dsep|", "mean degen", "mean|z|", "frac|z|>2"))
    for v in VARIANTS:
        sel = [c for c in live if c["variant"] == v]
        if not sel:
            continue
        ds = [abs(c["dir_sep"]) for c in sel]
        dg = [c["degen_share"] for c in sel if c["degen_share"] is not None]
        zs = [abs(c["z"]) for c in sel if c.get("z") is not None]
        big = (sum(1 for z in zs if z > 2) / float(len(zs))) if zs else None
        print("%-8s %-9s %6d %10.3f %12.2f %10s %10s"
              % (v, "ILLEGAL" if v in ILLEGAL else "blind-ok", len(sel),
                 sum(ds) / len(ds), (sum(dg) / len(dg)) if dg else float("nan"),
                 ("%.2f" % (sum(zs) / len(zs))) if zs else "-",
                 ("%.2f" % big) if big is not None else "-"))
    print("\nNOTE: POOLED and BLOCK read data at or after the decision day. They are ceilings,")
    print("      not candidates. Only FIXED and TRAIL are implementable in the blind.")

    # ---------------------------------------------------------------- LOBO stability
    print("\n" + "-" * 88)
    print("LEAVE-ONE-BLOCK-OUT - is the relationship STABLE, or an artifact of one block?")
    print("-" * 88)
    print("Spearman rank correlation across cells, recomputed with each block held out.")
    print("A relationship we would gate on must keep its SIGN in all six.\n")
    pool = [c for c in cells if c["degen_share"] is not None]
    print("%-10s %8s %14s %16s" % ("held out", "cells", "rho(degen,|d|)", "rho(|rate-.5|,|d|)"))
    signs_a, signs_b = [], []
    for hb in [None] + blocks_present:
        xs_a, xs_b, ys = [], [], []
        for c in pool:
            st = c if hb is None else recompute_dropping(c, outcomes, hb)
            if not st or st["dir_sep"] is None:
                continue
            xs_a.append(c["degen_share"])
            xs_b.append(abs(c["rate"] - 0.5))
            ys.append(abs(st["dir_sep"]))
        ra, rb = spearman(xs_a, ys), spearman(xs_b, ys)
        if hb is not None:
            if ra is not None:
                signs_a.append(ra)
            if rb is not None:
                signs_b.append(rb)
        print("%-10s %8d %14s %16s"
              % ("ALL" if hb is None else hb.replace("grp", "g"), len(ys),
                 ("%+.3f" % ra) if ra is not None else "-",
                 ("%+.3f" % rb) if rb is not None else "-"))
    for nm, sg in (("degen-share", signs_a), ("centrality", signs_b)):
        if sg:
            pos = sum(1 for r in sg if r > 0)
            verdict = ("SIGN-STABLE" if pos in (0, len(sg)) else "SIGN FLIPS - not gateable")
            print("  %-12s sign positive in %d of %d hold-outs -> %s"
                  % (nm, pos, len(sg), verdict))

    # ---------------------------------------------------------------- expected-null control
    zs_all = [abs(c["z"]) for c in live if c.get("z") is not None]
    if zs_all:
        frac2 = sum(1 for z in zs_all if z > 2) / float(len(zs_all))
        print("\n" + "-" * 88)
        print("CONTROL - if the sweep were pure noise, |z|>2 would appear on about 5% of cells.")
        print("Observed across %d cells that carry any within-block information: %.1f%%"
              % (len(zs_all), 100 * frac2))
        print("A number near 5% means this corpus cannot separate these conditions from noise -")
        print("which is a real answer about POWER (60 scored days, 6 blocks), not a failure.")
        print("-" * 88)

    if args.json:
        out = [{k: v for k, v in c.items() if k not in ("keys", "mask", "blks")} for c in cells]
        json.dump(dict(scored_days=len(scored), blocks=blocks_present, cells=out),
                  open(args.json, "w"), indent=1)
        print("\nwrote %s" % args.json)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="cap quantities (canary runs)")
    ap.add_argument("--nperm-cells", type=int, default=140,
                    help="how many cells get the permutation null")
    ap.add_argument("--json", metavar="PATH")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
