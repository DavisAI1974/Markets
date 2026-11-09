"""Five coordinated views on ten individual cases, one page, same ids across the views.

Views per case: (1) whole lifecycle, last price and oriented roll-20 lean from 300 s before t0 to 600 s after,
with t0, t0+5 knowable, onset, confirmation, seed known, archived recognition and later detector events
marked; (2) fresh against expiring flow, buy and sell lots entering the 20 s window each second against the
lots leaving it; (3) liquidity response, net adds minus cancels by side, executions by aggressor side, 10-level
depth by side and the quotes; (4) event sequence, this and other detector events (t0 to confirmation),
first-observed family starts, sealed touch-print decisions per second by side, size-one onsets per second by
side, prints by size and midpoint leg changes; (5) continuation and exhaustion after confirmation, oriented
price with pauses, the first 3-tick excursions with and against, sign changes and elapsed times. Under each
case a table of the pinned rows: ids and absolute clocks, with counts and the files holding the full lists.
Writes renders/ng-case-views.html. Numbers come from case-context-<tag>.json and case-tape-<tag>.json.
"""

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "renders"
NS = 1_000_000_000
TICK = 1_000_000
W = 940
ML, MR = 96, 120
S1, S2, S3, S4 = "var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"
MUTED, INK, INK2, GRID = "var(--muted)", "var(--ink)", "var(--ink2)", "var(--grid)"


CASES_DATA = "tasks/family-research-20261022/claude-code-cases"


def load_case_file(name):
    """Case rows are data: a fresh local copy if the builders just ran, else the gzip in markets-data
    (MARKETS_DATA_DIR or the scratchpad mirror through data_locator)."""
    import gzip
    local = HERE / name
    if local.exists():
        return json.load(open(local))
    import data_locator
    return json.loads(gzip.decompress(data_locator.read_bytes(f"{CASES_DATA}/{name}.gz")))


def esc(x):
    return html.escape(str(x))


def utc(e, frac=None):
    import datetime as dt
    s = dt.datetime.fromtimestamp(e, dt.timezone.utc).strftime("%H:%M:%S")
    return s if frac is None else f"{s}.{frac:09d}"


class View:
    def __init__(self, title, lo, hi, height):
        self.lo, self.hi, self.h = lo, hi, height
        self.parts = [f'<text x="{ML}" y="14" class="vtitle">{esc(title)}</text>']

    def x(self, t):
        return ML + (t - self.lo) / (self.hi - self.lo) * (W - ML - MR)

    def add(self, s):
        self.parts.append(s)

    def svg(self):
        return f'<svg class="view" viewBox="0 0 {W} {self.h}" role="img">' + "".join(self.parts) + "</svg>"


def xaxis(v, y, lo, hi, step):
    v.add(f'<line x1="{ML}" x2="{W - MR}" y1="{y}" y2="{y}" class="axis"/>')
    t = lo - (lo % step)
    while t <= hi:
        if t >= lo:
            v.add(f'<line x1="{v.x(t):.1f}" x2="{v.x(t):.1f}" y1="{y}" y2="{y + 4}" class="axis"/>')
            v.add(f'<text x="{v.x(t):.1f}" y="{y + 14}" class="tick" text-anchor="middle">{t:+d}</text>')
        t += step
    v.add(f'<text x="{W - MR + 6}" y="{y + 14}" class="tick">s from t0</text>')


def yscale(y0, y1, lo, hi):
    return lambda val: y1 - (val - lo) / (hi - lo) * (y1 - y0) if hi > lo else (y0 + y1) / 2


def yticks(v, ys, vals, fmt=lambda x: f"{x:g}", label=""):
    for val in vals:
        y = ys(val)
        v.add(f'<line x1="{ML}" x2="{W - MR}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        v.add(f'<text x="{ML - 6}" y="{y + 3:.1f}" class="tick" text-anchor="end">{esc(fmt(val))}</text>')
    if label:
        v.add(f'<text x="{ML - 6}" y="{ys(vals[-1]) - 8:.1f}" class="tick" text-anchor="end">{esc(label)}</text>')


def marker(v, t, y0, y1, label, color=INK2, dash="3 3", side=1, row=0):
    if t is None or not (v.lo <= t <= v.hi):
        return
    x = v.x(t)
    v.add(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y0}" y2="{y1}" stroke="{color}" stroke-width="1" stroke-dasharray="{dash}"/>')
    v.add(f'<text x="{x + 3 * side:.1f}" y="{y0 + 9 + 11 * row}" class="mk" text-anchor="{"start" if side > 0 else "end"}" style="fill:{color}">{esc(label)}</text>')


def step_path(v, pts, ys, color, width=1.8):
    d, last = [], None
    for t, val in pts:
        if val is None:
            continue
        x, y = v.x(t), ys(val)
        if last is None:
            d.append(f"M{x:.1f},{y:.1f}")
        else:
            d.append(f"H{x:.1f}V{y:.1f}")
        last = (x, y)
    if d:
        v.add(f'<path d="{" ".join(d)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')


def line_path(v, pts, ys, color, width=1.6, dash=None):
    d = " ".join(f"{v.x(t):.1f},{ys(val):.1f}" for t, val in pts if val is not None)
    if d:
        v.add(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{width}"{f" stroke-dasharray=\"{dash}\"" if dash else ""}/>')


def bars(v, items, ys, zero, color, w, tipfmt):
    for t, val in items:
        if not val:
            continue
        y, y0 = ys(val), ys(zero)
        v.add(f'<rect x="{v.x(t) - w / 2:.1f}" y="{min(y, y0):.1f}" width="{w:.1f}" height="{abs(y - y0):.1f}" fill="{color}"><title>{esc(tipfmt(t, val))}</title></rect>')


def clocks_of(ctx):
    c = ctx["clocks"]; t0 = c["t0"]
    out = [("t0", 0, S1), ("knowable t0+5", 5, INK2), ("onset", c["onset"] - t0 if c["onset"] is not None else None, S2), ("confirm", c["confirm"] - t0 if c["confirm"] is not None else None, S2),
           ("seed known", c["seed_known_s"] - t0 if c["seed_known_s"] is not None else None, INK2), ("recognised", c["recognition_s"] - t0 if c["recognition_s"] is not None else None, S3)]
    return out


def view1(ctx, tape):
    t0 = ctx["clocks"]["t0"]; pol = ctx["case"]["polarity"]
    v = View("1. Whole lifecycle: last price (ticks from the t0 price) and oriented roll-20 lean", -300, 600, 300)
    p0 = next((s["price"] for s in ctx["series"] if s["sec"] == t0 and s["price"]), None)
    pts = [(s["sec"] - t0, (s["price"] - p0) / TICK if s["price"] and p0 else None) for s in ctx["series"]]
    vals = [p for _, p in pts if p is not None]
    lo, hi = (min(vals), max(vals)) if vals else (-1, 1)
    pad = max(1, (hi - lo) * 0.08)
    ys = yscale(26, 150, lo - pad, hi + pad)
    tickvals = sorted({round(lo), 0, round(hi)})
    yticks(v, ys, tickvals, lambda x: f"{x:+d}", "ticks")
    step_path(v, pts, ys, S1)
    v.add(f'<text x="{W - MR + 6}" y="{ys(vals[-1]) + 3 if vals else 100:.1f}" class="dl">price</text>')
    lean = [(s["sec"] - t0, (s["roll20"] * pol) if s["roll20"] is not None else None) for s in ctx["series"]]
    ys2 = yscale(176, 262, -1, 1)
    yticks(v, ys2, [-1, 0, 1], lambda x: f"{x:+g}", "lean x polarity")
    line_path(v, lean, ys2, S2)
    v.add(f'<text x="{W - MR + 6}" y="{ys2(0) + 3:.1f}" class="dl">roll-20 lean</text>')
    for i, (lab, t, col) in enumerate(clocks_of(ctx)):
        marker(v, t, 26, 262, lab, col, side=1 if i % 2 == 0 else -1, row=i % 3)
    for o in ctx["other_detector_events"]:
        marker(v, o["t0"] - t0, 26, 262, f"event t0 {'+' if o['polarity'] > 0 else '-'}", MUTED, "1 3")
    xaxis(v, 270, -300, 600, 100)
    return v.svg()


def view2(ctx, tape):
    t0 = ctx["clocks"]["t0"]
    v = View("2. Fresh flow entering the 20 s window (up buy, down sell) against flow expiring from it (gray)", -120, 180, 230)
    sub = [s for s in ctx["series"] if -120 <= s["sec"] - t0 <= 180]
    m = max([max(s["buy"], s["sell"], s["buy_expiring"], s["sell_expiring"]) for s in sub] + [1])
    ys = yscale(24, 196, -m, m)
    yticks(v, ys, [-round(m), 0, round(m)], lambda x: f"{abs(x):g}", "lots")
    w = (W - ML - MR) / 300 * 0.9
    bars(v, [(s["sec"] - t0, s["buy_expiring"]) for s in sub], ys, 0, MUTED, w * 1.4, lambda t, x: f"t0{t:+d}s: {x:g} buy lots leave the window")
    bars(v, [(s["sec"] - t0, -s["sell_expiring"]) for s in sub], ys, 0, MUTED, w * 1.4, lambda t, x: f"t0{t:+d}s: {-x:g} sell lots leave the window")
    bars(v, [(s["sec"] - t0, s["buy"]) for s in sub], ys, 0, S1, w, lambda t, x: f"t0{t:+d}s: {x:g} fresh buy lots")
    bars(v, [(s["sec"] - t0, -s["sell"]) for s in sub], ys, 0, S2, w, lambda t, x: f"t0{t:+d}s: {-x:g} fresh sell lots")
    for i, (lab, t, col) in enumerate(clocks_of(ctx)):
        marker(v, t, 24, 196, lab, col, side=1 if i % 2 == 0 else -1, row=i % 3)
    xaxis(v, 200, -120, 180, 30)
    return v.svg()


def view3(ctx, tape):
    t0 = ctx["clocks"]["t0"]
    v = View("3. Liquidity response: net adds minus cancels by side, executions by aggressor, 10-level depth and quotes", -120, 180, 420)
    ps = tape["per_second"]; tb = tape["touch_by_second"]
    secs = list(range(t0 - 120, t0 + 181))
    def g(s, k):
        return ps.get(str(s), {}).get(k, 0)
    netb = [(s - t0, g(s, "add_B_lots") - g(s, "cancel_B_lots")) for s in secs]
    neta = [(s - t0, g(s, "add_A_lots") - g(s, "cancel_A_lots")) for s in secs]
    m = max([abs(x) for _, x in netb + neta] + [1])
    ys = yscale(24, 130, -m, m)
    yticks(v, ys, [-round(m), 0, round(m)], lambda x: f"{x:+g}", "adds minus cancels, lots")
    w = (W - ML - MR) / 300 * 0.45
    for pts, col, lab in ((netb, S1, "bid side"), (neta, S2, "ask side")):
        off = -w / 2 if col == S1 else w / 2
        for t, val in pts:
            if val:
                y, y0 = ys(val), ys(0)
                v.add(f'<rect x="{v.x(t) + off - w / 2:.1f}" y="{min(y, y0):.1f}" width="{w:.1f}" height="{abs(y - y0):.1f}" fill="{col}"><title>t0{t:+d}s {lab}: adds minus cancels {val:+g} lots</title></rect>')
    v.add(f'<text x="{W - MR + 6}" y="{ys(m) + 10:.1f}" class="dl">bid / ask adds minus cancels</text>')
    ex_b = [(s - t0, g(s, "aggr_buy_lots")) for s in secs]; ex_s = [(s - t0, -g(s, "aggr_sell_lots")) for s in secs]
    m2 = max([abs(x) for _, x in ex_b + ex_s] + [1])
    ys2 = yscale(150, 240, -m2, m2)
    yticks(v, ys2, [-round(m2), 0, round(m2)], lambda x: f"{abs(x):g}", "executed lots")
    bars(v, ex_b, ys2, 0, S1, w * 2, lambda t, x: f"t0{t:+d}s: {x:g} lots taken by buyers")
    bars(v, ex_s, ys2, 0, S2, w * 2, lambda t, x: f"t0{t:+d}s: {-x:g} lots taken by sellers")
    v.add(f'<text x="{W - MR + 6}" y="{ys2(0) + 3:.1f}" class="dl">buy / sell aggressor</text>')
    dep = [(s - t0, tb.get(str(s), {}).get("bid_depth10")) for s in secs]; dea = [(s - t0, tb.get(str(s), {}).get("ask_depth10")) for s in secs]
    dv = [x for _, x in dep + dea if x]
    ys3 = yscale(262, 330, 0, max(dv + [1]) * 1.05)
    yticks(v, ys3, [0, round(max(dv + [1]))], lambda x: f"{x:g}", "10-level depth")
    line_path(v, dep, ys3, S1); line_path(v, dea, ys3, S2)
    v.add(f'<text x="{W - MR + 6}" y="{ys3(max(dv + [1])) + 10:.1f}" class="dl">bid / ask depth</text>')
    p0 = next((s["price"] for s in ctx["series"] if s["sec"] == t0 and s["price"]), None)
    qb = [(s - t0, (tb[str(s)]["bid"][0] - p0) / TICK if str(s) in tb and p0 else None) for s in secs]
    qa = [(s - t0, (tb[str(s)]["ask"][0] - p0) / TICK if str(s) in tb and p0 else None) for s in secs]
    qv = [x for _, x in qb + qa if x is not None]
    ys4 = yscale(350, 395, min(qv + [-1]) - 0.5, max(qv + [1]) + 0.5)
    yticks(v, ys4, sorted({round(min(qv + [-1])), round(max(qv + [1]))}), lambda x: f"{x:+d}", "quote, ticks")
    step_path(v, qb, ys4, S1, 1.4); step_path(v, qa, ys4, S2, 1.4)
    v.add(f'<text x="{W - MR + 6}" y="{ys4(max(qv + [1])) + 3:.1f}" class="dl">best bid / ask</text>')
    for i, (lab, t, col) in enumerate(clocks_of(ctx)):
        marker(v, t, 24, 395, lab, col, side=1 if i % 2 == 0 else -1, row=i % 3)
    xaxis(v, 400, -120, 180, 30)
    return v.svg()


def view4(ctx, tape):
    t0 = ctx["clocks"]["t0"]; day0 = ctx["day0"]
    v = View("4. Event sequence along the same lifecycle", -300, 600, 300)
    rows_y = {"detector events": 40, "family starts": 75, "touch-print decisions per second (bid up, ask down)": 120, "size-one onsets per second (bid up, ask down)": 175, "prints by lots, midpoint leg changes": 235}
    for lab, y in rows_y.items():
        v.add(f'<text x="{ML - 6}" y="{y + 3}" class="tick" text-anchor="end">{esc(lab.split(" (")[0].split(",")[0])}</text>')
        v.add(f'<line x1="{ML}" x2="{W - MR}" y1="{y}" y2="{y}" class="grid"/>')
    c = ctx["clocks"]
    def ev_bar(tt0, onset, confirm, pol, col, label):
        if onset is not None and confirm is not None:
            v.add(f'<rect x="{v.x(tt0 - t0):.1f}" y="{rows_y["detector events"] - 6}" width="{max(2, v.x(confirm - t0) - v.x(tt0 - t0)):.1f}" height="12" rx="2" fill="{col}"><title>{esc(label)}</title></rect>')
        else:
            v.add(f'<rect x="{v.x(tt0 - t0) - 1:.1f}" y="{rows_y["detector events"] - 6}" width="2" height="12" fill="{col}"><title>{esc(label)}</title></rect>')
    ev_bar(t0, c["onset"], c["confirm"], ctx["case"]["polarity"], S1, f"this event: t0 {utc(day0 + t0)} UTC, onset +{(c['onset'] or 0) - t0} s, confirm +{(c['confirm'] or 0) - t0} s, {ctx['clocks']['candidate_id']}")
    for o in ctx["other_detector_events"]:
        if -300 <= o["t0"] - t0 <= 600:
            ev_bar(o["t0"], o["onset"], o["confirm"], o["polarity"], MUTED, f"detector event t0 {utc(o['epoch_s'])} UTC polarity {o['polarity']} seed {o['seed']} {o['a_state']}")
    for f in ctx["family_starts"]:
        v.add(f'<circle cx="{v.x(f["sec"] - t0):.1f}" cy="{rows_y["family starts"]}" r="3.5" fill="{S3}" stroke="var(--surface)" stroke-width="1"><title>family {f["family_id"]} start {f["start_recv_ns"]} ns ({utc(f["start_recv_ns"] // NS, f["start_recv_ns"] % NS)} UTC), occurrences {f["occurrence_count"]}</title></circle>')
    from collections import Counter
    db, da = Counter(), Counter()
    for d in ctx["touch_print_decisions"]:
        (db if d["side"] == "bid" else da)[d["sec"] - t0] += 1
    mx = max(list(db.values()) + list(da.values()) + [1])
    yd = rows_y["touch-print decisions per second (bid up, ask down)"]
    w = (W - ML - MR) / 900
    for t, n in db.items():
        v.add(f'<rect x="{v.x(t) - w / 2:.1f}" y="{yd - 20 * n / mx:.1f}" width="{max(w, 0.8):.1f}" height="{20 * n / mx:.1f}" fill="{S1}"><title>t0{t:+d}s: {n} bid-side touch-print candidates</title></rect>')
    for t, n in da.items():
        v.add(f'<rect x="{v.x(t) - w / 2:.1f}" y="{yd}" width="{max(w, 0.8):.1f}" height="{20 * n / mx:.1f}" fill="{S2}"><title>t0{t:+d}s: {n} ask-side touch-print candidates</title></rect>')
    ob, oa = Counter(), Counter()
    for o in ctx["size_one_onsets"]:
        (ob if o["side"] == "B" else oa)[o["sec"] - t0] += 1
    mo = max(list(ob.values()) + list(oa.values()) + [1]); yo = rows_y["size-one onsets per second (bid up, ask down)"]
    for t, n in ob.items():
        v.add(f'<rect x="{v.x(t) - w / 2:.1f}" y="{yo - 20 * n / mo:.1f}" width="{max(w, 0.8):.1f}" height="{20 * n / mo:.1f}" fill="{S1}"><title>t0{t:+d}s: {n} bid-side size-one onsets</title></rect>')
    for t, n in oa.items():
        v.add(f'<rect x="{v.x(t) - w / 2:.1f}" y="{yo}" width="{max(w, 0.8):.1f}" height="{20 * n / mo:.1f}" fill="{S2}"><title>t0{t:+d}s: {n} ask-side size-one onsets</title></rect>')
    yp = rows_y["prints by lots, midpoint leg changes"]
    for p in tape["prints"]:
        t = p["sec"] - t0
        if -300 <= t <= 600:
            r = min(7, 1.2 + p["size"] ** 0.5)
            col = S1 if p["aggressor"] == "buy" else S2 if p["aggressor"] == "sell" else MUTED
            v.add(f'<circle cx="{v.x(t):.1f}" cy="{yp + (-8 if p["aggressor"] == "buy" else 8 if p["aggressor"] == "sell" else 0)}" r="{r:.1f}" fill="{col}" fill-opacity="0.7"><title>print {p["size"]} lots at {p["price_raw"] / 1e6:.3f}, {p["aggressor"]} aggressor, {utc(p["epoch_s"], p["ts_recv_ns"] % NS)} UTC, cursor {p["cursor"]}</title></circle>')
    last = None
    for s in ctx["series"]:
        if s["mid"] is None:
            continue
        if last is not None and s["mid"] != last:
            up = s["mid"] > last
            v.add(f'<path d="M{v.x(s["sec"] - t0):.1f},{yp + (22 if up else 30)} l-3,{8 if up else -8} h6 z" fill="{INK2}"><title>midpoint leg {"up" if up else "down"} to {s["mid"] / 1e6:.4f} at {utc(s["epoch_s"])} UTC</title></path>')
        last = s["mid"]
    for i, (lab, t, col) in enumerate(clocks_of(ctx)):
        marker(v, t, 24, 262, lab, col, side=1 if i % 2 == 0 else -1, row=i % 3)
    xaxis(v, 270, -300, 600, 100)
    return v.svg()


def view5(ctx, tape):
    t0 = ctx["clocks"]["t0"]; pol = ctx["case"]["polarity"]; cf = ctx["clocks"]["confirm"]
    v = View("5. Continuation and exhaustion after confirmation: oriented price, pauses, first 3-tick excursions, sign changes", -60, 600, 280)
    pc = next((s["price"] for s in ctx["series"] if s["sec"] == cf and s["price"]), None) if cf is not None else None
    if pc is None:
        pc = next((s["price"] for s in ctx["series"] if s["sec"] == t0 and s["price"]), None)
    pts = [(s["sec"] - t0, pol * (s["price"] - pc) / TICK if s["price"] and pc else None) for s in ctx["series"] if s["sec"] - t0 >= -60]
    vals = [x for _, x in pts if x is not None]
    lo, hi = (min(vals), max(vals)) if vals else (-1, 1)
    pad = max(1, (hi - lo) * 0.1)
    ys = yscale(26, 220, lo - pad, hi + pad)
    yticks(v, ys, sorted({round(lo), 0, round(hi)}), lambda x: f"{x:+d}", "ticks with polarity, from confirm price")
    # pauses: runs of >= 30 s with no price change after confirmation
    after = [(t, x) for t, x in pts if cf is not None and t >= cf - t0 and x is not None]
    run_start, run_val = None, None
    pauses = []
    for t, x in after:
        if run_val is None or x != run_val:
            if run_start is not None and t - run_start >= 30:
                pauses.append((run_start, t))
            run_start, run_val = t, x
    if run_start is not None and after and after[-1][0] - run_start >= 30:
        pauses.append((run_start, after[-1][0]))
    for a, b in pauses:
        v.add(f'<rect x="{v.x(a):.1f}" y="26" width="{v.x(b) - v.x(a):.1f}" height="194" fill="var(--band)"><title>pause: no price change for {b - a} s (t0+{a} to t0+{b})</title></rect>')
    step_path(v, pts, ys, S1)
    hline_y = ys(0); v.add(f'<line x1="{ML}" x2="{W - MR}" y1="{hline_y:.1f}" y2="{hline_y:.1f}" stroke="{INK2}" stroke-width="1"/>')
    notes = []
    first_with = next((t for t, x in after if x >= 3), None); first_against = next((t for t, x in after if x <= -3), None)
    if first_with is not None:
        v.add(f'<circle cx="{v.x(first_with):.1f}" cy="{ys(3):.1f}" r="4" fill="{S3}"><title>first 3 ticks with polarity at t0+{first_with} s</title></circle>'); notes.append(f"3t with at +{first_with} s ({first_with - (cf - t0)} s after confirm)")
    if first_against is not None:
        v.add(f'<circle cx="{v.x(first_against):.1f}" cy="{ys(-3):.1f}" r="4" fill="{S2}"><title>first 3 ticks against polarity at t0+{first_against} s</title></circle>'); notes.append(f"3t against at +{first_against} s")
    prev = None; changes = 0
    for t, x in after:
        sgn = (x > 0) - (x < 0)
        if sgn and prev and sgn != prev:
            changes += 1
            if changes <= 6:
                v.add(f'<path d="M{v.x(t):.1f},{ys(0) - 6:.1f} l-4,-7 h8 z" fill="{INK2}"><title>sign change at t0+{t} s</title></path>')
        if sgn:
            prev = sgn
    for h in (60, 300, 600):
        val = next((x for t, x in pts if t == (cf - t0 if cf is not None else 0) + h and x is not None), None) if cf is not None else None
        if val is not None:
            v.add(f'<text x="{v.x((cf - t0) + h):.1f}" y="{ys(val) - 8:.1f}" class="dl" text-anchor="middle">{val:+g} @ confirm+{h}</text>')
    for i, (lab, t, col) in enumerate(clocks_of(ctx)):
        marker(v, t, 26, 220, lab, col, side=1 if i % 2 == 0 else -1, row=i % 3)
    v.add(f'<text x="{ML}" y="246" class="note">{esc("; ".join(notes) if notes else "no 3-tick excursion within the window")}; pauses of 30 s or more shaded: {len(pauses)}; sign changes after confirmation: {changes}</text>')
    xaxis(v, 254, -60, 600, 60)
    return v.svg()


def case_block(i, ctx, tape):
    c = ctx["case"]; k = ctx["clocks"]; day0 = ctx["day0"]
    head = (f'<h2>Case {i}. {esc(c["label"])}</h2><p class="reading">Rule: {esc(c["rule"])}. Session {esc(c["tag"])}, polarity {"+1 buy" if c["polarity"] > 0 else "-1 sell"}, '
            f'{esc(c["a_state"])}, seed {esc(c["seed"])}, runway {c["runway_s"]} s, confirmation +{c["confirm_offset_s"]} s, recognised +{c["recognition_offset_s"]} s.</p>')
    rows = [("this event, detector t0", f"t0 {k['t0']} (session s)", f"{day0 + k['t0']} / {utc(day0 + k['t0'])} UTC", "exhaustion-clock-<tag>-events"),
            ("archived candidate", esc(k["candidate_id"]), f"recognition_receive_ns {k['recognition_receive_ns']} / {utc(k['recognition_receive_ns'] // NS, k['recognition_receive_ns'] % NS)} UTC, cursor {k['recognition_cursor']}" if k.get("recognition_receive_ns") else "n/a", "dipole-post-recognition-<tag>-rows"),
            ("onset / confirmation", f"+{k['onset'] - k['t0']} s / +{k['confirm'] - k['t0']} s" if k["onset"] is not None and k["confirm"] is not None else "n/a", f"{utc(day0 + k['onset'])} / {utc(day0 + k['confirm'])} UTC" if k["onset"] is not None and k["confirm"] is not None else "", "exhaustion-clock-<tag>-events"),
            ("knowable / seed known", f"t0+5 / +{k['seed_known_s'] - k['t0']} s", f"{utc(day0 + k['t0'] + 5)} / {utc(day0 + k['seed_known_s'])} UTC", "exhaustion-clock-<tag>-events"),
            ("other detector events in window", str(len(ctx["other_detector_events"])), "; ".join(f"t0 {utc(o['epoch_s'])} pol {o['polarity']} {o['seed']}" for o in ctx["other_detector_events"][:6]), "exhaustion-clock-<tag>-events"),
            ("family starts in window", str(len(ctx["family_starts"])), "; ".join(f"{f['family_id']} @ {f['start_recv_ns']}" for f in ctx["family_starts"][:4]) + (" ..." if len(ctx["family_starts"]) > 4 else ""), "family-<date>/chronological-instance-index"),
            ("touch-print candidates in window", str(len(ctx["touch_print_decisions"])), "; ".join(f"g{d['group']} {d['side']} {d['rule']} @ {d['known_by_ns']}" for d in ctx["touch_print_decisions"][:3]) + " ...", "standalone-decisions/decisions"),
            ("size-one onsets in window", str(len(ctx["size_one_onsets"])), "; ".join(f"g{o['onset_group']}{o['side']} {o['outcome'][:4]} @ {o['onset_ns']}" for o in ctx["size_one_onsets"][:3]) + " ...", "size-one-episodes-<tag>"),
            ("prints in window", str(len(tape["prints"])), "; ".join(f"{p['size']}@{p['price_raw'] / 1e6:.3f} {p['aggressor']} {p['ts_recv_ns']}" for p in tape["prints"][:3]) + " ...", "case-tape-<tag> (from the tape)")]
    tbl = "".join(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td class='src'>{r[3]}</td></tr>" for r in rows)
    return (f'<section class="case" id="case-{i}">{head}' + view1(ctx, tape) + view2(ctx, tape) + view3(ctx, tape) + view4(ctx, tape) + view5(ctx, tape)
            + f'<details open><summary>Pinned rows: ids and clocks behind this case (full lists in case-context-{esc(c["tag"])}.json and case-tape-{esc(c["tag"])}.json)</summary><div class="tw"><table><thead><tr><th>what</th><th>id</th><th>clock</th><th>row file</th></tr></thead><tbody>{tbl}</tbody></table></div></details></section>')


def main():
    OUT.mkdir(exist_ok=True)
    cases = json.load(open(HERE / "cases-10.json"))
    ctxs = {t: load_case_file(f"case-context-{t}.json") for t in ("oct02", "oct03", "oct17", "oct18")}
    tapes = {t: load_case_file(f"case-tape-{t}.json") for t in ("oct02", "oct03", "oct17", "oct18")}
    blocks = [case_block(i + 1, ctxs[c["tag"]][str(c["t0"])], tapes[c["tag"]][str(c["t0"])]) for i, c in enumerate(cases)]
    css = """
<title>NG Case Views</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* layout: ten cases, each five stacked views over one time axis, then the pinned-row table */
:root { --surface:#fcfcfb; --paper:#f4f4f2; --ink:#111210; --ink2:#55574f; --muted:#a3a59c; --grid:#e3e4df; --band:#eef1f6;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --sans:"IBM Plex Sans", system-ui, sans-serif; --mono:"IBM Plex Mono", ui-monospace, Menlo, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --surface:#1a1a19; --paper:#222321; --ink:#f0efec; --ink2:#c3c2b7; --muted:#7f8178; --grid:#33352f; --band:#26303d; --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; color-scheme: dark } }
:root[data-theme="dark"] { --surface:#1a1a19; --paper:#222321; --ink:#f0efec; --ink2:#c3c2b7; --muted:#7f8178; --grid:#33352f; --band:#26303d; --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; color-scheme: dark }
body { background: var(--surface); color: var(--ink); font-family: var(--sans); padding-block: 24px 48px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
header, .case { max-width: 1000px; margin: 0 auto; }
h1 { font-size: 1.6rem; font-weight: 600; margin: 0 0 6px; text-wrap: balance; } header p { color: var(--ink2); margin: 0 0 24px; max-width: 75ch; line-height: 1.45; }
.case { padding-top: 18px; margin-bottom: 40px; border-top: 1px solid var(--grid); }
.case h2 { font-size: 1.1rem; font-weight: 600; margin: 0 0 4px; } .reading { color: var(--ink2); margin: 0 0 10px; line-height: 1.45; max-width: 90ch; }
.legend { display:flex; flex-wrap:wrap; gap:6px 18px; font-size:.82rem; color:var(--ink2); margin: 0 0 10px; } .li i { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; vertical-align:-1px; }
.view { width: 100%; height: auto; background: var(--paper); border-radius: 6px; display: block; margin-bottom: 8px; }
.vtitle { font: 600 11.5px var(--sans); fill: var(--ink); } .tick, .dl, .mk, .note { font: 9.5px var(--mono); fill: var(--ink2); } .dl { fill: var(--ink); } .note { fill: var(--ink2); }
.grid { stroke: var(--grid); stroke-width: 1; } .axis { stroke: var(--grid); stroke-width: 1; }
details { margin-top: 6px; font-size: .85rem; } summary { cursor: pointer; color: var(--ink2); }
.tw { overflow-x: auto; margin-top: 6px; } table { border-collapse: collapse; font-family: var(--mono); font-size: .76rem; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 3px 10px 3px 0; border-bottom: 1px solid var(--grid); vertical-align: top; } th { color: var(--ink2); font-weight: 500; } td.src { color: var(--ink2); }
@media print { .case { break-inside: avoid; } }
</style>"""
    legend = ('<div class="legend"><span class="li"><i style="background:var(--s1)"></i>buy side, price, this event</span><span class="li"><i style="background:var(--s2)"></i>sell side, lean, onset and confirmation</span>'
              '<span class="li"><i style="background:var(--s3)"></i>recognition, family starts, first 3 ticks with</span><span class="li"><i style="background:var(--muted)"></i>expiring flow, other events, mid-aggressor prints</span></div>')
    head = ('<header><h1>NG Case Views</h1><p>Ten individual exhaustion events across October 2, 3, 17 and 18, 2023, each in five coordinated views on one time axis (seconds from t0), '
            'with the same ids throughout: the detector t0, the archived candidate id and its recognition clock, onset and confirmation, and every dated row in the window. '
            'Views 2 and 3 zoom to t0-120 to t0+180 s; views 1, 4 and 5 run the full t0-300 to t0+600 s. Hover any mark for its row. Nothing here is a trade.</p>' + legend + '</header>')
    (OUT / "ng-case-views.html").write_text(css + head + "".join(blocks))
    print("wrote", OUT / "ng-case-views.html", len(blocks), "cases")


if __name__ == "__main__":
    main()
