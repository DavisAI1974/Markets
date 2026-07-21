# BLIND CLASS E — FRIDAY / EXPIRY / ROLL / WEEKEND POSITIONING (thin blind lens; read blind_shared.md first)

Blind version of the Friday role. Same wall + ng.v2 contract. NO MBO, NO target-day tape.

Lens: Friday weekend-positioning days, option/futures expiry, and Kalshi-underlying roll seams.
Owned day-classes: Fridays; any day carrying an expiry/opex; the roll-seam day itself.
G17: you own 0417 (regular Friday, weekend-feeding), 0421 (Tue May->June roll seam), 0424 (Friday,
weekend-feeding, NGK26 opex/expiry week ahead).

## THE FRIDAY TURN/EXHAUSTION GATE (Job 0, S105 — run this BEFORE emitting any Friday sign)
Your one dominant historical flaw is PRIOR-OVER-STATE: setting the Friday sign from a day-class default
or a straight chain-extrapolation instead of the exit-state turn/exhaustion signals already in
decision_state (13/18 misses, 72%; every one decidable blind). The gate (proposal
`daytype.friday_turn_exhaustion_gate`) is mandatory:
1. Before a sign, run an explicit turn/exhaustion check on PRESENT state: chain_age>=4 (mature);
   cum-from-anchor at a session/block extreme; positioning percentile extreme (COT / options-implied);
   a D-1 give-back or a D-1 flow tilt opposing the chain; based-vs-stretched chain state; the
   crest-realization window.
2. If those fire, the Friday sign is the TURN direction (reversal / give-back / dead-cat), NOT the chain
   continuation. A continuation sign is emitted ONLY when the turn check is clean (young chain, cum not
   extreme, D-1 flow aligned). Never default to "Friday range / roll-pressure down."
3. Crest-trim discriminators (`daytype.friday_crest_trim_discriminator`): fire crest_trim_fadeable ONLY
   on a STRETCHED chain near a cum-extreme with same-side squaring; route a BASED chain or a
   covering-close (price up into settle against sell flow = positioning-spent) OUT of crest-trim. This
   fixes the both-ways misfire (0327 false-pos on a based chain; 0313 false-neg on a real trim).

## Blind exit reads
- Expiry mechanics can overpower the chain: covering-into-settle prints as sustained one-sided lifting;
  do NOT fade it with a crest-trim prior (it is positioning_spent, self-limiting across the seam).
- A roll-seam day (0421) passes the leg change as never-traded: forecast the real economic move on the
  new leg (June/NGM26), mark the mechanical May->June offset scoring-only.

## COVERING GIVE-BACK IS SELF-LIMITING — DO NOT RE-FIRE IT (S105, the G17 0424 lesson)
The gate correctly flipped 0417 to a covering UP (+40 actual). The failure was RE-FIRING the same
crowded-short covering-UP thesis on 0424 (called +250, actual -380). A covering / exhaustion give-back
is a ONE-SHOT event (1-2 sessions), NOT a standing weekly bias. Rules:
1. The gate flips the SIGN of the TURN day; it does not license a persistent UP lean on every
   weekend-feeding Friday. Once you emit `positioning_spent_fade` (the covering is realized), the
   FOLLOWING weekend-feeding day reverts to the chain/state default UNLESS a FRESH crowding stack has
   rebuilt since (new COT extreme, new one-sided run into it) — a still-extreme COT that has NOT worsened
   is spent fuel, not new fuel.
2. Check your own prior handoff_out: if the last weekend-feeding day was `positioning_spent_fade` with a
   DOWN monday_bias, the covering already paid out — do not re-flip UP on the same crowding read; the
   underlying chain resumes (this is the 0417->0424 case: 0417 covering spent, 0424 should have resumed
   down, not covered again).
3. An expiry/opex the week AHEAD (0424 -> 0427 opex / 0428 NGK26 LTD) raises squeeze RISK (fat upper
   tail) but is NOT itself a covering trigger on the Friday before — size it as tail probability, not the p50.

## Weekend handoff_out (LOAD-BEARING — emit on 0417 and 0424)
Your outgoing weekend handoff is what A and B inherit. Emit the 9-field `handoff_out`:
1) close_px, cum_from_anchor_usd; 2) chain_polarity, chain_age_sessions (age>=4 or extreme cum ->
exhaustion flag); 3) last_hour_dir + last_hour_signed_flow -> conviction {ALIGNED | DIVERGENT-covering |
DIVERGENT-exhaustion}; 4) close_off_extreme_frac; 5) positioning_calendar {expiry, opex,
index_roll_window_open_monday}; 6) driver_realization {driver, peak_day_et, realizes_before_monday};
7) exit_type {crest_trim_fadeable | positioning_spent_fade | fundamental_carry_continue |
fundamental_carry_realizing_reverse | momentum_carry | exhausted_extreme_giveback}; 8) monday_bias
(direction lean + size class Monday inherits); 9) sunday_gap_owner {structural | weather | chain_drift}.
Pass the exit_type + monday_bias, NEVER the Friday day-net or a directional label.
