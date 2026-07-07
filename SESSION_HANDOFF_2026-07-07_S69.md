> ⛔ CORRECTED IN S70 (Greg): read `STRATEGY_INVENTORY.md` OPERATING CONTRACT + LIVE section FIRST (binding).
> This handoff calls the `queue`/back-of-line fill the "honest" fill — that is SUPERSEDED. **We ALWAYS operate
> FRONT-OF-LINE** (we post the best bid/offer via the enticing close, so we are first in line); `queue` is a
> worst-case footnote, never a mode. The capital model = ONE $5k greedy bank, front-of-line maker, best
> performer first, remainder cascades to the next-best LIVE coin (no queue-waiting). Everything else stands.

# SESSION HANDOFF — S69 (2026-07-07) — ZERO code changes; the lesson = ALWAYS RUN LIVE CODE FOR TESTS; the honest fill/capacity comes from the L2 BOOK, not the tape

Read `STRATEGY_INVENTORY.md` (top standing rule, now re-stated louder) first. This session made **no code
changes** — the branch is the clean S68 baseline (`46c134f`) + one doc-only commit. Below is what was
learned so the next session does not repeat it.

## THE ONE TAKEAWAY (Greg, S69 — now a standing rule at the top of STRATEGY_INVENTORY + the drop-in)
**ALWAYS RUN THE LIVE CODE FOR EVERY TEST. NO EXCEPTIONS.** Never estimate fills / capacity / edge with a
tape PROXY, a hand-rolled reimplementation, or a bolt-on (`capacity.py`-on-tape, a scratch script that
recomputes eligibility, etc.). Every fill/capacity/$hr test goes through the actual executor
(`run_stream` / `run_kraken_cell` → `swing_maker`) on the REAL data, and the honest FILL comes from the
L2 **BOOK** via `fill_model="queue"` + real `best_bid_sz`/`best_ask_sz` — **not** tape flow.
`scripts/basket_sim_kraken.py::load_book` already does exactly this.

## WHAT HAPPENED (so it isn't re-run)
- Greg flagged a hard-coded "~1000k" per-coin value in the capital model. It was real: `scripts/
  portfolio_sim_kraken.py` builds per-coin capacity via `cell_capacity_summary(..., window=None)` =
  the **whole-hold** flow bound (the retired S50 "coding issue that made caps wrong"), which inflates the
  majors to ~$1.3k–4k caps.
- The session then TAIL-CHASED: it tried to "fix" capacity with a per-leg **tape** proxy (`capacity.py`
  FILL_W), got nonsense ($25 median BTC caps, a bogus long/short asymmetry that turned out to be a
  cherry-picked-tail artifact), and re-derived the already-settled adverse-selection / winners-invisible
  / fill-is-the-wall findings (S45/S56/S60). **All of that was the wrong instrument** — the tape can't
  measure how much fills at a resting price; only the L2 book can.
- The capital-model **allocator itself is correct** (S69 verification agent: canary bit-for-bit; greedy
  rules all pass — shared pool, best-edge-first cascade, per-leg dynamic cap allowed to take the full
  $5k, skip-but-never-drop). The problem was never the allocator; it was feeding it tape-proxy capacity.
- **The right answer, from LIVE code on the REAL book** (`basket_sim_kraken.py --fill queue`, BTC 41.9h
  Kraken L2 book): **FRONT-of-line = 90% fill / +6.47 $/hr; QUEUE-honest = 34% fill / −2.31 $/hr**
  (one ~40h LOW-EDGE window). `fill%` is the real answer to "does BTC fill the $5k" — it fills the full
  position on 34% (queue) to 90% (front) of legs, matching Greg's intuition. The `capacity.py` $25 median
  was the artifact. This reproduces the doc (§8.7, S63: "raw maker fill ~40%; the leak is the FILL").
- **All exploratory code was discarded.** `git reset --hard 46c134f`; branch = baseline + the standing note.

## CAPITAL-MODEL STATUS (unchanged from S67 — still built + canary-clean)
`odcore/allocator.py`, `odcore/platform.run_portfolio`, `scripts/portfolio_sim_kraken.py`,
`scripts/grade_coin_kraken.py` are all at the S67/S68 state. The correct next step is to feed the
allocator **honest book fills** (queue) instead of tape capacity — i.e. run the shared-pool model over
the per-cell **book** legs (`basket_sim_kraken::load_book` + `run_cell(..., fill_model="queue")`), not
`capacity.py` on the tape. Do NOT re-open the tape-capacity thread.

## NEXT (Greg's S69 directives — the concrete, non-thrashing work)
1. **ADD THE NEW COINS TO THE POSSIBLE STACK + START THEIR BOOKS.** The graded candidates (LTC/AVAX/ADA/
   SUI) are already in `platform.KRAKEN_CANDIDATES[_MARGINAL]`; add the S67-sweep LARGE candidates too as
   ungraded seats. **Add them to `.github/workflows/kraken_book_collectors_durable.yml`** (currently
   sol/eth/btc/doge/xrp only) so their L2 books start accruing — the honest fill needs the book, and the
   book takes days to build, so start the clock now.
2. **Run the HONEST capital model on the real BOOK.** Materialize all coins' books
   (`data/<coin>-kraken-book` → `/tmp/kbook/<coin>_book.jsonl`), run the shared-$5k pool over the per-cell
   **queue-fill** legs (live code). Report POOL $/hr + fill% per coin. NEVER a tape capacity proxy.
3. Longer-window confirm of the S68 tuned configs (ADA/LTC + reversed SOL/XRP) before any live change.

## DATA / BRANCH STATE
- Kraken L2 book branches: `data/{btc,eth,sol,xrp,doge}-kraken-book` (only these 5; new coins need
  collectors added). BTC book = ~41.9h. `load_book` (basket_sim) is the loader.
- Kraken TAPE: `realbins/{btc,eth}_kraken_bins.json` 28d on box; the 7 others are re-pullable via
  `backfill_kraken_trades.py --days N --bins-path realbins/<coin>_kraken_bins.json` (⚠ tape dies on
  recycle; the tape is for STRUCTURE/edge, the BOOK is for FILLS).
- Branch `claude/davisai-s69-kickoff-l5b22y` = clean S68 baseline (`46c134f`) + the standing-note commit.
  Zero code changes this session.
