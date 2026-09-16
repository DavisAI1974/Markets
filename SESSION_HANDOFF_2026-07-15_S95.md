# SESSION HANDOFF — S95 (work date 2026-07-15) — continuous-curve representation + contract-roll adjustment + the FULL G3-5 refinement + G6 blind holdout; ALL machinery persisted to git

Branch: `claude/ng-coach-agent-loop-5ha5bf` (dev = trunk `claude/kalshi-s79-kickoff-ij8t9o` + S94/S95 work).
Read `research/kalshi/REFINE_DIRECTIVE_S94.md` for the method, then this. The loop runs IN the Claude env
(the agent's brain = the session model; sub-steps spawned via the Agent tool). git = CODE + committed
renders/substrate; S3 = the raw tape; local `data/` + `scratchpad/` = gitignored regenerable/secret.

## HEADLINE (S95)
Built the CONTINUOUS-CURVE representation (JOB 1) and the CONTRACT-ROLL adjustment, ran the FULL unblinded
G3-5 refinement on roll-clean data, and ran G6 as the first true BLIND holdout. Everything — the build/learn
scripts, the brain, the forecast records, and the committed renders — is saved to git so nothing is rebuilt.

## THE MACHINERY (all in `research/kalshi/`, committed — this is what re-spins the loop)
- **`fast_tape.py`** — fast trade-price loader: grep-prefilter `"action":"T"` + npz cache. ~7x faster than
  the full MBP-10 decode (7.8s cold / instant warm vs 54s). Rebuild of the lost scratchpad `fast_score2`.
- **`precache_window.py START END`** — pre-decodes every NG day in a window to npz (make the render instant).
- **`roll_adjust.py`** — detects contract rolls (instrument_id change) and returns per-day back-adjust
  offsets. THE fix for the continuous series (see roll section). Caches per-day iid in `roll_meta_NG.json`.
- **`continuous_rt.py`** — THE RENDER FILE (canonical, parameterized by dates). Real-price RT curve + optional
  forecast overlay (`--guess`), weekend/overnight bridges broken, rolls marked. One file for any window:
  `python continuous_rt.py --anchor <day-before> --start <first> --end <last> --seams <g4,g5> --tag <name> --guess <grpN.json>`
- **`continuous_score.py --guess grpN.json --actual gN_rt.json --tag N`** — per-event scorecard + the
  roll-ADJUSTED "skill view" overlay (guess vs actual, roll removed so skill is readable).
- **`characterize_turns.py <days...>`** — runs `month_characterize.characterize_day` on given days, MERGES
  the per-leg fingerprints into `renders/ng_refine_s95/fingerprints.json` (never clobbers).
- **`extract_guesses.py`** — pulls the per-day guess-vs-actual scalars out of the brain into `guesses.json`.

## THE TWO AGENT STEPS (spawned via the Agent tool; prompts captured in `research/kalshi/AGENT_RUNBOOK_S95.md`)
1. **REFINE agent (unblinded)** — reads the brain + `g3g4g5_rt.json` + `fingerprints.json` + `guesses.json`
   + `g3g4g5_state.json`; ties each day's drift to conditions, extracts GENERAL rules, corrects contaminated
   claims, produces the refined guess CURVES (→ `forecasts/grp{3,4,5}.json`) + a brain proposal. G3/4/5 ONLY.
2. **BLIND forecaster** — reads the brain + a group's `decision-state` + the anchor (prior-day hr24); forecasts
   each day day-into-day, no tape → `forecasts/grpN.json`. This is the true-holdout skill test (G6 was one).

## BRAIN (`research/kalshi/knowledge/ng_brain.json`) — ONE FILE, single source of truth
- Consolidated to ONE file (Greg): `meta` + **`reasoning_method`** (HOW he reasons) + **`fingerprints`** (the
  perception vocabulary) + `plays` (13) + `mechanisms` + `open_frontier` + `ruled_out`. `NG_BEHAVIOR_KNOWLEDGE.md`
  is now a generated view, not a parallel doc. Pre-S95 brain backed up to `ng_brain_s92.6_backup.json`.
- **s95.1** (committed): the 6-day-fingerprint pass. `flow_nowcast` 0.87, `grind_vs_spike` 0.90,
  `cross_block_reversion` 0.40; **`turn_far_thinning` DEMOTED to noise** (doesn't discriminate at leg
  granularity); intraday side is carried by `dip_imb_level` + continuation-ASYMMETRY + `peaked_fast`.
- **s95.2** (the FULL refinement proposal, `ng_brain_s95.2_proposal.json`): roll correction + G6 holdout folded
  in + all-20-day fingerprints. REVIEW before merging into `ng_brain.json`.

## CONTRACT-ROLL ADJUSTMENT (load-bearing data-integrity fix, S95)
The continuous `NG.v.0` rolls to the next contract ~monthly (instrument_id change) → a fake price JUMP (the
calendar spread). **Two rolls in the Sep-Nov window: Sep 24->25 (869->864 Oct->Nov, +0.276) and Oct 26->27
(864->863 Nov->Dec, +0.659).** Oct 7->8 (G4->G5) did NOT roll. Consequences:
- The prior refine's flagship "0925 overnight gap +$2760 swing-exhaustion" was EXACTLY the roll (0.276*10000)
  — VOID. The "G3->G4 reversal up" was ~half roll-inflated (real G4 up-move is ~0.28 smaller).
- Convention (Greg): **the RT/historic line stays REAL (not adjusted)**; the roll is MARKED, and the
  roll-handling lives on the FORECAST/scoring side (the skill overlay is roll-adjusted). `continuous_rt`
  detects + marks rolls but plots real; `continuous_score` flattens for the skill comparison.
- Intraday per-day nets (open->close, same contract) are roll-CLEAN. Only cross-roll gaps/cum need care.

## DATA AUDIT (S95, all clean)
- **13 months of NG on S3** (Jul 2025 -> Jun 2026 full + Jun 30 2025); CL matches. The walk-to-winter tape is
  all there. NYMEX tape lives on S3 (`bento-568968024170-us-east-2-an`, prefix `nymex/nymex_cont/`).
- **Every weekend present** — 52/52 Sunday-eve reopen sessions, 0 missing. The only missing weekday is
  2026-04-03 (Good Friday, market closed). The render's broken lines are the real Fri-4pm->Sun-6pm closure,
  NOT missing data. `eia_surprise.json` regenerated via `EIA_API_KEY=DEMO_KEY python eia_surprise.py`.

## G6 — FIRST TRUE BLIND HOLDOUT (Oct 22 -> Nov 4, on s95.1)
Roll-adjusted, G6 was a **V**: week-1 give-back DOWN (3.52->3.14) then week-2 recovery UP (->3.66), net +0.14
up. The blind forecast leaned down (reversion lean) and: (a) CAUGHT the week-1 give-back direction; (b) MISSED
the week-2 recovery — the intra-block TURN, the open problem, still unsolved; (c) MAGNITUDE was the dominant
error (undersized the dip AND the recovery — a muted, mean-reverting curve vs a sharp V); (d) the storage
surplus (bearish) got block direction WRONG — winter heating-demand (HDD rising) won. **Lesson:
`cross_block_reversion` is a GIVE-BACK, not a sustained reversal (the block can V back); fundamentals are not a
reliable block-direction cue at the winter transition.** Direction 4/10. Renders: `g6_continuous.png` (real RT
+ forecast), `g6_overlay.png` (roll-adj skill view).

## STATE / renders (committed, `research/kalshi/renders/ng_refine_s95/`)
- `g3g4g5_continuous.png` (real RT + refined guess, from the full refinement), `g6_continuous.png` (real RT +
  blind guess) — the two saved renders. Plus `*_rt.json`, `*_overlay.png`, `fingerprints.json` (20 days),
  `guesses.json`, `g3g4g5_state.json`, `grp6_state.json`.
- Forecast records: `forecasts/grp{3,4,5}.json` (refined, with guess curves) + `grp6.json` (blind).

## NEXT
1. REVIEW + merge the s95.2 refinement proposal into `ng_brain.json` (correct roll claims, fold G6).
2. **Group-7** = next consecutive block from Nov 5 (walking into winter — Nov fill-peak -> Dec drawdown, the
   real regime test). Blind on the merged brain via the BLIND forecaster; anchor = Nov 4 hr24. Watch the roll
   (there IS a Nov->Dec... already done Oct 27; next roll ~late Nov Dec->Jan).
3. The intra-block TURN (catching the V recovery) + open-time from-flat side remain THE open problems; magnitude
   undersize on catalyst days is structural. Winter is the decisive out-of-regime test.

## RULES (unchanged): PER-EVENT, NEVER pool/average; drift is a DESCRIPTOR not error; NOT point-fitting (general
condition->behavior rules only); brain blinded-merged per group, refine only on past consecutive tapes; true
holdout + provisional-until-live; net-of-fee; git=CODE/renders, S3=DATA; NG != WTI; weather HANDS OFF; keys are
SECRETS (rotate; `scratchpad/aws.env` gitignored).
