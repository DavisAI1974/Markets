"""Stage 8 of the graph adoption plan: the token test (can Claude agents carry Granite's daily load).

baseline.py  8a  every Granite call of one trade day, read from Granite's own saved job records
arms.py      8b  the five arms as data, each built from one baseline call
prices.py    8b  the API price table as data, and the cost of ONE call from its own usage figures
replay.py    8b  `plan` (sends nothing) and `go` (needs Greg's go, sends)
report.py    8c  one table, two charts, row counts reconciled to plotted points

Nothing here makes a model call at import. A run of the token test spends model tokens and needs
Greg's go, said to him first with its budget. The cost figures are the API's price for the tokens: a
compute cost of the test, not a trade cost; they enter no market calculation.
"""
