#!/usr/bin/env python3
"""Build the logo contact sheet - the three candidates at the sizes that actually decide it.

A logo is not chosen at 512px. A plugin icon is seen at 32 and sometimes 16, often masked to a
circle by the host, and on both light and dark chrome. This renders every candidate across all of
that on one page so the choice is made against how it will really be used, not against a hero shot.

    python mcp_server/logo/make_logo_sheet.py

Writes `logo_sheet.html` beside the SVGs. Self-contained - the SVGs are inlined, nothing is fetched.
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))

CANDIDATES = [
    ("A", "markets_terminal_a_curve.svg", "Forward Curve",
     "The full mark: anchor line, week one, the weekend gap, week two, the print. Most meaning, "
     "most detail - and detail is what dies first at 16px."),
    ("B", "markets_terminal_b_brackets.svg", "Bracketed Read",
     "Brackets carry both halves of the name at once - the terminal, and a curve held inside a "
     "frame it cannot write past. The cursor says it is waiting, not acting."),
    ("C", "markets_terminal_c_gap.svg", "The Gap",
     "Two strokes and a hole. Reduced to the one rule that is ours: the untraded hours are left "
     "OUT. The only one of the three still legible at 16px."),
]

SIZES = [512, 128, 64, 32, 24, 16]


def load(name: str) -> str:
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def sized(svg: str, px: int) -> str:
    """Re-stamp width/height; the viewBox does the scaling."""
    return (svg.replace('width="512" height="512"', 'width="%d" height="%d"' % (px, px))
               .replace("<?xml version='1.0' encoding='utf-8'?>", ""))


def main() -> None:
    parts = []
    for tag, fname, title, note in CANDIDATES:
        svg = load(fname)
        row = "".join(
            '<figure class="s"><div class="ico">%s</div><figcaption>%d</figcaption></figure>'
            % (sized(svg, px), px) for px in SIZES
        )
        circ = "".join(
            '<figure class="s"><div class="ico circ">%s</div><figcaption>%d</figcaption></figure>'
            % (sized(svg, px), px) for px in (128, 64, 32)
        )
        parts.append(f"""
        <section class="cand">
          <h2><span class="tag">{tag}</span> {title}</h2>
          <p class="note">{note}</p>
          <h3>on dark</h3>   <div class="strip dark">{row}</div>
          <h3>on light</h3>  <div class="strip light">{row}</div>
          <h3>circle-masked, as some hosts render it</h3>
          <div class="strip dark">{circ}</div>
          <p class="file">{fname}</p>
        </section>""")

    lockup = load(CANDIDATES[2][1])
    html = f"""<!doctype html>
<meta charset="utf-8">
<title>Markets Terminal - logo candidates</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; padding:48px 40px 96px; background:#0A0E15; color:#E8EDF4;
         font:15px/1.6 ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif; }}
  h1 {{ font-size:26px; margin:0 0 6px; letter-spacing:-.2px; }}
  .sub {{ color:#8FA0B5; margin:0 0 40px; max-width:60ch; }}
  .cand {{ border-top:1px solid #1E2A3A; padding:32px 0 8px; }}
  h2 {{ font-size:19px; margin:0 0 4px; font-weight:600; }}
  .tag {{ display:inline-block; min-width:26px; text-align:center; background:#42C2C6; color:#06131A;
          border-radius:6px; padding:1px 7px; font-size:14px; font-weight:700; margin-right:8px; }}
  .note {{ color:#8FA0B5; margin:0 0 22px; max-width:72ch; }}
  h3 {{ font-size:12px; text-transform:uppercase; letter-spacing:.09em; color:#66788F;
        margin:22px 0 10px; font-weight:600; }}
  .strip {{ display:flex; align-items:flex-end; gap:26px; flex-wrap:wrap;
            padding:22px 24px; border-radius:14px; }}
  .strip.dark  {{ background:#12181F; }}
  .strip.light {{ background:#F4F6F9; }}
  .strip.light figcaption {{ color:#5A6B80; }}
  figure.s {{ margin:0; display:flex; flex-direction:column; align-items:center; gap:8px; }}
  .ico {{ display:flex; align-items:flex-end; }}
  .circ svg {{ border-radius:50%; }}
  figcaption {{ font-size:11px; color:#66788F; font-variant-numeric:tabular-nums; }}
  .file {{ font:12px ui-monospace,SFMono-Regular,Menlo,monospace; color:#4E6076; margin:20px 0 0; }}
  .lock {{ display:flex; align-items:center; gap:20px; margin:38px 0 0; padding:26px 30px;
           background:#12181F; border-radius:14px; }}
  .wm {{ font-size:27px; font-weight:650; letter-spacing:-.4px; }}
  .wm small {{ display:block; font-size:12.5px; font-weight:400; color:#8FA0B5;
               letter-spacing:.02em; margin-top:3px; }}
</style>
<h1>Markets Terminal - logo candidates</h1>
<p class="sub">Built on D32: the product is a curve. Each mark carries the weekend GAP, because a
line drawn through untraded hours is the one thing our own render rule forbids.</p>
{''.join(parts)}
<section class="cand">
  <h2>Lockup</h2>
  <p class="note">Icon plus name, for the connector card.</p>
  <div class="lock">{sized(lockup, 64)}<div class="wm">Markets Terminal<small>Read-only access to the DavisAI Markets environment</small></div></div>
</section>
"""
    out = os.path.join(HERE, "logo_sheet.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote", out)


if __name__ == "__main__":
    main()
