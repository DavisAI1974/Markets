"""Publish an already-running recovery's retained artifacts; never rescan a journal."""
import hashlib,json,os,time,urllib.request,urllib.error
from pathlib import Path

def put(url,raw):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=raw,method='PUT'),timeout=60) as response:
            if response.status!=200:raise RuntimeError('unexpected publication response')
    except urllib.error.HTTPError as exc:
        raise RuntimeError('publication HTTP status '+str(exc.code)) from None
    except Exception:
        raise RuntimeError('publication transport unavailable') from None

def main(config):
    root=Path('/opt/frankie-box/work/sealed-recovery-35796793428')
    if any(p.is_symlink() for p in (root,*root.parents)):raise ValueError('recovery path has symlink')
    destinations=config['uploads']
    put(destinations['publication-probe.json'],b'{"schema":"FRANKIE_PUBLICATION_TRANSPORT_PROBE_V1","source_operations":0}\n')
    started=time.time()
    while True:
        progress=root/'progress.jsonl'
        if progress.is_file():
            raw=progress.read_bytes()
            # Never publish a partially appended final line.
            if raw.endswith(b'\n'):
                put(destinations['progress.jsonl'],raw)
        marker=root/'recovery-receipt.json'
        if marker.is_file():
            try:receipt_raw=marker.read_bytes();receipt=json.loads(receipt_raw)
            except (OSError,ValueError):
                time.sleep(1);continue
            required=dict(schema='FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1',status='complete',
                code_commit='01945e24da7ac3e628b897a5d45fda2cde9b1536',
                manifest_hash='a399377b5b005d989daa467048438437c47b8597dc8cfb5861c3706c6f92a355',
                record_count=2032203,journal_count=4064406,
                journal_hash='534f442aa0008032064c540f1c472433cb665a97bfec94399f8137ca103f207c',
                source_replays=0,adapter_apply_calls=0,parent_writes=0,original_ingest_status='Cancelled')
            if any(receipt.get(k)!=v for k,v in required.items()):raise ValueError('recovery receipt differs from independent pins')
            if receipt['container']!=dict(path='/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite',
                bytes=23687368704,sha256='947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888'):
                raise ValueError('container receipt differs')
            bodies={}
            for field,name in (('checkpoint','builder-checkpoint.c15.json'),('completion','completion.json')):
                artifact=receipt['artifacts'][field]
                if artifact['file']!=name:raise ValueError('unexpected artifact path')
                p=root/name
                if p.is_symlink():raise ValueError('artifact symlink')
                raw=p.read_bytes()
                if len(raw)!=artifact['bytes'] or hashlib.sha256(raw).hexdigest()!=artifact['sha256']:
                    raise ValueError('artifact bytes differ')
                bodies[name]=raw
            boundary=(root/'source-boundary.json').read_bytes()
            if hashlib.sha256(boundary).hexdigest()!=receipt['source_boundary_sha256']:raise ValueError('boundary receipt differs')
            completion=json.loads(bodies['completion.json'])
            if any(completion[k]!=receipt[k] for k in ('record_count','journal_count','journal_hash','group_count','source_prefix_hash')):
                raise ValueError('completion counters differ')
            # All source computations ended before this local completion receipt existed.
            # Publication cannot modify the computation directory or its original container.
            put(destinations['source-boundary.json'],boundary)
            for name,raw in bodies.items():put(destinations[name],raw)
            publication=dict(schema='FRANKIE_RECOVERY_PUBLICATION_V1',status='complete',
                computation_run_id=35796793428,computation_command_id='2ea4f5d5-bc7d-42eb-bb0c-d34832db53b4',
                computation_code_commit=required['code_commit'],publication_code_commit=config['commit'],
                publication_run_id=config['run'],recovery_receipt_sha256=hashlib.sha256(receipt_raw).hexdigest(),
                source_operations=0,journal_reads=0,original_journal_writes=0,published_unix=time.time())
            put(destinations['publication-receipt.json'],(json.dumps(publication,sort_keys=True)+'\n').encode())
            put(destinations['recovery-receipt.json'],receipt_raw)
            print('RECOVERY_RECEIPT '+receipt_raw.decode().replace('\n',''),flush=True)
            return
        if time.time()-started>20000:raise RuntimeError('existing computation has not produced completion; preserve all evidence')
        time.sleep(20)

if __name__=='__main__':main(CONFIG)
