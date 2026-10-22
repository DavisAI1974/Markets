"""Package actual Julia outputs, without touching the source SQLite database."""
import gzip
import hashlib
import json
import pathlib
import shutil
import tarfile

BASE = pathlib.Path('/opt/frankie-box/work/family-research-20261022')
OUT = BASE / 'descriptive-v1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


files = []
manifest = []
core_names = {
    'family_master.csv', 'samples.csv', 'features.csv', 'group_measurements.csv',
    'extended_group_measurements.csv', 'group_context_receipts.csv',
    'complete_context_measurements.csv', 'indexed_context_source_receipts.csv',
    'external_asof.csv', 'external_point_provenance.csv', 'plane_registry.csv',
    'source_registry.csv', 'view_definitions.csv', 'retained_group_sequence.csv',
    'second_set_context_receipts.csv', 'run_receipt.json',
    'Project.toml', 'Manifest.toml', 'complete-context.log',
    'group-enrichment.log', 'math-tests.log', 'input-audit.log',
    'input_completeness_receipt.json', 'analysis_status.json',
    'external_last_observed_measurements.csv', 'augment-external.log',
    'geometry_contexts.csv', 'pullback_measurements.csv',
    'family_context_linkage.csv', 'extract-geometry.log', 'complete-pullback.log',
}
for path in sorted(OUT.iterdir()):
    if not path.is_file() or path.suffix not in ('.csv', '.json', '.toml', '.log'):
        continue
    if path.name not in core_names and not path.name.startswith('input_'):
        continue
    if path.name == 'artifact_manifest.json':
        continue
    packed = path
    if path.suffix == '.csv' and path.stat().st_size >= 1_000_000:
        packed = path.with_suffix('.csv.gz')
        with path.open('rb') as src, packed.open('wb') as target:
            with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0) as dst:
                shutil.copyfileobj(src, dst)
    manifest.append({'source_name': path.name, 'source_bytes': path.stat().st_size,
                     'source_sha256': sha(path), 'saved_name': packed.name,
                     'saved_bytes': packed.stat().st_size, 'saved_sha256': sha(packed)})
    files.append(packed)
receipt = OUT / 'artifact_manifest.json'
receipt.write_text(json.dumps(manifest, indent=2) + '\n')
files.append(receipt)
archive = BASE / 'family-input-completeness.tar.gz'
with tarfile.open(archive, 'w:gz') as tar:
    for path in files:
        tar.add(path, arcname='descriptive-v1/' + path.name, recursive=False)
print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
                  'sha256': sha(archive), 'files': len(files)}))
