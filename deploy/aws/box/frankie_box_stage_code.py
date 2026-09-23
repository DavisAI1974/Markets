"""Stage exact reviewed source in a fresh inactive Linux checkout; never run it.

Git object packs contain one commit and its complete tree, without parent history.
No application credential, provider, ingestion, service-control or active-checkout action.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path('/opt/frankie-box')
CODE_PARENT = ROOT/'code'
BUCKET = 'frankie-granite42-568968024170-us-east-1'


def safe_path(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('normalized absolute path required')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink path refused')
    return path


@contextmanager
def regular(path):
    path = safe_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('regular file required')
        yield stream


def digest(path):
    with regular(path) as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sync_directory(path):
    descriptor = os.open(safe_path(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_new(path, body):
    path = safe_path(path)
    raw = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    sync_directory(path.parent)


def git(repository, *args, check=True, **kwargs):
    repository = safe_path(repository)
    gitdir = safe_path(repository/'.git')
    if gitdir.exists() and not gitdir.is_dir():
        raise ValueError('standalone Git directory required; gitdir redirection refused')
    for name in ('config','config.worktree','commondir','objects/info/alternates'):
        path = safe_path(gitdir/name)
        if name != 'config' and path.exists():
            raise ValueError('external Git metadata dependency refused')
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
               GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1')
    command = ['git','--no-optional-locks','--no-pager',
               '-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',
               '-c','core.untrackedCache=false','-c','core.autocrlf=false',
               '-c','core.attributesFile=/dev/null',
               '-C',str(repository),'--git-dir='+str(gitdir),'--work-tree='+str(repository)]
    # Config inspection itself runs no worktree/filter command and ignores include
    # files. Refuse includes and worktree config; neutralize every local filter.
    # This keeps ordinary cleanliness reads from launching fsmonitor/clean programs.
    if (gitdir/'config').exists():
        with regular(gitdir/'config'):
            pass
        settings = subprocess.run(command+['config','--local','--no-includes','--null','--list'],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        if settings.returncode:
            raise ValueError('Git configuration could not be inspected')
        for entry in settings.stdout.split(b'\0'):
            if not entry:
                continue
            config_key = entry.split(b'\n',1)[0].decode('utf-8')
            key = config_key.lower()
            if key.startswith(('include.','includeif.')) or key=='extensions.worktreeconfig':
                raise ValueError('external Git configuration refused')
            if key=='extensions.partialclone' or (key.startswith('remote.') and key.endswith('.promisor')):
                raise ValueError('partial clone dependency refused')
            if key.startswith('filter.') and key.rsplit('.',1)[-1] in ('clean','smudge','process','required'):
                command += ['-c',config_key+'='+('false' if key.endswith('.required') else '')]
    options = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    options.update(kwargs)
    result = subprocess.run(command+list(args), **options)
    if check and result.returncode:
        raise ValueError('git operation refused')
    return result


def full_commit(value):
    if not re.fullmatch('[0-9a-f]{40}', str(value)):
        raise ValueError('full commit required')
    return value


def clean_checkout(repository, commit):
    full_commit(commit)
    if git(repository,'rev-parse','HEAD').stdout.decode().strip() != commit:
        raise ValueError('checkout commit differs')
    if git(repository,'diff','--no-ext-diff','--no-textconv','--quiet','HEAD','--',
           check=False).returncode:
        raise ValueError('tracked checkout changed')
    if git(repository,'ls-files','--others').stdout:
        raise ValueError('untracked checkout files refused')
    verify_raw_checkout(repository, commit)


def tree_objects(repository, commit):
    objects = {commit, git(repository,'rev-parse',commit+'^{tree}').stdout.decode().strip()}
    count = 0
    raw = git(repository,'ls-tree','-r','-t','-z','--full-tree',commit).stdout
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, kind, identity = header.decode('ascii').split()
        path = name.decode('utf-8')
        if (path.startswith('/') or '\\' in path or
                any(part in ('', '.', '..') or part.lower()=='.git' for part in path.split('/')) or
                any(ord(c)<32 or ord(c)==127 for c in path)):
            raise ValueError('unsafe tracked path')
        if (mode,kind) not in (('040000','tree'),('100644','blob'),('100755','blob')):
            raise ValueError('tracked mode must be a regular file or tree')
        objects.add(identity)
        count += kind == 'blob'
    return objects, count


def verify_raw_checkout(repository, commit):
    """Git diff may hide EOL/encoding transforms; compare raw bytes and executable modes."""
    tree_objects(repository, commit)  # Validate names and modes before opening any tracked path.
    raw = git(repository,'ls-tree','-r','-z','--full-tree',commit).stdout
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t',1)
        mode, _, identity = header.decode('ascii').split()
        with regular(Path(repository)/name.decode('utf-8')) as stream:
            before = os.fstat(stream.fileno())
            if bool(before.st_mode & 0o111) != (mode == '100755'):
                raise ValueError('raw mode differs from reviewed tree')
            blob = hashlib.sha1(b'blob '+str(before.st_size).encode('ascii')+b'\0',
                                usedforsecurity=False)
            for block in iter(lambda: stream.read(1024*1024), b''):
                blob.update(block)
            after = os.fstat(stream.fileno())
            if ((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) !=
                    (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) or
                    blob.hexdigest() != identity):
                raise ValueError('raw blob differs from reviewed tree')


def create_pack(repository, commit, destination):
    """CI producer: one exact commit plus tree/blobs, never .git config or history."""
    repository = safe_path(repository)
    clean_checkout(repository, commit)
    objects, count = tree_objects(repository, commit)
    destination = safe_path(destination)
    if destination.is_relative_to(repository):
        raise ValueError('source pack must be outside checkout')
    with destination.open('xb') as stream:
        git(repository,'pack-objects','--stdout','--no-reuse-delta','--compression=1',
            input=('\n'.join(sorted(objects))+'\n').encode('ascii'), stdout=stream)
        stream.flush(); os.fsync(stream.fileno())
    sync_directory(destination.parent)
    return dict(schema='FRANKIE_SOURCE_PACK_V1',commit=commit,files=count,
                bytes=destination.stat().st_size,sha256=digest(destination))


def import_pack(pack, target, commit, checksum):
    target.mkdir(mode=0o700)
    git(target,'init','--quiet','--template=')
    with regular(pack) as stream:
        before = os.fstat(stream.fileno())
        if hashlib.file_digest(stream,'sha256').hexdigest() != checksum:
            raise ValueError('source pack hash changed')
        stream.seek(0)
        git(target,'index-pack','--stdin',stdin=stream)
        after = os.fstat(stream.fileno())
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) != (
                after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('source pack changed during import')
    # This deliberately shallow repository has no missing-parent dependency.
    with (target/'.git'/'shallow').open('x',encoding='ascii') as stream:
        stream.write(commit+'\n'); stream.flush(); os.fsync(stream.fileno())
    if git(target,'cat-file','-t',commit).stdout != b'commit\n':
        raise ValueError('pack lacks the reviewed commit')
    expected, count = tree_objects(target,commit)
    actual = {line.split()[0].decode('ascii') for line in
              git(target,'cat-file','--batch-all-objects','--batch-check').stdout.splitlines()}
    if actual != expected:
        raise ValueError('pack contains objects outside reviewed commit tree')
    git(target,'fsck','--full','--strict')
    git(target,'checkout','--quiet','--detach',commit)
    clean_checkout(target,commit)
    return count


def sync_tree(root):
    for parent, directories, files in os.walk(root, followlinks=False):
        parent = safe_path(parent)
        for name in directories:
            safe_path(parent/name)
        for name in files:
            with regular(parent/name) as stream:
                os.fsync(stream.fileno())
        sync_directory(parent)


def stage(pack, checksum, commit, run_id):
    if not sys.platform.startswith('linux'):
        raise ValueError('Linux staging only')
    full_commit(commit)
    if not re.fullmatch('[A-Za-z0-9_-]{1,96}', str(run_id)):
        raise ValueError('bare unique run id required')
    if not re.fullmatch('[0-9a-f]{64}',str(checksum)) or digest(pack) != checksum:
        raise ValueError('source pack hash differs')
    parent = safe_path(CODE_PARENT)
    root = safe_path(parent/(commit+'-'+run_id))
    if root.exists():
        raise FileExistsError('existing staging evidence retained')
    parent.mkdir(parents=True,exist_ok=True)
    root.mkdir(mode=0o700)
    sync_directory(parent)
    target = root/'markets'
    intent = root/'staging-intent.json'
    save_new(intent,dict(schema='FRANKIE_INACTIVE_CODE_STAGING_INTENT_V1',
                        commit=commit,code_root=str(target),pack_sha256=checksum,
                        pack_bytes=Path(pack).stat().st_size,run_id=run_id))
    count = import_pack(pack,target,commit,checksum)
    sync_tree(target)
    receipt = dict(schema='FRANKIE_INACTIVE_CODE_STAGING_RECEIPT_V1',
                   status='staged',commit=commit,code_root=str(target),
                   pack_sha256=checksum,files=count,intent_sha256=digest(intent),
                   active_checkout_changed=False,model_calls=0,source_replays=0)
    save_new(root/'staging-receipt.json',receipt)
    return receipt


def service_state():
    result = subprocess.run(['systemctl','list-units','--type=service',
        '--state=active,activating,deactivating','--no-legend','--plain',
        'frankie-cycle-*.service','frankie-heartbeat-*.service','frankie-correction-*.service'],
        capture_output=True,text=True,check=False)
    if result.returncode:
        raise ValueError('service state unavailable')
    # Unit names and states only; descriptions may contain incidental private data.
    return [dict(unit=fields[0],load=fields[1],active=fields[2],sub=fields[3])
            for line in result.stdout.splitlines() if len(fields:=line.split())>=4]


def path_metadata(path):
    path=safe_path(path)
    if not path.exists():
        return dict(path=str(path),exists=False)
    info=path.stat()
    return dict(path=str(path),exists=True,bytes=info.st_size,
                kind='directory' if stat.S_ISDIR(info.st_mode) else 'file',
                device=info.st_dev,inode=info.st_ino)


def inventory():
    root=safe_path(ROOT)
    checkout=root/'markets'
    report=dict(schema='FRANKIE_INACTIVE_CODE_INVENTORY_V1',
                root=path_metadata(root),code_parent=path_metadata(CODE_PARENT),
                model_calls=0,source_replays=0,application_writes=0)
    if checkout.is_dir():
        report['checkout']=dict(commit=git(checkout,'rev-parse','HEAD').stdout.decode().strip(),
            tracked_dirty=bool(git(checkout,'diff','--no-ext-diff','--no-textconv',
                                   '--quiet','HEAD','--',check=False).returncode),
            untracked=bool(git(checkout,'ls-files','--others').stdout))
    else:
        report['checkout']=dict(present=False)
    try:
        report['active_units']=service_state()
    except (OSError,ValueError):
        report['service_state']='unavailable'
    if root.exists():
        disk=os.statvfs(root)
        report['available_bytes']=disk.f_bavail*disk.f_frsize
    report['original_container']=path_metadata(root/'work/ingest-20211004-ingest-1790057801/journal.compact.sqlite')
    report['recovery_directory']=path_metadata(root/'work/sealed-recovery-35796793428')
    versions={}
    # Metadata text only: never execute an installed distribution or repository import.
    for path in sorted((root/'venv/lib').glob('python*/site-packages/*.dist-info/METADATA')):
        with regular(path) as stream:
            headers=stream.read(8192).decode('utf-8',errors='strict').split('\n\n',1)[0]
        fields=dict(line.split(': ',1) for line in headers.splitlines() if ': ' in line)
        if fields.get('Name','').lower() in {'torch','numpy','boto3','zstandard','cffi','databento-dbn'}:
            versions[fields['Name']]=fields.get('Version')
    report['distributions']=versions
    return report


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('download redirect refused')


def checked_url(value):
    url=urllib.parse.urlsplit(value)
    if (url.scheme!='https' or url.netloc!=BUCKET+'.s3.us-east-1.amazonaws.com'
            or url.fragment or not re.fullmatch('/[A-Za-z0-9_./-]{1,1000}',url.path)
            or any(part in ('','.', '..') for part in url.path[1:].split('/'))):
        raise ValueError('unsafe download capability')
    return value


def open_url(url):
    return urllib.request.build_opener(NoRedirect()).open(checked_url(url),timeout=120)


def download(url,destination,size,checksum):
    if type(size) is not int or size<1 or not re.fullmatch('[0-9a-f]{64}',str(checksum)):
        raise ValueError('complete source pack pin required')
    destination=safe_path(destination)
    hashed=hashlib.sha256(); count=0
    with destination.open('xb') as output:
        with open_url(url) as response:
            while chunk:=response.read(min(1<<20,size-count+1)):
                count+=len(chunk)
                output.write(chunk); hashed.update(chunk)
                if count>size:
                    output.flush(); os.fsync(output.fileno())
                    raise ValueError('download exceeds pinned size')
        output.flush(); os.fsync(output.fileno())
    sync_directory(destination.parent)
    if count!=size or hashed.hexdigest()!=checksum:
        raise ValueError('download bytes or hash differ')


def stage_from_map(commit,run_id,checksum,size,map_url):
    full_commit(commit)
    if not re.fullmatch('[A-Za-z0-9_-]{1,96}',str(run_id)):
        raise ValueError('bare unique run id required')
    with open_url(map_url) as response:
        raw=response.read(1<<20)
        if response.read(1):
            raise ValueError('upload map exceeds limit')
    mapping=json.loads(raw)
    if type(mapping) is not dict or set(mapping)!={'source.pack'}:
        raise ValueError('one explicit source pack capability required')
    pin=mapping['source.pack']
    if (type(pin) is not dict or pin.get('sha256')!=checksum or pin.get('bytes')!=size
            or pin.get('commit')!=commit):
        raise ValueError('source capability differs from dispatched pin')
    checked_url(pin['url'])
    parent=safe_path(CODE_PARENT)
    transfer=safe_path(parent/('transfer-'+commit+'-'+run_id))
    parent.mkdir(parents=True,exist_ok=True)
    transfer.mkdir(mode=0o700)
    sync_directory(parent)
    save_new(transfer/'transfer-intent.json',
             dict(schema='FRANKIE_SOURCE_TRANSFER_INTENT_V1',commit=commit,
                  bytes=size,sha256=checksum,run_id=run_id))
    pack=transfer/'source.pack'
    download(pin['url'],pack,size,checksum)
    return stage(pack,checksum,commit,run_id)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    inv=commands.add_parser('inventory')
    inv.add_argument('--commit',required=True)
    build=commands.add_parser('pack')
    build.add_argument('--repository',required=True); build.add_argument('--commit',required=True)
    build.add_argument('--output',required=True)
    action=commands.add_parser('stage')
    action.add_argument('--commit',required=True); action.add_argument('--run-id',required=True)
    action.add_argument('--pack-sha256',required=True); action.add_argument('--pack-bytes',required=True,type=int)
    args=parser.parse_args()
    try:
        if args.action=='inventory':
            full_commit(args.commit)
            result=inventory()
            result['dispatched_commit']=args.commit
        elif args.action=='pack':
            result=create_pack(args.repository,args.commit,args.output)
        else:
            result=stage_from_map(args.commit,args.run_id,args.pack_sha256,
                                  args.pack_bytes,os.environ['MAP_URL'])
    except Exception as error:
        print(json.dumps(dict(status='refused',error_type=type(error).__name__)),flush=True)
        if args.action=='pack':
            # CI redirects pack stdout into the pin file; the reason must reach the log.
            # Pack handles no capability URL, so its refusal text is safe to print.
            print('pack refused: '+type(error).__name__+': '+str(error),file=sys.stderr,flush=True)
        return 1
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
