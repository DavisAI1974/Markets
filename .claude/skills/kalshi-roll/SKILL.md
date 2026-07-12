---
name: kalshi-roll
description: Re-point the Pyth tick collector to new front-month futures contracts when the current ones expire (WTI / Henry Hub NG / Brent). Use when a roll date approaches or has passed, or when the Pyth feed records a flat/expired price for a symbol.
---

# Pyth front-month roll

The Kalshi lag pipeline streams the NYMEX/ICE front-month contracts Kalshi settles on. When a
contract expires, the feed must be re-pointed or the lag data goes stale/garbage.

Current contracts + roll dates live in the docstring of `research/kalshi/pyth_collector.py`
(as of S82: WTIQ6 exp 2026-07-21, NGDQ6 exp 2026-07-29, BRENTU6 exp 2026-07-31).

## Steps

1. **Identify the new front month.** Futures month codes: F G H J K M N Q U V X Z =
   Jan..Dec (e.g. after WTIQ6/Aug-2026 expires, the front month is WTIU6/Sep-2026).
   Confirm which contract KALSHI actually settles on (the series rulebook on kalshi.com)
   rather than assuming — Kalshi's settle contract is what we must lag against.

2. **Find the new Pyth feed ID.** Query Pyth Hermes for the price-feed list and locate the
   new symbol (asset-type FX/commodity metadata; same venue naming as the current IDs):
   `https://hermes.pyth.network/v2/price_feeds?query=<symbol>` — take the 64-hex feed id.

3. **Edit `research/kalshi/pyth_collector.py`:**
   - Replace the expired entry in the `FEEDS` dict (symbol -> new 64-hex id).
   - Update the module docstring's contract/expiry lines.
   - Keep the KEY as the new symbol name (files are per-symbol per-day, so the old symbol's
     accrued `data/pyth_ticks/<old>_*.jsonl` history is untouched — never delete it).

4. **Sanity-stream before committing** (a few seconds is enough):
   ```bash
   python research/kalshi/pyth_collector.py --symbols <NEWSYM> --seconds 30
   tail -3 data/pyth_ticks/<NEWSYM>_*.jsonl   # ticks with advancing ts + sane price?
   ```
   Note market hours: energy futures trade ~Sun 18:00 ET–Fri; off-hours a frozen price
   dedups to near-zero ticks — that alone is not a failure.

5. **Commit + push to the trunk** (`claude/kalshi-s79-kickoff-ij8t9o`, pull first) — the 6h
   `pyth_collector_durable.yml` workflow reads the collector from the trunk, so the roll takes
   effect on its next cycle. Update the roll dates in the docstring AND mention the roll in the
   session handoff.

6. **Downstream bookkeeping:** any analysis joining ticks across the roll boundary must treat
   old-symbol and new-symbol series as SEPARATE cells (never splice into one continuous series
   without an explicit, documented roll adjustment).
