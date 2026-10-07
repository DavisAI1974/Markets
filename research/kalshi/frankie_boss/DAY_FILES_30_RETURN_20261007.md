# Day files return: Frankie's 13 points for all 31 days (2026-10-07 night, session 2)

Day-file agent, branch `ccr-d2f8f826-iefeah-frankie` (worked on top of `3bf4f2d`; nothing committed or pushed by the agent).
SOURCE-BUILT, data BUILT AND VERIFIED; no run of any kind (no box, no SSM, no model, no install, no Databento, no
workflow dispatch). A fresh independent review is required before integration.

## 1. What exists now

31 day files, FRANKIE_DAY_EXTERNAL_V1, each with its receipt FRANKIE_DAY_EXTERNAL_RECEIPT_V1, at
`s3://bento-568968024170-us-east-2-an/frankie/day_external/<day>/day-external.json` and `day-external-receipt.json`.
Built locally in the container from the S3 holdings (the box module's own `verify_curve` + `build_day`, nothing fetched
from a public site), then uploaded by presigned PUT and verified on S3: 62/62 objects, size and ETag (single-part MD5)
equal to the local files; each receipt's sha256/bytes equal the day file.

| day | bytes | sha256 | listed missing |
|---|---|---|---|
| 20211005 | 59380696 | a49747267a1319213d9ffc974e8a36fe00631b2e5beec45b6d1cdeab4e2f1f51 | 19 |
| 20211006 | 67798187 | 4f06d8bab87f283ef3eaedcdabe6c10a1d9aae1c5aaa7ff7aca4481b01be120c | 19 |
| 20211012 | 46971399 | 1beb8acbfcf2b112a5056acd65f57f96d06ac71f0fc4b17562f8643d24ee81b1 | 1 |
| 20211013 | 47333008 | 8e1088c837e9a840d3f5011ffe1f4d26d9ec9eee4d71938b45c9db088e59fbef | 1 |
| 20211019 | 47972592 | 1726370143a98fa932b90e1eb5e25ba2bfbf05390a503129904a14d407d7f0a0 | 1 |
| 20211020 | 44965140 | ab9bcd83347c0438642f922e6feb27c4d3397190ab864f58787f113dbd8c5a70 | 1 |
| 20221004 | 42811282 | db39f1c06d4f04d19117428513a997f4d296bce9ead6e92214547e6dcc96af34 | 19 |
| 20221005 | 39874801 | f541849e1840b078ce86be501c21778e11643030b260f9f4854a1d98b1482dff | 19 |
| 20221011 | 40706824 | 790df19d5849d385473a19f14a2b1c3f965cd90d6f0cf0aa11b357a05c8680b6 | 19 |
| 20221012 | 40437672 | f75aacfca90b83f07243cb224f9f03378ae43c3cd42b07b1988ba57bc25945a2 | 1 |
| 20221018 | 44811546 | 0b1dcc3f377df471833b6a8451b3925b5bfbcefa1678dd6d989a878bddf43136 | 3 |
| 20221019 | 43630412 | 89446bc91ea032de334dbecae8234e7b617dc0da6b4b64a902c7cbcf137a39fb | 3 |
| 20231003 | 30576302 | 7d7d42ce9055f9e7c9db0f6dfe9def746fd654fcdbe696765bbb34e3c50019c8 | 25 |
| 20231004 | 33874438 | 2c9a9a962859f99120967af946ea7c79149d6fbb6a3e716f2af43c2067099bb8 | 25 |
| 20231010 | 40540381 | 3731344470943cbf4579f68607007e470960276dcae6c2aa2640679e6294b7f1 | 25 |
| 20231011 | 42782368 | a5b307d5ba729bad6aa341b8b237fde83ab455a0b9890412d23524b8286543eb | 25 |
| 20231017 | 38223001 | c8e9996106d90b259abf6cc7faa75852e6ed3ffd0c467872faad019918744237 | 7 |
| 20231018 | 35132189 | fed74484967d5748ab6a8c3ae6e8b77b18e184c522de1a3a811758508ccb812c | 7 |
| 20241001 | 38829185 | 9faaaf9187d26ee88c21abbe4af7bf58d6e19c6b922b74ac3b791d4df11dbdb8 | 4 |
| 20241002 | 39191073 | ed41a5d96756bc9d1e4ee1fbc707fee55715df276b9ba496572ad0a8af15e21b | 4 |
| 20241008 | 37230149 | 79d95f802826bd0e32e206501c202ff67a1594b8c15fe6d88f653f5694e39d7f | 5 |
| 20241009 | 38466156 | 3e9d5d93d50bfca5587604534c54ecdccf603b7b833e1e1a9b8b579c502ee17c | 5 |
| 20241015 | 36463903 | cc95875354834dbd52ad00fd87c28615d6fdde505eca325428753dc67b49982a | 7 |
| 20241016 | 40064561 | 226f6bac998c328f021cf96eaa5d963a6f0e350b4f514485d3afbe419058e855 | 7 |
| 20250930 | 38331382 | a8127fb412a6a9dc257ec37ec5aa8d3b043225f670774d5ca925965f6cd360ad | 1 |
| 20251001 | 45256878 | 6a1069188290fd274de090076d78c68223f013c8fb5fef5b153db80f765fc691 | 1 |
| 20251007 | 45290865 | 5aaf3ed766f51c0f3701e6eee8745be57204faf5b6080b75a2e10a878020e05f | 1 |
| 20251008 | 50245132 | 436416f39df5b7c0aaaf6d8baaa57559d78688cd4ac679f744396da549d6f504 | 1 |
| 20251014 | 43422060 | e074381cee3781fa89b1fb49f0e6c99572595634c0a0521beb1ee7dd9f841bae | 1 |
| 20251015 | 43977816 | 7ac6c5f17a416f08a687454e044cd09ad0b2f13401ba21b6e208feac909c5c34 | 1 |
| 20251021 | 64195905 | 5c782785a994a521b98e638e92aff5c585d8d5078dddeddd6b5776e105508473 | 1 |

Every day carries all 13 points' tables (calendar, 5 COT codes, storage.weekly, storage.estimate, weather.obs_hourly,
weather.gw_daily, mos.raw, mos.gw_by_cycle, mos.disagreement_by_cycle, eia930.hourly, eia930.us48, and the five curve
tables). Each receipt names every input key with its sha256 (manifest-checked), the curve verification, the 99 mapping
per table, the reader-stamp rule and the sha256 of the three code files (equal to the working tree at return).
`markets_sha` in the receipts reads `worktree-on-3bf4f2df` (the code was uncommitted at build time; the code_sha256
fields pin it exactly).

What the "listed missing" counts are (never fabricated, never zero, never a refused day):
- every day: `squeeze_watch.calendar_front_next_spread_chg_3d` (needs three prior sessions' settlements; no Databento
  pull, per Greg). The spread itself is in `curve.settled_shape`.
- 18 lines on days within 12 days of a month start (20211005/06, 20221004/05/11, 20231003/04/10/11): the prior-month
  ASOS file of each station (202109/202209/202309) was never fetched. Only gw_daily rows of September gas days are
  affected; the 72 h hourly window and the D-1 gas day are complete.
- 20221018/19: the 2022-10-20 print (after the day) has no archived report or estimate (fetch-gap line only).
- 2023 days: the 2023-09-28, 10-05, 10-12, 10-19 prints have no archived report or estimate; storage level/change are
  the EIA API series values and the estimate row is absent.
- 2024: 2024-09-26 and 10-03 prints: net change as printed, level and five-year average from the EIA series;
  2024-10-10 and 10-17: no archived report or estimate.

## 2. Superseded copies

Before any write under `frankie/day_external/`, the 34 objects there (17 days x 2: 20211005 06 12 13 20, the six 2022
days, the six 2023 days) were copied server-side to `frankie/day_external_superseded/20261007T144122Z/` and verified
(34/34 size and ETag equal). Re-listed after the uploads: still 34 objects, one stamp. The 14 other days had no prior
object.

## 3. Verification done

- Inputs: 883 of the 1,035 objects of `frankie/day_history/36576414768/manifest.json` mirrored and sha256-equal; the
  148 not mirrored are the consensus family (140, no longer read by the builder) and the 8 COT raw zips (the builder
  reads the store JSON). 4 consensus snapshot HTMLs failed the sha check after text transport (not read by the build).
  Curve: 141/141 native files sha256-equal to the curve pull's manifests (`verify_curve`).
- Every file passes `check_day_file` (stamp integer, < halt, event_time_ns <= stamp, no repeated column).
- Values vs an independent computation (the md tables, computed separately from the same S3 holdings at 14:00 ET):
  COT 023651 and 023391 (net, week change, 1y/3y percentiles, report date), calendar, GFS-NAM disagreement (runtime and
  max), EIA-930 US48 last hour (period, wind, gas), observed gw_hdd, storage level and change, estimate and actual,
  settled curve front/c1/front symbol: all 31 days equal, except observed gw_hdd on 20221005 (5.911 vs 5.891) and
  20251015 (4.711 vs 4.722). Recomputed from the full station files these match the day file: the md computation had
  missed two BOS observations (byte-range reads). Point 10 of all 31 md files was rewritten from the day files
  (23 files changed; most only in precip/formatting), so md and JSON agree.
- No future leak: the guard plus the 14:00 ET cut in the cross-check; point 6 (no event time) placed at 14:00 ET with the
  note "this is not a time-specific event" (`placement_ns`).

## 4. Points without an as-published value (best available used)

- Point 11 storage: 2023-09-28, 10-05, 10-12 prints (all 2023 days) and 2024-10-10 (20241015/16): level and change are the
  EIA API v2 series; 2024-09-26 and 10-03: level and five-year average from the series, net change as printed; 2025:
  five-year average computed from the series (level and change as first printed).
- Point 12 estimate: none held for the 2023 prints and 2024-10-10 (listed missing).
- Points 5 and 7 EIA-930: current revision everywhere (no as-published archive exists).
- Every other point is first-publication by nature (COT archive, MOS cycles, ASOS archive, exchange data, calendar rule).

## 5. Code changes (working tree; the parent commits by path)

| file | +/- | change |
|---|---|---|
| research/kalshi/frankie_boss/operations/frankie_day_external.py | +211 -35 | POINT_REGISTRY_MAP (13 points to closest 99 entries with reasons, event-time basis), EVENT_TIME_RULES, `place()` (reader stamp = max(event_time_ns, publication), 14:00 ET default, R-B), `as_printed` family replaces consensus, storage.weekly as printed, `storage.estimate` table (values), check_day_file event-time check, COT store fields colliding with lead columns kept as `store_<name>` (found by this build: StagingRefused on repeated columns) |
| research/kalshi/frankie_boss/operations/fetch_day_history.py | +171 | `as-printed` subcommand: WNGSR / TradingEconomics / investing.com archived pages to FRANKIE_STORAGE_AS_PRINTED_V1 |
| deploy/aws/box/frankie_box_day_external.py | +25 -8 | as_printed family, CODE_FILES, receipt adds point_registry_map / reader_stamp_rule / point_mappings / code_sha256; family-run check isalnum; FAMILIES drops consensus (builder parity) |
| .github/workflows/frankie_day_history.yml | +9 -1 | `days` input (DAY_HISTORY_DAYS), DAY_HISTORY_DEADLINE_S 16200 |
| research/kalshi/frankie_boss/day_files/*.md (23) | +23 -23 | point 10 synced to the day files |
| research/kalshi/frankie_boss/DAY_FILES_30_RETURN_20261007.md | new | this record |

Checks: `python3 -I -c "import ast,sys; [ast.parse(open(p).read(), p) for p in sys.argv[1:]]"` on the three .py files:
ok. Workflow YAML loads. `git diff --check`: clean.

Not touched, needs its owner: `research/kalshi/frankie_boss/dipole_classroom_external.py` lines 106-107 and 123 still
name `storage.estimate_captures` for point 12; the day files now carry `storage.estimate` (estimate_bcf, actual_bcf,
surprise_bcf rows). The classroom must read `storage.estimate`.

## 6. Workflow route for the remaining as-published gaps (not dispatched)

GitHub Actions `frankie_day_history.yml`, inputs: `action=fetch`, `families=consensus`,
`days=20231003,20231004,20231010,20231011,20231017,20231018,20241008,20241009,20241015,20241016`. Then
`fetch_day_history.py as-printed --src <mirror> --runs 36576414768,36618331994,<new run> --out <dir>`, upload as a new
`frankie/day_history/<id>/as_printed/` and rebuild those days with `HISTORY_FAMILY_RUNS as_printed=<id>` (superseded
copy first). Earlier Wayback CDX attempts for these prints were refused; the dispatch may also come back empty.

## 7. 20211020 ingest status

No ingest object for 20211020 (or 20211019) anywhere in S3 (`frankie/ingest/` holds 20221011 12 18 19, the six 2023 days,
20250930, 20251001, 20251014; no other prefix names the day). Per Greg the days are ingested; for 20211020 that can only
be on the box, which was not touched. Its day file is built and on S3 regardless.

## 8. Account calls (all S3, us-east-2, bucket bento-568968024170-us-east-2-an)

- Read: ListObjectsV2 and GetObject over frankie/day_history/, frankie/day_external/, frankie/ingest/, frankie/, nymex/,
  storage_vintage/, consensus/, ngwu/, weather/; presigned GETs for the mirror. SelectObjectContent tried once
  (MethodNotAllowed).
- Write: CopyObject x34 to frankie/day_external_superseded/20261007T144122Z/; PutObject of scratch bundles to
  frankie/day_external_work/20261007/ (156 objects, 249,172,620 bytes; still there, the parent may delete them);
  presigned PUT x62 to frankie/day_external/<day>/ (31 days, overwriting the 17 superseded); presigned PUT x3 to
  frankie/day_history/asprinted20261007/ (manifest.json, as_printed/receipt.json, as_printed/storage_as_printed.json,
  ETags verified).
- Nothing on EC2, SSM, IAM or any other service.

## 9. Addendum: Greg's go "Do the workflow for the storage nos ... get them out of frankie"

- Dispatch of `frankie_day_history.yml` (ref `ccr-d2f8f826-iefeah-frankie`, action=fetch, families=consensus,
  days=20231003,20231004,20231010,20231011,20231017,20231018) was REFUSED by GitHub:
  `POST .../actions/workflows/frankie_day_history.yml/dispatches: 404 Not Found`; `get_workflow` on the same file name
  also 404. The workflow is not registered in the repository (the file is on the work branch, with the `days` input,
  but not on the default branch). Stopped there as instructed; nothing pushed anywhere. No new as-printed data, no
  rebuild; the 2023 storage report/estimate rows stay listed missing with their reason.
- Registered alternative, not used (needs the parent's/Greg's word): the earlier day-history runs (36576414768 etc.)
  came from `ng_historical_mbo_5y_to_s3_20260820.yml`, `mode=day_history`, which carries the same fetch steps and
  accepts `families` and `days` (file on the work branch, lines 35-40 and 152-209). Dispatch inputs would be
  mode=day_history, families=consensus, days=20231003,20231004,20231010,20231011,20231017,20231018, ref
  ccr-d2f8f826-iefeah-frankie. Its day_history job uses no Databento.
- Scratch deleted: `frankie/day_external_work/20261007/`: listed 156 objects (249,172,620 bytes, all under the
  prefix), DeleteObjects 156 deleted, 0 errors; re-listed: 0 objects, and `frankie/day_external_work/` is empty.
  Nothing else touched. The only other object set this agent created under frankie/ is
  `frankie/day_history/asprinted20261007/` (3 objects), which is not scratch: every day file's receipt names it as the
  as_printed input.
