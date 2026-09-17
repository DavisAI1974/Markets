# Drop-in for the next chat - Frankie/BOSS, after 2026-09-17 (Claude Code)

Paste to Claude Code. Repository `DavisAI1974/Markets`. Run `using-agent-skills` first.

```
git fetch origin claude/first-run-using-agent-skills-bd52fj
git checkout -B claude/first-run-using-agent-skills-bd52fj origin/claude/first-run-using-agent-skills-bd52fj
git log --oneline -1
```
Read, in order: `CLAUDE.md` (top block: FRANKIE / BOSS standing rules), then
`research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260917.md`, then `CLAUDE_RECONCILIATION_20260916.md` in the same directory.

## State in one paragraph

This branch = recovery `34301ac0` + classroom `d152dd82` + review `61c73a2d` reconciled (first tree with all three) +
the old Granite smoke context removed from ALL Granite code and tests (131,072 only; output bounded by the context;
finite direct critic, bounded smoke launch and the smoke admission receipt retired). The first run's prefixes and reducer stack are
verified byte-identical to runtime pin `9a8f3f46` and are the GOLD STANDARD (57,027 records -> 114,054 entries -> 7,129
blocks, 715 s). Receiver `2ebb8ce8` is a sibling checkout, not merged. Launch is HOLD.

## First business

1. Greg's row count for the native context (`T_CTX` / `context_rows` / `model_context_rows` / prefix-builder guard).
2. The pre-existing test errors listed in the handoff: 8 failures, the 28 `test_granite_coordinator.py` setup errors
   (fixture `max_model_len=3000`, then a second setup problem), the `test_granite_retained_host.py` stall. Identical on
   the untouched tree; not introduced by the retirement work. Fix the root causes, never skip or deselect to get green.
3. Audit findings 2-8: 3 and 6 CLOSED; 4, 5, 2/7, 8 landed on the BOSS side (see the last section of
   `CLAUDE_HANDOFF_20260918.md`). Still pending: receiver produces the sealed-absence proof file; receiver binds the BOSS
   Memory A witness into the knowledge receipt; the fresh configuration (reviewed BOSS tip + new completion ref, Greg);
   host verification of the receiver checkout (HOLD). Then the token shrinks 3.1-3.4, then the CPU items.
   OPEN WITH ONE FAMILY RUN: the second session verified each slice by its own test file only.

## Standing orders (Greg)

- The old Granite smoke context (the four-thousand number) is RETIRED. Never reintroduce it in code, tests, fixtures or
  docs. 114,054 is a row count, not tokens.
- The first run's prefixes/reducer stack are the gold standard; for new days change dates only, never rebuild.
- Shrinking/optimizing the packet is one of the most important jobs. 8 threads, fixed. Per-event, never average.
- No Frankie/Granite/Pod/EC2/result-bearing action, no workflow, without Greg's explicit go. Nothing on local disk: git and S3.

## Launch runbook (Greg, 2026-09-17: start from yesterday's wrappers; bare-minimum tests; launch stays HOLD until his go)

Decision recorded: **Memory A is VALID (Greg).** No code anywhere names a "validation day"; the retained configuration
key `source_day_required` is read by nothing; the crosswalk's DEGENERATE_PROOF_SAME_AS_SUBJECT is an ACCOUNTED input
status that gates nothing. The attestation lives in code (`frankie_principal_adapter.MEMORY_A_ATTESTATION`) inside every
`memory-a-witness.json` BOSS writes. Audit finding 5 is CLOSED by decision.

The templates (all in `operations/`, all from 2026-09-16/17, unchanged):
- `restore_sunday_set_on_host.py --bucket --prefix --tools --receipt` : restore the Sunday set on the host from S3, byte-verified.
- `restore_sunday_working_tree_identity.py` : ONLY for the historical 050c5056 identity; a NEW run uses a clean checkout of the reviewed BOSS tip, not this.
- `seal_final_prelaunch_candidate.py --commit --audit-directory --configuration --host-script --bootstrap --helper --principal-instructions` : seal the candidate (import/--help never read data or cloud).
- `run_actual_sunday_ec2.py --configuration [--ec2-resume]` : the launch wrapper; new run directory/run id, numeric policy recorded, principal routed through the classroom wrapper.
- `run_actual_sunday_compact_source.py --configuration --verify-source-only --run-directory <scratch>` : compact-source verification (no model); the result-bearing route now composes through the classroom runner.

Order for the next chat:
1. ONE family run (`test_granite*`, `test_sunday*`, `test_run_actual*`, `test_frankie_controller`, `test_actual_host*`). If item 1 (`T_CTX`) surfaces there, then dig into the number; otherwise leave it.
2. Author the fresh configuration by copying the 2026-09-15 one and changing ONLY: `host_runtime.boss_commit` (reviewed tip), `receiver_commit` (2ebb8ce8, full sha in `launch_pins.NEXT_RUN`), `host_runtime.completion_workflow_ref` (Greg's new ref), `host_runtime.native_threads: 8`, `host_runtime.science_byte_exceptions` (from `launch_pins`), `principal_admission` (artifact + outputs dir + sealed proof path), all paths host-side (no `E:` desktop path, D34), a NEW `run_directory`/`run_id`. Then `launch_pins.validate(config, boss_commit=<tip>)` must pass with zero problems.
3. Seal with `seal_final_prelaunch_candidate.py`; `--verify-source-only` on a scratch directory (no model).
4. Pre-launch checklist (shipping-and-launch, tailored): pins validate; receiver checkout at the pinned commit with its parent repository (finding 8: `_code()` now refuses cleanly otherwise); sealed-absence proof file present (receiver `native_sealed_absence.prove_sealed_absent` has no producer yet: either produce it or declare NOT_PRESENTED/UNPROVEN only under a retained prompt); keys in `~/.config/markets/env`; rollback = the retained Pod stops through the ownership protocol (`completion_cleanup`), data retained; monitoring = the retained-host watchdog + `IncompleteModelOutput` alert.
5. Launch only on Greg's explicit go, via `run_actual_sunday_ec2.py --configuration`.
