"""Archive bounded research outputs; source DB/ledgers/runtime are never scanned."""
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import tarfile


def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    b=pathlib.Path('/opt/frankie-box/work/family-research-20261022')
    mode=os.environ.get('CHECKPOINT_MODE','final');assert mode in ['progress','final']
    if mode=='final':
        assert json.loads((b/'joint-models-v3/complete.json').read_text())['status']=='complete'
        assert (b/'layer-review-v3/v1_v3_comparison_receipt.json').exists()
    export=b/('full-depth-'+mode+'-export');assert not export.exists();export.mkdir()
    prefix=pathlib.Path('artifacts/sqlite-triage/20261022/families')
    files=[]
    for name in ['joint-inputs-v3','joint-models-v3','layer-review-v1','layer-review-v3','timestamped-mbo-window-v1']:
        for p in (b/name).iterdir():
            if p.is_file() and p.suffix!='.jls' and p.name!='full_depth_values.jsonl' and 'first-attempt' not in p.name:
                files.append(p)
        scripts=b/name/'scripts'
        if scripts.exists():files += [p for p in scripts.iterdir() if p.is_file() and p.suffix in ['.py','.jl','.sh']]
    for name in ['resume_receipt.json','run_core_task.jl','model_rules.jl']:
        p=b/'joint-models-v3/core-resume'/name
        if p.exists():files.append(p)
    for env in ['julia-model-env','julia-neural-env']:
        files += [b/env/n for n in ['Project.toml','Manifest.toml']]
    manifest=[]
    for src in sorted(set(files)):
        dst=export/prefix/src.relative_to(b);dst.parent.mkdir(parents=True,exist_ok=True)
        # Source CSV outputs are atomically replaced. Copy one open handle first,
        # then hash the copied snapshot, so a progress update cannot race hashes.
        shutil.copyfile(src,dst);source_hash=digest(dst);source_bytes=dst.stat().st_size
        if dst.stat().st_size>1_000_000 and dst.suffix in ['.csv','.jsonl','.log']:
            compressed=dst.with_name(dst.name+'.gz')
            with dst.open('rb') as a,gzip.open(compressed,'wb',compresslevel=1) as z:shutil.copyfileobj(a,z,8*1024*1024)
            dst.unlink();dst=compressed
        exported=[]
        if dst.stat().st_size>90_000_000:
            with dst.open('rb') as f:
                part=1
                while chunk:=f.read(64*1024*1024):
                    p=dst.with_name(dst.name+f'.part{part:03d}');p.write_bytes(chunk);exported.append(p);part+=1
            dst.unlink()
        else:exported=[dst]
        for n,p in enumerate(exported,1):
            manifest.append(dict(path=p.relative_to(export).as_posix(),bytes=p.stat().st_size,sha256=digest(p),
                source_path=src.relative_to(b).as_posix(),source_bytes=source_bytes,source_sha256=source_hash,
                transport_part=n,transport_parts=len(exported)))
    metadata={'mode':mode,'all_models_complete':mode=='final','files':manifest,
        'input_archive':'s3://bento-568968024170-us-east-2-an/frankie/family-prebirth/20261022/family-full-depth-inputs-v3-2d4f2553.tar.gz',
        'input_archive_sha256':'2d4f2553a3a98eb05b8e3f334329f71fc2a350bc547da62ed49d006bf87f7748',
        'split_files':'Concatenate .part001 onward in numeric order before gunzip; source digest applies to original source file, transport digests to each saved part.'}
    m=export/prefix/('full-depth-'+mode+'-manifest.json');m.write_text(json.dumps(metadata,indent=2)+'\n')
    archive=b/('family-full-depth-'+mode+'-results.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for p in sorted(export.rglob('*')):
            if p.is_file():t.add(p,arcname=p.relative_to(export).as_posix())
    archives=[dict(path=str(archive),bytes=archive.stat().st_size,sha256=digest(archive))]
    if mode=='final':
        states=[p for p in (b/'joint-models-v3').glob('*.jls') if not p.is_symlink()]
        state_manifest=[dict(path=p.relative_to(b).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in states]
        sm=b/'full-depth-state-manifest.json';sm.write_text(json.dumps({'files':state_manifest,'frozen_matrix_in_verified_input_archive':metadata['input_archive']},indent=2)+'\n')
        state_archive=b/'family-full-depth-v3-states.tar.gz';assert not state_archive.exists()
        with tarfile.open(state_archive,'w:gz',compresslevel=1) as t:
            for p in states+[sm]:t.add(p,arcname=p.relative_to(b).as_posix())
        archives.append(dict(path=str(state_archive),bytes=state_archive.stat().st_size,sha256=digest(state_archive)))
    receipt={'mode':mode,'saved_files':len(manifest),'archives':archives,'completed_models':mode=='final'}
    (b/('full-depth-'+mode+'-archive-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
