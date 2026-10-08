"""Session 8 (2026-10-08): file claims survive a reboot. The seven toys that proved the fix, as unittest cases on the
real functions: a FRANKIE_FILE_CLAIM_V1 row stores stat as [st_dev, ino, size, mtime_ns]; after a2's reboot the two NVMe
volumes enumerated in the other order, every row failed on st_dev alone and ~1.2 TB fell to "read whole". V2 drops st_dev
from the identity and adds the filesystem identity; V1 is read, taken on ino/size/mtime_ns + the 64 KiB tail, and
rewritten in place as V2. Run from the repo root: python -m unittest tests.test_file_claims_v2 (no network, no box)."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
BOX = REPO / 'deploy' / 'aws' / 'box'
for entry in (str(REPO), str(BOX)):
    if entry not in sys.path:
        sys.path.insert(0, entry)
try:
    import research.kalshi.frankie_boss  # noqa: F401  (its __init__ imports trunk -> torch; present on the box)
except ImportError:
    import research  # noqa: F401
    import research.kalshi  # noqa: F401
    _pkg = types.ModuleType('research.kalshi.frankie_boss')
    _pkg.__path__ = [str(REPO / 'research' / 'kalshi' / 'frankie_boss')]
    sys.modules['research.kalshi.frankie_boss'] = _pkg
from research.kalshi.frankie_boss.operations import ingest_block_sources as I  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, BOX / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S = _load('frankie_box_boss_session')
BR = _load('frankie_box_brain')
D = _load('frankie_box_experiment_data')
CLAIMS = 'file-claims.jsonl'


class FileClaimsV2(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='claims-toy-'))
        self.f = self.work / 'spool.jsonl'
        self.f.write_bytes(b'{"a":1}\n' * 20000)          # 160 KB > the 64 KiB tail
        self.info = self.f.stat()
        self.sha = hashlib.sha256(self.f.read_bytes()).hexdigest()
        tail = self.f.read_bytes()[-I.CLAIM_TAIL_BYTES:]
        info = self.info
        self.v1 = dict(schema='FRANKIE_FILE_CLAIM_V1', path=str(self.f.resolve()), bytes=info.st_size, sha256=self.sha,
                       stat=[info.st_dev + 1, info.st_ino, info.st_size, info.st_mtime_ns],   # the reboot: st_dev renumbered
                       tail_bytes=len(tail), tail_sha256=hashlib.sha256(tail).hexdigest(), claimed_by='old writer', at=1.0,
                       count=20000, count_basis='toy')
        self.v1_bad_tail = dict(self.v1, tail_sha256='0' * 64)
        self.item = dict(path=str(self.f), bytes=info.st_size, sha256=self.sha)
        self.assertEqual(I.FILE_CLAIM_SCHEMA, 'FRANKIE_FILE_CLAIM_V2')

    def rows(self):
        return [json.loads(line) for line in (self.work / CLAIMS).read_text().splitlines()]

    def check(self):
        claims = S._load_file_claims(self.work)
        seen, basis = S._artifact_check(self.item, claims, 'claim', claims_dir=self.work)
        return claims, seen, basis

    def test_1_v1_row_with_renumbered_st_dev_is_accepted_and_rewritten_as_v2(self):
        I.write_file_claims(self.work, [self.v1])
        claims, seen, basis = self.check()
        self.assertEqual(seen, dict(bytes=self.info.st_size, sha256=self.sha))
        self.assertIn('v1-compat', basis)
        self.assertIn('not read whole', basis)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['schema'], 'FRANKIE_FILE_CLAIM_V2')
        self.assertIn('fs_uuid', row)
        self.assertTrue(row['fs_basis'])
        self.assertEqual(row['stat'], [self.info.st_ino, self.info.st_size, self.info.st_mtime_ns])
        self.assertEqual((row['count'], row['count_basis'], row['upgraded_from']), (20000, 'toy', 'FRANKIE_FILE_CLAIM_V1'))
        self.assertEqual(list(self.work.glob(CLAIMS + '.*')), [], 'partial file left behind')
        self.assertEqual(claims[str(self.f.resolve())]['schema'], 'FRANKIE_FILE_CLAIM_V2')   # the in-memory map too

    def test_2_v2_row_on_the_same_filesystem_is_accepted_and_the_file_untouched(self):
        I.write_file_claims(self.work, [I.file_claim(self.f, self.info.st_size, self.sha, 'toy v2')])
        before = (self.work / CLAIMS).stat().st_mtime_ns
        _, _, basis = self.check()
        self.assertTrue(basis.startswith('the saved claim (v2)'), basis)
        self.assertEqual((self.work / CLAIMS).stat().st_mtime_ns, before, 'a V2 match must not rewrite')

    def test_3_v1_row_with_a_different_tail_is_read_whole_and_not_rewritten(self):
        I.write_file_claims(self.work, [self.v1_bad_tail])
        _, _, basis = self.check()
        self.assertTrue(basis.startswith('read whole'), basis)
        row = self.rows()[0]
        self.assertEqual((row['schema'], row['tail_sha256']), ('FRANKIE_FILE_CLAIM_V1', '0' * 64))

    def test_4_v2_row_on_another_filesystem_is_read_whole(self):
        other_fs = dict(I.file_claim(self.f, self.info.st_size, self.sha, 'toy v2'),
                        fs_uuid='00000000-dead-beef-0000-000000000000')
        I.write_file_claims(self.work, [other_fs])
        _, _, basis = self.check()
        self.assertTrue(basis.startswith('read whole'), basis)
        self.assertIsNone(S._claim_still_holds(other_fs))

    def test_5_legacy_spool_takes_a_v1_compat_claim_with_its_count_and_refreshes(self):
        I.write_file_claims(self.work, [self.v1])
        claims = S._load_file_claims(self.work)
        seen, count, how = S._legacy_spool_artifact(dict(self.item), claims, 'claim', {}, claims_dir=self.work)
        self.assertEqual(count, 20000)
        self.assertIn('v1-compat', how)
        row = self.rows()[0]
        self.assertEqual((row['schema'], row['count']), ('FRANKIE_FILE_CLAIM_V2', 20000))

    def test_6_brain_and_export_readers_take_v1_renumbered_and_v2_and_hash_another_filesystem(self):
        f, sha = str(self.f), self.sha
        I.write_file_claims(self.work, [self.v1])
        witness = BR.file_witnesses([f], BR.file_claims(self.work))
        self.assertEqual((witness[0][0], witness[0][1]['basis']), (sha, 'claim'))
        claims, _, _ = D._stage_claims(dict(root=str(self.work)))
        _, reused, _, _ = D._pins_progress(None, [f], True, claims=claims)
        self.assertEqual(reused[f][1], sha)
        good_v2 = I.file_claim(self.f, self.info.st_size, sha, 'toy v2')
        I.write_file_claims(self.work, [good_v2])
        witness = BR.file_witnesses([f], BR.file_claims(self.work))
        self.assertEqual(witness[0][1]['basis'], 'claim')
        claims, _, _ = D._stage_claims(dict(root=str(self.work)))
        _, reused, _, _ = D._pins_progress(None, [f], True, claims=claims)
        self.assertIn(f, reused)
        I.write_file_claims(self.work, [dict(good_v2, fs_uuid='00000000-dead-beef-0000-000000000000')])
        witness = BR.file_witnesses([f], BR.file_claims(self.work))
        self.assertEqual((witness[0][0], witness[0][1]['basis']), (sha, 'hashed'))
        claims, _, _ = D._stage_claims(dict(root=str(self.work)))
        _, reused, _, _ = D._pins_progress(None, [f], True, claims=claims)
        self.assertNotIn(f, reused)

    def test_7_refresh_is_atomic_and_keeps_order_and_the_other_row_byte_identical(self):
        g = self.work / 'other.bin'
        g.write_bytes(b'x' * 1000)
        g_row = I.file_claim(g, 1000, hashlib.sha256(b'x' * 1000).hexdigest(), 'toy')
        I.write_file_claims(self.work, [g_row, self.v1])
        self.check()
        rows = self.rows()
        self.assertEqual([r['path'] for r in rows], [str(g.resolve()), str(self.f.resolve())])
        self.assertEqual(rows[0], g_row)
        self.assertEqual(rows[1]['schema'], 'FRANKIE_FILE_CLAIM_V2')
        self.assertEqual(sorted(p.name for p in self.work.iterdir()), [CLAIMS, 'other.bin', 'spool.jsonl'])


if __name__ == '__main__':
    unittest.main()
