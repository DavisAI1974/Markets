"""
event_calendar.py — scheduled macro-event proximity for confidence dampening.

Maps a wall-clock timestamp to a confidence multiplier that reflects whether
the chunk falls inside (or near) a known high-volatility event window:
  - FOMC rate decisions (typically 18:00 UTC on decision Wednesdays)
  - US CPI / PPI prints (12:30 UTC on release days)
  - ETF flow/decision days (variable)
  - Major employment prints (NFP at 12:30 UTC first Friday of month)

Two factors combine multiplicatively, capped at the more conservative one
to avoid stacking dampers too aggressively:
  1. Time-of-day proximity: ±30 min of an event = strong dampener (0.7),
     ±60 min = mild (0.85), beyond that = none on time-of-day axis.
  2. Day-of-week: weekends get a baseline dampener (0.85) since weekend
     liquidity is thin and regime classification is less reliable.

Calendar source: events_calendar.json at repo root (loaded once at module
load with mtime-watch). Empty/missing file = no event dampeners; weekends
still apply.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Multiplier policy (HARDCODE accepted as policy this session)
# ---------------------------------------------------------------------------

EVENT_PROXIMITY_TIGHT_MIN = 30      # within this window: tight dampener
EVENT_PROXIMITY_LOOSE_MIN = 60      # within this window: loose dampener
EVENT_DAMPENER_TIGHT = 0.7          # ±30 min of event
EVENT_DAMPENER_LOOSE = 0.85         # ±60 min of event
WEEKEND_DAMPENER = 0.85             # any chunk on Sat/Sun
DEFAULT_MULTIPLIER = 1.0


# ---------------------------------------------------------------------------
# Event record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Event:
    ts_utc: float           # unix epoch seconds
    kind: str               # "FOMC" | "CPI" | "PPI" | "NFP" | "ETF_FLOW" | "OTHER"
    label: str              # human description, e.g. "FOMC May 2026"

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        ts = d.get("ts_utc")
        if ts is None and d.get("ts_iso"):
            iso = d["ts_iso"]
            if iso.endswith("Z"):
                iso = iso[:-1] + "+00:00"
            ts = datetime.fromisoformat(iso).timestamp()
        if ts is None:
            raise ValueError(f"event missing ts_utc or ts_iso: {d}")
        return cls(
            ts_utc=float(ts),
            kind=str(d.get("kind", "OTHER")).upper(),
            label=str(d.get("label", "")),
        )


# ---------------------------------------------------------------------------
# Calendar loader (mtime-aware)
# ---------------------------------------------------------------------------

class EventCalendar:
    """In-process cache of scheduled events with mtime-based hot reload."""

    def __init__(self, path: str | None):
        self.path = path
        self._mtime: float = 0.0
        self._events: list[Event] = []
        if path:
            self._maybe_reload()

    def _maybe_reload(self) -> None:
        if not self.path or not os.path.exists(self.path):
            self._events = []
            self._mtime = 0.0
            return
        try:
            mt = os.path.getmtime(self.path)
        except OSError:
            return
        if mt == self._mtime:
            return
        try:
            with open(self.path) as f:
                doc = json.load(f)
            raw = doc.get("events", []) if isinstance(doc, dict) else doc
            self._events = sorted(
                (Event.from_dict(d) for d in raw if isinstance(d, dict)),
                key=lambda e: e.ts_utc,
            )
            self._mtime = mt
        except Exception:
            # Bad JSON / parse error: keep prior events, don't crash
            return

    @property
    def events(self) -> list[Event]:
        self._maybe_reload()
        return self._events

    def nearest(self, ts_utc: float, window_min: float = EVENT_PROXIMITY_LOOSE_MIN
                ) -> tuple[Event, float] | None:
        """Return (nearest_event, |delta_minutes|) within window, else None."""
        if not self.events:
            return None
        window_s = window_min * 60.0
        best: tuple[Event, float] | None = None
        for ev in self.events:
            d = abs(ev.ts_utc - ts_utc)
            if d <= window_s and (best is None or d < best[1]):
                best = (ev, d)
        if best is None:
            return None
        return best[0], best[1] / 60.0


# ---------------------------------------------------------------------------
# Multiplier resolver
# ---------------------------------------------------------------------------

def _is_weekend(ts_utc: float) -> bool:
    """Saturday=5, Sunday=6 in datetime.weekday()."""
    return datetime.fromtimestamp(ts_utc, tz=timezone.utc).weekday() >= 5


def event_multiplier_for_ts(
    ts_utc: float,
    calendar: EventCalendar | None,
) -> tuple[float, str]:
    """Return (multiplier, note). Multiplier in (0, 1]. note is a short
    human reason or "" when multiplier == 1.0.

    Combines weekend dampener with event-proximity dampener; takes the
    more conservative (smaller) of the two when both fire.
    """
    weekend = _is_weekend(ts_utc)
    proximity_mult = DEFAULT_MULTIPLIER
    proximity_note = ""
    if calendar is not None:
        hit = calendar.nearest(ts_utc, window_min=EVENT_PROXIMITY_LOOSE_MIN)
        if hit is not None:
            ev, dmin = hit
            if dmin <= EVENT_PROXIMITY_TIGHT_MIN:
                proximity_mult = EVENT_DAMPENER_TIGHT
                proximity_note = (f"within ±{int(EVENT_PROXIMITY_TIGHT_MIN)}min of "
                                   f"{ev.kind} ({ev.label}); -{int((1-EVENT_DAMPENER_TIGHT)*100)}%")
            else:
                proximity_mult = EVENT_DAMPENER_LOOSE
                proximity_note = (f"within ±{int(EVENT_PROXIMITY_LOOSE_MIN)}min of "
                                   f"{ev.kind} ({ev.label}); -{int((1-EVENT_DAMPENER_LOOSE)*100)}%")
    if weekend:
        weekend_note = f"weekend session; -{int((1-WEEKEND_DAMPENER)*100)}%"
        if proximity_mult < WEEKEND_DAMPENER:
            return proximity_mult, proximity_note
        return WEEKEND_DAMPENER, weekend_note
    return proximity_mult, proximity_note


# ---------------------------------------------------------------------------
# CLI for inspecting the calendar
# ---------------------------------------------------------------------------

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--calendar-path", type=str, default="events_calendar.json")
    p.add_argument("--probe-ts", type=float, default=None,
                   help="Unix epoch to probe; defaults to now")
    args = p.parse_args()

    cal = EventCalendar(args.calendar_path)
    print(f"Loaded {len(cal.events)} events from {args.calendar_path}")
    for ev in cal.events[:20]:
        dt = datetime.fromtimestamp(ev.ts_utc, tz=timezone.utc)
        print(f"  {dt.isoformat():25s}  {ev.kind:<10s}  {ev.label}")

    import time
    ts = args.probe_ts if args.probe_ts is not None else time.time()
    mult, note = event_multiplier_for_ts(ts, cal)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    print(f"\nProbe ts={dt.isoformat()}  multiplier={mult:.2f}  note={note or '(none)'}")


if __name__ == "__main__":
    main()
