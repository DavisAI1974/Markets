"""Copy complete retained Native lifecycle ledgers from pinned archive parts.

Archive transport is streamed; source rows are preserved byte-for-byte. This
does not rerun Native or invent measurements absent from its saved ledger.
"""
import collections
import gzip
import hashlib
import io
import json
import os
import pathlib
import sys
import tarfile
import time
import urllib.request

import pyarrow as pa
import pyarrow.parquet as pq
import zstandard

REPO='DavisAI1974/Markets'
PINS={
    '20231002':'bebd939d99171ef747febdee4029aa729a8786fe',
    '20231003':'209f99ca3dab185bfdeca5db93e98036af0a56c5',
    '20231017':'f00fbac0dc1dcad53b349d43fc5ad4aa0c915c1e',
}


def get(url):
    headers={'User-Agent':'Frankie-retained-source-recovery'}
    if url.startswith('https://api.github.com/') and os.environ.get('GH_TOKEN'):
        headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    request=urllib.request.Request(url,headers=headers)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request,timeout=180) as response:return response.read()
        except Exception:
            if attempt==4:raise
            time.sleep(2**attempt)


class Parts(io.RawIOBase):
    def __init__(self, entries):
        super().__init__()
        self.entries=iter(entries)
        self.current=io.BytesIO()
        self.used=[]

    def readable(self):return True

    def readinto(self, target):
        data=self.current.read(len(target))
        while not data:
            try:entry=next(self.entries)
            except StopIteration:return 0
            data=get(entry['download_url'])
            assert len(data)==entry['size']
            digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            assert digest==entry['sha'],entry['name']
            self.used.append(dict(path=entry['path'],bytes=len(data),git_blob=digest,
                                  sha256=hashlib.sha256(data).hexdigest()))
            print('verified archive part',entry['name'],flush=True)
            self.current=io.BytesIO(data)
            data=self.current.read(len(target))
        target[:len(data)]=data
        return len(data)


def dump(path,value):
    path.write_text(json.dumps(value,indent=1,allow_nan=False)+'\n',encoding='utf-8')


def main(day,destination):
    revision=PINS[day]
    prefix=f'tasks/family-research-20261022/replay-artifacts/{day}/root-native-remaining'
    inventory=json.loads(get(f'https://api.github.com/repos/{REPO}/contents/{prefix}?ref={revision}'))
    entries=sorted([x for x in inventory if x['name'].startswith('remaining.tar.zst.part-')],key=lambda x:x['name'])
    assert entries
    for i,entry in enumerate(entries):assert entry['name']==f'remaining.tar.zst.part-{i:06d}'
    out=pathlib.Path(destination);out.mkdir(parents=True,exist_ok=False)
    parts=Parts(entries)
    sections=collections.Counter()
    field_names=collections.defaultdict(set)
    raw_hash=hashlib.sha256()
    raw_bytes=rows=part=0
    index=[];files=[];samples=[]
    current=None;current_bytes=0;current_rows=0;current_first=0

    def close_shard():
        nonlocal current,index
        if current is None:return
        current.close()
        name=f'lifecycle-{part-1:04d}.jsonl.gz'
        p=out/name
        with p.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        assert p.stat().st_size<95_000_000
        files.append(dict(path=name,rows=current_rows,first_source_row=current_first,
                          bytes=p.stat().st_size,sha256=digest))
        ip=out/f'lifecycle-index-{part-1:04d}.parquet'
        pq.write_table(pa.Table.from_pylist(index),ip,compression='zstd')
        data=ip.read_bytes()
        files.append(dict(path=ip.name,rows=len(index),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        current=None;index=[]

    with zstandard.ZstdDecompressor().stream_reader(parts) as decoded:
        with tarfile.open(fileobj=decoded,mode='r|') as archive:
            found=False
            for member in archive:
                if member.name in ('calculation-pins.json','source-binding.json'):
                    data=archive.extractfile(member).read()
                    json.loads(data)
                    (out/pathlib.PurePosixPath(member.name).name).write_bytes(data)
                    continue
                if not member.name.endswith('/exact_lifecycle_rows.jsonl'):
                    raise ValueError('Unexpected earlier archive member; refuse unbounded unrelated extraction: '+member.name)
                found=True
                stream=archive.extractfile(member)
                for raw in stream:
                    assert raw.endswith(b'\n'),'partial source row'
                    row=json.loads(raw)
                    emission=row.get('frankie_emission') or {}
                    section=row.get('emitting_section',row.get('section','UNSPECIFIED'))
                    fields=sorted(row)
                    if current is None or current_bytes>=32*1024*1024:
                        close_shard()
                        current=gzip.GzipFile(filename=str(out/f'lifecycle-{part:04d}.jsonl.gz'),mode='wb',compresslevel=3,mtime=0)
                        part+=1;current_bytes=0;current_rows=0;current_first=rows
                    current.write(raw)
                    raw_hash.update(raw);raw_bytes+=len(raw);current_bytes+=len(raw)
                    index.append(dict(source_row=rows,shard=f'lifecycle-{part-1:04d}.jsonl.gz',shard_row=current_rows,
                                      emitting_section=section,input_cursor=emission.get('input_cursor'),
                                      group_index=emission.get('group_index'),
                                      known_by_ns=row.get('emitted_at_recv_ns',emission.get('ts_recv_ns')),
                                      emitted_on=row.get('emitted_on'),phase=emission.get('phase')))
                    current_rows+=1;rows+=1
                    if sections[section]==0:samples.append(dict(source_row=rows-1,original=row))
                    sections[section]+=1;field_names[section].update(fields)
                    if rows%100000==0:print(day,'retained original lifecycle rows',rows,'bytes',raw_bytes,flush=True)
                close_shard()
                assert raw_bytes==member.size,(raw_bytes,member.size)
                source_member=member.name
                break
            assert found
    dump(out/'REVIEW_SAMPLES.json',samples)
    dump(out/'SOURCE_PARTS.json',dict(repository=REPO,revision=revision,parts=parts.used))
    dump(out/'SECTION_FIELDS.json',{k:sorted(v) for k,v in field_names.items()})
    dump(out/'MANIFEST.json',dict(files=files))
    receipt=dict(schema='FRANKIE_NATIVE_LIFECYCLE_RECOVERY_V1',day=day,source_repository=REPO,
                 source_revision=revision,source_member=source_member,source_member_bytes=raw_bytes,
                 reconstructed_source_sha256=raw_hash.hexdigest(),source_rows=rows,sections=dict(sections),
                 archive_parts_verified=len(parts.used),complete_retained_lifecycle_ledger=True,
                 complete_all_layers=False,producer_rerun=False,
                 rule='Original rows preserved in order. Each row retains its original emission clock and source cursor; no later state is substituted into earlier inputs.')
    dump(out/'RECOVERY_RECEIPT.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main(sys.argv[1],sys.argv[2])
