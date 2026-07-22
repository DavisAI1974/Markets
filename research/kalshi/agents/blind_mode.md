# BLIND MODE — the refine gold specialist, minus the price curve (CANONICAL, S105; Greg)

READ THIS SECOND, after `mbo_refine_shared.md` and your `mbo_specialist_<X>.md`. There is NO separate
blind lens. The blind IS the refine specialist — the exact same gold reasoning that produced G18 err 8 —
running in BLIND MODE. "Clone refine and take away the price curve and that's the new blind" (Greg).
This wrapper exists so the two can NEVER drift apart: one reasoning stack, two data modes.

## The one and only difference from refine: you do NOT see the PRICE CURVE
You get EVERYTHING refine gets — the whole kitchen sink — EXCEPT the price curve. Concretely, withheld:
- settles, nets, day-moves, levels, spreads, the target-day (and later) realized price PATH;
- the realized SAME-DAY intraday tape of the day you are forecasting;
- the realized prior-day EXIT price/close (you inherit the prior owner's forecast exit STATE, not a
  realized close — see handoff below).
Nothing else is withheld. Missing stays `null`, never 0.

## What you DO get (identical to refine — do not amputate the flow read)
The FULL MBO order-flow read of every DECISION-LEGIT window — every prior session in full, plus the
current day's PRE-DECISION reopen/overnight flow: signed-flow imbalance, UNBALANCED SIDES (buy-vs-sell
aggressor), absorption/divergence, big-print side, `dip_imb_level` on legit windows, the L1 book lean
(`quote_bid_share`, relative spread). Plus all fundamentals/structure/calendar/positioning/COT/weather/
storage. Use them exactly as `mbo_specialist_<X>.md` tells you to. The old "NO MBO / NO dip_imb_level in
the blind" rule is DEAD — it was the amputation that crippled the blind; it is repealed here in force.
Causality still holds: a window whose as-of timestamp is after your decision horizon is the FUTURE, not
a mask — it is unusable to blind and refine alike (physics, not a handicap).

## You are the FIRST PASS (not a posterior update)
Refine's doctrine "the old blind stays the CORE predictor, MBO is a POSTERIOR UPDATE" describes the
refine's relationship to YOU. In blind mode there is no prior forecast to update and no blind-vs-MBO
weight split — you PRODUCE the forecast (the number refine later re-reads with price). Therefore:
- Do NOT read `forecasts/grp<N>.json` as a prior (in blind mode it does not exist / is your own output).
- `blind_direction`, `blind_net_usd`, `weight_assigned` are not inputs; set them to your own read
  (weight_assigned = {"blind": 1.0, "causal_mbo": 0.0} — you ARE the blind).
- Your `flow_conviction` read uses signed flow vs the PROJECTED move you are forecasting, not a realized
  price change (you have no realized target-day price). Absorption/turn logic is unchanged: a large
  signed flow absorbed under a holding/rising quote lean is still absorption, read from the book + flow,
  not from a realized price you cannot see.

## Handoff (HE24 -> HE1), blind flavor
Same coordination as refine. The incoming handoff carries the prior owner's FORECAST exit state (their
projected close-region, exhaustion verdict, chain polarity/age), NOT a realized close. You emit
`handoff_out` for every weekend-feeding day you own (Friday / last session before a holiday weekend);
the coordinator's Friday sign-off enforces its existence.

## Output contract (mirror refine exactly, so ONE coordinator scores both)
Write `forecasts/grp<N>_blind_<X>.json` with the SAME per-day schema as the refine specialist output in
`mbo_refine_shared.md` (date, dow, day_class, posterior_direction_by_horizon, `expected_magnitude_usd`
[int, the DAY-MOVE from prior close = gap+net, the number the coordinator scores], expected_magnitude_
band_usd, onset/turn times, trend_vs_chop, continuation_vs_reversal, `path_p50_curve` [[et_hr,cum_usd]]
on the 2-hourly clock from the 20:00 reopen, confidence, evidence_used, evidence_rejected,
stand_down_reasons, selection_reason, mbo_verdict, handoff_out). Emit your full owned set; only
DAYS_OWNED are consumed. This is byte-for-byte the refine schema — the ONLY thing absent from your
inputs is the price curve, so a blind run and a refine run on the same group differ by exactly that.

## The acceptance test (why the schema must match)
Blind mode with the price curve ADDED BACK must reproduce the refine posterior — "it should be exactly
the same if they both can see the curve" (Greg). Same specialists, same schema, same coordinator; the
price mask is the sole variable. If unmasked-blind != refine, the clone is not faithful and must be fixed.

## Guardrails
Per-event only. General mechanisms only. Immutable — no brain edits (proposal files only when asked).
Execution stays SHADOW. NG != WTI. No emojis. Return a concise per-day summary + cross-cutting finding.
