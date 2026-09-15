"""Emit a separately pinned closed-source ancestry sidecar without source replay."""
import hashlib
import json
from pathlib import Path
import sqlite3


def sha256(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def _same(left,right):return Path(left).resolve()==Path(right).resolve()


def build_closed_lineage(final_source_path,ingestion_receipt,*,expected_ingestion_sha256,links):
    final_source_path=Path(final_source_path)
    if (final_source_path.parent/'failure.json').exists():
        raise ValueError('final source failure forbids lineage publication')
    if sha256(ingestion_receipt)!=expected_ingestion_sha256:
        raise ValueError('final ingestion receipt pin mismatch')
    ingestion=json.loads(Path(ingestion_receipt).read_bytes())
    if not links:raise ValueError('explicit recovery lineage required')
    expected_child=final_source_path
    output=[]
    seen=set()
    for index,link in enumerate(links):
        receipt_pin=link['recovery_receipt'];parent=link['closed_parent']
        receipt_path=Path(receipt_pin['path'])
        if sha256(receipt_path)!=receipt_pin['sha256']:
            raise ValueError('recovery receipt pin mismatch')
        if index==0 and receipt_pin['sha256']!=ingestion['recovery_receipt_sha256']:
            raise ValueError('first recovery receipt differs from final ingestion')
        receipt=json.loads(receipt_path.read_bytes())
        if (receipt['schema']!='C15_EXPLICIT_SOURCE_RECOVERY_V1'
                or receipt['existing_entries_rewritten']!=0
                or not _same(receipt['recovered_path'],expected_child)):
            raise ValueError('recovery lineage order or rewrite claim invalid')
        parent_path=Path(parent['path'])
        resolved=parent_path.resolve()
        if resolved in seen or resolved==final_source_path.resolve():
            raise ValueError('recovery lineage cycle')
        seen.add(resolved)
        if (not _same(receipt['parent_path'],parent_path) or
                receipt['parent']!={k:parent[k] for k in ('sha256','count','head_hash')}):
            raise ValueError('closed parent witness differs from recovery receipt')
        wal=Path(str(parent_path)+'-wal')
        if parent_path.is_symlink() or (wal.exists() and wal.stat().st_size):
            raise ValueError('parent must be a closed immutable journal')
        if sha256(parent_path)!=parent['sha256']:
            raise ValueError('closed parent physical bytes changed')
        db=sqlite3.connect(parent_path.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            tail=db.execute('SELECT ordinal,digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
            if tail is None or (tail[0]+1,tail[1])!=(parent['count'],parent['head_hash']):
                raise ValueError('closed parent tail differs from witness')
        finally:db.close()
        output.append(dict(recovery_receipt=dict(receipt_pin),closed_parent=dict(parent)))
        expected_child=parent_path
    return dict(schema='FRANKIE_CLOSED_SOURCE_LINEAGE_V1',final_source_path=str(final_source_path),links=output)
