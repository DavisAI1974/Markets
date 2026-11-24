# Decider programs

A decider program is one Python file with one function:

    decide(packet: dict) -> {"action": "take" | "skip", "why": "<one sentence>", "rests_on": ["<ids of packet lines>", ...]}

`packet` is exactly what `tools.kgraph.signal_packet.build` returned for that signal (text, lines with their ids,
the moment, the foot) and nothing else. The function gets no path, no store, no journal, no clock.

## What a program may read in `packet` when the question carried data (Greg, 2026-11-24: all of the data depth in)

With a question the packet also holds, as structure (the same whole values the platform gave):

- `packet["state"]`: the engine's state at the signal's own tick, whole, a set of layers by its own keys (today `inputs`
  {`strategy_inputs`, `tick`, `previous_trade_tick`}, `book` {`bid`, `ask`, `totals`, ...}, `rules`, `paper`,
  `mbo_window`, `conditions`, `left_out`, `known_at_tape_ns}`; a key the platform adds later is there too). Units: every
  price and size is the tape's own integer as stored (prices in billionths of a dollar); every `*_ns` is UTC nanoseconds
  on the tape's receive clock (`exchange_ns` is the exchange's clock); `width_s` is seconds; a flow value is bought minus
  sold over bought plus sold, between -1 and 1, null when nothing traded in the window. No mid price exists in it.
- `packet["flow_lines"]`: `{"dipole": {"value", "width_s"}, "exhaustion": {"value", "width_s"}}` and `packet["exchange_ns"]`.
- `packet["layers"]`: every layer by name with its `count` and where the whole of it is (`state.json`, `layers.json`,
  `planes_since.json`). Journal layers carry their `rows` (each with its id); ROOT's stored planes (`plane:<layer>`) are
  handed by count only, with their head line in `packet["lines"]` and `packet["planes"]` ({layer: {count, of}}): the
  rows of a plane are NOT parsed over stdin (a day's worth is megabytes and the program has a timeout), and the stored
  files' paths and hashes are not handed over.
- `packet["lines"]`: every line with its `source` id and `known_at_ns` (never after `packet["moment_ns"]`).

A decision may name in `rests_on` the id of any row of any layer of the whole packet, shown in the text or not
(`state:dipole`, `state.book.bid/[0]`, `plane:calc-resting-facts:12`). What is not an id: anything of the afterwards
file (kept for learning, never given to a decider), and a plane row number at or above its layer's count.

Each `decisions.jsonl` line records, for that decision alone, `layers_in_packet` (every layer's name with its count) and
`rests_on_layers` (the layer of each id the decision named), so that a later choice to drop or keep a layer can be made
from the runs' own record, never from a guess; nothing is totalled across lines.

Run: `python3 -m tools.decider.serve ... --program tools/decider/programs/<name>.py [--program-timeout-s 5]`.
Its decision goes through the same validation, the same `answer.json` and the same line in `decisions.jsonl` as an
agent's (`by` = `program:<file>@<commit of the file, or uncommitted>`; the line also holds the file's sha256).
A program that raises, runs past the timeout or returns an invalid decision is answered skip with the reason.

What is fenced: the program runs in a fresh interpreter in isolated mode (`-I`: no script folder, no current folder,
no user site, no PYTHON variables) in an empty folder with an empty environment, and is handed the packet as JSON
on stdin, so it cannot import Markets code or reach the store or journal by accident. What is NOT fenced: it is not
a sandbox. A program that opens a file by absolute path can read it, so a program is read before it is committed.

A program is written by an agent between runs. Every version is a commit. It is an input of a trial, like the plan.
It was written with these trade days already seen (the same limit the rule texts have).

Shipped: `skip_all.py`, which skips every packet. It exists to check the door. No program that takes trades is
written here: what one should decide is the agents' work in the loop.
