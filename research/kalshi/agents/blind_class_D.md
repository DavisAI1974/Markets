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
- Direction still anchors to the D-1 tilt + chain state; the print sizes/reweights, it does not license a
  blind sign flip on surprise alone.
