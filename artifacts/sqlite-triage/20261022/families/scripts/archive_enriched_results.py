"""Archive actual completed results, preserving the prior input bundle unchanged."""
import gzip,hashlib,json,pathlib,shutil,tarfile
BASE=pathlib.Path('/opt/frankie-box/work/family-research-20261022')
root=BASE/'enriched-results-export';root.mkdir(exist_ok=True)
prefix=pathlib.Path('artifacts/sqlite-triage/20261022/families')
oldstats='samples elapsed_windows direction_summary feature_availability exploratory_associations prestart_feature_changes prestart_nearby_feature_pairs prestart_nearby_feature_summary root_native_prestart_changes root_native_prestart_change_summary root_native_nearby_change_summary external_pre120_changes direction_freshness_sensitivity prior_price_diagnostics feature_phase_availability all_second_set_component_dispositions plane_disposition_summary nearby_price_pairs nearby_price_summary overlap_counts overlap_summary association_stability'.split()
files=[]
for name in oldstats:files.append((BASE/'descriptive-v1'/(name+'.csv'),prefix/'descriptive-v1'/(name+'.csv')))
for name in ['analysis_receipt.json','run_receipt.json','revised-run.log','revised-summary.log','revised-changes.log','revised-report.log']:
    files.append((BASE/'descriptive-v1'/name,prefix/'descriptive-v1'/name))
for f in (BASE/'enriched-v2').iterdir():
    if f.is_file() and not f.is_symlink() and f.name not in ['added_context_measurements.csv','analysis_status.json']:
        files.append((f,prefix/'enriched-v2'/f.name))
manifest=[]
for source,rel in files:
    dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    digest=hashlib.file_digest(source.open('rb'),'sha256').hexdigest()
    if source.stat().st_size>1_000_000 and source.suffix in ['.csv','.jsonl']:
        dest=dest.with_name(dest.name+'.gz')
        with source.open('rb') as a,gzip.open(dest,'wb',compresslevel=1) as b:shutil.copyfileobj(a,b,8*1024*1024)
    else:shutil.copyfile(source,dest)
    outdigest=hashlib.file_digest(dest.open('rb'),'sha256').hexdigest()
    parts=[]
    if dest.stat().st_size>90_000_000:
        with dest.open('rb') as f:
            i=1
            while data:=f.read(80_000_000):
                part=dest.with_name(dest.name+f'.part{i:03}');part.write_bytes(data)
                parts.append(dict(path=str(part.relative_to(root)).replace('\\','/'),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()));i+=1
        dest.unlink()
    manifest.append(dict(source_path=str(source),source_bytes=source.stat().st_size,source_sha256=digest,
                         saved_path=str(dest.relative_to(root)).replace('\\','/'),saved_sha256=outdigest,parts=parts))
(root/prefix/'enriched-v2/result_manifest.json').write_text(json.dumps(dict(files=manifest,input_bundle_sha256='3600071f33d6198c108e7e07ff7b1d08f804f1661732e2970c27203afdefba77',policy='Baseline and enriched actual outputs. Frozen baseline input symlinks refer to the preserved input bundle and repository. Concatenate any numbered parts in order before decompression.'),indent=2)+'\n')
archive=BASE/'family-enriched-descriptive-v2.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=1) as t:
    for f in sorted(root.rglob('*')):
        if f.is_file():t.add(f,arcname=str(f.relative_to(root)))
receipt=dict(path=str(archive),bytes=archive.stat().st_size,sha256=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),saved_files=len(manifest))
(BASE/'enriched-results-archive-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
