"""Linux preparation adapter tests; only tiny isolated recovered fixtures."""
import base64
import hashlib
import json
from pathlib import Path
import tarfile
from types import SimpleNamespace
import pytest
from test_recovered_ingestion_bridge import recovered_inputs
from test_prepare_trading_day import sha, witness, write_json, checked_json
from deploy.aws.box import frankie_box_prepare_trading_day as adapter

COMMIT = 'a' * 40

def fixture(tmp_path, monkeypatch):
    f = recovered_inputs(tmp_path, monkeypatch)
    root = tmp_path / 'preparations' / 'run-1'
    root.parent.mkdir()
    config = json.loads(f.config.read_bytes())
    config['schedule_directory'] = str(root / 'schedule')
    config['host_runtime']['prefixes_directory'] = str(root / 'prefixes')
    write_json(f.config, config)
    monkeypatch.setattr(adapter, 'OUTPUT_PARENT', root.parent)
    monkeypatch.setattr(adapter, 'ORIGINAL_CONTAINER', f.receipt['container'])
    monkeypatch.setattr(adapter, 'require_checkout', lambda commit: None)
    return f, root

def prepare(f, root):
    return adapter.prepare_bundle(f.config, configuration_sha256=sha(f.config),
                                  commit=COMMIT, output_root=root)

def repin_launch(f, **changes):
    config = json.loads(f.config.read_bytes())
    launch = checked_json(config['trading_day_launch'])
    launch.update(changes)
    config['trading_day_launch'] = write_json(config['trading_day_launch']['path'], launch)
    write_json(f.config, config)

def test_real_recovered_preparation_preserves_source_and_packages_only_fresh_outputs(tmp_path, monkeypatch):
    f, root = fixture(tmp_path, monkeypatch)
    from test_ingest_block_sources import tool
    monkeypatch.setattr(tool, 'main', lambda: pytest.fail('source ingestion restarted'))
    result = prepare(f, root)
    assert result['model_calls'] == result['source_replays'] == 0
    assert {str(p): sha(p) for p in f.source.iterdir() if p.is_file()} == f.before
    assert (root/'preparation-intent.json').is_file()
    receipt = json.loads((root/'preparation-receipt.json').read_bytes())
    assert receipt['source_container'] == f.receipt['container']
    assert receipt['result']['prefix_count'] == 1
    cfg = json.loads((root/'prepared-configuration.json').read_bytes())
    assert cfg['host_runtime']['compact_journal'] == f.receipt['container']
    schedule = checked_json(cfg['host_runtime']['schedule'])
    assert schedule['steps'][0]['as_of'] == 1633312800000000000
    with tarfile.open(root/'artifacts.tar', 'r:') as archive:
        names = archive.getnames()
        assert 'prepared-configuration.json' in names
        assert 'prefixes/prefix-00.sqlite' in names
        assert not any('journal.compact.sqlite' in n or n.startswith('/') or '..' in Path(n).parts for n in names)
        for entry in receipt['files']:
            data = archive.extractfile(entry['name']).read()
            assert len(data) == entry['bytes']
            assert hashlib.sha256(data).hexdigest() == entry['sha256']
    assert sha(root/'artifacts.tar') == result['archive']['sha256']
    assert result['publication_receipt'] == witness(root/'publication-receipt.json')

@pytest.mark.parametrize('field', ['model_context_rows','cutoff_rule','cutoffs','mapping','source_contract','publish_route'])
def test_missing_launch_values_refuse_before_output(tmp_path, monkeypatch, field):
    f, root = fixture(tmp_path, monkeypatch)
    repin_launch(f, **{field: None})
    with pytest.raises(ValueError):
        prepare(f, root)
    assert not root.exists()

def test_configuration_hash_and_credentials_refuse_before_output(tmp_path, monkeypatch):
    f, root = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        adapter.prepare_bundle(f.config, configuration_sha256='0'*64, commit=COMMIT, output_root=root)
    config = json.loads(f.config.read_bytes())
    config['api_key'] = 'DO_NOT_PRINT_ME'
    write_json(f.config, config)
    with pytest.raises(ValueError, match='credential'):
        prepare(f, root)
    assert not root.exists()

def test_copied_source_pin_is_not_accepted(tmp_path, monkeypatch):
    f, root = fixture(tmp_path, monkeypatch)
    expected = dict(f.receipt['container'], path=str(tmp_path/'copy.sqlite'))
    monkeypatch.setattr(adapter, 'ORIGINAL_CONTAINER', expected)
    with pytest.raises(ValueError, match='original container'):
        prepare(f, root)
    assert not root.exists()

@pytest.mark.parametrize('change', ['existing','escape','symlink'])
def test_existing_or_escaping_output_paths_refuse(tmp_path, monkeypatch, change):
    f, root = fixture(tmp_path, monkeypatch)
    if change == 'existing':
        root.mkdir()
        (root/'old').write_bytes(b'evidence')
    else:
        config = json.loads(f.config.read_bytes())
        if change == 'escape':
            config['schedule_directory'] = str(tmp_path/'foreign')
        else:
            target = tmp_path/'outside'
            target.mkdir()
            root.symlink_to(target, target_is_directory=True)
        write_json(f.config, config)
    with pytest.raises((ValueError, FileExistsError)):
        prepare(f, root)
    assert not (tmp_path/'foreign').exists()
    if change == 'existing':
        assert (root/'old').read_bytes() == b'evidence'

def test_failed_preparation_leaves_durable_intent_and_partial_evidence(tmp_path, monkeypatch):
    f, root = fixture(tmp_path, monkeypatch)
    def fail(*args, **kwargs):
        (root/'partial').write_bytes(b'keep')
        raise RuntimeError('fixture failure')
    monkeypatch.setattr(adapter, 'run_preparation', fail)
    with pytest.raises(RuntimeError):
        prepare(f, root)
    assert (root/'preparation-intent.json').is_file()
    assert (root/'partial').read_bytes() == b'keep'
    assert not (root/'publication-receipt.json').exists()

def test_checkout_requires_full_commit_and_clean_expected_head(monkeypatch):
    for commit in ('main', 'a'*39, 'A'*40):
        with pytest.raises(ValueError):
            adapter.require_checkout(commit)
    monkeypatch.setattr(adapter.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='b'*40+'\n'))
    with pytest.raises(ValueError, match='checkout'):
        adapter.require_checkout(COMMIT)
    calls = []
    def dirty(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0 if 'rev-parse' in args else 1, stdout=COMMIT+'\n')
    monkeypatch.setattr(adapter.subprocess, 'run', dirty)
    with pytest.raises(ValueError, match='tracked'):
        adapter.require_checkout(COMMIT)

def upload_map(root):
    prefix = 'readiness/20260922/trading-day-preparation/test-run'
    entries = {}
    for name in ('artifacts.tar','publication-receipt.json'):
        entries[name] = dict(sha256=sha(root/name), bytes=(root/name).stat().st_size,
            url='https://' + adapter.BUCKET + '.s3.us-east-1.amazonaws.com/' + prefix + '/' + name +
                '?X-Amz-SignedHeaders=host%3Bif-none-match%3Bx-amz-checksum-sha256&X-Amz-Signature=fixture')
    return dict(schema='FRANKIE_PREPARATION_UPLOAD_MAP_V1', bucket=adapter.BUCKET,
                prefix=prefix, files=entries)

def test_publication_streams_archive_then_receipt_with_verified_checksums(tmp_path, monkeypatch):
    f, root = fixture(tmp_path, monkeypatch)
    prepare(f, root)
    m = upload_map(root)
    uploaded = []
    def put(path, url, digest):
        uploaded.append((Path(path).name, sha(path), digest))
    monkeypatch.setattr(adapter, 'put_file', put)
    result = adapter.publish(root, m)
    assert [x[0] for x in uploaded] == ['artifacts.tar','publication-receipt.json']
    assert all(h == d for _, h, d in uploaded)
    assert result['status'] == 'published'
    assert 'url' not in json.dumps(result).lower()

def test_publication_failure_never_uploads_completion_receipt(tmp_path, monkeypatch):
    f, root = fixture(tmp_path, monkeypatch)
    prepare(f, root)
    def fail(*args): raise OSError('failed archive PUT')
    monkeypatch.setattr(adapter, 'put_file', fail)
    with pytest.raises(OSError):
        adapter.publish(root, upload_map(root))
    assert (root/'artifacts.tar').is_file()

@pytest.mark.parametrize('change', ['hash','destination','headers','redirect'])
def test_publication_rejects_unbound_or_unsafe_capabilities(tmp_path, monkeypatch, change):
    f, root = fixture(tmp_path, monkeypatch)
    prepare(f, root)
    m = upload_map(root)
    entry = m['files']['artifacts.tar']
    if change == 'hash': entry['sha256'] = '0'*64
    elif change == 'destination': entry['url'] = entry['url'].replace('/test-run/', '/other-run/')
    elif change == 'headers': entry['url'] = entry['url'].replace('if-none-match', 'other')
    else: entry['url'] = entry['url'].replace(adapter.BUCKET + '.s3.us-east-1.amazonaws.com', 'evil.example')
    monkeypatch.setattr(adapter, 'put_file', lambda *args: pytest.fail('unsafe PUT'))
    with pytest.raises(ValueError):
        adapter.publish(root, m)

def test_put_uses_conditional_checksum_bound_stream_not_a_memory_copy(tmp_path, monkeypatch):
    path = tmp_path/'payload'
    path.write_bytes(b'exact bytes')
    requests = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert hasattr(request.data, 'read')
            assert request.data.read() == b'exact bytes'
            return Response()
    monkeypatch.setattr(adapter.urllib.request, 'build_opener', lambda *args: Opener())
    adapter.put_file(path, 'https://unused.example/signed', sha(path))
    request = requests[0]
    assert request.method == 'PUT'
    headers = {k.lower(): v for k, v in request.header_items()}
    assert headers['if-none-match'] == '*'
    assert headers['content-length'] == str(path.stat().st_size)
    assert headers['x-amz-checksum-sha256'] == base64.b64encode(bytes.fromhex(sha(path))).decode()
