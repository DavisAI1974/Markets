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


def _read(path: Path) -> list[dict]:
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
                    raise ValueError(f"{path}:{n}: not a JSON line ({e})") from e
    return out


class GraphStore:
    def __init__(self, data_root: str | os.PathLike | None = None, graph_dir: str | os.PathLike | None = None):
        """`graph_dir` is for checks only: a scratch folder to write to while sources are still read
        from the real checkout. Left out, the graph is markets-data `graph/`."""
        self.data_root = markets_data_root(data_root)
        self.dir = Path(graph_dir) if graph_dir else self.data_root / GRAPH_DIR
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
                    for line in _read(p):
                        into.setdefault(line["id"], []).append(line)
        for into in (self._nodes, self._edges):
            for lines in into.values():
                lines.sort(key=lambda x: x["rev"])

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

        stamp, result, to_write = now(), {"new": 0, "revised": 0, "unchanged": 0}, {}
        for kind, items, table in (("nodes", nodes, self._nodes), ("edges", edges, self._edges)):
            for item in items:
                body = {k: item[k] for k in ("id", "type", "src", "dst", "attrs") if k in item}
                content = sha(body, 16)
                prev = table.get(item["id"])
                if prev and prev[-1]["content_sha"] == content:
                    result["unchanged"] += 1
                    continue
                line = dict(body, rev=(prev[-1]["rev"] + 1 if prev else 1), content_sha=content,
                            written_by=written_by, written_at=stamp)
                result["revised" if prev else "new"] += 1
                table.setdefault(item["id"], []).append(line)
                to_write.setdefault(self.dir / kind / f"{item['type']}.jsonl", []).append(line)
        for path, lines in to_write.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                for line in lines:
                    f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
        if to_write:
            self.write_manifest()
        return result

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

    # ---- the four write rules, over the whole graph ----------------------------------------------
    def check_all(self) -> list[str]:
        """Every breach of a write rule in the stored graph, one line each. Empty when there is none."""
        self._load_lines()
        out = []
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
        for e in self.edges("SUPERSEDES"):
            if e["dst"] not in self._nodes:
                out.append(f"SUPERSEDES {e['id']}: the superseded {e['dst']} is no longer addressable")
        return out
