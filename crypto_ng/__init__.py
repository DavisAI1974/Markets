"""CRYPTO AND NG: the crypto trading program of July 2026, brought back to be run on natural gas.

Greg, 2026-11-18: "Bring back the program and just designate it crypto and ng so we know what it is at a later date.
And it's crypto outputs if are any will now go into our excel sheet. They would be for observation or verification
purpose only".

What this is. `crypto_ng/program/` holds the crypto platform's own code as it stood on Markets commit `75b15fa`
(branch `claude/davisai-s71-counterparty-capacity-sf1168`, 2026-07-07), the code that made the trades behind the
picture "Kraken onset->exhaustion arcs REGROUPED BY TYPE": the turn finder (`flip_detector.py`), the trade maker
(`swing_maker.py`), the cell runner (`platform.py`) and the divergence read it writes beside each trade
(`info_dipole.py`). Three of the four files are byte for byte the July files; `platform.py` differs in three import
lines only, so that it reads these copies and not today's `odcore` (which was changed on 2026-11-16).
`PROVENANCE.md` has the fingerprints and `tests/crypto_ng/test_provenance.py` proves them.

What it is for. ONE thing: the natural gas exhaustion render made the way the crypto one was made ("The only
difference between the two should be that was crypto and we're doing ng"). The program makes the trades the arcs
follow. Its outputs are for OBSERVATION AND VERIFICATION ONLY: never a signal, never an input to another
calculation, never a trade result of ours.

What it is not. It is the ONE exception, on Greg's explicit word, to "no bitcoin-era rules". The fill rule, the
wait, the fee settings and every other crypto trade rule inside these files apply inside this package and nowhere
else. Nothing here may be imported by the Kalshi work, by ROOT's calculations or by a strategy. The trades it
makes are "the crypto and ng program's trades": not paper trades, not trade legs.

NANO TICKS (Greg, 2026-11-18, after the first run): "Definitely run it on nano ticks. .1 is losing too much data".
The July program walks a grid of tenths of a second; that grid is NOT allowed on our tape. The first natural gas
run used it, was refused, and its outputs and its job were deleted. The program in `program/` stays as the July
record and is not run on our tape. `tick.py` holds the same rules and numbers read on the clock (each trade at its
own nanosecond, the 600 cells as 60 seconds, the 300 cells as 30 seconds; the turn finder is the July function
itself); `root/crypto_ng_tick.py` is the job that runs them.

Left out of the crypto calculation on Greg's word (2026-11-18): the winner and loser labels; the average line of
each kind; the short or long split. Every trade is kept and drawn on its own.
"""
