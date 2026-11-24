"""Stage 2 of the graph adoption plan: the experiment record (AgentHub pattern).

Every trial is one entry: its parent, the agent run that made it, what was tried, the change (a git
commit), each figure it measured, how long it ran, where, and how it ended. A reverted trial and a
crashed trial are entries like any other. Nothing is averaged, ranked or dropped.

Storage, in a markets-data checkout (Markets holds this code only):
  experiments/trials.jsonl             the record. Only ever added to: a change of status or a
                                       correction is a new line with the next `rev`.
  experiments/frankie_exp_dag.sqlite   the plan's SQLite file, rebuilt whole from trials.jsonl by
                                       `rebuild`. It is an index, not the record: Desktop and Codex
                                       push to the same branch, and lines merge where a binary does not.
  experiments/MANIFEST.json            path, bytes, sha256 of both.

Verbs (AgentHub's): push, fetch <id>, log, children <id>, leaves, lineage <id>, diff <a> <b>.
Also: set-status <id> <status>, rebuild.

  python3 -m tools.exp_dag push --hypothesis "..." --status recorded --key paper-run:orders-...
  python3 -m tools.exp_dag lineage exp-0123456789ab
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from tools.kgraph.store import canonical, markets_data_root, now, sha

EXP_DIR = "experiments"
RECORD = "trials.jsonl"
SQLITE = "frankie_exp_dag.sqlite"
SCHEMA_VERSION = "markets.exp_dag.v1"

# kept / reverted / crash are the plan's three. `recorded` is a trial that was run and written down
# with no keep-or-revert decision made on it (a paper run that is not scored, a backfilled entry).
STATUSES = ("kept", "reverted", "crash", "recorded")

FIELDS = ("parent", "agent_run", "hypothesis", "change", "metrics", "runtime_s", "environment",
          "status", "links", "loop", "note")


class Refused(ValueError):
    pass


class ExpDag:
    def __init__(self, data_root=None, exp_dir=None):
        """`exp_dir` is for checks only (a scratch folder). Left out: markets-data `experiments/`."""
        self.data_root = markets_data_root(data_root)
        self.dir = Path(exp_dir) if exp_dir else self.data_root / EXP_DIR
        self.record = self.dir / RECORD
        self._lines: list[dict] | None = None

    # ---- the record ------------------------------------------------------------------------------
    def lines(self) -> list[dict]:
        if self._lines is None:
            self._lines = []
            if self.record.exists():
                with self.record.open(encoding="utf-8") as f:
                    self._lines = [json.loads(x) for x in f if x.strip()]
        return self._lines

    def latest(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for line in self.lines():
            if line["id"] not in out or line["rev"] > out[line["id"]]["rev"]:
                out[line["id"]] = line
        return out

    def _append(self, line: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.record.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
        self.lines().append(line)

    @staticmethod
    def _check(body: dict, known: dict) -> None:
        if not body.get("hypothesis"):
            raise Refused("a trial says what was tried (hypothesis)")
        if body.get("status") not in STATUSES:
            raise Refused(f"status must be one of {STATUSES}")
        if body.get("parent") and body["parent"] not in known:
            raise Refused(f"parent {body['parent']} is not in the record")
        for other in body.get("links") or []:
            if other not in known:
                raise Refused(f"linked trial {other} is not in the record")
        ch = body.get("change")
        if ch is not None and not (isinstance(ch, dict) and ch.get("repo") and ch.get("commit")):
            raise Refused("change is {repo, commit} (the commit the trial ran), or left out")
        for m in body.get("metrics") or []:
            if not isinstance(m, dict) or "name" not in m or "value" not in m:
                raise Refused("each metric is {name, value, unit, note}: one figure of this one trial")

    # ---- the verbs -------------------------------------------------------------------------------
    def push(self, *, hypothesis: str, status: str, parent: str | None = None,
             agent_run: str | None = None, change: dict | None = None, metrics: list | None = None,
             runtime_s: float | None = None, environment=None, links: list | None = None,
             loop: str | None = None, note: str | None = None, key: str | None = None,
             written_by: str) -> str:
        """Add a trial. `key` is a natural key (a run folder, a commit) so that loading the same
        thing twice makes one entry; without it every push is a new entry."""
        body = {"parent": parent, "agent_run": agent_run, "hypothesis": hypothesis, "change": change,
                "metrics": metrics or [], "runtime_s": runtime_s, "environment": environment,
                "status": status, "links": links or [], "loop": loop, "note": note}
        known = self.latest()
        self._check(body, known)
        stamp = now()
        tid = "exp-" + (sha(["key", key]) if key else sha([body, stamp, len(self.lines())]))
        content = sha(body, 16)
        prev = known.get(tid)
        if prev and prev["content_sha"] == content:
            return tid
        self._append(dict(body, id=tid, key=key, rev=(prev["rev"] + 1 if prev else 1),
                          content_sha=content, written_by=written_by, written_at=stamp))
        return tid

    def set_status(self, tid: str, status: str, *, note: str | None, written_by: str) -> dict:
        prev = self.latest().get(tid)
        if not prev:
            raise Refused(f"{tid} is not in the record")
        body = {k: prev.get(k) for k in FIELDS}
        body["status"] = status
        if note:
            body["note"] = note
        self._check(body, self.latest())
        line = dict(body, id=tid, key=prev.get("key"), rev=prev["rev"] + 1, content_sha=sha(body, 16),
                    written_by=written_by, written_at=now())
        self._append(line)
        return line

    def fetch(self, tid: str) -> list[dict]:
        """Every line of one trial, oldest first (its whole history)."""
        return sorted((l for l in self.lines() if l["id"] == tid), key=lambda l: l["rev"])

    def log(self) -> list[dict]:
        return sorted(self.latest().values(), key=lambda l: (self.fetch(l["id"])[0]["written_at"], l["id"]))

    def children(self, tid: str) -> list[dict]:
        return [l for l in self.log() if l["parent"] == tid]

    def leaves(self) -> list[dict]:
        parents = {l["parent"] for l in self.latest().values() if l["parent"]}
        return [l for l in self.log() if l["id"] not in parents]

    def lineage(self, tid: str) -> list[dict]:
        """From the trial back to its first ancestor."""
        latest, out, seen = self.latest(), [], set()
        while tid and tid in latest and tid not in seen:
            seen.add(tid)
            out.append(latest[tid])
            tid = latest[tid]["parent"]
        return out

    def diff(self, a: str, b: str, repos: dict[str, str] | None = None) -> dict:
        """What differs between two trials: each field, each figure side by side, and the git diff
        of their commits when both are in one repository whose checkout is given in `repos`."""
        latest = self.latest()
        if a not in latest or b not in latest:
            raise Refused("both trials must be in the record")
        x, y = latest[a], latest[b]
        out = {"a": a, "b": b, "fields": {}, "metrics": [], "git": None}
        for k in FIELDS:
            if k != "metrics" and x.get(k) != y.get(k):
                out["fields"][k] = {"a": x.get(k), "b": y.get(k)}
        names = []
        for m in x["metrics"] + y["metrics"]:
            if m["name"] not in names:
                names.append(m["name"])
        for name in names:
            out["metrics"].append({"name": name,
                                   "a": [m["value"] for m in x["metrics"] if m["name"] == name],
                                   "b": [m["value"] for m in y["metrics"] if m["name"] == name]})
        ca, cb = x.get("change"), y.get("change")
        if ca and cb and ca["repo"] == cb["repo"] and repos and ca["repo"] in repos:
            r = subprocess.run(["git", "-C", repos[ca["repo"]], "diff", "--stat", ca["commit"], cb["commit"]],
                               capture_output=True, text=True)
            out["git"] = r.stdout if r.returncode == 0 else f"git diff failed: {r.stderr.strip()}"
        return out

    # ---- the SQLite file ------------------------------------------------------------------------
    def rebuild(self) -> Path:
        """Write experiments/frankie_exp_dag.sqlite whole from trials.jsonl, and the manifest."""
        self.dir.mkdir(parents=True, exist_ok=True)
        out = self.dir / SQLITE
        if out.exists():
            out.unlink()
        db = sqlite3.connect(out)
        db.executescript("""
            create table trial (id text, rev integer, is_latest integer, key text, parent text,
                agent_run text, hypothesis text, change_repo text, change_commit text, status text,
                runtime_s real, environment text, loop text, note text, written_by text,
                written_at text, primary key (id, rev));
            create table metric (trial_id text, rev integer, n integer, name text, value text,
                unit text, note text);
            create table link (trial_id text, rev integer, other_id text);
            create index trial_parent on trial (parent);
            create table meta (k text primary key, v text);
        """)
        latest = self.latest()
        for l in sorted(self.lines(), key=lambda l: (l["id"], l["rev"])):
            ch = l.get("change") or {}
            env = l.get("environment")
            db.execute("insert into trial values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                l["id"], l["rev"], int(latest[l["id"]]["rev"] == l["rev"]), l.get("key"), l["parent"],
                l["agent_run"], l["hypothesis"], ch.get("repo"), ch.get("commit"), l["status"],
                l["runtime_s"], env if isinstance(env, str) or env is None else canonical(env),
                l["loop"], l["note"], l["written_by"], l["written_at"]))
            for n, m in enumerate(l["metrics"]):
                v = m["value"]
                db.execute("insert into metric values (?,?,?,?,?,?,?)", (
                    l["id"], l["rev"], n, m["name"], v if isinstance(v, str) else canonical(v),
                    m.get("unit"), m.get("note")))
            for other in l["links"]:
                db.execute("insert into link values (?,?,?)", (l["id"], l["rev"], other))
        raw = self.record.read_bytes() if self.record.exists() else b""
        db.execute("insert into meta values ('schema', ?)", (SCHEMA_VERSION,))
        db.execute("insert into meta values ('built_from_sha256', ?)", (hashlib.sha256(raw).hexdigest(),))
        db.execute("insert into meta values ('lines', ?)", (str(len(self.lines())),))
        db.commit()
        db.execute("vacuum")
        db.close()
        self.write_manifest()
        return out

    def write_manifest(self) -> Path:
        files = []
        for name, source in ((RECORD, "the record: one line for each trial and each change to one"),
                             (SQLITE, "rebuilt whole from trials.jsonl by tools/exp_dag.py rebuild")):
            p = self.dir / name
            if p.exists():
                raw = p.read_bytes()
                rel = str(p.relative_to(self.data_root)) if p.is_relative_to(self.data_root) else str(p)
                files.append({"path": rel, "bytes": len(raw),
                              "sha256": hashlib.sha256(raw).hexdigest(), "source": source})
        m = {"what": "The experiment record of the agent program (graph adoption plan, stage 2): every "
                     "trial with its parent, run, change, figures and how it ended, the reverted and "
                     "the crashed too.",
             "schema": SCHEMA_VERSION, "how_to_read": "Markets tools/exp_dag.py (push, fetch, log, "
             "children, leaves, lineage, diff)", "files": files}
        out = self.dir / "MANIFEST.json"
        out.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return out


def _show(line: dict) -> str:
    ch = line.get("change") or {}
    figs = "; ".join(f"{m['name']}={m['value']}{' ' + m['unit'] if m.get('unit') else ''}" for m in line["metrics"])
    return (f"{line['id']} rev {line['rev']} [{line['status']}] parent={line['parent'] or '-'} "
            f"{(ch.get('repo', '') + '@' + ch.get('commit', '')[:10]) if ch else '-'}\n"
            f"    {line['hypothesis']}" + (f"\n    figures: {figs}" if figs else "")
            + (f"\n    note: {line['note']}" if line.get("note") else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", help="path of the markets-data checkout")
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("push")
    p.add_argument("--hypothesis", required=True)
    p.add_argument("--status", required=True, choices=STATUSES)
    p.add_argument("--parent")
    p.add_argument("--agent-run")
    p.add_argument("--repo")
    p.add_argument("--commit")
    p.add_argument("--metric", action="append", default=[], help="name=value[:unit], one for each figure")
    p.add_argument("--runtime-s", type=float)
    p.add_argument("--environment")
    p.add_argument("--link", action="append", default=[])
    p.add_argument("--loop")
    p.add_argument("--note")
    p.add_argument("--key")
    p.add_argument("--by", required=True, help="who writes it: an AgentRun id or code:<module>@<commit>")
    for verb in ("fetch", "children", "lineage"):
        sub.add_parser(verb).add_argument("id")
    sub.add_parser("log")
    sub.add_parser("leaves")
    sub.add_parser("rebuild")
    p = sub.add_parser("diff")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--repo-path", action="append", default=[], help="name=path of a checkout, for the git diff")
    p = sub.add_parser("set-status")
    p.add_argument("id")
    p.add_argument("status", choices=STATUSES)
    p.add_argument("--note")
    p.add_argument("--by", required=True)
    a = ap.parse_args(argv)
    dag = ExpDag(a.data)
    try:
        if a.verb == "push":
            metrics = []
            for m in a.metric:
                name, _, rest = m.partition("=")
                value, _, unit = rest.partition(":")
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
                metrics.append({"name": name, "value": value, "unit": unit or None, "note": None})
            change = {"repo": a.repo, "commit": a.commit} if a.repo and a.commit else None
            print(dag.push(hypothesis=a.hypothesis, status=a.status, parent=a.parent, agent_run=a.agent_run,
                           change=change, metrics=metrics, runtime_s=a.runtime_s, environment=a.environment,
                           links=a.link, loop=a.loop, note=a.note, key=a.key, written_by=a.by))
        elif a.verb == "fetch":
            for l in dag.fetch(a.id):
                print(json.dumps(l, ensure_ascii=False, indent=1))
        elif a.verb in ("log", "leaves"):
            for l in getattr(dag, a.verb)():
                print(_show(l))
        elif a.verb in ("children", "lineage"):
            for l in getattr(dag, a.verb)(a.id):
                print(_show(l))
        elif a.verb == "diff":
            repos = dict(x.split("=", 1) for x in a.repo_path)
            print(json.dumps(dag.diff(a.a, a.b, repos), ensure_ascii=False, indent=1))
        elif a.verb == "set-status":
            print(_show(dag.set_status(a.id, a.status, note=a.note, written_by=a.by)))
        elif a.verb == "rebuild":
            print(dag.rebuild())
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
