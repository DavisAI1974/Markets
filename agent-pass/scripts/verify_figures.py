"""Reconcile every saved figure against its panel/series denominator inventory."""
from common import *
from PIL import Image

referenced=set();panels=0
for p in sorted((ROOT/'tables').glob('*figure-reconciliation.csv')):
    z=pd.read_csv(p)
    extra=z.endpoint_points_in_companion.fillna(0) if 'endpoint_points_in_companion' in z else 0
    assert (z.rows_in==z.points_plotted+z.rows_excluded+extra).all(),p
    panels+=len(z);referenced.update(z.figure)
for filename in referenced:
    p=ROOT/'figures'/filename
    with Image.open(p) as img:
        assert img.width>0 and img.height>0
        img.verify()
saved={p.name for p in (ROOT/'figures').glob('*.png')}
assert saved==referenced,dict(unreconciled=saved-referenced,missing=referenced-saved)
print('Verified',len(saved),'PNG figures;',panels,'panel/series rows; no unreconciled figures')
