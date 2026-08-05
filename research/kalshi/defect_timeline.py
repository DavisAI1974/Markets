#!/usr/bin/env python3
"""
defect_timeline.py - which groups ran on a known-broken input, and was the EVIDENCE re-measured?

WHY THIS EXISTS (Greg, S112, and it reframed how the 82-play audit output should be read):
"You will see that the earlier runs had less data, broken data, etc which is fine as long as we
fixed the issues later. The point of these runs was to get better so bad runs aren't a problem as
long as the issue is fixed later."

That is the S107 development-loop framing applied to the audit. A degraded run is NOT a mark against
a play, and grading plays by the quality of the run their evidence came from is the wrong question.

THE RIGHT QUESTION IS NARROWER: was the defect fixed, and was the play's evidence RE-MEASURED after
the fix? Because the standing failure mode is that we fix the FEED and never recompute the NUMBER
that was derived from it. The feed moves on; the brain keeps the old number forever.

IT HAS ALREADY HAPPENED ONCE, AND IT WAS CAUGHT BY HAND. S107 found `big_print_b_share` was serving
the count-based series under the size-weighted name. The G19 post-mortem had already concluded, off
the broken series, that "the 0.55 gate never fires, block max 0.537" - an artifact; the size-weighted
series reaches 0.550 and FIRES. That conclusion had to be retracted in s103.6. One instance was
caught because a human happened to re-read it. This file is that check, mechanised.

THE FIELD THAT DECIDES EVERYTHING is `repair`:
  RETRO_REPAIRED - the historical states were rebuilt, so evidence recomputed off them is sound.
  FORWARD_ONLY   - the source was fixed for future stagings and the affected groups were NEVER
                   re-staged. Any evidence derived inside the window is still the broken number.
  OPEN           - not fixed at all yet.
FORWARD_ONLY is the dangerous class, and it is the one nothing currently flags.

Report-only. Never edits the brain.

USAGE
    python defect_timeline.py list                 # the defect registry
    python defect_timeline.py groups               # per-group: which inputs were broken
    python defect_timeline.py stale                # plays whose evidence sits in a FORWARD_ONLY window
"""

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BRAIN = os.path.join(HERE, "knowledge", "ng_brain.json")
AUDIT_DIR = os.path.join(HERE, "forecasts", "brain_audit")

RETRO, FWD, OPEN = "RETRO_REPAIRED", "FORWARD_ONLY", "OPEN"

# --------------------------------------------------------------------------------------
# THE REGISTRY. Every entry carries its instance inline (the S110 rule) and cites where in the
# committed record it is documented. `quantities` are the served names a play would read; they are
# how a play gets matched to a window. Where a scope is stated in the record but not independently
# re-verified here, `verified` says so - never a silent assumption.
# --------------------------------------------------------------------------------------
DEFECTS = [
    dict(id="h-vol_regime", found="S107", fixed="S107", repair=FWD,
         groups=[16, 17, 18, 19, 20],
         quantities=["vol_regime"],
         what="vol_regime DEAD on a hard-coded SPAN_END. The module built to condition MAGNITUDE - "
               "the brain's own stated dominant residual - and five groups were scaled without it.",
         fix="root fix S107: span now derives from the tape, not a constant",
         verified="scope per CLAUDE.md S107; not independently re-measured here"),
    dict(id="h-weather_path", found="S107", fixed="S107", repair=FWD,
         groups=list(range(6, 22)),
         quantities=["weather", "gw_hdd", "gw_cdd"],
         what="the weather block was EMPTY on every staged group from a path mismatch "
              "(data/nws_temp/ vs where the pull landed it)",
         fix="path corrected S107; restore_substrate.py rebuilds the store",
         verified="stated 'EVERY staged group' in S107; group list is inferred, treat as approximate"),
    dict(id="h-storage", found="S107", fixed="S107", repair=FWD,
         groups=[18, 19, 20, 21], quantities=["storage", "stor_surprise"],
         what="storage / stor_surprise blocks silently EMPTY", fix="S107", verified="CLAUDE.md S107"),
    dict(id="h-l1book", found="S107", fixed="S107", repair=FWD,
         groups=[20, 21], quantities=["l1_book", "session_signed_flow"],
         what="the signed-flow + l1_book read was empty", fix="S107", verified="CLAUDE.md S107"),
    dict(id="h-options_surface", found="S107", fixed="S110", repair=FWD,
         groups=[16, 20, 21], quantities=["options_surface"],
         what="options_surface empty, and separately the strike ladder was 10x wrong until S110",
         fix="S107 emptiness; S110 the x10 scale", verified="CLAUDE.md S107 + S111"),
    dict(id="h-big_print_series", found="S107", fixed="S107", repair=FWD,
         groups=[19], quantities=["big_print_b_share"],
         what="WRONG SERIES - the count-based value shadowed the size-weighted one under the same "
              "name. THE WORKED CASE FOR THIS WHOLE FILE: the G19 post-mortem concluded 'the 0.55 "
              "gate never fires, block max 0.537' off the broken series; the size-weighted series "
              "reaches 0.550 and FIRES, and the conclusion was retracted in s103.6.",
         fix="S107", verified="CLAUDE.md S107 - and this one WAS re-measured, which is why it is the model"),
    dict(id="h-bshare_denom", found="S108", fixed="S108", repair=FWD,
         groups=list(range(6, 22)), quantities=["session_b_share", "phase_b_share",
                                                "big_print_b_share", "session_b_share_two_sided"],
         what="every *_b_share divided by TOTAL volume while the tape carries a third side value "
              "('N') worth 13.49% of volume - denominator only. Served mean 0.4078 against a "
              "two-sided 0.4999, and the two disagree about the 0.50 side 45.7% of the time.",
         fix="fixed ADDITIVELY S108 (the two-sided series added alongside)",
         verified="CLAUDE.md S108"),
    dict(id="h-tape_offinstrument", found="S108", fixed="S108", repair=FWD,
         groups=[21, 23], quantities=["tape_conditions", "session_signed_flow", "session_b_share"],
         what="tape_conditions served the DEFERRED contract after a roll - the source picked "
              "'whichever store has MORE trades'. G21 served 18-60% of the real tape with signed "
              "flow SIGN-FLIPPED on the blind's only open-time flow channel. G21 4 days, G23 1 day; "
              "G20 and G22 clean.",
         fix="fixed at source S108; tape_reconcile.py blocks the rest",
         verified="CLAUDE.md S108"),
    dict(id="h-nws_tail", found="S108", fixed="S108", repair=FWD,
         groups=[23], quantities=["nws_temp", "gw_hdd", "gw_cdd", "weather"],
         what="PARTIAL FETCH TAIL - the last day of any pull is computed on incomplete hours and is "
              "WRONG while reporting coverage 1.0. 07-13 read 8.034/mod_cool as a tail against "
              "13.548/hard_cool once a later day was fetched: a 68% error and a REGIME FLIP inside "
              "G23's window.",
         fix="S108", verified="CLAUDE.md S108"),
    dict(id="h-session_bshare_encoding", found="S109", fixed="S109", repair=RETRO,
         groups=[22, 23], quantities=["session_b_share"],
         what="WRONG ENCODING - the two readers spelled a trade side differently ('B' vs 1), so on "
              "the leg path nothing matched and the served share was a flat 0.0 on all 8 scored-leg "
              "days of BOTH G22 and G23.",
         fix="source normalized + copy-through + an ALGEBRAIC IDENTITY guard in state_health; "
             "historical states RETRO-REPAIRED by bshare_restage_repair.py, each repaired reading "
             "declaring itself via session_b_share_basis",
         verified="CLAUDE.md S109 - the one defect whose history was actually rebuilt"),
    dict(id="h-squeeze_live", found="S109", fixed="S109", repair=RETRO,
         groups=[22, 23], quantities=["squeeze_watch"],
         what="the _live limbs were the FROZEN value under a live name, asserting satisfied_live "
              "true on five sessions whose live dte is 18-21 against a <=7 window",
         fix="squeeze_watch_live_repair.py", verified="CLAUDE.md S109"),
    dict(id="h-mbo_book_absent", found="S110", fixed=None, repair=OPEN,
         groups=[21, 22, 23], quantities=["l1_book", "book", "mbo"],
         what="MBO book files absent for g21/g22/g23 - the book layer stood down GROUP-WIDE",
         fix=None, verified="DROP_IN_S112 live traps"),
    dict(id="a10-fingerprint_book", found="S112", fixed=None, repair=OPEN,
         groups=[11, 12, 13],
         quantities=["dip_imb_level", "exhaustion", "aligned_imb", "imb_R", "aligned_imb_R",
                     "aligned_imb_push", "far_thinning", "spread_ratio", "bid_dep_entry",
                     "ask_dep_entry", "dip_mi_flow"],
         what="eleven BOOK-derived features hard-constant in fingerprints.json from 2026-01-18 "
              "(dip_imb_level exactly +1.000 on all 2,160 legs against 70-72 distinct values/day "
              "before). Cause: run_g11_fingerprints_s98.py runs on the TRADES-ONLY tape and wrote "
              "0.0/1.0 DEFAULTS where a null would have been caught. pre_vol survives because it is "
              "trade-derived - which is what isolates the cause.",
         fix=None, verified="MEASURED S112, this session, registry item A-10"),
]


def cmd_list(_):
    print("%-26s %-6s %-6s %-14s %s" % ("defect", "found", "fixed", "repair", "groups"))
    print("-" * 96)
    for d in DEFECTS:
        print("%-26s %-6s %-6s %-14s %s" % (d["id"], d["found"], d["fixed"] or "-", d["repair"],
                                            ",".join(str(g) for g in d["groups"])[:34]))
    n_fwd = sum(1 for d in DEFECTS if d["repair"] == FWD)
    print("\n  %d defects | RETRO_REPAIRED %d | FORWARD_ONLY %d | OPEN %d"
          % (len(DEFECTS), sum(1 for d in DEFECTS if d["repair"] == RETRO), n_fwd,
             sum(1 for d in DEFECTS if d["repair"] == OPEN)))
    print("  FORWARD_ONLY is the class that matters: source fixed, affected groups never re-staged,")
    print("  so any evidence derived inside the window is STILL the broken number.")
    return 0


def cmd_groups(_):
    per = {}
    for d in DEFECTS:
        for g in d["groups"]:
            per.setdefault(g, []).append(d)
    print("%-6s %-9s %s" % ("group", "defects", "ids (repair state)"))
    print("-" * 96)
    for g in sorted(per):
        ids = ", ".join("%s[%s]" % (d["id"].split("-", 1)[1][:16],
                                    {RETRO: "R", FWD: "F", OPEN: "O"}[d["repair"]])
                        for d in per[g])
        print("%-6s %-9d %s" % ("g%d" % g, len(per[g]), ids[:86]))
    print("\n  R = history rebuilt, evidence sound. F = forward-only, evidence NOT re-measured.")
    print("  O = still open.")
    return 0


def _audit_records():
    recs = []
    for f in sorted(glob.glob(os.path.join(AUDIT_DIR, "batch_*.json"))):
        with open(f, encoding="utf-8") as fh:
            recs.extend(json.load(fh).get("audits", []))
    return recs


def cmd_stale(_):
    """A play is FLAGGED when an instance it cites sits in a group where a quantity the play reads
    was broken under a FORWARD_ONLY or OPEN repair. That is evidence derived on a number that was
    later corrected and never recomputed."""
    recs = _audit_records()
    if not recs:
        print("no audit batches in %s yet - run the audit first" % os.path.relpath(AUDIT_DIR, ROOT))
        return 1
    with open(BRAIN, encoding="utf-8") as f:
        brain = json.load(f)
    text_of = {p["id"]: json.dumps(p).lower() for p in brain["plays"]}

    flagged = []
    for r in recs:
        pid = r.get("play_id")
        blob = text_of.get(pid, "")
        hits = []
        for inst in r.get("instances", []):
            grp = str(inst.get("group", "")).lower().lstrip("g")
            if not grp.isdigit():
                continue
            g = int(grp)
            for d in DEFECTS:
                if d["repair"] == RETRO or g not in d["groups"]:
                    continue
                # the play must actually READ the broken quantity
                if not any(q.lower() in blob for q in d["quantities"]):
                    continue
                hits.append((d["id"], d["repair"], g, inst.get("date")))
        if hits:
            flagged.append((pid, r.get("support_class"), hits))

    print("EVIDENCE DERIVED ON AN INPUT THAT WAS LATER CORRECTED AND NEVER RECOMPUTED")
    print("(%d of %d audited plays)\n" % (len(flagged), len(recs)))
    for pid, cls, hits in sorted(flagged, key=lambda x: -len(x[2])):
        seen = sorted({(h[0], h[1], h[2]) for h in hits})
        print("  %-56s %s" % (pid[:56], cls))
        for did, rep, g in seen:
            print("       g%-3d %-14s %s" % (g, rep, did))
    print("\n  This is NOT a verdict on the plays. Per Greg S112 a degraded run is fine if the issue")
    print("  was fixed - the open question is only whether the NUMBER was re-derived after the fix.")
    print("  Worked precedent: big_print_b_share's broken-series conclusion WAS re-measured and")
    print("  retracted in s103.6. That is the treatment each line above still needs.")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    return {"list": cmd_list, "groups": cmd_groups, "stale": cmd_stale}.get(
        sys.argv[1], lambda _: (print(__doc__), 1)[1])(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
