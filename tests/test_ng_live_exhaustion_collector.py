from pathlib import Path
import tempfile
import types
import unittest
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'research'))
sys.path.insert(0,str(ROOT/'research'/'kalshi'))
from ng_live_exhaustion_collector import ExhaustionState, MBP10_RTYPE

SCALE=1_000_000_000

def rec(*,rtype,second,price,bid,ask,size=1,action='T'):
    level=types.SimpleNamespace(bid_px=int(round(bid*SCALE)),ask_px=int(round(ask*SCALE)),bid_sz=10,ask_sz=10)
    return types.SimpleNamespace(rtype=rtype,ts_event=int(second*1_000_000_000),price=int(round(price*SCALE)),size=size,action=action,levels=[level])

class LiveCollectorTapTests(unittest.TestCase):
    def test_mbp10_trade_is_consumed(self):
        with tempfile.TemporaryDirectory() as td:
            s=ExhaustionState('NG.v.0',Path(td)/'x.dbn')
            s._observe_exhaustion_input(rec(rtype=MBP10_RTYPE,second=100,price=3.002,bid=3.000,ask=3.002,size=5))
            self.assertEqual(s.exhaustion_mbp10_trade_records,1)
            self.assertEqual(s.exhaustion_flow.classified_trades,1)
            self.assertEqual(s.exhaustion_flow.raw_value_at(100),1.0)
    def test_tbbo_trade_is_not_double_counted(self):
        with tempfile.TemporaryDirectory() as td:
            s=ExhaustionState('NG.v.0',Path(td)/'x.dbn')
            s._observe_exhaustion_input(rec(rtype=1,second=100,price=3.002,bid=3.000,ask=3.002,size=99))
            self.assertEqual(s.exhaustion_mbp10_trade_records,0)
            self.assertEqual(s.exhaustion_flow.classified_trades,0)
            self.assertIsNone(s.exhaustion_flow.raw_value_at(100))
    def test_nontrade_mbp10_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            s=ExhaustionState('NG.v.0',Path(td)/'x.dbn')
            s._observe_exhaustion_input(rec(rtype=MBP10_RTYPE,second=100,price=3.001,bid=3.000,ask=3.002,size=10,action='A'))
            self.assertEqual(s.exhaustion_mbp10_trade_records,0)
if __name__=='__main__': unittest.main()
