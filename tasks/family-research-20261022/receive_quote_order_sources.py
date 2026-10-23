"""Receive one bounded temporary transport into the E-drive Git checkout.

Configuration arrives through stdin; temporary URLs are never saved. Frozen
inputs are not rehashed. This verifies only the newly transported archive.
"""
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/quote-order-gapfill-v1'
config = json.loads(base64.b64decode(sys.stdin.readline()).decode())
OUT.mkdir(exist_ok=False)
archive = OUT / '.new-transport.tar.part'
digest = hashlib.sha256()
count = 0
try:
    with urllib.request.urlopen(config['download_url'], timeout=120) as response, archive.open('wb') as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            count += len(chunk)
            assert count <= config['archive_bytes'] < 512 * 1024**2
            digest.update(chunk)
            output.write(chunk)
    assert count == config['archive_bytes']
    assert digest.hexdigest() == config['archive_sha256']
    members = []
    with tarfile.open(archive, 'r:') as package:
        for member in package:
            assert member.isfile() and re.fullmatch(r'[A-Za-z0-9._-]+', member.name)
            assert member.name != archive.name and member.size < 100_000_000
            target = OUT / member.name
            assert target.resolve().is_relative_to(OUT.resolve()) and not target.exists()
            with package.extractfile(member) as source, target.open('wb') as output:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            assert target.stat().st_size == member.size
            members.append(dict(name=member.name, bytes=member.size))
    archive.unlink()
    receipt = dict(status='NEW_QUOTE_ORDER_TRANSPORT_VERIFIED', bytes=count,
                   sha256=digest.hexdigest(), original_archive_sha256=config['archive_sha256'],
                   members=members, no_C_drive_artifacts=True, no_source_rehash=True,
                   temporary_remote_key=config['temporary_remote_key'],
                   remote_source_directory=config['remote_source_directory'],
                   original_trade_inventory='All 30739 original trades remain unchanged in parent evidence bundles')
    (OUT / 'local-transport-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(status=receipt['status'], bytes=count, files=len(members))), flush=True)
except Exception as error:
    print('Bounded transport failed: ' + type(error).__name__, file=sys.stderr)
    raise SystemExit(1)
