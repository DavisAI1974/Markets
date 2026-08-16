#!/usr/bin/env python3
"""Render a completed S135 date-session with every forecast node and every realized trade point.

Each day is rendered as its own matplotlib figure (no pooled/downsampled actual path).  The final PNG
is a PIL contact sheet of those ten standalone day renders.  Forecast P25/P50/P75 values come from the
frozen curve_nodes; realized path is every MBO trade expressed as cumulative USD from that session open.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

import group_actual
import group_config as gc

RUNTIME_GID = "gdate"
MULT = 10000.0
ET = "America/New_York"


def install_config(cfg: dict) -> None:
    days = [str(x).replace("-", "") for x in cfg["days"]]
    seam = str(cfg.get("seam") or "").replace("-", "") or None
    gc.GROUPS[RUNTIME_GID] = {
        "window": f"{days[0]}..{days[-1]}",
        "days": days,
        "anchor": float(cfg["anchor"]),
        "anchor_date": str(cfg["anchor_date"]).replace("-", ""),
        "anchor_lasthr_dir": int(cfg.get("anchor_lasthr_dir", 0)),
        "mask_after": str(cfg["anchor_date"]).replace("-", ""),
        "seam": seam,
        "legs": ({"pre": str(cfg["pre_leg"]).lower(), "post": str(cfg["post_leg"]).lower()}
                 if seam else {"all": str(cfg["pre_leg"]).lower()}),
        "eia_thursdays": [str(x).replace("-", "") for x in cfg.get("eia", [])],
        "holidays": [],
        "basis": str(cfg.get("basis", "date-driven S135 historical run")),
    }


def session_x_from_hour(hour: float) -> float:
    h = float(hour)
    return h if h >= 18.0 else h + 24.0


def actual_session(day: str):
    store = gc.leg_for(RUNTIME_GID, day)
    ts, px = group_actual.load_trades(store, day)
    if px.size == 0:
        raise SystemExit(f"no actual trades for {day} {store}")
    et = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    hours = np.array([
        t.hour + t.minute / 60.0 + t.second / 3600.0 + t.microsecond / 3.6e9
        for t in et.to_pydatetime()
    ])
    x = np.where(hours < 18.0, hours + 24.0, hours)
    y = (px - float(px[0])) * MULT
    return x, y, store


def forecast_file(outputs: Path, day: str) -> Path:
    matches = sorted(outputs.glob(f"forecast_*_{day}.json"))
    if len(matches) != 1:
        raise SystemExit(f"expected one frozen forecast for {day}, found {matches}")
    return matches[0]


def render_day(outputs: Path, outdir: Path, day: str) -> Path:
    fpath = forecast_file(outputs, day)
    fc = json.loads(fpath.read_text(encoding="utf-8"))
    nodes = fc.get("curve_nodes")
    if not isinstance(nodes, list) or not nodes:
        raise SystemExit(f"{fpath}: curve_nodes missing")

    x_act, y_act, store = actual_session(day)
    x_fc = [session_x_from_hour(n["et_hour"]) for n in nodes]
    p25 = [float(n["p25_cum_usd"]) for n in nodes]
    p50 = [float(n["p50_cum_usd"]) for n in nodes]
    p75 = [float(n["p75_cum_usd"]) for n in nodes]

    fig, ax = plt.subplots(figsize=(10.5, 5.4), dpi=160)
    ax.plot(x_act, y_act, linewidth=1.0, label=f"Actual — all {len(y_act):,} trades")
    ax.plot(x_fc, p25, marker="o", linestyle="--", linewidth=1.2, label="Frankie P25 nodes")
    ax.plot(x_fc, p50, marker="o", linewidth=2.0, label="Frankie P50 nodes")
    ax.plot(x_fc, p75, marker="o", linestyle="--", linewidth=1.2, label="Frankie P75 nodes")
    ax.axhline(0.0, linewidth=0.7)

    for x, y in zip(x_fc, p50):
        ax.annotate(f"{y:+.0f}", (x, y), xytext=(0, 8), textcoords="offset points",
                    ha="center", fontsize=8)

    owner = str(fc.get("specialist") or "?")
    disposition = str(fc.get("disposition") or "?")
    guess = float(fc.get("guessed_net_usd") or 0.0) - float(fc.get("overnight_gap_usd") or 0.0)
    actual_net = float(y_act[-1])
    ax.set_title(
        f"{day[:4]}-{day[4:6]}-{day[6:]}  |  Owner {owner}  |  {disposition}  |  "
        f"P50 net {guess:+.0f}  |  actual {actual_net:+.0f} USD"
    )
    ax.set_xlabel("ET session clock")
    ax.set_ylabel("Cumulative USD from session open")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)

    ticks = [18, 20, 24, 28, 32, 36, 40, 41]
    labels = ["18", "20", "00", "04", "08", "12", "16", "17"]
    ax.set_xticks(ticks, labels)
    xmin = min(float(np.min(x_act)), min(x_fc))
    xmax = max(float(np.max(x_act)), max(x_fc))
    ax.set_xlim(min(18.0, xmin), max(41.0, xmax))

    note = f"{store.replace('ng_mbo_', '').upper()} • every realized trade point • every frozen S132 curve node"
    ax.text(0.01, 0.01, note, transform=ax.transAxes, fontsize=7, va="bottom")

    fig.tight_layout()
    out = outdir / f"{day}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def contact_sheet(paths: list[Path], out: Path) -> None:
    imgs = [Image.open(p).convert("RGB") for p in paths]
    width = max(im.width for im in imgs)
    normalized = []
    for im in imgs:
        if im.width != width:
            new_h = round(im.height * width / im.width)
            im = im.resize((width, new_h), Image.Resampling.LANCZOS)
        normalized.append(im)
    gap = 18
    total_h = sum(im.height for im in normalized) + gap * (len(normalized) - 1)
    sheet = Image.new("RGB", (width, total_h), "white")
    y = 0
    for im in normalized:
        sheet.paste(im, (0, y))
        y += im.height + gap
    sheet.save(out, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    install_config(cfg)
    outputs = ROOT / str(cfg["outputs"])
    args.out.mkdir(parents=True, exist_ok=True)
    daydir = args.out / "days"
    daydir.mkdir(parents=True, exist_ok=True)

    paths = [render_day(outputs, daydir, str(day).replace("-", "")) for day in cfg["days"]]
    final = args.out / "frankie_20250922_20251003_full_points.png"
    contact_sheet(paths, final)
    print(final)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
