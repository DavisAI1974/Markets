# Day selection for the experiment: 30 closely matched Tuesdays and Wednesdays (2026-09-29)

Greg, 2026-09-29, verbatim: "we have to start picking closely matched Tue and Wed. We can use the last week of Sept
through this year. I'd like to have 30 days when we're done." and "The historical data days should be in aws."
Greg's answer the same day (relayed by the coordinator) to the wall question: use 2021-2026; the window is the last week
of September through October of every year the data covers, all years treated alike for selection; the 30 include
Tue 2021-10-05 and Wed 2021-10-06 (days 1 and 2, being ingested tonight).

Status: PROPOSAL. Nothing dispatched, nothing ingested, no raw byte read. Built in this change (not run):
`operations/day_selection_candidates.py` (the table below, from committed metadata), its output
`blocks/DAY_SELECTION_CANDIDATES_20260929.json`, the box script `deploy/aws/box/frankie_box_day_facts.py/.sh` (the facts
that need the raw files, plus the staged block manifests), a `halt_utc_hour` argument on
`operations/stage_block_sources.count_records` (default 21, unchanged behaviour), and the script's own lock in
`frankie_box_run.yml` (`box-facts-<instance>`).

## 1. What the data covers

- The 5-year NG MBO pull on S3 (`bento-568968024170-us-east-2-an`, us-east-2), committed object manifest
  `research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json`: 1,565 UTC partitions,
  `glbx-mdp3-20210820` .. `glbx-mdp3-20260819`, symbol `NG.v.0` (volume-continuous: one instrument per partition,
  chosen by volume). Every object carries key, bytes and sha256 and was S3-head-validated.
- **2026: nothing in the window is on S3.** The pull ends 2026-08-19; late September 2026 is partly this week and October
  2026 has not happened. Getting 2026-09-22/23 (the only 2026 days of the window that exist) onto S3 needs a Databento
  pull (`ng_historical_mbo_5y_to_s3_20260820.yml` is the only workflow holding the key), which this work does not touch,
  and both are in the October contract's roll window anyway (table).
- The Oct 2021 block is also staged under `frankie/block_20211004_20211006/sources/` (committed
  `blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json`).

## 2. A trading day, and why a Tuesday needs two partitions

Tuesday D opens 18:00 ET Monday and halts 17:00 ET Tuesday (21:00Z: every day in the window is under EDT). Its records
are the TAIL of the Monday partition (at or after 21:00Z) and the HEAD of the Tuesday partition (before 21:00Z); a
Wednesday is the Tuesday partition's tail plus its own head. So a week's Tue+Wed pair needs the Mon, Tue and Wed
partitions; a lone Tuesday needs Mon and Tue. The measured tail/head counts come from staging (section 5), never from
bytes. For reference, the four partitions already staged run 17.07-17.14 bytes per record (57,027 / 1,994,358 /
2,111,930 / 2,308,160 records); that is context, not a count.

## 3. "Closely matched": the facts, the tolerances, and which are filters

Proposed from the data, per day, nothing pooled. Every tolerance is an argument of `day_selection_candidates.py`, so
Greg can change it and re-run (the JSON and this table re-derive).

Filters (a day failing any is listed OUT with its reason):
1. Weekday Tuesday or Wednesday; window 22 Sep - 31 Oct (`--window-start 0922 --window-end 1031`).
2. Both partitions on S3 (the committed manifest).
3. **Outside the roll window**: not within 5 business days before to 1 business day after the last trade date (LTD) of
   the contract expiring nearest to it (`--pre-ltd 5 --post-ltd 1`). LTD = 3 business days before the first of the
   delivery month (`contract_structure.computed_expiry`); no NYMEX holiday falls in or near the window (Labor Day is
   early September, Veterans Day is 11 November; Columbus Day trades and its partitions are full size). Why 5 before:
   the thinnest partitions in the table sit 2-4 business days before an LTD (2022-10-25 6.0 MB, 2023-10-24 6.0 MB,
   2025-09-24 6.2 MB, 2025-09-23 8.4 MB, 2021-09-24 6.7 MB) - the volume-continuous series still on the fading
   contract - so a narrower window would admit a thin, dying-contract day.
4. **Front contract = the November contract** (`--front-month X`), as for days 1 and 2 (NGX21, 15-16 business days to
   its LTD). This is what drops 2023-10-31 (front NGZ23, 2 days after the November expiry).
5. No holiday or shortened session (none in the window).

Reported per day, NOT filters (for Greg to set a tolerance on, if he wants one):
- Business days to the front LTD (proposed days: 6 to 21; days 1-2: 16, 15).
- The week pair: whether the Tue and Wed of that week both pass (14 pairs; 2 lone Tuesdays).
- Own-partition bytes and the ratio to day 1 (Tue 2021-10-05, 36,192,430 bytes), each day on its own: proposed days run
  0.356 (2023-10-18) to 1.093 (day 2). October 2021 is the most active month in the window; 2023 and 2024 the least.
  A byte ratio is an activity proxy only; the measured record and trade counts replace it once the box facts exist.
- Committed calendar events: October 2025 = the US federal shutdown (CFTC COT publication suspended 2025-10-01 to
  11-12; CLAUDE.md S97), on the six proposed October 2025 days.
- The spec role label (discovery 2021-2023 / confirmation 2024-2025), kept as a label only per Greg's answer.

## 4. The proposed 30 (exactly 30 pass every filter)

| # | Days | Year | Front | BD to LTD | Unit |
|---|---|---|---|---|---|
| 1-2 | Tue 20211005, Wed 20211006 (days 1 and 2) | 2021 | NGX21 | 16, 15 | pair |
| 3-4 | Tue 20211012, Wed 20211013 | 2021 | NGX21 | 11, 10 | pair |
| 5 | Tue 20211019 | 2021 | NGX21 | 6 | lone (Wed 10-20 is at -5) |
| 6-11 | 20221004/05, 20221011/12, 20221018/19 | 2022 | NGX22 | 17/16, 12/11, 7/6 | 3 pairs |
| 12-17 | 20231003/04, 20231010/11, 20231017/18 | 2023 | NGX23 | 18/17, 13/12, 8/7 | 3 pairs |
| 18-23 | 20241001/02, 20241008/09, 20241015/16 | 2024 | NGX24 | 20/19, 15/14, 10/9 | 3 pairs |
| 24-29 | 20250930 + 20251001, 20251007/08, 20251014/15 | 2025 | NGX25 | 21/20, 16/15, 11/10 | 3 pairs |
| 30 | Tue 20251021 | 2025 | NGX25 | 6 | lone (Wed 10-22 is at -5) |

17 of the 30 are in 2021-2023 and 13 in 2024-2025; one (2025-09-30) is in the last week of September.
The alternate: 2023-10-31, the one candidate that fails a single filter (front NGZ23, 2 business days after the
November LTD); every other excluded day is in a roll window.
Two proposed days deserve the box check first: 2021-10-19 and 2025-10-21 sit 6 business days before the November LTD,
one day outside the window, and the 2025-10-20..23 partitions are large (29-32 MB): if the box facts show the
volume-continuous series already on the December contract there (a different instrument id in the tail and head, or
from the November one), the day is flagged and Greg decides.

## 5. Every candidate, per day (from `blocks/DAY_SELECTION_CANDIDATES_20260929.json`)

BD = business days; "nearest LTD" is signed (+ after, - before). Bytes are the committed object sizes.

| Day | Wd | Spec role | Front | BD to front LTD | BD from nearest LTD | Tail partition bytes | Own partition bytes | Own vs day 1 | Week pair | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 20210922 | Wed | discovery | NGV21 | 4 | -4 (NGV21 2021-09-28) | 17,092,095 | 12,459,020 | 0.344 | no | out: roll window -4; front NGV21 |
| 20210928 | Tue | discovery | NGV21 | 0 | +0 (NGV21 2021-09-28) | 23,542,089 | 51,542,823 | 1.424 | no | out: roll window +0 (the October LTD itself); front NGV21 |
| 20210929 | Wed | discovery | NGX21 | 20 | +1 (NGV21 2021-09-28) | 51,542,823 | 31,251,732 | 0.863 | no | out: roll window +1 |
| 20211005 | Tue | discovery | NGX21 | 16 | +5 (NGV21 2021-09-28) | 34,300,424 | 36,192,430 | 1.0 | yes | PROPOSED (day 1, already in) |
| 20211006 | Wed | discovery | NGX21 | 15 | +6 (NGV21 2021-09-28) | 36,192,430 | 39,566,060 | 1.093 | yes | PROPOSED (day 2, already in) |
| 20211012 | Tue | discovery | NGX21 | 11 | +10 (NGV21 2021-09-28) | 24,934,018 | 25,309,137 | 0.699 | yes | PROPOSED |
| 20211013 | Wed | discovery | NGX21 | 10 | -10 (NGX21 2021-10-27) | 25,309,137 | 23,294,893 | 0.644 | yes | PROPOSED |
| 20211019 | Tue | discovery | NGX21 | 6 | -6 (NGX21 2021-10-27) | 25,084,280 | 21,910,551 | 0.605 | no | PROPOSED |
| 20211020 | Wed | discovery | NGX21 | 5 | -5 (NGX21 2021-10-27) | 21,910,551 | 22,735,364 | 0.628 | no | out: roll window -5 |
| 20211026 | Tue | discovery | NGX21 | 1 | -1 (NGX21 2021-10-27) | 20,631,481 | 24,918,228 | 0.688 | no | out: roll window -1 |
| 20211027 | Wed | discovery | NGX21 | 0 | +0 (NGX21 2021-10-27) | 24,918,228 | 27,371,146 | 0.756 | no | out: roll window +0 |
| 20220927 | Tue | discovery | NGV22 | 1 | -1 (NGV22 2022-09-28) | 22,607,228 | 23,430,627 | 0.647 | no | out: roll window -1; front NGV22 |
| 20220928 | Wed | discovery | NGV22 | 0 | +0 (NGV22 2022-09-28) | 23,430,627 | 25,202,848 | 0.696 | no | out: roll window +0; front NGV22 |
| 20221004 | Tue | discovery | NGX22 | 17 | +4 (NGV22 2022-09-28) | 25,375,981 | 28,802,266 | 0.796 | yes | PROPOSED |
| 20221005 | Wed | discovery | NGX22 | 16 | +5 (NGV22 2022-09-28) | 28,802,266 | 23,163,109 | 0.64 | yes | PROPOSED |
| 20221011 | Tue | discovery | NGX22 | 12 | +9 (NGV22 2022-09-28) | 21,770,634 | 22,761,904 | 0.629 | yes | PROPOSED |
| 20221012 | Wed | discovery | NGX22 | 11 | +10 (NGV22 2022-09-28) | 22,761,904 | 21,225,960 | 0.586 | yes | PROPOSED |
| 20221018 | Tue | discovery | NGX22 | 7 | -7 (NGX22 2022-10-27) | 21,933,619 | 24,542,624 | 0.678 | yes | PROPOSED |
| 20221019 | Wed | discovery | NGX22 | 6 | -6 (NGX22 2022-10-27) | 24,542,624 | 20,410,005 | 0.564 | yes | PROPOSED |
| 20221025 | Tue | discovery | NGX22 | 2 | -2 (NGX22 2022-10-27) | 14,923,931 | 6,030,792 | 0.167 | no | out: roll window -2 (thin partition) |
| 20221026 | Wed | discovery | NGX22 | 1 | -1 (NGX22 2022-10-27) | 6,030,792 | 21,393,493 | 0.591 | no | out: roll window -1 |
| 20230926 | Tue | discovery | NGV23 | 1 | -1 (NGV23 2023-09-27) | 12,442,762 | 15,527,135 | 0.429 | no | out: roll window -1; front NGV23 |
| 20230927 | Wed | discovery | NGV23 | 0 | +0 (NGV23 2023-09-27) | 15,527,135 | 14,657,243 | 0.405 | no | out: roll window +0; front NGV23 |
| 20231003 | Tue | discovery | NGX23 | 18 | +4 (NGV23 2023-09-27) | 13,590,194 | 14,701,450 | 0.406 | yes | PROPOSED |
| 20231004 | Wed | discovery | NGX23 | 17 | +5 (NGV23 2023-09-27) | 14,701,450 | 16,033,680 | 0.443 | yes | PROPOSED |
| 20231010 | Tue | discovery | NGX23 | 13 | +9 (NGV23 2023-09-27) | 18,621,395 | 16,234,972 | 0.449 | yes | PROPOSED |
| 20231011 | Wed | discovery | NGX23 | 12 | +10 (NGV23 2023-09-27) | 16,234,972 | 20,324,989 | 0.562 | yes | PROPOSED |
| 20231017 | Tue | discovery | NGX23 | 8 | -8 (NGX23 2023-10-27) | 15,401,414 | 14,484,156 | 0.4 | yes | PROPOSED |
| 20231018 | Wed | discovery | NGX23 | 7 | -7 (NGX23 2023-10-27) | 14,484,156 | 12,867,663 | 0.356 | yes | PROPOSED |
| 20231024 | Tue | discovery | NGX23 | 3 | -3 (NGX23 2023-10-27) | 11,950,893 | 5,969,278 | 0.165 | no | out: roll window -3 (thin partition) |
| 20231025 | Wed | discovery | NGX23 | 2 | -2 (NGX23 2023-10-27) | 5,969,278 | 12,276,270 | 0.339 | no | out: roll window -2 |
| 20231031 | Tue | discovery | NGZ23 | 20 | +2 (NGX23 2023-10-27) | 14,888,651 | 24,796,357 | 0.685 | no | out: front NGZ23 (the only failed filter; the alternate) |
| 20240924 | Tue | confirmation | NGV24 | 2 | -2 (NGV24 2024-09-26) | 22,903,088 | 19,053,772 | 0.526 | no | out: roll window -2; front NGV24 |
| 20240925 | Wed | confirmation | NGV24 | 1 | -1 (NGV24 2024-09-26) | 19,053,772 | 18,948,486 | 0.524 | no | out: roll window -1; front NGV24 |
| 20241001 | Tue | confirmation | NGX24 | 20 | +3 (NGV24 2024-09-26) | 20,360,768 | 20,509,128 | 0.567 | yes | PROPOSED |
| 20241002 | Wed | confirmation | NGX24 | 19 | +4 (NGV24 2024-09-26) | 20,509,128 | 18,569,552 | 0.513 | yes | PROPOSED |
| 20241008 | Tue | confirmation | NGX24 | 15 | +8 (NGV24 2024-09-26) | 17,224,899 | 14,620,557 | 0.404 | yes | PROPOSED |
| 20241009 | Wed | confirmation | NGX24 | 14 | +9 (NGV24 2024-09-26) | 14,620,557 | 16,871,730 | 0.466 | yes | PROPOSED |
| 20241015 | Tue | confirmation | NGX24 | 10 | -10 (NGX24 2024-10-29) | 13,167,179 | 16,554,619 | 0.457 | yes | PROPOSED |
| 20241016 | Wed | confirmation | NGX24 | 9 | -9 (NGX24 2024-10-29) | 16,554,619 | 16,653,944 | 0.46 | yes | PROPOSED |
| 20241022 | Tue | confirmation | NGX24 | 5 | -5 (NGX24 2024-10-29) | 17,464,032 | 22,749,632 | 0.629 | no | out: roll window -5 |
| 20241023 | Wed | confirmation | NGX24 | 4 | -4 (NGX24 2024-10-29) | 22,749,632 | 18,717,892 | 0.517 | no | out: roll window -4 |
| 20241029 | Tue | confirmation | NGX24 | 0 | +0 (NGX24 2024-10-29) | 24,923,992 | 17,614,310 | 0.487 | no | out: roll window +0 |
| 20241030 | Wed | confirmation | NGZ24 | 20 | +1 (NGX24 2024-10-29) | 17,614,310 | 17,728,225 | 0.49 | no | out: roll window +1; front NGZ24 |
| 20250923 | Tue | confirmation | NGV25 | 3 | -3 (NGV25 2025-09-26) | 15,707,887 | 8,397,915 | 0.232 | no | out: roll window -3 (thin); front NGV25 |
| 20250924 | Wed | confirmation | NGV25 | 2 | -2 (NGV25 2025-09-26) | 8,397,915 | 6,173,344 | 0.171 | no | out: roll window -2 (thin); front NGV25 |
| 20250930 | Tue | confirmation | NGX25 | 21 | +2 (NGV25 2025-09-26) | 19,141,301 | 19,045,003 | 0.526 | yes | PROPOSED |
| 20251001 | Wed | confirmation | NGX25 | 20 | +3 (NGV25 2025-09-26) | 19,045,003 | 25,685,127 | 0.71 | yes | PROPOSED (shutdown month) |
| 20251007 | Tue | confirmation | NGX25 | 16 | +7 (NGV25 2025-09-26) | 21,667,445 | 24,241,781 | 0.67 | yes | PROPOSED (shutdown month) |
| 20251008 | Wed | confirmation | NGX25 | 15 | +8 (NGV25 2025-09-26) | 24,241,781 | 26,681,679 | 0.737 | yes | PROPOSED (shutdown month) |
| 20251014 | Tue | confirmation | NGX25 | 11 | -11 (NGX25 2025-10-29) | 17,671,247 | 19,550,137 | 0.54 | yes | PROPOSED (shutdown month) |
| 20251015 | Wed | confirmation | NGX25 | 10 | -10 (NGX25 2025-10-29) | 19,550,137 | 17,766,902 | 0.491 | yes | PROPOSED (shutdown month) |
| 20251021 | Tue | confirmation | NGX25 | 6 | -6 (NGX25 2025-10-29) | 29,534,696 | 32,271,843 | 0.892 | no | PROPOSED (shutdown month) |
| 20251022 | Wed | confirmation | NGX25 | 5 | -5 (NGX25 2025-10-29) | 32,271,843 | 31,938,757 | 0.882 | no | out: roll window -5 |
| 20251028 | Tue | confirmation | NGX25 | 1 | -1 (NGX25 2025-10-29) | 28,044,328 | 28,071,472 | 0.776 | no | out: roll window -1 |
| 20251029 | Wed | confirmation | NGX25 | 0 | +0 (NGX25 2025-10-29) | 28,071,472 | 23,506,353 | 0.649 | no | out: roll window +0 |
| 2026 (12 days) | | outside | NGV26/NGX26 | | | - | - | - | no | out: not on S3 (pull ends 20260819); 09-22/23, 10-21, 10-27/28 also in a roll window |

## 6. What the table cannot say without the raw files, and the box script that measures it

Not in any committed file for these days (searched: blocks/, the NG exhaustion records, month_characterize outputs,
contract_structure stores; only Oct 2021 has committed counts): the trading day's record count, trade count and volume,
price level and range, activity per hour, the instrument id in each part (roll continuity), whether the tail partition
opens with Databento's F_SNAPSHOT book (the warm start), large gaps and bad-timestamp flags.

`deploy/aws/box/frankie_box_day_facts.sh` (+ `.py`) measures them per day and, in the same pass, writes the staged
BLOCK manifest of every new block with `stage_block_sources.count_records` (the staging tool's function, unchanged):

- Partitions: presigned GETs of the archive keys from the committed canonical manifest, sha256 + size checked, saved as
  `/opt/frankie-box/data/block_<block>/glbx-mdp3-<day>.mbo.dbn.zst` (the directory `frankie_box_ingest_block.sh
  ACTION=fetch` reads, so a later ingest finds or hard-links them; nothing re-downloaded). A file already on the box
  under any `data/block_*` with the same sha256 is hard-linked. A different file at a destination is never overwritten.
- Output: `/opt/frankie-box/work/day-facts/<RUN>/days/<day>.json` (FRANKIE_DAY_FACTS_V1),
  `blocks/BLOCK_<block>_SOURCE_MANIFEST.json`, `receipt.json`; all printed whole into the job log.
- Blocks (one per week): 20211004_20211006 (days 1-2: facts only, their manifests are committed), 20211011_20211013,
  20211018_20211019, 20221003_20221005, 20221010_20221012, 20221017_20221019, 20231002_20231004, 20231009_20231011,
  20231016_20231018, 20240930_20241002, 20241007_20241009, 20241014_20241016, 20250929_20251001, 20251006_20251008,
  20251013_20251015, 20251020_20251021. 46 partitions, 990,627,345 bytes.
- 2024-2025 days: the script's `CONFIRMATION` input is `refuse` (default) or `staging-only` (record counts at the halt
  only, which is what a manifest needs, no price/trade/book fact). Greg's answer lifts the hold for selection; a mode
  that runs the full facts pass on 2024-2025 days was NOT built in this change (the session's permission check stopped
  that edit). Until Claude/Greg add it, dispatch with `CONFIRMATION=staging-only`: the 2021-2023 days get every fact,
  the 2024-2025 days get their block manifests (so they can be derived and ingested) but no facts, and their
  cross-partition instrument continuity is not checked (count_records reports the NUMBER of instruments per partition,
  1, not the id).

Exact dispatch (at a lull, on Greg's go; after Claude merges this commit into `claude/frankie-monday-cycle-0-urozez` and
pushes; box `i-035994afa8bdf66a5` must be running):

1. Stage the tip: `frankie_box_stage_code.sh ACTION=stage` as usual (gives `/opt/frankie-box/code/<sha>-<run>-1/markets`),
   or reuse an ingest worktree `/opt/frankie-box/ingest-code/<sha>` if an ingest was dispatched from the same commit.
2. `frankie_box_run.yml` with
   - `script`: `deploy/aws/box/frankie_box_day_facts.sh`
   - `variables`: `CODE_ROOT=<the staged checkout> RUN=select-20260929-1 WORKERS=6 CONFIRMATION=staging-only DAYS=20211005,20211006,20211012,20211013,20211019,20221004,20221005,20221011,20221012,20221018,20221019,20231003,20231004,20231010,20231011,20231017,20231018,20241001,20241002,20241008,20241009,20241015,20241016,20250930,20251001,20251007,20251008,20251014,20251015,20251021`
   - `timeout`: `3600`; `presign_hours`: `4`
   - `presign`: the `presign` string in `blocks/DAY_SELECTION_CANDIDATES_20260929.json` (46 `bucket/key` items,
     4,921 characters; the first is `bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/native/20211001_20211101/glbx-mdp3-20211004.mbo.dbn.zst`).
   It takes its own lock (`box-facts-<instance>`), runs under `nice`, and can run beside tonight's ingest.
3. Probe: `frankie_box_read_log.sh MODE=tail FILE=work/day-facts/select-20260929-1/receipt.json`; read each block
   manifest back whole with `MODE=receipt FILE=work/day-facts/select-20260929-1/blocks/BLOCK_<block>_SOURCE_MANIFEST.json`
   (or from the job log).

Cost: S3 GET transfer us-east-2 to the us-east-1 box, about 0.99 GB at the inter-region rate (about $0.02), plus
request charges (negligible); box time on a box that is already billing (two decode passes of 46 partitions of
2.0-2.3 M records each, 6 workers: minutes, not measured); the dispatch's runner minutes. Nothing touches Databento.

## 7. Staging plan, day by day (what each day needs before it can be ingested)

A day is ingestible when `research/kalshi/frankie_boss/blocks/BLOCK_<day>_SOURCE_MANIFEST.json` is committed. Days 1 and 2
have theirs. For the other 28:

1. The box run above writes 15 new block manifests (BOSS_BLOCK_SOURCE_MANIFEST_V1, the body shape of
   `stage_block_sources.main()`, counts from its `count_records`). Differences, declared in the body: `prefix` /
   `archive_prefix` = `nymex/ng_mbo_5y_v0/native` and each session carries `archive_key` (the object's full key),
   because the box cannot copy objects under `frankie/block_*/sources` (its role writes nothing to S3); `staged_by`
   names the script. `ingest_block_sources.py` reads `prefix` only in its `--fetch` path, which the box never uses (the
   box fetches by the presigned map, matched on the member file name). A block whose partitions straddle two archive
   segments (20240930_20241002, 20250929_20251001) is fine for that reason.
2. In the container (no AWS): copy each block manifest into `research/kalshi/frankie_boss/blocks/`, recompute
   `raw_mbo_source_manifest.manifest_hash` and compare, then derive each day:
   `python3.12 research/kalshi/frankie_boss/operations/derive_trading_day_manifest.py --block-manifest research/kalshi/frankie_boss/blocks/BLOCK_<block>_SOURCE_MANIFEST.json --trading-day <day> --out research/kalshi/frankie_boss/blocks/BLOCK_<day>_SOURCE_MANIFEST.json`
   Each Tuesday/Wednesday gets a `tail_members` entry (skip = the prior day's pre-halt records) and a
   `partial_members` take, exactly as 20211005/20211006 did. Commit.
3. Ingest (each on Greg's go): the partitions are already on the box, so `ACTION=fetch` links them; days warm their own
   opening book (no prior-day ingest needed since the "No Monday dependency" build), so they can run side by side
   (`DAYS_AT_ONCE`, or the orchestrator's `--parallel-days`). A day's presign list is its sessions' `archive_key`s.

Should the stage instead run where it ran first (a session with AWS keys running `stage_block_sources.py` itself, which
also copies each object under `frankie/block_<block>/sources`): that tool takes one `--archive` prefix and the
archive's real layout is per-segment (`native/20211001_20211101/`), so it would need a per-day key lookup first. Not
built; the box route above avoids it.

## 8. Walls in the orchestrator that this selection runs into (listed, not changed)

`deploy/aws/box/frankie_box_experiment.py`, `load_plan` (around line 156): `role = ROLE_OF_YEAR.get(date.year) if
date.month == 10 else None`. So (a) **2025-09-30 is LEFT OUT** of any run (a September day), and (b) every 2024-2025 day is
a `confirmation` day, LEFT OUT unless a frozen survivor list is given, and never a classroom-arm day. Greg's answer
treats all years alike for SELECTION; whether it also makes 2024-2025 discovery days for the RUN (or keeps them as the
confirmation set, with discovery = the 17 days of 2021-2023) is his call, and the code change follows it.

## 9. Questions for Greg

1. The matching facts and tolerances in section 3 (roll window -5/+1 business days, front = November contract, week
   pairs preferred but lone Tuesdays kept): keep, or change?
2. After the box facts: add a tolerance on activity (record or trade count against day 1, per day) or on price range?
   Today the proposed days run 0.36-1.09 of day 1's partition bytes.
3. 2024-2025 in the run: discovery like 2021-2023 (orchestrator ROLE_OF_YEAR changes), or the confirmation set (their
   facts read now for selection only)? And may the box read their full facts (a `CONFIRMATION=facts` mode, not built),
   or counts only?
4. 2025-09-30 (last week of September): admit September days in the orchestrator (the month check)?
5. 2026: the window's days are not on S3 (pull ends 2026-08-19). Pull 2026-09-22/23 from Databento later, or not
   (both fall in the October roll window under the current filters)?
6. 2021-10-19 and 2025-10-21 (6 business days before the November LTD): keep if the box shows one instrument across
   both parts?
