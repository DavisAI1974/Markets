"""Stage 5a: a session starts from the graph, not from the pile of handoffs.

  python3 -m tools.kgraph.context --budget 6000                        # a session start
  python3 -m tools.kgraph.context --budget 4000 --task "<what the session is to do>" [--hops 2]
      [--out context.md] [--cut-list cut.json]

NOTHING IS REPLACED (Greg, 2026-11-24; the paper: "every superseded object remains addressable",
"prioritize recent verified claims", "include conflicts and uncertainty"). No claim is left out because a
later one exists or because it is parked. A claim that has something against it is MARKED with what
stands against it. A claim with a later claim set over it (SUPERSEDES) and a claim firmly marked as
belonging to the tastytrade platform are CALLED LAST, so under a budget they are the first to fall, and a
larger budget shows them. A claim that a claim contradicts (CONTRADICTS) is marked, with the first 100
characters of the claim that contradicts it, and is NOT called last: both stand, as the paper says
("include conflicts and uncertainty"). A claim a check on record has marked (its text carries a figure that is
not on its lines; given as Greg's but his name is not on its lines) carries that mark too.

What it does (plan, stage 5a):
  1. with a task: finds the things the task names (entities, by name or by a name merged into them),
     and walks one or two hops over the links to the claims about them. Without a task: every claim.
  2. folds a claim into another's line only when one quote holds the other (at least FOLD_WORDS words),
     the two are of two DIFFERENT files, and they have the same statement kind and the same speaker. No
     chain through a third claim: a group is one standing claim plus the claims folded directly into it,
     and never holds two claims of one file. The line cites each folded claim by file:line and by id.
  3. marks a claim that has something against it: a later claim says otherwise (a SUPERSEDES link), a
     claim contradicts it (both stand), it is parked as a tastytrade platform issue, or it names that
     platform (nothing new may rest on it); and the marks of the checks on record.
  4. writes the claims by kind, those with nothing against them first and newest first, within the
     token budget, each line with its claim id, its file and line, who said it and when, so any line
     can be followed back and checked.
  5. says at the end what is NOT in the text: how many claims fell under the budget (and of which
     kind), how many have something against them, which documents have not been read into claims yet
     (and, of each one read at an earlier wording, to which line), why claims were not believed (each
     reason counted), and the checks on record by decision. Nothing is left out in silence: the returned
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
    parked = {c for c, t in ties.items() if t["rule"] not in platform_scope.PROVISIONAL and c in claims}
    called_last = sorted(set(over) | parked)

    def standing(cid: str) -> int:
        # called last: a later claim set over it, or firmly marked as the tastytrade platform's.
        # A contradicted claim is marked, not called last (both stand).
        return 1 if (cid in over or cid in parked) else 0

    entities, hop_of, how = [], {}, "every claim of the graph (a session start)"
    if task:
        entities, hop1, hop2, how = _reach(store, live, task, hops)
        hop_of = {**{c: 2 for c in hop2}, **{c: 1 for c in hop1}}
        reached = [c for c in live if c in hop_of]
    else:
        reached = list(live)
    not_reached = sorted(set(live) - set(reached))

    # Fold claims that carry the same words in two FILES. One quote holds the other, word for word, the
    # shorter is at least FOLD_WORDS words, the two files differ, and they have the same statement kind and
    # the same speaker. No chain: the claim that stands takes in the claims folded DIRECTLY into it, and a
    # group never holds two claims of one file.
    quotes = {c: _strip(live[c]["attrs"].get("quote") or "") for c in reached}

    def foldable(x: str, y: str) -> bool:
        ax, ay = live[x]["attrs"], live[y]["attrs"]
        if ax.get("source") == ay.get("source"):
            return False
        if ax["statement_kind"] != ay["statement_kind"] or ax.get("said_by") != ay.get("said_by"):
            return False
        qx, qy = quotes[x], quotes[y]
        if len(qx.split()) < FOLD_WORDS or len(qy.split()) < FOLD_WORDS:
            return False
        return qx in qy or qy in qx

    order = sorted(reached, key=lambda c: clock.key(live[c]), reverse=True)
    order.sort(key=standing)                                # one with nothing against it stands first
    stands_for, folded, taken = {}, [], set()
    for head in order:
        if head in taken:
            continue
        taken.add(head)
        files = {live[head]["attrs"].get("source")}
        mine = []
        for other in order:
            if other in taken or live[other]["attrs"].get("source") in files or not foldable(head, other):
                continue
            mine.append(other)
            taken.add(other)
            files.add(live[other]["attrs"].get("source"))
        stands_for[head] = mine
        folded += mine

    # the marks each claim carries (every claim of the graph)
    evals_of: dict[str, list[dict]] = {}
    for e in store.edges("EVALUATES"):
        ev = store.node(e["src"])
        if ev is not None and ev["type"] == "Evaluation" and e["dst"] in claims:
            evals_of.setdefault(e["dst"], []).append(ev)

    def _figures(ev: dict) -> str:
        seen = ev["attrs"].get("what_was_observed") or []
        seen = [seen] if isinstance(seen, str) else seen
        figs = list(dict.fromkeys(m for t in seen for m in re.findall(r"\d[\d,]*(?:\.\d+)?", str(t))))
        return ", ".join(figs) if figs else "; ".join(str(t) for t in seen)[:160]

    marks: dict[str, list[str]] = {}
    for cid, c in claims.items():
        m = []
        if c["attrs"]["inference"]:
            m.append("a reading, not a measurement")
        if cid in over:
            m.append("a later claim says otherwise: " + ", ".join("c:" + o.split(":", 1)[1] for o in over[cid]))
        for o in against.get(cid, []):
            said = _ws.sub(" ", claims[o]["attrs"]["text"]).strip()[:100] if o in claims else "(not a claim of this graph)"
            m.append(f"contradicted by c:{o.split(':', 1)[1]}: \"{said}\"; both stand")
        if cid in parked:
            m.append("parked: a tastytrade platform issue")
        elif cid in ties:
            m.append("names the tastytrade platform: nothing new may rest on it")
        for ev in evals_of.get(cid, []):
            rub = ev["attrs"].get("rubric") or ""
            if rub.startswith("text against its lines v1"):
                m.append(f"its text carries a figure that is not on its lines: {_figures(ev)}")
            elif rub.startswith("said by v1"):
                m.append("given as Greg's; his name is not on its lines")
        marks[cid] = list(dict.fromkeys(m))

    def where_of(cid: str) -> str:
        a = live[cid]["attrs"]
        src = a.get("source") or ""
        return f"{src.rsplit('/', 1)[-1]}:{a.get('line_start')}" if src else "no source line"

    def line(cid: str) -> str:
        a = live[cid]["attrs"]
        also = ""
        if stands_for.get(cid):
            own = _ws.sub(" ", a["text"]).strip()

            def folded_line(o: str) -> str:
                t = _ws.sub(" ", live[o]["attrs"]["text"]).strip()
                said = f' "{t}"' if t != own else ""          # a folded claim worded otherwise keeps its own wording here
                return (f"also {where_of(o)} (c:{o.split(':', 1)[1]})" + said
                        + "".join(f" ({m})" for m in marks[o] if m != "a reading, not a measurement"))
            also = " | " + ", ".join(folded_line(o) for o in stands_for[cid])
        mark = "".join(f"({m}) " for m in marks[cid])
        return (f"- {mark}{_ws.sub(' ', a['text']).strip()} [c:{cid.split(':', 1)[1]} | {where_of(cid)} | "
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
    evaluations = store.nodes("Evaluation")
    asks = [e for e in evaluations if e["attrs"].get("decision") == "revise"]
    docs = {c["attrs"].get("source") for c in claims.values() if c["attrs"].get("source")}

    head = [
        "# Session context, built from the knowledge graph",
        f"Built {now()} by {code_stamp('tools.kgraph.context')} from {len(claims)} claims read out of {len(docs)} documents "
        f"(this text is built from those {len(docs)} documents and no others).",
        "Manual of the agent program: Markets tools/README_AGENT_PROGRAM.md.",
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
        for t in sorted(changed, key=lambda t: t.get("source") or ""):
            out.append(f"  - {(t.get('source') or '?').rsplit('/', 1)[-1]}: read to line "
                       f"{t.get('last_line_with_a_claim')} of {t.get('lines')}; the lines after are not in this text")
        if thrown:
            why: dict[str, int] = {}
            for t in thrown:
                r = t["attrs"].get("reason") or "no reason on the Task line"
                why[r] = why.get(r, 0) + 1
            out.append(f"- {len(thrown)} claims a reader returned were not believed as they are; they are kept as Task "
                       "lines. By reason: " + "; ".join(f"{n} {r}" for r, n in sorted(why.items(), key=lambda x: (-x[1], x[0]))) + ".")
        if evaluations:
            by_dec: dict[str, int] = {}
            for e in evaluations:
                d = e["attrs"].get("decision") or "no decision"
                by_dec[d] = by_dec.get(d, 0) + 1
            out.append(f"- {len(evaluations)} checks on record; {len(asks)} of them ask for evidence (decision \"revise\"). "
                       "By decision: " + ", ".join(f"{n} {d}" for d, n in sorted(by_dec.items())) + ". "
                       "(`python3 -m tools.kgraph.grounding all`).")
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
            "cut_by_kind": cut_by_kind, "not_reached": not_reached, "called_last": called_last, "marks": marks,
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
        Path(a.cut_list).write_text(json.dumps({k: out[k] for k in ("cut", "cut_by_kind", "folded", "not_reached", "called_last", "marks")},
                                               indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in out.items() if k != "text"}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
