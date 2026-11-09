"""Inventory only existing local files. Does not fetch, upload, or invent a destination."""
from common import ROOT
import hashlib,json
from datetime import datetime,timezone
files=[]
for directory in ['tables','figures']:
    for p in sorted((ROOT/directory).glob('*')):
        if p.is_file():files.append(p)
files += sorted(ROOT.glob('*-receipt.json'))
for name in ['research-tables.xlsx','source-manifest.json']:
    p=ROOT/name
    if p.is_file():files.append(p)
entries=[dict(path=str(p.relative_to(ROOT)).replace('\\','/'),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
source=[]
for e in json.loads((ROOT/'source-manifest.json').read_text()):
    cache=ROOT/'cache'/hashlib.sha256((e['revision']+':'+e['path']).encode()).hexdigest()
    source.append(dict(**e,locally_present=cache.is_file(),local_bytes=cache.stat().st_size if cache.is_file() else None,local_path=str(cache) if cache.is_file() else None))
out=dict(status='inventoried_for_markets_data_publication',no_aws_or_s3=True,created_utc=datetime.now(timezone.utc).isoformat(),files=entries,source_blobs=source)
p=ROOT/'cache/pending-publication-manifest.json';p.write_text(json.dumps(out,indent=2)+'\n')
checksum=hashlib.sha256(p.read_bytes()).hexdigest()
text=f'''# Artifact publication

GitHub is the durable working source. Code, findings and handoffs belong in DavisAI1974/Markets;
data, tables, renders, workbooks and provenance belong in DavisAI1974/markets-data.
The user removed the local-only rule on 2026-11-08. Existing desktop files are migration
sources only. Preserve existing input paths; corrected artifacts use new immutable paths.
No AWS/S3. No merge.

- Inventoried artifacts: {len(entries)} files, {sum(e['bytes'] for e in entries):,} bytes.
- Inventory: `agent-pass/cache/pending-publication-manifest.json`.
- Inventory SHA256: `{checksum}`.
- Pinned source blobs: {len(source)}; present: {sum(e['locally_present'] for e in source)}.
- Sizes are measured from present files; absent sources are null, never zero.

This script inventories migration inputs. It does not upload or claim publication.
Preserve the verified destination receipt in PUBLICATION.md; rerunning this inventory
must not replace that receipt or reintroduce a requirement to keep outputs local.
'''
(ROOT/'PENDING_PUBLICATION.md').write_text(text)
print(len(entries),'files',sum(e['bytes'] for e in entries),'bytes; manifest',checksum)
