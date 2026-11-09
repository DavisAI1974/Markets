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
out=dict(status='local_pending_Ccode_three_tier_layout',no_aws_or_s3=True,created_utc=datetime.now(timezone.utc).isoformat(),files=entries,source_blobs=source)
p=ROOT/'cache/pending-publication-manifest.json';p.write_text(json.dumps(out,indent=2)+'\n')
checksum=hashlib.sha256(p.read_bytes()).hexdigest()
text=f'''# Pending artifact publication

Research outputs are preserved locally under `{ROOT}`. Ccode owns the three-tier repository layout; its destination paths and immutable-version conventions have not been supplied to this pass. No AWS/S3 or alternate repository was used.

- Generated local artifacts: {len(entries)} files, {sum(e['bytes'] for e in entries):,} bytes.
- Local inventory: `agent-pass/cache/pending-publication-manifest.json`.
- Inventory SHA256: `{checksum}`.
- Pinned source blobs in the inventory: {len(source)}; locally present: {sum(e['locally_present'] for e in source)}.
- Sizes are measured only from present files. Missing local sources are explicit nulls, never zero; the inventory does not fetch Git objects.

The inventory records SHA256 and byte size for each CSV, compressed observation table, chart, workbook and receipt, plus each pinned source revision/path/hash and its local cache coordinate. It is an inventory pending routing, not an assertion that a destination manifest has been created.

Already-published pre-policy artifacts are listed by commit and path family in PROGRESS.md. No published history was rewritten. Since the policy change only code, Markdown and references have been staged. Original tracked generated artifacts now have intentional unstaged local updates; preserve them for the data-repository handoff.

After Ccode supplies the configured layout, publish from these local files using its conventions, verify read-back hashes, and replace local-only references with actual immutable destination versions. Do not create a duplicate tier layout or copy the artifacts into another Markets commit.
'''
(ROOT/'PENDING_PUBLICATION.md').write_text(text)
print(len(entries),'files',sum(e['bytes'] for e in entries),'bytes; manifest',checksum)
