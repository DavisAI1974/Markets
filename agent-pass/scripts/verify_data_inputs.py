"""Read-only external input audit; exercise refusal of changed or unverified inputs."""
from common import *
import tempfile

directory=Path(os.environ['MARKETS_DATA_DIR']).resolve()
manifest_bytes=(directory/'MANIFEST.json').read_bytes()
entries=json.loads(manifest_bytes)['entries']
audit=[];equivalent=[]
for e in entries:
    relative=e.get('markets_data_path')
    p=directory/relative if relative else None
    local=p is not None and p.is_file()
    status='external_reference_or_missing'
    if local:
        b=p.read_bytes()
        if e.get('sha256'):
            assert hashlib.sha256(b).hexdigest()==e['sha256'] and (e.get('bytes') is None or len(b)==e['bytes']),e['path']
            status='manifest_hash_verified'
        else:status='unverified_null_hash'
    audit.append(dict(path=e['path'],markets_data_path=relative,status=status,local_bytes=p.stat().st_size if local else None))
for e in json.loads((ROOT/'source-manifest.json').read_text()):
    cache=ROOT/'cache'/hashlib.sha256((e['revision']+':'+e['path']).encode()).hexdigest()
    if cache.is_file():
        external=manifest_input(e['path'],cache.read_bytes())
        if external is not None:equivalent.append(dict(path=e['path'],revision=e['revision'],sha256=hashlib.sha256(external).hexdigest()))
with tempfile.TemporaryDirectory(dir=ROOT/'cache') as tmp:
    p=Path(tmp);(p/'input').write_bytes(b'pinned')
    e=dict(path='fixture',markets_data_path='input',bytes=6,sha256=hashlib.sha256(b'pinned').hexdigest())
    def write(): (p/'MANIFEST.json').write_text(json.dumps(dict(entries=[e])))
    write();os.environ['MARKETS_DATA_DIR']=tmp
    assert manifest_input('fixture',b'pinned')==b'pinned'
    assert manifest_input('absent',b'pinned') is None
    def rejected(pinned):
        try:manifest_input('fixture',pinned)
        except ValueError:return
        raise AssertionError('Changed input was accepted')
    rejected(b'changed population')
    (p/'input').write_bytes(b'tampered');rejected(b'pinned')
    e['sha256']=None;write();assert manifest_input('fixture',b'pinned') is None
    os.environ['MARKETS_DATA_DIR']=str(directory)
receipt=dict(repository=str(directory),revision=subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip(),manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),entries=audit,equivalent_pinned_inputs=equivalent,negative_checks=['changed population rejected','tampered file rejected','null hash not accepted','missing entry uses fallback'])
(ROOT/'input-routing-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('External statuses:',pd.Series([e['status'] for e in audit]).value_counts().to_dict())
print('Byte-identical pinned inputs accepted:',len(equivalent))
