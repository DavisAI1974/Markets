# NG Exhaustion Focused POX — Session Findings and Corrections — 2026-08-19

Status: **DURABLE SESSION RECORD. FIXED-POPULATION CORRECTION COMPLETE; PROPOSALS UPDATED; FINAL POX PREDICTION/TRADE ECONOMICS NOT YET COMPLETE.**

Branch: `chatgpt/ng-exhaustion-entry-timing-revival-20260818`

## Executive state

The focused POX line remains active. This session did real work, but it did **not** finish the final 3,429-case predictive/economic run. The major accomplishment was preventing an incorrect population reconstruction from becoming a durable result, replacing that code path with a fixed-ledger contract, preserving contamination discipline, and updating the brain/strategy proposals so the mistake is not learned later.

The next chat must **not** spend time reconfirming the population numbers or re-litigating their provenance. Treat these as fixed working truth:

- total focused POX population: **3,429**;
- later FLIP: **1,546** (45.1%);
- later SAME: **1,883** (54.9%);
- initial sign persistence through +60: approximately **94.4%**;
- population policy: `FIXED_3429_DO_NOT_REOPEN`.

## Protected boundary preserved

No modification was made to:

- frozen exhaustion detector;
- canonical evidence;
- Phase-1 lineage/scores;
- finalized Phase-2 findings;
- frozen runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS play.

No play was promoted and no permanent brain merge occurred.

## Read-in findings retained from finalized POX work

The following remain valid context and were not reopened:

1. POX is a branching state-transition problem, not a universal POX -> FLIP rule.
2. The historical narrow fixed-entry/causal subset showed meaningful opposite-current strength and held same-current losses; failures remain preserved.
3. Once a later successor exhaustion is causally confirmed, adding old POX ancestry was not stably incremental across blocks; successor behavior is better treated as a fresh/re-origin checkpoint.
4. Universal exit at successor confirmation was not consistently superior to the normal +60 parent exit.
5. SAME/delayed re-expression is real but conditional: shallow adverse cases recovered materially more often than deep adverse cases, but recovery can relapse and is not automatic re-entry permission.
6. Finalized Phase-2 management remains: execute validated parent -> normal +60 exit -> reset -> watch -> re-enter only on a later trusted causal setup.
7. Exact future successor identity may not be backdated into an open parent trade.

## Population-definition correction from this session

### What went wrong

An initial focused runner incorrectly assumed that the 3,429 population could be reconstructed as literal consecutive canonical seed states `P,O,X` with a following canonical event, and that FLIP/SAME could be assigned from the next canonical event polarity.

That assumption was tested before a durable result was allowed to land. The literal canonical-adjacency construction produced only about **3,015** cases and a different branch split, so it was rejected.

### Why this matters

The 3,429 focused population is **not** allowed to be replaced by a newly inferred canonical-adjacency population. Case identity and authoritative FLIP/SAME labels belong to the fixed master ledger; canonical events and raw tape are enrichment sources only.

### Historical provenance noted once, then closed

The original frozen exhaustion experiment had **1,718 reveal + 1,711 held = 3,429** event identities, and later canonical work recovered that original roster. This provenance was enough to confirm that 3,429 is a real frozen population quantity, but it is **not a research task for the next chat**. Do not spend more time re-proving it.

## Code/protocol correction completed

The focused protocol now states:

- `FIXED_3429_DO_NOT_REOPEN`;
- do not re-derive 3,429 from canonical adjacency or another population construction;
- load authoritative case identity/branch labels from the fixed ledger;
- fail closed if a supplied ledger does not contain exactly 3,429 unique rows split 1,546 FLIP / 1,883 SAME;
- a mismatch is an input/ledger problem, not permission to invent a replacement population;
- preserve every valid losing/delayed/choppy/false/non-executable row.

The runner was replaced with a fixed-ledger validator. It no longer contains or calls the rejected canonical P/O/X population enumerator.

The workflow was replaced with a **manual fixed-ledger gate**. It now requires an explicit authoritative ledger artifact ID/member path and cannot auto-launch from a population-reconstruction push.

## Contamination wall preserved

Independent D0-D5 result artifacts were not opened for POX rule selection in this session. The incremental POX-vs-D0-D5 crosswalk remains:

`DEFERRED_UNTIL_POX_AND_D0_D5_ARE_INDEPENDENTLY_FROZEN`

The next chat should continue this separation until standalone POX rules/economics are frozen.

## New execution finding retained

A contamination-safe result from the earlier entry-timing revival lane was reviewed:

- generic D1 `+0` early-entry tune gate: **FAILED**;
- in the D1 confirmation block, all-prediction gross mean was approximately **+0.037 ticks** over 1,427 rows;
- after 0.5 tick round-trip stress, mean was approximately **-0.463 ticks** and positive-week fraction was 0;
- therefore no generic D1 immediate-entry execution rule transfers into POX.

Interpretation: this is negative evidence for **generic D1 +0 execution**, not a rejection of D1 structure and not a rejection of POX. POX initial-continuation economics must validate separately on the fixed 3,429 population.

## Focused POX architecture now frozen at proposal level

The proposal architecture is:

1. **Stage 1 — initial continuation first.** Find the earliest validated causal POX signal and measure exact raw-tape economics at +5/+10/+20/+30/+60 with 0.5/1/2 tick cost stress.
2. **Stage 2 — later FLIP vs SAME prediction.** Predict the authoritative future branch from causal prefixes only.
3. **Stage 3 — branch management only if predictive value is strong enough to matter.** Compare continue/reset/reverse/follow-new-state/stand-down only at actual causal checkpoints.
4. **Stage 4 — delayed SAME watch/re-entry separately.** Never rewrite the original loss; never auto-re-enter from realized recovery.

## Current blockers / incomplete work

The following are **not yet finished**:

- authoritative fixed 3,429 ledger has not yet been materialized into the corrected runner in a completed workflow run;
- exact earliest causal POX-membership predictor is not yet frozen;
- if Target A is formulated as binary POX membership, an honest candidate/control universe must be supplied separately; do not fabricate negatives;
- fixed-population initial-continuation raw-tape economics are not yet produced;
- fixed-population FLIP-vs-SAME predictor is not yet produced;
- branch observational-knowability timing on the master ledger is not yet produced;
- successor/reset/action economics are not yet produced;
- delayed SAME watch/re-entry economics are not yet produced;
- no final all-findings result artifact exists yet.

## Fixed-ledger latest authority — 2026-08-19

The initial next-session file-location gate found frozen artifact `9279235031` (`ng-exhaustion-week-chain-state-roster-20260817`) carrying the marked 3,429-row roster and a stored immediate `next_event_target.same_polarity` split of 1,546 FLIP / 1,883 SAME. The earlier written 1,444 / 1,985 split prevented the gate from passing.

The user explicitly resolved that conflict on 2026-08-19: **use the newest numbers**. The authoritative fixed contract is therefore 3,429 / 1,546 / 1,883 from artifact `9279235031`. This is a direct authority update, not a population reconstruction, and must not be reopened again.

## Proposal updates committed

Updated/added proposal documents:

- `research/kalshi/knowledge/ng_brain_exhaustion_entry_timing_extension_20260818.json`
  - now references the focused POX extension;
  - adds authoritative-ledger/population-separation lesson;
  - adds generic D1 +0 non-transferability lesson;
  - records fixed POX population policy.
- `research/kalshi/knowledge/ng_brain_exhaustion_pox_focused_proposal_20260819.json`
  - focused proposal only; not merged.
- `research/strategy_evolution/NG_EXHAUSTION_POX_TRADE_STRATEGY_PROPOSAL_20260819.json`
  - separate strategy proposal only; not frozen.

## Commits from this focused session

- `690d7a069ee2a2c8aeba9faf17b5ab9a44ee374e` — fix focused POX protocol around immutable 3,429 ledger.
- `84056cb62d7602c4207a4bc9931b9880f287f693` — lock launch marker to fixed 3,429 population.
- `d1762d7e24f87153aacc8b396548c11038f8d141` — replace runner with ledger-driven fail-closed gate.
- `cb3a74664ea9bb4ac20a4bac4714297b455f0dc7` — replace workflow with manual fixed-ledger gate.
- `aeab154867a10f5f451fec559b2b3fde8029c9a6` — add focused POX brain proposal.
- `90e039ae3f5239ad7cfc9cafeea1e50a88cb7e46` — add focused POX trade strategy proposal.
- `f95ce6c7c533223107c7a94aeab84f449d6cd032` — update parent entry-timing proposal with focused POX lessons.

Earlier setup commits from this chat remain part of history but their incorrect adjacency assumption is superseded by the correction above:

- `d2d1f4c621995adfcd3a7469584ecf87cb166481` — original focused protocol draft;
- `0c3fbe325fc28af7572472374862c1800bfd1a00` — original runner draft; **superseded**;
- `a531e5571aa23eb67464f135f27f6fe644326474` — original workflow draft; **superseded**;
- `091b10731fa15215f20b270348a51290970a3797` — original launch marker; **superseded by fixed-population update**.

## Continuation — newest authority, causal richness, and residual-only H

The newest explicit user authority fixes the immutable population at 3,429 cases split 1,546 FLIP / 1,883 SAME from frozen chain-state roster artifact `9279235031`. The deterministic ledger SHA-256 is `328d66e61b14d4a04905ea95776cb7cca153a52726bf6cd41d18bc6aa2a645dc`. Its causal join is exact: 1,718 reveal + 1,711 blind, with zero missing, overlap, membership changes, or label changes.

The research design is now **prebirth first, residual H only** for both POX-membership prediction and conditional FLIP/SAME prediction:

- test `-60,-45,-30,-20,-15,-10,-5,-4,-3,-2,-1` first;
- remove every emitted prebirth call before H, including errors, so outcomes never grant a retry;
- run `0,1,2,3,4,5,10,15,20,30,45,60` only on the genuine no-call residual;
- record each residual case's first predictive H and preserve unresolved cases;
- the full OOT population reaches H only if the prebirth pass emits zero calls.

The causal input is maximally rich rather than price-blind: full dense detector/book/flow/MBO prefixes when available, causal milestone state, raw price/quote/trade/volume, every MBP-10 level, within-second market summaries, and action counts through the completed checkpoint second. Before birth, future origin polarity, event family, t0 price, confirmation delay, structural onset, and polarity-oriented features are withheld. Nothing from the next second onward is visible, and the first executable fill begins at the next second boundary.

The earlier local price-blind Stage-2 diagnostic is **superseded and must not be learned or promoted**. The updated workflow must obtain the authoritative raw MBP-10 shards and rerun the full causal cascade before results are frozen.

## Exact next research sequence

Do this next, in order, without reopening population archaeology:

1. Locate/materialize the **authoritative fixed 3,429 case ledger** or the already-existing artifact that carries those exact case identities and authoritative FLIP/SAME labels. This is a file-location task, not a population-rederivation task.
2. Run the fixed-ledger gate. If it passes 3,429 / 1,546 / 1,883, freeze the ledger reference/hash and move on immediately.
3. Join fixed identities to causal detector/canonical timestamps and authoritative raw NG tape. Do not let the join alter membership.
4. Produce Stage-1 initial-continuation economics at the earliest causal checkpoints, preserving all rows and exact signal timestamps.
5. Build Stage-2 FLIP/SAME predictor from causal prefixes with chronological OOT validation.
6. Measure branch causal knowability and whether branch prediction is early/strong enough to alter Stage-1 management.
7. Compare Stage-3 successor/reset actions and Stage-4 delayed SAME watch/re-entry.
8. Freeze standalone POX findings/proposals.
9. Only then open independent D0-D5 outcomes for the incremental-value crosswalk.

## Non-negotiable instruction for the next chat

**SKIP ALL POPULATION RECONFIRMATION.**

Do not spend time proving 3,429, 1,546, 1,883, 94.4%, 1,718+1,711, or re-testing literal canonical P/O/X adjacency. Those facts/failed paths are documented here precisely so the next chat can start with the actual predictability and tradeability work.
