"""Read-only recovery of one historical Granite attempt. No resource mutation."""
import datetime as dt
import hashlib
from pathlib import Path
import time

try:
    from . import granite_run_artifacts as a, granite_deployment as d, sagemaker_inventory as inventory
except ImportError:
    import granite_run_artifacts as a
    import granite_deployment as d
    import sagemaker_inventory as inventory


def save(path, value):
    def normalize(item):
        if isinstance(item, dt.datetime):return {'aws_datetime_iso8601':item.isoformat()}
        if isinstance(item, dict):return {k:normalize(v) for k,v in item.items()}
        if isinstance(item, (list,tuple)):return [normalize(v) for v in item]
        return item
    a.save_receipt(path,normalize(value))

STEM = 'frankie-granite42-ci-34906771361-1'
NAMES = {'endpoint': STEM+'-endpoint', 'endpoint_config': STEM+'-config', 'model': STEM+'-model'}
START = dt.datetime(2026, 9, 14, 23, 0, tzinfo=dt.timezone.utc)
END = dt.datetime(2026, 9, 14, 23, 45, tzinfo=dt.timezone.utc)


def related(value):
    if isinstance(value, dict):return any(related(v) for v in value.values())
    if isinstance(value, list):return any(related(v) for v in value)
    return isinstance(value, str) and (value in NAMES.values() or any(value.endswith('/'+n) for n in NAMES.values()))


def cloudtrail(client, *, sleep=time.sleep, max_pages=20):
    """One source filter plus exact local resource matching; at most 1 request/s."""
    args = dict(LookupAttributes=[{'AttributeKey':'EventSource','AttributeValue':'sagemaker.amazonaws.com'}],
                StartTime=START, EndTime=END, MaxResults=50)
    events, seen, pages, excluded = [], set(), 0, 0
    for _ in range(max_pages):
        try:response=client.lookup_events(**args)
        except Exception as exc:
            return dict(status='error',events=events,pages=pages,excluded_events=excluded,failure=d.failure_evidence(exc))
        pages+=1
        for item in response['Events']:
            event=a.strict_json(item['CloudTrailEvent'])
            if (event.get('eventSource')!='sagemaker.amazonaws.com' or event.get('awsRegion')!='us-east-1'
                    or (not related(event.get('requestParameters',{})) and not related(event.get('resources',[])))):
                excluded+=1;continue
            # Omit identity/access keys, IP, user-agent and container environment.
            fields=('eventID','eventTime','eventName','eventSource','awsRegion','errorCode','errorMessage',
                    'requestID','responseElements','serviceEventDetails')
            events.append(d.sanitize_diagnostic({k:event[k] for k in fields if k in event}))
        token=response.get('NextToken')
        if not token:return dict(status='complete',events=events,pages=pages,excluded_events=excluded)
        if token in seen:return dict(status='pagination_error',events=events,pages=pages,excluded_events=excluded)
        seen.add(token);args['NextToken']=token;sleep(1)
    return dict(status='truncated',events=events,pages=pages,excluded_events=excluded)


def logs(client, *, max_pages=20):
    """Only this attempt's log group and frozen time range, with finite pages."""
    group='/aws/sagemaker/Endpoints/'+NAMES['endpoint']
    args=dict(logGroupName=group,startTime=int(START.timestamp()*1000),endTime=int(END.timestamp()*1000),limit=1000)
    events,seen=[],set()
    for page in range(max_pages):
        try:result=client.filter_log_events(**args)
        except Exception as exc:
            return dict(status='error',pages=page,events=events,failure=d.failure_evidence(exc))
        events.extend(d.sanitize_diagnostic(result.get('events',[])))
        token=result.get('nextToken')
        if not token:return dict(status='complete',pages=page+1,events=events)
        if token in seen:return dict(status='pagination_error',pages=page+1,events=events)
        seen.add(token);args['nextToken']=token
    return dict(status='truncated',pages=max_pages,events=events)


def describe(client, kind):
    name=NAMES[kind]
    key={'endpoint':'EndpointName','endpoint_config':'EndpointConfigName','model':'ModelName'}[kind]
    try:return {'status':'present','descriptor':getattr(client,'describe_'+kind)(**{key:name})}
    except Exception as exc:
        if d.missing(exc,name):return {'status':'absent','failure':d.failure_evidence(exc)}
        raise


def collect(clients, directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    identity=clients['sts'].get_caller_identity()
    if hashlib.sha256(identity['Account'].encode()).hexdigest()!=a.APPROVED_ACCOUNT_SHA256:
        raise ValueError('approved AWS account required')
    report=dict(schema='GRANITE_READ_ONLY_RECOVERY_V1',historical_run='34906771361',region='us-east-1',
                collected_at=dt.datetime.now(dt.timezone.utc),start=START,end=END,resource_names=NAMES,
                budget={'approved_attempt_compute_usd':'2.10195','approved_hourly_compute_usd':'2.8026000000',
                        'new_endpoint_attempts':0,'actual_billed_spend':'not_collected','remaining_budget':'not_established'},
                cause='unknown',sections={})
    save(directory/'recovery.json',report)
    operations=[('cloudtrail',lambda:cloudtrail(clients['cloudtrail'])),
                ('logs',lambda:logs(clients['logs'])),
                ('current_owned_endpoints',lambda:inventory.endpoints(clients['sagemaker'])),
                ('current_quota',lambda:inventory.quotas(clients['service-quotas'])),
                ('current_price',lambda:inventory.prices(clients['pricing'],'us-east-1'))]
    for kind in NAMES:
        operations.append(('historical_'+kind,lambda kind=kind:describe(clients['sagemaker'],kind)))
    for name,operation in operations:
        try:result=operation()
        except Exception as exc:result={'status':'error','failure':d.failure_evidence(exc)}
        report['sections'][name]=d.sanitize_diagnostic(result)
        save(directory/'recovery.json',report)
        print(name,result['status'],flush=True)
    # Presence/absence and errors remain distinct; no cause inferred from missing logs.
    report['status']='complete' if all(v['status'] in ('complete','present','absent') for v in report['sections'].values()) else 'incomplete'
    save(directory/'recovery.json',report)
    return report


def main():
    import argparse
    import boto3
    from botocore.config import Config
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True)
    args=parser.parse_args()
    config=Config(connect_timeout=5,read_timeout=15,retries={'total_max_attempts':1,'mode':'standard'})
    clients={name:boto3.client(name,region_name='us-east-1',config=config)
             for name in ('sts','cloudtrail','logs','sagemaker','service-quotas','pricing')}
    try:collect(clients,args.directory)
    except Exception as exc:
        save(Path(args.directory)/'collector-failure.json',d.failure_evidence(exc))
        raise SystemExit('read-only diagnostic collector failed') from None


if __name__=='__main__':main()
