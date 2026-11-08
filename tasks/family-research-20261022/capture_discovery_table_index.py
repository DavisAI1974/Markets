"""Read already-produced small ROOT tables; leave job monitoring to the heartbeat.

Transfers derived flow tables and spool references, never the bulk frame spool.
No receipt audit, producer execution, recovery or shutdown is performed here.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
OUT = HERE / 'flow-book-discovery-v1' / 'date-tables'
JOBS = [('20231002', 34955, 'skqgzuaskb6d10', 'partial'),
        ('20231003', 31686, '902unhjrkncf8c', 'full_session'),
        ('20231017', 31620, '9m9fubscvdgow5', 'partial')]
REMOTE = r'''
import base64,datetime,gzip,json,pathlib,sys
day=sys.argv[1]
control=pathlib.Path('/opt/frankie-box/replay-control')/day
root=pathlib.Path('/opt/frankie-box/work/experiment-roots')/('ng-replay-'+day)
solo=pathlib.Path('/opt/frankie-box/work/standalone-inputs')/day
def text(path):
    return path.read_text().strip() if path.is_file() else None
report={'day':day,'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'control_path':str(control),'root_path':str(root),'standalone_path':str(solo),
        'job_status':text(control/'status'),'standalone_status':text(control/'standalone-status'),
        'phase':text(root/'phase'),'tables':[],'payloads':{}}
for name in ('legacy_price','legacy_native_signed_flow','legacy_per_second_roll20',
             'legacy_book_imbalance','legacy_structure_observables'):
    path=root/'work/derived'/(name+'.json')
    if not path.is_file():
        continue
    try:
        raw=path.read_bytes()
        data=json.loads(raw)
    except (OSError,ValueError):
        report['tables'].append({'path':str(path),'state':'not_readable_yet'})
        continue
    info={'path':str(path),'bytes':len(raw),'status':data.get('status'),
          'producer':data.get('producer'),'count':data.get('count')}
    if 'per_second' in data:
        series=data['per_second']
        info.update(count=len(series),first_second=series[0]['second'],last_second=series[-1]['second'])
    if 'series' in data:
        info.update(count=len(data['series']),first_second=data['first_second'],
                    last_second=data['first_second']+len(data['series'])-1)
    for field in ('frames','groups'):
        if isinstance(data.get(field),dict) and 'attempt_path' in data[field]:
            ref=data[field]
            info['bulk_spool']={'path':str(root/ref['attempt_path']),'count':ref['count'],'bytes':ref['bytes']}
    info['local_filename']=name+'.json.gz'
    report['tables'].append(info)
    report['payloads'][info['local_filename']]=base64.b64encode(gzip.compress(raw,mtime=0)).decode()
report['standalone_files']=[{'path':str(p),'bytes':p.stat().st_size} for p in solo.glob('*') if p.is_file()]
print(json.dumps(report))
'''


def capture(job):
    day, port, pod, coverage = job
    result = subprocess.run(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6',
                             '-p', str(port), 'root@38.80.152.147', 'python3', '-', day],
                            input=REMOTE, text=True, capture_output=True, timeout=60, check=True)
    report = json.loads(result.stdout)
    report.update(pod=pod, tape_scope=coverage,
                  runtime_revision_from_handoff='6f9178bbb97721c7a71e94bb602ac256db348c87',
                  stage_disposition='interim table availability; neither full ROOT/Native completion nor scoring admission',
                  bulk_retention='Spools remain at their exact remote paths; small referenced JSON files are preserved here.')
    destination = OUT / day
    destination.mkdir(parents=True, exist_ok=True)
    for name, payload in report.pop('payloads').items():
        (destination / name).write_bytes(base64.b64decode(payload))
    (destination / 'table-index.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        for report in pool.map(capture, JOBS):
            print(report['day'], report['job_status'], len(report['tables']), 'retained small tables')
