"""Continue the one authorized GitHub snapshot job across chat boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).parent
REPO = 'DavisAI1974/Markets'

def write(name, value):
    with (ROOT/name).open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2)
        output.flush()
        os.fsync(output.fileno())

def main():
    write('pipeline-process.json', dict(pid=os.getpid(),started_at=time.time()))
    while not (ROOT/'snapshot-ready.json').exists():
        if (ROOT/'snapshot-failure.json').exists():
            raise ValueError('snapshot preparation failed')
        time.sleep(15)
    subprocess.run([sys.executable,'-B',str(ROOT/'publish_parallel_job.py')],check=True,cwd=ROOT)
    publication = json.loads((ROOT/'publication.json').read_bytes())
    while True:
        response = subprocess.run(['gh','api','repos/'+REPO+'/actions/runs?head_sha='+publication['commit']+'&per_page=100'],
            capture_output=True,check=True,text=True)
        runs = [run for run in json.loads(response.stdout)['workflow_runs']
            if run['head_sha'] == publication['commit']
            and run['path'] == '.github/workflows/frankie_parallel_source.yml'
            and run['event'] == 'push']
        if len(runs) > 1:
            raise ValueError('multiple matching verification runs need reconciliation')
        if runs:
            run = runs[0]
            break
        time.sleep(15)
    record = {key:run[key] for key in ('id','html_url','head_sha','path','status','conclusion','created_at')}
    write('github-run.json',record)
    print(json.dumps(record),flush=True)
    subprocess.run([sys.executable,'-B',str(ROOT/'upload_snapshot.py'),str(run['id'])],check=True,cwd=ROOT)
    write('pipeline-upload-complete.json',dict(run_id=run['id'],url=run['html_url'],at=time.time()))

if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        write('pipeline-failure.json',dict(error_type=type(error).__name__,at=time.time()))
        print('Parallel pipeline needs attention: '+type(error).__name__,flush=True)
        raise SystemExit(1) from None
