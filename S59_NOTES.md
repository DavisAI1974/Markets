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

## SESSION LOG (append per round)
- Bins backfill x5 relaunched in background 21:34 (/tmp/backfill, ~40min).
- Entry DoD promotion into odcore: IN PROGRESS (coinbase-titled files, sandbox-first,
  baseline canary bit-identical, per-cell registry per the five-verdict board).
