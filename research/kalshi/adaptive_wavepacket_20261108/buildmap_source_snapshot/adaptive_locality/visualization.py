"""Standalone offline scientific frame + display. No production or BuildMap runtime imports.

Design pattern inspired by janearc/slayer: retain raw computations; develop a view
independently; verify source identities; provide deterministic replay probes.
This implementation contains no Slayer source code and uses only Python stdlib.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Sequence

from .core import LocalityError, MetricContract, Observation, _digest, finite_cauchy

MAX_SOURCE = 100_000
MAX_VISIBLE = 2_000


def _rank(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scientific_frame(
    events: Sequence[Observation],
    shadow: dict,
    metric: MetricContract,
    x_feature: str,
    y_feature: str,
    *,
    limit: int = 350,
    window: int = 4,
    tolerance: float = 0.1,
) -> dict:
    """Check every observation, then sample display points without omitting science."""
    events = list(events)
    if shadow.get("kind") != "adaptive-locality-shadow" or shadow.get("schema_version") != 1:
        raise LocalityError("expected shadow-only evidence")
    if shadow.get("trust") != "UNSIGNED_RESEARCH_ARTIFACT_NOT_ACCEPTANCE_EVIDENCE":
        raise LocalityError("unknown evidence trust")
    if shadow.get("scientific_jobs_eliminated") != 0:
        raise LocalityError("a viewer must not suppress scientific jobs")
    provenance = shadow.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("metric_identity") != metric.identity():
        raise LocalityError("metric identity mismatch")
    if (x_feature == y_feature or x_feature not in metric.features
            or y_feature not in metric.features):
        raise LocalityError("choose two distinct declared metric features")
    if type(limit) is not int or not 1 <= limit <= MAX_VISIBLE or len(events) > MAX_SOURCE:
        raise LocalityError("source or display bound exceeded")
    if type(window) is not int or not 2 <= window <= 1_000:
        raise LocalityError("invalid convergence window")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise LocalityError("invalid finite convergence tolerance")

    observations = {}
    for event in events:
        if event.event_id in observations:
            raise LocalityError("duplicate event identity")
        metric.vector(event)
        observations[event.event_id] = event
    decisions = shadow.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != len(events):
        raise LocalityError("evidence/observation cardinality mismatch")
    mapped = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise LocalityError("malformed decision")
        eid = decision.get("event_id")
        if eid not in observations or eid in mapped:
            raise LocalityError("missing or duplicate decision event")
        if decision.get("event_identity") != observations[eid].identity():
            raise LocalityError("decision references stale event")
        if decision.get("status") not in ("NEW_CENTER", "PROPOSE_ONLY", "DUPLICATE", "ABSTAIN"):
            raise LocalityError("unsupported decision state")
        center = decision.get("center")
        if center is not None and center not in observations:
            raise LocalityError("center is outside bounded source")
        mapped[eid] = decision

    ids = sorted(observations)
    centers = [eid for eid in ids if mapped[eid]["status"] == "NEW_CENTER"]
    # Center-first deterministic visual sampling; not data sampling or filtering.
    chosen = sorted(centers, key=_rank)[:limit]
    chosen_set = set(chosen)
    chosen += sorted((eid for eid in ids if eid not in chosen_set), key=_rank)[:limit - len(chosen)]
    chosen.sort()
    points = [{
        "id": eid,
        "family": observations[eid].family,
        "clock": observations[eid].event_clock,
        "x": float(observations[eid].features[x_feature]),
        "y": float(observations[eid].features[y_feature]),
        "status": mapped[eid]["status"],
        "center": mapped[eid].get("center"),
        "event_identity": observations[eid].identity(),
    } for eid in chosen]

    groups = defaultdict(list)
    for event in events:
        groups[event.family].append(event)
    diagnostics = []
    for family in sorted(groups):
        series = sorted(groups[family], key=lambda item: (item.event_clock, item.event_id))
        if len(series) >= window:
            result = finite_cauchy(series, metric, tolerance, window)
            diagnostics.append({
                "family": family, "window": window, "tolerance": tolerance,
                "max_distance": result.max_distance,
                "status": "WITHIN_TOLERANCE" if result.finite_window else "NOT_WITHIN_TOLERANCE",
            })
        else:
            diagnostics.append({
                "family": family, "window": window, "tolerance": tolerance,
                "max_distance": None, "status": "INSUFFICIENT_WINDOW",
            })

    frame = {
        "schema_version": 1,
        "kind": "adaptive-locality-raw-scientific-frame",
        "trust": "UNSIGNED_SHADOW_NOT_PRODUCTION_EVIDENCE",
        "axes": [x_feature, y_feature],
        "metric_identity": metric.identity(),
        "provenance": provenance,
        "source_count": len(events),
        "shown_count": len(points),
        "sampled_for_display_only": len(points) < len(events),
        "all_center_count": len(centers),
        "families": sorted(groups),
        "points": points,
        "finite_convergence": diagnostics,
        "scientific_jobs_eliminated": 0,
        "source_event_set_sha256": _digest([
            {"id": eid, "identity": observations[eid].identity(), "decision": mapped[eid]}
            for eid in ids
        ]),
        "limits": [
            "Two-dimensional projection; the distance metric may contain unseen dimensions.",
            "Finite-window Cauchy diagnostics cannot prove infinite convergence.",
            "Proposed geometric assignments are not proof of equivalent calculations.",
            "Display-only sampling never reduces scientific source data or work.",
            "Unsigned offline research view, not a production acceptance receipt.",
        ],
    }
    frame["frame_sha256"] = _digest(frame)
    return frame


def verify_frame(frame: dict) -> None:
    if not isinstance(frame, dict) or frame.get("schema_version") != 1 or frame.get("kind") != "adaptive-locality-raw-scientific-frame":
        raise LocalityError("unsupported frame")
    digest = frame.get("frame_sha256")
    if not isinstance(digest, str) or digest != _digest({key: value for key, value in frame.items() if key != "frame_sha256"}):
        raise LocalityError("tampered frame")
    if frame.get("scientific_jobs_eliminated") != 0:
        raise LocalityError("not a non-destructive frame")
    if frame.get("shown_count") != len(frame.get("points", [])):
        raise LocalityError("display count mismatch")


def replay_probes(frame: dict, count: int = 16) -> list[dict]:
    """Deterministic inspection probes; source identity required for replay."""
    verify_frame(frame)
    if type(count) is not int or not 1 <= count <= 256:
        raise LocalityError("invalid probe count")
    ordered = sorted(frame["points"], key=lambda point: _rank(frame["frame_sha256"] + ":" + point["id"]))
    return [{
        "id": p["id"], "event_identity": p["event_identity"],
        "x": p["x"], "y": p["y"],
    } for p in ordered[:count]]


def render_html(frame: dict) -> str:
    """Develop a self-contained report; presentation never recomputes a metric."""
    verify_frame(frame)
    encoded = json.dumps(frame, sort_keys=True, ensure_ascii=True,
                         allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    return _HTML.replace("FRAME_PAYLOAD_PLACEHOLDER", encoded)


def write_html(frame: dict, destination: str | Path) -> None:
    with Path(destination).open("x", encoding="utf-8") as output:
        output.write(render_html(frame))


_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>Locality Lab — offline scientific review</title>
<style>
:root{color-scheme:dark;--bg:#25272b;--surface:#34373c;--fg:#f0f2f4;--muted:#c2c7cd;--border:#656b74}
body.light{color-scheme:light;--bg:#f3f4f5;--surface:#fff;--fg:#282c31;--muted:#505863;--border:#a3a9b1}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Arial,sans-serif;background:var(--bg);color:var(--fg);line-height:1.45}
header{padding:16px 20px;border-bottom:1px solid var(--border)}
h1{font-size:22px;margin:0}h2{font-size:16px;margin:0 0 10px}.muted{color:var(--muted)}
main{display:grid;grid-template-columns:minmax(300px,2fr) minmax(250px,1fr);gap:12px;padding:12px}
.panel{background:var(--surface);border:1px solid var(--border);padding:14px;min-width:0}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
button{border:1px solid var(--border);border-radius:2px;background:transparent;color:inherit;padding:5px 9px;font:inherit;cursor:pointer}
button[aria-pressed=true]{font-weight:bold;border-color:#9dbad7}
button:focus-visible{outline:2px solid #9bbff0;outline-offset:2px}
canvas{display:block;width:100%;height:400px}
.scroll{max-height:220px;overflow:auto}table{border-collapse:collapse;font-size:12px;width:100%}
td,th{padding:4px;border-bottom:1px solid var(--border);text-align:left}
code{overflow-wrap:anywhere}.section{margin-top:20px}li{margin-bottom:5px}
footer{padding:12px 20px;color:var(--muted);font-size:12px}
@media(max-width:800px){main{grid-template-columns:1fr}canvas{height:320px}}
</style></head><body>
<header><h1>Locality Lab <small class="muted">— offline experiment</small></h1>
<div class="muted">Not a convergence proof, production decision or scientific reuse receipt.</div></header>
<main><section class="panel"><h2>Neighborhood and packing-center projection</h2>
<div class="controls">
<button id="dark" type="button" aria-pressed="true">Dark</button>
<button id="light" type="button" aria-pressed="false">Light</button>
<button id="links" type="button" aria-pressed="true">Show candidate links</button>
</div>
<canvas id="plot" role="img" aria-label="Two-dimensional observation plot. A table of values follows."></canvas>
<p id="plotNote" class="muted"></p>
<div class="scroll"><table aria-label="Displayed observation data"><thead>
<tr><th>Observation</th><th>Family</th><th>Status</th><th>Coordinates</th></tr></thead>
<tbody id="tableRows"></tbody></table></div>
</section>
<aside class="panel">
<h2>Source and display counts</h2><div id="counts"></div>
<p id="scope" class="muted"></p>
<div class="section"><h2>Selected observation</h2><div id="selected" aria-live="polite">Select a point or an observation row.</div></div>
<div class="section"><h2>Finite-window diagnostics</h2><div id="diagnostics"></div></div>
<div class="section"><h2>Interpretation limits</h2><ul id="limits"></ul></div>
<div class="section"><h2>Frame digest</h2><code id="digest"></code></div>
</aside></main>
<footer>Source observations preserved. Display sampling only. Zero scientific jobs suppressed. No network calls.</footer>
<script type="application/json" id="rawFrame">FRAME_PAYLOAD_PLACEHOLDER</script>
<script>
"use strict";
const frame=JSON.parse(document.getElementById("rawFrame").textContent);
const plot=document.getElementById("plot"),ctx=plot.getContext("2d");
const rows=document.getElementById("tableRows");
const colors=["#5b9bd5","#cf9b70","#8bb88f","#bf8ebf","#c4b458","#75bac0","#a9a9d5","#c47f82"];
const byId=new Map(frame.points.map(p=>[p.id,p]));
let view="dark",showLinks=true,spots=[];
const get=id=>document.getElementById(id);
function add(tag,content,parent){const node=document.createElement(tag);node.textContent=String(content);parent.appendChild(node);return node;}
function choose(p){const panel=get("selected");panel.replaceChildren();
 for(const [name,value] of Object.entries({"ID":p.id,"Family":p.family,"Clock":p.clock,"Status":p.status,
 "Candidate center":p.center||"None","X":p.x,"Y":p.y,"Event identity":p.event_identity})){
 const row=add("div",name+": ",panel);const strong=add("strong",value,row);strong.style.overflowWrap="anywhere";}}
function draw(){
 const rect=plot.getBoundingClientRect(),w=Math.max(250,rect.width),h=Math.max(250,rect.height),dpr=Math.min(2,window.devicePixelRatio||1);
 plot.width=Math.round(w*dpr);plot.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
 ctx.fillStyle=view==="dark"?"#34373c":"#ffffff";ctx.fillRect(0,0,w,h);
 const xs=frame.points.map(p=>p.x),ys=frame.points.map(p=>p.y),xmin=xs.length?Math.min(...xs):0,
 xmax=xs.length?Math.max(...xs):1,ymin=ys.length?Math.min(...ys):0,ymax=ys.length?Math.max(...ys):1;
 const dx=xmax-xmin||1,dy=ymax-ymin||1,pad=40;
 const pos=p=>[pad+(p.x-xmin)/dx*(w-2*pad),h-pad-(p.y-ymin)/dy*(h-2*pad)];
 ctx.strokeStyle=view==="dark"?"#9da5af":"#727b85";ctx.lineWidth=1;
 ctx.beginPath();ctx.moveTo(pad,10);ctx.lineTo(pad,h-pad);ctx.lineTo(w-10,h-pad);ctx.stroke();
 if(showLinks){ctx.strokeStyle=view==="dark"?"#85909d":"#a4aab2";ctx.globalAlpha=.55;
 for(const p of frame.points){const target=byId.get(p.center);if(!target||target.id===p.id)continue;
 const a=pos(p),b=pos(target);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();}
 ctx.globalAlpha=1;}
 spots=[];for(const p of frame.points){const xy=pos(p),center=p.status==="NEW_CENTER";
 ctx.beginPath();ctx.arc(xy[0],xy[1],center?7:4.5,0,Math.PI*2);
 ctx.fillStyle=colors[Math.max(0,frame.families.indexOf(p.family))%colors.length];ctx.fill();
 if(center){ctx.strokeStyle=view==="dark"?"#fff":"#111";ctx.lineWidth=2;ctx.stroke();}
 spots.push([xy[0],xy[1],p]);}
 ctx.fillStyle=view==="dark"?"#e0e5eb":"#242b31";ctx.font="12px system-ui";
 ctx.fillText(frame.axes[0],w/2,h-9);
 ctx.save();ctx.translate(16,h/2);ctx.rotate(-Math.PI/2);ctx.fillText(frame.axes[1],0,0);ctx.restore();
}
function populate(){
 for(const [name,value] of Object.entries({"Original observations":frame.source_count,"Displayed":frame.shown_count,
 "All source centers":frame.all_center_count,"Families":frame.families.length,"Jobs eliminated":frame.scientific_jobs_eliminated}))
 add("div",name+": "+value,get("counts"));
 get("scope").textContent="Run "+frame.provenance.run+" / "+frame.provenance.day+
 (frame.sampled_for_display_only?". Deterministic display subset only.":". Entire bounded source displayed.");
 get("plotNote").textContent="Two-dimensional projection. The true metric may include additional features.";
 get("digest").textContent=frame.frame_sha256;
 for(const item of frame.finite_convergence)add("div",item.family+": "+item.status+" (window "+item.window+")",get("diagnostics"));
 for(const line of frame.limits)add("li",line,get("limits"));
 for(const p of frame.points){const tr=document.createElement("tr"),td=document.createElement("td"),
 btn=add("button",p.id,td);btn.type="button";btn.addEventListener("click",()=>choose(p));tr.appendChild(td);
 for(const item of [p.family,p.status,p.x.toPrecision(4)+", "+p.y.toPrecision(4)])add("td",item,tr);
 rows.appendChild(tr);}
}
plot.addEventListener("click",event=>{const rect=plot.getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;
 let found=null,distance=Infinity;
 for(const [px,py,p] of spots){const d=(px-x)**2+(py-y)**2;if(d<distance){distance=d;found=p;}}
 if(found&&distance<=225)choose(found);});
get("links").addEventListener("click",()=>{showLinks=!showLinks;get("links").setAttribute("aria-pressed",String(showLinks));draw();});
for(const mode of ["dark","light"])get(mode).addEventListener("click",()=>{
 view=mode;document.body.classList.toggle("light",mode==="light");
 for(const item of ["dark","light"])get(item).setAttribute("aria-pressed",String(item===mode));draw();});
window.addEventListener("resize",draw);
populate();draw();
</script></body></html>
"""
