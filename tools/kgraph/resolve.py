"""Stage 4b, the last part: names that mean one thing are merged, and every merge can be undone.

A merge is one RESOLVED_TO link from a surface form (an Entity named in a document) to the entry it
means (a file's Source, a Commit, a dipole, or another Entity). The link keeps the name as written
(`alias`), the evidence, the confidence and who made it. Nothing is rewritten: the surface form
stays a node, its MENTIONS links stay, and `undo` takes the link back by adding a withdrawn line.

Two makers of merges:
  code   exact rules only, each with its evidence, confidence 1.0 (`rules`): a name that is one
         tracked file's path or its only basename; a commit id that one repository knows; a dipole
         id; "handoff W" where one handoff file carries that letter.
  model  the resolver (the plan gives this to Sonnet) returns {"merges": [{from, to, evidence,
         confidence}]}; `apply` checks each one and writes those at or above the cutoff. A merge
         under the cutoff, or one that cannot be placed, is kept as a Task line, not applied and
         not lost.

  python3 -m tools.kgraph.resolve rules                      # apply the exact rules
  python3 -m tools.kgraph.resolve candidates --out brief.txt # the resolver's brief: what is still unmerged
  python3 -m tools.kgraph.resolve apply --merges m.json --run run:0025 [--min-confidence 0.9]
  python3 -m tools.kgraph.resolve undo --edge e:... --reason "..." --run run:0025
  python3 -m tools.kgraph.resolve supersede --new claim:... --old claim:... --why "..." --run run:0025
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import schema
from .extract import repo_dirs
from .sources import code_stamp, commit_node, git, link, source_id, source_node
from .store import GraphStore, sha

NEVER_READ = (".env",)           # key files: never opened, never hashed
MERGE_TARGET_TYPES = ("Entity", "Source", "Commit", "DipoleEvent", "Peak", "TradeDay", "CalcOutput",
                      "AgentRun", "Family", "Chain", "Render", "Artifact")


SURFACE = "named in a document"      # the Entities that are surface forms; a scope or a rule version is not one


def surface_forms(store: GraphStore) -> list[dict]:
    return [e for e in store.nodes("Entity") if e["attrs"].get("entity_kind") == SURFACE]


def clean(name: str) -> str:
    return name.strip().strip("`'\"").strip()


def _standing_merges(store: GraphStore) -> dict[str, list[dict]]:
    """surface form -> its standing RESOLVED_TO links, the earliest written first."""
    by: dict[str, list[dict]] = {}
    for e in store.edges("RESOLVED_TO"):
        by.setdefault(e["src"], []).append(e)
    for v in by.values():
        v.sort(key=lambda e: (e["written_at"], e["id"]))
    return by


def double_merges(store: GraphStore) -> list[str]:
    """One line for each surface form that has two or more standing merges (to different entries or
    through different links): the check lists them; none is withdrawn or chosen away by code."""
    out = []
    for src, links in sorted(_standing_merges(store).items()):
        if len(links) > 1:
            out.append(f"{src}: {len(links)} standing merges, to " + "; ".join(
                f"{e['dst']} ({e['attrs'].get('rule', e['attrs'].get('evidence', ''))}, written {e['written_at']})"
                for e in links))
    return out


def canonical(store: GraphStore, node_id: str, notes: list | None = None) -> str:
    """Follow the merges that stand from a node to the entry it means (itself when unmerged). When a
    surface form has two standing merges the EARLIEST written one is followed, and `notes` (when given)
    says so and names the ones not followed; `kgraph check` lists every such form."""
    by = _standing_merges(store)
    seen = set()
    while node_id in by and node_id not in seen:
        seen.add(node_id)
        links = by[node_id]
        if len(links) > 1 and notes is not None:
            notes.append(f"{node_id} has {len(links)} standing merges: followed {links[0]['dst']} (the earliest written); "
                         "not followed: " + ", ".join(e["dst"] for e in links[1:]))
        node_id = links[0]["dst"]
    return node_id


def aliases(store: GraphStore, node_id: str) -> list[str]:
    """Every name written for an entry: the surface forms merged into it, directly or through another."""
    names, todo, seen = [], [node_id], set()
    edges = store.edges("RESOLVED_TO")
    while todo:
        cur = todo.pop()
        for e in edges:
            if e["dst"] == cur and e["src"] not in seen:
                seen.add(e["src"])
                names.append(e["attrs"]["alias"])
                todo.append(e["src"])
    return sorted(set(names))


# ---- the exact rules ---------------------------------------------------------------------------
def _tracked(dirs: dict[str, Path]) -> dict[str, list[tuple[str, str]]]:
    """name -> [(repo, path)] for every tracked file, under its full path and under its basename."""
    index: dict[str, list[tuple[str, str]]] = {}
    for repo, d in dirs.items():
        for path in git(d, "ls-files").splitlines():
            for key in {path, path.rsplit("/", 1)[-1]}:
                index.setdefault(key, []).append((repo, path))
    return index


def rule_merges(store: GraphStore, dirs: dict[str, Path]) -> tuple[list[dict], list[dict], list[dict]]:
    """The merges the exact rules give for the Entities not merged yet: (merges, new nodes they point
    at, names a rule matched but could not place, each with the reason)."""
    tracked = _tracked(dirs)
    merged = {e["src"] for e in store.edges("RESOLVED_TO")}
    merges, new_nodes, unplaced = [], {}, []
    for ent in surface_forms(store):
        if ent["id"] in merged:
            continue
        name = clean(ent["attrs"]["name"])
        target, evidence = None, None
        hits = tracked.get(name) or tracked.get(name.lstrip("./"))
        m_handoff = re.fullmatch(r"(?i)handoff ([A-Z])", name)
        if hits is not None:
            if len(hits) > 1:
                unplaced.append({"entity": ent["id"], "name": name,
                                 "why": f"{len(hits)} tracked files carry this name: " + ", ".join(f"{r}:{p}" for r, p in hits[:6])})
                continue
            repo, path = hits[0]
            if path.endswith(NEVER_READ):
                unplaced.append({"entity": ent["id"], "name": name, "why": "a key file: it is never opened or hashed"})
                continue
            node = source_node(repo, dirs[repo], path)
            new_nodes[node["id"]] = node
            target, evidence = node["id"], f"the name is the path or the only basename of one tracked file: {repo}:{path}"
        elif m_handoff:
            files = [(r, p) for key, v in tracked.items() for r, p in v
                     if key == p and re.fullmatch(rf".*NEXT_SESSION_HANDOFF_\d{{8}}{m_handoff.group(1).upper()}\.md", p)]
            if len(files) == 1:
                repo, path = files[0]
                node = source_node(repo, dirs[repo], path)
                new_nodes[node["id"]] = node
                target, evidence = node["id"], f"one handoff file carries the letter: {repo}:{path}"
            else:
                unplaced.append({"entity": ent["id"], "name": name, "why": f"{len(files)} handoff files carry that letter"})
                continue
        elif re.fullmatch(r"[0-9a-f]{7,40}", name):
            found = []
            for repo, d in dirs.items():
                try:
                    full = git(d, "rev-parse", "--verify", "-q", name + "^{commit}")
                except RuntimeError:
                    continue
                if full:
                    found.append((repo, full))
            if len(found) == 1:
                node = commit_node(found[0][0], dirs[found[0][0]], found[0][1])
                new_nodes[node["id"]] = node
                target, evidence = node["id"], f"the checkout of {found[0][0]} knows this commit id and no other does"
            else:
                unplaced.append({"entity": ent["id"], "name": name,
                                 "why": f"{len(found)} of the local checkouts know this commit id"})
                continue
        elif re.fullmatch(r"dip-\d+-\d+", name) and store.node(f"dipole:{name}"):
            target, evidence = f"dipole:{name}", "the name is the dipole's own id in ROOT_dipoles_pinned.xlsx"
        if target:
            merges.append({"from": ent["id"], "to": target, "alias": ent["attrs"]["name"], "evidence": evidence,
                           "confidence": 1.0, "method": "exact rule"})
    return merges, list(new_nodes.values()), unplaced


def apply_rules(store: GraphStore, dirs: dict[str, Path]) -> dict:
    by = code_stamp("tools.kgraph.resolve")
    merges, new_nodes, unplaced = rule_merges(store, dirs)
    edges = [link("RESOLVED_TO", m["from"], m["to"], alias=m["alias"], evidence=m["evidence"],
                  confidence=m["confidence"], method=m["method"], made_by=by) for m in merges]
    res = store.write(new_nodes, edges, written_by=by)
    res.update(merged=len(merges), matched_but_not_placed=unplaced)
    return res


# ---- the model's merges ------------------------------------------------------------------------
def _find(store: GraphStore, ref: str) -> str | None:
    """A merge names its ends by node id or by an Entity's name as written."""
    if store.node(ref):
        return ref
    want = clean(ref).lower()
    hits = [n["id"] for n in surface_forms(store) if clean(n["attrs"]["name"]).lower() == want]
    return hits[0] if len(hits) == 1 else None


def apply(store: GraphStore, merges: list[dict], run: str, min_confidence: float = 0.9) -> dict:
    """Write the resolver's merges. Each is checked; one that fails a check or falls under the cutoff
    is kept as a Task line with the reason. Returns what was applied, what was held under the cutoff
    and what could not be placed."""
    node = store.node(run)
    if node is None or node["type"] != "AgentRun":
        raise schema.Refused(f"{run} is not an AgentRun of the graph: record the run first")
    by = code_stamp("tools.kgraph.resolve")
    standing = {e["src"]: e for e in store.edges("RESOLVED_TO")}
    edges, tasks, out = [], [], {"applied": 0, "already_standing": 0, "under_the_cutoff": 0, "not_placed": []}
    planned = {s: e["dst"] for s, e in standing.items()}

    def hold(m: dict, why: str, state: str) -> None:
        tid = "task:merge-held:" + sha([m, why])
        tasks.append({"id": tid, "type": "Task", "attrs": {
            "text": f"A merge the resolver returned was not applied: {why}.", "state": state,
            "reason": why, "returned": m, "run": run}})
        edges.append(link("PRODUCED", run, tid))

    for m in merges:
        src, dst = _find(store, str(m.get("from", ""))), _find(store, str(m.get("to", "")))
        conf, evidence = m.get("confidence"), m.get("evidence")
        why = None
        if src is None or dst is None:
            why = "one of its ends is not a node of the graph (or the name fits more than one Entity)"
        elif store.node(src)["type"] != "Entity" or store.node(src)["attrs"].get("entity_kind") != SURFACE:
            why = "only a surface form (a name lifted from a document) is merged into something"
        elif store.node(dst)["type"] not in MERGE_TARGET_TYPES:
            why = f"a name is not merged into a {store.node(dst)['type']}"
        elif not isinstance(conf, (int, float)) or not 0 <= conf <= 1 or not evidence:
            why = "it has no evidence or no confidence between 0 and 1"
        elif src == dst:
            why = "both ends are the same node"
        if why:
            out["not_placed"].append({"merge": m, "why": why})
            hold(m, why, "blocked")
            continue
        if src in planned:
            if planned[src] == dst:
                out["already_standing"] += 1
            else:
                why = f"{src} is already merged into {planned[src]}: undo that merge first"
                out["not_placed"].append({"merge": m, "why": why})
                hold(m, why, "blocked")
            continue
        end, seen = dst, {src}
        while end in planned and end not in seen:      # the merge must not close a ring
            seen.add(end)
            end = planned[end]
        if end in seen:
            why = "it would close a ring of merges"
            out["not_placed"].append({"merge": m, "why": why})
            hold(m, why, "blocked")
            continue
        if conf < min_confidence:
            out["under_the_cutoff"] += 1
            hold(m, f"its confidence {conf} is under the cutoff {min_confidence}", "open")
            continue
        planned[src] = dst
        edges.append(link("RESOLVED_TO", src, dst, alias=store.node(src)["attrs"]["name"], evidence=evidence,
                          confidence=conf, method="model", made_by=run))
        edges.append(link("PRODUCED", run, src, key="merge"))
        out["applied"] += 1
    out["written"] = store.write(tasks, edges, written_by=by)
    return out


def undo(store: GraphStore, edge: str, reason: str, run: str) -> dict:
    """Take one merge back. The link's earlier line stays; the surface form stands on its own again."""
    last = (store.history(edge) or [None])[-1]
    if last is None or last["type"] != "RESOLVED_TO":
        raise schema.Refused(f"{edge} is not a merge of the graph")
    return store.withdraw_edge(edge, reason=f"{reason} (undone by {run})", written_by=code_stamp("tools.kgraph.resolve"))


# ---- a later claim set over an earlier one (nothing is replaced) --------------------------------
def _when(store: GraphStore, claim: dict, dirs: dict | None) -> tuple:
    """(the date the lines give or the file's name gives, the time of the commit it was read at)."""
    a = claim["attrs"]
    src = a.get("source") or ""
    m = re.search(r"(20\d{6})", src)
    day = a.get("said_on") or (f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else "")
    stamp = 0
    repo = src.split(":", 2)[1] if src.count(":") >= 2 else None
    if dirs and repo in dirs and a.get("source_commit"):
        try:
            stamp = int(git(dirs[repo], "log", "-1", "--format=%ct", a["source_commit"]))
        except (RuntimeError, ValueError):
            stamp = 0
    return (day, stamp)


def supersede(store: GraphStore, new_id: str, old_id: str, why: str, run: str, dirs: dict | None = None) -> str:
    """Set a later claim over an earlier one (a SUPERSEDES link). NOTHING IS REPLACED: the earlier claim
    stays in the graph and in reach; the session context marks it "a later claim says otherwise" and
    calls it last, and the grounding check says so. The link can be taken back like any other."""
    new, old = store.node(new_id), store.node(old_id)
    if not new or not old or new["type"] != "Claim" or old["type"] != "Claim":
        raise schema.Refused("both ends of a SUPERSEDES link are claims of the graph")
    if not why or not why.strip():
        raise schema.Refused("a SUPERSEDES link says why the later claim stands over the earlier one")
    maker = store.node(run)
    if not (run.startswith("code:") or (maker and maker["type"] == "AgentRun")):
        raise schema.Refused(f"{run} is not an AgentRun of the graph: record the run first")
    a, b = _when(store, new, dirs), _when(store, old, dirs)
    if a[0] and b[0] and a < b:
        raise schema.Refused(f"{new_id} was made earlier than {old_id} ({a[0]} against {b[0]}): only a later claim takes "
                             "the place of an earlier one")
    e = link("SUPERSEDES", new_id, old_id, why=why, made_by=run)
    store.write([], [e], written_by=run if run.startswith("run:") else code_stamp("tools.kgraph.resolve"))
    return e["id"]


# ---- the resolver's brief ----------------------------------------------------------------------
BRIEF = """You are the RESOLVER of DavisAI Markets (stage 4b of the graph adoption plan). Below is every name the
readers lifted from the documents that is not merged yet, one a line: `<id> | <name as written> | <how many
claims name it> | <one claim that names it>`. Some of these names mean the same thing (a file written with
and without its folder, a component under two spellings, a plural, a nickname the documents use for one
fixed thing). Find those. Do NOT merge two things that are only related (a stage and the code that builds
it; a plan and the program it plans; a rule and the strategy family it belongs to), and do not merge a
general word into a specific thing unless every claim that uses the word means that thing.

Return JSON only: {"merges": [{"from": "<id of the surface form>", "to": "<id of the entry it means>",
"evidence": "<why, in one sentence, citing what the claims say>", "confidence": <0 to 1>}]}
`to` is the id whose name is the clearest, fullest form. A name is merged into ONE entry. Leave a name out
when you are not sure: an unmerged name does no harm, a wrong merge does.
"""


def candidates(store: GraphStore) -> str:
    merged = {e["src"] for e in store.edges("RESOLVED_TO")}
    by_ent: dict[str, list[str]] = {}
    for e in store.edges("MENTIONS"):
        by_ent.setdefault(e["dst"], []).append(e["src"])
    rows = []
    for ent in sorted(surface_forms(store), key=lambda n: n["attrs"]["name"].lower()):
        if ent["id"] in merged:
            continue
        claims = by_ent.get(ent["id"], [])
        example = store.node(claims[0])["attrs"]["text"] if claims else ""
        rows.append(f"{ent['id']} | {ent['attrs']['name']} | {len(claims)} | {example[:160]}")
    return BRIEF + "\n" + "\n".join(rows) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--markets")
    ap.add_argument("--platform")
    ap.add_argument("--graph-dir")
    sub = ap.add_subparsers(dest="verb", required=True)
    sub.add_parser("rules")
    p = sub.add_parser("candidates")
    p.add_argument("--out", required=True)
    p = sub.add_parser("apply")
    p.add_argument("--merges", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--min-confidence", type=float, default=0.9)
    p = sub.add_parser("supersede")
    p.add_argument("--new", required=True)
    p.add_argument("--old", required=True)
    p.add_argument("--why", required=True)
    p.add_argument("--run", required=True)
    p = sub.add_parser("undo")
    p.add_argument("--edge", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--run", required=True)
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    dirs = repo_dirs(store.data_root, a.markets, a.platform)
    if a.verb == "rules":
        print(json.dumps(apply_rules(store, dirs), indent=1, ensure_ascii=False))
    elif a.verb == "candidates":
        text = candidates(store)
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"{a.out}: {len(text.splitlines())} lines")
    elif a.verb == "apply":
        raw = Path(a.merges).read_text(encoding="utf-8")
        merges = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])["merges"]
        print(json.dumps(apply(store, merges, a.run, a.min_confidence), indent=1, ensure_ascii=False))
    elif a.verb == "supersede":
        print(supersede(store, a.new, a.old, a.why, a.run, dirs))
    elif a.verb == "undo":
        print(json.dumps(undo(store, a.edge, a.reason, a.run)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
