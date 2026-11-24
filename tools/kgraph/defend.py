"""Tickets 02 and 03 of the 44: a claim is registered before its outcome is seen, and an independent
reviewer challenges it without the proposer's reasoning.

Greg, 2026-11-24: every claim has to be defended with the independent verifier (research/kalshi/
FRANKIE_INDEPENDENT_SCIENTIFIC_VERIFIER_PLAN.md: "the proposer of a claim must not be its sole verifier").
The Claim fields of the registration contract and the Evaluation fields of the check register are already in
tools/kgraph/schema.py; this module fills them. It adds no node type, no edge type and no schema field.

  python3 -m tools.kgraph.defend register --claim-file <claim.json> --run run:NNNN
  python3 -m tools.kgraph.defend challenge-brief --claim <claim id> --out <brief.md>
  python3 -m tools.kgraph.defend challenge --claim <claim id> --file <challenge.json> --run run:NNNN
  python3 -m tools.kgraph.defend show --claim <claim id>
  python3 -m tools.kgraph.defend undefended

Every command takes [--data <markets-data>] [--graph-dir <scratch graph>]. The real graph is written only
when --graph-dir is left out.

CLAIM FILE (JSON object). Required, each refused by name when missing or empty:
  claim_key        a short stable name the proposer gives the claim; the same key with a changed file is the
                   claim's next revision, the same file twice writes nothing
  hypothesis, exact_claim, scope, mechanism                      plain text
  alternatives     list of text, at least one (alternative explanations)
  falsifiers       list, at least one; each {"observation": ..., "record": ...} (what observation in which
                   record would count against the claim), written beforehand
  code_commit      git sha of the code the claim is about; artifact_path and artifact_sha256 (64 hex)
  outcome_visibility   plain statement of what outcome, if any, the proposer had seen
  inference        true or false; inference_reason (text) when true
  rests_on         list of grounds (see below); at least one when inference is false (the first "greg" one
                   becomes the claim's source)
Optional: boundaries, statement_kind (one of schema.STATEMENT_KINDS, default "state"), source_event_ids,
  data_manifest_hashes, event_time, knowledge_time.
Grounds: {"kind": "claim", "id": "<Claim id of the graph>"}
         {"kind": "rule", "rule_id": "CL01", "commit": "<sha in paper-trading-platform>"}  (the text of
              paper_platform/rules/<rule_id>.json at that commit)
         {"kind": "greg", "repo": "markets-data", "path": ..., "line_start": N, "line_end": M, "quote": ...}
              (the quote stands in those lines of the file in the checkout)

CHALLENGE FILE (JSON object). Required, each refused by name when missing or empty:
  alternatives     list of text, at least one competing explanation
  falsifiers       list of text or {"observation", "record"}, at least one
  distinguishing_observation   the exact observation that tells the claim and the competing explanation apart
  what_was_checked, what_was_observed, what_remains_open     text or list of text
  objections       list (every objection; may be empty)
No status, verdict, decision or result field may carry a verdict word.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from . import schema
from .extract import repo_dirs
from .sources import code_stamp, git, link
from .store import GraphStore, sha

REGISTRATION = "claim registration v1"
RUBRIC = ("independent challenge v1: a reviewer who was not given the proposer's reasoning gives at least one "
          "competing explanation, one falsifier and the observation that distinguishes them")
RULES_DIR = "paper_platform/rules"
VERDICT_WORDS = {
    "supported", "refuted", "proven", "proved", "pass", "passed", "passes", "fail", "failed", "fails",
    "confirmed", "rejected", "approved", "verified", "valid", "invalid", "true", "false", "correct",
    "incorrect", "inconclusive", "accepted", "holds", "falsified", "sound", "unsound", "ok",
}
STATUS_KEYS = ("status", "verdict", "decision", "result", "outcome", "grade", "conclusion", "finding")
_ws = re.compile(r"\s+")
_hex = re.compile(r"^[0-9a-f]{7,40}$")
_hex64 = re.compile(r"^[0-9a-f]{64}$")


def _norm(s: str) -> str:
    return _ws.sub(" ", s).strip()


def _text(d: dict, key: str, where: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v.strip():
        raise schema.Refused(f"{where}: {key} is missing or empty")
    return v.strip()


def _items(d: dict, key: str, where: str, *, shape: str = "text") -> list:
    v = d.get(key)
    if isinstance(v, str) and v.strip() and shape == "text":
        v = [v]
    if not isinstance(v, list) or not v:
        raise schema.Refused(f"{where}: {key} needs at least one entry")
    out = []
    for x in v:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
        elif isinstance(x, dict) and shape in ("text", "falsifier") and x.get("observation"):
            out.append(x)
        else:
            raise schema.Refused(f"{where}: {key} has an empty or malformed entry: {str(x)[:80]}")
    return out


def _load_json(path) -> dict:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise schema.Refused(f"{path}: not a readable JSON file ({e})") from e
    if not isinstance(d, dict):
        raise schema.Refused(f"{path}: the file is not a JSON object")
    return d


def _agent_run(store: GraphStore, run: str) -> None:
    n = store.node(run) if run else None
    if not (run and run.startswith("run:") and n and n["type"] == "AgentRun"):
        raise schema.Refused(f"run: {run!r} is not an AgentRun of the graph (record the run first)")


def _falsifiers(d: dict, where: str) -> list:
    out = []
    for f in _items(d, "falsifiers", where, shape="falsifier"):
        if isinstance(f, dict):
            if not (str(f.get("observation", "")).strip() and str(f.get("record", "")).strip()):
                raise schema.Refused(f"{where}: falsifiers entry needs both observation and record: {str(f)[:80]}")
            out.append({"observation": f["observation"].strip(), "record": f["record"].strip()})
        else:
            out.append({"observation": f, "record": ""} if where == "challenge" else _bad_falsifier(f, where))
    return out


def _bad_falsifier(f, where):
    raise schema.Refused(f"{where}: falsifiers entry must say what observation in which record: {str(f)[:80]}")


# ---- the grounds ------------------------------------------------------------------------------------
def _read_ground(store: GraphStore, dirs: dict, g: dict) -> dict:
    """Resolve one ground to its full text, or refuse naming rests_on. Read again every time."""
    where = "rests_on"
    if not isinstance(g, dict) or "kind" not in g:
        raise schema.Refused(f"{where}: a ground is an object with a kind (claim, rule or greg): {str(g)[:80]}")
    k = g["kind"]
    if k == "claim":
        c = store.node(str(g.get("id")))
        if not c or c["type"] != "Claim":
            raise schema.Refused(f"{where}: {g.get('id')!r} is not a Claim of the graph")
        a = c["attrs"]
        src = store.node(a["source"]) if a.get("source") else None
        return {"kind": k, "id": c["id"], "text": a.get("exact_claim") or a["text"], "source": a.get("source"),
                "path": src["attrs"]["path"] if src else None, "line_start": a.get("line_start"),
                "line_end": a.get("line_end"), "quote": a.get("quote"), "inference": a["inference"]}
    if k == "rule":
        plat = dirs.get("paper-trading-platform")
        rid, commit = str(g.get("rule_id", "")), str(g.get("commit", ""))
        if not rid or not _hex.match(commit) or plat is None:
            raise schema.Refused(f"{where}: a rule ground needs rule_id and commit, and a platform checkout")
        try:
            raw = git(plat, "show", f"{commit}:{RULES_DIR}/{rid}.json")
            spec = json.loads(raw)["specification"]
            full = git(plat, "rev-parse", commit)
        except (RuntimeError, ValueError, KeyError) as e:
            raise schema.Refused(f"{where}: no text of rule {rid} at commit {commit} in the platform checkout ({e})") from e
        return {"kind": k, "rule_id": rid, "commit": full, "text": spec, "path": f"{RULES_DIR}/{rid}.json"}
    if k == "greg":
        repo, path = str(g.get("repo", "")), str(g.get("path", ""))
        try:
            a, b, quote = int(g["line_start"]), int(g["line_end"]), str(g["quote"])
        except (KeyError, ValueError, TypeError) as e:
            raise schema.Refused(f"{where}: a greg ground needs repo, path, line_start, line_end, quote") from e
        p = dirs[repo] / path if repo in dirs else None
        if p is None or not p.is_file():
            raise schema.Refused(f"{where}: {repo}:{path} is not a file of a local checkout")
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if not quote.strip() or a < 1 or b < a or not _norm(quote) in _norm(" ".join(lines[a - 1:b])):
            raise schema.Refused(f"{where}: the quoted line does not stand in {path} lines {a}-{b}")
        return {"kind": k, "repo": repo, "path": path, "line_start": a, "line_end": b, "quote": quote,
                "text": "\n".join(lines[a - 1:b])}
    raise schema.Refused(f"{where}: unknown ground kind {k!r}")


# ---- register ----------------------------------------------------------------------------------------
def register(store: GraphStore, claim_file, run: str, dirs: dict | None = None) -> dict:
    d = _load_json(claim_file)
    dirs = dirs or repo_dirs(store.data_root, None, None)
    _agent_run(store, run)
    w = "claim file"
    key = _text(d, "claim_key", w)
    hypothesis, exact = _text(d, "hypothesis", w), _text(d, "exact_claim", w)
    scope, mechanism = _text(d, "scope", w), _text(d, "mechanism", w)
    alternatives = _items(d, "alternatives", w)
    falsifiers = _falsifiers(d, w)
    visibility = _text(d, "outcome_visibility", w)
    code_commit, art_path = _text(d, "code_commit", w), _text(d, "artifact_path", w)
    art_sha = _text(d, "artifact_sha256", w)
    if not _hex.match(code_commit):
        raise schema.Refused(f"{w}: code_commit is not a git sha")
    if not _hex64.match(art_sha):
        raise schema.Refused(f"{w}: artifact_sha256 is not a sha256")
    if not isinstance(d.get("inference"), bool):
        raise schema.Refused(f"{w}: inference must be true or false")
    if d["inference"]:
        reason = _text(d, "inference_reason", w)
    grounds = d.get("rests_on", [])
    if not isinstance(grounds, list):
        raise schema.Refused(f"{w}: rests_on is not a list")
    resolved = [_read_ground(store, dirs, g) for g in grounds]
    kind = d.get("statement_kind", "state")
    cid = "claim:reg-" + sha(key)
    attrs = {
        "text": exact, "statement_kind": kind, "inference": d["inference"], "registration": REGISTRATION,
        "claim_key": key, "proposer": str(d.get("proposer") or store.node(run)["attrs"].get("role")),
        "proposer_run": run, "hypothesis": hypothesis, "exact_claim": exact, "scope": scope,
        "boundaries": d.get("boundaries", ""), "mechanism": mechanism, "alternatives": alternatives,
        "falsifiers": falsifiers, "code_commit": code_commit, "artifact_path": art_path,
        "artifact_sha256": art_sha, "outcome_visibility": visibility,
        "rests_on": [{k: v for k, v in g.items() if k != "text"} if g["kind"] != "claim" else {"kind": "claim", "id": g["id"]}
                     for g in resolved],
    }
    for opt in ("source_event_ids", "data_manifest_hashes", "event_time", "knowledge_time"):
        if opt in d:
            attrs[opt] = d[opt]
    if d["inference"]:
        attrs["inference_reason"] = reason
    edges = [link("PRODUCED", run, cid)]
    if not d["inference"]:
        greg = next((g for g in resolved if g["kind"] == "greg"), None)
        src = f"src:{greg['repo']}:{greg['path']}" if greg else None
        if not src or not store.node(src):
            raise schema.Refused(f"{w}: rests_on: a claim that is not an inference needs a greg ground whose file "
                                 "is a Source of the graph")
        attrs.update(source=src, line_start=greg["line_start"], line_end=greg["line_end"], quote=greg["quote"])
        edges.append(link("SUPPORTS", src, cid))
    for g in resolved:
        if g["kind"] == "claim":
            edges.append(link("DEPENDS_ON", cid, g["id"]))
        elif g["kind"] == "rule":
            rv = store.node(f"rulever:{g['rule_id']}@{g['commit'][:10]}")
            if rv:
                edges.append(link("DEPENDS_ON", cid, rv["id"]))
        else:
            s = store.node(f"src:{g['repo']}:{g['path']}")
            if s and s["id"] != attrs.get("source"):
                edges.append(link("DEPENDS_ON", cid, s["id"]))
    res = store.write([{"id": cid, "type": "Claim", "attrs": attrs}], edges, written_by=run)
    res["claim"] = cid
    return res


# ---- the brief ---------------------------------------------------------------------------------------
def _registered(store: GraphStore, claim_id: str) -> dict:
    c = store.node(claim_id)
    if not c or c["type"] != "Claim" or c["attrs"].get("registration") != REGISTRATION:
        raise schema.Refused(f"claim: {claim_id!r} is not a claim registered with `defend register`")
    return c


def brief(store: GraphStore, claim_id: str, dirs: dict | None = None) -> str:
    c = _registered(store, claim_id)
    a = c["attrs"]
    dirs = dirs or repo_dirs(store.data_root, None, None)
    grounds = []
    for g in a["rests_on"]:
        g = dict(g)
        if g["kind"] == "rule":
            g["commit"] = g["commit"]
        grounds.append(_read_ground(store, dirs, g))
    out = [f"# Challenge brief for {claim_id} (revision {c['rev']})", "",
           "You are the independent reviewer. You were not given the proposer's reasoning and you are not to ask "
           "for it. Below are the claim, where it applies and the evidence admitted for it, in full.", "",
           "## The exact claim", "", a["exact_claim"], "", "## Scope and boundaries", "", f"Scope: {a['scope']}"]
    if a.get("boundaries"):
        out.append(f"Boundaries: {a['boundaries']}")
    out += ["", "## The artifact the claim is about", "", f"- path: {a['artifact_path']}",
            f"- code commit: {a['code_commit']}", f"- sha256: {a['artifact_sha256']}", "",
            "## The admissible evidence, in full", ""]
    if not grounds:
        out.append("(none: the claim names no ground)")
    for i, g in enumerate(grounds, 1):
        if g["kind"] == "claim":
            where = f"{g['path']} lines {g['line_start']}-{g['line_end']}" if g["path"] else "no source line (marked an inference)"
            out += [f"### {i}. Claim of the graph {g['id']} ({where})", "", g["text"]]
            if g.get("quote"):
                out += ["", f"Quoted from the file: {g['quote']}"]
        elif g["kind"] == "rule":
            out += [f"### {i}. Rule {g['rule_id']} at commit {g['commit']} ({g['path']})", "", g["text"]]
        else:
            out += [f"### {i}. Greg's words, {g['repo']}:{g['path']} lines {g['line_start']}-{g['line_end']}", "", g["text"]]
        out.append("")
    out += ["## What to hand back", "",
            "One JSON object, nothing else, with these fields:", "",
            "```json", json.dumps({
                "alternatives": ["at least one competing explanation of what the evidence shows"],
                "falsifiers": [{"observation": "at least one observation that would count against the claim",
                                "record": "in which record it would be looked for"}],
                "distinguishing_observation": "the exact observation that would tell the claim and the competing explanation apart",
                "what_was_checked": ["what you checked"],
                "what_was_observed": ["what you observed"],
                "what_remains_open": ["what remains open"],
                "objections": ["every objection you have, each its own entry"]}, indent=2), "```", "",
            "No verdict word and no pass or fail framing anywhere in it: say what was checked, what was observed "
            "and what remains open. Do not average, rank or score anything.", ""]
    return "\n".join(out)


# ---- challenge ---------------------------------------------------------------------------------------
def _no_verdict(d: dict) -> None:
    for k in STATUS_KEYS:
        if k in d:
            words = set(re.findall(r"[a-z]+", json.dumps(d[k]).lower())) & VERDICT_WORDS
            if words:
                raise schema.Refused(f"challenge file: {k} carries a verdict word ({', '.join(sorted(words))}); "
                                     "say what was checked, observed and open instead")


def challenge(store: GraphStore, claim_id: str, challenge_file, run: str) -> dict:
    c = _registered(store, claim_id)
    d = _load_json(challenge_file)
    _agent_run(store, run)
    _no_verdict(d)
    w = "challenge file"
    proposers = {l["attrs"].get("proposer_run") for l in store.history(claim_id)}
    if run in proposers:
        raise schema.Refused(f"run: {run} is the run that registered {claim_id}; the proposer must not be its sole verifier")
    alts = _items(d, "alternatives", w)
    fals = _falsifiers(d, "challenge")
    dist = _text(d, "distinguishing_observation", w)
    checked, observed = _items(d, "what_was_checked", w), _items(d, "what_was_observed", w)
    open_ = _items(d, "what_remains_open", w)
    if not isinstance(d.get("objections"), list):
        raise schema.Refused(f"{w}: objections is missing (a list; empty if there are none)")
    raw = Path(challenge_file).read_bytes()
    eid = "eval:" + sha([claim_id, c["rev"], RUBRIC, run, hashlib.sha256(raw).hexdigest()])
    a = c["attrs"]
    attrs = {
        "rubric": RUBRIC, "what_was_checked": checked, "what_was_observed": observed, "what_remains_open": open_,
        "check_type": "independent challenge", "method": "tools.kgraph.defend challenge",
        "method_version": code_stamp("tools.kgraph.defend"), "claim_revision": c["rev"],
        "input_hash": c["content_sha"], "location": "tools/kgraph/defend.py", "scope": a["scope"],
        "expected_observation": dist, "reproducibility": f"the challenge file, sha256 {hashlib.sha256(raw).hexdigest()}",
        "exceptions": d["objections"], "reviewer": run,
        "alternatives": alts, "falsifiers": fals, "distinguishing_observation": dist, "objections": d["objections"],
    }
    edges = [link("EVALUATES", eid, claim_id), link("PRODUCED", run, eid)]
    res = store.write([{"id": eid, "type": "Evaluation", "attrs": attrs}], edges, written_by=run)
    res["evaluation"] = eid
    return res


def challenges_of(store: GraphStore, claim_id: str) -> list[dict]:
    return [e for e in (store.node(x["src"]) for x in store.edges("EVALUATES") if x["dst"] == claim_id)
            if e and e["attrs"].get("rubric") == RUBRIC]


def show(store: GraphStore, claim_id: str) -> str:
    c = _registered(store, claim_id)
    a = c["attrs"]
    out = [f"{claim_id}  revision {c['rev']}  (registered by {a['proposer_run']})"]
    for k in ("proposer", "hypothesis", "exact_claim", "scope", "boundaries", "mechanism", "alternatives", "falsifiers",
              "code_commit", "artifact_path", "artifact_sha256", "outcome_visibility", "inference", "inference_reason",
              "source_event_ids", "data_manifest_hashes", "event_time", "knowledge_time"):
        if k in a:
            out.append(f"{k}: {json.dumps(a[k], ensure_ascii=False) if not isinstance(a[k], str) else a[k]}")
    out.append("rests on:")
    out += [f"  {json.dumps(g, ensure_ascii=False)}" for g in a["rests_on"]] or ["  nothing"]
    ch = challenges_of(store, claim_id)
    out.append("challenges on record:")
    for e in ch:
        ea = e["attrs"]
        out += [f"  {e['id']}  by {ea['reviewer']}  at claim revision {ea['claim_revision']}",
                f"    alternatives: {json.dumps(ea['alternatives'], ensure_ascii=False)}",
                f"    falsifiers: {json.dumps(ea['falsifiers'], ensure_ascii=False)}",
                f"    distinguishing observation: {ea['distinguishing_observation']}",
                f"    what was checked: {json.dumps(ea['what_was_checked'], ensure_ascii=False)}",
                f"    what was observed: {json.dumps(ea['what_was_observed'], ensure_ascii=False)}",
                f"    objections: {json.dumps(ea['objections'], ensure_ascii=False)}"]
    if not ch:
        out.append("  none")
    out.append("what remains open:")
    if not ch:
        out.append("  no independent challenge is on record")
    for e in ch:
        out += [f"  ({e['id']}) {x}" for x in e["attrs"]["what_remains_open"]]
        if e["attrs"]["claim_revision"] != c["rev"]:
            out.append(f"  ({e['id']}) it was made at revision {e['attrs']['claim_revision']}, not the current {c['rev']}")
    return "\n".join(out)


def undefended(store: GraphStore) -> list[str]:
    out = []
    for c in sorted(store.nodes("Claim"), key=lambda n: n["id"]):
        if c["attrs"].get("registration") != REGISTRATION:
            continue
        if not any(e["attrs"]["claim_revision"] == c["rev"] for e in challenges_of(store, c["id"])):
            out.append(f"{c['id']}  revision {c['rev']}  {c['attrs']['exact_claim'][:100]}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("verb", choices=("register", "challenge-brief", "challenge", "show", "undefended"))
    ap.add_argument("--claim-file")
    ap.add_argument("--claim")
    ap.add_argument("--file")
    ap.add_argument("--out")
    ap.add_argument("--run")
    ap.add_argument("--data")
    ap.add_argument("--graph-dir")
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    try:
        if a.verb == "register":
            print(json.dumps(register(store, a.claim_file, a.run)))
        elif a.verb == "challenge-brief":
            Path(a.out).write_text(brief(store, a.claim), encoding="utf-8")
            print(f"wrote {a.out}")
        elif a.verb == "challenge":
            print(json.dumps(challenge(store, a.claim, a.file, a.run)))
        elif a.verb == "show":
            print(show(store, a.claim))
        else:
            print("\n".join(undefended(store)))
    except schema.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
