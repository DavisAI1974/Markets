# ccode handoff, Dipole classroom (2026-09-16, end of day)

For the chat reviewers (ChatGPT, Claude Desktop). Repository `DavisAI1974/Markets`.

## Where the work is

| branch | tip | content |
|---|---|---|
| `chatgpt/frankie-dipole-classroom-20260916` | `0b290a30` | ChatGPT's classroom plus the two hardening commits (`38b90e16`, `0797d54f`) and the handoff asking for their review |
| `ccode/frankie-dipole-classroom-review-20260916` | see `git log -1` | that tip, fast-forwarded, plus ccode's review commit: fixes, tests, `CCODE_REVIEW_DIPOLE_CLASSROOM_FINAL_20260916.md` |

Rebase target for any further classroom work: the ccode review branch. It contains everything on the ChatGPT branch.

## What the review found in the two hardening commits

The handoff said the commits had been syntax-checked, not run. Run: 53 tests green as committed.
Science files (targets, teachers, normalisers, context session, cache, reasoner, checkpoint,
lawful host, base principal adapter, encoder, journal, packet, refrag) are byte-identical to the
lawful `050c5056`. Then, against the architecture reviewer's ten items and ChatGPT's fourteen
review requests, these defects, each now fixed with a test that drives the real code path:

1. **Answer-key material still reached the model-facing principal directory.** Only the teacher-key
   FILE had been removed. Both new adapters' `prepare()` still wrote the source snapshot there
   before Frankie's first answer, and that snapshot holds every retained value and state the key
   is derived from; the full post-grade followed after the answer. Fix: a host-owned
   `audit_directory` on the base classroom adapter (default `<cycle>/classroom-audit`, refused if
   inside the principal directory); source, key and full post-grade go there in all three
   adapters; the wrapper reads the prior post-grade from there. Proven end to end through
   `FinalDipoleClassroomPrincipalAdapter` in SOCRATIC mode with distinctive retained values: no
   file in the principal directory other than Frankie's own responses and the transcript that
   prints them contains a value. Stated limit: a session that can read the run directory can read
   the audit directory too; the guard is the session's filesystem scope, which the host owns.
2. **The intermediate hardened adapter crashed on every cycle after the first**: its transcript
   renderer dereferenced full-grade fields on the correction summary the same layer had just
   substituted. Fix: the summary now originates in the core (`dipole_classroom.prior_correction_summary`,
   emitted by `build_pre_message`), no layer strips and re-adds it, and the renderer accepts only
   the summary shape. Proven for the core, hardened and final builders.
3. **A narrative HYPOTHESIS could coexist with a factual ledger classification** (the cross-check
   skipped HYPOTHESIS). Greg ruled that out. Fix: the 171-pair ledger is authoritative; a narrative
   HYPOTHESIS is an additional hypothesis only when the ledger records a `developing_structure` for
   that pair, otherwise it is a `representation:` item that lowers mastery. Proven both ways.
4. **The transcript printed only each review item's message text** while Frankie received the
   item's data fields. It now prints every field of every item and each novelty investigation's
   inspected-evidence statuses, so the transcript is the exchange.
5. **Magic cycle bound**: the final layer had copied the 40-line core snapshot function to avoid
   `cycle_index < 19`. Fix: core `snapshot_teacher_attachment` and `prepare_cycle` take a required
   `cycle_count` (the host derives it from the retained schedule steps), the final layer delegates,
   the wrapper's request search globs `execution/cycle-*`. Still hard-coded on purpose: the lawful
   base host's `range(19)` and `load_contract`'s `len(cycles) != 19`, the Sunday contract's shape;
   both become manifest fields with the block work.
6. Pearson floor declared once (`MIN_PEARSON_PRESENT_OVERLAP = 8` in the core; the core `_pearson`
   applies it; message text reads it). New proof on real 8-row and 7-row keys through the real
   builder: coefficient at 8, suppressed at 7 with the overlap count retained.
7. `learning_measurement` and `independent_discovery_eligible` carried in the binding and the
   completion record, not only the receipt, so the completion history `select_hardened_mode`
   consumes never reads a TEACH pass as a discovery.
8. Tautology in `audit_teacher_complete` replaced; three trailing newlines restored (on-disk bytes
   feed the host code hash).

Verified as correct and left alone: correction turn carries only correction items; next cycle
carries identifiers, count and mastery only; novelty never touches the grade; "the data is
showing ... instead" wording, local to the cited subclaim; investigation runs before the
correction request exists; taper regresses one level on a non-mastered cycle and needs two
consecutive mastered cycles to advance; root-cause grouping puts all 18 pair items of one wrong
direction under one root while every correction id stays individually retained.

## Tests

Focused classroom suites: 59 passed (53 before the review; 6 new in
`tests/test_dipole_classroom_review_fixes.py`). The whole `tests/` directory was started twice
on the workstation; the first run stalled at 275 CPU-seconds without progress and I could not
identify the test because its output was buffered, and the rerun was declined. The CI workflow
`.github/workflows/boss_frankie_tests.yml` (uncommitted on the main working branch) runs the
whole directory on Linux under the pinned numeric runtime; that is the right place for the full
count.

## Open, named

- `dipole_classroom_hardening.py` is now an intermediate layer whose adapter and correction
  builders are superseded by the final layer; only `select_hardened_mode` and the key re-pin are
  live. Collapse into the final module at integration, not before the branches meet.
- Wrapper seam unchanged: `main()` rebinds `source_contract_runtime.DipoleClassroomPrincipalAdapter`,
  `base.ActualHost` and `base.await_recorded_principal`, and `runtime()` patches
  `driver.SundayRuntime` around one call. Accepted for the isolated branch. At integration the
  seam is a constructor argument (the adapter class) on `SundayRuntime` / `make_principal_adapter`.
- On this branch the lawful `run_actual_sunday.py` cannot complete a cycle without the classroom
  wrapper; the two benchmark harnesses on the working branch need the wrapper or an explicit
  benchmark exemption when the branches meet (unchanged from the first review).
- `validate_novel_findings` requires the `dipole_novel_findings` key on every response (empty
  list allowed, absent key refused). The receiver prompt must keep saying so.
- `_direction_relation` maps FLAT to UNRESOLVED, so a FLAT/FLAT pair is UNRESOLVED. Consistent with
  the direction definition in the pre-message; recorded so nobody reads UNRESOLVED as "no data".

No Frankie, Granite, EC2, Pod, market-data or result-bearing run was performed for any of this.
