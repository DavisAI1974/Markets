# NG Exhaustion Chain Phase 2 — All Agent Findings — 2026-08-18

Status: **DURABLE ALL-AGENT FINDINGS RECORD; PHASE-2 CHARACTERIZATION FINALIZED; NO NEW PLAY PROMOTION.**

This file exists so a future chat does not have to reconstruct the parallel-agent work from scattered artifacts. It records the findings from every Phase-2 parallel lane, including positive findings, sign-changing/false cases, timing families, extension failures, and the standing `FLAG_AND_DECOMPOSE` policy. It also reconciles those lanes with the main P-O-X/post-exit continuation work.

Nothing here changes the frozen detector, frozen 54-week canonical base, held-week rows, runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS paper play.

## Immutable inputs and verification

The four agents independently used the same immutable source artifacts:

- base54 canonical: artifact `9281733364`, ZIP SHA256 `f50eaf74a57654334691cbf5cce3b038443f6944a9c00eb5da6ca35b557802b1`;
- held 20260329 canonical: artifact `9281272840`, ZIP SHA256 `21577d01d45241264df714ab6ee5b95f6a774e1475e0d74a9454221fdfdde12e`;
- Phase-1 lineage: artifact `9289929292`, ZIP SHA256 `a67caab9de6b183e8c102ebd73a7e542aa909e23f66575290563e40b056efd95`;
- final 55-week reconciliation: artifact `9306082330`, ZIP SHA256 `f17c130df029429bfbc35067d1cc9d16128ca4fb227dd37f3fb4fbb8bbaf8875`.

The four lane contracts were executed concurrently and all exited `0`. The exact deterministic lane-output hashes are:

- pairings: `3a66afdc130fd5f7f7cbf2995b01f96d53683603b92e463af05d8e6de753209c`;
- extension: `2ac93604f7b5dbde216a53c3e8c3253b4a39da1fb771241253f8de0f19abfaa1`;
- timing: `befa55fddfe03ef0a24c23f9060b3d866f676bd1a5d30390252bfc1055ccb7b2`;
- investigator: `adb6e8910ae7e7c74a46eb2e3444de54c61f1a5e44abbdac45427d1213ab2253`.

Durable verification is `research/NG_EXHAUSTION_CHAIN_PHASE2_PARALLEL_LOCAL_VERIFICATION_20260818.json` at commit `5ed07a15f857c92f73458d370e0722846b14b0d1`.

The deterministic runner is `research/ng_exhaustion_chain_phase2_parallel_agents_20260818.py`. If exact per-pattern machine output is ever needed again, rerun the frozen runner against the four verified artifacts above; do not alter the detector or source rows.

---

## Agent 1 — pair / triplet recurrence

Question: do smaller direction-invariant subchains repeat inside otherwise different strict higher-order chains?

Answer: **yes.** Whole-chain identity does not need to repeat for local chain grammar to recur.

State codes: `P = persistent_exhaustion`, `O = collapsed_opposite_flow_reversal`, `S = collapsed_same_flow_reload`, `X = collapsed_sparse_indeterminate`. After the pipe, `S` means same-polarity transition and `F` means polarity flip within the module.

Most repeated strict-D2+ pairs:

- `PP|S`: 291 pre-held, 38 held;
- `PO|S`: 145 pre-held, 32 held;
- `OO|F`: 143 pre-held, 23 held;
- `OP|F`: 138 pre-held, 28 held;
- `XP|F`: 132 pre-held, 20 held;
- `SS|S`: 124 pre-held, 18 held;
- additional recurring pairs include `OX|F`, `PX|S`, `OO|S`, `SO|S`, and other state/polarity combinations retained by the deterministic lane.

Most repeated strict-D2+ triplets:

- `PPP|SS`: 87 pre-held, 13 held;
- `PPX|SS`: 40 pre-held, 11 held;
- `OOO|FF`: 27 pre-held, 1 held;
- `PPS|SS`: 27 pre-held, 2 held;
- `POP|SF`: 23 pre-held, 6 held;
- additional recurrent triplets include `XPP|SS`, `PPP|FS`, `SSS|SS`, `XPP|FS`, `PXP|SF`, and the rest of the deterministic lane output.

The recurrence lane also tracked how many different full-chain contexts contained each pair/triplet. The same small modules appeared inside multiple different surrounding chains, which is the evidence for **modular chain grammar** rather than one immutable ancestry string.

Agent-1 boundary: recurrence alone is structural evidence. It does not authorize a trade or imply that a repeated module has positive executable expectancy.

---

## Agent 2 — D1 -> D2 extension propensity

Question: when a strict D1 chain begins with a particular pair module, is that module unusually likely to extend into D2 relative to the block-wide D1->D2 baseline?

Answer: **some modules repeatedly extend above baseline, some repeatedly underperform, and some change by regime. All are retained.**

Lift order below is `Eras1-3 / Eras4-5 / untouched confirmation / held`:

- `PP|S`: `1.272 / 1.217 / 1.290 / 1.201`;
- `PO|S`: `0.907 / 0.675 / 0.831 / 1.334`;
- `PX|S`: `0.915 / 0.837 / 0.543 / 0.736`;
- `OO|F`: `1.062 / 0.782 / 1.271 / 0.881`;
- `SO|S`: `0.557 / 0.682 / 0.845 / 1.204`;
- `SS|S`: `0.854 / 0.966 / 1.054 / 1.087`;
- `PS|S`: `0.618 / 1.015 / 0.845 / 0.521`;
- `OS|F`: `0.647 / 0.892 / 0.494 / 0.903`;
- `OO|S`: `1.101 / 0.861 / 0.291 / 0.847`;
- `OS|S`: `0.943 / 0.658 / 0.918 / 0.968`;
- `OP|F`: `1.210 / 1.330 / 1.204 / 0.730`;
- `OX|F`: `1.392 / 1.036 / 0.770 / 1.311`;
- `SO|F`: `0.707 / 0.968 / 0.810 / 1.031`;
- `XP|F`: `1.371 / 1.194 / 2.019 / 1.426`;
- `PP|F`: `1.702 / 1.189 / 1.269 / 2.014`;
- `SP|S`: `1.020 / 1.435 / 1.265 / 0.797`;
- `XO|F`: `0.989 / 1.251 / 0.904 / 1.042`;
- `XO|S`: `1.000 / 1.098 / 0.772 / 1.694`;
- `SS|F`: `0.883 / 1.412 / 1.045 / 1.219`;
- `SX|S`: `1.152 / 0.924 / 0.836 / 0.462`;
- `XX|S`: `0.480 / 1.271 / 0.879 / 0.363`;
- `XP|S`: `1.309 / 1.143 / 1.525 / 1.196`;
- `XX|F`: `1.319 / 1.093 / 0.730 / 1.129`;
- `OX|S`: `0.854 / 1.025 / 0.836 / 0.782`;
- `PX|F`: `1.933 / 1.315 / 0.876 / 0.565`;
- `PO|F`: `0.611 / 0.674 / 0.953 / 1.290`;
- `XS|S`: `1.095 / 0.872 / 0.000 / 0.874`;
- `XS|F`: `1.194 / 0.798 / 1.525 / 0.753`;
- `SX|F`: `1.729 / 0.455 / 0.701 / 0.713`;
- `PS|F`: `1.176 / 0.602 / 1.496 / 1.042`;
- `OP|S`: `1.152 / 1.138 / 2.255 / 0.521`;
- `SP|F`: `0.983 / 0.877 / 0.926 / 0.000`.

Strongest stable extension examples for future structural study are `PP|S`, `XP|F`, and `PP|F` because each is above the block baseline in all four chronological blocks.

`OP|F` is a deliberate investigator example: above baseline in all three pre-held blocks, then below the unusually high held baseline. It is **not killed**.

Agent-2 boundary: extension propensity says a module is more or less likely to grow into a deeper strict chain. It is not an entry or exit rule.

---

## Agent 3 — timing / lifespan families

Question: do strict chain lifespans form distinct timing families rather than one continuous generic duration?

Answer: **yes for D2 and D3; D4/D5 are too sparse and must not be force-fit.**

Exact D2, frozen pre-held log-time mixture:

- short center: `126.246s`;
- middle center: `215.192s`;
- rare long-tail center: `797.964s` (~13.3 minutes);
- pre-held counts: `947 / 380 / 52`;
- held assignments under the frozen pre-held model: `156 / 52 / 5`;
- total exact-D2: 1,379 pre-held, 213 held.

Exact D3:

- short center: `210.509s`;
- longer-tail center: `609.339s`;
- pre-held counts: `83 / 10`;
- held assignments: `25 / 6`;
- total exact-D3: 93 pre-held, 31 held.

Agent-3 interpretation: the broad timing-family proportions replicate better than the exact state/polarity module composition inside each family. Therefore short/long lifespan is a real chain axis even though the grammar that populates the long tail can change by regime.

Agent-3 boundary: fitted centers are population characterization only. They are not hard live cutoffs. Current D4/D5 sample size is the explicit unresolved boundary.

---

## Agent 4 — true / false context investigator

Question: which causal predecessor patterns work consistently, which flip by block, and what should be done with failures?

Answer: **many patterns change sign by block. Those failures are informative context cases, not automatic deletions.**

The lane tested causal predecessor state strings of depth 1 through 4, paired with whether the current exhaustion polarity was `SAME` or `FLIP` relative to the latest predecessor. Only patterns meeting the predeclared minimum sample in Eras1-3, Eras4-5, and confirmation were retained by the deterministic lane.

Reproduced headline sign-changing cases, gross mean order `Eras1-3 / Eras4-5 / confirmation / held`:

- `O -> FLIP`: `+0.0579 / +0.0302 / +0.1204 / -0.4765` ticks;
- `P -> FLIP`: `+0.1913 / +0.3232 / +0.1609 / -0.8182`;
- `OOO -> FLIP`: `+0.0817 / +0.0649 / +0.1463 / -0.7692`;
- `POX -> SAME`: `+0.2830 / +0.2800 / +0.4872 / -0.8571`.

The full qualifying investigator output is substantially larger than these headline examples: depth-1, depth-2, depth-3, and depth-4 causal patterns were all retained by the deterministic output whose exact SHA256 is recorded above. A future chat that needs a specific pattern should reproduce/read the frozen runner output instead of assuming unlisted patterns were discarded.

The critical investigator finding is that restoring older context can materially split a shorter pattern. `OOO -> FLIP` is the clearest example: deeper ancestors such as `XOOO`, `POOO`, `OOOO`, and `SOOO` do not behave as one homogeneous class. Some held subtypes are positive while others are negative.

The lane policy is permanently recorded as:

**`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`**

Preserve true and false instances. Investigate longer ancestry, timing/lifespan family, and regime. Never delete valid rows merely to rescue an aggregate mechanism.

---

## Independent-module novelty screen after agent recurrence work

The parallel agents established that modular recurrence exists. A separate Phase-2 novelty screen then removed every event already qualifying as trusted SSOS or P-O-X-opposite to determine whether apparently new motifs were merely aliases of known setups.

Sanity checks:

- `POX -> FLIP` correctly falls to zero unique instances because it is exactly the known P-O-X-opposite branch;
- `SOS -> FLIP` loses stable confirmation after SSOS overlap removal.

Independent higher-support modules that remain after known-setup removal:

- `OOSS -> FLIP`, structural orientation **AGAINST_CURRENT**;
- `SOOS -> SAME`, **WITH_CURRENT**;
- `OOO -> SAME`, **AGAINST_CURRENT**;
- `XSX -> FLIP`, **AGAINST_CURRENT**.

Higher-magnitude/lower-frequency independent modules:

- `OSP -> SAME`, WITH_CURRENT;
- `OSP -> FLIP`, WITH_CURRENT;
- `PSOS -> FLIP`, WITH_CURRENT;
- `SXOO -> FLIP`, WITH_CURRENT.

These are a future candidate queue only. The screen was exploratory/many-pattern and did not perform a multiple-testing-adjusted promotion study. `AGAINST_CURRENT` is a structural orientation, not an automatically authorized reversal trade.

---

## Main-line P-O-X / reset-reentry findings that must travel with the agents

The parallel recurrence work is not separable from the finalized main Phase-2 execution doctrine.

Valid P-O-X population:

- base54: 666;
- held: 13;
- total: 679;
- valid instances removed: 0.

Settled parent management:

**execute -> normal structural endpoint+60 exit -> reset -> watch -> re-enter only on a later trusted full SSOS or P-O-X-opposite setup.**

Reason: 496/666 base and 11/13 held immediate successors start strictly before the normal parent +60 exit, but exact canonical successor identity is causally unavailable before the parent exit in every such case under the frozen detector. The closest base miss is +81 seconds. Do not synthesize an early successor detector.

Post-exit fresh trusted re-entry:

- 650/666 base parents reach another trusted target before weekly close;
- next type: 395 SSOS / 255 P-O-X-opposite;
- median exit-to-target lag: 14,462.5s (~4.02h);
- median intervening exhaustion events: 178.5;
- held: 13/13, with 7 SSOS / 6 P-O-X-opposite and median lag 9,935s (~2.76h).

Every first trusted target had all required predecessor h=60 information become available after the parent exit. Operationally, the re-entry state is genuinely rebuilt after reset.

P-O-X opposite-current remains the priority executable candidate, **not frozen**:

- pre-held 36 OOT weeks n=207;
- gross mean ~+0.401 ticks;
- same-week demeaned delta ~+0.340 ticks;
- week sign-flip p ~0.01215;
- held n=6, mean ~+0.500 ticks, zero negative cases.

P-O-X same-current post-exit watch decomposition:

- shallow adverse: no worse than -1 tick at +30 and exactly -1 tick at +60;
  - pre-held nonnegative by +120 or +300: 20/30 = 66.7%;
  - Era4-5 + confirmation: 9/11;
  - held: 2/2;
- deep persistent adverse: -2 ticks or worse at both +30 and +60;
  - pre-held recovery: 1/11 = 9.1%;
  - Era4-5 + confirmation: 0/4;
  - held: 0/1.

This shallow/deep split is **watch priority only**, not a trade. Recovery probability is not positive expected return; some +120 recoveries relapse by +300. Another trade still requires a trusted full setup.

---

## Final all-agent conclusions

1. Higher-order exhaustion behavior is modular: smaller pair/triplet structures recur across different whole chains.
2. Some modules preferentially extend into deeper strict chains; others are below baseline or regime-sensitive.
3. Short/middle/long timing families are a real axis distinct from exact chain grammar.
4. Failed folds and sign changes contain structure and must be decomposed rather than deleted.
5. Independent recurring modules exist beyond SSOS and P-O-X-opposite, but none were promoted in this pass.
6. Exact causal detector identity availability governs what can be used live; retrospective structural existence is not sufficient.
7. For P-O-X, the parent exits normally at +60 before reset; fresh trusted re-entry usually occurs much later.
8. The existing frozen SSOS play remains unchanged; Phase 2 froze no additional play.
9. Permanent Frankie remains unchanged. The brain work remains proposal-only until Greg explicitly approves a deliberate merge.

## Future work, not unfinished Phase 2

- dedicated prospective/OOT promotion study for P-O-X opposite-current;
- candidate-specific causal/OOT promotion studies for selected independent recurrence modules;
- candidate-specific deeper true/false decomposition if a module advances;
- additional D4/D5 timing-family research only when sample size becomes sufficient;
- selective older-ancestry tests at specific future re-origin subtypes.
