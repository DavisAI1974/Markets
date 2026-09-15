"""Preserve every result file in Git as an encrypted, bounded-part archive."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import tarfile
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--request',type=Path,required=True)
    args=parser.parse_args()
    if not args.result.is_dir():
        raise ValueError('existing result directory required')
    args.destination.mkdir(parents=True,exist_ok=False)
    # Release only this job's disposable input copy. Its exact original remains
    # in the retained local snapshot and private checksum-bound S3 archive.
    runner=Path(os.environ['RUNNER_TEMP']).resolve()
    disposable=runner/'journal-stack-input'/'bundle'/'source.sqlite'
    if not args.result.resolve().is_relative_to(runner):
        raise ValueError('result must belong to this runner')
    if disposable.is_file() and not disposable.is_symlink():
        disposable.unlink()
    request=json.loads(args.request.read_bytes())
    public=serialization.load_der_public_key(base64.b64decode(request['recipient_public_key_der_base64']))
    if not isinstance(public,rsa.RSAPublicKey):
        raise ValueError('retained RSA recipient required')
    key=os.urandom(32)
    wrapped=public.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                                          algorithm=hashes.SHA256(),label=None))
    archive=args.result.parent/'journal-stack-result.tar.gz'
    files=[]
    with tarfile.open(archive,'x:gz') as tar:
        for path in sorted(args.result.rglob('*')):
            if path.is_symlink():
                raise ValueError('result symlink refused')
            if path.is_file():
                name=path.relative_to(args.result).as_posix()
                files.append(dict(path=name,bytes=path.stat().st_size,sha256=digest(path)))
                tar.add(path,arcname='result/'+name,recursive=False)
    cipher=AESGCM(key)
    parts=[]
    with archive.open('rb') as stream:
        while chunk:=stream.read(64*1024*1024):
            index=len(parts)
            nonce=os.urandom(12)
            aad=('FRANKIE_JOURNAL_GIT_ARCHIVE_V1:'+str(index)).encode()
            encrypted=cipher.encrypt(nonce,chunk,aad)
            if cipher.decrypt(nonce,encrypted,aad)!=chunk:
                raise ValueError('encrypted archive part roundtrip differs')
            name=f'part-{index:05d}.aesgcm'
            (args.destination/name).write_bytes(encrypted)
            parts.append(dict(path=name,bytes=len(encrypted),
                sha256=hashlib.sha256(encrypted).hexdigest(),
                nonce_base64=base64.b64encode(nonce).decode(),aad=aad.decode()))
    manifest=dict(schema='FRANKIE_JOURNAL_GIT_ARCHIVE_V1',
        key_wrapping='RSA-OAEP-SHA256',encryption='AES-256-GCM',
        encrypted_key_base64=base64.b64encode(wrapped).decode(),
        recipient_public_key_sha256=hashlib.sha256(
            base64.b64decode(request['recipient_public_key_der_base64'])).hexdigest(),
        archive_sha256=digest(archive),archive_bytes=archive.stat().st_size,
        files=files,parts=parts,github_run_id=os.environ.get('GITHUB_RUN_ID'))
    (args.destination/'archive-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True))
    # Public progress and receipts carry only allowlisted metadata. The complete
    # original bytes, including checkpoint and partials on failure, are archived.
    for name in ('verification-receipt.json','verification-failure.json','progress.json'):
        source=args.result/name
        if source.is_file():
            (args.destination/name).write_bytes(source.read_bytes())
    (args.destination/'README.md').write_text(
        '# Complete journal result archive\n\n'
        'All result files are preserved in the authenticated encrypted parts listed in archive-manifest.json. '
        'Use the existing retained RSA private recipient key to unwrap the AES key with OAEP/SHA256; '
        'decrypt parts in order using their nonce and AAD, concatenate, verify archive SHA256, '
        'then extract the tar.gz. Raw market journal/checkpoint bytes and credentials are not public.\n')
    print(json.dumps(dict(phase='git_archive_ready',parts=len(parts),
          archive_bytes=archive.stat().st_size,files=len(files))),flush=True)

if __name__=='__main__':
    main()
