"""Stage 4b, the model part: handoffs, kickoffs and notes become claims tied to their source.

The scout (Haiku) reads; this code does everything that needs no model:
  1. `plan`      lists the documents in scope, newest first, with their lines (what there is to read)
  2. `prompt`    cuts a document into pieces and writes the scout's brief, with every line numbered.
                 The text is put IN the brief: the scout has no need to open a file, and the path,
                 the commit and the line numbers are attached here, by code, not by the model.
  3. `load`      takes what the scout returned and checks every claim against the file itself: its
                 lines must be inside the piece it was given and its quote must stand, word for word,
                 on those lines. A claim that passes is written with a SUPPORTS link from its source.
                 A claim that does not is NOT written as a claim: it is kept as a Task line with the
                 reason, so nothing the scout returned is lost and nothing unverified is believed.
  4. `coverage`  writes one Task line for each document: read (with its counts) or not read yet.

  python3 -m tools.kgraph.extract plan
  python3 -m tools.kgraph.extract prompt --doc markets-data:<path> [--doc ...] --out brief.txt
  python3 -m tools.kgraph.extract load --result returned.json --run run:0017
  python3 -m tools.kgraph.extract coverage
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import schema
from .sources import code_stamp, link, source_node
from .store import GraphStore, sha

WORK = "tasks/family-research-20261022/research-union-current"
MAX_PIECE_LINES = 260

# The documents in scope (plan 4b: "the 30-plus SESSION_HANDOFF, KICKOFF and HANDOFF files, the
# research notes"). Each entry: repository name, a glob under it. Order within the list is the order
# of reading; within a glob the newest name is read first.
SCOPE = (
    ("markets-data", f"{WORK}/NEXT_SESSION_HANDOFF_*.md"),
    ("markets-data", f"{WORK}/root-redesign-20261116/ROOT_GAMEPLAN_DECISIONS.md"),
    ("markets-data", f"{WORK}/*.md"),
    ("markets-data", f"{WORK}/paper-trading-20261123/*.md"),
    ("markets-data", f"{WORK}/strategy-20261123-claude/*.md"),
    ("markets-data", f"{WORK}/root-redesign-20261116/*.md"),
    ("paper-trading-platform", "tasty/RUNNING_LIST.md"),
    ("Markets", "research/kalshi/frankie_boss/*20261123.md"),
    ("Markets", "SESSION_HANDOFF_*.md"),
    ("Markets", "KICKOFF_*.md"),
    ("Markets", "NEW_SESSION_HANDOFF_*.md"),
    ("Markets", "research/kalshi/*.md"),
)


def repo_dirs(data_root: Path, markets: str | None, platform: str | None) -> dict[str, Path]:
    here = Path(__file__).resolve().parents[2]
    out = {"markets-data": Path(data_root), "Markets": Path(markets) if markets else here}
    cand = Path(platform) if platform else here.parent / "paper-trading-platform"
    if cand.exists():
        out["paper-trading-platform"] = cand
    return out


def documents(dirs: dict[str, Path]) -> list[dict]:
    seen, out = set(), []
    for repo, pattern in SCOPE:
        if repo not in dirs:
            continue
        for p in sorted(dirs[repo].glob(pattern), key=lambda p: p.name, reverse=True):
            rel = str(p.relative_to(dirs[repo]))
            if (repo, rel) in seen or not p.is_file():
                continue
            seen.add((repo, rel))
            raw = p.read_bytes()
            out.append({"repo": repo, "path": rel, "lines": raw.count(b"\n") + (not raw.endswith(b"\n")),
                        "bytes": len(raw)})
    return out


def pieces(lines: list[str], max_lines: int = MAX_PIECE_LINES) -> list[tuple[int, int]]:
    """Cut a document into runs of whole lines, (first, last), 1-based. A cut is made only at a
    heading or at the start of a top-level bullet, so no entry is split between two pieces; an entry
    longer than `max_lines` stays whole."""
    n = len(lines)
    if n <= max_lines:
        return [(1, n)] if n else []
    starts = [i for i, l in enumerate(lines, 1) if i == 1 or l.startswith("#") or l.startswith("- ")]
    out, first = [], 1
    for a, b in zip(starts, starts[1:] + [n + 1]):
        if b - first > max_lines and a > first:
            out.append((first, a - 1))
            first = a
    out.append((first, n))
    return out


BRIEF_HEAD = """You are the SCOUT of DavisAI Markets in EXTRACTION MODE. You turn a document into claims for the
knowledge graph. You locate and copy; you do not judge, sum up, rank or interpret. Use NO tools: the text
is below, every line numbered as `<line number>| <text>`. Return JSON only, no words around it.

For each document piece return every claim it makes. A CLAIM is one statement that stands on its own:
one decision, one measured figure, one state of a thing, one rule, one open question, one slip, one plan,
one definition. A bullet that holds three facts gives three claims. Do not merge two facts; do not skip a
section; do not add anything that is not in the lines. Headings, link lists and pure pointers ("see file
X") give no claim unless they state a fact.

Each claim is an object with exactly these fields:
- "line_start", "line_end": the numbered lines the claim stands on (as numbered below).
- "quote": 6 to 30 consecutive words copied EXACTLY, character for character, from those lines (not from
  the heading above them). It is checked against the file by code; a quote that is not found word for
  word makes the claim be thrown out. Do not fix spelling, do not shorten with "...".
- "text": the claim in one plain sentence that can be read alone: name the thing, the number with its
  unit, the date if the lines give one. Use the document's own words and figures. No new numbers.
- "statement_kind": one of "decision", "measurement", "state", "rule", "open_question", "slip", "plan",
  "definition".
- "inference": true ONLY when the document itself marks the statement as a reading, a guess or a likely
  cause (words like "Claude's reading", "most likely", "his to strike", "not proven"); otherwise false.
- "said_by": "Greg", "Claude", "Codex", "builder agent", "reviewer agent", "scout agent" or null: who the
  lines say decided, said or measured it. A sentence in quotation marks given as Greg's is "Greg".
- "said_on": a date as YYYY-MM-DD if the lines give one for this statement, else null.
- "mentions": the names of things the claim is about, copied as written (file names, folders, branches,
  commit ids, rule ids like CL14, stage numbers like "stage 4b", run folders, components). At most 6.

Return: {"pieces": [{"piece": "<the piece id given below>", "claims": [ ... ]}, ...]}
One entry in "pieces" for each piece below, in order, even when it has no claim.
"""


def build_brief(store: GraphStore, dirs: dict[str, Path], docs: list[str]) -> tuple[str, list[dict]]:
    """The scout's brief for the named documents ("<repo>:<path>") and the list of pieces in it."""
    body, listing = [BRIEF_HEAD], []
    for spec in docs:
        repo, rel = spec.split(":", 1)
        src = source_node(repo, dirs[repo], rel)
        lines = (dirs[repo] / rel).read_text(encoding="utf-8").splitlines()
        for a, b in pieces(lines):
            pid = f"{src['id']}@{src['attrs']['commit'][:10]}#L{a}-L{b}"   # the wording it was cut from
            listing.append({"piece": pid, "source": src, "repo": repo, "path": rel, "first": a, "last": b})
            body.append(f"\n===== PIECE {pid} =====\n(document {rel}, lines {a} to {b})\n")
            body.extend(f"{n}| {lines[n - 1]}" for n in range(a, b + 1))
    body.append("\n===== END =====\nReturn the JSON now.")
    return "\n".join(body), listing


_ws = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _ws.sub(" ", s).strip()


def claim_id(source_id: str, quote: str, text: str | None = None) -> str:
    """One statement of one document, one id: the document and the quoted words. Line numbers are
    left out so the id holds when lines are added above it. Two different claims resting on the same
    quoted words are told apart by their text (the second and later ones only)."""
    return "claim:" + sha([source_id, _norm(quote)] + ([_norm(text)] if text else []))


def entity_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._/#@-]+", "-", name.strip().lower()).strip("-")
    return "entity:" + (slug or sha(name))


def check_claim(c: dict, lines: list[str], first: int, last: int) -> str | None:
    """None when the claim stands; otherwise the reason it is thrown out."""
    try:
        a, b = int(c["line_start"]), int(c["line_end"])
    except (KeyError, TypeError, ValueError):
        return "no line numbers"
    if not (first <= a <= b <= last):
        return f"lines {a}-{b} are outside the piece ({first}-{last})"
    quote = c.get("quote")
    if not isinstance(quote, str) or len(_norm(quote).split()) < 4:
        return "no quote, or a quote of fewer than 4 words"
    if _norm(quote) not in _norm(" ".join(lines[a - 1:b])):
        return "the quote is not on those lines word for word"
    if not c.get("text"):
        return "no text"
    if c.get("statement_kind") not in schema.STATEMENT_KINDS:
        return f"statement_kind {c.get('statement_kind')!r} is not one of the kinds"
    if not isinstance(c.get("inference"), bool):
        return "inference is not true or false"
    return None


def load_result(store: GraphStore, dirs: dict[str, Path], result: dict, run: str) -> dict:
    """Write what the scout returned. `run` is its AgentRun id (it must already be in the graph)."""
    if store.node(run) is None or store.node(run)["type"] != "AgentRun":
        raise schema.Refused(f"{run} is not an AgentRun of the graph: record the run first")
    by = code_stamp("tools.kgraph.extract")
    report = {"pieces": 0, "claims_written": 0, "thrown_out": 0, "entities": 0, "per_piece": []}
    for piece in result.get("pieces", []):
        m = re.fullmatch(r"(src:([^:@]+):(.+))@([0-9a-f]{10})#L(\d+)-L(\d+)", str(piece.get("piece", "")))
        if not m:
            raise schema.Refused(f"a returned piece has no usable id: {str(piece.get('piece'))[:80]}")
        sid, repo, rel, cut_at = m.group(1), m.group(2), m.group(3), m.group(4)
        first, last = int(m.group(5)), int(m.group(6))
        src = source_node(repo, dirs[repo], rel)
        if src["attrs"]["commit"][:10] != cut_at:
            raise schema.Refused(f"{rel} has changed since the brief was made (commit {cut_at} then, "
                                 f"{src['attrs']['commit'][:10]} now): make the brief again")
        lines = (dirs[repo] / rel).read_text(encoding="utf-8").splitlines()
        nodes, edges, thrown, same_quote = [src], [], 0, 0
        seen_ent, claim_ids = set(), {}
        for n, c in enumerate(piece.get("claims", [])):
            why = check_claim(c, lines, first, last)
            if why:
                thrown += 1
                tid = "task:thrown-out:" + sha([sid, first, last, n, c])
                nodes.append({"id": tid, "type": "Task", "attrs": {
                    "text": f"A claim the scout returned for {rel} lines {first}-{last} was not written: {why}.",
                    "state": "blocked", "reason": why, "returned": c, "source": sid, "piece": piece["piece"]}})
                edges.append(link("PRODUCED", run, tid))
                continue
            a, b = int(c["line_start"]), int(c["line_end"])
            cid = claim_id(sid, c["quote"])
            if cid in claim_ids and claim_ids[cid] != _norm(c["text"]):
                cid = claim_id(sid, c["quote"], c["text"])      # the same words carry a second claim
                same_quote += 1
            claim_ids[cid] = _norm(c["text"])
            attrs = {"text": c["text"], "statement_kind": c["statement_kind"], "inference": c["inference"],
                     "said_by": c.get("said_by"), "said_on": c.get("said_on"),
                     "source": sid, "source_commit": src["attrs"]["commit"],
                     "line_start": a, "line_end": b, "quote": c["quote"],
                     "proposer": c.get("said_by"), "knowledge_time": c.get("said_on"),
                     "extracted_by": run}
            nodes.append({"id": cid, "type": "Claim", "attrs": attrs})
            edges.append(link("SUPPORTS", sid, cid, line_start=a, line_end=b))
            edges.append(link("PRODUCED", run, cid))
            for name in (c.get("mentions") or [])[:6]:
                if not isinstance(name, str) or not name.strip():
                    continue
                eid = entity_id(name)
                if eid not in seen_ent and store.node(eid) is None:
                    nodes.append({"id": eid, "type": "Entity", "attrs": {
                        "name": name.strip(), "entity_kind": "named in a document", "aliases": []}})
                    report["entities"] += 1
                seen_ent.add(eid)
                edges.append(link("MENTIONS", cid, eid))
        # the same claim returned twice in one piece is one node; ids are made from source, lines, quote
        uniq = {}
        for nd in nodes:
            uniq[nd["id"]] = nd
        euniq = {}
        for e in edges:
            euniq[e["id"]] = e
        store.write(list(uniq.values()), list(euniq.values()), written_by=by)
        written = sum(1 for nd in uniq.values() if nd["type"] == "Claim")
        report["pieces"] += 1
        report["claims_written"] += written
        report["thrown_out"] += thrown
        report["per_piece"].append({"piece": piece["piece"], "claims_written": written, "thrown_out": thrown,
                                    "second_claims_on_the_same_quote": same_quote})
    return report


def coverage(store: GraphStore, dirs: dict[str, Path]) -> dict:
    """One Task line for each document in scope: which lines have been read into claims, and what is
    left. A document not read yet is written down as not read, never passed over in silence."""
    by = code_stamp("tools.kgraph.extract")
    claims_by_source: dict[str, list[dict]] = {}
    for c in store.nodes("Claim"):
        if c["attrs"].get("source"):
            claims_by_source.setdefault(c["attrs"]["source"], []).append(c)
    nodes, edges = [], []
    out = {"read": 0, "changed_since_read": 0, "not_read": 0, "lines_read": 0, "lines_not_read": 0, "documents": []}
    for d in documents(dirs):
        try:
            src = source_node(d["repo"], dirs[d["repo"]], d["path"])
        except RuntimeError as e:
            out["documents"].append({**d, "state": "not a committed file", "why": str(e)})
            continue
        cl = claims_by_source.get(src["id"], [])
        read_at = sorted({c["attrs"].get("source_commit") for c in cl if c["attrs"].get("source_commit")})
        now_at = src["attrs"]["commit"]
        last_line = max((c["attrs"]["line_end"] for c in cl), default=0)
        if not cl:
            state, bucket = "not_extracted", "not_read"
            text = f"{d['path']} ({d['repo']}, {d['lines']} lines) has not been read into claims yet."
        elif now_at in read_at:
            state, bucket = "done", "read"
            text = f"{d['path']} ({d['repo']}, {d['lines']} lines): {len(cl)} claims read from it as it stands now."
        else:
            state, bucket = "open", "changed_since_read"
            text = (f"{d['path']} ({d['repo']}, {d['lines']} lines): {len(cl)} claims were read from an earlier "
                    f"wording (up to line {last_line}); the file has changed since and the new lines are not read.")
        tid = f"task:extract:{d['repo']}:{d['path']}"
        nodes += [src, {"id": tid, "type": "Task", "attrs": {
            "text": text, "state": state, "source": src["id"], "lines": d["lines"], "claims": len(cl),
            "read_at_commits": read_at, "file_now_at_commit": now_at, "last_line_with_a_claim": last_line}}]
        edges.append(link("DEPENDS_ON", tid, src["id"]))
        out[bucket] += 1
        out["lines_read" if state == "done" else "lines_not_read"] += d["lines"]
        out["documents"].append({**d, "state": state, "claims": len(cl)})
    store.write(nodes, edges, written_by=by)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--markets")
    ap.add_argument("--platform")
    ap.add_argument("--graph-dir")
    sub = ap.add_subparsers(dest="verb", required=True)
    sub.add_parser("plan")
    p = sub.add_parser("prompt")
    p.add_argument("--doc", action="append", required=True, help="<repo>:<path>")
    p.add_argument("--out", required=True)
    p = sub.add_parser("load")
    p.add_argument("--result", required=True)
    p.add_argument("--run", required=True)
    sub.add_parser("coverage")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    dirs = repo_dirs(store.data_root, a.markets, a.platform)
    if a.verb == "plan":
        docs = documents(dirs)
        for d in docs:
            print(f"{d['lines']:>6} lines {d['bytes']:>8} bytes  {d['repo']}:{d['path']}")
        print(f"{sum(d['lines'] for d in docs)} lines, {sum(d['bytes'] for d in docs)} bytes in {len(docs)} documents")
    elif a.verb == "prompt":
        brief, listing = build_brief(store, dirs, a.doc)
        Path(a.out).write_text(brief, encoding="utf-8")
        print(json.dumps({"out": a.out, "bytes": len(brief.encode()), "pieces": [
            {k: v for k, v in l.items() if k != "source"} for l in listing]}, indent=1))
    elif a.verb == "load":
        text = Path(a.result).read_text(encoding="utf-8")
        start, end = text.find("{"), text.rfind("}")
        print(json.dumps(load_result(store, dirs, json.loads(text[start:end + 1]), a.run), indent=1))
    elif a.verb == "coverage":
        out = coverage(store, dirs)
        print(json.dumps({k: v for k, v in out.items() if k != "documents"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
