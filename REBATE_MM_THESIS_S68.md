# REBATE MARKET-MAKING THESIS — Honest Markout Test (S68)

**Question (Greg):** On Kraken's rebate-eligible alt pairs the maker fee is **−2 bp (a REBATE)** —
every passive fill pays us. Can we **get paid to churn**: rest passive maker quotes purely to
collect the rebate (+ any spread), *not* to time turns? Our swing sim's circular-shift **floor**
says the heavy-volume rebate pairs (e.g. CAP) earn large raw $/hr from exactly this churn. But the
floor is a **known inflation** — it under-charges **adverse selection** (S56: *never cite the floor
as edge*). This memo tests the thesis **honestly** by charging adverse selection via **markout**.

**Scope / discipline:** separate thesis from the mean-reversion swing signal. No live-code edits, no
commits. New pieces only: `scripts/_s68_rebatemm_markout.py` (tape markout engine),
`scripts/_s68_rebatemm_book.py` (book-honest validation). Results JSON in `/tmp/sc/`.

---

## TL;DR VERDICT

**Rebate-farming does NOT cleanly clear its own adverse selection.** Unconditional passive making is
adversely selected on **every** pair and on **real book data** (all markouts negative, growing with
hold time). The **+2 bp rebate is too small** to cover the pick-off except in a narrow corner:

- **Clears (barely), short-hold only:** `HYPEUSD`, `CCUSD`, `MONUSD`, `NIGHTUSD` — the liquid,
  balanced-flow names — net **+0.3 to +1.3 bp/fill** at a **≤5 s** flatten horizon, honest (zero
  spread credit). All go **negative by 30 s.**
- **Fails outright:** `CAPUSD`, `SYNUSD`, `SLXUSD`, `XPLUSD` — the volatile / wide-spread / thinner
  names. Adverse markout (−2 to −11 bp @5 s, −5 to −21 bp @30 s) swamps the rebate.
- **CAP specifically:** its big swing-sim floor is an **adverse-selection illusion**, not real rebate
  money (see §4). CAP is the *worst* pick-off in the set.

**"Get paid to churn" is a real but small, fragile, execution-intensive edge confined to a few liquid
rebate names at sub-5-second inventory turnover — NOT the free money the floor implied.** The
deflationary answer dominates for the thin names. Recommendation: at most a **narrowly-scoped HYPE-class
prototype** with a real maker/cancel + inventory loop — not a broad deployment. (§7)

---

## 1. Why the swing floor can't answer this — and the honest fix

When you rest a passive maker order you get filled **preferentially right as the market moves against
you** (a resting bid fills when sellers turn aggressive — you buy just before it drops). That is
adverse selection / pick-off. The swing sim's fill models don't fully charge it, so a big floor $/hr is
partly artifact.

**Honest per-fill economics (built here):**
```
net_bps(fill, Δ) = spread_capture_bps + rebate_bps(+2) + markout_bps(Δ)
markout_bps(Δ) = favorable-signed mid move over Δ after the fill
               = BUY:  (mid[t+Δ]-mid[t])/mid[t]·1e4   ;  SELL: (mid[t]-mid[t+Δ])/mid[t]·1e4
               NEGATIVE markout == adverse selection == picked off.
```
A pure both-sided rebate-farmer filled by random taker flow realizes the **markout distribution of the
tape**. If mean adverse markout > rebate + realized spread, the thesis **fails**.

### The measurement trap (and how it's avoided)
The tape `mid` is the **last trade price** (per `load_bins`), *not* a true mid: on a sell cell it sits
near the **bid**, on a buy cell near the **ask**. Naively marking a resting-bid fill (at the depressed
sell-cell price) forward to later trade prices **recovers the bid-ask bounce as fake favorable
markout** — the classic MM-backtest lie, largest exactly on wide-spread pairs.

Fix: a **bounce-free synthetic mid** = geo-mean(last buy-cell px, last sell-cell px), which brackets
the true mid. That cleanly separates:
- **spread capture** = distance from our touch fill to the synthetic mid (real, but on volatile thin
  alts this conflates spread with price moves between prints, so it *overstates*);
- **adverse markout** = favorable move of the **synthetic mid** (the true pick-off).

Two defensible brackets are reported per pair:

| Bracket | Fill / mark | Reads as |
|---|---|---|
| **STRICT** (`net_pf_bps_rebate_only`) | synthetic-mid markout, **zero** spread credit | *Does +2 bp alone beat adverse drift?* — the honest floor. **Trust for wide-spread pairs.** |
| **REALISTIC** (`net_pf_bps_realistic`) | fill at touch, mark to tape's own mid (real bounce = real spread) | Central estimate **for tight-spread pairs** (strict≈realistic there). **Over-optimistic for wide-spread pairs** (re-credits volatile bounce). |

The **OPTIMISTIC** synth-full-spread bracket is discarded (spread term inflated by volatility on thin
alts). Fill model = **front-of-line** (every opposing print fills our touch quote up to a $5k clip) —
the best case for the thesis; the sign of adverse selection is queue-independent, and §5 validates it.

---

## 2. Per-pair honest markout (tape, 28-day+ Kraken tapes)

Markout is **favorable-signed** (negative = adverse). Rebate = +2 bp/fill. Clip = $5 000.

| Pair | span h | fills/h | adv_mk 5 s | adv_mk 30 s | **STRICT net 5 s** | SEAT | REAL net 5 s | $/hr (real) | REAL net 30 s |
|---|--:|--:|--:|--:|--:|:--:|--:|--:|--:|
| **HYPEUSD** | 2894 | 212 | −0.75 | −1.97 | **+1.25** | ✅ | +2.02 | +51.1 | +1.88 |
| **CCUSD**   | 672  | 80  | −0.98 | −2.40 | **+1.02** | ✅ | +1.75 | +5.7  | +1.47 |
| **MONUSD**  | 2880 | 50  | −1.48 | −3.79 | **+0.52** | ✅ | +1.34 | +3.9  | +0.82 |
| **NIGHTUSD**| 2880 | 71  | −1.71 | −3.68 | **+0.29** | ✅ | +2.47 | +6.3  | +2.89 |
| XPLUSD  | 2893 | 47 | −2.25 | −4.79 | **−0.25** | ❌ | +1.55 | +3.0 | +1.26 |
| SYNUSD  | 2880 | 30 | −5.70 | −12.88 | **−3.70** | ❌ | +3.38† | +5.4 | +8.04† |
| SLXUSD  | 992  | 77 | −5.63 | −12.61 | **−3.63** | ❌ | +4.25† | +8.4 | +7.67† |
| **CAPUSD** | 233 | 114 | −10.80 | −21.34 | **−8.80** | ❌ | −0.85 | −2.8 | +5.20† |

SEAT = STRICT net > 0 at the 5 s (validated) horizon. **†** = REAL-net numbers for wide-spread pairs
(SYN/SLX/CAP) are **not trustworthy** — they re-credit the volatile bid-ask bounce (§1) and the book
validation (§5) shows long-horizon adverse selection is *worse*, not better. Read STRICT for these.

**Signal in the table:**
1. **Every** adverse markout is **negative** and **grows with horizon** — textbook adverse selection.
   A rebate-farmer only wins if it can flatten in **seconds**; holding 30 s+ loses on every pair.
2. Adverse markout tracks liquidity/flow balance: HYPE (212 fills/h, tight) −0.75 bp @5 s vs CAP
   (thin, bursty) −10.8 bp. The rebate is a fixed +2 bp; it only wins where pick-off is < 2 bp.
3. Only **4/8** pairs clear the honest floor at all, all **marginally** (< +1.3 bp/fill), all only at
   ≤5 s hold.

---

## 3. The adverse-selection cost the floor omits

Circular-shift null: rotate the price series vs the fill times → destroys the fill-timing↔adverse
coupling, leaving structure-free rebate + ~0 markout (what the swing floor effectively measures). The
gap **shuffle_markout − real_markout** = the pick-off cost the floor **under-charges**:

| Pair | omitted adverse cost @5 s | @30 s |
|---|--:|--:|
| CAPUSD | **+10.5 bp** | **+20.7 bp** |
| SYNUSD | +6.4 | +14.1 |
| SLXUSD | +5.4 | +12.4 |
| XPLUSD | +2.2 | +5.5 |
| NIGHTUSD | +1.7 | +3.5 |
| MONUSD | +1.5 | +3.9 |
| CCUSD | +1.0 | +2.5 |
| HYPEUSD | +0.8 | +2.0 |

The floor over-states per-fill edge by **1–21 bp** depending on pair/hold — largest exactly on the
thin, "high raw $/hr" names the floor makes look best. This is *why* the standing rule (S56) forbids
citing the floor as edge, quantified.

---

## 4. CAP resolution — illusion, not rebate money

**CAP's big swing-sim floor is an adverse-selection illusion.** Concretely:
- CAP has the **worst** honest adverse markout in the set: **−10.8 bp @5 s, −21.3 bp @30 s** per fill.
- STRICT net (rebate vs pick-off, no spread credit): **−8.8 bp @5 s, −19.3 bp @30 s.** Deeply negative.
- Even the *realistic* bracket is **−0.85 bp @5 s** (fails). The only positive CAP number anywhere
  (REAL +5.2 bp @30 s) is the **volatile-bounce artifact** — CAP's ~36 bp synthetic "spread" is price
  volatility between one-sided bursts, not a reliably quotable spread, and 30 s "recovery" on a
  bounce-free mid is actually **−19 bp** (the price keeps going).
- The floor omits **+10.5 bp (5 s) to +20.7 bp (30 s)** of pick-off per fill on CAP.

**Verdict:** CAP's headline raw $/hr is structure-free rebate churn on a name whose every passive fill
is a pick-off in front of a continued move. Charged honestly, CAP is the *worst* rebate-farm target,
not the best. **Not real money.**

---

## 5. Methodology validation — tape-proxy vs book-honest (BTC/ETH, 0 bp control)

Majors are **0 bp** (no rebate) — methodology control only. They have a **true mid** and **L2 queue
depth**, so we cross-check the tape front-of-line proxy against a queue-honest fill (`maker_book.py`
mechanic: join back of best level, fill only after cumulative opposing taker vol clears the queue).

| Coin | half-spread | Δ | adverse markout **proxy** | adverse markout **book-honest** |
|---|--:|--:|--:|--:|
| BTC | 0.018 bp | 1 s | −0.18 | −0.06 |
|     |          | 5 s | −0.23 | −0.36 |
|     |          | 30 s | −0.27 | **−1.34** |
|     |          | 60 s | −0.27 | **−1.56** |
| ETH | 0.217 bp | 1 s | −0.34 | −0.09 |
|     |          | 5 s | −0.59 | −0.37 |
|     |          | 30 s | −0.60 | **−1.52** |
|     |          | 60 s | −0.74 | **−1.71** |

**Findings:**
1. **Both models agree at short horizons (1–5 s), same sign & order of magnitude** (within ~0.2 bp) →
   the tape front-of-line markout accounting is **realistic for the ≤5 s window** — the window that
   matters for the thesis. The smallcap 5 s numbers are trustworthy.
2. **At 30–60 s they diverge: book-honest is ~2–5× MORE adverse.** Queue-honest fills only trigger
   after a *sustained* opposing burst clears the queue — precisely the toxic, directional fills —
   whereas front-of-line also fills on benign small prints. So the **tape proxy UNDER-states adverse
   selection at long holds.** This makes the smallcap **30 s STRICT numbers optimistic** → the real
   long-hold verdict is *worse*, reinforcing "flatten in seconds or lose."
3. **Majors net@0 fee is negative at every horizon** (BTC 5 s book −0.34, ETH −0.16): unconditional
   making loses on 0 bp venues — the tiny major half-spread (0.02–0.22 bp) can't cover pick-off. This
   is exactly the textbook result and confirms the engine behaves correctly; the rebate is the only
   thing that could flip it, which is why wide-spread **rebate** pairs are the only candidates.

---

## 6. What the honest numbers say about the mechanism

- Passive making is **structurally short adverse selection**; the rebate is a fixed +2 bp subsidy.
- The subsidy only wins where **per-fill pick-off < 2 bp**, which requires **(a) tight, balanced,
  liquid flow** (so fills aren't in front of moves) and **(b) sub-5-second inventory turnover** (so
  the compounding adverse drift doesn't run). Both hold only for HYPE-class names.
- Wide spreads on thin alts are **not** free spread capture — they are the *compensation for* the
  large adverse selection, and here the adverse selection wins (CAP/SYN/SLX).
- Realized spread capture (the difference between STRICT and REALISTIC on the tight names, ~0.8 bp on
  HYPE) is real but small and **execution-dependent** — you only get it if you actually rest at the
  touch and are not queue-jumped, which the book validation shows costs you fills.

---

## 7. Thesis verdict & recommendation

**Is "get paid to churn" a real deployable edge on any rebate pair after honest costs?**

- **Not as a naive both-sided quoter, and not on the thin/volatile names.** On CAP/SYN/SLX/XPL the
  +2 bp rebate is eaten by adverse selection — cleanly FAIL (the deflationary answer, and the correct
  read of the swing floor's CAP number).
- **A thin, real, conditional edge exists on the liquid rebate names** (HYPE the standout: +1.25 bp/
  fill honest @5 s, 212 fills/h, ≈ $51/h realistic on a $5 k clip; plus CCUSD/MON/NIGHT at +0.3–1.0
  bp) **only if** inventory is flattened within a few seconds and quotes actually rest at the touch.

**Is it worth a real build?** **Qualified yes, narrowly.** It is *not* the large free-churn income the
floor advertised, and it is **execution-bound**, not signal-bound: the edge is +0.3–1.3 bp/fill and
lives entirely in a sub-5-second window that the book validation shows is fragile to queue position.
Recommended next steps, in order of cheapness:
1. **HYPE-only prototype** with a real maker post/cancel loop, hard inventory cap, and a **≤5 s
   flatten** rule; benchmark realized markout against the −0.75 bp/5 s number here. If it can't hold
   the 5 s markout in live queue conditions, stop.
2. **Add a light stand-aside gate** (skip quoting during one-sided flow bursts — the CAP failure
   mode). Even a crude imbalance filter that removes the worst-decile adverse fills would move the
   marginal names (XPL/NIGHT) decisively positive; this is the one place the *swing-side* flow signal
   could earn its keep on the MM side.
3. **Do not** deploy broad both-sided quoting on CAP/SYN/SLX class names on the strength of the swing
   floor — the honest markout says they bleed.

**Bottom line:** the rebate covers pick-off only for the most liquid rebate pairs at seconds-scale
turnover; everywhere else, and especially on CAP, "get paid to churn" is adverse selection wearing a
rebate. A small, execution-focused HYPE-class build is defensible; a broad rebate-farm is not.

---
*Engines: `scripts/_s68_rebatemm_markout.py` (tape), `scripts/_s68_rebatemm_book.py` (book validation).
Results: `/tmp/sc/_s68_markout_results.json`, `/tmp/sc/_s68_book_results.json`. Tape-only + numpy,
causal. Rebate +2 bp/fill, clip $5 k, horizons {1,5,30,60}s. No live-code edits, no commits.*
