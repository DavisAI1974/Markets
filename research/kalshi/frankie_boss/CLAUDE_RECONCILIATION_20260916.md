# Claude reconciliation record - integrated recovery + classroom tree (2026-09-16)

Step 1 of the Codex pre-launch audit handoff (`outputs/frankie-boss/20260916/prelaunch-audit/CLAUDE_HANDOFF.md`
on `codex/frankie-prelaunch-audit-handoff-20260916`): reconcile the audited recovery, classroom and receiver
trees in isolation. Git-only work. No Frankie, Granite, Pod, EC2, S3, market-data or result-bearing action was
taken. Launch remains closed. Nothing here authorises a run.

## What the integrated tree is

Branch `claude/first-run-using-agent-skills-bd52fj`. Integrated code tree = commit `dd5d4447`.

| input | SHA | relation to the integrated tree |
|---|---|---|
| classroom composition `chatgpt/frankie-feed-output-memory-wiring-20260916` | `d152dd82` | base of the integrated tree (checked out as-is) |
| recovery `ccode/frankie-lawful-recovery-review-20260915` | `34301ac0` | merged at `02aa62db`; the only recovery commit absent from `d152dd82` is `34301ac0` itself, which touches two documents (`DROP_IN_NEXT_CHAT_20260917.md`, `audits/FRANKIE_FEED_AUDIT_SUNDAY_CYCLE0_20260916.md`) and no code |
| classroom integration review `ccode/frankie-dipole-classroom-integration-review-20260916` | `61c73a2d` | merged at `dd5d4447`; its one commit (review document + two test additions) was absent from `d152dd82` |
| receiver `ccode/frankie-receiver-feed-20260916` | `2ebb8ce8` | NOT merged. It is a separate lineage (`research/kalshi/frankie_raw_mbo_benchmark`, common ancestor `a7dd99e7`, 2026-08-24) and is a pinned sibling checkout, not a merge target. The pin the drop-in requires (`receiver_commit 2ebb8ce8`) is a configuration change and is deliberately not made here (audit finding 2) |
| lawful ancestor | `050c5056` | science-byte comparison baseline (below) |

Ancestry facts checked: `d152dd82` contains `cf9e2c87`, `02306339`, `5d5c2138`; the marker/placeholder commits
between `5d5c2138` and `d152dd82` net to one added work-in-progress note. All three audited remote tips were
unchanged from the audit's SHAs at the time of this work. No `codex/*` or `chatgpt/*` branch contains all three
inputs; this is the first tree that does.

## The one merge conflict and how it was resolved

`tests/test_dipole_classroom_review_fixes.py`, test `test_final_adapter_keeps_answer_key_material_out_of_the_principal_directory`.
The classroom side parametrised it over `(adapter_class, builder)` with the integrated adapter on
`prepare_integrated_cycle`; the review commit parametrised it over `adapter_class` only, driving the integrated
adapter on a `prepare_final_cycle` package. These are different cases, so neither was chosen over the other: the
classroom form is kept and the review's case is added as a third parameter with its comment. All three pass.

## Evidence (this container: Linux, Python 3.11.15, torch 2.x CPU, numpy 2.4.6; `PYTHONPATH=.:research/kalshi/frankie_boss:research/kalshi/frankie_boss/tests`)

| run | tree | result |
|---|---|---|
| audit's `audit-tests.xml` set (10 files) | `d152dd82` untouched | 99 passed (matches the audit) |
| audit's `recovery-tests.xml` set (4 files) | `d152dd82` untouched | 21 passed (matches the audit, run on `34301ac0`) |
| audit set | `dd5d4447` | 100 passed (the +1 is the review commit's added seam test in `test_dipole_classroom_integration.py`) |
| recovery set | `dd5d4447` | 21 passed |
| `test_dipole_classroom_review_fixes.py` + `test_dipole_classroom_integration.py` | `dd5d4447` | 13 passed |
| classroom family (`test_dipole_classroom*.py`, `test_sunday_execution.py`, `test_classroom_recovery_reconciliation.py`) | `dd5d4447` | 48 passed |

Science files vs `050c5056` on `dd5d4447` (the list from the three classroom reviews: `dipole_target.py`,
`c15_teacher.py`, `c15_teacher_r3.py`, `teacher.py`, `c15_normalizer.py`, `c15_normalizer_r3.py`, `c15_dstate.py`,
`context_session.py`, `prepared_context_cache.py`, `b1_reasoner.py`, `boss_training_checkpoint.py`,
`feedback_cycle.py`, `frankie_principal_adapter.py`, `operations/run_actual_sunday.py`, `native_mbo_encoder.py`,
`trunk.py`, `c15_journal.py`, `causal_packet.py`, `research/refrag`): blob-identical except `c15_journal.py`
(35 lines) and `prepared_context_cache.py` (29 lines), exactly the two exceptions the audit's finding 7 states.
The receiver's 246-test suite was not run here; the receiver tree is untouched at `2ebb8ce8`.

## What this does NOT close

Audit findings 2 through 8 are untouched: stale launch pins, compact-source host selection, sealed/output
admission on the BOSS boundary, independent Memory A proof, authority map entries, the science-byte exceptions'
runtime identity, and the remote receiver checkout without a parent repository. The classroom tip's own
`WORK_IN_PROGRESS_FEED_OUTPUT_MEMORY_WIRING_20260916.md` lists the same seven targets as planned, not done.
The full frankie_boss suite (180 test files) was not run here.

## Environment facts for the next session

This work ran in a remote Linux container, not the Windows workstation. No Runpod credential or SSH key is
present; AWS credential environment variables are present but were not used; `boto3`, `zstandard` and CPU torch
were installed for the suites. `.github/workflows/boss_frankie_tests.yml` does not exist on any of the three
inputs or on this branch. Nothing was started, stopped, dispatched or uploaded.
