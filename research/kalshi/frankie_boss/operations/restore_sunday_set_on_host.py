"""Restore the Sunday set on the native host from S3, verifying every byte against the upload manifest.

Runs on the Windows host with the stock C:/Python313 interpreter and the AWS CLI (instance role).
Nothing here imports Frankie, opens a journal, or touches C:/Python313 site-packages.

Steps: read UPLOAD_MANIFEST.json; download each bulk object to its mirror path and check sha256;
download each archive, check sha256, extract byte-exact (PAX tar, no mode or newline changes) to
its mirror directory and check every member's sha256; copy the small in-git package files from the
tools checkout to their mirror paths; then audit the restored working tree with the reviewed
byte-exact restore module and write a receipt. Idempotent: files already present with the right
hash are not downloaded again.

    C:/Python313/python.exe restore_sunday_set_on_host.py --bucket <b> --prefix frankie/sunday_20260915_restore
        --tools C:/tools/Markets --receipt E:/Codex/RESTORE_RECEIPT.json
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

MIRROR_ROOTS = {'FB': 'E:/Codex/Frankie-BOSS-20260915', 'C_Codex': 'C:/Users/A/Documents/Codex'}
AWS = r'C:\Program Files\Amazon\AWSCLIV2\aws.exe'
GIT = r'C:\Program Files\Git\cmd\git.exe'


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 22), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_module_by_path(name, path):
    """Import a stdlib-only module from its file, bypassing the torch-importing package __init__."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mirror_target(mirror_path):
    short, rest = mirror_path.split('/', 1)
    return Path(MIRROR_ROOTS[short]) / rest


PRESIGNED = {}  # key -> presigned GET url, when the host has no S3 role rights (2026-09-16: the Ssm role has none)


def s3_get(bucket, key, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = PRESIGNED.get(key)
    if url:
        import urllib.request
        with urllib.request.urlopen(url, timeout=600) as response, open(destination, 'wb') as out:
            for chunk in iter(lambda: response.read(1 << 22), b''):
                out.write(chunk)
        return
    subprocess.run([AWS, 's3', 'cp', f's3://{bucket}/{key}', str(destination), '--region', 'us-east-2'], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--prefix', required=True)
    parser.add_argument('--tools', required=True, help='checkout of the review branch holding sunday_20260915_package')
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--stage', default='C:/restore-stage')
    parser.add_argument('--presigned', help='JSON {key: presigned GET url} for hosts whose role cannot read the bucket')
    args = parser.parse_args()
    if args.presigned:
        PRESIGNED.update(json.loads(Path(args.presigned).read_bytes())['urls'])
    stage = Path(args.stage); stage.mkdir(parents=True, exist_ok=True)
    started = time.time(); log = []

    def note(**values):
        values['t'] = round(time.time() - started, 1); log.append(values); print(json.dumps(values, default=str), flush=True)

    manifest_path = stage / 'UPLOAD_MANIFEST.json'
    s3_get(args.bucket, f'{args.prefix}/UPLOAD_MANIFEST.json', manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get('schema') != 'FRANKIE_SUNDAY_RESTORE_SET_UPLOAD_V1':
        raise SystemExit('unexpected upload manifest schema')
    tools = Path(args.tools)
    package = tools / 'research' / 'kalshi' / 'frankie_boss' / 'sunday_20260915_package'
    restoration = json.loads((package / 'RESTORATION_MANIFEST.json').read_bytes())
    if sha256_file(package / 'RESTORATION_MANIFEST.json') != manifest['restoration_manifest_sha256']:
        raise SystemExit('tools checkout carries a different restoration manifest than the upload was made from')

    # 1. bulk objects to their mirror paths
    for entry in [e for e in manifest['entries'] if e['kind'] == 'bulk']:
        key = entry['key']; target = mirror_target(key[len(args.prefix) + 1:])
        if target.is_file() and target.stat().st_size == entry['bytes'] and sha256_file(target) == entry['sha256']:
            note(bulk=target.name, status='already present'); continue
        s3_get(args.bucket, key, target)
        if sha256_file(target) != entry['sha256']:
            raise SystemExit('bulk object hash differs after download: ' + key)
        note(bulk=target.name, bytes=entry['bytes'], status='restored')

    # 2. archives, extracted byte-exact to their mirror directories
    for entry in [e for e in manifest['entries'] if e['kind'] == 'archive']:
        tar_path = stage / entry['archive']; target_dir = mirror_target(entry['restore_to_mirror'])
        if not (tar_path.is_file() and sha256_file(tar_path) == entry['sha256']):
            s3_get(args.bucket, entry['key'], tar_path)
            if sha256_file(tar_path) != entry['sha256']:
                raise SystemExit('archive hash differs after download: ' + entry['archive'])
        target_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar_path, 'r', format=tarfile.PAX_FORMAT) as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                out = target_dir / member.name
                if out.is_file() and out.stat().st_size == member.size:
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, open(out, 'wb') as dst:
                    for chunk in iter(lambda: src.read(1 << 22), b''):
                        dst.write(chunk)
        bad = [m['path'] for m in entry['members'] if sha256_file(target_dir / m['path']) != m['sha256']]
        if bad:
            raise SystemExit(f'{len(bad)} members differ after extraction in {entry["archive"]}: {bad[:3]}')
        note(archive=entry['archive'], members=len(entry['members']), target=str(target_dir), status='restored and verified')

    # 3. the small in-git package files to their mirror paths. Bytes come from the git OBJECT STORE
    #    (git show HEAD:path), never the working tree: a checkout with core.autocrlf rewrote 17 of the
    #    170 files to CRLF and the first host restore refused them (2026-09-16). The blobs are pinned
    #    -text and manifest-exact (tests/test_sunday_package_blobs_match_manifest.py).
    copied = 0
    package_rows = list(restoration['files'])
    for addendum_path in sorted(package.glob('RESTORATION_MANIFEST_ADDENDUM_*.json')):
        addendum_rows = json.loads(addendum_path.read_bytes())['files']
        note(addendum=addendum_path.name, files=len(addendum_rows))
        package_rows += addendum_rows
    for row in package_rows:
        if not row['in_git']:
            continue
        target = Path(row['original_path'])
        shown = subprocess.run([GIT, '-C', str(tools), 'show', 'HEAD:' + row['git_path']], capture_output=True)
        raw = shown.stdout
        if shown.returncode != 0 or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise SystemExit('tools checkout package blob differs from restoration manifest: ' + row['git_path'])
        if not (target.is_file() and sha256_file(target) == row['sha256']):
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw); copied += 1
    note(package_small_files=sum(r['in_git'] for r in package_rows), copied=copied)

    # 4. audits: every bulk pin of the restoration manifest, and the byte-exact working tree.
    #    Both modules are stdlib-only; they are loaded by FILE PATH because importing them through the
    #    package runs research/kalshi/frankie_boss/__init__.py, which imports torch, which the stock
    #    host interpreter does not have (the third host restore died there, 2026-09-16).
    operations = tools / 'research' / 'kalshi' / 'frankie_boss' / 'operations'
    A = load_module_by_path('audit_sunday_restoration_manifest', operations / 'audit_sunday_restoration_manifest.py')
    R = load_module_by_path('restore_sunday_working_tree_identity', operations / 'restore_sunday_working_tree_identity.py')
    addendum = json.loads((package / 'BULK_HASH_ADDENDUM_20260915.json').read_bytes())
    audit = A.audit(restoration, addendum, sha256_file(package / 'RESTORATION_MANIFEST.json'))
    if not audit['passed']:
        raise SystemExit('restoration manifest audit did not pass')
    missing = [r['original_path'] for r in restoration['files'] if not Path(r['original_path']).is_file()]
    if missing:
        raise SystemExit(f'{len(missing)} manifest files absent after restore: {missing[:3]}')
    identity, identity_raw = R.load_identity_manifest(package / 'WORKING_TREE_IDENTITY_BYTES_20260915.json', require_sunday=True)
    R.load_requirements(next(package.glob('*UNREPRODUCIBLE_BYTES_REQUIRED*')), identity, identity_raw)
    tree = R.audit_working_tree(identity['repository'], identity, verify_git=True)
    note(working_tree_audit=tree['identity_files_verified'], identity_set=tree['identity_set_sha256'][:16])
    receipt = dict(schema='FRANKIE_SUNDAY_HOST_RESTORE_RECEIPT_V1', host=os.environ.get('COMPUTERNAME'),
                   bucket=args.bucket, prefix=args.prefix, upload_manifest_sha256=sha256_file(manifest_path),
                   restoration_manifest_sha256=manifest['restoration_manifest_sha256'],
                   bulk_audit=dict(bulk_files=audit['bulk_files'], hash_complete=audit['hash_complete']),
                   working_tree=tree, log=log, completed_unix=time.time())
    Path(args.receipt).write_bytes(json.dumps(receipt, indent=1, sort_keys=True, default=str).encode())
    note(stage='complete', receipt=args.receipt)
    return 0


if __name__ == '__main__':
    sys.exit(main())
