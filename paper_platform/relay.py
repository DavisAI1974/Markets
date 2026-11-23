"""Read-only phone dashboard with an authenticated ingest route for the Actions runner."""

import asyncio
import base64
import json
import os
import secrets
import sqlite3


from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .rulebook import catalogue
from .market import markets
from .views import card, page


class Packet(BaseModel):
    event: dict
    status: dict


def relay():
    reader = os.environ["PAPER_VIEW_PASSWORD"]
    writer = os.environ["PAPER_RELAY_TOKEN"]
    if not reader or not writer or reader == writer:
        raise ValueError("set separate dashboard and runner credentials")
    basic = "Basic " + base64.b64encode(("greg:" + reader).encode()).decode()
    dbfile = os.environ.get("PAPER_RELAY_DB", "/tmp/ng-paper-events.sqlite")

    def connect():
        return sqlite3.connect(dbfile, timeout=10)

    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS events(run TEXT, sequence INTEGER, body TEXT NOT NULL,
                PRIMARY KEY(run,sequence));
            CREATE TABLE IF NOT EXISTS sessions(run TEXT PRIMARY KEY, body TEXT NOT NULL, first_ns TEXT NOT NULL);
        """)

    def viewer(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization.encode(), basic.encode()):
            raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="NG paper dashboard"'})

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health():
        return {"ready": True}

    @app.post("/ingest")
    def ingest(packet: Packet, authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization.encode(), ("Bearer " + writer).encode()):
            raise HTTPException(403)
        event, status = packet.event, packet.status
        run = event.get("run")
        seq = event.get("sequence")
        if (
            not isinstance(run, str)
            or not run
            or type(seq) is not int
            or seq < 0
            or status.get("run") != run
            or event.get("market") not in markets()
            or status.get("market") != event["market"]
            or type(event.get("recorded_ns")) not in (str, int)
        ):
            raise HTTPException(422, "invalid session or sequence")
        body = json.dumps(event, sort_keys=True, separators=(",", ":"))
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT body FROM events WHERE run=? AND sequence=?", (run, seq)).fetchone()
            if old:
                if old[0] != body:
                    raise HTTPException(409, "sequence collision")
                return {"next": seq + 1}
            latest = db.execute("SELECT MAX(sequence) FROM events WHERE run=?", (run,)).fetchone()[0]
            expected = 0 if latest is None else latest + 1
            if expected != seq:
                raise HTTPException(409, detail={"next": expected})
            db.execute("INSERT INTO events VALUES(?,?,?)", (run, seq, body))
            db.execute(
                "INSERT INTO sessions VALUES(?,?,?) ON CONFLICT(run) DO UPDATE SET body=excluded.body",
                (run, json.dumps(status), str(event["recorded_ns"])),
            )
        return {"next": seq + 1}

    def selected(db, run, market):
        if run:
            row = db.execute(
                "SELECT run FROM sessions WHERE run=? AND json_extract(body,'$.market')=?", (run, market)
            ).fetchone()
        else:
            row = db.execute(
                "SELECT run FROM sessions WHERE json_extract(body,'$.market')=? ORDER BY first_ns DESC LIMIT 1",
                (market,),
            ).fetchone()
        return row[0] if row else None

    @app.get("/api/session", dependencies=[Depends(viewer)])
    def status(run: str | None = None, market: str = "nymex-ng"):
        with connect() as db:
            row = db.execute("SELECT body FROM sessions WHERE run=?", (selected(db, run, market),)).fetchone()
        return json.loads(row[0]) if row else {"status": "Waiting for a session", "events": 0}

    @app.get("/api/markets", dependencies=[Depends(viewer)])
    def market_list():
        return markets()

    @app.get("/api/rules", dependencies=[Depends(viewer)])
    def rules(market: str = "nymex-ng"):
        profiles = markets()
        if market not in profiles:
            raise HTTPException(404, "unknown market")
        all_rules = catalogue()
        return {k: all_rules[k] for k in profiles[market]["rules"]}

    def stream_rows(after, rule, follow, run, market, html):
        profiles = markets()
        if market not in profiles or rule and rule not in profiles[market]["rules"]:
            raise HTTPException(404, "unknown market or rule")
        profile = profiles[market]

        async def rows():
            cursor, current = after, run
            while True:
                with connect() as db:
                    current = selected(db, current, market)
                    batch = db.execute(
                        "SELECT sequence,body FROM events WHERE run=? AND sequence>? ORDER BY sequence LIMIT 256",
                        (current, cursor),
                    ).fetchall()
                    saved = db.execute("SELECT body FROM sessions WHERE run=?", (current,)).fetchone()
                state = json.loads(saved[0]) if saved else {}
                for cursor, body in batch:
                    event = json.loads(body)
                    if rule and event.get("rule") != rule:
                        continue
                    if html:
                        data = json.dumps(dict(html=card(event, profile), status=state["status"]))
                        yield f"id: {current}/{cursor}\nevent: message\ndata: {data}\n\n"
                    else:
                        yield body + "\n"
                if len(batch) == 256:
                    continue
                if not follow or state and state["status"] != "active":
                    if html:
                        yield "event: finished\ndata: {}\n\n"
                    return
                await asyncio.sleep(0.1)

        return StreamingResponse(
            rows(),
            media_type="text/event-stream" if html else "application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/events", dependencies=[Depends(viewer)])
    def events(
        after: int = -1,
        rule: str | None = None,
        follow: bool = False,
        run: str | None = None,
        market: str = "nymex-ng",
    ):
        return stream_rows(after, rule, follow, run, market, False)

    @app.get("/stream", dependencies=[Depends(viewer)])
    def stream(
        after: int = -1,
        rule: str = "",
        run: str = "",
        market: str = "nymex-ng",
        last_event_id: str | None = Header(default=None),
    ):
        if last_event_id:
            prior, _, seq = last_event_id.partition("/")
            if not seq.isdigit() or run and run != prior:
                raise HTTPException(400, "invalid stream cursor")
            after, run = max(after, int(seq)), prior
        return stream_rows(after, rule, True, run, market, True)

    @app.get("/", response_class=HTMLResponse, dependencies=[Depends(viewer)])
    def dashboard(market: str = "nymex-ng", rule: str = "", run: str = ""):
        if market not in markets():
            raise HTTPException(404, "unknown market")
        if rule not in markets()[market]["rules"]:
            rule = ""
        state = status(run, market)
        with connect() as db:
            recent = db.execute(
                "SELECT body FROM events WHERE run=? AND (?='' OR json_extract(body,'$.rule')=?) "
                "ORDER BY sequence DESC LIMIT 100",
                (state.get("run"), rule, rule),
            ).fetchall()
        return page(market, rule, state, [json.loads(r[0]) for r in reversed(recent)])

    return app
