# DROP-IN BOX - S107 (start a FRESH session with this)

## 0. Branch + read order (do this FIRST)

```bash
git fetch origin claude/kalshi-agents-coordinator-guard-1175nr
git checkout -B claude/kalshi-agents-coordinator-guard-1175nr origin/claude/kalshi-agents-coordinator-guard-1175nr
git log --oneline -1     # expect the S106 close-out commit
```
Read in order: `SESSION_HANDOFF_2026-07-31_S106.md` (in full) -> `research/kalshi/agents/README.md`
-> `CLAUDE.md` header.

Fresh container needs: `pip install numpy pandas matplotlib boto3 databento`

## 1. THE STANDING ORDER (Greg, load-bearing - read this before touching anything)

**One agent regime. The blind IS the refine engine** (`mbo_refine_shared.md` + `mbo_specialist_{A..E}.md`),
**with the price curve masked in the DATA and NOTHING else different.** "He ingests and has the same
process and build as refine EXCEPT just take away the ability to see the price curve. THAT ONE THING IS
LITERALLY IT... do not change anything except for that one thing."

- The mask is a BUILT-IN PARAMETER: `decision_state(days, mask_after=YYYYMMDD)`. Set = blind, None = refine.
- **Do NOT edit the agent files, the coordinators, or the brain reasoning to make something work.** If a
  run cannot proceed without a change, STOP AND ASK. No silent turning-off. Talk before changing any
  blind/refine reasoning.
- `verify_gold.py` hard-fails any run on a tampered gold vault. Keep it passing.

## 2. STATE

- **Brain = s103.1, 61 plays** (merged S106: +7 general plays from the G19 refine; 54/54 incumbents
  byte-identical). Backup `ng_brain_s102.9_backup.json`.
- **G19 COMPLETE through refine round 1**: blind 4/10 mean|err| **939** -> refine r1 10/10 mean|err| **79**
  (every day <100, six sign-flips all correct). The clean blind REPLACED the S105 suspect grp19.json.
- G17/G18 done+merged. G20-G23 staged data-ready.
- **Round-2 infra STAGED**: databento installed, all 10 G19 MBO legs in `data/ng_mbo_g17/` (gitignored).

## 3. DO THIS, IN ORDER

1. **G19 refine ROUND 2 (the HE24->HE1 pass) - the opener.**
   `python research/kalshi/group_he24_he1_handoff.py --source actual g19` (tapes already staged) ->
   inject each specialist's own round-1 posterior + the handoff -> re-run the 5 specialists (refine can
   run round 2 PARALLEL; its handoffs are precomputed from the actual) -> `group_coordinate_refine.py
   g19 --r2`. Precedent: G15 72->66, G17 24->11 - the day-into-day pass roughly HALVES the error
   (magnitude/timing only, ZERO direction changes).
2. **G20 blind on s103.1 - THE REAL TEST.** G19's biggest finding (B, corroborated by all five):
   **neither Monday miss required the price curve** - both were fixable from the corrected handoff plus
   the worsening COT alone. New play `boundary.chain_label_must_track_realized_cum` says the blind is NOT
   exempt from carrying chain state (it travels in the handoff, which is never masked). So: run the G20
   blind with the handoff carrying cum/chain state and see how much of the refine's gain the blind keeps.
   G20 = Sun 05-24 -> Fri 06-05, Memorial Day 05-25 holiday (A owns it), EIA shifts Thu 05-28 -> Fri
   05-29, clean July/NGN26 leg, anchor from G19's actual 05-22 close.
3. **Render continuity (Q2)**: forecast as ONE polyline, NaN only at >3h gaps, both coordinators.
4. **The 3 plumbing defects**: #3 `big_print_b_share` size-weighted copy-through at
   `forecast_harness.py:630` (currently the count-based value shadows it); #1 log the `ng_l1` miss +
   a per-day `firehose_present` flag; #2 surface `flow_read_error` as a top-level flag.
5. **Live MBO entitlement check** - is GLBX.MDP3 actually STREAMING (vs historical-only) on the existing
   $179 Standard plan? Non-pro already selected, cost solved. The $1,500 Plus bump is NOT needed (it only
   buys historical depth we already have on S3).
6. **ROTATE THE AWS KEY** (photographed into chat again in S106).

## 4. RUN MECHANICS (the turnkey loop - do not re-author)

- **Sequenced spawn, BOTH passes**: wave 1 = C (core) + D (EIA) + E (Fri/seam) in parallel -> wave 2 = A
  (weekend-seam bridge, consumes E's `handoff_out`) -> wave 3 = B (Monday, consumes A's bridge; A informs,
  B DECIDES and owns the number). Model opus.
- **Blind input set = brain + the price-masked decision_state ONLY** (per `doctrine_tier3.blind_run_hygiene`).
  Blind must NOT read `forecasts/grp<N>.json` (no prior on a first pass) nor the price-bearing
  `g<N>_mbo_evidence.json` / feature_states / l1_manifest.
- **Refine additionally gets** `g<N>_mbo_evidence.json` (per-day open/close/net, phases {sflow,pxchg,vol},
  ph_absorb, turns) - that is the ONLY data difference.
- **Seam day = a REAL, TRADED, SCORED day** on the post-roll leg; only the overnight GAP is voided
  (`overnight_gap_usd = 0`). Precedent g17 0421. Do NOT zero the seam day's move.
- **First day anchoring**: day 1 has no in-block prior - anchor its path to the prior block's close
  (`group_config` anchor + `anchor_lasthr_dir`); its `path_p50_curve` opens at cum 0 at the reopen.
- **Assembly**: the engine emits `expected_magnitude_usd`; `group_coordinate_blind.py` reads
  `guessed_net_usd`. Bridge with the VERBATIM reformat (rename + reshape `path_p50_curve` ->
  `path_distribution`), numbers untouched - NOT a code change. `group_coordinate_refine.py` speaks the
  engine schema natively (and needs `grp<N>.json` + `g<N>_actual.json` present).
- **Archive the blind specialist files** (`forecasts/g<N>_blind_round1/`) before the refine overwrites
  the shared `grp<N>_mbo_specialist_<X>.json` names.
- **AWS**: always `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY` (container injects placeholders);
  real pair in `~/.aws/credentials`.

## 5. THE FOUR FIXES THAT WON G19 (now brain plays - apply them, they are live in s103.1)

1. `direction.flow_conviction_sign_gate` - per-phase sign(sflow)*sign(pxchg) is the SIGN gate. The
   `big_print_b_share >= 0.55` arm NEVER fires in a covering rally (G19 max 0.537).
2. `direction.absorption_is_reversal` - absorbed SELL under rising price -> UP; absorbed BUY under
   falling price -> DOWN. Never a damp, never a cap.
3. `structure.covering_extension_distribution_flip` - the identical absorption signature flips to
   distribution-DOWN at a maximally-extended crest, but ONLY when the absorption tell itself reverses.
   Extension alone is a FALSE trigger (G19 0519, age 7, correctly not flipped, actual +840).
4. `positioning.covering_self_limiting_cot_wow_gate` + `boundary.seam_gap_up_prior_on_worsening_cot` -
   "spent" needs an evidence bar and a falsifiability clause (never the same direction from OPPOSITE
   exit states); a worsening COT WoW means covering is LIVE and the seam gap carries a directional UP
   prior, gap-first in magnitude.
Plus `boundary.chain_label_must_track_realized_cum` (no day restarts at cum 0) and
`daytype.friday_exit_close_location_over_flow_shape` (close location, not flow-shape decay).

## 6. STANDING DOCTRINE

- **Scoreboard = FORWARD-CURVE error / P&L, not daily direction hit-rate.** (The S105 "+$2,290" that hid
  a 15c drift is the cautionary tale.)
- Kitchen sink for both agents; the blind's ONLY mask is the price curve.
- One group = two weeks. Stage all groups' data, RUN ONE at a time. Running ahead is scope creep.
- One thing at a time. Talk before changing blind/refine reasoning.
- Group windows: Sunday reopen -> the SECOND Friday, always. FOCUS = FRIDAY AND MONDAY (Friday is the
  cascade root). Target: honest under-100 every day.
- Magnitudes DERIVED from measurable state, never fitted to the actual; a reactive tail is not ours to
  claim. Never pool/average as the final word - each event individually.
- git = code, S3 = data. AWS creds are SECRETS. Committer noreply@anthropic.com / Claude. No emojis.
- Brain merges are PROPOSAL FILES + adjudication (incumbents byte-identical), never a direct edit.
