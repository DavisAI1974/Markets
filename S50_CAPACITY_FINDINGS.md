# S50 FINDINGS — per-cell DOLLAR-capacity model + the venue/edge read (Coinbase-first → rebate-venue pivot)

`scripts/_capacity_model.py` (+ `_capacity_model_results.json`). Reuses the deployable pipeline
(`build_channels` → `detect_flips` → `simulate_swing_maker`, cover-grace) to get the real swing legs, then
overlays a size-dependent fill **bounded by the ACTUAL opposing trade flow per leg**. mk0/tk5, same 29.2h
window as S49 (btc = its 196h control book). Answers Greg's S50 questions: same volume to make the same money?
does it work on other venues? — and the follow-ups ("$19/hr seems low"; "the wrong-tail sounds like a coding
issue" — both correct, see below).

## CORRECTION (Greg was right — the wrong-tail ceiling WAS a coding issue)
The first cut summed opposing flow over the **whole hold** (open→close) as fillable size, which made SOL's
S→∞ ceiling spuriously **−$204/hr** (losing legs, where price runs against us, flood the fill side for the
whole leg → capacity balloons on losers). But a maker-at-the-turn position fills a **fixed size near the turn**
(S40 climax volume) and holds one leg turn-to-turn — it does NOT scale into the whole adverse move. Bounding the
fill to a **1s entry window** (`FILL_W=10`) removes the artifact: SOL ceiling flips **−204 → +19 $/hr**, and the
lose-vs-win capacity gap collapses (corr(cap,net) −0.123 → −0.025 = a small residual adverse tilt only, not
sign-flipping). Verified across windows (whole −204 / 2s −12 / 1s +19 / 0.5s +14). The 1s number is the
CONSERVATIVE end (fills only what arrives at the turn); the true capacity is higher, bounded by adverse
selection as you rest longer — the v2 mark-to-fill model owes the exact tradeoff.

## Corrected per-cell $/hr (entry-window fill, mk0, flat, one/two windows)
| cell | net/leg | turns/hr | $/hr @ $1k/leg | ceiling (all turn-flow) | fill@$1k |
|------|---------|----------|----------------|-------------------------|----------|
| **SOL** | +1.75 bps | 155 | **+$8** | **+$19** | 39% |
| XRP  | +1.16 | 140 | +$4 | +$6 | 34% |
| ETH  | +0.55 | 162 | +$4 | ~$0 | 55% |
| DOGE | +1.35 | 53  | +$2 | +$9 | 22% |
| BTC  | +0.52 | 40  | ~$1 | (see JSON) | — |

**SOL still leads** (best net/leg with a real spread + high turn rate). But the absolute dollars are SMALL —
and that is the real finding, not a bug.

## Why the number is small — and what actually moves it (Greg: "$19/hr seems low")
Two measured facts:
1. **Conviction sizing is a ~+25% garnish, not a multiplier.** SOL flat vs sized at a $2k/turn budget:
   1s +$11→+$14, 5s +$18→+$21, whole +$45→+$54. `corr(size, net) = +0.03` — the size multiplier is barely
   aligned with which legs win, because (S47, DEAD) **winners are NOT separable from losers at entry**. Sizing
   loads *big moves*, and big moves are ~half wrong-tail. So "load winners not losers" is not achievable; sizing
   adds a real but modest lift.
2. **Throughput = edge(bps) × passively-fillable notional, and 1.75 bps is THIN.** To make $100/hr on SOL you
   must passively fill ~$570k/hr of notional (~11% of SOL's one-sided volume) at the turns. The $/hr scales with
   capital-per-turn until the flow/adverse-selection wall (resting longer: whole-hold $54 vs 1s $14 — but that
   reintroduces the adverse selection we just corrected). A thin edge caps the dollars structurally.

**The lever that actually moves it is a MAKER REBATE — as bps, not just viability.** All numbers are mk0. A
venue paying a **−1 bp maker rebate adds ~+2 bps/round-trip** on the SAME fills → **more than doubles net/leg
(1.75 → ~3.75) → roughly doubles $/hr**. So the rebate venue is the single biggest multiplier on the dollars,
and it stacks with finding a venue whose SOL book is WIDER-spread than Coinbase's (more half-spread to capture).

## Answers to the two questions
1. **"Same volume on the top coins to make the same money?" NO.** Volume/depth is wildly uneven and does not
   track per-trade edge. SOL is the standout; DOGE has the 2nd-best net/leg but almost no capacity (med
   turn-flow $25); BTC/ETH have depth but thin (timing) edge on near-zero spread.
2. **"Does it work on other venues?" UNTESTED — every book is Coinbase.** The code is venue-agnostic (collectors
   are parameterized) but the edge must be re-measured per venue-cell (a rebate on a tight/deep book won't
   print). The rebate-venue path is both the viability gate AND the main magnitude lever.

## Decision (Greg S50)
- **Coinbase-first was reconsidered**: Coinbase's zero-maker floor needs the $250M+/30d VIP tier (or ~$500K/mo
  upgrade) — not realistically reachable → **pivot to a rebate venue** (market-maker-agreement path).
- **Focus SOL initially** — data-confirmed the best cell.

## CAVEATS
- All mk0 (needs a rebate/zero-maker venue). Fill model still OPTIMISTIC on the filled portion (full net_bps, no
  walk-the-book markdown); the 1s window is conservative on capacity but the per-fill price is not marked —
  the v2 mark-to-fill model resolves both at once. One/two windows (paper cron keeps accruing).

## NEXT (S51)
1. **Quantify the rebate scenario** — re-run capacity at maker −1 / −2 bps to show exactly how much $/hr a
   rebate buys on SOL (the number that informs the venue pick).
2. **Pick 1–2 rebate venues**, collect their **SOL book**, re-measure spread + fill there (per-cell rule).
3. **v2 fill model**: walk-the-book / mark-to-fill markdown so $/hr at larger size is honest (resolves both the
   conservative-window and the optimistic-price simplifications).
4. Wire a per-leg **size cap** + conviction `size_legs` into deploy sizing (small lift, still worth it).
