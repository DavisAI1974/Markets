#!/usr/bin/env python3
"""Phone-readable logo sheet - one portrait SVG instead of a scrolling HTML page.

The HTML contact sheet is the right tool at a desk and the wrong one on a phone. This renders the
same decision - each candidate large, then at 64 and 32 on both dark and light - as a SINGLE
portrait image that a phone shows whole.

    python mcp_server/logo/make_phone_sheet.py
"""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

CANDIDATES = [
    ("A", "markets_terminal_a_curve.svg", "Forward Curve",
     "Anchor, week one, the gap, week two, the print."),
    ("B", "markets_terminal_b_brackets.svg", "Bracketed Read",
     "Brackets = terminal AND read-only. Cursor waits."),
    ("C", "markets_terminal_c_gap.svg", "The Gap",
     "Two strokes and a hole. Readable at 16px."),
]

W = 760
ROW_H = 430
HEAD_H = 150


def nest(path: str, x: float, y: float, size: float) -> str:
    """Re-nest a standalone 512x512 SVG as an inner <svg> at a given box.

    Gradient ids are already prefixed per candidate (a_/b_/c_), so nesting cannot collide.
    """
    with open(os.path.join(HERE, path), encoding="utf-8") as fh:
        src = fh.read()
    src = re.sub(r"<\?xml[^>]*\?>", "", src)
    src = re.sub(r"<title>.*?</title>", "", src, flags=re.S)
    return re.sub(
        r"<svg\b[^>]*>",
        '<svg viewBox="0 0 512 512" x="%g" y="%g" width="%g" height="%g">' % (x, y, size, size),
        src, count=1,
    )


def main() -> None:
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
        'font-family="ui-sans-serif,-apple-system,Segoe UI,Roboto,sans-serif">' % (
            W, HEAD_H + ROW_H * len(CANDIDATES) + 24, W, HEAD_H + ROW_H * len(CANDIDATES) + 24),
        '<rect width="100%" height="100%" fill="#0A0E15"/>',
        '<text x="40" y="62" fill="#E8EDF4" font-size="34" font-weight="650">'
        'Markets Terminal</text>',
        '<text x="40" y="98" fill="#8FA0B5" font-size="20">Three logo candidates</text>',
        '<text x="40" y="126" fill="#66788F" font-size="17">Every mark carries the weekend GAP.</text>',
    ]

    for i, (tag, fname, title, note) in enumerate(CANDIDATES):
        top = HEAD_H + i * ROW_H
        out.append('<line x1="40" y1="%d" x2="%d" y2="%d" stroke="#1E2A3A" stroke-width="2"/>'
                   % (top, W - 40, top))
        out.append('<rect x="40" y="%d" width="46" height="34" rx="8" fill="#42C2C6"/>' % (top + 26))
        out.append('<text x="63" y="%d" fill="#06131A" font-size="22" font-weight="700" '
                   'text-anchor="middle">%s</text>' % (top + 51, tag))
        out.append('<text x="102" y="%d" fill="#E8EDF4" font-size="26" font-weight="600">%s</text>'
                   % (top + 51, title))
        out.append('<text x="40" y="%d" fill="#8FA0B5" font-size="19">%s</text>' % (top + 88, note))

        # hero
        out.append(nest(fname, 40, top + 110, 230))

        # the sizes that actually decide it, on both chromes
        out.append('<rect x="304" y="%d" width="416" height="122" rx="14" fill="#12181F"/>'
                   % (top + 110))
        out.append(nest(fname, 330, top + 139, 64))
        out.append(nest(fname, 428, top + 155, 32))
        out.append('<text x="330" y="%d" fill="#66788F" font-size="15">64</text>' % (top + 224))
        out.append('<text x="428" y="%d" fill="#66788F" font-size="15">32</text>' % (top + 224))
        out.append('<text x="500" y="%d" fill="#66788F" font-size="16">on dark</text>' % (top + 178))

        out.append('<rect x="304" y="%d" width="416" height="122" rx="14" fill="#F4F6F9"/>'
                   % (top + 248))
        out.append(nest(fname, 330, top + 277, 64))
        out.append(nest(fname, 428, top + 293, 32))
        out.append('<text x="330" y="%d" fill="#5A6B80" font-size="15">64</text>' % (top + 362))
        out.append('<text x="428" y="%d" fill="#5A6B80" font-size="15">32</text>' % (top + 362))
        out.append('<text x="500" y="%d" fill="#5A6B80" font-size="16">on light</text>' % (top + 316))

    out.append("</svg>")
    dest = os.path.join(HERE, "logo_sheet_phone.svg")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("wrote", dest)


if __name__ == "__main__":
    main()
