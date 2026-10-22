"""Resolve exact registry sources from a pinned Git object, never execute them.

This is a source-reading receipt, explicitly not scientific consumption proof.
"""
import collections
import hashlib
import json
import pathlib
import subprocess

REF = '2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134'


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    out = root/'full-context-audit'
    registry = json.loads((out/'canonical-99-registry.json').read_text())
    layers = [dict(group_id=g['group_id'], **e) for g in registry['groups'] for e in g['entries']]
    assert len(layers) == len({e['layer_id'] for e in layers}) == 99
    sources = sorted({p for e in layers for p in e.get('source_paths', [])})
    receipts = []
    for path in sources:
        result = subprocess.run(['git', 'cat-file', 'blob', REF+':'+path], capture_output=True)
        row = dict(source_path=path, git_ref=REF, layer_ids=[e['layer_id'] for e in layers if path in e.get('source_paths',[])],
                   scientific_consumption='pending_semantic_review_and_runtime_checks')
        if result.returncode:
            row.update(status='missing_at_pinned_ref', error=result.stderr.decode(errors='replace'))
        else:
            data = result.stdout
            dst = out/'canonical-sources'/path
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                assert dst.read_bytes() == data
            else:
                dst.write_bytes(data)
            row.update(status='bytes_recovered', bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                       saved_path=dst.relative_to(root).as_posix())
        receipts.append(row)
    report = dict(schema='CANONICAL_99_SOURCE_RECOVERY_V1', git_ref=REF, canonical_layers=99,
                  unique_sources=len(receipts), recovered=sum(r['status']=='bytes_recovered' for r in receipts),
                  source_bytes=sum(r.get('bytes',0) for r in receipts), sources=receipts,
                  coverage_gate='NOT_PASSED', limits=['File recovery and hashing do not demonstrate scientific or fitted-model consumption.'])
    (out/'canonical-source-recovery.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='sources'}))


if __name__ == '__main__':
    main()
