"""Durable bounded checkpoint for incomplete full-context work and frozen v3.

Never touches the original DB/runtime/large recovery trees. No model is run.
"""
import hashlib
import json
import pathlib
import tarfile


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def manifest(base,files,path,**extra):
    rows=[dict(path=p.relative_to(base).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(set(files))]
    path.write_text(json.dumps(dict(files=rows,**extra),indent=2)+'\n')
    return path


def archive(base,name,files):
    p=base/name;assert not p.exists()
    with tarfile.open(p,'w:gz',compresslevel=1) as t:
        for f in sorted(set(files)):t.add(f,arcname=f.relative_to(base).as_posix(),recursive=False)
    report=dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p))
    print(json.dumps(report),flush=True);return report


def main():
    b=pathlib.Path('/opt/frankie-box/work/family-research-20261022');audit=b/'full-context-audit'
    assert json.loads((b/'joint-models-v3/frozen_for_99_plane_audit.json').read_text())
    assert json.loads((b/'joint-inputs-v4/native_second_full_extraction_receipt.json').read_text())['coverage_gate']=='NOT_PASSED'
    large=[p for p in (audit/'indexed-payloads').iterdir() if p.is_file()]
    large += [audit/'external_history.sqlite',audit/'supplemental_lifecycle_payloads.jsonl.gz']
    large += [p for p in (b/'joint-inputs-v4').iterdir() if p.is_file()]
    large += [p for p in (b/'dipole-audit-v1').iterdir() if p.is_file() and p.suffix=='.bin']
    lm=manifest(b,large,b/'full-context-incomplete-input-manifest.json',coverage_gate='NOT_PASSED',model_matrix_built=False,model_fits_started=False)
    reports=[archive(b,'family-full-context-v4-incomplete-inputs.tar.gz',large+[lm])]
    d=b/'joint-models-v3'
    frozen=[p for p in d.rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in str(p)]
    links={p.relative_to(b).as_posix():str(p.readlink()) for p in d.rglob('*') if p.is_symlink()}
    fm=manifest(b,frozen,b/'full-context-frozen-v3-state-manifest.json',all_models_complete=False,
        symlinks_not_copied=links,input_matrix_archive='family-full-depth-inputs-v3-2d4f2553.tar.gz',
        disposition='All finished/interrupted/uncommitted states retained with original paths; no interrupted task is promoted as a completed fit.')
    reports.append(archive(b,'family-v3-frozen-model-states-and-jobs.tar.gz',frozen+[fm]))
    small=[]
    for name in ['full-context-audit','dipole-audit-v1','joint-inputs-v4']:
        d=b/name
        small += [p for p in d.iterdir() if p.is_file() and p.suffix in ['.csv','.json','.log']]
        for sub in ['brain-manifests','runtime-knowledge','scripts']:
            if (d/sub).exists():small += [p for p in (d/sub).rglob('*') if p.is_file() and '__pycache__' not in str(p)]
    small += [audit/'indexed_source_receipts.jsonl.gz',lm,fm,b/'joint-models-v3/frozen_for_99_plane_audit.json']
    sm=manifest(b,small,b/'full-context-handoff-output-manifest.json',coverage_gate='NOT_PASSED')
    reports.append(archive(b,'family-full-context-handoff-outputs.tar.gz',small+[sm]))
    receipt=dict(status='complete_incomplete-research_checkpoint',coverage_gate='NOT_PASSED',archives=reports,
        remaining='Finish source/consumer mapping and full as-of input build, then rerun all models; no v4 matrix or fit yet.')
    (b/'full-context-handoff-archive-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
