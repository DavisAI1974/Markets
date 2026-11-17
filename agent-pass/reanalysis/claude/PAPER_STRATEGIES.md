# Paper strategy candidates (Claude Code independent reanalysis, 2026-11-09; rerun v2 — S7 revised, first-pass S7 and its amendment withdrawn)

Research numbers below are GROSS (house rule: trade cost is not a market condition). Execution assumptions are listed as unmeasured paper-only settings to be LOGGED by the paper runner, never applied to the findings. Parameters marked EVIDENCE come from the frozen packet with the table named; parameters marked PROVISIONAL are paper-only settings chosen here and must be frozen before prospective observation. Platform: Tradovate demo (user's selection); it supplies best bid/ask and depth snapshots, not message-level order flow, which is why only S2 can execute tonight. Machine-readable twin: PAPER_STRATEGIES.json.

## S2 — Large-move fade (status: READY FOR A PAPER EXECUTION CHECK; blocked only by the missing Tradovate connection)

Market and session. CME NG front month on Tradovate demo, Globex session 18:00-17:00 ET; no-trade inside the settle window (SETTLE_UTC guard) and in the first 15 minutes after the 18:00 ET open (PROVISIONAL, mirrors the detector warm-up).

Thesis (EVIDENCE, CLAIMS M2-1, M2-2). A midpoint jump of at least 2 ticks between consecutive completed quotes extends in the next 5 s (first-5 s extreme p50 3.0-4.5 ticks vs 2.0 jump) and then returns fully to the pre-move midpoint within 600 s in 35/46, 48/58, 42/57, 49/64 cases (Oct 2, 3, 17, 18), half-returns in 41/46, 57/58, 48/57, 53/64. Full-return time p50 38 / 9 / 14 / 84 s, p90 203 / 237 / 254 / 341 s. Non-return within 600 s: 11, 10, 15, 15.

Inputs. Best bid and ask with receive timestamps; midpoint = (bid+ask)/2; tick = 0.001. Event clock = quote receive time; decision clock = quote receive time + platform latency (log both). No order-flow input needed.

Setup and trigger (EVIDENCE for definition: c-large-quote-events). Pre-move quote Q0 = last midpoint before the jump; trigger when |mid - Q0| >= 2 ticks between two consecutive quote updates. Direction d = sign of the jump. Wait 5 s from the trigger quote (PROVISIONAL, taken from the source's first-5 s extreme window) and record the extreme E (most displaced midpoint in those 5 s).

Entry. At trigger+5 s, enter AGAINST d (sell after an up-jump, buy after a down-jump) with a marketable limit at the then best quote on the side being joined; log quoted spread, intended price, assumed fill price and time. Fill assumption (PROVISIONAL, UNMEASURED): fill at the touch if the touch persists for 1 s after order time; otherwise no fill, log as missed.

Target and exit. Target = Q0 (full return, EVIDENCE endpoint). Exit at target touch, or at trigger+600 s (EVIDENCE window), whichever first. Reversal rule: none; this is a one-shot fade.

Invalidation / stop (PROVISIONAL, UNMEASURED). Exit if the midpoint moves beyond E by 3 ticks in direction d. Evidence gap: the adverse path after +5 s is not in the packet (OPEN_QUESTIONS 4). Deterministic pause: no new entries while a position is open; cooldown 60 s after any exit (PROVISIONAL).

Priority when rules fire together. One position at a time; a second trigger in the opposite direction while in a position is logged as a suppressed signal, not acted on. A second trigger in the same direction while in a position: hold, log.

Sizing and limits (PROVISIONAL). 1 contract; max 1 open; daily stop after 3 consecutive stopped exits (log and pause until next session).

Data and clock handling. Missing or stale quote (> 5 s without an update during RTH): no entry; if in a position, hold to target/time limit on the next good quote and log the gap. Out-of-order timestamps: ignore the quote and log it. Disconnect: cancel working orders, flatten at reconnect, log. Conflicting clocks (platform vs local): record both, decide on platform time.

Supporting and adverse evidence. Supporting: 174/225 full returns across the four dates individually (never pooled as a headline). Adverse: 51 non-returns within 600 s; Oct 18 returns are slow (p50 84 s) so a shorter time limit would have missed many. Prior pressure signals do not sort returns (agree-majority 15/23, 21/24, 19/23, 22/30 vs disagree 19/21, 26/31, 21/31, 25/32), so no filter is applied. Known failure mode: a genuine repricing (news) that does not return; no event-overlap filter exists in the evidence.

Invalidation of the rule. Prospective paper full-return share below 0.6 over the first 40 triggers, or median return time above 300 s, invalidates the parameterisation.

Logging. Per trigger: Q0, jump size, E, decision quote and time, order, assumed fill or miss, target touch time, exit reason, exit price, gross ticks, MAE/MFE at 1 s, spread at entry and exit, suppressed-signal reasons.

Frozen configuration. S2 v0.1 as in PAPER_STRATEGIES.json (hash the JSON before the first paper session).

## S1 — Dipole recognition log and no-entry rule (status: OBSERVATION-ONLY)

Thesis (EVIDENCE, CLAIMS M1-1..M1-3). At the actual recognition clock the Native dipole carries no average direction, and about half of lifecycles are already over. The decision this supports is abstention and exit timing, not entry: if a position exists in the birth direction, a recognition with flow state "opposite" says the window has reversed (93-96% already ended).

What to log prospectively. Each recognition with its flow state, orientation, nominal and actual lag, and the 60/300/600 s midpoint outcome; the prospective version of the M1 cell table. Cannot run on Tradovate data (needs message-level flow to compute the 20 s window); observation-only until a message feed exists.

## S3 — Thin-touch continuation/failure nowcast (status: OBSERVATION-ONLY)

Thesis (EVIDENCE, CLAIM M3-1). Standing best shrank to one lot + attacking fresh 1 s flow -> retreat 0.63-0.66 on all dates; new best of one lot + flow away -> hold 0.61-0.67. Horizon is milliseconds; requires message-level data. Use: an execution-quality rule (do not rest at a thin level under attack), to be logged, not traded. S3b (size-one up-bias at 1-5 s) stays observation-only until CONFLICTS C9 is resolved.

## S4 — Touch-imbalance / refill 1-5 s nowcast (status: OBSERVATION-ONLY)

Thesis (EVIDENCE, CLAIMS M4-1..M4-3, M5-1, M8b-3). Touch imbalance and refill at the hit side sort the next 1-5 s with the same sign on all four dates (continuation 0.54-0.61 at 1 s; Spearman 0.06-0.29) and decay to coin-flip by 60-300 s. The move is 1-2 ticks against a 1-2 tick spread; without fill evidence this is not a trade. Log only; requires depth and order-count data at the touch.

## S5 — Weakening-onset early warning (status: OBSERVATION-ONLY)

Thesis (EVIDENCE, CLAIM M6-1). flow_vanished / flow_resumed onsets in the live 20 s ratio precede the next birth with 0.58-0.65 precision and 25-32 s median lead; step weakening leads 12-13 s with 0.42-0.49 precision. Use: an exit warning for a position held with a dipole (the dipole is decaying by definition at the onset). No price outcome evidence after onsets; requires message-level flow.

## Not promoted

Tier 1 original stack (60+/5-/1- bid-heavy): reversed on Oct 3 (CONFLICTS C4). Chain plays: 8/6/15/14 eligible per date. a-state direction: symmetric. Pre-recognition drift: not available at the decision clock.

## S6 — Dipole weakening as a "no reason to stay" exit overlay (status: OBSERVATION-ONLY; added after the user's exit question)

Thesis (EVIDENCE, CLAIMS X-4, X-6; negative results X-3, X-5 retained). For a position held in a dipole's direction from any entry, the first fresh-opposed weakening or vanished-flow onset of that dipole marks the point after which later moves follow and oppose the direction in near-equal counts (expected further drive zero, median absolute 60 s move 0.5 to 1.5 ticks). Exiting there is justified as removing exposure without drive, not as avoiding a measured adverse move. Exiting at an "opposite" recognition is neutral versus holding; a dipole recognized inside a large-move fade does not reliably mark non-return.

Rule to log (not trade). Inputs: live 20 s native buy/sell lots by completed second (message-level feed required; Tradovate does not supply it). Exit cue A: fresh opposed lots reduce |ratio| from 1 (fresh_opposed_weakening onset). Exit cue B: window total falls to zero (flow_vanished). Log the oriented 5/20/60 s move after each cue for positions held in paper by S2 or any other rule; evaluate per date, no pooling. Not applied to S2 tonight (S2 uses only best bid/ask).

## S7 (REVISED in rerun v2) — Touch-queue read at the dipole's look-ahead clock, exhaustion-end exit (status: OBSERVATION-ONLY on Tradovate; CANDIDATE FOR A PAPER EXECUTION CHECK on a message-level feed, small expected magnitude)

What changed. The first-pass S7 ("dipole drive ride, about 3 to 1 until the first opposed lot") is WITHDRAWN. Its ride was measured to the midpoint at the START of the exhaustion second, before the opposed print was known; measured to the END of that second (the first moment a position can act on the cue) the ride is symmetric on all four dates (192/369/180, 213/431/180, 192/345/203, 227/379/246; REPORT section 5, CLAIMS M16B-*). The window alone has no direction at any realizable clock. What does sort the outcome at the window's own +5 s clock is the displayed queue at both touches (REPORT section 6).

Dipole layers used: native fresh buy/sell lots per completed second, the 20 s rolling window, its oriented ratio (the entry CLOCK), the first fresh opposed lot (the exit MARK). Complementary inputs (the DIRECTION read): own-side and target-side touch size and order count at +5 s (own = the side the birth direction rests on; target = the side being hit); best bid/ask.

Thesis (EVIDENCE, CLAIMS M17-ride_exh_end-touch_ratio_k5, M23-ride_exh_end-raw_own_touch_orders_k5, M26 in tables/m26_v2_headline_cells.json). When the 20 s aggressor window becomes fully one-sided and a qualifying peak is confirmed (+5 s), the oriented midpoint from +5 s to the END of the first opposed-lot second (or 60 s) is up/flat/down 80/128/39, 65/166/32, 78/133/40, 84/145/55 when the own/target touch-size ratio is in the session's top tertile, and 35/144/61, 49/170/61, 50/131/71, 52/152/87 in the bottom tertile. With the raw-tape own-side touch order count also in the top tertile: 29/60/19, 39/89/14, 43/73/28, 41/76/31. Same read on the earliest-knowable cluster population with the raw book: 60 s up/flat/down 113/68/84, 104/97/93, 128/68/74, 135/66/85 (high) versus 100/53/112, 84/91/112, 79/69/108, 96/61/130 (low).

Inputs. Message-level prints classified against the preceding completed-group midpoint (CONFLICTS C1); per-second with/against lots; the full touch queue on both sides (size and order count), best bid/ask. Decision clock = completed second.

Setup and entry. Window fully one-sided (|ratio| = 1) with total lots above the trailing baseline per the recovered detector (EVIDENCE for the definition; PROVISIONAL as a live rule because the competition window is not waited for). At the first quote after k = +5 s, read own/target touch-size ratio and own-side order count; enter in the window direction only if both are in the top tertile of the live session's own running distribution (PROVISIONAL thresholds; EVIDENCE for the direction of the sort on all four dates). Otherwise log the window as a suppressed signal. One position at a time.

Exit (EVIDENCE for the mark, M16/M16b). At the END of the first completed second containing a fresh opposed lot (exhaustion onset), or at 60 s, whichever first. The exhaustion second itself carries the adverse tick on every date (146/284/311, 171/359/294, 149/274/317, 184/260/408); the exit cannot precede it. Do not wait for the operational end (third opposite second), 20 s later.

Flip. The window turning majority-opposite (median 34 to 36 s) precedes the opposite-polarity successor's recorded birth by median 23 to 39 s (M24 A) and is logged as a transition mark; it is NOT a reversal signal (after the flip second ends, the next 60 s is symmetric: 294/166/281, 269/250/305, 257/187/296, 322/199/330). The first-pass flip overlay is withdrawn.

Magnitudes and the honest caveat. Exit-rule outcome in the top tertile: p25/p50/p75 0/0/0.5 tick on Oct 2, 17, 18 and 0/0/0 on Oct 3; non-flat up-to-down about 2 to 1 (80/39, 65/32, 78/40, 84/55). The spread is 1 to 2 ticks. By the house rule that comparison is for the paper log; it is the first thing the log must measure, and the reason the status says small expected magnitude.

Population. Evidence on the recorded births (741/824/740/852) AND on the earliest-knowable clusters (803/844/801/864, including 64/78/73/87 that never became recorded births; their price behaviour matches the winners, M24 B). The live rule acts on the cluster population.

Invalidation (prospective). Over the first 100 qualifying windows that pass the entry filter, non-flat up-to-down below 1.3 to 1, or the bottom-tertile windows (logged, not traded) not leaning down.

Sizing, limits, data handling, logging: as S2, plus the per-second lot classification, the touch-queue snapshot at +5 s with its tertile boundaries, the exhaustion second, and every suppressed window.

Status. Tradovate supplies no message-level data and no order counts at the touch, so S7 cannot run there. On a message-level feed (the Databento route used for the historical tape) it is a candidate for a paper execution check with a small expected magnitude; S2 remains the primary candidate.

## S2 amendment (robustness, REPORT section 13)

Entry delay: enter at the first quote after the trigger (+1 s) instead of +5 s; at +5 s the rule already misses 5/18/16/5 of the eventual full returns (Oct 2/3/17/18), at +1 s only 2/11/7/2. Time limit: full returns at 60/120/300/600 s are 20/24/33/35, 37/40/44/48, 32/35/40/42, 21/30/39/49; 600 s stays. Dipole layers used: none. Complementary inputs: best bid/ask only.

## Dipole layers used by each candidate

S2 none; S1 flow state at emission (Native recognition clock); S3 none (thin touch, fresh wire flow); S4 none (touch queue); S5 weakening onsets (fresh opposed vs expiry, vanished/resumed); S6 fresh opposed / window empty; S7 (revised) fresh lots, 20 s window, ratio saturation as the clock, exhaustion onset as the exit mark; direction from the touch queue (not a dipole layer).

## S2 amendment (post-trade dipole exit, REPORT section 19; EVIDENCE M20)

After entering the fade, read the native 20 s aggressor window each completed second. If net native flow over the first 20 s after the move continues WITH the jump, exit: those fades failed to return in 8/28, 6/24, 10/22, 9/31 versus 3/16, 3/32, 3/29, 6/32 when flow turned against the jump. Requires message-level flow; on Tradevate (top-of-book only) this overlay is logged as unavailable. Before-trade note: a busy tape in the prior 60 s returns fast (median 5 to 25 s), a quiet tape slowly (18 to 138 s); use this to set the expected hold, not to filter.

## S7 amendment (first pass) — WITHDRAWN

The first-pass amendment ("prefer births into a quiet, thin-target book; leave-one-date-out score >= 3: 139/24, 126/26, 126/41, 140/34") was measured under the start-of-second convention. Under the realizable convention, quiet births move more in BOTH directions (132/129/117, 148/184/116, 130/143/142, 149/131/164 vs busy 60/240/63, 65/247/64, 62/202/61, 78/248/82; M20-ride-ride_end_by_prebirth_total_lots) and the all-layer leave-one-date-out score separates on three of four dates only (79/49 vs 34/52, 55/45 vs 73/73, 78/54 vs 48/74, 99/97 vs 51/67; M23). The entry filter now lives in the revised S7 above (touch ratio and own-side order count).
