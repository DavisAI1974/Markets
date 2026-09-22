import hashlib,json,os,sqlite3,subprocess,sys
from pathlib import Path
root=Path('/opt/frankie-box')
work=root/'work/ingest-20211004-ingest-1790057801'
p=work/'journal.compact.sqlite'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
live=[]
for d in Path('/proc').glob('[0-9]*'):
 try:
  args=(d/'cmdline').read_bytes().split(b'\0')
  if any(a.endswith(b'/operations/ingest_block_sources.py') for a in args):live.append(int(d.name))
 except OSError:pass
if live:raise RuntimeError('ingest process still active')
if any(x.is_symlink() for x in (p,*p.parents)):raise RuntimeError('symbolic link in source path')
if any(Path(str(p)+s).exists() for s in ('-wal','-shm','-journal')):raise RuntimeError('journal sidecar present')
before=p.stat()
with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as db:
 seal=db.execute('SELECT format,count,head FROM seal').fetchall()
 count=db.execute('SELECT count(*),sum(count) FROM blocks').fetchone()
print('RECOVERY_AUDIT_PROGRESS '+json.dumps(dict(phase='physical_hash',bytes=before.st_size)),flush=True)
digest=sha(p)
after=p.stat()
if any(getattr(before,k)!=getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):raise RuntimeError('container changed')
expected={"c15_builder.py":"7d30ce9601bce92bb37fad1721226b91db209b80","c15_observer.py":"e6f36bccd5f9c8b4aa2f200301798154c40f19be","c15_journal.py":"dd323e2ac423988a0b78d066071f8e8b79a30951","c15_registry.py":"1a6eab95672353f854fdcb8399b62185cc98791f","causal_prefix.py":"ca5d1db4e4d036a9079c58bea2ac14a262910c63","causal_prefix_records.py":"f792c00bbf2401072583e3e4d1266c44344addc4","causal_packet.py":"e204565411062ecca09fa593ecced7d3b59ba60d","mbo_resume_state.py":"1bea3bc2b77dcde55e91dd0e8367f05abee819d6","ng_exhaustion_mbo_v4_state_adapter_20260820.py":"1f07a786cab890b955fb1c631d10900fd5a09e06"}
for name,digest_ in expected.items():
 path=root/'markets'/'research'/name if name.startswith('ng_') else root/'markets/research/kalshi/frankie_boss'/name
 raw=path.read_bytes()
 if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=digest_:raise RuntimeError('original implementation bytes differ: '+name)
sys.path.insert(0,str(root/'markets'))
from research.kalshi.frankie_boss.c15_registry import implementation_identity
head=subprocess.run(['git','-C',str(root/'markets'),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
files=[dict(name=x.name,bytes=x.stat().st_size,sha256=sha(x)) for x in work.iterdir() if x.is_file() and x!=p and x.stat().st_size<10000000]
progress=[]
if (work/'progress.jsonl').is_file():
 for line in (work/'progress.jsonl').read_text().splitlines():
  event=json.loads(line)
  if event.get('phase') in ('start','source_verification','source_saved','complete'):progress.append(event)
sources=[dict(path=str(x),bytes=x.stat().st_size) for x in (root/'data').rglob('*.dbn.zst')]
result=dict(schema='FRANKIE_SEALED_RECOVERY_INPUT_AUDIT_V1',path=str(p),sha256=digest,bytes=after.st_size,seal=seal,boxes=count[0],journal_count=count[1],checkout=head,implementation=implementation_identity(),files=files,progress=progress,sources=sources,ingest_pids=live)
print('RECOVERY_AUDIT '+json.dumps(result,sort_keys=True),flush=True)
