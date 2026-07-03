# STRATEGY — Accumulate-at-the-turn (Greg, S52) — the full spec, in Greg's terms

Laid out piece by piece in the S52 dissection session (2026-07-03), mapped line-by-line against the
deployed one-shot (`odcore/swing_maker.py`). Implemented as the sibling executor `odcore/swing_accum.py`
(the validated one-shot is NOT forked or modified — it stays the deployed baseline). Scored by
`scripts/_s52_accum_vs_oneshot.py`.

## The design (Greg's words, S52)

1. **Turn selection — the dipole picks the REAL turns.** "We have to eliminate a lot of the noise with
   little movements and not just hit lift hit lift hit lift over and over thousands of times over tiny
   movements like we were before. this is where the dipole comes in." Few, big swings — not the 150+/hr
   micro-turn stream.
2. **At a valley: best bid on the way up, offer pulled.** "Starting there we always want to have the
   best bid going up so that we are always being hit on the way up while pulling back our offer so that
   it's never lifted."
3. **Two-phase size schedule.** Incremental while UNSURE ("if we need to be incremental because we are
   unsure that's fine too"), then on CONFIRMATION: "if we acknowledge a winner, we want to go all in on
   the remainder as quickly as possible. we don't want to be incremental on confirmed winners the whole
   way up... we want to have as much of our trading done as quickly as possible on confirmed winners."
4. **At the peak: unload for the highest dollar amount, fees included.** "The goal is to unload the long
   position for the highest dollar amount whether that's someone lifting our offer or we hit a bid,
   taking fees into account." Unload max at the top ("our highest priced buys on the way up get matched
   to our highest price sales on the way down which is why it's important to unload as much as we can at
   the top" — LIFO layer matching); keep the best offer on the way down for the remainder; hit bids when
   not getting lifted. The unloaded fraction at the top (25%, 50%, 62%...) is an OUTCOME, never a knob.
5. **Symmetric down-leg.** "We want to do the opposite on the way down... sell as much as we can as soon
   as we can after we have confirmed" — the peak unload doubles as the short build, front-loaded.
6. **Loser protection is structural.** "The point with my strategy is that you don't go all in on a
   loser and you can dump it quickly if it starts going against you in a worst case." Size arrives only
   with confirmation, so wrong calls are small by construction and the dump is cheap.
7. **The accepted trade-off.** "We may not get the absolute best price at the bottom on our complete
   trade but we eliminate a lot of the losers."

## The five deltas vs the deployed one-shot (verified against swing_maker.py)

| # | Greg's design | deployed one-shot |
|---|---|---|
| 1 | trailing best bid accumulates up the leg; size arrives with confirmation | ONE fill at the valley price; no re-peg, no adds |
| 2 | layered unload: max at top, best offer down the slide, fee-aware taker on remainder | single maker fill at the turn closes everything (sim credits it at the turn price with no price-eligibility) |
| 3 | per-lot inventory, LIFO matching | one open_px / close_px per leg |
| 4 | quick cheap dump on failed calls (small position) | no adverse exit at all — a failed call rides the whole slide, and at deploy size losers are the only legs that fill completely (S52 fill-asymmetry: SOL med $483 winners vs $6,161 losers) |
| 5 | dipole-selected REAL turns only | 153 turns/hr on SOL over 2–4 bps swings |

## Why prior DEAD labels do NOT close this design (each verified)

- **S51 "scale-in falsified"** — that verdict attaches to the FRONT-OF-QUEUE fill-model class (the
  reversed-side control out-earned conviction = the class validates nothing), and S52 showed the same
  class failed the price-eligibility audit. Model-class kill, not a strategy kill.
- **S47 "stops falsified"** — tested on the one-shot, where a stop cuts a FULL-size position (winners
  that dip get cut expensively). In this design wrong-legs are SMALL by construction; the same exit is
  cheap. Different regime.
- **S47 "entry gates dead"** — on the one-shot every leg is cheap and +EV, so any filter subtracts. The
  accumulate cycle is expensive per cycle and needs big swings — turn selection is load-bearing here,
  not subtractive.
- **S47 "winners not separable at entry"** — STANDS, and this design routes around it: it does not
  predict the winner at entry; the market reveals it mid-leg (confirmation) and size follows.

## Known headwinds (measure, never assume away)

- **S40 crescendo**: opposing flow peaks INTO the turn, so passive trailing adds concentrate near the
  top of the leg. Mitigated by the all-in-on-confirmation schedule (size anchors just above the
  confirmation point); measured by the add-height metric in the harness.
- **Turn-stream scale (S52 smoke finding)**: the lean-based flip detector yields ~2.5 bps median swings
  at EVERY zigzag REV — too small for the accumulate cycle to engage (confirmation is fee-floored). The
  design requires the SWING-SCALE stream: causal price zigzag, θ = 4×(half_spread+taker) bps (the S36b
  minimum-tradeable-swing arithmetic, fixed multiple — not a tuned knob).
- **Exit realism**: the unload is a TRAILING best offer down the slide (per the design), priced per cell
  — not a fixed limit at the exit-turn price (a fixed post-peak offer almost never gets lifted).

## Scoring rules (standing)

Controls on every run: shuffled-gate (same pass-rate, no information) + reversed-side (if reversed wins,
the model class is broken — report, don't deploy) + honest-queue bracket (queue_frac=1). Per-cell verdicts;
never tune off one window; the Bybit venue books are ONE 5.83h window each = PROVISIONAL. The one-shot +
forward paper ledger remain the deployed baseline until this variant survives multi-window confirmation.
