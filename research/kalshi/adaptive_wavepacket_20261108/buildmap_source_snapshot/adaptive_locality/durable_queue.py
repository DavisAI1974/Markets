"""Local SQLite transactional shadow scheduler; never executes external jobs.

Single SQLite database, atomic IMMEDIATE transactions, expiry-fenced lease tokens,
WAL/full-sync durability. A SQLite lease does not provide distributed fencing for
real-world side effects: production execution is explicitly unsupported.
"""
from __future__ import annotations
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import uuid
import math
from .core import LocalityError
from .queue import ReadyGroup


class DurableShadowQueue:
    def __init__(self, path: str | Path, *, source_identity: str,
                 contract_identity: str, capacity: int = 1024):
        if not source_identity or not contract_identity or type(capacity) is not int or capacity < 1:
            raise LocalityError("invalid durable queue contract")
        self.path = Path(path)
        self.source_identity = source_identity
        self.contract_identity = contract_identity
        self.capacity = capacity
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        with self._tx():
            self.db.execute("CREATE TABLE IF NOT EXISTS metadata (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
            self.db.execute("""CREATE TABLE IF NOT EXISTS groups (
                group_id TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('pending','leased','completed')),
                lease_token TEXT, lease_until REAL, attempts INTEGER NOT NULL DEFAULT 0,
                result_identity TEXT
            )""")
            configuration = {"source_identity": source_identity,
                             "contract_identity": contract_identity, "capacity": str(capacity),
                             "schema": "1"}
            existing = dict(self.db.execute("SELECT k, v FROM metadata"))
            if existing and existing != configuration:
                raise LocalityError("incompatible queue source/contract/capacity")
            for key, value in configuration.items():
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES (?, ?)", (key, value))

    @contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def submit(self, group: ReadyGroup) -> str:
        if group.source_identity != self.source_identity:
            raise LocalityError("queue/source identity mismatch")
        payload = json.dumps(group.__dict__, sort_keys=True, separators=(",", ":"))
        digest = group.identity()
        with self._tx():
            existing = self.db.execute(
                "SELECT digest,state FROM groups WHERE group_id=?", (group.group_id,)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise LocalityError("conflicting group ID")
                return "ALREADY_COMPLETED" if existing[1] == "completed" else "ALREADY_PENDING"
            active = self.db.execute(
                "SELECT COUNT(*) FROM groups WHERE state != 'completed'").fetchone()[0]
            if active >= self.capacity:
                return "BACKPRESSURE"
            self.db.execute("INSERT INTO groups (group_id,digest,payload,state) VALUES (?,?,?,'pending')",
                            (group.group_id, digest, payload))
            return "QUEUED"

    def lease(self, *, now: float, duration: float) -> tuple[ReadyGroup, str] | None:
        if not all(math.isfinite(x) for x in (now, duration)) or duration <= 0:
            raise LocalityError("invalid lease clock/duration")
        with self._tx():
            self.db.execute("""UPDATE groups SET state='pending',lease_token=NULL,lease_until=NULL
                WHERE state='leased' AND lease_until<=?""", (now,))
            row = self.db.execute("""SELECT group_id,payload FROM groups
                WHERE state='pending' ORDER BY group_id LIMIT 1""").fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            self.db.execute("""UPDATE groups SET state='leased',lease_token=?,lease_until=?,
                attempts=attempts+1 WHERE group_id=? AND state='pending'""",
                (token, now + duration, row[0]))
            raw = json.loads(row[1])
            return ReadyGroup(**{**raw, "evidence_ids": tuple(raw["evidence_ids"])}), token

    def complete(self, group_id: str, lease_token: str, *, now: float,
                 verified_identity: str, result_identity: str) -> str:
        if not math.isfinite(now) or not lease_token or not result_identity:
            raise LocalityError("missing completion validation")
        with self._tx():
            row = self.db.execute("""SELECT digest,state,lease_token,lease_until,result_identity
                FROM groups WHERE group_id=?""", (group_id,)).fetchone()
            if row is None:
                raise LocalityError("unknown group")
            digest, state, token, deadline, result = row
            if digest != verified_identity:
                raise LocalityError("group identity mismatch")
            if state == "completed":
                if result != result_identity:
                    raise LocalityError("conflicting completed result")
                return "ALREADY_COMPLETED"
            if state != "leased" or token != lease_token or deadline <= now:
                raise LocalityError("expired or fenced lease")
            self.db.execute("""UPDATE groups SET state='completed',lease_token=NULL,
                lease_until=NULL,result_identity=? WHERE group_id=?""", (result_identity, group_id))
            return "COMPLETED"

    def retry(self, group_id: str, lease_token: str, *, now: float) -> None:
        if not math.isfinite(now):
            raise LocalityError("invalid clock")
        with self._tx():
            row = self.db.execute("SELECT state,lease_token,lease_until FROM groups WHERE group_id=?",
                                  (group_id,)).fetchone()
            if row is None or row[0] != "leased" or row[1] != lease_token or row[2] <= now:
                raise LocalityError("stale retry lease")
            self.db.execute("""UPDATE groups SET state='pending',
                lease_token=NULL,lease_until=NULL WHERE group_id=?""", (group_id,))

    def snapshot(self) -> dict:
        rows = self.db.execute("""SELECT group_id,digest,state,attempts,result_identity
            FROM groups ORDER BY group_id""").fetchall()
        return {"schema": 1, "source_identity": self.source_identity,
                "contract_identity": self.contract_identity,
                "capacity": self.capacity,
                "groups": [dict(zip(("group_id", "digest", "state", "attempts",
                                      "result_identity"), r)) for r in rows],
                "scientific_jobs_eliminated": 0}
