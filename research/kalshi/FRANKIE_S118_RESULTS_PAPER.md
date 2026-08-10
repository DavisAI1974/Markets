# Agent Frankie — S118 run: what it did, why, and what it measured

**Session S118 · branch `claude/kalshi-agents-coordinator-guard-sg0n15` · Frankie code at
`chatgpt/agent-frankie-s117` @ `3a72fee`**
Complete machine-readable record: `research/kalshi/records/S118/FRANKIE_S118_COMPLETE_RUN.json`
(every forecast, its reasoning, its outcome, its benchmarks).
Written for an external reader. **The registry (`OPEN_ITEMS.md`) is truth where this disagrees.**

---

## 0. READ THIS BEFORE THE RESULTS — four limits that bound everything below

1. **ONE POINT PER DAY.** `path_p50_curve` in every posterior is a **linear interpolation of the
   single net figure already decided** — literally `[open, open+net*0.45, open+net*0.8, close]`. It
   has four entries and no intraday content: no ET hours, no onset, no turn, no shape. The canonical
   contract specifies `[[et_hr, cum_usd], ...]` **on the 2-hourly clock from the 20:00 reopen**.
   **17 of the contract's 20 day-level fields were never emitted** — including
   `expected_magnitude_band_usd`, `onset_time_et`, `turn_time_et`, `stand_down_reasons`,
   `evidence_used`, `evidence_rejected`. Registered as **A-86**.
2. **It passed validation anyway**, because `_validate_day` checks that the curve is a *list of
   length ≥ 2*. A straight line satisfies that. A gate existing is not a gate passing (D51).
3. **This is NOT A-67 evidence.** g18/g19/g20 are **walked** groups whose lessons are already merged
   into the brain. This run validates contracts and plumbing. The architecture test needs an unseen
   block.
4. **The reasoning agent is Claude (opus-5)**, running on the runner's resume path — no API backend
   is credentialed on this host. **Arm B's agent had already seen arm A's results.** Declared, not
   hidden.

---

## 1. What was run

Three groups, thirty forecast days, plus three E→A→B weekend bridges. Two arms differing in exactly
one thing.

| arm | groups | sizing passage |
|---|---|---|
| **A** | g18, g19 | **baseline** — the shared role file's *"Target honest under-100 USD error per day"* |
| **B** | g20 | **varied** — that target withdrawn; size what the drivers support, sum independent drivers, scoreboard is the forward curve against named benchmarks |

Everything else was held: same brain, same causal slices, same contracts, same harness, same agent.

Two defects had to be fixed before any of it was meaningful:

- **A-80** — the runner served **zero plays** on all 20 days while its preflight reported
  `PACKETS_CAUSAL`. Three stacked shape assumptions against `brain_view` (`play_index` is an
  envelope with rows one level down; `plays` is a list keyed by `id`; the row's key is `play`), each
  failing *open*. Fixed: served_plays 0 → 33.
- **A-82** — the leak guard then hard-stopped on `actual_day_move_usd` appearing in a play's
  evidence about **g17's 2026-04-22**, a prior walked group. Swept all 20 days: every outcome-token
  occurrence was attached only to dates *before* its group's window — 0 reached into or past it.
  Rescoped to **dates, not names**; file tokens stay absolute; an undated realized value **fails
  closed**. Negative-tested 7/7 — it still fires on own-day, later-day, both forbidden files and
  undated values.

---

## 2. Results, per event — never averaged

D4/D37: no pooled rate is reported, and the largest actual moves are named individually, because
those are the events that decide whether a candidate helped.

### g18 — arm A. A real loss, concentrated where it costs.

Improved 3/10, worsened 7/10, and **worse on 6 of its 8 largest moves**.

| day | actual | Frankie | old blind | verdict |
|---|---|---|---|---|
| 04-30 | **+1,230** | +330 | +400 | worse |
| 05-05 | −830 | −200 | −400 | worse |
| 05-07 | +730 | +90 | −120 | better |
| 05-04 | +610 | −280 | −130 | worse |
| 05-06 | −530 | +220 | +100 | worse |

**04-30 is the emblem.** It was the block's strongest coherent buy signal — the only `b_share` above
0.50, `signed_flow` +7,783 (twice any other day), big prints at 0.621 clearing the gate. The
direction was called right and **the size was 27% of the move**.

**05-04 was self-inflicted.** A's weekend bridge read the Friday exit as a give-back and handed B a
DOWN bias; the market went +610. The bridge fed the error forward — which is the S104 cascade
finding reproduced.

### g19 — arm A. A real improvement, also concentrated on the big days.

Improved 7/10, **better on 5 of its 8 largest**.

| day | actual | Frankie | old blind | verdict |
|---|---|---|---|---|
| 05-11 | **+1,740** | −160 | −450 | better (both bad) |
| 05-20 | −1,050 | −200 | +200 | better |
| 05-18 | +660 | **+300** | **−550** | better |
| 05-22 | −990 | −250 | −190 | better |
| 05-12 | −960 | +120 | −200 | worse |

**05-18 is the best event of the run.** Forecast `gw_cdd` tripled (3.99 → 10.33) and the regime
flipped `hard_cool` — a genuine mid-May cooling ramp. The old harness called −550 into a +660;
Frankie called +300. Error 1,210 → 360.

### g20 — arm B. Bigger calls, and no better.

Improved 5/10, worsened 5/10.

| day | actual | Frankie | old blind | verdict |
|---|---|---|---|---|
| 05-28 | **+2,100** | −520 | +150 | worse |
| 06-05 | −1,340 | −560 | −500 | better |
| 06-04 | +1,130 | −400 | −450 | better |
| 06-01 | −990 | +250 | +350 | better |
| 05-27 | +610 | −330 | −500 | better |

---

## 3. The two findings that matter

### 3.1 The under-emission is INSTRUCTIONAL (A-83, closed)

The baseline passage tells the forecaster to *"target honest under-100 USD error per day"* on blocks
whose realized moves run several hundred. **That target is only reliably reachable by emitting near
zero**, because a small guess has a bounded error whether or not it is right. It cannot distinguish
a calibrated small call from a timid one, and it pays for timidity.

Withdraw it and the numbers move immediately:

| | \|guess\| p50 | MAX | events ≥ 400 | events < 200 |
|---|---|---|---|---|
| arm A (n=20) | 200 | 330 | **0 of 20** | 9 of 20 |
| arm B (n=10) | 400 | 560 | **5 of 10** | 0 of 10 |

### 3.2 …and it did not help, because size carries no information (A-85, open, ESSENTIAL)

Sort each arm's events by `|actual|` and read `|guess|` beside it:

| arm | smallest-half `|actual|` → `|guess|` | largest-half → `|guess|` |
|---|---|---|
| A | 100 … 270 | **90 … 330** |
| B | 240 … 420 | **250 … 560** |

**The ranges overlap almost completely in both arms.** The emitted size does not separate a 30 USD
day from a 2,100 USD day. Arm B overshot the quiet days — 05-25 actual **30**, called 240 (8.00x);
06-02 actual **80**, called 380 (4.75x) — and still undershot the large ones (05-28 at 0.25x on a
+2,100 day).

**Under-emission was the symptom. The disease is that magnitude is not being forecast at all** — a
roughly constant band is emitted regardless of the day, and varying the passage moved the band up
without touching its discrimination. That is the direct argument for **A-60/A-63**: the band should
be the **empirical spread of the matched cohort**, not a number the agent produces. It is also why
A-86 matters — a forecaster with no magnitude signal certainly has no intraday shape signal.

---

## 4. A rule that lost, and lost cleanly (A-84)

On arm A, the two days where the tape and the forecast weather disagreed hardest were resolved in
**opposite directions**, and both were wrong: 04-29 sided with the weather (+150 into a −440);
05-11 sided with the tape (−160 into a **+1,740**). The brain's own
`selector.divergence_resolution` says default to the tape/flow regime unless
`gw_hdd >= 16.4 AND b_share >= 0.50`. Neither day met the override, so the play said *tape* on both.

Arm B applied it consistently — and it lost all three of g20's split days:

| day | tape | weather | took | actual |
|---|---|---|---|---|
| 05-27 | sell −1,290 | cdd rising to 8.20 | tape | **+610** |
| 06-04 | sell −2,852 | cdd rising to 9.30 | tape | **+1,130** |
| 05-28 | sell −4,910 | softening | tape | **+2,100** |

Consistency is what made the losses legible. This is A-84's own falsifier firing: the rule may
deserve **demotion**, not harder enforcement. The 200-day corpus recovered this session (A-77) is
now there to settle it per cell.

---

## 5. What an external reader should take from this

1. **Do not read the renders as curves.** They are daily nets joined by interpolation. Fix A-86
   before judging path quality.
2. **The blind/refine machinery is sound; the magnitude channel is not.** Direction was right on the
   run's best events and the size was a fraction of the move; on the quiet events the size was a
   multiple of it.
3. **The next experiment is not another forecast run.** It is A-85's falsifier: find *any* served
   quantity that separates large-move days from quiet ones across the 200-day corpus
   (`vol_regime`, realized sigma, options-implied move, `|signed_flow|`, forecast run delta). If one
   does, this is a serving gap. If none does, the honest product is a band and `path_p50_curve`
   should be **removed** rather than filled with decoration.
4. **Nothing here is architecture evidence.** A-67 arm 1 still needs an unseen block, and the
   unwalked head (h1, 2025-08-04 → 08-15) is staged but blocked: its fundamental stores are
   2026-only, so 14 blocks are empty and `state_health` correctly refuses it.

---

## Appendix — files

| file | what |
|---|---|
| `records/S118/FRANKIE_S118_COMPLETE_RUN.json` | every forecast, reasoning, outcome, benchmarks |
| `records/S118/frankie_s118_b/` | arm A posteriors + bridges (g18, g19) |
| `records/S118/frankie_s118_c/` | arm B posteriors + bridge (g20) |
| `records/S118/frankie_s118_b_scores.json`, `..._c_scores.json` | scored per-event output |
| `records/S118/g18_s118_curve.png`, `g19_`, `g20_` | forward-curve renders (see limit 1) |
| `records/S118/a80_a82_frankie_forecast_fixes.patch` | the two fixes, against `3a72fee`, not pushed to that branch |
