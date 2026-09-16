"""Every in-git Sunday package file's committed BLOB hashes to RESTORATION_MANIFEST.json.

The on-host restore copies these 170 files from the git object store (git show HEAD:path), so the
guarantee that matters is blob-exactness, independent of any checkout's line-ending mode. On
2026-09-16 an autocrlf checkout had rewritten 17 of them to CRLF and four others had been committed
LF while the manifest pinned CRLF bytes; both are now pinned by `-text` in .gitattributes.
"""
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MANIFEST = ROOT / 'research/kalshi/frankie_boss/sunday_20260915_package/RESTORATION_MANIFEST.json'


class PackageBlobTests(unittest.TestCase):
    def test_every_in_git_blob_matches_manifest(self):
        rows = [r for r in json.loads(MANIFEST.read_bytes())['files'] if r['in_git']]
        for addendum in sorted(MANIFEST.parent.glob('RESTORATION_MANIFEST_ADDENDUM_*.json')):
            rows += [r for r in json.loads(addendum.read_bytes())['files'] if r['in_git']]
        self.assertGreaterEqual(len(rows), 171)
        bad = []
        for row in rows:
            shown = subprocess.run(['git', '-C', str(ROOT), 'show', 'HEAD:' + row['git_path']], capture_output=True)
            if shown.returncode != 0 or hashlib.sha256(shown.stdout).hexdigest() != row['sha256']:
                bad.append(row['git_path'])
        self.assertEqual(bad, [], f'{len(bad)} package blobs differ from the restoration manifest')

    def test_package_is_pinned_text_free(self):
        attrs = subprocess.run(['git', '-C', str(ROOT), 'check-attr', 'text', '--',
                                'research/kalshi/frankie_boss/sunday_20260915_package/RESTORATION_MANIFEST.json'],
                               capture_output=True, text=True).stdout
        self.assertIn('text: unset', attrs)


if __name__ == '__main__':
    unittest.main()
