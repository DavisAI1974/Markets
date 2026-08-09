#!/usr/bin/env python3
"""land_head_trades_a71.py - move the head trades out of the phantom tree and onto S3. (A-71, S115.)

WHAT WENT WRONG, corrected from what M-16 originally said. The 2025-07-22..2025-11-02 NG trades pull
completed at Databento (job GLBX-20260806-SEC5NWEY4U, 2,384,994 rows, $0.44) and the rows landed in
`research/kalshi/data/pyth_ticks/` - TWO defects stacked, not one:

  1. the phantom root: OUT_DIR is RELATIVE, so it resolved against cwd (research/kalshi);
  2. THE WRONG STORE NAME: `OUT_DIR = "data/pyth_ticks"` is the trades writer's hardcoded default and
     `_write_df(df, symbol)` takes no out_dir, so `--out-dir` is accepted and IGNORED.

M-16 named only the first, and A-71 told the next session to look in `data/nymex_cont_n0` - which is
an EMPTY DIRECTORY. Someone following that would have concluded the data was gone and re-pulled it.
**The second defect is the worse one: a flag that is accepted and ignored is a lie the caller cannot
see.**

VERIFIED BEFORE MOVING ANYTHING (never trust a row count you have not counted):
  rows on disk 2,384,994 == rows the job reported 2,384,994
  missing weekdays across 2025-07-22..2025-10-31: 0
  seam clean: phantom ends 20251031, canonical nymex_cont_n0 starts 20251102, no overlap, no gap

DESTINATION IS S3, NOT LOCAL (D34, Greg: "everything should be in aws"; D47: a store rebuilt in a
session is not a fix until it is on S3). Local `data/` is disposable and dies with the container.

    python land_head_trades_a71.py            # dry run
    python land_head_trades_a71.py --write    # gzip -> data/nymex_cont_n0/ -> S3, then READ BACK
"""
import argparse
import gzip
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KALSHI = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
# TWO levels up, not one. The first version of THIS SCRIPT went up one - landing the local copies
# in `research/data/` while fixing a bug whose whole content is "a relative path resolved against
# the wrong root". S3 was correct (that is the destination that matters, D34) but the local copy
# was a fresh phantom tree. Caught by listing the destination instead of trusting the exit code -
# which is the same check the script exists to enforce. NC-3, and mine, in the fix for its own
# family.
ROOT = os.path.abspath(os.path.join(KALSHI, "..", ".."))
sys.path.insert(0, KALSHI)

BUCKET = "bento-568968024170-us-east-2-an"
MOVES = [
    (os.path.join(KALSHI, "data", "pyth_ticks"), os.path.join(ROOT, "data", "nymex_cont_n0"),
     "nymex/nymex_cont_n0/"),
    (os.path.join(KALSHI, "data", "ng_l1"), os.path.join(ROOT, "data", "ng_l1"), "nymex/ng_l1/"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    import creds
    s3 = creds.aws_client("s3", "us-east-2")

    for src, dst, prefix in MOVES:
        if not os.path.isdir(src):
            print("[a71] %s absent - nothing to move" % src)
            continue
        files = sorted(f for f in os.listdir(src) if f.endswith((".jsonl", ".jsonl.gz")))
        os.makedirs(dst, exist_ok=True)
        existing = set(os.listdir(dst))
        print("\n[a71] %s -> %s -> s3://%s/%s" % (os.path.relpath(src, ROOT),
                                                  os.path.relpath(dst, ROOT), BUCKET, prefix))
        print("[a71]   %d file(s)" % len(files))
        # COLLISION IS A HARD STOP, NOT AN OVERWRITE. The canonical store is the walk's substrate;
        # silently replacing a day in it is how a group gets re-scored against different data than
        # it was forecast on.
        clash = [f for f in files if (f if f.endswith(".gz") else f + ".gz") in existing]
        if clash:
            raise SystemExit("[a71] REFUSING: %d name(s) already in the destination: %s"
                             % (len(clash), clash[:5]))
        if not a.write:
            print("[a71]   dry run - would move %s .. %s" % (files[0], files[-1]))
            continue

        landed = 0
        for f in files:
            out = f if f.endswith(".gz") else f + ".gz"
            dpath = os.path.join(dst, out)
            if f.endswith(".gz"):
                shutil.copyfile(os.path.join(src, f), dpath)
            else:
                with open(os.path.join(src, f), "rb") as r, gzip.open(dpath, "wb") as w:
                    shutil.copyfileobj(r, w)
            s3.upload_file(dpath, BUCKET, prefix + out)
            landed += 1
        print("[a71]   uploaded %d" % landed)

        # READ BACK FROM S3. Not the upload's exit code - the whole point of A-71 is that a
        # success report is not a landing (M-16, three occurrences of that family).
        keys, tok = set(), None
        while True:
            kw = dict(Bucket=BUCKET, Prefix=prefix)
            if tok:
                kw["ContinuationToken"] = tok
            r = s3.list_objects_v2(**kw)
            keys |= {o["Key"].split("/")[-1] for o in r.get("Contents", [])}
            if not r.get("IsTruncated"):
                break
            tok = r["NextContinuationToken"]
        want = {f if f.endswith(".gz") else f + ".gz" for f in files}
        missing = sorted(want - keys)
        print("[a71]   S3 read-back: %d of %d present%s"
              % (len(want) - len(missing), len(want),
                 "" if not missing else " - MISSING %s" % missing[:5]))
        if missing:
            raise SystemExit("[a71] FAILED: S3 does not hold what we just uploaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
