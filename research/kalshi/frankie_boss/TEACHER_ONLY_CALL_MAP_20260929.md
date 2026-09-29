# Teacher-only step: how the launch calls the Dipole teacher, and how to call it without a launch (2026-09-29)

Research for handoff item 1 (`HANDOFF_20260929_EXPERIMENT_BUILD.md`), read from the code (file:line), not run.
Paths are under research/kalshi/frankie_boss/ unless another directory is named.

Summary: no model, Pod or schedule is needed. `concurrent_teacher._run` (concurrent_teacher.py:103-137) is already a
teacher-only process (reader + bare builder + the teacher's pass + finish). The new step follows that pattern and
builds the context spec itself.

## 1. The launch's chain
- operations/run_actual_sunday.py:656-690 `prime_cache`: without a retained recovery it replaces `context._prepare`
  with `prepare_parallel(context, as_of, through_cursor)` (:681-683), then `api.prepare_context_cache`.
- parallel_journal.py `prepare_parallel` (:577) runs `parallel_walk` (:516-574) around the unchanged
  `type(context)._prepare`: sets `module.journal_prefix = parallel_journal_prefix`, `_ENTITY[0] = context.entity`,
  `T.evidence_hash = _chain_hash_factory` (:461), `JournalTeacherR3.attach = parallel_teacher.parallel_attach`, applies
  `teacher_changes.apply()` (:513) + `install_binding()` (:499) unless FRANKIE_TEACHER_CHANGES=0, and starts
  `concurrent_teacher` only for a `FrankieCompactReader` journal.
- context_session.py:152-199 `_prepare`: walks `journal_prefix`, keeps rows with ts_recv <= as_of for entity
  (publisher_id, instrument_id), the last t_ctx by (recv, cursor); rows are 7 fields (cursor, raw_record, normalized,
  source_member_index, session_id, integrity, terminal_prefix_hash); :189 `self.teacher.attach(journal_prefix(builder,
  through_cursor), context, as_of=as_of, source_manifest_hash=builder.scope.scope_id)`.
- parallel_teacher.py:454 `parallel_attach`: the concurrent teacher if running, else `row_pass` (:353) then
  `finish(self, rows, processed, entity_hashes, context_spec(context), source_manifest_hash=...)` (:389).
- c15_teacher_r3.py:310-377 `attach(evidence, context, *, as_of, source_manifest_hash)`; constructor
  `JournalTeacherR3(tick_raw, *, normalizer)` (:287); the launch uses `JournalTeacherR3({111313: 1000000},
  normalizer=IdentityNormalizerR3((111313,)))`, entity (1, 111313) (sunday_native_runtime.py:69-72). `as_of` is only an
  upper-bound check (c15_teacher_r3.py:227, c15_teacher.py:84, teacher_changes r3_iter_raw).
- dipole_classroom.py:198-240 `snapshot_teacher_attachment(teacher, *, request_id, cycle_index, cycle_count,
  source_hash, as_of, through_cursor)`; the launch saves package["source"] with sunday_execution `_save` (:45,
  canonical_bytes(pack(body))). The teacher-only step needs only the snapshot.

## 2. retained_preparation_recovery.py
Needs a live context and a retained native prompt snapshot (:48-72), which a new day does not have; its serial
VerifiedJournalReader view (:93-104) is the pattern, not the function to call.

## 3. Context rows for a whole day
model_context_rows = count (trading_day_schedule.py:216; frankie_box_author_monday_launch.py:201): the context is every
entity (1, 111313) row of the day. through_cursor = record_count - 1; source_hash = the terminal source_prefix_hash;
as_of = max ts_recv; cycle_index 0, cycle_count 1. `row_pass` returns entity_hashes; spec = [(c, True, h) for c, h in
sorted(entity_hashes.items())] matches `_prepare`'s selection. CAVEAT: with that spec the exact-row check in `finish`
compares the rows with themselves and proves nothing; an independent check needs a second walk (listed, Greg's call).
Use a bare builder (not completed_schedule_view: it wraps the reader, so the FrankieCompactReader check fails and the
step falls back to one CPU). scope not needed: receipt manifest_hash == scope_id (operations/prepare_trading_day.py:66-67).

## 4. Pinned: call, never edit
frankie_box_projection.py, context_session.py, c15_journal.py, c15_teacher_r3.py, the normalizers (c15_normalizer.py,
c15_normalizer_r3.py), c15_teacher.py, dipole_target.py, frankie_journal_reader._read_block, the model-hash files
(context_session.py:136-137). Keep teacher_changes.py unchanged too: its sha256 enters candidate_digest
(teacher_changes.py:42, parallel_teacher.py:345-350).

## 5. Resources
FrankieCompactReader(workers=1..64) pins workers to the process's own affinity minus the first CPU
(frankie_journal_reader.py:40-45, 83). parallel_teacher._cpus() = affinity - 1 (:334), for the raw-streams pool and the
finish pool. Days in parallel: each under taskset on its own CPUs. Walk cache defaults to <journal dir>/walk-cache
(parallel_journal.py:208), INSIDE the sealed ingest directory: set FRANKIE_WALK_CACHE to a per-day scratch directory.
Memory: row_pass keeps one tuple per record (Monday 2,032,203) plus one DipoleTarget per entity row; unmeasured
(several GB/day expected). Timing: no finished whole-day teacher run is recorded (r9 stopped; its handoff expected
~20-25 min per walk + ~25 min finish; HANDOFF_20260928_R9_PARALLEL.md:18-20, 57).

## Proposed call sequence (pseudo-code with the real names)
```python
# env: FRANKIE_TEACHER_CHANGES=1; FRANKIE_WALK_CACHE=<day scratch>; run under taskset <day CPUs>
from research.kalshi.frankie_boss import parallel_journal as PJ, context_session as CS, c15_teacher_r3 as T, \
    parallel_teacher as PT, teacher_changes as TC, dipole_classroom as DC, sunday_execution as SE
# rc = ingestion-receipt.json; verify journal bytes/sha256 + completion.json as frankie_box_experiment_root.py does
TC.install_binding()
teacher = T.JournalTeacherR3({111313: 1000000}, normalizer=IdentityNormalizerR3((111313,)))
reader = FrankieCompactReader(journal, expected_count=rc['journal_count'], expected_head_hash=rc['journal_hash'], workers=W)
builder = SimpleNamespace(journal=reader, _failed=False, chain=SimpleNamespace(next_cursor=rc['record_count']))
through = rc['record_count'] - 1
PJ._SERIAL = CS.journal_prefix; PJ._ENTITY[0] = (1, 111313)
h0 = T.evidence_hash; T.evidence_hash = PJ._chain_hash_factory(h0); TC.apply()
try:
    ev = PJ.parallel_journal_prefix(builder, through, None)
    rows, n, hashes = PT.row_pass(teacher, ev, as_of=BOUND, source_manifest_hash=rc['manifest_hash'])
    as_of = max(r[4] for r in rows)
    spec = [(c, True, h) for c, h in sorted(hashes.items())]
    att = PT.finish(teacher, rows, n, hashes, spec, source_manifest_hash=rc['manifest_hash'])   # before TC.restore()
finally:
    TC.restore(); T.evidence_hash = h0; PJ._ENTITY[0] = None; PJ._CANONICAL.clear(); PJ._SUBSETS.clear(); reader.close()
src = DC.snapshot_teacher_attachment(att, request_id=<chosen>, cycle_index=0, cycle_count=1,
        source_hash=rc['source_prefix_hash'], as_of=as_of, through_cursor=through)
SE._save(out / 'host-dipole-classroom-source.c15.json', src)   # out = /opt/frankie-box/work/experiment-teacher-rows/<day>/
```

## Not settled by the repo (list, do not guess)
BOUND (no max ts_recv stored in the receipt; any int >= the real max is safe, as_of is only a check); whether the
normalized ts_recv_ns equals the raw ts_recv the schedule takes its max over; request_id (the launch uses
<run_id>-cycle-00); real wall time and memory; byte parity with a launch's source (untested).
