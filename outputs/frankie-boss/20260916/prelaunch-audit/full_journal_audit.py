import hashlib, json, os, sys, time
from pathlib import Path
sys.path.insert(0, 'E:/Markets/research/kalshi/frankie_boss')
from frankie_journal_reader import FrankieCompactReader
from c15_journal import pack, unpack

def witness(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return dict(bytes=path.stat().st_size, sha256=h.hexdigest())

def main():
    root = Path(__file__).resolve().parent
    config = json.loads(Path('E:/Codex/Frankie-BOSS-20260915/sunday-launch-20260915/actual-host-final-configuration.json').read_bytes())
    pin = config['host_runtime']['compact_journal']
    path = Path(pin['path'])
    before = witness(path)
    if before != {k:pin[k] for k in ('bytes','sha256')}: raise ValueError('physical compact journal pin differs')
    checkpoint = Path('E:/Codex/Frankie-BOSS-20260915/source-recovery-resume-20260915/checkpoints/000032-cursor-57027.c15.json')
    state = unpack(json.loads(checkpoint.read_bytes()))
    count, head = state['journal_count'], state['journal_hash']
    started = time.perf_counter()
    reader = FrankieCompactReader(path, expected_count=count, expected_head_hash=head, workers=min(15,max(1,(os.cpu_count() or 1)-1)), emit=lambda x: print(json.dumps(x),flush=True))
    rows=applied=inputs=0; pending=None
    try:
        for entry in reader.entries():
            rows += 1
            payload = entry['payload']
            if entry['kind']=='INPUT':
                if pending is not None: raise ValueError('unresolved input')
                inputs += 1; pending=payload
            elif entry['kind']=='APPLIED':
                if pending is None or pack(payload['raw_record']) != pack(pending['record']): raise ValueError('input/applied evidence differs')
                applied += 1; pending=None
            else: raise ValueError('unexpected journal disposition')
        if pending is not None or (rows,inputs,applied)!=(114054,57027,57027): raise ValueError('terminal coverage differs')
    finally: reader.close()
    after=witness(path)
    if before!=after: raise ValueError('physical journal changed during audit')
    result=dict(schema='CODEX_FRANKIE_FULL_COMPACT_JOURNAL_AUDIT_V1',passed=True,rows=rows,inputs=inputs,applied=applied,journal_count=count,journal_head_hash=head,physical=after,checkpoint_sha256=witness(checkpoint)['sha256'],seconds=time.perf_counter()-started,sampled=False,model_calls=0,training_updates=0,scope='Full compact journal envelope/hash chain and exact INPUT/APPLIED raw-record pairing; does not prove final launch attachments or model understanding.')
    (root/'evidence/full-journal-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__': main()
