"""Receive only the named component archive and verify every archived member."""
import hashlib
import json
import os
import pathlib
import tarfile
import urllib.request

root=pathlib.Path(__file__).resolve().parents[1]
archive=root/'external-classroom-audit-v1.tar.gz'
with urllib.request.urlopen(os.environ['FAMILY_COMPONENT_URL']) as source, archive.open('wb') as out:
    while chunk:=source.read(1048576): out.write(chunk)
assert archive.stat().st_size==11654997
assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()=='99fb865d41874f949c90090872fc6e5d1b27e219310777416c36d813b6ce8579'
with tarfile.open(archive,'r:gz') as source:
    members=source.getmembers()
    manifest=json.load(source.extractfile('external-classroom-audit-v1/component_file_manifest.json'))
    expected={r['path']:r for r in manifest['files']}
    assert {m.name for m in members}==set(expected)|{'external-classroom-audit-v1/component_file_manifest.json'}
    for member in members:
        assert member.isfile() and not pathlib.PurePosixPath(member.name).is_absolute()
        assert '..' not in pathlib.PurePosixPath(member.name).parts
        data=source.extractfile(member).read()
        if member.name in expected:
            ref=expected[member.name]
            assert len(data)==ref['bytes'] and hashlib.sha256(data).hexdigest()==ref['sha256']
        target=root/member.name
        # The source script mirror is retained separately from the working scripts.
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists(): assert target.read_bytes()==data, str(target)
        else: target.write_bytes(data)
receipt=dict(status='verified',archive_bytes=archive.stat().st_size,
             archive_sha256='99fb865d41874f949c90090872fc6e5d1b27e219310777416c36d813b6ce8579',
             files_verified=len(expected),coverage_gate='NOT_PASSED',
             s3_key='frankie/family-prebirth/20261022/external-classroom-audit-v1-99fb865d.tar.gz')
(root/'external-classroom-audit-v1/local_transport_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
