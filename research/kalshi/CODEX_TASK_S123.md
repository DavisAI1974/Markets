# CODEX TASK - S123

Repository `DavisAI1974/Markets`, branch **`chatgpt/frankie-raw-mbo-benchmark-20260828`**, base commit
`a30c7f4`. Baseline suite: **1,973 passed, 6,387 subtests.**

There are **six tasks**. Section 7 names what is out of scope and why each was ruled out.

Every anchor below (file, symbol, line, signature) was checked by EXECUTING or reading the code at
`a30c7f4`, not from a handoff. **If something is not where this file says, stop and report it - do
not go looking and do not work around it.** That instruction earned its place last session: the S122
packet asserted four crosswalk pins should survive, execution proved all twelve should go, and
saying so was the right answer.

---

## 0. RULES

1. **Tests first.** Write the failing test, RUN it, watch it fail for the reason you intend, then
   implement. A test that never failed has tested nothing.
2. **A refusal is produced by a test**, never asserted in prose.
3. **A test that encodes a defect as its specification preserves the defect.** If an existing test
   asserts the absence you are fixing, rebaseline it to measured truth and say so in the commit.
4. **Never edit `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`** (hash-locked, D61).
   `git diff --quiet` on it exits 0 at every commit.
5. **D87: no transient file anywhere but the gitignored `data/` tree**, deleted when done. Tests use
   `tempfile` inside the test. No committed file may name a path outside the repository (D34).
6. **Commit and push after every task** (D84):
   `git push -u origin chatgpt/frankie-raw-mbo-benchmark-20260828`. One task per commit. Never
   force-push. If you run out of budget, commit what is green as a labelled save point, commit
   tests-first files with RED in the subject, push, and stop.
7. **No historical number is a spec** (D60). Derive counts at run time. Never type `99`, `75`, `63`
   or `1024` as an expected count in a test.
8. **Nothing is dropped** (D60/D76). If a change would remove a field or a row, keep it and say so.
9. **One arm: `A_MEMORY`** (D86/D88). `A_CLEAN` stays a valid enum value as an inert record.
10. **DO NOT DISPATCH ANY WORKFLOW, IN ANY MODE (D89, Greg, this session).** Verbatim: *"we are not
    doing canary until all of this other stuff is done first."* This packet IS the other stuff. A
    run over unfinished wiring produces one more set of before-numbers, which is exactly what run
    33630348943 cost. The canary is dispatched after these tasks land; the box is a separate spend
    and is Greg's alone.
11. **No emojis.** Commit messages end with exactly:
    `Co-Authored-By: Codex <noreply@openai.com>`

### Gates before every commit

```bash
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests -q -p no:cacheprovider \
  > data/suite.log 2>&1; echo "EXIT $?"; tail -2 data/suite.log
python3 research/kalshi/store.py check     # 4 PASS lines
python3 research/kalshi/store.py docs      # PASS docs
git diff --quiet research/ng_exhaustion_mbo_v4_state_adapter_20260820.py && echo LOCKED_OK
```

**Redirect pytest to a file and read `EXIT`.** Piping to `tail` hides a failure from `set -e`; that
exact mistake pushed a red commit two sessions running.

### Do not touch

`A_MEMORY_SEED_*.json`, `register_a_memory_knowledge.py`, `rebind_registry_knowledge_layers.py`, the
registry's `a_memory_overlay` group, `chat_packet_seam.py`, `native_staging.py`'s `prior_memory/**`
and `principal_runs/**` trees, and every `.github/workflows/frankie_*` file.

---

## 1. TASK A - CALL THE SPAWN GATE FROM `emit()` (F-24, ESSENTIAL)

**Why.** `gate_applicable_inputs` is the item-7 gate. It exists, it is correct, and **nothing in
production calls it.** Its only caller is the crosswalk's own CLI. So a spawn can be emitted against
a run that delivered nothing.

**Verified state at `a30c7f4`.**

| symbol | file:line | today |
|---|---|---|
| `gate_applicable_inputs(crosswalk_body)` | `native_layer_crosswalk.py:1438` | raises `CrosswalkGateError`, names every offender |
| its only caller | `native_layer_crosswalk.py:1696` | the module's `main()` |
| `emit(result_path, *, delivery_receipt, repo_root, evidence_uri)` | `emit_frankie_spawn.py:134` | never mentions the crosswalk |
| the arm lookup | `emit_frankie_spawn.py:162` | `arm = _lookup(identity, "arm")` |

**The design problem, and it is the whole task.** `crosswalk()` (`native_layer_crosswalk.py:1251`)
takes `registry, *, arm, result, delivery_receipt, stream_receipt, knowledge_receipt,
outputs_receipt, sealed_proof, ledger_dir`. `emit()` today holds only `result` and the delivery
receipt. **If you call the gate with just those two, it will refuse nearly every applicable input
layer** - not because the run is bad but because emit() was never handed the evidence. That refusal
would be true but useless, and the temptation to weaken the gate to get past it is the exact failure
mode D-4 was written against.

**So the task is to give `emit()` the receipts, then gate on them.**

1. Extend `emit()`'s keyword-only signature with `stream_receipt`, `knowledge_receipt`,
   `outputs_receipt`, `sealed_proof` and `ledger_dir`, each `Path | str | None = None`, each loaded
   the way `delivery_receipt` already is (`_load_delivery_receipt` at `:92` is the pattern; reuse it
   or generalise it - do not duplicate the reader).
2. After the arm lookup at `:162`, build the crosswalk body with `registry=None` (it loads the live
   registry itself) and `arm=arm`, and pass every receipt through. `crosswalk()` already raises if
   the requested arm disagrees with the result identity's arm, so do not re-check that here.
3. Call `gate_applicable_inputs(body)`. Catch `CrosswalkGateError` and re-raise as `EmitError` with
   the original message preserved whole - the offender list IS the diagnosis and must not be
   summarised or truncated.
4. Put the call **after** the mission-hash check and **before** any prompt text is rendered. A
   refused spawn must not produce half a prompt.
5. Carry the crosswalk's own summary counts into the emitted prompt's evidence section by the same
   D82 rule the rest of that section follows: import the names from the module that computes them,
   never restate a number.

**Tests.** A result whose applicable inputs are accounted emits; a result with one unaccounted input
raises `EmitError` naming that layer id and its computed status; the message names **every** offender,
not the first. Derive the expected offenders from the crosswalk body in the test - do not type a count.

**Done when** `grep -rn 'gate_applicable_inputs' --include=*.py research/kalshi/frankie_raw_mbo_benchmark | grep -v tests/`
shows a caller in `emit_frankie_spawn.py`, and the gate cannot be satisfied by anything except a
computed row.

---

## 2. TASK B - AN HONEST FIXTURE FOR THE GATE (F-24, and it is the harder half)

**Why.** The existing fixtures cannot prove the gate can PASS. They carry an empty field census, no
retention receipts, a one-key legacy row, and one gate test that **hand-sets a status to DELIVERED**.
**A fixture that passes because a status was assigned is worse than no fixture**: it makes the gate
look wired while proving nothing about it.

**Do this.** Build the fixture from what production actually emits - drive a small fixture run
through `NativeReplayDriver`, take the result and the ledgers it really writes, and produce the
receipts from the real producers rather than by hand. Where a receipt genuinely cannot be produced
without a box run, **say so in the test's docstring and leave that layer unaccounted** - an honest
partial fixture that names its gap is the deliverable; a complete one that fabricates a receipt is not.

**Tests.** One test proves the gate PASSES on the honest fixture. One proves it FAILS when a single
receipt is withheld from that same fixture. Delete or rewrite the hand-set-DELIVERED test and say in
the commit body which one it was and why it proved nothing.

**Report to Greg** (do not solve it): the list of layers that could not be accounted without a run.
That list is the real remaining distance to a passing gate and nobody has ever written it down.

---

## 3. TASK C - WIRE THE KNOWLEDGE READ GATE

**Why.** The seam is built, named, and pinned `None` by a test so that wiring it flips a test rather
than going unnoticed. It has never been pointed at anything.

**Verified state.**

| symbol | file:line | today |
|---|---|---|
| `KnowledgeUseGate = Callable[..., Any]` | `native_staging.py:110` | the alias |
| `KNOWLEDGE_USE_GATE` | `native_staging.py:111` | `None` |
| the call site | `native_staging.py:337-345` | calls it only `if knowledge_use_gate is not None`, wraps any exception as `StagingError` |
| `validate_knowledge_use(knowledge_use, *, knowledge_receipt, model_visible_context, serialized_principal_input)` | `native_knowledge_delivery.py:1018` | the existing read gate |
| the default wiring | `native_staging.py:987` | `knowledge_use_gate=KNOWLEDGE_USE_GATE` |

**The shape mismatch is the task.** The seam calls
`knowledge_use_gate(body, knowledge_receipt_sha256=...)`. `validate_knowledge_use` wants
`knowledge_use`, `knowledge_receipt`, `model_visible_context` and `serialized_principal_input`.
Write the adapter that gets those four out of the artifact body and the staged run, and set
`KNOWLEDGE_USE_GATE` to it. **Do not change `validate_knowledge_use`'s signature** - it is the
existing gate and its four arguments are what make the binding proof work.

If any of the four cannot be obtained at that call site, **stop and report which one**. Do not pass
a placeholder: a read gate that validates against a fabricated context is worse than an unwired seam,
and this is the same shape as the hand-set fixture in Task B.

**Tests.** The pinned-`None` test flips to assert the gate is wired. An artifact citing an
undelivered knowledge id is refused BY NAME through `StagingError`. A well-formed one passes.

---

## 4. TASK D - F-35: STAMP THE FOUR FROZEN DOCUMENTS

**Why.** Four committed documents assert that `raw_actions` is absent and the order-lifecycle layers
read `RECEIPTED_CARRIER_ABSENT`. **All four are false of current code** since your own Task A last
session. They are dated records of what an earlier run delivered, so **rewriting them would falsify
history** - you were right not to touch them. But a frozen record that reads as live state is how a
closed defect gets re-opened as a finding two sessions later. That has now happened twice in this
program (S112, S114).

**The four files**, all under `research/kalshi/frankie_raw_mbo_benchmark/`:

- `FRANKIE_FEED_RECORD_SUNDAY_33630348943_20260903.md`
- `LAYER_CROSSWALK_SUNDAY_33630348943_RENDER_20260902.md`
- `LAYER_CROSSWALK_SUNDAY_33630348943_FED_RENDER_20260903.md`
- `LAYER_CROSSWALK_FIXTURE_RENDER_20260902.md`

**Do exactly this.** Add ONE stamp block immediately under each title. Nothing else in the body
changes - not a number, not a word. The stamp names: the date, the commit that changed the behaviour
(`e4d576f` for `raw_actions` on the member row; `9f984bf` for the crosswalk computing evidence from
delivered carriers), which specific assertions in that document are now superseded, and the sentence
that this is a dated record of what an earlier run delivered and is deliberately not rewritten.

**Then make it enforceable**, or the next one rots the same way: a test that fails if any of these
four files loses its stamp, and a document-registry entry for the stamp convention. Check
`research/kalshi/store.py docs` still passes.

---

## 5. TASK E - F-36: THE CENSUS BOUND MUST SAY WHAT IT SCANNED

**Why.** `_bounded_member_census` (`native_layer_crosswalk.py:1002`) scans at most
`MEMBER_SCAN_MAX_ROWS` (`:998`) and `MEMBER_SCAN_MAX_BYTES` (`:999`). The docstring is already honest
and the bound is already repeated in the evidence detail - that part is right. But against a 10.6 GB
member ledger that is a **prefix**, and a gate refusal that says a field is "absent" when it means
"absent from the first rows I read" is a false statement in the one place it costs most.

**Do exactly this.** Every status and evidence detail derived from a bounded scan says **absent from
the scanned prefix**, and carries the rows and bytes actually read (they are already returned by
`_bounded_member_census`). A census that reached the end of the ledger says so and keeps the
unqualified wording - the distinction between a complete scan and a truncated one must be visible in
the output, not just in the code.

**Tests.** A ledger longer than the bound yields the qualified wording and the true scanned counts; a
short one yields the unqualified wording. Do not type the bound constants in the test - import them.

---

## 6. TASK F - F-34: THE SEED'S PROOF IS ITS OWN SUBJECT

**Why.** The A_MEMORY seed's package layer and its proof layer **bind the same file**, so the proof
proves itself. Measured at the S122 close by executing the seal step. This is the S108 lesson exactly:
a check whose two sides share a source proves nothing.

**This is a declaration, not an invention.** Do NOT manufacture a receipt to make it look proven.
Either bind a real, independently produced receipt over the seed if one exists, or **declare the
collapse deliberately**: a named status on that layer saying the proof and its subject are the same
file, why that is currently unavoidable, and what would close it. A declared degenerate proof is
honest; an undeclared one is a false green.

**Test.** The declared status is computed from the two bindings being equal, not stamped - so it
clears by itself the moment a real receipt is bound.

---

## 7. EXPLICITLY OUT OF SCOPE - DO NOT START THESE

1. **Any workflow dispatch, canary or full.** D89, Greg, verbatim in rule 10.
2. **Retiring the 4.16 horizon ladder (F-32).** `HORIZON_SETS` (`native_response.py:146`) is the
   response table's architecture - fixed horizons, each with its own at-risk denominator, written
   once, refusing a second write, lateness per reading, read live by the launcher and the runner.
   Replacing it is a redesign and is Greg's call. Investigated and declined twice.
3. **Wiring `precursor_for` to make PRIOR reachable (F-33).** There is no precursor detector in the
   repository; wiring the callback means inventing one. `native_candidate_adapter.py:14-24` says so
   itself. `prior_reachable: false` is a true statement about the evidence surface, not a defect.
   **Proposed as a build item twice and refuted twice from the same paragraph. Do not raise it a third time.**
4. **Removing the retired A-clean overlay, profiles and workflow (F-28).** A D60 discussion, Greg's.
5. **Making `emit_frankie_spawn` succeed on the Sunday result 33630348943.** It refuses correctly:
   the bound mission and contract hashes no longer match the files on disk and the run predates the
   field census. **Never weaken a refusal to make a run pass.** Fix the feeding, never the gate.
6. **`tests/test_native_layer_crosswalk_s122.py`** on `persona/s121-wire-knowledge-gates` at
   `dd874f3`. It is the spec for unbuilt slices and fails five ways against what shipped, three of
   them because it asserts the F-30 absence you fixed. Read it for D-2's intended shape if useful;
   do not merge it.

---

## 8. ORDER

**A, then B, then C, then D, E, F.** A is the ruling. B is what makes A mean anything. C is
independent and small. D, E and F are the three that rot if left.

---

## 9. YOUR REPORT

Per task: DONE / IN_PROGRESS / NOT_STARTED; every commit sha with confirmation it was pushed; the
test count at your tip **read from an exit code, not from a pipe**; **anything in this file that
turned out to be wrong**; every decision that belongs to Greg, stated and left open (D60 - nothing
is dropped while it waits), specifically the Task B list of layers that cannot be accounted without
a run; and confirmation that no transient file was written outside `data/`, that the D61 adapter is
byte-identical, and that no workflow was dispatched.

---

# ADDENDUM - TASKS G, H, I (added S123 after the first report; base `b896c3f`)

Section 0's rules all still apply, **including rule 10: dispatch nothing.** These came from your own
diagnosis and from Greg's ruling on it. I have not re-verified G's and H's anchors - confirm each by
execution, and if a claim is wrong, say so and stop.

**Order: H, G, I, then A, B, C, D, E, F.** H unblocks any run at all. G is C's prerequisite. I is the
largest and is now the reason the rest matters.

---

## TASK G - the knowledge block is gated on but never rendered into the prompt

`emit_frankie_spawn.py` loads the knowledge receipt only for crosswalk and gating; it never imports
or calls `render_knowledge_block`, so the emitted prompt does not contain it. Frankie is spawned
knowledge-gated and knowledge-blind.

1. **Before packet Task C.** The read gate proves the exact model-visible context sits inside the
   serialized principal input. With no rendered block there is no context to prove and the gate is
   decorative.
2. Render in `emit()` from **the same receipt object the gate consulted** - not a re-load, not a
   re-read. What he is gated on and what he reads must be the same bytes, or the gate certifies a
   document he was never shown.
3. D82: import every name from the module that carries the block. Do not restate its schema,
   headings or counts in `emit_frankie_spawn.py`.
4. Tests: the prompt CONTAINS the rendered block; the block is derived from the gated receipt
   (assert the binding, not a substring); an absent receipt still refuses as today.
5. Report prompt size before and after - a D60 size decision, recorded now.

**Push G even though the seed is static** (see Task I). Today he reads no block at all, so a static
block is undetectable; once he reads one, "the same block every day" becomes an observable fact.
Do not widen G to build the loop.

---

## TASK H - the checkpoint memory-mode token mismatch (BLOCKER)

A bounded local A_MEMORY launch raises `CheckpointError: unknown benchmark memory mode`:
`native_a_arm_launch.py` writes `MEMORY`, the checkpoint contract accepts `MEMORY_ASSISTED`.

1. Find which token is canonical before changing either side. Locate the contract's definition of
   the accepted set and every writer and reader. The contract is the authority unless you can show
   the contract itself is wrong.
2. **Correct the WRITER.** Widening the accepted set so both pass is weakening a refusal to make a
   run go green - section 7 item 5. If the contract really is the wrong side, say so with the
   evidence and stop; that is a ruling.
3. `MEMORY_ASSISTED` and the arm id `A_MEMORY` are different vocabularies. Do not collapse them.
4. Treat it as a class: sweep every other token the launcher writes into the checkpoint against that
   contract and report every mismatch, fixed or not.
5. Tests: a bounded local A_MEMORY launch reaches checkpoint without raising; an unknown mode still
   raises by name. Reproduce the original failure first, then show the path passing.
6. Report whether the canary would have failed on this had it been dispatched.

---

## TASK I - THE DAY-OVER-DAY MEMORY LOOP (D90 + D91, F-37)

**REWRITTEN after Greg narrowed it (D91). An earlier draft of this task said the whole output bundle
accumulates. That was the wrong unit - ignore it if you saw it.** What accumulates is Frankie's
FINDINGS.

Greg: *"frankie generates a json with his new findings after a day run if there are any new ones and
that gets added to his memory so that it accumulates day after day like how a memory builds when you
are acquiring new knowledge every day. he can tell us what that is when he does his post run
analysis. if something feels off then we can take it out."* Confirmed: *"and it's an automatic
workflow."*

### I.0 Most of this is already built - verify before you write anything

The premise of this whole session holds again here: **built, not wired.** Confirm each by execution
and report anything that is not where this says.

| piece | state at `b896c3f` |
|---|---|
| the findings artifact | `principal_runs/33605852433/frankie_principal_findings.json` - 44 findings, schema `id, category, section, claim, evidence, falsifier, confidence_basis` |
| the admission gate | `NativeCalculationRun.attach_principal_findings` (`native_calculation_runner.py:461`) - **already refuses a finding with no falsifier** |
| the render gate | `render_frankie_report.REQUIRED_FIELDS` (`:33`) = `id, section, claim, falsifier` |
| the seed builder | `build_a_memory_seed.py` - reads `principal_runs/` **by rule**, so a newly committed findings file lands on the next `--write` |
| what is missing | the findings file reaching the committed tree, and an automatic workflow running the rebuild |

**DO NOT REBUILD THE FALSIFIER BAR.** It exists at the admission boundary. A promoted finding
already cannot lack a falsifier. If you find a path into the seed that bypasses
`attach_principal_findings`, that is a finding - report it.

### I.1 Close the two links, automatically

- **The findings file reaches the committed tree** under `principal_runs/<run_id>/`. Decide from the
  existing machinery which workflow does it and say why.
- **The rebuild sequence runs automatically** and commits: `build_a_memory_seed --write` ->
  `register_a_memory_knowledge --write` -> `rebind_registry_knowledge_layers --write` ->
  `refresh_native_frankie_knowledge --write`. The seed builder's docstring carries the order; nothing
  calls it today.

Name which link each commit closes.

### I.2 NEW ones only - and an empty day is a legitimate day

*"if there are any new ones."* **The loop must never require a finding.** A requirement to produce
one is a pressure to invent one.

- Carry forward only findings **not already in the seed**. Identity is the finding's own `id`; if ids
  are not stable across runs, say so rather than inventing a surrogate key.
- **A day with no new findings adds nothing and is not a failure.**
- **An empty findings file must be distinguishable from a run that never wrote one.** This is the
  S119 lesson exactly: seven of sixteen defects were correct calculators nothing ever called, each
  reporting an exact zero indistinguishable from a real measurement. Write that test first.

### I.3 Promotion is AUTOMATIC - a deliberate rejection of the PR pattern

`frankie_native_knowledge_refresh_20260828.yml` already carries a "Create reviewed refresh pull
request" job. **Do not copy it.** A carry that waits for a human to merge is not a day-over-day
carry. The promotion commits.

If automatic promotion genuinely cannot work - a permissions wall, or the promotion commit
retriggering the run - **state it and stop.** Do not silently fall back to a PR.

### I.4 THE VETO IS A LABEL, NEVER A DELETION

*"if something feels off then we can take it out."* Taking it out is a status change.

- A vetoed finding **stays in the seed** with its status and stops being SERVED.
- Veto by the finding's **id**, recorded in a committed file, applied by the builder on the next write.
- **Idempotent across rebuilds.** A rebuild that resurrects a vetoed finding is the defect this
  bullet exists to prevent - write that test first.
- **Never a git revert.** That discards the run record along with the lesson.
- Precedent, already inside the seed: the wrong-data run `32851909748-1` sits there AS the wrong-data
  run, labelled, never filtered (D60/D76).

### I.5 The carry explains itself inside the post-run analysis

*"he can tell us what that is when he does his post run analysis."* This is a **section of an output
he already produces**, not a new ceremony. It names which findings are new this day and why they
should be carried.

The fields it needs are already on every finding - `claim`, `evidence`, `falsifier`,
`confidence_basis`. Render them; do not invent a parallel vocabulary.

**Two rules that keep the incentive honest.** Only **stream evidence** moves a finding from
UNVERIFIED to VERIFIED (D86) - never the strength of its own write-up. And **an unpersuasive
explanation is not grounds for veto; an unfalsifiable finding is** - though the admission gate should
already have refused that one, so if an unfalsifiable finding reaches the seed, report the path.

### I.6 The bound is the roster, and four is never typed

`raw_mbo_source_manifest` pins the roster at exactly four objects (`:153`, `:203`). "These four days"
IS the roster. **Derive the bound; never type `4`** (rule 7). A fifth day is a manifest change, which
is a contract change, which is Greg's - not something the loop can drift into.

### I.7 Done when

A fixture run's findings reach the committed tree; the rebuild runs and commits with no human; a
second run adds only its NEW findings; a run with none adds nothing and is distinguishable from a run
that wrote no file; the next spawn's knowledge block (Task G) carries the new entries; a vetoed id
stays present and unserved across a rebuild; the bound comes off the manifest. Each with a test that
fails without its fix.

**Report to Greg, do not decide:** anything the loop cannot verify itself, any finding you believe
should have been vetoed and was not, and any path into the seed that bypasses the admission gate.
