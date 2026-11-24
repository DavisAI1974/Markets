# decider_v1: what it skips and what it takes

It takes every opening signal, except in four cases where it skips and says why. If the packet gives no ground,
the answer is take, "no ground in the packet to skip; the rule's own signal stands", which is how the platform
runs today. It never raises: a packet it cannot read gets the same take with the reason said. It decides take or
skip only; the hold and the exit (give back 20% of the highest open profit) are not its business. Nothing here
has been tried on the tape, and nothing is claimed about it being good.

## The four skips

1. **Suspended additions** (`[suspended-additions]`). Skip when an earlier row of this run is a CX13 or CX14
   "suspend additions" on the same side as the signal and that warning is still standing (the newest row of that
   trade is still the suspension; a release, an "unresolved" end or a close ends it). Rests on CX13: "Suspend
   additions to the upward position", released "if the bid first rises above q's bid or exhaustion becomes
   nonnegative"; CX14 the same downward.
2. **Same run again** (`[same-run]`). Skip when the same rule already opened a trade on the same run of the same
   quote (the signal's own journaled `run` and `quote`). Rests on CL16: "The same run of the quote never opens a
   second trade", and the "OPENS AGAIN: at the next run's start" lines of CL03 and CL09.
3. **Crossed quote** (`[crossed-quote]`). Skip when the best offer is at or below the best bid at the signal.
   Rests on CL06: "Not while the best offer is at or below the best bid".
4. **Strong divergence on an entry with the move** (`[divergence]`). For CL01, CL03, CL06, CL10, CL13, CL15 and
   CL16 (their SIDE lines put the trade with the quote's step), skip when the 20-second flow carried on the newest
   dipole event known by then (bought minus sold over bought plus sold) runs against the trade's side at -0.20 or
   worse. Rests on the dipole research in CLAUDE.md: "DIVERGENCE: aligned_flow = imb_level x sign(price_drift);
   strong divergence (<= -0.20) -> ~65% reversal". It is the divergence read, not the flow as a direction call.

## Inferences (for Greg)

- 1: applying a CX13/CX14 warning to an opening signal of any rule on that side. The texts name the position
  they warn on, not other rules.
- 3: applying CL06's sentence to every rule. Only CL06's text says it.
- 4: that the flow on the newest known dipole event stands for the line now (the event can be minutes old, and
  the packet's dipole line shows the 20-second flow at its birth, not at the signal); that -0.20 is on the scale
  of ours (CLAUDE.md does not say the scale of `imb_level`); that this rule list is the "with the move" rules.
  CL10 is in the list although its own trigger is "the dipole stands on the OTHER side"; so it skips when the
  flow is strongly against, which is the case its trigger describes.

## What it cannot know

It sees no future and not the book: only what the packet carries. It was written with these trade days already
studied, as the rule texts were. The newest dipole event may be old. It cannot see the signal's lateness:
see below.

## What I left out, and why

- **Lateness** ("we're always late"). The packet's signal row carries `received` but not the exchange time of
  the message, so lateness cannot be read from it (finding for the packet's builder: `exchange` is in the
  journal row but not in ROW_FIELDS).
- **Spread / hit when retreating, lift when rising** (Greg). Reading it would skip every rule built to enter
  against a step (CL02, CL09, CL11, CL12, CL14), which are the rule texts as written; no number or text says
  how far back to look.
- **Hold time.** Not the decider's.
- **A mirror of the divergence skip for entries against the move.** The research gives a number only for the
  reversal side (-0.20); the mirror threshold would be invented.
- **Skipping on what other rules did at the same instant** (many rules fire together on the same quote). No
  source says a crowd is a ground.
- **Exhaustion collapse** (flow moving toward balance). The packet does carry two readings per dipole event
  (20 seconds before and after its birth second), so a comparison without a number is possible; I did not write
  it because the research states the collapse on a line over time, and these two readings are a second apart
  while the newest event can be minutes old. It is a candidate for the next version.
- **Any use of trades closed earlier** (their fill prices are in the packet). Using them would be reading
  outcomes, with no rule text or claim behind a threshold.
