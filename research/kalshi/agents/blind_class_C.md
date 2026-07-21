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
