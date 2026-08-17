import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'research'))
from ng_exhaustion_live_clock import AggressorRoll20Feed, FamilyClassifierIntegrityError, FrozenPreFamilyClassifier, LiveClockInputError, _fill_curve

FAMILY=ROOT/'research'/'FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json'
BLIND=Path('/mnt/data/ng_batch_input/ng_frankie_blind_records.json')

class LiveClockInputTests(unittest.TestCase):
    def test_trade_side_matches_price_vs_mid(self):
        f=AggressorRoll20Feed(); self.assertEqual(f.ingest_trade(100,price=3.002,size=5,bid_px=3.000,ask_px=3.002),'buy'); self.assertEqual(f.ingest_trade(100,price=3.000,size=2,bid_px=3.000,ask_px=3.002),'sell'); self.assertEqual(f.ingest_trade(100,price=3.001,size=9,bid_px=3.000,ask_px=3.002),'midpoint'); self.assertAlmostEqual(f.raw_value_at(100),(5-2)/(5+2))
    def test_roll20_is_trailing_inclusive(self):
        f=AggressorRoll20Feed()
        for s in range(30): f.ingest_volume(s,buy_volume=1 if s<20 else 0,sell_volume=0 if s<20 else 1)
        self.assertAlmostEqual(f.raw_value_at(19),1.0); self.assertAlmostEqual(f.raw_value_at(29),0.0)
    def test_fill_curve_forward_then_backward(self):
        self.assertEqual(_fill_curve([None,None,0.5,None,0.25]),(0.5,0.5,0.5,0.5,0.25))
        with self.assertRaises(LiveClockInputError): _fill_curve([None,None])
    def test_out_of_order_seconds_fail_closed(self):
        f=AggressorRoll20Feed(); f.ingest_volume(10,buy_volume=1)
        with self.assertRaises(LiveClockInputError): f.ingest_volume(9,buy_volume=1)
    def test_family_artifact_sha_drift_fails_closed(self):
        FrozenPreFamilyClassifier.load(FAMILY)
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/'bad.json'; data=bytearray(FAMILY.read_bytes()); data[-2]^=1; bad.write_bytes(data)
            with self.assertRaises(FamilyClassifierIntegrityError): FrozenPreFamilyClassifier.load(bad)
    @unittest.skipUnless(BLIND.exists(),'frozen blind records not materialized')
    def test_family_assignments_match_full_blind_batch(self):
        c=FrozenPreFamilyClassifier.load(FAMILY); rows=json.loads(BLIND.read_text()); self.assertEqual(len(rows),1711); bad=0
        for r in rows: bad += c.classify(r['dipole_roll20_oriented_t_minus60_to_plus60'][:61]).family != r['family']
        self.assertEqual(bad,0)
    @unittest.skipUnless(BLIND.exists(),'frozen blind records not materialized')
    def test_live_roll20_post_window_matches_full_blind_batch_exactly(self):
        rows=json.loads(BLIND.read_text()); checked=0
        for r in rows:
            f=AggressorRoll20Feed()
            for i,(b,s) in enumerate(zip(r['aggressor_buy_volume_t_minus60_to_plus60'],r['aggressor_sell_volume_t_minus60_to_plus60'])): f.ingest_volume(i-60,buy_volume=0.0 if b is None else float(b),sell_volume=0.0 if s is None else float(s))
            raw=_fill_curve(f.raw_series(0,60)); pol=int(r['dipole_polarity']); got=[pol*x for x in raw]; expected=[float(x) for x in r['dipole_roll20_oriented_t_minus60_to_plus60'][60:]]; self.assertEqual(got,expected); checked += len(got)
        self.assertEqual(checked,1711*61)
if __name__=='__main__': unittest.main()
