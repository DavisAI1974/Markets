# DROP-IN S124 - REVIEW COMPLETE; RUN ONLY WHEN AUTHORIZED

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Check `git log --oneline -1`; the tip must carry
`SESSION_HANDOFF_2026-09-03_S123.md` or later. **S123 baseline: 1,997 benchmark tests and 2,706
across all three trees. S124 complete pytest: 2,004 passed, 14 warnings, 6,389 subtests.**

Read `SESSION_HANDOFF_2026-09-03_S123.md` section 0, then this. Nothing else before you start.

---

## ITEM ZERO - THE WIRING AND REVIEW ARE FINISHED. AUTHORIZATION STANDS BETWEEN HERE AND A MEASURED RESULT.

Three sessions built this. S121 wired the causal stream, crosswalk, output ledgers and clocks; S122
carried `raw_actions`, stamped the lifecycle rows, retired the fixed windows and built the seed;
**S123 finished it** - the spawn gate called, the knowledge gate wired, the knowledge block rendered,
the checkpoint token fixed, and the day-over-day memory loop built and automatic.

**S124 correction completed before review or run:** the 44 established findings are now in Frankie's
A_MEMORY seed unchanged and served as `VERIFIED`. Their ids, content, dates and historical A_CLEAN
source provenance remain intact. Future admitted findings are `NEW`, meaning recent rather than
uncertain; their existing exemplar/falsifier admission gate is unchanged. `VETOED` alone blocks
service.

The calculation instruction is also now explicit end to end: the mission and contract are
`ALWAYS_LOAD`, the emitted prompt tells Frankie to compute every current `### 4.x` section himself,
and the output gate derives the required ledgers from that contract. The current set is 18—4.0,
4.0b and 4.1–4.16—not the stale count of sixteen. Those exact 18 section identities are the minimum
floor; later headings grow the set but cannot replace a baseline section. A section with no lawful
population still returns a reasoned `NULL_RESULT`; silent omission refuses the whole spawn. The mission tells him why he is
doing them: to discover causal market mechanics, relationships, falsifiers and possible signals,
including how non-exhaustion behavior connects to exhaustion—not merely to fill ledgers with math.
After direct inspection he must also assess whether any raw-MBO layer or field group adds no value
to ongoing ingestion. If so, he recommends it with evidence and Greg decides whether to eliminate
it; Frankie does not remove it and is under no obligation to find one. `KEEP EVERYTHING` is valid.
Exactly zero informational value is the only elimination bar: even slight credible value means
KEEP. That applies to `book_full` and FIFO as whole surfaces and to every constituent field, depth
level, order identity, queue, queue-position fact and derived component; no part inherits a broader
elimination verdict.

**Nothing has been fed by a run on the wired code. That has been true for three sessions and it is
still true.** F-31 stands, and it is now the only ESSENTIAL item that a session can close by itself.
The roster is run as four separate complete daily productions—October 1, 3, 4, then 5—with each
day frozen and promoted into A_MEMORY before the next day begins. The earlier bounded execution
used less than a full day's MBO and is not complete-day proof.

**Initial four-day input isolation:** reliable day-aligned October 2021 values are not currently
available for weather, storage, COT/positioning, pipeline/LNG, production/demand,
grid/nuclear/solar, STEO, options, cash basis, macro or equivalent non-MBO context. For these four
one-day runs they are `IGNORE_AS_EVIDENCE`: do not infer, fabricate, backfill, retrieve or use
them. Their input identities are preserved for later phases and later dates where aligned values
exist; this is not deletion and not a zero-value judgment. Native raw/derived MBO, the full
calculation mission and all 44 A_MEMORY seed findings remain in scope. A historical mention of an
external input in a seed finding is provenance only, not a substitute for missing day-aligned data.

The review is complete. It found and closed two required run-boundary gaps:

1. The carry accepted a later roster day while an earlier day's artifact was `MISSING`; it now
   refuses that order while treating `PRESENT_EMPTY` as a legitimately completed day.
2. `is_bounded_slice` alone mislabeled a full source day when the workflow supplied that object's
   exact record count as a bound; the launcher now derives `is_complete_source_day` from the
   manifest object and the prompt reports complete versus reduced evidence from that field.

No other Critical or Required A–I review finding remains. **The run is next, but it still requires
Greg's authorization. Nothing was dispatched during the review or these corrections.**

After the final D99 input-isolation correction, the six changed test modules pass all 289 tests.
Store/generation checks, JSON parsing, `py_compile`, `git diff --check` and the D61 hash gate pass.
The current scratch runtime lacks pytest and databento, so the earlier complete 2,004-test pytest
result remains the latest full pass; unittest discovery separately executed 1,988 tests without an
assertion failure and reported three import errors caused by the absent databento package.

---

## ITEM ONE - REVIEW RECORD

The review read `research/kalshi/CLAUDE_S123_A_I_IMPLEMENTATION_HANDOFF_20260903.md` and checked
the five named high-risk areas rather than treating the prior green suite as approval.

**These six were checked:**

- **The spawn gate (Task A)** passes the producer-built accounted fixture and preserves every
  computed offender/status when refusing an unaccounted one. A live result still requires the
  authorized canary; the review did not fabricate one.
- **The honest fixture (Task B)** names four layers it cannot account for without a run - the DBN
  decoding witness, S3 object identity, `PLAIN_SIZES`, `PLAIN_SHA256SUMS`. They remain named rather
  than fabricated, and withholding the computed knowledge receipt refuses the gate.
- **The C/G coupling** passes only when the renderer receives the exact already-gated receipt
  object; absent knowledge still refuses, and the rendered block is present byte-for-byte.
- **The D60 prompt-size watch.** G grew the earlier honest fixture prompt from 13,092 to 15,999
  bytes (+2,907, 22.2%). After adding the 44 findings, the regenerated build-time knowledge block
  alone is 128,418 bytes. Neither number is an actual emitted prompt from a live run. The review
  preserved the watch; record the
  first run's actual emitted prompt bytes and report growth without dropping lawful knowledge or
  findings to make the number smaller.
- **The memory loop's refusals (Task I)** reject a changed-content reused id and an unknown veto;
  a vetoed finding survives repeated rebuilds present and unserved. The review added the missing
  causal-order refusal for a later day arriving before an earlier-day artifact.
- **`PRESENT_EMPTY` vs `MISSING`** is proved by execution: an empty first-day artifact satisfies
  the new order gate and remains distinct from a day that never wrote an artifact.

---

## ITEM TWO - THE RUN, IN ORDER

1. **Canary.** Dispatch `frankie_a_memory_rt_native_launch_20260828.yml` with `mode=canary`. Defaults
   carry everything (aliasing on, change points on, Sunday `20211003` as the only traversed object).
   It exits non-zero on any verdict but ACCEPTED, so it cannot go green over a refused calculation.
   **Task H's fix is what lets it reach checkpoint at all** - a bounded local reproduction proved the
   canary would have died there before S123.
2. **Read the canary's own artifact**, not the summary: verdict, failed gates, sections fed, and
   whether member rows carry `raw_actions` and every lifecycle row `emitted_at_recv_ns`.
3. **Complete October 1 source day only**, `mode=full`, explicitly setting `traverse_sources` to
   `glbx-mdp3-20211001.mbo.dbn.zst`, on the box over SSM; watch with
   `frankie_box_monitor_20260829.yml`. **Starting the box is a spend and it is Greg's call.** The
   ledger will be BIGGER than 10.6 GB now that raw actions are carried. This is the first of four
   sequential daily runs, not a one-day subset of one combined four-day execution.
4. **Deliver it**: re-dispatch `frankie_ledger_delivery_20260902.yml` pinned to the NEW run id, then
   `fetch_frankie_ledgers fetch` into gitignored `data/`. Delete the plain and gzipped ledgers once
   the measurements are taken and say how many bytes were freed.
5. **Measure the four falsifiers a fresh run finally makes answerable:**
   - **F-20:** `withheld_no_own_clock` and `withheld_close_occasion` read **zero** (before: 43,569
     and 65,960, 29.0% of 377,454 lifecycle rows).
   - **F-30:** the field census sees the per-record raw action fields.
   - **F-26:** no fixed-seconds block on the row; `activity_since` present on its anchors.
   - **4.16:** change points fed without a flag.
6. **The crosswalk on the new result, with receipts, gate enforced.** Sunday read **75 of 75
   applicable inputs NOT DELIVERED** before any of this. Whatever it reads now is the headline, good
   or bad. **Report it either way** - a worse number honestly measured is the point of the exercise.
7. **Freeze and promote October 1 before starting the next roster day.** Then repeat the same
   complete one-day process for October 3, October 4 and October 5, in that order.
   Keep the initial four-day non-MBO context isolation active on every one of those runs; fill those
   preserved inputs only on later source days for which reliable aligned values are available.

---

## ITEM THREE - THE MEMORY LOOP'S FIRST REAL DAY

The loop is built and has never carried a live finding. After the run:

- Confirm the findings artifact is committed and the carry fires **without a human**.
- Confirm only admitted stable ids enter after the seed, with status `NEW`, and that a day with none
  adds nothing. `NEW` records recency, not uncertainty.
- **The first link is outside the machine and was declared, not hidden:** Actions cannot make an
  uncommitted external findings artifact appear in the repository. The carry starts when that commit
  ARRIVES and the loop cannot verify that it ever does. **This is the one way the loop silently never
  fires** - so on day one, check that it fired rather than assuming it did.
- Day-one memory includes the **44 established findings**, unchanged, as `VERIFIED`. They remain in
  their historical A_CLEAN source artifact and are additionally exposed through A_MEMORY; their
  original ids, content, dates and provenance are not migrated. This one-time seed addition does
  not relax the exemplar admission path used by future daily findings.

---

## ITEM FOUR - WHAT IS GREG'S, NOT THE SESSION'S

- **The box spend** for the full roster.
- **The 4.16 horizon ladder (F-32)** - retiring it is a redesign of the response table, not a wiring
  change. Investigated and declined twice.
- **PRIOR (F-33)** - structurally unreachable until a precursor signal exists. Proposed and refuted
  **twice from the same docstring**. Do not raise it a third time.
- **F-28**, removing the retired A-clean overlay.

---

## STANDING RULES THAT BIT THIS SESSION

- **Prose expires; execute instead.** `build_a_memory_seed`'s docstring said membership was "derived,
  never typed" while line 62 hard-coded a single run id. That false invariant was copied into a task
  packet and a decision record. **The F-30 shape, and it caught the person enforcing it on everyone
  else.**
- **Redirect pytest to a file and read the exit code.** Piping to `tail` hid a failure twice.
- **Run the OTHER test trees.** A green package suite says nothing about `research/kalshi/tests` or
  `tests/`; all three were run at the close for exactly that reason.
- **A registry row built by copying its neighbour inherits its neighbour's body.** F-37 did, and a
  half-copied row reads as real later.
- **When something in a packet turns out to be wrong, say so and do not work around it.** It has now
  earned its place three times: the twelve `structurally_absent` pins, Task I's unit, and all three
  of the premises Task I was specified on.
