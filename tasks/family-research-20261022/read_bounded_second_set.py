"""Read four pinned compact second-set members via a bounded presigned S3 GET.

Input: base64-encoded presigned GET URL on stdin. Never log/persist the URL.
All recovered member bytes are preserved as independent gzip chunks in Git.
This is the 19-number compact source, not the entire rich second-set payload.
"""
import base64
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import time
import urllib.request
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/sqlite-triage/20261022/families'
OUT=BASE/'trade-lifecycle-targeted-v1'
SOURCE=OUT/'second-set-source'
SOURCE.mkdir(exist_ok=True)
PIN=json.loads((BASE/'dipole-audit-v1/complete_component_input_receipt.json').read_text())
WANTED={f['name']:f for f in PIN['files']}
CAP=128*1024*1024
started=time.monotonic()

class CountReader:
    def __init__(self,response):self.response=response;self.count=0
    def read(self,n=-1):
        if n<0:n=CAP-self.count+1
        data=self.response.read(min(n,CAP-self.count+1));self.count+=len(data)
        if self.count>CAP:raise RuntimeError('Compressed byte cap exceeded')
        return data

url=base64.b64decode(sys.stdin.readline().strip()).decode('ascii')
request=urllib.request.Request(url,headers={'Range':f'bytes=0-{CAP-1}'})
data={};transport=[];source_members=[]
try:
    with urllib.request.urlopen(request,timeout=60) as response:
        assert response.status==206,'Server must honor the fixed range request'
        reader=CountReader(response);uncompressed=0
        with tarfile.open(fileobj=reader,mode='r|gz') as archive:
            for member in archive:
                uncompressed+=member.size
                if uncompressed>512*1024*1024:raise RuntimeError('Tar prefix size cap exceeded')
                name=member.name.rsplit('/',1)[-1]
                if '/dipole-audit-v1/' not in '/'+member.name or name not in WANTED:continue
                pin=WANTED[name];assert member.size==pin['bytes']
                raw=archive.extractfile(member).read()
                assert hashlib.sha256(raw).hexdigest()==pin['sha256'],'New bounded transport member identity mismatch'
                data[name]=raw;chunks=[]
                for number,offset in enumerate(range(0,len(raw),32*1024*1024),1):
                    part=raw[offset:offset+32*1024*1024]
                    dest=SOURCE/f'{name}.chunk{number:03d}.gz'
                    dest.write_bytes(gzip.compress(part,compresslevel=3,mtime=0))
                    chunks.append(dict(path=dest.relative_to(ROOT).as_posix(),uncompressed_bytes=len(part),compressed_bytes=dest.stat().st_size))
                source_members.append(dict(original_member=member.name,bytes=member.size,sha256=pin['sha256'],chunks=chunks))
                print('Verified exact compact member',name,member.size,flush=True)
                if set(data)==set(WANTED):break
        compressed_read=reader.count
except Exception as exc:
    # Do not include request URLs or response objects in logs.
    print('Bounded archive read failed:',type(exc).__name__,getattr(exc,'code',''),file=sys.stderr)
    raise SystemExit(1)
assert set(data)==set(WANTED),'Required compact members not all within bounded prefix'
rows=PIN['rows'];names=PIN['names'];clocknames=PIN['clock_names']
clocks=np.frombuffer(data['clocks-i64.bin'],dtype='<i8').reshape(rows,len(clocknames))
raw64=np.frombuffer(data['raw-components-f64.bin'],dtype='<f8').reshape(rows,len(names))
source32=np.frombuffer(data['components-f32.bin'],dtype='<f4').reshape(rows,len(names))
states=np.frombuffer(data['states-u8.bin'],dtype='u1').reshape(rows,len(names))
index={int(cursor):i for i,cursor in enumerate(clocks[:,0])}
assert len(index)==rows
states_names=PIN['component_state_names']

def record(cursor):
    if cursor not in index:return {'disposition':'EXACT_CURSOR_ABSENT','input_cursor':cursor}
    i=index[cursor]
    return {'source_row_index':i,'clocks':{key:int(clocks[i,k]) for k,key in enumerate(clocknames)},
        'numbers':{name:{'raw_float64':float(raw64[i,k]) if np.isfinite(raw64[i,k]) else None,
                         'raw_float64_hex':float(raw64[i,k]).hex(),
                         'source_float32':float(source32[i,k]) if np.isfinite(source32[i,k]) else None,
                         'state_code':int(states[i,k]),'state':states_names[int(states[i,k])],
                         'reason':'Not present in compact projection; do not invent a reason'} for k,name in enumerate(names)},
        'scope':'original 19-number compact selected-cohort representation; full second-set payload is richer'}

with gzip.open(OUT/'all-30739-trades.csv.gz','rt',newline='') as f:trades=list(csv.DictReader(f))
matched=0;present_trade=0;present_close=0
with gzip.open(OUT/'every-trade-original-second-set.jsonl.gz','wt',encoding='utf-8',compresslevel=3) as f:
    for trade in trades:
        cursor=int(trade['trade_input_cursor']);close=int(trade['group_close_input_cursor'])
        assert cursor in index and close in index
        a=record(cursor);b=record(close)
        assert a['clocks']['event_ns']==int(trade['event_ns'])
        assert a['clocks']['receive_ns']==int(trade['receive_ns'])
        assert b['clocks']['known_by_ns']==int(trade['available_ns'])
        matched+=1
        present_trade+=any(v['state_code']==0 for v in a['numbers'].values())
        present_close+=any(v['state_code']==0 for v in b['numbers'].values())
        pre=trade.get('pre_group_input_cursor','')
        j={'trade_ordinal':int(trade['source_ordinal']),'trade_input_cursor':cursor,
           'at_trade_input':a,'at_emission_group_close':b,
           'previous_input':record(cursor-1),
           'last_completed_group_before_trade':record(int(pre)) if pre else {'disposition':'NO_PREVIOUS_COMPLETED_GROUP'},
           'interpretation':'Original values and explicit states, without averaging, imputation or replacing this trade by a family/dipole average'}
        f.write(json.dumps(j,separators=(',',':'),allow_nan=False)+'\n')
assert matched==30739
receipt={'status':'VERIFIED_BOUNDED_SECOND_SET_READ_AND_ALL_TRADE_JOINS',
    'bucket':'bento-568968024170-us-east-2-an',
    'key':'frankie/family-prebirth/20261022/family-full-context-v4-incomplete-inputs-7f823885.tar.gz',
    'region':'us-east-2','compressed_byte_cap':CAP,'compressed_bytes_read':compressed_read,
    'elapsed_seconds':round(time.monotonic()-started,3),'source_rows':rows,'original_number_names':names,
    'matched_trade_records':matched,'trade_rows_with_any_present_component':present_trade,
    'emission_rows_with_any_present_component':present_close,'source_members':source_members,
    'representation':'full original compact source preserved in gzip byte chunks; named numbers/states nested per trade; richer full second-set fields not claimed here',
    'new_transport_checks':'Each newly retrieved member SHA matches frozen receipt; no full archive/database rehash',
    'no_trades_dropped':True,'no_averaging_or_imputation':True,'ec2_starts':0,'fits':0,
    'semantic_coverage':'NOT_PASSED'}
(OUT/'bounded-second-set-read-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Every trade matched with exact event, receive and group-close clocks:',matched,flush=True)
print('Compressed archive bytes read:',compressed_read,flush=True)
