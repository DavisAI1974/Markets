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
