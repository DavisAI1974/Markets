# Stacks pass, TEACHER stage (2026-10-07 night, session 5)

Owner: teacher-stage agent. Branch ccr-d2f8f826-iefeah-frankie at 2f39ddc. SOURCE-ONLY: no AWS call, no run, no install.
Owned files: deploy/aws/box/frankie_box_experiment_teacher.py (ET.py), frankie_box_experiment_teacher.sh (ET.sh),
frankie_box_teacher_knowledge.py, frankie_box_joined_teacher.py/.sh, frankie_box_teach.py, frankie_box_teacher_discussion.py,
frankie_box_teacher_successor.sh. The teacher's pools themselves live in research/kalshi/frankie_boss/parallel_teacher.py
(PT.py, NOT in the owned list: read-only here; cross-owner requests below) and the shared reader in
frankie_box_market_timeline.py (hashed into a2's ROOT binding: untouchable during a2).

## Interim audit (state at 2f39ddc, before any edit of this pass)

Step 0: py_compile on the five .py files and bash -n on the three .sh files all pass at 2f39ddc. The WIP snapshots
f9f4460 / 6dedbba / a215495 left the teacher files COMPLETE (no half-edit): the read-ahead precompute, the failed-next
propagation, the finish placement and the spare-CPU split are whole and consistent with PT.py at 42c4e89.

Which files are on a2's teacher path: ET.sh -> ET.py (Run.child stage 'teacher', DAY_RUN_STAGES, under
frankie_box_cores.py run --size day_cpus() = 32) is THE teacher stage. teacher_knowledge.py is called in-process by
the orchestrator after the rows (brain filing, small JSON, no pool). teacher_successor.sh is an exec wrapper of the
successor dispatch (later stage 14). teach.py, joined_teacher.py/.sh and teacher_discussion.py are not on the a2 path
(Monday-era facts; joined teacher retired from host config; the discussion is a model-voiced transport reused by the
exchange): N/A for CPU stacks, audited for D only.

| Item | State | Where (file:line at 2f39ddc) | Note |
|---|---|---|---|
| A1 pools sized from booking | DONE (one gap) | ET.sh:39-48,59-61,80-81 (own affinity = booking, SPARE split, FRANKIE_LANE_CPUS, --workers = slice-1); ET.py:527-540 (lane = sched_getaffinity) | Gap: ET.py:847 `--workers` default 8 literal (only a hand start; the wrapper always passes it) -> PARTIAL |
| A2 pinned workers, serial consumer on a whole core | DONE on the shared path | ET.py:527-540 (consumer core + siblings, raw CPUs physical first), ET.py:632-640 (pin after streams start), ET.py:712-718 (finish plan); PT.py:195-205 | Legacy no-policy walk unpinned by design (not a2's path) |
| A3 ordered hand-off / in-order join with overlap | DONE | ET.py:563-590 (read-ahead in source order), PT.py:820-830 join_ready while chunks run | |
| A4 dead worker: redo same args same slot, one fewer, never stop | DONE in PT pools | PT.py:333-357 (raw), PT.py:507-533 (precompute), PT.py:835-880 (finish) | Hazard NOT fixable here: the shared reader's decode pool (market_timeline.py:212-258) is a multiprocessing.Pool with `.get()` and no timeout: a dead decode worker hangs the walk forever (queued request 3 in the session-5 drop-in). Cross-owner, after a2 |
| A5 read and hashed once | DONE | ET.py:84-99 prefetch, ET.py:438-447 witness handed to the shared reader | rows file and attachment are written then re-read for sha256 (ET.py:776-777): PARTIAL (hash as written possible for the attachment) |
| A6 encode once | DONE | ET.py:550-620 EvidencePrecompute registered into PJ._CANONICAL/_SUBSETS, guard per batch | |
| A7 sub-steps side by side | PARTIAL | journal sha256 overlapped (ET.py:84); raw pool, precompute and walk overlap; finish join overlap | Publication tail is serial: attachment write -> rows write -> two re-read hashes -> external section; the rows-file hash and the attachment hash can run beside the external section |
| A8 every stop bounded | PARTIAL | PT pools are spawn (no inherited SIGTERM handler, so the a2 shard-hang pattern of fork + inherited handler + unbounded join does not apply); pool.shutdown(wait=True) after cancel waits only for a running batch | Unbounded waits remain in market_timeline (Pool `.get()`), cross-owner |
| A9 thread env fixed | MISSING | none of the teacher files sets OMP/OPENBLAS/MKL threads; PT._chunk imports torch in 31 spawn workers | torch is only used to build tensors (no reductions), so a cap cannot change bytes |
| A10 byte-identical toy self-test | DONE for PT pools (42c4e89 era, per its commit) | | re-run here for what this pass changes |
| B1 sizes from plan/booking | DONE (see A1) | | |
| B2 FRANKIE_WORK_PROBE_V1 / units heartbeat, stall flag | PARTIAL | ET.py:358-366 phase(): report_phase at phase boundaries only, units = number of phases | The raw pass (hours on a full day) and the finish pool show NO unit movement: the heartbeat's 600 s stall flag fires on a healthy walk and cannot tell a hung decode pool from a working walk. No progress.json for `frankie_box_progress.sh DIRECTORY=experiment-teacher-rows/<day>` (ET.sh:7 promises it) |
| B3 run settings to children (FA-6) | DONE | env inherited (ET.sh:49 export, no env scrub) | |
| B4 DETACH (FA-2) | N/A | the teacher is a Run.child of the orchestrator, no wrapper of its own | |
| C1 S3 ranged/CRT reads | N/A | the teacher reads only local files (sealed journal, ROOT, day file) | |
| C2 big sequential chunks | DONE | ET.py:101-106 64 MB blocks | |
| C3 skip re-hash on unchanged stat | N/A (Greg's open call c) | would apply to the sealed journal re-hashed by every later process (classroom, export, school) | |
| D visibility on receipt + inspection markdown | PARTIAL | cpu_pinning, raw_pool, finish_pool, evidence_precompute are on the receipt (ET.py:722-735) | NOT in workflow_report (the inspection markdown projects workflow_report only): pool rebuilds, not-registered batches, pin fallback, the prefetch's swallowed error (ET.py:92-94), the defaults taken (FRANKIE_TEACHER_CHANGES setdefault ET.py:471, workers default) are invisible in the markdown; workflow_report.outputs.waits is always [] |
| E science unchanged | DONE so far | | every change of this pass is additive |
| teacher_knowledge / successor.sh | N/A for A-C; D DONE | brain filing in-process; successor exec wrapper | |
| teach.py / joined_teacher / teacher_discussion | N/A (not on a2's path) | joined_teacher.py:756 default workers from os.cpu_count() (host count, not the booking) | listed, not changed: retired path |

Missing or partial today, in fix order: A8/A4 (cross-owner only), A1 default, A9 thread caps, A7 publication tail,
A5 attachment hash as written, B2 unit probes (raw pass and finish), D (stack events into workflow_report).
