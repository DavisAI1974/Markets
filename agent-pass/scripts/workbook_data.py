"""Workbook review tables, consolidated across dates without pooling observations."""
import sys,json,re
from common import *
files=sorted((ROOT/'tables').glob('*.csv'))
selected=[p for p in files if any(s in p.name for s in ['candidate-operands','path-members','cases.csv','figure-reconciliation','detector-summary','lag-measurements','operator-summary','grouping-counts','moonshot-summary','crossday-summary'])]
groups={}
for p in selected:
    cols=[c for c in pd.read_csv(p,nrows=0).columns if c.endswith('_ns')]
    d=pd.read_csv(p,dtype={c:str for c in cols})
    for c in cols:d[c]=d[c].map(lambda v: chr(39)+str(v) if pd.notna(v) else None)
    if 'day' not in d and re.match(r'^\d{8}-',p.name):d.insert(0,'day',p.name[:8])
    key=re.sub(r'^\d{8}-','',p.name)
    groups.setdefault(key,[]).append((p.name,d))
out=[]
for key,items in groups.items():
    d=pd.concat([d for _,d in items],ignore_index=True)
    out.append(dict(file=key,sources=[n for n,_ in items],columns=d.columns.tolist(),rows=json.loads(d.to_json(orient='values'))))
(ROOT/'cache/workbook-input.json').write_text(json.dumps(out))
