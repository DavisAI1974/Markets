import importlib.util, json, hashlib, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location('r', 'deploy/aws/box/frankie_box_receipts.py'); R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
work = Path(tempfile.mkdtemp()) / 'work'; (work / 'boss-jobs').mkdir(parents=True)
def job(d, name):
    (work / 'boss-jobs' / d).mkdir(); (work / 'boss-jobs' / d / 'request.json').write_text(json.dumps(dict(name=name, body_sha256='a'*64))); (work / 'boss-jobs' / d / 'outcome.json').write_text(json.dumps(dict(job_id=d, usage=dict(prompt_tokens=1, completion_tokens=1), seconds=3.0)))
job('reading0001', 'read-0000')
R.write(work); before = hashlib.sha256((work/'session-receipts.md').read_bytes()).hexdigest()
job('writing0001', 'write-analysis')                      # the first writing pass leaves its durable jobs behind
R.write(work); after = hashlib.sha256((work/'session-receipts.md').read_bytes()).hexdigest()
print('session-receipts.md sha before writing == after writing:', before == after)
