# Plan: cycle 0's bedrock build (the spec is `SPEC_CYCLE0_BEDROCK_20260921.md`)

Status: PLAN, 2026-09-21 (chat 6 close). Greg: "We definitely need a spec plan to follow before we put our hardhats on
and build ... Don't use scratchpad. But do the spec sheet work first." This is the plan and the task list. Nothing here
has been built. Nothing runs on the host, box, Pod or endpoint without Greg's go.

## Rule this plan adds: NO SCRATCHPAD (Greg, 2026-09-21; D34 "there is nothing local")

Everything the build needs to RUN lives in git or on the box. The pinned producers (lineage
`ccode/frankie-receiver-feed-20260916` at `2ebb8ce8`) are reached through a git worktree INSIDE the repo,
`<repo>/.producers-2ebb8ce8/` (gitignored), created by `deploy/aws/box/producers_checkout.sh` (`git fetch origin
ccode/frankie-receiver-feed-20260916 && git worktree add --detach .producers-2ebb8ce8 2ebb8ce8`). Tests reach it through
`FRANKIE_BOX_PRODUCERS` (default `<repo>/.producers-2ebb8ce8`); CI runs the checkout step before the tests. The box already
holds the same commit at `/opt/frankie-box/producers`. Plan and task records: this file and `tasks/todo.md`'s pointer.

## Dependency graph and build order

```
BR-0 producers checkout (foundation)
  |
  +--> BR-1 pin-bedrock (adapter side; no box code)          <- checkpoint A
  |
  +--> BR-2 frankie_box_bedrock.run (driver on the checkout) --+
  |                                                            +--> BR-4 session derive wiring  <- checkpoint B
  +--> BR-3 frankie_box_bedrock.project + status_of ----------+          |
                                                                          +--> BR-5 digest V6 + the size measurement
                                                                          |
                                                                          +--> BR-6 teach stage (needs BR-4's facts)
                                                                                     |
                                                                                     +--> BR-7 docs, brain, writing prompt  <- checkpoint C
                                                                                                |
                                                                                                +--> BR-8 /ship, handoff, runbook, drop-in
```

Parallel: BR-1 is independent of BR-2/BR-3 (different files, different test suites) and can run beside them. BR-2 and
BR-3 are independent of each other (BR-3 works on synthetic ledgers). Everything after BR-4 is sequential.

## Verification checkpoints

- A (after BR-1): adapter suites green (`test_frankie_principal_adapter.py`, `test_cycle_calculation_pin_loader.py`);
  `load_cycle_calculation_pin(0)` carries the bedrock; the instruction carries all 25 layers.
- B (after BR-4): box suite green torch-present AND torch-hidden; the integration test runs the real driver on the
  checkout's fixture stream end to end (consume -> finalize -> reconcile -> project) and the session `derive()` writes
  25 layer files on a stub prefix.
- C (after BR-7): box + host contract suites green; docs bundle and brain entry list the new files; the writing
  prompt's accounting sentence pinned by a text-contract test.
- D (BR-8): /ship fan-out on the whole change; GO after fixes; handoff, runbook and drop-in updated.
- E (on Greg's go, box only, no model call): `ACTION=derive_only` measures the V6 digest's token count and the part
  count, reported with the reading-lane cost before the rerun is dispatched.

## Risks and mitigations

- The driver refuses a record without `source_dbn_object`; the box's INPUT observations come from the journal, not a
  DBN file. Mitigation: `driver_records` stamps the verified prefix container as the source object (path + sha256);
  the receipt says so; a test proves the driver accepts it.
- `source_record` refuses values JSONL would coerce and deep-copies the mapping; a journal observation may carry
  keys the V4 adapter never saw. Mitigation: the integration test feeds a journal-shaped observation (the exact keys
  the box's `_find_observation` returns), not a DBN record.
- The candidate lane cannot fire on a 13-second slice (900 s warmup). Mitigation: `status_of` files `could_not` with
  the measured span; the spec's open question 1 is put to Greg before the rerun, not discovered after it.
- The V6 digest may push the read from 4 parts to many. Mitigation: checkpoint E measures before any paid read; the
  digest carries the carrier columns only, the whole ledgers ride the bundle.
- The pin change moves the request hash: an old request on the box would derive a bedrock the instruction never asked
  for. Mitigation: the derive gate compares `derive.json`'s pin identity with the request's pin sidecar and refuses on
  mismatch (a receipt, not a silent re-derive).
- Memory: the exact member ledger grows ~20 MiB per thousand groups; cycle 0 (2,282 groups) is ~45 MiB on disk through
  `LedgerSinks`, never held in RAM. The whole day would be ~1 GiB: fine on the box, out of scope here.
- Regression on the legacy five: they stay the same code path; `test_frankie_box_digest_render` and the packet tests
  pin their bytes.

## Rollback

Every task is one commit on `claude/cycle-0-frankie-box-rerun-od5sxk`; the box runs whatever `MARKETS_REF` names, so
a `restart_session` on the previous commit restores the previous session; durable jobs are keyed by prompt, so no paid
work is lost. The pin change is reverted by reverting BR-1's commit (the request re-renders back to the old hash).

## Task list (each task: RED test first, then the code; one commit; ~5 files or fewer)

### BR-0 producers checkout in the repo, no scratchpad
- [ ] `deploy/aws/box/producers_checkout.sh`: fetch the lineage, `git worktree add --detach .producers-2ebb8ce8 2ebb8ce8`,
      print the commit and the sha256 of `native_replay_driver.py`; idempotent; refuses on a different commit.
- [ ] `.gitignore`: `.producers-*/`. `tests/conftest.py` (or a tiny `tests/_producers.py`): `producers_root()` from
      `FRANKIE_BOX_PRODUCERS`, and a fixture that FAILS with a clear message when the variable is set and the path is
      absent, SKIPS with a printed reason only when it is unset.
- [ ] `.github/workflows/frankie_box_codecs_ci.yml`: the checkout step before pytest, `FRANKIE_BOX_PRODUCERS` set.
- Acceptance: the script run twice leaves one worktree at 2ebb8ce8; CI's step passes; the fixture behaves both ways.
- Verify: `bash deploy/aws/box/producers_checkout.sh && python -m pytest -q tests/test_producers_checkout.py`.
- Files: the script, `.gitignore`, `tests/_producers.py`, `tests/test_producers_checkout.py`, the CI workflow.

### BR-1 pin-bedrock
- [ ] RED: `test_frankie_principal_adapter.py` gains bedrock assertions (three groups, verbatim equal to pins 1-3,
      receipts re-hashed, instruction carries all 25 layers, other pins carry no bedrock);
      `test_cycle_calculation_pin_loader.py` refuses a malformed bedrock entry and a bedrock group no cycle pins.
- [ ] `CYCLE_CALCULATION_PINS.json`: pin 0 `bedrock` (verbatim copies) + root `bedrock_rule` (Greg's words, dated).
- [ ] `frankie_principal_adapter.py`: loader validation; `calculation_pin_instruction` renders the bedrock sentence
      and the reworded "not required now" clause; `pin['bedrock_layers']` convenience list.
- Acceptance: checkpoint A. Verify: the two adapter suites from the repo root.
- Files: the pins JSON, the adapter, the two test files.

### BR-2 frankie_box_bedrock.run (the pinned driver on the box's records)
- [ ] RED: `tests/test_frankie_box_bedrock.py`: `NeverInvoke.should_invoke` is False for every argument shape the
      protocol names; `driver_records` stamps source object/sha/raw_symbol and refuses an empty container path;
      the integration test: journal-shaped observations from the checkout's own driver test fixture (locate it in
      `.producers-2ebb8ce8/research/kalshi/frankie_raw_mbo_benchmark/tests/`; if none is importable, a 3-group
      stream built from `test_ng_exhaustion_mbo_v4_state_adapter_20260820.py`'s records) -> `run` -> `result.json`
      + three ledgers + reconciliation OK; torch hidden.
- [ ] `deploy/aws/box/frankie_box_bedrock.py`: `NeverInvoke`, `driver_records`, `identity`, `run` (per the spec's
      constructor arguments, all named from the launcher), result written minus rows, ledger witnesses.
- Acceptance: the integration test green with torch hidden; `sinks.reconcile_all` passes.
- Verify: `python -m pytest -q tests/test_frankie_box_bedrock.py` (torch present and hidden).
- Files: the module, the test.

### BR-3 frankie_box_bedrock.project and status_of
- [ ] RED: synthetic member/lifecycle ledgers -> 20 files; member_paths projected with the group key; lifecycle rows
      filtered by section; `status_of` rules (derived / could_not measured / NO_PRODUCER_FOUND); the crosswalk records
      are read from the checkout's `native_layer_crosswalk.py`, never restated here.
- [ ] `project`, `status_of`, `span_seconds`, the layer file shape.
- Acceptance: every layer file names module.symbol, carrier, sections, count, reason. Verify: the same test file.
- Files: the module, the test.

### BR-4 session derive wiring and the derive gate
- [ ] RED: `tests/test_frankie_box_boss_session_derive.py`: a stub session with `_input_records` monkeypatched to the
      fixture stream; `derive()` writes 25 layer files and `derive.json.bedrock`; the gate re-derives when
      `derive.json` lacks bedrock or its pin identity differs from the request's pin sidecar; the legacy five bytes
      unchanged against a recorded witness.
- [ ] `frankie_box_boss_session.py`: `derive()` calls `run` + `project` after the legacy five; `_run` gate; the
      docstring's derive line.
- Acceptance: checkpoint B. Verify: the box suite, both torch modes.
- Files: the session, the new test.

### BR-5 digest V6 and the size measurement
- [ ] RED: `test_frankie_box_digest_render.py`: V6 header names the bedrock tables; a derived bedrock layer renders a
      dense exact table through `render_layers`; the parse-back self-check holds on nested `J...` cells.
- [ ] `frankie_box_digest_render.py`: `SCHEMA = 'DIGEST_V6'`, `bedrock_tables(layers)`; `digest_text` appends them.
- [ ] `deploy/aws/box/frankie_box_session.sh`: `ACTION=derive_only` (verify + labels + derive + digest + a token
      count line; no model call) for checkpoint E, on Greg's go.
- Acceptance: tests green; the action is text-contract tested. Files: the renderer, its test, session.sh, its test.

### BR-6 the exhaustion/D teach stage
- [ ] RED: `tests/test_frankie_box_boss_session_teach.py`: facts built from stub layer files and the brain's frozen
      entry (D-depth histogram, open/closed lineages, the largest gaps named, clock order count, family counts, the
      candidate-lane verdict, the four frozen files' text); a stub BOSS answer with every topic passes; a number not
      in the facts is refused (retry then receipt); a missing topic is refused; durable (second call no model call);
      a facts text over the part budget refuses with the sizes.
- [ ] `frankie_box_teach.py` (facts, prompt, parse, number transcription check, markdown) and the session's `teach()`
      + `_run` placement after the classroom.
- Acceptance: the tests above. Files: the module, the session, the test.

### BR-7 docs, brain, writing prompt
- [ ] RED: docs index lists `exhaustion-teachback.md` and the bedrock layer files; brain entry includes the teach-back;
      the accounting prompt carries the bedrock sentence; analysis prompt names the teach-back section.
- [ ] `frankie_box_docs.py`, `frankie_box_brain.py`, the session's writing prompts.
- Acceptance: checkpoint C. Files: the two modules, the session, `test_frankie_box_docs.py`, `test_frankie_box_brain.py`.

### BR-9 sections 4.2 and 4.4 as V6 tables (Greg, 2026-09-22; SPEC-bedrock-section-tables.md; built da294b91)
- [x] RED: project_sections on the pinned driver's fixture run (6 companion rows, 1 pair, 6 mirror rows); the render of the
      five section tables parsing back equal; derive.json indexing both files; the docs bundle referencing them.
- [x] frankie_box_bedrock.project_sections; frankie_box_digest_render.bedrock_tables section tables + the header sentence;
      frankie_box_boss_session._derive_bedrock wiring (`sections` in the bedrock record). The producers untouched.
- [ ] Checkpoint E re-measures the V6 digest with the section tables (on Greg's go; his call 2).

### BR-8 ship, records, runbook
- [ ] `/ship` on BR-0..BR-7; fix every finding with its test; decision recorded in the handoff.
- [ ] Runbook: the pin change's host steps (supersede principal request, export, fetch, restart_session), checkpoint E
      (`ACTION=derive_only`), then the rerun a-i; every host step on Greg's go.
- [ ] `KALSHI_TRADING.md`, `CLAUDE.md` state line, `DROP_IN_CLAUDE_20260921.md`.

## Greg's calls before BR-8 dispatches anything
1. Bedrock on the 13-second slice now, or hold for the whole-day run (the candidate lane fires only on the day).
2. Reading cost after checkpoint E's measurement: accept the parts, or carrier columns only in the digest.
3. Cycles 1-3 keep their own pins (the plan's assumption).
4. The critic's zero hypotheses (handoff 22:xxZ; host side; two routes).
