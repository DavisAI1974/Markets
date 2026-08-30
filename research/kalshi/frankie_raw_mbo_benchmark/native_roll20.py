"""Feed inventory section 8: recreate the legacy per-second `roll20` from the native stream.

Section 8 requires that "the same causal replay must recreate the exact lawful surface on
which the 54/55-week structures were learned", naming per-second `roll20` among them, and
that "every legacy field requires an explicit crosswalk to its V4-native source fields,
calculation, availability time, and state hash. The crosswalk must not contain October
target identities."

RECREATE is the operative word. The prior program's per-second output for these days exists
and is sealed as the target answer, so it is not an input here and this module deliberately
reads nothing from disk at all - its only input is the legacy control row the V4 adapter
PROJECTS from native MBO, which `native_replay_driver` already retains verbatim under D60.

THE RISK THIS MODULE CARRIES is not that it fails. It is that it emits a series that is
present, typed, in range, and not the quantity the frozen events were detected from. Two
defences: the arithmetic below mirrors the frozen `flow_series` statement for statement so
the floats agree bit for bit, and the classification is the frozen midpoint rule rather than
the tape's own `side` field, which the frozen program deliberately does not consult.

THE CLOCK IS NOT ASSUMED. The prior census binned on event time; this package's causal clock
is `ts_recv_ns`, and the calculation contract makes "the first lawful knowledge time for a
completed group" its F_LAST receive time. Those differ, so `SecondBinner` refuses to be
constructed without a named clock and the crosswalk hash changes with it - a different clock
is a different quantity, not a formatting choice.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

TRADE_ACTION = "T"
RECV_CLOCK = "ts_recv"
EVENT_CLOCK = "ts_event"
VALID_CLOCKS = (RECV_CLOCK, EVENT_CLOCK)

BID_TOUCH_FIELD = "bid_px_00"
ASK_TOUCH_FIELD = "ask_px_00"
DEFAULT_WINDOW = 20

MAX_DENSE_SPAN = 40 * 86400
"""Forty days, expressed in whole seconds. A wider dense series is a unit error.

Named to avoid a token the sealed-source guard in this module's tests forbids - that guard
rejects several literal strings that name sealed prior-program artifacts, and it fired on
the first draft of this constant. The guard is crude and it was right.
"""

NATIVE_SOURCE_FIELDS = ["action", "price", "size", BID_TOUCH_FIELD, ASK_TOUCH_FIELD, RECV_CLOCK]

CALCULATION = (
    "aggressor side is inferred from the trade price against the prevailing midpoint, never "
    "from the tape's own side field: mid = 0.5 * (bid_px_00 + ask_px_00), taken on rows with "
    "action == 'T' and price > 0 and size > 0 and bid_px_00 > 0 and ask_px_00 >= bid_px_00; "
    "price > mid adds size to buy volume, price < mid adds size to sell volume, and a trade "
    "priced exactly at the mid contributes to neither. Volumes are summed per whole second "
    "on the declared clock, then roll20 at second t is (b - s) / (b + s) over the trailing "
    "20 seconds inclusive of t, undefined where that window carries no volume."
)


class Roll20Error(ValueError):
    """A per-second flow series could not be built consistently."""


def _is_trade(row: Mapping[str, Any]) -> bool:
    return row.get("action") == TRADE_ACTION


def _finite(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return out if math.isfinite(out) else float("nan")


class SecondBinner:
    """Accumulates per-second aggressor buy and sell volume from legacy control rows.

    Counters are kept for every row it declines to classify, so a thin or malformed stretch
    is visible as a count rather than as a quiet zero (D60: retained and counted, never
    silently ignored).
    """

    def __init__(self, *, clock: str) -> None:
        if clock not in VALID_CLOCKS:
            raise Roll20Error(
                f"clock must be one of {list(VALID_CLOCKS)}; the frozen census binned on "
                f"{EVENT_CLOCK} and this package's causal clock is {RECV_CLOCK}, so the "
                "choice is a declaration and has no default"
            )
        self.clock = clock
        self.buy: dict[int, float] = {}
        self.sell: dict[int, float] = {}
        self.rows_seen = 0
        self.trades_seen = 0
        self.excluded_at_mid = 0
        self.excluded_no_quote = 0
        self.excluded_unusable_price_or_size = 0

    def observe(self, row: Mapping[str, Any]) -> None:
        """Bin one row at the second carried by the row's own declared clock."""
        self._bin(row, self._second(row) if _is_trade(row) else None)

    def observe_group(self, rows: Sequence[Mapping[str, Any]], *, second: int) -> None:
        """Bin a whole F_LAST group at ONE second, which is what the frozen census does.

        The census takes the second from the event group's frame and applies it to every
        legacy row the group emitted, so a group straddling a second boundary contributes
        entirely to the group's own second. Reproducing the frozen series requires the same
        assignment; per-row binning silently splits such a group and produces a different,
        plausible number. It is also what the contract implies, since a completed group's
        first lawful knowledge time is a property of the group and not of its rows.
        """
        for row in rows:
            self._bin(row, second)

    def _bin(self, row: Mapping[str, Any], second: int | None) -> None:
        self.rows_seen += 1
        if not _is_trade(row):
            return

        price = _finite(row.get("price"))
        size = _finite(row.get("size"))
        if not (price > 0) or not (size > 0):
            self.excluded_unusable_price_or_size += 1
            return
        self.trades_seen += 1

        bid = _finite(row.get(BID_TOUCH_FIELD))
        ask = _finite(row.get(ASK_TOUCH_FIELD))
        if not (bid > 0) or not (ask >= bid):
            self.excluded_no_quote += 1
            return

        if second is None:
            second = self._second(row)
        mid = 0.5 * (bid + ask)
        if price > mid:
            self.buy[second] = self.buy.get(second, 0.0) + size
        elif price < mid:
            self.sell[second] = self.sell.get(second, 0.0) + size
        else:
            self.excluded_at_mid += 1

    def _second(self, row: Mapping[str, Any]) -> int:
        stamp = _finite(row.get(self.clock))
        if math.isnan(stamp):
            raise Roll20Error(f"row carries no usable {self.clock}")
        return int(math.floor(stamp))

    def buy_volume_at(self, second: int) -> float:
        return self.buy.get(second, 0.0)

    def sell_volume_at(self, second: int) -> float:
        return self.sell.get(second, 0.0)

    def span(self) -> tuple[int, int] | None:
        """The inclusive second range that carries any classified volume."""
        seconds = set(self.buy) | set(self.sell)
        return (min(seconds), max(seconds)) if seconds else None

    def series(self) -> tuple[list[float], list[float], int]:
        """Dense buy and sell arrays over the observed span, plus the first second."""
        window = self.span()
        if window is None:
            return [], [], 0
        first, last = window
        n = last - first + 1
        if n > MAX_DENSE_SPAN:
            # REFUSE, never allocate. `observe(row)` keys a bin on floor(clock), so a caller
            # handing it nanoseconds gets bins numbered in the billions and this line would
            # try to build a dense array of them - which does not fail, it HANGS, and a hang
            # in a traversal reads as a slow run rather than as a defect. Found by feeding it
            # nanoseconds by mistake; the mistake is easy and the symptom is not diagnosable.
            raise Roll20Error(
                f"second span of {n} exceeds {MAX_DENSE_SPAN}; bins are keyed on "
                "floor(clock), so this is a caller passing a clock that is not in seconds"
            )
        buys = [self.buy.get(first + i, 0.0) for i in range(n)]
        sells = [self.sell.get(first + i, 0.0) for i in range(n)]
        return buys, sells, first

    def rolling_value(self, second: int, *, window: int = DEFAULT_WINDOW) -> float:
        """The trailing signed imbalance AT one second, without materialising the series.

        The same quantity `roll20()` puts at that index, computed from the bins this object
        already holds. It exists so a streaming traversal can hand a detector one second at a
        time instead of waiting for the whole day and then walking it - which would be a
        retrospective read of a causal quantity, the exact shape D66 rules out.

        A window carrying no volume yields NaN, never 0.0: a stretch with no trades is
        undefined, not balanced. A reconciliation test asserts this equals `roll20()` at every
        index, because two ways of computing one number that are never checked against each
        other are two numbers.
        """
        if window < 1:
            raise Roll20Error("window must be a positive number of seconds")
        buys = sum(self.buy.get(s, 0.0) for s in range(second - window + 1, second + 1))
        sells = sum(self.sell.get(s, 0.0) for s in range(second - window + 1, second + 1))
        total = buys + sells
        if total <= 0:
            return float("nan")
        return (buys - sells) / total

    def summary(self) -> dict[str, Any]:
        return {
            "clock": self.clock,
            "rows_seen": self.rows_seen,
            "trades_seen": self.trades_seen,
            "classified_buy_seconds": len(self.buy),
            "classified_sell_seconds": len(self.sell),
            "excluded_at_mid": self.excluded_at_mid,
            "excluded_no_quote": self.excluded_no_quote,
            "excluded_unusable_price_or_size": self.excluded_unusable_price_or_size,
            "midpoint_rule": "price vs mid; the tape side field is never consulted",
        }


def roll20(
    buy_volume: Sequence[float],
    sell_volume: Sequence[float],
    *,
    window: int = DEFAULT_WINDOW,
) -> list[float]:
    """Causal trailing signed aggressor-volume imbalance at one-second resolution.

    Deliberately written as the frozen `flow_series` is written - prefix sums, then one
    subtraction per second - rather than as an equivalent rolling update. An equivalent
    formulation would agree to within floating-point noise; this one agrees exactly, and
    exact is the only agreement that proves it is the same series.

    A window carrying no volume yields NaN, never 0.0: a second with no trades is
    undefined, not balanced, and collapsing the two would invent a reading.
    """
    n = len(buy_volume)
    if len(sell_volume) != n:
        raise Roll20Error("buy and sell volume arrays must be the same length")
    if window <= 0:
        raise Roll20Error("window must be positive")

    cb = [0.0] * (n + 1)
    cs = [0.0] * (n + 1)
    for i in range(n):
        cb[i + 1] = cb[i] + buy_volume[i]
        cs[i + 1] = cs[i] + sell_volume[i]

    out = [float("nan")] * n
    for t in range(n):
        lo = max(0, t - window + 1)
        b = cb[t + 1] - cb[lo]
        s = cs[t + 1] - cs[lo]
        z = b + s
        if z > 0:
            out[t] = (b - s) / z
    return out


def crosswalk(*, clock: str, window: int = DEFAULT_WINDOW) -> dict[str, Any]:
    """The section 8 crosswalk for the one legacy field this module recreates.

    Carries no day, roster or target identity by construction - it describes a definition,
    not a run, which is what keeps it lawful to hold before the answer wall opens.
    """
    if clock not in VALID_CLOCKS:
        raise Roll20Error(f"clock must be one of {list(VALID_CLOCKS)}")
    body = {
        "legacy_per_second_roll20": {
            "legacy_field": "roll20",
            "v4_native_source_fields": list(NATIVE_SOURCE_FIELDS),
            "calculation": CALCULATION,
            "availability_time": clock,
            "window_seconds": window,
            "undefined_when": "the trailing window carries no classified volume",
            "recreated_not_read": (
                "computed from the projected legacy control row on the native stream; the "
                "prior program's own per-second output for these days is the sealed target "
                "answer and is not an input"
            ),
        },
        "companion_fields": {
            "aggressor_buy_volume": "sum of size for trades priced above the midpoint",
            "aggressor_sell_volume": "sum of size for trades priced below the midpoint",
        },
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    body["state_hash"] = digest
    return body
