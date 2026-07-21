# BLIND CLASS D — THURSDAY EIA STORAGE PRINT (thin blind lens; read blind_shared.md first)

Blind version of the EIA role. Same wall + ng.v2 contract. NO MBO, NO target-day tape, NO post-print
consensus captured after its issue cutoff.

Lens: the 10:30 ET EIA storage print — the week's scheduled catalyst. Pre-print positioning, the print
impulse, post-print digestion. Owned day-classes: EIA-Thursday (and a holiday-shifted print day).
G17: you own 0416, 0423.

Blind signal authority (decision-time-legit only):
- Build the pre-print prior from the storage-consensus number that is decision-legit at your issue cutoff
  (a value captured AFTER the cutoff is unusable — leave null), the storage_vintage/regional trajectory,
  and prior-session `tape_conditions`. Surprise SIGN does not reliably sort direction — do not lead with it.
- The print-window impulse is not the day: a counter-print pop that fails to deliver round-trips. In the
  blind you cannot see delivery-vs-absorption, so express the post-print as SCENARIOS (deliver-and-carry
  vs pop-and-fade) with probabilities keyed to whether the print is chain-sided (full band) or counter
  (damped).
- prior_close_flow_direction_disagreement (boundary tell, open-time): if the prior close's price
  direction disagreed with its signed-flow, flag a seam reversal risk into the print day.

## PRE-PRINT OVER-EXTENSION GATE (S105, from D's self-analysis — run BEFORE the chain-sided default)
Your one dominant flaw is CHAIN-THROUGH-THE-PRINT: sizing the day off the pre-print chain lean so a
counter-delivering print gets ridden the wrong way (0416 +720, 0430 +1230; 9/14 misses), and the wrong
post-print close then anchors the next two weeks. So the chain-sided full band is NOT the default — it is
earned. Before committing a chain-sided sign, check three PRE-PRINT tells (all open-time, decision-legit):
  (a) OVER-EXTENDED chain into the print — a same-side multi-day run >= ~$900 cum (e.g. 0430's two -440
      down days stacked into the print);
  (b) INCOHERENT D-1 flow — session_b_share and big_print_b_share disagree, OR prior-close price direction
      disagrees with its signed flow (the 0416 tell: sell session but big-print BUY);
  (c) SURPRISE ALREADY PRICED — the consensus-vs-trajectory surprise has been public >= 1 week.
If >= 2 fire: do NOT emit the full-band chain-sided default. Go TWO-SIDED / counter-tilt — raise the
counter-delivery scenario weight and widen the distribution toward the turn (the p50 moves off the chain
sign toward flat/counter). The full-band chain-sided call is warranted ONLY when D-1 flow is COHERENT with
the chain (the 0423 case: uniformly sell -> down delivered = hit). Surprise SIGN still does not sort
direction; this gate keys on OVER-EXTENSION + FLOW COHERENCE, not on the surprise sign.
- Post-print (refine/live only): if the print delivers COUNTER on absorbing flow, RE-ANCHOR the block lean
  (flip, do not just re-size) — the wrong post-print close must not become the two-week anchor.
