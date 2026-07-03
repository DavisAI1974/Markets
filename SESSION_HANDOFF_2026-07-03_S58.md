# SESSION HANDOFF — S58 (2026-07-03) — THE ENTRY PIECE: 6 rounds + per-coin verdicts (ETH
# dropped) + the fallback falsification + KRAKEN kr_mk0 VERIFIED (fine band research-reopened)

**THE PRIMARY ARTIFACT IS `S58_ENTRY_NOTES.md`** — the round-by-round record (mistakes-caught
ledger, all 6 rounds with numbers, the five-verdict board, fingerprint surfaces map, parked
items, definition-of-done). This handoff is the summary; read the notes file for detail.

Branch: designated `claude/davisai-markets-s58-nmqpae` == canonical `5c5vg9` (synced every
push). Piece discipline (Greg): ENTRY ONLY until called done; exit/hold findings PARKED in
notes, never chased. Old kills are not verdicts (S56 grades were rebate-regime + fixed-25bp).

## 1. WHERE THE ENTRY STANDS (after 6 rounds)
- Frontier moved from -17..-23 $/hr (naive round-1) to **-1.4..-4 $/hr at cb_real** with
  positive gross everywhere and the first positive weeks (SOL fade+climax th100: wk 2/5).
  **Entry-alone cannot cross cb_real — by design it hands the per-leg budget to Piece 2.**
- THE FIVE-VERDICT BOARD (per-coin agents on leg-level dumps): SOL = LEAD (Coinbase th100
  NAIVE, +6.1 net/leg books n=56); BTC = keep conditional (th80-only stack, opposing-
  mandatory; GATED on the book collector — now FIXED, accruing); DOGE = keep REMAPPED
  (climax-Q4+exhaustion, th100; the ONLY flow map that held its books venue-check);
  XRP = keep naive-only (its stack lift was a pooled-window artifact; death-combo anti-print
  carried: opposing+climax WITHOUT exhausting = win 8-21%, -31..-53bp/leg, replicated 4x);
  **ETH = DROPPED** (books promise = 2 legs of one tape in the false-fire bucket; top-legs
  audit: the big legs were 20-48h trend rides, unrecognizable at entry; named re-entry test
  ~100 book confirms top-2-excluded mean >+10bp).
- MASTER FINDING: **price mechanics port across venues; flow reads don't** (r3 controls +
  5 agents unanimous; SOL books inversion = VENUE, window-matched). Coinbase deploy shapes
  are NAIVE k0; bins member maps are research-only until books-validated per cell.
- Round 5 falsification: bounce-fallback REJECTED (tail 1.4-3x, PART -10..-20pts); the S56
  "fallback sells troughs" narrative was fine-scale-local — at mid-band fallbacks OUT-gross
  vetoed confirms 7/10 cells. Baseline fallback stands (bnc25 = BTC-only candidate).
- WINNER SIDE: all agents independently — big winners are INVISIBLE to the 6 causal flow
  reads; separation lives in bucket structure = the S35 fingerprint wire-in (dual-print:
  match-to-winner MINUS match-to-loser, micros-first) is the only path. Spec in notes.

## 2. VENUE / FEE REALITY (S58 verifications)
- **KRAKEN PRO US SPOT: 0.00% maker at $10M/30d VERIFIED** (primary sources + API; no
  application; Ohio fine; SOL/XRP/XDG online; climb bleed $3,905 one-time; ⚠ schedule
  changes JULY 9 — our band unchanged, AoP shortcut added). The S57 "0/6 ceiling-only"
  column is now REACHABLE (kr_mk0 = 0/10). Live volume: Kraken = 35-42% of Coinbase.
- **FINE BAND: DEAD -> RESEARCH-REOPENED, KRAKEN-GATED** (4 conditions in notes; the fine
  machine's cadence sustains the tier for all cells — lawful volume-paycheck synergy).
- Coinbase CFM perp fee agent was still RUNNING at close — fold its report into
  S57_VENUE_FINDINGS.md next session (check the session log / re-run if lost).

## 3. INFRA (done this session, on the default/crons branch, commit 45c145b)
- Rotation guardrail on ALL book collectors (>85MB freezes live file as archived segment —
  pre-empts the S37 100MiB cap stall; sol/eth were at ~50MB).
- BTC book workflow REPAIRED (ref -> canonical 5c5vg9, grid 1000ms, restore/commit all
  segments) — BTC Coinbase book truth accrues from the next 6h cron.
- ETH backfill etc: 30d x 5 Binance bins in /tmp/backfill (re-pull per S54 kickoff; /tmp
  dies). Coinbase books re-materialize from data/<coin>-book branches.

## 4. NEXT (S59) — see KICKOFF_2026-07-04_S59.md
1. kr_mk0 re-price of the round-6 tables (5-min, big information).
2. KRAKEN BOOK COLLECTOR (new workflow; S37 kraken bins collector + today's rotation
   pattern) — gates the fine-band reopen AND all Kraken cells.
3. S35 fingerprint wire-in prep (micros-tier buckets from the 30d legs + dual-print scorer;
   preconditions in notes: onset canary, per-band revalidation, leakage).
4. ENTRY definition-of-done when Greg calls it: promote armed machine + mode-0 fix +
   baseline fallback + per-cell config registry into odcore (sandbox-first, canaried).
5. Books accrual checks; DOGE clmxexh map is the top per-venue-validation candidate.
