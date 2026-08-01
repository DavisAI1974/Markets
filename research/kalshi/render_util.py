"""render_util.py - the ONE implementation of the walk's render rules (S107).

Both coordinators previously carried their own copy of break_gaps and their own copy of the
grid-hour -> timestamp mapping. The copies agreed, so the SAME two defects lived in both:

1. THE TERMINAL-POINT FOLD. The mapping was `day0 - 1d + h` when `h >= 18`, else `day0 + h`. The
   2-hourly grid runs from the PRIOR evening's 20:00 reopen through the forecast day, so a full
   13-point path reads 20, 22, 0, 2, ... 16, 18, 20. Under the old rule the trailing 18 and 20 were
   sent BACK to the prior evening - the day's CLOSING point, which is the number the coordinator
   scores, was drawn ~22 hours early and landed on top of its own opening point, with a spurious
   line running backwards across the whole session. Owners emitting an 11-point grid ending at 16
   (E, this block) dodged it; C and D did not.

2. ONE POLYLINE PER DAY. Each day was a separate ax.plot call, so the forecast rendered as N
   disconnected segments - the "days do not flow" complaint - while the ACTUAL curve was already
   drawn as a single break_gaps line. The two curves were not comparable as shapes.

Both are fixed here, once. S104 render rule is unchanged and now applies to the forecast too:
never bridge a session gap with a straight line - insert a NaN break wherever consecutive points
are more than max_gap_h apart, so matplotlib lifts the pen across weekends, holidays and halts.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

ET = "America/New_York"


def break_gaps(ct, cp, max_gap_h: float = 3.0):
    """S104 RENDER RULE. Insert a NaN break wherever consecutive points are >max_gap_h apart, so a
    weekend or holiday is a lifted pen rather than a fake diagonal. ct = epoch seconds, cp = values."""
    ct = np.asarray(ct, float)
    cp = np.asarray(cp, float)
    if ct.size < 2:
        return ct, cp
    gi = np.where(np.diff(ct) > max_gap_h * 3600.0)[0]
    if gi.size == 0:
        return ct, cp
    return np.insert(ct, gi + 1, ct[gi]), np.insert(cp, gi + 1, np.nan)


def path_times(day0: pd.Timestamp, path) -> list[pd.Timestamp]:
    """Map a day's 2-hourly ET grid onto real timestamps.

    The grid opens at the PRIOR calendar day's 20:00 reopen and runs through the forecast day, so
    the correct day offset is decided by the MIDNIGHT WRAP, not by the hour value alone: hours
    before the wrap belong to day0-1, everything from the wrap onward belongs to day0. That is what
    keeps a trailing 18:00/20:00 on the forecast day where it belongs (the close) instead of folding
    it back onto the open.
    """
    hs = [h for h, _ in path]
    if not hs:
        return []
    off = -1 if hs[0] >= 18 else 0
    out, prev = [], None
    for h in hs:
        if prev is not None and h < prev and off < 0:
            off += 1            # the midnight wrap, taken once
        out.append(day0 + pd.Timedelta(days=off) + pd.Timedelta(hours=h))
        prev = h
    return out


def plot_forecast(ax, xs, ys, *, color: str, label: str, lw: float = 1.2, z: int = 4,
                  max_gap_h: float = 3.0):
    """Draw a whole block's forecast as ONE polyline with NaN breaks at real session gaps.
    xs = tz-aware Timestamps across every day of the block, ys = matching prices."""
    if not xs:
        return
    order = np.argsort([x.value for x in xs])
    xs = [xs[i] for i in order]
    ys = [ys[i] for i in order]
    ts = np.array([x.timestamp() for x in xs], float)
    gt, gp = break_gaps(ts, np.asarray(ys, float), max_gap_h)
    gdt = pd.to_datetime(gt, unit="s", utc=True).tz_convert(ET)
    ax.plot(gdt, gp, color=color, lw=lw, zorder=z, label=label)


def brain_version(default: str = "unknown") -> str:
    """The LIVE brain version, read at render/assemble time. Both coordinators had 's102.8' hard
    coded into the title and into the emitted forecast JSON, so every artifact since that release
    has been mislabelled with a brain it did not run on."""
    import json, os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge", "ng_brain.json")
    try:
        return json.load(open(p))["meta"]["version"]
    except Exception:
        return default
