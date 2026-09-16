"""Upload the complete Sunday restoration set to S3 with a sha256 manifest, from the source workstation.

What goes up, all read-only from the source:
- the 27 bulk files the restoration manifest lists as not-in-git, each keyed by its mirror path;
- the byte-exact working-tree restore output (the module's verified copy), as one tar;
- the host virtual environment (actual-host-python), the receiver checkout, the verified tokenizer,
  the retained-recovery witness directory and the retained readiness directory, each as one tar.

Tars are written uncompressed with no path normalisation so bytes survive exactly; every archive
member and every bulk file is sha256-hashed and the manifest is uploaded last. Nothing is deleted.

    python upload_sunday_restore_set.py --bucket <bucket> --prefix frankie/sunday_20260915_restore --log <log.jsonl>
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import time
from pathlib import Path

RUNTIME = Path('E:/Codex/Frankie-BOSS-20260915')
PACKAGE = Path(__file__).resolve().parents[1] / 'sunday_20260915_package'
MIRROR = {'E:/Codex/Frankie-BOSS-20260915': 'FB', 'C:/Users/A/Documents/Codex': 'C_Codex'}
ARCHIVES = {
    'working-tree-byte-exact.tar': ('C:/Users/A/AppData/Local/Temp/r2/Markets', 'FB/sunday-launch-20260915/Markets'),
    'actual-host-python.tar': ('E:/Codex/Frankie-BOSS-20260915/actual-host-python', 'FB/actual-host-python'),
    'receiver-Markets-source.tar': ('C:/Users/A/Documents/Codex/2026-09-14/continue-the-frankie-build-in-parallel/work/Markets-source',
                                    'C_Codex/2026-09-14/continue-the-frankie-build-in-parallel/work/Markets-source'),
    'verified-tokenizer.tar': ('C:/Users/A/Documents/Codex/2026-09-14/if-you-mean-claude-code-a/work/verified-tokenizer',
                               'C_Codex/2026-09-14/if-you-mean-claude-code-a/work/verified-tokenizer'),
    'retained-recovery.tar': ('C:/Users/A/Documents/Codex/2026-09-15/first-run-using-agent-skills-continue/work/retained-recovery',
                              'C_Codex/2026-09-15/first-run-using-agent-skills-continue/work/retained-recovery'),
    'retained-ready-runtime-aligned.tar': ('E:/Codex/Frankie-BOSS-20260915/retained-ready-34987737686-runtime-aligned',
                                           'FB/retained-ready-34987737686-runtime-aligned'),
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 22), b''):
            digest.update(chunk)
    return digest.hexdigest()


def mirror_key(original):
    posix = Path(original).as_posix()
    for prefix, short in MIRROR.items():
        if posix.startswith(prefix + '/'):
            return short + '/' + posix[len(prefix) + 1:]
    raise ValueError('path outside the mirror roots: ' + posix)


def load_credentials():
    env = {}
    for line in open('scratchpad/aws.env', encoding='utf-8', errors='replace'):
        m = re.match(r'\s*(?:export\s+)?([A-Z_]+)\s*=\s*"?([^"\n]+)"?', line)
        if m:
            env[m.group(1)] = m.group(2).strip()
    for k in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'):
        os.environ[k] = env[k]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--log', required=True)
    args = parser.parse_args()
    load_credentials()
    import boto3
    from boto3.s3.transfer import TransferConfig
    s3 = boto3.client('s3', region_name='us-east-2')
    config = TransferConfig(multipart_chunksize=64 * 1024 * 1024, max_concurrency=4)
    log = open(args.log, 'a', encoding='utf-8')

    def note(**values):
        record = dict(unix=time.time(), **values)
        log.write(json.dumps(record, default=str) + '\n'); log.flush()
        print(json.dumps(record, default=str), flush=True)

    def upload(path, key, expected_sha256=None):
        size = os.path.getsize(path); started = time.perf_counter()
        digest = sha256_file(path)
        if expected_sha256 and digest != expected_sha256:
            raise ValueError(f'bulk file differs from manifest pin: {path}')
        s3.upload_file(str(path), args.bucket, key, Config=config, ExtraArgs={'Metadata': {'sha256': digest}})
        head = s3.head_object(Bucket=args.bucket, Key=key)
        if head['ContentLength'] != size:
            raise ValueError('uploaded size differs: ' + key)
        note(uploaded=key, bytes=size, sha256=digest, seconds=round(time.perf_counter() - started, 1))
        return dict(key=key, bytes=size, sha256=digest)

    manifest = json.loads((PACKAGE / 'RESTORATION_MANIFEST.json').read_bytes())
    entries = []
    bulk = [row for row in manifest['files'] if not row['in_git']]
    note(stage='bulk_start', files=len(bulk), bytes=sum(r['bytes'] for r in bulk))
    for row in sorted(bulk, key=lambda r: r['bytes']):
        entries.append(dict(kind='bulk', original_path=row['original_path'],
                            **upload(row['original_path'], f"{args.prefix}/{mirror_key(row['original_path'])}", row.get('sha256'))))
    for name, (source, mirror) in ARCHIVES.items():
        source_path = Path(source)
        if not source_path.is_dir():
            raise FileNotFoundError(source)
        members = []
        with tempfile.NamedTemporaryFile(prefix='sunday-', suffix='.tar', delete=False) as tmp:
            tar_path = tmp.name
        started = time.perf_counter()
        with tarfile.open(tar_path, 'w', format=tarfile.PAX_FORMAT) as tar:
            for f in sorted(source_path.rglob('*')):
                if f.is_file() and not f.is_symlink():
                    rel = f.relative_to(source_path).as_posix()
                    tar.add(f, arcname=rel, recursive=False)
                    members.append(dict(path=rel, bytes=f.stat().st_size, sha256=sha256_file(f)))
        note(stage='archived', archive=name, members=len(members), seconds=round(time.perf_counter() - started, 1))
        record = upload(tar_path, f"{args.prefix}/archives/{name}")
        os.unlink(tar_path)
        entries.append(dict(kind='archive', archive=name, source=source, restore_to_mirror=mirror, members=members, **record))
    body = dict(schema='FRANKIE_SUNDAY_RESTORE_SET_UPLOAD_V1', bucket=args.bucket, prefix=args.prefix,
                restoration_manifest_sha256=sha256_file(PACKAGE / 'RESTORATION_MANIFEST.json'),
                mirror_roots=MIRROR, entries=entries, completed_unix=time.time())
    raw = json.dumps(body, indent=1, sort_keys=True, default=str).encode()
    s3.put_object(Bucket=args.bucket, Key=f'{args.prefix}/UPLOAD_MANIFEST.json', Body=raw)
    Path(args.log).with_suffix('.manifest.json').write_bytes(raw)
    note(stage='complete', entries=len(entries), manifest_sha256=hashlib.sha256(raw).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
