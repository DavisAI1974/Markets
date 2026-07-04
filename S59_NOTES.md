# S59 NOTES — ENTRY DoD (Greg called it) + kr_mk0 re-price + KRAKEN GATE (2026-07-03)

GREG'S CALLS AT SESSION OPEN: (1) **ENTRY IS DONE** — promote the entry code into the
platform BEFORE any exit work (Piece 2 opens only after the promotion commit); (2) finish
the COINBASE build while Kraken books collect (much transfers); (3) FINE-GRAIN untouched —
we will use it again; (4) do the kr_mk0 re-price; (5) **"coinbase" goes in code file titles**
— platforms stay separate in the codebase from here on.

Branch: designated `claude/davisai-s59-entry-us0004`, reconciled to canonical 5c5vg9 @
7c734a6 (was cut from the default/crons lineage — the same wrong-parent trap as S58; reset
--hard, pushed; infra commits live on the default branch, nothing lost).

## kr_mk0 RE-PRICE — PASS A (paper, from the recorded round-6 tables)

Method: legs/h backed out of each cell's recorded (gr/leg, $real@cb_real 16bp RT) pair;
kr_mk0 = 0bp maker both sides => $kr/hr = gr/leg x legs/h x $0.50 (at $5k flat).

| cell                 | gr/leg | legs/h | $cb_real | $kr_mk0 |
|----------------------|-------:|-------:|---------:|--------:|
| sol_fadeclmx th80    |  +5.61 |  1.138 |    -5.91 |   +3.19 |
| sol_fadeclmx th100   |  +5.65 |  0.785 |    -4.06 |   +2.22 |
| btc_opp+bnc25 th80   |  +9.26 |  0.427 |    -1.44 |   +1.98 |
| doge_clmxexh th100   |  +6.35 |  0.516 |    -2.49 |   +1.64 |
| doge_ce_noopp th100  |  +7.24 |  0.502 |    -2.20 |   +1.82 |

Best-per-coin sum (sol th100 + btc th80 + doge noopp): **~+$6.0/hr** on the 30d bins tape.
Books shapes (thin n, MIXED frame — Coinbase tape at Kraken fees, shape only): SOL th100 k0
gross +22.1bp/leg -> net = gross at kr_mk0 (n=56); DOGE clmxexh th100 books cb_real -0.05
~= breakeven -> clearly positive at kr_mk0 (n~23).

**HEADLINE: every surviving round-6 config flips POSITIVE at kr_mk0.** The S58 "entry-alone
cannot cross fees" ceiling is a COINBASE-FEE statement, not a structural one — at 0bp maker
the entry machine is already net-positive on paper. This re-orders venue priority: Kraken
book validation is now the highest-information data acquisition in the program.

**CAVEATS (all load-bearing, none waivable):**
1. VENUE LAW — these gross numbers are Binance-instrument; NOTHING here is a Kraken-cell
   forecast. Kraken books unmeasured (fill/queue reality unknown; live volume 35-42% of
   Coinbase). The re-price says "worth validating", not "deployable".
2. Maker-fill assumption — taker share 0-5% was measured on Coinbase mechanics; must be
   revalidated with Kraken cover mechanics (fallback flips are the taker-risk moment).
3. Tier sustenance — kr_mk0 requires $10M/30d rolling; paper cadence clears it (~$25-30M/mo)
   but only while the machine RUNS; a paused machine decays back to 2-6bp maker tiers.
4. July-9 schedule change — $1M+ ladder unchanged per S58 verification; re-confirm post-facto.
Pass B (honest column with taker-share accounting, machine re-run) queued on the bins
backfill (relaunched this session, /tmp died).

## ENTRY DoD PROMOTION (the S58 definition-of-done, executed)

**`odcore/entry_coinbase.py`** (venue in the title — Greg's platform-separation rule):
`armed_midband_flips` = the round-6 reference machine promoted VERBATIM (v2 arming, c-scaled
confirm, MODE-0 fallback fix, baseline fallback; bounce_frac carried as the BTC-only
candidate; per-cell confirm-predicate SOCKET deliberately data-blind — flow maps stay
research-only until per-venue books pass). `assert_truncation_invariance` = the machine's own
leakage gate, run on every tape. Registry `COINBASE_MIDBAND` = the five-verdict board:
sol mb100 / xrp mb80 / doge mb100 ACTIVE (all NAIVE k0), btc mb80 INACTIVE (pending book
accrual), ETH absent (dropped; re-entry test in S58 notes). Execution through
`platform.run_stream` (one-version law); legs FLAT size (mid-band sizing not earned, parked
Piece 3); fees on config = cb_real 8/16. Wired into `scripts/paper_trade.py` as a SANDBOX
section — mid-band rows accrue the SANDBOX ledger only, baseline forward ledger untouched.

**CANARY (scripts/_s59_promotion_canary.py) — ALL PASS:**
1. FAITHFUL PORT: bit-identical flips vs the S58 reference on all 5 Coinbase book tapes x
   both thetas x bounce variant (sol 96/57, btc 23/15, doge 61/41, xrp 33/21, eth 59/38).
2. LEAKAGE: truncation invariance PASS on every tape.
3. BASELINE BIT-IDENTICAL: run_cell(DEPLOYED) rows with/without the module = identical
   (26,784 rows) — the baseline forward record is untouched by the promotion.

## KRAKEN BOOK COLLECTOR — LIVE (gates kr_mk0 validation + fine-band reopen)
`kraken_book_collector.py` (v2 WS book+trade, coinbase row schema so loaders reuse
unchanged, trade-snapshot-replay guard from the S37 bins collector, book truncated to
subscribed depth) — live-smoke-tested on SOL/USD (428 rows/45s, 10 levels both sides, taker
flow captured). Workflow `kraken_book_collectors_durable.yml`: ALL 5 COINS (Greg — per-cell
law: ETH/BTC Kraken cells are their own cells), 6h cron, anti-clobber + >85MB rotation
guardrails, data/<coin>-kraken-book branches. Committed to canonical AND the default branch
(94a7428) — cron activates from default; Greg can click Run workflow for an immediate start.

## BACKGROUND CHECKS
- Coinbase books accrual: ALL 5 branches pushed within ~30min of check (BTC repair
  CONFIRMED accruing: 47.2MB @21:03Z); all under the 85MB rotation threshold.
- Kraken schedule: live fee page re-confirms 0.00% maker at $10M+/30d and the 6/4/2/0
  ladder ($1M+) exactly as S58 verified; no Jul-9 table visible on the live page yet —
  post-facto re-confirm after Jul 9 stays queued.

## kr_mk0 RE-PRICE — PASS B (machine re-run on the re-pulled 30d bins; $top col = kr_mk0
## under the maker-both-sides frame — taker-share honesty stays a KRAKEN-BOOKS question)

Round-6 tables reproduce exactly (same tape window); Pass A arithmetic confirmed to the cent
(sol_fadeclmx +3.19/+2.22, btc_opp_bnc +1.97, doge_clmxexh +1.64, ce_noopp +1.82 $/hr).
**HONEST ASTERISK: XRP th80 — its COINBASE deploy shape — is NEGATIVE on bins even at 0 fee**
(k0 -0.95, dcveto -0.41 $/hr; th100 variants positive +0.71/+1.19). The th80 shape was earned
on the Coinbase books (where XRP inverts hardest vs bins), so the "every surviving config
flips positive" headline reads precisely as: every surviving MEMBER-MAP config + the
books-frame shapes; XRP's Kraken forecast genuinely waits on Kraken book accrual. SOL k0 th80
also ~breakeven at 0 fee on bins (+0.08) — the paper prize is in the mapped/th100 cells.

## FINGERPRINT PREP (micros tier) — NULL RESULT, recorded not tuned
`scripts/_s59_fingerprint_prep.py`: per-cell dual-print (match-to-winner MINUS
match-to-loser, cosine to standardized centroids) over the 10 causal onset descriptors
(opposing/exhausting/clmx/ER/fade/runup/dur/hod/side) on the deploy-shape k0 legs,
OOS half-split both directions, leakage spotcheck PASS all 4 cells.
**VERDICT: no robust OOS separation** — AUC 0.47-0.59 and DIRECTION-UNSTABLE (sol topQ
+7.1 forward / -7.9 reverse; doge 0.593 forward only; xrp/btc ~chance). This CONFIRMS the
five-agent S58 finding at the feature level: the winner side is invisible to the causal
flow-read descriptor space, so a dual-print built FROM that space cannot carry it either.
-> The 5th-member path narrows to the S35 ENCODER tier (chunker micros + 128-dim OD coeffs,
match-to-winner minus match-to-loser), which stays gated on: (a) the S35b onset canary,
(b) the win/lose archives on Greg's LOCAL E: drive (not in this container), (c) per-(cell,
band) revalidation. No further micros-tier iteration off this one window (discipline).

## THE KRAKEN TAPE VERDICT (30d trade-history bins, promoted k0 machine, leakage PASS x5)

`scripts/_s59_kraken_tape_run.py` on `backfill_kraken_trades.py` output (4.2M trades).
**THE GROSS EXISTS ON KRAKEN'S OWN PRICES — 9/10 (coin,theta) cells positive at kr_mk0:**

| cell (k0) | gr/leg | $kr0 (10M tier) | $kr2 (5M) | $kr6 (1M) | wk+ | zw |
|---|---:|---:|---:|---:|---|---:|
| sol th100  | +4.96 | **+3.16** | +0.61 | -4.48 | **5/5** | **+2.5** |
| doge th100 | +5.01 | **+2.11** | +0.43 | -2.94 | 3/5 | +1.4 |
| eth th100  | +3.91 | **+1.72** | -0.04 | -3.56 | 3/5 | +1.3 |
| doge th80  | +3.08 | +1.91 | -0.57 | -5.53 | 4/5 | +1.4 |
| eth th80   | +1.50 | +1.02 | -1.69 | -7.10 | 2/5 | +0.8 |
| xrp th80   | +0.88 | +0.61 | -2.17 | -7.73 | 4/5 | +0.4 |
| xrp th100  | +0.67 | +0.30 | -1.52 | -5.15 | 2/5 | +0.4 |
| btc th80/100 | +0.31 | +0.13/+0.09 | neg | neg | 3/5,1/5 | ~0 |
| sol th80   | -0.87 | -0.86 | neg | neg | 3/5 | -0.3 |

- **SOL th100 = the first cell in program history with positive net $, ALL 5 weeks
  positive, AND weekly z +2.5.** Best-cells sum ~+$7.4/hr at $5k flat (~$5.3k/mo paper).
- **ETH IS ALIVE ON KRAKEN** (+1.72 th100) — per-cell law vindicated: its Coinbase drop
  says nothing about its Kraken cell. th100 leads 4/5 coins (consistent with Coinbase).
- **Climb economics:** at the $5M tier (2bp) SOL/DOGE th100 are ALREADY positive — the
  late climb doesn't bleed on the lead cells; the $1M tier (6bp) bleeds everywhere =
  the known one-time ~$3,905 early-climb cost.
- **CAVEATS (both point at the live book collector):** (1) fills NOT modeled — every
  number rides maker-both-sides at mid; (2) tape SPARSITY — bin coverage 3-24% (doge 3%),
  mid forward-filled between trades, so confirm fills on price-jump seconds are optimistic.
  Kraken books = the decisive gate for both. No theta picked here (discipline); the read
  is existence + stability, not a deploy map.
- Bins backfill x5 relaunched 21:34 (/tmp/backfill) — all 5 complete.
- Coinbase books x5 restored from data branches.
- Promotion canary PASS (3/3 obligations); paper_trade end-to-end run + Pass B machine
  re-run on fresh bins launched. Pass B complete (above).
- Wired paper harness ran end-to-end: BASELINE +0 new trades, ledger intact (26,784) —
  the DoD condition, live. MID-BAND SANDBOX record started (+128 rows, one books window):
  sol_mb100 +418.1 net bps (n=56, taker 0%), xrp_mb80 -349.0 (n=32), doge_mb100 -212.4
  (n=40), btc_mb80 inactive as designed. One window — the forward sandbox ledger accrues
  the real verdict per cell from here.

## ENTRY PIECE: **DONE** (promotion commit = this one). PIECE 2 (EXIT) IS OPEN.
The per-leg budget Piece 2 inherits: surviving configs' gross ~+5.6..+9.3 bp/leg vs
cb_real 16bp RT (deficit -1.4..-4 $/hr) — and the parked R8 exit prize (~123bp/side
lean-collapse at coarse theta) is the first named candidate. Parked exit items in
S58_ENTRY_NOTES.md ("PARKED FOR LATER PIECES").
