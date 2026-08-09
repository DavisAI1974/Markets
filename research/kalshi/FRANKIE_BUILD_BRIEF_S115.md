# FRANKIE BUILD BRIEF — S115

**For the external collaborator building Frankie. Generated from the S115 registry (A-59..A-69,
M-16) so it cannot drift from it: the REGISTRY IS TRUTH, this file is a render of it. Where they
disagree, `research/kalshi/OPEN_ITEMS.json` wins.**

Your gap analysis was accurate. Three things you could not have known are below, and they reorder
the work. Then the sequence, the acceptance tests, and the constraints that decide whether a build
is valid on this desk at all.

---

## 1. THREE CORRECTIONS TO THE PLAN AS YOU HAVE IT

### 1.1 M-16 BLOCKS A-67's SUBSTRATE — the data plane for the held-out head is EMPTY

Registered at the end of S115, after your file was written. Two NG pulls completed at Databento and
**landed nothing where anything reads**:

```
head trades 2025-07-22..2025-11-02  logged "2,384,994 rows -> data/nymex_cont_n0"
L1 gap      2026-07-31..2026-08-06  logged "1,386,421 rows -> data/nymex_mbp10"
```

Afterwards `/home/user/Markets/data/nymex_cont_n0` was UNCHANGED at 223 files still starting
`20251102`, and `data/nymex_mbp10` did not exist. Three bugs:

1. `OUT_DIR` / `MBP10_DIR` / `L1_DIR` in `databento_backfill.py` are **relative strings**. Run from
   `research/kalshi/` (which is where the SOP says to run everything) they resolve to
   `research/kalshi/data/...`. A **phantom second data tree** now holds 219 MB of trades and 22 MB
   of L1 while the real plane got nothing.
2. `_write_df(df, symbol)` takes **no `out_dir`**, though both sibling writers do — so `--out-dir`
   is silently ignored on the most common schema.
3. The log prints `{total} rows -> {flush_dir or out_dir or MBP10_DIR}` — the **requested**
   destination, never the writer's actual one. That is what made (1) and (2) invisible.

**Consequence for you:** do not plan A-67 as if the head block is stageable. It is not, until M-16
is fixed and the data is moved or re-decoded (Databento re-serves the jobs FREE for 30 days; nothing
needs re-buying). **Fix M-16 first or the architecture test has no substrate.**

### 1.2 A-69's TRAINING CORPUS IS 70 DAYS, NOT ~180 — and the gap is a rebuild

I originally wrote "18 walked blocks, ~180 scored days" from CLAUDE.md's narrative. Measured against
the files:

| blocks | state | actual | usable for self-training? |
|---|---|---|---|
| g18–g24 | yes | yes | **YES — 7 blocks, 70 days** |
| g17 | **no** | yes | no — cannot forecast from it |
| g6–g16 | yes | **no** | no — can forecast, **cannot grade** |

**The actual is not optional.** Greg's discipline is explicit: *"He only sees the curve AFTER, to
score himself and to make improvements."* A block with no actual gives the agent nothing to grade
against — it forecasts into silence and the loop does not close. Those blocks are unlabelled data,
not training substrate.

**The gap is a REBUILD, not a re-pull:** day ranges recover from the state files themselves (each
state is keyed by its own days), `group_actual.build(gid)` already exists and is what `stage_group`
calls, and the tape covers it — `nymex_cont_n0` spans `2025-11-02..2026-07-20`, containing all of
g10–g16. Corpus roughly **doubles to ~140 days at no Databento cost.**

**Do it before the loop starts.** 70 days across four lenses is E≈21, C≈21, D≈14, B≈14 — thin before
any day-class split, and D4/D37 forbids pooling classes to manufacture an n.

**Caveat that must travel with it:** g6–g16 predate S105 and some ran on the `NG.v.0` basis rather
than `NG.n.0` (S97: v.0 whipsaws between contracts through expiry weeks, which forced a g11 re-pull).
Rebuild each actual on the basis its STATE was built on, and record which. A corpus silently mixing
bases is S108 hole #8 arriving through the training door.

### 1.3 A-63 IS DELIBERATELY DEFERRED FROM THE FIRST A/B — not forgotten

You list it as a gap; it is, but it is **scoped OUT of A-67 arm 1 on purpose**: it depends on **A-5**
(the library index — seasonal window, regime label, day class, shape descriptor), which does not
exist. Building a retrieval kernel with nothing to retrieve from is not a smaller version of the
job, it is a different job.

**But note what you would otherwise miss: A-63 and A-60 are ONE BUILD.** D32 already says it —
*"one analog for the central path, the cohort that PASSED the match test but was not chosen for the
band — nothing averaged."* **The band is the empirical spread of the matched cohort**, not a
quantity to fit. So "score the band" and "build the kernel" are the same work seen from two sides,
and the fitted-sigma route is already refuted: S114 struck `weekend_gap_wide_band_emission`'s
0.5–1.0x sigma band because it held on **1 of its own 4 instances**, while the observation beneath
it survived (D37). Sequence them together or neither is honest.

---

## 2. BUILD SEQUENCE, WITH DEPENDENCIES

```
0.  M-16   fix the puller + move/re-decode          BLOCKS everything that needs the head
    A-61   pin the verification snapshot            do first, it is an hour, protects every audit
    A-50   confirm the leak gate is on every run    CLAUDE.md is auto-loaded before any agent reads

1.  A-66   the OWNERSHIP TABLE                      before any of A-59/62/64/65 — it is what stops
                                                    them colliding

2.  A-59   NOOA render target + typed contract      the core structural claim
    A-68   the lens's book (retention)              PREREQUISITE for A-67 arm 2
    A-62   specialist track records                 needs A-65's test to prove it helped

3.  A-65   validated compaction / view regression   the test every later view change ships under

4.  A-67   arm 1: BLIND vs FRANKENSTEIN on the head harness + emission. Needs 0 and 2.
    A-69   self-training on the walked corpus       needs A-68 + the actual rebuild (1.2)

5.  A-67   arm 2: retention, three sequential blocks needs A-68 in place and arm 1 done first
    A-42   first FJ-1 run                           the grader for A-69, built and never executed

LATER (own cycle, not before paper):
    A-5    the library index
    A-63   the retrieval kernel  ──┐ one build
    A-60   band calibration       ──┘
```

**Why A-66 is first among the builds:** the first pass over the components found **three writing to
"memory"** (A-62 priors, A-65 compaction, D8 merge). That looked like a collision and is not —
"memory" was too coarse a word. The resolution is Greg's, and it is ownership, not arbitration:

| owner | owns | writes |
|---|---|---|
| **D8 merge** | play CONTENT — claims, calls, falsifiers, instances | the store, adjudicated |
| **A-62 priors** | the agent's TRACK RECORD | a generated index, never authored |
| **A-65 compaction** | SERVING POLICY — what reaches the reader | nothing in memory at all |

Store / derived index / serving policy — the three-layer split **already exists** here
(`ng_brain.json` / `instrument_priors` / `brain_view`). Two components may share a LAYER freely; they
may not own the same PART. On a genuine overlap, **split the part more finely first** (that is what
the `owner_map` does for days); a coordination protocol only if that fails, and record it, because
it would be the first.

---

## 3. ACCEPTANCE TESTS — the thing you said you were missing

Every one of these is a *falsifier*, not a target. On this desk a build that cannot fail its own
test is not finished.

**A-59 (render target + typed contract)**
- The prototype must reproduce the CURRENT emitted BLD-1/RFN-1 prompt **byte-for-byte from the
  store** — the same proof `store.py check` demands of every render today. If it cannot, the render
  abstraction does not hold and only the typed-contract slice survives.
- A malformed or under-specified posterior must fail **at write time**, not at the coordinator.

**A-68 (the lens's book)**
- **Append-only and causal**: each entry written at its own decision point, readable only by
  **strictly later** days. Negative-test it — an entry from a later day must be *absent*, not merely
  discouraged. Same shape as `build_causal_slices`.
- If journal-carrying days show no improvement over non-carrying days *for the same lens*, per event,
  within-run retention buys nothing at a one-session horizon — keep the object-state machinery for
  its CONTRACT value only and say so.

**A-62 (specialist priors)**
- Generated from posteriors + actuals, **never authored** (so it cannot drift, like
  `instrument_priors`).
- If a run under it shows no change in the named failure mode AND no drop in emission on that lane,
  it is inert — cut it rather than keep it for tidiness.
- **Design risk to build against:** a track record can suppress as easily as inform. Serve the
  MECHANISM of past failure and what corrected it, not the score alone — otherwise it is the
  emission ceiling (A-40) arriving through a new door.

**A-65 (validated compaction)**
- Same specialist, same day, twice — full view vs changed view — **diff the posterior**. If
  direction, magnitude, or the fired/stood-down set moves, the change took something load-bearing.
- Per-cell, never pooled: a view validated on a quiet Tuesday is **not** validated on an EIA Thursday.
- If posterior-diffing shows no change for a compaction you independently believe is lossy, the test
  is insensitive — fix the test before trusting anything it blesses.

**A-67 arm 1 (blind vs Frankenstein)**
- Both arms **blind**, same staged state, separate namespaces, never canonical filenames (NC-4).
- **Metric fixed BEFORE the run**, per event, never pooled: `sum|err|` vs the three named benchmarks
  (`zero_change`, `seasonal_naive`, `persistence` — A-1); **emission ratio** `mean|guess|/mean|actual|`
  (the standing disease is 0.29x, trending 0.55 → 0.68 → 0.29); band coverage; stand-down honesty;
  derived-vs-fitted read from the reasoning.
- **Hazard:** neither arm's outcome may reach CLAUDE.md, a handoff, or any narrative until BOTH have
  run. Writing one up contaminates the block for the other (A-50).
- If the hybrid does not move those per-event, the harness is not the constraint — ship it on
  maintainability grounds only, stated plainly, not dressed as a performance win.

**A-69 (self-training)**
- Train with the **blind wall UP**, or he learns to RECALL rather than reason. Walked outcomes sit in
  CLAUDE.md (A-50), in 624+ dated brain instances, and in the handoffs.
- **Report the corpus number and the held-out number TOGETHER.** A corpus gain quoted alone is
  exactly what this refuses. If performance improves on the walked corpus but NOT on the held-out
  head, the loop taught recall — scrap it rather than tune it.
- Grade with **FJ-1**, not free-form self-assessment: `failure_localization.py` carries a frozen
  taxonomy (41 modes + 2 declared local extensions) and a `validate()` that REFUSES any off-table
  (edge, mode, fault_side) triple. Free-form self-grading rationalises; a frozen table with a
  validator does not let an agent invent a flattering category. Its root-cause rule labels the
  **earliest unrecovered** failure, not the loudest — which is what stops the grader blaming the last
  thing that broke.

---

## 4. CONSTRAINTS THAT DECIDE WHETHER A BUILD IS VALID HERE

These are not style preferences. Each was paid for.

- **D8 — never a direct edit of the brain.** Proposal → adjudication → merge, incumbents
  byte-identical, backup first. **Adapt fast at PROPOSING, stay slow at COMMITTING**: the lens's book
  may update daily; the brain may not. A five-day drawdown must never rewrite doctrine.
- **D4 / D37 — never average above and below.** Report per-day, `sum|err|`, drift AND survival
  together. **An R², a correlation and a fitted slope are all averages** — that is the form the rule
  keeps being broken in. Use `per_event.report()`; it deliberately returns no scalar.
- **D3 — causality is physics, not a mask.** Per-day causal slices; the future must be ABSENT, not
  discouraged.
- **D31 — nothing declared dead is actually dead.** A refutation is SCOPED to the cell and instrument
  it was measured on. Do not convert a scoped non-fit into a verdict.
- **NC-3 — a test that never produced the guard's OUTPUT did not test the guard.** Asserting a return
  value or a chosen branch is not enough; the reporting statement is part of the path.
- **An absence must announce itself.** Holes #7 and #8 were silent absences that read downstream
  exactly like a deliberate mask. Any ACM-style offload must be **declared and retrievable by name**.
- **D22 — the ledger is not a second brain.** General lessons reach the blind only through the
  adjudicated brain. A-68 threads this: a book entry is **this lens's record of its own days**, never
  a general lesson. If an entry starts reading like doctrine, it belongs in a merge proposal.
- **The gold vault.** `agents/mbo_refine_shared.md` + the five lens files are frozen 0444 under a
  sha256 manifest; `verify_gold` hard-fails a run on drift. That freeze is what PROVES blind and
  refine ran the identical engine (D7). Under A-59 it is preserved by **hashing the render** — it is
  re-aimed, not discarded.
- **A pull that reports rows is not a pull that landed data** (M-16, and S114 before it). After any
  pull, ASSERT the expected files exist on disk and hard-fail if not.

---

## 5. WHAT THE SCAFFOLD ALREADY TELLS AN AGENT — extend it, never replace it

The refinement doctrine's load-bearing line is that the blind **stays** the core predictor and MBO is
a posterior update, *"not a replacement predictor."* Greg applies the same rule one level up: Frankie
**extends** the machine, he does not succeed it.

| already served to every specialist | what Frankie adds |
|---|---|
| the **mission brief** — why you exist | the **toolbox catalogue** — what you may call |
| **`reasoning_method.decision_order`** — how to decide | **the lens's book** — what you are carrying |
| the **output contract** — what to produce | **your track record** — how you have been wrong |
| the **field inventory** — what you were served | the **grading duty** — score yourself after |

**Additive in what is AVAILABLE, selective in what is CONSULTED.** The working view reached ~431k
tokens because things were added and nothing was removed; the S115 answer to that was NOT to cut
content (that attempt lost `audit.argument` on all 82 plays and falsifiers on 17, and was reverted) —
it was `play_index` over 90 whole plays, so the agent **holds everything and chooses what to read**.
Never shrink the toolbox to make the choosing easier.
