"""Publish one reviewed parallel-verification request without changing local HEAD."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).parent
REPO = 'DavisAI1974/Markets'
BRANCH = 'codex/full-frankie-boss-connection-20260915'
EXPECTED_PARENT = 'afa32cf070c3adb5ed4a96e27815cff8cd3cfc0a'
CODE = '35982ac7d42b546446038866299c23ca4fc50edc'

def api(path, value=None, method=None):
    command = ['gh','api','repos/'+REPO+'/'+path]
    if value is not None:
        command += ['--method',method or 'POST','--input','-']
    result = subprocess.run(command, input=None if value is None else json.dumps(value),
        capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

def write(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2)

def main():
    if (ROOT/'publication-intent.json').exists():
        raise ValueError('publication intent exists; reconcile before any repeat')
    ready = json.loads((ROOT/'snapshot-ready.json').read_bytes())
    pins = json.loads((ROOT/'bundle/bundle-manifest.json').read_bytes())
    code_check = json.loads((ROOT/'prepublication-code-check.json').read_bytes())
    if len(code_check['code_pins']) != 12 or not all(p['matches_committed_normalized'] for p in code_check['code_pins']):
        raise ValueError('exact source-code comparison missing')
    if hashlib.sha256((ROOT/'code/verify_snapshot.py').read_bytes()).hexdigest() != 'b71281dcf8adedadc296fe411be64cbaa7c80ee1959beabd84dd5cdabc9dc9b6':
        raise ValueError('reviewed verifier bytes changed')
    public = json.loads(Path('C:/Users/A/Documents/Codex/2026-09-15/first-run-using-agent-skills-continue/work/bootstrap-jobs/recipient-public.json').read_bytes())
    request = dict(schema='FRANKIE_GITHUB_PARALLEL_VERIFY_REQUEST_V1', code_commit=CODE,
        archive_sha256=ready['sha256'], archive_bytes=ready['bytes'],
        uncompressed_bytes=sum(pin['bytes'] for pin in pins['files'].values())+1024**2,
        bundle_manifest_sha256=ready['bundle_manifest_sha256'],
        recipient_public_key_der_base64=public['recipient_public_key_der_base64'])
    write(ROOT/'request.json', request)
    head = api('git/ref/heads/'+BRANCH)['object']['sha']
    if head != EXPECTED_PARENT:
        raise ValueError('remote branch changed; inspect before publishing')
    base = api('git/commits/'+head)
    target = 'research/kalshi/frankie_boss/operations/parallel_source/'
    pairs = [('workflow.yml','.github/workflows/frankie_parallel_source.yml'),
        ('request.json','.github/frankie-parallel-source-request.json'),
        ('cloud_transfer.py',target+'cloud_transfer.py'),
        ('upload_snapshot.py',target+'upload_snapshot.py'),
        ('prepare_snapshot.py',target+'prepare_snapshot.py'),
        ('test_cloud_transfer.py',target+'test_cloud_transfer.py'),
        ('code/verify_snapshot.py',target+'verify_snapshot.py'),
        ('code/test_verify_snapshot.py',target+'test_verify_snapshot.py'),
        ('code/README.md',target+'README.md'),
        ('PARALLEL_SOURCE_AUDIT.md','outputs/frankie-boss/20260915/PARALLEL_SOURCE_AUDIT.md'),
        ('JOURNAL_OPTIMIZATION_REVIEW.md','outputs/frankie-boss/20260915/JOURNAL_OPTIMIZATION_REVIEW.md')]
    rows = []
    witnesses = []
    for source, destination in pairs:
        raw = (ROOT/source).read_bytes()
        if len(raw) > 128*1024:
            raise ValueError('only reviewed small code and reports may be committed')
        blob = api('git/blobs', dict(content=base64.b64encode(raw).decode(), encoding='base64'))
        rows.append(dict(path=destination,mode='100644',type='blob',sha=blob['sha']))
        witnesses.append(dict(path=destination,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    tree = api('git/trees',dict(base_tree=base['tree']['sha'],tree=rows))
    commit = api('git/commits',dict(message='feat: verify exact Sunday source snapshot on parallel GitHub CPUs', tree=tree['sha'],parents=[head]))
    intent = dict(parent=head,commit=commit['sha'],code_commit=CODE,files=witnesses,request=request)
    write(ROOT/'publication-intent.json', intent)
    api('git/refs/heads/'+BRANCH,dict(sha=commit['sha'],force=False),method='PATCH')
    actual = api('git/ref/heads/'+BRANCH)['object']['sha']
    if actual != commit['sha']:
        raise ValueError('remote publication needs reconciliation')
    write(ROOT/'publication.json', dict(intent,status='published'))
    print(json.dumps(dict(status='published',commit=actual)))

if __name__ == '__main__':
    main()
