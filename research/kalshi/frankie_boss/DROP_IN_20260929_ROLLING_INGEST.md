# DROP-IN 2026-09-29 ~13:10Z (next chat): rolling ingest across main box, small box and GitHub runners

Branch `claude/frankie-monday-cycle-0-urozez` (tip 9c46da4b or later). `git fetch origin claude/frankie-monday-cycle-0-urozez
&& git checkout -B claude/frankie-monday-cycle-0-urozez origin/claude/frankie-monday-cycle-0-urozez`. Read this, then
`HANDOFF_20260929_TUEWED_DATAPOINTS.md` (section "Update ~13:05Z"), `BOX_DATA_INVENTORY_20260929.md`. Skills:
using-agent-skills, experiment-orchestrator, full-run-orchestrator before any box step. AWS pair: ask Greg (put in
`~/.config/markets/env`, chmod 600, verify with STS; no rotation until the build is done).

Rules: NO DATA DROPPED; counts not averages; py_compile/bash -n only; [skip ci] every push; restage before a staged-code
box dispatch; never edit pinned files; a probe on every long run. SSM runs scripts under sh (POSIX only, and no $HOME).

## Greg's standing calls (this chat)
- **Fill spare room, rolling: "as 2 leave 2 enter".** Whenever a pair finishes on a machine, start the next pair there.
  Do NOT pile days on the small box: ONE pair at a time there (8 vCPU, WORKERS=7, DAYS_AT_ONCE=2).
- **No new boxes** without asking. The 16 vCPU box launched by mistake was terminated. The Windows box
  i-0e90ee6110ef609aa is stopped, untouched; Greg is weighing replacing it with a same-size Linux box (no double billing:
  per-second compute, disks prorated; us-east-2 cap is 16 vCPU and the small box uses 8 -> needs a quota raise in the
  console or us-east-1).
- GitHub runners are free (public repo): use them for whole days. Journals stay in AWS (S3), git gets pointers only.
- Deep clean of the box later ("when we get more time").

## Running at hand-off (probe each first)
| What | Where | Dispatched |
|---|---|---|
| 12 discovery days 20211019/20, 20221011/12, 20221018/19, 20231003/04, 20231010/11, 20231017/18 | GitHub run 36571235912 (one 4-CPU runner per day, VERIFY=inline) | 12:54Z |
| ingest 20241001/02 (confirmation pair) | small box i-08cee7171c0a76a04 (us-east-2), DAYS_AT_ONCE=2 WORKERS=7 VERIFY=inline | ~13:03Z |
| conform Wed 20211006 | main box, `ACTION=conform DIRECTORY=/opt/frankie-box/work/ingest-20211006-ingest-1790675371` | ~13:03Z |
| fetch 20241008/09 | main box (partitions 20241007-09); INGEST NOT STARTED | ~13:03Z |
| pairs2 ingests 20221004 / 20211012 / 20211013 | main box, deferred verify; ~13:10 / ~13:35 / ~13:30Z | earlier |
Sealed today: Tue 20211005 (inline verified), Wed 20211006, 20221005 (both need ACTION=conform).

## Next, in order
1. Probe all of the above. Runner days: job log shows progress only at the end for run 36571235912 (later runs stream
   every 100k records); results in `s3://bento-568968024170-us-east-2-an/frankie/ingest/<day>/gh-<run>-<attempt>/`,
   pointers on branch `frankie-ingest-pointers` (`ingest_pointers/`). A failed runner day: read its pointer/log, fix, rerun.
2. Main box: when 20221004 seals, start 20241008/09 (`frankie_box_ingest_block.sh ACTION=ingest DAYS_AT_ONCE=2
   WORKERS=8 VERIFY=inline MANIFEST=<BLOCK_20241008>,<BLOCK_20241009>`); as 20211012/13 seal, next pair, and so on.
   Then `ACTION=conform` for 20221005, 20221004, 20211012, 20211013 (deferred verify).
3. Remaining confirmation pairs (manifests committed 9c46da4b): 20241015/16, 20250930/20251001, 20251007/08,
   20251014/15, 20251021 (lone). Each: fetch (presign the day-before + both partitions from the canonical manifest
   `research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json`, WORKERS<=box CPUs), then ingest; or send
   whole days to runners (`script=deploy/aws/box/frankie_runner_ingest.sh variables="DAYS=... WORKERS=3 VERIFY=inline"`).
4. Tue/Wed 20211005/06 downstream (13 data points, ROOT, teacher, classroom V2, Jev) still waits on the free-source fetch
   (run 36557302661) and the day files: see the older drop-in `DROP_IN_20260929_TUEWED_DATAPOINTS.md` items 4-9.
5. Databento Oct 2024+2025 (run 36564541947): tell Greg when the last file lands so he can cancel. HOLD Oct 2021-2023 and
   the 5-year MBO.

## Built this chat (all on the branch)
`frankie_box_cleanup_code.sh`, `frankie_box_cleanup_bedrock.sh` (named-only cleanups), `frankie_box_worker_setup.sh`
(worker = main box's Python 3.13.15 + 75 pins + markets checkout + ingest worktree), `frankie_runner_ingest.sh` + jobs
runner-plan/runner-ingest/runner-pointers in `frankie_box_run.yml`, `frankie_box_venv_requirements.txt`. 25 new day
manifests (12 discovery, 13 confirmation) + 13 block manifests. Main box free disk 1.55 TB.
