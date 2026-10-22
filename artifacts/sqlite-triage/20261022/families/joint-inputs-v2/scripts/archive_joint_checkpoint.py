"""Archive finite completed joint outputs and all fitted/matrix states; no source rescans."""
import pathlib,json,hashlib,gzip,shutil,tarfile
B=pathlib.Path('/opt/frankie-box/work/family-research-20261022')
P=pathlib.Path('artifacts/sqlite-triage/20261022/families')
root=B/'joint-checkpoint-export';root.mkdir(exist_ok=True)
files=[]
for name in ['joint-models-v1','joint-inputs-v2']:
 for f in (B/name).rglob('*'):
  if f.is_file() and f.suffix!='.jls':files.append((f,P/f.relative_to(B)))
for env in ['julia-model-env','julia-neural-env']:
 for n in ['Project.toml','Manifest.toml']:files.append((B/env/n,P/env/n))
manifest=[]
for src,rel in files:
 dst=root/rel;dst.parent.mkdir(parents=True,exist_ok=True)
 sha=hashlib.file_digest(src.open('rb'),'sha256').hexdigest()
 if src.stat().st_size>1000000 and src.suffix=='.csv':
  dst=dst.with_name(dst.name+'.gz')
  with src.open('rb') as a,gzip.open(dst,'wb',compresslevel=1) as z:shutil.copyfileobj(a,z,8*1024*1024)
 else:shutil.copyfile(src,dst)
 assert dst.stat().st_size<90000000,(dst,dst.stat().st_size)
 manifest.append(dict(source=str(src),path=dst.relative_to(root).as_posix(),bytes=dst.stat().st_size,sha256=hashlib.file_digest(dst.open('rb'),'sha256').hexdigest(),source_sha256=sha))
(root/P/'joint-checkpoint-manifest.json').write_text(json.dumps({'files':manifest},indent=2)+'\n')
archives=[]
r=B/'family-joint-results-checkpoint.tar.gz'
with tarfile.open(r,'w:gz',compresslevel=1) as t:
 for f in sorted(root.rglob('*')):
  if f.is_file():t.add(f,arcname=f.relative_to(root).as_posix())
archives.append(r)
states=[f for name in ['joint-models-v1','joint-inputs-v2'] for f in (B/name).rglob('*.jls')]
state_manifest=[dict(path=f.relative_to(B).as_posix(),bytes=f.stat().st_size,sha256=hashlib.file_digest(f.open('rb'),'sha256').hexdigest()) for f in states]
sm=B/'joint-state-manifest.json';sm.write_text(json.dumps({'files':state_manifest},indent=2)+'\n')
r=B/'family-joint-states-checkpoint.tar.gz'
with tarfile.open(r,'w:gz',compresslevel=1) as t:
 for f in states+[sm]:t.add(f,arcname=f.relative_to(B).as_posix())
archives.append(r)
receipt={'archives':[dict(path=str(f),bytes=f.stat().st_size,sha256=hashlib.file_digest(f.open('rb'),'sha256').hexdigest()) for f in archives],'result_files':len(files),'state_files':len(states)}
(B/'joint-checkpoint-archive-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
