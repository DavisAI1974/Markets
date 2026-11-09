import sys,json
from common import *
phase=sys.argv[1]
files=sorted((ROOT/'tables').glob('*.csv'))
# Exact rows in review tables; long per-second tables remain CSV.gz for scale.
selected=[p for p in files if any(s in p.name for s in ['candidate-operands','path-members','cases.csv','figure-reconciliation','detector-summary','lag-measurements','operator-summary','grouping-counts','moonshot-summary','crossday-summary'])]
out=[]
for p in selected:
 d=pd.read_csv(p,dtype={'recognition_ns':'str','anchor_ns':'str','recognition_receive_ns':'str'})
 out.append(dict(file=p.name,columns=d.columns.tolist(),rows=json.loads(d.to_json(orient='values'))))
(ROOT/'cache'/'workbook-input.json').write_text(json.dumps(out))
