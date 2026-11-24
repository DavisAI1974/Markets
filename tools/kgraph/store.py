"""Stage 4a: the graph's files and how they are written and read.

Storage (plan 4a): lines in markets-data `graph/nodes/<Type>.jsonl` and `graph/edges/<TYPE>.jsonl`,
listed in `graph/MANIFEST.json`, loaded into a NetworkX MultiDiGraph for queries.

Only added to, never rewritten:
- a node or link that already stands with the same content is not written again;
- a changed one is written as a new line with the next `rev`; the earlier line stays in the file and
  stays addressable (`history(id)`), which is write rule 4 of the plan;
- taking a link back (a merge undone, a claim withdrawn) is a new line with `withdrawn: true`.

Markets holds this code only. The files live in a markets-data checkout: pass its path, or set
MARKETS_DATA, or keep the two checkouts side by side.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from pathlib import Path

from . import schema

GRAPH_DIR = "graph"
# What can "rest on" something: a thing that states or decides. A record linked to a record (an order
# to the file it was read from) is not resting on it in that sense.
RESTING_TYPES = ("Claim", "Entity", "Evaluation")


def markets_data_root(explicit: str | os.PathLike | None = None) -> Path:
    for cand in (explicit, os.environ.get("MARKETS_DATA"),
                 Path(__file__).resolve().parents[3] / "markets-data"):
        if cand and (Path(cand) / "MANIFEST.json").exists():
            return Path(cand)
    raise FileNotFoundError("no markets-data checkout found: pass its path or set MARKETS_DATA")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha(obj, n: int = 12) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()[:n]


def edge_id(etype: str, src: str, dst: str, key: str = "") -> str:
    return "e:" + sha([etype, src, dst, key])


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


PENDING = ".pending-write.json"


def _read(path: Path, skipped: list | None = None) -> list[dict]:
    """The lines of one file. A line that is not JSON raises with the file and the line number; given a
    `skipped` list (a tolerant load) it is left out of the result and listed there instead, so the
    check can still run and say which line it is."""
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError as e:
                    msg = f"{path}:{n}: not a JSON line ({e})"
                    if skipped is None:
                        raise ValueError(msg) from e
                    skipped.append(msg)
    return out


class GraphStore:
    def __init__(self, data_root: str | os.PathLike | None = None, graph_dir: str | os.PathLike | None = None,
                 tolerant: bool = False):
        """`graph_dir` is for checks only: a scratch folder to write to while sources are still read
        from the real checkout. Left out, the graph is markets-data `graph/`.
        `tolerant=True` loads past a line that is not JSON (it is listed in `skipped_lines` and reported
        by `check_all`) so the check can run on a file with a line cut part way."""
        self.data_root = markets_data_root(data_root)
        self.dir = Path(graph_dir) if graph_dir else self.data_root / GRAPH_DIR
        self.tolerant = tolerant
        self.skipped_lines: list[str] = []
        self._nodes: dict[str, list[dict]] | None = None   # id -> every line, oldest first
        self._edges: dict[str, list[dict]] | None = None

    # ---- reading -------------------------------------------------------------------------------
    def _load_lines(self) -> None:
        if self._nodes is not None:
            return
        self._nodes, self._edges = {}, {}
        for sub, into in (("nodes", self._nodes), ("edges", self._edges)):
            d = self.dir / sub
            if d.is_dir():
                for p in sorted(d.glob("*.jsonl")):
                    for line in _read(p, self.skipped_lines if self.tolerant else None):
                        into.setdefault(line["id"], []).append(line)
        for into in (self._nodes, self._edges):
            for lines in into.values():
                lines.sort(key=lambda x: (x["rev"], x["written_at"], x["content_sha"]))

    def node(self, node_id: str) -> dict | None:
        self._load_lines()
        lines = self._nodes.get(node_id)
        return lines[-1] if lines else None

    def history(self, any_id: str) -> list[dict]:
        """Every line ever written for a node or link id, oldest first. Nothing is ever lost."""
        self._load_lines()
        return list(self._nodes.get(any_id) or self._edges.get(any_id) or [])

    def nodes(self, ntype: str | None = None) -> list[dict]:
        self._load_lines()
        return [l[-1] for l in self._nodes.values() if ntype is None or l[-1]["type"] == ntype]

    def edges(self, etype: str | None = None, *, withdrawn: bool = False) -> list[dict]:
        self._load_lines()
        out = [l[-1] for l in self._edges.values() if etype is None or l[-1]["type"] == etype]
        return out if withdrawn else [e for e in out if not e["attrs"].get("withdrawn")]

    def counts(self) -> dict:
        self._load_lines()
        c = {"nodes": {}, "edges": {}, "node_lines": 0, "edge_lines": 0}
        for lines in self._nodes.values():
            c["nodes"][lines[-1]["type"]] = c["nodes"].get(lines[-1]["type"], 0) + 1
            c["node_lines"] += len(lines)
        for lines in self._edges.values():
            c["edges"][lines[-1]["type"]] = c["edges"].get(lines[-1]["type"], 0) + 1
            c["edge_lines"] += len(lines)
        return c

    def to_networkx(self, *, withdrawn: bool = False):
        """The graph as it stands now: the latest line of every node and every link not taken back."""
        import networkx as nx
        g = nx.MultiDiGraph(schema=schema.SCHEMA_VERSION)
        for n in self.nodes():
            g.add_node(n["id"], type=n["type"], rev=n["rev"], written_by=n["written_by"], **{"attrs": n["attrs"]})
        for e in self.edges(withdrawn=withdrawn):
            g.add_edge(e["src"], e["dst"], key=e["id"], type=e["type"], rev=e["rev"],
                       written_by=e["written_by"], attrs=e["attrs"])
        return g

    # ---- writing -------------------------------------------------------------------------------
    def write(self, nodes: list[dict] = (), edges: list[dict] = (), *, written_by: str) -> dict:
        """Add nodes and links. Each is {"id","type","attrs"} (+ "src","dst" for a link).

        `written_by` is the AgentRun id or `code:<module>@<commit>` that made them: every line names
        its author. The whole batch is checked first; if one line is refused, nothing is written.
        Returns how many lines were new, how many were a new revision and how many already stood.
        """
        if not written_by:
            raise schema.Refused("a write names who made it (an AgentRun id or code:<module>@<commit>)")
        self._load_lines()
        nodes, edges = list(nodes), list(edges)
        for n in nodes:
            schema.check_node(n)
        batch_ids = {n["id"] for n in nodes}
        for e in edges:
            schema.check_edge(e)
            for end in (e["src"], e["dst"]):
                if end not in batch_ids and end not in self._nodes:
                    raise schema.Refused(f"edge {e['id']} ({e['type']}): {end} is not a node of the graph")
        # Nothing new may rest on a claim in a closed scope (Greg, 2026-11-24: no new claim is tied to a
        # tastytrade platform issue). A link that is already standing is not a new tie.
        closed = self.closed_scope_members()
        if closed:
            kinds = {n["id"]: n["type"] for n in nodes}
            for e in edges:
                rested = self._rested_on(e)
                if rested not in closed or e["attrs"].get("withdrawn"):
                    continue
                resting = e["dst"] if rested == e["src"] else e["src"]
                kind = kinds.get(resting) or (self._nodes[resting][-1]["type"] if resting in self._nodes else None)
                standing = self._edges.get(e["id"])
                if kind in RESTING_TYPES and not (standing and not standing[-1]["attrs"].get("withdrawn")):
                    raise schema.Refused(
                        f"{e['type']} {e['src']} -> {e['dst']}: {rested} is in the scope \"{closed[rested]}\"; "
                        "nothing new may rest on it (it is kept and marked; a mark is lifted only with its reason)")
        # A line that names where it came from (`source`) names a node of the graph, whatever its type.
        for n in nodes:
            src = n["attrs"].get("source")
            if src is not None and src not in batch_ids and src not in self._nodes:
                raise schema.Refused(f"{n['type']} {n['id']}: its source {src} is not a node of the graph")
        # write rule 1, the link side: a claim that is not an inference is tied to its source by a
        # SUPPORTS link from that source, in this batch or already standing.
        supported = {e["dst"] for e in edges if e["type"] == "SUPPORTS"}
        supported |= {e["dst"] for e in self.edges("SUPPORTS")}
        for n in nodes:
            if n["type"] == "Claim" and not n["attrs"]["inference"] and n["id"] not in supported:
                raise schema.Refused(f"Claim {n['id']}: no SUPPORTS link from its source")

        if self.is_real_graph() and written_by.endswith("+uncommitted"):
            raise schema.Refused(
                f"{written_by}: code with uncommitted changes does not write into the real graph "
                f"({self.dir}); commit the code first, so the writer of every line can be read back")
        stamp, result, to_write = now(), {"new": 0, "revised": 0, "unchanged": 0}, {}
        staged: dict[str, list[dict]] = {}           # id -> lines of this batch, not yet in the tables
        for kind, items, table in (("nodes", nodes, self._nodes), ("edges", edges, self._edges)):
            for item in items:
                body = {k: item[k] for k in ("id", "type", "src", "dst", "attrs") if k in item}
                content = sha(body, 16)
                prev = list(table.get(item["id"]) or []) + staged.get(item["id"], [])
                if prev and prev[-1]["content_sha"] == content:
                    result["unchanged"] += 1
                    continue
                revs = [l["rev"] for l in prev]
                if len(set(revs)) != len(revs):
                    raise schema.Refused(
                        f"{item['type']} {item['id']}: two lines carry the same rev (two writers' lines merged); "
                        "no further revision is added until that is resolved (nothing is deleted by code: "
                        "see `kgraph check`)")
                line = dict(body, rev=(prev[-1]["rev"] + 1 if prev else 1), content_sha=content,
                            written_by=written_by, written_at=stamp)
                result["revised" if prev else "new"] += 1
                staged.setdefault(item["id"], []).append(line)
                to_write.setdefault(self.dir / kind / f"{item['type']}.jsonl", []).append(line)
        if not to_write:
            return result
        pend = self.dir / PENDING
        if pend.exists():
            raise schema.Refused(f"{pend} is left over from a write that did not finish: look at it with "
                                 "`kgraph check` and settle it before writing more")
        text = {path: [json.dumps(l, ensure_ascii=False, sort_keys=True) for l in lines]
                for path, lines in to_write.items()}
        pend.parent.mkdir(parents=True, exist_ok=True)
        pend.write_text(json.dumps({"written_by": written_by, "written_at": stamp,
                                    "files": {self._rel(p): t for p, t in text.items()}},
                                   ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        for path, lines in text.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write("".join(l + "\n" for l in lines))
                f.flush()
                os.fsync(f.fileno())
        self.write_manifest()
        pend.unlink()
        for table, kind in ((self._nodes, "nodes"), (self._edges, "edges")):
            for path, lines in to_write.items():
                if path.parent.name == kind:
                    for line in lines:
                        table.setdefault(line["id"], []).append(line)
        return result

    def is_real_graph(self) -> bool:
        return Path(self.dir).resolve() == (self.data_root / GRAPH_DIR).resolve()

    @staticmethod
    def _rested_on(edge: dict) -> str | None:
        """The end of a link that the other end rests on, for the links that mean "rests on" or "is a
        later wording of"."""
        if edge["type"] in ("DERIVED_FROM", "DEPENDS_ON", "REVISES"):
            return edge["dst"]
        if edge["type"] == "SUPPORTS":
            return edge["src"]
        return None

    def closed_scope_members(self) -> dict[str, str]:
        """node id -> the scope's name, for everything that is a member of a closed scope (an Entity with
        entity_kind "scope" and closed true). Nothing new may rest on a member; the member itself stays."""
        self._load_lines()
        scopes = {l[-1]["id"]: l[-1]["attrs"].get("name", l[-1]["id"]) for l in self._nodes.values()
                  if l[-1]["type"] == "Entity" and l[-1]["attrs"].get("entity_kind") == "scope" and l[-1]["attrs"].get("closed")}
        if not scopes:
            return {}
        return {e["src"]: scopes[e["dst"]] for e in self.edges("MEMBER_OF") if e["dst"] in scopes}

    def withdraw_edge(self, edge_id_: str, *, reason: str, written_by: str) -> dict:
        """Take a link back without losing it: a new line marked withdrawn, the old one kept."""
        self._load_lines()
        lines = self._edges.get(edge_id_)
        if not lines:
            raise schema.Refused(f"{edge_id_} is not a link of the graph")
        last = lines[-1]
        attrs = dict(last["attrs"], withdrawn=True, withdrawn_reason=reason)
        return self.write(edges=[{"id": last["id"], "type": last["type"], "src": last["src"],
                                  "dst": last["dst"], "attrs": attrs}], written_by=written_by)

    def write_manifest(self) -> Path:
        files = []
        for p in sorted(self.dir.glob("*/*.jsonl")):
            raw = p.read_bytes()
            files.append({"path": self._rel(p), "bytes": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest(), "lines": raw.count(b"\n"),
                          "source": "written by Markets tools/kgraph (the knowledge graph, plan stage 4)"})
        manifest = {
            "what": "The knowledge graph of the agent program (graph adoption plan, stage 4): one line "
                    "for each node and each link, only ever added to.",
            "schema": schema.SCHEMA_VERSION,
            "how_to_read": "Markets tools/kgraph/store.py GraphStore; the latest rev of an id is how it "
                           "stands, earlier revs stay in the file.",
            "files": files,
        }
        out = self.dir / "MANIFEST.json"
        out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return out

    def _rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(self.data_root))
        except ValueError:
            return str(p)

    def _pending_and_manifest_breaches(self) -> list[str]:
        """A write that did not finish (a leftover pending file, and which of its lines are not in the
        files) and every place MANIFEST.json disagrees with the files."""
        out = []
        pend = self.dir / PENDING
        if pend.exists():
            try:
                body = json.loads(pend.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                body = None
                out.append(f"{pend}: left over from a write that did not finish, and it is not readable ({e})")
            if body is not None:
                for rel, lines in sorted(body.get("files", {}).items()):
                    p = Path(rel) if Path(rel).is_absolute() else self.data_root / rel
                    have = set()
                    if p.exists():
                        have = {l.strip() for l in p.read_text(encoding="utf-8").splitlines()}
                    missing = [l for l in lines if l not in have]
                    out.append(f"{pend.name}: left over from a write by {body.get('written_by')} that did not "
                               f"finish; {rel}: {len(missing)} of its {len(lines)} lines are missing from the file"
                               + ("".join(f" ({json.loads(l)['id']} rev {json.loads(l)['rev']})" for l in missing[:5])))
        mf = self.dir / "MANIFEST.json"
        if mf.exists():
            m = json.loads(mf.read_text(encoding="utf-8"))
            listed = set()
            for f in m.get("files", []):
                p = Path(f["path"]) if Path(f["path"]).is_absolute() else self.data_root / f["path"]
                listed.add(p.resolve())
                if not p.exists():
                    out.append(f"MANIFEST.json lists {f['path']}, which is not there")
                    continue
                raw = p.read_bytes()
                if hashlib.sha256(raw).hexdigest() != f.get("sha256"):
                    out.append(f"MANIFEST.json: {f['path']} sha256 differs from the file")
                nl = raw.count(b"\n")
                if nl != f.get("lines"):
                    out.append(f"MANIFEST.json: {f['path']} has {nl} lines, the manifest says {f.get('lines')}")
                if len(raw) != f.get("bytes"):
                    out.append(f"MANIFEST.json: {f['path']} has {len(raw)} bytes, the manifest says {f.get('bytes')}")
            for p in sorted(self.dir.glob("*/*.jsonl")):
                if p.resolve() not in listed:
                    out.append(f"MANIFEST.json does not list {self._rel(p)}")
        elif any(self.dir.glob("*/*.jsonl")):
            out.append("MANIFEST.json is missing")
        return out

    # ---- the four write rules, over the whole graph ----------------------------------------------
    def check_all(self) -> list[str]:
        """Every breach of a write rule in the stored graph, one line each. Empty when there is none."""
        self._load_lines()
        out = list(self.skipped_lines)
        out += self._pending_and_manifest_breaches()
        supported = {e["dst"]: e for e in self.edges("SUPPORTS")}
        for lines in self._nodes.values():
            n = lines[-1]
            try:
                schema.check_node(n)
            except schema.Refused as e:
                out.append(str(e))
                continue
            src = n["attrs"].get("source")
            if src is not None and src not in self._nodes:
                out.append(f"{n['type']} {n['id']}: its source {src} is not in the graph")
            if n["type"] == "Claim" and not n["attrs"]["inference"] and n["id"] not in supported:
                out.append(f"Claim {n['id']}: no SUPPORTS link from its source")
            if [l["rev"] for l in lines] != list(range(1, len(lines) + 1)):
                out.append(f"{n['type']} {n['id']}: revisions are not 1..{len(lines)} in order")
        for lines in self._edges.values():
            e = lines[-1]
            for end in (e["src"], e["dst"]):
                if end not in self._nodes:
                    out.append(f"edge {e['id']} ({e['type']}): {end} is not a node")
        closed = self.closed_scope_members()
        for e in self.edges():
            rested = self._rested_on(e)
            if rested in closed:
                resting = e["dst"] if rested == e["src"] else e["src"]
                if self._nodes.get(resting, [{}])[-1].get("type") in RESTING_TYPES:
                    out.append(f"{e['type']} {e['id']}: {resting} rests on {rested}, which is in the scope \"{closed[rested]}\"")
        for e in self.edges("SUPERSEDES"):
            if e["dst"] not in self._nodes:
                out.append(f"SUPERSEDES {e['id']}: the superseded {e['dst']} is no longer addressable")
        return out
