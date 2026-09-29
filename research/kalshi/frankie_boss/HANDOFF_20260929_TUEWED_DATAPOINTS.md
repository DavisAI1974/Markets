# HANDOFF 2026-09-29 (~12:00Z): Tue/Wed running, Frankie's 13 data points, the 31 days, Databento, disk and CPUs

Branch `claude/frankie-monday-cycle-0-urozez` (no merge base with the trunk). Read with
`DROP_IN_20260929_TUEWED_DATAPOINTS.md` (the next chat's work list). Earlier today:
`HANDOFF_20260929_EXPERIMENT_BUILD.md` (its later sections: HOLD, next two pairs).

Greg closed this chat at ~11:55Z: "we need to create handoff and drop in because you have become extremely slow ...
We'll continue box work in next chat."

## What is running (read these first)

| What | Where | State at ~11:55Z |
|---|---|---|
| Tue 20211005 ingest | box `work/ingest-20211005-ingest-1790673001` | **SEALED 11:22Z**: 2,104,864 records, journal 4,209,728 entries, inline conformance passed; opening book from Monday's sealed recovery `work/sealed-recovery-35796793428/builder-checkpoint.c15.json`. 25 GB on disk. |
| Wed 20211006 ingest | box `work/ingest-20211006-ingest-1790675371`, GitHub run 36551601815 | ingesting, 1.81M / 2,304,995 records; **deferred verify**: needs `frankie_box_ingest_block.sh ACTION=conform DIRECTORY=<that dir>` after it seals. Warm-started its own opening book. |
| Duplicate Wednesday (stopped) | box `work/ingest-20211006-ingest-1790680900` (34 MB partial) | started by the old chained run 36547330372 52 s before it was cancelled; the process died with the cancel. Worthless; delete with the failed runs. |
| Orchestrator run `pairs2-20260929-1` (STAGES=fetch,ingest) | box `work/experiment/pairs2-20260929-1`, code `38182d7c` staged at `/opt/frankie-box/code/38182d7c8999ba74f3b6a4fad13866e55e31f422-36561739665-1/markets` | fetch done; ingesting 20211012 (240k/1,477,942), 20211013 (210k/1,341,217), 20221004 (320k/1,640,652), 20221005 (290k/1,316,445); deferred verify (each needs ACTION=conform later). Its plan.json was made BEFORE the classroom default changed: classroom_arm = 20211012,20211013 only. |
| Databento Oct 2024 + Oct 2025 | GitHub run 36564541947 (mode curve_days, ceiling $70) | running; skips days already held |
| Free historical sources for the 30 days | GitHub run 36557302661 (mode day_history) | still in its fetch step at 11:55Z; uploads only at the end to `s3://bento-568968024170-us-east-2-an/frankie/day_history/36557302661/`. It predates Wed 20211020 (needs its own fetch). |
| Old-data inventory (read-only) | an agent of the closing chat | writes `research/kalshi/frankie_boss/BOX_DATA_INVENTORY_20260929.md` UNCOMMITTED in the closing chat's container; if it is not on the branch, redo it (see drop-in). |
| Check-ins | trig_017VdmDUNZYokbSXZJU5sRvx (12:14Z, pulls) fires into the CLOSING session only | the next chat must re-arm its own |

## Done this chat (commits on the branch, all pushed, [skip ci])
- **Frankie's data wish list** (`FRANKIE_DATA_WISHLIST_20260929.md`, `operations/frankie_data_wishlist.py`): Frankie has
  no model seat, so his brain (ng_brain.json, 90 plays) answers: what his plays depend on, counted by source family.
  Greg's set = **13 points**: COT managed-money percentiles 1y/3y + WoW change + ICE LD1 1y; forecast gw_hdd (MOS);
  model disagreement; EIA-930 US48 wind and gas burn; sessions since expiry (squeeze: **DEFERRED by Greg**, not
  dropped); observed gw_hdd; **EIA weekly storage**; **storage estimate vs actual**; **the futures curve shape**.
  Rules (in `SPEC-scientific-teacher.md` "Data access"): one day file per trading day beside the sealed ingest, every
  reader of the ingest sees it (Frankie, BOSS teacher, scientific teacher/search, classroom, Jev), native resolution,
  publication time on every value, **time-only leak guard** (Greg: "I'm not concerned about him having trade curves"),
  missing values listed with day and reason; attached permanently to the day (S3 key, brain attachment) even for
  readers not wired yet.
- **The 5-year MBO pull is the FRONT MONTH only** (`NG.v.0`, one instrument per partition, full depth). Other contract
  months come from the new NG.FUT parent pull (`nymex/ng_fut_parent_v0/<schema>/native/`).
- **Day selection** (`DAY_SELECTION_20260929.md`, `blocks/DAY_SELECTION_CANDIDATES_20260929.json`): 30 days + Wed
  20211020 (Greg: pair the lone Tue 20211019) = **31 days**. Tue/Wed 20211005/06 are days 1-2 of them.
- **History plan** (`HISTORICAL_DATA_PLAN_20260929.md`), fetch driver `operations/fetch_day_history.py`, curve pull
  `operations/pull_curve_days.py` (NG.FUT parent; comma list of ranges; skips days held per schema; all jobs submitted
  at once; quote-only mode). Both run as MODES of `.github/workflows/ng_historical_mbo_5y_to_s3_20260820.yml`
  (`mode=five_year|curve_days|day_history`): a brand-new workflow file 404s on dispatch until it has run once.
- **Day file** (`operations/frankie_day_external.py`: FRANKIE_DAY_EXTERNAL_V1, `AsOfReader`, `check_day_file`,
  `search_series`; box step `deploy/aws/box/frankie_box_day_external.sh`): wired into the search, the ROOT receipt,
  the day-data export and a brain attachment.
- **Classroom and teachers see the 13 points** (swap, no pinned file edited): `dipole_classroom_external.py`,
  `dipole_classroom_v2.py`, `deploy/aws/box/frankie_box_classroom_external_code.py`,
  `frankie_box_experiment_classroom_v2.py/.sh` (use V2 for every day), teacher step reads the day file, Jev's relay
  and `clm_sidecar/sit_in.py` carry the external part. The V1 19/171 grade is unchanged.
- **The experiment directive** (`knowledge/EXPERIMENT_DIRECTIVE_V1.json`, Greg: "We're trying to make correlations and
  the best trade signals we can"): in the V2 classroom request (Frankie and Jev), Frankie's brain entry (included),
  and the teacher, search and orchestrator records.
- **Orchestrator** (`deploy/aws/box/frankie_box_experiment.py`): Tue/Wed **pairing** (`pair_units`: same week, then
  across weeks, then singles; days run unit by unit; `--parallel-days 4` = two pairs); new stages
  fetch, ingest, **external**, root, teacher, **classroom** (V2, PREVIOUS chained), **jev** (material; the Pod is a
  separate workflow step), data, search, lessons; `ACTION=plan` prints the presign string; **classroom on every day by
  default** (Greg: "Just run every pair will get teach and class", `--classroom-arm-cycle 5/5`).
- **Cleanup**: `frankie_box_cleanup_side.sh` takes `SCRATCHES=` (abandoned `.digest-<hex>` scratches that saved no
  table). Ran: removed 5 abandoned Monday digest scratches + 3 empty side dirs (~68 GB); cache cleanup ran (pip cache
  purged; the 80 `code/transfer-*` packs were NOT removed, cause not found). Free: 173 GB -> ~258 GB.
- **Keys**: Greg pasted the AWS pair for the `Claude` IAM user (STS verified, account ...4170). They lived in
  `~/.config/markets/env` + `~/.aws/credentials` of the closing container only; the next chat needs them again. With
  them, box probes run directly over SSM (a 20-line boto3 `send_command` / `get_command_invocation` helper on
  i-035994afa8bdf66a5, AWS-RunShellScript, read-only commands) instead of a GitHub dispatch per probe.

## Databento (Greg's plan, exact)
1. The 30 (31) days: **DONE** 11:35:58Z. 47 UTC partitions x definition, statistics, mbo; mbo 11.64 GB; quoted $50.76.
2. October 2024 + October 2025, minus days held: RUNNING (run 36564541947, ceiling $70).
3. HOLD until Greg says: October 2021-2023 (the five Octobers quoted $136.14 together) and the full
   2021-08-20..2026-08-20 MBO ($1,602.08). Definitions and statistics are $0 for every range.
4. When the last file lands, tell Greg: he cancels the Databento subscription then (the pulls may be $0 in-subscription;
   the key is the GitHub secret `MARKETS_NG_LIVE_MBO`).

## Greg's standing calls from this chat
- Tue/Wed: never paused mid-process; after each ingest finishes, its ROOT/teacher/classroom/Jev WAIT until its 13
  points are on S3 and its day file is attached ("no point in not taking full advantage of this run").
- "Just do the rest of the 30 days and pause other jobs until it's done": my reading (NOT confirmed): ingest all 30/31
  days, other box jobs wait until then.
- Every pair gets teacher and classroom. Jev sits in (blind outside student, his own Pod; go given for Tue/Wed).
- Old data on the box: "Keep important data that's useful from older runs but I'm sure there's duplicates and failed
  runs are worthless", "zip older run data that we keep", "we can also delete failed runs that weren't used", move
  the zipped data off the box (he asked git or the smallest box; git cannot hold data (D34, GitHub 100 MB limit);
  recommended S3, which needs a one-time upload permission for the box: HIS GO PENDING).
- CPUs: "We need more CPUs for 4 pairs and we have a 32 cpu box doing nothing." EC2 today shows only:
  i-035994afa8bdf66a5 r7i.8xlarge 32 vCPU RUNNING (the box), i-08cee7171c0a76a04 r6i.2xlarge 8 vCPU Linux STOPPED
  (us-east-2, 300 GB), i-0e90ee6110ef609aa **r7i.4xlarge** 16 vCPU **Windows** STOPPED (us-east-2, 120+250 GB).
  CLAUDE.md says the Windows native host was resized to r7i.8xlarge; EC2 says 4xlarge. Ask Greg which box he means
  before starting anything (starting a box is a go).

## Open items (in the drop-in's order)
See the drop-in. Known defects: the orchestrator's plan prints partition keys without the S3 segment folder
(`native/<name>` instead of `native/20211001_20211101/<name>`); the free fetch lacks 20211020; storage-estimate
numbers are not extracted from the archived pages; Frankie's code answers TEACH only and the mastery ramp moves to
GUIDED after two mastered TEACH classroom days (the next classroom day after Tue/Wed if both are mastered: build GUIDED
answers or hold at TEACH, Greg's call); the BOSS teacher's answer turn of the three-way conference (spec item 5) is not
built; Jev's material may exceed 8 x 4 MB relay slots.
