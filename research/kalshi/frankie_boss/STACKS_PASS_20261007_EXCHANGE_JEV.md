# Stacks pass 2026-10-07 night (session 5): exchange, Jev, voice, meeting, adviser bridge

Owner: the EXCHANGE / JEV / VOICE / ADVISER stage agent (stage 11 three-way meeting with the Granite coordinator and
voice transport, stage 13 Jev blind comparison, the Jev sit-in, the adviser market bridge). Greg's go (session 5): every
workflow step on the optimizer stacks, CPUs and workers, and the AWS tool upgrades ROOT got. Branch
`ccr-d2f8f826-iefeah-frankie`, base `2f39ddc`. The parent's WIP snapshots (e81c3a7 .. 5905684) carried these edits as
they were made; this record describes the whole delta against `2f39ddc`.

SOURCE-BUILT / RUNTIME-UNVERIFIED. No AWS call, no run, no install, no model call. What ran: py_compile, ast.parse,
bash -n, git diff --check, and four toy self-tests in
`/tmp/claude-0/-home-user-Markets/2248cf40-1f2f-560c-b5b2-bc0289b3f56b/scratchpad/exchange/` (outputs below).

a2 gets none of this unless the work-branch tip is restaged BEFORE a2's exchange, Jev and meeting stages start (after
ROOT, teacher, classroom and search). Stage only the tip, never a WIP snapshot.

## Files

Owned and edited: `deploy/aws/box/frankie_box_jev_cpu.py`, `frankie_box_adviser_market.py`,
`frankie_box_experiment_exchange.py`, `frankie_box_granite_meeting.py`, `frankie_box_granite_runner.py`.
Owned, audited, unchanged: `frankie_box_exchange_voice.py`, `frankie_box_jev_cpu.sh`, `frankie_box_experiment_exchange.sh`,
`frankie_box_granite_meeting.sh`, `frankie_box_granite_meeting_setup.sh`, `frankie_box_jev_reports.sh`, the sit-in module
`research/kalshi/frankie_boss/clm_sidecar/sit_in.py` (claimed: Jev's client; no other owner lists it).
WIP check: e0804ec/e113676 touched `frankie_box_experiment_exchange.py` (LEDGER_POOLS on the context-only line),
`frankie_box_jev_cpu.py` (SI.RENDER_POOLS, cpu_placement) and `frankie_box_granite_meeting.py` (threads_source text).
Every name they use is defined (LEDGER_POOLS exchange:498 at base, sit_in.RENDER_POOLS sit_in.py:249); every owned file
compiled at the start. ea72f31 touched none of my files. No half-edit was left in my files. 45423b6 (experiment.py, not
mine) sets MEETING_THREADS to the lane size and the adviser claim to every CPU: verified at experiment.py:2463-2468, 2942-2949.

## The blocking defect found first

`frankie_box_jev_cpu.execute` refused every request whose lane was not exactly 16 CPUs
(`len(request['cpus']) != 16`, base jev_cpu.py:377-380), while Run.jev (experiment.py:3598, 3614-3616) admits any
`frankie_box_cores.DAY_RUN_SIZES` (16, 32) lane and binds `cpus=list(held['cpus'])`. On DAY_CPUS=32 (a2) Jev would have
refused at its first line. Fixed: the size must be one of `C.DAY_RUN_SIZES`, all distinct (jev_cpu.py:368-378). Session 4's
"Jev on the whole 32-CPU lane at 32 threads" was therefore NOT finished before this pass; the rest of it (lane_threads,
LlamaServer pinning, taskset entry check) was in place.

## Template map (Greg: "ingest, calc and crunch the way its FASTER SIBLING does")

| Sept-29 template item / lane_pin primitive | Where in these pieces |
|---|---|
| pieces side by side | exchange: evidence-count PinnedMap started before the shared read (exchange.py:1430-1450); adviser: `_PinHasher` hashes pins beside the reader constructor (adviser 1730-1830); Jev: `ST.pre_read` native reads beside the part scan (jev_cpu 710-725, new) |
| read once on the lane, consumer on a whole core | `AM.reader_plan` (adviser 1486-1503) via `frankie_box_lane_pin.core_order`; cutoff read once before Jev (`EXCHANGE_CONTEXT_ONLY`, exchange `context_only` ~1900; Run.jev_context_read experiment.py:3749-3770); Jev reuses `<run>/exchange/<day>/shared-market-context.json` (jev_cpu 470-495) |
| pass 1 / pass 2 / pass 3, exact saves at group-closed points | exchange: the retained shared-market-context.json is the input-assembly save point (AM.from_teacher reuse, adviser ~2071); meeting: per-item `ItemProgress` after every round (meeting 1240-1270); Jev: sit_in state.json per call |
| deferred verify / batch decode, every per-record check kept | shared reader (frankie_box_market_timeline, frozen for a2); `_PinHasher` verdicts taken in pin order |
| `lane_cpus()`, `core_order()`, `placement(n)`, `record()` | adviser `lane_cpus`/`core_order` wrappers (adviser 1460-1484), `PinnedMap.record` (LP.record), meeting `_server_cpus` (LP.core_order), runner `files()` (LP.lane_cpus, new) |
| `pinned_pool()` + `wait_result`/`check_alive` (dead worker redone with one fewer) | `AM.PinnedMap` (adviser 1530-1660) over `LP.pinned_pool` and `LP.check_alive`; restart with `workers - 1`; in-process below two |
| `executor('thread')` | granite runner `files()` hashing (runner 19-50, new) |
| `ordered_map()` | not used by these pieces (PinnedMap is the earlier sibling of the same rule); see cross-owner request X1 |

## Audit table A-F (before -> after)

| # | Item | Before (file:line at 2f39ddc) | After |
|---|---|---|---|
| A1 | pools/threads sized from the lane | DONE: reader_plan, PinnedMap(cpus), JEV_THREADS clamped to lane (jev 70-88), MEETING_THREADS = lane size (experiment.py 2463) | unchanged; Jev now admits 32 (DEFECT fixed) |
| A2 | serial consumer on a whole physical core | DONE (reader_plan consumer + idle sibling) | unchanged |
| A3 | ordered hand-off / in-order join | DONE (PinnedMap.results in argument order) | unchanged |
| A4 | dead-worker redo with one fewer | DONE (PinnedMap._wait restart workers-1) | unchanged |
| A5 | every stop bounded | PARTIAL: `PinnedMap.close` = `terminate(); join()` unbounded (adviser 1641-1646); Jev installs a catching SIGTERM handler (jev 453) BEFORE the reader/render pools fork, so a busy worker ignored terminate() and join() hung (reproduced, test 1); LlamaServer.stop bounded 30+10 s (meeting 1138-1152) | DONE: `bounded_pool_close` (adviser 1661-1705) bounds terminate+join at 30 s, SIGKILLs live workers, 30 s more, records `closes`; `_pool_task` restores SIGTERM default in workers (adviser 1517-1528) |
| A6 | shared reads once | PARTIAL: see F1 | see F |
| A7 | sub-steps side by side | PARTIAL: see "Additional CPU spots" | Jev pre_read added |
| A8 | OPENBLAS/llama threads env explicit | MISSING on record (llama.cpp uses --threads; env inherited, unrecorded) | DONE as record: `thread_env()` (meeting 654-657) and `runtime_attention()` (meeting 639-652) on every server attempt's placement and the Jev receipt (`runtime_attention`, jev 814); values unchanged |
| A9 | byte-identical to serial, toy-proven | n/a before | tests 2-3 below |
| B1 | sizes from plan/booking | DONE except the 16-CPU literal in Jev (fixed) | DONE |
| B2 | progress heartbeat with units, units/min, 600 s stall | PARTIAL: report_phase with unit='phases' (base jev 446-450, meeting 1608-1611); units never moved during a model call | DONE: units = tokens generated (`report_model_progress`, meeting 604-636), call in flight / answered from LlamaServer.chat (meeting 1172-1192) and Jev's chat wrapper (jev 650-676), phases/items/calls as fields; the parent heartbeat (frankie_box_stage_progress) computes units/min and STALLED unchanged |
| B3 | run settings exported to children (FA-6) | DONE in Run (not mine); wrappers pass env through (`exec`) | unchanged |
| B4 | DETACH exit semantics (FA-2) | N/A: these wrappers run as Run.child children, never DETACH units | unchanged |
| C1 | S3 ranged/CRT transport | N/A: no owned file reads or writes S3. Inputs are owner-local files; `frankie_box_jev_reports.sh` is an operator read over a presigned map (small objects); `granite_meeting_setup.sh` fetches GitHub/Hugging Face (not S3), one stream each, once per box (day-1 setup, Greg's go) | unchanged; noted |
| C2 | skip re-hash on unchanged stat | Greg's open call (c), NOT done. Sites: adviser `_PinHasher` comment (adviser ~1745); meeting model/binary hashed 4x per meeting (gate via local_runtime 1691, gate 1785, binding 1826, record 1968) and once more in Jev's bind_runtime (jev 104) | unchanged; listed |
| D1 | every skip/wait/refusal/fallback on receipt | DONE mostly (PinnedMap fallbacks/restarts, model_clock, refusals); swallowed: `_pin_child` refusal (meeting ~931, child cannot report; owning affinity bounds it), report_phase/report_model_progress (probe only) | added: pool `closes` records, ledger mode record, `scientific_pre_read` note, meeting `interrupted_calls` |
| D2 | Granite sees the whole picture; only the cap refuses | DONE (system prompt over cap refuses visibly, meeting ~1868) | unchanged |
| D3 | Jev stays blind | DONE (seal before Frankie, JEV_WALL) | unchanged; pre_read reads only what test read |
| E | science unchanged | - | ledger values/order/errors identical (test 2); runner hashes identical (test 3); attention/env/progress record-only; ONE semantic change by Greg's order: meeting re-does an interrupted call (below) |
| F1 | COMPUTE dedupe | cutoff + picture read once (context_only before Jev, reuse by Jev and exchange); REMAINING: teacher rows JSON parsed, hashed and ledgered twice (context_only process and exchange process, exchange.py `teacher_rows` called from `context_only` ~1910 and `exchange` ~1405); model GGUF hashed 4-5x (C2); meeting gate run twice back to back (1691 inside local_runtime, 1785) | ledgers now one pass (F2); the double rows read and double gate remain, listed |
| F2 | PASS dedupe | 19 ledger passes over every row on a fork pool, results pickled back (exchange 478-495) | DONE: `_ledgers_one_pass` (exchange 487-501), one pass with 19 accumulators, bound to `dipole_classroom._dimension_ledger` source sha256 e14080f5...; any mismatch or error runs the serial passes (same first error) |
| F3 | CONTENT dedupe (what Granite/Jev read) | DONE by the existing stacks: meeting input `stacks=True` (meeting 403-470, AM.render_material: STACKED_TEXT_V1 keys once, DIGEST_V10 tables, parse-back proven); Jev material `stacked` encoding with brain dedupe (sit_in 59-61, 648-660); the shared picture via stacked text (adviser 59, 150-300) | unchanged; no new format. Remaining repetition: the system prompt (charter + whole picture) is re-sent on every coordinator call (stateless chat); llama-server's prompt cache reuses its KV on consecutive calls (--parallel 1), so compute is not repeated; tokens on the wire are |

## Changes (functions and line ranges, current tip of the working tree)

1. `frankie_box_jev_cpu.py`
   - `execute` 368-378: lane size one of `frankie_box_cores.DAY_RUN_SIZES`, distinct CPUs (was exactly 16).
   - `_run.phase` 452-454: heartbeat through `transport.report_model_progress` (units = tokens generated).
   - `_run.chat` 650-676: call in flight / answered progress; usage read from the reply (reply unchanged).
   - `_run` 710-725: `ST.pre_read(days, [doc], scientific_dir)` then `ST.test(..., scanned=)` (cross-owner R4), fallback to
     the old reads when the scientific teacher lacks pre_read; `placement['scientific_pre_read']` on the receipt.
   - receipt 811-815: `runtime_attention` (Greg's open call (a), record only).
2. `frankie_box_adviser_market.py`
   - `_pool_task` 1517-1530: SIGTERM default restored in pool workers.
   - `PinnedMap.close` 1651-1658 and new `bounded_pool_close` 1661-1705.
3. `frankie_box_experiment_exchange.py`
   - `DIMENSION_LEDGER_SOURCE_SHA256`, `_ledgers_one_pass` 478-501, `_ledgers` 504-540 (record mode one_pass /
     serial_per_column into LEDGER_POOLS). `_ledger_task` kept (unused, harmless).
4. `frankie_box_granite_meeting.py`
   - `MODEL_PROGRESS`, `report_model_progress` 604-636; `FLASH_ATTENTION_FLAGS`, `THREAD_ENV`, `runtime_attention`,
     `thread_env` 637-657; `LlamaServer._start` 881-935 records them (~925); `LlamaServer.chat` progress; `_meeting.phase` and the
     per-item heartbeat use tokens as units.
   - `discuss_item` (1284) pending branch ~1312-1340 and the caller's three `retained.get('status') != 'complete'` checks
     (1898, 1911, 1915): an interrupted call is RE-DONE (see below); docstring updated.
5. `frankie_box_granite_runner.py` `files()` 19-50: hashes on `LP.executor('thread')` (<= 8 threads), sorted order kept;
   serial fallback with the same first error.

### The one semantic change (Greg, relayed 2026-10-07 night: "a model call that was interrupted is re-done, never skipped")
Before: a retained pending pre-send intent closed the item `LEFT_OPEN_BY_CODE` (`interrupted_call`) without a call.
After: the intent is stamped `unknown_completion` on the model clock (kept), listed in the item progress
`interrupted_calls` with `redone: true`, and the round is re-sent from the SAME retained transcript (refused if the
intent's transcript sha256 differs from the retained one: explicit owner recovery). The re-sent request is identical
(test 4). The meeting record's `interrupted_call_items` is now normally empty; the clock keeps both stamps.
Jev is NOT changed: its state lists unresolved calls and Run records `waiting` ("none is retried or erased",
experiment.py:3683-3688, not mine; sit_in call accounting). Cross-owner request X3.

## Tests run (toy, scratchpad/exchange/)

1. `hang_repro2.py` (the hazard): a fork Pool with a caught SIGTERM inherited and a busy worker:
   `default closed 0.0` / `caught HUNG after 8 s 8.0` (left running until killed). Same shape as the a2 shard exit hang.
2. `test_close.py` (adviser `bounded_pool_close` + `_pool_task`, extracted by ast):
   `raw task (no reset): SIGKILL path sigkill_after_bound killed=1 3.0 s`;
   `_pool_task (reset): terminate path terminate_join killed=0 0.0 s`; `parent SIGTERM handler kept: True`.
3. `test_ledgers_runner.py`: `mirrored source sha256 matches: True`; `one pass == serial (pickle bytes): True keys in
   order: True` (5,000 rows x 19 columns); `same error: True ('ValueError', 'teacher row column order changed')`;
   `runner files() == serial: True 40 files` (0-3 MB random files, threaded vs serial).
4. `test_meeting_redo.py` (real `discuss_item` with a fake server): `attempt 1: LEFT_OPEN_BY_CODE pending kept: True status:
   interrupted`; `attempt 2: LEAVE_OPEN status: complete interrupted_calls: 1 redone: True`; `re-sent request identical to
   the interrupted one: True`; stamps `failed`, `unknown_completion`, `answered` for r1.
Not tested: the Jev 32-CPU admission (needs a held booking), the model-call heartbeat (needs a Run.child), pre_read in Jev
(needs real search parts), the attention/env record (needs llama-server). All RUNTIME-UNVERIFIED.

## Greg's open call (a), documented, values left
- Jev threads: `JEV_THREADS = 32` (jev_cpu.py:42), clamped to the lane (`lane_threads`, jev 70-88); on a 32-CPU lane all 32
  hardware threads (both siblings of every core), on 16 one per core. Bound into Jev's owner identity
  (`shared_runtime.threads`, jev ~438).
- Meeting threads: `MEETING_THREADS = None` -> the day lane size (experiment.py:180, 2463-2468), clamped to the affinity by
  `threads_resolution` (meeting 586-604); passed as `--threads` (meeting 891).
- Attention: no `--flash-attn` flag passed (command, meeting 890-892): llama-server b11440 default `auto`, ON for the CPU
  backend; split-KV decode reduction depends on the thread count (jev_cpu.py:70-80 note). Now explicit on every attempt
  record (`placement.attention`, `placement.thread_env`) and the Jev receipt (`runtime_attention`). `--threads-batch` not
  passed (= --threads).
- Jev runtime pins: Jev binds Granite's shared definition (no JEV_CPU_RUNTIME_V1 file); a blank or differing pin refuses
  visibly (`bind_runtime` -> model_clock not_called + ValueError -> status waiting). Nothing borrowed or skipped.

## Additional CPU spots (walk end to end; shares are estimates, nothing measured)

Ranked by expected gain. "Built" = done in this pass.

1. The llama.cpp calls (Jev and the meeting): the whole stage's dominant share (estimated 80-95% of Jev and meeting wall).
   Uses `threads` CPUs of the lane pinned in core order (meeting `_server_cpus` 976-990): 32 threads = every CPU of a
   32-CPU lane, 16 = one per core with the 16 siblings idle. The calling Python process waits on HTTP. Anything beside it
   competes with a memory-bandwidth-bound decode whose threads spin at barriers, so it slows the call; it would not change
   the model's inputs or text (the text depends on the thread count only). Candidates beside a call: Jev's
   `ST.load_searches` + `ST.pre_read` (inputs fixed before the claims; could prefetch during the calls on the sibling
   threads when threads = physical cores), the meeting's per-item `_layer_counts` /tokenize of the NEXT item. Blocked by
   Greg's call (a) (32 vs 16 threads decides whether idle CPUs exist at all).
2. Meeting items discussed serially (meeting ~1880-1915), one server slot (`--parallel 1`). Concurrent items need
   `--parallel N` (splits the context and batches sequences together: different numerics) or N servers (thread split).
   Changes outputs: Greg's call.
3. Teacher rows parsed, hashed and ledgered twice (context_only and the exchange step, two processes; exchange.py
   `teacher_rows`). Estimated a few % of the exchange. Fix: the context-only step retains the pinned rows identity and
   ledgers (pickle + manifest bound to the rows sha256 and the mirrored ledger source) for the exchange to load. Not built
   (new retained artifact; wanted Greg-visible). The one-pass ledgers (built) already cut most of the cost.
4. Model GGUF and llama-server hashed 4-5 times per meeting/Jev (C2). Estimated 1-2 s per 2 GB hash. Blocked by open call (c)
   for the cross-time re-hashes; the back-to-back double gate (meeting 1691 and 1785) could be one: not built (the two
   differ in the binary=None case; needs care).
5. Exchange item loop (boss_turn, scientific turn per item) serial after the prefetch (exchange ~1450-1700). The heavy
   counts are prefetched on the pool; the remaining per-item work is small. Low gain.
6. Shared picture consumer: one serial ordered consumer on a whole core, 30 decode workers (frankie_box_market_timeline).
   Frozen for a2 (hashed into the binding); queued requests (start-at-cursor, double spool read) belong to that owner.
7. Jev report rendering and brain publication (jev ~735-790) serial, small. Report rendering could overlap the scientific
   test (independent inputs) on a thread: low gain, not built.
8. Granite runner hashing: built (thread executor). Voice validator: per-item, microseconds, N/A (and not wired).
9. Uploads: none in these pieces (owner-local outputs); the GitHub route of the meeting is the listed fallback, unused.

## Cross-owner requests
- X1 `frankie_box_lane_pin.py` (shared helper owner): `ordered_map`'s `finally: pool.terminate(); pool.join()` (lane_pin
  ~436-437) and `pinned_pool` workers keep an inherited caught SIGTERM: the same unbounded join. Reset SIGTERM to SIG_DFL
  in `_pool_initializer`/`_tracked_initializer`, and bound the close (the `bounded_pool_close` pattern, adviser 1661).
- X2 `frankie_box_experiment.py` (Run): nothing needed for the 32-CPU Jev fix (Run already binds the lane); please keep
  `request['cpus']` = the held booking's CPUs.
- X3 Jev interrupted calls re-done (Greg's rule as relayed): experiment.py:3683-3688 records waiting on
  `unresolved_calls` and never re-dispatches; sit_in's call accounting (`intents_without_reply`) and jev_cpu.py
  (`client['call_accounting']['intents_without_reply']` raise, 702) would need the meeting's pattern (stamp
  unknown_completion, re-send from the retained state). Not changed here: it changes Jev's documented rule ("no model
  request is retried or erased") and needs Run's side; Greg to confirm it applies to Jev too.
- X4 R4 from the school owner (ST.pre_read / test(scanned=)): DONE in jev_cpu.py 710-725.
- X5 frankie_box_market_timeline.py: no request from these pieces beyond the ones queued after a2.

## Remaining / not done
- Exchange ledger save point (pickle) and the double teacher-rows read (spot 3).
- Double gate dedupe in the meeting (spot 4); stat-skip re-hash (open call (c)).
- Jev interrupted-call redo (X3).
- Everything above is SOURCE-BUILT / RUNTIME-UNVERIFIED; first runtime evidence will be the restaged one-day run.
