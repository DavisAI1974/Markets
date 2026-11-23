"""DXLink FEED_DATA frames into PRINT, QUOTE and DAYVOLUME events (Part A). Reads a 7e recording or one frame.

No sign-in, no socket, no order. A recording line of kind "received" holds the raw frame as a JSON string in "raw",
our receive time in "t_ns" and its "msg_no". Only the FULL format (a list of event objects) is read.
"""
from __future__ import annotations

import json
from typing import Iterator, Optional

from strategies.paper.events import DAYVOLUME, MS_TO_NS, PRINT, QUOTE, num

SIDES = {'BUY': 'B', 'SELL': 'S'}


def events_from_frame(raw: str, t_ns: int, msg_no: int) -> Iterator:
    """PRINT, QUOTE and DAYVOLUME events of one frame, in the frame's own order."""
    try:
        frame = json.loads(raw)
    except (TypeError, ValueError):
        return
    if not isinstance(frame, dict) or frame.get('type') != 'FEED_DATA':
        return
    data = frame.get('data')
    if not isinstance(data, list):
        raise ValueError(f'message {msg_no}: FEED_DATA data is not a list of event objects (FULL format)')
    for k, e in enumerate(data):
        if not isinstance(e, dict):
            raise ValueError(f'message {msg_no}: event {k} is not an object (compact format is not read)')
        place, kind = (msg_no, k), e.get('eventType')
        if kind == 'TimeAndSale':
            if e.get('type', 'NEW') != 'NEW' or e.get('validTick', True) is not True:
                raise ValueError(f'message {msg_no}: a TimeAndSale of type {e.get("type")!r} validTick '
                                 f'{e.get("validTick")!r}: not read, no rule for it (STOP)')
            yield PRINT(place, t_ns, int(e['time']) * MS_TO_NS, int(e['sequence']), num(e.get('price')),
                        num(e.get('size')), SIDES.get(e.get('aggressorSide')), num(e.get('bidPrice')),
                        num(e.get('askPrice')))
        elif kind == 'Quote':
            yield QUOTE(place, t_ns, num(e.get('bidPrice')), num(e.get('askPrice')), num(e.get('bidSize')),
                        num(e.get('askSize')))
        elif kind == 'Trade':
            yield DAYVOLUME(place, t_ns, num(e.get('dayVolume')))


def events_from_recording(path, cut: Optional[int] = None) -> Iterator:
    """Events in arrival order from a 7e recording; `cut` = only the first K received messages."""
    seen = 0
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if not line.strip():
                continue
            o = json.loads(line)
            if o.get('kind') != 'received':
                continue
            if cut is not None and seen >= cut:
                return
            seen += 1
            yield from events_from_frame(o['raw'], int(o['t_ns']), int(o['msg_no']))
