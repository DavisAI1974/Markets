import hashlib
import json

import pytest

from research.kalshi.frankie_boss import granite_startup_pins as pins
from research.kalshi.frankie_boss.tests.test_granite_active_run import Journal


def candidate():
    rows = [dict(path='example.py', size=1, sha256='a'*64)]
    return dict(schema='GRANITE_RETAINED_RUNTIME_CONFIGURATION_V1', files=rows,
        bundle_sha256=hashlib.sha256(pins.canonical(dict(schema='GRANITE_RUNPOD_BUNDLE_V1', files=rows))).hexdigest(),
        supervisor_command_sha256='b'*64, source_commit='c'*40,
        context_encoding='stacked_v1', service_context=131072, transport_protocol='jobs_v1',
        bootstrap_directory='/opt/ml/additional-model-data-sources/bootstrap-jobs-v1')


def test_replacement_uses_original_runtime_pins_without_reading_checkout():
    journal = Journal()
    value = candidate()
    assert pins.persist_configuration(journal, value) == value
    assert pins.persist_configuration(journal, None) == value
    with pytest.raises(ValueError):
        pins.persist_configuration(journal, dict(value, source_commit='d'*40))
    with pytest.raises(ValueError):
        pins.persist_configuration(Journal(), dict(value, service_key='secret'))


def test_expired_or_missing_url_refused_before_start_and_only_expiry_persisted():
    value = candidate()
    url = 'https://bucket.s3.amazonaws.com/example.py?X-Amz-Date=20260915T000000Z&X-Amz-Expires=1800&X-Amz-Signature=secret'
    environment = {'RP_BOOTSTRAP_URLS': json.dumps({'example.py': url, 'runpod_bundle.json': url})}
    now = pins.datetime(2026, 9, 15, tzinfo=pins.timezone.utc).timestamp()
    assert pins.validate_url_freshness(environment, value, now=now) == now+1800
    with pytest.raises(ValueError):
        pins.validate_url_freshness(environment, value, now=now+1750)
    with pytest.raises(ValueError):
        pins.validate_url_freshness({'RP_BOOTSTRAP_URLS': '{}'}, value, now=now)


def test_actual_fifteen_minute_capability_allows_elapsed_staging_but_refuses_near_expiry():
    value = candidate()
    start = pins.datetime(2026, 9, 15, tzinfo=pins.timezone.utc).timestamp()
    url = 'https://bucket.s3.amazonaws.com/example.py?X-Amz-Date=20260915T000000Z&X-Amz-Expires=900&X-Amz-Signature=synthetic'
    environment = {'RP_BOOTSTRAP_URLS': json.dumps({'example.py': url, 'runpod_bundle.json': url})}
    assert pins.validate_url_freshness(environment, value, now=start+10) == start+900
    with pytest.raises(ValueError):
        pins.validate_url_freshness(environment, value, now=start+850)


def test_real_bootstrap_roster_includes_json_and_manifest_download():
    from research.kalshi.frankie_boss.granite_runpod_package import FILES
    value = candidate()
    rows = [dict(path=name, size=10, sha256='a'*64) for name in FILES]
    value['files'] = rows
    value['bundle_sha256'] = hashlib.sha256(pins.canonical(dict(
        schema='GRANITE_RUNPOD_BUNDLE_V1', files=rows))).hexdigest()
    assert pins.validate_configuration(value) == value
    now = pins.datetime(2026, 9, 15, tzinfo=pins.timezone.utc).timestamp()
    urls = {name: 'https://bucket.s3.amazonaws.com/'+name+
        '?X-Amz-Date=20260915T000000Z&X-Amz-Expires=900&X-Amz-Signature=synthetic'
        for name in (*FILES, 'runpod_bundle.json')}
    assert pins.validate_url_freshness({'RP_BOOTSTRAP_URLS': json.dumps(urls)}, value, now=now+10) == now+900
    del urls['runpod_bundle.json']
    with pytest.raises(ValueError):
        pins.validate_url_freshness({'RP_BOOTSTRAP_URLS': json.dumps(urls)}, value, now=now+10)


def test_retired_smoke_service_context_is_refused():
    with pytest.raises(ValueError):
        pins.validate_configuration(dict(candidate(), service_context=4096))
