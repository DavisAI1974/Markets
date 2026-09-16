import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from research.kalshi.frankie_boss.operations.restore_sunday_working_tree_identity import (
    CRITICAL_PATHS,
    IDENTITY_SCHEMA,
    REQUIREMENTS_SCHEMA,
    _git_blob_sha,
    audit_working_tree,
    copy_verified_working_tree,
    load_identity_manifest,
    load_requirements,
)


def _run(root,*args):
    return subprocess.check_output(['git',*args],cwd=root,text=True).strip()


def _fixture(tmp_path):
    root=tmp_path/'source';root.mkdir()
    subprocess.run(['git','init','-q'],cwd=root,check=True)
    subprocess.run(['git','config','user.email','test@example.invalid'],cwd=root,check=True)
    subprocess.run(['git','config','user.name','Sunday Restore Test'],cwd=root,check=True)
    subprocess.run(['git','config','core.autocrlf','false'],cwd=root,check=True)
    originals={}
    for index,rel in enumerate(CRITICAL_PATHS):
        path=root.joinpath(*rel.split('/'));path.parent.mkdir(parents=True,exist_ok=True)
        raw=(f'critical-{index}-a\r\ncritical-{index}-b\ncritical-{index}-c\r\n').encode()
        path.write_bytes(raw);originals[rel]=raw
    subprocess.run(['git','add','.'],cwd=root,check=True)
    subprocess.run(['git','commit','-q','-m','fixture'],cwd=root,check=True)
    head=_run(root,'rev-parse','HEAD')
    index={}
    raw=subprocess.check_output(['git','ls-files','-s','-z'],cwd=root)
    for record in raw.split(b'\0'):
        if not record:continue
        header,path=record.split(b'\t',1);_,blob,_=header.decode().split();index[path.decode()]=blob
    rows=[]
    for rel in CRITICAL_PATHS:
        rows.append(dict(path=rel,disk_sha256=hashlib.sha256(originals[rel]).hexdigest(),git_blob=index[rel],
            reproducible_by_crlf_checkout=False,reproducible_by_lf_checkout=False,tracked=True))
    identity=dict(schema=IDENTITY_SCHEMA,repository=str(tmp_path/'destination'),head=head,files=rows)
    identity_path=tmp_path/'identity.json'
    identity_raw=json.dumps(identity,indent=2,sort_keys=True).encode()+b'\n';identity_path.write_bytes(identity_raw)
    requirements=dict(schema=REQUIREMENTS_SCHEMA,identity_manifest='identity.json',
        identity_manifest_git_blob=_git_blob_sha(identity_raw),historical_head=head,bytes_embedded=False,
        external_byte_exact_source_required=True,reconstruction_from_git_forbidden=True,
        files=[dict(path=row['path'],disk_sha256=row['disk_sha256'],identity_effect='test') for row in rows])
    requirements_path=tmp_path/'requirements.json';requirements_path.write_text(json.dumps(requirements),encoding='utf-8')
    return root,identity_path,requirements_path,originals


def test_binary_copy_preserves_every_unreproducible_byte(tmp_path):
    source,identity_path,requirements_path,originals=_fixture(tmp_path)
    identity,identity_raw=load_identity_manifest(identity_path,require_sunday=False)
    load_requirements(requirements_path,identity,identity_raw)
    destination=tmp_path/'restored'
    result=copy_verified_working_tree(source,destination,identity,enforce_historical_path=False)
    assert result['source']['identity_files_verified']==len(CRITICAL_PATHS)
    assert result['destination']['identity_set_sha256']==result['source']['identity_set_sha256']
    for rel,raw in originals.items():
        assert destination.joinpath(*rel.split('/')).read_bytes()==raw
    assert _run(destination,'status','--porcelain=v1','--untracked-files=no')==''


def test_line_ending_normalization_is_refused(tmp_path):
    source,identity_path,_,_=_fixture(tmp_path)
    identity,_=load_identity_manifest(identity_path,require_sunday=False)
    path=source.joinpath(*CRITICAL_PATHS[0].split('/'))
    path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
    with pytest.raises(ValueError,match='disk SHA-256 differs'):
        audit_working_tree(source,identity,verify_git=True)


def test_source_mismatch_fails_before_destination_is_created(tmp_path):
    source,identity_path,_,_=_fixture(tmp_path)
    identity,_=load_identity_manifest(identity_path,require_sunday=False)
    path=source.joinpath(*CRITICAL_PATHS[-1].split('/'));path.write_bytes(b'wrong bytes\n')
    destination=tmp_path/'never-created'
    with pytest.raises(ValueError,match='disk SHA-256 differs'):
        copy_verified_working_tree(source,destination,identity,enforce_historical_path=False)
    assert not destination.exists()


def test_requirements_cannot_substitute_another_hash(tmp_path):
    _,identity_path,requirements_path,_=_fixture(tmp_path)
    identity,identity_raw=load_identity_manifest(identity_path,require_sunday=False)
    body=json.loads(requirements_path.read_text())
    body['files'][0]['disk_sha256']='0'*64
    requirements_path.write_text(json.dumps(body),encoding='utf-8')
    with pytest.raises(ValueError,match='SHA-256 differs'):
        load_requirements(requirements_path,identity,identity_raw)


def test_production_loader_refuses_a_small_fixture_manifest(tmp_path):
    _,identity_path,_,_=_fixture(tmp_path)
    with pytest.raises(ValueError,match='historical Sunday working-tree manifest identity differs'):
        load_identity_manifest(identity_path,require_sunday=True)
