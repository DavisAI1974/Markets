"""Recovery-only closed-source-lineage verification for resumable Sunday hosts.

This is the lawful ActualHost.source_lineage check with one deliberate correction:
sidecar liveness is delegated to journal_prefix_snapshot._sidecars, the existing
audited rule that treats rollback journals and WAL frames as hot but does not let
a read-only SQLite open poison the next resume with header-only WAL/SHM residue.
All hashes, tails, recovery links and source-prefix anchors are otherwise checked
identically. This helper never writes or deletes a journal or sidecar.
"""
from pathlib import Path
import sqlite3

from .journal_prefix_snapshot import _sidecars


def verify_closed_source_lineage(owner, source, ingestion, *, verified_json, verified):
    lineage=verified_json(owner.host['source_lineage'])
    if (lineage.get('schema')!='FRANKIE_CLOSED_SOURCE_LINEAGE_V1' or
        Path(lineage['final_source_path']).resolve()!=(source/'source.sqlite').resolve() or not lineage['links']):
        raise ValueError('explicit closed source lineage required')
    child=(source/'source.sqlite').resolve();seen=set()
    for index,link in enumerate(lineage['links']):
        witness=link['recovery_receipt'];recovery=verified_json(witness);parent=link['closed_parent']
        path=Path(parent['path']).resolve()
        if (str(path) in seen or path==child or Path(recovery['recovered_path']).resolve()!=child or
            Path(recovery['parent_path']).resolve()!=path or recovery['existing_entries_rewritten']!=0 or
            any(parent[k]!=recovery['parent'][k] for k in ('sha256','count','head_hash')) or
            (index==0 and witness['sha256']!=ingestion['recovery_receipt_sha256'])):
            raise ValueError('closed lineage differs from actual recovery receipts')
        if _sidecars(path):
            raise ValueError('lineage parent must be closed before verification')
        verified(parent)
        connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        try:tail=connection.execute('SELECT ordinal,digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
        finally:connection.close()
        if tail is None or (tail[0]+1,tail[1])!=(parent['count'],parent['head_hash']):
            raise ValueError('closed lineage parent differs from independently supplied tail')
        connection=sqlite3.connect(child.as_uri()+'?mode=ro',uri=True)
        try:anchor=connection.execute('SELECT digest FROM entries WHERE ordinal=?',(recovery['journal_count']-1,)).fetchone()
        finally:connection.close()
        if anchor is None or anchor[0]!=recovery['journal_hash']:
            raise ValueError('child no longer contains its verified rehydration boundary')
        owner.source_origins[str(path)]=parent['count']//2*2
        seen.add(str(path));child=path
    owner.save('verified-source-lineage.c15.json',dict(witness=owner.host['source_lineage'],lineage=lineage))
