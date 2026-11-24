"""Stage 6 of the graph adoption plan: the swarm (one worker for each dipole event, a reducer, a refute wave).

This package is code only. Nothing here runs a model unless `python3 -m tools.swarm.run go` is given
Greg's go and a plan that passes its check; no caller makes up an answer.

The contract of a worker's answer (changed 2026-11-24 after the review of stage 6): in a claim's text every
figure is a pair `column=value` copied from a cell; the loader takes a claim only if each pair is a cell it
cites (an inference: a cell of a claim it rests on) and the text holds no number outside pairs, no number
written as a word, and none of the refused words (total, mean, most, best, good, net, fee, correct, pass ...).
The same words are refused in a refuter's "why". A refuter's check is taken only for a claim of the brief it
answered; any other check is kept as a Task line with its reason, and one event's failure in the reduce or
refute step is recorded for that event and the run goes on. A claim stores `source_commit` and
`cited_node_rev`, the wording of the workbook it was read from.
"""
