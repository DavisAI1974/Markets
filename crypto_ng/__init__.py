"""CRYPTO AND NG: the rules of the crypto exhaustion calculation of July 2026, run on natural gas at the nanosecond.

Greg, 2026-11-18: "Bring back the program and just designate it crypto and ng so we know what it is at a later date.
And it's crypto outputs if are any will now go into our excel sheet. They would be for observation or verification
purpose only"; "Definitely run it on nano ticks".

What this is. `tick.py` holds the rules and numbers of the calculation behind the picture "Kraken
onset->exhaustion arcs REGROUPED BY TYPE" (Markets commit `75b15fa`, branch
`claude/davisai-s71-counterparty-capacity-sf1168`, 2026-07-07, where the original files stay): the 20-second
line, the turn finder, and how a trade of the program starts and ends. Every trade is taken at the nanosecond it
was received; nothing is put on a time grid of any size. `root/crypto_ng_tick.py` is the job that runs it.

What it is for. ONE thing: the natural gas exhaustion calculation made the way the crypto one was made ("The only
difference between the two should be that was crypto and we're doing ng"). Its outputs are for OBSERVATION AND
VERIFICATION ONLY: never a signal, never an input to another calculation, never a trade result of ours.

What it is not. It is the ONE exception, on Greg's explicit word, to "no bitcoin-era rules". The fill rule, the
wait, the fee settings and every other crypto trade rule inside this package apply inside it and nowhere else.
Nothing here may be imported by the Kalshi work, by ROOT's calculations or by a strategy. The trades it makes are
"the crypto and ng program's trades": not paper trades, not trade legs.

Left out of the crypto calculation on Greg's word (2026-11-18): the winner and loser labels; the average line of
each kind; the short or long split. Every trade is kept and drawn on its own.
"""
