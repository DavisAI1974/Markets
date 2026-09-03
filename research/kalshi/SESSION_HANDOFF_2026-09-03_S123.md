# SESSION HANDOFF 2026-09-03 S123 - THE WIRING IS FINISHED AND THE RUN IS THE ONLY THING LEFT

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Opened at `a30c7f4` (1,973 tests), closed at the
tip carrying this file. **1,997 benchmark tests, and 2,706 across all three trees.** Decisions 88 -> 91.

**READ SECTION 0 FIRST.**

---

## 0. THE STATE IN ONE PARAGRAPH

S122 closed saying two sessions of wiring had landed and nothing had been fed. **S123 finished the
wiring.** Tasks A through I are implemented, tested and pushed: the spawn gate calls
`gate_applicable_inputs`, the knowledge read gate is wired, the knowledge block is RENDERED into the
prompt, the frozen records are stamped, the bounded census says what it scanned, the degenerate seed
proof is declared, the checkpoint mode token is corrected, and **the day-over-day memory loop is
built and automatic.** **Nothing was dispatched.** The run is the whole of the next session, and it
is now blocked by nothing except a review that has not happened.

---

## 1. THE ORDER WAS REVERSED, AND IT PAID FOR ITSELF THE SAME DAY (D89)

`DROP_IN_S123.md` opened by saying run first, and Greg reversed it: *"we are not doing canary until
all of this other stuff is done first."* Recorded as **D89** and the drop-in was CORRECTED rather
than stamped, because it is a live expectation and F-35's taxonomy says a stale live expectation
preserves the defect if kept.

**The reversal was vindicated within hours.** Task H found that a bounded local A_MEMORY launch dies
with `CheckpointError: unknown benchmark memory mode` - `native_a_arm_launch.py` wrote `MEMORY` while
the checkpoint contract accepts `MEMORY_ASSISTED`. **The canary would have failed at checkpoint had
it been dispatched as the original drop-in instructed.** The fix corrected the WRITER, keeping the
contract authoritative; widening the accepted set would have been weakening a refusal to make a run
go green.

---

## 2. THE MEMORY LOOP (D90, D91, F-37)

**The measured gap.** Asked which workflow ingests run outputs into A_MEMORY, the answer was **none,
and none ever did.** `frankie_native_knowledge_refresh_20260828.yml` is a determinism gate whose
`git diff --exit-code` step makes ingestion impossible by construction. `build_a_memory_seed.py` was
the only path from a past run into the seed and no workflow called it. No workflow referenced
`principal_runs/`, which held exactly one entry. The launch workflow commits nothing; it PUTs to S3
and returns. **Commit `8039f39` removed the wrong-data PACKAGE step, not an accumulation loop -
there was never a loop**, which makes this a build item and not a regression, and stops the next
session hunting for what broke.

**D90 (Greg):** build it, promote automatically, keep a veto, bound it to the roster, and have
Frankie argue for his own carry. **D91 narrowed the unit:** what accumulates is his FINDINGS JSON,
new ones only, by automatic workflow - *"like how a memory builds when you are acquiring new
knowledge every day"* - explained inside the post-run analysis he already produces, and *"if
something feels off then we can take it out."*

**Three design calls, each with a plausible wrong version:**

- **Promotion is automatic**, which deliberately rejects the reviewed-PR pattern the refresh workflow
  already carries. A carry that waits for a human to merge is not a day-over-day carry.
- **The veto is a LABEL, never a deletion.** A vetoed finding stays present with `served: false`.
  The precedent was already in the seed: the wrong-data run `32851909748-1` sits there AS the
  wrong-data run, labelled, never filtered (D60/D76). Never a git revert - that discards the run
  record with the lesson.
- **An empty day is a legitimate day.** The loop never requires a finding, because a requirement to
  produce one is a pressure to invent one - and `PRESENT_EMPTY` is distinguished from `MISSING`,
  which is the S119 lesson exactly, where seven of sixteen defects were correct calculators nothing
  ever called, each reporting an exact zero indistinguishable from a real measurement.

**The risk that was designed against rather than discovered:** Greg asked for a convincing argument,
and if the gate is "convincing" then the optimised thing is RHETORIC. So the carry's case is
structured evidence, only stream evidence moves a finding UNVERIFIED -> VERIFIED (D86), and an
unpersuasive argument is not grounds for veto while an unfalsifiable finding is - though
`attach_principal_findings` **already refuses a finding with no falsifier**, so that bar existed and
was not rebuilt.

---

## 3. MY THREE PREMISES WERE WRONG, AND THE CAUSE IS A DEFECT CLASS WE HAVE ALREADY NAMED

I specified Task I on three claims, all false, all reported back by the implementer rather than
worked around:

1. `build_a_memory_seed` "derives membership by rule, so a newly committed findings file lands on the
   next `--write` with no code change." **It was hard-coded**: `LAST_RUN_DIR = PKG +
   "principal_runs/33605852433/"` at line 62.
2. It routes findings through the admission path. **It did not** - zero references to
   `attach_principal_findings`; it hashed files directly, bypassing the gate. Reporting that bypass
   was an explicit instruction in the packet, and it was found and closed.
3. The loop would finally read the 44 S119 findings, closing an S120 item. **It does not read them**
   - their ids are run-local (`F-01`) and they lack the current path's exemplars, so they stay the
   historical A_CLEAN day-one artifact and S120's finding stays OPEN.

**Where premise 1 came from is the part worth keeping: the module's own docstring said "Derived,
never typed. Membership is read off the tree by rule."** The prose asserted a property the code did
not have, and I put it in a task packet and a decision record without executing it. **This is the
F-30 shape from last session - a false invariant in a comment is why nobody re-checks - and I
enforced verify-by-execution on everyone else all session while breaking it myself.** The docstring
is now honest and the code matches it.

D91 carries the third claim STRUCK in place rather than quietly amended: a decision record that
overstates what a build achieved is the same defect as a frozen record that reads as live state.

**Two smaller errors of mine, recorded:** the F-37 registry row was built by copying the previous
entry and silently inherited F-36's entire body - caught on inspection and every field rewritten,
but a half-copied registry row reads as real later. And I reported a `REQUIRED_STARTING_TIP`
ancestry failure as a possible blocker before establishing that the container clone is shallow
(grafted at 140 commits), which makes `merge-base --is-ancestor` a false negative; CI checks out at
`fetch-depth: 0`, so the check is inconclusive from here and is recorded as inconclusive.

---

## 4. WHAT LANDED

| Task | What |
|---|---|
| A | `emit()` obtains every receipt, computes the live crosswalk, and calls `gate_applicable_inputs` before rendering; refusal preserves all offenders |
| B | The hand-set `DELIVERED` fixture replaced by a producer-built honest one; withholding the receipt proves refusal |
| C | `KNOWLEDGE_USE_GATE` wired through an adapter to `validate_staged_knowledge_use`; placeholder arguments refuse |
| D | Four frozen F-35 records stamped, not rewritten, with a regression test |
| E | Bounded scans say `ABSENT_FROM_SCANNED_PREFIX` with rows and bytes; only an EOF scan claims plain absence |
| F | The one-day seed subject/proof equality DECLARED a degenerate bootstrap rather than papered over with a manufactured receipt; clears itself when a distinct receipt exists |
| G | The knowledge block rendered from the exact receipt object the gate inspected; prompt 13,092 -> 15,999 bytes (+22.2%) |
| H | Checkpoint writer corrected `MEMORY` -> `MEMORY_ASSISTED`; contract kept authoritative; unknown modes still raise |
| I | The automatic findings carry: discovery by rule, admission through the shared path, new stable ids only, empty days recorded and not promoted, vetoes by id kept and unserved, ordered rebuild, direct commit, no review PR |

The C/G coupling was checked rather than assumed: before G the gate was **not** vacuous - staging
separately serialized the bundle and the prompt alone refused with `serialized principal input lacks
exact model-visible context`. C bound the bundle; G was still required to put the rendered block in
the prompt.

---

## 5. WHAT IS NOT DONE

- **The run.** Nothing blocks it but the review. F-31 stands.
- **The review of A-I.** The implementer explicitly asked for one and named what must not be
  weakened. It was not started here, deliberately - reviewing nine tasks on a spent budget is how a
  rubber stamp happens, and a rubber stamp before the first real run is the worst place for one.
- **The loop's first link is outside the machine and was declared, not hidden.** Actions cannot make
  an uncommitted external findings artifact appear in the repository. The carry starts when that
  commit ARRIVES, and the loop cannot verify that it ever does. This is the one way the loop
  silently never fires.
- **The 44 historical findings are not in memory** (section 3), so day-one memory is the seed alone.
- Task B named four layers it cannot account for without a real run rather than fabricating
  receipts: the DBN decoding witness, S3 object identity, `PLAIN_SIZES`, `PLAIN_SHA256SUMS`.

---

## 6. VERIFIED BY EXECUTION AT THE CLOSE

- **Benchmark suite 1,997 passed / 6,389 subtests** (exit code read from a file, not a pipe).
- **`research/kalshi/tests` 664 passed. `tests/` 45 passed, 10 skipped.** The other two trees were
  run because a green package suite says nothing about the rest of the repository.
- **193 workflows parse, 0 failures.** The retired October launch has no push trigger and all three
  jobs guarded `${{ false }}` - retained as a record, incapable of launching.
- Store check 4/4, docs gate pass, D34 grep clean on new files.
- **D61 adapter byte-identical**, sha256 `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce`.
- No workflow dispatched, in any mode.
