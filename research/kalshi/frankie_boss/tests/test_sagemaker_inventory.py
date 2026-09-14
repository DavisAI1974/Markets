import sagemaker_inventory as module


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
