"""The plain events of the paper runner (Part A). No I/O, no clock.

A `place` is where an event stands in the recording: (message number, index inside that frame's data list).
A price that is NaN (a float NaN or the string 'NaN') is a missing input and becomes None, never a number.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

MS_TO_NS = 1_000_000


def num(x) -> Optional[float]:
    """A price or size as a float; None where the feed says NaN or gives nothing."""
    if x is None:
        return None
    if isinstance(x, str):
        if x.strip().lower() == 'nan':
            return None
        x = float(x)
    x = float(x)
    return None if math.isnan(x) else x


@dataclass(frozen=True)
class PRINT:
    place: tuple          # (msg_no, index in the frame)
    t_ns: int             # our receive time
    time_ns: int          # the feed's time in milliseconds made into nanoseconds, exactly
    sequence: int
    price: Optional[float]
    size: Optional[float]
    side: Optional[str]   # 'B', 'S' or None
    bid: Optional[float]  # the print's own best bid
    offer: Optional[float]


@dataclass(frozen=True)
class QUOTE:
    place: tuple
    t_ns: int
    bid: Optional[float]
    offer: Optional[float]
    bid_size: Optional[float]
    offer_size: Optional[float]


@dataclass(frozen=True)
class DAYVOLUME:
    place: tuple
    t_ns: int
    day_volume: Optional[float]
