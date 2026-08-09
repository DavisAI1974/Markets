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

## 3. THEN A-71 — MOVE THE HEAD DATA OUT OF THE PHANTOM TREE

M-16's GUARD is built (`databento_backfill_s115.py`: repo-root absolute destinations, NG roll
defaults to `n`, asserts destination byte growth). **The already-paid data is still in the wrong
place**: `research/kalshi/data/` holds ~219MB of head trades and ~22MB of L1 that two completed
Databento jobs wrote there when `OUT_DIR` resolved against cwd.

**Move it, do not re-pull — it is paid for.** Then **verify by READING BACK** file count and span,
not by trusting the mover's exit code. This is the same posture as D47 (a store rebuilt in a session
is not a fix until it is on S3), applied one layer down.

**If the phantom tree is gone, you are still fine**: the pull logs are committed at
`research/kalshi/records/S115/databento_logs/` and carry the job ids, and **a completed Databento job
re-decodes FREE**. Head trades NG.n.0 2025-07-22..2025-11-02 = `GLBX-20260806-SEC5NWEY4U`; L1 mbp-1
NG.n.0 2026-07-31..2026-08-06 = `GLBX-20260806-FUHPD9FHH5`. **Two other ids in those logs are the
WRONG LEG** — `NEK78EWGLK` and `Y65VR393GC` are NG.v.0, which whipsaws through expiry weeks; the walk
is `.n.0`.

**A-71 blocks A-67 arm 1**, because the unwalked head is arm 1's substrate.

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

## 6. STILL OPEN, LOWER PRIORITY

- **A-61 before the next audit**: 3 of 4 "REFUTED" verdicts in an earlier audit were verified
  against a tree that moved underneath the verifier. Pin the snapshot first.
- **A-77 — the g6-g16 actual rebuild**: states exist, actuals do not, so the gradeable corpus is
  **70 days, not ~180**. A REBUILD, not a re-pull (`group_actual.build(gid)` already exists). Use
  the basis each STATE was built on and **do not silently normalize old blocks onto one continuous
  basis** (`.v.0` vs `.n.0`) — that produces a corpus that scores cleanly and measures the wrong
  contract. Blocks A-69.
- **A-78 — the g24 refine** (REST, and the demotion is deliberate). Round 1's point is MAGNITUDE:
  the blind emitted 0.29x of realized, under on 8 of 10 days. A 10/10 direction result at the same
  sizing is the failure wearing a hit-rate. Inputs survive at `records/S115/refine_g24_aborted/`.
- The live feed setup for the coach — Greg's call was to do it after the last group, and that is
  still where it sits. **Two of its pieces now have registry lines and one of them needs Greg**:
  **A-73** (live MBO is not authorized on our $179 Databento tier; the collector hot-loops on the
  entitlement error rather than failing loudly; the tier that carries it is ~$1,500/mo — buy it, or
  design the live lane onto trades + L1 and MEASURE what is lost) and **A-74**
  (collector-as-a-service: `ng_live_collector` + `ng_live_watchdog` under systemd with a heartbeat
  the andon reads).
- **A-72** — re-run the order-flow direction nowcast CAUSALLY against persistence and slope
  benchmarks before anyone grants it authority. It is the highest-agreement result the desk has
  (0.68/0.84/0.94/0.93 by strength, 34 of 34 on three unseen days) and it had zero registry lines
  until S115 close. Note both honest halves: the original audit package is gone, and it is a
  running-leg NOWCAST, not a from-flat forecast.
- **A-17A/C/D** are buildable now from free public sources (ERCOT/PJM/MISO/SPP aggregate outages,
  NRC daily unit status, EIA-860M with a retained revision history). **A-17B is a measured public-data
  gap** — no free public nationwide unit-level nuclear refuelling calendar exists, and one must never
  be inferred from aggregate ISO MW or from typical 18/24-month cycles.

