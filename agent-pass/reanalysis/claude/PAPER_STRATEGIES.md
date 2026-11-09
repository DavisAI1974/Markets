# Paper strategy candidates (Claude Code independent reanalysis, 2026-11-09)

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

## S7 — Dipole drive ride at the look-ahead clock with exhaustion exit (status: OBSERVATION-ONLY on Tradovate; READY FOR A PAPER EXECUTION CHECK on a message-level feed)

Dipole layers used: native fresh buy/sell lots per completed second, the 20 s rolling window, its oriented ratio; complementary input: none required (best bid/ask for the midpoint). Added after the user's look-ahead correction (REPORT section 12).

Thesis (EVIDENCE, CLAIMS LA-1, LA-2, LA-4). When the 20 s aggressor window becomes fully one-sided and a qualifying peak is confirmed (+5 s), the midpoint moves with that direction about 3 to 1 until the first fresh opposed lot arrives (median 19 to 20 s after the birth second); after that lot the next 60 s moves against. Windows still one-sided at 60 s keep driving (51/20, 46/21, 48/20, 54/31).

Inputs. Message-level prints classified against the preceding completed-group midpoint (the Native action-midpoint rule, CONFLICTS C1); per-second with/against lots; best bid/ask. Decision clock = completed second.

Setup and entry. Window fully one-sided (|ratio| = 1) with total lots above the trailing 85th percentile baseline per the recovered detector (EVIDENCE for definition; PROVISIONAL as a live rule because the competition window is not waited for). Enter in the window direction at the first quote after k = +5 s (PROVISIONAL; the local-max confirmation clock). One position at a time.

Exit (EVIDENCE). At the first completed second containing a fresh opposed lot (exhaustion onset), or at 60 s, whichever first. Do not wait for the operational end (third opposite second), which is 20 s later and gives the gain back.

Flip overlay (EVIDENCE, CLAIM LA-3; PROVISIONAL as a rule). If the window turns majority-opposite (median 34 to 36 s after birth), reverse into the new direction for 60 s: after the flip the midpoint follows it 356/245, 401/220, 395/199, 457/235.

Magnitudes and the honest caveat. Median ride 0 ticks, p75 0.5 tick, mean absolute 0.3 to 0.5 tick; moves of one tick or more with the direction 81/69/96/111 vs against 35/27/24/40. The spread is 1 to 2 ticks. By the house rule that comparison is for the paper log, not for these numbers; it is the first thing the log must measure.

Population caveat. Evidence is on the recorded births (competition winners). A live rule acts on the first qualifying peak; Ccode's emulation puts that population at 803/843/800/863 with 675 to 700 exact matches to the recorded 741/832/740/863. Price paths for the extra peaks are not in the packet (OPEN_QUESTIONS 15); the first paper sessions must log them separately.

Sizing, limits, data handling, logging: as S2, plus the per-second lot classification must be logged with its rule.

Status. Tradovate supplies no message-level data, so S7 cannot run there. On a message-level feed (the Databento route used for the historical tape) it is the primary candidate for a paper execution check.

## S2 amendment (robustness, REPORT section 13)

Entry delay: enter at the first quote after the trigger (+1 s) instead of +5 s; at +5 s the rule already misses 5/18/16/5 of the eventual full returns (Oct 2/3/17/18), at +1 s only 2/11/7/2. Time limit: full returns at 60/120/300/600 s are 20/24/33/35, 37/40/44/48, 32/35/40/42, 21/30/39/49; 600 s stays. Dipole layers used: none. Complementary inputs: best bid/ask only.

## Dipole layers used by each candidate

S2 none; S1 flow state at emission (Native recognition clock); S3 none (thin touch, fresh wire flow); S4 none (touch queue); S5 weakening onsets (fresh opposed vs expiry, vanished/resumed); S6 fresh opposed / window empty; S7 fresh lots, 20 s window, ratio saturation, exhaustion onset, flip.
