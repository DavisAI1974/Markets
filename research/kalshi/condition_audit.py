#!/usr/bin/env python3
"""
condition_audit.py - can each brain condition CHANGE STATE? (report-only; never fixes anything)

WHY THIS EXISTS (S111, D23).
We have always audited forecast ERROR for cancellation (D4: never average above and below).
We had never once audited a TRIGGER for it. Measured on s105.0: `gw_hdd >= 16.4` fires 46.6%
pooled over 161 sessions - a healthy-looking discriminator - while per block it runs 19/20,
12/12, 12/12, 10/12 in winter and 0/10, 0/10, 0/10, 0/10 in all four summer blocks. The pooled
rate is a cancellation artifact, exactly the shape D4 forbids, applied to a condition instead of
to an error.

CORRECTION (S111, and the earlier wording was FALSE): this file originally said the bar "never
discriminates INSIDE a block". The tool's own output contradicts that - it is degenerate in 7 of
14 blocks and DOES split in the other seven (g7 2/10, g8 4/10, g9 19/20, g10 9/11, g13 10/12,
g14 4/12, g15 3/12). The true shape is worse than the false claim and more interesting: it is
degenerate at BOTH extremes - always-on in deep winter, always-off in summer - and discriminates
only in the SHOULDER, i.e. exactly the season the S102 salience slider says weather matters least.
The false sentence was carried into a commit message and into DECISIONS D28; recorded here rather
than quietly edited, per the standing rule that corrections are stated, not absorbed.

THE DISEASE, stated precisely (Greg, D23, sharpened): a condition whose state is decided by the
REGIME rather than by the DAY carries no information, whatever form it is written in. A limb that
never changes sign cannot gate (D-0709: `d_gw_cdd` at h1 positive 20/20 across G22+G23).

VERDICTS
  DEAD_NEVER        fires on no session anywhere - cannot gate
  DEAD_ALWAYS       fires on every session anywhere - cannot gate
  BLOCK_DEGENERATE  inside EVERY block it is 0% or 100%, but the blocks disagree. The pooled rate
                    looks alive and is an artifact. This is the verdict the pooled check hides.
  MOSTLY_DEGENERATE degenerate in >= DEGEN_WARN of its blocks. It discriminates somewhere, but on
                    most blocks the specialist reading it gets the same answer every day.
  LIVE              discriminates inside most of its blocks
  UNMAPPED          the quantity is not a served scalar - not checkable from the committed state
                    (reported as an open task, never as a pass - D24 state c)

THE MEASURE THAT MATTERS is the DEGENERATE-BLOCK SHARE, not the pooled fire rate: of the blocks
where this condition was evaluable, in how many did it return the same answer on every single day?
A specialist owns ONE day inside ONE block (D3, per-day causal slices), so a condition that is
0-of-10 or 10-of-10 within that block told it nothing, however lively the pooled number looks.

TWO RESULTS FROM THE FIRST RUN, both of which corrected the author (S111):
  1. `gw_hdd >= 16.4` is NOT a clean winter/summer split. It is degenerate at BOTH extremes
     (g11 12/12, g12 12/12 deep winter; g20-g23 0/10 all four summer blocks) and discriminates
     ONLY in the shoulder blocks (g7 2/10, g8 4/10, g14 4/12, g15 3/12). It carries information
     exactly in the season the S102 salience slider says weather matters least, and none in the
     season it dominates.
  2. The SHAPE-FORM positive control FAILED. `<= 5th percentile` is degenerate in 10 of 11
     blocks - because a 5%-rate condition on a 10-day block is 0.5 expected fires. Percentile
     form does NOT by itself fix degeneracy. The binding constraint is the FIRE RATE against the
     BLOCK SIZE, not whether the bar is written as a value or as a rank.

This tool is REPORT-ONLY by construction: it opens the brain and the staged states read-only,
writes nothing, and always exits 0. It is a measuring instrument, not a gate. Promoting any
verdict to a hard gate is Greg's call (same posture as D27).
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
STATE_DIR = os.path.join(HERE, "renders", "ng_refine_s95")

# blocks that carry the modern (S102+) served state; older groups predate tape_conditions
DEFAULT_GROUPS = ["grp6", "grp7", "grp8", "grp9", "grp10", "grp11", "grp12", "grp13",
                  "grp14", "grp15", "grp16", "grp18", "grp19", "grp20", "grp21",
                  "grp22", "grp23"]

MIN_BLOCK_N = 5          # blocks thinner than this do not vote on degeneracy
DEGEN_WARN = 0.60        # degenerate in >= this share of its blocks -> MOSTLY_DEGENERATE
# A block is ~10 sessions (D5: Sunday -> second Friday). A condition needs a fire rate far enough
# off 0 and 1 to expect a split in a 10-day window; that is the real bar, and it is a RATE test,
# not a FORM test. Kept as a named constant so the threshold is arguable rather than buried.


# --------------------------------------------------------------------------------------
# CONDITION KINDS - the four populations found in the S111 inventory (48 literals, 29 plays)
# --------------------------------------------------------------------------------------
KIND_COUNT = "COUNT"        # sessions / cycles / occurrences. Regime-proof by construction.
KIND_SHAPE = "SHAPE"        # percentile, ratio, fraction, sigma-multiple. The target form.
KIND_ABS = "ABSOLUTE"       # a level in a market unit (gw, Bcf, lots, USD, a raw share). The disease.
KIND_MIXED = "SHAPE_QTY_VALUE_BAR"   # shape-form QUANTITY carrying a value bar. Half-cured.

KIND_NOTE = {
    KIND_COUNT: "regime-proof: a session count means the same thing in January and July",
    KIND_SHAPE: "TRANSFERS across regimes - but does NOT by itself discriminate (see below)",
    KIND_ABS: "a level in a market unit - moves under the play when the regime moves",
    KIND_MIXED: "the quantity travels; the bar on it may not (k3 <= 0.05, |dip_imb| >= 0.15)",
}

# THE FINDING THAT INVERTED THE AUTHOR'S PRIOR (S111, measured by this tool on its first run):
# KIND is NOT what predicts degeneracy. POSITION IN THE DISTRIBUTION is.
#   worst  91% degenerate : `<= 5th percentile`            - SHAPE form, an EXTREME of its series
#   best    0% degenerate : `session_b_share_two_sided < 0.50` - ABSOLUTE form, the CENTRE of its
#                                                            series (the 50/50 physics line)
# So there are TWO distinct diseases and we had been conflating them:
#   (1) TRANSFER failure    - the bar means something else in a new regime. Cured by SHAPE form.
#                             Real: gw_hdd >= 16.4 is 12/12 in g11/g12 and 0/10 in all four
#                             summer blocks.
#   (2) DISCRIMINATION failure - the condition returns the SAME answer on every day of the block
#                             the specialist is actually standing in. Cured by siting the bar
#                             near the CENTRE of its own distribution. A rate property, not a
#                             form property.
# (2) is the one that costs us, because of D3: a specialist owns ONE day inside ONE block and
# never sees the pooled corpus. A condition that is 0-of-10 within its block told that specialist
# nothing, however cleanly it transfers. A healthy condition needs BOTH properties, and shape
# form buys only the first - which is why S98's ratio reformulation of C2 was refuted on
# comparable data (0.714 on a true instance vs 0.718 on a false one).


# --------------------------------------------------------------------------------------
# THE REGISTRY - condition -> served quantity. HAND-CURATED ON PURPOSE.
#
# Fuzzy name-matching a prose condition to a state field is exactly the class of silent
# wrongness this program keeps finding (hole #8 recomputed coherently off the wrong contract;
# hole #9 read a plausible 0.0). Every mapping here is asserted by hand, carries its own
# `basis` string, and anything not mapped is reported UNMAPPED rather than guessed.
# --------------------------------------------------------------------------------------
def _abs_(v):
    return abs(v) if v is not None else None


REGISTRY = [
    # ---- the named D23 failures ---------------------------------------------------------
    dict(play="structure.accumulation_arm_turn", label="big_print_b_share >= 0.55",
         path="tape_conditions.big_print_b_share", op=">=", bar=0.55, kind=KIND_ABS,
         basis="raw big-print buy share; S107 found the size-weighted series is the live one"),
    dict(play="structure.accumulation_arm_turn", label="big_print_b_share >= 0.62 (extreme)",
         path="tape_conditions.big_print_b_share", op=">=", bar=0.62, kind=KIND_ABS,
         basis="same series, the single-day extreme arm"),
    dict(play="structure.accumulation_arm_turn", label="gw_hdd >= 16.4 (divergence override)",
         path="weather.gw_hdd", op=">=", bar=16.4, kind=KIND_ABS,
         basis="selector.divergence_resolution's catalyst-override gate, cited by this play"),
    dict(play="magnitude.shoulder_weather_band_void", label="near-window max HDD <= 13.5",
         path="weather_forecast.forecast_gw_hdd", op="<=", bar=13.5, kind=KIND_ABS,
         basis="PROXY: play means the near-window forecast MAX; served value is the run's gw_hdd"),
    dict(play="magnitude.shoulder_weather_band_void", label="HDD >= 16 (band owns normally)",
         path="weather_forecast.forecast_gw_hdd", op=">=", bar=16.0, kind=KIND_ABS,
         basis="PROXY, same caveat as the 13.5 arm"),
    dict(play="magnitude.s1void_injection_chain_bleed", label="session_b_share < 0.50",
         path="tape_conditions.session_b_share", op="<", bar=0.50, kind=KIND_ABS,
         basis="RAW encoding - the one the plays actually read"),
    dict(play="magnitude.s1void_injection_chain_bleed",
         label="session_b_share < 0.50 [TWO-SIDED control]",
         path="tape_conditions.session_b_share_two_sided", op="<", bar=0.50, kind=KIND_ABS,
         basis="CONTROL: the physics-correct series. Divergence from the raw arm above measures "
               "how much of the bar's behaviour was the S108 denominator defect, not the market"),
    dict(play="monday.overnight_headfake_into_catchup", label="sell-share < 0.50",
         path="tape_conditions.session_b_share", op="<", bar=0.50, kind=KIND_ABS,
         basis="same raw series, non-confirming-flow limb"),
    dict(play="tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell",
         label="session buy flow > +1000 lots",
         path="tape_conditions.session_signed_flow", op=">", bar=1000, kind=KIND_ABS,
         basis="absolute lot count on a tape whose session volume spans 12.9x stub-free"),
    dict(play="tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell",
         label="session buy flow > +1500 lots",
         path="tape_conditions.session_signed_flow", op=">", bar=1500, kind=KIND_ABS, basis="ladder rung 2"),
    dict(play="tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell",
         label="session buy flow > +2000 lots",
         path="tape_conditions.session_signed_flow", op=">", bar=2000, kind=KIND_ABS, basis="ladder rung 3"),
    dict(play="tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell",
         label="session buy flow > +3000 lots",
         path="tape_conditions.session_signed_flow", op=">", bar=3000, kind=KIND_ABS, basis="ladder rung 4"),
    dict(play="magnitude.terminal_impact_coefficient_carry", label="ph3 flow >= 500 lots (floor)",
         path="tape_conditions.phase_signed_flow[2]", op=">=", bar=500, kind=KIND_ABS,
         transform=_abs_, basis="the k3 QUANTITY is shape-form; this floor on it is not"),

    # ---- positive controls: forms we believe are healthy, measured rather than assumed ----
    dict(play="weekend.seam_sign_from_stability_ladder", label="book at <= 5th percentile",
         path="cot.managed_money_net_pctile_3y", op="<=", bar=5.0, kind=KIND_SHAPE,
         basis="CONTROL: an already-percentile-form condition. Expected LIVE across regimes"),
    dict(play="boundary.weekend_gap_wide_band_emission", label="<= 5-pctile worsening extreme",
         path="cot.managed_money_net_pctile_3y", op="<=", bar=5.0, kind=KIND_SHAPE,
         basis="CONTROL: same percentile instrument, band-emission arm"),
]

# conditions found in the inventory that CANNOT be checked from the committed state.
# Recorded as open tasks (D24 state c), never as passes.
UNMAPPED = [
    dict(play="direction.flow_nowcast", label="|dip_imb_level| >= 0.15", kind=KIND_MIXED,
         why="leg-level flow feature; not a served state scalar"),
    dict(play="tape.squeeze_ratchet_confirm", label="controls <= 17 trades/k", kind=KIND_ABS,
         why="trades-per-thousand is not served; trades_per_min is a different unit"),
    dict(play="daytype.eia_print_impulse_arbiter", label="60s impulse within +-300 USD", kind=KIND_ABS,
         why="price content - masked from the state by design (D2), needs the evidence file"),
    dict(play="magnitude.unpriced_shot_extension", label="no session closed >= +300 at shot sign",
         kind=KIND_ABS, why="price content - masked by design (D2)"),
    dict(play="magnitude.weekend_chain_drift_day_move", label="2x class mid (~2200 USD)",
         kind=KIND_MIXED, why="price content - masked by design (D2); the 2x multiplier is shape-form"),
    dict(play="handoff.residual_tilt_field", label="roll cohort >= +4,800 struck", kind=KIND_ABS,
         why="cohort attribution needs the second leg (NGU26) - unstageable as staged"),
    dict(play="magnitude.positioning_saturation_turn", label="+44 Bcf surplus erases", kind=KIND_ABS,
         why="derived comparison against a 5yr weekly pace, not a single served scalar"),
    dict(play="ride.magnitude_staircase", label="USD ladder 50/150/250/350/500", kind=KIND_ABS,
         why="price content - masked by design (D2). A pure value ladder: the whole play is bars"),
]


# --------------------------------------------------------------------------------------
def get_path(blk, path):
    """dotted path with optional [i] index; returns None if any hop is missing."""
    cur = blk
    for part in path.split("."):
        m = re.match(r"^([A-Za-z0-9_]+)\[(\d+)\]$", part)
        idx = None
        if m:
            part, idx = m.group(1), int(m.group(2))
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
        if idx is not None:
            if not isinstance(cur, list) or idx >= len(cur):
                return None
            cur = cur[idx]
    if isinstance(cur, bool) or not isinstance(cur, (int, float)):
        return None
    return cur


def fires(val, op, bar):
    return {">=": val >= bar, "<=": val <= bar, ">": val > bar, "<": val < bar}[op]


def load_blocks(groups):
    out = OrderedDict()
    for g in groups:
        f = os.path.join(STATE_DIR, g + "_state.json")
        if not os.path.exists(f):
            continue
        try:
            s = json.load(open(f))
        except Exception as e:                                   # a corrupt state is a finding
            print("  WARN unreadable state %s: %s" % (g, e))
            continue
        days = [(d, b) for d, b in s.items() if isinstance(b, dict) and d.isdigit()]
        if days:
            out[g] = sorted(days)
    return out


def evaluate(entry, blocks):
    """per-block fire counts for one condition."""
    tr = entry.get("transform")
    per = OrderedDict()
    for g, days in blocks.items():
        n = h = 0
        for _d, blk in days:
            v = get_path(blk, entry["path"])
            if tr is not None:
                v = tr(v)
            if v is None:
                continue
            n += 1
            if fires(v, entry["op"], entry["bar"]):
                h += 1
        if n:
            per[g] = (h, n)
    return per


def verdict(per):
    """returns (verdict, fired, evaluated, splitting_blocks, degenerate_blocks)."""
    tot_h = sum(h for h, _ in per.values())
    tot_n = sum(n for _, n in per.values())
    if tot_n == 0:
        return "UNMAPPED", 0, 0, [], []
    votes = [(g, h, n) for g, (h, n) in per.items() if n >= MIN_BLOCK_N]
    split = [g for g, h, n in votes if 0 < h < n]
    degen = [g for g, h, n in votes if h == 0 or h == n]
    if tot_h == 0:
        return "DEAD_NEVER", tot_h, tot_n, split, degen
    if tot_h == tot_n:
        return "DEAD_ALWAYS", tot_h, tot_n, split, degen
    if votes and not split:
        return "BLOCK_DEGENERATE", tot_h, tot_n, split, degen
    if votes and len(degen) / float(len(votes)) >= DEGEN_WARN:
        return "MOSTLY_DEGENERATE", tot_h, tot_n, split, degen
    return "LIVE", tot_h, tot_n, split, degen


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--groups", nargs="*", default=DEFAULT_GROUPS)
    ap.add_argument("--json", metavar="PATH", help="also write the findings as JSON")
    ap.add_argument("--quiet", action="store_true", help="verdict lines only")
    a = ap.parse_args()

    blocks = load_blocks(a.groups)
    if not blocks:
        print("no staged states found under %s - nothing to audit" % STATE_DIR)
        return 0

    nday = sum(len(d) for d in blocks.values())
    brain = json.load(open(BRAIN))
    bver = brain.get("meta", {}).get("version", "?")
    have = {p["id"] for p in brain["plays"]}

    print("=" * 86)
    print("CONDITION AUDIT - can each brain condition CHANGE STATE?   (report-only)")
    print("brain %s | %d plays | %d blocks | %d day-blocks" % (bver, len(have), len(blocks), nday))
    print("=" * 86)

    rows, counts = [], Counter()
    for e in REGISTRY:
        if e["play"] not in have:
            e = dict(e, missing=True)
        per = evaluate(e, blocks)
        v, h, n, split, degen = verdict(per)
        counts[v] += 1
        rows.append((e, per, v, h, n, split, degen))

    order = {"BLOCK_DEGENERATE": 0, "DEAD_NEVER": 1, "DEAD_ALWAYS": 2,
             "MOSTLY_DEGENERATE": 3, "UNMAPPED": 4, "LIVE": 5}
    rows.sort(key=lambda r: (order[r[2]], -len(r[6]), r[0]["play"]))

    for e, per, v, h, n, split, degen in rows:
        pct = (100.0 * h / n) if n else 0.0
        nvote = len(split) + len(degen)
        dshare = (100.0 * len(degen) / nvote) if nvote else 0.0
        flag = "  <== pooled rate is a cancellation artifact" if v.endswith("DEGENERATE") else ""
        print("\n%-18s %-6s %s" % (v, e["kind"], e["play"]))
        print("    condition : %s" % e["label"])
        print("    pooled    : %d/%d = %.1f%%%s" % (h, n, pct, flag))
        print("    DEGENERATE in %d of %d blocks (%.0f%%) - same answer every day of those blocks"
              % (len(degen), nvote, dshare))
        if e.get("missing"):
            print("    NOTE      : play id not present in this brain version")
        if not a.quiet:
            print("    basis     : %s" % e["basis"])
            if per:
                cells = ["%s%s %d/%d" % (g.replace("grp", "g"),
                                         "*" if g in degen else " ", hh, nn)
                         for g, (hh, nn) in per.items()]
                print("    per block : %s   (* = degenerate)" % "  ".join(cells))
            if split:
                print("    splits in : %s" % ", ".join(s.replace("grp", "g") for s in split))
            else:
                print("    splits in : NOWHERE - it never discriminates on a DAY, only on which "
                      "BLOCK you are in")

    print("\n" + "-" * 86)
    print("UNCHECKABLE FROM THE COMMITTED STATE (open tasks, not passes - D24 state c)")
    print("-" * 86)
    for u in UNMAPPED:
        print("  %-6s %-58s %s" % (u["kind"], u["play"], u["label"]))
        print("         why: %s" % u["why"])

    print("\n" + "=" * 86)
    print("SUMMARY  " + "  ".join("%s=%d" % (k, c) for k, c in sorted(counts.items())))
    print("         unmapped-by-inspection=%d" % len(UNMAPPED))
    print("KIND KEY")
    for k in (KIND_COUNT, KIND_SHAPE, KIND_ABS, KIND_MIXED):
        print("  %-20s %s" % (k, KIND_NOTE[k]))
    print("\nThis tool never fixes anything and never fails a run. Promoting any verdict to a")
    print("hard gate is Greg's call (same posture as D27 render continuity).")
    print("=" * 86)

    if a.json:
        payload = dict(brain_version=bver, groups=list(blocks), day_blocks=nday,
                       findings=[dict(play=e["play"], condition=e["label"], kind=e["kind"],
                                      verdict=v, fired=h, evaluated=n,
                                      per_block={g: list(t) for g, t in per.items()},
                                      splits_within=split, degenerate_within=degen,
                                      degenerate_block_share=(
                                          round(len(degen) / float(len(split) + len(degen)), 3)
                                          if (split or degen) else None),
                                      basis=e["basis"])
                                 for e, per, v, h, n, split, degen in rows],
                       uncheckable=UNMAPPED)
        with open(a.json, "w") as fh:
            json.dump(payload, fh, indent=1)
        print("wrote %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
