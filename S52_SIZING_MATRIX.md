# S52 CANONICAL $/hr MATRIX — corrected fill model (price-eligibility). Supersedes ALL prior matrices.

> ⚠ **Cite the cell, never a single number** (Greg's standing correction). Every $/hr = one cell of
> {venue, maker fee, fill model, deploy size, window}. ⚠ **ARTIFACT NOTE**: every matrix before S52 used
> `_leg_caps` WITHOUT price-eligibility — it credited flow that traded after price had left our limit
> (uncatchable). Those mk0 positives (+$7–18/hr SOL) were artifacts. This matrix is the corrected model:
> a resting limit fills only while price is at-or-through it. Fill-fraction asymmetry is REAL and
> load-bearing: SOL med fillable $483 on winners vs $6,161 on losers (the market fills you fully when
> you're wrong, rations you when you're right) — the rebate is what makes that trade survivable.

## One-shot executor (deployed), rest-until-turn fills, flat, $/hr at $1k / $5k per leg

### Coinbase (multi-window books, 29–196h)
| cell | mk0 | mk−1 (rebate venue scenario) |
|---|---|---|
| SOL  | −2.7 / −39.4 | **+17.5 / +30.4** |
| XRP  | −3.2 / −28.3 | +14.2 / +29.0 |
| ETH  | −5.1 / −31.5 | +9.0 / +26.4 |
| BTC  | −1.0 / −6.9  | +3.9 / +13.9 |
| DOGE | −4.4 / −15.5 | −0.7 / −6.2 (fails even with rebate — thin tape) |

**mk0 is measured-DEAD at size on every cell** (fill-window audit + TIF sweep + head-to-head, all three
agree). No cancel-remainder window rescues it (best ≈ $0 at $100/leg).

### Bybit venue cells (⚠ ONE 5.83h window each — PROVISIONAL, confirm as the cron accrues)
| cell | mk+2 (standard) | mk0 | mk−0.5 (MM2) | mk−1.25 (MM3) |
|---|---|---|---|---|
| SOL (spread 1.24bps, tape $15.7M/hr this window) | **−32.8 / −156.9** | +5.7 / +10.5 | +15.4 / +52.4 | **+29.8 / +115.2** |
| ETH (spread 0.06bps, tape $39.8M/hr) | **−58.2 / −272.9** | −5.3 / −35.6 | +7.9 / +23.7 | **+27.8 / +112.7** |

- **Bybit standard fees are catastrophic → the MM program is the EXISTENCE condition, not an optimization.**
- MM3 is worth ~10x the mk0 case (SOL +10.5 → +115 at $5k). SOL = first cell (spread + rebate both pay);
  ETH = second (pure rebate harvesting on the bigger tape; no spread to capture).
- Tape multiple this window: 3.3x (SOL) / 6.9x (ETH) vs Coinbase — below the 24h-ticker 10x; one quiet slice.

## Sizing columns (status)
- **Entry-conviction sizing** (`size_legs`, deployed): real per-leg OOS (+16..47% on the forward ledger,
  25,845 trades) BUT at deployed size under the corrected fills it is rebate-contingent (at mk0 sized ≤
  flat — up-sizing feeds the adverse-fill asymmetry; at −1bp sized ≈/> flat at rest). Keep deployed;
  cite per fee tier.
- **Winner-side sizing**: the twxv4t anti-martingale kill STANDS (no leg-outcome persistence). The
  twxv4t green-add fillability kill is SUPERSEDED (measured the wrong window) — replaced by the ACCUM
  design result below.

## Accumulate design (Greg's, S52 — `odcore/swing_accum.py`) — R&D thread, validated in miniature
On the zigzag swing-scale stream (θ≈4×(hs+taker)≈20–24bps) + dipole gate, SOL Coinbase, $5k, mk−1:
**+$1.3–1.6/hr on ~66 legs, beats shuffle control (−$3) AND reversed control (−$3)** — first arm where
the gate beats its shuffle and reversed loses. Mechanics per the design: 4:1 winner/loser notional
(all-in $5k on confirmed winners netting +$0.76..+$63.73; dumped $1,250 starters at −$1.50), add-height
~2.2bps (all-in-on-confirmation beat the S40 crescendo). Loses on every micro scale (nothing to confirm
at 1–4bps swings). Tiny $ → NOT deploy; refine bands + confirm multi-window + Bybit data (S53).
Renders: `docs/renders/s52/` (60 trades). Spec: `STRATEGY_accumulate_S52.md`.

## Sources
`_s52_accum_vs_oneshot_results.json` (7 cells × 4 scales × tiers), `_s52_fill_window_audit_results.json`,
`_s52_tif_sweep_results.json`, `_capacity_model_results.json` (refreshed, corrected defaults).
