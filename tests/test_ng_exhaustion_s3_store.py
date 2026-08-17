import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research'))

import ng_exhaustion_s3_store as storemod

STAGE = Path(__import__('os').environ.get('NG_EXHAUSTION_STAGE_DIR', '/mnt/data/ng_exhaustion_s3_stage_final_local'))


class Body:
    def __init__(self, data): self._bio=io.BytesIO(data)
    def read(self, n=-1): return self._bio.read(n)


class FakeS3:
    def __init__(self, stage=STAGE):
        self.objects = {}
        self.downloads = 0
        for p in stage.rglob('*'):
            if p.is_file():
                rel = p.relative_to(stage).as_posix()
                self.objects[storemod.PREFIX + rel] = p.read_bytes()
    def get_object(self, Bucket, Key):
        if Bucket != storemod.BUCKET or Key not in self.objects: raise KeyError(Key)
        return {'Body': Body(self.objects[Key])}
    def download_file(self, Bucket, Key, Filename):
        self.downloads += 1
        Path(Filename).write_bytes(self.objects[Key])


@unittest.skipUnless(STAGE.exists(), 'exact staged S3 fixture not available')
class S3StoreTests(unittest.TestCase):
    def test_manifest_and_day_read(self):
        with tempfile.TemporaryDirectory() as td:
            s3=FakeS3(); st=storemod.NGExhaustionS3Store(s3=s3, cache_dir=td)
            m=st.load_manifest()
            self.assertEqual(m['frozen_invariants']['records'],1711)
            rows=st.day_records('20250717')
            self.assertEqual(len(rows),420)
            self.assertEqual(s3.downloads,1)
            self.assertEqual({r['day'] for r in rows},{'20250717'})
            self.assertFalse(any('future_price' in r for r in rows))

    def test_cache_hit_and_corruption_refetch(self):
        with tempfile.TemporaryDirectory() as td:
            s3=FakeS3(); st=storemod.NGExhaustionS3Store(s3=s3, cache_dir=td)
            p,hit=st.ensure_day_cached('20250923'); self.assertFalse(hit); self.assertEqual(s3.downloads,1)
            p2,hit=st.ensure_day_cached('20250923'); self.assertTrue(hit); self.assertEqual(p,p2); self.assertEqual(s3.downloads,1)
            p.write_bytes(b'bad')
            _,hit=st.ensure_day_cached('20250923'); self.assertFalse(hit); self.assertEqual(s3.downloads,2)

    def test_manifest_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            s3=FakeS3()
            key=storemod.PREFIX+'content_manifest.json'
            d=json.loads(s3.objects[key]); d['frozen_invariants']['records']=1710
            s3.objects[key]=(json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
            st=storemod.NGExhaustionS3Store(s3=s3, cache_dir=td)
            with self.assertRaises(storemod.S3StoreError): st.load_manifest()

if __name__=='__main__': unittest.main()
