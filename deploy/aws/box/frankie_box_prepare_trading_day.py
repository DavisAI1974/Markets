"""Prepare the recovered Monday data in place, then publish fresh artifacts separately.

No model, ingestion, runtime control, checkout mutation or evidence deletion.
The existing prepare_trading_day operation owns all schedule/science semantics.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request

REPOSITORY = Path(__file__).resolve().parents[3]
OUTPUT_PARENT = Path('/opt/frankie-box/work/trading-day-preparation')
BUCKET = 'frankie-granite42-568968024170-us-east-1'
ORIGINAL_CONTAINER = dict(
    path='/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite',
    bytes=23687368704,
    sha256='947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888')
sys.path.insert(0, str(REPOSITORY))


def safe_path(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('absolute path without parent traversal required')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink path refused')
    return path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def witness(path):
    path = safe_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('regular artifact required')
    return dict(path=str(path), bytes=info.st_size, sha256=digest(path))


def read_pin(pin):
    if (type(pin) is not dict or not {'path', 'bytes', 'sha256'} <= set(pin)
            or type(pin['bytes']) is not int):
        raise ValueError('complete file pin required')
    path = safe_path(pin['path'])
    if not path.is_file():
        raise ValueError('regular pinned artifact required')
    raw = path.read_bytes()
    if len(raw) != pin['bytes'] or hashlib.sha256(raw).hexdigest() != pin['sha256']:
        raise ValueError('pinned file bytes differ')
    return json.loads(raw)


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_new(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(Path(path).parent)


def require_checkout(commit):
    if not re.fullmatch('[0-9a-f]{40}', str(commit)):
        raise ValueError('full reviewed commit required')
    def git(*args):
        return subprocess.run(['git', '--no-optional-locks', '-C', str(REPOSITORY), *args],
                              capture_output=True, text=True, check=False)
    head = git('rev-parse', 'HEAD')
    if head.returncode or head.stdout.strip() != commit:
        raise ValueError('checkout differs from reviewed commit')
    if git('diff', '--quiet', 'HEAD', '--').returncode:
        raise ValueError('tracked checkout changes refused')
    if git('ls-files', '--error-unmatch', 'deploy/aws/box/frankie_box_prepare_trading_day.py').returncode:
        raise ValueError('preparation adapter must be tracked at reviewed commit')


def reject_credentials(value):
    forbidden = {'api_key', 'password', 'token', 'access_key', 'secret_key',
                 'aws_access_key_id', 'aws_secret_access_key', 'aws_session_token'}
    if isinstance(value, dict):
        if any(str(k).lower() in forbidden for k in value):
            raise ValueError('literal credential field refused')
        for child in value.values():
            reject_credentials(child)
    elif isinstance(value, list):
        for child in value:
            reject_credentials(child)
    elif isinstance(value, str) and ('X-Amz-Signature=' in value or 'X-Amz-Credential=' in value):
        raise ValueError('credential capability refused in configuration')


def output_root_path(value):
    root = safe_path(value)
    if root.parent != OUTPUT_PARENT or not re.fullmatch('[A-Za-z0-9_-]{1,96}', root.name):
        raise ValueError('fresh named preparation root required')
    return root


def run_preparation(configuration, output_configuration):
    from research.kalshi.frankie_boss.operations.prepare_trading_day import prepare
    return prepare(configuration, output_configuration=output_configuration)


def prepare_bundle(configuration, *, configuration_sha256, commit, output_root):
    if not sys.platform.startswith('linux'):
        raise ValueError('Linux preparation only')
    require_checkout(commit)
    configuration = safe_path(configuration)
    raw = configuration.read_bytes()
    pin = dict(path=str(configuration), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    if pin['sha256'] != configuration_sha256:
        raise ValueError('configuration sha256 differs')
    config = json.loads(raw)
    reject_credentials(config)
    from research.kalshi.frankie_boss.trading_day_schedule import require_launch_fields
    launch = require_launch_fields(read_pin(config['trading_day_launch']))
    if launch.get('trading_day') != '20211004':
        raise ValueError('explicit Monday trading day required')
    roster = read_pin(launch['cutoffs']).get('invocation_cutoffs')
    if type(roster) is not list or not roster:
        raise ValueError('explicit nonempty cutoff roster required')
    descriptor = read_pin(launch['ingestion_receipt'])
    if descriptor.get('schema') != 'FRANKIE_VERIFIED_RECOVERED_INGESTION_V1':
        raise ValueError('verified recovered ingestion descriptor required')
    recovery = read_pin(descriptor['recovery_receipt'])
    verification = read_pin(descriptor['verification'])
    if recovery.get('container') != ORIGINAL_CONTAINER or verification.get('container') != ORIGINAL_CONTAINER:
        raise ValueError('exact original container required in place')
    source = safe_path(ORIGINAL_CONTAINER['path'])
    before = source.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('original container is not regular')
    root = output_root_path(output_root)
    if root.exists():
        raise FileExistsError('existing preparation evidence preserved')
    if (safe_path(config['schedule_directory']) != root/'schedule'
            or safe_path(config['host_runtime']['prefixes_directory']) != root/'prefixes'):
        raise ValueError('configured output paths escape preparation root')
    if configuration.is_relative_to(root):
        raise ValueError('configuration must precede the fresh output root')
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir()
    sync_directory(root.parent)
    intent = dict(schema='FRANKIE_LINUX_PREPARATION_INTENT_V1', commit=commit,
                  configuration=pin, source_container=ORIGINAL_CONTAINER,
                  output_root=str(root), model_calls=0, source_replays=0)
    save_new(root/'preparation-intent.json', intent)
    result = run_preparation(configuration, root/'prepared-configuration.json')
    after = source.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('original container changed during preparation')
    if witness(configuration) != pin:
        raise ValueError('configuration changed during preparation')
    files = []
    for top in (root/'schedule', root/'prefixes', root/'prepared-configuration.json'):
        paths = sorted(top.rglob('*')) if top.is_dir() else [top]
        for path in paths:
            safe_path(path)
            info = path.stat()
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('generated nonregular or hardlinked artifact refused')
            item = witness(path)
            files.append(dict(name=path.relative_to(root).as_posix(),
                              bytes=item['bytes'], sha256=item['sha256']))
    if not files or result.get('configuration') != witness(root/'prepared-configuration.json'):
        raise ValueError('prepared configuration receipt differs')
    receipt = dict(schema='FRANKIE_LINUX_PREPARATION_RECEIPT_V1',
                   intent=witness(root/'preparation-intent.json'), source_container=ORIGINAL_CONTAINER,
                   result=result, files=files, model_calls=0, source_replays=0)
    save_new(root/'preparation-receipt.json', receipt)
    members = [item['name'] for item in files] + ['preparation-intent.json', 'preparation-receipt.json']
    with (root/'artifacts.tar').open('xb') as stream:
        with tarfile.open(fileobj=stream, mode='w|') as archive:
            for name in members:
                archive.add(root/name, arcname=name, recursive=False)
        stream.flush()
        os.fsync(stream.fileno())
    for item in files:
        actual = witness(root/item['name'])
        if actual['bytes'] != item['bytes'] or actual['sha256'] != item['sha256']:
            raise ValueError('generated artifact changed during archival')
    publication = dict(schema='FRANKIE_PREPARATION_PUBLICATION_V1',
                       archive=witness(root/'artifacts.tar'),
                       preparation_receipt=witness(root/'preparation-receipt.json'),
                       source_container=ORIGINAL_CONTAINER, commit=commit,
                       model_calls=0, source_replays=0)
    save_new(root/'publication-receipt.json', publication)
    return dict(archive=publication['archive'], publication_receipt=witness(root/'publication-receipt.json'),
                model_calls=0, source_replays=0)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('publication redirect refused')


def put_file(path, url, sha256):
    checksum = base64.b64encode(bytes.fromhex(sha256)).decode('ascii')
    with Path(path).open('rb') as stream:
        request = urllib.request.Request(url, data=stream, method='PUT',
            headers={'Content-Length': str(Path(path).stat().st_size),
                     'If-None-Match': '*', 'x-amz-checksum-sha256': checksum})
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=900):
            pass


def publish(output_root, upload_map):
    root = output_root_path(output_root)
    if (upload_map.get('schema') != 'FRANKIE_PREPARATION_UPLOAD_MAP_V1'
            or upload_map.get('bucket') != BUCKET
            or not re.fullmatch('readiness/20260922/trading-day-preparation/[A-Za-z0-9_-]{1,96}',
                                str(upload_map.get('prefix')))):
        raise ValueError('explicit fresh publication destination required')
    names = ('artifacts.tar', 'publication-receipt.json')
    if set(upload_map.get('files', {})) != set(names):
        raise ValueError('archive and completion receipt capabilities required')
    publication = json.loads(safe_path(root/names[1]).read_bytes())
    if (publication.get('schema') != 'FRANKIE_PREPARATION_PUBLICATION_V1'
            or publication.get('archive') != witness(root/names[0])
            or publication.get('preparation_receipt') != witness(root/'preparation-receipt.json')):
        raise ValueError('publication evidence changed')
    for name in names:
        entry = upload_map['files'][name]
        actual = witness(root/name)
        if any(entry.get(k) != actual[k] for k in ('bytes', 'sha256')):
            raise ValueError('upload capability bytes differ')
        url = urllib.parse.urlsplit(entry.get('url', ''))
        signed = urllib.parse.parse_qs(url.query).get('X-Amz-SignedHeaders', [''])[0].split(';')
        if (url.scheme != 'https' or url.netloc != BUCKET+'.s3.us-east-1.amazonaws.com'
                or url.path != '/'+upload_map['prefix']+'/'+name or url.fragment
                or not {'host', 'if-none-match', 'x-amz-checksum-sha256'} <= set(signed)):
            raise ValueError('unsafe or unbound upload capability')
    for name in names:
        entry = upload_map['files'][name]
        put_file(root/name, entry['url'], entry['sha256'])
    return dict(status='published', bucket=BUCKET, prefix=upload_map['prefix'],
                archive_sha256=upload_map['files'][names[0]]['sha256'],
                receipt_sha256=upload_map['files'][names[1]]['sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--configuration', required=True)
    prep.add_argument('--configuration-sha256', required=True)
    prep.add_argument('--commit', required=True)
    prep.add_argument('--output-root', required=True)
    publication = sub.add_parser('publish')
    publication.add_argument('--output-root', required=True)
    publication.add_argument('--upload-map', required=True)
    publication.add_argument('--upload-map-sha256', required=True)
    args = parser.parse_args()
    try:
        if args.mode == 'prepare':
            result = prepare_bundle(args.configuration, configuration_sha256=args.configuration_sha256,
                                    commit=args.commit, output_root=args.output_root)
        else:
            path = safe_path(args.upload_map)
            if digest(path) != args.upload_map_sha256:
                raise ValueError('upload map bytes differ')
            result = publish(args.output_root, json.loads(path.read_bytes()))
    except Exception as error:
        # Exception messages from HTTP clients can contain signed capabilities.
        print(json.dumps(dict(status='refused', error_type=type(error).__name__)), flush=True)
        return 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
