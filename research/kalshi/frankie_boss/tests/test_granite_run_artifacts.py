"""Exact artifact staging tests; synthetic bytes prove mechanics, not real weights."""
import hashlib
import io
import json
from pathlib import Path
import pytest
import granite_run_artifacts as m


def fixture(tmp_path):
    manifest=json.loads(Path(m.DEFAULT_MANIFEST).read_bytes())
    blobs={row['path']:b'fixture:'+row['path'].encode() for row in manifest['files']}
    shards=[name for name in blobs if name.endswith('.safetensors')]
    blobs['model.safetensors.index.json']=json.dumps({'weight_map':{str(i):name for i,name in enumerate(shards)}}).encode()
    for row in manifest['files']:
        row.update(size=len(blobs[row['path']]),sha256=hashlib.sha256(blobs[row['path']]).hexdigest())
        (tmp_path/row['path']).write_bytes(blobs[row['path']])
    return manifest,blobs


def test_complete_mount_receipt_is_derived_from_all_real_bytes(tmp_path):
    manifest,blobs=fixture(tmp_path)
    receipt=m.verify_directory(tmp_path,manifest)
    assert receipt['manifest_sha256']==m.manifest_digest(manifest)
    assert len(receipt['files'])==13
    assert receipt['bytes']==sum(map(len,blobs.values()))


@pytest.mark.parametrize('damage',['corrupt','extra','missing','directory','symlink'])
def test_mount_rejects_any_roster_or_byte_mismatch(tmp_path,damage,monkeypatch):
    manifest,blobs=fixture(tmp_path)
    name='config.json'
    if damage=='corrupt': (tmp_path/name).write_bytes(b'bad')
    if damage=='extra': (tmp_path/'extra').write_bytes(b'bad')
    if damage=='missing': (tmp_path/name).unlink()
    if damage=='directory': (tmp_path/'extra').mkdir()
    if damage=='symlink':
        (tmp_path/name).unlink()
        try:
            (tmp_path/name).symlink_to(tmp_path/'tokenizer.json')
        except OSError as exc:
            if getattr(exc,'winerror',None)!=1314: raise
            (tmp_path/name).write_bytes(blobs[name])
            original=Path.is_symlink
            monkeypatch.setattr(Path,'is_symlink',lambda p: p==tmp_path/name or original(p))
    with pytest.raises(ValueError): m.verify_directory(tmp_path,manifest)


@pytest.mark.parametrize('damage',['traversal','duplicate','negative-size','bool-size','bad-hash','revision','missing-shard'])
def test_untrusted_manifest_never_selects_arbitrary_paths(tmp_path,damage):
    manifest,_=fixture(tmp_path)
    if damage=='traversal': manifest['files'][0]['path']='../escape'
    if damage=='duplicate': manifest['files'].append(manifest['files'][0])
    if damage=='negative-size': manifest['files'][0]['size']=-1
    if damage=='bool-size': manifest['files'][0]['size']=True
    if damage=='bad-hash': manifest['files'][0]['sha256']='no'
    if damage=='revision': manifest['revision']='main'
    if damage=='missing-shard': manifest['files']=[r for r in manifest['files'] if not r['path'].endswith('.safetensors')]
    with pytest.raises(ValueError): m.manifest_digest(manifest)


def test_index_cannot_omit_or_add_shards(tmp_path):
    manifest,_=fixture(tmp_path)
    for mapping in ({'tensor':'../evil.safetensors'},{'tensor':'model-00001-of-00004.safetensors'}):
        with pytest.raises(ValueError): m.verify_index(json.dumps({'weight_map':mapping}).encode(),manifest)


class S3:
    def __init__(self,blobs,prefix): self.blobs={prefix+k:v for k,v in blobs.items()};self.closed=[]
    def get_object(self,**args):
        outer=self
        class Body(io.BytesIO):
            def close(self): outer.closed.append(True);super().close()
        data=self.blobs[args['Key']]
        return {'Body':Body(data),'ContentLength':len(data),'VersionId':'v1','ETag':'not-a-hash'}
    def list_objects_v2(self,**args):
        return {'Contents':[{'Key':k,'Size':len(v)} for k,v in self.blobs.items()],'IsTruncated':False}


def test_s3_reads_whole_bytes_and_rejects_corruption_or_extra_keys(tmp_path):
    manifest,blobs=fixture(tmp_path);prefix='models/'+m.manifest_digest(manifest)+'/'
    client=S3(blobs,prefix)
    receipt=m.verify_s3(client,'synthetic-bucket',manifest)
    assert len(receipt['files'])==len(blobs) and len(client.closed)==len(blobs)
    client.blobs[prefix+'extra']=b'extra'
    with pytest.raises(ValueError,match='roster'): m.verify_s3(client,'synthetic-bucket',manifest)
    del client.blobs[prefix+'extra'];client.blobs[prefix+'config.json']=b'bad'
    with pytest.raises(ValueError): m.verify_s3(client,'synthetic-bucket',manifest)


def test_pinned_manifest_matches_reviewed_total():
    manifest=json.loads(Path(m.DEFAULT_MANIFEST).read_bytes())
    m.validate_manifest(manifest)
    assert sum(r['size'] for r in manifest['files'] if r['path'].endswith('.safetensors'))==17583228032


class Download(io.BytesIO):
    def __init__(self,data,status=200,headers=None):
        super().__init__(data);self.status=status;self.headers=headers or {'ETag':'"immutable"'}


def test_download_verifies_exact_bytes_before_promotion(tmp_path):
    manifest,blobs=fixture(tmp_path); row=manifest['files'][0]
    target=tmp_path/'download';target.mkdir()
    path=m.download_file(row,target,opener=lambda *a,**kw:Download(blobs[row['path']]))
    assert path.read_bytes()==blobs[row['path']]
    assert not path.with_suffix(path.suffix+'.partial').exists()


def test_download_corruption_never_becomes_final_file(tmp_path):
    manifest,_=fixture(tmp_path);row=manifest['files'][0];target=tmp_path/'download';target.mkdir()
    with pytest.raises(ValueError): m.download_file(row,target,opener=lambda *a,**kw:Download(b'wrong'))
    assert not (target/row['path']).exists()


@pytest.mark.parametrize('changed',['none','etag','range','status'])
def test_resume_checks_remote_identity_and_rehashes_whole_file(tmp_path,changed):
    manifest,blobs=fixture(tmp_path);row=manifest['files'][0];target=tmp_path/'download';target.mkdir()
    raw=blobs[row['path']];offset=3
    partial=target/(row['path']+'.partial');partial.write_bytes(raw[:offset])
    metadata={'url':m.download_url(row),'etag':'"immutable"','sha256':row['sha256'],'size':row['size']}
    (target/(row['path']+'.partial.json')).write_bytes(m.canonical(metadata))
    def opener(req,**kwargs):
        assert req.get_header('Range')=='bytes=3-'
        assert req.get_header('If-range')=='"immutable"'
        return Download(raw[offset:],status=200 if changed=='status' else 206,
                        headers={'ETag':'"changed"' if changed=='etag' else '"immutable"',
                                 'Content-Range':f'bytes {4 if changed=="range" else offset}-{len(raw)-1}/{len(raw)}'})
    if changed=='none': assert m.download_file(row,target,opener=opener).read_bytes()==raw
    else:
        with pytest.raises(ValueError):m.download_file(row,target,opener=opener)
        assert partial.read_bytes()==raw[:offset]


def test_staging_keeps_local_bytes_until_remote_verifies(tmp_path):
    manifest,blobs=fixture(tmp_path); target=tmp_path/'stage';target.mkdir();prefix=m.prefix_for(manifest)
    client=S3({},prefix)
    def upload_file(path,bucket,key,**kwargs): client.blobs[key]=Path(path).read_bytes()
    client.upload_file=upload_file
    def fetch(row,directory):
        path=directory/row['path'];path.write_bytes(blobs[row['path']]);return path
    receipt=m.stage(client,'synthetic-bucket',manifest,target,tmp_path/'receipt.json',fetch=fetch)
    assert receipt['status']=='verified'
    assert not list(target.iterdir())
    assert len(client.blobs)==13
    assert json.loads((tmp_path/'receipt.json').read_bytes())==receipt


def test_staging_rejects_corrupt_existing_object_without_overwrite(tmp_path):
    manifest,blobs=fixture(tmp_path);prefix=m.prefix_for(manifest)
    client=S3({'config.json':b'bad'},prefix)
    client.upload_file=lambda *a,**kw:pytest.fail('must not overwrite existing object')
    target=tmp_path/'stage';target.mkdir()
    with pytest.raises(ValueError): m.stage(client,'synthetic-bucket',manifest,target,tmp_path/'receipt.json')


@pytest.mark.parametrize('missing',[False,True])
def test_bucket_creation_is_only_exact_scoped_name_and_absent_only(missing):
    calls=[]
    class Absent(Exception): response={'Error':{'Code':'404'}}
    class Client:
        def head_bucket(self,**kw):
            calls.append(('head',kw['Bucket']))
            if missing and len(calls)==1: raise Absent()
        def create_bucket(self,**kw): calls.append(('create',kw['Bucket']))
    bucket=m.ensure_scoped_bucket(Client(),'123456789012')
    assert bucket=='frankie-granite42-123456789012-us-east-1'
    assert calls==[('head',bucket)]+([('create',bucket),('head',bucket)] if missing else [])


def test_bucket_access_denial_does_not_attempt_create():
    class Denied(Exception): response={'Error':{'Code':'403'}}
    class Client:
        def head_bucket(self,**kw): raise Denied()
        def create_bucket(self,**kw): pytest.fail('denial must not create')
    with pytest.raises(Denied):m.ensure_scoped_bucket(Client(),'123456789012')


def test_bucket_rejects_invalid_account():
    with pytest.raises(ValueError):m.ensure_scoped_bucket(object(),'../other')
