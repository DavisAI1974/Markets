# DROP-IN BOX - S108 (start a FRESH session with this)

## 0. Branch + read order (do this FIRST)

```bash
git fetch origin claude/kalshi-agents-coordinator-guard-1175nr
git checkout -B claude/kalshi-agents-coordinator-guard-1175nr origin/claude/kalshi-agents-coordinator-guard-1175nr
git log --oneline -1     # expect the S107 close-out commit
```

Read in order: `SESSION_HANDOFF_2026-08-01_S107.md` (in full) -> `research/kalshi/agents/README.md`
-> `CLAUDE.md` header.

## 1. THE CONTAINER HAS NO DATA. RESTORE IT FIRST - ONE COMMAND.

`data/` is gitignored and does NOT survive the session. The committed state/forecast artifacts DO.
S107 opened with an empty `data/` and burned time rediscovering the S3 prefix mapping - that is now
a script. Do this before anything else:

```bash
pip install numpy pandas matplotlib boto3 databento
mkdir -p ~/.aws && printf '[default]\naws_access_key_id = <ID>\naws_secret_access_key = <SECRET>\n' > ~/.aws/credentials && chmod 600 ~/.aws/credentials
printf 'AWS_ACCESS_KEY_ID=<ID>\nAWS_SECRET_ACCESS_KEY=<SECRET>\nAWS_DEFAULT_REGION=us-east-2\n' > scratchpad/aws.env && chmod 600 scratchpad/aws.env
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY python research/kalshi/restore_substrate.py
python research/kalshi/state_health.py        # G21/G22 must PASS
```

**ALWAYS run AWS/boto3 via `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY`** - the container
injects PLACEHOLDER creds that override `~/.aws/credentials`. Keys are SECRETS: `~/.aws/credentials`
and `scratchpad/aws.env` only, never the repo. Databento key -> `scratchpad/bento.env`.

`restore_substrate.py` also REBUILDS `vol_regime` (it is derived from the tape, not stored). Two
mappings are not the obvious one and caused a silent hole in S107:
`weather/nws_temp/ -> data/nws_temp` (NOT `data/weather/nws_temp`), `consensus/ ->
data/storage_consensus`, `eia/ -> data/eia_surprise.json` (a FILE).

## 2. THE STANDING ORDER (Greg, load-bearing)

**One agent regime. The blind IS the refine engine** (`mbo_refine_shared.md` +
`mbo_specialist_{A..E}.md`), **with the price curve masked in the DATA and NOTHING else different.**
"THAT ONE THING IS LITERALLY IT... do not change anything except for that one thing."

- The mask is a BUILT-IN PARAMETER: `decision_state(days, mask_after=YYYYMMDD)`.
- **Do NOT edit agent files, coordinators, or brain reasoning to make something work.** If a run
  cannot proceed without a change, STOP AND ASK. No silent turning-off - and no silent turning-ON
  either (adding an input the config does not carry is the same class of error).
- `verify_gold.py` hard-fails any run on a tampered vault. Keep it passing.

## 3. STATE

- **Brain s103.2, 62 plays.** Backup `ng_brain_s103.1_backup.json`.
- **G19 COMPLETE**: blind 4/10 err 939 -> refine r1 10/10 err 79 -> **refine r2 10/10 err 34**.
- **G20 BLIND DONE AND SCORED: 6/10 dir, mean abs err 788** (`forecasts/grp20.json`, engine files
  archived at `forecasts/g20_blind_round1/`, render
  `renders/ng_refine_s95/g20_blind_vs_actual.png`).
  `0525 A +180/+30 | 0526 C -280/-190 | 0527 C -500/+610 | 0528 D +150/+2100 | 0529 E -380/-160 |
  0601 B +350/-990 | 0602 C +250/-80 | 0603 C +480/+750 | 0604 D -450/+1130 | 0605 E -500/-1340`
  (guess/actual).
  **The number that matters: FORWARD-CURVE DRIFT -2560** - block cum blind -700 vs actual +1860, so
  the blind ended at 2.964 against 3.220. 6/10 flatters it. **G20's refine is the next run.**
- **G21, G22 staged and PASSING `state_health`.**
- **G23 BLOCKED - do NOT run it.** `weather` genuinely missing 2026-07-14..07-17 (the degree-day
  store ends 07-13). Extend `nws_temp` four days, restage, confirm the gate passes.

## 4. DO THIS, IN ORDER

1. **G20 REFINE** - the blind is done and scored (6/10, err 788, forward-curve -2560). Same sequenced
   spawn (C+D+E -> A -> B), unblinded: the refine additionally gets `g20_mbo_evidence.json` and that
   is the ONLY data difference. Coordinate with `group_coordinate_refine.py g20`, PRINT the render,
   HARD PAUSE for Greg, then round 2 (`group_he24_he1_handoff.py g20` - `--source` is now wired and
   the refine uses the default `actual`), coordinate `--r2`, PRINT, adjudicate, merge on Greg's go.
   **Two things the refine must explain, and they are DIFFERENT failures - do not merge them:**
   (a) the two EIA Thursdays are 3,530 of the 7,880 total error (0528 +2100 actual vs +150; 0604
   +1130 vs -450), and 0528 is the first clean print-day read since the calendar was corrected C->D;
   (b) B's 0601 (+350 vs -990) missed even though the G19 cum-0 structural fix HELD - B built
   inherited cum properly and still called it wrong, so that is a reasoning miss sitting on top of a
   fixed mechanism, not a repeat of the old flaw.
   Bridging note for any future blind: the engine emits `expected_magnitude_usd` / `path_p50_curve`
   and `group_coordinate_blind.py` reads `guessed_net_usd` / `path_distribution` - reformat VERBATIM
   in a scratchpad alias (numbers untouched, `handoff_out` carried through for the Friday sign-off).
   NOT a code change. `group_coordinate_refine.py` speaks the engine schema natively.
3. **G21** - the first group to run with the full kitchen sink actually intact (storage + vol_regime
   + weather + the corrected size-weighted `big_print_b_share` all live for the first time since
   G16). **This is the point of the walk, not a complication in it (Greg, S107): we are improving
   the forecaster group over group, not running a controlled experiment.** A better input set is a
   better forecaster - do not hedge the result or hold a group back to preserve a comparison.
   The ONE thing to keep straight is ATTRIBUTION IN THE POST-MORTEM: when a day improves, say
   whether the brain earned it or a restored input did, so a merge does not bank a data fix as
   evidence for a play. That is about not writing false lessons into the brain - nothing to do with
   comparability.
4. The open items in the S107 handoff, in this order of value: per-day blind state slices (the mask
   is currently unenforced across days), the Sunday prior-session inconsistency, the live
   orchestrator, the options strike-ladder scale bug, the `nws_temp` extension for G23.
5. **DO NOT ROTATE THE KEYS.** Standing decision (Greg, S107): *"the keys won't rotate while we're
   running the groups."* Both the AWS pair and the Databento key will need rotating eventually -
   **after the walk, not during it.** Rotating mid-walk breaks S3 and Databento access and stalls
   every staged group and every `restore_substrate` run. This is a DECISION, not a pending task:
   do not act on it and do not re-raise it each session. Just handle the keys properly -
   `~/.aws/credentials`, `scratchpad/aws.env`, `scratchpad/bento.env`, all chmod 600, never in the
   repo, never echoed into chat or a commit.

## 5. RUN MECHANICS (turnkey - do not re-author)

- **Sequenced spawn, BOTH passes**: wave 1 = C + D + E parallel -> wave 2 = A -> wave 3 = B. Model
  opus. A INFORMS, B DECIDES, B owns the Monday number.
- **A IS A FULL OWNER** now (S107) - both coordinators select A like anyone else. On a day A owns it
  must emit a `days` array, not only its bridge block.
- **Blind input set = brain + the price-masked `grp<N>_state.json` ONLY.** No `grp<N>.json` on a
  first pass, no `g<N>_mbo_evidence.json`, no actual, no raw tape. Refine additionally gets
  `g<N>_mbo_evidence.json` - that is the ONLY data difference.
- **Seam day = a REAL, TRADED, SCORED day** on the post-roll leg; only the overnight GAP voids.
- **Friday sign-off**: the coordinator HARD-REFUSES any weekend-feeding Friday whose posterior lacks
  `handoff_out`.
- **Check the calendar against the STATE, not the config.** S107: `group_config` claimed the G20 EIA
  print shifted to Friday; `flow_calendar` said otherwise and was right, and `owner_map` derives
  ownership from that list. A specialist caught it by stopping. The state feed wins.

## 6. WHAT S107 CHANGED THAT YOU WILL NOTICE

- `state_health.py` refuses to stage a group with an empty block. **Do not route around it** - fix
  the store or declare the block optional, deliberately.
- `firehose_present {mbo_flow, l1_book}` per day, `flow_read_error` and `frozen_structure_stale` at
  the day's top level. A degraded input now STATES itself instead of looking like a mask.
- `big_print_b_share` is the SIZE-WEIGHTED series, labelled by `big_print_b_share_basis`. Threshold
  intuition formed before S107 was formed on a different measurement.
- `vol_regime` is populated again for the first time since G16, and its span now follows the tape.
- Renders: one polyline per block, correct terminal point, the blind curve actually drawn, live
  brain version in the title.
- `group_he24_he1_handoff.py --source {actual|blind}` is wired, and the blind path no longer leaks
  the actual tape into the handoff.

## 7. STANDING DOCTRINE

- **Scoreboard = FORWARD-CURVE error / P&L, not daily hit-rate.**
- Kitchen sink for both agents; the blind's ONLY mask is the price curve.
- One group = two weeks. Stage all, RUN ONE at a time.
- Group windows: Sunday reopen -> the SECOND Friday. FOCUS = FRIDAY AND MONDAY. Target: honest
  under-100 every day.
- Magnitudes DERIVED from measurable state, never fitted; a reactive tail is not ours to claim.
- Never pool/average as the final word - each event individually.
- git = code, S3 = data, `data/` disposable. Committer noreply@anthropic.com / Claude. No emojis.
- Brain merges are PROPOSAL FILES + adjudication (incumbents byte-identical), never a direct edit.
- **A silently empty input is the recurring enemy.** Six in one session. When something reads as
  "no data", prove it is not a missing file before reasoning over it.
