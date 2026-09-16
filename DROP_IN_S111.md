# DROP-IN BOX - S111 (start a FRESH session with this)

## BOX 1 - BRANCH. PASTE THIS ALONE, FIRST, AND READ THE VERDICT BEFORE CONTINUING.

```bash
B=claude/kalshi-agents-coordinator-guard-1175nr
git fetch origin $B && git checkout -B $B origin/$B
echo "--------------------------------------------------------------"
echo "branch : $(git rev-parse --abbrev-ref HEAD)"
echo "tip    : $(git log --oneline -1)"
echo "tree   : $(git ls-files | wc -l) files tracked"
echo "expect : S110 close-out (or later)"
test -f research/kalshi/agents/RUN_SOP.md \
  && test -f DECISIONS.md \
  && test -f SESSION_HANDOFF_2026-08-02_S110.md \
  && test "$(git rev-parse --abbrev-ref HEAD)" = "$B" \
  && echo "BRANCH OK - safe to paste BOX 2" \
  || echo "BRANCH FAILED - do NOT continue. Re-run this box; if it fails again, say so."
```

Why separate: the harness assigns every session its own auto-named branch and that branch is NEVER
the work. Two traps. STALE-TIP: the session is cut from an old tip and looks fine. EMPTY-CHECKOUT: the
assigned branch does not exist on the remote, so the container comes up on an orphan `master` with an
EMPTY TREE and every file read fails. The three sentinel files were created in S110, so their presence
rules out both at once. This box deliberately touches no credentials, so a branch failure can never be
confused with a creds failure.

---

## BOX 2 - THE SESSION. PASTE AFTER BOX 1 SAYS BRANCH OK.

```
0. READ ORDER: SESSION_HANDOFF_2026-08-02_S110.md (full) -> research/kalshi/agents/RUN_SOP.md
   (THE SPEC BOOK - binding, follow it to the letter) -> DECISIONS.md (D23-D27 are Greg's open calls)
   -> research/kalshi/G23_REFINE_LEDGER_S110.md -> CLAUDE.md header.

1. EMPTY TO READY:
   pip install --quiet numpy pandas matplotlib boto3 databento
   python research/kalshi/verify_gold.py          # MUST print PASS + runtime==gold
   python research/kalshi/plant_status.py         # the andon board: expect ALL CLEAR
   Keys and data/ do NOT survive a session - expected, not a bug. A group staged at S108+ runs
   both rounds with NO data plane. Kalshi keys live in scratchpad/kalshi.env (prod + demo, both
   verified HTTP 200 in S110); the EIA/AWS/Databento keys need re-pasting only for staging.

2. STATE: brain s105.0, 82 plays. G22 COMPLETE (blind 4/10 5,965 -> r1 10/10 500 -> r2 10/10 330).
   G23 COMPLETE r1 (blind 5/10 5,920 drift +4,900 survives 83% -> refine 10/10 720); r2 NOT run.
   Both merges executed. The S110 centerpiece play is RETIRED on its own forward test.
   G23 was the last staged block - there is no G24 staged.

3. GREG'S OPEN CALLS - HE ASKED FOR THESE FIRST, AND THEY ARE DESIGN DECISIONS, NOT BUILDS:
   - D23 VALUE REPLACEMENT / SHAPE. "We can only pay attention to SHAPE for forecasting purposes...
     any time you use it after that, the value has to be replaced." Measured: 24 of 76 plays carried
     an absolute bar and the plays that FAILED this session are the value-keyed ones. Sharpened by
     the burn gate's death: a condition that CANNOT CHANGE STATE carries no information, whatever
     form it is written in (HDD >= 16.4 never reachable in summer; the CDD-add limb positive 20/20).
     Greg expects to TEST THE CHANGES ON A NEW GROUP.
   - D24 RETRO-INSTANCE PROGRAM (queued, high value). A mechanism is n=1 until the corpus is
     searched. QUALIFIED: past evidence is used WHEN AVAILABLE; a finding is NEVER disregarded for
     lacking it; record which of three states applies (found / searched-none / not-searched).
     Why it may matter most: k3_prev and its kin are PRE-CUTOFF, so anything validated this way is
     BLIND-LEGAL.
   - D25 ORDER OF REASONING. "It matters the ORDER of reasoning the agents use to make their
     decisions. There has to be a certain order of steps." Note only - Greg designs it.
   - D26 HARNESS SCORING CONVENTION (20:00-to-20:00 vs a 17:00 clock; changing it re-defines every
     historical score).
   - D27 render continuity: BUILT as announce; promoting it to a hard gate is Greg's call.

4. THE PROTOCOLS THAT NOW GOVERN EVERY RUN (RUN_SOP.md is binding; these are its spine):
   - NOTHING RUNS OFF-SOP. A gap STOPS the line: report it, propose a diff, get Greg's go, version-log
     it, then execute. Deviations are recorded NONCONFORMANCES, never silently absorbed.
   - Spawn from the VERBATIM templates (AUD-1 / BLD-1 / BLD-2 / RFN-1 / RFN-2); slots are LOOKUPS.
     Calendar premises are QUOTED from flow_calendar, never paraphrased (NC-1 was mine: a directive
     said "first post-roll session" when BCOM was on day 5 of 5).
   - No fix is DONE until a test proves the fixed path EXECUTES (D11). I violated this twice today and
     the rule caught me both times.
   - A feed enters the state only with a NAMED CONSUMER or an explicit PARK note (D12).
   - Reasoning capture is REQUIRED at close-out: a ledger with a machine-checked DECISION CLAIMS
     table, plus `decision_trace.py build <gid> --embed` and `verify` (0 UNRESOLVED).
   - INSTANCE-INLINE: every claim carries its evidence in the same sentence.
   - THE LEDGER IS NOT A SECOND BRAIN (D22): lessons reach the BLIND only through the adjudicated
     brain. Spawn templates cite the brain, never ledgers.
   - Brain merges are PROPOSAL FILES + adjudication, incumbents byte-identical. RETIREMENT is the one
     declared class allowed to mutate `status`, and it must carry its refuting evidence as a NEW key.
   - TALLIES ASSEMBLED FROM INDEPENDENT SLICES ARE SYSTEMATICALLY INCOMPLETE (S110, the burn-gate
     dissent): recompute counts at the coordinator across all ten days before merging a tally claim.

5. LIVE TRAPS
   - MBO book files (`g<N>_mbo_feature_states.jsonl`, `g<N>_mbo_l1_manifest.json`) are MISSING for
     g21/g22/g23 though the shared directive requires them - the book layer stands down group-wide.
   - Only NGQ26 is staged: roll attribution is unanswerable without the NGU26 leg.
   - Session 0710's tape is absent from every g23 slice; `ph_absorb` has no magnitude term;
     `grid_stack` serves no `wind_chg_7d`; storage_consensus dead post-0709; vol_regime n0
     era-degraded; contract_structure frozen at the 0703 vintage.
   - No A-bridge exists for a BLOCK-OPEN Monday (g22 and g23 both) while B's lens requires one.
   - No tropical/hurricane consumer yet, and Aug-Oct is live (the feed itself is built and smoked).

6. WHAT TO DO, IN ORDER (subject to Greg's calls in 3)
   1. Greg's D23/D25 design decisions - then a versioned SOP/brain change, then TEST ON A NEW GROUP
      (his stated intent). Staging a G24 needs the data plane (keys) - that is the gating dependency.
   2. D24 retro-instance program: systematize the corpus scan (C-0714 and D-0716 did it by hand).
   3. G23 round 2 (HE24->HE1) if wanted - the exit states are staged and need no data plane.
   4. Paper dock G1-G3: wire the coach's daily forecast into paper/forecast_today.json; stand the
      collector up as a service (NOTE: deploy/aws/install-ng-live.sh pins a STALE branch - re-point).
   5. The QC checklist can run any time on a cheap model: agents/QC_CHECKLIST.md, report-only.

KEYS DO NOT ROTATE DURING THE WALK. git = code + records, S3 = data, data/ disposable.
No emojis. Committer noreply@anthropic.com.
```
