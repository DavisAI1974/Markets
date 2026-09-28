# Handoff 2026-09-28 ~10:0xZ: V8 digest grammar, repeat passes removed, expensive Granite stopped

Branch `claude/frankie-monday-cycle-0-gj113f` (cut from `claude/frankie-monday-continuation-qlkvqr` tip `bf4a9a9c`).
Read first: `HANDOFF_20260928_TOKEN_STACKS.md` (the earlier record of the day).

## Greg's standing rules added this session
- **NO TESTS.** Do not run test suites locally or trigger CI (they cost money). Every push carries `[skip ci]`:
  a push touching the digest files otherwise starts "Frankie box codecs tests" (it did once: run 36405866782,
  cancelled at ~1 min).
- **Cost first.** Stop anything billing that is not needed, immediately, not queued behind other work.
- No V8 canary.

## FIRST (Greg, 2026-09-28): switch the Granite Pod
The expensive Granite setup is what must not run again by accident. The Jev (CLM) work is fine.
1. Move Granite to a cheaper option (Greg to choose if not already stated):
   - (a) serverless only, min workers 0, pay only while reading;
   - (b) one L40S Pod, run only for a read, community/spot price (staged reading resumes after interruption);
   - (c) a cheaper GPU, if the 131,072-token context fits.
2. Make sure nothing can start the old expensive one. Candidates to check:
   - the retained observer's automatic start (`frankie_retained_granite.yml`, `granite_retained_host.py`);
   - `POD_ID_DEFAULT = 'fhiwwlouzyx6l2'` in `frankie_box_boss_session.py:66`;
   - `/opt/frankie-box/serverless.json` (the reading lane);
   - the serverless endpoint's minimum-worker setting (not checked this session).

## State at handoff (all verified from run logs)

| Item | State |
|---|---|
| Granite Pod `fhiwwlouzyx6l2` (L40S, secure, $1.09/h) | **EXITED** (stopped via Pod control `stop`, run 36406308094). It had been up ~26 h at 0% GPU. Disks kept. |
| Pod `g7y3g2w1kor4l3` | EXITED (the older retained generation). |
| All RunPod Pods | Only these two exist (Pod control `list`, run 36406869973). |
| Launch r3 (run 36398770889, `frankie_box_cycle0.sh ACTION=launch`, config r3) | GitHub run cancelled. The box process `run_actual_sunday_ec2.py` (PID 4851, 79 min) was killed by `frankie_box_stop_cycle.sh` (run 36406968475, STOPPED, receipt `/opt/frankie-box/receipts/cycle-stop-*.json`). The first attempt (run 36406841877) failed: the box's `dash` builtin kill refused the process-group kill; fixed with `/bin/kill`. |
| Jev CLM Pod run (36398106270) | **Cancelled by me in error.** Greg wanted it. Its cleanup found no Pod file, and the list shows no orphan Pod. Do NOT re-dispatch it (Greg, 2026-09-28: do not redispatch anything); for reference only, the dispatch was ( `frankie_box_clm_sidecar_pod.sh`, `DATASET_KEY=clm-sidecar/monday-20260928a/dataset.jsonl.gz STAMP=monday-20260928a MAX_MINUTES=150`). |
| Session unit `frankie-cycle-00` | Not running. |

**Greg, 2026-09-28: do not redispatch anything. Nothing is to be dispatched without Greg's explicit go.**

## New operator controls (this session)
- `frankie_pod_control.yml`: `action=stop` (halts billing, keeps disks) and `action=list` (every Pod, status, cost).
- `frankie_box_session.sh ACTION=stop_session` stops the session unit, with a receipt, and does not restart it.
- `deploy/aws/box/frankie_box_stop_cycle.sh` stops a running cycle launch on the box (TERM, then KILL, with a receipt).

## Code landed (commits on this branch)
- `5b1e5f9b` **DIGEST_V8** (all additive on V1-V7, lossless; every writer proves parse == rows):
  - keys-once objects (`shapes:` line, `R` cells);
  - packed digit lists (`P`);
  - same-row integer refs (`<i`);
  - count columns derived as list lengths (`lengths:` line);
  - columns ordered by presence;
  - dictionary only where it pays (estimated pinned-Granite tokens).

  The grammar now lives ONCE in `frankie_box_digest_render.py`; stream and parallel only orchestrate. The same commit
  closes every review item: serial == parallel byte test, `DISK_RESERVE` as a parameter / `FRANKIE_DIGEST_DISK_RESERVE`
  setting, docstrings (members not byte-identical), and the Jev purge `j < cut`. `SCHEMA` = `DIGEST_V8`, so the next
  session run re-derives the digest (a ROOT re-run from saved sources; Greg's go).
- `a44141f6` **repeat passes removed**:
  - one-note merge groups pass through;
  - the digest head goes once in writing (other calls carry the status header);
  - the reading plan is reused when the corpus and part target match;
  - the classroom cache identity ignores `reading.json` `at`;
  - the classroom staged read takes the digest by reference (still navigable by range).

  Only `py_compile` was run (no tests, per Greg).
- Tests were written before the no-tests rule (they were green then): `tests/test_digest_parallel.py` and
  `tests/pinned_producers.py`. The 6 old digest failures were test-setup gaps:
  - the producers were not loaded; now fixed;
  - the projection pool needs 16 cores; fixed with an in-process stand-in on smaller hosts;
  - the disk reserve could not be passed; now a setting.

  3 remained unexamined when Greg stopped test work: memory subprocess, change-after-proof, no-whole-file.

## Queue after the Pod switch (principal HELD until Greg's go)
Re-render the digest (V8) -> stage the SAME commit -> config r4 -> launch r4 (+probe) -> principal (+probe) -> record ->
resume -> correction -> retain. `boss_commit` in the config must equal the executing checkout.
Paths: `HANDOFF_20260928_TOKEN_STACKS.md` "Cycle-0 queue".
