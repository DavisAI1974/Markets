# NG Exhaustion Chain Phase 2 — Final Research Freeze / Handoff — 2026-08-18

Status: **PHASE-2 CHARACTERIZATION FINALIZED FOR THE CURRENT FROZEN 55-WEEK RESEARCH PASS.**

Branch: `chatgpt/ng-exhaustion-chain-phase2-20260817`

This freeze closes the Phase-2 characterization requested by the continuation handoff. It does **not** merge anything into permanent Frankie, does not alter Frankie 1, does not retune the frozen exhaustion detector, does not modify the 54-week canonical base or held-week rows, does not alter the frozen runway clock, does not change `research/kalshi/spawn.py`, and does not change the frozen SSOS paper play.

Future prospective/OOT promotion studies remain valid future work, but they are no longer treated as unfinished Phase-2 characterization.

---

## 1. Final parent management doctrine

For a valid P-O-X parent trade:

**execute -> normal structural endpoint+60 exit -> reset -> watch -> re-enter only on a later trusted full setup.**

A structural successor exhaustion may begin while the parent trade is still open, but exact canonical successor identity is not causally available soon enough under the frozen detector to manage that short parent trade.

Among the frozen valid P-O-X population:

- base54 valid P-O-X: 666;
- held: 13;
- total: 679;
- valid instances removed: 0.

Immediate next exhaustion starts strictly before the parent structural endpoint+60 exit in:

- 496/666 base parents;
- 11/13 held parents.

Yet the necessary final source-day threshold wall is after the parent exit in every such case:

- base minimum miss: +81s;
- base median miss: +59,505s;
- held minimum miss: +3,799s;
- held median miss: +58,181s.

Therefore no synthetic early successor identity is permitted. The parent exits normally first.

---

## 2. Post-exit reset and fresh trusted re-entry

After the normal parent exit, the chain resets and later trusted setups are treated as fresh/re-origin execution opportunities rather than proof that the original parent remained alive.

Base54:

- 650/666 P-O-X parents (97.60%) reach another trusted SSOS or P-O-X-opposite target before weekly close;
- next type: 395 SSOS / 255 P-O-X-opposite;
- median exit-to-target lag: 14,462.5s (~4.02h);
- p25: 6,982s;
- p75: 25,956.25s;
- median intervening exhaustion events: 178.5.

Held:

- 13/13 reach another trusted target;
- 7 SSOS / 6 P-O-X-opposite;
- median lag: 9,935s (~2.76h);
- median intervening exhaustion events: 131.

All 650 base first trusted targets and all 13 held first trusted targets have every required predecessor h=60 information-availability timestamp after the parent exit. Thus the usable information is genuinely rebuilt after reset.

---

## 3. P-O-X opposite-current and same-current branches

### Opposite-current

P-O-X with current polarity opposite the latest X predecessor remains the priority executable candidate but is **not frozen** as a new play in this Phase-2 pass.

Preheld 36 OOT weeks:

- n=207;
- gross mean ~+0.401 ticks;
- same-week demeaned delta ~+0.340 ticks;
- week sign-flip p ~0.01215.

Held:

- n=6;
- mean ~+0.500 ticks;
- zero negative cases.

It requires a future dedicated prospective/OOT promotion study before any freeze.

### Same-current delayed/re-expression branch

The parent still exits normally at +60. After the position is flat, the completed path can prioritize delayed-reexpression watch state.

Among negative-at-+60 same-current cases:

- preheld: 27/57 are nonnegative at either +120 or +300;
- held: 4/5.

A post-exit geometry split is materially informative:

**Shallow adverse:** no worse than -1 tick at +30 and exactly -1 tick at +60.

- preheld recovery at +120 or +300: 20/30 = 66.7%;
- Eras 4-5 + untouched confirmation: 9/11;
- held: 2/2.

**Deep persistent adverse:** -2 ticks or worse at both +30 and +60.

- preheld recovery: 1/11 = 9.1%;
- Eras 4-5 + untouched confirmation: 0/4;
- held: 0/1.

Preheld shallow-vs-deep Fisher one-sided p=0.001281; later Era4-5+confirmation one-sided p=0.01099.

This is **watch priority only**, not a re-entry trade. Some +120 recoveries relapse by +300, the shallow group does not have robust positive mean return across all preheld blocks, and another trade still requires a trusted full setup.

---

## 4. Reusable subchain grammar exists across different whole chains

Phase-1 strict lineages contain recurring direction-invariant pair and triplet modules even when the full surrounding chains differ.

Repeated strict-D2+ pairs include:

- `PP|S`: 291 preheld / 38 held;
- `PO|S`: 145 / 32;
- `OO|F`: 143 / 23;
- `OP|F`: 138 / 28;
- `XP|F`: 132 / 20;
- `SS|S`: 124 / 18.

Repeated triplets include:

- `PPP|SS`: 87 / 13;
- `PPX|SS`: 40 / 11;
- `OOO|FF`: 27 / 1;
- `PPS|SS`: 27 / 2;
- `POP|SF`: 23 / 6.

This is a modular chain grammar, not evidence that one entire ancestor string must repeat identically.

---

## 5. Some modules preferentially extend into longer strict chains

Among strict D1+ origins, several pair modules repeatedly have above-baseline probability of extending to D2.

`PP|S` lift versus block baseline:

- Eras 1-3: 1.27x;
- Eras 4-5: 1.22x;
- confirmation: 1.29x;
- held: 1.20x.

`XP|F`: 1.37x / 1.19x / 2.02x / 1.43x.

`PP|F`: 1.70x / 1.19x / 1.27x / 2.01x.

`OP|F` is above baseline in all three preheld blocks but below the unusually high held baseline. It is retained as an investigator subtype, not hard-killed.

D2->D3 extension families also exist but are sparse. `OPO|FS` is one recurring example across the preheld OOT blocks. D4/D5 are too sparse for a stable family doctrine and must not be force-fit.

---

## 6. Short versus long chains are real timing families

Exact D2 elapsed time is best characterized by three preheld log-time components:

- short center ~126.25s;
- middle center ~215.19s;
- rare long-tail center ~797.96s (~13.3m).

Preheld counts: 947 / 380 / 52.

Held assignments under the frozen preheld model: 156 / 52 / 5.

Exact D3 is usefully characterized by two families:

- ~210.51s;
- ~609.34s.

Preheld counts: 83 / 10.

Held: 25 / 6.

The timing-family proportions replicate better than the exact module composition inside each family. Thus long/short lifespan is a real axis while the state/polarity grammar populating a family can vary by regime.

The fitted centers are characterization only, not live timing cutoffs.

---

## 7. Failed folds are investigator cases, never automatic deletion

Final policy remains:

**FLAG_AND_DECOMPOSE.**

Preserve both true and false instances. Restore longer context, inspect timing/lifespan family, and test why a motif works in some blocks and not others.

`OOO -> FLIP` is the clearest example. Restoring one older predecessor produces materially different `XOOO`, `POOO`, `OOOO`, and `SOOO` behaviors rather than one homogeneous failure class.

No valid row is removed because it loses or conflicts with an aggregate mean.

---

## 8. Independent recurring modules exist beyond SSOS and P-O-X-opposite

A novelty screen removed every current event already qualifying as trusted SSOS or P-O-X-opposite.

Sanity checks behaved correctly:

- `POX -> FLIP` falls to zero unique instances because it is exactly the known P-O-X-opposite branch;
- `SOS -> FLIP` loses stable confirmation after SSOS overlap is removed.

Other modules remain independent and preserve oriented gross and same-week-demeaned sign across discovery, replication, confirmation, and held.

Higher-support examples:

- `OOSS -> FLIP`, **AGAINST_CURRENT**;
- `SOOS -> SAME`, **WITH_CURRENT**;
- `OOO -> SAME`, **AGAINST_CURRENT**;
- `XSX -> FLIP`, **AGAINST_CURRENT**.

Higher-magnitude/lower-frequency examples:

- `OSP -> SAME`, WITH_CURRENT;
- `OSP -> FLIP`, WITH_CURRENT;
- `PSOS -> FLIP`, WITH_CURRENT;
- `SXOO -> FLIP`, WITH_CURRENT.

These form a **future candidate queue only**. The screen is exploratory and many-pattern; no multiple-testing-adjusted play promotion was performed. An AGAINST_CURRENT structural orientation is not an automatically authorized reversal trade.

---

## 9. Parallel recurrence verification

Four independent lane contracts were run concurrently:

1. pair/triplet recurrence;
2. D1->D2 extension propensity;
3. D2/D3 timing families;
4. true/false-context investigator.

All four processes returned exit code 0 against locally downloaded artifacts whose ZIP SHA256 values exactly matched the frozen source handoff.

Durable verification:

- `research/NG_EXHAUSTION_CHAIN_PHASE2_PARALLEL_LOCAL_VERIFICATION_20260818.json`
- commit `5ed07a15f857c92f73458d370e0722846b14b0d1`

Lane output hashes:

- pairings `3a66afdc130fd5f7f7cbf2995b01f96d53683603b92e463af05d8e6de753209c`;
- extension `2ac93604f7b5dbde216a53c3e8c3253b4a39da1fb771241253f8de0f19abfaa1`;
- timing `befa55fddfe03ef0a24c23f9060b3d866f676bd1a5d30390252bfc1055ccb7b2`;
- investigator `adb6e8910ae7e7c74a46eb2e3444de54c61f1a5e44abbdac45427d1213ab2253`.

A GitHub Actions replay workflow also exists, but the connected GitHub interface cannot expose or dispatch that branch-only run. No GitHub-run success is claimed; the verified concurrent local run is the Phase-2 durable parallel proof.

---

## 10. Execution-play boundary

The existing frozen paper-only play remains:

`NG_CHAIN_D4_SSOS_CONTINUATION_V1`

It is unchanged.

No P-O-X branch and no recurrence-atlas module is newly frozen by this finalization.

No live-edge claim is made from gross-return research statistics.

---

## 11. Brain boundary

Permanent Frankie remains unchanged.

Proposal lineage remains:

- runway parent proposal: `research/FRANKIE_NG_EXHAUSTION_BRAIN_LESSON_PROPOSAL_20260817.md` at `f45a38e3266e67d103348c069ba827fff65fdd53`;
- Phase-2 extension proposal: `research/kalshi/knowledge/ng_brain_exhaustion_chain_phase2_proposal_20260818.json`;
- authoritative index: `research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md`.

The Phase-2 proposal records durable general lessons but keeps individual P-O-X/recurrence candidates provisional. A permanent brain merge is blocked until Greg explicitly approves it.

---

## 12. Future research, not unfinished Phase 2

The following are valid next-stage research threads but do not prevent this Phase-2 characterization freeze:

- prospective/OOT promotion study for P-O-X opposite-current;
- deliberately selected candidate contracts for independent recurrence modules;
- candidate-specific deeper true/false decomposition;
- D4/D5 timing-family research if future sample size becomes sufficient;
- selective older-ancestry tests at specific re-origin subtypes.

---

## 13. Frozen source provenance

- base54 canonical artifact `9281733364`; ZIP SHA256 `f50eaf74a57654334691cbf5cce3b038443f6944a9c00eb5da6ca35b557802b1`;
- held canonical artifact `9281272840`; ZIP SHA256 `21577d01d45241264df714ab6ee5b95f6a774e1475e0d74a9454221fdfdde12e`;
- Phase-1 lineage artifact `9289929292`; ZIP SHA256 `a67caab9de6b183e8c102ebd73a7e542aa909e23f66575290563e40b056efd95`;
- final 55W reconciliation artifact `9306082330`; ZIP SHA256 `f17c130df029429bfbc35067d1cc9d16128ca4fb227dd37f3fb4fbb8bbaf8875`.

The final protected-file diff audit is the last mechanical check after this document is committed.
