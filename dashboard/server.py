"""DavisAI Markets dashboard server - the read plane for Mission Control.

Serves the prototype frontend (dashboard/frontend/) and the /api/v1 snapshot endpoints
that replace its simulated state with real stores, exactly per DASHBOARD_HANDOFF_S100:
read-only toward the signal core, additive only, per-event rows, provenance everywhere.

Run from the repo root (the signal core reads data/ relative paths):
    python -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8100
or: python dashboard/server.py
"""
from __future__ import annotations

import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from dashboard.adapters import brain, decision, demo, fees, health, lagmap, market, paths, signals  # noqa: E402

app = FastAPI(title="DavisAI Markets Dashboard", docs_url="/api/docs")

_DAY8 = re.compile(r"^\d{8}$")


def _validate_day(day: str) -> str:
    if not _DAY8.match(day):
        raise HTTPException(400, "day must be YYYYMMDD")
    try:
        datetime.date(int(day[:4]), int(day[4:6]), int(day[6:]))
    except ValueError:
        raise HTTPException(400, f"not a calendar date: {day}")
    return day


def _default_day() -> str:
    kd = market.list_event_days()
    if kd.get("available"):
        iso = market.event_day_iso(kd["event_tickers"][-1])
        if iso:
            return iso.replace("-", "")
    return datetime.date.today().strftime("%Y%m%d")


def _resolved_day(day: str | None) -> str:
    return _validate_day(day) if day is not None else _default_day()


@app.get("/api/v1/operations/health")
def api_health():
    return health.snapshot()


@app.get("/api/v1/brain")
def api_brain():
    return brain.summary()


@app.get("/api/v1/brain/full")
def api_brain_full():
    return brain.load()


@app.get("/api/v1/decision-state/{day}")
def api_decision_state(day: str):
    return decision.state_for_day(_validate_day(day))


@app.get("/api/v1/signals/in-use")
def api_signals_in_use(day: str | None = None):
    day8 = _resolved_day(day)
    ds = decision.state_for_day(day8)
    return signals.snapshot(day8, ds)


@app.get("/api/v1/demo/opportunities")
def api_demo_opportunities(day: str | None = None):
    day8 = _resolved_day(day)
    ds = decision.state_for_day(day8)
    sigs = signals.snapshot(day8, ds)
    return demo.snapshot(day8, ds, sigs)


@app.get("/api/v1/demo/credentials")
def api_demo_credentials():
    return demo.credential_status()


@app.get("/api/v1/lag-map/summary")
def api_lag_summary():
    return lagmap.summary()


@app.get("/api/v1/lag-map/window")
def api_lag_window(band: str = "ATM", cls: str | None = None, tod: str | None = None):
    return lagmap.expected_window(band=band, cls=cls, tod=tod)


@app.get("/api/v1/lag-map/events/{day_iso}")
def api_lag_events(day_iso: str, limit: int = 200):
    return lagmap.events_for_day(day_iso, limit=min(limit, 2000))


@app.get("/api/v1/fees/round-trip")
def api_fees(p_entry: float = 0.5, p_exit: float = 0.5,
             spread_entry: float = 0.04, spread_exit: float = 0.04):
    for v in (p_entry, p_exit):
        if not 0.0 <= v <= 1.0:
            raise HTTPException(400, "prices must be in [0,1]")
    if not 0.0 <= spread_entry <= 1.0 or not 0.0 <= spread_exit <= 1.0:
        raise HTTPException(400, "spreads must be in [0,1] dollars")
    return fees.round_trip(p_entry, p_exit, spread_entry, spread_exit)


@app.get("/api/v1/kalshi/days")
def api_kalshi_days():
    return market.list_event_days()


@app.get("/api/v1/kalshi/candles/{event_ticker}")
def api_kalshi_candles(event_ticker: str):
    if not re.match(r"^[A-Z0-9\-\.]+$", event_ticker):
        raise HTTPException(400, "bad ticker")
    return market.kalshi_day_candles(event_ticker)


@app.get("/api/v1/nymex/days")
def api_nymex_days():
    return {"root": "NG", "days": market.nymex_available_days()}


@app.get("/api/v1/nymex/minute-bars/{day}")
def api_nymex_bars(day: str):
    return market.nymex_minute_bars(_validate_day(day))


@app.get("/api/v1/desk/snapshot")
def api_desk_snapshot(day: str | None = None):
    """Composite Mission Control snapshot for one as-of day."""
    day8 = _resolved_day(day)
    ds = decision.state_for_day(day8)
    sigs = signals.snapshot(day8, ds)
    demo_feed = demo.snapshot(day8, ds, sigs)
    return {
        "as_of_day": day8,
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "health": health.snapshot(),
        "brain": brain.summary(),
        "decision_state": ds,
        "signals_in_use": sigs,
        "demo_feed": demo_feed,
        "lag_map": lagmap.summary(),
        "doctrine_banner": [
            "per-event rows, never pooled means as headlines",
            "ledgers never pooled (NYMEX / Kalshi / any future lane)",
            "maker-first economics; taker reserved for the measured fast tail",
            "provenance labels on every probability (blind vs refined, provisional-until-live)",
            "demo feed has no execution authority and browser holds no credentials",
            "Polymarket lane = context-only until its own feed exists",
        ],
    }


FRONTEND = os.path.join(paths.DASHBOARD, "frontend")


@app.get("/")
def index():
    """Serve the prototype and inject the additive demo wiring after its existing scripts."""
    index_path = os.path.join(FRONTEND, "index.html")
    with open(index_path, encoding="utf-8") as fh:
        html = fh.read()
    demo_script = '<script src="signals_demo.js"></script>'
    if demo_script not in html:
        html = html.replace("</body>", f"  {demo_script}\n</body>")
    return HTMLResponse(html)


app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")


if __name__ == "__main__":
    import uvicorn
    os.chdir(paths.REPO)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("DASH_PORT", "8100")))
