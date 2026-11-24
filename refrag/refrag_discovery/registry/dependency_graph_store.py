"""SQLite-backed mirror of the registry dependency graph (arch §3.1).

Arch §3.1 mandates that the dependency-graph storage uses both an adjacency-list
JSON file *and* a SQLite database, because:

    "Adjacency list for fast traversal. SQLite for complex queries (transitive
    deps, cycle detection)."  — arch §3.2

The JSON file (``registry/dependency_graph/graph.json``) and the topological
order file (``registry/dependency_graph/topological_order.json``) are already
materialised by ``scripts/build_registry_indexes.py`` from the manifests. They
remain the **source of truth** for human readers and git diffs.

This module adds the SQL-queryable mirror. The mirror is **additive** and
**idempotent** — running ``bootstrap_sqlite_from_json`` repeatedly produces the
same database state. The schema follows the arch §3.1 layout (nodes + edges)
and the arch §6 depth-banded topological order (D0–D4 for operators; the
``od_spectral_retrieval_pipeline`` template lives at the deepest computed
depth as a terminal node).

Plane assignment is read straight from each manifest's ``execution_class``
field (per arch §1.1/1.2). The arch text uses the labels ``runtime``,
``control``, ``cross_layer`` while the manifests on disk use ``runtime`` and
``control_plane``. We mirror the manifest verbatim — the manifests are the
source of truth, the arch text is descriptive.

Concurrency: each public function opens its own connection, sets
``journal_mode=WAL`` for read concurrency, and closes the connection before
returning. This keeps the module composition-safe with the other Phase 1
control-plane writers, none of which touch SQLite.

Arch citations:
    §1.1 / §1.2 — runtime / control plane definitions
    §3.1       — dependency_graph/ directory + JSON + SQLite storage spec
    §3.2       — backend rationale ("SQLite for complex queries")
    §3.3 / Rule 3 — registry writes are restricted; this module is read+bootstrap
                    only, no per-run mutation
    §6         — depth banding D0–D4
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

from refrag_discovery.paths import DEPENDENCY_GRAPH_DIR, MANIFESTS_DIR


# Default on-disk paths. Tests and bootstrap can override.
DEFAULT_GRAPH_JSON_PATH: Path = DEPENDENCY_GRAPH_DIR / "graph.json"
DEFAULT_TOPO_JSON_PATH: Path = DEPENDENCY_GRAPH_DIR / "topological_order.json"
DEFAULT_SQLITE_PATH: Path = DEPENDENCY_GRAPH_DIR / "graph.sqlite"


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    operator_id TEXT PRIMARY KEY,
    plane TEXT NOT NULL,
    manifest_version TEXT,
    manifest_path TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    dep_type TEXT NOT NULL,
    PRIMARY KEY (source, target, dep_type),
    FOREIGN KEY (source) REFERENCES nodes(operator_id),
    FOREIGN KEY (target) REFERENCES nodes(operator_id)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);

CREATE TABLE IF NOT EXISTS topological_order (
    operator_id TEXT PRIMARY KEY,
    depth INTEGER NOT NULL,
    position INTEGER NOT NULL,
    FOREIGN KEY (operator_id) REFERENCES nodes(operator_id)
);
"""


# ----------------------------------------------------------------------------
# Connection helpers
# ----------------------------------------------------------------------------


@contextmanager
def _connect(sqlite_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection with WAL journaling enabled.

    WAL is set per-connection — SQLite persists ``journal_mode=WAL`` to the
    database header on first write, so subsequent connections inherit it.
    Each public API call opens + closes its own connection (no module-level
    pool) per arch Rule 3 spirit: connection lifecycles are explicit and
    auditable.
    """
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(sqlite_path))
    try:
        conn.row_factory = sqlite3.Row
        # WAL: better read concurrency vs the default DELETE journal. Foreign
        # keys: enforce edge.source / edge.target referential integrity per
        # the schema declaration.
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent — CREATE ... IF NOT EXISTS for every object."""
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


# ----------------------------------------------------------------------------
# Manifest plane lookup (arch §1.1 / §1.2)
# ----------------------------------------------------------------------------


def _load_manifest_plane_map(
    manifests_dir: Path = MANIFESTS_DIR,
) -> dict[str, dict[str, str]]:
    """Return ``{operator_id: {plane, version, path}}`` keyed by manifest.

    Plane is read straight from ``execution_class``. Pipeline templates
    declare ``execution_class: runtime`` too — that matches arch §1 (templates
    run inside the runtime plane).
    """
    plane_map: dict[str, dict[str, str]] = {}
    if not manifests_dir.is_dir():
        return plane_map
    for manifest_path in sorted(manifests_dir.glob("*.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Skip unreadable manifests rather than failing the bootstrap;
            # the manifest validator (Phase 1) is the gate for malformed JSON.
            continue
        operator_id = manifest.get("operator_id")
        if not operator_id:
            continue
        plane_map[str(operator_id)] = {
            "plane": str(manifest.get("execution_class", "unknown")),
            "version": str(manifest.get("$schema_version", "")),
            "path": str(manifest_path),
        }
    return plane_map


# ----------------------------------------------------------------------------
# Bootstrap (JSON -> SQLite)
# ----------------------------------------------------------------------------


def bootstrap_sqlite_from_json(
    graph_json_path: Path = DEFAULT_GRAPH_JSON_PATH,
    topo_json_path: Path = DEFAULT_TOPO_JSON_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    manifests_dir: Path = MANIFESTS_DIR,
) -> dict[str, int]:
    """Materialise the SQLite mirror from the adjacency-list JSON.

    Safe to call repeatedly: uses ``CREATE TABLE IF NOT EXISTS`` + ``INSERT
    OR REPLACE``. Returns ``{nodes, edges, topo}`` counts for sanity checks.

    Arch §3.1 explicitly pairs ``graph.json`` (the human-readable adjacency
    list) with a SQL store ("SQLite for complex queries"). This function is
    the JSON -> SQL hand-off.
    """
    graph_payload = json.loads(graph_json_path.read_text(encoding="utf-8"))
    topo_payload = json.loads(topo_json_path.read_text(encoding="utf-8"))
    plane_map = _load_manifest_plane_map(manifests_dir)

    operators: dict[str, dict[str, Any]] = graph_payload.get("operators", {})
    if not operators:
        raise ValueError(
            f"{graph_json_path} contains no operators; "
            "run scripts/build_registry_indexes.py first"
        )

    waves: list[list[str]] = topo_payload.get("waves") or []
    if not waves:
        raise ValueError(
            f"{topo_json_path} contains no waves; "
            "run scripts/build_registry_indexes.py first"
        )

    with _connect(sqlite_path) as conn:
        _ensure_schema(conn)

        # Nodes — INSERT OR REPLACE keeps the function idempotent.
        node_rows: list[tuple[str, str, str, str, str]] = []
        for operator_id in sorted(operators):
            manifest_info = plane_map.get(operator_id, {})
            metadata = {
                "upstream": operators[operator_id].get("upstream", []),
                "downstream": operators[operator_id].get("downstream", []),
            }
            node_rows.append(
                (
                    operator_id,
                    manifest_info.get("plane", "unknown"),
                    manifest_info.get("version", ""),
                    manifest_info.get("path", ""),
                    json.dumps(metadata, sort_keys=True),
                )
            )
        conn.executemany(
            """
            INSERT OR REPLACE INTO nodes
                (operator_id, plane, manifest_version, manifest_path, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            node_rows,
        )

        # Edges — clear + reinsert so removed edges in graph.json propagate.
        # The (source, target, dep_type) primary key prevents duplicates; the
        # DELETE keeps the table from drifting if an edge is removed upstream.
        conn.execute("DELETE FROM edges;")
        edge_rows: list[tuple[str, str, str]] = []
        for operator_id, record in operators.items():
            for upstream in record.get("upstream", []):
                # Arch dep table semantics: an "upstream" entry on B means
                # A -> B (A is upstream, B depends_on A). We store the edge
                # from B (source = dependent) to A (target = dependency) with
                # dep_type = "depends_on". This matches graph.json semantics
                # where ``operators[B].upstream`` lists what B depends on.
                edge_rows.append((operator_id, str(upstream), "depends_on"))
            for downstream in record.get("downstream", []):
                # Mirror "feeds" direction for queryability. The (source,
                # target, dep_type) PK keeps this from duplicating with the
                # depends_on rows.
                edge_rows.append((str(downstream), operator_id, "depends_on"))
        # Deduplicate before insert to keep the executemany clean even though
        # the PRIMARY KEY would handle it.
        deduped: list[tuple[str, str, str]] = sorted(set(edge_rows))
        conn.executemany(
            """
            INSERT OR REPLACE INTO edges (source, target, dep_type)
            VALUES (?, ?, ?)
            """,
            deduped,
        )

        # Topological order — depth = wave index (matches arch §6 D0..DN
        # banding); position = index within wave.
        conn.execute("DELETE FROM topological_order;")
        topo_rows: list[tuple[str, int, int]] = []
        for depth, wave in enumerate(waves):
            for position, operator_id in enumerate(wave):
                topo_rows.append((operator_id, depth, position))
        conn.executemany(
            """
            INSERT OR REPLACE INTO topological_order
                (operator_id, depth, position)
            VALUES (?, ?, ?)
            """,
            topo_rows,
        )

        conn.commit()

        counts = {
            "nodes": _scalar(conn, "SELECT COUNT(*) FROM nodes"),
            "edges": _scalar(conn, "SELECT COUNT(*) FROM edges"),
            "topo": _scalar(conn, "SELECT COUNT(*) FROM topological_order"),
        }

    return counts


def _scalar(conn: sqlite3.Connection, query: str) -> int:
    """Single-row, single-column int query helper."""
    row = conn.execute(query).fetchone()
    return int(row[0]) if row is not None else 0


# ----------------------------------------------------------------------------
# Query API
# ----------------------------------------------------------------------------


def query_dependencies(
    operator_id: str,
    direction: str = "upstream",
    transitive: bool = False,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> list[str]:
    """Return operator_ids related to ``operator_id`` in the given direction.

    ``direction="upstream"`` returns operators that ``operator_id`` depends on
    (parents). ``direction="downstream"`` returns operators that depend on
    ``operator_id`` (children).

    ``transitive=True`` follows the dependency edges to closure. Cycles are
    impossible by construction (the JSON is a DAG, validated by the
    topological build) but we guard with a visited set anyway.

    Arch §3.2 names "transitive deps" as the headline reason SQLite was
    selected over JSON for complex queries.
    """
    if direction not in {"upstream", "downstream"}:
        raise ValueError(
            f"direction must be 'upstream' or 'downstream', got {direction!r}"
        )

    with _connect(sqlite_path) as conn:
        _ensure_schema(conn)
        if not transitive:
            rows = _one_hop(conn, operator_id, direction)
            return sorted(rows)

        seen: set[str] = set()
        frontier: deque[str] = deque([operator_id])
        while frontier:
            current = frontier.popleft()
            for neighbour in _one_hop(conn, current, direction):
                if neighbour in seen or neighbour == operator_id:
                    continue
                seen.add(neighbour)
                frontier.append(neighbour)
    return sorted(seen)


def _one_hop(
    conn: sqlite3.Connection,
    operator_id: str,
    direction: str,
) -> list[str]:
    """Direct neighbours of ``operator_id`` in the requested direction.

    Edge semantics (set in ``bootstrap_sqlite_from_json``):
      edges(source=B, target=A, dep_type="depends_on") <=> B depends on A.

    So "upstream of B" (what B depends on) = SELECT target WHERE source=B.
    "downstream of A" (who depends on A) = SELECT source WHERE target=A.
    """
    if direction == "upstream":
        cursor = conn.execute(
            "SELECT target FROM edges WHERE source = ? AND dep_type = 'depends_on'",
            (operator_id,),
        )
    else:
        cursor = conn.execute(
            "SELECT source FROM edges WHERE target = ? AND dep_type = 'depends_on'",
            (operator_id,),
        )
    return [row[0] for row in cursor.fetchall()]


def get_topological_layer(
    depth: int,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> list[str]:
    """Return operator_ids at the given topological depth, ordered by position.

    Depth 0 is the "build first" set (arch §6: zero-dependency operators).
    Depth N is the operators whose deepest upstream sits at depth N-1.
    """
    with _connect(sqlite_path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute(
            """
            SELECT operator_id
            FROM topological_order
            WHERE depth = ?
            ORDER BY position
            """,
            (depth,),
        )
        return [row[0] for row in cursor.fetchall()]


def get_node(
    operator_id: str,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> dict[str, Any] | None:
    """Return the node row (plane, version, path, metadata) for an operator.

    Returns ``None`` if the operator is unknown. Callers wanting "must exist"
    semantics should raise on ``None`` themselves — arch Rule 3 keeps this
    module read-only and side-effect-free outside ``bootstrap_*``.
    """
    with _connect(sqlite_path) as conn:
        _ensure_schema(conn)
        row = conn.execute(
            """
            SELECT operator_id, plane, manifest_version, manifest_path,
                   metadata_json
            FROM nodes
            WHERE operator_id = ?
            """,
            (operator_id,),
        ).fetchone()
    if row is None:
        return None
    metadata: dict[str, Any] = {}
    raw_metadata = row["metadata_json"]
    if raw_metadata:
        try:
            metadata = json.loads(raw_metadata)
        except json.JSONDecodeError:
            metadata = {}
    return {
        "operator_id": row["operator_id"],
        "plane": row["plane"],
        "manifest_version": row["manifest_version"],
        "manifest_path": row["manifest_path"],
        "metadata": metadata,
    }


def list_nodes(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> list[str]:
    """Return all operator_ids in the dependency graph, sorted."""
    with _connect(sqlite_path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute("SELECT operator_id FROM nodes ORDER BY operator_id")
        return [row[0] for row in cursor.fetchall()]


def count_edges(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    """Return the edge count — handy for parity checks vs ``graph.json``."""
    with _connect(sqlite_path) as conn:
        _ensure_schema(conn)
        return _scalar(conn, "SELECT COUNT(*) FROM edges")


def iter_edges(
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> Iterable[tuple[str, str, str]]:
    """Yield (source, target, dep_type) tuples for every edge.

    Used by the verification script for JSON↔SQLite parity checks.
    """
    with _connect(sqlite_path) as conn:
        _ensure_schema(conn)
        cursor = conn.execute(
            "SELECT source, target, dep_type FROM edges ORDER BY source, target, dep_type"
        )
        # Materialise inside the connection scope so the iterator does not
        # outlive the closed connection.
        return [(row[0], row[1], row[2]) for row in cursor.fetchall()]


__all__ = [
    "DEFAULT_GRAPH_JSON_PATH",
    "DEFAULT_SQLITE_PATH",
    "DEFAULT_TOPO_JSON_PATH",
    "bootstrap_sqlite_from_json",
    "count_edges",
    "get_node",
    "get_topological_layer",
    "iter_edges",
    "list_nodes",
    "query_dependencies",
]
