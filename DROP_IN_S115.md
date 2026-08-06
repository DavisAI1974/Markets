# DROP-IN BOX — S115

**BRANCH: `claude/kalshi-agents-coordinator-guard-sg0n15`**
**TIP AT HANDOFF: run `git log --oneline -1` and confirm it is the S114 docs commit or later.**
**BRAIN: s105.9, 90 plays. DECISIONS: 48. G24 BLIND IS RUN AND SCORED. THE G24 REFINE IS YOUR OPENER.**

---

## 0. FIRST FOUR COMMANDS, IN ORDER

```
git fetch origin claude/kalshi-agents-coordinator-guard-sg0n15
git checkout -B claude/kalshi-agents-coordinator-guard-sg0n15 origin/claude/kalshi-agents-coordinator-guard-sg0n15
git log --oneline -1
python research/kalshi/restore_substrate.py
```

**GREG NOW ONLY PASTES TWO VALUES: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.** Put them in
`~/.config/markets/env` (chmod 600, outside the repo). **`DATABENTO_API_KEY` and `EIA_API_KEY` are
retrieved AUTOMATICALLY** from AWS SSM Parameter Store (`/markets/*`, SecureString, our own
account) the first time `creds.get()` asks for them — S114. The AWS pair is deliberately NOT in
SSM: it is the bootstrap that reads SSM. After any paste or rotation run
`python research/kalshi/creds.py --sync-ssm`, which pushes and verifies by READ-BACK. Nothing else
survives the container. `creds.py` resolves them; **`creds.aws_client()` is the ONLY sanctioned way
to build a boto3 client** — the harness injects a `proxy-injected` placeholder that shadows the real
AWS pair, and a bare `boto3.client()` fails with `InvalidClientTokenId` on a known-good key. Full
inventory and the per-key verification table: `KEYS.md`. **Keys do NOT rotate during the walk (D1).**

**The data plane on S3 is CURRENT as of S114 close and was verified by reading each store BACK from
S3** — `model_disagreement`, `storage_regional`, `vol_regime`, all five COT books, `eia_surprise`,
`gefs_forcing`, and 9 `ng_l1` sessions. Restore gives you the FIXED data, not the pre-fix data.

---

## 1. THE JOB: RUN THE G24 REFINE

```
# 1. archive the blind FIRST - merge_perday writes the CANONICAL specialist filenames (NC-4)
python research/kalshi/archive_blind.py g24

# 2. re-stage g24 UNMASKED for the refine (grp24_state.json is the blind's IMMUTABLE record)
#    a fresh build is 0 hard / 3 soft
python research/kalshi/stage_group.py g24            # confirm the refine/unmasked path

# 3. spawn per RFN-1, one specialist per day, into forecasts/g24_refine_perday/
python research/kalshi/spawn.py emit RFN-1 g24 --day <DAY> --spec <X>

# 4. assemble, score, render
python research/kalshi/merge_perday.py g24 --perday-dir g24_refine_perday
python research/kalshi/group_coordinate_refine.py g24
python research/kalshi/blind_score_nonpooled.py g24
```

**THE REFINE DOES NOT NEED THE BLIND WALL (D45, Greg).** Do not gate, delay or constrain it on
blind-wall grounds. Stage unmasked.

**THE WAVE ORDER STILL BINDS.** E (Fridays) -> A (weekend bridge, BLD-2/RFN equivalent) -> B
(Mondays). g24's owner map has **no A day**, which is correct — A produces a BRIDGE artifact, not a
session — and that is exactly how wave 2 got skipped in the blind. `spawn` now STOPS on a Monday
whose in-block Friday has no bridge; pass `--no-bridge` only to declare the deviation on the record.

**WHAT THE REFINE SHOULD BE POINTED AT.** The blind's dominant failure was not direction (6/10, its
best of the walk) — it was **MAGNITUDE: 0.29x of realized, under on 8 of 10 days**. A refine that
returns 10/10 direction with the same 0.29x sizing has not fixed the thing that is wrong.

---

## 2. WHAT CHANGED UNDER YOU AT S114 (so you do not re-derive it)

New/changed SERVED state fields the refine specialists will see:

| field | what it is |
|---|---|
| `weather_forcing_forecast` | **NEW.** Forward wind + solar, 31-member GEFS density, per day. Wind and solar NEVER summed. |
| `scored_leg` | **NEW.** Which contract this day is scored on + a post-seam structural-mask caveat. |
| `stor_surprise_basis` | **NEW.** The report date, actual vs seasonal expectation, the formula, what the sign means. |
| `grid_stack.*_share_chg_7d` | **NEW.** Gas/wind/solar/hydro SHARE deltas. Sign can differ from the MWh delta. |
| `tape_conditions.phase_bounds_et` | **NEW.** The phase clock. Phase 2 is NOT reliably the US session. |
| `vol_regime.*_prev_full_session_*`, `*_prev_is_stub`, `*_window_excluded_stub_sessions` | **NEW.** Stub-aware windows; sigma_20 moved +12%. |
| `options_surface.months[].days_to_opex` | **FIXED.** Now relives per day (8/5/1/0/-3), keeps `_frozen`, flags negatives. |
| `freeze_risk` threshold counts | **FIXED.** Null + named reason where there is no temperature coverage. |
| `_state_build` | **NEW top-level.** The state's own vintage, so a new required block cannot turn old states red. |
| `firehose_present.l1_book` | Now TRUE across the block (was False on 8 of 10 days). |

**PLAY STATUS CHANGED UNDER YOU — READ THIS BEFORE THE REFINE.** Nine plays were demoted
PROVISIONAL -> **`DEGENERATE`** on their own opening verdict. `DEGENERATE` does **not** mean the
claim is false (that is `REFUTED`) — it means the TRIGGER carries no information as written (the
D23 disease: fires always, never, or on a bar sited outside its own distribution). **The mechanism
may be worth keeping; the repair is to re-site the bar.** A specialist meeting one must stand it
down and NAME the status — and may cite its mechanism only by re-deriving the trigger and saying so.
Every instance now carries `do` / `dont` / `observation`, and `fire_record` counts do/dont ONLY, so
a play merged-but-never-run shows n=0 rather than letting its instance count look like a record.
Full reasoning: `reasoning_method.what_a_play_status_means_S114` in the brain.

Brain view additions (GENERATED, never a second copy): `instrument_priors` (53 plays' measured
track records, surfaced), `live_verdict` (22 plays' own refuting line hoisted above the call),
`evaluability` (A-46 — every parsed condition resolved against YOUR slice).

---

## 3. OPEN, AND THE FIRST TWO NEED GREG

1. **THE BLIND ANCHOR / BLIND SUBDIRECTORY — Greg deferred this to S115 explicitly.**
   `g24_actual.json`, `g24_exit_states.json` and `g24_mbo_evidence.json` sit in the SAME DIRECTORY as
   the anchor a blind specialist is told to read. Named as a hazard in S109, still live; the only
   defence in force is that the specialist does not tab-complete. Blind-only, so it does not block
   the refine.
2. **IS OPEN INTEREST OVER-MASKED?** It is exchange-published and is not a price, but the one-shot
   mask freezes it through roll week — the one week OI migration is the informative series. A real
   doctrinal question, not a bug.
3. `weather_forecast_cycle` nets 18Z/00Z/06Z into ONE delta vector — a specialist can derive the
   total add but not WHEN it arrived, so five of twelve path points are a timing judgment where a
   per-cycle breakdown would make them arithmetic.
4. `storage_vintage` is 5 months stale (STEO archived workbooks, never pulled).
5. The unwalked head **2025-07-22 -> 2025-09-05** (34 sessions, ~3 blocks) is the only remaining walk
   gap. **G25 is impossible** — only 3 of its 10 sessions have happened.
6. The **Workflow tool's subagents had a broken tool layer** all through S114 (9 agents, zero
   successful tool calls, permission handler stripping required params). The **`Agent` tool worked
   fine** in the same session — 10 blind specialists ran. If you need fan-out, use `Agent`.

---

## 4. STANDING RULES THAT BIT SOMEONE THIS SESSION

- **D47 — a store rebuilt in a session is not a fix until it is on S3, verified by reading it BACK.**
  At S114 close, S3 still held pre-fix copies of four stores and `eia_surprise.json` was absent
  entirely. A fresh session at that moment would have silently undone the whole day.
- **D34 / A-7 — edit the STORE, never the render.** `store/sop_templates.json` is the source;
  `agents/RUN_SOP.md`'s appendix is generated. I edited the markdown directly and had to revert.
  `python research/kalshi/store.py check` catches it.
- **NC-3 — a test that never produced the guard's OUTPUT did not test the guard.** Every guard added
  this session was negative-tested in both directions, and doing that is what caught the
  `live_verdict` false-positive machine before it shipped.
- **D37 — the observation and the story explaining it are independent.** The
  `weekend_gap_wide_band_emission` sigma band was struck (it holds on 1 of its own 4 instances) while
  the observation it rests on survives.
