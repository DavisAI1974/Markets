# SESSION HANDOFF — S60 (2026-07-04) — THE KRAKEN TAPE VERDICT (gross exists on Kraken's own
# prices) + PIECE 2 EXIT worked to per-cell verdicts + COINBASE-EXIT FIX reframed (fill/fee,
# not timing) + the DIPOLE RESEARCH PROGRAM (paper + dive chapter + absorption resolved)

**PRIMARY ARTIFACT: `S60_EXIT_NOTES.md`** (round-by-round, R1a–R7). This is the summary.
Branch: designated `claude/davisai-s60-entry-exit-mq0mb5` == canonical `5c5vg9` (synced every
push). NOTE: designated branch was cut from the wrong default/crons parent AGAIN (3rd session
running) — reset to canonical at open. The parallel S59 session pushed its own Kraken tape
verdict to canonical mid-session (independent convergence, +3.16 vs our +3.14); rebased clean.

## 1. THE KRAKEN TAPE VERDICT (Job 1) — YES, the gross exists on Kraken's own prices
`scripts/_s60_kraken_tape_machines.py` — promoted mid-band machine (naive k0, venue law: no
flow maps) on 30d Kraken trade-history bins, all 5 coins, leakage PASS. All registry cells
kr_mk0-positive: **sol_kraken_mb100 +$3.14/hr 5/5 weeks** (first program cell net-positive at
a real reachable tier on its own venue tape), doge +2.11, xrp +0.61, btc +0.12, **eth +1.72
(its OWN cell — per-cell law: the Coinbase drop never pre-judged eth_kraken)**. Best-per-coin
~+$7.7/hr @$5k. Honest-fill check PASS (median fill delay 0s; sparse-tape concern dissolves).
Tier ladder load-bearing (kr_mk2 flips most negative → the $10M/30d 0bp tier is the game).
REMAINING UNKNOWN: do maker quotes FILL at Kraken volume (books, accruing).

## 2. PIECE 2 (EXIT) — worked to per-cell verdicts; ZIGZAG holds, one corrector earned
Exit dump (`_s60_piece2_exitdump.py`) + renders + machines (`_s60_piece2_exit_machines.py`).
- **Toll law (now 4/4 coins BOTH venues):** winners' giveback = c*theta EXACTLY (~40 th80 /
  ~50 th100); excess over toll +0.7..+1.8bp. NO peak harvester exists — the +18-25bp
  flow-climax ceiling is hindsight = S35 fingerprint-tier. Winners invisible to causal flow
  reads confirmed EXIT-side, all coins.
- **The bleed = 2 populations:** wrong-side theta-deaths + the structural toll. The only exit
  edge family = the WRONG-SIDE CORRECTOR (opposing dive while underwater = flow-confirmed
  failure), and it is DIAGONAL per cell: SOL none (zigzag near-optimal; armed-before find,
  8/8 cell info, perm z 2.4-3.5) / BTC plain price-stop only (cell still negative, rider) /
  DOGE cascade-join flip (BUY-only, +1.10/hr structure premium over shuffle, instrument-
  validated) / XRP none. Cross-pollination matrix (R3b): pieces do NOT cross-pollinate.
- **BTC "flow-exit coin" (R1c) KILLED (R2):** exposure-shrink on a bleeding cell, 4 ways
  (winner/loser decomp, regime flip, blind-timer control, top-3-excluded).
- Kraken exit race (R3): DOGE flip fails the Kraken shuffle floor -> venue law holds, needs
  own per-venue pass. **KRAKEN EXITS PARKED (Greg) until Coinbase exit fixed.**

## 3. COINBASE EXIT FIX (Greg's halt-all focus) — the fix is FILL/FEE-shaped, not timing
Per-coin Coinbase-frame agents + 2 scrap miners (archive + code). Convergent finding:
- **XRP: the cell's problem is NOT the exit** — -16bp fees on +4.1 gross; perfect-oracle exit
  ceiling barely crosses zero. Fix = fee-tier / entry-side / venue-shaped.
- **DOGE: cascflip spec'd as a SANDBOX VARIANT** (`doge_coinbase_mb100_cascflip`; ~30-fire
  accrual bar; ledger decides) but does NOT turn the cell at cb_real (-6.71 -> -1.56 face).
- **CODE MINER (load-bearing):** the sandbox ledger CANNOT see the real exit fill cost —
  128/128 mid-band closes booked maker=True by construction (`_next_positive`, no queue).
  The honest fill machinery exists UNWIRED (`maker_book._first_fill_index`,
  `swing_accum._eligible_fill`). Mid-band path runs **grace=0** (S48 cover-grace unwired).
  run_stream lean = 60s-wall on books (confound INSIDE the platform).
- **ARCHIVE MINER gold (ranked):** (1) cover-grace at mid-band (both miners' #1); (2) post
  the cover into the CLIMAX (not the dive — the dive is thin-tape, §2.1 inversion); (3)
  resting cover at (extreme - c_x*theta); (4) taker-share acceptance metric; (5) fill-
  asymmetry dollars; (6) FEE TIER > the whole exit prize (2 Greg clicks, unverified).
- BUILD ORDER (proposed, awaiting Greg sign-off): honest fill model FIRST (measure real
  maker_close% on books) -> fee-aware unload rules -> grace arm -> cascflip variant.
- ⚠ NOT DELIVERED (killed by mid-session interrupts): the SOL Coinbase-exit-fix agent and the
  BTC armed-before recheck. Strategic conclusion already clear from the other three; re-run
  if wanted next session.

## 4. THE DIPOLE RESEARCH PROGRAM (Greg's PI directive) — paper printed
- **`docs/DIPOLE_PAPER_S60.md` (+ .html print-ready)** — PI survey answering Greg's verbatim
  inquiry (Section 0). Taxonomy D1-D8 + classification machinery; 4 experiments; the coupling
  taxonomy (raw-cov=fixed-phase/lag, MI-in-null=dynamical coupling, flow dMI/dt=nothing
  standalone + opposition-signature-is-construction-generated, reproduced on market data
  first time); three-offices finding; 29 candidate uses (crypto/digital/physical) each with a
  first falsifiable test.
- **`docs/DIPOLE_DIVE_CHAPTER_S60.md` (+ .html, +§3.5R)** — the dive: three offices, FILL-
  office inversion (dive = thin tape, z-13; S45 fill moment is the CLIMAX side not the dive),
  timing no-lead, size null at mid-band, cross-domain map (seizure-onset flow collapse =
  novel-leaning standout).
- **`docs/DIPOLE_CRYPTO_USES_S60.md`** — ranked candidate crypto uses + earned record.
- **ABSORPTION/SPOOF candidate (Greg "we can definitely use this"): RESOLVED, decided
  against** (`_s60_absorption_wall.py`, §3.5R). Latency KILLED (Binance R^2 0.003), wall
  FALSIFIED (deep-wall = thin, zero reversal info). Real SOL-only signal is a delayed
  price-discovery lead, maker-quoting-frame-only (taker-dead vs 16bp), filed to the fill
  fingerprint thread. Nulls were the deliverable.

## 5. THE DIPOLE-DIVE STANDING NOTE (Greg asked it be recorded)
The trailing taker-flow lean = ONE object, THREE offices, each earning separately per (cell,
band, venue, ROLE): entry-confirm grading / wrong-side failure confirmation / fill-moment
marking. Timing-as-exit died at mid-band; the corrector office is what earned. A dipole's
value = (operator x what it is conditioned against), never the operator alone.

## 6. INFRA / STANDING
- Kraken book collectors: cron on default (00/06/12/18Z); at last check still 0 runs post-tick
  — CHECK the Actions tab; Greg's Run-workflow click = fast path. Coinbase books accruing.
- FINE-GRAIN untouched. DEPLOYED baseline ledger pure (26,784). Mid-band SANDBOX accruing.
- Kraken exits PARKED (Greg) until Coinbase exit fixed.

## 7. NEXT (S61) — see KICKOFF_2026-07-05_S61.md
1. Coinbase exit fix build order (honest fill model first) — Greg sign-off.
2. Fee-tier verification (2 clicks: Coinbase fee-upgrade program + CFM tier tab).
3. Kraken exits UN-PARK once Coinbase exit lands.
4. Kraken books accrual -> the fill unknown; the paper's candidate uses as a research menu.
