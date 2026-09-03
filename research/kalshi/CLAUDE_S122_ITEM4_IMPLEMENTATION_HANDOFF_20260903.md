# Claude Handoff — S122 Item 4 Implementation

Date: 2026-09-03
Repository: `DavisAI1974/Markets`
Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`
Task packet: `research/kalshi/CODEX_TASK_S122_ITEM4.md`
Original implementation starting tip for this work: `3e0eec9535c9b814fc88c42e0beb0edbc94df302`
Required task order: **A -> D -> B -> C**

This handoff is a dated record of what was implemented, why it was implemented, what files changed, what tests proved each change, what stale Task A material was found, and what was intentionally not changed.

## 1. Executive summary

All four S122 Item 4 tasks were completed in the required order using tests-first verification and non-force fast-forward landings. The implementation was kept inside the packet’s scope. The hash-locked adapter `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py` was never edited. Historical `*_RENDER_*.md` and `FRANKIE_FEED_RECORD_*.md` artifacts were deliberately preserved even when they now describe pre-F-30 behavior, because the task packet explicitly classified them as frozen records.

The implementation chain is:

1. Task A — `e4d576f25bee8850a0bafa48d573927b938adda4`
   - `fix: carry per-record raw actions on member rows`
2. Task D — `9f984bf9160dffc240c32463476faa04af25973b`
   - `fix: compute crosswalk evidence from delivered carriers`
3. Task D docs-gate repair — `e409a9e2180890ded98262ac098b7e714d4025f1`
   - `docs: repair S122 Task D index gate`
4. Task B — `3018ed490886e0526ad18b1a8f51c010277fe5c2`
   - `fix: enable change points by canonical default`
5. Task C — `d8ed23986655f4aaa95cc0786f1edfb46686f565`
   - `fix: validate candidate recognition labels at call time`
6. Task C test warning cleanup — `f2fc36181df4b0c82ad0e8ea643b1858bcdec8fd`
   - `test: make H+N recognition regex explicit`
7. Task A live-prose stale-state cleanup — `0fcb8970954c2fcff6a005128990e32190a12a58`
   - `docs: align live F-30 crosswalk prose with carried raw actions`

The final behavioral suite before this handoff was written was:

- **1,911 passed**
- **5,657 subtests passed**
- `store.py check`: all four stores PASS
- `store.py docs`: PASS
- D61 locked adapter: `LOCKED_OK`
- no historical render/feed-record file changed

## 2. Process and guardrails used

The work followed the task packet’s required tests-first discipline. Before implementation for each task, a RED test set was run against the exact current target tip. Production code was only changed after the intended failure was observed. Each task candidate was isolated from the target branch and was landed only after its focused tests, full package suite, store checks, docs checks, forbidden-path checks, and D61 lock check passed.

The work also preserved the explicit non-goals from section 6 of `CODEX_TASK_S122_ITEM4.md`:

- no retirement or redesign of the 4.16 horizon ladder / `HORIZON_SETS`
- no new precursor detector and no new `precursor_for` wiring
- no spawn-gate work in `emit_frankie_spawn.emit`
- no weakening of refusal behavior to make the old Sunday run spawn
- no A_MEMORY seed, packet-seam, staging, or launch-workflow work
- no edits to `chat_packet_seam.py`
- no edits to `A_MEMORY_SEED_*.json`
- no edits to `register_a_memory_knowledge.py`
- no edits to `rebind_registry_knowledge_layers.py`
- no edits to the registry’s `a_memory_overlay`
- no edits to `.github/workflows/frankie_a_memory_rt_native_launch_20260828.yml`
- no edits to `native_staging.py`
- no edits under `prior_memory/**` or `principal_runs/**`
- no edits to historical `*_RENDER_*.md` or `FRANKIE_FEED_RECORD_*.md`

## 3. Task A — carry per-record `raw_actions` on the exact member row

### Problem

The driver supplied `raw_actions` to `native_clocks.member_clock_row` so clocks could be derived, but that function returned a new member dictionary without the actions. `native_replay_driver._on_group` then explicitly skipped `raw_actions` while copying the rest of the frame onto the member row. The comment at that seam claimed the member row already contained the actions. Execution proved that comment false.

That meant the exact per-record A/C/M/R/T/F/N messages existed in the frame but were dropped before the delivered member ledger. This specifically undermined the requirement that the principal receive every record of every field and caused order-lifecycle layers to appear receipted while their per-record carrier was absent.

### RED proof

The Task A RED run produced **5 intended failures**. The failures included missing `raw_actions` keys on member rows and a differential row/hash mismatch once the tests expected the new retained content.

### Implementation

`native_replay_driver.py`

- stopped excluding `raw_actions` from the frame-to-member carry loop
- the exact frame `raw_actions` list is now retained on the exact member row
- the row therefore carries one raw-action object per component, in receive order

`native_layer_crosswalk.py`

- changed the live producer/carrier model from “produced then dropped” to “carried”
- removed now-false structural absence pins for raw actions when the fields were proven on real rows
- declared the real per-record paths as member carriers, including provenance, snapshot state, order IDs, and `book_effect` where execution showed them present

`tests/test_native_replay_driver.py`

- verifies every member row carries `raw_actions`
- verifies the list equals the frame’s own list whole, not a count or hash
- verifies `len(row["raw_actions"]) == row["component_count"]`
- verifies there is one member-row copy of the field

`tests/test_native_layer_crosswalk.py`

- rebaselined the crosswalk assertions from structural absence to actual carried fields

`tests/test_native_row_sink_differential.py`

- rebaselined the member-ledger differential because retaining raw records deliberately changes ledger bytes and hashes

### Measured byte cost

Fixture member ledger before Task A:

- bytes: `1,027,352`
- SHA-256: `b1627f4cb89672021a2fca323e2e8b6c8aee2ad5a51e32491292e05f8f45fd54`

After Task A:

- bytes: `1,204,796`
- SHA-256: `69abf2cba3a48b07b745404957b20e835679dcb47a1e5749150964885254bd18`

Measured delta:

- `177,444` bytes across 60 rows
- `2,957.40` bytes per member row

This byte/hash change is intentional: the output is larger because the per-record messages are no longer discarded.

### GREEN proof

Task A focused verification:

- **253 passed**
- **3,145 subtests passed**

Full package suite at Task A:

- **1,889 passed**
- **5,511 subtests passed**

Store/docs and D61 lock all passed.

### Important stale Task A findings

There were several different kinds of “stale” state, and they should not be conflated.

#### A. Stale live expectations that had to change

Some existing crosswalk tests and live crosswalk assertions encoded the old F-30 defect as expected behavior: raw-action fields were expected to be absent. Once Task A correctly retained `raw_actions`, keeping those tests would have preserved the defect. Those assertions were rebaselined to the measured new truth rather than treating the old absence as a specification.

#### B. Stale live prose found after the implementation

After the code and `member_paths` correctly said the fields were carried, four live notes in `native_layer_crosswalk.py` still literally said those same fields were “dropped.” This was contradictory live documentation, not historical evidence. It was corrected in follow-up commit `0fcb8970954c2fcff6a005128990e32190a12a58`.

The four corrected live statements concerned:

- `raw_actions[].is_snapshot`
- `raw_actions[].source_dbn_sha256`
- R-clear `raw_actions[].book_effect`
- the per-record `raw_actions[].order_id` sequence

Only the live crosswalk prose was changed. The full suite remained **1,911 passed / 5,657 subtests passed** after this cleanup.

#### C. Historical stale artifacts intentionally left alone

The task packet explicitly prohibited editing historical renders and feed records. Therefore old artifacts that accurately record the pre-F-30 run still contain the old absence/status story. That is intentional. They describe what the old run delivered; rewriting them would falsify history.

Examples intentionally left untouched include:

- `research/kalshi/frankie_raw_mbo_benchmark/LAYER_CROSSWALK_FIXTURE_RENDER_20260902.md`
- `research/kalshi/frankie_raw_mbo_benchmark/LAYER_CROSSWALK_SUNDAY_33630348943_RENDER_20260902.md`
- `research/kalshi/frankie_raw_mbo_benchmark/LAYER_CROSSWALK_SUNDAY_33630348943_FED_RENDER_20260903.md`
- `research/kalshi/frankie_raw_mbo_benchmark/FRANKIE_FEED_RECORD_SUNDAY_33630348943_20260903.md`

Claude should treat those as frozen evidence of the earlier run, not as the current live implementation specification.

#### D. Packet assumptions that became obsolete after execution

The packet said some nested raw-action fields should remain structural absences unless visible on a real row. The implementation checked the actual row. Fields such as provenance, snapshot state, and `book_effect` were present in the carried raw-action objects, so their old absence assumptions were removed where execution proved them false. This is an important example of the packet correctly instructing the implementer to prefer measured rows over inherited assumptions.

## 4. Task D — make the crosswalk compute evidence from what was actually delivered

Task D was the largest item and addressed five measured defects from the real Sunday feed surface.

### RED proof

A dedicated tests-first file was created:

- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk_s122_item4_d.py`

The RED run produced:

- **40 failed**
- **1 passed**

The failures covered the intended defects: missing member-ledger census source, conflation of absent evidence and absent carrier, no derived carrier authority, wrong CLI arm default, silent result/request arm mismatch, stale knowledge producer status, missing principal lock-time status, and the old Sunday example arm.

### D-1 — distinguish missing census evidence from measured carrier absence

Before the fix, if the result had no field census, the crosswalk could return `RECEIPTED_CARRIER_ABSENT` even though it had not actually measured the delivered member ledger. Missing evidence and measured absence shared one status.

The fix added:

- `CENSUS_ABSENT` for genuinely unavailable member-census evidence
- a bounded scan of the delivered member ledger when `--ledger-dir` is supplied
- explicit scan bounds in code/status details:
  - maximum rows: **1,024**
  - maximum bytes: **64 MiB**
- source labels distinguishing a result-provided census from a bounded delivered-ledger scan

A carrier is now called absent only when measured evidence says it is absent.

### D-2 — one carrier authority instead of two disagreeing tables

Before the fix:

- `native_causal_stream.LAYER_CARRIERS` was a hand-written group-level table
- `native_layer_crosswalk.LAYER_PRODUCERS[*].ledgers` was a separate per-layer authority

Those two authorities could and did disagree.

The fix added `group_carriers_from_producers` in `native_layer_crosswalk.py` and made `native_causal_stream.LAYER_CARRIERS` derive from the producer records. The stream no longer maintains an independent hand-written carrier table.

This also corrected cases where lifecycle or legacy delivery was real but the group-level table attributed the wrong carrier.

### D-3 — bind the requested arm to the run identity

Before the fix, the crosswalk ignored `layers.identity_receipt.arm`. An explicitly requested A_MEMORY crosswalk could silently be applied to an A_CLEAN-identity result.

New semantics:

- no result and no explicit `--arm` -> `A_MEMORY`
- result supplied and no explicit `--arm` -> use the result identity arm
- explicit arm that disagrees with the result identity -> refuse loudly and return failure
- `A_CLEAN` remains a valid enum value

The live Sunday example in the module was also switched to A_MEMORY as required.

### D-4/F-27 — compute knowledge binding from the rebound registry

Before the fix, producer records contained a stale copied flag for whether knowledge was bound only to the feed inventory document. The registry had already been rebound, so a static copied boolean could lie immediately after the registry changed.

The fix now derives doc-only binding at runtime using:

- `native_knowledge_delivery.layers_bound_only_to(...)`
- `KNOWLEDGE_INPUT_POLICIES`
- `KNOWLEDGE_LAYER_SOURCES`

Knowledge producer records are rebound to the classified KEEP-file sources from `KNOWLEDGE_LAYER_SOURCES`; without a knowledge receipt they become `PRODUCED_NOT_DELIVERED`. A genuinely doc-only mutated registry still gets `BOUND_TO_INVENTORY_DOCUMENT`, even if a receipt tries to claim delivery.

### D-4/F-29 — account for the lock clock as principal-stamped

`clock_lock_time` is not an ingestion-produced input. The lock instant is created by the principal’s own `output_first_locks_and_no_locks` ledger.

The fix added computed status:

- `PRINCIPAL_STAMPED`

and identifies the principal carrier:

- `output_first_locks_and_no_locks`

`gate_applicable_inputs` accepts `DELIVERED` or `PRINCIPAL_STAMPED` for input accounting, while the earlier pre-call stamp is still allowed to disagree. The registry layer was not moved.

### D-5 — A_MEMORY default

The standalone crosswalk CLI no-result default is now A_MEMORY. A_CLEAN remains legal but is not the canonical default.

### Files changed by Task D

- `research/kalshi/frankie_raw_mbo_benchmark/native_causal_stream.py`
- `research/kalshi/frankie_raw_mbo_benchmark/native_layer_crosswalk.py`
- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk.py`
- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk_s122_item4_d.py` — new tests-first file

### Task D verification

Final focused Task D verification before landing:

- **120 passed**
- **1,074 subtests passed**

Full suite:

- **1,902 passed**
- **5,657 subtests passed**

Store check, docs check, forbidden historical-file perimeter, and D61 lock passed.

### D documentation-index repair

A separate non-behavioral repair was needed after Task D committed the new test file.

What happened:

- before the test file was tracked, `store.py docs` could not see it in the git-backed Python-file inventory
- after Task D became a real commit, `store.py docs` correctly required the new test file to appear in `KALSHI_TRADING.md`

The repair commit `e409a9e2180890ded98262ac098b7e714d4025f1` ran the repository’s generated-index mechanism (`store.py docs --write`) and updated only the generated inventory entry/count in `KALSHI_TRADING.md`. No Task D behavior changed.

## 5. Task B — change points ON by canonical default

### Problem

The event-driven 4.16 change-point machinery already existed and had produced real observations, but both the driver and launcher defaulted it OFF. That made the canonical launcher require an opt-in flag for a component D83/D88 says should be part of the default experiment.

The task was deliberately limited to the default and declared-comparison semantics. It did **not** redesign the fixed horizon response ladder.

### RED proof

Task B RED produced **7 intended failures** covering:

- driver default still `False`
- launcher default still `False`
- missing `--no-change-points`
- absence of an explicit enabled/disabled state in the section summary

### Implementation

`native_replay_driver.py`

- `emit_change_points=True` by default
- normal no-override construction now runs the existing change-point path

`native_a_arm_launch.py`

- `launch(... emit_change_points=True ...)`
- CLI changed from opt-in to opt-out:
  - `--no-change-points`
  - `action="store_false"`
  - `dest="emit_change_points"`
  - default `True`
- help text states that change points are ON by default under D83/D88 and OFF is a declared comparison

`native_response.py`

- the 4.16 summary now exposes whether change points were enabled versus deliberately disabled
- an explicit disabled comparison is no longer indistinguishable from “enabled but no event fired”

Tests changed:

- `tests/test_native_a_arm_launch.py`
- `tests/test_native_replay_driver.py`

The tests use a non-vacuous candidate fixture so “default ON” is proven by actual emitted change points, not just by inspecting a function signature.

### GREEN proof

Focused Task B verification:

- **80 passed**

Full suite:

- **1,906 passed**
- **5,657 subtests passed**

Store/docs and D61 lock passed. `HORIZON_SETS` was not changed.

## 6. Task C — give `native_clocks.RecognitionLabel` its production caller

### Problem

`native_clocks.RecognitionLabel` already contained the canonical recognition invariants:

- known label only
- `ts_recv_ns` clock
- PRIOR observed before reference
- T0 observed exactly at reference
- H+N observed after reference
- `lead_ns = reference_ns - observed_ns`, positive before birth

But the production candidate adapter was writing recognition state through `CandidateRecognition.record_call` without constructing `RecognitionLabel`. The validated type therefore existed but was not in the production write path.

### RED proof

The Task C caller-level RED run produced **5 intended failures**:

- three failures because the validated `recognition_label` object did not exist on the output
- one impossible T0 pair was accepted instead of raising `ClockError`
- one impossible H+N pair was accepted instead of raising `ClockError`

### Implementation

`native_candidate_adapter.py`

Immediately after the existing `CandidateRecognition.record_call` path:

- construct `native_clocks.RecognitionLabel`
- use the candidate birth as the reference instant
- use the first recognized receive instant as the observed instant
- let `RecognitionLabel.__post_init__` enforce the timing/clock invariants before output is written
- preserve all existing recognition fields
- add the validated object’s dictionary beside the existing fields on both the open-row output and closed recognition output

Nothing was dropped or renamed.

Critically, `precursor_for` was **not** changed. The existing optional callback remains exactly the existing mechanism. No new precursor detector was invented, and PRIOR was not made artificially reachable.

Tests changed:

- `tests/test_native_candidate_adapter.py`

The tests prove:

- H+N carries canonical negative lead when observed after birth
- PRIOR lead is positive and equals `reference - observed`
- impossible T0 timing refuses at the adapter caller
- impossible H+N timing refuses at the adapter caller
- closed recognition output preserves old fields and adds the validated object

### GREEN proof

Focused C verification:

- **91 passed**
- **10 subtests passed**

Full suite:

- **1,911 passed**
- **5,657 subtests passed**

Store/docs and D61 lock passed, and the verifier explicitly checked that the Task C diff did not change `precursor_for` wiring.

### C test-only warning cleanup

The first green C run emitted a Python `SyntaxWarning` because the test regex was written as a normal string containing `"H\+N"`. Production behavior was already correct. A follow-up test-only commit changed the regex to a raw string.

Commit:

- `f2fc36181df4b0c82ad0e8ea643b1858bcdec8fd`

Verification after cleanup:

- warning itself reproduced under `-W error::SyntaxWarning` before the fix
- focused tests: **74 passed / 10 subtests passed**
- full suite: **1,911 passed / 5,657 subtests passed**
- store/docs PASS
- D61 lock PASS

No production code changed in that follow-up.

## 7. Complete changed-file inventory for the implementation chain

From the original working tip through the completed behavioral work and cleanups, the meaningful target-branch files changed are:

### Production/live code

- `research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py`
  - Task A raw-action retention
  - Task B change-point default
- `research/kalshi/frankie_raw_mbo_benchmark/native_layer_crosswalk.py`
  - Task A carrier truth
  - Task D evidence/status/arm/knowledge/lock logic
  - Task A live-prose stale cleanup
- `research/kalshi/frankie_raw_mbo_benchmark/native_causal_stream.py`
  - Task D carrier map now derived from producer records
- `research/kalshi/frankie_raw_mbo_benchmark/native_a_arm_launch.py`
  - Task B default-on and `--no-change-points`
- `research/kalshi/frankie_raw_mbo_benchmark/native_response.py`
  - Task B explicit change-point enabled/disabled state
- `research/kalshi/frankie_raw_mbo_benchmark/native_candidate_adapter.py`
  - Task C `RecognitionLabel` production caller

### Tests

- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_replay_driver.py`
- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk.py`
- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_row_sink_differential.py`
- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_layer_crosswalk_s122_item4_d.py`
- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_a_arm_launch.py`
- `research/kalshi/frankie_raw_mbo_benchmark/tests/test_native_candidate_adapter.py`

### Generated live documentation/index

- `KALSHI_TRADING.md`
  - only the generated Python-file inventory was updated to include the new Task D test

### This handoff

- `research/kalshi/CLAUDE_S122_ITEM4_IMPLEMENTATION_HANDOFF_20260903.md`

## 8. Things Claude should not “clean up” because they are intentional

1. Do not rewrite the historical Sunday render/feed records to make them match the new code. They are records of what the earlier run delivered.
2. Do not remove the A_CLEAN enum just because A_MEMORY is canonical. The task explicitly kept A_CLEAN as a valid inert arm.
3. Do not convert `PRINCIPAL_STAMPED` to `DELIVERED`; lock time is produced by the principal’s output ledger, not the ingestion path.
4. Do not merge a missing census into carrier absence again. `CENSUS_ABSENT` exists specifically to keep “not measured” separate from “measured and absent.”
5. Do not hand-maintain a second `LAYER_CARRIERS` table. The carrier map is now derived from `LAYER_PRODUCERS`.
6. Do not turn the Task B work into a horizon-ladder redesign. `HORIZON_SETS` was intentionally left alone.
7. Do not invent a precursor signal to make PRIOR reachable. Task C only validates the recognition that the existing candidate path actually produced.
8. Do not weaken spawn/refusal gates to make the historical Sunday result pass.
9. Do not edit the D61 hash-locked adapter.

## 9. Final verification state before handoff creation

The latest full behavioral verification was run after both the C warning cleanup and the Task A live-prose cleanup.

Task A stale-live-prose follow-up focused tests:

- **76 passed**
- **1,072 subtests passed**

Full package suite:

- **1,911 passed**
- **5,657 subtests passed**

Repository gates:

- `store.py check`: PASS for failure_judge, decisions, sop, open_items
- `store.py docs`: PASS
- `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`: `LOCKED_OK`
- historical render/feed record files: unchanged

## 10. Suggested Claude read order

1. `research/kalshi/CLAUDE_S122_ITEM4_IMPLEMENTATION_HANDOFF_20260903.md`
2. `research/kalshi/CODEX_TASK_S122_ITEM4.md`
3. commits in order:
   - `e4d576f25bee8850a0bafa48d573927b938adda4`
   - `9f984bf9160dffc240c32463476faa04af25973b`
   - `e409a9e2180890ded98262ac098b7e714d4025f1`
   - `3018ed490886e0526ad18b1a8f51c010277fe5c2`
   - `d8ed23986655f4aaa95cc0786f1edfb46686f565`
   - `f2fc36181df4b0c82ad0e8ea643b1858bcdec8fd`
   - `0fcb8970954c2fcff6a005128990e32190a12a58`
4. live implementation files listed in section 7
5. historical render/feed records only as evidence of the old Sunday run, not as current live truth

## 11. Status

- Task A: **DONE**
- Task D: **DONE**
- Task B: **DONE**
- Task C: **DONE**
- C warning cleanup: **DONE**
- A stale live-prose cleanup: **DONE**
- historical frozen artifacts: **intentionally unchanged**
- out-of-scope section 6 items: **not started**

No force push was used for the task landings. The target branch was advanced by verified fast-forwards. The hash-locked D61 adapter remains untouched.