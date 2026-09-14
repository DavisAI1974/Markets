"""Read-only Bedrock deployment metadata inventory; never invokes a model.

Only explicit List APIs are used. No credential values or exception messages
are printed or stored. Permission failures are evidence, not empty inventories.
"""
from datetime import datetime, timezone
import json
from pathlib import Path


OPERATIONS = (
    ('list_foundation_models', 'modelSummaries', False),
    ('list_custom_models', 'modelSummaries', True),
    ('list_imported_models', 'modelSummaries', True),
    ('list_marketplace_model_endpoints', 'marketplaceModelEndpoints', True),
    ('list_custom_model_deployments', 'modelDeploymentSummaries', True),
    ('list_provisioned_model_throughputs', 'provisionedModelSummaries', True),
    ('list_inference_profiles', 'inferenceProfileSummaries', True),
)


def collect_operation(operation, result_key, *, paginated, max_pages=5):
    if type(max_pages) is not int or max_pages <= 0:
        raise ValueError('positive page limit required')
    result = {'status': 'running', 'items': [], 'pages': 0}
    args = {'maxResults': 100} if paginated else {}
    seen = set()
    try:
        for _ in range(max_pages):
            page = operation(**args)
            result['items'].extend(page[result_key])
            result['pages'] += 1
            token = page.get('nextToken')
            if not token:
                result['status'] = 'complete'
                return result
            if not paginated or token in seen:
                result['status'] = 'pagination_error'
                return result
            seen.add(token)
            args['nextToken'] = token
        result['status'] = 'truncated'
    except Exception as exc:
        result['status'] = 'error'
        result['error_type'] = type(exc).__name__
        response = getattr(exc, 'response', {})
        result['error_code'] = response.get('Error', {}).get('Code')
        result['request_id'] = response.get('ResponseMetadata', {}).get('RequestId')
    return result


def main(argv=None):
    import argparse
    import boto3
    from botocore.config import Config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--regions', nargs='+', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'BOSS_BEDROCK_INVENTORY_V1', 'boto3_version': boto3.__version__,
              'started_utc': datetime.now(timezone.utc).isoformat(),
              'regions': {}, 'status': 'running'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream)

    def save():
        output.write_text(json.dumps(report, sort_keys=True, indent=2, default=str) + '\n', encoding='utf-8')

    for region in args.regions:
        entries = report['regions'][region] = {}
        try:
            client = boto3.client('bedrock', region_name=region,
                                  config=Config(connect_timeout=3, read_timeout=5,
                                                retries={'total_max_attempts': 1, 'mode': 'standard'}))
        except Exception as exc:
            entries['client'] = {'status': 'error', 'error_type': type(exc).__name__}
            save()
            continue
        for name, key, paginated in OPERATIONS:
            operation = getattr(client, name, None)
            if operation is None:
                entries[name] = {'status': 'unsupported_sdk_operation'}
            else:
                entries[name] = collect_operation(operation, key, paginated=paginated)
            save()
            print(region, name, entries[name]['status'], len(entries[name].get('items', [])))
    complete = all(entry['status'] == 'complete' for entries in report['regions'].values() for entry in entries.values())
    report['status'] = 'complete' if complete else 'incomplete'
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
