"""
pull_year_mbp10.py — pull a YEAR (or any month range) of continuous MBP-10 for CL+NG, month by month,
gzip to the data/nymex-ticks branch, delete local. Bounded disk; the year accrues gzipped on the branch
(pay-once, restored free every session via kalshi-session-start). Greg S87.

Per month, per contract: databento_backfill.batch_pull (submit -> poll -> download -> decode, one day in
memory at a time) -> data/nymex_cont/<ROOT>_YYYYMMDD.jsonl -> gzip into the worktree's nymex_cont/ ->
delete the raw .jsonl -> commit+push the worktree. RESUMABLE: a month already on the branch is skipped.

Setup (once, before running): a worktree of the data branch at WT:
    git worktree add --force /tmp/nymexdata data/nymex-ticks

Usage:
    DATABENTO_API_KEY=db-... python research/kalshi/pull_year_mbp10.py --start 2025-07 --end 2026-07
"""
from __future__ import annotations

import argparse
import glob
import gzip
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import databento_backfill as dbf                              # noqa: E402

WT = "/tmp/nymexdata"                                          # worktree of data/nymex-ticks
OUT = "data/nymex_cont"                                        # local scratch for decoded JSONL
BRANCH_DIR = os.path.join(WT, "nymex_cont")


def _months(start, end):
    """[start, end) as (year, month), start/end are 'YYYY-MM'."""
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    y, m = sy, sm
    while (y, m) < (ey, em):
        out.append((y, m))
        m += 1
        if m > 12:
            y += 1; m = 1
    return out


def _first_of_next(y, m):
    return f"{y+1}-01-01" if m == 12 else f"{y}-{m+1:02d}-01"


def _on_branch(root, y, m):
    return bool(glob.glob(os.path.join(BRANCH_DIR, f"{root}_{y}{m:02d}*.jsonl.gz")))


def _git(*args):
    return subprocess.run(["git", "-C", WT, *args], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM inclusive")
    ap.add_argument("--end", required=True, help="YYYY-MM exclusive")
    ap.add_argument("--max-cost-per", type=float, default=1000.0,
                    help="per (month,contract) cost gate ($). Price is pre-agreed -> high by default; the "
                         "estimate is still printed so spend is logged.")
    ap.add_argument("--worktree", default=WT,
                    help="path to a git worktree of the data/nymex-ticks branch (default /tmp/nymexdata). "
                         "Set this to run on any machine; create it once with: "
                         "git worktree add --force <path> data/nymex-ticks")
    ap.add_argument("--scratch", default=OUT, help="local scratch dir for decoded JSONL before gzip")
    args = ap.parse_args()

    global WT, OUT, BRANCH_DIR
    WT = args.worktree
    OUT = args.scratch
    BRANCH_DIR = os.path.join(WT, "nymex_cont")

    if not os.path.isdir(os.path.join(WT, ".git")) and not os.path.exists(os.path.join(WT, ".git")):
        sys.exit(f"[pull_year] worktree missing at {WT}; run: git worktree add --force {WT} data/nymex-ticks")
    os.makedirs(BRANCH_DIR, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    client = dbf._client()
    _git("config", "user.email", "noreply@anthropic.com")
    _git("config", "user.name", "Claude")

    total_rows = 0
    for (y, m) in _months(args.start, args.end):
        start, end = f"{y}-{m:02d}-01", _first_of_next(y, m)
        for root in ("CL", "NG"):
            if _on_branch(root, y, m):
                print(f"[pull_year] skip {root} {y}-{m:02d} (already on branch)", flush=True)
                continue
            try:
                # flush_dir -> each per-day JSONL is gzipped into the worktree AS IT LANDS and the raw
                # is deleted, so local never holds more than one day of raw even for a whole-month batch.
                n = dbf.batch_pull(client, root, start, end, "mbp-10", args.max_cost_per,
                                   out_dir=OUT, flush_dir=BRANCH_DIR)
                total_rows += n
            except SystemExit as e:
                print(f"[pull_year] SKIP {root} {y}-{m:02d}: {e}", flush=True)
            except Exception as e:
                print(f"[pull_year] ERROR {root} {y}-{m:02d}: {e}", flush=True)
        # fallback: gzip any straggler raw JSONL not already flushed (belt-and-suspenders)
        for f in sorted(glob.glob(os.path.join(OUT, "*.jsonl"))):
            with open(f, "rb") as src, gzip.open(os.path.join(BRANCH_DIR, os.path.basename(f) + ".gz"),
                                                 "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)
            os.remove(f)
        # commit the month if anything new landed in the worktree
        _git("add", "nymex_cont/")
        staged = _git("diff", "--cached", "--quiet").returncode != 0
        if staged:
            _git("commit", "-q", "-m", f"data: continuous MBP-10 nymex_cont/ {y}-{m:02d} (CL+NG), full-raw\n\n"
                 f"Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>")
            for _ in range(4):
                _git("pull", "--rebase", "origin", "data/nymex-ticks")
                r = _git("push", "origin", "HEAD:data/nymex-ticks")
                if r.returncode == 0:
                    break
            print(f"[pull_year] {y}-{m:02d} pushed (cum rows {total_rows})", flush=True)
        else:
            print(f"[pull_year] {y}-{m:02d} nothing new to commit", flush=True)
    print(f"[pull_year] DONE {args.start}..{args.end}: {total_rows} rows total", flush=True)


if __name__ == "__main__":
    main()
