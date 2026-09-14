"""Inventory contract tests, entirely offline."""
from botocore.exceptions import ClientError
from research.kalshi.frankie_boss.bedrock_inventory import collect_operation


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
