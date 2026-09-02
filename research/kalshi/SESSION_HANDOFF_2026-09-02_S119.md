# SESSION HANDOFF — S119, 2026-09-02

**Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. 896 -> 1162 tests. Decisions 71 -> 77.**
**All sixteen defects in Frankie's register are CLOSED, WIRED and PUSHED. Nothing relaunched.**

---

## 0. READ THIS FIRST: HOW FRANKIE WAS RUN. NO API. NO SOL. NO BEDROCK.

This section exists because the question has cost most of a session more than once, and the
answer is now on the record so it does not cost another one.

**The principal for run 33605852433 was `claude-opus-5` — me, running as this agent session
over committed files.** Greg authorised it explicitly and unprompted:

> *"i'm completely fine with you running it and we don't need bedrock. that's not a critical
> piece for this. this is basicallly a test piece to run our native boss against so i truly
> don't care who runs it"*

**No provider API was called. There is no OpenAI call, no Anthropic API call, no Bedrock
invocation, and no `principal_invocation_id` anywhere in the run.** The mechanism is the same
one used for the blind/reveal group runs:

1. The traversal runs and writes a **committed staged request** — the evidence artifact plus
   its hash.
2. `emit_frankie_spawn.py` renders the prompt from that artifact, every slot by LOOKUP, and
   HALTS naming the failed lookup if any slot cannot be resolved.
3. The principal reads it as an agent session and writes a **committed artifact** back.
4. `corrected_a_arm_execution_gate_20260828.validate_principal_execution` binds the two by
   hash and **refuses identical hashes**, because a run that returned its own input produced
   no findings.

**That gate was rebuilt file-based at S115 for exactly this reason.** While it demanded
`provider` / `requested_model` / `served_model` / `principal_invocation_id` / token `usage`,
it would have **REJECTED a correct session run and accepted only an API one** — the
correction lived in prose while the check enforced the opposite. A test now pins that a
provider-shaped record is REFUSED, so the API shape cannot come back.

**The one dead instruction, struck not deleted:** `C2C_014_SWITCH_FRANKIE_TO_GPT56_SOL.md`
told a past session to call the OpenAI API. It carries a SUPERSEDED header and the instruction
is struck through. It is left readable because the switch it records did happen; what is dead
is the mechanism it named. Do not re-derive the architecture from it — that has happened more
than once.

**D70 records the seat as a decision, not an accident.** If a future run is to be Sol, that is
a new decision and a new seat; it is not the status quo, and nothing in the code needs a
provider to run.

---

## 1. What this session did

Frankie's report on the sixteen calculations — produced at the end of S118 from the first real
principal run — carried a **defect register of sixteen entries, D-1 through D-16**. Greg:
*"do all the fixes that are flagged before we do the next day run."* All sixteen are closed.

**The dominant finding, across the whole register: SEVEN of the sixteen were a correct
calculator that nothing ever called, and each reported a zero.** (D73.)

| what | what it reported | why |
|---|---|---|
| `f_last_to_decision_delay_ns` | n=0, **43,569 excluded** | no caller ever passed a decision time |
| `phase_depletion` / `phase_refill` | 0.0 at every quantile, **all 109 strata** | dataclass fields nothing wrote |
| SEARCHED `phase_duration_ns` | min = max = **0.0**, all 91 candidates | entered and left at the same nanosecond |
| `recurrence_count` | min = max = **0.0**, all 28 strata | `note_recurrence` existed, nothing called it |
| `censored_stage_age_ns` (4.13) | n=0, **21,651 excluded** | derived from an exit only a successor stamps |
| `ExhaustionCalculator.complete` | 91 opened, **0 completed, 91 censored** | never called at all |

**A measure that ran perfectly and was handed nothing is indistinguishable, in every gate we
had, from a measure that ran and found nothing.** Two more were sections BUILT AND DARK: 4.2
did not exist as a module, and 4.4's matcher was correct but absent from the runner's section
map, the numbering jumping 4.2 straight to 4.5. **A passing verdict is not evidence that a
section ran** — `DarkSectionRegressionTest` now asserts that directly, aimed at the shape
rather than at the two instances.

---

## 2. The gate (D72), and the review that found it evadable

Frankie, unprompted, on his own highest-value change:

> *"If only one of those three ships, ship the gate. The binding fixes one defect; the gate is
> what would have caught it."*

The eight existing section-6 gates each check a section **against itself** — declared
denominators, reconciled populations, exact members beneath every summary — and a one-sided
book satisfies every one of them. On run 33605852433, **4.9 returned exactly +/-1.0 on 152 of
154** readings of `(bid-ask)/(bid+ask)` while **4.12 computed the identical formula on the same
instrument and day and returned [0.0116, 0.1109] on 3,454**, never once reaching a bound. **All
eight gates passed.** The only thing separating a correct book from a one-sided one was a
second computation of the same quantity sitting in the same artifact, and nothing compared them.

`native_cross_section_agreement.py` is the ninth gate and the **only horizontal one**. The test
is **distributional, not a range check**: 4.9's `[-1, 1]` CONTAINS 4.12's range, so only shape
separates them.

**Then a code-review persona found the first version evadable by the exact defect class it was
built for.** Mean and extreme share BOTH cancel under sign symmetry — a section pinned half at
+1 and half at -1 has a mean of 0.0, and a stratum straddling both bounds contributes no
extremes because a summary cannot be resolved into members. So a **100%-degenerate section
passed simply by being stratified differently**, and the real run only fired because 4.9's
strata happened to be sign-pure. Closed by leading on the **population-weighted second
moment**, `sum(sum_of_squares)/sum(n)` — already emitted on every distribution row and going
unread. It does not cancel and does not move under re-stratification: on the real artifact it
separates **0.9871 from 0.0031** against a 0.10 tolerance, where the mean managed 0.1291
against 0.05.

Five further evasions closed, each reproduced before and after: a populated row with a missing
`sum` read as a mean of exactly 0.0; `value["n"]` alone reads zero for RATIO_PAIR and SURVIVAL
rows, so a future register entry naming one would be permanently blind; reversed bounds
silently disabled the extreme-share test while reporting a clean pass; values outside their own
declared bounds passed; and four legitimate one-sided readings could reject a whole run.

**Register entries are added when a shared estimand is IDENTIFIED, never when a disagreement is
found** — a register that grows only in response to known defects tests only the defects
already known. It now carries three members for `relative_book_imbalance`: 4.9, 4.12 and the
new 4.2, which reads the book most directly. Three measurements from three substrates locate
the odd one out where two only say that one of them is wrong.

---

## 3. The defects, one line each

| # | what it was | what it is now |
|---|---|---|
| **D-1** | decision clock n=0, all 43,569 excluded | replay decides at F_LAST; delay 0 with the **basis on the record** so a measured zero is never an unknown one |
| **D-2** | depletion/refill 0.0 in 109 strata | fed from 4.8's own per-group quantities; same-side only; multiplicity published |
| **D-3** | `restoration_ratio` was arrival density, 18.18 attributions/episode | **relabelled** `neighborhood_arrival_ratio`; arithmetic untouched so the comparison survives |
| **D-4** | **4.2 did not exist**; `book_full` (10.13 GB, 93.47%) had no consumer | `native_book_regime.py`; reads the book already on the row |
| **D-5** | 4.9 on a one-sided book; +/-1.0 on 152 of 154 | bound to the reconstructed full book; BOTH sides emitted always |
| **D-6** | 4.14's interarrival was 4.5's within-group gap, byte for byte | `same_path_interarrival_gap_ns` — the 19,625 recurring paths finally measured |
| **D-7** | absorption + withdrawal = one degree of freedom, labelled as two | identity stated in the formula; `traded_over_opposite_retreat_ratio` is the free dimension |
| **D-8** | replacement numerator 0.0 in all 205 strata | **neither proposed cause** — see below |
| **D-9** | censored age excluded 100% of the censored | censoring clock is an INPUT, as 4.6 already had it |
| **D-10** | 4.16 emitted 1 of 7 channels | flow/full-book/queue fed; three REFUSED by name; six horizons |
| **D-11** | SEARCHED duration and recurrence count both 0.0 | searched span is the trailing window; recurrence comes from 4.14 |
| **D-12** | 1,692 strata for 3,454 obs; **zero REVERSAL stages** | stage index binned into closed octaves; phase decided before the stage is observed |
| **D-13** | one declared population for two units | six measures, six true populations; the fifteen made countable |
| **D-14** | `cluster_version` empty on 16,209 of 16,293 rows | `CLUSTERING_NOT_RUN` is a declaration; the empty string is refused |
| **D-15** | two root counts differing by exactly 48 | both named and reconciled; the identity is a CHECK, not a definition |
| **D-16** | 4.4: zero pairs, no distance, no reasons | reasons and distances **at zero pairs**, which is when the diagnosis is needed |

### The three worth reading in full

**D-8 was NEITHER cause Frankie proposed** (D74). He offered *"either same-side replacement is
not being attributed to the runway, or the numerator is not wired."* It was wired and it was
attributed. It could not fire because it was scoped to a **single F_LAST group**, and on this
tape depletion and same-side addition are mutually exclusive inside one: **24,617 of 43,569
runways are INDETERMINATE — zero depletion, the pure-add groups — and the 18,952 carrying
depletion contain no adds at all.** A maker replacing size it just lost does so in a LATER
group. **No amount of tape would have made that numerator nonzero.**

**D-12's fix could not ship alone without fabricating data** (D75). Making stages carry their
own second's phase is what lets REVERSAL exist. But `close_segment` **also** stamped REVERSAL,
for episodes merely cut off at a boundary — inert while the off-by-one hid it, and actively
false the moment it is fixed. Censored episodes now end in a registered discovered phase,
`CENSORED_AT_OBSERVATION_END`, deliberately absent from `TERMINAL_PHASES`.

**4.16's regime came back NEGATIVE on the obvious hypothesis.** `starting_liquidity_regime`
read `DEPTH_SKEW_BID` on all 84 at-risk rows, and the natural guess — that it was downstream of
D-5's one-sided book — is **wrong**. It reads the full reconstructed book and did so before
that run. It is a bare sign comparison of two absolute depths and the sign never flipped on
this instrument-day, corroborated by the reopen snapshot's 154 bid adds against 90 ask and ~121
occupied bid prices against 76. **That is D23 applied to a stratum key: a condition that cannot
change state carries no information, whatever form it is written in.** The real repair is to
source it from 4.2, which now exists.

---

## 4. Two mistakes of mine, recorded because the pattern matters

**A stream-end finalize in the wrong loop.** Adding absorption to the driver's finalize list
for D-8, the edit landed in the **segment-close** loop instead of the **stream-end** one, so
pending same-side replacements never censored at end of stream. The D-8 tests passed because
they call the calculator directly. Found only by wiring D-16 through the same path. **A unit
test on a calculator does not test the driver that is supposed to call it — which is the
session's own dominant finding, committed by me while writing it up.**

**A subagent reverted the shared tree** (D77). It ran `git stash` to measure a baseline and
swept every session's uncommitted work — my 4.2 wiring plus four agents' output — in one
command. Recovered in full from the stash, verified against scratchpad copies, nothing lost,
and the agent reported it against itself. **The parallel fan-out was still worth it** (six
defects in disjoint sections closed concurrently) but the isolation is the FILE boundary only
and the tree is shared. Next time: `isolation: worktree`, and never an agent instruction that
can touch git state.

---

## 5. Documentation state, including a gate I turned red

The document registry held **44 entries against 236 tracked documents**, so **192 carried no
class and no gate could reach them.** The andon had been red for several sessions. Closed: the
158 with a session or date suffix are RECORD **by rule** (the class is literally "dated and
finished"); the remaining 34 were classified by hand. The load-bearing ones are named — the
**mission and the calculation contract are VAULT**, because they are HASH-BOUND into every run
identity and S119 changed the mission and locked the spawn emitter out of two prior runs by
doing so; the five `mbo_specialist_*.md` are LIVE because blind and refine read them
byte-identical.

`index_py` is now green — 25 untracked-in-the-index modules named, of which 20 predated this
session.

**I made one andon line worse, and it is the correct kind of worse.** Station 0 read *"6 of 7
briefings never audited"*; it now reads **23 of 27**, because classifying the C2C packets as
EXTERNAL made seventeen previously-invisible briefings visible to the audit. Under D36 an
EXTERNAL document carries recommendations and must be audited against the registry. **The
number rose because the denominator became honest.** Do not fix it by reclassifying them back.

The other FAIL — `branch ... EXPECTED claude/kalshi-agents-coordinator-guard-sg0n15` — is
stale and has been since S115. This line is the A-arm benchmark, not the forecaster trunk.

---

## 6. Where it stands, and what is NOT done

**Nothing was relaunched.** The last real run is still 33605852433 (Sunday, complete session,
57,027 records, 43,569 groups), produced against the code as it was **before** all sixteen
fixes. Every number quoted above comes from that artifact.

**Open, in the order Greg set them:**

1. **The token reducers.** Measured, not applied (D71): key names are **49.5%** of the averaged
   companions at all depths and aliasing saves **33.8%**, about 1.69M tokens on Sunday alone.
   `plan_retrieval` is untouched and is still where D67's real value sits.
2. **Rerun the canary AND Sunday** on the corrected code. Greg: *"we will rerun frankie with
   the new changes over the canary and sunday again before we do the weekday so we have 2
   separate pieces to gauge what if anything we can drop."*
3. **Then the weekday.**

**D76 governs how the drop question is asked.** Greg, verbatim: *"frankie doesn't have to find
something that we should drop. if he says to keep everything then we keep it."* The measurement
already points there — **all sixteen calculations combined are ~1.5% of the bytes and the most
expensive, `replenishment`, is 0.6%** — so dropping a calculation saves essentially nothing.
The only thing with mass is the per-group `book_full` snapshot at **93.47%**, which Greg has
already ruled stays.

**Two things need Greg, and neither was pre-empted:**

- **4.16's event-driven change points.** Under D60 every change point is retained on its track,
  so retained volume becomes open tracks times changes — up to **91 tracks against 43,569
  groups** on Sunday. That is a size decision. Unfed, the summary declares
  `NOT_FED_BY_THE_TRAVERSAL` rather than staying silent.
- **The box's instance role still has NO S3 access** (`A_ARM_CAN_READ_SOURCES=no`,
  `A_ARM_CAN_READ_PACKET=no`). Reads are worked around with presigned GETs; **the UPLOAD cannot
  be.** The scoped policy is written and NOT applied:
  `research/kalshi/FRANKIE_A_ARM_FULL_DISPATCH_BLOCKER_20260830.md`.

**Unchecked:** the canary re-traversal dispatched against the corrected mission. Its status was
never read back, and it is item one of the next session.

**Also flagged and not acted on**, each reported rather than done: 4.6's exit-stamped stratum
(F-17 — 97.3% of lifecycles outlive their birth group; it changes stratum construction and is a
different defect from D-13); `replaced_quantity` in 4.7 carries the same naming defect the old
ratio did; and the fifteenth queue-episode residual cannot be attributed by cause from the
committed artifact, so it was made **countable** instead of guessed at.
