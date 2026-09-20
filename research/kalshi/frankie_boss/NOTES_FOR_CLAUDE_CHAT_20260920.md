# Notes for Claude chat (architecture): what launch day taught, and how to make the day chain one workflow we do not touch

Written 2026-09-20 ~20:10Z by the engineering session, at Greg's request, for the architect. Source of every
claim: `CLAUDE_HANDOFF_20260920.md` (receipts, run ids, timestamps). Nothing here is proposed for the run in
flight; it is for the next run.

## 1. What happened today, as causes (not as the twelve incidents)

Twelve refusals between 13:00Z and 19:55Z. Grouped by cause there are five, and the first one produced seven
of the twelve.

**A. One hash binds the science to the tooling.** `identities.code_hash` hashes every `.py` under the
package (except tests) plus the host runner. The training checkpoint digest encodes the identities, so a
one-line change in an operations script re-mints, in order: the training identity, the host and execution
identities, every cycle preparation pinned to the checkpoint, the request plan's `arm_hash`, the coordinator's
saved binding, and the export manifest's `boss_commit`. Every one of those refused today, one at a time, each
costing advance + code-bound supersede + declaration + a 13-minute re-preparation. The weights, optimizer,
sessions, source prefix and controller result were byte-identical across all four advances (measured by the
binding-diff probe). The fix built today is a receipted supersede that accepts exactly the provenance
differences; it works, and it should not be needed.

**B. Retained state refuses re-entry on provenance, not on content.** `sunday_execution._save` and
`CycleCoordinator._save` refuse any differing bytes. Right for science, wrong for a record whose only moved
field is which checkout wrote it. There is no notion of "same content, new provenance" anywhere in the retained
state.

**C. Inputs the run needs were not verified before the run.** `mapping/index.jsonl` (16 MB, pinned by
mapping.json) was never in the 20260915 package; cycle 0 found out at `bind_prefix` after 20 minutes of
preparation. Same family: the CRLF checkout on the Windows host (three refusals), the 09-17 classroom package,
the CRLF-era prefix batch and readiness pins. Each was discovered by a refusal deep in the host stage.

**D. The environment acts on the run without knowing about it.** The trunk's scheduled idle guard stopped the
host at 16:07Z while cycle 0 was preparing (CPU under the threshold during a wait). A stopped Pod loses its
GPU within minutes under low stock (measured yesterday). The Pod identity is minted in one place but the
completion workflow ref still pins the old generation.

**E. The chain is operated by hand between stages.** Today's sequence for one code change was: family
checks -> advance -> supersede -> declare -> re-dispatch, each a workflow with typed inputs, each with its own
quoting rule (`--set` refuses apostrophes, the advance wants a 40-hex sha). Per cycle: observer + readiness
delivery + dispatch, then the human HOLD, then a re-dispatch. Every hand-off is a place to get the order wrong,
and today several were.

## 2. What to change so it runs smoothly next time

Ordered by leverage.

1. **Split the identity.** `code_hash` becomes `science_hash` over a declared list (native runtime,
   training checkpoint, journal/reducer stack, controller, critic request builder, prefix builder) and
   `tooling_hash` over everything else (operations, adapters, host runner, workflows). Only `science_hash`
   enters the training identity, the checkpoint digest, the arm and the bindings. `tooling_hash` is recorded
   in every receipt for provenance and binds nothing. Then a tooling fix mid-run is an advance and nothing
   else. The list is a declaration Greg owns; it is the one design call in this file.
2. **Pin the identity at run start.** Mint the identities once into `initialization.c15.json`; an advance
   records `advanced_from`/`advanced_to` in the host identity and the receipts and re-mints nothing. The
   guard refuses only a `science_hash` change. With 1 in place this is small.
3. **Provenance fields are labels, not pins.** In every retained record, separate `content` (hashed, must
   match) from `provenance` (checkout, exporter, timestamp; recorded, compared only for reporting). `_save`
   compares content; a provenance difference is appended to the record's history. The supersede machinery
   built today then becomes unnecessary for provenance and stays for genuine content overrides.
4. **A preflight stage that proves every pinned input exists on the host.** Before `cycles`: every path the
   configuration pins (mapping, mapping index, prefixes, package, classroom package, checkpoint) is present
   with the pinned sha, the checkout is LF (`git config core.autocrlf` + a CRLF scan of the tools tree), the
   tools HEAD equals `boss_commit`, the Pod is RUNNING and its identity matches the checkout. One receipt,
   refuses before any compute. Today's C-family would all have stopped there in under a minute.
5. **The run owns its environment.** The pipeline tags `KeepRunning=true` at dispatch and clears it in the
   compute-stop stage; the idle guard also skips any instance whose tag names an open run receipt. The Pod
   policy "prepared stays RUNNING, adoption never passes through EXITED" is already codified; move it into
   the same preflight.
6. **One advance operation.** `frankie_host_advance.yml` becomes advance-with-receipts: fetch, verify
   ancestry, checkout, rewrite `boss_commit`, then (only if `science_hash` changed) run the supersede and the
   declaration itself. Inputs: the full sha and a reason read from a file, never from a quoted argument.
   Today the same thing took three workflows and two quoting refusals.
7. **Derive the test family from the tree.** The pipeline's checks job names sixteen test files by hand and
   missed the two written today; the torch runner had to be added as a separate workflow. Run everything
   under `tests/` on the checks job, and run it on push to any branch that touches the package, not only on a
   `checks_only` dispatch.
8. **Operator inputs get a schema.** `ssm_run_ps1.py --set` refuses quotes and newlines; the advance wants
   40 hex; readiness wants a request sha. Put the rules in the workflow inputs (patterns) and fail on the
   GitHub side before an SSM round trip.

## 3. Weaving it into one continuous workflow

The day chain already has the right shape: stages with git receipts, resume from the first missing receipt,
HOLD before cycles without a go. Two kinds of gap keep it from being one workflow: the per-cycle readiness
hand-off, and the human HOLD. Both can be events the pipeline waits on instead of dispatches a person makes.

**Target shape (one `day_pipeline` state machine, every transition a receipt):**

```
sources -> journal -> preflight -> host stages -> for each cycle:
    readiness (observer spawned by the pipeline, delivered by the pipeline)
    -> controller + critic on the Pod
    -> export + principal request written
    -> HOLD: wait for the recorded Frankie response          <- the only human step
    -> verify -> learning -> readback -> completion
-> completion publication -> compute stop -> KeepRunning cleared
```

- **Readiness inside the pipeline.** The cycles stage knows the request sha as soon as the request plan
  exists; the pipeline spawns the observer bound to it and delivers readiness in the same job, then the
  runner proceeds. Today that is `frankie_retained_granite.yml` + `frankie_deliver_readiness.yml` dispatched
  by hand with a request id typed in.
- **The HOLD as an event, not a re-dispatch.** The runner exits 3 with `actual_frankie_session_pending`
  and writes the request. Root's session records the response with the recorder (unchanged). The recorder
  writes a receipt into the day directory on the branch; a `workflow_run`/push trigger on that receipt
  re-dispatches the pipeline, which resumes at the first missing receipt. Nobody re-dispatches by hand, and
  the pipeline never polls.
- **The advance as a stage.** When the checkout on the host is behind the branch, the pipeline runs the
  advance operation (item 6) before the host stages, so a fix pushed to the branch reaches the host on the
  next dispatch with no separate workflow.
- **Completion publication reads the Pod identity** from `granite_retained_identity.py` at run time instead
  of a pinned generation, so a Pod migration never strands the publication (deferred item 7 today).
- **Compute stop and tag revert** are the last stage's job, with the same receipt discipline (today: manual,
  deferred item 9).

What stays manual, by design: Greg's go; Root's Frankie session; and any override of a science-hash
difference (a declared supersede with a reason), which should be rare once the identity is split.

## 4. The order to do it in

1. Split the identity (1) and the provenance/content separation (3). These remove the whole A/B family.
2. Preflight (4) and environment ownership (5). These remove the C/D family.
3. The single advance operation (6) and the input schema (8). These remove most of today's operator errors.
4. Readiness and HOLD as pipeline events (section 3). This is the "one workflow we do not touch".
5. Test family from the tree (7).

Everything above keeps the gold standard untouched (reducer stack, prefixes, packing), keeps every content
hash check, and deletes nothing.
