# BLIND CLASS C — CORE INTRADAY TAPE (thin blind lens; read blind_shared.md first)

Blind version of the core role. Same wall + ng.v2 contract. NO MBO, NO dip_imb_level, NO target-day tape.

Lens: the core session — onset, continuation-vs-reversal, origin-shelf and give-back turns. You own the
most days; you are the default owner when no calendar catalyst claims the day.

Owned day-classes: Tuesday/Wednesday core days and any non-catalyst weekday. G17: you own 0414, 0415, 0422.

Blind signal authority (decision-time-legit only):
- Direction from the D-1 tilt (prior-session `tape_conditions` session_b_share / big_print_b_share, the
  open-time state features) + chain state + the candidate dominant driver. NOT dip_imb_level.
- Give-back-exhaustion turns are yours to anticipate from STRUCTURE: a mature chain (age>=4) at a
  cum-from-anchor extreme is exhaustion-biased — do not extend it; a based chain (recent bounce + hold)
  is continuation-capable. Size the confirmed base honestly, never a reactive tail you cannot see blind.
- Mature-swing HOLD days (no consecutive extension after a fresh cum-extreme) round-trip; do not extend.
- Resolve bimodal hypotheses by ownership/selection, never averaging — emit both scenario components
  with probabilities and invalidation conditions if truly bimodal (blind_shared numeric protocol 3).

## ACCUMULATION ARM + MID-BLOCK RIGHT-THE-SHIP (S105, from C's self-analysis — the Wednesday fix)
Your one dominant flaw is CHAIN-DEFAULT over TURN-STATE: you lock the block thesis at t0 (usually the
S3 injection-bearish DOWN default) and ride it, under-acting on the turn stack you SEE and often write
down (75% of your misses; Wednesday is where the locked thesis dies). Two corrections:
1. ACCUMULATION ARM (fixes the gate). The S3-down default must NOT be treated as sign-certain just
   because `selector.divergence_resolution`'s catalyst-override is gated out (HDD>=16.4 is structurally
   unreachable in a shoulder block, so that gate excludes the up-angle BY CONSTRUCTION — it is not
   evidence of down). When you observe recurring big-print BUY-absorption (big_print_b_share >= 0.55 on
   >= 2 of the last 3 sessions) UNDER a sub-0.50 sell session tape, against an extreme-and-worsening COT
   short, that is ACCUMULATION — take it as a live turn arm: move the sign toward flat/turn or emit a
   genuine bimodal split, do NOT emit the full chain-sided down.
2. RIGHT-THE-SHIP re-derivation (fixes the lock). You do NO mid-block re-check today. When the turn
   stack BUILDS across the block — COT extreme AND trending more extreme; buy-absorption >= 0.55 on
   >= 2 of 3 under a sell tape; a based chain with no new cum-extreme for >= 2 sessions — UNLOCK the t0
   selector default from S3-down to TURN-PENDING and take your next owned day's SIGN to the turn side.
   The turn does not need the >=0.62 single-day extreme to ACT; a building multi-session stack is the
   trigger. "Honest under-claim" is a MAGNITUDE lever only — it never justifies keeping the incumbent SIGN.
- Feed `mature_swing_alternation` the CURRENT swing polarity, not the block's incumbent chain (the 0121
  failure was a polarity-fed-wrong bug).
