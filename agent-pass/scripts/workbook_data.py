import sys,json
from common import *
phase=sys.argv[1]
files=sorted((ROOT/'tables').glob('*.csv'))
# Exact rows in review tables; long per-second tables remain CSV.gz for scale.
selected=[p for p in files if any(s in p.name for s in ['candidate-operands','path-members','cases.csv','figure-reconciliation','detector-summary','lag-measurements','operator-summary','grouping-counts','moonshot-summary','crossday-summary'])]
out=[]
for p in selected:
 cols=[c for c in pd.read_csv(p,nrows=0).columns if c.endswith('_ns')]
 d=pd.read_csv(p,dtype={c:str for c in cols})
 for c in cols: d[c]=d[c].map(lambda v: chr(39)+str(v) if pd.notna(v) else None)
 out.append(dict(file=p.name,columns=d.columns.tolist(),rows=json.loads(d.to_json(orient='values'))))
(ROOT/'cache'/'workbook-input.json').write_text(json.dumps(out))
