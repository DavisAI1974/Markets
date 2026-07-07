# SESSION HANDOFF — S70 (2026-07-07)

> READ FIRST: `STRATEGY_INVENTORY.md` **OPERATING CONTRACT + LIVE section** (binding; the greedy capital
> strategy is locked there in plain words, 8 points). This handoff is only the delta + the one next step.
> Do NOT re-derive the strategy or re-open queue/tape/proxy — the contract overrides any stale doc.

## What S70 fixed (process — this was the session's real work)
The recurring "sessions don't use live code / keep rehashing" problem was the DOCS themselves: the strategy
doc was a 560-line history log whose own drop-in Jobs said "queue" and "grade on tape." Fixed:
- **`STRATEGY_INVENTORY.md`** now opens with an **OPERATING CONTRACT** (binding, overrides everything below)
  then splits into **✅ LIVE** (the agreed current stack) vs **🗑️ SCRAP HEAP — NOT LIVE** (dead/parked/history).
- **The greedy capital strategy is LOCKED in plain words** in the LIVE section (8 points). Settled.
- Standing rules added: **#0b** (firing FIXED — fill-layer only), **#0c** (live-code-only for tests, no proxies/
  bolt-ons), and the book/front-of-line decisions. CLAUDE.md + the S70 kickoff + S69 handoff reconciled to the
  contract (banners).
- **Process (Greg, S70):** ONE change at a time, go slow. Live code only — a "does it run" functional check
  then the live run is fine, but **no canary as a ritual**. Book = fills, tape = plumbing. **Always front-of-line**
  (queue is NOT a mode). Firing untouched.

## Where the code is (all live-code, book-only)
- **`scripts/pool_book_kraken.py`** = THE live driver: book → `run_cell` (front-of-line) → `run_portfolio`
  greedy $5k pool. Reuses live pieces only (`basket_sim_kraken.load_book`/`run_cell`, `platform.run_portfolio`).
- **`run_portfolio`** now reports honest **TIME-weighted** deployment (`time_in_play_frac`, `time_util`) — the old
  `mean_util` was event-sampled and misleading.
- **BASELINE run** (5 majors, 41.9h book, front-of-line, kr_mk0, `caps=pool`): **POOL +14.51 $/hr**, money in
  play **97%** of the window — BUT the $5k ran **one coin at a time** (`caps=pool` lets the best coin monopolize
  the bank), so **550/1996 legs funded, 72% dropped**. The $608/41.9h is thin per-leg edge (1–6 bp) on a
  low-edge window, concentrated on the best-available coin — NOT idle capital. Per-coin edge: xrp +12.0, sol
  +6.6, btc +6.5, eth +5.5, doge +5.4 $/hr @ $5k.

## THE ONE NEXT STEP (the greedy test, left for you)
Give greedy the **counterparty capacity** so multiple positions run at once (short BTC + long SOL together),
per the locked strategy rules 3–4: fill best up to what its book absorbs, cascade the leftover to next-best.
- **Capacity source (Greg's call, firm): the L2 BOOK DEPTH — the resting bid/ask SIZES = the COUNTER's
  capacity, NOT trade volume.** The whole point was to read what's actually resting to trade against, not
  sparse realized volume. The book carries full depth per 100ms bin (`bids[[offset,size]×10]`, `asks[...]`);
  `load_book` currently keeps only top-of-book size — extend it to the depth you need, convert size→$ at mid.
- **Mechanism:** add an optional per-leg cap to `run_portfolio` (built + reverted this session — ~6 lines: a
  `leg_caps={coin:[$per leg]}` param that bounds each opening leg's demand+cap; `None` = unchanged). Feed each
  leg its book-depth capacity → run `pool_book_kraken.py` → read POOL $/hr, funded%, and whether we now hold
  several positions concurrently (funded should jump from 28%). ONE change; run it live; compare to +14.51.

## DONE in S70 — "never fund negative edge" gate STRIPPED (tested, +14.51 unchanged)
Greg (S70, firm): "never fund a negative edge" is a WRONG rule. **Removed** the `key_weight<=0` skip in
`allocator.allocate()` greedy mode — edge is now the funding ORDER only, never a gate; negatives fund last,
never dropped. **Tested** (pool_book_kraken, 5 majors): POOL $/hr = **+14.51, identical to baseline** — the
gate wasn't binding (all 5 have positive edge), so a clean/safe no-op on this window. It only bites once
negative-average coins are seated (the 16 minors), which is the point. Do NOT re-add it.

## Data / infra state
- Book branches: 5 majors `data/{btc,eth,sol,xrp,doge}-kraken-book` (BTC ~42h). **16 candidate minors now
  collecting** via `kraken_candidate_book_collectors_durable.yml` (S70, on the default branch, cron 03/09/15/21
  UTC) — HYPE/SUI/ADA/ZEC/XMR/AVAX/XLM/AAVE/LTC/NEAR/TAO/LINK/BCH/BNB/TON/XPL. Books take days; grade them ON
  BOOK when deep (never tape).
- Materialize books: `git show origin/data/<coin>-kraken-book:<coin>_kraken_book.jsonl.gz | gunzip > /tmp/kbook/<coin>_book.jsonl`.
- Coinbase Liquidity Program (Greg was evaluating it cold, no rep): 0bp maker on US spot but a %-of-exchange-
  volume gate a $5k book can't hold organically → stays PARKED. Not a re-pivot. (Corrects the old "Coinbase has
  no 0bp" belief, but doesn't change the Kraken plan.)
