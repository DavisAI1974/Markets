#!/usr/bin/env python3
"""Rasterize every logo SVG to PNG.

Exists because SVG is the right SOURCE format and the wrong DELIVERY format - a phone will not
reliably open one, which is how this got found. The SVGs stay authoritative; the PNGs are a render
of them, regenerated rather than hand-edited.

    pip install cairosvg
    python mcp_server/logo/rasterize.py
"""
from __future__ import annotations

import os

import cairosvg

HERE = os.path.dirname(os.path.abspath(__file__))

# (source, output width, square?) - icons are square, the contact sheet keeps its own aspect
JOBS = [
    ("markets_terminal_a_curve.svg", 512, True),
    ("markets_terminal_b_brackets.svg", 512, True),
    ("markets_terminal_c_gap.svg", 512, True),
    ("logo_sheet_phone.svg", 1080, False),
]


def main() -> None:
    for name, width, square in JOBS:
        src = os.path.join(HERE, name)
        dst = src[:-4] + ".png"
        kw = {"output_width": width}
        if square:
            kw["output_height"] = width
        cairosvg.svg2png(url=src, write_to=dst, **kw)
        print("wrote %-38s %8d bytes" % (os.path.basename(dst), os.path.getsize(dst)))


if __name__ == "__main__":
    main()
