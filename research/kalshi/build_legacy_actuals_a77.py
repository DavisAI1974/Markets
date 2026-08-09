#!/usr/bin/env python3
"""build_legacy_actuals_a77.py - recover the g6-g16 actual corpus. (A-77, S118.)

THE CORPUS WAS 70 GRADEABLE DAYS. Only g18-g24 carried both a state and an actual, so A-69's
self-training loop had no training set. g6-g16 have committed masked STATES and no `gN_actual.json`.

**THE ACTUALS WERE NEVER MISSING - THEY WERE UNDER DIFFERENT FIELD NAMES.** Each group's
`gN_score.json`, written in the session that walked that group, carries `actual_gap_usd`,
`actual_net_usd`, `actual_day_move_usd` and `actual_close_cum` on every day row. Because that file
was produced by the group's own run, it is **BY CONSTRUCTION on the basis that group's STATE was
built on** - which is exactly what A-77's falsifier demands and what a tape rebuild cannot promise.

WHY NOT REBUILD FROM THE TAPE, MEASURED RATHER THAN ARGUED. Comparing `actual_close_cum` against a
cum derived independently from the committed NG.n.0 tape (`(last_print - anchor) * 10000`):

    g16   11/11 exact          n.0 IS this group's basis
    g12   12/12 exact          n.0 IS this group's basis
    g14    2/12, max |220|     the S103 split: g14's basis is calendar-front NGJ26, n.0 was already NGK26
    g10    0/11, ~5,000-6,000  a different leg entirely
    g6     0/10, up to 9,960   a different leg entirely

**A tape rebuild would have silently produced a corpus that scores cleanly and measures the wrong
contract for g6, g10 and g14** - the S108 hole #8 failure, applied to training data. The 23 exactly
reconciling days of g12+g16 are the independent corroboration that the score-file field means what
this script assumes and is scaled at $10,000 per $1.00 (NG = 10,000 MMBtu).

LEVELS ARE DERIVED, NOT INVENTED: close = anchor + actual_close_cum/10000, open = close -
actual_net_usd/10000. Every derived value is stamped `derived_from` so no reader mistakes it for a
tape read. `leg` is NOT emitted - this route cannot know it, and a guessed leg is worse than an
absent one.

    python build_legacy_actuals_a77.py            # dry run - per-group report
    python build_legacy_actuals_a77.py --write    # write renders/ng_refine_s95/gN_actual.json
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RENDERS = os.path.join(HERE, "renders", "ng_refine_s95")
TAPE = os.path.abspath(os.path.join(HERE, "..", "..", "data", "nymex_cont_n0"))
USD_PER_POINT = 10000.0
GROUPS = ["g%d" % n for n in range(6, 17)]


def _score_file(gid):
    """The group's OWN score file. Prefer the plain one: `_refined`/`_v2` variants carry the same
    actual_* columns (they are the same realized tape) but a refined GUESS, and we want the file
    whose provenance is least processed."""
    plain = os.path.join(RENDERS, "%s_score.json" % gid)
    if os.path.isfile(plain):
        return plain
    other = sorted(glob.glob(os.path.join(RENDERS, "%s*score.json" % gid)))
    return other[0] if other else None


def _tape_last(day):
    p = os.path.join(TAPE, "NG_%s.jsonl.gz" % day)
    if not os.path.isfile(p):
        return None
    px = None
    with gzip.open(p, "rt") as f:
        for line in f:
            try:
                px = json.loads(line)["price"]
            except Exception:
                pass
    return px


def build(gid):
    sf = _score_file(gid)
    if not sf:
        return None, "no score file"
    s = json.load(open(sf, encoding="utf-8"))
    # THE ANCHOR HAS TWO SHAPES ACROSS THE ERA. g6-g10/g12+ carry {date, price, last_hour_dir};
    # g11 carries a bare float. Normalise instead of assuming - the first version assumed a dict
    # and died on g11, which is the group that also has no actual_* columns, so the crash hid the
    # more interesting finding behind a less interesting one.
    anchor = s.get("anchor")
    if isinstance(anchor, (int, float)):
        anchor = {"date": None, "price": float(anchor)}
    elif not isinstance(anchor, dict):
        anchor = {}
    apx = anchor.get("price")
    if apx is None:
        return None, "score file carries no anchor price"
    rows = s.get("days") or []
    usable = [d for d in rows if d.get("actual_close_cum") is not None]
    if not usable:
        # g11 is this case: its score file predates the actual_* columns. Say so; do not fabricate.
        return None, "score file carries NO actual_* columns (%d day rows)" % len(rows)

    # INDEPENDENT RECONCILIATION, reported per group and never used to CORRECT the score file.
    # Where the tape agrees, this group's basis is n.0 and the corpus is corroborated. Where it
    # disagrees, the score file is still authoritative - it is on the group's own basis and the
    # tape is not - and the disagreement is RECORDED so nobody later reads agreement into it.
    checked = exact = 0
    worst = 0
    for d in usable:
        px = _tape_last(d["date"])
        if px is None:
            continue
        checked += 1
        diff = round((px - apx) * USD_PER_POINT) - d["actual_close_cum"]
        worst = max(worst, abs(diff))
        exact += (diff == 0)
    # THREE STATES, NOT TWO. g8 reconciles 7 of 10 and g9 3 of 20 - a leg that CHANGED INSIDE the
    # window, which a boolean would render as a flat "no" and lose. Partial agreement is the most
    # informative answer available and it is reported as its own state.
    if checked == 0:
        basis_state = "UNCHECKED"
    elif exact == checked:
        basis_state = "N0"
    elif exact == 0:
        basis_state = "OWN_LEG"
    else:
        basis_state = "MIXED_LEG_CHANGES_INSIDE_WINDOW"
    basis_agrees = basis_state == "N0"

    days = []
    for d in usable:
        cum = d["actual_close_cum"]
        close = round(apx + cum / USD_PER_POINT, 4)
        net = d.get("actual_net_usd")
        row = {
            "date": d["date"],
            "dow": d.get("dow"),
            "close": close,
            "net_usd": net,
            "gap_usd": d.get("actual_gap_usd"),
            "day_move_usd": d.get("actual_day_move_usd"),
            "cum_from_anchor_usd": cum,
        }
        if net is not None:
            row["open"] = round(close - net / USD_PER_POINT, 4)
        days.append(row)

    out = {
        "group": gid,
        "anchor": anchor,
        "basis": s.get("note") or "",
        "days": days,
        "provenance": {
            "built_by": "build_legacy_actuals_a77.py (A-77, S118)",
            "source": os.path.relpath(sf, HERE),
            "source_is_group_own_run": True,
            "derived_from": ("close = anchor + cum_from_anchor_usd/10000; "
                             "open = close - net_usd/10000. Levels are DERIVED from the group's own "
                             "recorded USD moves, not read from a tape."),
            "usd_per_point": USD_PER_POINT,
            "leg_omitted": ("this route cannot determine the contract leg; a guessed leg is worse "
                            "than an absent one"),
            "tape_reconciliation": {
                "tape": "data/nymex_cont_n0 (NG.n.0)",
                "days_checked": checked,
                "days_exact": exact,
                "max_abs_diff_usd": worst,
                "basis_state": basis_state,
                "basis_is_n0": basis_agrees,
                "note": ("n.0 AGREES on every checked day, so this group's basis is the continuous "
                         "front and the corpus is independently corroborated."
                         if basis_agrees else
                         "n.0 agrees on SOME days and not others - the contract leg CHANGES INSIDE "
                         "this window. A single-leg rebuild is wrong for this group in both "
                         "directions."
                         if basis_state == "MIXED_LEG_CHANGES_INSIDE_WINDOW" else
                         "n.0 DISAGREES - this group was walked on a different leg. The score file "
                         "is authoritative because it is on the group's own basis; the tape is not. "
                         "Do NOT rebuild this group from n.0 (A-77 falsifier)."),
            },
        },
    }
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    made = skipped = total_days = 0
    print("%-5s %6s %7s %-9s %s" % ("gid", "days", "tape", "basis", "note"))
    for gid in GROUPS:
        out, err = build(gid)
        if err:
            print("%-5s %6s %7s %-9s SKIP: %s" % (gid, "-", "-", "-", err))
            skipped += 1
            continue
        tr = out["provenance"]["tape_reconciliation"]
        print("%-5s %6d %7s %-9s anchor %s %.3f"
              % (gid, len(out["days"]), "%d/%d" % (tr["days_exact"], tr["days_checked"]),
                 {"N0": "n.0", "OWN_LEG": "OWN LEG", "MIXED_LEG_CHANGES_INSIDE_WINDOW": "MIXED",
                  "UNCHECKED": "?"}[tr["basis_state"]],
                 out["anchor"].get("date"), out["anchor"].get("price")))
        total_days += len(out["days"])
        made += 1
        if a.write:
            p = os.path.join(RENDERS, "%s_actual.json" % gid)
            if os.path.exists(p):
                raise SystemExit("[a77] REFUSING to overwrite existing %s" % p)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=1, ensure_ascii=False)
    print("\n[a77] %d group(s) recoverable, %d day(s); %d skipped." % (made, total_days, skipped))
    print("[a77] %s" % ("WROTE gN_actual.json" if a.write else "dry run - nothing written."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
