# FROZEN GOLD MASTER - REFINE (S105, brain s102.9) - DO NOT EDIT

This directory is a byte-identical, UNTOUCHABLE snapshot of the 5-specialist MBO causal-refine
agent stack as it stood when it produced the reference results:
  - G15 MBO refine: 12/12, mean abs err 72
  - G18 MBO refine r2: 10/10, mean abs err 8 (HE24->HE1 halved r1's err 30)

This is "the refine that used the market data (almost) perfectly" (Greg, S105). It is preserved so
the perfect reasoning can never be lost to a later edit. The NEW BLIND is a clone of THIS stack with
the ONLY difference being the price-curve mask (Greg: "clone refine and take away the price curve and
that's the new blind"). Any iteration happens on the WORKING copies (../mbo_*.md and the blind clone),
NEVER here.

Frozen files: mbo_refine_shared.md, mbo_specialist_{A,B,C,D,E}.md
Provenance commit: recorded in the commit that adds this directory.
