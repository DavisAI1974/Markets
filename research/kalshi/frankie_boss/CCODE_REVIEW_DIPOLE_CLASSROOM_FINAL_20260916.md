# ccode final review - Dipole classroom hardening commits (2026-09-16)

Reviewed: `chatgpt/frankie-dipole-classroom-20260916` at `0b290a30` (commits `38b90e16` and
`0797d54f` on top of my earlier review `f6f3787f`), against the architecture reviewer's ten
carry-forward items and the fourteen review requests in
`CCODE_HANDOFF_DIPOLE_CLASSROOM_FINAL_REVIEW_20260916.md`. Review commits are on
`ccode/frankie-dipole-classroom-review-20260916`, fast-forwarded to that tip first. No Frankie,
Granite, EC2, market-data or result-bearing run; unit tests on temporary fixtures only.

## Executed, because the handoff said it never was

The two post-review commits had been syntax-checked, not run. On the workstation (Python 3.13.7,
torch 2.9.1+cpu, numpy 2.3.5):

| suite | before this review | after |
|---|---|---|
| test_dipole_classroom, _session, _hardening, _final_review, test_sunday_execution, principal adapter, source contract, cycle review fixes, integrated recovery | 53 passed | 59 passed (6 new) |
| whole `tests/` directory | see the commit message for the count | |

Science drift (request 13): `dipole_target.py`, both teachers, both normalisers, `c15_dstate.py`,
`context_session.py`, `prepared_context_cache.py`, `b1_reasoner.py`, `boss_training_checkpoint.py`,
`feedback_cycle.py`, `frankie_principal_adapter.py`, `operations/run_actual_sunday.py`,
`native_mbo_encoder.py`, `trunk.py`, `c15_journal.py`, `causal_packet.py`, `research/refrag`:
byte-identical to the lawful `050c5056` (`git diff --stat` empty). The branch touches only the
classroom modules, the classroom wrapper, `run_actual_sunday_ec2.py` (routes through the wrapper),
`source_contract_runtime.py` (adapter class + `classroom_package` argument) and
`sunday_execution.py` (`classroom_package` field and the two binding checks).

## Defects found and fixed on this branch

1. **Answer-key material was still written into the model-facing principal directory.** Only the
   teacher-key FILE had been removed. Both new adapters' `prepare()` still retained
   `dipole-classroom-source.json` there before Frankie's first answer, and it holds every retained
   value and state for all 19 columns, which is what the teacher key is derived from; the full
   post-grade (every actual observation and all 171 actual relations) followed after the answer.
   Fix: the base classroom adapter gains a host-owned `audit_directory` (default
   `<cycle>/classroom-audit`, refused if inside the principal directory) and `_retain_audit()`;
   source, teacher key and full post-grade go there in all three adapters; the host wrapper reads
   the prior post-grade from there. Proven end to end through `FinalDipoleClassroomPrincipalAdapter`
   in SOCRATIC mode: with distinctive retained values, no file in the principal directory other
   than Frankie's own responses and the transcript that prints them contains a value; source, key
   and post-grade are absent there and present in the audit directory
   (`test_final_adapter_keeps_answer_key_material_out_of_the_principal_directory`, the first test
   that drives the final adapter's whole two-turn flow rather than inspecting its source).
   **Limit, stated plainly:** a session that can read the run directory can read `classroom-audit`
   too. The layout withholds the key only from a session whose filesystem scope is the principal
   directory; that scope is the guard, and it belongs to the host that dispatches Frankie.
2. **The intermediate hardened adapter crashed on every cycle after the first.** Its
   `_recover_with_classroom` rendered the transcript through `render_pre_message`, which
   dereferenced `teacher_closing` and `component_grades` on the prior-correction SUMMARY the same
   layer had just substituted (`KeyError`). Not on the production path (the final adapter
   overrides it) but exported and reachable. Fix: the summary now originates in the core
   (`dipole_classroom.prior_correction_summary`, emitted by `build_pre_message` itself), so no
   layer strips and re-adds it, and the renderer accepts only the summary shape and refuses a full
   grade. Proven for the core, hardened and final builders.
3. **A narrative HYPOTHESIS could coexist with a factual ledger classification.** The cross-check
   skipped HYPOTHESIS outright, which Greg ruled out. Fix: the 171-pair ledger is authoritative;
   a narrative HYPOTHESIS is an additional hypothesis only when the ledger also records a
   `developing_structure` for that pair, otherwise it is a `representation:` item that lowers
   mastery. Proven both ways.
4. **The transcript printed only the message text of each review item**, while Frankie received
   the item's data fields (`frankie_said`, `data_shows`, `specific_differences`). The section
   claimed to be "exactly the evidence review sent back"; now it prints every field of every item
   and the inspected-evidence statuses of each novelty investigation.
5. **Magic cycle bound.** The final layer had avoided `cycle_index < 19` by copying the 40-line
   core snapshot function with one extra parameter. Fix: the core `snapshot_teacher_attachment`
   and `prepare_cycle` take a required `cycle_count`; the final layer delegates; the wrapper
   derives it from the retained schedule steps (already did) and its request search globs
   `execution/cycle-*` instead of `range(19)`. Still hard-coded and deliberately untouched: the
   lawful base host's `range(19)` (lawful file) and `load_contract`'s `len(cycles)!=19` in
   `source_contract_runtime.py`, which is the Sunday contract's own shape; both become manifest
   fields with the block work, not here.
6. **Pearson floor declared once.** `MIN_PEARSON_PRESENT_OVERLAP = 8` lives in the core and the
   core `_pearson` applies it; the hardened re-pin is now an identity on a core-built key and the
   message text reads the constant. New proof on a real 8-row and 7-row key through the real
   builder: coefficient reported at 8, suppressed at 7 with the overlap count retained. The prior
   test only exercised a synthetic key.
7. **Curriculum record.** `learning_measurement` and `independent_discovery_eligible` are now in
   the binding and the completion record, not only the receipt, so the completion history that
   `select_hardened_mode` consumes never reads a TEACH pass as a discovery.
8. Tautology `prior_cycle_change_reviewed: key["cycle_index"]==0 or True` replaced by `True` with
   the reason (the raise above it is the check). Three files' trailing newlines restored
   (`run_actual_sunday_ec2.py`, `source_contract_runtime.py`, `sunday_execution.py`); on-disk bytes
   feed the host code hash.

## The fourteen review requests

| # | request | verdict |
|---|---|---|
| 1 | no answer-key leak-back | correction turn: correction items only (claimed, actual, explanation per corrected item); next cycle: identifiers, count, mastery. Verified; the filesystem half was open and is fixed (item 1) |
| 2 | transcript fidelity | fixed (item 4); the transcript is now the model-visible exchange, field for field |
| 3 | novelty non-punitive | verified: `investigate_novel_findings` never touches the grade, `scored_for_classroom_mastery` is False. Caveat: a MALFORMED novel finding raises and aborts the recovery, like any malformed ledger; strict by the same rule as everything else, not a mastery penalty |
| 4 | granular contradiction | verified: every difference names one observation, pair or field, says "the data is showing ... instead" and that the broader premise stays open; no "wrong" in the model-facing text |
| 5 | investigation before response | verified: exact Dipole refs are checked before the correction request exists; other causal evidence is retained as not-yet-testable |
| 6 | discovery attribution | verified and now carried in binding and completion (item 7) |
| 7 | relationship cross-check | fixed (item 3): HYPOTHESIS is distinct only when the ledger marks a developing structure |
| 8 | root-cause grouping | verified: pair items whose endpoint has a direction miss group under that component root; all 18 pairs of one wrong direction under one root while all 19 correction ids stay individually retained. Chain stops at the component: a wrong first/last PRESENT observation that CAUSED the wrong direction is not attributed further |
| 9 | Pearson floor | verified and consolidated (item 6) |
| 10 | taper regression | verified: one level back on a non-mastered cycle, two consecutive mastered cycles at the current level to advance again |
| 11 | audit-key filesystem isolation | was incomplete (source snapshot and post-grade); fixed (item 1) with the scope caveat |
| 12 | schedule-bound snapshot | verified and simplified (item 5) |
| 13 | no science drift | verified byte-identical, list above |
| 14 | wrapper seam | unchanged: `main()` patches `source_contract_runtime.DipoleClassroomPrincipalAdapter`, `base.ActualHost` and `base.await_recorded_principal`, and `runtime()` patches `driver.SundayRuntime` around one call. Greg accepted this for the isolated branch. At integration the seam is a constructor argument on `SundayRuntime`/`make_principal_adapter` (the adapter class), not a module rebind |

## Left as is, named

- `dipole_classroom_hardening.py` is now an intermediate layer whose adapter and correction
  builders are superseded by the final layer; only `select_hardened_mode` and the key re-pin are
  live. Collapse it into the final module at integration, not before the branches meet.
- The core `_direction_relation` maps FLAT to UNRESOLVED, so a FLAT/FLAT pair is UNRESOLVED, not
  SAME_DIRECTION. Consistent with the stated direction definition; recorded so nobody reads
  UNRESOLVED as "no data".
- `validate_novel_findings` requires the `dipole_novel_findings` key on every response (empty list
  allowed, absent key refused). The instruction says so; the receiver prompt must keep saying so.
