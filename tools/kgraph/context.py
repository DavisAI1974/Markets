"""Stage 5a: a session starts from the graph, not from the pile of handoffs.

  python3 -m tools.kgraph.context --budget 6000                        # a session start
  python3 -m tools.kgraph.context --budget 4000 --task "<what the session is to do>" [--hops 2]
      [--out context.md] [--cut-list cut.json]

NOTHING IS REPLACED (Greg, 2026-11-24; the paper: "every superseded object remains addressable",
"prioritize recent verified claims", "include conflicts and uncertainty"). No claim is left out because a
later one exists or because it is parked. A claim that has something against it is MARKED with what
stands against it and CALLED LAST, so under a budget it is the first to fall, and a larger budget shows it.

What it does (plan, stage 5a):
  1. with a task: finds the things the task names (entities, by name or by a name merged into them),
     and walks one or two hops over the links to the claims about them. Without a task: every claim.
  2. folds claims that carry the same words in two files (Greg's sentence copied from the decisions
     file into a handoff) into one line that cites every file.
  3. marks a claim that has something against it: a later claim says otherwise (a SUPERSEDES link), a
     claim contradicts it (both stand), it is parked as a tastytrade platform issue, or it names that
     platform (nothing new may rest on it).
  4. writes the claims by kind, those with nothing against them first and newest first, within the
     token budget, each line with its claim id, its file and line, who said it and when, so any line
     can be followed back and checked.
  5. says at the end what is NOT in the text: how many claims fell under the budget (and of which
     kind), how many have something against them, which documents have not been read into claims yet,
     and how many checks on record ask for evidence. Nothing is left out in silence: the returned
     lists place every claim of the graph in exactly one of included, folded, cut, not_reached.

Tokens are estimated at 4 characters a token (no tokenizer is called here); the text says so.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import platform_scope
from .extract import repo_dirs
from .resolve import canonical, clean
from .sources import code_stamp, git
from .store import GraphStore, now

CHARS_PER_TOKEN = 4
HUB_LIMIT = 40          # a second hop does not pass through a name carried by more claims than this
FOLD_WORDS = 8          # two files carry "the same words" when one quote holds the other and it is this long

# section title, the statement kinds in it, its share of the budget (declared; what a section does
# not use passes to the next one)
SECTIONS = (
    ("WHAT GREG DECIDED (newest first)", ("decision",), 0.25),
    ("RULES THAT STAND", ("rule",), 0.15),
    ("WHERE THINGS STAND", ("state", "measurement"), 0.30),
    ("PLANNED, NOT DONE", ("plan",), 0.10),
    ("OPEN, NOT ANSWERED", ("open_question",), 0.10),
    ("SLIPS, SO THEY ARE NOT MADE AGAIN", ("slip",), 0.05),
    ("WORDS AND WHAT THEY MEAN", ("definition",), 0.05),
)
_ws = re.compile(r"\s+")
_word = re.compile(r"[A-Za-z][A-Za-z0-9_/.\-]{3,}")


def estimate_tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def _norm(s: str) -> str:
    return _ws.sub(" ", s).strip().lower()


def _strip(s: str) -> str:
    """A quote without its case, its punctuation at the ends and its spacing: the words themselves."""
    return _norm(re.sub(r"[^\w\s'-]", " ", s))


def _doc_date(path: str) -> str:
    m = re.search(r"(20\d{6})([A-Z])?", path)
    return (m.group(1)[:4] + "-" + m.group(1)[4:6] + "-" + m.group(1)[6:] + (m.group(2) or "")) if m else ""


class _Clock:
    """When a claim was made, as well as the graph can tell: the date the lines give, else the date in
    the file's name; then the commit date of the file; then the line (a later line of one file is
    later)."""

    def __init__(self, store: GraphStore, dirs: dict | None):
        self.store, self.dirs, self._commit = store, dirs or {}, {}

    def commit_date(self, source_id: str) -> str:
        if source_id not in self._commit:
            src, out = self.store.node(source_id), ""
            repo = source_id.split(":", 2)[1]
            if src and repo in self.dirs and src["attrs"].get("commit"):
                try:
                    out = git(self.dirs[repo], "log", "-1", "--format=%cI", src["attrs"]["commit"])
                except RuntimeError:
                    out = ""
            self._commit[source_id] = out
        return self._commit[source_id]

    def key(self, claim: dict):
        a = claim["attrs"]
        src = a.get("source") or ""
        return (a.get("said_on") or _doc_date(src)[:10], self.commit_date(src) if src else "", _doc_date(src),
                a.get("line_start") or 0)


def _task_entities(store: GraphStore, task: str) -> list[str]:
    """The Entities the task names, by their name as written (whole phrase, any letter case)."""
    hits = []
    for e in store.nodes("Entity"):
        if e["attrs"].get("entity_kind") == "scope":
            continue
        name = clean(e["attrs"]["name"])
        if len(name) < 3:
            continue
        if re.search(r"(?<![\w/])" + re.escape(name) + r"(?![\w/])", task, flags=re.IGNORECASE):
            hits.append(e["id"])
    return sorted(hits)


def _reach(store: GraphStore, claims: dict, task: str, hops: int) -> tuple[list[str], list[str], list[str], str]:
    """(entities named by the task, claims reached at hop 1, claims reached only at hop 2, how)."""
    ents = _task_entities(store, task)
    canon = {e: canonical(store, e) for e in ents}
    targets = set(ents) | set(canon.values())
    about: dict[str, set[str]] = {}          # claim -> the (canonical) things it names
    carriers: dict[str, set[str]] = {}       # thing -> claims that name it
    for e in store.edges("MENTIONS"):
        if e["src"] in claims:
            thing = canonical(store, e["dst"])
            for t in {e["dst"], thing}:
                about.setdefault(e["src"], set()).add(t)
                carriers.setdefault(t, set()).add(e["src"])
    hop1 = set()
    for t in targets:
        hop1 |= carriers.get(t, set())
        hop1 |= {cid for cid, c in claims.items() if c["attrs"].get("source") == t}   # the task names a file
    how = "the things the task names"
    if not hop1:
        # no named thing: the claims that carry at least half of the task's own words
        words = [w.lower() for w in dict.fromkeys(_word.findall(task))]
        for cid, c in claims.items():
            low = (c["attrs"]["text"] + " " + (c["attrs"].get("quote") or "")).lower()
            if words and sum(w in low for w in words) * 2 >= len(words):
                hop1.add(cid)
        how = "no named thing was found in the task; claims carrying at least half of its words"
    hop2 = set()
    if hops >= 2:
        for cid in hop1:
            for thing in about.get(cid, ()):
                if thing in targets or len(carriers.get(thing, ())) > HUB_LIMIT:
                    continue
                hop2 |= carriers[thing]
        hop2 -= hop1
    return ents, sorted(hop1), sorted(hop2), how


def build(store: GraphStore, task: str | None, budget_tokens: int, hops: int = 1, dirs: dict | None = None) -> dict:
    clock = _Clock(store, dirs)
    claims = {c["id"]: c for c in store.nodes("Claim")}
    live = claims
    # NOTHING IS REPLACED (Greg, 2026-11-24). A claim that has something against it is marked with what
    # stands against it and is called last; it is never left out because of a link.
    over = {}                                    # claim -> the later claim(s) set over it
    for e in store.edges("SUPERSEDES"):
        if e["dst"] in claims:
            over.setdefault(e["dst"], []).append(e["src"])
    against = {}                                 # claim -> the claims that contradict it
    for e in store.edges("CONTRADICTS"):
        if e["dst"] in claims:
            against.setdefault(e["dst"], []).append(e["src"])
    ties = platform_scope.ties(store)
    parked = {c for c, t in ties.items() if t["rule"] == "the running list" and c in claims}
    called_last = sorted(set(over) | parked)

    def standing(cid: str) -> int:
        return 1 if (cid in over or cid in parked) else 0

    entities, hop_of, how = [], {}, "every claim of the graph (a session start)"
    if task:
        entities, hop1, hop2, how = _reach(store, live, task, hops)
        hop_of = {**{c: 2 for c in hop2}, **{c: 1 for c in hop1}}
        reached = [c for c in live if c in hop_of]
    else:
        reached = list(live)
    not_reached = sorted(set(live) - set(reached))

    # Fold claims that carry the same words in two FILES (the newest stands for them): one quote holds
    # the other, word for word, and the shorter is at least FOLD_WORDS words. Inside one file nothing
    # is folded: two claims that quote overlapping words of one document are two claims.
    quotes = {c: _strip(live[c]["attrs"].get("quote") or "") for c in reached}
    parent = {c: c for c in reached}

    def root(c: str) -> str:
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    long_enough = [c for c in reached if len(quotes[c].split()) >= FOLD_WORDS]
    long_enough.sort(key=lambda c: len(quotes[c]))
    for i, short in enumerate(long_enough):
        for other in long_enough[i + 1:]:
            if live[short]["attrs"].get("source") != live[other]["attrs"].get("source") and quotes[short] in quotes[other]:
                parent[root(short)] = root(other)
    groups: dict[str, list[str]] = {}
    for cid in reached:
        groups.setdefault(root(cid), []).append(cid)
    stands_for, folded = {}, []
    for ids in groups.values():
        ids.sort(key=lambda c: clock.key(live[c]), reverse=True)
        ids.sort(key=standing)                              # one with nothing against it stands for the group
        stands_for[ids[0]] = ids[1:]
        folded += ids[1:]

    def line(cid: str) -> str:
        a = live[cid]["attrs"]
        src = a.get("source") or ""
        where = f"{src.rsplit('/', 1)[-1]}:{a.get('line_start')}" if src else "no source line"
        also = ""
        if stands_for.get(cid):
            also = " | also " + ", ".join(
                f"{live[o]['attrs']['source'].rsplit('/', 1)[-1]}:{live[o]['attrs']['line_start']}" for o in stands_for[cid])
        mark = "(a reading, not a measurement) " if a["inference"] else ""
        if cid in over:
            mark += "(a later claim says otherwise: " + ", ".join("c:" + o.split(":", 1)[1] for o in over[cid]) + ") "
        if cid in against:
            mark += "(contradicted by " + ", ".join("c:" + o.split(":", 1)[1] for o in against[cid]) + "; both stand) "
        if cid in parked:
            mark += "(parked: a tastytrade platform issue) "
        elif cid in ties:
            mark += "(names the tastytrade platform: nothing new may rest on it) "
        return (f"- {mark}{_ws.sub(' ', a['text']).strip()} [c:{cid.split(':', 1)[1]} | {where} | "
                f"{a.get('said_by') or '-'} | {a.get('said_on') or '-'}{also}]")

    by_section = []
    for title, kinds, share in SECTIONS:
        ids = [c for c in stands_for if live[c]["attrs"]["statement_kind"] in kinds]
        ids.sort(key=lambda c: clock.key(live[c]), reverse=True)
        ids.sort(key=lambda c: hop_of.get(c, 1))            # what the task names first, then the second hop
        if kinds == ("decision",):
            ids.sort(key=lambda c: live[c]["attrs"].get("said_by") != "Greg")     # his own decisions first
        ids.sort(key=standing)                               # a claim with something against it is called last
        by_section.append([title, share, ids, []])

    not_read = [t["attrs"] for t in store.nodes("Task") if t["attrs"]["state"] == "not_extracted"]
    changed = [t["attrs"] for t in store.nodes("Task") if t["id"].startswith("task:extract:") and t["attrs"]["state"] == "open"]
    thrown = [t for t in store.nodes("Task") if t["id"].startswith("task:thrown-out:")]
    asks = [e for e in store.nodes("Evaluation") if e["attrs"].get("decision") == "revise"]
    docs = {c["attrs"].get("source") for c in claims.values() if c["attrs"].get("source")}

    head = [
        "# Session context, built from the knowledge graph",
        f"Built {now()} by {code_stamp('tools.kgraph.context')} from {len(claims)} claims read out of {len(docs)} documents.",
        f"Scope: {how}." + (f" Task: {task}" if task else ""),
        f"Budget {budget_tokens} tokens, estimated at {CHARS_PER_TOKEN} characters a token (no tokenizer was called).",
        "A line reads: what is claimed [c:<claim id> | file:line | who | when]. A claim can be followed back "
        "to its file, and `python3 -m tools.kgraph.grounding claim claim:<id>` checks it.",
    ]

    def foot(cut_ids: list[str]) -> list[str]:
        kinds: dict[str, int] = {}
        for c in cut_ids:
            k = live[c]["attrs"]["statement_kind"]
            kinds[k] = kinds.get(k, 0) + 1
        out = ["", "## NOT IN THIS TEXT"]
        out.append(f"- {len(cut_ids)} claims are not shown for want of budget"
                   + (": " + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())) if kinds else "")
                   + ". A larger budget or a task brings them.")
        if not_reached:
            out.append(f"- {len(not_reached)} claims are about things the task does not name (not reached in {hops} hop(s)).")
        if called_last or ties:
            out.append(f"- {len(called_last)} claims have something against them ({len(over)} with a later claim that says "
                       f"otherwise, {len(parked)} parked as tastytrade platform issues). Nothing is removed: each is marked "
                       "and called last, so it is the first to fall under the budget; a larger budget shows it. "
                       f"{len([c for c in ties if c not in parked])} more only name the tastytrade platform and are marked.")
        out.append(f"- {len(folded)} claims are folded into a line that carries the same words from another file (cited there).")
        if not_read or changed:
            lines_left = sum(t.get("lines") or 0 for t in not_read)
            out.append(f"- {len(not_read)} documents ({lines_left} lines) have not been read into claims; "
                       f"{len(changed)} were read at an earlier wording and have changed since. "
                       "`python3 -m tools.kgraph.extract coverage` lists them.")
        if thrown:
            out.append(f"- {len(thrown)} claims a reader returned were not believed (their quote was not in the file); "
                       "they are kept as Task lines.")
        if asks:
            out.append(f"- {len(asks)} checks on record ask for evidence (`python3 -m tools.kgraph.grounding all`).")
        return out

    budget_chars = budget_tokens * CHARS_PER_TOKEN
    fixed = len("\n".join(head)) + len("\n".join(foot(list(stands_for)))) + 120
    room = max(0, budget_chars - fixed - sum(len(s[0]) + 6 for s in by_section))
    carry = 0.0
    for sec in by_section:                       # first pass: each section its share, the unused passed on
        allow, used = sec[1] * room + carry, 0
        while sec[2] and used + len(line(sec[2][0])) + 1 <= allow:
            cid = sec[2].pop(0)
            sec[3].append(cid)
            used += len(line(cid)) + 1
        carry = allow - used
    left = carry
    for sec in by_section:                       # second pass: what is still free, in section order
        while sec[2] and len(line(sec[2][0])) + 1 <= left:
            cid = sec[2].pop(0)
            sec[3].append(cid)
            left -= len(line(cid)) + 1

    def render() -> tuple[str, list[str], list[str]]:
        body, included = list(head), []
        for title, _, _, chosen in by_section:
            if chosen:
                body += ["", f"## {title}"] + [line(c) for c in chosen]
                included += chosen
        cut = [c for sec in by_section for c in sec[2]]
        return "\n".join(body + foot(cut)) + "\n", included, cut

    text, included, cut = render()
    while estimate_tokens(text) > budget_tokens and any(sec[3] for sec in by_section):
        sec = max((s for s in by_section if s[3]), key=lambda s: len(s[3]))      # trim the longest section's last line
        sec[2].insert(0, sec[3].pop())
        text, included, cut = render()

    cut_by_kind: dict[str, int] = {}
    for c in cut:
        k = live[c]["attrs"]["statement_kind"]
        cut_by_kind[k] = cut_by_kind.get(k, 0) + 1
    return {"text": text, "tokens_estimated": estimate_tokens(text), "budget_tokens": budget_tokens,
            "task": task, "hops": hops, "entities": entities, "reached": sorted(reached),
            "included": included, "folded": sorted(folded), "cut": cut,
            "cut_by_kind": cut_by_kind, "not_reached": not_reached, "called_last": called_last,
            "documents_not_read": len(not_read), "claims_in_graph": len(claims)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--markets")
    ap.add_argument("--platform")
    ap.add_argument("--graph-dir")
    ap.add_argument("--budget", type=int, required=True, help="tokens")
    ap.add_argument("--task")
    ap.add_argument("--hops", type=int, default=1, choices=(1, 2))
    ap.add_argument("--out")
    ap.add_argument("--cut-list", help="write the ids of every claim not in the text, by why, to this file")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    out = build(store, a.task, a.budget, a.hops, repo_dirs(store.data_root, a.markets, a.platform))
    if a.out:
        Path(a.out).write_text(out["text"], encoding="utf-8")
    else:
        sys.stdout.write(out["text"])
    if a.cut_list:
        Path(a.cut_list).write_text(json.dumps({k: out[k] for k in ("cut", "cut_by_kind", "folded", "not_reached", "called_last")},
                                               indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in out.items() if k != "text"}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
