"""Exercise the phone view and event API with an actual decision from a purchased tape prefix."""

import os
from datetime import date
from pathlib import Path
import secrets
import time
import uuid

from fastapi.testclient import TestClient

from .api import wire
from .engine import Engine
from .feed import HistoricalFeed
from .relay import relay


def test_html_api_and_stream_share_one_recorded_event(tmp_path, monkeypatch):
    view, ingest = secrets.token_urlsafe(), secrets.token_urlsafe()
    monkeypatch.setenv("PAPER_VIEW_PASSWORD", view)
    monkeypatch.setenv("PAPER_RELAY_TOKEN", ingest)
    monkeypatch.setenv("PAPER_RELAY_DB", str(tmp_path / "relay.sqlite"))
    client = TestClient(relay())
    assert client.get("/").status_code == 401
    auth = ("greg", view)
    assert "Waiting for a session" in client.get("/", auth=auth).text

    source = HistoricalFeed(
        Path(os.environ["MARKETS_DATA"]) / "data/nymex_mbo/ng_v0_oct2023", date(2023, 10, 2)
    )
    run = uuid.uuid4().hex
    engine = Engine(source.trade_day, run)
    decision = next(e for m in source.messages() for e in engine.tick(m) if e["action"] == "open")
    event = wire(
        dict(run=run, market="nymex-ng", sequence=0, recorded_ns=time.time_ns(), kind="signal", **decision)
    )
    packet = dict(event=event, status=dict(run=run, market=event["market"], events=1, status="active"))
    assert client.post("/ingest", json=packet, auth=auth).status_code == 403
    headers = {"Authorization": "Bearer " + ingest}
    for _ in range(2):
        assert client.post("/ingest", json=packet, headers=headers).json() == {"next": 1}
    rows = client.get("/api/events", params={"rule": event["rule"]}, auth=auth).text.splitlines()
    assert len(rows) == 1
    assert str(event["received"]) in rows[0]
    html = client.get("/", params={"rule": event["rule"]}, auth=auth).text
    assert "Henry Hub Natural Gas" in html and event["trade_id"] in html and "USD/MMBtu" in html
    assert "Rule definition" in html and "EventSource" in html
    assert {e["id"] for e in client.get("/api/markets", auth=auth).json().values()} == {"nymex-ng"}
    assert client.get("/api/events", params={"market": "unregistered"}, auth=auth).status_code == 404
