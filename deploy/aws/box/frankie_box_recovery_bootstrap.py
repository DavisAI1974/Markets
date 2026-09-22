import fcntl,hashlib,io,json,os,subprocess,sys,urllib.request,zipfile
from pathlib import Path
run=CONFIG['run']
if not run.isdigit():raise ValueError('invalid run identity')
base=Path('/opt/frankie-box/work')
if any(p.is_symlink() for p in (base,*base.parents)):raise ValueError('work path has symlink')
lock_path=base/'sealed-recovery-20211004.lock'
lock_fd=os.open(lock_path,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
# This parent retains the cross-run lock until the child has exited.
for process in Path('/proc').glob('[0-9]*'):
    try:args=(process/'cmdline').read_bytes().split(b'\0')
    except OSError:continue
    if any(a.endswith(b'/operations/ingest_block_sources.py') for a in args):
        raise RuntimeError('ingest still active')
    if b'research.kalshi.frankie_boss.sealed_recovery_run' in args:
        raise RuntimeError('another sealed recovery is active')
code=base/('sealed-recovery-code-'+run)
code.mkdir(exist_ok=False)
try:
    with urllib.request.urlopen(CONFIG['get'],timeout=120) as response:raw=response.read(CONFIG['bundle_bytes']+1)
except Exception:
    raise RuntimeError('code download failed; no ingest action taken') from None
if len(raw)!=CONFIG['bundle_bytes'] or hashlib.sha256(raw).hexdigest()!=CONFIG['bundle_sha256']:
    raise ValueError('code bundle identity differs')
with (code/'bundle.zip').open('xb') as stream:
    stream.write(raw);stream.flush();os.fsync(stream.fileno())
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    for info in archive.infolist():
        relative=Path(info.filename)
        if relative.is_absolute() or '..' in relative.parts or info.is_dir() or (info.external_attr>>16)&0o170000==0o120000:
            raise ValueError('unsafe archive member')
        dest=code/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(archive.read(info));stream.flush();os.fsync(stream.fileno())
private=code/'upload-map.json'
fd=os.open(private,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as stream:json.dump(CONFIG['uploads'],stream)
os.chmod(code,0o700)
env=dict(os.environ,PYTHONPATH=str(code),PYTHONDONTWRITEBYTECODE='1')
command=[sys.executable,'-m','research.kalshi.frankie_boss.sealed_recovery_run',
    '--output',str(base/('sealed-recovery-'+run)),'--boundary',str(code/'source-boundary.json'),
    '--code-commit',CONFIG['commit'],'--upload-map',str(private)]
result=subprocess.run(command,cwd=code,env=env)
raise SystemExit(result.returncode)
