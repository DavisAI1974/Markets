"""Restore the historical Sunday repository from byte-exact working-tree evidence.

This operation deliberately DOES NOT clone or check out Git content.  The failed
Sunday identity depends on literal working-tree bytes which Git cannot reproduce
for six tracked files.  A lawful historical restore therefore requires a surviving
or captured copy of the Sunday working tree, audits its raw bytes against the
161-file identity manifest, binary-copies the tracked tree and .git directory to
the original repository path, and audits the destination again before emitting a
receipt.

A clean checkout is a different teacher/runtime identity and is not accepted by
this historical-restoration operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import uuid

IDENTITY_SCHEMA = 'FRANKIE_WORKING_TREE_IDENTITY_BYTES_V1'
REQUIREMENTS_SCHEMA = 'FRANKIE_SUNDAY_WORKING_TREE_EXTERNAL_BYTES_REQUIREMENTS_V1'
RECEIPT_SCHEMA = 'FRANKIE_SUNDAY_BYTE_EXACT_WORKING_TREE_RESTORE_V1'
SUNDAY_HEAD = '050c5056c3657a954d6a3ee17f3a216999930768'
SUNDAY_IDENTITY_FILES = 161
HEX40 = re.compile(r'[0-9a-f]{40}')
HEX64 = re.compile(r'[0-9a-f]{64}')
CRITICAL_PATHS = (
    'research/kalshi/frankie_boss/c15_teacher.py',
    'research/kalshi/frankie_boss/c15_teacher_r3.py',
    'research/kalshi/frankie_boss/sunday_native_runtime.py',
    'research/kalshi/frankie_boss/feedback_cycle.py',
    'research/kalshi/frankie_boss/operations/package_final_committed.py',
    'research/kalshi/frankie_boss/operations/seal_final_prelaunch_candidate.py',
)


def _sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def _git_blob_sha(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()


def _safe_relative(value):
    if type(value) is not str or not value or '\\' in value:
        raise ValueError('portable repository-relative path required')
    path=PurePosixPath(value)
    if path.is_absolute() or any(part in ('','.','..') for part in path.parts):
        raise ValueError('unsafe repository-relative path')
    return path


def load_identity_manifest(path, *, require_sunday=True):
    raw=Path(path).read_bytes();body=json.loads(raw)
    if type(body) is not dict or body.get('schema')!=IDENTITY_SCHEMA:
        raise ValueError('reviewed Sunday working-tree identity manifest required')
    if type(body.get('repository')) is not str or not body['repository']:
        raise ValueError('identity manifest repository path required')
    if type(body.get('head')) is not str or not HEX40.fullmatch(body['head']):
        raise ValueError('identity manifest exact Git head required')
    rows=body.get('files')
    if type(rows) is not list or not rows:
        raise ValueError('identity manifest files required')
    seen={};critical=[]
    for row in rows:
        if type(row) is not dict:
            raise ValueError('identity manifest file row required')
        rel=str(_safe_relative(row.get('path')))
        if rel in seen:raise ValueError('duplicate working-tree identity path')
        if row.get('tracked') is not True or not HEX64.fullmatch(str(row.get('disk_sha256',''))):
            raise ValueError('tracked file and exact disk SHA-256 required')
        if not HEX40.fullmatch(str(row.get('git_blob',''))):
            raise ValueError('exact normalized Git blob required')
        for name in ('reproducible_by_crlf_checkout','reproducible_by_lf_checkout'):
            if type(row.get(name)) is not bool:raise ValueError('explicit checkout reproducibility required')
        seen[rel]=row
        if not row['reproducible_by_crlf_checkout'] and not row['reproducible_by_lf_checkout']:
            critical.append(rel)
    if require_sunday:
        if body['head']!=SUNDAY_HEAD or len(rows)!=SUNDAY_IDENTITY_FILES:
            raise ValueError('historical Sunday working-tree manifest identity differs')
        if tuple(critical)!=CRITICAL_PATHS:
            raise ValueError('historical unreproducible working-tree set differs')
    return body,raw


def load_requirements(path, identity, identity_raw):
    raw=Path(path).read_bytes();body=json.loads(raw)
    if type(body) is not dict or body.get('schema')!=REQUIREMENTS_SCHEMA:
        raise ValueError('reviewed external working-tree byte requirements required')
    if body.get('historical_head')!=identity['head'] or body.get('bytes_embedded') is not False:
        raise ValueError('external byte requirements historical identity differs')
    if body.get('external_byte_exact_source_required') is not True or body.get('reconstruction_from_git_forbidden') is not True:
        raise ValueError('external byte requirements must fail closed against Git reconstruction')
    if body.get('identity_manifest_git_blob')!=_git_blob_sha(identity_raw):
        raise ValueError('external byte requirements bind different identity-manifest bytes')
    expected={row['path']:row['disk_sha256'] for row in identity['files']}
    rows=body.get('files')
    if type(rows) is not list or tuple(row.get('path') for row in rows)!=CRITICAL_PATHS:
        raise ValueError('all six unreproducible working-tree byte requirements required')
    for row in rows:
        if expected.get(row['path'])!=row.get('disk_sha256'):
            raise ValueError('unreproducible working-tree SHA-256 differs from identity manifest')
    return body,raw


def _git(root,*args, text=True):
    try:return subprocess.check_output(['git',*args],cwd=root,text=text,stderr=subprocess.STDOUT)
    except (OSError,subprocess.CalledProcessError) as error:
        raise ValueError('working tree Git verification failed') from error


def _git_index(root):
    raw=_git(root,'ls-files','-s','-z',text=False);result={}
    for item in raw.split(b'\0'):
        if not item:continue
        try:header,path=item.split(b'\t',1);mode,blob,stage=header.decode().split()
        except Exception as error:raise ValueError('unexpected Git index record') from error
        rel=path.decode('utf-8')
        _safe_relative(rel)
        if stage!='0' or mode not in ('100644','100755') or not HEX40.fullmatch(blob):
            raise ValueError('historical restore supports ordinary stage-zero tracked files only')
        if rel in result:raise ValueError('duplicate Git index path')
        result[rel]=(mode,blob)
    return result


def audit_working_tree(root, identity, *, verify_git=True):
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('working-tree directory required')
    index=None;head=None
    if verify_git:
        gitdir=root/'.git'
        if gitdir.is_symlink() or not gitdir.is_dir():
            raise ValueError('self-contained .git directory required for path-preserving copy')
        head=_git(root,'rev-parse','HEAD').strip()
        if head!=identity['head']:raise ValueError('working-tree HEAD differs from historical Sunday identity')
        status=_git(root,'status','--porcelain=v1','--untracked-files=no')
        if status.strip():raise ValueError('historical tracked working tree must be Git-clean')
        index=_git_index(root)
    verified=[]
    for row in identity['files']:
        rel=str(_safe_relative(row['path']));path=root.joinpath(*PurePosixPath(rel).parts)
        if path.is_symlink() or not path.is_file():raise ValueError('identity file must be a regular file: '+rel)
        observed=_sha256_file(path)
        if observed!=row['disk_sha256']:raise ValueError('working-tree disk SHA-256 differs: '+rel)
        if index is not None:
            indexed=index.get(rel)
            if indexed is None or indexed[1]!=row['git_blob']:
                raise ValueError('working-tree normalized Git blob differs: '+rel)
        verified.append(dict(path=rel,disk_sha256=observed,git_blob=row['git_blob']))
    critical=[row for row in verified if row['path'] in CRITICAL_PATHS]
    if len(critical)!=len(CRITICAL_PATHS):raise ValueError('six unreproducible identity files were not all verified')
    return dict(root=str(root),head=head or identity['head'],identity_files_verified=len(verified),
        identity_set_sha256=hashlib.sha256(_canonical(verified)).hexdigest(),critical_files=critical)


def _tracked_paths(root):
    index=_git_index(root)
    return tuple(sorted(index))


def _same_path(left,right):
    return os.path.normcase(os.path.normpath(str(left)))==os.path.normcase(os.path.normpath(str(right)))


def copy_verified_working_tree(source, destination, identity, *, enforce_historical_path=True):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if source==destination:raise ValueError('restore source and destination must differ')
    if destination.exists():raise FileExistsError('historical restore destination must be new')
    if enforce_historical_path:
        if os.name!='nt':raise ValueError('historical Sunday repository path is Windows-bound')
        expected=Path(identity['repository']).resolve()
        if not _same_path(destination,expected):raise ValueError('restore destination differs from original Sunday repository path')
    source_audit=audit_working_tree(source,identity,verify_git=True)
    tracked=_tracked_paths(source)
    staging=destination.with_name(destination.name+'.partial-'+uuid.uuid4().hex)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if staging.exists():raise FileExistsError('unique restore staging directory already exists')
    staging.mkdir()
    try:
        shutil.copytree(source/'.git',staging/'.git',copy_function=shutil.copy2,symlinks=True)
        for rel in tracked:
            src=source.joinpath(*PurePosixPath(rel).parts)
            dst=staging.joinpath(*PurePosixPath(rel).parts)
            if src.is_symlink() or not src.is_file():
                raise ValueError('tracked restore member must be a regular file: '+rel)
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
        staging_audit=audit_working_tree(staging,identity,verify_git=True)
        if staging_audit['identity_set_sha256']!=source_audit['identity_set_sha256']:
            raise ValueError('staged working-tree bytes differ from verified source')
        os.replace(staging,destination)
    except BaseException:
        # Preserve a failed staging tree as diagnostic evidence; never silently
        # delete or retry a byte-identity failure.
        raise
    destination_audit=audit_working_tree(destination,identity,verify_git=True)
    if destination_audit['identity_set_sha256']!=source_audit['identity_set_sha256']:
        raise ValueError('final restored working-tree bytes differ from verified source')
    return dict(source=source_audit,destination=destination_audit,tracked_files_copied=len(tracked))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-manifest',required=True)
    parser.add_argument('--requirements',required=True)
    parser.add_argument('--source-working-tree',required=True)
    parser.add_argument('--destination',required=True)
    parser.add_argument('--receipt',required=True)
    args=parser.parse_args()
    identity,identity_raw=load_identity_manifest(args.identity_manifest,require_sunday=True)
    requirements,requirements_raw=load_requirements(args.requirements,identity,identity_raw)
    result=copy_verified_working_tree(args.source_working_tree,args.destination,identity,enforce_historical_path=True)
    receipt=dict(schema=RECEIPT_SCHEMA,historical_head=identity['head'],historical_repository=identity['repository'],
        identity_manifest_sha256=hashlib.sha256(identity_raw).hexdigest(),
        identity_manifest_git_blob=_git_blob_sha(identity_raw),requirements_sha256=hashlib.sha256(requirements_raw).hexdigest(),
        bytes_embedded=requirements['bytes_embedded'],external_byte_exact_source_used=True,
        reconstruction_from_git_performed=False,byte_exact_verified=True,**result)
    receipt['receipt_sha256']=hashlib.sha256(_canonical(receipt)).hexdigest()
    out=Path(args.receipt);out.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(receipt,indent=2,sort_keys=True).encode()+b'\n'
    with out.open('xb') as stream:stream.write(raw)
    print(raw.decode(),end='')
    return 0


if __name__=='__main__':raise SystemExit(main())
