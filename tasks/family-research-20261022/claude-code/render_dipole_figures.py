"""Render the dipole work of claude-october-discovery-20261108.md as one HTML page of inline SVG figures.

Reads only the committed summary files beside this script. Each figure: title, one-line reading, small
multiples by session (Oct 2, 3, 17, 18), a legend when there is more than one series, and a table view of
the plotted numbers. Colors come from the validated reference palette (light and dark steps), text from
the page tokens. Writes renders/ng-dipole-renders.html.
"""

import html
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "renders"
TAGS = [("oct02", "Oct 2"), ("oct03", "Oct 3"), ("oct17", "Oct 17"), ("oct18", "Oct 18")]
J = lambda name: json.load(open(HERE / name))
S = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"]
MUTED = "var(--muted)"
GRID = "var(--grid)"
INK = "var(--ink)"
INK2 = "var(--ink2)"

PW, PH = 300, 190          # panel size
ML, MR, MT, MB = 44, 14, 22, 30


def set_margin(ml):
    global ML
    ML = ml


def esc(s):
    return html.escape(str(s))


class Panel:
    def __init__(self, title):
        self.parts = [f'<text x="{ML}" y="13" class="ptitle">{esc(title)}</text>']

    def add(self, s):
        self.parts.append(s)

    def svg(self):
        return f'<svg class="panel" viewBox="0 0 {PW} {PH}" role="img">' + "".join(self.parts) + "</svg>"


def xlin(lo, hi):
    return lambda v: ML + (v - lo) / (hi - lo) * (PW - ML - MR)


def ylin(lo, hi):
    return lambda v: PH - MB - (v - lo) / (hi - lo) * (PH - MT - MB)


def ylog(lo, hi):
    a, b = math.log10(lo), math.log10(hi)
    return lambda v: PH - MB - (math.log10(v) - a) / (b - a) * (PH - MT - MB)


def axes(p, xticks, yticks, xfmt=str, yfmt=str, xs=None, ys=None, xlabel="", ylabel=""):
    x0, x1, y0, y1 = ML, PW - MR, PH - MB, MT
    for v, lab in yticks:
        y = ys(v)
        p.add(f'<line x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        p.add(f'<text x="{x0 - 5}" y="{y + 3:.1f}" class="tick" text-anchor="end">{esc(lab)}</text>')
    for v, lab in xticks:
        x = xs(v)
        p.add(f'<text x="{x:.1f}" y="{y0 + 12}" class="tick" text-anchor="middle">{esc(lab)}</text>')
    p.add(f'<line x1="{x0}" x2="{x1}" y1="{y0}" y2="{y0}" class="axis"/>')
    if xlabel:
        p.add(f'<text x="{(x0 + x1) / 2:.1f}" y="{PH - 3}" class="alabel" text-anchor="middle">{esc(xlabel)}</text>')
    if ylabel:
        p.add(f'<text x="10" y="{(y0 + y1) / 2:.1f}" class="alabel" text-anchor="middle" transform="rotate(-90 10 {(y0 + y1) / 2:.1f})">{esc(ylabel)}</text>')


def dot(p, x, y, color, tip, r=3.6):
    p.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" stroke="var(--surface)" stroke-width="1.5"><title>{esc(tip)}</title></circle>')


def hline(p, y, dash=True, color=MUTED):
    p.add(f'<line x1="{ML}" x2="{PW - MR}" y1="{y:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="1.2"{" stroke-dasharray=\"4 3\"" if dash else ""}/>')


def bar_h(p, x_from, x_to, y, h, color, tip):
    x_a, x_b = min(x_from, x_to), max(x_from, x_to)
    p.add(f'<rect x="{x_a:.1f}" y="{y - h / 2:.1f}" width="{max(0.5, x_b - x_a):.1f}" height="{h}" rx="2" fill="{color}"><title>{esc(tip)}</title></rect>')


def bar_v(p, x, w, y_base, y_top, color, tip):
    y_a, y_b = min(y_base, y_top), max(y_base, y_top)
    p.add(f'<rect x="{x - w / 2:.1f}" y="{y_a:.1f}" width="{w}" height="{max(0.5, y_b - y_a):.1f}" rx="2" fill="{color}"><title>{esc(tip)}</title></rect>')


def polyline(p, pts, color, dash=False):
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    p.add(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="2"{" stroke-dasharray=\"5 3\"" if dash else ""} stroke-linejoin="round"/>')


def figure(fid, title, reading, panels, legend, table_head, table_rows, note=""):
    leg = ""
    if legend:
        leg = '<div class="legend">' + "".join(f'<span class="li"><i style="background:{c}"></i>{esc(n)}</span>' for n, c in legend) + "</div>"
    th = "".join(f"<th>{esc(h)}</th>" for h in table_head)
    tr = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in table_rows)
    return (f'<section class="fig" id="{fid}"><h2>{esc(title)}</h2><p class="reading">{esc(reading)}</p>{leg}'
            f'<div class="panels">{"".join(panels)}</div>'
            + (f'<p class="note">{esc(note)}</p>' if note else "")
            + f'<details><summary>Table view</summary><div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div></details></section>')


def f1_clocks():
    panels, rows = [], []
    for tag, label in TAGS:
        d = J(f"exhaustion-clock-{tag}-summary.json")["day_native"]
        rw, cf, ar = d["runway_s"], d["confirm_offset_s"], d.get("archived_recognition_offset_s")
        p = Panel(label)
        xs = xlin(0, 160); ys = ylin(0, 4)
        axes(p, [(v, str(v)) for v in (0, 50, 100, 150)], [], xs=xs, ys=ys, xlabel="seconds after t0")
        for i, (name, q, col) in enumerate((("runway (onset)", rw, S[0]), ("confirmation", cf, S[1]))):
            y = ys(3 - i)
            bar_h(p, xs(q["q25"]), xs(q["q75"]), y, 10, col, f"{label} {name}: q25 {q['q25']} / median {q['median']} / q75 {q['q75']} s, n {q['n']}")
            p.add(f'<line x1="{xs(q["median"]):.1f}" x2="{xs(q["median"]):.1f}" y1="{y - 8:.1f}" y2="{y + 8:.1f}" stroke="var(--surface)" stroke-width="2"/>')
            p.add(f'<text x="{xs(q["q75"]) + 5:.1f}" y="{y + 3:.1f}" class="dl">{int(q["median"])} s</text>')
        if ar:
            y = ys(1)
            bar_h(p, xs(ar["min"]), xs(ar["max"]), y, 3, MUTED, f"{label} archived recognition offset: min {ar['min']} / median {ar['median']} / max {ar['max']} s, n {ar['n']}")
            dot(p, xs(ar["median"]), y, S[2], f"{label} archived recognition median {ar['median']} s (n {ar['n']})")
            p.add(f'<text x="{xs(ar["max"]) + 5:.1f}" y="{y + 3:.1f}" class="dl">{int(ar["median"])} s</text>')
        for i, nm in enumerate(("runway", "confirm", "recognised")):
            p.add(f'<text x="{ML - 4}" y="{ys(3 - i) + 3:.1f}" class="tick" text-anchor="end">{nm}</text>')
        panels.append(p.svg())
        rows.append([label, d["events"], f"{rw['q25']} / {rw['median']} / {rw['q75']}", f"{cf['q25']} / {cf['median']} / {cf['q75']}", f"{ar['min']} / {ar['median']} / {ar['max']} (n {ar['n']})" if ar else "n/a", d["remaining_runway_at_info50_s"]["negative"]])
    return figure("clocks", "1. Three clocks of the frozen dipole detector",
                  "Runway (t0 to onset) and confirmation sit at 31 to 38 s median on every session; the archived recognition arrives at 51 to 52 s. Roughly six in ten bursts are over before they are knowable.",
                  panels, [("runway, q25 to q75 with median", S[0]), ("confirmation, q25 to q75 with median", S[1]), ("archived recognition offset, median on min to max", S[2])],
                  ["session", "events", "runway q25 / median / q75 (s)", "confirmation q25 / median / q75 (s)", "recognition offset min / median / max (s)", "runway already over at t0+50"], rows)


def f2_duration():
    set_margin(54)
    panels, rows = [], []
    scales = ["3", "5", "8", "13"]
    for tag, label in TAGS:
        r = J(f"frozen-a-classifier-{tag}-summary.json")["results"]["price_with"]["by_state"]
        p = Panel(label)
        xs = lambda i: ML + 20 + i * (PW - ML - MR - 40) / 3
        ys = ylog(200, 20000)
        axes(p, [(i, f"{k}t") for i, k in enumerate(scales)], [(v, f"{v:,}") for v in (300, 1000, 3000, 10000)], xs=xs, ys=ys, xlabel="ticks travelled with polarity", ylabel="seconds from t0")
        for st, col, off in (("A-fast-collapse", S[0], -6), ("A-persistent", S[1], 6)):
            pts = []
            for i, k in enumerate(scales):
                c = r[st][k]
                x = xs(i) + off
                p.add(f'<line x1="{x - 7:.1f}" x2="{x + 7:.1f}" y1="{ys(c["frozen_total"]):.1f}" y2="{ys(c["frozen_total"]):.1f}" stroke="{MUTED}" stroke-width="2"><title>frozen {st} {k}t: {c["frozen_total"]} s</title></line>')
                dot(p, x, ys(c["km_median"]), col, f"{label} {st} {k}t realised KM median {c['km_median']} s (frozen {c['frozen_total']})")
                pts.append((x, ys(c["km_median"])))
                rows.append([label, st, k, c["km_median"], c["frozen_total"], round(c["km_median"] / c["frozen_total"], 2)])
            polyline(p, pts, col)
        panels.append(p.svg())
    return figure("duration", "2. The frozen duration math on four sessions",
                  "Persistent beats fast-collapse at every scale on every day (16 of 16). The frozen totals (gray dashes) match the persistent state on October 18 only; elsewhere both states run long.",
                  panels, [("A-fast-collapse, realised", S[0]), ("A-persistent, realised", S[1]), ("frozen total", MUTED)],
                  ["session", "state", "scale (ticks)", "realised KM median (s)", "frozen total (s)", "ratio"], rows)


def f3_clock():
    set_margin(44)
    d = J("runway-clock-v2-summary.json")["clocks"]
    panels, rows = [], []
    cells = [("A-fast-collapse", k) for k in ("3", "5", "8", "13")] + [("A-persistent", k) for k in ("3", "5", "8", "13")]
    for tag, label in TAGS:
        p = Panel(label)
        xs = lambda i: ML + 14 + i * (PW - ML - MR - 28) / 7
        ys = ylog(0.4, 3.5)
        p.add(f'<rect x="{ML}" y="{ys(1.25):.1f}" width="{PW - ML - MR}" height="{ys(0.8) - ys(1.25):.1f}" fill="var(--band)"/>')
        axes(p, [(i, f"{'F' if st.startswith('A-f') else 'P'}{k}") for i, (st, k) in enumerate(cells)], [(v, str(v)) for v in (0.5, 1, 2, 3)], xs=xs, ys=ys, xlabel="state (F fast, P persistent) and ticks", ylabel="realised over predicted")
        hline(p, ys(1.0), dash=False, color=INK2)
        for ver, col, off in (("v1_frozen", S[0], -4), ("v4_v2a_state_factor_loo", S[1], 4)):
            for i, (st, k) in enumerate(cells):
                c = d[tag][ver][st][k]
                if c["ratio_real_over_pred"]:
                    dot(p, xs(i) + off, ys(c["ratio_real_over_pred"]), col, f"{label} {ver} {st} {k}t ratio {c['ratio_real_over_pred']} (reach within prediction {c['reached_within_prediction']})")
                    rows.append([label, ver, st, k, c["ratio_real_over_pred"], c["reached_within_prediction"]])
        panels.append(p.svg())
    return figure("clock", "3. The delivered clock: frozen (v1) against day-scaled with state factor (v4)",
                  "The shaded band is within 20 percent of calibrated. v1 lands 4 of 32 cells in it; v4 lands 22 of 32 with a reach-within-prediction share of 0.48 against 0.50 ideal.",
                  panels, [("v1 frozen totals", S[0]), ("v4 matched day scale x leave-one-day-out state factor", S[1])],
                  ["session", "version", "state", "scale", "realised / predicted", "reached within prediction"], rows,
                  note="Ratios above 1 mean the clock said too soon; v4's factors for a day never use that day.")


def f4_beyond():
    measures = [("plus60_600_volume", "volume"), ("plus60_600_path", "path"), ("plus60_600_range", "range"), ("plus60_600_disp", "dispersion"), ("plus60_600_t_first_tick", "first tick"), ("plus60_600_hold_share", "hold share")]
    set_margin(72)
    panels, rows = [], []
    for tag, label in TAGS:
        a = J(f"beyond-direction-prebirth-{tag}-summary.json")["beyond_direction"]["auc_persistent_vs_fast"]
        p = Panel(label)
        xs = xlin(0.2, 0.8); ys = lambda i: MT + 8 + i * (PH - MT - MB - 16) / 5
        axes(p, [(v, str(v)) for v in (0.3, 0.5, 0.7)], [], xs=xs, ys=lambda v: v, xlabel="AUC, persistent over fast-collapse")
        p.add(f'<line x1="{xs(0.5):.1f}" x2="{xs(0.5):.1f}" y1="{MT}" y2="{PH - MB}" stroke="{INK2}" stroke-width="1.2"/>')
        for i, (k, nm) in enumerate(measures):
            v = a[k][0] if a.get(k) else None
            p.add(f'<text x="{ML - 4}" y="{ys(i) + 3:.1f}" class="tick" text-anchor="end">{esc(nm)}</text>')
            if v is not None:
                p.add(f'<line x1="{xs(0.5):.1f}" x2="{xs(v):.1f}" y1="{ys(i):.1f}" y2="{ys(i):.1f}" stroke="{S[0]}" stroke-width="2"/>')
                dot(p, xs(v), ys(i), S[0], f"{label} {nm}: AUC {v}")
                rows.append([label, nm, v])
        panels.append(p.svg())
    return figure("beyond", "4. What the state carries besides direction (600 s after the +60 anchor)",
                  "The persistent state marks a quieter aftermath on every session: less volume, path and range, a slower first tick and a longer hold. Most of it is pre-birth activity carried forward.",
                  panels, [], ["session", "measure", "AUC persistent vs fast"], rows)


def f5_prebirth():
    targets = [("time_to_3t_either", "3t either"), ("time_to_3t_with", "3t with"), ("range_600_from_plus60", "600 s range"), ("volume_300_from_plus60", "300 s volume"), ("oriented_net_300_from_plus60", "direction")]
    set_margin(78)
    panels, rows = [], []
    for tag, label in TAGS:
        sp = J(f"beyond-direction-prebirth-{tag}-summary.json")["prebirth"]["spearman"]
        p = Panel(label)
        xs = xlin(-0.8, 1.0); ys = lambda i: MT + 10 + i * (PH - MT - MB - 20) / 4
        axes(p, [(v, str(v)) for v in (-0.5, 0, 0.5)], [], xs=xs, ys=lambda v: v, xlabel="Spearman rho of the pre-birth 300 s feature")
        p.add(f'<line x1="{xs(0):.1f}" x2="{xs(0):.1f}" y1="{MT}" y2="{PH - MB}" stroke="{INK2}" stroke-width="1.2"/>')
        for i, (t, nm) in enumerate(targets):
            p.add(f'<text x="{ML - 4}" y="{ys(i) + 3:.1f}" class="tick" text-anchor="end">{esc(nm)}</text>')
            for feat, col, off in (("pre300_volume", S[0], -4), ("pre300_path", S[1], 4)):
                r = sp[t].get(feat)
                if r:
                    bar_h(p, xs(0), xs(r["rho"]), ys(i) + off, 6, col, f"{label} {feat} vs {nm}: rho {r['rho']} (n {r['n']})")
                    rows.append([label, feat, nm, r["rho"], r["n"]])
        panels.append(p.svg())
    return figure("prebirth", "5. Pre-birth activity predicts the clocks, not the direction",
                  "The 300 s volume and path before t0 correlate about minus 0.5 with the time to 3 ticks and about plus 0.6 with the 600 s range on all four sessions, and 0.0 with the oriented 300 s change.",
                  panels, [("pre-birth 300 s volume", S[0]), ("pre-birth 300 s path length", S[1])], ["session", "feature", "target", "rho", "n"], rows)


def f6_recognition():
    set_margin(44)
    H = ["1", "5", "20", "60", "300"]
    panels, rows = [], []
    for tag, label in TAGS:
        d = J(f"dipole-post-recognition-{tag}-summary.json")
        p = Panel(label)
        xs = lambda i: ML + 10 + i * (PW - ML - MR - 62) / 4
        ys = ylin(0.2, 0.85)
        axes(p, [(i, f"{h} s") for i, h in enumerate(H)], [(v, f"{v:.1f}") for v in (0.3, 0.5, 0.7)], xs=xs, ys=ys, xlabel="horizon after recognition", ylabel="with-share of non-flat")
        hline(p, ys(0.5), dash=False, color=INK2)
        ends = []
        ctl = d["day_reference"]["touch_imbalance_control_all_active_seconds"]["touch_imbalance"]
        series = [("touch aligned to birth", d["arms"]["book/aligned"]["horizons"], "with_birth", "against_birth", S[0], False),
                  ("touch opposed to birth", d["arms"]["book/opposed"]["horizons"], "with_birth", "against_birth", S[1], False),
                  ("baseline, birth polarity", d["arms"]["baseline"]["horizons"], "with_birth", "against_birth", S[2], False),
                  ("control: heavier touch side, all active seconds", ctl, "with_heavier_side", "against_heavier_side", MUTED, True)]
        for nm, hz, a, b, col, dash in series:
            pts = []
            for i, h in enumerate(H):
                x = hz.get(h) or hz.get(int(h)) or {}
                w, ag = x.get(a, 0), x.get(b, 0)
                if w + ag:
                    v = w / (w + ag); pts.append((xs(i), ys(v)))
                    rows.append([label, nm, h, w, ag, round(v, 3)])
            polyline(p, pts, col, dash)
            if pts:
                ends.append([pts[-1][1], nm.split(",")[0].split(":")[0]])
        ends.sort()
        for j in range(1, len(ends)):
            if ends[j][0] - ends[j - 1][0] < 10:
                ends[j][0] = ends[j - 1][0] + 10
        for yy, nm in ends:
            p.add(f'<text x="{xs(4) + 5:.1f}" y="{yy + 3:.1f}" class="dl" style="fill:{INK2}">{esc(nm[:9])}</text>')
        panels.append(p.svg())
    return figure("recognition", "6. After the actual archived recognition: direction, and the touch read against its control",
                  "Birth polarity carries nothing at any horizon on any session. The heavier touch side wins the next few ticks and decays to the all-seconds control by 300 s; the control has no dipole in it.",
                  panels, [("touch aligned to birth", S[0]), ("touch opposed to birth", S[1]), ("baseline, birth polarity", S[2]), ("control, heavier touch side at every active second", MUTED)],
                  ["session", "series", "horizon (s)", "with", "against", "with-share"], rows, note="Opposed is drawn as with-share of the birth polarity, so it mirrors aligned below 0.5.")


def f7_next_burst():
    set_margin(44)
    panels, rows = [], []
    for tag, label in TAGS:
        tr = J(f"other-things-{tag}-summary.json")["transitions"]
        nb = J(f"next-burst-forecast-{tag}-summary.json")["forecast_state"]["all_next_after_anchor"]
        p = Panel(label)
        cats = [("after persistent", tr["a_state_rows"]["A-persistent"]["next_flip_share"]), ("after fast", tr["a_state_rows"]["A-fast-collapse"]["next_flip_share"]),
                ("after P", tr["seed_rows"]["P"]["next_flip_share"]), ("after O", tr["seed_rows"]["O"]["next_flip_share"])]
        xs = lambda i: ML + 22 + i * (PW - ML - MR - 44) / 5
        ys = ylin(0, 0.9)
        axes(p, [(i, lab) for i, lab in enumerate(("pers", "fast", "P", "O"))] + [(4.3, "right"), (5.3, "wrong")], [(v, f"{v:.1f}") for v in (0.2, 0.4, 0.6, 0.8)], xs=xs, ys=ys, ylabel="share")
        hline(p, ys(tr["base_next_flip_share"]))
        for i, (nm, v) in enumerate(cats):
            bar_v(p, xs(i), 22, ys(0), ys(v), S[0], f"{label} next burst flips {nm}: {v} (base {tr['base_next_flip_share']})")
            rows.append([label, f"next burst flips {nm}", v])
        r, w = nb["next_window_when_forecast_right"], nb["next_window_when_forecast_wrong"]
        ra = r["against"] / max(1, r["with_"] + r["against"]); ww = w["with_"] / max(1, w["with_"] + w["against"])
        bar_v(p, xs(4.3), 22, ys(0), ys(ra), S[1], f"{label} forecast right: price against that burst {ra:.3f} ({r['against']} of {r['with_'] + r['against']})")
        bar_v(p, xs(5.3), 22, ys(0), ys(ww), S[1], f"{label} forecast wrong: price with the burst that came {ww:.3f} ({w['with_']} of {w['with_'] + w['against']})")
        rows += [[label, "forecast right: price against that burst", round(ra, 3)], [label, "forecast wrong: price with the burst that came", round(ww, 3)]]
        p.add(f'<text x="{xs(4.8):.1f}" y="{MT + 2}" class="tick" text-anchor="middle">absorption</text>')
        panels.append(p.svg())
    return figure("nextburst", "7. The state forecasts the next burst's side, and the expected burst is absorbed",
                  "Flip share of the next frozen-detector event (dashed line is the day's base rate). When the forecast is right the price moves against that burst 64 to 70 percent of the time; when it is wrong, with it.",
                  panels, [("next-burst flip share", S[0]), ("absorption: against when right, with when wrong", S[1])], ["session", "quantity", "share"], rows)


def f8_cells():
    d = J("cell-flip-diagnosis-4day.json")["chance"]
    panels, rows = [], []
    for tag, label in TAGS:
        c = d[tag]
        p = Panel(label)
        xs = lambda i: ML + 60 + i * 100
        ys = ylin(0, 70)
        axes(p, [(0, "observed"), (1, "expected by chance")], [(v, str(v)) for v in (0, 20, 40, 60)], xs=xs, ys=ys, ylabel="cells beyond 0.42 / 0.58")
        bar_v(p, xs(0), 40, ys(0), ys(c["beyond_008"]), S[0], f"{label}: {c['beyond_008']} of {c['cells_n30']} cells beyond the band")
        bar_v(p, xs(1), 40, ys(0), ys(c["expected_beyond_008_if_no_information"]), MUTED, f"{label}: {c['expected_beyond_008_if_no_information']} expected with no information")
        p.add(f'<text x="{xs(0):.1f}" y="{ys(c["beyond_008"]) - 4:.1f}" class="dl" text-anchor="middle">{c["beyond_008"]}</text>')
        p.add(f'<text x="{xs(1):.1f}" y="{ys(c["expected_beyond_008_if_no_information"]) - 4:.1f}" class="dl" text-anchor="middle">{c["expected_beyond_008_if_no_information"]}</text>')
        panels.append(p.svg())
        rows.append([label, c["cells_n30"], c["beyond_008"], c["expected_beyond_008_if_no_information"]])
    x = d["cross_day"]
    for k, v in x["pairwise"].items():
        rows.append([k, "", f"same sign {v['same_sign_share']}", f"rho {v['spearman_rho']}"])
    rows.append(["all four days same sign", x["common_cells"], x["same_sign_all_days"], x["expected_same_sign_all_days_if_independent"]])
    return figure("cells", "8. Direction cells: structure within each day, none across days",
                  "Each session has about twice the extreme direction cells chance predicts, and across sessions the signs agree at chance: 45 of 355 cells on the same side all four days where 44 is expected. The lifts are each day's drift.",
                  panels, [("observed", S[0]), ("expected with no information", MUTED)], ["session or pair", "cells with 30+ decided", "beyond band / same-sign", "expected / rho"], rows)


def f9_ssos():
    panels, rows = [], []
    for tag, label in TAGS:
        d = J(f"chain-play-filter-{tag}-summary.json")
        p = Panel(label)
        xs = xlin(-5, 5); y = (MT + PH - MB) / 2
        axes(p, [(v, f"{v:+d}" if v else "0") for v in (-4, -2, 0, 2, 4)], [], xs=xs, ys=lambda v: v, xlabel="gross return, ticks, onset+5 to onset+30")
        p.add(f'<line x1="{xs(0):.1f}" x2="{xs(0):.1f}" y1="{MT}" y2="{PH - MB}" stroke="{INK2}" stroke-width="1.2"/>')
        vals = [r["return_ticks"] for r in d["play_rows"] if r["return_ticks"] is not None]
        from collections import Counter
        cnt = Counter(vals)
        for v, n in cnt.items():
            for j in range(n):
                dot(p, xs(v), y - 10 - j * 11, S[0], f"{label} SSOS instance return {v:+.1f} ticks")
        if vals:
            m = sum(vals) / len(vals)
            p.add(f'<line x1="{xs(m):.1f}" x2="{xs(m):.1f}" y1="{PH - MB - 24}" y2="{PH - MB}" stroke="{S[1]}" stroke-width="2.5"><title>{label} mean {m:+.2f} ticks over {len(vals)} instances</title></line>')
            p.add(f'<text x="{xs(m):.1f}" y="{PH - MB - 27}" class="dl" text-anchor="middle">mean {m:+.2f}</text>')
        panels.append(p.svg())
        rows.append([label, d["play"]["n"], d["play"]["frequency"], d["play"]["mean"], f"{d['play']['with_']} / {d['play']['flat']} / {d['play']['against']}", d["eligible_universe"]])
    return figure("ssos", "9. The frozen SSOS play as written, per session",
                  "10 / 10 / 3 / 7 instances on October 2 / 3 / 17 / 18 against 399 to 415 eligible targets. Gross means are negative on three of four sessions; the frozen base averaged plus 0.26 ticks.",
                  panels, [("instance return", S[0]), ("session mean", S[1])], ["session", "instances", "frequency of eligible", "mean (ticks)", "with / flat / against", "eligible targets"], rows,
                  note="Each dot is one play instance; stacked dots share a return. Entry with the current polarity at onset+5 after a confirmed endpoint, exit at onset+30, S,S,O,S predecessors knowable before t0.")


def main():
    OUT.mkdir(exist_ok=True)
    figs = [f1_clocks(), f2_duration(), f3_clock(), f4_beyond(), f5_prebirth(), f6_recognition(), f7_next_burst(), f8_cells(), f9_ssos()]
    css = """
<title>NG Dipole Renders</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* layout: one column of figures, each a strip of four session panels; numbers in the mono face */
:root { --surface:#fcfcfb; --paper:#f4f4f2; --ink:#111210; --ink2:#55574f; --muted:#9a9c93; --grid:#e3e4df; --band:#eef1f6;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --sans:"IBM Plex Sans", system-ui, sans-serif; --mono:"IBM Plex Mono", ui-monospace, Menlo, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --surface:#1a1a19; --paper:#222321; --ink:#f0efec; --ink2:#c3c2b7; --muted:#7f8178; --grid:#33352f; --band:#26303d;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; color-scheme: dark } }
:root[data-theme="dark"] { --surface:#1a1a19; --paper:#222321; --ink:#f0efec; --ink2:#c3c2b7; --muted:#7f8178; --grid:#33352f; --band:#26303d;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; color-scheme: dark }
body { background: var(--surface); color: var(--ink); font-family: var(--sans); padding-block: 24px 48px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
header { max-width: 1240px; margin: 0 auto 28px; }
h1 { font-size: 1.6rem; font-weight: 600; margin: 0 0 6px; text-wrap: balance; }
header p { color: var(--ink2); margin: 0; max-width: 70ch; line-height: 1.45; }
.fig { max-width: 1240px; margin: 0 auto 40px; padding-top: 18px; border-top: 1px solid var(--grid); }
.fig h2 { font-size: 1.1rem; font-weight: 600; margin: 0 0 4px; text-wrap: balance; }
.reading { color: var(--ink2); margin: 0 0 10px; max-width: 80ch; line-height: 1.45; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 0 0 8px; font-size: 0.82rem; color: var(--ink2); }
.li i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.panels { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }
.panel { width: 100%; height: auto; background: var(--paper); border-radius: 6px; }
.ptitle { font: 600 11px var(--sans); fill: var(--ink); }
.tick, .alabel, .dl { font: 9.5px var(--mono); fill: var(--ink2); }
.alabel { fill: var(--muted); }
.dl { fill: var(--ink); }
.grid { stroke: var(--grid); stroke-width: 1; }
.axis { stroke: var(--grid); stroke-width: 1; }
.note { color: var(--ink2); font-size: 0.85rem; margin: 8px 0 0; max-width: 80ch; }
details { margin-top: 10px; font-size: 0.85rem; } summary { cursor: pointer; color: var(--ink2); }
.tw { overflow-x: auto; margin-top: 6px; } table { border-collapse: collapse; font-family: var(--mono); font-size: 0.78rem; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 3px 10px 3px 0; border-bottom: 1px solid var(--grid); white-space: nowrap; } th { color: var(--ink2); font-weight: 500; }
@media print { .fig { break-inside: avoid; } details { display: none; } }
</style>"""
    head = ('<header><h1>NG Dipole Renders</h1><p>The dipole work of the October discovery pass, drawn from the committed summaries on codex/ng-shadow-discovery-20261108: '
            'the frozen roll-20 detector on four sessions (October 2, 3, 17 and 18, 2023), its clocks, its states, and what they do and do not carry. '
            'Every figure has its numbers in a table below it. Hover a mark for its value. No trade cost enters anything shown.</p></header>')
    (OUT / "ng-dipole-renders.html").write_text(css + head + "".join(figs))
    print("wrote", OUT / "ng-dipole-renders.html", sum(len(f) for f in figs), "bytes of figures")


if __name__ == "__main__":
    main()
