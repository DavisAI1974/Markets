"""A decider over a finished run's real opening signals, with no engine.

  python3 -m tools.decider.replay_questions --data <markets-data> --run <run id> [--journal <events.jsonl>]
        --platform <checkout> --budget <packet tokens> (--program <file> | --mailbox-only) --out <folder>
        [--from-sequence N] [--limit N] [--poll-s N] [--timeout-s N]

Walks the real opening signals of a finished run's journal in order. For each one it makes the question folder
`<out>/q-<sequence>/question.json` as the platform does, and puts the question through the same door a trial uses
(`tools.decider.serve.Server`: packet, leak check, brief, decision, validation, one line in `decisions.jsonl`).
With --program the program answers. With --mailbox-only the briefs are written and each question waits for a
`decision.json` (a live agent), as `serve` does.

WHAT THIS IS NOT: it is not a trial. The journal is a finished run's, so a `skip` changes nothing that follows.
It shows what a decider WOULD answer at each real signal and what each packet and brief weighs in tokens, and
nothing about how any trade ends. No engine, no tape, no model, no network.

The last printed line is one JSON object of COUNTS (each a count of what was written, none a result).
Sizes are named as characters / 4; the two totals are totals of sizes, not averages, and say nothing of trades.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from tools.decider import serve
from tools.kgraph import signal_packet as sp

NOT_A_TRIAL = ("NOT A TRIAL: a finished run's real signals put through the decider's door; a skip changes nothing "
               "that follows, and nothing is said about how any trade ends")


class ReplayServer(serve.Server):
    """The door as it is, plus a note of how many characters each brief would have been when a program answers
    (a program is not handed a brief.md; the brief it would have had is sized, not written)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.brief_chars = {}

    def by_program(self, box, q, pk):
        self.brief_chars[q["sequence"]] = len(serve.make_brief(q, pk, box))
        return super().by_program(box, q, pk)


def _write_journal(rows, path: Path):
    with path.open("w", encoding="utf8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def counts(out: Path, asked: list, brief_chars: dict, stopped=None) -> dict:
    lines = []
    log = out / "decisions.jsonl"
    if log.exists():
        lines = [json.loads(l) for l in log.read_text(encoding="utf8").splitlines() if l.strip()]
    by_code = [l for l in lines if l["answered_by"] == "this code"]
    reasons = {}
    for l in by_code:
        reasons[l["skip_reason"]] = reasons.get(l["skip_reason"], 0) + 1
    leak = [l for l in lines if (l["skip_reason"] or "").startswith("the packet failed its own leak check")]
    sized = [(l["packet_tokens_estimated_chars_div_4"], l["sequence"]) for l in lines
             if l["packet_tokens_estimated_chars_div_4"] is not None]
    small = min(sized, key=lambda t: (t[0], t[1])) if sized else None
    large = max(sized, key=lambda t: (t[0], -t[1])) if sized else None
    brief_total = 0
    for s in asked:
        b = out / f"q-{s}" / "brief.md"
        if s in brief_chars:
            brief_total += brief_chars[s] // 4
        elif b.exists():
            brief_total += len(b.read_text(encoding="utf8")) // 4
    return {
        "what_this_is_not": NOT_A_TRIAL,
        "signals_asked": len(asked),
        "answered": len(lines),
        "take": sum(l["action"] == "take" for l in lines),
        "skip": sum(l["action"] == "skip" for l in lines),
        "skip_answered_by_this_code": len(by_code),
        "skip_answered_by_this_code_reasons": reasons,
        "packets_refused_by_the_leak_check": len(leak),
        "smallest_packet_tokens": small[0] if small else None,
        "smallest_packet_sequence": small[1] if small else None,
        "largest_packet_tokens": large[0] if large else None,
        "largest_packet_sequence": large[1] if large else None,
        "packet_tokens_total_chars_div_4": sum(t for t, _ in sized),
        "brief_tokens_total_chars_div_4": brief_total,
        "stopped_waiting_at_sequence": stopped,
    }


def run(a) -> dict:
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if next(out.glob("q-*"), None) is not None:
        raise SystemExit(f"{out} already holds question folders: use a folder that is free")
    store_root = a.data
    if a.journal:
        journal = Path(a.journal).resolve()
        rows = sp.journal_from_file(journal)
    else:
        rows = sp.journal_from_branch(a.data, a.run)
        journal = out / "journal.jsonl"
        _write_journal(rows, journal)
    seqs = [s for s in sp.open_sequences(rows) if a.from_sequence is None or s >= a.from_sequence]
    if a.limit is not None:
        seqs = seqs[:a.limit]
    srv = ReplayServer(out, store_root, a.platform, a.budget, "replay_questions", graph_dir=a.graph_dir,
                       program=a.program)
    by_seq = {r["sequence"]: r for r in rows if r["kind"] == "signal"}
    asked, stopped = [], None
    for s in seqs:
        sig = by_seq[s]
        box = out / f"q-{s}"
        box.mkdir()
        serve.write_json(box / "question.json", dict(sequence=s, rule=sig["rule"], side=sig.get("side"),
                                                     trade_id=sig["trade_id"], tape_received_ns=sig["received"],
                                                     journal=str(journal)))
        asked.append(s)
        deadline = time.monotonic() + a.timeout_s
        while not (box / "answer.json").exists():
            srv.once()
            if (box / "answer.json").exists():
                break
            if a.program:
                break                                       # a program answers in one pass; nothing to wait for
            if time.monotonic() >= deadline:
                stopped = s
                break
            time.sleep(a.poll_s)
        if stopped is not None:
            break
    return counts(out, asked, srv.brief_chars, stopped)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", required=True)
    ap.add_argument("--run")
    ap.add_argument("--journal")
    ap.add_argument("--platform", required=True)
    ap.add_argument("--budget", type=int, required=True, help="packet tokens")
    how = ap.add_mutually_exclusive_group(required=True)
    how.add_argument("--program")
    how.add_argument("--mailbox-only", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--from-sequence", type=int)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--graph-dir")
    ap.add_argument("--poll-s", type=float, default=1.0)
    ap.add_argument("--timeout-s", type=float, default=3600.0, help="how long one question waits for its decision.json")
    a = ap.parse_args(argv)
    if not (a.run or a.journal):
        ap.error("give --run (the record branch) or --journal (a local events.jsonl)")
    print(json.dumps(run(a), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
