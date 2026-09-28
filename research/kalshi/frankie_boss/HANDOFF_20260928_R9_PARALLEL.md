# HANDOFF 2026-09-28 18:3xZ -- cycle 0 launch r9 (every preparation stage across the CPUs); principal queued behind it; Jev sitting in

Branch `claude/frankie-monday-cycle-0-urozez`. Code under test: `222ac66b` (staged). Previous handoff:
`HANDOFF_20260928_R6_LAUNCH.md`.

Standing rules:
- No tests: py_compile with python3.12 only. `[skip ci]` on every push. No canaries. A probe on every long box run.
- Never edit frankie_box_projection.py or the pinned readers/teacher/normalizer/context files (swap, never edit).
- Keys are secrets.
- A cycle0.sh dispatch refuses unless the staged CODE_ROOT commit == the dispatch ref's tip: dispatch launch/principal
  BEFORE pushing anything, or stage the new tip first.
- Only ONE pending run per concurrency lock: a new box-run dispatch replaces a queued one (the principal queued behind a
  launch is lost if anything else is dispatched on box-run).

## RUNNING / QUEUED (probe first)
- **Launch r9**: GitHub run 36464699766 (started 18:22:12Z, timeout 12 h), config `monday-run-config/full-20211004-20260928-r9`, code root
  `/opt/frankie-box/code/222ac66b77fa27e83d07de3d495c4f05ac83b006-36464188064-1/markets`, run dir
  `/opt/frankie-box/work/runs/monday-20211004-20260928-r9`). Expected: walk 1 (~20-25 min), context encode (workers),
  walk 2 (~20-25 min), teacher raw streams (parent, NOT yet measured), teacher normalizer/targets/receipts (workers,
  ~25 min), then the request `execution/cycle-00/principal/session-request.json` and the WAIT.
- **Principal** GitHub run 36464728520 (pending), queued on box-run behind r9: `frankie_box_cycle0.sh ACTION=principal`, same code root,
  `CALCULATIONS=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`,
  `REQUEST_DIRECTORY=<r9 run dir>/execution/cycle-00/principal`, timeout 86400. Starts when r9's launch run ends.
- **Jev**: relay restarted for r9 (dispatched 18:2xZ; the previous relay 36462590549 cancelled); Pod run 36458383653 (stamp `monday-20260928-jev1`, 3 reader Pods, 600 min, checkpoints 30 min) -- no S3
  output seen at 17:59Z (no pod.log/progress); relay restarted on r9's request dir (resends dipole material every bundle
  until delivered; continues from the first free feed slot).
- 4 A100 Pods (BOSS kqp1qwzv6vo67a; readers x2vprjb4cs2ulu, mhj0jwod7yfdz5, vbh922dqk8x2f9), slots 3. Runpod balance
  ran out once today (HTTP 402 on Jev's Pod); Greg topped it up.

## Probes (all read-only)
- `frankie_box_session_cpu.sh MODE=profile` (no PID: finds the launch or the principal and EVERY descendant; py-spy
  --subprocesses; every stream of every process).
- `frankie_box_read_log.sh MODE=processes FILE=work/runs/<run>` and `MODE=tail FILE=work/runs/<run>/host-progress/progress.json`.
- `frankie_box_jev_reports.sh` with presign `getprefix:frankie-granite42-568968024170-us-east-1/clm-sidecar/monday-20260928-jev1/`.
- Output is never truncated now: ssm_run_sh.py pages anything >= 23,000 characters as "report part i/n" (rejoin by
  splitting on '\n----- report part i/n -----\n'); the job summary holds it whole up to 1 MiB; the artifact always.

## DONE this chat (commits, in order)
- `3cb15cc7` parallel_context.py: after walk 1 the pinned _prepare's per-row encode, reconstruction check, packet
  hashes run on workers; teacher exact-row hashes from the walks.
- `ab89dd4d` principal one-CPU fixes: token counts via encode_batch (GIL), teach's six layer streams in processes,
  corpus render decode/containment/JSON render in processes (local: identical output), compare/receipts/push threaded,
  frankie_box_filehash.py (one sha256 per unchanged file per run).
- `59201297`/`84f073e7`/`429b4121`/`82118126` probes: every process/stack; no truncation (paging); byte-exact rejoin.
- `82118126`/`8bc723a1` Jev reader (never prints config.json presigned URLs).
- `bf86d734` Jev relay: dipole material every bundle until found (also via the principal's verify.json); putrange
  skips already-written slots so a restarted relay continues.
- `2f5b28cf` one parse per journal entry in both walks (r7 profile: 38% json encode, 27% json decode per worker):
  same entries and checks; each worker's first block compared with the pinned reader. Local: identical, 50% CPU.
- `222ac66b` parallel_teacher.py: JournalTeacherR3.attach's normalizer (18 ms/row), DipoleTarget and receipt
  (~0.4 s/row: evidence_hash(export()) of 19 x 4096 windows) moved to workers from pinned restores; receipt hash from
  per-value fragments, guarded against normalizer.receipt() (first 2 per chunk + every 50,000th). Local: identical.
  Before this no launch could finish (days on one CPU for a whole-day context).
- Stopped: r6 (one CPU after walk 1), r7 (for 2f5b28cf); r8 configured but never launched.

## OPEN
1. Measure the teacher's RAW streams (c15_teacher_r3._paired_raw: control JournalTeacher._columns/_dynamics and R3
   _absorption/_cohort over up to 1024-1025 groups, one instrument 111313) -- still sequential in the parent. If long,
   they are next (history replay per chunk like the normalizer).
2. After attach: context_session input hash over the token tensors (one sha over GB of hex), and prepared_context_cache
   (1M+ DipoleTargets) -- not yet profiled on a whole-day context.
3. At the WAIT: principal starts automatically (queued). Probe it throughout; then record initial -> resume 1 ->
   correction -> record correction -> resume 2 -> retain (MONDAY_CHECKLIST_20260927.md).
4. Jev: confirm his Pod is up (read his outputs); if nothing, check the Pod on Runpod.
5. Retained-preparation reuse: point future cycle-0 configs' retained_preparation_recovery at r9's prepared request.
6. Environment approval on frankie_box_run.yml (review follow-up, not taken).
