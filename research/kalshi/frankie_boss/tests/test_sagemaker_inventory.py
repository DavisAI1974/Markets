import sagemaker_inventory as module
import json
import pytest


def test_exact_endpoint_quota_stops_before_unrelated_pages():
    class Client:
        calls = 0
        def list_service_quotas(self, **kwargs):
            self.calls += 1
            assert self.calls <= 2
            return {'Quotas': [{'QuotaCode': 'unrelated', 'QuotaName': 'ml.g6e.2xlarge training', 'Value': 99}]
                    if self.calls == 1 else [{'QuotaCode': 'L-F8D7F460', 'QuotaName': 'ml.g6e.2xlarge for endpoint usage', 'Value': 0, 'Adjustable': True}],
                    'NextToken': str(self.calls)}
    client = Client()
    result = module.quotas(client, max_pages=2)
    assert result['status'] == 'complete'
    assert len(result['items']) == 1 and result['items'][0]['Value'] == 0
    assert client.calls == 2


def test_quota_missing_or_bounded_search_does_not_claim_complete():
    class Client:
        def list_service_quotas(self, **kwargs):
            return {'Quotas': [], 'NextToken': str(int(kwargs.get('NextToken', '0'))+1)}
    assert module.quotas(Client(), max_pages=2)['status'] == 'truncated'
    class Missing:
        def list_service_quotas(self, **kwargs):
            return {'Quotas': []}
    assert module.quotas(Missing())['status'] == 'unresolved'


def price_product(component='Hosting', rate='1.23'):
    return {'product': {'sku': 'synthetic', 'attributes': {'component': component,
            'instanceName': 'ml.g6e.2xlarge', 'regionCode': 'us-east-1'}},
            'terms': {'OnDemand': {'term': {'priceDimensions': {'dimension':
                {'unit': 'Hrs', 'pricePerUnit': {'USD': rate}}}}}}}


def test_pricing_uses_hosting_scope_and_does_not_promote_studio_price():
    class Client:
        def get_products(self, **kwargs):
            filters = {f['Field']: f['Value'] for f in kwargs['Filters']}
            assert filters == {'instanceName': 'ml.g6e.2xlarge', 'component': 'Hosting', 'regionCode': 'us-east-1'}
            return {'PriceList': [json.dumps(price_product('studio-jupyterlab'))]}
    result = module.prices(Client(), 'us-east-1')
    assert result['status'] == 'unresolved'
    assert result['endpoint_rates'] == []
    assert len(result['items']) == 1


def test_hosting_hourly_price_retains_exact_decimal_and_scope():
    class Client:
        def get_products(self, **kwargs):
            return {'PriceList': [json.dumps(price_product())]}
    result = module.prices(Client(), 'us-east-1')
    assert result['status'] == 'complete'
    assert result['endpoint_rates'][0]['usd_per_instance_hour'] == '1.23'
    assert result['scope'] == 'on_demand_hosting_compute_only'


@pytest.mark.parametrize('rate', ['NaN', 'Infinity', '-1', 'not-a-price'])
def test_invalid_endpoint_rate_is_unresolved(rate):
    class Client:
        def get_products(self, **kwargs):
            return {'PriceList': [json.dumps(price_product(rate=rate))]}
    result = module.prices(Client(), 'us-east-1')
    assert result['status'] == 'unresolved'
    assert result['endpoint_rate_status'] == 'unresolved'


@pytest.mark.parametrize('scenario', ['missing', 'ambiguous', 'wrong-region', 'wrong-unit', 'incomplete'])
def test_endpoint_rate_requires_one_complete_matching_hourly_dimension(scenario):
    product = price_product()
    if scenario == 'wrong-region':
        product['product']['attributes']['regionCode'] = 'elsewhere'
    if scenario == 'wrong-unit':
        product['terms']['OnDemand']['term']['priceDimensions']['dimension']['unit'] = 'GB-Mo'
    class Client:
        def get_products(self, **kwargs):
            response = {'PriceList': [] if scenario == 'missing' else [json.dumps(product)] * (2 if scenario == 'ambiguous' else 1)}
            if scenario == 'incomplete':
                response['NextToken'] = 'repeated'
            return response
    result = module.prices(Client(), 'us-east-1')
    assert result['status'] != 'complete'
    assert result['endpoint_rate_status'] == 'unresolved'


def test_pages_follows_tokens_and_reports_incomplete():
    seen = []
    def call(**kwargs):
        seen.append(kwargs)
        return {'Values': [len(seen)], 'NextToken': 'again'}
    assert module.pages(call, 'Values') == {'status': 'pagination_error', 'items': [1, 2]}
    assert seen == [{}, {'NextToken': 'again'}]
    assert module.pages(call, 'Values', max_pages=1)['status'] == 'truncated'


def test_safe_error_never_persists_exception_message():
    class Failure(Exception):
        response = {'Error': {'Code': 'AccessDenied', 'Message': 'private'},
                    'ResponseMetadata': {'RequestId': 'id'}}
    def fail():
        raise Failure('private')
    result = module.safe(fail)
    assert result['error_code'] == 'AccessDenied'
    assert 'private' not in str(result)


def test_roles_retains_only_sagemaker_execution_candidates():
    class Client:
        def list_roles(self, **kwargs):
            return {'Roles': [{'Arn': 'arn:role:yes', 'RoleName': 'yes',
                               'AssumeRolePolicyDocument': {'Principal': {'Service': 'sagemaker.amazonaws.com'}}},
                              {'Arn': 'arn:role:no', 'RoleName': 'no'}]}
    assert module.roles(Client())['items'] == [{'arn': 'arn:role:yes', 'name': 'yes'}]


def test_image_missing_is_not_success():
    class Client:
        def batch_get_image(self, **kwargs):
            assert kwargs['registryId'] == '763104351884'
            assert kwargs['imageIds'] == [{'imageTag': module.IMAGE_TAG}]
            return {'images': [], 'failures': [{'failureCode': 'ImageNotFound', 'failureReason': 'private'}]}
    assert module.image(Client()) == {'status': 'unresolved', 'images': [], 'failure_codes': ['ImageNotFound']}


def test_endpoints_use_granite_prefix_and_exclude_substring_collisions():
    class Client:
        def list_endpoints(self, **kwargs):
            assert kwargs['NameContains'] == 'frankie-granite42-'
            return {'Endpoints': [{'EndpointName': 'frankie-granite42-run', 'EndpointStatus': 'InService'},
                                  {'EndpointName': 'other-frankie-granite42-run', 'EndpointStatus': 'Failed'}]}
    result = module.endpoints(Client())
    assert result['status'] == 'complete'
    assert result['scope'] == 'frankie-granite42-'
    assert [item['EndpointName'] for item in result['items']] == ['frankie-granite42-run']


def test_image_retains_and_verifies_actual_registry_manifest():
    import hashlib
    manifest = '{"schemaVersion":2,"config":{"digest":"sha256:config"}}'
    digest = 'sha256:' + hashlib.sha256(manifest.encode()).hexdigest()
    class Client:
        def batch_get_image(self, **kwargs):
            return {'images': [{'imageId': {'imageDigest': digest}, 'registryId': '763104351884',
                               'repositoryName': 'vllm', 'imageManifest': manifest,
                               'imageManifestMediaType': 'application/vnd.docker.distribution.manifest.v2+json'}]}
    result = module.image(Client())
    assert result['status'] == 'complete'
    assert result['images'][0]['imageManifest'] == manifest
    assert result['images'][0]['manifest_digest_verified'] is True


def test_image_digest_mismatch_cannot_be_resolved():
    class Client:
        def batch_get_image(self, **kwargs):
            return {'images': [{'imageId': {'imageDigest': 'sha256:' + '0' * 64},
                               'registryId': '763104351884', 'repositoryName': 'vllm',
                               'imageManifest': '{}'}]}
    assert module.image(Client())['status'] == 'unresolved'
