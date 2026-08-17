#!/usr/bin/env python3
"""Drop-in NG live collector entrypoint with the exact exhaustion roll-20 tap.

It reuses research/kalshi/ng_live_collector.py's ONE Databento session and archive
path. No second market-data connection is created. The only change is a State
subclass that derives the exact historical 20-second aggressor-volume imbalance
from MBP-10 trade records and exposes a 180-second raw roll20 history in health.json.

This remains an isolated runway-clock input overlay; it does not mutate Frankie or
make trade decisions.
"""
from __future__ import annotations
import threading
from pathlib import Path
import sys
from typing import Any

HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parent
if str(RESEARCH) not in sys.path: sys.path.insert(0,str(RESEARCH))
import ng_live_collector as base
from ng_exhaustion_live_clock import AggressorRoll20Feed, LiveClockInputError

class ExhaustionState(base.State):
    def __init__(self, symbol: str, archive: Path) -> None:
        super().__init__(symbol, archive)
        self.exhaustion_flow=AggressorRoll20Feed(retain_seconds=600)
        self.exhaustion_lock=threading.Lock()
        self.exhaustion_error: str | None=None
        self.exhaustion_mbp10_trade_records=0

    def _observe_exhaustion_input(self, record: Any) -> None:
        if self.exhaustion_error is not None: return
        levels=getattr(record,'levels',None); action=base.enum_text(getattr(record,'action',None))
        if levels is None or str(action or '').upper() not in {'T','TRADE'}: return
        try:
            level0=levels[0]; ts_ns=int(record.ts_event); price=base.decimal_price(record.price); bid=base.decimal_price(level0.bid_px); ask=base.decimal_price(level0.ask_px); size=int(record.size)
            if price is None or bid is None or ask is None: return
            sec=ts_ns//1_000_000_000
            with self.exhaustion_lock:
                self.exhaustion_flow.ingest_trade(sec,price=price,size=size,bid_px=bid,ask_px=ask)
                self.exhaustion_mbp10_trade_records += 1
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError, LiveClockInputError) as exc:
            with self.exhaustion_lock: self.exhaustion_error=repr(exc)

    def on_record(self, record: Any) -> None:
        self._observe_exhaustion_input(record)
        super().on_record(record)

    def snapshot(self) -> dict[str, Any]:
        payload=super().snapshot()
        with self.exhaustion_lock:
            tap=self.exhaustion_flow.snapshot(seconds=180); err=self.exhaustion_error; mbp10_trades=self.exhaustion_mbp10_trade_records
        payload['exhaustion_input']={
            'schema':'markets.ng_exhaustion.live_roll20_input.v1','status':'PASS' if err is None else 'FAIL_CLOSED','roll_seconds':20,'history_seconds':180,
            'trade_side_rule':'MBP10 trade price > concurrent mid => buy; price < mid => sell; midpoint skipped',
            'formula':'(buy_volume-sell_volume)/(buy_volume+sell_volume) over trailing 20 seconds inclusive',
            'mbp10_trade_records_seen':mbp10_trades,'derived_error':err,**tap,'future_price_accessed':False,'permanent_frankie_mutated':False,
        }
        return payload

def main()->int:
    base.State=ExhaustionState
    return base.main()

if __name__=='__main__': raise SystemExit(main())
