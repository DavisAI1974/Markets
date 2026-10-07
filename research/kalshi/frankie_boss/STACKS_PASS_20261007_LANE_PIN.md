# Stacks pass 2026-10-07 night, session 5: frankie_box_lane_pin.py (bounded pool end, SIGTERM reset, sibling-idle placement, RedoPool)

Role: lane_pin owner (one file). SOURCE-BUILT / RUNTIME-UNVERIFIED on the box: nothing ran on AWS; the module and its
tests ran in the session container only (4 CPUs, one hardware thread per core, Python 3.13.16). Branch
`ccr-d2f8f826-iefeah-frankie`, started from `5905684`; the parent's WIP snapshots (`585a932`, `f985763`, `2f3ab8b`, later)
swept the in-progress edits of this file in as they were made; the diff of the whole pass is `git diff 5905684 --
deploy/aws/box/frankie_box_lane_pin.py` (+388/-25; 440 -> 803 lines). Not committed by this role; the parent commits.

Requests served (all additive; every existing public signature and return shape unchanged, callers positional or keyword
as they are today keep working; placement changes nothing computed):
- R1 (school-stage owner): (a) every process initializer resets SIGTERM to its default action before any task; (b) every
  terminate/join in the module is bounded (STOP_JOIN_SECONDS = 10 s, as frankie_box_boss_session.STOP_JOIN_SECONDS), SIGKILL of
  the survivors by pid, join again bounded, each kill in report['stop_kills'] = [{pid, cpu, at, exit_code}]; the module's
  blocking waits audited.
- R2 (data/search owner): `exclude_sibling=` keyword on placement / pinned_pool / executor / ordered_map / record (default
  False: every current caller unchanged) leaving the coordinator's hyperthread sibling out of the worker set; record() lists it.
- X1 (ingest owner): (a) the bounded stop as a public drop-in for callers that hold a pool: `end_pool(pool, grace, report)`,
  the shape operations/ingest_cpus.end_pool built (helper thread, grace, kill by pid, never raises), plus the record;
  (b) a submit/get pool with the dead-worker redo rule: `RedoPool` (added; small, built over the ordered_map machinery).

## The defect this answers (E2E_ONE_DAY_20231018.md, sessions 4 and 5)

a2, 22:36Z: forked workers inherited the ROOT's SIGTERM handler (frankie_box_experiment_root.calculate_day: sets the save
flag only); a worker blocked in a pipe write resumed the write after the handler (PEP 475), terminate() was swallowed, the
unbounded join waited forever. For a multiprocessing.Pool the unbounded join is INSIDE `Pool.terminate()` itself (CPython
`_terminate_pool` ends with `p.join()` per worker, no timeout; `Pool.join()` the same), so a bounded end cannot call
terminate() and wait for it in the calling thread: here terminate() + join() run in a helper thread, watched with the bound.

## Changes, by function (line numbers as of this record)

Module docstring (1-46): end_pool / end_executor, RedoPool, reset_worker_sigterm and exclude_sibling added to the index;
`import signal` (30); `STOP_JOIN_SECONDS = 10.0` (51-52).

- `reset_worker_sigterm()` (187-202), NEW public: in a worker, SIGTERM back to SIG_DFL unless already default; returns
  'reset' / 'default' / 'kept (<why>)' (not the main thread); never raises; the parent's handler is a different process's.
  Docstring names the window it cannot close: a worker between its fork and its initializer when terminate() arrives
  still holds the parent's handler for those milliseconds (seen once, below); end_pool's bound and kill cover it.
- `_pool_initializer()` (205-210): calls reset_worker_sigterm() FIRST, before the pin and before any task. It is the
  initializer of pinned_pool, executor('process') and (through `_tracked_initializer`, 534) ordered_map and RedoPool.
  `_thread_initializer` (263) unchanged: a thread shares the process's handler and signal.signal() refuses off the main
  thread; a thread executor has no process to SIGTERM.
- `_coordinator_siblings()` (115-123), NEW private; `_place()` (126-154), NEW private: placement()'s work plus the idle
  CPUs it set aside. Default path byte-for-byte the former placement() logic (coordinator = order[0]; workers < len(order):
  other cores' threads first, the coordinator's sibling last; else cycle over the whole order). exclude_sibling=True:
  the sibling thread(s) leave the worker set; the basis string says "; the coordinator's sibling thread N left idle
  (whole core for the coordinator)"; oversubscribed it cycles over the lane minus the sibling (the default rule's shape,
  coordinator CPU included); a lane with no other core keeps the sibling as a worker CPU (never idle, basis notes it);
  no sibling in the lane / topology unreadable: same CPUs as the default, basis notes it.
- `placement(workers, cpus=None, *, exclude_sibling=False)` (157-164): same 3-tuple return.
- `pinned_pool(context, workers, cpus=None, *, exclude_sibling=False)` (213-221): the keyword threaded to placement;
  docstring points to end_pool.
- `executor(kind, workers, cpus=None, mp_context=None, *, exclude_sibling=False)` (270-284): same; points to end_executor.
- `_worker_cpu(pid)` (287-298), NEW private: a worker's pinned CPU from /proc/<pid>/status Cpus_allowed_list, read before
  the kill (an int for one CPU, a sorted list for several, None when unreadable).
- `_kill_survivors(processes, kills)` (301-320), `_record_kills(kills, report)` (323-333), NEW private: SIGKILL by pid of
  every process still alive (exitcode None), one record each {pid, cpu, at, exit_code} (exit_code filled in once the
  helper reaped it, -9), a pid already gone skipped, an OS refusal recorded with `error`; never raise.
- `end_pool(pool, grace=None, report=None, *, normal=False, label='pool')` (336-382), NEW public: terminate() (or close()
  when normal=True) THEN pool.join(), both in a daemon helper thread, waited `grace` (STOP_JOIN_SECONDS); survivors (the
  pool's workers at entry plus any the pool's own handler forked meanwhile) SIGKILLed and recorded; helper waited `grace`
  more; report['stop_kills'] extended; a helper still alive after that goes to report['stop_incomplete'] (left to end on
  its own, never waited for). Never raises; returns dict(label, how, seconds, kills, joined, errors); end_pool(None) is a
  no-op outcome. A terminate() already in flight elsewhere (a no-op the second time) changes nothing: the join is what
  the bound watches (test 1c found the first draft calling pool.join() unbounded after a no-op terminate; fixed).
- `end_executor(pool_executor, grace=None, report=None, *, label='executor')` (385-433), NEW public: for the
  ProcessPoolExecutor executor() returns (shutdown(wait=True) joins the manager thread, which waits for every running
  task and joins each worker without a bound): shutdown(wait=False, cancel_futures=True), terminate() every live worker,
  join them within `grace` in all, SIGKILL survivors and join again bounded, then the manager thread bounded; kills in
  report['stop_kills']; the running futures end BrokenProcessPool from the executor itself. A thread executor gets the
  shutdown only. Never raises.
- `record(workers, cpus=None, what=None, *, exclude_sibling=False)` (436-447): two additive keys on the
  FRANKIE_LANE_PLACEMENT_V1 dict, `sibling_idle` (the choice, bool) and `idle_cpus` (the sibling threads set aside, []
  when none); schema name unchanged (frankie_box_workflow_inspection reads workers / worker_cpus / basis and ignores
  extra keys).
- `ordered_map(..., exclude_sibling=False, stop_join=None)` (567-670): two new keywords at the end; placement with the
  keyword; `report.setdefault('stop_kills', [])` beside worker_deaths / redone; the cleanup `finally: pool.terminate();
  pool.join()` is now `end_pool(pool, stop_join, report, label='ordered_map')`. Section note (519-530) says so. Results,
  order, the window shrink, the redo rule, exception propagation: unchanged.
- `_RedoResult` (683-711) and `RedoPool` (714-803), NEW public (X1 b): RedoPool(workers, *, context, cpus, poll, attempts,
  report, fallback, on_retry, exclude_sibling) over the same tracked initializer/call as ordered_map; apply_async(function,
  job) -> handle; handle.get(timeout=None) polls `poll` seconds at a time, runs ordered_map's recover rule over every
  outstanding handle (a pid that vanished = a dead worker; its unfinished task and any taken-before-a-later-start task
  are redone, `attempts` pool tries then once in the coordinator or fallback(job)); multiprocessing.TimeoutError after
  `timeout` when given (task stays outstanding); ready(); outstanding(); end(grace, normal) = end_pool; context manager.
  report['worker_deaths'] / ['redone'] / ['stop_kills'] as ordered_map; cpu_map = record(...). The pool replaces a dead
  worker itself (the respawned one takes the next CPU in turn); in-flight bounding is the caller's (ordered_map keeps
  the window); one coordinator thread drives it (a lock guards the bookkeeping).

## The blocking-wait audit (every wait in the module)

- `wait_result` (240): result.wait(poll) then check_alive: bounded, unchanged. result.get() only after ready(): immediate.
- `iterate_ordered` (249): iterator.next(poll) bounded, check_alive on TimeoutError: unchanged.
- `ordered_map`: entry.wait(poll) bounded + recover(): unchanged; started.get() only after started.empty() with one
  consumer: immediate; _Done.get(): immediate; the cleanup was the one unbounded wait (terminate's internal join): bounded.
- `pinned_pool` / `executor` creation: forks only. The end of a pinned_pool is the caller's: end_pool is the rule to call
  (frankie_box_adviser_market holds one; ingest_cpus.end_pool can delegate). An executor's `shutdown(wait=True)` in a
  caller is unbounded: end_executor is the rule to call.
- `RedoPool.get`: result.wait(min(poll, remaining)) bounded; end() bounded.
- In a worker: `_tracked_call`'s started.put (a SimpleQueue pipe write) can block when the coordinator is not draining;
  the coordinator drains every loop turn (ordered_map) / every ready()-get() (RedoPool). Unchanged.

## Tests: scratchpad/lane_pin/test_stop.py (output test_stop_out.txt), 40/40 PASS, three consecutive runs

frankie_box_boss_session imports here without a stub (no torch at import; cpu_topology / core_groups real). A fake
two-threads-per-core topology (FakeSession) is used only for the exclude_sibling test, since this container has one thread
per core.
1. The a2 shape. (1a) Parent holds a flag-only SIGTERM handler; ordered_map with three workers, two blocked in a pipe
   write (an inherited os.pipe nobody reads), the consumer breaks after the first result: cleanup 0.34 s (bound 1 s), every
   worker ended, stop_kills == [], the parent's handler and flag untouched. (1b) The tasks install their own flag handler
   (the reset cannot help): cleanup 1.31 s (1 s bound + the 0.3 s sleep), the two blocked workers SIGKILLed and recorded
   {pid, cpu, at, exit_code -9}, the idle one needed no kill, nothing incomplete. (1c) The pre-session-5 initializer (no
   reset) + the old cleanup shape (pool.terminate() watched in a thread): still running after 2 s with both workers
   alive = the a2 hang reproduced; end_pool on that pool ended it in 1.00 s, 2 kills recorded, the first terminate()
   returned too.
2. ordered_map == serial map on a toy function (12 jobs, 3 workers) without a death; with a worker that SIGKILLs itself
   once on job 3: identical results, one worker_deaths entry, job 3 redone, stop_kills [].
3. The clean path records nothing extra: report == {'worker_deaths': [], 'redone': [], 'stop_kills': []}, no
   stop_incomplete (stop_kills is present as [] beside the two existing lists, for one report shape).
4. exclude_sibling on the fake topology: default placement unchanged (sibling last, 5 and 7 workers); excluded (7 workers
   cycle over the lane minus the sibling; 3 workers the other cores); record() lists sibling_idle / idle_cpus both ways;
   a single-core lane keeps the sibling as a worker (= the default placement, noted); the real topology without siblings
   gives the same CPUs with the basis note.
5. RedoPool: 12 apply_async/get with a self-SIGKILLing worker == serial; death + redo listed; nothing outstanding;
   get(timeout=0.5) on a blocked task raises TimeoutError; end with SIG_DFL workers: no kill; end with SIGTERM-swallowing
   tasks: 2 kills recorded, exit_code -9; cpu_map is a FRANKIE_LANE_PLACEMENT_V1 record.
6. end_executor: two workers stuck in a pipe write with their own flag handler: ended in 1.00 s, both killed and recorded,
   the stuck futures done (BrokenProcessPool); process executor workers under an inherited flag handler report SIG_DFL;
   a clean executor end records no kill.
7. reset_worker_sigterm in a plain fork: 'reset' and SIG_DFL in the child, the parent keeps its handler; 'default' when
   nothing to do; end_pool(None) no-op.

Finding from the first (flaky) runs, kept: a worker still between its fork and its initializer when terminate() arrives
holds the parent's flag handler, swallows the SIGTERM, then sits on the drained inqueue; a pool ended ~1 ms after its start
hit it once (one survivor, killed at the bound and recorded: exactly what (b) is for). The module's reset cannot close
that window (multiprocessing's bootstrap runs the initializer after the fork); it is documented in reset_worker_sigterm's
docstring, and the test makes job 0 sleep 0.3 s so every worker is initialized before the cleanup.

Checks: `python3 -m py_compile`, `ast.parse`, `git diff --check` clean on the module.

## Runtime-unverified / open

- Nothing ran on the box or under the ROOT; the 10 s bound, the kill records and the sibling-idle placement are
  unverified on the 32-CPU lanes with real siblings (the exclude_sibling path ran only on the fake topology here).
- Callers still call their own cleanups: frankie_box_adviser_market's pinned_pool holder, operations/ingest_cpus.end_pool
  (its own helper-thread shape; can delegate to lane_pin.end_pool for one rule), and any `executor().shutdown(wait=True)`
  (frankie_box_school_knowledge, frankie_box_receipts, frankie_box_classroom_code, frankie_box_granite_runner,
  parallel_teacher: thread executors need nothing; a process executor's bounded end is end_executor). Not edited here
  (other owners' files).
- frankie_box_scientific_teacher._default_sigterm (its own per-task reset) is now redundant with the initializer reset but
  harmless; its owner's call.
- The two additive record() keys (sibling_idle, idle_cpus) reach every FRANKIE_LANE_PLACEMENT_V1 receipt from now on;
  frankie_box_workflow_inspection's projection reads named keys and is unaffected (not re-run here).
