# SESSION HANDOFF — S115 (2026-08-09)

**Branch: `claude/kalshi-agents-coordinator-guard-sg0n15`. Brain s105.9, 90 plays — UNCHANGED,
byte-untouched except the four ONE-DOC repairs below. No group run, no merge. 44 commits.**
Registry **164 -> 181 items**. Decisions **48 -> 51**.

Read this with `DROP_IN_S116.md`. The one-line version: **the platform got its pre-live audit, the
brain became genuinely one document, five papers became a registered build sequence, and an external
collaborator BUILT that sequence on a branch that is verified but deliberately not merged.**

---

## 0. WHAT GREG ASKED FOR, VERBATIM, BECAUSE IT SETS THE BAR

> "go through the entire platform setup, code and data point calls and make sure everything is
> working as it should and intended, fix any major gaps or flaws and make any recommendations for
> anything that we missed. Make sure you check the schema and brain to make sure it's constructed
> optimally for the agents to use and use correctly. **I want to keep it as the one doc so nothing
> gets overlooked or forgotten about.** So don't change the doc amount unless we discuss a better
> way of doing it. **We are running our last tests to start doing paper trades and I want them to be
> our final time we are doing these types of fixes. This should be live ready.**"

That is a production-readiness review, not a bug list, and the ONE DOC clause turned out to be the
load-bearing half.

---

## 1. THE SESSION'S WORST MOMENT, FIRST, BECAUSE IT IS THE LESSON

**I built a "working view" of the brain that CUT the reasoning out of it, and Greg caught it.**

The brain view for a 90-play brain runs ~420k tokens. To make it fit I withheld `legacy_notes` and
compressed `audit` prose. Measured afterwards, this is exactly what I had cut:

| field | plays affected |
|---|---|
| `audit.argument` | **82** |
| `legacy_notes.forward_evidence` | 77 |
| `legacy_notes.evidence` | 75 |
| `legacy_notes.conditions_note` | 57 |
| `legacy_notes.exemplars` | 33 |
| **`legacy_notes.falsifier`** | **17** |

Greg:

> "reasoning is exactly what we want tied to the decision! This is what we've been discussing and
> built the schema for so that their decisions could have some contest reasoning behind them. We've
> been chasing this all day and **you have intentionally made a separate doc that explains why their
> brain tells them to do something**."

He is right and the framing is the point: a view that serves the CALL and withholds the ARGUMENT
does not shrink the brain, it **splits** it — and the split half is the half S114 spent a whole
session establishing ("if you cut the view, cut CALLS before FALSIFIERS"). **Fully reverted**
(commit `90ecbce`); the selftest now asserts that nothing is withheld. The brain FILE was never
touched during any of it.

The recurrence guard that came out of it is the ONE-DOC work in section 3.

---

## 2. THE PRE-LIVE AUDIT — WHAT WAS BROKEN AND WHAT WAS FIXED

Ten audit dimensions were run against the platform. The confirmed defects, each fixed at its cause:

**D4-1 (BLOCKER) — the blind wall did not cover `meta` or the group's own name.** `brain_view`'s
window redaction walked plays but not the meta block, and matched only date forms — so `g24`/`G24`/
`grp24` passed through. Fixed; the wall now covers meta and all three name forms.

**`brain_view.build()` was not idempotent.** It handed the caller a REFERENCE to the brain's plays
and then annotated them in place. Invisible while every annotation was additive; destructive the
moment a cut popped a key — which is precisely what happened in section 1. Fixed with a deep copy.
**This is the same species as NC-3: the defect was latent until a new caller exercised the path.**

**Credentials: the paste ritual ends.** `creds.py` now resolves `MARKETS_<NAME>` first, which the
container's `proxy-injected` placeholders cannot shadow, then falls back to the plain name, then to
`~/.config/markets/env`. `aws_client()` passes the resolved pair explicitly rather than trusting
boto3's precedence chain — the trap that cost S100 an hour. Five consumers migrated onto the one
resolver; `databento_backfill.py` was the last holdout and is now on it too.

**`state_health`'s storage guard was one-directional.** It fired when `storage` ran ahead of
`storage_regional` but not the reverse, so the S114 defect's mirror image would have passed. Made
symmetric, plus a 9-day weekly-cadence bound. Its CLI is now read-only by default (`--manifest` to
write) — a read-only-looking command that wrote was the NC-4 family.

**`squeeze_watch.sessions_since_prompt_expiry` was exempt from the relive**, the same
top-level-keys-only blind spot that exempted `options_surface.days_to_opex` for the whole S114 walk.
Added to `_RELIVE_FIELDS` with its derived `unwind_watch` flag.

**The evaluability resolver could not index lists.** `_resolve` handled dotted paths but not `[N]`,
so any play whose `state_path` reached into an array read INPUT_ABSENT. Fixed.

**g24's storage lane was wrong and is now right.** 12 hard failures -> **0 hard, 13 soft
(declared)**, via `storage_restage_repair.py` — a targeted graft of the correct EIA-weekly family
onto the committed state, dry-run by default, idempotent, declaring `storage_repair_basis` per
repaired day. **A graft rather than a re-stage on purpose**: a fresh re-stage would have emptied
`storage_consensus`, `weather_forecast_cycle` and `freeze_risk`, because **D47 failed in the real
world** — 3 of S114's 5 store fixes never reached S3, so the substrate a re-stage would have read is
older than the state it would have overwritten. That is D47 measured, not restated.

**M-16 (ESSENTIAL, and the one I nearly missed): the puller writes to a phantom `data/` and lies
about where.** Two completed Databento jobs reported **2,384,994** and **1,386,421** rows and landed
nothing where anything reads. `OUT_DIR`/`L1_DIR`/`MBP10_DIR` are relative, so they resolved against
cwd and created `research/kalshi/data/` (219MB trades + 22MB L1); `_write_df(df, symbol)` takes no
`out_dir` at all; and the log printed the **requested** destination, never the actual one. **Third
occurrence of the reports-rows-writes-nothing family** (S114's missing `ng_l1` writer; this
session's `--roll v` near-miss). It was found by verifying Greg's "we have the whole year's data for
ng, we're good" instead of accepting it.

---

## 3. THE BRAIN IS NOW ACTUALLY ONE DOCUMENT (A-58, and Greg's standing rule)

> "Any function that has to do with the brain should be in the brain file" / "Let's clear this all
> up now, is there another hidden doc somewhere" / "merge the reasoning file"

**Measured: the brain pointed OUT of itself 21 times inside role-served sections, three of them to
files that DO NOT EXIST.** Four defects, all closed in `brain_onedoc_fix_s115.py`:

1. **A second doctrine file was in the agents' read list.**
   `knowledge/refinement_architecture_doctrine.md` says in its own header that it was merged into
   the brain at S103 "and kept as the human-readable source" — and RFN-1 had ordered every refine
   specialist to read it ever since. **Two copies of one doctrine, one of them served: that is the
   S105 root cause verbatim** (`blind_shared.md` said USE the MBO firehose while `blind_class_*`
   said NO MBO, and it cost a session to diagnose). The brain's copy was complete except the file's
   FLOW line; that line is now transcribed in, and the file is off RFN-1's read list.
2. **Three dead citations inside served plays** — `blind_class_{C,D,E}.md`, deleted at S105 **by
   design** (D7: no blind-specific rule file may exist). Repaired to state what happened and name
   the surviving lens, not silently dropped.
3. **Doctrine that deferred substance to an external file** — `doctrine.mbo_refinement_findings`
   ended "Integration gotchas: `G15_MBO_FIXES_FOR_CHATGPT.md`", i.e. served doctrine telling a
   specialist to go read somewhere else. Measured: that file is a 57-line S103 build list, not
   forecasting doctrine, and it is superseded. Reframed as dated provenance.
4. **Nothing stopped any of it recurring** — `brain_schema.check_cited_files()`: any `.md` named
   inside a role-served section must EXIST, or validation hard-fails. Same posture as D34's
   `_is_machine_path`.

**A bug worth carrying forward, because it nearly shipped as a success.** The first version of the
fixer branched on `where.split(".")[0] == "plays"` — but **every play id contains dots**
(`daytype.covering_giveback_self_limiting`), so the split yielded `"plays[daytype"`, the branch never
fired, and **the run reported success while doing nothing**. Caught only by re-reading the brain
after `--write`. NC-3 again, in a third costume: *a fix is not done until the fixed path is observed
to have executed.*

---

## 4. FIVE PAPERS BECAME A BUILD SEQUENCE — AND THEN SOMEONE BUILT IT

Greg brought five arXiv papers and framed the target himself:

> "Our agent is going to look like Frankenstein hah. But if we can take the pieces we want and stack
> one family from different approaches for him on top of weaving different families together, we'll
> end up with a monstrously great agent."

| paper | what we took |
|---|---|
| NOOA — 2607.20709 | agent-as-render-target, typed contracts, explicit agent object |
| ACM long-horizon — 2607.23809 | context management (fuller read: likely needs fine-tuning we do not have — recorded, not hidden) |
| ACM lifecycle — 2607.21503 | five primitives; **validated compaction** |
| Kernel Forge — 2607.24762 | MCTS over multiple candidates (the CUDA half is out of scope, closed) |
| Self-Improvement survey — 2607.13104 | update-target x driving-signal taxonomy, and its curated index |

Registered as **A-59 .. A-69**, plus `research/kalshi/FRANKIE_BUILD_BRIEF_S115.md` — the
dependency-ordered sequence, **a falsifier as the acceptance test for every item**, the ownership
table, and the desk constraints (D8, D4/D37, D3, D31, NC-3, D22, gold vault, "a pull that reports
rows is not a pull that landed data").

### Greg's two corrections, which changed the design and not just the wording

**"Don't look at things as downgrade or less than. They might improve the same thing but if they
attack different angles then they are FORCE MULTIPLIERS."** This is his own S36 standing rule
(*tools are COMPLEMENTARY — evaluate by STACKING, never head-to-head*) and I had drifted off it into
ranking language. A-59/A-64/A-66 rewritten.

**"Or you can write the contract that says they own DIFFERENT PARTS of the same job and they
complement each other."** My A-66 draft had a "which signal wins" arbitration clause — head-to-head
reasoning smuggled back in. The root cause was that my taxonomy was too coarse: **"memory" is three
layers** — content store / derived index / serving policy — and once you split it, the collision
disappears and no arbitration is needed. **Split the part more finely before inventing a protocol.**

### The architecture test (A-67), as Greg specified it

> "I say we build it before the group run and run two different refine runs on that data. Refine vs
> Frankenstein" -> "**Better yet, Blind vs Frankenstein**" -> "That will be closer to real world
> conditions."

Then, on retention: *"Is a 10 day run long enough for frankie to show how he retains context
better?"* — no, and the reason is architectural, so **arm 2 is a separate three-block test**. And on
self-training: *"He only sees the curve after to score himself and to make improvements... We don't
tune or fix him, he does that himself"* -> A-69.

### Two things I got wrong here and corrected in the record

- **I recommended A-59 from ABSTRACTS.** Greg: *"Did you read it"*. Corrected with declared
  provenance, and the full-PDF read materially narrowed the recommendation.
- **I asserted the corpus size from narrative** — "18 blocks, ~180 days". **Measured: 70 gradeable
  days.** Only g18-g24 carry both a state and an actual; g6-g16 have states with no rebuilt actuals.
  So A-69's training corpus is a REBUILD job, not a re-pull.

---

## 5. THE EXTERNAL BUILD: FRANKIE EXISTS, IS VERIFIED, AND IS NOT MERGED

ChatGPT built the brief on **`chatgpt/agent-frankie-s117` @ `48e50b9` (PR #8)**, against blob
`6cddd0c` of `FRANKIE_BUILD_BRIEF_S115.md`. **49 files, ~7,954 insertions.**

- entry point: `research/kalshi/agent_frankie.py`
- conformance record: `research/kalshi/FRANKIE_S115_IMPLEMENTATION.md`
- handoff: `CHATGPT_HANDOFF_S117_AGENT_FRANKIE.md`
- architecture: `research/kalshi/FRANKIE_ARCHITECTURE_S117.md`

**What I verified here rather than took on description** (all of it re-runnable):

- `git merge --no-commit --no-ff` -> "Automatic merge went well", **0 conflicted paths** (aborted).
- From a detached worktree at `48e50b9`: `python agent_frankie.py health` reports **spawn.py's git
  blob observed == expected** (`2eb3ab8…`) and the paper manifest **READY at 9 papers**.
- `python agent_frankie.py selftest` -> **11/11 PASS**, including *"Frankie can never enable
  execution"*, *"self-improvement cannot apply itself"*, *"self-improvement cannot touch spawn.py"*.
- `frankie_s115_status.py` reports A-59/A-61/A-62/A-65/A-66/A-67/A-68/A-69 contracts present and
  **A-63/A-60 explicitly `DEFERRED_BY_S115_UNTIL_A-5_LIBRARY_INDEX`** — it did not quietly pull the
  fitted-sigma shortcut forward when doing so would have been easy and would have looked like
  progress.

**The single best thing in that build is not code: `FRANKIE_S115_IMPLEMENTATION.md` splits its own
report into "Built" and "Not claimed as passed"**, and lists six items as harness-present /
evidence-absent — the M-16 physical repair, the g6-g16 actual rebuild, A-67 arm 1, A-69, A-67 arm 2,
A-42's first production run. **That is promoted to D51 and is now binding on us**: a registry item
whose CODE landed does not move to DONE, because the measurement is the whole point of the item.
Same defect, same door as S114's "a live status on dead evidence".

**Why it is NOT merged, and it has nothing to do with Frankie.** The branch is based on
`chatgpt/novel-edge-lab-s116`, so the merge commit also lands ~1,500 lines of dashboard /
novel-edge-lab code, two new CI workflows and two S116 handoff docs that nobody on this side has
read. **Verified is not reviewed, and a merge commit signs for the whole diff.** That review is
**A-70 (ESSENTIAL)** and is S116's item zero. Expected to be a 20-minute read; it is ESSENTIAL for
what it guards, not for what it is expected to find.

---

## 6. LEDGER

**D49** — D40-D44 were never assigned; the numbering gap is recorded so it is not read as loss.
**D50** — D13's `enforced_by` claimed a QC sweep that does not exist. The gas-only scope decision is
unchanged and still binding; what changed is the honesty of its enforcement claim.
**D51** — a gate that exists is not a gate that passed, and an external build is verified before it
is merged, with the verification named.
**D52** — nothing authored may live only on a session scratchpad (Greg, at close: *"whatever is on
scratchpad needs to be committed to a file in git so we don't lose whatever is on it... and we're not
supposed to be using scratchpad anymore"*). D33/D34 restated where they kept failing. **~15MB was
sitting outside the repo when this handoff was being written.** Rescued into
`research/kalshi/records/S115/`, each copy **verified by sha256 against the source rather than by the
copy command's exit code**: the four Databento pull logs (the primary evidence for M-16, and the
carrier of the job ids `GLBX-20260806-SEC5NWEY4U` / `-FUHPD9FHH5` that make A-71's "do not re-pull"
recoverable, since a completed job re-decodes free), the aborted g24 refine's directive + rendered
prompt + three pre-influence records, and the three one-off scripts whose effects are committed but
whose provenance a store diff does not show. **Everything deliberately dropped is listed in that
directory's README with the command that regenerates it** — a silent drop reads as "we saved
everything". SOP **v1.19** puts the sweep in STEP 7, before the drop-in box is written. It is a
checklist line and not a gate, and the reason is stated rather than hidden: the scratchpad gate can
catch a handoff that NAMES a temp path, but nothing inside the repo can observe work that merely SAT
on one.

---

## 7. STATE AT CLOSE

- **Andon: 1 FAIL** — `station0/briefings`, 8 of 12 unaudited (it got WORSE on purpose: the glob was
  widened this session, so it now sees briefings it previously missed). Every other station PASS.
  `git` clean, `gold` intact, `state_health` g24 **0 hard**, `keys` resolvable, `store` all four
  renders match.
- **Line: g24 staged -> blind-scored -> archived [ACTIVE].** The **g24 refine has still not run** —
  it was started and stopped at 2 of 10 posteriors, both discarded as degraded-view artifacts from
  the section-1 cut. It is now housekeeping, not the frontier: **A-67 arm 1 is a BLIND run on the
  unwalked head, which is a better test than a refine of a contaminated block.**
- **Registry 181 items** (21 ESSENTIAL). A-70 and A-71 are new; A-59/A-61/A-62/A-65/A-66/A-67/A-68/
  A-69/A-42/A-50/A-64/M-16 each carry an `external_build` note naming branch, commit and the exact
  symbol that implements them — and every one of them **stays OPEN**.
- **Brain s105.9, 90 plays, CALLS unchanged.** One D8 proposal is PENDING Greg
  (`emission_ceiling_check` -> DEGENERATE + re-site).
- **Data plane restored and verified** (478 files; STS account tail 4170; SSM retrieval proven
  cold). **But the head trades and the L1 gap are in the phantom tree** — that is A-71, and it
  blocks staging the unwalked head, which is A-67 arm 1's substrate.

---

## 8. THE SHORTEST HONEST SUMMARY

The platform is materially more live-ready than it was: the blind wall covers what it claimed to,
credentials cannot be shadowed, the storage guard is symmetric, two relive exemptions are closed,
g24 is clean, and the brain is one document with a gate that keeps it one. **Three things are not
done**: the head data is in the wrong directory (A-71), an unread branch stands between us and the
architecture test (A-70), and **every single Frankie item is a harness with no measurement behind it
yet (D51)** — which is exactly the state the record should show, because the measurements are the
next session's work.
