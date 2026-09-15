"""Publish completed Sunday prefixes as encrypted exact page references in Git.

Each prefix's bytes are reproducible from the already archived compact journal
plus this small authenticated patch. No raw market data or private key is public.
The publisher retains runtime prefixes because the Sunday host still needs them.
"""
import argparse
import base64
import gzip
import hashlib
import json
import mmap
import os
from pathlib import Path
import subprocess
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPO='DavisAI1974/Markets'
BRANCH='codex/journal-reduction-stack-20260915'
BASE_SHA='19603159548b1e443a3565f8c999543981c43c23c80fd511c11e760f633b260f'
BASE_COMMIT='fb2e988c9c55b84db497047a173e4db990f6d709'
PAGE=4096


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def api(path, payload=None):
    command=['gh','api','repos/'+REPO+'/'+path]
    if payload is not None:
        command+=['--method','POST','--input','-']
    result=subprocess.run(command,input=None if payload is None else json.dumps(payload).encode(),
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('Git archive API operation failed: '+path.split('?')[0])
    return json.loads(result.stdout)


def decode_pages(value, base):
    if value['schema']!='FRANKIE_EXACT_PREFIX_PAGE_REFERENCES_V1' or value['base_sha256']!=BASE_SHA:
        raise ValueError('page reference schema or base differs')
    for item in value['pages']:
        if type(item) is int:
            if not 0 <= item < len(base)//PAGE:
                raise ValueError('invalid base page index')
            yield base[item*PAGE:(item+1)*PAGE]
        elif type(item) is str:
            page=base64.b64decode(item,validate=True)
            if not 0 < len(page) <= PAGE: raise ValueError('invalid literal page')
            yield page
        else:
            raise ValueError('invalid page reference')


def make_patch(target, expected_sha, base, index):
    pages=[]
    source_digest=hashlib.sha256()
    with target.open('rb') as stream:
        while page:=stream.read(PAGE):
            source_digest.update(page)
            match=index.get(sha(page)) if len(page)==PAGE else None
            if match is not None and base[match*PAGE:(match+1)*PAGE]==page:
                pages.append(match)
            else:
                pages.append(base64.b64encode(page).decode())
    if source_digest.hexdigest()!=expected_sha:
        raise ValueError('completed prefix changed before archiving')
    value=dict(schema='FRANKIE_EXACT_PREFIX_PAGE_REFERENCES_V1',base_sha256=BASE_SHA,
        base_archive_commit=BASE_COMMIT,page_bytes=PAGE,target_bytes=target.stat().st_size,
        target_sha256=expected_sha,pages=pages)
    # Independently decode the actual archive representation before publication.
    encoded=gzip.compress(json.dumps(value,separators=(',',':')).encode())
    decoded=json.loads(gzip.decompress(encoded))
    digest=hashlib.sha256();size=0
    for page in decode_pages(decoded,base):
        digest.update(page);size+=len(page)
    if digest.hexdigest()!=expected_sha or size!=value['target_bytes']:
        raise ValueError('exact prefix archive reconstruction differs')
    return encoded


def publish(files, destination, state):
    if state.exists():
        record=json.loads(state.read_bytes())
        commit=record['commit']
        # Lost update acknowledgement is resolved against the exact committed files.
        remote=api('git/ref/heads/'+BRANCH)['object']['sha']
        if remote==commit or api('compare/'+commit+'...'+remote)['status'] in ('ahead','identical'):
            return commit
        raise ValueError('prior archive publication needs review')
    remote=api('git/ref/heads/'+BRANCH)['object']['sha']
    tree=api('git/commits/'+remote)['tree']['sha']
    entries=[]
    for name,raw in files.items():
        blob=api('git/blobs',dict(content=base64.b64encode(raw).decode(),encoding='base64'))
        expected_blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\x00'+raw).hexdigest()
        if blob['sha']!=expected_blob: raise ValueError('Git blob readback identity differs')
        entries.append(dict(path=destination+'/'+name,mode='100644',type='blob',sha=blob['sha']))
    new_tree=api('git/trees',dict(base_tree=tree,tree=entries))['sha']
    commit=api('git/commits',dict(message='archive: preserve completed compact Sunday prefix [skip ci]',
                                 tree=new_tree,parents=[remote]))['sha']
    with state.open('x') as stream:
        json.dump(dict(commit=commit,parent=remote,destination=destination),stream)
        stream.flush();os.fsync(stream.fileno())
    # The Git ref update is fast-forward only; an unrelated branch change is preserved.
    command=['gh','api','repos/'+REPO+'/git/refs/heads/'+BRANCH,
             '--method','PATCH','--input','-']
    result=subprocess.run(command,input=json.dumps(dict(sha=commit,force=False)).encode(),
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('archive ref update requires inspection; commit and local files retained')
    if api('git/ref/heads/'+BRANCH)['object']['sha']!=commit:
        raise RuntimeError('archive publication acknowledgement needs inspection')
    return commit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--prefixes',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--recipient-public',type=Path,required=True)
    parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    if file_sha(args.base)!=BASE_SHA: raise ValueError('restored base pin differs')
    public_value=json.loads(args.recipient_public.read_bytes())
    public_der=base64.b64decode(public_value['recipient_public_key_der_base64'])
    public=serialization.load_der_public_key(public_der)
    args.output.mkdir(parents=True,exist_ok=False)
    completed=set()
    with args.base.open('rb') as stream, mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as base:
        index={sha(base[offset:offset+PAGE]):offset//PAGE for offset in range(0,len(base)-PAGE+1,PAGE)}
        while True:
            for cycle in range(1,19):
                if cycle in completed: continue
                witness=args.prefixes/f'prefix-{cycle:02d}-witness.json'
                if not witness.is_file(): continue
                files=json.loads(witness.read_bytes())
                target=Path(files['snapshot']['path'])
                patch=make_patch(target,files['snapshot']['sha256'],base,index)
                originals={}
                for path in (witness,Path(files['receipt']['path']),
                             args.prefixes/f'prefix-{cycle:02d}-packet-seed.json'):
                    originals[path.name]=base64.b64encode(path.read_bytes()).decode()
                if sha(base64.b64decode(originals[Path(files['receipt']['path']).name]))!=files['receipt']['sha256']:
                    raise ValueError('prefix receipt changed before publication')
                plaintext=gzip.compress(json.dumps(dict(schema='FRANKIE_PREFIX_ARCHIVE_V1',
                    prefix_patch_base64=base64.b64encode(patch).decode(),
                    original_files_base64=originals),separators=(',',':')).encode())
                key=os.urandom(32);nonce=os.urandom(12)
                aad=f'FRANKIE_PREFIX_ARCHIVE_V1:{cycle}'.encode()
                ciphertext=AESGCM(key).encrypt(nonce,plaintext,aad)
                if AESGCM(key).decrypt(nonce,ciphertext,aad)!=plaintext:
                    raise ValueError('encrypted prefix archive roundtrip differs')
                if len(ciphertext)>64*1024*1024:
                    raise ValueError('prefix delta exceeds bounded Git blob; preserve runtime for review')
                wrapped=public.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                    algorithm=hashes.SHA256(),label=None))
                manifest=dict(schema='FRANKIE_ENCRYPTED_PREFIX_ARCHIVE_V1',cycle_index=cycle,
                    base_archive_commit=BASE_COMMIT,base_sha256=BASE_SHA,
                    target_sha256=files['snapshot']['sha256'],target_bytes=target.stat().st_size,
                    ciphertext_sha256=sha(ciphertext),ciphertext_bytes=len(ciphertext),
                    nonce_base64=base64.b64encode(nonce).decode(),aad=aad.decode(),
                    encrypted_key_base64=base64.b64encode(wrapped).decode(),
                    recipient_public_key_sha256=sha(public_der),encryption='AES-256-GCM',
                    key_wrapping='RSA-OAEP-SHA256',exact_reconstruction_verified=True)
                folder=args.output/f'cycle-{cycle:02d}'
                folder.mkdir(exist_ok=False)
                payloads={'prefix.aesgcm':ciphertext,'manifest.json':json.dumps(manifest,indent=2).encode()}
                for name,raw in payloads.items(): (folder/name).write_bytes(raw)
                destination=f'outputs/frankie-boss/20260915/compact-sunday-prefixes/cycle-{cycle:02d}'
                commit=publish(payloads,destination,folder/'publication.json')
                completed.add(cycle)
                print(json.dumps(dict(phase='completed_prefix_preserved_in_git',cycle_index=cycle,
                    archive_bytes=len(ciphertext),runtime_prefix_bytes=target.stat().st_size,
                    commit=commit)),flush=True)
            if len(completed)==18 or not args.watch: break
            time.sleep(10)


if __name__=='__main__':
    main()
