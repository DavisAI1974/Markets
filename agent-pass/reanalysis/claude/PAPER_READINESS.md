# Paper readiness (Claude Code independent reanalysis, 2026-11-09)

Platform: Tradovate demo environment (user's selection, stated 2026-11-09). This repository contains no Tradovate client, credential handling, contract mapping, quote logger or paper order/fill ledger (repository-wide search for "tradovate": no files). The NG runner on this branch (`research/kalshi/adaptive_wavepacket_20261108/markets_bridge/ng_runner.py`) is a tape replay probe with, in its own words, "no paper ledger". Nothing is connected. No paper order has been placed by this work.

## Ranked candidates

| rank | candidate | status | why |
|---|---|---|---|
| 1 | S2 large-move fade | ready for a paper execution check | needs only best bid/ask; 174/225 full returns across the four dates individually; stop is provisional |
| 2 | S1 dipole recognition log / no-entry | observation-only | needs message-level flow for the 20 s native window; Tradovate does not provide it |
| 3 | S5 weakening-onset exit warning | observation-only | same data need; no price-outcome evidence after onsets |
| 4 | S4 touch-imbalance / refill nowcast | observation-only | 1-2 tick effect vs 1-2 tick spread; needs depth and order counts at the touch |
| 5 | S3 thin-touch retreat nowcast | observation-only | millisecond horizon; message-level data; S3b sign convention unresolved (CONFLICTS C9) |

## Exact launch / check steps for S2

1. Credentials: Tradovate demo username/password and API key as environment secrets on the paper host (never in the repository). Obtain an access token; verify it against the demo (not live) endpoint and record the environment name in the log header.
2. Contract: resolve the current NG front month on Tradovate (the four dates were the Nov-2023 front month; the rule is contract-agnostic). Record contract id, tick size 0.001 and tick value in the log header.
3. Market data: subscribe to quotes for that contract; log every best bid/ask update with platform timestamp and local receive timestamp for 60 s; confirm the two clocks agree within an acceptable bound and record the offset.
4. Replay check before any live quote: run the S2 rule over the frozen Oct 18 best bid/ask reconstruction (combined-events groups, markets-data@87dc338) and reproduce the 64 triggers and 49 full returns of `c-large-quote-events`; any mismatch stops the launch.
5. Order path: place one 1-lot limit order far from the market in the demo account, confirm it appears as working, cancel it, confirm the cancel. Log both.
6. Freeze: hash `PAPER_STRATEGIES.json` (S2 v0.1) and write the hash into the session log header. No parameter changes during the session.
7. Run: S2 only, 1 contract, one position at a time, settle-window and open-window exclusions on, logging as specified. Do not call a replay a live paper run; the first prospective session is the first paper observation.
8. Review after the session: full-return share, median return time, missed fills, suppressed signals, MAE/MFE, spread at entry and exit, gaps and disconnects. Compare with the per-date evidence table (not with a pooled number).

## Shared logging and evaluation requirements (all candidates)

- Every decision logged with: inputs as of the decision clock, decision, order, assumed fill or miss, exit, reason, and both clocks.
- Suppressed signals logged with their reason (position open, cooldown, stale data, settle window).
- Missed opportunities, false alarms, excursions, drawdown, duration and gross result per trigger; nothing averaged as the headline; per-session distributions.
- Prospective results kept separate from the four historical dates, which are already-studied days and not out-of-sample validation.

## Tonight blockers

- No Tradovate client or credentials in the repository (OPEN_QUESTIONS 1).
- Message-level data is not available from Tradovate, so S1, S3, S4, S5 cannot run (OPEN_QUESTIONS 2).
- S2 stop parameter has no evidence behind it (OPEN_QUESTIONS 4); it is labelled provisional.

## Deferred gaps

See OPEN_QUESTIONS.md items 6-14.
