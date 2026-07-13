# SESSION HANDOFF — S89 (work date 2026-07-13) — durable RAW MBP-10 ingestion, now landing on AWS S3

Branch: rebased onto the s79 trunk at start (came up on the stale S70 tip `3c70ff5`, rebased).
All code + docs pushed to `claude/kalshi-s79-kickoff-ij8t9o`.

## The job (from KICKOFF S89): build the durable RAW-INGESTION workflow. DONE + running.
Pull the continuous full-raw MBP-10 year (CL+NG, 2025-07..2026-07), keep ALL raw data, batch download,
gzip, store durably. Greg's call in-session: month-at-a-time batch; store on AWS (his account) not git;
IAM user + S3 bucket.

## What was BUILT / FIXED (trunk)
1. **Zero-filter raw writer** (`databento_backfill._write_mbp10_df`): removed the ONE silent row-drop
   (a row whose ts couldn't be parsed used to be discarded; now it always writes, to an `_undated`
   file if needed). Verified against a real CL day = **76 fields/row**, all 10 bid+ask levels
   (px/sz/ct) + action/side/depth/flags/sequence/ts_event/ts_recv. Truly zero reduction.
2. **`batch_pull(flush_dir=...)`** (`databento_backfill.py`): gzips each per-day JSONL AS IT LANDS and
   deletes the raw, so local never holds more than ONE day of raw even for a whole-month batch. This is
   what makes month-at-a-time safe (a full raw month ~= 29 GB would overrun a runner; one day gz ~= 61 MB).
3. **`pull_year_mbp10.py`** reworked: month loop, `flush_dir`, commit-only-if-new, `--worktree`/`--scratch`
   flags (run on any machine), and **`--dest`**: `git` (worktree of data/nymex-ticks) OR
   **`s3://BUCKET/PREFIX`** (boto3 upload to PREFIX/nymex_cont/, resume-skip via bucket list, standard
   AWS env auth). No git worktree needed in s3 mode.
4. **`AWS_INGEST_SETUP_S89.md`** — the runbook (bucket, IAM, run commands, split, verify).

## The one-day PROOF (before committing hours)
Pulled one CL day (2026-05-14) full-raw: **975,836 messages, 1.3 GB raw -> ~61 MB gz** (< GitHub's
100 MB/file cap), 76 fields, full ladder populated. This is the full new raw type -- NOT the earlier
incomplete format. Cost ~$0.28/CL-day -> ~$7.5 per (month,contract) -> ~$150 for the CL+NG year.

## LIVE STATE — the year is being pulled to AWS S3
- **Bucket** `bento-568968024170-us-east-2-an`, region **us-east-2**, prefix `nymex/`
  (objects: `nymex/nymex_cont/{CL,NG}_YYYYMMDD.jsonl.gz`). IAM user **`Claude`** (AmazonS3FullAccess).
- **Creds are SECRETS, not in git**: the IAM access key/secret + `DATABENTO_API_KEY` are pasted per
  session. A new session must have them re-pasted to monitor/resume.
- **Split (disjoint, no double-charge):** this S89 container runs **Jan-Jun 2026** to the bucket
  (`--start 2026-01 --end 2026-07`); **Greg's machine runs Jul-Dec 2025** (`--start 2025-07 --end
  2026-01`) to the same bucket. At handoff time the first (Jan CL) batch job was still `queued` at
  Databento; **bucket was still empty** (batch jobs take minutes-to-hours to process).
- The container half dies when this container is reclaimed -> it's RESUMABLE (re-run skips months
  already in the bucket). Greg's box is the durable half.
- Credential test PASSED (boto3 put/list/get to the bucket). `nymex/_healthcheck.txt` left in the bucket
  (harmless; resume globs `{root}_{yyyymm}` so it's ignored).

## Data changes on git
- Wiped the old incomplete `nymex_cont/` off `data/nymex-ticks` (52 files). Release-window tapes KEPT:
  `nymex_tape/` (28, S85 trades) + `nymex_mbp10/` (27, S86 depth). The full-raw year is a SUPERSET of
  those windows and supersedes them.
- The git-branch stopgap half (Jan CL) pushed NOTHING before being stopped -> the whole corpus now goes
  to S3, uniformly full-raw. `data/nymex-ticks:nymex_cont/` is currently EMPTY.
- Struck the "reduced data" framing from S88 handoff + S89 kickoff (Greg: it was a mistake; there is no
  reduced tier, all data is raw).

## NEXT (S90)
1. **Finish the year to the bucket.** Check what months are in `nymex/nymex_cont/`; resume the missing
   ones (re-paste creds; `pull_year_mbp10.py --start .. --end .. --dest s3://bento-568968024170-us-east-2-an/nymex`).
   Verify a sample day end-to-end (download from S3, confirm 76-field raw rows).
2. **Rework the scoring to read the RAW tape from the bucket** (Greg S88): `month_characterize.py`,
   `bucket_continuation.py`, `forecaster_month_pass.workflow.js` currently pre-process on the ingest
   side -- move that to the trade-signal side; the scoring reads the full raw S3 tape. Add an S3 reader.
3. Standing: rotate/deactivate the IAM key once the pull is done (Greg not worried, but good hygiene).

## RULES (unchanged): historical data RAW, keep ALL info, zero gates on the data side; gates ONLY on
trade signals; leakage gate before any scoring; exclude settle window (trade side); net-of-fee maker AND
taker; zero synthetic; provisional-until-live; NYMEX=canary/fire on Kalshi; weather forecaster = Greg's
spec HANDS OFF; DATABENTO_API_KEY + AWS keys are secrets (never commit).
