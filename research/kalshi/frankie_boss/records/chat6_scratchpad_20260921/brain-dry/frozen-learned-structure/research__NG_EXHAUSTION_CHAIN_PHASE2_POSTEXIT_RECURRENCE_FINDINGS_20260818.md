# NG Exhaustion Chain Phase 2 — Post-Exit Reset / Re-entry and Recurrence Atlas — 2026-08-18

Status: **ADDITIVE PHASE-2 RESEARCH COMPLETE FOR THIS PASS; NOT A PERMANENT-FRANKIE PROMOTION.**

This continuation does not reopen Phase 1, retune the frozen exhaustion detector, modify the 54-week base, modify the held week, modify the frozen runway clock, modify Frankie/Frankie 1, modify `research/kalshi/spawn.py`, or change the frozen SSOS paper play.

## 1. Parent management is now post-exit, not successor-managed

The settled P-O-X parent trade remains valid and exits normally at its frozen structural endpoint `+60s`. A later successor exhaustion is not used to manage the open parent position.

The reason is now reproduced against the frozen detector semantics rather than assumed. Among the 666 valid base-54 P-O-X parents, 496 have the immediately following canonical exhaustion start **strictly before** the frozen structural endpoint+60 exit. The held week has 11 of 13. Exact canonical successor identity still cannot be known in time: the frozen detector's source-day 85th-percentile threshold is not final until the UTC source day completes. Relative to the parent exit, that necessary threshold-availability wall is positive in every one of those cases.

Base-54 in-trade successors: n=496; minimum threshold-wall miss `+81s`; median `+59,505s`; p25 `+48,295.25s`; p75 `+72,753.5s`.

Held in-trade successors: n=11; minimum miss `+3,799s`; median `+58,181s`.

Therefore the executable sequence for this research branch is:

**take valid parent -> normal +60 exit -> reset -> watch -> re-enter only on a later trusted setup.**

No synthetic early successor checkpoint is introduced.

## 2. Post-exit trusted re-entry is common, but usually hours later

Across all 666 frozen base-54 P-O-X parents, 650 (97.60%) reach another trusted SSOS or P-O-X-opposite target after the normal exit before the weekly chain ends.

- next trusted type: 395 SSOS, 255 P-O-X-opposite;
- median lag from parent exit to trusted target t0: `14,462.5s` (~4.02h);
- p25: `6,982s` (~1.94h);
- p75: `25,956.25s` (~7.21h);
- median intervening exhaustion events: `178.5`.

Held week: 13/13 reach a later trusted target; 7 SSOS and 6 P-O-X-opposite; median lag `9,935s` (~2.76h); median intervening events `131`.

This reinforces the existing separation between short-lag delayed expression and fresh re-entry. The hours-later trusted target is a new execution opportunity after reset, not evidence that the original parent should have remained open.

### Clean-reset check

For all 650 base parents that reach a later trusted target, every predecessor state required by that first trusted target reaches its h=60 causal-availability timestamp **after** the parent exit. Thus 650/650 first targets are clean on information availability.

A stronger raw-start test requires every predecessor event t0 itself to occur after the parent exit. The first trusted target already satisfies that stricter condition in 645/650 cases. In the remaining five, at least one predecessor t0 began before the parent exit but its usable h=60 state did not become available until after reset. Held is 13/13 under both definitions.

Operational conclusion: post-exit reset is clean; a tiny minority bridge a pre-exit raw event whose actionable state matures only after exit.

## 3. Phase-1 lineages contain reusable subchain modules

The recurrence search normalizes absolute UP/DOWN direction and retains relative polarity transitions (`S` = same polarity as prior exhaustion; `F` = flip). State codes remain `P/O/X/S`.

A module such as `PP|S` means two consecutive `P` seed states with the second exhaustion having the same polarity as the first. These modules are counted inside strict all-model-positive Phase-1 chains, even when the surrounding full chains differ.

### Reused pairs inside strict D2+ chains

Several pair modules recur across many different strict chains and across every OOT block plus held:

- `PP|S`: 291 pre-held strict D2+ chains; appears in all 36 OOT weeks; held 38. It occurs inside many distinct longer-chain contexts (19 / 26 / 16 distinct contexts across the three pre-held OOT blocks).
- `PO|S`: 145 pre-held; held 32.
- `OO|F`: 143 pre-held; held 23.
- `OP|F`: 138 pre-held; held 28.
- `XP|F`: 132 pre-held; held 20.
- `SS|S`: 124 pre-held; held 18.

This is direct evidence for reusable chain building blocks rather than only unique whole-chain identities.

### Reused triplets inside strict D2+ chains

The strongest repeated triplets include:

- `PPP|SS`: 87 pre-held strict chains; held 13;
- `PPX|SS`: 40 pre-held; held 11;
- `OOO|FF`: 27 pre-held; held 1;
- `PPS|SS`: 27 pre-held; held 2;
- `POP|SF`: 23 pre-held; held 6;
- `XPP|FS`: 20 pre-held; held 2.

The full-chain contexts around these triplets vary, so they are modules, not merely duplicates of one identical long chain.

## 4. Some recurring pairs are also chain-extension modules

Among strict D1+ origins, the block baseline probability of surviving one more link to D2 is about 7.44% in Eras 1-3, 8.45% in Eras 4-5, 7.71% in untouched confirmation, and 14.76% in held.

Several direction-invariant pairs exceed that baseline repeatedly:

### `PP|S`

- Eras 1-3: 80/845 extend (9.47%), lift 1.27x; median origin->D2 elapsed 139s.
- Eras 4-5: 77/749 (10.28%), lift 1.22x; median 139s.
- Confirmation: 41/412 (9.95%), lift 1.29x; median 151s.
- Held: 28/158 (17.72%), lift 1.20x; median 120s.

### `XP|F`

- Eras 1-3: 20/196 (10.20%), lift 1.37x.
- Eras 4-5: 24/238 (10.08%), lift 1.19x.
- Confirmation: 19/122 (15.57%), lift 2.02x.
- Held: 8/38 (21.05%), lift 1.43x.

### `PP|F`

- Eras 1-3: 19/150 (12.67%), lift 1.70x.
- Eras 4-5: 25/249 (10.04%), lift 1.19x.
- Confirmation: 14/143 (9.79%), lift 1.27x.
- Held: 11/37 (29.73%), lift 2.01x.

`OP|F` is above baseline in all three pre-held blocks but drops below the unusually high held D1->D2 baseline. It is therefore an investigator case, not a killed module.

These extension results are structural Phase-1 lineage findings, not frozen trade rules.

## 5. D2->D3 extension already separates into multiple families

The D2->D3 population is much smaller, so no universal rule is frozen. Still, recurring candidate families exist.

`OPO|FS` extends at 2/7, 1/4, and 1/3 in the three pre-held OOT blocks, corresponding to large lifts versus the very low D2->D3 block baselines. It has no held occurrence, so it remains a sparse recurring family, not a promoted rule.

Other triplets such as `XPP|FS` and `PXP|SS` appear to extend preferentially in later OOT/confirmation and held while not doing so in the earliest block. That is exactly the sort of regime/subtype behavior the investigator lane must preserve rather than average away.

This supports the working hypothesis that there are multiple short-to-long growth families rather than one universal chain-growth grammar.

## 6. Causal predecessor motifs beyond SSOS and P-O-X also recur

A separate exploratory screen asks whether causally available predecessor-state motifs plus the current polarity relation have a consistent endpoint+5 to endpoint+60 oriented return. This is a recurrence atlas, **not a multiple-testing-adjusted play promotion screen**.

Examples positive in Eras 1-3, Eras 4-5, untouched confirmation, and held include:

- `S -> SAME`;
- `X -> FLIP`;
- `PS -> SAME`;
- `OOS -> SAME`;
- `SOS -> FLIP`;
- `OSX -> FLIP`;
- `OOX -> FLIP`;
- `POO -> SAME`;
- `XOO -> FLIP`;
- `POX -> FLIP` (the already-prioritized P-O-X-opposite branch).

Examples consistently negative across the pre-held blocks and also negative/nonpositive in held include `OOO -> SAME`, `SOX -> SAME`, and `XSX -> FLIP`. These may represent anti-continuation / reversal-oriented structures and should be investigated symmetrically rather than discarded because their sign is negative.

## 7. Failed folds are investigator cases, not hard kills

The recurrence atlas explicitly preserves sign-changing motifs. Examples include `OOO -> FLIP`, `POX -> SAME`, `O -> FLIP`, `P -> FLIP`, `SS -> SAME`, and others that were positive in pre-held aggregates but negative in held.

The next action for such a motif is **FLAG_AND_DECOMPOSE**:

- retain every valid instance;
- inspect longer surrounding state/polarity context;
- inspect timing/lifespan family;
- distinguish conditions where the motif is true from conditions where it is false;
- do not use one failed held fold as an automatic retirement gate.

Early decomposition already shows why this matters. `OOO -> FLIP` does not behave uniformly once a fourth predecessor is restored: `XOOO -> FLIP`, `POOO -> FLIP`, `OOOO -> FLIP`, and `SOOO -> FLIP` have materially different chronological behavior. The shorter motif therefore hides multiple contexts.

## 8. Finalization boundary

Phase 2 should not be called finalized until the following are documented together:

1. normal parent exit -> post-exit reset -> trusted re-entry map;
2. short-lag delayed P-O-X-same re-expression kept separate from fresh re-entry;
3. reusable Phase-1 pair/triplet/longer modules across otherwise different chains;
4. D1->D2 and D2->D3 extension families, including timing/lifespan;
5. investigator decompositions for important true/false contexts rather than hard-fail deletion;
6. parallel/independent recurrence checks reconciled into one findings record;
7. Phase-2 brain proposal/index updated proposal-only with only durable lessons;
8. frozen SSOS play unchanged unless a separate deliberate research decision is made;
9. no permanent Frankie merge without Greg's explicit approval.

This pass resolves items 1, 3, and the first extension-family layer of 4, while preserving the remaining investigator/finalization work.
