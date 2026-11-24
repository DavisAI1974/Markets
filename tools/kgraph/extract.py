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
  python3 -m tools.kgraph.extract load --result returned.json --run run:0017 [--pieces brief.txt.pieces.json]
  python3 -m tools.kgraph.extract recheck
  python3 -m tools.kgraph.extract coverage
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import schema
from .sources import code_stamp, git, link, source_node
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


BRIEF_HEAD = """You are the READER of DavisAI Markets in EXTRACTION MODE (the scout's extraction mode of the plan).
You turn a document into claims for the knowledge graph. You locate and copy; you do not judge, sum up,
rank or interpret. The text is below, every line numbered as `<line number>| <text>`; you need no other
file. Return JSON only, no words around it.

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
  lines say decided, said or measured it. "Greg" only for words given in quotation marks as his, or a
  decision the lines say he made; a rule restated in someone else's prose is said_by null.
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
        only = None
        m = re.fullmatch(r"(.+)#L(\d+)-L(\d+)", rel)          # "<path>#L<first>-L<last>": only those lines
        if m:
            rel, only = m.group(1), (int(m.group(2)), int(m.group(3)))
        src = source_node(repo, dirs[repo], rel)
        lines = (dirs[repo] / rel).read_text(encoding="utf-8").splitlines()
        cuts = pieces(lines)
        if only:
            # whole entries only: the range is widened to the entry boundaries it falls in
            starts = [i for i, l in enumerate(lines, 1) if i == 1 or l.startswith("#") or l.startswith("- ")]
            first = max(x for x in starts if x <= only[0])
            last = min([x - 1 for x in starts if x > only[1]] + [len(lines)])
            sub = pieces(lines[first - 1:last])
            cuts = [(a + first - 1, b + first - 1) for a, b in sub]
        for a, b in cuts:
            pid = f"{src['id']}@{src['attrs']['commit'][:10]}#L{a}-L{b}"   # the wording it was cut from
            listing.append({"piece": pid, "source": src, "repo": repo, "path": rel, "first": a, "last": b})
            body.append(f"\n===== PIECE {pid} =====\n(document {rel}, lines {a} to {b})\n")
            body.extend(f"{n}| {lines[n - 1]}" for n in range(a, b + 1))
    body.append("\n===== END =====\nReturn the JSON now.")
    return "\n".join(body), listing


_ws = re.compile(r"\s+")


def git_text(repo_dir, commit: str, rel: str) -> str:
    """A file as it stood at one commit (not stripped: every line as written)."""
    import subprocess
    r = subprocess.run(["git", "-C", str(repo_dir), "show", f"{commit}:{rel}"], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip())
    return r.stdout.decode("utf-8")


def _norm(s: str) -> str:
    return _ws.sub(" ", s).strip()


def claim_id(source_id: str, quote: str, text: str | None = None) -> str:
    """One statement of one document, one id: the document and the quoted words. Line numbers are
    left out so the id holds when lines are added above it. Two different claims resting on the same
    quoted words are told apart by their text (the second and later ones only)."""
    return "claim:" + sha([source_id, _norm(quote)] + ([_norm(text)] if text else []))


def claim_id_beside(source_id: str, quote: str, text: str, statement_kind: str, said_by,
                    inference: bool | None = None, lines: tuple | None = None) -> str:
    """The id of a claim that stands BESIDE an earlier one on the same quote: made from the source, the
    quote, the text, the kind and who said it (then also `inference`, then also the lines, only when
    the id before it is already taken by a claim that differs in that)."""
    key = [source_id, _norm(quote), _norm(text), statement_kind, said_by]
    if inference is not None:
        key.append(inference)
    if lines is not None:
        key.append(list(lines))
    return "claim:" + sha(key)


def entity_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._/#@-]+", "-", name.strip().lower()).strip("-")
    return "entity:" + (slug or sha(name))


def _same_claim(attrs: dict, text: str, kind: str, said_by, inference: bool) -> bool:
    return (_norm(attrs.get("text") or "") == _norm(text) and attrs.get("statement_kind") == kind
            and attrs.get("said_by") == said_by and attrs.get("inference") == inference)


MIN_QUOTE_WORDS = 6


_words = re.compile(r"\w+")


def locate_quote(quote: str, lines: list[str], a: int, b: int) -> tuple[int, int] | None:
    """The smallest run of lines inside a..b that holds the quote, its words as whole tokens (runs of letters and digits;
    words, markup and punctuation between them ignored) in a row: never a piece that starts or ends inside a word. None when the quote is not
    on those lines. Found by code, not taken from the reader."""
    q = _words.findall(quote)
    if not q:
        return None
    flat = [(t, n) for n in range(a, b + 1) for t in _words.findall(lines[n - 1])]
    toks = [t for t, _ in flat]
    best = None
    for i in range(0, len(toks) - len(q) + 1):
        if toks[i:i + len(q)] == q:
            span = (flat[i][1], flat[i + len(q) - 1][1])
            if best is None or span[1] - span[0] < best[1] - best[0]:
                best = span
    return best


def check_claim(c: dict, lines: list[str], first: int, last: int) -> str | None:
    """None when the claim stands; otherwise the reason it is thrown out."""
    try:
        a, b = int(c["line_start"]), int(c["line_end"])
    except (KeyError, TypeError, ValueError):
        return "no line numbers"
    if not (first <= a <= b <= last):
        return f"lines {a}-{b} are outside the piece ({first}-{last})"
    quote = c.get("quote")
    if not isinstance(quote, str) or len(quote.split()) < MIN_QUOTE_WORDS:
        return f"no quote, or a quote of fewer than {MIN_QUOTE_WORDS} words"
    if locate_quote(quote, lines, a, b) is None:
        return "the quote is not on those lines word for word (whole words, in a row)"
    if not c.get("text"):
        return "no text"
    if c.get("statement_kind") not in schema.STATEMENT_KINDS:
        return f"statement_kind {c.get('statement_kind')!r} is not one of the kinds"
    if not isinstance(c.get("inference"), bool):
        return "inference is not true or false"
    return None


# ---- the two marks (kept as Evaluations; the claim itself is never changed or dropped) -------------
RUBRIC_TEXT = "text against its lines v1: every figure in a claim's text stands on the lines of its own entry"
RUBRIC_SAID_BY = "said by v1: a claim given as Greg's has his name on its lines or the two lines above"
_figure = re.compile(r"[A-Za-z]*\d[\w]*(?:[.,]\d+)*")
_greg = re.compile(r"\b(?:Greg|his|he)\b", re.I)
_entry_start = re.compile(r"(#|- |\d+[.)] |\s*\|)")


def _figures(s: str) -> set[str]:
    return {m.group(0).replace(",", "").rstrip(".").lower() for m in _figure.finditer(s)}


def entry_range(lines: list[str], line_start: int) -> tuple[int, int]:
    """The entry a line belongs to: from the last line at or before it that is line 1, a heading, a
    top-level bullet, a numbered item or a table row, to the line before the next such line."""
    def starts(i):
        return i == 1 or bool(_entry_start.match(lines[i - 1]))
    first = line_start
    while first > 1 and not starts(first):
        first -= 1
    end = first
    while end < len(lines) and not starts(end + 1):
        end += 1
    return first, end


def marks_for(claim: dict, lines: list[str]) -> list[tuple[str, str, list[str], list[str], list[str]]]:
    """(rubric, what_was_checked, what_was_observed ...) for each mark the claim earns; empty when the
    checks observe nothing. Two checks by code."""
    at = claim["attrs"]
    a, b = at["line_start"], at["line_end"]
    out = []
    ef, el = entry_range(lines, a)
    on_entry = _figures("\n".join(lines[ef - 1:el]))
    missing = sorted(f for f in _figures(at["text"]) if f not in on_entry)
    if missing:
        out.append((RUBRIC_TEXT,
                    [f"the figures in the claim's text, against lines {ef}-{el} (its entry) of {at['source']} at {at['source_commit'][:10]}"],
                    ["figures in the text that are not on those lines: " + ", ".join(missing)],
                    ["whether the figure comes from another place in the document, or from the reader's own words"]))
    if at.get("said_by") == "Greg":
        lo = max(1, a - 2)
        if not _greg.search("\n".join(lines[lo - 1:b])):
            out.append((RUBRIC_SAID_BY,
                        [f"the claim's lines {a}-{b} and the two lines above ({lo}-{a - 1 if a > lo else a}) of {at['source']} at {at['source_commit'][:10]} for his name"],
                        ["the lines do not name him: no \"Greg\", \"his\" or \"he\" as a whole word on them"],
                        ["whether the substance is his rule restated in another voice"]))
    return out


METHOD = "tools.kgraph.extract"


def evaluation_nodes(claim: dict, lines: list[str], by: str, run: str | None = None) -> tuple[list[dict], list[dict]]:
    """The Evaluation nodes and EVALUATES links for what the two checks observe on one claim. The id
    carries the claim's revision, the rubric, the method, the reviewer and what was observed: the same
    check of the same revision is one node, and another reviewer's check of it is another."""
    nodes, edges = [], []
    for rubric, checked, observed, open_ in marks_for(claim, lines):
        eid = "eval:" + sha([claim["id"], claim["rev"], rubric, METHOD, "code:" + METHOD, observed])
        nodes.append({"id": eid, "type": "Evaluation", "attrs": {
            "rubric": rubric, "what_was_checked": checked, "what_was_observed": observed,
            "what_remains_open": open_,
            "check_type": "deterministic", "method": METHOD, "method_version": by,
            "claim_revision": claim["rev"], "input_hash": claim["content_sha"],
            "location": "tools/kgraph/extract.py",
            "scope": "the claim's own lines at its source_commit",
            "expected_observation": "nothing observed",
            "reviewer": by}})
        edges.append(link("EVALUATES", eid, claim["id"]))
        if run:
            edges.append(link("PRODUCED", run, eid))
    return nodes, edges


def _mark(store: GraphStore, claim_ids, lines: list[str], by: str, run: str | None) -> int:
    nodes, edges = [], []
    for cid in claim_ids:
        n, e = evaluation_nodes(store.node(cid), lines, by, run)
        new = {nd["id"] for nd in n if store.node(nd["id"]) is None}
        nodes += [nd for nd in n if nd["id"] in new]
        edges += [x for x in e if x["src"] in new or x["dst"] in new]
    if nodes:
        store.write(nodes, edges, written_by=by)
    return len(nodes)


def recheck(store: GraphStore, dirs: dict[str, Path]) -> dict:
    """The two marks for every claim already in the graph, each read at its own `source_commit`. An
    Evaluation is written only where something is observed, and one already there is not written again."""
    by = code_stamp(METHOD)
    cache: dict = {}
    rep = {"claims": 0, "no_lines_to_read": 0, "unreadable": [], "marks_written": 0, "already_marked": 0}
    nodes, edges = [], []
    for c in store.nodes("Claim"):
        at = c["attrs"]
        m = re.fullmatch(r"src:([^:@]+)(?:@[^:]+)?:(.+)", at.get("source") or "")
        if not (m and at.get("source_commit") and isinstance(at.get("line_start"), int) and m.group(1) in dirs):
            rep["no_lines_to_read"] += 1
            continue
        key = (m.group(1), m.group(2), at["source_commit"])
        if key not in cache:
            try:
                cache[key] = git_text(dirs[key[0]], key[2], key[1]).splitlines()
            except RuntimeError as e:
                cache[key] = None
                rep["unreadable"].append(f"{key[1]} at {key[2][:10]}: {e}")
        if cache[key] is None:
            continue
        rep["claims"] += 1
        n, e = evaluation_nodes(c, cache[key], by)
        for nd in n:
            if store.node(nd["id"]) is None:
                nodes.append(nd)
            else:
                rep["already_marked"] += 1
        edges += e
    have = {nd["id"] for nd in nodes}
    edges = [e for e in edges if e["src"] in have]       # an Evaluation already there is not linked again
    if nodes:
        store.write(nodes, edges, written_by=by)
    rep["marks_written"] = len(nodes)
    return rep


def _prepare_piece(dirs, piece) -> dict:
    """Everything a piece needs, checked: raises Refused before anything is written."""
    m = re.fullmatch(r"(src:([^:@]+):(.+))@([0-9a-f]{10})#L(\d+)-L(\d+)", str(piece.get("piece", "")))
    if not m:
        raise schema.Refused(f"a returned piece has no usable id: {str(piece.get('piece'))[:80]}")
    sid, repo, rel, cut_at = m.group(1), m.group(2), m.group(3), m.group(4)
    if repo not in dirs:
        raise schema.Refused(f"a returned piece names {repo}, which is not a checkout given here")
    first, last = int(m.group(5)), int(m.group(6))
    src = source_node(repo, dirs[repo], rel)
    read_at = src["attrs"]["commit"]
    if read_at[:10] == cut_at:
        lines = (dirs[repo] / rel).read_text(encoding="utf-8").splitlines()
    else:
        # The file has changed since the brief was cut (the decisions file is added to all the
        # time). The read is checked against the file AS IT STOOD when it was cut, and each claim
        # says which wording it was read from. The grounding check reads the words again later.
        try:
            read_at = git(dirs[repo], "rev-parse", "--verify", "-q", cut_at + "^{commit}")
            lines = git_text(dirs[repo], read_at, rel).splitlines()
        except RuntimeError:
            raise schema.Refused(f"the brief of {rel} was cut at commit {cut_at}, which this checkout of {repo} "
                                 "does not have: make the brief again")
    return {"piece": piece, "sid": sid, "repo": repo, "rel": rel, "first": first, "last": last,
            "src": src, "read_at": read_at, "lines": lines}


def load_result(store: GraphStore, dirs: dict[str, Path], result: dict, run: str,
                expected_pieces: list[dict] | None = None) -> dict:
    """Write what the scout returned. `run` is its AgentRun id (it must already be in the graph).
    Every piece of the answer is checked (its id, its commit) before anything is written: an answer that
    is refused writes nothing. `expected_pieces` (the list `prompt` wrote beside the brief) makes a Task
    line, state open, for each piece of the brief that the answer left out."""
    if store.node(run) is None or store.node(run)["type"] != "AgentRun":
        raise schema.Refused(f"{run} is not an AgentRun of the graph: record the run first")
    by = code_stamp("tools.kgraph.extract")
    prepared = [_prepare_piece(dirs, piece) for piece in result.get("pieces", [])]
    report = {"pieces": 0, "claims_written": 0, "thrown_out": 0, "entities": 0, "marks": 0, "per_piece": []}
    for pp in prepared:
        piece, sid, rel, first, last = pp["piece"], pp["sid"], pp["rel"], pp["first"], pp["last"]
        src, read_at, lines = pp["src"], pp["read_at"], pp["lines"]
        nodes, edges, thrown, beside, identical = [src], [], 0, 0, 0
        seen_ent, taken, new_claims = set(), {}, []
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
            ra, rb = int(c["line_start"]), int(c["line_end"])
            a, b = locate_quote(c["quote"], lines, ra, rb)       # the smallest run of lines holding the quote
            kind, said_by, inf, text = c["statement_kind"], c.get("said_by"), c["inference"], c["text"]
            # A different wording never revises a claim: the plain id stands when no claim has it or the
            # claim that has it says the same; otherwise this one is a second claim beside the first.
            ladder = [claim_id(sid, c["quote"]), claim_id_beside(sid, c["quote"], text, kind, said_by),
                      claim_id_beside(sid, c["quote"], text, kind, said_by, inf),
                      claim_id_beside(sid, c["quote"], text, kind, said_by, inf, (a, b))]
            cid, skip = None, False
            for cand in ladder:
                held = taken.get(cand)
                if held is not None:                              # an earlier return of this piece
                    if _same_claim(held["attrs"], text, kind, said_by, inf):
                        if (held["attrs"]["line_start"], held["attrs"]["line_end"]) == (a, b):
                            skip = True                           # the same return twice: one claim
                            break
                        continue
                    continue
                ex = store.node(cand)
                if ex is None or _same_claim(ex["attrs"], text, kind, said_by, inf):
                    cid = cand
                    break
            if skip:
                identical += 1
                continue
            if cid is None:                                       # cannot happen: the last id holds the lines
                raise schema.Refused(f"no id is free for a claim of {rel} lines {a}-{b}")
            if cid != ladder[0]:
                beside += 1
            attrs = {"text": text, "statement_kind": kind, "inference": inf,
                     "said_by": said_by, "said_on": c.get("said_on"),
                     "source": sid, "source_commit": read_at,
                     "line_start": a, "line_end": b, "lines_as_returned": [ra, rb], "quote": c["quote"],
                     "proposer": said_by, "knowledge_time": c.get("said_on"),
                     "extracted_by": run}
            taken[cid] = {"attrs": attrs}
            nodes.append({"id": cid, "type": "Claim", "attrs": attrs})
            new_claims.append(cid)
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
        uniq = {}
        for nd in nodes:
            uniq[nd["id"]] = nd
        euniq = {}
        for e in edges:
            euniq[e["id"]] = e
        store.write(list(uniq.values()), list(euniq.values()), written_by=by)
        report["marks"] += _mark(store, new_claims, lines, by, run)
        # Greg, 2026-11-24: no new claim is tied to a tastytrade platform issue. What belongs to the
        # platform is marked here, piece by piece as it is loaded, so that nothing made later can rest on it.
        from . import platform_scope
        report["marked_as_tastytrade_platform"] = report.get("marked_as_tastytrade_platform", 0) + platform_scope.mark(store, dirs)["new"]
        written = len(new_claims)
        report["pieces"] += 1
        report["claims_written"] += written
        report["thrown_out"] += thrown
        report["per_piece"].append({"piece": piece["piece"], "claims_written": written, "thrown_out": thrown,
                                    "second_claims_on_the_same_quote": beside,
                                    "identical_returns_in_one_piece": identical})
    if expected_pieces is not None:
        got = {pp["piece"]["piece"] for pp in prepared}
        nodes, edges = [], []
        for ex in expected_pieces:
            if ex["piece"] in got:
                continue
            tid = "task:piece-not-returned:" + sha([ex["piece"], run])
            attrs = {"text": f"The brief held {ex['path']} lines {ex['first']}-{ex['last']}; the answer of {run} has nothing for "
                             "that piece (no claim and no empty entry), so it is not read.",
                     "state": "open", "reason": "the piece is not in the answer", "piece": ex["piece"]}
            try:
                s0 = source_node(ex["repo"], dirs[ex["repo"]], ex["path"])
                nodes.append(s0)
                attrs["source"] = s0["id"]
            except (RuntimeError, KeyError):
                pass
            nodes.append({"id": tid, "type": "Task", "attrs": attrs})
            edges.append(link("PRODUCED", run, tid))
            if "source" in attrs:
                edges.append(link("DEPENDS_ON", tid, attrs["source"]))
        if nodes:
            store.write(nodes, edges, written_by=by)
        report["pieces_left_out_by_the_answer"] = sum(1 for n in nodes if n["type"] == "Task")
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
    p.add_argument("--pieces", help="the <brief>.pieces.json that `prompt` wrote")
    sub.add_parser("coverage")
    sub.add_parser("recheck")
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
        Path(str(a.out) + ".pieces.json").write_text(json.dumps(
            [{**{k: v for k, v in l.items() if k != "source"}, "source_id": l["source"]["id"]} for l in listing],
            indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"out": a.out, "bytes": len(brief.encode()), "pieces": [
            {k: v for k, v in l.items() if k != "source"} for l in listing]}, indent=1))
    elif a.verb == "load":
        text = Path(a.result).read_text(encoding="utf-8")
        start, end = text.find("{"), text.rfind("}")
        exp = json.loads(Path(a.pieces).read_text(encoding="utf-8")) if a.pieces else None
        print(json.dumps(load_result(store, dirs, json.loads(text[start:end + 1]), a.run, exp), indent=1))
    elif a.verb == "recheck":
        print(json.dumps(recheck(store, dirs), indent=1))
    elif a.verb == "coverage":
        out = coverage(store, dirs)
        print(json.dumps({k: v for k, v in out.items() if k != "documents"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
