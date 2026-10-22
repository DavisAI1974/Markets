"""Recover actual manifested brain documents and claims without giant rescans.

Large calculation/classroom representations remain pinned to their indexed
carriers. Reading a manifest is never marked as consuming its large payload.
"""
import hashlib
import json
import os
import pathlib
import shutil


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    audit=base/'full-context-audit';out=audit/'runtime-knowledge';out.mkdir(exist_ok=True)
    manifests=json.loads((audit/'brain_manifest_inventory.json').read_text());receipts=[]
    for m in manifests:
        parent=pathlib.Path(m['path']).parent
        for e in m.get('entries',[]):
            p=parent/e['name'];row=dict(manifest=m['path'],manifest_day=m.get('day'),**e)
            if p.is_file() and p.stat().st_size<=10_000_000:
                data=p.read_bytes();h=hashlib.sha256(data).hexdigest()
                if len(data)!=e['bytes'] or h!=e['sha256']:
                    row.update(recovery='different_current_version',actual_path=str(p),actual_sha256=h,actual_bytes=len(data))
                    row['scientific_consumption']='pending_exact_historical_version_resolution'
                    receipts.append(row)
                    continue
                dst=out/parent.name/(h+'--'+p.name);dst.parent.mkdir(exist_ok=True)
                if dst.exists():assert dst.read_bytes()==data
                else:dst.write_bytes(data)
                row.update(recovery='complete_payload_verified',actual_path=str(p),saved_path=str(dst),actual_sha256=h)
            elif p.is_file():
                row.update(recovery='large_payload_pinned_not_read_by_this_collector',actual_path=str(p),actual_bytes=p.stat().st_size)
            else:
                row.update(recovery='manifested_copy_unavailable',actual_path=str(p))
            row['scientific_consumption']='pending_semantic_review_or_source_bound_check'
            receipts.append(row)
    native=pathlib.Path('/opt/frankie-box/brain/20231018-cycle-00/classroom-findings.json')
    external=pathlib.Path('/opt/frankie-box/brain/20231018-cycle-00/classroom-external-findings.json')
    n=json.loads(native.read_text());x=json.loads(external.read_text())['findings']
    assert len({r['finding_id'] for r in n})==len(n)
    assert len({r['finding_id'] for r in x})==len(x)
    (out/'native_classroom_claims.json').write_text(json.dumps(n,indent=2)+'\n')
    (out/'external_classroom_claims.json').write_text(json.dumps(x,indent=2)+'\n')
    report=dict(schema='ACTUAL_RUNTIME_KNOWLEDGE_RECOVERY_V1',status='complete',coverage_gate='NOT_PASSED',
        native_claims=len(n),external_claims=len(x),entries=receipts,
        limits=['Large digest/classroom bytes are not declared consumed by reading their manifests.',
                'Target-day learning and later historical claims are hypotheses/reference evidence, not pre-start predictive inputs.',
                'Retained/superseded, excluded and unverified roles stay explicit.'])
    (audit/'runtime_knowledge_recovery.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(native_claims=len(n),external_claims=len(x),entry_recovery_counts={v:sum(r['recovery']==v for r in receipts) for v in sorted({r['recovery'] for r in receipts})})))


if __name__=='__main__':main()
