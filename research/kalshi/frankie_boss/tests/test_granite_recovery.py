"""Recovery fakes never contact AWS or mutate endpoint state."""
import hashlib
import json
import pytest
import granite_recovery as r

class Failure(Exception):
    response={'Error':{'Code':'AccessDeniedException','Message':'cloudtrail denied token=private'},'ResponseMetadata':{'RequestId':'request-id'}}


def event(name=None, **extra):
    return {'CloudTrailEvent':json.dumps(dict(eventID='event-id',eventName='DeleteEndpoint',
        eventSource='sagemaker.amazonaws.com',awsRegion='us-east-1',requestParameters={'endpointName':name or r.NAMES['endpoint']},
        errorCode='ValidationException',errorMessage='Endpoint is being created',userIdentity={'accessKeyId':'private'},**extra))}


def test_cloudtrail_retains_scoped_error_and_exact_query_without_identity():
    class Client:
        def lookup_events(self,**kwargs):
            assert kwargs['StartTime']==r.START and kwargs['EndTime']==r.END
            assert kwargs['LookupAttributes']==[{'AttributeKey':'EventSource','AttributeValue':'sagemaker.amazonaws.com'}]
            return {'Events':[event(),event('unrelated-endpoint')]}
    result=r.cloudtrail(Client())
    assert result['status']=='complete' and result['excluded_events']==1
    assert result['events'][0]['errorMessage']=='Endpoint is being created'
    assert 'private' not in str(result)


def test_cloudtrail_repeated_token_is_incomplete():
    class Client:
        def lookup_events(self,**kwargs):return {'Events':[event()],'NextToken':'repeated'}
    result=r.cloudtrail(Client(),sleep=lambda _:None)
    assert result['status']=='pagination_error' and result['pages']==2


def test_cloudtrail_later_denial_retains_prior_events():
    class Client:
        calls=0
        def lookup_events(self,**kwargs):
            self.calls+=1
            if self.calls==2:raise Failure()
            return {'Events':[event()],'NextToken':'next'}
    result=r.cloudtrail(Client(),sleep=lambda _:None)
    assert result['status']=='error' and len(result['events'])==1
    assert result['failure']['response']['ResponseMetadata']['RequestId']=='request-id'
    assert 'private' not in str(result)


def test_log_empty_page_continues_and_preserves_partial_failure():
    class Client:
        calls=0
        def filter_log_events(self,**kwargs):
            assert kwargs['logGroupName'].endswith(r.NAMES['endpoint'])
            self.calls+=1
            if self.calls==1:return {'events':[],'nextToken':'next'}
            raise Failure()
    result=r.logs(Client())
    assert result['status']=='error' and result['pages']==1


def test_describe_denied_is_not_absent():
    class Client:
        def describe_endpoint(self,**kwargs):raise Failure()
    with pytest.raises(Failure):r.describe(Client(),'endpoint')


def test_describe_exact_not_found_is_absent():
    class Missing(Exception):
        response={'Error':{'Code':'ValidationException','Message':r.NAMES['endpoint']+' does not exist'}}
    class Client:
        def describe_endpoint(self,**kwargs):raise Missing()
    assert r.describe(Client(),'endpoint')['status']=='absent'


def test_wrong_account_stops_before_other_calls(tmp_path):
    class STS:
        def get_caller_identity(self):return {'Account':'wrong'}
    with pytest.raises(ValueError,match='approved'):
        r.collect({'sts':STS()},tmp_path/'recovery')


def test_cloudtrail_page_cap_is_not_complete():
    class Client:
        def lookup_events(self,**kwargs):return {'Events':[event()],'NextToken':'next'}
    result=r.cloudtrail(Client(),max_pages=1,sleep=lambda _:None)
    assert result['status']=='truncated' and len(result['events'])==1


def test_collection_retains_access_gap_and_unknown_budget(tmp_path,monkeypatch):
    monkeypatch.setattr(r.a,'APPROVED_ACCOUNT_SHA256',hashlib.sha256(b'synthetic').hexdigest())
    class STS:
        def get_caller_identity(self):return {'Account':'synthetic'}
    class Denied:
        def lookup_events(self,**kwargs):raise Failure()
        def filter_log_events(self,**kwargs):raise Failure()
        def describe_endpoint(self,**kwargs):raise Failure()
        def describe_endpoint_config(self,**kwargs):raise Failure()
        def describe_model(self,**kwargs):raise Failure()
    for name in ('endpoints','quotas','prices'):
        monkeypatch.setattr(r.inventory,name,lambda *args:{'status':'complete','items':[]})
    denied=Denied()
    result=r.collect({'sts':STS(),**{name:denied for name in ('cloudtrail','logs','sagemaker','pricing','service-quotas')}},tmp_path/'record')
    assert result['status']=='incomplete'
    assert result['sections']['historical_endpoint']['status']=='error'
    assert result['sections']['cloudtrail']['failure']['response']['Error']['Code']=='AccessDeniedException'
    assert result['budget']['new_endpoint_attempts']==0
    assert result['budget']['remaining_budget']=='not_established'
    assert 'private' not in (tmp_path/'record'/'recovery.json').read_text()
