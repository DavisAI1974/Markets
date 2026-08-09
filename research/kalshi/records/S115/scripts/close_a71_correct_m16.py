#!/usr/bin/env python3
"""Close A-71 and correct M-16's description of its own defect. (S115.)

Both items named the WRONG LOCATION, and the correction matters more than the closure: A-71 sent the
next session to `data/nymex_cont_n0`, which is an EMPTY DIRECTORY. Following it would have produced
"the data is gone" and a needless re-pull.
"""
import collections
import json
import os

REG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "OPEN_ITEMS.json")

CORRECTION = (
    "\n\n**CORRECTED S115 - THE DEFECT IS TWO DEFECTS, AND THIS ITEM NAMED ONLY ONE.** Measured when "
    "A-71 was executed: the rows did not land in a phantom `data/nymex_cont_n0` (that directory was "
    "created EMPTY). They landed in **`research/kalshi/data/pyth_ticks/`** - the phantom root AND the "
    "wrong store name - because **`OUT_DIR = \"data/pyth_ticks\"` is the trades writer's hardcoded "
    "default and `_write_df(df, symbol)` takes no `out_dir`, so `--out-dir` is ACCEPTED AND IGNORED.** "
    "The relative path is the lesser half. **A flag that is accepted and ignored is a lie the caller "
    "cannot see**, and it is why the trades ended up filed as pyth ticks - a store from a different "
    "market, in a different format, that nothing would ever have looked in. The guarded entry point "
    "(`databento_backfill_s115.py`, arriving with A-70) fixes the root and asserts byte growth; it "
    "must also be checked for the ignored-`out_dir` half before the next trades pull.")

CLOSE = (
    "\n\n**DONE S115, and the location in the original text was WRONG - read the correction before "
    "trusting anything else here.** The head trades were never in `data/nymex_cont_n0`; they were in "
    "`research/kalshi/data/pyth_ticks/` (see M-16's S115 correction). Nothing was re-pulled.\n\n"
    "VERIFIED BEFORE MOVING: rows on disk **2,384,994 == the 2,384,994 the job reported**; **zero "
    "missing weekdays** across 2025-07-22..2025-10-31; seam clean (phantom ends 20251031, canonical "
    "began 20251102 - no overlap, no gap).\n\n"
    "LANDED: gzipped into `data/nymex_cont_n0/` and uploaded to **s3://bento-568968024170-us-east-2-an"
    "/nymex/nymex_cont_n0/**, then **READ BACK FROM S3** rather than trusting the upload's exit code - "
    "88 of 88 present. Trades on S3 now span **NG_20250722 .. NG_20260720, 311 files**. The 5 stranded "
    "L1 days went the same way; `nymex/ng_l1/` spans NG_20250722 .. NG_20260805, 326 files. Both "
    "phantom trees deleted.\n\n"
    "**A DEFECT I SHIPPED INSIDE THE FIX, recorded because the pattern is the point:** the mover's "
    "first version computed the repo root ONE level too high and wrote the local copies into "
    "`research/data/` - a fresh phantom tree, created by the script whose entire purpose is to undo "
    "one. S3 was correct throughout, which is the destination that matters (D34), and the local copies "
    "were relocated. It was caught by LISTING the destination, which is the same check this item "
    "exists to enforce.\n\n"
    "STILL TRUE AND WORTH KEEPING: the four Databento jobs are `done` and re-decodable free until "
    "**2026-09-05** - `GLBX-20260806-SEC5NWEY4U` (head trades) and `-FUHPD9FHH5` (L1) are the right "
    "leg; `-NEK78EWGLK` and `-Y65VR393GC` are NG.v.0 and must never be mixed into the walk.")


def main():
    with open(REG, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)
    by = {i["id"]: i for i in d["items"]}

    m16 = by["M-16"]
    if "CORRECTED S115 - THE DEFECT IS TWO DEFECTS" not in m16.get("why", ""):
        m16["why"] += CORRECTION
        print("M-16 corrected")

    a71 = by["A-71"]
    if a71["status"] != "DONE":
        a71["status"] = "DONE"
        a71["tier"] = "DONE"
        a71["why"] += CLOSE
        print("A-71 closed")

    with open(REG, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    print("ok")


if __name__ == "__main__":
    main()
