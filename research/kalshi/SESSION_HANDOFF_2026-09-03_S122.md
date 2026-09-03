# SESSION HANDOFF 2026-09-03 S122 - THE WIRING IS DONE AND NOT ONE RUN HAS BEEN FED

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Started at `268ceae` (1,816 tests). Closed at
the tip carrying this file. **1,973 tests green, 6,387 subtests.** Decisions 87 -> 88.

**READ SECTION 0 FIRST.** It is the one thing that decides what the next session does.

---

## 0. THE STATE IN ONE PARAGRAPH, AND IT IS AN UNCOMFORTABLE ONE

Two sessions have now been spent wiring, and **nothing wired in either has been fed by a run on
the wired code**. S121 built the causal stream, the crosswalk, the output ledgers and the clocks;
S122 carried per-record `raw_actions` onto the member row, stamped every lifecycle row, retired
the fixed-seconds windows, turned change points on, made the crosswalk compute evidence from what
was actually delivered, built the A_MEMORY seed and the knowledge receipt and the sealed-absence
proof, and made the launch workflow canonical. **The only feeding that happened ran the S121 CODE
against ledgers written by PRE-CENSUS code**, so every number in the feed record is a
before-number. The launch workflow's seal step was verified passing at the close, so the run is no
longer blocked by anything. **The Sunday re-run is the whole of the next session's opening.**
Registered as **F-31, ESSENTIAL**.

---

## 1. WHAT GREG RULED (D88, four rulings in one message, recorded the hour they were said)

- *"if you can't find the canary just use something from the last run. like i said I'm not picky
  about that and it's wasting time."* The day-one seed is the last run's committed outputs. No
  canary output is committed; none was hunted for after this.
- *"look in step1 files and outputs for all of the stuff in clocks, winds."* The clock and window
  designs come from the Step-1 files first. Step-1 RESULT values stay sealed; the DESIGN is
  reusable, the outputs are not deliverable.
- *"we aren't running clean anymore only memory."* One arm. Nothing built, defaulted or
  exemplified for A_CLEAN; its overlay, profiles and workflow stay as inert records (F-28).
- *"there is supposed to be a canonical file or a runner, launcher file with everything."*
  `native_a_arm_launch.py` carries everything as DEFAULTS; a flag exists only to turn a default
  OFF for a declared comparison.

Also standing from the session: **the branch was stopped mid-session on Greg's instruction and the
remaining work was handed to Codex as a written packet** rather than run here.

---

## 2. WHAT LANDED

### 2.1 Item one, the two small edits
`emit_frankie_spawn`'s return shape asks for `outputs_receipt_sha256` and a new section states what
the output bundle is - schema, directory, `RECEIPT.json`, the chain-hashed append-only ledgers, the
required set DERIVED with no count - every name imported from `native_principal_outputs`, the file
that carries it (D82), never restated. `native_staging.REQUIRED_CUTOFF_KEYS` gains
`clock_model_evaluation_ns`, so the model-evaluation clock is a required layer of every spawn
request. Both tests-first.

### 2.2 The canonical launcher and the delivery root
The A_MEMORY launch workflow was rebuilt from the retired A-clean workflow's mature box machinery
(inline manifest, presigned GET and PUT, receipts written BEFORE compression, growpart, the disk
precheck computed from the slice's own record count, the staging watch, fire-and-return). The
wrong-data package step is gone; the seal step now derives the memory package from the registry's
overlay bindings and **refuses by name while any layer still binds an `external:` identity**.
Aliasing and change points default ON. Sunday is the default traversal. The SSM parameter file
moved to `RUNNER_TEMP`. The delivery workflow's `ROOT_PREFIX` widened from the a-clean tree to the
whole benchmark tree, so an A_MEMORY run is found by run id.

**The push canary refused exactly as designed** (run 33698921052), naming
`a_memory_prior_lessons_package` and the `external:` binding - correct, and it stayed correct until
the seed landed.

### 2.3 The personas
Four ran. Two were killed by the session rate limit mid-slice and **everything they had was
salvaged and pushed** (D84 working as intended, second application).

| persona | outcome |
|---|---|
| outputs-staging | DONE, merged `4a790b6`: A_MEMORY defaults, the RT handoff trio built from read-back off the identity receipt's `source_manifest_hash`, the canonical read-back CLI with a NAMED SEAM for the knowledge gate |
| feed-wired | DONE, merged `13b091f`: the first full causal pass over the real Sunday ledgers |
| clocks-windows | killed; salvaged `d0e6308`, merged `8e578f5`: F-20's stamp, `activity_since` on event anchors, the fixed blocks retired, the cadence audit |
| knowledge-gates | killed twice; salvaged `dd874f3`, merged `1129f37`: **the A_MEMORY seed**, the knowledge receipt, the sealed-absence proof |

### 2.4 Codex's Item 4 (reviewed by execution, not by report)
Handed off as a written packet, returned at `91440b2` with its own handoff. Verified here:

- **Task A (F-30)** - `raw_actions` carried on the member row, minimal and correct: the exclusion
  removed from the carry loop and the FALSE comment (`the member row already holds it`) replaced
  with a measured statement.
- **Task D** - the crosswalk computes evidence from delivered carriers: `CENSUS_ABSENT` separated
  from carrier absence, `group_carriers_from_producers` giving one carrier authority,
  the arm read off the identity receipt, F-27 and F-29 both computed rather than stamped.
- **Task B** - change points ON by canonical default; `HORIZON_SETS` untouched.
- **Task C** - `RecognitionLabel` given its production caller; `precursor_for` untouched.
- All eight forbidden files byte-identical, the D61 adapter byte-identical, suite 1,911 green
  (verified here, not taken on report).

---

## 3. THE MOST INSTRUCTIVE THING IN THE SESSION: THE PACKET WAS WRONG AND SAYING SO WAS THE RIGHT ANSWER

The task packet told Codex that four `structurally_absent` pins should survive - the raw-action
fields the tape supposedly does not carry. **He removed all twelve**, and reported why: he checked
a real row and the fields were there.

That claim was verified independently here rather than accepted, because it is the single most
load-bearing statement in his handoff - if wrong, the crosswalk would report carriers present that
are absent and the spawn gate would pass on nothing. Executing the driver shows every one of
`is_snapshot`, `source_dbn_sha256`, `source_dbn_object` and `book_effect` on a carried raw-action
object; and checking PRODUCTION rather than the fixture, `native_a_arm_launch.native_records`
computes `file_sha256(path)` and stamps the provenance on every row while the D61 wrapper's
`_enrich` attaches `book_effect`. **The packet's assumption was the stale thing.**

The packet had told him: *when something in this file turns out to be wrong, say so and do not
silently work around it*. He did exactly that. **That instruction earned its place and should stay
in every future packet.**

### 3.1 And the four kinds of stale, which is the taxonomy worth keeping

Codex's handoff separates them and the distinction matters:

- **Stale live expectations** - crosswalk tests that encoded the F-30 defect as expected behaviour.
  Keeping them would have PRESERVED the defect. Rebaselined to measured truth.
- **Stale live prose** - four live notes still saying those fields were "dropped" after the code
  said otherwise. Contradictory live documentation, corrected in `0fcb897`.
- **Historical artifacts, deliberately left alone** - the renders and the feed record. Rewriting
  them would falsify history.
- **Packet assumptions proven false by execution** - the twelve pins.

**The third one has a consequence he could not fix and it is now F-35**: four committed documents
assert `raw_actions` absent and the order-lifecycle layers `RECEIPTED_CARRIER_ABSENT`, all false of
current code, and nothing on their face says so. That is the S112/S114 expiring-finding shape - a
frozen record that reads as live state. The fix is not to rewrite them but to stamp each with a
superseded-by line naming the commit that changed the behaviour.

---

## 4. WHAT THE REAL SUNDAY LEDGERS SAID (the feed record, and it is all BEFORE-numbers)

`FRANKIE_FEED_RECORD_SUNDAY_33630348943_20260903.md`. The whole 10.6 GB member ledger streamed
causally for the first time: **43,569 groups, byte-identical, zero refusals**, 569 s, 259 MB RSS.
The size witness CONFIRMED all three ledgers. The emitter REFUSED, correctly, on the mission hash.

Two findings from it were fixed the same session:

- **The launcher mutated the result AFTER the runner hashed it** - `ledger_retention`, `gates`,
  `evidence_identity` and `slice` all added post-`finalize`, with no re-hash, so **every**
  launcher-written result declared a `result_hash` that did not recompute and `read_back` refused
  all of them. The tests never saw it because they build results through the runner, never the
  launcher. Fixed: the runner's hash is kept as `runner_result_hash` and `result_hash` is
  recomputed last.
- **The delivery fetcher verified the result object by S3 length alone** while the box's
  `PLAIN_SHA256SUMS` carried a digest for it. Now carried in the manifest and verified; a wrong
  digest is a `SHA_MISMATCH` refusal.

**F-20's measurement, which is the before-number that matters:** 109,532 of 377,454 lifecycle rows
(29.0%) could not ride inside any group - `withheld_no_own_clock` 43,569, `withheld_close_occasion`
65,960. The stamp that fixes it is merged. **Its falsifier is that those read ZERO on a fresh run,
and no fresh run exists.**

---

## 5. MY OWN ERROR, RECORDED

I ran the full suite piped to `tail`, which hid a failure from `set -e`, and **pushed a red
commit** claiming a test count I had not verified. Caught on the next command, fixed in `20817f5`.
The rule that follows is now in every packet: **redirect pytest to a file and read its exit code.**
It is the same shape as the S113 nonconformance - reporting a verification that did not happen.

---

## 6. WHAT IS NOT DONE

- **The Sunday re-run and everything downstream of it** (F-31). Nothing is blocking it.
- **The spawn gate in `emit()`** (F-24) - `gate_applicable_inputs` still has no production caller.
  The sealed proof and the knowledge receipt it needs are now both merged.
- **The knowledge read gate is not wired** - the seam is named at `native_staging.py:111`
  (`KNOWLEDGE_USE_GATE`), called at `:337-345`, pinned `None` by a test so wiring it flips a test
  rather than going unnoticed. It needs pointing at `validate_knowledge_use`.
- **The 4.16 ladder** (F-32) - a redesign, Greg's call, deliberately not attempted.
- **`tests/test_native_layer_crosswalk_s122.py`** stays on `persona/s121-wire-knowledge-gates`,
  NOT merged: it is the spec for the unbuilt slices and fails five ways against what shipped,
  three of them because it asserts the F-30 absence that Task A fixed.
- **The seed's proof binds the seed itself** (F-34) - a degenerate proof, measured at the close.

---

## 7. THE CLOSE

Suite **1,973 passed / 6,387 subtests**. Store check 4/4, docs gate pass, D34 grep clean, the
hash-locked adapter byte-identical, scratchpad empty (D87). Every persona branch pushed. The seal
step verified passing by execution, so the next session opens on a run and not on a repair.
