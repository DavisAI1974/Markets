"""HTMX operations desk for the unattended live NG collector.

This first slice is intentionally truthful: it shows the underlying CME/NYMEX
feed and labels the event-contract lane SHADOW until ECNG/ECH books are wired.
"""
from __future__ import annotations

import html
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

HEALTH_FILE = Path(os.getenv("NG_LIVE_HEALTH_FILE", "/var/lib/markets/ng_live/health.json"))
app = FastAPI(title="DavisAI Markets Desk")


def read_health() -> dict[str, Any]:
    if not HEALTH_FILE.exists():
        return {"connection": "offline", "last_error": "health snapshot not found"}
    try:
        payload = json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"connection": "error", "last_error": str(error)}
    try:
        updated = datetime.fromisoformat(str(payload["updated_at"]))
        payload["health_age_s"] = max(0.0, time.time() - updated.timestamp())
    except (KeyError, TypeError, ValueError):
        payload["health_age_s"] = None
    return payload


def esc(value: Any) -> str:
    return html.escape("--" if value is None else str(value))


def number(value: Any, digits: int = 3, suffix: str = "") -> str:
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "--"


def integer(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "--"


def status_class(payload: dict[str, Any]) -> tuple[str, str]:
    connection = str(payload.get("connection", "offline")).lower()
    health_age = payload.get("health_age_s")
    record_age = payload.get("record_age_ms")
    stale = False
    try:
        stale = float(health_age) > 20 or (record_age is not None and float(record_age) > 30_000)
    except (TypeError, ValueError):
        pass
    if connection == "live" and not stale:
        return "live", "LIVE"
    if connection in {"connecting", "reconnecting", "stopping", "closed"} and not stale:
        return "warn", connection.upper()
    return "down", "STALE" if stale else connection.upper()


@app.get("/api/ng/live")
def api_ng_live() -> JSONResponse:
    return JSONResponse(read_health())


@app.get("/partials/ng-top-stack", response_class=HTMLResponse)
def ng_top_stack() -> str:
    p = read_health()
    market = p.get("market") or {}
    mbo = p.get("latest_mbo") or {}
    latency = p.get("latency_ms") or {}
    counts = p.get("record_counts") or {}
    state_class, state_label = status_class(p)
    imbalance = market.get("depth_imbalance_10")
    if imbalance is None:
        imbalance_label = "--"
        imbalance_side = "awaiting depth"
    else:
        imbalance_label = f"{float(imbalance):+.3f}"
        imbalance_side = "bid pressure" if float(imbalance) > 0 else "ask pressure"
    total_records = sum(int(value) for value in counts.values() if isinstance(value, (int, float)))
    return f"""
<section class="stack-card">
  <div class="stack-header">
    <div>
      <span class="eyebrow">TOP STACK · UNDERLYING LANE</span>
      <h1>Henry Hub NG live microstructure</h1>
      <p>{esc(p.get('raw_symbol') or p.get('requested_symbol') or 'NG.v.0')} · GLBX.MDP3 · personal Standard</p>
    </div>
    <div class="badges"><span class="badge {state_class}"><i></i>{state_label}</span><span class="badge shadow">CME EVENTS · SHADOW</span></div>
  </div>
  <div class="metric-grid">
    <article><span>Last trade</span><strong>{number(market.get('trade_price'), 3)}</strong><em>{esc(market.get('trade_side'))} · {integer(market.get('trade_size'))} lots</em></article>
    <article><span>Bid / ask</span><strong>{number(market.get('best_bid'), 3)} / {number(market.get('best_ask'), 3)}</strong><em>spread {number(market.get('spread'), 3)}</em></article>
    <article class="accent"><span>10-level imbalance</span><strong>{imbalance_label}</strong><em>{imbalance_side}</em></article>
    <article><span>Feed latency p50 / p95</span><strong>{number(latency.get('p50'), 1)} / {number(latency.get('p95'), 1)} ms</strong><em>client wall minus ts_recv</em></article>
    <article><span>Record age</span><strong>{number(p.get('record_age_ms'), 0, ' ms')}</strong><em>health age {number(p.get('health_age_s'), 1, ' s')}</em></article>
  </div>
  <div class="lower-grid">
    <div class="book-panel">
      <div class="panel-title"><span>MBP-10 DEPTH</span><b>aggregated</b></div>
      <div class="book-row"><span>Bid depth</span><strong>{integer(market.get('bid_depth_10'))}</strong></div>
      <div class="book-row"><span>Ask depth</span><strong>{integer(market.get('ask_depth_10'))}</strong></div>
      <div class="book-row"><span>Best bid size</span><strong>{integer(market.get('best_bid_size'))}</strong></div>
      <div class="book-row"><span>Best ask size</span><strong>{integer(market.get('best_ask_size'))}</strong></div>
    </div>
    <div class="book-panel">
      <div class="panel-title"><span>LATEST MBO EVENT</span><b>order level</b></div>
      <div class="book-row"><span>Action</span><strong>{esc(mbo.get('action'))}</strong></div>
      <div class="book-row"><span>Side</span><strong>{esc(mbo.get('side'))}</strong></div>
      <div class="book-row"><span>Price</span><strong>{number(mbo.get('price'), 3)}</strong></div>
      <div class="book-row"><span>Size</span><strong>{integer(mbo.get('size'))}</strong></div>
    </div>
    <div class="book-panel signal-panel">
      <div class="panel-title"><span>SIGNAL AUTHORITY</span><b>honest gate</b></div>
      <div class="call"><span>Dipole look-ahead</span><strong>WIRING NEXT</strong></div>
      <p>Raw MBO, MBP-10, trades and TBBO are collecting now. ECNG/ECH market books and strike/VWAP fair-value logic are not connected yet, so execution stays disabled.</p>
    </div>
  </div>
  <div class="stack-footer">
    <span>{integer(total_records)} records this session</span>
    <span>{integer(p.get('archive_bytes'))} bytes local DBN</span>
    <span>{integer(p.get('reconnect_count'))} reconnects</span>
    <button disabled>CME order routing unavailable</button>
  </div>
  {f'<div class="error-strip">{esc(p.get("last_error"))}</div>' if p.get('last_error') else ''}
</section>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DavisAI Markets · NG Live</title><script src="https://unpkg.com/htmx.org@2.0.4"></script>
<style>
:root{--bg:#071019;--panel:#0d1722;--panel2:#111e2b;--line:#203144;--text:#e7eef6;--muted:#71849a;--cyan:#42d9f5;--green:#5de4a3;--amber:#ffc96b;--red:#ff6f7f;--purple:#d56dff;font-family:Inter,ui-sans-serif,system-ui,sans-serif;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 70% 0,rgba(66,217,245,.07),transparent 30%),var(--bg);color:var(--text);min-height:100vh}.shell{display:grid;grid-template-columns:220px 1fr;min-height:100vh}.side{border-right:1px solid var(--line);padding:22px 16px;background:#09131d}.brand{font-weight:800;letter-spacing:-.02em}.brand small{display:block;color:var(--muted);font:10px ui-monospace,monospace;margin-top:4px}.nav{margin-top:34px;display:grid;gap:8px}.nav div{padding:10px;border:1px solid transparent;border-radius:7px;color:var(--muted);font-size:12px}.nav .active{color:var(--text);background:var(--panel2);border-color:var(--line)}.side-note{margin-top:30px;padding:10px;border:1px solid rgba(255,201,107,.18);background:rgba(255,201,107,.05);border-radius:7px;color:var(--muted);font-size:10px;line-height:1.5}.main{padding:22px;max-width:1500px;width:100%}.topline{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.topline h2{font-size:14px;margin:0}.topline span{font:10px ui-monospace,monospace;color:var(--muted)}.stack-card{border:1px solid var(--line);border-radius:10px;background:linear-gradient(180deg,rgba(17,30,43,.98),rgba(11,20,30,.98));overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,.24)}.stack-header{padding:18px 20px;display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid var(--line)}.eyebrow{color:var(--cyan);font:9px ui-monospace,monospace;letter-spacing:.12em}.stack-header h1{margin:5px 0 4px;font-size:22px}.stack-header p{margin:0;color:var(--muted);font:10px ui-monospace,monospace}.badges{display:flex;gap:7px;align-items:flex-start}.badge{padding:6px 8px;border-radius:5px;font:8px ui-monospace,monospace;font-weight:800}.badge i{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:5px}.badge.live{color:var(--green);background:rgba(93,228,163,.08)}.badge.live i{background:var(--green);box-shadow:0 0 9px var(--green)}.badge.warn{color:var(--amber);background:rgba(255,201,107,.08)}.badge.warn i{background:var(--amber)}.badge.down{color:var(--red);background:rgba(255,111,127,.08)}.badge.down i{background:var(--red)}.badge.shadow{color:var(--purple);background:rgba(213,109,255,.08)}.metric-grid{display:grid;grid-template-columns:repeat(5,1fr);border-bottom:1px solid var(--line)}.metric-grid article{padding:15px;border-right:1px solid var(--line);display:grid;gap:5px}.metric-grid article:last-child{border-right:0}.metric-grid span,.panel-title span{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}.metric-grid strong{font:16px ui-monospace,monospace}.metric-grid em{font-style:normal;color:var(--muted);font-size:9px}.metric-grid .accent{background:rgba(66,217,245,.04)}.metric-grid .accent strong{color:var(--cyan)}.lower-grid{display:grid;grid-template-columns:1fr 1fr 1.2fr;gap:10px;padding:12px}.book-panel{border:1px solid var(--line);border-radius:7px;background:rgba(7,16,25,.45);padding:11px}.panel-title{display:flex;justify-content:space-between;margin-bottom:9px}.panel-title b{color:var(--muted);font-size:8px}.book-row{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(32,49,68,.55);font-size:10px}.book-row:last-child{border-bottom:0}.book-row span{color:var(--muted)}.book-row strong{font-family:ui-monospace,monospace}.signal-panel{border-color:rgba(213,109,255,.25)}.call{display:flex;justify-content:space-between;padding:10px;background:rgba(213,109,255,.06);border-radius:5px;font-size:10px}.call strong{color:var(--purple)}.signal-panel p{color:var(--muted);font-size:9px;line-height:1.55;margin:10px 2px 0}.stack-footer{display:flex;gap:20px;align-items:center;padding:12px 15px;border-top:1px solid var(--line);color:var(--muted);font:9px ui-monospace,monospace}.stack-footer button{margin-left:auto;border:1px solid var(--line);background:#101a25;color:#53657a;padding:8px 10px;border-radius:5px}.error-strip{padding:9px 15px;background:rgba(255,111,127,.06);color:var(--red);font:9px ui-monospace,monospace}.htmx-request{opacity:.75}@media(max-width:1000px){.shell{grid-template-columns:1fr}.side{display:none}.metric-grid{grid-template-columns:1fr 1fr}.lower-grid{grid-template-columns:1fr}.stack-header{display:grid}.badges{flex-wrap:wrap}}
</style></head><body><div class="shell"><aside class="side"><div class="brand">DavisAI Markets<small>LIVE DESK · S100 BUILD</small></div><div class="nav"><div class="active">NG Microstructure</div><div>CME Hourly · Shadow</div><div>Kalshi Execution</div><div>Portfolio & Risk</div><div>Operations</div></div><div class="side-note">Collection is independent of this browser and chat. systemd owns the feed, restart policy, watchdog and S3 archival.</div></aside><main class="main"><div class="topline"><h2>Energy & event-contract stack</h2><span>HTMX · refresh 2s · execution gated</span></div><div id="ng-stack" hx-get="/partials/ng-top-stack" hx-trigger="load, every 2s" hx-swap="innerHTML"><section class="stack-card"><div class="stack-header"><h1>Loading NG live state...</h1></div></section></div></main></div></body></html>"""
