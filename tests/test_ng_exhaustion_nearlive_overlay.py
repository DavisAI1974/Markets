import io
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'research'))
import ng_exhaustion_s3_store as sm
from ng_exhaustion_runway_clock import ExhaustionRunwayClock
from ng_exhaustion_nearlive_overlay import replay_day, record_to_update, IsolatedRunwayOverlay
from nova_ng_exhaustion_packet import FrankieRunwayPacket

STAGE=Path(__import__('os').environ.get('NG_EXHAUSTION_STAGE_DIR', '/mnt/data/ng_exhaustion_s3_stage_final_local'))
CLASSIFIER=ROOT/'research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json'
class Body:
    def __init__(self,d): self.b=io.BytesIO(d)
    def read(self,n=-1): return self.b.read(n)
class FakeS3:
    def __init__(self):
        self.o={sm.PREFIX+p.relative_to(STAGE).as_posix():p.read_bytes() for p in STAGE.rglob('*') if p.is_file()}
    def get_object(self,Bucket,Key): return {'Body':Body(self.o[Key])}
    def download_file(self,Bucket,Key,Filename): Path(Filename).write_bytes(self.o[Key])

@unittest.skipUnless(STAGE.exists(), 'exact staged S3 fixture not available')
class OverlayTests(unittest.TestCase):
    def test_full_day_s3_to_clock_to_nova(self):
        with tempfile.TemporaryDirectory() as td:
            store=sm.NGExhaustionS3Store(s3=FakeS3(),cache_dir=td)
            clock=ExhaustionRunwayClock.from_classifier_path(CLASSIFIER)
            packet,summary=replay_day(store=store,clock=clock,day='20250717',checkpoints=(0,30,60,300))
            self.assertEqual(summary['status'],'PASS')
            self.assertEqual(summary['records'],420)
            self.assertEqual(summary['clock_updates'],1680)
            self.assertEqual(summary['a_assignment_mismatches'],0)
            self.assertGreater(summary['nova_reduction_pct'],90.0)
            self.assertFalse(summary['future_price_accessed'])
            self.assertFalse(summary['source']['cache_hit_initial'])
            restored=FrankieRunwayPacket.unpack_batch(packet)
            self.assertEqual(len(restored['rows']),1680)
            self.assertTrue(restored['header']['s3'].endswith('day=20250717/records.jsonl.gz'))
            _, warm = replay_day(store=store, clock=clock, day='20250717', checkpoints=(0,30,60,300))
            self.assertTrue(warm['source']['cache_hit_initial'])

    def test_live_contract_legal_gate(self):
        with tempfile.TemporaryDirectory() as td:
            store=sm.NGExhaustionS3Store(s3=FakeS3(),cache_dir=td)
            row=store.day_records('20250717')[0]
            clock=ExhaustionRunwayClock.from_classifier_path(CLASSIFIER)
            overlay=IsolatedRunwayOverlay(clock)
            pre=overlay.update(record_to_update(row,30))
            at=overlay.update(record_to_update(row,60))
            if row['family']=='A':
                self.assertEqual(pre['post_state'],'A_STATE_PENDING')
                self.assertEqual(at['post_state'],row['frozen_post_state_assignment']['label'])
            self.assertFalse(at['future_price_accessed'])

if __name__=='__main__': unittest.main()
