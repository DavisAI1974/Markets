# DROP-IN S120 — Frankie A-arm raw-MBO benchmark

**Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`. Tip `9fb041a` "S119 close-out",
1162 tests green.** First commands of the session:

```bash
git fetch origin chatgpt/frankie-raw-mbo-benchmark-20260828
git checkout -B chatgpt/frankie-raw-mbo-benchmark-20260828 origin/chatgpt/frankie-raw-mbo-benchmark-20260828
git log --oneline -1
python3 -m pytest research/kalshi/frankie_raw_mbo_benchmark/tests/ -q   # expect 1162 passed
```

Read, in order: `SESSION_HANDOFF_2026-09-02_S119.md` **section 0 first**, then this file.

---

## ITEM ZERO — HOW FRANKIE IS RUN. DO NOT RE-LITIGATE THIS.

**The principal is an AGENT SESSION over committed files. There is no API call — not OpenAI,
not Anthropic, not Bedrock.** Run 33605852433 was run by `claude-opus-5` (the assistant
session itself), with Greg's explicit authorisation:

> *"i'm completely fine with you running it and we don't need bedrock. that's not a critical
> piece for this. this is basically a test piece to run our native boss against so i truly
> don't care who runs it"*

The mechanism, and the only one:

1. traversal writes a **committed staged request** (evidence artifact + hash);
2. `emit_frankie_spawn.py` renders the prompt, every slot by LOOKUP, HALTING on any it cannot
   resolve;
3. the principal reads it as a session and writes a **committed artifact** back;
4. `validate_principal_execution` binds the two by hash and **refuses identical hashes**.

`corrected_a_arm_execution_gate_20260828` was rebuilt file-based at S115 precisely because,
while it demanded `provider` / `served_model` / `principal_invocation_id` / token `usage`, it
would have **REJECTED a correct session run and accepted only an API one**. A test pins that a
provider-shaped record is refused.

**`C2C_014_SWITCH_FRANKIE_TO_GPT56_SOL.md` is SUPERSEDED and its API instruction is struck
through.** It is left readable because the switch it records happened; the mechanism it named
is dead. **Do not re-derive the architecture from it — that has already happened more than
once and cost most of a session each time.** If a future run is to be Sol, that is a NEW
decision (D70 records the seat as a decision, not an accident).

---

## The state

**All sixteen defects in Frankie's register (D-1 … D-16) are CLOSED, WIRED and PUSHED.** 552 ->
1162 tests. Decisions 71 -> 77. **Nothing has been relaunched**: the last real run is still
33605852433, produced against the code as it was BEFORE the fixes, so every number in the
handoff comes from the pre-fix artifact.

The dominant finding, and the reason the ninth gate exists: **seven of the sixteen were a
correct calculator that nothing ever called, and each reported an exact zero.** Two more were
sections BUILT AND DARK — 4.2 had no module at all, and 4.4's working matcher was absent from
the runner's section map. **A passing verdict is not evidence that a section ran.**

---

## The work, in Greg's order

### 1. Token reducers

Measured, not applied (D71). Key names are **49.5%** of the averaged companions at all depths —
56 names repeated 788,868 times across 20,023,101 compact bytes — and 1–2 character aliasing
saves **33.8%**, about **1.69M tokens on Sunday alone**. Top-level keys alone are only 7.0%, so
a measurement that stops at the outer level misses six sevenths of the cost.

**`plan_retrieval` is untouched and is still where D67's real value sits.** The skeleton is
137 KB and Frankie read the rows section by section, so the practical cost of the Sunday run
was never 5M tokens. Aliasing lowers the ceiling; declared refusable retrieval decides how
much of the ceiling anyone reaches. They are complementary.

Detail: `FRANKIE_MEASURED_TOKEN_REDUCTION_20260902.md`.

### 2. Rerun the canary AND Sunday on the corrected code

Greg: *"we will rerun frankie with the new changes over the canary and sunday again before we
do the weekday so we have 2 separate pieces to gauge what if anything we can drop."* Two
independent slices, one weekday-shaped and one reopen, before the weekday run.

**Item one of the session: the canary re-traversal dispatched against the corrected mission at
S119 was never checked.** Read its status before dispatching anything new.

### 3. THE DROP QUESTION IS NOT A HUNT (D76)

Greg, verbatim: *"frankie doesn't have to find something that we should drop. if he says to
keep everything then we keep it."*

The measurement already points there: **all sixteen calculations combined are ~1.5% of the
bytes and the most expensive, `replenishment`, is 0.6%.** Dropping a calculation saves
essentially nothing. The only thing with mass is the per-group `book_full` snapshot at
**93.47%**, which Greg has already ruled stays. Frame the D68 report as an open question with
keep-everything as a first-class outcome.

---

## Needs Greg, and neither was pre-empted

- **4.16's event-driven change points.** Under D60 every change point is retained on its track,
  so retained volume becomes open tracks × changes — up to **91 tracks against 43,569 groups**
  on Sunday. That is a size decision. Unfed, the section declares
  `NOT_FED_BY_THE_TRAVERSAL` rather than staying silent.
- **The box's instance role has NO S3 access** (`A_ARM_CAN_READ_SOURCES=no`,
  `A_ARM_CAN_READ_PACKET=no`). Reads are worked around with presigned GETs; **the upload cannot
  be**, and a run ending `A_ARM_RESULTS_ON_BOX` is a finished traversal and an unfinished run,
  because D34 puts data on S3. The scoped policy is written and NOT applied:
  `FRANKIE_A_ARM_FULL_DISPATCH_BLOCKER_20260830.md`.

---

## Two andon lines are RED, and one of them I made worse on purpose

- **`station0/briefings`: 23 of 27 unaudited, up from 6 of 7.** The number rose because
  classifying the C2C packets as EXTERNAL made **seventeen previously invisible briefings
  visible to the audit**. Under D36 an EXTERNAL document carries recommendations and must be
  audited against the registry. **The denominator became honest. Do not fix it by
  reclassifying them back.**
- **`branch ... EXPECTED claude/kalshi-agents-coordinator-guard-sg0n15`** — stale since S115.
  This line is the A-arm benchmark, not the forecaster trunk.

The document registry itself is now complete: **44 entries against 236 tracked documents became
239 of 239.** `index_py` is green.

---

## Standing rules that bit this session

- **D60 — nothing is dropped without discussing it first.** Seven of the sixteen defects were
  this rule's failure mode in its quietest form: not a dropped row, a measure with no input,
  reporting a zero that looked exactly like a finding.
- **D77 — parallel agents may never touch git state in a shared worktree.** A subagent ran
  `git stash` to measure a baseline and reverted five sessions' uncommitted work in one
  command. Recovered in full, nothing lost, and the agent reported it against itself. The
  fan-out was still worth it — six defects in disjoint sections closed concurrently — but the
  isolation is the FILE boundary only. **Use `isolation: worktree` next time.**
- **A caveat that lives only in prose expires.** Every fix this session put its qualifier ON
  the value as a field: `decision_basis`, `ladder_scope`, `opened_basis`,
  `starting_liquidity_regime_basis`, `stage_bin_rule`, `attribution_rule`.
- **Store discipline.** `DECISIONS.md`, `OPEN_ITEMS.md`, `RUN_SOP.md` and the knowledge
  capsules are RENDERS. Edit the store or the source spec, then `store.py check --write` /
  `refresh_native_frankie_knowledge.py --write`. Never the render.

---

## Also flagged, not acted on

Each reported rather than done, so none of it is a silent omission:

- **4.6's exit-stamped stratum** (F-17): 97.3% of lifecycles outlive the group that gave rise
  to them. It changes stratum construction and is a different defect from D-13.
- **`replaced_quantity` in 4.7** carries the same naming defect the old `restoration_ratio` did
  — it is the ratio's numerator and "replaced" implies replacement of what left.
- **The fifteenth queue-episode residual** cannot be attributed by cause from the committed
  artifact, so it was made **countable** rather than guessed at.
- **4.7's many-to-many attribution is unchanged and deliberate.** Only its labelling was wrong,
  and only the label was fixed, so the comparison with run 33605852433 survives.
