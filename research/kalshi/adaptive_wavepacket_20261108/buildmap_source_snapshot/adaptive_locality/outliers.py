"""Lossless outlier review registry; never a filter for scientific evidence.

Flagged events remain individually addressable, original and non-aggregated.
'Quarantine' pauses only a SHADOW grouping decision; no production jobs exist here.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from .core import Observation, LocalityError, _digest


@dataclass(frozen=True)
class OutlierRecord:
    event_id: str
    evidence_identity: str
    reason: str
    review_state: str
    source_identity: str


class OutlierRegistry:
    """Transactional review registry, with immutable full original event payloads."""
    def __init__(self, path: str | Path, *, source_identity: str):
        if not source_identity:
            raise LocalityError("source identity required")
        self.source_identity = source_identity
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        with self._tx():
            self.db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
            self.db.execute("""CREATE TABLE IF NOT EXISTS evidence(
                event_id TEXT PRIMARY KEY,identity TEXT NOT NULL,
                source_identity TEXT NOT NULL,payload TEXT NOT NULL,
                reason TEXT NOT NULL,review_state TEXT NOT NULL,
                last_review TEXT NOT NULL DEFAULT ''
            )""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS history(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL,
                action TEXT NOT NULL,reason TEXT NOT NULL,reviewer TEXT NOT NULL,
                previous_hash TEXT NOT NULL,entry_hash TEXT NOT NULL
            )""")
            previous=self.db.execute("SELECT v FROM meta WHERE k='source'").fetchone()
            if previous and previous[0]!=source_identity:
                raise LocalityError("outlier source mismatch")
            self.db.execute("INSERT OR IGNORE INTO meta VALUES ('source',?)",(source_identity,))

    @contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _append(self, event_id, action, reason, reviewer):
        previous=self.db.execute(
            "SELECT entry_hash FROM history ORDER BY sequence DESC LIMIT 1").fetchone()
        parent=previous[0] if previous else "GENESIS"
        entry=_digest({"event_id":event_id,"action":action,"reason":reason,
                       "reviewer":reviewer,"previous":parent})
        self.db.execute("""INSERT INTO history(event_id,action,reason,reviewer,
            previous_hash,entry_hash) VALUES (?,?,?,?,?,?)""",
            (event_id,action,reason,reviewer,parent,entry))

    @staticmethod
    def _payload(obs):
        return json.dumps({"event_id":obs.event_id,"family":obs.family,
                           "features":dict(obs.features),"event_clock":obs.event_clock,
                           "provenance":obs.provenance,"order_id":obs.order_id,
                           "member_id":obs.member_id,"direction":obs.direction},
                          sort_keys=True,separators=(",",":"),allow_nan=False)

    def flag(self, observation: Observation, reason: str, reviewer: str = "shadow-validator"):
        if not reason or not reviewer:
            raise LocalityError("explicit outlier reason/reviewer required")
        identity=observation.identity()
        payload=self._payload(observation)
        with self._tx():
            existing=self.db.execute(
                "SELECT identity,payload FROM evidence WHERE event_id=?",
                (observation.event_id,)).fetchone()
            if existing:
                if existing != (identity,payload):
                    raise LocalityError("conflicting original outlier evidence")
                return "ALREADY_RETAINED"
            self.db.execute("""INSERT INTO evidence(event_id,identity,source_identity,payload,
                reason,review_state) VALUES (?,?,?,?,?,'AWAITING_REVIEW')""",
                (observation.event_id,identity,self.source_identity,payload,reason))
            self._append(observation.event_id,"FLAG_FOR_REVIEW",reason,reviewer)
            return "RETAINED_FOR_REVIEW"

    def get(self, event_id: str) -> tuple[Observation, OutlierRecord]:
        row=self.db.execute("""SELECT identity,source_identity,payload,reason,review_state
            FROM evidence WHERE event_id=?""",(event_id,)).fetchone()
        if not row:
            raise LocalityError("outlier not found")
        identity,source,payload,reason,state=row
        if source!=self.source_identity:
            raise LocalityError("outlier source mismatch")
        obs=Observation(**json.loads(payload))
        if obs.identity()!=identity:
            raise LocalityError("outlier evidence corrupted")
        return obs,OutlierRecord(event_id,identity,reason,state,source)

    def review(self, event_id: str, *, state: str, reason: str, reviewer: str):
        if state not in ("UNDER_REVIEW","RETAIN_SEPARATE","RELEASE_SHADOW_GROUPING"):
            raise LocalityError("invalid review state")
        if not reason or not reviewer:
            raise LocalityError("review explanation and reviewer required")
        with self._tx():
            if not self.db.execute("SELECT 1 FROM evidence WHERE event_id=?",
                                   (event_id,)).fetchone():
                raise LocalityError("unknown outlier")
            self.db.execute("""UPDATE evidence SET review_state=?,last_review=?
                WHERE event_id=?""",(state,reason,event_id))
            self._append(event_id,state,reason,reviewer)

    def counts(self):
        rows=self.db.execute("SELECT review_state,COUNT(*) FROM evidence GROUP BY review_state").fetchall()
        return {"retained_total":sum(count for _,count in rows),
                "states":dict(rows),"discarded":0,"averaged":0,"flattened":0}

    def verify(self):
        rows=self.db.execute("""SELECT event_id,identity,payload FROM evidence
            ORDER BY event_id""").fetchall()
        for event_id,identity,payload in rows:
            obs=Observation(**json.loads(payload))
            if obs.event_id!=event_id or obs.identity()!=identity:
                raise LocalityError("outlier evidence integrity failure")
        parent="GENESIS"
        for event_id,action,reason,reviewer,previous,h in self.db.execute(
                """SELECT event_id,action,reason,reviewer,previous_hash,entry_hash
                   FROM history ORDER BY sequence"""):
            expected=_digest({"event_id":event_id,"action":action,"reason":reason,
                              "reviewer":reviewer,"previous":parent})
            if previous!=parent or h!=expected:
                raise LocalityError("outlier review history corrupted")
            parent=h
        return True
