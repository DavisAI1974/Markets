"""Publish a verified data packet without pushing unrelated shallow history."""
import base64
import concurrent.futures
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request


def main(directory,branch,prefix):
    root=pathlib.Path(directory).resolve()
    repository=os.environ['GITHUB_REPOSITORY']
    token=os.environ['GH_TOKEN']
    def api(method,path,payload=None):
        data=None if payload is None else json.dumps(payload).encode()
        request=urllib.request.Request(f'https://api.github.com/repos/{repository}/{path}',data=data,method=method,
                                      headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                                               'User-Agent':'Frankie-verified-packet-publication'})
        for attempt in range(16):
            try:
                with urllib.request.urlopen(request,timeout=180) as response:
                    return None if method=='HEAD' else json.load(response)
            except urllib.error.HTTPError as exc:
                detail=exc.read().decode('utf-8',errors='replace')
                limited=exc.code==403 and ('rate limit' in detail.lower() or 'abuse' in detail.lower())
                if (exc.code not in (429,500,502,503,504) and not limited) or attempt==15:
                    print('Git API error',method,path,exc.code,detail[:1500],flush=True)
                    raise
                delay=max(5,min(60,2**attempt))
                if limited or exc.code==429:
                    delay=max(delay,int(exc.headers.get('Retry-After','60')))
                    if exc.headers.get('X-RateLimit-Remaining')=='0':
                        delay=max(delay,int(exc.headers.get('X-RateLimit-Reset','0'))-int(time.time())+5)
                print('Git API retry',exc.code,'wait seconds',delay,flush=True)
                time.sleep(delay)
    receipt=json.loads((root/'RECOVERY_RECEIPT.json').read_text())
    allowed={'FRANKIE_MBO_BOOK_RECOVERY_V1':'completed_book_fifo_recovery',
             'FRANKIE_NATIVE_LIFECYCLE_RECOVERY_V1':'complete_retained_lifecycle_ledger',
             'FRANKIE_SECOND_SET_REPLAY_V1':'complete_second_set_replay'}
    assert receipt[allowed[receipt['schema']]]
    if receipt['schema'] in ('FRANKIE_MBO_BOOK_RECOVERY_V1','FRANKIE_SECOND_SET_REPLAY_V1'):
        assert receipt['expected_trades']==receipt['recovered_trades']
    manifest=json.loads((root/'MANIFEST.json').read_text())
    for entry in manifest['files']:
        path=(root/entry['path']).resolve()
        assert path.is_relative_to(root)
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        assert digest==entry['sha256'] and path.stat().st_size==entry['bytes'],entry['path']
    head=api('GET','git/ref/heads/codex/frankie-four-day-audit-20261109')['object']['sha']
    base=api('GET','git/commits/'+head)['tree']['sha']
    files=sorted(p for p in root.rglob('*') if p.is_file())
    def blob(path):
        data=path.read_bytes()
        assert len(data)<95_000_000,path.name
        sha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        try:api('HEAD','git/blobs/'+sha)
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
            result=api('POST','git/blobs',{'encoding':'base64','content':base64.b64encode(data).decode()})
            assert result['sha']==sha
            time.sleep(1.1)
        return dict(path=path.relative_to(root).as_posix(),mode='100644',type='blob',sha=sha)
    elements=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        for i,item in enumerate(pool.map(blob,files),1):
            elements.append(item)
            if i%25==0:print('verified Git blobs',i,'of',len(files),flush=True)
    # This very large repository times out validating hundreds of new blob
    # references in one tree request. Each update retains the previous tree.
    child=None
    for offset in range(0,len(elements),40):
        payload={'tree':elements[offset:offset+40]}
        if child:payload['base_tree']=child['sha']
        child=api('POST','git/trees',payload)
        print('verified tree entries',min(offset+40,len(elements)),flush=True)
    listing=api('GET','git/trees/'+child['sha']+'?recursive=1')
    assert not listing.get('truncated')
    observed={entry['path']:entry['sha'] for entry in listing['tree'] if entry['type']=='blob'}
    assert observed=={entry['path']:entry['sha'] for entry in elements}
    tree=api('POST','git/trees',{'base_tree':base,'tree':[dict(path=prefix,mode='040000',type='tree',sha=child['sha'])]})
    commit=api('POST','git/commits',{'message':f'data: preserve verified recovered inputs for {receipt["day"]} [skip ci]',
                                  'tree':tree['sha'],'parents':[head]})
    try:api('POST','git/refs',{'ref':'refs/heads/'+branch,'sha':commit['sha']})
    except urllib.error.HTTPError:
        # A response failure can occur after the server has accepted the ref.
        assert api('GET','git/ref/heads/'+branch)['object']['sha']==commit['sha']
    verified=api('GET','git/ref/heads/'+branch)['object']['sha']
    assert verified==commit['sha']
    print(json.dumps(dict(day=receipt['day'],commit=verified,files=len(elements),prefix=prefix)),flush=True)


if __name__=='__main__':main(*sys.argv[1:4])
