"""Read the shared session or advance exactly one recorded message with its expected cursor."""

import asyncio
import json
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, StrictInt


class Advance(BaseModel):
    after: StrictInt


def wire(value):
    """Preserve nanoseconds and exchange order IDs in browser clients."""
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    if type(value) is int and abs(value) > (1 << 53) - 1:
        return str(value)
    return value


def application(session):
    @asynccontextmanager
    async def lifespan(app):
        done = threading.Event()

        def watch():
            while not done.wait(0.2):
                if session.state != "active":
                    return
                why = session.due()
                if why:
                    session.stop(why)
                    return

        watchdog = threading.Thread(target=watch, daemon=True)
        watchdog.start()
        try:
            yield
        finally:
            done.set()
            watchdog.join()
            session.stop("session stopped")

    app = FastAPI(title="NG paper trading", lifespan=lifespan)

    @app.get("/api/session")
    def status():
        return session.status()

    @app.get("/api/rules")
    def rules():
        return session.rules

    @app.get("/api/book")
    def book():
        with session.lock:
            return wire(session.last)

    @app.post("/api/step")
    def advance(body: Advance):
        try:
            return wire(session.step(body.after))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/events")
    async def events(after: int = -1, rule: str | None = None, follow: bool = False):
        if rule is not None and rule not in session.rules:
            raise HTTPException(status_code=404, detail="unknown rule")

        async def rows():
            with (session.folder / "events.jsonl").open(encoding="utf8") as f:
                while True:
                    offset = f.tell()
                    row = f.readline()
                    if row.endswith("\n"):
                        event = json.loads(row)
                        if event["sequence"] > after and (rule is None or event.get("rule") == rule):
                            yield json.dumps(wire(event)) + "\n"
                    else:
                        f.seek(offset)
                        if not follow or session.state != "active":
                            break
                        await asyncio.sleep(0.1)

        return StreamingResponse(rows(), media_type="application/x-ndjson")

    return app
