"""Download exact component archives; stream-verify all members without DB extraction."""
import hashlib
import json
import os
import pathlib
import tarfile
import urllib.request


def main():
    root=pathlib.Path(__file__).resolve().parents[1]
    archive_dir=root.parents[4]/'family-continuation-archives'
    archive_dir.mkdir(exist_ok=True)
    specs=json.loads(os.environ['FAMILY_ARCHIVE_TRANSPORT_SPECS'])
    folder=root/'continuation-archives-v1';folder.mkdir(exist_ok=True)
    receipt_file=folder/'local_transport_receipts.json'
    receipts=json.loads(receipt_file.read_text()) if receipt_file.exists() else []
    for spec in specs:
        target=archive_dir/(spec['name']+'.tar.gz')
        if not target.exists():
            partial=target.with_suffix('.partial');assert not partial.exists()
            with urllib.request.urlopen(spec['url'],timeout=900) as source,partial.open('wb') as output:
                while chunk:=source.read(4*1048576):output.write(chunk)
            partial.rename(target)
        assert target.stat().st_size==spec['bytes']
        assert hashlib.file_digest(target.open('rb'),'sha256').hexdigest()==spec['sha']
        verified={};expected=None
        with tarfile.open(target,'r|gz') as source:
            for member in source:
                path=pathlib.PurePosixPath(member.name)
                assert member.isfile() and not path.is_absolute() and '..' not in path.parts
                handle=source.extractfile(member)
                if member.name=='manifest.json':expected=json.load(handle)['files'];continue
                digest=hashlib.sha256();size=0;small=[]
                retain=member.size<12_000_000 and '.sqlite' not in member.name and not member.name.endswith('.tar.gz')
                while chunk:=handle.read(4*1048576):
                    digest.update(chunk);size+=len(chunk)
                    if retain:small.append(chunk)
                assert size==member.size
                verified[member.name]=dict(bytes=size,sha256=digest.hexdigest())
                if retain:
                    dest=root.joinpath(*path.parts);dest.parent.mkdir(parents=True,exist_ok=True)
                    data=b''.join(small)
                    if dest.exists():assert dest.read_bytes()==data,str(dest)
                    else:dest.write_bytes(data)
        if expected is not None:
            assert set(verified)=={r['path'] for r in expected}
            for r in expected:assert verified[r['path']]=={k:r[k] for k in ['bytes','sha256']},r['path']
        receipt={k:v for k,v in spec.items() if k!='url'}
        receipt.update(status='verified',local_archive=str(target),member_files_verified=len(verified),manifest_verified=expected is not None,coverage_gate='NOT_PASSED')
        receipts=[r for r in receipts if r['name']!=spec['name']]+[receipt];print(json.dumps(receipt),flush=True)
        receipt_file.write_text(json.dumps(receipts,indent=2)+'\n')


if __name__=='__main__':main()
