# SESSION HANDOFF — S50 (2026-07-01) — 2nd-window gate re-confirmed after a restart; DOLLAR-capacity model built; the edge is thin → the deploy lever is a REBATE VENUE, focus SOL

Branch: `claude/crypto-liquidity-signals-s49-rqtcfk` == canonical `5c5vg9` (kept synced every push). Read
`S50_CAPACITY_FINDINGS.md` + the S50 delta atop CLAUDE.md. This session resumed the S49 work after a container
restart (verified nothing lost), then answered Greg's venue/volume questions with a new capacity model.

## What S50 did
### 0. Resumed S49 after a container restart — verified, not lost
The S49 2nd-window work (gate PASSES on all 5 cells OOS; conviction sizing wired leakage-clean into
`size_legs`) was already committed + pushed at `a0be673` before the restart. Re-verified git state and
**re-ran the mandatory leakage gate end-to-end → OVERALL PASS** (clmx + size axes, all 5 cells). So the S49
result stands: the 2nd-window gate that blocked the thread since S46 is cleared.

### 1. Answered "same volume to make the same money?" + "does it work on other venues?"
Measured per-cell spread / top-of-book depth / trade volume / turns from the books. **Volume is wildly uneven
and does NOT track per-trade edge**: SOL is the standout (real 1.36 bps spread + $5M/hr volume + 155 turns/hr);
DOGE has the 2nd-best net/leg but ~10× less volume and almost no depth; ETH/BTC have volume but near-zero spread
(their edge is thin timing, not spread capture). **Other venues: UNTESTED — every book we have is Coinbase.**

### 2. Built the DOLLAR-capacity model (`scripts/_capacity_model.py`)
Reuses the deployable pipeline for real legs, overlays a fill bounded by the ACTUAL opposing flow per leg.
- **Greg caught a coding issue (confirmed):** the first cut summed opposing flow over the WHOLE hold, making
  SOL's uncapped ceiling spuriously −$204/hr (losing legs flood the fill side for the whole leg). A fixed
  per-turn position fills NEAR THE TURN and holds — bounding fill to a 1s entry window (`FILL_W=10`) flips the
  ceiling to +$19/hr and collapses the lose/win capacity gap (corr −0.123 → −0.025). Fixed in place.
- **Corrected numbers (mk0, flat, 1s window = conservative):** SOL ceiling +$19/hr, XRP +$6, DOGE +$9, ETH ~$0,
  BTC thin. SOL leads but the absolute dollars are SMALL.

### 3. Diagnosed WHY it's small + what actually scales it (Greg: "$19/hr seems low")
- **Conviction sizing is only ~+25%, not a multiplier.** `corr(size,net)=+0.03` — winners are NOT separable
  from losers at entry (S47 DEAD result), so sizing loads *big moves* (half of which are wrong-tail). Real but
  modest lift.
- **Throughput = edge(bps) × passively-fillable notional; 1.75 bps is THIN.** $100/hr on SOL needs ~$570k/hr of
  passive fills (~11% of one-sided volume). A thin edge structurally caps the dollars.
- **THE LEVER = a MAKER REBATE (as bps).** A −1 bp rebate adds ~+2 bps/round-trip → ~doubles net/leg (1.75→3.75)
  → ~doubles $/hr, on the same fills. The rebate venue is both the viability gate AND the main magnitude lever,
  and stacks with a wider-spread venue book.

## Decisions (Greg, S50)
- **Coinbase zero-maker tier is not realistically reachable ($250M+/30d) → pivot to a REBATE VENUE**
  (market-maker-agreement path, not a volume wall).
- **Focus SOL initially** (data-confirmed best cell).

## Git / state
Commits this session (both branches synced): capacity model + entry-window fix + corrected results/findings.
Paper cron kept accruing the forward ledger (07-01, 07-02 windows) onto 5c5vg9 — rebased cleanly under the S50
work each push. Books load from `/tmp/*_coinbase_book.jsonl.gz` (materialize from `data/<coin>-book` after a
restart). `_capacity_model_results.json` = full per-cell curves.

## NEXT (S51) — see `KICKOFF_2026-07-02_S51.md`
1. **Quantify the rebate scenario** (capacity at maker −1/−2 bps) — the number that informs the venue pick.
2. **Pick 1–2 rebate venues, collect their SOL book, re-measure spread+fill** (per-cell rule; a rebate on a
   tight book won't print). Verify fee schedules, don't cite from memory.
3. **v2 fill model**: walk-the-book / mark-to-fill markdown (resolves both the conservative 1s window and the
   optimistic per-fill price).
4. Wire per-leg size cap + `size_legs` into deploy sizing (modest lift).
DEAD (don't re-chase): timing retiming, wrong-tail entry-gates, spread/dive as timing, expecting conviction
sizing to be more than a +25% garnish (winners not separable at entry — S47).
