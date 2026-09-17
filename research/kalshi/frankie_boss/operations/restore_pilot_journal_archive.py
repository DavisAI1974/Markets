"""Restore the existing authenticated Git journal archive into fresh runtime staging."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

COMMIT='cf20738a90e7b3bf46dea2bbf46f101f9bbaf104'
BASE='https://raw.githubusercontent.com/DavisAI1974/Markets/'+COMMIT+'/outputs/frankie-boss/20260915/reduction-stack/runs/35182872832/'
ARCHIVE_SHA='b4b2fa08b44811babcd2bcbc3111dc8a0fa34dc548abbc10ee99e2cf54c7bfc0'
JOURNAL_SHA='039c4ae8760d93ceb5f982701a48e6208f9c850dcf6cc2de388a4c03c82ea88d'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--private-key-ssm',required=True)
    parser.add_argument('--region',required=True)
    args=parser.parse_args()
    root=args.destination.resolve()
    if root.exists():
        raise ValueError('fresh restore directory required; preserve previous attempts')
    with urlopen(BASE+'archive-manifest.json') as response:
        manifest=json.loads(response.read(1024*1024))
    if manifest['archive_sha256']!=ARCHIVE_SHA:
        raise ValueError('retained archive pin differs')
    import boto3
    parameter=boto3.client('ssm',region_name=args.region).get_parameter(Name=args.private_key_ssm,WithDecryption=True)['Parameter']
    if parameter['Type'] != 'SecureString':
        raise ValueError('private recipient must be a SecureString')
    private=serialization.load_pem_private_key(parameter['Value'].encode(),password=None)
    del parameter
    public=private.public_key().public_bytes(serialization.Encoding.DER,
                                            serialization.PublicFormat.SubjectPublicKeyInfo)
    if hashlib.sha256(public).hexdigest()!=manifest['recipient_public_key_sha256']:
        raise ValueError('existing archive recipient differs')
    key=private.decrypt(base64.b64decode(manifest['encrypted_key_base64']),
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    root.mkdir(parents=True,exist_ok=False)
    archive=root/'journal-result.tar.gz'
    digest=hashlib.sha256()
    count=0
    with archive.open('xb') as out:
        for index,part in enumerate(manifest['parts']):
            if part['path']!=f'part-{index:05d}.aesgcm' or not 0 < part['bytes'] <= 64*1024*1024+16:
                raise ValueError('bounded archive part required')
            with urlopen(BASE+part['path']) as response:
                encrypted=response.read(part['bytes']+1)
            if len(encrypted)!=part['bytes'] or hashlib.sha256(encrypted).hexdigest()!=part['sha256']:
                raise ValueError('encrypted part pin differs')
            raw=AESGCM(key).decrypt(base64.b64decode(part['nonce_base64']),encrypted,part['aad'].encode())
            out.write(raw);out.flush()
            digest.update(raw);count+=len(raw)
            print(json.dumps(dict(phase='restore_existing_git_journal',parts=index+1,
                total_parts=len(manifest['parts']),percent=round(100*(index+1)/len(manifest['parts']),2))),flush=True)
    if count!=manifest['archive_bytes'] or digest.hexdigest()!=ARCHIVE_SHA:
        raise ValueError('complete archive pin differs')
    expected={'result/'+item['path']:item for item in manifest['files']}
    seen=set()
    with tarfile.open(archive,'r|gz') as tar:
        for member in tar:
            if member.name not in expected or member.name in seen or not member.isfile():
                raise ValueError('unlisted or unsafe archive member')
            item=expected[member.name]
            if member.size!=item['bytes']:
                raise ValueError('archive member size differs')
            target=(root/member.name).resolve()
            if not target.is_relative_to(root):
                raise ValueError('archive member escaped runtime staging')
            target.parent.mkdir(parents=True,exist_ok=True)
            source=tar.extractfile(member)
            file_digest=hashlib.sha256()
            with target.open('xb') as out:
                while chunk:=source.read(1024*1024):
                    out.write(chunk);file_digest.update(chunk)
            if file_digest.hexdigest()!=item['sha256']:
                raise ValueError('restored member pin differs')
            seen.add(member.name)
    if seen!=set(expected) or expected['result/journal.compact.sqlite']['sha256']!=JOURNAL_SHA:
        raise ValueError('restored file coverage differs')
    receipt=dict(schema='FRANKIE_EXISTING_GIT_JOURNAL_RESTORED_V1',commit=COMMIT,
        archive_sha256=ARCHIVE_SHA,files=len(seen),
        journal=dict(path=str(root/'result/journal.compact.sqlite'),sha256=JOURNAL_SHA,
                     bytes=expected['result/journal.compact.sqlite']['bytes']),
        source_replays=0,model_calls=0)
    (root/'restore-receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(dict(phase='existing_git_journal_restored',files=len(seen),percent=100)),flush=True)


if __name__=='__main__':
    main()
