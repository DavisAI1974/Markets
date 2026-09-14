"""Read-only prerequisites for exact Granite deployment; no resource creation."""
import json
from pathlib import Path

IMAGE_TAG = '0.20.2-gpu-py312-cu130-ubuntu22.04-sagemaker'


def pages(operation, key, *, args=None, token_key='NextToken', max_pages=20):
    request, items, seen = dict(args or {}), [], set()
    for _ in range(max_pages):
        response = operation(**request)
        items.extend(response[key])
        token = response.get(token_key)
        if not token:
            return {'status': 'complete', 'items': items}
        if token in seen:
            return {'status': 'pagination_error', 'items': items}
        seen.add(token)
        request[token_key] = token
    return {'status': 'truncated', 'items': items}


def safe(operation):
    try:
        return operation()
    except Exception as exc:
        response = getattr(exc, 'response', {})
        return {'status': 'error', 'error_type': type(exc).__name__,
                'error_code': response.get('Error', {}).get('Code'),
                'request_id': response.get('ResponseMetadata', {}).get('RequestId')}


def roles(client):
    result = pages(client.list_roles, 'Roles', args={'MaxItems': 100}, token_key='Marker')
    result['items'] = [{'arn': role['Arn'], 'name': role['RoleName']}
                       for role in result['items']
                       if 'sagemaker.amazonaws.com' in json.dumps(role.get('AssumeRolePolicyDocument', {}))]
    return result


def quotas(client):
    result = pages(client.list_service_quotas, 'Quotas', args={'ServiceCode': 'sagemaker', 'MaxResults': 100})
    result['items'] = [{key: item.get(key) for key in ('QuotaName', 'QuotaCode', 'Value', 'Adjustable')}
                       for item in result['items'] if 'g6e.2xlarge' in item.get('QuotaName', '')]
    return result


def prices(client, region):
    result = pages(client.get_products, 'PriceList', args={'ServiceCode': 'AmazonSageMaker', 'MaxResults': 100,
                   'Filters': [{'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': 'ml.g6e.2xlarge'},
                               {'Type': 'TERM_MATCH', 'Field': 'regionCode', 'Value': region}]})
    result['items'] = [json.loads(item) for item in result['items']]
    return result


def image(client):
    response = client.batch_get_image(registryId='763104351884', repositoryName='vllm',
                                     imageIds=[{'imageTag': IMAGE_TAG}])
    return {'status': 'complete' if response.get('images') and not response.get('failures') else 'unresolved',
            'images': [{'imageId': item['imageId'], 'registryId': item['registryId'],
                        'repositoryName': item['repositoryName']} for item in response.get('images', [])],
            'failure_codes': [item.get('failureCode') for item in response.get('failures', [])]}


def main(argv=None):
    import argparse
    import boto3
    from botocore.config import Config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regions', nargs='+', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'BOSS_SAGEMAKER_PREREQUISITES_V1', 'regions': {}}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream)

    def client(service, region):
        return boto3.client(service, region_name=region,
                            config=Config(connect_timeout=3, read_timeout=5,
                                          retries={'total_max_attempts': 1, 'mode': 'standard'}))

    def save():
        output.write_text(json.dumps(report, sort_keys=True, indent=2, default=str) + '\n', encoding='utf-8')

    report['execution_roles'] = safe(lambda: roles(client('iam', 'us-east-1')))
    save()
    for region in args.regions:
        entries = report['regions'][region] = {}
        for name, collect in (
            ('gpu_quotas', lambda: quotas(client('service-quotas', region))),
            ('gpu_prices', lambda: prices(client('pricing', 'us-east-1'), region)),
            ('image_digest', lambda: image(client('ecr', region))),
            ('existing_boss_endpoints', lambda: pages(client('sagemaker', region).list_endpoints, 'Endpoints',
                                                       args={'NameContains': 'boss', 'MaxResults': 100})),
        ):
            entries[name] = safe(collect)
            save()
            print(region, name, entries[name]['status'])
    complete = report['execution_roles']['status'] == 'complete' and all(
        entry['status'] == 'complete' for region in report['regions'].values() for entry in region.values())
    report['status'] = 'complete' if complete else 'incomplete'
    save()
    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
