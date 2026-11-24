"""Ticket 04 of the 44: nothing keeps the outcome from the challenger until the challenge is on record. This is the one rule
that says who may see a claim's outcome-bearing records and when, and the one door the code hands them through.

THE RULE (may_see_outcome). The claim is a registered claim (`defend register`). A run whose agent is the reviewer (the
agent type of the run, else the first word of its role: the same test `defend._independent` makes) may see the claim's
outcome-bearing records only when ITS OWN independent challenge of the claim's CURRENT revision is on record. Any other run,
and a caller that names no run, only when at least one independent challenge of the current revision is on record. A new
revision of the claim closes the door again until it is challenged. The function only reads; it writes nothing.

  python3 -m tools.kgraph.outcome release --claim <claim id> --run run:NNNN --record <repo>:<path>@<commit> [--record ...]
                                          --out <folder> [--data <markets-data>] [--graph-dir <scratch graph>]
  python3 -m tools.kgraph.outcome releases --claim <claim id> --run run:NNNN

`release` refuses by the rule (the refusal is kept as a Task through defend, verb "outcome"; exit 2, or 3 when it could not
be kept). Each record is `repo:path@commit` (repo = the first colon, commit = after the last @, any ref that resolves in
that checkout). The commit is resolved to its full id and the sha256 is taken from the bytes at that commit, as the
artifact check of `defend register` does. Only then is ONE Task written (state done, text "outcome records handed to <run>
for <claim> revision <N>"; the claim, its revision, the run, each record's repo, path, full commit, sha256 and bytes, the ids
of the challenges on record at that moment, the time; MENTIONS from the Task to the Claim, PRODUCED from the run to the
Task), and only after the Task is written are the files copied to <out>/<repo>/<path>, byte for byte; an existing file is
never overwritten. `releases` says who was handed the outcome and when, for every caller; the record paths and hashes
only to a run that passes the rule.

WHAT THIS DOES NOT HOLD. An agent with a file tool can open a record it was not handed, and the graph's own files, directly:
nothing here stops that, and a refusal here is not a lock on the disk. What tickets 05 and 06 will write after a check is in
the session text for everyone, so a challenge written after a check is not blind: it is marked as that
(`outcome_on_record_before_challenge` on the challenge, defend.py), not prevented. A refusal of `may_see_outcome` called from
the file proposer or from `afterwards brief` is not kept as a Task (those callers hold a read-only or no graph).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import string
import sys
from pathlib import Path

from . import defend, schema
from .extract import repo_dirs
from .sources import git, link
from .store import GraphStore, now, sha


def _agent_is_reviewer(node: dict) -> bool:
    """The same test as defend._independent (copied: that function mixes it with other refusals)."""
    role = str(node["attrs"].get("role", ""))
    atype = str(node["attrs"].get("agent_type") or "").strip()
    first = role.split()[0].strip(string.punctuation).lower() if role.split() else ""
    return (atype.lower() if atype else first) == "reviewer"


def is_reviewer(store: GraphStore, run: str) -> bool:
    return _agent_is_reviewer(defend._agent_run(store, run))


def current_challenges(store: GraphStore, claim_id: str) -> list[dict]:
    c = store.node(claim_id)
    return [e for e in defend.challenges_of(store, claim_id) if e["attrs"].get("claim_revision") == c["rev"]]


def own_current_challenge(store: GraphStore, claim_id: str, run: str) -> bool:
    return any(e["attrs"].get("reviewer") == run for e in current_challenges(store, claim_id))


def may_see_outcome(store: GraphStore, claim_id: str, run: str | None = None) -> tuple[bool, str]:
    c = store.node(claim_id)
    if not c or c["type"] != "Claim" or c["attrs"].get("registration") != defend.REGISTRATION:
        return False, f"claim: {claim_id!r} is not a claim registered with `defend register`"
    rev = c["rev"]
    if run is not None:
        try:
            node = defend._agent_run(store, run)
        except schema.Refused as e:
            return False, str(e)
        if _agent_is_reviewer(node):
            if own_current_challenge(store, claim_id, run):
                return True, f"{run} has its own independent challenge of {claim_id} revision {rev} on record"
            return False, (f"{claim_id} revision {rev}: the outcome is held back from {run} until its own independent "
                           f"challenge of revision {rev} is on record; none is")
    if current_challenges(store, claim_id):
        return True, f"an independent challenge of {claim_id} revision {rev} is on record"
    return False, (f"{claim_id} revision {rev}: the outcome is held back until an independent challenge of revision {rev} "
                   "is on record; none is")


def releases_of(store: GraphStore, claim_id: str) -> list[dict]:
    ids = {e["src"] for e in store.edges("MENTIONS") if e["dst"] == claim_id}
    out = [n for n in (store.node(i) for i in ids) if n and n["type"] == "Task" and n["attrs"].get("outcome_release")]
    return sorted(out, key=lambda n: (n["attrs"]["released_at"], n["id"]))


def outcome_on_record(store: GraphStore, claim_id: str, run: str) -> bool:
    """True when, now, a release of the claim's records to `run` (any revision) is on record, or a falsifier check
    (ticket 05 writes those; the second half has no check against real records until then) EVALUATES the claim."""
    if any(r["attrs"].get("run") == run for r in releases_of(store, claim_id)):
        return True
    for e in store.edges("EVALUATES"):
        if e["dst"] == claim_id:
            n = store.node(e["src"])
            if n and str(n["attrs"].get("rubric", "")).startswith("falsifier check"):
                return True
    return False


def check_show(store: GraphStore, claim_id: str, run: str | None) -> None:
    """`defend show` prints the proposer's mechanism, alternatives and falsifiers: a reviewer without its own challenge
    of the current revision is refused. Every other run (the proposer included) may read it, challenges or not."""
    if run is None:
        return
    node = defend._agent_run(store, run)
    c = defend._registered(store, claim_id)
    if _agent_is_reviewer(node) and not own_current_challenge(store, claim_id, run):
        raise schema.Refused(f"run: {run} is a reviewer without its own challenge of {claim_id} revision {c['rev']} on "
                             "record; `show` prints the proposer's mechanism, alternatives and falsifiers")


def _parse(spec: str) -> tuple[str, str, str]:
    if ":" not in spec or "@" not in spec:
        raise schema.Refused(f"record: {spec!r} is not <repo>:<path>@<commit>")
    repo, rest = spec.split(":", 1)
    path, commit = rest.rsplit("@", 1)
    if not (repo and path and commit):
        raise schema.Refused(f"record: {spec!r} is not <repo>:<path>@<commit>")
    return repo, path, commit


def release(store: GraphStore, claim_id: str, run: str, specs: list[str], out, dirs: dict | None = None) -> dict:
    try:
        return _release(store, claim_id, run, specs, out, dirs)
    except defend.NotRetained:
        raise
    except schema.Refused as e:
        defend._retain(store, "outcome", run, str(e), {"claim": claim_id, "records": list(specs)})
        raise


def _release(store, claim_id, run, specs, out, dirs):
    c = defend._registered(store, claim_id)
    ok, why = may_see_outcome(store, claim_id, run)
    if not ok:
        raise schema.Refused(why)
    if not specs:
        raise schema.Refused("record: none given (--record <repo>:<path>@<commit>)")
    dirs = dirs or repo_dirs(store.data_root, None, None)
    recs, blobs = [], []
    for spec in specs:
        repo, path, ref = _parse(spec)
        if repo not in dirs:
            raise schema.Refused(f"record {spec}: repo {repo!r} has no local checkout")
        try:
            full = git(dirs[repo], "rev-parse", "--verify", ref + "^{commit}")
        except RuntimeError:
            raise schema.Refused(f"record {spec}: commit {ref} does not exist in the {repo} checkout") from None
        try:
            raw = defend._blob(dirs[repo], full, path)
        except RuntimeError:
            raise schema.Refused(f"record {spec}: path {path} is not in {repo} at {full}") from None
        recs.append({"repo": repo, "path": path, "commit": full, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        blobs.append(raw)
    targets = [Path(out) / r["repo"] / r["path"] for r in recs]
    for t in targets:
        if t.exists():
            raise schema.Refused(f"out: {t} already exists; a handed-over file is never rewritten")
    stamp = now()
    chs = sorted(e["id"] for e in defend.challenges_of(store, claim_id))
    tid = "task:outcome-release-" + sha([claim_id, c["rev"], run, recs, chs, stamp])
    attrs = {"text": f"outcome records handed to {run} for {claim_id} revision {c['rev']}", "state": "done",
             "outcome_release": True, "claim": claim_id, "claim_revision": c["rev"], "run": run, "records": recs,
             "challenges": chs, "released_at": stamp}
    res = store.write([{"id": tid, "type": "Task", "attrs": attrs}],
                      [link("MENTIONS", tid, claim_id), link("PRODUCED", run, tid)], written_by=run)
    for t, raw in zip(targets, blobs):      # the hand-over is on record first; a failed copy never leaves one off the record
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_bytes(raw)
    res["release"] = tid
    return res


def describe(store: GraphStore, claim_id: str, run: str | None) -> str:
    defend._registered(store, claim_id)
    ok = run is not None and may_see_outcome(store, claim_id, run)[0]
    lines = [f"{claim_id}: outcome records handed over, oldest first"]
    for r in releases_of(store, claim_id):
        a = r["attrs"]
        lines.append(f"  {a['released_at']}  handed to {a['run']}  claim revision {a['claim_revision']}  ({r['id']})")
        if ok:
            lines += [f"    {x['repo']}:{x['path']}@{x['commit']}  sha256 {x['sha256']}  {x['bytes']} bytes" for x in a["records"]]
    if len(lines) == 1:
        lines.append("  none")
    if not ok:
        lines.append("  (record paths and hashes are shown only to a run that passes the rule)")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("verb", choices=("release", "releases"))
    for f in ("--claim", "--run", "--out", "--data", "--graph-dir"):
        ap.add_argument(f)
    ap.add_argument("--record", action="append", default=[])
    a = ap.parse_args(argv)
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    try:
        if a.verb == "release":
            print(json.dumps(release(store, a.claim, a.run, a.record, a.out)))
        else:
            print(describe(store, a.claim, a.run))
    except defend.NotRetained as e:
        print(f"refused, and NOT retained: {e}", file=sys.stderr)
        return 3
    except schema.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
