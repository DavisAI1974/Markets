"""Tickets 02 and 03 of the 44: a claim is registered before its outcome is seen, and an independent
reviewer challenges it without the proposer's reasoning.

Greg, 2026-11-24: every claim has to be defended with the independent verifier (research/kalshi/
FRANKIE_INDEPENDENT_SCIENTIFIC_VERIFIER_PLAN.md: "the proposer of a claim must not be its sole verifier").
The Claim fields of the registration contract and the Evaluation fields of the check register are already in
tools/kgraph/schema.py; this module fills them. It adds no node type, no edge type and no schema field.

  python3 -m tools.kgraph.defend register --claim-file <claim.json> --run run:NNNN
  python3 -m tools.kgraph.defend challenge-brief --claim <claim id> --out <brief.md>
  python3 -m tools.kgraph.defend challenge --claim <claim id> --file <challenge.json> --brief <brief.md> --run run:NNNN
  python3 -m tools.kgraph.defend show --claim <claim id>      (the proposer's side: never given to the reviewer)
  python3 -m tools.kgraph.defend undefended

Every command takes [--data <markets-data>] [--graph-dir <scratch graph>]. The real graph is written only
when --graph-dir is left out.

CLAIM FILE (JSON object). Every key is checked; an unknown key is refused by name, never dropped. The whole
file is kept on the claim (attr claim_file) beside the fields lifted out of it.
  claim_key        stable name; same key + changed file = the claim's next revision, same file = nothing new.
                   Only the run that first registered the claim may revise it.
  hypothesis, exact_claim, scope, mechanism                      plain text
  alternatives     list of text, at least one
  falsifiers       list, at least one, each {"observation", "record"}, written beforehand
  artifact_repo    Markets | markets-data | paper-trading-platform; artifact_path; code_commit; artifact_sha256.
                   The commit is resolved in that repository's checkout and the sha256 is compared with the file
                   at that commit; a commit that does not exist or a differing hash is refused naming both.
  data_manifest_hashes   a list of {"what", "sha256"} or {"none": "<why no data bears on this claim yet>"}
  outcome_visibility     {"outcome_seen": true|false, "what": "<what the proposer had seen of any outcome>"};
                   true is kept and said ("registered after an outcome was seen: ..."), never refused
  inference        true or false; inference_reason when true. A claim that rests on a rule's text or a cited
                   line has a source and is not an inference unless it says so.
  rests_on         list of grounds:
                   {"kind":"claim","id":<Claim of the graph>}                      -> DERIVED_FROM
                   {"kind":"rule","rule_id","commit","quote"}  the rule file paper_platform/rules/<id>.json
                        at that commit (a Source node is made or found) and words of it  -> SUPPORTS
                   {"kind":"cited","repo","path","line_start","line_end","quote","said_by"}  a quoted line of
                        a named file (said_by stored; the file's sha256 and the commit it was read at are
                        stored; a Source node is made or found)                    -> SUPPORTS
                   A quote is at least six whole words in a row on those lines (extract.check_claim /
                   locate_quote). A claim that is not an inference needs a rule or cited ground; the first
                   is its source, quote and lines.
Optional: boundaries, statement_kind, proposer, source_event_ids, event_time, knowledge_time,
  reasoning_files (companion files the reviewer must not open before its challenge is written).
When register refuses it writes a Task node (not a Claim) holding the file, the reason, the run and the time.

CHALLENGE FILE (JSON object), with --brief (the brief file the reviewer was given). The code builds the brief of the
claim at its current revision itself and refuses unless the bytes of that file hash the same; the sha256 is stored:
  alternatives (at least one), falsifiers (at least one), distinguishing_observation, what_was_checked,
  what_was_observed, what_remains_open, objections (list, may be empty), saw_proposer_reasoning (true|false),
  what_i_opened (list). The whole file is kept on the Evaluation.

Independence, as far as code can hold it: the reviewer run is an AgentRun whose role is exactly "reviewer" (trimmed,
lower-cased), is not the run that registered any revision, and is not the extracted_by, proposer_run or proposer of
any ground claim, the grounds of those grounds and so on over DERIVED_FROM. What code CANNOT
see: the same agent under two run numbers; the main session writing both files; whether the reviewer opened
what it was told not to (it says so in the file, stored as given).

Verdict words: every stored free-text field of a claim and of a challenge is checked. Refused: the verifier plan's
own six labels (SUPPORTED_WITHIN_SCOPE, REFUTED_WITH_EVIDENCE, INCONCLUSIVE, NEEDS_MORE_EVIDENCE,
BLOCKED_INPUT_SCOPE, SUPERSEDED_RETAINED) anywhere, as whole words, in any letter case, with underscores or spaces;
and a field whose WHOLE value is one plain form (verdict, passed, failed, pass, fail, pass/fail, proven, disproven,
approved, rejected). An ordinary sentence or a file name that holds a plain word ("orders rejected by the exchange
appear", "out/verdict.json") is accepted. A quoted line (key "quote") is a file's words, not the writer's, and is
not checked.
Not settled here: a REVISES edge on a revision, a CONTRADICTS edge from an objection (plan 4a-bis; goes to Greg).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import sys
from pathlib import Path

import subprocess

from . import schema
from .extract import MIN_QUOTE_WORDS, check_claim as quote_check, repo_dirs
from .sources import REPOS, code_stamp, git, link, source_id, source_node
from .store import GraphStore, now, sha

REGISTRATION = "claim registration v1"
RUBRIC = ("independent challenge v1: a reviewer who was not given the proposer's reasoning gives at least one "
          "competing explanation, one falsifier and the observation that distinguishes them")
RULES_DIR = "paper_platform/rules"
ARTIFACT_REPOS = ("Markets", "markets-data", "paper-trading-platform")
LABELS = ("SUPPORTED_WITHIN_SCOPE", "REFUTED_WITH_EVIDENCE", "INCONCLUSIVE", "NEEDS_MORE_EVIDENCE",
          "BLOCKED_INPUT_SCOPE", "SUPERSEDED_RETAINED")
PLAIN_FORMS = ("verdict", "passed", "failed", "pass", "fail", "pass/fail", "proven", "disproven", "approved", "rejected")
_label_re = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(x).replace("_", "[_ ]") for x in LABELS)
                       + r")(?![A-Za-z0-9_])", re.I)
CLAIM_KEYS = {
    "claim_key", "hypothesis", "exact_claim", "scope", "mechanism", "alternatives", "falsifiers", "artifact_repo",
    "artifact_path", "code_commit", "artifact_sha256", "data_manifest_hashes", "outcome_visibility", "inference",
    "inference_reason", "rests_on", "boundaries", "statement_kind", "proposer", "source_event_ids", "event_time",
    "knowledge_time", "reasoning_files"}
CHALLENGE_KEYS = {"alternatives", "falsifiers", "distinguishing_observation", "what_was_checked", "what_was_observed",
                  "what_remains_open", "objections", "saw_proposer_reasoning", "what_i_opened"}
_hex = re.compile(r"^[0-9a-f]{7,40}$")
_hex64 = re.compile(r"^[0-9a-f]{64}$")


def _text(d: dict, key: str, where: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v.strip():
        raise schema.Refused(f"{where}: {key} is missing or empty")
    return v.strip()


def _list_of_text(d: dict, key: str, where: str, *, at_least_one=True) -> list:
    v = d.get(key)
    if isinstance(v, str) and v.strip():
        v = [v]
    if not isinstance(v, list) or (at_least_one and not v):
        raise schema.Refused(f"{where}: {key} needs at least one entry")
    if not all(isinstance(x, str) and x.strip() for x in v):
        raise schema.Refused(f"{where}: {key} has an entry that is not text")
    return [x.strip() for x in v]


def _falsifiers(d: dict, where: str) -> list:
    v = d.get("falsifiers")
    if not isinstance(v, list) or not v:
        raise schema.Refused(f"{where}: falsifiers needs at least one entry")
    out = []
    for f in v:
        if not (isinstance(f, dict) and str(f.get("observation", "")).strip() and str(f.get("record", "")).strip()):
            raise schema.Refused(f"{where}: falsifiers entry needs both observation (what) and record (in which record): {str(f)[:80]}")
        out.append({"observation": f["observation"].strip(), "record": f["record"].strip()})
    return out


def _load_json(path) -> dict:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise schema.Refused(f"{path}: not a readable JSON file ({e})") from e
    if not isinstance(d, dict):
        raise schema.Refused(f"{path}: the file is not a JSON object")
    return d


def _unknown(d: dict, allowed: set, where: str) -> None:
    extra = sorted(set(d) - allowed)
    if extra:
        raise schema.Refused(f"{where}: unknown key {', '.join(extra)} (it is refused, not dropped)")


def _labels(obj, where: str, path: str = "") -> None:
    """Refuse a verifier-plan label (or its plain form) as a whole word in any stored free text."""
    if isinstance(obj, str):
        m = _label_re.search(obj)
        word = m.group(1) if m else (obj.strip() if obj.strip().lower() in PLAIN_FORMS else None)
        if word:
            raise schema.Refused(f"{where}: {path or 'text'} carries the word {word!r}; say what was checked, "
                                 "observed and open instead")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k != "quote":
                _labels(v, where, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _labels(v, where, f"{path}[{i}]")


def _agent_run(store: GraphStore, run: str) -> dict:
    n = store.node(run) if run else None
    if not (run and run.startswith("run:") and n and n["type"] == "AgentRun"):
        raise schema.Refused(f"run: {run!r} is not an AgentRun of the graph (record the run first)")
    return n


def _blob(repo_dir, commit: str, path: str) -> bytes:
    r = subprocess.run(["git", "-C", str(repo_dir), "show", f"{commit}:{path}"], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"{path} is not in {repo_dir} at {commit}")
    return r.stdout


def _source_at(store: GraphStore, dirs: dict, repo: str, path: str, commit: str, raw: bytes) -> tuple[str, dict | None]:
    """The Source node of repo:path as it stood at `commit`: the graph's own node when its sha256 matches,
    else the checkout's current node when that is the same bytes, else a node for that commit alone."""
    h = hashlib.sha256(raw).hexdigest()
    std = source_id(repo, path)
    n = store.node(std)
    if n and n["attrs"].get("sha256") == h:
        return std, None
    try:
        wn = source_node(repo, dirs[repo], path)
        if wn["attrs"]["sha256"] == h:
            return std, wn
    except (RuntimeError, OSError, KeyError):
        pass
    attrs = {"kind": "file", "repo": REPOS.get(repo, repo), "path": path, "commit": commit, "bytes": len(raw), "sha256": h,
             "lines": raw.count(b"\n")}
    return source_id(repo, path, commit[:10]), {"id": source_id(repo, path, commit[:10]), "type": "Source", "attrs": attrs}


def _lines(raw: bytes) -> list[str]:
    return raw.decode("utf-8", errors="replace").splitlines()


def _check_quote(quote: str, lines: list[str], a: int, b: int, where: str) -> None:
    why = quote_check({"line_start": a, "line_end": b, "quote": quote, "text": "x", "statement_kind": "state",
                       "inference": False}, lines, 1, len(lines))
    if why:
        raise schema.Refused(f"{where}: {why}")


def _ground(store: GraphStore, dirs: dict, g, i: int) -> dict:
    """Resolve one ground, or refuse naming rests_on[i]."""
    where = f"rests_on[{i}]"
    if not isinstance(g, dict) or "kind" not in g:
        raise schema.Refused(f"{where}: a ground is an object with a kind (claim, rule or cited): {str(g)[:80]}")
    k = g["kind"]
    if k == "claim":
        c = store.node(str(g.get("id")))
        if not c or c["type"] != "Claim":
            raise schema.Refused(f"{where}: {g.get('id')!r} is not a Claim of the graph")
        return {"kind": k, "id": c["id"]}
    if k == "rule":
        plat, rid, commit = dirs.get("paper-trading-platform"), str(g.get("rule_id", "")), str(g.get("commit", ""))
        if not rid or not _hex.match(commit) or plat is None:
            raise schema.Refused(f"{where}: a rule ground needs rule_id, a commit sha and a platform checkout")
        path = f"{RULES_DIR}/{rid}.json"
        try:
            full = git(plat, "rev-parse", "--verify", commit + "^{commit}")
            raw = _blob(plat, full, path)
            json.loads(raw)["specification"]
        except (RuntimeError, ValueError, KeyError) as e:
            raise schema.Refused(f"{where}: rule {rid} has no text at commit {commit} in the platform checkout ({e})") from e
        lines, quote = _lines(raw), str(g.get("quote", ""))
        a, b = _span(quote, lines, where)
        sid, node = _source_at(store, dirs, "paper-trading-platform", path, full, raw)
        return {"kind": k, "rule_id": rid, "commit": full, "path": path, "line_start": a, "line_end": b, "quote": quote,
                "sha256": hashlib.sha256(raw).hexdigest(), "source": sid, "_node": node}
    if k == "cited":
        repo, path, said = str(g.get("repo", "")), str(g.get("path", "")), str(g.get("said_by", "")).strip()
        try:
            a, b, quote = int(g["line_start"]), int(g["line_end"]), str(g["quote"])
        except (KeyError, ValueError, TypeError) as e:
            raise schema.Refused(f"{where}: a cited ground needs repo, path, line_start, line_end, quote") from e
        if not said:
            raise schema.Refused(f"{where}: said_by is missing (who said the quoted words)")
        if repo not in dirs or not (dirs[repo] / path).is_file():
            raise schema.Refused(f"{where}: {repo}:{path} is not a file of a local checkout")
        try:
            commit = git(dirs[repo], "log", "-1", "--format=%H", "--", path)
            raw = _blob(dirs[repo], commit, path)
        except RuntimeError as e:
            raise schema.Refused(f"{where}: {path} is not committed in {repo} ({e})") from e
        _check_quote(quote, _lines(raw), a, b, where)
        named = said.lower() in "\n".join(_lines(raw)[a - 1:b]).lower()
        sid, node = _source_at(store, dirs, repo, path, commit, raw)
        return {"kind": k, "repo": repo, "path": path, "line_start": a, "line_end": b, "quote": quote, "said_by": said,
                "said_by_named_in_lines": named,
                "commit": commit, "sha256": hashlib.sha256(raw).hexdigest(), "source": sid, "_node": node}
    raise schema.Refused(f"{where}: unknown ground kind {k!r} (claim, rule or cited)")


def _span(quote: str, lines: list[str], where: str) -> tuple[int, int]:
    from .extract import locate_quote
    _check_quote(quote, lines, 1, len(lines), where)
    return locate_quote(quote, lines, 1, len(lines))


def _verify_artifact(dirs: dict, repo: str, commit: str, path: str, want: str) -> str:
    if repo not in ARTIFACT_REPOS or repo not in dirs:
        raise schema.Refused(f"artifact_repo: {repo!r} is not one of {ARTIFACT_REPOS} with a local checkout")
    try:
        full = git(dirs[repo], "rev-parse", "--verify", commit + "^{commit}")
    except RuntimeError:
        raise schema.Refused(f"code_commit: {commit} does not exist in the {repo} checkout") from None
    try:
        got = hashlib.sha256(_blob(dirs[repo], full, path)).hexdigest()
    except RuntimeError:
        raise schema.Refused(f"artifact_path: {path} is not in {repo} at {full}") from None
    if got != want:
        raise schema.Refused(f"artifact_sha256: the claim says {want}, the file {path} at {full} hashes to {got}")
    return full


def _outcome(d: dict) -> dict:
    v = d.get("outcome_visibility")
    if (not isinstance(v, dict) or not isinstance(v.get("outcome_seen"), bool)
            or not isinstance(v.get("what"), str) or not v["what"].strip() or set(v) - {"outcome_seen", "what"}):
        raise schema.Refused('claim file: outcome_visibility must be {"outcome_seen": true|false, "what": "<text>"}')
    return {"outcome_seen": v["outcome_seen"], "what": v["what"].strip()}


def _manifest(d: dict, dirs: dict) -> list:
    """Each item names a file at a commit in one of the checkouts; the sha256 is compared with that file, as the artifact is."""
    v = d.get("data_manifest_hashes")
    if isinstance(v, dict) and set(v) == {"none"} and isinstance(v["none"], str) and v["none"].strip():
        return [v]
    keys = {"what", "sha256", "repo", "path", "commit"}
    if not (isinstance(v, list) and v and all(isinstance(x, dict) and set(x) == keys and all(
            isinstance(x[k], str) and x[k].strip() for k in keys) and _hex64.match(x["sha256"]) for x in v)):
        raise schema.Refused('claim file: data_manifest_hashes must be a list of {"what","sha256","repo","path","commit"} '
                             'or {"none": "<why>"}')
    for i, x in enumerate(v):
        where = f"data_manifest_hashes[{i}]"
        if x["repo"] not in dirs:
            raise schema.Refused(f"{where}: repo {x['repo']!r} has no local checkout")
        try:
            full = git(dirs[x["repo"]], "rev-parse", "--verify", x["commit"] + "^{commit}")
        except RuntimeError:
            raise schema.Refused(f"{where}: commit {x['commit']} does not exist in the {x['repo']} checkout") from None
        try:
            got = hashlib.sha256(_blob(dirs[x["repo"]], full, x["path"])).hexdigest()
        except RuntimeError:
            raise schema.Refused(f"{where}: path {x['path']} is not in {x['repo']} at {full}") from None
        if got != x["sha256"]:
            raise schema.Refused(f"{where}: the claim says {x['sha256']}, the file {x['path']} at {full} hashes to {got}")
    return v


# ---- register ----------------------------------------------------------------------------------------
def register(store: GraphStore, claim_file, run: str, dirs: dict | None = None) -> dict:
    try:
        return _register(store, claim_file, run, dirs or repo_dirs(store.data_root, None, None))
    except schema.Refused as e:
        _retain(store, claim_file, run, str(e))
        raise


def _retain(store: GraphStore, claim_file, run: str, reason: str) -> None:
    """A refused registration is kept as a Task (never a Claim): never a silent exclusion."""
    try:
        raw = Path(claim_file).read_text(encoding="utf-8", errors="replace")
        try:
            content = json.loads(raw)
        except json.JSONDecodeError:
            content = raw
    except OSError:
        content = "(the file could not be read)"
    stamp = now()
    tid = "task:defend-refused-" + sha([str(run), content, reason, stamp])
    attrs = {"text": f"not admissible for a check: {reason}; retained", "state": "blocked", "claim_file": content,
             "reason": reason, "run": str(run), "refused_at": stamp}
    ok = store.node(run) and store.node(run)["type"] == "AgentRun" if run else False
    try:
        store.write([{"id": tid, "type": "Task", "attrs": attrs}], [],
                    written_by=run if ok else code_stamp("tools.kgraph.defend"))
    except Exception:
        pass


def _register(store: GraphStore, claim_file, run: str, dirs: dict) -> dict:
    d = _load_json(claim_file)
    _agent_run(store, run)
    w = "claim file"
    _unknown(d, CLAIM_KEYS, w)
    key = _text(d, "claim_key", w)
    hypothesis, exact = _text(d, "hypothesis", w), _text(d, "exact_claim", w)
    scope, mechanism = _text(d, "scope", w), _text(d, "mechanism", w)
    alternatives, falsifiers = _list_of_text(d, "alternatives", w), _falsifiers(d, w)
    visibility, manifest = _outcome(d), _manifest(d, dirs)
    code_commit, art_path = _text(d, "code_commit", w), _text(d, "artifact_path", w)
    art_repo, art_sha = _text(d, "artifact_repo", w), _text(d, "artifact_sha256", w)
    if not _hex.match(code_commit):
        raise schema.Refused(f"{w}: code_commit is not a git sha")
    if not _hex64.match(art_sha):
        raise schema.Refused(f"{w}: artifact_sha256 is not a sha256")
    if not isinstance(d.get("inference"), bool):
        raise schema.Refused(f"{w}: inference must be true or false")
    reason = _text(d, "inference_reason", w) if d["inference"] else None
    opt = {}
    for k_, t in (("boundaries", str), ("proposer", str), ("event_time", str), ("knowledge_time", str)):
        if k_ in d:
            if not isinstance(d[k_], t) or not d[k_].strip():
                raise schema.Refused(f"{w}: {k_} must be non-empty text")
            opt[k_] = d[k_].strip()
    for k_ in ("source_event_ids", "reasoning_files"):
        if k_ in d:
            opt[k_] = _list_of_text(d, k_, w)
    if "reasoning_files" in opt and posixpath.normpath(art_path) in {posixpath.normpath(x) for x in opt["reasoning_files"]}:
        raise schema.Refused(f"{w}: reasoning_files lists the artifact {art_path}; the artifact is printed in full in "
                             "the brief as the thing claimed about, so it cannot also be the proposer's reasoning")
    kind = d.get("statement_kind", "state")
    if kind not in schema.STATEMENT_KINDS:
        raise schema.Refused(f"{w}: statement_kind {kind!r} is not one of {schema.STATEMENT_KINDS}")
    if not isinstance(d.get("rests_on", []), list):
        raise schema.Refused(f"{w}: rests_on is not a list")
    _labels({k_: v for k_, v in d.items() if k_ not in ("claim_key",)}, w)
    full_commit = _verify_artifact(dirs, art_repo, code_commit, art_path, art_sha)
    grounds = [_ground(store, dirs, g, i) for i, g in enumerate(d.get("rests_on", []))]
    if d["inference"] and not grounds:
        raise schema.Refused(f"{w}: rests_on: an inference names what it is inferred from; rests_on is empty")
    cid = "claim:reg-" + sha(key)
    prev = store.history(cid)
    if prev and prev[0]["attrs"].get("proposer_run") != run:
        raise schema.Refused(f"run: {run} did not register {cid}; only {prev[0]['attrs'].get('proposer_run')} may revise it")
    sources = [g for g in grounds if g["kind"] in ("rule", "cited")]
    attrs = {
        "text": exact, "statement_kind": kind, "inference": d["inference"], "registration": REGISTRATION,
        "claim_key": key, "proposer": opt.pop("proposer", None) or store.node(run)["attrs"].get("role"),
        "proposer_run": run, "hypothesis": hypothesis, "exact_claim": exact, "scope": scope, "mechanism": mechanism,
        "alternatives": alternatives, "falsifiers": falsifiers, "code_commit": full_commit, "artifact_repo": art_repo,
        "artifact_path": art_path, "artifact_sha256": art_sha, "outcome_visibility": visibility,
        "data_manifest_hashes": manifest, "claim_file": d,
        "rests_on": [{k_: v for k_, v in g.items() if k_ != "_node"} for g in grounds],
    }
    attrs.update(opt)
    if prev and prev[-1]["attrs"].get("claim_file") == d:      # the same file again: nothing new, so the flag is carried
        if "falsifiers_changed_from_revision" in prev[-1]["attrs"]:
            attrs["falsifiers_changed_from_revision"] = prev[-1]["attrs"]["falsifiers_changed_from_revision"]
    elif prev and prev[-1]["attrs"]["falsifiers"] != falsifiers:
        attrs["falsifiers_changed_from_revision"] = prev[-1]["rev"]
    if reason:
        attrs["inference_reason"] = reason
    nodes, edges = [], [link("PRODUCED", run, cid)]
    for g in grounds:
        if g["kind"] == "claim":
            edges.append(link("DERIVED_FROM", cid, g["id"]))
        elif g.get("_node") is not None and not any(n["id"] == g["_node"]["id"] for n in nodes):
            nodes.append(g["_node"])
        if g["kind"] != "claim":
            edges.append(link("SUPPORTS", g["source"], cid))
    if not d["inference"]:
        if not sources:
            raise schema.Refused(f"{w}: rests_on: a claim that is not an inference rests on a rule's text or a cited "
                                 "line (its source); none is given")
        s0 = sources[0]
        attrs.update(source=s0["source"], line_start=s0["line_start"], line_end=s0["line_end"], quote=s0["quote"])
    nodes.append({"id": cid, "type": "Claim", "attrs": attrs})
    res = store.write(nodes, edges, written_by=run)
    new_ids = {e["id"] for e in edges}
    res["withdrawn"] = []
    # only the links an earlier revision's registration of THIS claim wrote (its grounds, written by the proposer's run);
    # a link another run wrote into the claim is left standing
    wrote = set()
    for l in prev:
        for g in l["attrs"].get("rests_on", []):
            wrote.add(link("DERIVED_FROM", cid, g["id"])["id"] if g["kind"] == "claim"
                      else link("SUPPORTS", g["source"], cid)["id"])
    for e in store.edges():
        mine = ((e["type"] == "DERIVED_FROM" and e["src"] == cid) or (e["type"] == "SUPPORTS" and e["dst"] == cid)) \
            and e["id"] in wrote and store.history(e["id"])[0]["written_by"] == run
        if mine and e["id"] not in new_ids:
            store.withdraw_edge(e["id"], reason=f"a ground dropped by revision {store.node(cid)['rev']} of {cid}", written_by=run)
            res["withdrawn"].append(e["id"])
    res["claim"] = cid
    return res


# ---- the brief ---------------------------------------------------------------------------------------
def _registered(store: GraphStore, claim_id: str) -> dict:
    c = store.node(claim_id)
    if not c or c["type"] != "Claim" or c["attrs"].get("registration") != REGISTRATION:
        raise schema.Refused(f"claim: {claim_id!r} is not a claim registered with `defend register`")
    return c


def _saidline(g: dict) -> str:
    """Where a cited line is from, and what code does and does not know about who said it."""
    return (f"Quoted lines, {g['repo']}:{g['path']} lines {g['line_start']}-{g['line_end']} (commit {g['commit']}, "
            f"sha256 {g['sha256']}); said by {g['said_by']} as the proposer states; code does not check who said it. "
            f"The said_by name appears in the cited lines: {str(g['said_by_named_in_lines']).lower()}")


def _falsifiers_line(a: dict) -> str | None:
    n = a.get("falsifiers_changed_from_revision")
    return f"the falsifiers were changed in this revision from those of revision {n}" if n else None


def _outcome_line(a: dict) -> str | None:
    v = a["outcome_visibility"]
    return f"registered after an outcome was seen: {v['what']}" if v["outcome_seen"] else None


def brief(store: GraphStore, claim_id: str, dirs: dict | None = None) -> str:
    c = _registered(store, claim_id)
    a = c["attrs"]
    dirs = dirs or repo_dirs(store.data_root, None, None)
    art = _blob(dirs[a["artifact_repo"]], a["code_commit"], a["artifact_path"]).decode("utf-8", errors="replace")
    out = [f"# Challenge brief for {claim_id} (revision {c['rev']})", "",
           "You are the independent reviewer. You were not given the proposer's mechanism, alternatives, falsifiers "
           "or reasons, and you are not to look for them. Below are the claim, its plain-language hypothesis, where it "
           "applies, the artifact it is about and the evidence admitted for it, in full.", "",
           "## The hypothesis, in plain words", "", a["hypothesis"], "", "## The exact claim", "", a["exact_claim"], "",
           "## Scope and boundaries", "", f"Scope: {a['scope']}"]
    if a.get("boundaries"):
        out.append(f"Boundaries: {a['boundaries']}")
    ol = _outcome_line(a)
    if ol:
        out += ["", ol]
    fl = _falsifiers_line(a)
    if fl:
        out += ["", "Note: " + fl + " (what they say is not in this brief)."]
    out += ["", "## The artifact the claim is about", "", f"- repository: {a['artifact_repo']}", f"- path: {a['artifact_path']}",
            f"- code commit: {a['code_commit']}", f"- sha256: {a['artifact_sha256']}", "",
            "The artifact as committed, printed in full as the thing claimed about (it is not the proposer's reasoning):", "", "```", art, "```", ""]
    if a.get("reasoning_files"):
        out += ["Do NOT open these companion files before your challenge is written (they may hold the proposer's "
                "reasoning): " + ", ".join(a["reasoning_files"]), ""]
    out += ["Do NOT run `defend show` on this claim before your challenge is written.", "",
            "## The admissible evidence, in full", ""]
    if not a["rests_on"]:
        out.append("(none: the claim names no ground)")
    for i, g in enumerate(a["rests_on"], 1):
        if g["kind"] == "claim":
            n = store.node(g["id"])
            ga = n["attrs"]
            src = store.node(ga["source"]) if ga.get("source") else None
            where = (f"{src['attrs']['path']} lines {ga['line_start']}-{ga['line_end']}" if src
                     else "no source line (marked an inference)")
            out += [f"### {i}. Claim of the graph {g['id']} ({where})", "", ga.get("exact_claim") or ga["text"]]
            if ga.get("quote"):
                out += ["", f"Quoted from the file: {ga['quote']}"]
        elif g["kind"] == "rule":
            spec = json.loads(_blob(dirs["paper-trading-platform"], g["commit"], g["path"]))["specification"]
            out += [f"### {i}. Rule {g['rule_id']} at commit {g['commit']} ({g['path']})", "", spec, "",
                    f"The words relied on: {g['quote']}"]
        else:
            lines = _lines(_blob(dirs[g["repo"]], g["commit"], g["path"]))
            out += [f"### {i}. {_saidline(g)}", "", "\n".join(lines[g["line_start"] - 1:g["line_end"]])]
        out.append("")
    out += ["## What to hand back", "", "One JSON object, nothing else, with these fields:", "",
            "```json", json.dumps({
                "alternatives": ["at least one competing explanation of what the evidence shows"],
                "falsifiers": [{"observation": "at least one observation that would count against the claim",
                                "record": "in which record it would be looked for"}],
                "distinguishing_observation": "the exact observation that would tell the claim and the competing explanation apart",
                "what_was_checked": ["what you checked"], "what_was_observed": ["what you observed"],
                "what_remains_open": ["what remains open"],
                "objections": ["every objection you have, each its own entry"],
                "saw_proposer_reasoning": "true or false: did you see the proposer's reasoning before writing this",
                "what_i_opened": ["every file or record you opened"]}, indent=2), "```", "",
            "No verdict word and no pass or fail framing anywhere in it: say what was checked, what was observed "
            "and what remains open. Do not average, rank or score anything.", ""]
    return "\n".join(out)


# ---- challenge ---------------------------------------------------------------------------------------
def _independent(store: GraphStore, claim_id: str, run: str) -> None:
    node = _agent_run(store, run)
    role = str(node["attrs"].get("role", ""))
    authors = {l["attrs"].get("proposer_run") for l in store.history(claim_id)}
    if run in authors:
        raise schema.Refused(f"run: {run} is the run that registered {claim_id}; the proposer must not be its sole verifier")
    derived = {}
    for e in store.edges("DERIVED_FROM"):
        derived.setdefault(e["src"], []).append(e["dst"])
    seen, todo = {claim_id}, list(derived.get(claim_id, []))
    while todo:                      # the grounds, and the grounds of the grounds, over DERIVED_FROM
        gid = todo.pop()
        if gid in seen:
            continue
        seen.add(gid)
        ga = store.node(gid)["attrs"]
        if run in (ga.get("extracted_by"), ga.get("proposer_run"), ga.get("proposer")):
            raise schema.Refused(f"run: {run} made the ground claim {gid}; a reviewer must not have authored what the claim rests on")
        todo += derived.get(gid, [])
    if role.strip().lower() != "reviewer":
        raise schema.Refused(f"run: {run} has the role {role!r}; the challenge is made by a run whose role is exactly 'reviewer'")


def challenge(store: GraphStore, claim_id: str, challenge_file, run: str, brief_file=None, dirs: dict | None = None) -> dict:
    c = _registered(store, claim_id)
    d = _load_json(challenge_file)
    _independent(store, claim_id, run)
    w = "challenge file"
    if not brief_file or not Path(brief_file).is_file():
        raise schema.Refused("brief: the brief file the reviewer was given is required (--brief)")
    brief_raw = Path(brief_file).read_bytes()
    want = hashlib.sha256(brief(store, claim_id, dirs).encode("utf-8")).hexdigest()
    if hashlib.sha256(brief_raw).hexdigest() != want:
        raise schema.Refused(f"brief: the file is not the brief of {claim_id} at revision {c['rev']}: its sha256 is "
                             f"{hashlib.sha256(brief_raw).hexdigest()}, the brief the code builds hashes to {want}")
    _unknown(d, CHALLENGE_KEYS, w)
    alts, fals = _list_of_text(d, "alternatives", w), _falsifiers(d, w)
    dist = _text(d, "distinguishing_observation", w)
    checked, observed = _list_of_text(d, "what_was_checked", w), _list_of_text(d, "what_was_observed", w)
    open_ = _list_of_text(d, "what_remains_open", w)
    if not isinstance(d.get("objections"), list):
        raise schema.Refused(f"{w}: objections is missing (a list; empty if there are none)")
    if not isinstance(d.get("saw_proposer_reasoning"), bool):
        raise schema.Refused(f"{w}: saw_proposer_reasoning must be true or false")
    opened = _list_of_text(d, "what_i_opened", w, at_least_one=False)
    _labels(d, w)
    raw = Path(challenge_file).read_bytes()
    fh, bh = hashlib.sha256(raw).hexdigest(), hashlib.sha256(brief_raw).hexdigest()
    eid = "eval:" + sha([claim_id, c["rev"], RUBRIC, run, fh, bh])
    attrs = {
        "rubric": RUBRIC, "what_was_checked": checked, "what_was_observed": observed, "what_remains_open": open_,
        "check_type": "independent challenge", "method": "tools.kgraph.defend challenge",
        "method_version": code_stamp("tools.kgraph.defend"), "claim_revision": c["rev"],
        "input_hash": c["content_sha"], "location": "tools/kgraph/defend.py", "scope": c["attrs"]["scope"],
        "expected_observation": dist, "reproducibility": f"the challenge file, sha256 {fh}; the brief, sha256 {bh}",
        "exceptions": d["objections"], "reviewer": run, "alternatives": alts, "falsifiers": fals,
        "distinguishing_observation": dist, "objections": d["objections"], "brief_sha256": bh,
        "saw_proposer_reasoning": d["saw_proposer_reasoning"], "what_i_opened": opened, "challenge_file": d,
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
              "artifact_repo", "artifact_path", "code_commit", "artifact_sha256", "data_manifest_hashes",
              "outcome_visibility", "inference", "inference_reason", "source_event_ids", "event_time", "knowledge_time",
              "reasoning_files"):
        if k in a:
            out.append(f"{k}: {a[k] if isinstance(a[k], str) else json.dumps(a[k], ensure_ascii=False)}")
    ol = _outcome_line(a)
    if ol:
        out.append(ol)
    if _falsifiers_line(a):
        out.append(f"falsifiers_changed_from_revision: {a['falsifiers_changed_from_revision']}  ({_falsifiers_line(a)})")
    out.append("every revision's falsifiers, with the time each was written:")
    for l in store.history(claim_id):
        out.append(f"  revision {l['rev']}, written {l['written_at']} by {l['written_by']}: "
                   f"{json.dumps(l['attrs']['falsifiers'], ensure_ascii=False)}")
    out.append("rests on:")
    out += [f"  {json.dumps(g, ensure_ascii=False)}" for g in a["rests_on"]] or ["  nothing"]
    out += [f"  {_saidline(g)}" for g in a["rests_on"] if g["kind"] == "cited"]
    ch = challenges_of(store, claim_id)
    out.append("challenges on record:")
    for e in ch:
        ea = e["attrs"]
        out += [f"  {e['id']}  by {ea['reviewer']}  at claim revision {ea['claim_revision']}  (brief sha256 {ea['brief_sha256']}; "
                f"saw the proposer's reasoning: {ea['saw_proposer_reasoning']}; opened: {json.dumps(ea['what_i_opened'])})",
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
            fl = _falsifiers_line(c["attrs"])
            out.append(f"{c['id']}  revision {c['rev']}  {c['attrs']['exact_claim'][:100]}" + (f"  [{fl}]" if fl else ""))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("verb", choices=("register", "challenge-brief", "challenge", "show", "undefended"))
    for f in ("--claim-file", "--claim", "--file", "--brief", "--out", "--run", "--data", "--graph-dir"):
        ap.add_argument(f)
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    try:
        if a.verb == "register":
            print(json.dumps(register(store, a.claim_file, a.run)))
        elif a.verb == "challenge-brief":
            Path(a.out).write_text(brief(store, a.claim), encoding="utf-8")
            print(f"wrote {a.out}")
        elif a.verb == "challenge":
            print(json.dumps(challenge(store, a.claim, a.file, a.run, a.brief)))
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
