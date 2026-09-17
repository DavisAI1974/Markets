"""A journal readback must reproduce the exact reviewed bootstrap command."""
import hashlib
import json
from pathlib import Path
from research.kalshi.frankie_boss.granite_runpod_package import FILES
from research.kalshi.frankie_boss.granite_runpod_cloud import bootstrap_command

def test_command_survives_canonical_journal_key_order():
    root=Path(__file__).resolve().parents[1]
    rows=[]
    for name in FILES:
        raw=(root/name).read_bytes()
        rows.append(dict(path=name,size=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    original=bootstrap_command(rows,'c'*64,'fixed-bucket',directory='/opt/ml/bootstrap',open_ended=True)
    restored=json.loads(json.dumps(rows,sort_keys=True,separators=(',',':')))
    assert list(restored[0]) != list(rows[0])
    assert bootstrap_command(restored,'c'*64,'fixed-bucket',directory='/opt/ml/bootstrap',open_ended=True)==original
    changed=[dict(row) for row in restored]
    changed[0]['sha256']='d'*64
    assert hashlib.sha256(bootstrap_command(changed,'c'*64,'fixed-bucket',directory='/opt/ml/bootstrap',open_ended=True).encode()).hexdigest()!=hashlib.sha256(original.encode()).hexdigest()
