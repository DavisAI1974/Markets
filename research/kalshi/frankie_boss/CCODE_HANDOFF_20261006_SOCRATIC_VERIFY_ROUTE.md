# CCode handoff, 2026-10-06: the SOCRATIC/VERIFY independent evidence route

**Historical handoff, superseded on the current Codex branch:** Greg subsequently authorized the second learner walk
for accumulated-knowledge recognition. `frankie_box_classroom_reader.py` and its runner connection now reuse the pinned
measurement walk in a learner-owned directory; the external adapter is called with that lawful evidence. All four mode
readers are source-wired, runtime-unverified. Re-measurement with the same instrument is not independent scientific
confirmation. The refusal/uncalled/open-permission statements below describe the earlier checkpoint only. Read
`HANDOFF_20261006_STEP2_KNOWLEDGE.md` for the integrated state. No AWS go or E2E result follows from this authorization.

Branch: `ccr-e9f0f4af-lqxmss` (CCode's parallel branch), based on Codex checkpoint `82649247`.
Commits on it, both `[skip ci]`, both SOURCE-BUILT / RUNTIME-UNVERIFIED (py_compile, module import, diff review only):

- `8b14182f` GUIDED: answer GUIDED days from the visible observations with the teacher's own math (integrated by Codex).
- `c547c01a` SOCRATIC/VERIFY: independent day-file reader for the external section; precise refusal reasons.

Files owned by CCode: `deploy/aws/box/frankie_box_classroom_code.py`, `deploy/aws/box/frankie_box_classroom_external_code.py`.
Nothing else was edited: runner, lane state, brain, scientific teacher, exchange, grading, visibility, pinned files and
all scientific mathematics are unchanged. No tests, installs, dispatch, E2E or AWS action. Work stopped before #5.

## Where the classroom modes stand

| Mode | Code seat | Evidence source |
| --- | --- | --- |
| TEACH | answers (transcribes) | the pre-message shows everything |
| GUIDED | answers (recomputes) | visible observations; terminal state, direction and the 171 pairs computed with `dipole_classroom._direction`, `_pearson`, `_co_movement`, `_direction_relation`; external facts/alignment from visible known values and row runs, series x Dipole pairs from the V1 observations Codex passes as `dipole_visible` |
| SOCRATIC, VERIFY | refuses, reason names the gap | no lawful independent producer of the 19 dimensions exists (below) |

Mastery progression (`select_integrated_mode`), PREVIOUS history and `learner_context` are untouched; GUIDED can
be reached and mastered lawfully; SOCRATIC is the first mode the curriculum cannot enter.

## The trace: why SOCRATIC/VERIFY still refuse

The 19 Dipole dimensions (`c15_normalizer.COLUMNS`) have exactly one producer in the repository: the pinned C15
teacher walk over the sealed journal, `c15_teacher_r3.JournalTeacherR3.attach` run through
`parallel_teacher.parallel_attach`, snapshotted by `dipole_classroom.snapshot_teacher_attachment`. Checked:

- A grep for the column names over `research/` and `deploy/` finds only `dipole_classroom.py`, `c15_normalizer.py`,
  `frankie_principal_adapter.py` and tests; the three box modules that matched did so on the word "replenishment".
- The experiment ROOT (`frankie_box_experiment_root.py`) runs the legacy pass only: five legacy layers and the row
  spools (decoded INPUT records), bedrock off. It does not compute Dipole targets.
- The data export (`frankie_box_experiment_data.py`) includes the teacher-only step's rows as data, but those are
  the same audit snapshot the mode withholds; reading them in SOCRATIC/VERIFY would bypass the withholding. Excluded.
- `TEACHER_ONLY_CALL_MAP_20260929.md` section 3 already records: "an independent check needs a second walk (listed,
  Greg's call)".

The external section is different. Every pre-message, in every mode, carries the day file's path and sha256, the
cutoff and the open, and the file is readable without the key through `operations/frankie_day_external.AsOfReader`.
`frankie_box_classroom_external_code.independent_day_file_evidence(pre)` now reuses the reading half of
`build_external_key` (`open_day_external`, `read_series`, `_facts`, `reader.until` for table counts) and returns every
known value, each series' facts including the table's not-yet-known count, each point's tables and the missing lists.
It lists what it cannot supply: the per-row alignment (needs the Dipole rows' timestamps) and every pair (needs the
Dipole ledgers). It has no caller until the Dipole route exists; `answers()` keeps refusing SOCRATIC/VERIFY.

## The question for Greg

To let SOCRATIC/VERIFY run, Frankie's seat needs the 19 dimensions at the classroom cursors without reading the
teacher's snapshot. The only instrument in the repository is the teacher's own pinned walk. The proposal is an adapter
under Frankie's seat that re-walks the sealed journal with that pinned teacher at the binding's `through_cursor` and
`as_of` (the same `row_pass` then `finish` path `frankie_box_experiment_teacher.py` uses; inputs: the ingestion receipt
and journal from the ROOT's source binding, the day's entity), snapshots it, and feeds `_evidence()` the way GUIDED is
fed. Two things make this Greg's ruling rather than an engineering default:

1. Cost: it repeats the heaviest stage once per classroom day (the teacher pass is days of one CPU, hours on a
   16-CPU lane), inside the day's held lane.
2. Meaning: a re-measurement with the same pinned instrument on the same bytes yields rows identical to the teacher's.
   Whether that counts as the "independent recognition" SOCRATIC/VERIFY are meant to measure, or whether Frankie's
   independent reading should come from his own calculation surfaces (which do not contain these 19 quantities), is a
   scientific decision.

Until that ruling, the refusals stay as they are and the curriculum tops out at GUIDED. This is a launch limitation,
not a reason to reset history, force TEACH or expose the key.

## Settled constraints carried forward

AWS CPU only; no Pods; three held 16-CPU lanes (two main, one Linux), 15 workers plus coordinator; a day stays on its
lane from ROOT to completion; giant artifacts stay local. All 30 days accumulate knowledge regardless of trading date.
Checked single occurrences receive equal treatment; no caps, no changed discovery/fitting mathematics. Stop before #5;
Granite's report is handled separately; Jev's CPU route needs discussion.
