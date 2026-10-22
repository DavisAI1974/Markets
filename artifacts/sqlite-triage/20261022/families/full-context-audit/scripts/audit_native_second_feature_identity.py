"""Recheck all extracted native/second values with strict source-name guards.

This is an identity/collision audit, not a repeated extraction or metadata fix.
The saved component payload and all old model matrices stay unchanged.
"""
import collections
import gzip
import hashlib
import itertools
import json
import os
import pathlib
from full_context_measurements import native_measurements,second_measurements


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    inputs=base/'full-context-audit/indexed-payloads';out=base/'joint-inputs-v4'
    receipt=out/'native_second_feature_identity_audit.json';assert not receipt.exists()
    n=0;numeric=0;categorical=0;definitions={};rowhashes=hashlib.sha256()
    with gzip.open(inputs/'native.member.jsonl.gz','rt') as nf,gzip.open(inputs/'second_set.jsonl.gz','rt') as sf, \
         gzip.open(out/'native_second_full_context_values.jsonl.gz','rt') as vf:
        for nl,sl,vl in itertools.zip_longest(nf,sf,vf):
            assert nl is not None and sl is not None and vl is not None
            nw,sw,saved=map(json.loads,[nl,sl,vl]);a,b=nw['row'],sw['row']
            assert nw['source_ordinal']==saved['source_ordinal']
            assert b['key']['input_cursor']==a['frankie_emission']['input_cursor']==saved['input_cursor']
            numbers={};categories={}
            for m in [native_measurements(a),second_measurements(b,a)]:
                assert not (set(numbers)|set(categories)) & (set(m.numeric)|set(m.categories))
                numbers.update(m.numeric);categories.update(m.categories)
                for name,path in m.source_paths.items():
                    definition=(path,m.units[name],'numeric' if name in m.numeric else 'categorical')
                    if name in definitions:assert definitions[name]==definition,(name,definition,definitions[name])
                    else:definitions[name]=definition
            assert numbers==saved['numeric'] and categories==saved['categories']
            numeric+=len(numbers);categorical+=len(categories);n+=1
            rowhashes.update((nw['row_sha256']+'|'+sw['row_sha256']+'\n').encode())
            if n%1000==0:print('Revalidated normalized names, units, source paths and saved values',n,flush=True)
    assert n==6265
    report=dict(schema='NATIVE_SECOND_FEATURE_IDENTITY_AUDIT_V1',status='complete',coverage_gate='NOT_PASSED',
        unique_records=n,numeric_cells_compared=numeric,categorical_cells_compared=categorical,
        field_identities=len(definitions),source_coordinate_stream_sha256=rowhashes.hexdigest(),
        normalized_source_or_kind_collisions=0,saved_component_values_changed=False,
        code_sha256=hashlib.file_digest((base/'full-context-audit/scripts/full_context_measurements.py').open('rb'),'sha256').hexdigest(),
        limitations=['Verifies actual normalized identities, source paths, units and saved values; generic source-defined units still need semantic source-role review.',
                     'This does not establish complete field-consumer coverage, a v4 matrix, or any fitted model.'])
    receipt.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
