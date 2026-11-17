"""Part 2, piece 1: the flow and the exhaustion peak. Real tape only. The full recount of every column is the check
run inside `root.run calc` on a whole trade day; here the calculation is read on a short real stretch."""
import datetime as dt
import itertools
import os
from pathlib import Path

from root import part2, tape
from root.calcs import flow_peak as F

TAPE = Path(os.environ.get('MARKETS_DATA', '../markets-data')) / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'
DAY = dt.date(2023, 10, 2)
STRETCH = 60000                  # the first ticks of trade day Oct 2 read here


def test_flow_is_the_trades_of_the_last_20_seconds_and_peaks_are_known_after_their_high():
    week = tape.read_week(TAPE, DAY)
    ticks = list(itertools.islice(part2.gated(week, DAY), STRETCH))
    out = list(F.calculate(iter(ticks)))
    I = {name: k for k, name in enumerate(F.NAMES)}
    trades = [(int(r['ts_recv']), bytes(r['side']), int(r['size'])) for _, r in ticks if bytes(r['action']) == F.TRADE]
    assert trades and len(out) == len(ticks)
    peaks = 0
    for (position, record), (out_position, v) in zip(ticks, out):
        assert position == out_position
        now = int(record['ts_recv'])
        inside = [(s, z) for at, s, z in trades if now - F.FLOW_SPAN_NS < at <= now]
        if position % 997 == 0 or v[I['peak_high_position']] is not None:      # a direct recount on some rows
            trade_now = sum(1 for at, _, _ in trades if at == now)
            if trade_now <= 1:       # with several trades in one nanosecond the later ones are not yet on this row
                assert v[I['flow_bought_20s']] == sum(z for s, z in inside if s == F.BUY)
                assert v[I['flow_sold_20s']] == sum(z for s, z in inside if s == F.SELL)
        b, s = v[I['flow_bought_20s']], v[I['flow_sold_20s']]
        assert (v[I['flow_20s']] is None) == (b + s == 0)
        if v[I['peak_high_position']] is not None:
            peaks += 1
            assert v[I['peak_high_position']] < position                       # known only after its high
            assert v[I['peak_high_received_time_ns']] <= now
            assert v[I['peak_side']] in (F.BUY_TEXT, F.SELL_TEXT) and 0 < v[I['peak_size']] <= 1
    assert peaks


def test_the_calculation_is_one_trade_day_through_the_gate():
    week = tape.read_week(TAPE, DAY)
    from root.calendar import label
    seen = {label(int(r['ts_event'])) for _, r in itertools.islice(part2.gated(week, DAY), STRETCH)}
    assert seen == {('trade day', DAY)}
