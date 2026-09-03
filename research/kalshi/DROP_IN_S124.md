# DROP-IN S124 - REVIEW IT, THEN RUN IT

Branch `chatgpt/frankie-raw-mbo-benchmark-20260828`. Check `git log --oneline -1`; the tip must carry
`SESSION_HANDOFF_2026-09-03_S123.md` or later. **1,997 benchmark tests; 2,706 across all three trees.**

Read `SESSION_HANDOFF_2026-09-03_S123.md` section 0, then this. Nothing else before you start.

---

## ITEM ZERO - THE WIRING IS FINISHED. TWO THINGS STAND BETWEEN HERE AND A MEASURED RESULT.

Three sessions built this. S121 wired the causal stream, crosswalk, output ledgers and clocks; S122
carried `raw_actions`, stamped the lifecycle rows, retired the fixed windows and built the seed;
**S123 finished it** - the spawn gate called, the knowledge gate wired, the knowledge block rendered,
the checkpoint token fixed, and the day-over-day memory loop built and automatic.

**Nothing has been fed by a run on the wired code. That has been true for three sessions and it is
still true.** F-31 stands, and it is now the only ESSENTIAL item that a session can close by itself.

Two things, in this order:

1. **Review Tasks A-I.** The implementer asked for it explicitly and named what must not be weakened.
   It was deliberately not started at the S123 close - reviewing nine tasks of gate and loop wiring on
   a spent budget is how a rubber stamp happens, and a rubber stamp immediately before the first real
   run is the worst possible place for one.
2. **Then the run.** D89's order (work first) is satisfied the moment the review is.

---

## ITEM ONE - THE REVIEW, AND WHERE TO AIM IT

Read `research/kalshi/CLAUDE_S123_A_I_IMPLEMENTATION_HANDOFF_20260903.md` first; it is the
implementer's own account and it is candid, including about the limits of what it could prove.

**Aim at these five, because each is a place where a green test proves less than it appears to.**

- **The gate can now REFUSE a spawn (Task A).** Confirm it refuses for the right reason on a real
  result and does not pass for a wrong one. A gate that cannot fail is worse than no gate.
- **The honest fixture (Task B)** names four layers it cannot account for without a run - the DBN
  decoding witness, S3 object identity, `PLAIN_SIZES`, `PLAIN_SHA256SUMS`. Confirm they are named
  rather than filled, and that the gate refuses when one is withheld.
- **The C/G coupling.** Before G the read gate was checked and found NOT vacuous. Re-derive that
  yourself rather than accepting it: a knowledge gate that passes over a prompt lacking its own
  subject is a false green on the gate we just wired.
- **The D60 prompt-size watch.** G grew the honest fixture prompt from 13,092 to 15,999 bytes
  (+2,907, 22.2%); that was measured before a real run, not on one. Future served findings are
  roster-bounded. Record the first run's actual emitted prompt bytes and report growth without
  dropping lawful knowledge or findings to make the number smaller.
- **The memory loop's refusals (Task I).** An id reused with changed content must be refused; a veto
  for an unknown id must be refused; a vetoed finding must survive a rebuild still present and
  unserved. **Test the rebuild-resurrection case specifically** - it is the one that quietly undoes
  the veto.
- **`PRESENT_EMPTY` vs `MISSING`.** Confirm by execution that a day which ran and found nothing is
  distinguishable from a day that never wrote an artifact. This is the S119 defect class and it is
  the reason the distinction exists.

---

## ITEM TWO - THE RUN, IN ORDER

1. **Canary.** Dispatch `frankie_a_memory_rt_native_launch_20260828.yml` with `mode=canary`. Defaults
   carry everything (aliasing on, change points on, Sunday `20211003` as the only traversed object).
   It exits non-zero on any verdict but ACCEPTED, so it cannot go green over a refused calculation.
   **Task H's fix is what lets it reach checkpoint at all** - a bounded local reproduction proved the
   canary would have died there before S123.
2. **Read the canary's own artifact**, not the summary: verdict, failed gates, sections fed, and
   whether member rows carry `raw_actions` and every lifecycle row `emitted_at_recv_ns`.
3. **Full roster, Sunday only**, `mode=full`, on the box over SSM; watch with
   `frankie_box_monitor_20260829.yml`. **Starting the box is a spend and it is Greg's call.** The
   ledger will be BIGGER than 10.6 GB now that raw actions are carried.
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

---

## ITEM THREE - THE MEMORY LOOP'S FIRST REAL DAY

The loop is built and has never carried a live finding. After the run:

- Confirm the findings artifact is committed and the carry fires **without a human**.
- Confirm only NEW stable ids enter, and that a day with none adds nothing.
- **The first link is outside the machine and was declared, not hidden:** Actions cannot make an
  uncommitted external findings artifact appear in the repository. The carry starts when that commit
  ARRIVES and the loop cannot verify that it ever does. **This is the one way the loop silently never
  fires** - so on day one, check that it fired rather than assuming it did.
- Day-one memory is **the seed alone**: the 44 historical findings are excluded by the admission path
  (run-local ids, missing exemplars) and stay the historical A_CLEAN artifact. S120's finding that
  they were never surfaced remains OPEN.

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
