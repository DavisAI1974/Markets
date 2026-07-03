# SESSION HANDOFF — S59 (2026-07-03) — ENTRY PIECE **DONE** (DoD promotion committed) +
# kr_mk0 RE-PRICE (all surviving configs flip positive at 0bp maker) + KRAKEN DATA MACHINE
# LIVE (book collector all 5 coins + 30d trade-history backfill)

**THE PRIMARY ARTIFACT IS `S59_NOTES.md`** (round-by-round). This is the summary.

Branch: designated `claude/davisai-s59-entry-us0004` == canonical `5c5vg9` (synced every
push). NOTE: the S59 designated branch was ALSO cut from the wrong parent (default/crons
lineage) — reconciled by reset to canonical at session open, same as the kickoff warned.

## 1. ENTRY PIECE: DONE — Greg called it; the DoD promotion is committed (790b71c)
- **`odcore/entry_coinbase.py`** (venue in file titles from now on — Greg's platform-
  separation rule): `armed_midband_flips` = the round-6 machine promoted VERBATIM (v2
  arming, c-scaled confirm, mode-0 fallback fix, baseline fallback, bounce_frac = BTC-only
  candidate, data-blind confirm-predicate socket) + `assert_truncation_invariance` leakage
  gate + `COINBASE_MIDBAND` registry per the five-verdict board: sol mb100 / xrp mb80 /
  doge mb100 ACTIVE (all NAIVE k0), btc mb80 INACTIVE (pending books), ETH absent.
- One-version law: flips only; execution through `platform.run_stream` (swing_maker).
  Flat size (mid-band sizing not earned — parked Piece 3). Wired into `paper_trade.py` as
  SANDBOX cells -> SANDBOX ledger only. The paper cron (default branch) checks out
  canonical, so the mid-band forward record accrues automatically from the next 6h run;
  `paper_ledger_sandbox.jsonl` is committed on canonical (git = source of truth).
- **CANARY 3/3 PASS** (`scripts/_s59_promotion_canary.py`): (1) bit-identical flips vs the
  S58 reference on all 5 book tapes x both thetas x bounce variant; (2) truncation-
  invariance leakage PASS every tape; (3) baseline run_cell(DEPLOYED) BIT-IDENTICAL with
  the module present (26,784 rows) AND the live paper run appended +0 baseline trades.
- First sandbox window: +128 rows — sol_mb100 **+418.1 net bps** (n=56, taker 0%),
  xrp_mb80 -349.0, doge_mb100 -212.4, btc 0 (inactive). One window; the ledger decides.
- **PIECE 2 (EXIT) IS OPEN.** First candidate: the parked R8 lean-collapse exit
  (~123bp/side prize at coarse theta) through the same executor. Parked list in
  S58_ENTRY_NOTES.md.

## 2. kr_mk0 RE-PRICE (Pass A paper + Pass B machine re-run, identical to the cent)
- **Every surviving member-map config flips POSITIVE at Kraken 0bp maker**: sol_fadeclmx
  +3.19/+2.22, btc_opp_bnc +1.97, doge_clmxexh +1.64, ce_noopp +1.82 $/hr (~+$6/hr
  best-per-coin at $5k). The S58 "entry-alone can't cross fees" ceiling was a COINBASE-FEE
  statement, not structural.
- **XRP ASTERISK:** its th80 Coinbase deploy shape is NEGATIVE on bins even at 0 fee
  (k0 -0.95 $/hr; th100 variants positive) — books-derived shape, bins-divergent coin;
  XRP's Kraken read waits on Kraken books hardest.
- **THE TWO-UNKNOWN SPLIT (Greg's read, confirmed):** (a) does the gross exist on Kraken's
  own thinner tape (~35-42% of Coinbase volume)? — answerable with historical trades, NOW;
  (b) do maker quotes FILL at that volume? — only the live book collector answers (no
  historical L2 exists anywhere). Fees are solved; tape + fills are the open questions.

## 3. THE KRAKEN DATA MACHINE (both halves live this session)
- **Book collector (fills truth): `kraken_book_collector.py`** — v2 WS book+trade,
  IDENTICAL row schema to the coinbase collector (loaders reuse), trade-snapshot-replay
  guard, depth-truncation; live-smoke-tested (SOL 428 rows/45s). Workflow
  `kraken_book_collectors_durable.yml`: **ALL 5 COINS** (Greg — per-cell law), 6h cron,
  anti-clobber + >85MB rotation, data/<coin>-kraken-book branches. On canonical AND the
  default branch (94a7428) — cron live; Greg's click starts it sooner.
- **Trade history (tape truth): `backfill_kraken_trades.py`** — Kraken REST Trades
  pagination -> 1-sec bins, same schema as the Binance backfill; paced ~1 req/s,
  checkpointed/resumable. 30d x 5 pull RUNNING at session close (/tmp/kraken_backfill;
  REST pairs SOLUSD/XBTUSD/XDGUSD/XRPUSD/ETHUSD). **S60 FIRST JOB: run the entry machines
  on this tape at kr_mk0 per cell** — flow maps re-derived per venue, never ported.

## 4. FINGERPRINT MICROS-TIER PREP: CLEAN NULL (recorded, not tuned)
Dual-print (match-winner MINUS match-loser) over the 10 causal onset descriptors on
deploy-shape legs, OOS half-split both directions, leakage PASS: **AUC 0.47-0.59,
direction-unstable — no separation.** Confirms the five-agent S58 finding at feature
level: the winner side is invisible to the flow-read descriptor space. The 5th-member
path NARROWS to the S35 ENCODER tier (chunker micros + 128-dim OD coeffs), gated on:
S35b onset canary + the win/lose archives on Greg's LOCAL E: drive + per-(cell,band)
revalidation. No micros-tier iteration off this window.

## 5. BACKGROUND / STANDING
- Coinbase books: all 5 branches accruing (BTC repair CONFIRMED pushing; all <85MB).
- Kraken fee page re-confirmed live (0bp @$10M/30d; 6/4/2/0 ladder). Jul-9 post-facto
  re-confirm queued. Greg: CFM login-gated futures tier tab still his read.
- FINE-GRAIN: untouched by all of this (Greg: we'll use it again). DEPLOYED fine cells
  bit-identical, forward ledger pure.

## 6. NEXT (S60) — see KICKOFF_2026-07-04_S60.md
1. Kraken tape machine run (the real venue re-price) — bins in /tmp/kraken_backfill.
2. PIECE 2: the exit — R8 lean-collapse at coarse theta through the platform executor.
3. Kraken books accrual checks; DOGE clmxexh + BTC mid-band books validation as
   Coinbase windows accrue.
