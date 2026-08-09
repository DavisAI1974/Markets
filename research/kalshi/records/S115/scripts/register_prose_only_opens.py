#!/usr/bin/env python3
"""Register the two open things that were living only in handoff prose. (S115 close.)

Greg, S115: "Open things go to the open items md." That is D30 restated - a finding with no home in
the registry does not exist - and the sweep found two, both of which I had been carrying in the
handoff and drop-in narrative across two sessions:

  1. the g6-g16 ACTUAL REBUILD, described inside A-69's `why` but with no line of its own, despite
     being a distinct data operation with its own failure mode (silently normalising every old block
     onto one continuous basis);
  2. the G24 REFINE itself, mentioned inside A-65's `why` as the thing that will first exercise it,
     but never registered - it has been "S115's opener", then "housekeeping", for two sessions, in
     prose only.

Written HERE rather than on a scratchpad, per D52 and because that rule was already broken once this
session. Idempotent.
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "..", "..", "..", "OPEN_ITEMS.json")


def main():
    with open(REG, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)
    have = {i["id"] for i in d["items"]}

    def add(**kw):
        if kw["id"] in have:
            print("exists", kw["id"])
            return
        d["items"].append(collections.OrderedDict(kw))
        print("added", kw["id"])

    add(id="A-77",
        title="REBUILD THE g6-g16 ACTUALS - the corpus is 70 gradeable days, not the ~180 the narrative implied",
        source="S115 close; measured when scoping A-69, and named as its own item in the external build's "
               "'not claimed as passed' list. Registered on Greg's instruction that open things go to the "
               "registry, not into handoff prose.",
        first_raised="S115", status="OPEN", size="M", tier="ESSENTIAL",
        tier_why="A-69's self-training loop has no training set without it, and A-69 is one of the two arms "
                 "of the architecture test. It was described inside A-69's `why` and had no line of its own, "
                 "which is exactly the shape D30 exists to catch.",
        why="MEASURED S115, against a number I had asserted from narrative. I said '18 blocks, ~180 days'. "
            "Only g18-g24 carry BOTH a state and a rebuilt actual - **70 gradeable days**. g6-g16 have "
            "states with no actuals, so they are unlabelled data: a blind can be run on them but nothing "
            "can score it.\n\n"
            "THE GAP IS A REBUILD, NOT A RE-PULL. The day ranges are recoverable from the state files "
            "themselves (each state is keyed by its own days) and `group_actual.build(gid)` already exists - "
            "it is what `stage_group` calls. Nothing needs to be bought.",
        what="Rebuild each missing actual **on the basis that group's STATE was built on**. g6-g16 span the "
             "period when the series construction changed (S97: NG.v.0 whipsaws through expiry weeks, G11 "
             "was re-pulled on NG.n.0, G3-G10 are clean), so the per-group basis is NOT uniform. Record the "
             "basis used per group alongside the actual, the way `storage_repair_basis` and "
             "`session_b_share_basis` declare themselves.",
        falsifier="**DO NOT silently normalise every old block onto one continuous basis** - that would "
                  "produce a corpus that scores cleanly and measures the wrong contract, which is the S108 "
                  "hole #8 failure (off-instrument data that is populated, self-consistent, and wrong). The "
                  "check: for a group whose state was built on a different leg, the rebuilt actual must "
                  "DIFFER from a naive NG.n.0 rebuild by the measured basis. If they are identical across "
                  "every group, the basis is not being honoured.")

    add(id="A-78",
        title="THE g24 REFINE HAS NEVER RUN - carried as 'the opener' then 'housekeeping' for two sessions, in prose only",
        source="S115 close, sweeping the handoff and drop-in for opens with no registry line (Greg: 'Open "
               "things go to the open items md')",
        first_raised="S114 (as S115's opener)", status="OPEN", size="M", tier="REST",
        tier_why="Deliberately REST, and the demotion is the honest part. A-67 arm 1 is a BLIND run on the "
                 "clean unwalked head, which is a better test than a refine of a block whose state has been "
                 "read forwards and backwards all session. This is real work that should happen; it is not "
                 "the frontier, and pretending otherwise is how the frontier gets displaced.",
        why="g24 blind scored 6/10, sum|err| 4,890 - **0.98x zero_change and 1.20x seasonal_naive**, i.e. we "
            "tied doing nothing and lost to naive. The refine has never been run against it. It was started "
            "at S115 and stopped at 2 of 10 posteriors, both DISCARDED as artifacts of the degraded brain "
            "view that was reverted the same session; the inputs survive at "
            "`research/kalshi/records/S115/refine_g24_aborted/`.\n\n"
            "THE POINT OF THE ROUND IS MAGNITUDE, NOT DIRECTION, and the aborted directive already says so: "
            "the blind's dominant failure was emitting **0.29x of realized magnitude, under on 8 of 10 "
            "days**, worsening from 0.55x (g22) and 0.68x (g23). A refine that returns 10/10 direction at "
            "the same sizing has fixed nothing.",
        what="Re-run round 1 from the surviving directive, on the REPAIRED g24 state (storage lane grafted "
             "at S115, 12 hard -> 0 hard) and the full brain view with nothing withheld. Score with "
             "`blind_score_nonpooled.py` against its three named benchmarks (A-1) and report with "
             "`per_event.py` (D4/D37 - no pooled scalar).",
        falsifier="The round succeeds only if mean|guess| / mean|actual| moves materially off 0.29x **and** "
                  "sum|err| beats zero_change. A 10/10 direction result at 0.3x emission is the failure "
                  "wearing a hit-rate, and should be reported as one.")

    with open(REG, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    print("registry now %d items" % len(d["items"]))


if __name__ == "__main__":
    main()
