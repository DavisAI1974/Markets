"""Immutable nonsecret runtime configuration and pre-start capability freshness."""
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import parse_qs, urlsplit

from .granite_run_artifacts import canonical
from .granite_runpod_admission import CONTEXT


def validate_configuration(value):
    fields = {'schema', 'files', 'bundle_sha256', 'supervisor_command_sha256',
        'source_commit', 'context_encoding', 'service_context', 'transport_protocol', 'bootstrap_directory'}
    if (type(value) is not dict or set(value) != fields
            or value['schema'] != 'GRANITE_RETAINED_RUNTIME_CONFIGURATION_V1'
            or value['context_encoding'] not in ('compact_v1', 'stacked_v1', 'stacked_v2')
            or type(value['service_context']) is not int or value['service_context'] != CONTEXT
            or value['transport_protocol'] not in ('direct_v1', 'jobs_v1')
            or not re.fullmatch('[0-9a-f]{40}', str(value['source_commit']))
            or not re.fullmatch('/opt/ml/additional-model-data-sources/[a-z0-9-]+', str(value['bootstrap_directory']))):
        raise ValueError('explicit immutable runtime configuration required')
    for key in ('bundle_sha256', 'supervisor_command_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', str(value[key])):
            raise ValueError('runtime hash required')
    rows = value['files']
    if type(rows) is not list or not rows or len(rows) > 32:
        raise ValueError('exact bootstrap roster required')
    names = set()
    for row in rows:
        if (type(row) is not dict or set(row) != {'path', 'size', 'sha256'}
                or not re.fullmatch(r'[a-z0-9_]+\.(py|json)', str(row['path']))
                or row['path'] == 'runpod_bundle.json'
                or row['path'] in names or type(row['size']) is not int or not 0 < row['size'] <= 1048576
                or not re.fullmatch('[0-9a-f]{64}', str(row['sha256']))):
            raise ValueError('invalid bootstrap file pin')
        names.add(row['path'])
    digest = hashlib.sha256(canonical(dict(schema='GRANITE_RUNPOD_BUNDLE_V1', files=rows))).hexdigest()
    if digest != value['bundle_sha256']:
        raise ValueError('bootstrap roster hash differs')
    return value


def persist_configuration(journal, supplied):
    prior = journal.get('retained-runtime-configuration.json')
    if prior is not None:
        validate_configuration(prior)
        if supplied is not None and canonical(validate_configuration(supplied)) != canonical(prior):
            raise ValueError('replacement observer configuration differs from original')
        return prior
    value = validate_configuration(supplied)
    journal.put('retained-runtime-configuration.json', value, once=True)
    return value


def validate_url_freshness(environment, configuration, *, now):
    try:
        urls = json.loads(environment['RP_BOOTSTRAP_URLS'])
        expected_names = {row['path'] for row in configuration['files']} | {'runpod_bundle.json'}
        if type(urls) is not dict or set(urls) != expected_names:
            raise ValueError()
        expiries = []
        for url in urls.values():
            parsed = urlsplit(url)
            query = parse_qs(parsed.query, strict_parsing=True)
            if parsed.scheme != 'https' or parsed.username or parsed.password:
                raise ValueError()
            dates, spans = query['X-Amz-Date'], query['X-Amz-Expires']
            if len(dates) != 1 or len(spans) != 1:
                raise ValueError()
            start = datetime.strptime(dates[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).timestamp()
            span = int(spans[0])
            if not 0 < span <= 604800 or start > now+60:
                raise ValueError()
            expiries.append(start+span)
        earliest = min(expiries)
        if earliest < now+60:
            raise ValueError()
        return earliest
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError('refresh bootstrap capabilities before start; at least 60 seconds required') from None
