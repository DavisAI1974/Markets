# Decider programs

A decider program is one Python file with one function:

    decide(packet: dict) -> {"action": "take" | "skip", "why": "<one sentence>", "rests_on": ["<ids of packet lines>", ...]}

`packet` is exactly what `tools.kgraph.signal_packet.build` returned for that signal (text, lines with their ids,
the moment, the foot) and nothing else. The function gets no path, no store, no journal, no clock.

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
