"""Watch a platform mailbox, hand each question to an agent as a brief, turn the agent's decision into the answer.

  python3 -m tools.decider.serve --mailbox <folder> --data <markets-data> --platform <checkout> --budget <tokens>
        --by <agent run> [--graph-dir D] [--poll-s N] [--max-wall-clock-s N] [--once]

A question folder `q-<sequence>/` moves through these files, each written whole (temp name, then rename):
  question.json (platform) -> brief.md + packet.json (here) -> decision.json (the agent) -> answer.json (here).
  A packet that fails its own leak check, or cannot be built, gets refused.json and a skip answer.
  A decision that is not valid is kept as decision.rejected.json and answered skip.
One line a question goes to <mailbox>/decisions.jsonl. Nothing is added up across lines.
No model is called here; no network; nothing is read from the tape.
"""

from __future__ import annotations

import argparse
import json
import os
import hashlib
import re
import subprocess
import sys
import time
from pathlib import Path

from tools.kgraph import signal_packet as sp
from tools.kgraph.store import GraphStore

RUNNER = Path(__file__).with_name("_run_program.py")


def program_identity(path):
    """(by, sha256) of a decider program file: its name, the commit of that file or "uncommitted", and its bytes' hash."""
    path = Path(path).resolve()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    commit = "uncommitted"
    try:
        run = lambda *a: subprocess.run(["git", "-C", str(path.parent), *a], capture_output=True, text=True, timeout=20)
        tracked = run("ls-files", "--error-unmatch", path.name)
        dirty = run("status", "--porcelain", "--", path.name)
        last = run("log", "-1", "--format=%H", "--", path.name)
        if tracked.returncode == 0 and not dirty.stdout.strip() and last.stdout.strip():
            commit = last.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return f"program:{path.name}@{commit}", sha


def run_program(path, packet, timeout_s):
    """(decision, None) or (None, reason). The program gets the packet as JSON on stdin and nothing else: a fresh
    interpreter in isolated mode (no script folder, no current folder, no user site, no PYTHON* variables) that
    runs in an empty scratch folder with an empty environment. NOT a sandbox: a program that opens a file by its
    absolute path can still read it, so a program is read before it is committed."""
    import tempfile
    with tempfile.TemporaryDirectory() as empty:
        try:
            r = subprocess.run([sys.executable, "-I", str(RUNNER), str(Path(path).resolve())],
                               input=json.dumps(packet), capture_output=True, text=True, timeout=timeout_s,
                               cwd=empty, env={})
        except subprocess.TimeoutExpired:
            return None, f"the program took longer than {timeout_s} seconds"
    if r.returncode != 0:
        last = (r.stderr.strip().splitlines() or ["no message"])[-1]
        return None, f"the program raised: {last[:300]}"
    try:
        return json.loads(r.stdout), None
    except ValueError:
        return None, "the program returned something that is not JSON"


def build_packet(rows, sequence, budget, store, platform_dir, question=None):
    """The one place a packet is built. A check swaps this to hand over a packet made to breach. The whole question
    (its `state`, `lines` and `exchange_ns` too) goes to the build."""
    return sp.build(rows, sequence, budget, store=store, platform_dir=platform_dir, question=question)


def question_facts(q, rows):
    """What a decisions.jsonl line says of the data a question carried: whether it had a state, its sha256 (the
    platform's own canonical digest), whether the journal's question row says the same, the book levels, the two lines.
    Per question; nothing is added across questions."""
    state = q.get("state")
    given = isinstance(state, dict)
    sha = sp.state_sha256(state) if given else None
    row = next((r for r in rows or [] if r.get("kind") == "question" and r.get("signal_sequence") == q.get("sequence")),
               None)
    book = state.get("book") if given else None
    lines = q.get("lines") if isinstance(q.get("lines"), dict) else {}
    val = lambda n: (lines.get(n) or {}).get("value") if isinstance(lines.get(n), dict) else None
    return {"state_given": given, "state_sha256": sha,
            "state_matches_journal": None if not (given and row and row.get("state_sha256")) else row["state_sha256"] == sha,
            "book_levels_bid": len(book["bid"]) if isinstance(book, dict) and isinstance(book.get("bid"), list) else None,
            "book_levels_ask": len(book["ask"]) if isinstance(book, dict) and isinstance(book.get("ask"), list) else None,
            "dipole": val("dipole"), "exhaustion": val("exhaustion")}


def write_whole(path: Path, text: str):
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(text, encoding="utf8")
    os.replace(tmp, path)


def write_json(path: Path, obj):
    write_whole(path, json.dumps(obj, sort_keys=True, indent=2) + "\n")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf8")), None
    except (OSError, ValueError) as e:
        return None, f"not readable: {type(e).__name__}"


def question_folders(mailbox: Path):
    found = []
    for p in mailbox.glob("q-*"):
        m = re.fullmatch(r"q-(\d+)", p.name)
        if m and p.is_dir() and (p / "question.json").exists():
            found.append((int(m.group(1)), p))
    return [p for _, p in sorted(found)]


BRIEF = """You are the decider for one paper trade on Greg's own paper-trading platform. A rule has fired on the stored
tape and wants to open a trade. Say take or skip.

THE RULES YOU DECIDE UNDER
- Decide from the packet below alone. Nothing else is given and nothing else counts.
- Every reason names the lines of the packet it rests on, by their ids (the text before the first " | " of a line).
  Any id of any layer may be named, shown in the text below or not: the whole of every layer is beside this brief, in
  state.json (the engine's state at the signal) and layers.json (every other layer), each row with its id.
- Say skip when the packet gives no ground to take.
- The hold rule in force is "hold until the trade gives back 20% of its highest open profit". It is not yours to change.
- There is no trade cost and no mid price in this decision; the packet shows bid and ask side by side as stored.

THE QUESTION
signal journal sequence {sequence}; rule {rule}; side {side}; trade_id {trade_id}.

THE PACKET ({tokens} tokens estimated at 4 characters a token; sha256 {sha})
----- packet begins -----
{packet}----- packet ends -----

HOW TO REPLY
Write q-{sequence}/decision.json in the mailbox ({box}) as one JSON object:
  {{"action": "take" | "skip", "why": "<one sentence>", "rests_on": ["<id of a packet line>", ...]}}
at least one id, every id one that stands in the packet.
(Or: python3 -m tools.decider.answer --mailbox {mailbox} --sequence {sequence} --action take|skip --why "<one sentence>" --rests-on <id> ...)
"""


def ids_of(pk):
    """Every explicit id of the packet, shown in the text or not (the state's own rows are addressed, see PacketIds)."""
    return sorted(sp.layer_of_map(pk))


def layer_counts(pk):
    """{layer name: how many lines or rows it held}: the layers of a packet built with a question; else the sections."""
    if pk.get("layers"):
        return {n: l["count"] for n, l in pk["layers"].items()}
    return {s: sum(1 for l in pk["lines"] if l["section"] == s) for s in sp.SECTIONS}


def packet_ids(pk):
    return sp.PacketIds(sp.layer_of_map(pk), pk.get("state"))


def make_brief(q, pk, box: Path):
    return BRIEF.format(sequence=q["sequence"], rule=q.get("rule"), side=q.get("side"), trade_id=q.get("trade_id"),
                        tokens=pk["tokens_estimated"], sha=pk["sha256"], packet=pk["text"], box=box,
                        mailbox=box.parent)


def validate_decision(d, ids):
    """The reason a decision is not valid, or None."""
    if not isinstance(d, dict):
        return "the decision is not one JSON object"
    if d.keys() - {"action", "why", "rests_on"}:
        return "unknown field: " + ", ".join(sorted(d.keys() - {"action", "why", "rests_on"}))
    if d.get("action") not in ("take", "skip"):
        return "action is not take or skip"
    why = d.get("why")
    if not isinstance(why, str) or not why.strip():
        return "why is missing or empty"
    if "\n" in why.strip():
        return "why is more than one line"
    rests = d.get("rests_on")
    if not isinstance(rests, list) or not rests:
        return "rests_on names no line of the packet"
    if not all(isinstance(r, str) for r in rests):
        return "rests_on holds something that is not an id"
    unknown = [r for r in rests if r not in ids]       # `ids` holds the WHOLE packet (see PacketIds), not the text
    if unknown:
        return "rests_on names ids that are not in the packet: " + ", ".join(unknown)
    return None


class Server:
    def __init__(self, mailbox, data, platform, budget, by, graph_dir=None, clock_ns=time.time_ns,
                 program=None, program_timeout_s=5.0):
        self.mailbox, self.budget, self.by, self.platform = Path(mailbox), budget, by, platform
        self.program, self.program_timeout_s, self.program_sha = program, program_timeout_s, None
        if program:
            self.by, self.program_sha = program_identity(program)
        self.store = GraphStore(data, graph_dir=graph_dir)
        self.clock_ns = clock_ns
        self.journals = {}                       # path -> (size, rows)

    def rows(self, path):
        size = os.stat(path).st_size
        c = self.journals.get(path)
        if c is None or c[0] != size:
            c = (size, sp.journal_from_file(path))
            self.journals[path] = c
        return c[1]

    # -- one log line a question
    def log(self, box, q, pk, answer, source, reason, rests_on=None, ids=None):
        qmtime = (box / "question.json").stat().st_mtime_ns
        line = {"sequence": q["sequence"], "rule": q.get("rule"), "side": q.get("side"), "trade_id": q.get("trade_id"),
                "tape_received_ns": q.get("tape_received_ns"),
                "packet_sha256": pk["sha256"] if pk else None,
                "packet_tokens_estimated_chars_div_4": pk["tokens_estimated"] if pk else None,
                "lines_in": pk["lines_in"] if pk else None,
                "lines_cut": pk["lines_cut"] if pk else None,
                "action": answer["action"], "why": answer["why"], "rests_on": rests_on, "by": answer["by"],
                "wall_ms_question_to_decision": round((self.clock_ns() - qmtime) / 1e6, 3),
                "answered_by": source, "skip_reason": reason, "program_sha256": self.program_sha}
        try:
            jrows = self.rows(q["journal"]) if isinstance(q.get("journal"), str) else None
        except OSError:
            jrows = None
        line.update(question_facts(q, jrows))
        # per decision line only: which layers the packet held and which layer each id the decision rests on is in.
        # Recorded so that a later choice to drop a layer can be made from the runs' own record; no total, no ranking.
        line["layers_in_packet"] = pk.get("layers_in_packet") if pk else None
        line["rests_on_layers"] = {i: ids.layer(i) for i in rests_on} if (rests_on and ids is not None) else None
        with open(self.mailbox / "decisions.jsonl", "a", encoding="utf8") as f:
            f.write(json.dumps(line, sort_keys=True) + "\n")

    def answer(self, box, q, action, why, pk):
        a = {"id": f"decision-{q['sequence']}", "action": action, "asked_at_sequence": q["sequence"], "by": self.by,
             "why": why, "packet": {"sha256": pk["sha256"], "tokens": pk["tokens_estimated"]} if pk else None}
        write_json(box / "answer.json", a)
        return a

    def refuse(self, box, q, pk, what):
        if pk:
            pk = {"sha256": pk["sha256"], "tokens_estimated": pk["tokens_estimated"], "lines_in": len(pk["lines"]),
                  "lines_cut": sum(pk["cut"].values()), "layers_in_packet": layer_counts(pk)}
        write_json(box / "refused.json", {"sequence": q["sequence"], "breach": what})
        why = f"the packet failed its own leak check: {'; '.join(what)}"
        self.log(box, q, pk, self.answer(box, q, "skip", why, pk), "this code", why)

    def brief(self, box):
        q, bad = read_json(box / "question.json")
        if bad or not isinstance(q, dict) or type(q.get("sequence")) is not int or not isinstance(q.get("journal"), str):
            return                                         # not whole yet, or not a question; left alone
        pk = None
        try:
            rows = self.rows(q["journal"])
            pk = build_packet(rows, q["sequence"], self.budget, self.store, self.platform, question=q)
            breach = sp.leakage_check(pk, store=self.store, journal_rows=rows)
            if question_facts(q, rows)["state_matches_journal"] is False:
                breach.append("the question's state is not the state its journal row's state_sha256 names")
        except (OSError, ValueError, KeyError) as e:
            return self.refuse(box, q, None, [f"the packet could not be built: {type(e).__name__}: {e}"])
        if breach:
            return self.refuse(box, q, pk, breach)
        if self.program:
            return self.by_program(box, q, pk)
        self.write_layers(box, pk)
        write_json(box / "packet.json", {"sha256": pk["sha256"], "tokens_estimated": pk["tokens_estimated"],
                                         "ids": ids_of(pk), "layer_of": sp.layer_of_map(pk),
                                         "layers_in_packet": layer_counts(pk), "lines_in": len(pk["lines"]),
                                         "lines_cut": sum(pk["cut"].values())})
        write_whole(box / "brief.md", make_brief(q, pk, box))

    def write_layers(self, box, pk):
        """The whole of every layer beside the brief: state.json (the question's state, whole) and layers.json (every
        other layer, whole, each row with its id). Nothing is dropped; the text is the head of each."""
        if pk.get("state") is not None:
            write_json(box / "state.json", pk["state"])
        if pk.get("layers"):
            write_json(box / "layers.json", {n: {k: v for k, v in l.items() if k != "in_text"}
                                             for n, l in pk["layers"].items() if "rows" in l})

    def by_program(self, box, q, pk):
        meta = {"sha256": pk["sha256"], "tokens_estimated": pk["tokens_estimated"], "lines_in": len(pk["lines"]),
                "lines_cut": sum(pk["cut"].values()), "layers_in_packet": layer_counts(pk)}
        self.write_layers(box, pk)
        ids = packet_ids(pk)
        d, reason = run_program(self.program, pk, self.program_timeout_s)
        if reason is None:
            reason = validate_decision(d, ids)
        if reason:
            why = f"the decider's answer was not valid: {reason}"
            self.log(box, q, meta, self.answer(box, q, "skip", why, meta), "this code", why)
            return
        a = self.answer(box, q, d["action"], d["why"].strip(), meta)
        self.log(box, q, meta, a, "the program", None, rests_on=d["rests_on"], ids=ids)

    def settle(self, box):
        q, _ = read_json(box / "question.json")
        meta, _ = read_json(box / "packet.json")
        d, bad = read_json(box / "decision.json")
        if bad:
            return                                          # maybe half written; the next pass reads it again
        pk = meta
        state, _ = read_json(box / "state.json")
        ids = sp.PacketIds(meta.get("layer_of") or {i: None for i in meta["ids"]}, state)
        reason = validate_decision(d, ids)
        if reason:
            write_json(box / "decision.rejected.json", {"reason": reason, "decision": d})
            why = f"the decider's answer was not valid: {reason}"
            self.log(box, q, pk, self.answer(box, q, "skip", why, pk), "this code", why)
            return
        a = self.answer(box, q, d["action"], d["why"].strip(), pk)
        self.log(box, q, pk, a, "the decider", None, rests_on=d["rests_on"], ids=ids)

    def once(self):
        """One pass: briefs for new questions, answers for new decisions. Returns the number of files it settled."""
        n = 0
        for box in question_folders(self.mailbox):
            if (box / "answer.json").exists():
                continue
            if not (box / "brief.md").exists() and not (box / "refused.json").exists():
                self.brief(box)
                n += 1
            if (box / "brief.md").exists() and (box / "decision.json").exists() and not (box / "answer.json").exists():
                self.settle(box)
                n += 1
        return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mailbox", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--platform", required=True)
    ap.add_argument("--budget", type=int, required=True, help="packet tokens")
    ap.add_argument("--by", required=True)
    ap.add_argument("--graph-dir")
    ap.add_argument("--poll-s", type=float, default=1.0)
    ap.add_argument("--max-wall-clock-s", type=float)
    ap.add_argument("--program", help="a decider program file: answers each question by its decide(), no model, no wait")
    ap.add_argument("--program-timeout-s", type=float, default=5.0)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args(argv)
    srv = Server(a.mailbox, a.data, a.platform, a.budget, a.by, a.graph_dir, program=a.program,
                 program_timeout_s=a.program_timeout_s)
    srv.mailbox.mkdir(parents=True, exist_ok=True)
    stop = None if a.max_wall_clock_s is None else time.monotonic() + a.max_wall_clock_s
    while True:
        srv.once()
        if a.once or (stop is not None and time.monotonic() >= stop):
            return 0
        time.sleep(a.poll_s)


if __name__ == "__main__":
    sys.exit(main())
