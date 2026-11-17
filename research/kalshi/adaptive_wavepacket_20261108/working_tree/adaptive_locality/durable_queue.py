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


GROUPS_SCHEMA = """CREATE TABLE IF NOT EXISTS groups (
                group_id TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('pending','leased','completed','exhausted')),
                lease_token TEXT, lease_until REAL, attempts INTEGER NOT NULL DEFAULT 0,
                result_identity TEXT, last_reason TEXT
            )"""


class DurableShadowQueue:
    def __init__(self, path: str | Path, *, source_identity: str,
                 contract_identity: str, capacity: int = 1024, max_attempts: int = 8):
        if not source_identity or not contract_identity or type(capacity) is not int or capacity < 1:
            raise LocalityError("invalid durable queue contract")
        if type(max_attempts) is not int or max_attempts < 1:
            raise LocalityError("max_attempts must be a positive integer")
        self.path = Path(path)
        self.source_identity = source_identity
        self.contract_identity = contract_identity
        self.capacity = capacity
        self.max_attempts = max_attempts
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        with self._tx():
            self.db.execute("CREATE TABLE IF NOT EXISTS metadata (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
            self.db.execute(GROUPS_SCHEMA)
            self._migrate_groups_table()
            # E-5: every submit/lease/expire/retry/complete/exhaust keeps its reason here.
            self.db.execute("""CREATE TABLE IF NOT EXISTS history (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT NOT NULL,
                action TEXT NOT NULL, reason TEXT NOT NULL, now REAL,
                token_prefix TEXT NOT NULL DEFAULT ''
            )""")
            self.db.execute("CREATE INDEX IF NOT EXISTS history_group ON history(group_id, seq)")
            configuration = {"source_identity": source_identity,
                             "contract_identity": contract_identity, "capacity": str(capacity),
                             "schema": "1"}
            existing = dict(self.db.execute("SELECT k, v FROM metadata WHERE k != 'max_attempts'"))
            if existing and existing != configuration:
                raise LocalityError("incompatible queue source/contract/capacity")
            for key, value in configuration.items():
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES (?, ?)", (key, value))
            # The retry cap is an operating policy of the opener, recorded but not a compatibility key.
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES ('max_attempts', ?)", (str(max_attempts),))

    def _migrate_groups_table(self) -> None:
        """Rebuild a pre-E-5 groups table (no 'exhausted' state / last_reason) losslessly."""
        sql = self.db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='groups'").fetchone()[0]
        if "'exhausted'" in sql and "last_reason" in sql:
            return
        self.db.execute(GROUPS_SCHEMA.replace("CREATE TABLE IF NOT EXISTS groups", "CREATE TABLE groups_e5"))
        self.db.execute("""INSERT INTO groups_e5 (group_id,digest,payload,state,lease_token,lease_until,
            attempts,result_identity) SELECT group_id,digest,payload,state,lease_token,lease_until,
            attempts,result_identity FROM groups""")
        self.db.execute("DROP TABLE groups")
        self.db.execute("ALTER TABLE groups_e5 RENAME TO groups")

    def _record(self, group_id: str, action: str, reason: str, now: float | None, token: str | None = None) -> None:
        self.db.execute("INSERT INTO history (group_id, action, reason, now, token_prefix) VALUES (?,?,?,?,?)",
                        (group_id, action, reason, now, (token or "")[:8]))

    def _release(self, group_id: str, attempts: int, reason: str, now: float, token: str | None) -> None:
        """Return a leased row to 'pending', or retain it as 'exhausted' once attempts reach the cap."""
        if attempts >= self.max_attempts:
            self.db.execute("""UPDATE groups SET state='exhausted', lease_token=NULL, lease_until=NULL,
                last_reason=? WHERE group_id=?""", (reason, group_id))
            self._record(group_id, "EXHAUST",
                         f"attempts {attempts} reached max_attempts {self.max_attempts}; last reason: {reason}",
                         now, token)
        else:
            self.db.execute("""UPDATE groups SET state='pending', lease_token=NULL, lease_until=NULL,
                last_reason=? WHERE group_id=?""", (reason, group_id))

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
                if existing[1] == "completed":
                    return "ALREADY_COMPLETED"
                if existing[1] == "exhausted":
                    return "EXHAUSTED"
                return "ALREADY_PENDING"
            active = self.db.execute(
                "SELECT COUNT(*) FROM groups WHERE state NOT IN ('completed','exhausted')").fetchone()[0]
            if active >= self.capacity:
                return "BACKPRESSURE"
            self.db.execute("INSERT INTO groups (group_id,digest,payload,state) VALUES (?,?,?,'pending')",
                            (group.group_id, digest, payload))
            self._record(group.group_id, "SUBMIT", "queued shadow group", None)
            return "QUEUED"

    def lease(self, *, now: float, duration: float) -> tuple[ReadyGroup, str] | None:
        if not all(math.isfinite(x) for x in (now, duration)) or duration <= 0:
            raise LocalityError("invalid lease clock/duration")
        with self._tx():
            expired = self.db.execute("""SELECT group_id,lease_token,lease_until,attempts FROM groups
                WHERE state='leased' AND lease_until<=? ORDER BY group_id""", (now,)).fetchall()
            for group_id, old_token, deadline, attempts in expired:
                reason = f"lease expired at {deadline!r} (swept at now={now!r})"
                self._record(group_id, "EXPIRE", reason, now, old_token)
                self._release(group_id, attempts, reason, now, old_token)
            row = self.db.execute("""SELECT group_id,payload FROM groups
                WHERE state='pending' ORDER BY group_id LIMIT 1""").fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            self.db.execute("""UPDATE groups SET state='leased',lease_token=?,lease_until=?,
                attempts=attempts+1 WHERE group_id=? AND state='pending'""",
                (token, now + duration, row[0]))
            self._record(row[0], "LEASE", f"leased until {now + duration!r}", now, token)
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
            self._record(group_id, "COMPLETE", f"result identity {result_identity}", now, lease_token)
            return "COMPLETED"

    def retry(self, group_id: str, lease_token: str, *, now: float, reason: str) -> None:
        """E-5: a retry must say why; the reason is kept in history and on the row."""
        if not math.isfinite(now):
            raise LocalityError("invalid clock")
        if not isinstance(reason, str) or not reason:
            raise LocalityError("retry reason required")
        with self._tx():
            row = self.db.execute("SELECT state,lease_token,lease_until,attempts FROM groups WHERE group_id=?",
                                  (group_id,)).fetchone()
            if row is None or row[0] != "leased" or row[1] != lease_token or row[2] <= now:
                raise LocalityError("stale retry lease")
            self._record(group_id, "RETRY", reason, now, lease_token)
            self._release(group_id, row[3], reason, now, lease_token)

    def history(self, group_id: str | None = None) -> tuple[dict, ...]:
        """E-5: the action history, oldest first, for one group or for all."""
        if group_id is None:
            rows = self.db.execute("SELECT seq,group_id,action,reason,now,token_prefix FROM history ORDER BY seq").fetchall()
        else:
            rows = self.db.execute("""SELECT seq,group_id,action,reason,now,token_prefix FROM history
                WHERE group_id=? ORDER BY seq""", (group_id,)).fetchall()
        return tuple(dict(zip(("seq", "group_id", "action", "reason", "now", "token_prefix"), r)) for r in rows)

    def snapshot(self) -> dict:
        rows = self.db.execute("""SELECT group_id,digest,state,attempts,result_identity,lease_until,last_reason
            FROM groups ORDER BY group_id""").fetchall()
        return {"schema": 1, "source_identity": self.source_identity,
                "contract_identity": self.contract_identity,
                "capacity": self.capacity, "max_attempts": self.max_attempts,
                "groups": [dict(zip(("group_id", "digest", "state", "attempts",
                                      "result_identity", "lease_until", "last_reason"), r)) for r in rows],
                "scientific_jobs_eliminated": 0}
