"""Inventory contract tests, entirely offline."""
from botocore.exceptions import ClientError
from bedrock_inventory import collect_operation


def test_complete_pagination_retains_metadata():
    calls = []
    def operation(**kwargs):
        calls.append(kwargs)
        return {'items': [len(calls)], **({'nextToken': 'next'} if len(calls) == 1 else {})}
    result = collect_operation(operation, 'items', paginated=True)
    assert result['status'] == 'complete'
    assert result['items'] == [1, 2]
    assert calls == [{'maxResults': 100}, {'maxResults': 100, 'nextToken': 'next'}]


def test_page_bound_is_explicit_incomplete():
    result = collect_operation(lambda **kw: {'items': [1], 'nextToken': 'next'},
                               'items', paginated=True, max_pages=1)
    assert result['status'] == 'truncated'


def test_permission_failure_has_safe_code_not_message_or_credentials():
    def operation(**kwargs):
        raise ClientError({'Error': {'Code': 'AccessDeniedException', 'Message': 'do not retain sensitive text'},
                           'ResponseMetadata': {'RequestId': 'req'}}, 'ListImportedModels')
    result = collect_operation(operation, 'items', paginated=True)
    assert result['status'] == 'error'
    assert result['error_code'] == 'AccessDeniedException'
    assert 'sensitive' not in str(result)


def test_nonpaginated_no_invalid_arguments():
    def operation(**kwargs):
        assert kwargs == {}
        return {'items': []}
    assert collect_operation(operation, 'items', paginated=False)['status'] == 'complete'


def test_installed_sdk_shapes_match_every_inventory_operation():
    import boto3
    from bedrock_inventory import OPERATIONS
    client = boto3.client('bedrock', region_name='us-east-2',
                          aws_access_key_id='offline', aws_secret_access_key='offline')
    for name, result_key, paginated in OPERATIONS:
        model = client.meta.service_model.operation_model(client.meta.method_to_api_mapping[name])
        assert result_key in model.output_shape.members
        if paginated:
            bounds = model.input_shape.members['maxResults'].metadata
            assert bounds['min'] <= 100 <= bounds['max']
            assert 'nextToken' in model.input_shape.members
            assert 'nextToken' in model.output_shape.members


def test_inventory_import_does_not_require_torch_or_package_initialization():
    import pathlib
    import subprocess
    import sys
    import bedrock_inventory
    directory = pathlib.Path(bedrock_inventory.__file__).resolve().parent
    code = ("import sys; sys.path.insert(0, sys.argv[1]); sys.modules['torch'] = None; "
            "import bedrock_inventory; "
            "assert 'research.kalshi.frankie_boss' not in sys.modules")
    subprocess.run([sys.executable, '-I', '-c', code, str(directory)], check=True)
