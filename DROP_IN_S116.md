# DROP-IN BOX — S116

Paste this into a FRESH session. It is the whole starting state.

---

## 0. FIRST COMMANDS — do not skip, the harness cuts sessions from stale tips

```bash
git fetch origin claude/kalshi-agents-coordinator-guard-sg0n15
git checkout -B claude/kalshi-agents-coordinator-guard-sg0n15 origin/claude/kalshi-agents-coordinator-guard-sg0n15
git log --oneline -1        # must be the S115 close-out (andon ALL CLEAR)
```

**Branch = `claude/kalshi-agents-coordinator-guard-sg0n15`.** Develop and push here.

Then read, in this order:
1. `SESSION_HANDOFF_2026-08-09_S115.md`
2. this box
3. `research/kalshi/FORECAST_ARCHITECTURE_S111.md` (the product is a CURVE; the walk is a LIBRARY
   BUILD)
4. `research/kalshi/FRANKIE_BUILD_BRIEF_S115.md` (what Frankie was supposed to be)

Then, from `research/kalshi`:

```bash
python plant_status.py         # the andon board - expect ALL CLEAR
python state_health.py         # g24: 0 hard, 13 soft (declared)
python store.py check          # four renders must match their stores
```

**Credentials no longer need pasting.** `creds.py` resolves `MARKETS_AWS_ACCESS_KEY_ID` /
`MARKETS_AWS_SECRET_ACCESS_KEY` from the environment first — a namespace the container's
`proxy-injected` placeholders cannot shadow — then Databento and EIA follow from SSM. If the andon's
`keys` line is PASS, you are done. The SessionStart hook restores the data plane automatically.

---

## 1. STATE AT S115 CLOSE

- **Brain s105.9, 90 plays, CALLS unchanged.** One D8 proposal PENDING Greg
  (`emission_ceiling_check` -> DEGENERATE + re-site).
- **Registry 192 items, 25 ESSENTIAL. Decisions 52.**
- **Line: g24 staged -> blind-scored -> archived [ACTIVE].** g24 blind was **6/10, sum|err| 4,890,
  0.98x zero_change** — we tied doing nothing. The dominant problem is still **under-emission at
  0.29x of realized magnitude**.
- **The g24 refine has NOT run** (A-78, REST). Housekeeping, not the frontier — see item 4.
- **Andon: ALL CLEAR** (first time). The briefing backlog was discharged with real dispositions -
  all 13 audited - and it produced four registry gaps, two of them live-trading: **A-73** (live MBO
  is not authorized on our $179 Databento tier and the collector hot-loops on the error; ~$1,500/mo
  for the tier - a decision for Greg, not a build) and **A-74** (collector-as-a-service, never
  built, never tracked). Also **A-72** (the order-flow direction nowcast had zero registry lines)
  and **A-17 split into A-17A/B/C/D** on the nuclear report's own instruction.

---

## 2. ITEM ZERO — A-70: REVIEW AND MERGE THE FRANKIE BRANCH

**`chatgpt/agent-frankie-s117` @ `48e50b9` (PR #8). 49 files, ~7,954 insertions.**
Entry point `research/kalshi/agent_frankie.py`. Conformance record
`research/kalshi/FRANKIE_S115_IMPLEMENTATION.md`. Handoff `CHATGPT_HANDOFF_S117_AGENT_FRANKIE.md`.

**Already verified at S115 close — do not redo, but do re-confirm after merging:**

- `git merge --no-commit --no-ff origin/chatgpt/agent-frankie-s117` -> "Automatic merge went well",
  **0 conflicted paths**.
- From a worktree at `48e50b9`: `python agent_frankie.py health` reports spawn.py's git blob
  **observed == expected**; `selftest` **11/11 PASS**, including "Frankie can never enable
  execution" and "self-improvement cannot touch spawn.py".
- `frankie_s115_status.py` shows A-59/A-61/A-62/A-65/A-66/A-67/A-68/A-69 contracts present and
  **A-63/A-60 explicitly deferred until A-5** — it did not pull the fitted-sigma shortcut forward.

**What is NOT verified, and is the whole reason the merge waited:** the branch is based on
`chatgpt/novel-edge-lab-s116`, so the merge commit also lands ~1,500 lines of dashboard /
novel-edge-lab code, two new CI workflows and two S116 handoff docs that nobody on this side has
read. **Verified is not reviewed. A merge commit signs for the whole diff.**

Do this:

1. Read `CHATGPT_HANDOFF_S116_NOVEL_EDGE_LAB.md` + its addendum, then `dashboard/adapters/novel.py`
   and the `dashboard/server.py` diff. **One narrow question**: does anything there READ a store or
   WRITE a path the forecaster depends on, and does `dashboard/novel_candidates.json` claim evidence
   it did not measure.
2. Audit `.github/workflows/agent_frankie_ci.yml` and `novel_edge_lab_ci.yml` for anything that
   pushes, promotes or mutates git.
3. Merge. Then re-run `verify_gold.py`, `plant_status.py`, `state_health.py`, `store.py check` and
   `agent_frankie.py selftest` **on the merged tree**, not on the branch.
4. Register the new Frankie files in `store/documents.json` and run `store.py docs --write`.

Expect this to be a short read. It is ESSENTIAL for what it guards, not for what it will find.

---

## 3. A-71 IS DONE — THE HEAD DATA IS ON S3

Closed at S115 close, and **the location M-16 originally named was wrong**, so read this rather than
the old text. The head trades were never in a phantom `data/nymex_cont_n0` (that directory was
created EMPTY). They were in **`research/kalshi/data/pyth_ticks/`** — phantom root *and* wrong store
— because `OUT_DIR = "data/pyth_ticks"` is the trades writer's hardcoded default and `_write_df`
takes no `out_dir`, so **`--out-dir` is accepted and ignored.** That second half is the worse one and
it is still unfixed on trunk: check it in `databento_backfill_s115.py` when A-70 lands.

Verified before moving: **2,384,994 rows on disk == 2,384,994 reported**, zero missing weekdays,
clean seam. Landed and **read back from S3**, not trusted from an exit code.

```
s3://bento-568968024170-us-east-2-an/nymex/nymex_cont_n0/   311 files  NG_20250722 .. NG_20260720
s3://bento-568968024170-us-east-2-an/nymex/ng_l1/           326 files  NG_20250722 .. NG_20260805
```

**The unwalked head (2025-07-22 -> 2025-09-05) now has both trades and L1.** Nothing was re-pulled.
The four Databento jobs stay re-decodable free until **2026-09-05** if anything is ever lost:
`GLBX-20260806-SEC5NWEY4U` (head trades) and `-FUHPD9FHH5` (L1) are the right leg; `-NEK78EWGLK` and
`-Y65VR393GC` are NG.v.0 and must never be mixed in.

---

## 4. THEN THE FRONTIER — A-67 ARM 1: BLIND vs FRANKENSTEIN

Greg's own framing: *"Better yet, Blind vs Frankenstein"* / *"That will be closer to real world
conditions."*

- **Substrate: the unwalked head, 2025-07-22 -> 2025-09-05.** It is the only clean block left — g24
  is contaminated and cannot host a blind re-run. Leak-audited at S115: **0 leaks**.
- Both arms blind, same staged and pinned substrate, separate non-canonical namespaces, **metrics
  fixed in the seal before either arm runs** (`frankie_validation_s115.py`).
- Per-event outputs only: absolute error, the three benchmarks (zero-change, seasonal-naive,
  persistence), emission ratio, band coverage, stand-down honesty, derived-vs-fitted provenance.
  **No pooled above/below scalar** (D4/D37).
- Arm 2 (retention across three sequential blocks) is a SEPARATE test. Ten days cannot measure
  retention and the reason is architectural, not statistical.

The g24 refine (**A-78**) can be run any time after this. **Do not let it displace arm 1** — a blind
run on clean substrate is a better test than a refine of a block read forwards and backwards all
session. When it does run, its point is MAGNITUDE: a 10/10 direction result at the same 0.29x
emission is the failure wearing a hit-rate.

---

## 5. THE STANDING RULES THAT BIT THIS SESSION — carry them

- **D51 (new): a gate that exists is not a gate that passed.** Every Frankie registry item stays
  OPEN. The harness is built; the measurement is not made. Six items are named as harness-present /
  evidence-absent in `FRANKIE_S115_IMPLEMENTATION.md` — treat that list as the work, not the
  changelog.
- **D51 second half: an external build is verified before it is merged, and the verification is
  NAMED**, not asserted.
- **Reasoning is tied to the decision.** A brain view that serves the CALL and withholds the
  ARGUMENT does not shrink the brain, it splits it. The S115 cut removed `audit.argument` on all 82
  plays and 17 falsifiers before it was caught and reverted. **Do not re-attempt a "working view"
  that drops fields.** If the view is too large, that is a genuine problem — bring it to Greg, do not
  solve it by cutting.
- **A fix is not done until the fixed path is observed to have EXECUTED** (NC-3, third occurrence
  this session: the ONE-DOC fixer branched on a string split that never matched, and reported
  success while doing nothing).
- **A pull that reports rows is not a pull that landed data** (M-16, third occurrence of that
  family). Read back the destination.
- **Force multipliers, not rankings** (Greg, S115 restating his S36 rule): pieces that attack
  different angles stack; evaluate by STACKING, never head-to-head.
- **Split the part more finely before inventing an arbitration protocol** (Greg, S115). "Memory" is
  three layers: content store, derived index, serving policy.
- **Open things go to the registry, never to handoff prose (Greg, S115; D30).** The S115 sweep found
  two carried in narrative for two sessions and registered them as A-77 and A-78. If it is open and
  it is not an item, it does not exist.
- **D52 (new): nothing authored may live only on a session scratchpad.** The harness offers one and
  will keep offering one; that is not permission (D33/D34 — there is nothing local). Work files go
  under the repo. **Sweep the temp directory BEFORE writing the drop-in box** (SOP v1.19, STEP 7),
  copy anything authored or evidential into `research/kalshi/records/S<n>/`, verify by reading the
  committed copy back, and LIST what you dropped with the command that regenerates it. Worked
  example: `research/kalshi/records/S115/README.md`.
- **KEYS DO NOT ROTATE DURING THE WALK** (Greg, S107, standing).

---

## 6. EVERYTHING ELSE OPEN

**Read `OPEN_ITEMS.md`.** It is the render of `research/kalshi/OPEN_ITEMS.json`, 192 items, tiered,
and it is the ONLY place open work lives (Greg, S115: *"Open things go to the open items md"*; D30).
This box does not restate it - a second list is a second thing to keep in sync, and the one that
goes stale is always the copy.

```bash
python research/kalshi/registry_grep.py <regex>          # every text field, not just the title
python research/kalshi/registry_grep.py . --tier ESSENTIAL --status OPEN
python research/kalshi/registry_grep.py <regex> --full
```

Sections 2-4 above name what is SEQUENCED - A-70, then A-67 arm 1 (A-71 is done) -
because ordering is instruction and does not live in the registry. Everything else is in the render.
