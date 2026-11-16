# Direction memory for the NG four-day reanalysis (Claude Code), reconstructed 2026-11-09

The memory files named in the Ccode handoff (`/areas/october-ng-dipole-direction.md`, `/preferences.md`) are not present in this environment or in the repository. This file reconstructs Greg's direction from the repository documents and from his statements in the 2026-11-09 session, so that no future session depends on a memory store it cannot reach. Sources: agent-pass/AGENTS.md (all November 8-9 sections), claude-pass-3day/HANDOFF_NEXT_SESSION_20261109.md section 1, SHARED_BRIEF.md (breadth and price-as-input sections), START_FOR_CCODE.md at c674834, CLAUDE.md trading rules, and the session.

## Greg's direction (verbatim where possible)

1. The research target is the meaning of a recognizable developing movement, not curve fitting. Find historical occurrences of the same behavior at their original values. Never normalize, rescale, time-warp or smooth.
2. Determine the earliest recognizable point, what was available then, the subsequent move, and what distinguishes continuation from a failed start or reversal. The practical objective is a meaningful ride: joining, leaving, or changing direction.
3. **The look-ahead advantage is real and applies on NYMEX, not only on Kalshi.** A saturated 20 s window is knowable the second it completes; the Native detector reports it about 50 s later. Measure every dipole quantity from the knowable clock, never from the archived recognition clock, and apply the look-ahead everywhere a decision clock exists.
4. **The dipole explains exhaustion and tells you the flip.** Direction is one of its outputs, not its test. Separate: prospective transition warning, structural runway, direction nowcast, recognition delay, cross-market lag.
5. Explain remaining duration and remaining driving strength; warn of exhaustion and reversal early enough to act; include avoiding a squeeze, not only entering.
6. Every event and instance individually. No averages as the final word. Per cell, never pooled as the headline. Distributions and per-trade fingerprints.
7. No signal is discarded. Every relationship, however weak, inverse, rare, conflicting or unexplained, stays in CLAIMS and COVERAGE with its denominators.
8. Use the full depth of the data. The raw MBO tape is the largest input and the base layer; the 99 layers and 13 points were pinned so they could be used, so use them. Build the picture of how many layers together move things, not one layer at a time.
9. Apply the findings to the trade environment before and after each trade candidate, one row per trade.
10. Trade cost is not a market condition: all research numbers gross; execution assumptions are paper-log items.
11. Zero synthetic data. Provisional until live. Four already-studied days are discovery, never validation.
12. Both directions: behavior preceding price, and price followed by orders, liquidity, trading and later price; separate mechanical same-second effects from later responses and shared causes.
13. Keep execution and artifacts in GitHub. No desktop computation, no AWS/S3, no live-money, no PR15 merge. No reconciliation with Codex; two separate reports.
14. Do not ask Greg to restate direction. Find what you need yourself; if something is genuinely unavailable, say so once with evidence, then proceed.
15. Data first: tables and counts before commentary; plotted and tabulated counts reconcile to rows; measured things only; speculation labelled.

## Failures on 2026-11-09 that this file exists to prevent

- Measured the dipole from the recognition clock and concluded "no direction" (wrong clock).
- Counted 99-layer coverage from one attachment file (17/99) when the ledgers map 35 measurement layers over 1,775 fields.
- Misread the external series as never changing within a session (a key-name bug).
- Did not decode the raw MBO tape; treated the derived tables as the data.
- Did not find or ask for the memory file at the start.
- Summarised claims instead of recording every measured cell.
- Measured the look-ahead ride to the midpoint at the START of the exhaustion second (before the opposed print existed) and promoted the resulting 3:1 "drive" to a paper candidate. Rule from this: every mark is dated at the END of the completed second that contains it, and every ride to a mark uses that end-of-second price; tabulate the start-of-second variant only as the mechanical component.
- Hard-coded conclusion text in the claim generator (M17/M20) instead of deriving it from the cells, so a convention change did not propagate. Rule: conclusions in generated rows come from the numbers or name the convention explicitly.
