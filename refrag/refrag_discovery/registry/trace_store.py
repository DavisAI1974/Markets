"""
SQLite-backed execution trace store (arch §3.2).

Replaces the JSONL append-only file at ``artifacts/execution_traces.jsonl`` with
a SQLite database at ``artifacts/execution_traces.sqlite``. Per arch §3.2:

    Execution traces — SQLite (append-only)
    Structured, queryable, supports aggregate analysis for manifest_synthesizer
    and benchmark suite.

Why SQLite (not JSONL)
----------------------
1. **Concurrent writers don't corrupt each other.** JSONL relies on
   OS-level atomic-append, which only guarantees atomicity up to ~4 KB (Windows
   FILE_APPEND_DATA / POSIX PIPE_BUF). Larger writes can interleave under
   concurrency. SQLite serializes transactions, so concurrent orchestrator
   processes are safe at any payload size.
2. **Crash safety per transaction.** A SIGKILL mid-INSERT either commits or
   rolls back atomically. JSONL leaves you with a half-written line that the
   reader has to defensively skip (or fail on).
3. **Structured queries.** The main reader (markets_refrag_adapter Phase 4
   manifest_synthesizer call) currently does ``tail -200 | json.loads each``.
   That becomes ``SELECT payload_json FROM traces ORDER BY ts DESC LIMIT 200``
   — same shape, no Python parsing loop, and indexable per-domain or
   per-pipeline as readers evolve.

WAL journaling
--------------
``journal_mode=WAL`` lets readers (e.g. control-plane synthesis) execute
concurrently with the runtime writer (orchestrator). Without WAL, every read
would block on the writer's transaction. The arch doc doesn't prescribe a
journal mode but WAL is the only choice that satisfies the implied
"reader-friendly while runtime is writing" requirement of §3.3.

API
---
* ``append_trace(trace)`` — orchestrator writes one trace per pipeline run.
* ``recent_traces(limit=200)`` — adapter pulls the most recent N for pattern
  mining. Returns full dicts (drop-in shape for the old ``execution_logs``).
* ``recent_traces_by_domain(domain, limit)`` — future-proof for per-domain mining.
* ``count()`` — verification.
* ``migrate_jsonl(jsonl_path)`` — one-shot backfill from the legacy JSONL file.

CLI
---
    python -m refrag_discovery.registry.trace_store migrate
        Backfills artifacts/execution_traces.jsonl into the SQLite store.
    python -m refrag_discovery.registry.trace_store count
        Prints the row count.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

# Repo root resolution: this file is at refrag_discovery/registry/trace_store.py
# so the refrag/ root is three parents up. Artifacts dir lives at the root.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
DEFAULT_DB_PATH = _REPO_ROOT / "artifacts" / "execution_traces.sqlite"
LEGACY_JSONL_PATH = _REPO_ROOT / "artifacts" / "execution_traces.jsonl"

# Schema. ``payload_json`` keeps the full trace verbatim — the indexed columns
# are denormalized copies for query efficiency, not the source of truth. If a
# trace's shape evolves, only the indexed columns need a migration; payload
# always round-trips losslessly.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    run_id                TEXT PRIMARY KEY,
    ts_ms                 INTEGER NOT NULL,    -- Unix epoch ms at append time
    pipeline_id           TEXT NOT NULL,
    domain                TEXT NOT NULL,
    termination_condition TEXT,
    closed_loop_iterations INTEGER,
    total_wall_time_ms    REAL,
    discovery_recorded    INTEGER,             -- 0/1; SQLite has no BOOL
    payload_json          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_traces_ts        ON traces(ts_ms DESC);
CREATE INDEX IF NOT EXISTS idx_traces_domain    ON traces(domain, ts_ms DESC);
CREATE INDEX IF NOT EXISTS idx_traces_pipeline  ON traces(pipeline_id, ts_ms DESC);
"""


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with WAL + foreign_keys, ensure schema exists."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    # WAL = readers don't block on writer (arch §3.3 implied requirement).
    conn.execute("PRAGMA journal_mode=WAL")
    # Synchronous=NORMAL is the WAL-mode sweet spot: durability per checkpoint,
    # not per transaction. For an append-only trace log this is the right trade
    # — a crash loses the last unflushed transactions, never corrupts the DB.
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(_SCHEMA)
    return conn


def _row_from_trace(trace: dict, ts_ms: int | None = None) -> tuple:
    """Project an in-memory trace dict to the (positional) tuple the INSERT expects."""
    return (
        trace["run_id"],
        ts_ms if ts_ms is not None else int(time.time() * 1000),
        trace.get("pipeline_id", ""),
        trace.get("domain", ""),
        trace.get("termination_condition"),
        trace.get("closed_loop_iterations"),
        trace.get("total_wall_time_ms"),
        1 if trace.get("discovery_recorded") else 0,
        json.dumps(trace, separators=(",", ":")),
    )


_INSERT_SQL = """
INSERT OR REPLACE INTO traces
    (run_id, ts_ms, pipeline_id, domain, termination_condition,
     closed_loop_iterations, total_wall_time_ms, discovery_recorded, payload_json)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def append_trace(trace: dict, db_path: Path | None = None) -> None:
    """Insert a single trace. INSERT OR REPLACE for run_id idempotency.

    Replaces the JSONL ``os.write(fd, json.dumps(trace) + b"\\n")`` pattern
    in operator_orchestrator. Open-per-call is fine — the orchestrator writes
    one trace per pipeline run, and SQLite connection overhead is microseconds
    against pipeline runtimes measured in seconds.
    """
    if "run_id" not in trace:
        raise ValueError("trace missing required field 'run_id'")
    conn = _connect(db_path)
    try:
        conn.execute(_INSERT_SQL, _row_from_trace(trace))
        conn.commit()
    finally:
        conn.close()


def recent_traces(limit: int = 200, db_path: Path | None = None) -> list[dict]:
    """Return the N most recent traces as dicts, newest first.

    Drop-in replacement for the adapter's ``execution_logs[-200:]`` pattern.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM traces ORDER BY ts_ms DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(r[0]) for r in rows]


def recent_traces_by_domain(
    domain: str, limit: int = 200, db_path: Path | None = None
) -> list[dict]:
    """Recent traces filtered to a single domain. Newest first.

    Not used today but cheap to expose now — manifest_synthesizer is likely
    to want per-domain mining once cross_domain_transfer_detector matures.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM traces "
            "WHERE domain = ? ORDER BY ts_ms DESC LIMIT ?",
            (domain, limit),
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(r[0]) for r in rows]


def count(db_path: Path | None = None) -> int:
    """Total number of traces in the store."""
    conn = _connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
    finally:
        conn.close()


def migrate_jsonl(
    jsonl_path: Path | None = None,
    db_path: Path | None = None,
    batch_size: int = 500,
) -> dict:
    """Backfill an existing JSONL trace file into the SQLite store.

    Idempotent: ``INSERT OR REPLACE`` on the run_id primary key means re-running
    is safe. Returns a summary dict with parsed/inserted/skipped counts.

    Timestamps for migrated traces are synthesized from file order — the JSONL
    line index becomes the relative ordering. We anchor against the JSONL
    file's mtime so migrated traces land BEFORE any newly-appended ones, and
    space them 1 ms apart so they sort stably.
    """
    src = jsonl_path or LEGACY_JSONL_PATH
    if not src.exists():
        return {"status": "skipped", "reason": f"no JSONL at {src}"}

    # Anchor: file mtime minus (N lines × 1 ms). Earliest line gets the
    # oldest synthetic ts, latest line gets ts just before mtime.
    file_mtime_ms = int(src.stat().st_mtime * 1000)
    with src.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    n_lines = len(lines)
    base_ts_ms = file_mtime_ms - n_lines

    parsed = 0
    skipped_malformed = 0
    skipped_missing_run_id = 0

    conn = _connect(db_path)
    try:
        batch: list[tuple] = []
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                trace = json.loads(line)
            except json.JSONDecodeError:
                skipped_malformed += 1
                continue
            if "run_id" not in trace:
                skipped_missing_run_id += 1
                continue
            batch.append(_row_from_trace(trace, ts_ms=base_ts_ms + idx))
            parsed += 1
            if len(batch) >= batch_size:
                conn.executemany(_INSERT_SQL, batch)
                conn.commit()
                batch.clear()
        if batch:
            conn.executemany(_INSERT_SQL, batch)
            conn.commit()
        final_count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
    finally:
        conn.close()

    return {
        "status": "ok",
        "source": str(src),
        "destination": str(db_path or DEFAULT_DB_PATH),
        "lines_read": n_lines,
        "parsed": parsed,
        "skipped_malformed": skipped_malformed,
        "skipped_missing_run_id": skipped_missing_run_id,
        "final_row_count": final_count,
    }


def _cli() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "migrate":
        result = migrate_jsonl()
        print(json.dumps(result, indent=2))
        return 0
    if cmd == "count":
        print(count())
        return 0
    if cmd == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        for t in recent_traces(limit=limit):
            print(f"  {t['run_id']}  {t.get('domain')}  {t.get('termination_condition')}")
        return 0
    print(f"unknown command: {cmd!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
