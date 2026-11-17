"""Disk-backed exact-verified grid lookup for CPU-first offline research.

SQLite bounds Python resident memory by streaming row reads. Grid candidates
are only a filter: every returned match is checked by the frozen exact metric.
High-dimensional cases deliberately fall back to a complete streaming scan.
"""
from __future__ import annotations
from contextlib import contextmanager
from itertools import product
import bisect
import json
import math
from pathlib import Path
import sqlite3
from .core import Observation, MetricContract, LocalityError
from .index import IndexedHit


class DiskGridIndex:
    def __init__(self, path: str | Path, metric: MetricContract, radius: float,
                 *, source_identity: str, max_cells: int = 243):
        if not source_identity or not math.isfinite(radius) or radius <= 0 or max_cells < 1:
            raise LocalityError("invalid disk index contract")
        self.metric = metric
        self.radius = radius
        self.source_identity = source_identity
        self.dimensions = tuple(i for i, w in enumerate(metric.weights) if w > 0)
        self.indexed = 3 ** len(self.dimensions) <= max_cells
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=30000")
        with self._tx():
            self.db.execute("CREATE TABLE IF NOT EXISTS index_meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
            self.db.execute("""CREATE TABLE IF NOT EXISTS centers(
                event_id TEXT PRIMARY KEY, identity TEXT NOT NULL,
                family TEXT NOT NULL, direction TEXT,
                clock INTEGER NOT NULL, cell TEXT NOT NULL,
                payload TEXT NOT NULL,
                active INTEGER NOT NULL CHECK(active IN (0,1)),
                reason TEXT
            )""")
            self.db.execute("CREATE INDEX IF NOT EXISTS centers_cell ON centers(cell,family,active)")
            self.db.execute("CREATE INDEX IF NOT EXISTS centers_active ON centers(active,family)")
            config={"source":source_identity,"metric":metric.identity(),
                    "radius":repr(radius),"dimensions":str(self.dimensions),"schema":"1"}
            existing=dict(self.db.execute("SELECT k,v FROM index_meta WHERE k!='revision'"))
            if existing and existing != config:
                raise LocalityError("disk index source/metric/radius mismatch")
            for k,v in config.items():
                self.db.execute("INSERT OR IGNORE INTO index_meta VALUES (?,?)",(k,v))
            self.db.execute("INSERT OR IGNORE INTO index_meta VALUES ('revision','0')")

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

    def __exit__(self, *args):
        self.close()

    @property
    def revision(self):
        return int(self.db.execute("SELECT v FROM index_meta WHERE k='revision'").fetchone()[0])

    @property
    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM centers WHERE active=1").fetchone()[0]

    def _revision_advance(self):
        self.db.execute("UPDATE index_meta SET v=CAST(CAST(v AS INTEGER)+1 AS TEXT) WHERE k='revision'")

    def _cell(self, obs: Observation):
        coords=[]
        vec=self.metric.vector(obs)
        for i in self.dimensions:
            scaled = math.sqrt(self.metric.weights[i]) * vec[i] / self.radius
            if not math.isfinite(scaled):
                raise LocalityError("index coordinate overflow")
            coords.append(math.floor(scaled))
        return tuple(coords)

    @staticmethod
    def _encode(obs: Observation):
        return json.dumps({"event_id":obs.event_id,"family":obs.family,
                           "features":dict(obs.features),"event_clock":obs.event_clock,
                           "provenance":obs.provenance,"order_id":obs.order_id,
                           "member_id":obs.member_id,"direction":obs.direction},
                          sort_keys=True,separators=(",",":"),allow_nan=False)

    @staticmethod
    def _decode(payload: str):
        try:
            return Observation(**json.loads(payload))
        except (TypeError, ValueError, KeyError) as error:
            raise LocalityError("corrupt index observation") from error

    def get(self,event_id: str) -> Observation | None:
        row=self.db.execute("SELECT identity,payload,active FROM centers WHERE event_id=?",(event_id,)).fetchone()
        if row is None or not row[2]:
            return None
        obs=self._decode(row[1])
        if obs.identity()!=row[0]:
            raise LocalityError("index evidence identity mismatch")
        return obs

    def add(self, obs: Observation):
        cell=json.dumps(self._cell(obs),separators=(",",":"))
        identity=obs.identity()
        with self._tx():
            row=self.db.execute("SELECT identity,active FROM centers WHERE event_id=?",
                                (obs.event_id,)).fetchone()
            if row:
                if row[0]!=identity:
                    raise LocalityError("conflicting indexed event identity")
                if not row[1]:
                    raise LocalityError("retired center cannot be reused without restore")
                return "EXISTS"
            self.db.execute("""INSERT INTO centers(event_id,identity,family,direction,clock,
                cell,payload,active) VALUES (?,?,?,?,?,?,?,1)""",
                (obs.event_id,identity,obs.family,obs.direction,obs.event_clock,
                 cell,self._encode(obs)))
            self._revision_advance()
        return "ADDED"

    def retire(self, center_id: str, reason: str):
        if not reason:
            raise LocalityError("retirement reason required")
        with self._tx():
            count=self.db.execute("""UPDATE centers SET active=0,reason=?
                 WHERE event_id=? AND active=1""",(reason,center_id)).rowcount
            if count!=1:
                raise LocalityError("center missing or already retired")
            self._revision_advance()

    def restore(self, obs: Observation):
        with self._tx():
            row=self.db.execute("SELECT identity,active FROM centers WHERE event_id=?",
                                (obs.event_id,)).fetchone()
            if row is None or row[1] or row[0]!=obs.identity():
                raise LocalityError("original retired evidence required")
            self.db.execute("""UPDATE centers SET active=1,reason=NULL
                WHERE event_id=?""",(obs.event_id,))
            self._revision_advance()

    def candidates(self, obs: Observation, *, max_neighbors: int = 64,
                   allow_cross_family: bool = False, same_direction: bool = True,
                   historical_only: bool = True) -> tuple[IndexedHit, ...]:
        if type(max_neighbors) is not int or not 1 <= max_neighbors <= 4096:
            raise LocalityError("bounded neighbor count must be 1..4096")
        cell=self._cell(obs)
        clauses=["active=1"]
        params=[]
        if not allow_cross_family:
            clauses.append("family=?")
            params.append(obs.family)
        if same_direction:
            clauses.append("direction IS ?")
            params.append(obs.direction)
        if historical_only:
            clauses.append("clock<=?")
            params.append(obs.event_clock)
        base=" AND ".join(clauses)
        if self.indexed:
            cells=[json.dumps(tuple(a+b for a,b in zip(cell,offsets)),separators=(",",":"))
                   for offsets in product((-1,0,1),repeat=len(cell))]
        else:
            cells=None

        ordered=[]
        def process(cursor):
            while True:
                rows=cursor.fetchmany(128)
                if not rows:
                    break
                for evidence_id, encoded in rows:
                    center=self._decode(encoded)
                    if center.identity()!=evidence_id:
                        raise LocalityError("index read identity mismatch")
                    distance=self.metric.distance(obs,center)
                    if distance>self.radius:
                        continue
                    candidate=(distance,center.event_id,IndexedHit(center.event_id,distance,evidence_id))
                    bisect.insort(ordered,candidate)
                    if len(ordered)>max_neighbors:
                        ordered.pop()

        if cells is None:
            process(self.db.execute("SELECT identity,payload FROM centers WHERE "+base,
                                    params))
        else:
            for begin in range(0,len(cells),100):
                batch=cells[begin:begin+100]
                sql="SELECT identity,payload FROM centers WHERE "+base+" AND cell IN (" + (
                    ",".join("?" for _ in batch)) + ")"
                process(self.db.execute(sql,params+batch))
        return tuple(row[2] for row in ordered)

    def snapshot(self):
        return {"schema":1,"source_identity":self.source_identity,
                "metric_identity":self.metric.identity(),"radius":self.radius,
                "revision":self.revision,"active_centers":self.count,
                "retired_centers":self.db.execute(
                    "SELECT COUNT(*) FROM centers WHERE active=0").fetchone()[0],
                "grid_accelerated":self.indexed,
                "scientific_jobs_eliminated":0}
