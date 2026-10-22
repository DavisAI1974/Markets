"""Recover omitted saved lineage, complete episode and coverage plane payloads.

Read two exact saved projections from the producer manifest, not a recovery
directory or the multi-GB raw ledger. Emission availability is never entry time.
"""
import collections
import gzip
import hashlib
import json
import os
import pathlib
from audit_full_context_sources import Inventory


def canonical(row):
    return json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'full-context-audit';dst=out/'supplemental_lifecycle_payloads.jsonl.gz'
    assert not dst.exists()
    manifest=json.loads((out/'native_entries.json').read_text())
    root=pathlib.Path('/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1')
    existing=set()
    with gzip.open(base/'enriched-v2/lifecycle_original_rows.jsonl.gz','rt') as f:
        for line in f:
            j=json.loads(line)
            if j['row']['emitting_section'] in ['episode','lineage','detector_coverage']:
                existing.add(hashlib.sha256(canonical(j['row'])).hexdigest())
    seen=set();files=[];counts=collections.Counter();phases=collections.Counter();inventory=Inventory();duplicate_existing=0;duplicate_projection=0
    with gzip.open(dst,'wt',compresslevel=1) as output:
        for plane in ['derived_unresolved_age_chain_trajectory','prebirth_negative_opportunity_cases']:
            path=root/manifest['entries'][plane]['projected_file'];blob=path.read_bytes();digest=hashlib.sha256(blob).hexdigest()
            j=json.loads(gzip.decompress(blob));assert j['layer']==plane and j['crosswalk_commit']=='2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134'
            rows=j['lifecycle_rows'];assert len(rows)==j['lifecycle_count']==manifest['entries'][plane]['root_count']
            files.append(dict(plane=plane,path=str(path),bytes=len(blob),sha256=digest,rows=len(rows),carrier=j['carrier']))
            for ordinal,row in enumerate(rows):
                sec=row['emitting_section'];assert sec in ['lineage','episode','detector_coverage']
                content=hashlib.sha256(canonical(row)).hexdigest()
                if content in existing:duplicate_existing+=1;continue
                if content in seen:duplicate_projection+=1;continue
                seen.add(content);counts[sec]+=1;phases[(sec,row.get('emitted_on',''))]+=1
                emission=row['frankie_emission'];known=max(row.get('emitted_at_recv_ns') or 0,emission['ts_recv_ns'])
                assert isinstance(known,int) and isinstance(emission['input_cursor'],int)
                inventory.add('lifecycle.'+sec,row)
                output.write(json.dumps(dict(source_plane=plane,source_path=str(path),source_file_sha256=digest,
                    projection_row_ordinal=ordinal,canonical_row_sha256=content,known_by_ns=known,
                    input_cursor=emission['input_cursor'],instrument_id=emission['instrument_id'],row=row),separators=(',',':'))+'\n')
            print('Recovered saved lifecycle projection',plane,len(rows),flush=True)
    inventory.write(out/'supplemental_lifecycle_field_inventory.csv')
    report=dict(schema='SUPPLEMENTAL_SAVED_LIFECYCLE_PLANES_V1',status='complete',coverage_gate='NOT_PASSED',
        sources=files,new_unique_rows=dict(counts),duplicate_cached_rows=duplicate_existing,duplicate_projection_rows=duplicate_projection,
        emission_phases={'|'.join(k):v for k,v in phases.items()},field_paths=len(inventory.rows),
        limits=['Lineage entered_recv_ns/exited_recv_ns are event facts, not availability. SEGMENT_CLOSE rows are unusable before emission.',
                'Full episode stages/path outcomes must not be backfilled to their earlier starts.',
                'Source names such as unresolved/prebirth do not establish a live at-risk predictor. Actual carrier and emission determine role.',
                'Recovered rows have not yet been as-of aligned, numerically extracted or fitted.'])
    (out/'supplemental_lifecycle_recovery.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
