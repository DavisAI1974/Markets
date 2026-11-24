"""Consolidation as a standing step of every read (ticket 46): find where a later claim stands over an earlier one.

Three verbs; none calls a model.
  brief   --read run:00NN --out FILE   the candidate pairs for the claims that read added, and ONLY those (not the
                                       whole graph again): each of its claims against every EARLIER claim that
                                       mentions an Entity it mentions and is not already under a later-over-earlier
                                       link with it. Every candidate is in the brief; none is cut for size or ranked.
  apply   --read run:00NN --pairs FILE --run run:00MM
                                       each pair of the reader's answer through resolve.supersede as it stands (its
                                       own link, its reason, its run); a pair supersede refuses is printed with the
                                       refusal and kept in the count; then ONE Task node says this read has been
                                       through the step. An empty answer is a real answer: the reader found none.
  status                               from the graph itself, for each read (each run some claim names in
                                       `extracted_by`): has it its Task, and how many claims it added.

Nothing is deleted; a link is taken back with `python3 -m tools.kgraph.resolve undo`. The date of a claim is
resolve._when's: `said_on`, else the 8-digit date in the source FILE's name (never its folder's). A pair on the same
date, and a pair with a claim that has no date, cannot be put in order by the date: each is listed in its own section, not cut
(supersede itself refuses only a later date set under an earlier one)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import resolve, schema
from .extract import repo_dirs
from .sources import code_stamp, link
from .store import GraphStore, sha

TASK_PREFIX = "task:consolidated:"

BRIEF = """You are the CONSOLIDATOR of DavisAI Markets (agent run {run}). {n_claims} claims were added to the graph by one read ({read}).
Below, each of those claims (the LATER side) is set against the EARLIER claims that mention the same thing. A new session
starting from the graph is misled when an old claim stands beside a later one with nothing to say which stands.

YOUR ONE JOB: find pairs where the LATER claim says something about the SAME subject that makes the EARLIER claim no longer
the state of things. Return them so the earlier one can be marked "a later claim says otherwise". Nothing is deleted: the
earlier claim stays on record, and every link can be taken back.

A pair qualifies ONLY when all of these hold:
1. Both claims are about the same subject (the same thing AND the same question about it: where it is, whether it is built,
   who decides it, what its value is, whether it needs a go).
2. They cannot both be the present state: the later one changes, settles, overturns or completes what the earlier one says.
   Examples: "X is not built" then later "X is built"; "the figure is not decided" then later "Greg decided the figure is Y";
   "the work is on branch A" then later "the work is on branch B"; "waits for Greg's go" then later "Greg gave his go"; an open
   question then later its answer.
3. The later claim's date is the same day or later. On the same day, the later one is the one from the later handoff (letters
   run U, V, W, X, Y, Z, AA) or, in ROOT_GAMEPLAN_DECISIONS.md, the higher line number. Where a claim shows "undated" no date
   says which is later: judge from the words and the file, and leave the pair out if you cannot tell.
NOT a pair: two claims that say the same thing (a restatement); two claims that are both true at once; a rule and a later use of
the rule; anything you are not sure about. When in doubt, leave it out: a wrong pair hides a true claim. An empty list is a real
answer: it says you read every pair and found none.

Return JSON only, no words around it: {{"pairs": [{{"new": "<claim id of the later claim>", "old": "<claim id of the earlier claim>", "why": "<one plain sentence: what the later claim says that the earlier one no longer holds>"}}, ...]}}
Use the claim ids exactly as printed (they start with claim:). Work through every pair to the last one.

Each claim line is: claim id | date | file:line | kind | said by | the claim.
A pair marked "order not settled by date: the reader says which is later, from the words" has two claims of this same read; it is listed ONCE. Say which of the two is later and return that one direction only: never both.
{n_pairs} pairs ({n_earlier} where the earlier claim has an earlier date, {n_same} where both have the same date, {n_undated} where a claim has no date, {n_order} listed once with the order not settled by date), {n_with} of the {n_claims} claims have at least one.
"""


def _mentions(store: GraphStore) -> dict:
    """claim -> the entries it mentions, each followed through the merges that stand (resolve's own rule)."""
    by, seen_to = resolve._standing_merges(store), {}

    def canon(x):
        if x not in seen_to:
            cur, seen = x, set()
            while cur in by and cur not in seen:
                seen.add(cur)
                cur = by[cur][0]["dst"]
            seen_to[x] = cur
        return seen_to[x]
    out: dict[str, set] = {}
    for e in store.edges("MENTIONS"):
        out.setdefault(e["src"], set()).add(canon(e["dst"]))
    return out


def reads_of(store: GraphStore) -> dict:
    """read run -> the ids of the claims whose `extracted_by` names it."""
    out: dict = {}
    for n in store.nodes("Claim"):
        out.setdefault(n["attrs"].get("extracted_by"), []).append(n["id"])
    return out


def candidates(store: GraphStore, read: str) -> tuple[list[str], list[tuple]]:
    """(the claims the read added, [(later id, earlier id, shared entity ids, "earlier" | "same" | "undated")])."""
    added = sorted(reads_of(store).get(read, []))
    ment = _mentions(store)
    linked = set()
    for e in store.edges("SUPERSEDES"):
        linked |= {(e["src"], e["dst"]), (e["dst"], e["src"])}
    day = {n["id"]: resolve._when(store, n, None)[0] for n in store.nodes("Claim")}
    by_entity: dict[str, list[str]] = {}
    for cid, ents in ment.items():
        for en in ents:
            by_entity.setdefault(en, []).append(cid)
    pairs = []
    for cid in added:
        shared: dict[str, set] = {}
        for en in ment.get(cid, ()):
            for other in by_entity.get(en, ()):
                if other != cid and other in day:
                    shared.setdefault(other, set()).add(en)
        for other in sorted(shared, key=lambda o: (day[o] or "~", o)):
            if (cid, other) in linked:
                continue
            if day[cid] and day[other]:
                if day[other] > day[cid]:
                    continue                                  # a claim dated later is not an earlier claim
                kind = "earlier" if day[other] < day[cid] else "same"
            else:
                kind = "undated"                              # no date says which is later: listed, not cut
            pairs.append((cid, other, sorted(shared[other]), kind))
    # Two claims of the SAME read that are candidates for each other are one pair, listed once (the lower id first): no date
    # says which is later, the reader does, from the words. A pair and its reverse are never both applied (resolve.supersede).
    have = {(p[0], p[1]) for p in pairs}
    once = []
    for p in pairs:
        if (p[1], p[0]) in have:
            if p[0] > p[1]:
                continue
            p = (p[0], p[1], p[2], "order")
        once.append(p)
    return added, once


def _line(store: GraphStore, cid: str) -> str:
    n = store.node(cid)
    a = n["attrs"]
    day = resolve._when(store, n, None)[0] or "undated"
    src = (a.get("source") or "").rsplit("/", 1)[-1]
    return (f"{cid} | {day} | {src}:{a.get('line_start', '?')} | {a.get('statement_kind', '-')} | "
            f"said by {a.get('said_by') or '-'} | {a.get('text', '')}")


def brief(store: GraphStore, read: str, run_hint: str = "") -> tuple[str, dict]:
    added, pairs = candidates(store, read)
    if not added:
        raise schema.Refused(f"no claim of the graph names {read} in extracted_by")
    n = {k: sum(1 for p in pairs if p[3] == k) for k in ("earlier", "same", "undated", "order")}
    stats = {"claims_added": len(added), "claims_with_a_candidate": len({p[0] for p in pairs}), "pairs": len(pairs), **n}
    text = BRIEF.format(run=run_hint or "run:????", read=read, n_claims=len(added), n_pairs=len(pairs), n_earlier=n["earlier"],
                        n_same=n["same"], n_undated=n["undated"], n_order=n["order"], n_with=stats["claims_with_a_candidate"])
    body = []
    for kind, title in (("earlier", "PAIRS WHERE THE EARLIER CLAIM HAS AN EARLIER DATE"),
                        ("same", "PAIRS WHERE BOTH CLAIMS HAVE THE SAME DATE (the later handoff letter, or the higher line of the decisions file, is the later)"),
                        ("undated", "PAIRS WHERE A CLAIM HAS NO DATE"),
                        ("order", "PAIRS OF TWO CLAIMS OF THIS READ, ORDER NOT SETTLED BY DATE (listed once: the reader says which is later, from the words)")):
        body.append(f"\n## {title}\n")
        for i, (new, old, ents, _) in enumerate(p for p in pairs if p[3] == kind):
            names = "; ".join(f"{store.node(e)['attrs'].get('name', e)} [{e}]" for e in ents)
            if kind == "order":
                body.append(f"### pair {i + 1}\norder not settled by date: the reader says which is later, from the words\n"
                            f"one: {_line(store, new)}\nother: {_line(store, old)}\nshared: {names}\n")
            else:
                body.append(f"### pair {i + 1}\nlater: {_line(store, new)}\nearlier: {_line(store, old)}\nshared: {names}\n")
    return text + "\n".join(body), stats


def task_id(read: str) -> str:
    return TASK_PREFIX + sha([read])


def apply(store: GraphStore, read: str, pairs: list, run: str, dirs: dict | None = None) -> dict:
    added, cands = candidates(store, read)       # counted BEFORE anything is applied
    if not added:
        raise schema.Refused(f"no claim of the graph names {read} in extracted_by")
    maker = store.node(run)
    if not (run.startswith("code:") or (maker and maker["type"] == "AgentRun")):
        raise schema.Refused(f"{run} is not an AgentRun of the graph: record the run first")
    tid = task_id(read)
    if store.node(tid):
        raise schema.Refused(f"{read} has already been through the step ({tid}); take a link back with "
                             "`resolve undo` rather than applying a second answer")
    applied, refused = [], []
    own = set(added)
    for p in pairs:
        try:
            if not isinstance(p, dict) or p.get("new") not in own:
                made_by = (store.node(p.get("new")) or {}).get("attrs", {}).get("extracted_by") if isinstance(p, dict) else None
                raise schema.Refused(f"the later claim {p.get('new') if isinstance(p, dict) else p!r} is not one of the claims of {read} "
                                     f"(its extracted_by is {made_by}): apply takes only the pairs whose later claim the read added")
            applied.append({"new": p["new"], "old": p["old"], "edge": resolve.supersede(store, p["new"], p["old"], p.get("why", ""), run, dirs)})
        except (schema.Refused, KeyError, TypeError) as e:
            refused.append({"new": p.get("new") if isinstance(p, dict) else None, "old": p.get("old") if isinstance(p, dict) else None,
                            "refusal": str(e)})
    task = {"id": tid, "type": "Task", "attrs": {
        "text": (f"The claims of {read} have been through the consolidation step: {len(cands)} candidate pairs in its brief, "
                 f"{len(applied)} pairs applied, {len(refused)} refused, applied by {run}."),
        "state": "done", "read": read, "applied_by": run, "claims": len(added), "candidate_pairs": len(cands),
        "pairs_applied": len(applied), "pairs_refused": len(refused), "refused": refused}}
    edges = [link("PRODUCED", run, tid)] if run.startswith("run:") else []
    store.write([task], edges, written_by=run if run.startswith("run:") else code_stamp("tools.kgraph.consolidate"))
    return {"read": read, "run": run, "candidate_pairs": len(cands), "applied": [a["edge"] for a in applied],
            "applied_pairs": applied, "refused": refused, "task": tid}


def status(store: GraphStore) -> tuple[list[str], dict]:
    done = {n["attrs"].get("read"): n["id"] for n in store.nodes("Task") if n["id"].startswith(TASK_PREFIX)}
    by = reads_of(store)
    lines, through, nread = [], 0, 0
    for read in sorted(by, key=lambda r: (r is None, r or "")):
        ok = read in done
        through += len(by[read]) if ok else 0
        nread += 0 if ok else 1
        lines.append(f"{read} | claims={len(by[read])} | {'through the step' if ok else 'not yet'} | task={done.get(read, 'none')}")
    total = sum(len(v) for v in by.values())
    lines.append(f"COUNTS claims={total} through_the_step={through} not_yet={total - through} reads={len(by)} reads_not_yet={nread}")
    return lines, {"claims": total, "through_the_step": through}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--markets")
    ap.add_argument("--platform")
    ap.add_argument("--graph-dir")
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("brief")
    p.add_argument("--read", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("apply")
    p.add_argument("--read", required=True)
    p.add_argument("--pairs", required=True)
    p.add_argument("--run", required=True)
    sub.add_parser("status")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    if a.verb == "brief":
        text, st = brief(store, a.read)
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"{a.out}: {len(text.splitlines())} lines")
        print(f"{a.read}: claims_added={st['claims_added']} claims_with_a_candidate={st['claims_with_a_candidate']} "
              f"pairs={st['pairs']} (earlier_date={st['earlier']} same_date={st['same']} undated={st['undated']} order_not_settled={st['order']})")
    elif a.verb == "apply":
        raw = Path(a.pairs).read_text(encoding="utf-8")
        pairs = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])["pairs"]
        dirs = repo_dirs(store.data_root, a.markets, a.platform)
        print(json.dumps(apply(store, a.read, pairs, a.run, dirs), indent=1, ensure_ascii=False))
    else:
        print("\n".join(status(store)[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
