# SESSION HANDOFF - 2026-08-01, S107 (G19 round 2 done; SIX silent data holes found and closed; brain s103.2)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr`. Brain: **s103.1 -> s103.2, 62 plays**
(Greg-approved). This session finished G19 through refine round 2, then spent most of its time on
something nobody was looking for: **six separate decision-state blocks that were silently EMPTY**,
each one reading downstream exactly like a deliberate price mask.

## THE HEADLINE

- **G19 refine round 2: 10/10 dir, mean abs err 34** (blind 939 -> r1 79 -> **r2 34**). Better than
  the G15/G17 precedent (72->66, 24->11). **Zero direction changes anywhere in the block** - all five
  specialists filed an empty `direction_changes_from_r1`. Every day still lands honestly UNDER actual.
- **SIX SILENT DATA HOLES.** Every one presented as a null or `{"masked_one_shot": true, "value":
  null}` - indistinguishable from a deliberate mask or from "the market had no data". Three separate
  mechanisms produce that same null: `_load_json` returns `{}` for a missing file, feeds return `None`
  for no-coverage, and the one-shot mask emits `{"value": null}` when it has nothing to freeze.
- **`vol_regime` had been DEAD SINCE G16** - a hard-coded `SPAN_END = "2026-03-13"`. That is the
  module built to condition MAGNITUDE, which the brain itself calls the walk's dominant residual.
  Five groups' magnitudes were scaled without it.

## THE SIX HOLES (all closed except the last, which is correctly BLOCKING G23)

| # | block | who it hit | cause | state |
|---|-------|-----------|-------|-------|
| 1 | `storage` / `stor_surprise` | G18-G21 | `data/eia_surprise.json` absent | FIXED |
| 2 | `tape_conditions` signed flow / `l1_book` | G20/G21 as staged | stores absent at stage time | FIXED |
| 3 | `options_surface` | G16, G20, G21 | `options_ng/surface.json.gz` not pulled | FIXED |
| 4 | `vol_regime` | **every group from G16** | hard-coded `SPAN_END` | FIXED at the root |
| 5 | `squeeze_watch` frozen on an EXPIRED front | any block where the front expires inside it | one-shot freeze outlives the contract | now DECLARES itself |
| 6 | `weather` | **every staged group** | path mismatch: harness reads `data/nws_temp/`, the pull landed it at `data/weather/nws_temp/` | FIXED |

**#4 was fixed at the root, not by bumping the date**: `SPAN_END` is now a FLOOR and the build end is
DERIVED from the tape on disk, so a hard-coded horizon cannot starve a future group again. Store
rebuilt from 223 sessions (2025-11-02..2026-07-20); `--selftest` passes its blind-wall audit.

**#5 does not un-mask anything** - `flow_calendar` carries the live front and is never masked, so the
discrepancy is detectable without price. `decision_state` now sets `frozen_front_expired` on
`contract_structure` and `squeeze_watch` plus a day-level `frozen_structure_stale`.

## THE BUILD THAT STOPS A SEVENTH: `state_health.py`

Wired into `stage_group` AFTER the state is built and BEFORE actual/evidence. **A block may be empty
only if something DECLARED it may be.** Anything else is a hard failure at stage time - not a
discovery in the post-mortem, where a data hole gets written into the brain as a reasoning lesson.

- `REQUIRED_EVERY_DAY` (21 blocks) - hard fail.
- `MASKED_MUST_HAVE_FROZEN_VALUE` (the 5 price-derived blocks) - masked is fine; masked with
  **nothing behind it** is the vol_regime failure and is a hard fail.
- `EXPECTED_SPARSE` (holiday) - never a failure.
- Declared degradations (L1 absent on a thin Sunday reopen, a frozen front past expiry) = SOFT.

Current: **G21 PASS, G22 PASS, G23 REFUSED** (see below). Run it any time:
`python research/kalshi/state_health.py`.

## `restore_substrate.py` - the container does NOT keep data

git = code + the committed state/forecast artifacts. S3 = data. `data/` is gitignored and **dies with
the container** - S107 opened with an empty `data/` and burned time rediscovering the prefix mapping.
One command now restores the whole plane and rebuilds `vol_regime` (which is DERIVED, not stored):

```bash
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY python research/kalshi/restore_substrate.py
```

Two mappings are NOT the obvious one and are the reason hole #6 existed:
- `weather/nws_temp/` -> **`data/nws_temp`** (NOT `data/weather/nws_temp`)
- `consensus/` -> `data/storage_consensus`; `eia/` -> `data/eia_surprise.json` (a FILE)

## OTHER FIXES THIS SESSION

**Three firehose plumbing defects** (the S107 list, all closed):
- **#3 was the material one**: `big_print_b_share` was the WRONG SERIES. The copy-through omitted it,
  so the COUNT-based value shadowed flow_read's SIZE-WEIGHTED one under the same key. The G19
  post-mortem concluded the 0.55 gate "never fires, block max 0.537" - **that 0.537 was the count
  series; the size-weighted series reaches 0.550 and the gate fires.** The gate was not
  mis-specified, it was fed the wrong instrument. They are different measurements, not a scale shift
  (some sessions read lower size-weighted).
- **#1** per-session `firehose_present {mbo_flow, l1_book}` + a stderr line naming the missing path.
  Negative-tested. It earned itself on its first production run, correctly flagging L1 absent on
  Sunday reopens.
- **#2** `firehose_present` / `flow_read_error` hoisted to the day's top level.

**A price leak in the handoff chain, found while wiring `--source`** (Greg approved the CLI fix; the
leak came with it). `group_he24_he1_handoff.py:138` called `exit_state(gid, pd_)` UNCONDITIONALLY -
a fresh read of the ACTUAL tape - so a `--source blind` run would have carried the REALIZED close,
open, day-move and signed flow into the blind. The mask violated by the very mechanism meant to give
the blind its chain state. Also guarded a second latent leak (`prior_owner_verdict` reading the
refine's posterior from a blind run). Verified: the blind chain now carries forecast closes and cum,
`source: "forecast"`, null signed flow, and **no field matching the actual**. Refine path proven
BYTE-IDENTICAL.

**Three render defects**, all in code duplicated across both coordinators - consolidated into
`render_util.py`:
- the **blind curve was never drawn** (lookup used `path_distribution`; `grp<n>.json` stores
  `path_p50`) - the chart's whole point is blind-vs-refine-vs-price;
- the **terminal-point fold**: `h >= 18` sent the trailing 18/20 back a day, so the day's CLOSING
  point - the number being scored - was drawn ~22h early on top of its own open;
- **one polyline per day** instead of per block.
- Both coordinators also had `brain_version "s102.8"` HARD CODED into the title and emitted JSON, so
  every artifact since that release was mislabelled. Now read live.

**A is a full coordinator owner.** `agents/README.md` always said A owns holiday/extended-weekend
reopens; both coordinators carried a TODO that hard-failed the ENTIRE block on any A-owned day. It
occurred (G20 Memorial Day 0525, a real thin session). Every other guard unchanged. Regression:
G19 r2 re-coordinates byte-identical.

**G20 calendar correction, caught in pre-flight by specialist D stopping on its own.** `eia_thursdays`
claimed the print shifted Thu->Fri for Memorial Day. The EIA feed says `is_eia_print_day` TRUE on
20260528, `shifted: false`. A **Monday** holiday does not move the Thursday gas report. `owner_map`
derives D's ownership from that list, so D's EIA lens was pointed at a non-print Friday while the real
print was handled as a core day. Corrected: 0528 C->D, 0529 D->E. G21/G22/G23 checked, all match.
A **second copy** of the same error lived in `group_config.HOLIDAYS` (`eia_shift: "20260529"`) and was
propagating into the ACTUAL file via `group_actual.py:63` - also corrected.

**Anchor last-hour bits** supplied for G20 (+1) and G21/G22/G23 (+1/-1/-1). G22 is the subtle one:
its anchor CLOSE comes from G21, so the last hour must be read on G21's NGN26 leg, not its own NGQ26.

## BRAIN MERGE s103.1 -> s103.2 (62 plays), Greg-approved

Adjudicated: **60/61 incumbents byte-identical**, all non-play sections byte-identical. Backup
`ng_brain_s103.1_backup.json`; proposal preserved.

1. `direction.flow_conviction_sign_gate` - **struck** "This sign gate REPLACES big_print_b_share>=0.55
   as the direction discriminator" and withdrew the evidence built on the count-based 0.537. The play
   is KEPT in full. It fails twice: the evidence was the shadowed series, AND flow_conviction requires
   realized price (refine-only) while `big_print_b_share` is open-time and is the BLIND's instrument
   in the same role. Complements on different channels, never substitutes. Letting it stand would have
   left the blind with nothing in that slot - which mattered urgently, because G20 is a blind run.
2. NEW `flow.big_print_bshare_thin_tape_guard`, measured on 204 sessions:
   - **season: NO.** Fire rate flat - winter 25.3% / shoulder 29.2% / summer 29.7%; equal-rate bars
     0.524 / 0.550 / 0.553.
   - **tape thickness: YES.** Thinnest big-print quartile carries double the dispersion (sd 0.255 at
     median 9 prints vs 0.132/0.120/0.127); `corr(|b-0.5|, log n) = -0.465`. Below ~20 big prints
     raise to ~0.60 or stand down. Per-quartile spread 7.9pp -> 4.5pp. Recorded as MODEST.
   - **NEGATIVE RESULT RECORDED**: the smooth `0.5 + k/sqrt(n)` form was tested FIRST and lost badly
     at every k (16.3-22.4pp vs 7.9pp fixed) - it over-corrects the thick tail and ends up firing MORE
     on the thickest quartile than the thinnest. Written into the play so it is not re-proposed.
   - **Forward evidence already, on its first ride**: C, D, E and A EACH independently found that
     Memorial Day 20260525 (0.599 on 13 big prints) is the block's only reading clearing 0.55 and that
     the ~0.60 bar correctly kills it, disarming a spurious `accumulation_arm_turn` fire. Four lenses,
     one day, same verdict. D generalized it: every holiday block feeds exactly one thin-sample session
     into that window.
   - Study committed reproducible: `research/kalshi/bshare_threshold_study.py`.

## STATE OF THE WALK

- **G19 COMPLETE**: blind 4/10 err 939 -> refine r1 10/10 err 79 -> **refine r2 10/10 err 34**.
- **G20 BLIND: NINE of ten days committed, NOT coordinated, NO score, NO render.** The session closed
  with specialist B still running on its single day, 20260601. The coordinator guard hard-fails on a
  missing owner, so the block cannot be assembled until B's number exists. What is on disk and
  committed:

  ```
  0525 A  +180      0529 E  -380     0603 C  +480
  0526 C  -280      0601 B  MISSING  0604 D  -450
  0527 C  -500      0602 C  +250     0605 E  -500
  0528 D  +150
  ```

  To finish: re-run specialist B for 20260601 ONLY (wave 3, consuming A's committed bridge in
  `grp20_mbo_specialist_A.json` and E's 0529 `handoff_out`), then bridge + coordinate + render per
  the drop-in's step 1. Everything else G20 needs is committed and does not need re-running.
- **G21, G22 staged and PASSING state_health.**
- **G23 is BLOCKED and must NOT be run**: `weather` genuinely missing 2026-07-14..07-17 (the
  degree-day store ends 07-13). A real data gap, not a path bug. The gate is holding it back
  correctly. Its state file exists but the group is NOT staged (actual/evidence not rebuilt).
  Extend `nws_temp` four days, restage, and it should pass.

## OPEN / NOT DONE

1. **Per-day blind state slices.** E's finding: `grp<N>_state.json` is BLOCK-WIDE, so a multi-day
   owner reading its later day necessarily has the earlier days' tapes in view. E self-policed and
   said the thing that matters: *a block-wide blind state can ASK for per-day open-time hygiene but
   cannot ENFORCE it.* "We rely on the agent not to look" is not a mask. Distinct from the price mask
   and unenforced anywhere.
2. **Sunday "prior session" inconsistency.** `_tape_conditions_block` walks back to the first day with
   a tape file, so a Monday's "prior session" resolves to the ~2h SUNDAY reopen when a Sunday file
   exists (G22/G23) and to the full FRIDAY when it does not (G20/G21). Same field name, materially
   different object. Not a leak (pre-decision reopen flow is granted by the doctrine) but it rubs
   against the Sunday fold.
3. **Live orchestrator** (the S105 escalation clause). A's OWN day (0525) depends only on the anchor,
   not on E, yet the fixed E->A->B order serializes it. ~10 min of avoidable wall-clock per group.
4. **`options_surface` strike ladder is not on the contract's price scale** (A, F2): top-OI strikes
   0.25-0.35 against a 2.907 front. The pin read was NOT COMPUTABLE on the one day it mattered
   (opex T-1). A substituted nothing.
5. **`nws_temp` extension** for G23 (4 days).
6. **ROTATE BOTH KEYS.** AWS and now the Databento key were both photographed into chat. Deferred by
   Greg until the groups are done - still outstanding.

## DOCTRINE REMINDERS (unchanged)

- Scoreboard = FORWARD-CURVE error / P&L, not daily direction hit-rate.
- One group = two weeks; stage all, RUN ONE at a time.
- git = code, S3 = data, `data/` is disposable. Committer noreply@anthropic.com. No emojis.
- Never pool/average as the final word; each event individually.
- Magnitudes DERIVED, never fitted; a reactive tail is not ours to claim.
