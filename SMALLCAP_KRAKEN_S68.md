# SMALLCAP_KRAKEN_S68 — heavy-volume rebate-eligible small-cap grade (2026-07-07)

Graded the ~10 heaviest rebate-eligible (−2bp maker tier) Kraken USD alt pairs — the highest-$/hr
candidates by liquidity — per cell through the LIVE path (`detect_flips(lean_series, WFLIP=600)` →
`odcore.platform.run_stream`), exactly as `scripts/grade_coin_kraken.py`, changing only two params:
**maker_fee = −2.0 bps (the rebate)**, taker_fee = 5.0; and reporting **both** `fill_model="front"`
(optimistic ceiling) and `fill_model="queue"` (pessimistic bound). No live code touched; no commits.
Grading harness: `/tmp/sc/grade_smallcap.py` (a param-only adaptation of grade_coin_kraken).

## THE HEADLINE METRIC — PREMIUM over the null floor (Greg, S68)

With a −2bp maker rebate, **any** round-trip churn is paid ~4bp/round-trip, so raw $/hr is positive even
for random-timed flips. The **circular-shift null floor** measures exactly that rebate/churn payout with
the timing edge destroyed. The deployable structure number is therefore:

> **PREMIUM = (best queue-honest $/hr with the −2bp rebate) − (its circular-shift null floor)**

Raw $/hr above the floor is real timing edge (survives adverse selection); raw $/hr = the floor is just
getting paid to churn (does **not** survive real fills). **A pair SEATs only if PREMIUM is clearly
positive.** Ranked by PREMIUM (headline column):

| pair | best $/hr @queue (−2bp rebate) | null floor | **PREMIUM** | verdict |
|---|---:|---:|---:|:--|
| **BILLUSD** | +13.70 | +9.89 | **+3.82** | SEAT |
| **XPLUSD**  | +6.89  | +4.24 | **+2.66** | SEAT |
| **MONUSD**  | +6.19  | +4.49 | **+1.70** | SEAT |
| CCUSD    | +5.37  | +5.89 | **−0.52** | MARGINAL (≈zero) |
| SYNUSD   | −1.73  | +3.23 | **−4.96** | REJECT |
| HYPEUSD  | +9.97  | +16.62 | **−6.64** | REJECT |
| NIGHTUSD | +0.60  | +7.36 | **−6.75** | REJECT |
| PLAYUSD  | −3.20  | +11.35 | **−14.55** | REJECT |
| CAPUSD   | +24.95 | +40.84 | **−15.89** | REJECT |
| SLXUSD   | −2.65  | +18.88 | **−21.53** | REJECT |

**CAP is the poster child for Greg's question:** its raw queue $/hr is the biggest of the field (+24.95),
but its null floor is +40.84 → **premium −15.89**. All of CAP's headline profit is rebate churn; there is
zero timing edge. Same story for HYPE (+9.97 raw, −6.64 premium — see below).

## Full grade (all required columns)

| pair | 24h vol | side | rev | $/hr front | $/hr queue (rebate) | null floor | frac-win-pos | legs/hr | $5k leg as %hourly | verdict |
|---|---:|:--|--:|--:|--:|--:|--:|--:|--:|:--|
| BILLUSD  | \$374k   | FWD | 0.10 | +21.59 | **+13.70** | +9.89  | 86%  | 4.2 | **32.1%** | SEAT (capacity-bound) |
| XPLUSD   | \$1.12M  | FWD | 0.13 | +11.87 | **+6.89**  | +4.24  | 100% | 2.0 | 10.7% | SEAT |
| MONUSD   | \$1.16M  | FWD | 0.13 | +10.59 | **+6.19**  | +4.49  | 100% | 2.2 | 10.3% | SEAT |
| CCUSD    | \$0.89M  | FWD | 0.10 | +10.50 | +5.37  | +5.89  | 100% | 2.8 | 13.4% | MARGINAL |
| SYNUSD   | \$2.49M  | FWD | 0.30 | −2.21  | −1.73  | +3.23  | 57%  | 1.0 | 4.8%  | REJECT |
| HYPEUSD  | \$12.9M  | REV | 0.10 | +17.94 | +9.97  | +16.62 | 86%  | 8.2 | **0.9%** | REJECT (deep but no edge) |
| NIGHTUSD | \$0.83M  | REV | 0.30 | +4.56  | +0.60  | +7.36  | 57%  | 3.9 | 14.5% | REJECT |
| PLAYUSD  | \$0.33M  | FWD | 0.30 | −6.06  | −3.20  | +11.35 | 57%  | 3.0 | 36.4% | REJECT |
| CAPUSD   | \$1.50M  | FWD | 0.30 | +22.22 | +24.95 | +40.84 | 86%  | 3.8 | 8.0%  | REJECT (all churn) |
| SLXUSD   | \$0.93M  | REV | 0.30 | +9.80  | −2.65  | +18.88 | 29%  | 3.4 | 12.8% | REJECT |

$/hr is on a $5k leg. Gate = queue $/hr > 0, beats reversed, reversed ≤ ~0, > shift-null floor,
≥60% sub-windows positive, ≥0.8 legs/hr. Verdicts key on the **queue-honest** fill (the deployable bound).

## The pairs I picked (top ~10 rebate-eligible by live 24h notional, 2026-07-07)

Ranked from a live `GET /0/public/Ticker` pull intersected with the S66 −2bp-eligible universe (352 pairs),
majors excluded. All 10 confirmed on the negative-maker (−2bp) tier; none are the 9 majors.

HYPE \$12.9M · SYN \$2.49M · CAP \$1.50M · MON \$1.16M · XPL \$1.12M · SLX \$0.93M · CC \$0.89M ·
NIGHT \$0.83M · BILL \$0.37M · PLAY \$0.33M. (Live volumes shifted vs the S66 07-06 snapshot; MON/CC
climbed into the top-10, AI/ARX/NES/BASED dropped just below. 8 came from the committed
`data/kraken-smallcap-tape` branch; CC + BILL were backfilled fresh, 28d each.)

## The deployable subset (clears queue-honest + rebate + null gate)

**3 cells SEAT: BILLUSD, XPLUSD, MONUSD** (all FWD, rev 0.10–0.13). All three beat their reversed control
(which loses), clear their null floor on the queue-honest fill, and are sub-window consistent (86–100%
positive). **CC is a hold** (positive queue $/hr but sits ~$0.5 below its own churn floor — not
distinguishable from rebate churn).

But the SEATs are dominated by **capacity**, not edge — see below.

## Capacity — the whole point, and the sleeve's undoing

A $5k maker leg as a % of the pair's **hourly** notional (24h_vol/24):

- **HYPE — the only genuinely deep pair (0.9% of hourly)** — has a **negative premium**. Its book can
  absorb size, but there is no timing structure; the +9.97 raw queue $/hr is below its +16.62 churn floor.
  Depth without edge.
- **The 3 SEATs are all capacity-starved:** BILL a **$5k leg is 32% of an entire hour's volume**; XPL 10.7%;
  MON 10.3%. A single leg that large is a huge share of the book — real fillable per-leg is a small
  fraction of $5k. Scaling the premium to a realistic per-leg size (~1–5% of hourly, so it clears in
  minutes and doesn't walk the book): BILL ≈ \$0.12–0.60/hr, XPL ≈ \$0.25–1.24/hr, MON ≈ \$0.16–0.82/hr.
  **Aggregate real structural premium ≈ \$0.5–2.7/hr** across all three — on top of a fragile rebate floor.

The field shows a clean **inverse relationship**: the one pair deep enough to deploy $5k (HYPE) has no
edge; the pairs with edge (BILL/XPL/MON) can't take the size. Edge and depth do not co-occur in this
rebate universe.

## Honest flags / caveats

- **No L2 book in the tapes → queue fill is a volume proxy.** These are TRADE tapes (`spread`=0 on all;
  measured half-spread = 0.0 bps). True `fill_model="queue"` needs `best_bid_sz`/`best_ask_sz` from the
  book collector; with zero book sizes it degenerates to front. I supplied a documented queue-ahead proxy =
  **median active-second volume** (our $5k order fills only after ~one typical active-second of opposing
  flow clears past the front). This is the honest trade-tape stand-in; a real queue-honest bound (and any
  real adverse-selection cost) needs the L2 book — treat both front and queue as still somewhat optimistic.
- **hs = 0 means the sim neither pays nor earns the spread.** Real fills post at the touch and would earn
  some spread but also eat adverse selection the proxy doesn't model — roughly offsetting; flagged, not resolved.
- **Data spans vary.** HYPE/SYN/MON/XPL/NIGHT/PLAY ≈ 120d; SLX 41d; CC/BILL 28d; **CAP only 9.7d** (its
  numbers are the least robust — but its verdict, REJECT on negative premium, is not close).
- **BILL's SEAT rests on the thinnest, most capacity-bound pair** (\$0.37M/24h, 32% capacity) — treat it as
  the softest of the three; its edge is real on-tape but essentially undeployable at size.
- **The rebate inflates every raw number.** Under −2bp, churn alone is positive, so the null floor is high
  and 6 of 10 pairs post a positive raw queue $/hr while failing on premium. Premium is the only honest read.

## Sleeve economics — is the heavy-volume small-cap sleeve worth building?

**Recommendation: NOT worth building as a per-$ edge sleeve. Marginal, optional value as pool headroom.**

- Only **3 of 10** heaviest pairs clear the queue-honest + rebate + null gate, and their **capacity-scaled
  structural premium is tiny (~\$0.5–2.7/hr aggregate at realistic per-leg size).** The one deep pair (HYPE)
  is pure churn.
- ~2/3 of even the SEATs' raw queue $/hr is the rebate floor (BILL 9.89/13.70, XPL 4.24/6.89, MON 4.49/6.19)
  — i.e. mostly the paycheck, only ~1/3 real timing edge, and the paycheck portion is what adverse selection
  eats first at real fills.
- This matches the **S67 pool-bound finding exactly**: backup/thin cells buy **uncorrelated pool headroom +
  a rebate paycheck for idle-majors windows**, NOT per-$ edge (best per-$ config remains majors-only). BILL/
  XPL/MON qualify as *seatable, idle-fill* cells under the greedy allocator (never dropped, funded only when
  majors are between legs and their edge clears the bar) — but they should **not** pull capital from the
  majors pool, and none justify building infrastructure around the small-cap sleeve on their own.
- If the allocator wants a few uncorrelated idle-fill seats, **seat BILL/XPL/MON (FWD, rev 0.10–0.13) at a
  small per-leg cap and let them collect the rebate when majors are idle.** Otherwise the heavy small-cap
  sleeve does not earn its complexity vs just running the majors pool.

### Recommended candidate CellConfigs (idle-fill seats only, per-leg-capped — not core capital)
```
CellConfig("BILLUSD", venue="kraken", side=+1, rev=0.10, grace=300, improve=0.5),  # premium +3.82, but 32% capacity — softest
CellConfig("XPLUSD",  venue="kraken", side=+1, rev=0.13, grace=300, improve=0.5),  # premium +2.66, 10.7% capacity
CellConfig("MONUSD",  venue="kraken", side=+1, rev=0.13, grace=300, improve=0.5),  # premium +1.70, 10.3% capacity
```
Provisional (tape-proxy fill, no L2 book, front/queue both somewhat optimistic; recommendations only).
