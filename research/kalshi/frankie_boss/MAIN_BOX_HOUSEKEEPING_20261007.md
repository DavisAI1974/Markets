# Main box housekeeping, 2026-10-07 night (session 2)

Box `i-035994afa8bdf66a5` (us-east-1, r7i.8xlarge, profile Ssm). This was housekeeping only, on Greg's go: "throw
away trash files in main box and zip important stuff and store [it elsewhere] ... just get a cheap store". S3 is
the store.

What did not happen:
- no day run, ROOT, model call, E2E or fit;
- nothing on the small box;
- no IAM change;
- no repo code edit, commit or push.

The box is **STOPPED**, with `KeepRunning=false` (confirmed by DescribeInstances).

## Disk

| | Used | Free | Size |
|---|---|---|---|
| Before (16:3xZ) | 956.9 GB | 1,172.1 GB | 2,129.0 GB (`/dev/root`) |
| After (17:25Z) | 703.5 GB (34%) | **1,425.5 GB** | 2,129.0 GB |

Space freed by step:

| Step | Freed | Script |
|---|---|---|
| 12 archived and verified ingest day directories removed | 188.1 GB | guarded removal (below) |
| 43 stale staged checkouts and 10 ingest worktrees removed | 65.5 GB | `frankie_box_cleanup_code.sh` |
| 18 transfer `source.pack` files removed, about 591 MB each | about 10.6 GB | `frankie_box_cleanup_cache.sh`, workflow run 824 |
| PySR and Julia added | -1.4 GB (space used) | install, see PySR below |

## Inventory (`du`)

Before, in `/opt/frankie-box` (952 GB total):
- `work`: 863 GB
  - Monday root: 427 GB
  - `experiment-roots`: 80 GB
  - `experiment-teacher-rows`: 25 GB
  - `day-external`: 10 GB
  - 12 archivable ingest days: 188 GB
  - 11 KEEP ingests
- `code`: 70 GB (52 checkouts of 1.35 GB each, plus 18 transfer packs of 591 MB each)
- `ingest-code`: 7.6 GB
- `session`: 2.7 GB
- `granite`: 2.3 GB
- `venv`: 2.0 GB
- `data`: 1.65 GB
- `markets`: 1.4 GB
- `tmp`: 1.3 GB

After, in `/opt/frankie-box` (693 GB total):
- `work`: 675 GB
- `ingest-code`: 3.3 GB (4 worktrees)
- `venv`: 3.0 GB
- `session`: 2.7 GB
- `granite`: 2.3 GB (untouched)
- `data`: 1.65 GB
- `markets`: 1.48 GB
- `code`: 1.35 GB (1 checkout)
- `tmp`: 1.33 GB
- `producers`: 0.23 GB

Outside `/opt/frankie-box`: `/var/log` 1.8 GB, apt cache 0.25 GB, `/root/.julia` 0.34 GB.

Command used for the after picture: `frankie_box_disk_usage.sh TARGET=. DEPTH=1`.

## Classification

KEEP_ON_BOX (untouched):
- `granite`, `venv` (PySR added, below) and `markets`.
- The Monday root `monday-calculations/full-20211004-20260927-r1-48`: 427 GB, `calculations_retained`. There is no archive tool for roots.
- The gold day `ingest-20211004-ingest-1790057801` (23.7 GB).
- The 10 ingests from GitHub run 36571235912 that are already complete on S3:
  - 20221011, 20221012, 20221018, 20221019
  - 20231003, 20231004, 20231010, 20231011, 20231017, 20231018

IMPORTANT, but no archive tool exists for these kinds, so they were left in place and listed only:
- `experiment-roots` (80 GB), `experiment-teacher-rows` (25 GB), `day-external` (10 GB) and `runs` (0.76 GB);
- the 20211004 canaries (about 150 MB each);
- `ingest-20211006-ingest-1790680900` (35 MB; unsealed);
- the empty `ingest-20211005-ingest-1790672828`;
- `sealed-recovery-code-*`, `monday-launch`, `performance-session`;
- `session` clones, `/var/log` and `tmp/markets-measure`.

TRASH: the stale staged checkouts and worktrees, and the redundant transfer packs. Both were removed by the repo's
cleanup scripts, which kept all of their refusals.

## Archives (`frankie_box_archive_day.sh` + `.py`, ACTION=plan, then upload, then verify, one directory at a time)

Tool: the worktree `ingest-code/af168c2d99e8e9408546801deca5f3bbdeece2ac`. The `.sh` sha256 is `ffaf9b3f...`.

Layout: `s3://bento-568968024170-us-east-2-an/frankie/ingest/<day>/box-<dir>/` holds `objects/NNNN` (4 GiB pieces)
and `archive-manifest.json`.

Route:
- The script ran over SSM `AWS-RunShellScript`.
- `MAP_URL` was a presigned GET of a JSON map holding the presigned PUTs (`If-None-Match: *`) or GETs. The maps were
  written to `frankie-granite42-568968024170-us-east-1/box-runs/housekeeping-20261007/` and deleted at the end (20
  objects).
- `frankie_box_run.yml` was used for the 20251014 re-verify (run 820) and for `cleanup_cache` (run 824). GitHub
  Actions then failed: run 823 failed with no jobs and dispatches returned HTTP 500. The rest therefore went through
  SSM.

Every verify below read every object back and compared it with the local directory: VERIFIED (local same), with 0
problems.

| Day | Box directory | Files | Bytes | Objects + manifest | Verify receipt (box `/opt/frankie-box/receipts/`) |
|---|---|---|---|---|---|
| 20211005 | ingest-20211005-ingest-1790673001 | 7 | 26,538,139,354 | 13 | archive-20211005-20261007T170330Z.json |
| 20211006 | ingest-20211006-ingest-1790675371 | 9 | 28,897,432,287 | 16 | archive-20211006-20261007T172027Z.json |
| 20211012 | ingest-20211012-ingest-1790681387 | 9 | 17,541,018,111 | 14 | archive-20211012-20261007T171452Z.json |
| 20211013 | ingest-20211013-ingest-1790681387 | 9 | 16,619,924,650 | 13 | archive-20211013-20261007T171545Z.json |
| 20211020 | ingest-20211020-ingest-1790709584 | 8 | 16,161,051,974 | 12 | archive-20211020-20261007T171639Z.json (uploaded with `ALLOW_UNCONFORMED=1`: deferred conformance, no conformance.json) |
| 20221004 | ingest-20221004-ingest-1790681387 | 9 | 13,403,116,572 | 13 | archive-20221004-20261007T171813Z.json |
| 20221005 | ingest-20221005-ingest-1790681387 | 9 | 10,599,722,105 | 12 | archive-20221005-20261007T172020Z.json |
| 20241008 | ingest-20241008-ingest-1790687928 | 6 | 9,176,649,187 | 9 | archive-20241008-20261007T171236Z.json |
| 20241009 | ingest-20241009-ingest-1790687929 | 6 | 11,779,912,482 | 9 | archive-20241009-20261007T171400Z.json |
| 20241015 | ingest-20241015-ingest-1790688059 | 6 | 11,745,349,800 | 9 | archive-20241015-20261007T171459Z.json |
| 20241016 | ingest-20241016-ingest-1790688060 | 6 | 12,160,297,025 | 9 | archive-20241016-20261007T171555Z.json |
| 20251014 | ingest-20251014-ingest-1790706785 | 6 | 13,524,605,735 | 10 | archive-20251014-20261007T164419Z.json (archived 2026-09-29; re-verified tonight, run 820) |

Manifest sha256 values recorded at upload:

| Day | Manifest sha256 |
|---|---|
| 20211012 | `88869be8...` |
| 20211013 | `1b368606...` |
| 20211020 | `da94a3ca...` |
| 20221004 | `5ca1f775...` |
| 20221005 | `cc5730c5...` |
| 20241008 | `a9aa4f8f...` |
| 20241009 | `58fe8836...` |
| 20241015 | `3536f17f...` |
| 20241016 | `4b480a5a...` |
| 20251014 | `e02f8fd6...` |

Every verify receipt carries its `manifest_sha256`, and so does every removal receipt below.

Nothing was written under `frankie/box_archive/`; a listing of that prefix is empty.

## Deletions

1. **The 12 verified ingest directories above** (188,147,269,282 bytes).
   - `archive_day` has no delete action. This step was Greg's word for verified days only, carried out by a guarded
     one-off on the box (`/opt/frankie-box/tmp/hk-remove-verified.py`).
   - Each directory was removed only after these checks:
     - the latest verify receipt naming that directory has action verify, status verified, `local: same` and 0 problems;
     - no file in it changed after that receipt;
     - no process has a file open in it or its cwd inside it (checked through /proc);
     - it is not the gold day and not a gh-36571235912 KEEP ingest.
   - Each removal wrote `receipts/housekeeping-removal-<dir>-<utc>.json`, recording the file list, bytes, verify
     receipt and S3 prefix.
   - All 12 were removed and none refused.
2. **`frankie_box_cleanup_code.sh`**:
   - `MODE=plan` ran with the default `RECENT_HOURS=24`. Its `DELETE_SHA256` was `f11679dc...`.
   - `MODE=delete` then removed 43 checkouts (57.49 GB), 17 transfer directories (9.8 KB, already emptied of their
     packs) and 10 ingest worktrees (7.54 GB).
   - Receipt: `receipts/code-cleanup-20261007T172429Z.json`.
   - Kept:
     - the newest checkout `code/94f0d073...-36674311691-1` and its transfer directory;
     - the worktrees `83091a87`, `af168c2d`, `dcf97c7e` and `df0f8dec`. These are the archive tool's own worktree,
       which tonight's receipts name, plus the newest.
   - A `RECENT_HOURS=0` plan would also have removed `af168c2d` and three other worktrees; it was not used.
3. **`frankie_box_cleanup_cache.sh`** (workflow run 824,
   `CODE_ROOT=/opt/frankie-box/code/94f0d073...-36674311691-1/markets`):
   - removed the 18 redundant transfer `source.pack` files, each with its `cache-removal-receipt.json`;
   - one receipt read back shows 590,870,483 bytes, sha256 `4f593afa...`.
4. **Scripts not applicable:**
   - `cleanup_side`: there are no `.digest-side` directories on this box.
   - `cleanup_bedrock`: the Monday root's `.digest` scratch holds 5 saved tables and is KEEP.
   - `cleanup_swapfiles`: the swapfiles are on the worker (`/mnt/markets`), not this box.

## Added task: the 20231018 day file beside the sealed ingest

Ingest directory: `/opt/frankie-box/work/ingest-20231018-gh-36571235912-1` (sealed, `trading_day` 20231018). It is
the only 20231018 ingest on the box.

Old pair (receipt run `days-20260930-1-ext-20231018-a1`, a hard link of
`work/day-external/days-20260930-1-ext-20231018-a1/20231018/`, which was left untouched there):
- `day-external.json`: 28,498,591 bytes, sha256 `3b169f86b0b433528381e407012aac496c407e7d0cbf3f5adb7c3b87bbeccaf0`
- `day-external-receipt.json`: 25,597 bytes, sha256 `e64e2547...`

The old pair was moved aside in the same directory, never deleted:
- `day-external.json.superseded-20261007T172011Z`
- `day-external-receipt.json.superseded-20261007T172011Z`

New pair, fetched by presigned GET from `s3://bento-568968024170-us-east-2-an/frankie/day_external/20231018/`:
- `day-external.json`: 35,132,189 bytes, sha256 `fed74484967d5748ab6a8c3ae6e8b77b18e184c522de1a3a811758508ccb812c`
- `day-external-receipt.json`: 35,449 bytes, sha256 `51752d2c...`

The new pair matches:
- The day file's sha256 and bytes equal both its receipt (sha256 and bytes fields) and DAY_FILES_30_RETURN_20261007.md.
- The body's `trading_day` is 20231018.
- The files were placed under the attach step's names and layout (`DAY_FILE` and `DAY_FILE_RECEIPT` beside the
  sealed ingest). They are regular copies, not hard links, written as a `.part` and then renamed.
- `frankie_box_experiment.attached_day_file(<dir>)`, run on the box from worktree `af168c2d`, returned
  `(<dir>/day-external.json, fed74484..., None)`. That means `check_day_file` passed. Nothing else was run.

No other day was touched.

Slip: the first fetch attempt used presigned URLs I had assembled before the presign result came back. The URLs were
wrong, curl got HTTP 400, and `set -e` stopped the script before any file moved. The script was resent with the real
URLs.

## PySR (Greg: "Yes for pysr")

The install ran into `/opt/frankie-box/venv`, the venv the experiment uses: `frankie_box_experiment.sh` runs
`/opt/frankie-box/venv/bin/python` with `HOME=/root` and `PYTHONNOUSERSITE=1`, and there is no systemd sandbox.
`/opt/frankie-box/granite` was not touched (no file in it is newer than the install log).

- Command: `/opt/frankie-box/venv/bin/pip install pysr==1.5.10`, which returned rc 0. Then the first `import pysr`
  with `HOME=/root`, so juliapkg resolved and downloaded Julia and precompiled SymbolicRegression, PythonCall and
  OpenSSL_jll. Then the version checks.
  - Log: `/opt/frankie-box/tmp/hk-pysr-install.log` (17:14:21Z to 17:15:53Z).
  - pip freeze before and after: `tmp/hk-pip-freeze-{before,after}.txt`.
- Versions: pysr 1.5.10, juliacall 0.9.26, Julia **1.11.9**. These match the pin in `requirements.txt`.
  - juliapkg project: `/opt/frankie-box/venv/julia_env`
  - Julia executable: `/opt/frankie-box/venv/julia_env/pyjuliapkg/install/bin/julia`
  - Depot: `/root/.julia`
- pip added only these packages: juliacall 0.9.26, juliapkg 0.1.27, pysr 1.5.10, semver 3.1.0, tomli 2.5.0 and
  tomlkit 0.15.1. Nothing existing changed.
- Disk: the venv grew from 1.97 GB to 3.01 GB, of which `julia_env` is 1.04 GB, and `/root/.julia` is 0.34 GB. That
  is about 1.4 GB in total.
- Mismatch with the producer: none found.
  - `frankie_box_experiment_search.py` imports `pysr` through `odcore.symbolic._regressor` in the same venv, with
    the same `HOME`, so it finds the same juliapkg project and depot.
  - There was no fit and no producer run, so whether a fit works at runtime is UNVERIFIED.
- Deviation: the install was started while the archive verifies were still running, not after all cleanup.

## R2 verdict

The main box has 1,425.5 GB free of 2,129.0 GB, after PySR's 1.4 GB. The largest S3-complete day directory on the
box is 14.7 GB (20231011), and the Monday root's whole derived tree is 427 GB. Space is therefore not a constraint
for running all days on this box.

The R2 figure "19 GB free of 116 GB" belongs to the worker box `i-0d17573dbce871520`, which was not touched tonight.
That number still stands for the worker.

## Account calls (all through the Aws connector, apart from GitHub)

- **EC2:** DescribeInstances, CreateTags (KeepRunning true at start; false at end), StartInstances, StopInstances,
  DescribeVolumes.
- **SSM:**
  - DescribeInstanceInformation.
  - SendCommand (AWS-RunShellScript) for: the inventory, archive plan, upload and verify per day, PySR, the
    day-file swap, the guarded removal, cleanup_code plan and delete, and disk_usage.
  - GetCommandInvocation.
- **S3:**
  - ListObjectsV2 on the bento ingest prefixes and on `frankie/box_archive/`.
  - PutObject of the map files to frankie-granite42 `box-runs/housekeeping-20261007/` (SSE AES256).
  - DeleteObjects of those 20 map files.
  - Presigned PUT and GET URLs through `get_presigned_url`.
- **STS:** GetCallerIdentity.
- **GitHub (`frankie_box_run.yml`):**
  - runs 820 (20251014 re-verify), 821, 822 and 824 (cleanup_cache);
  - run 823 failed with no jobs, and later dispatches returned HTTP 500.

Everything here is a runtime record of housekeeping only. No model or data run happened.
