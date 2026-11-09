"""One-time corrections from review, without rebuilding raw paths or clustering."""
from common import *
from part1a import render_paths
from part2 import render_operators
import sys
for day in ['20231002','20231003','20231017','20231018']:
    C=pd.read_csv(ROOT/f'tables/{day}-candidate-operands.csv',dtype={'original_coverage':str})
    M=pd.read_csv(ROOT/f'tables/{day}-path-members.csv',dtype={'original_coverage':str})
    X=pd.read_csv(ROOT/f'tables/{day}-paths.csv.gz',dtype={'original_coverage':str},low_memory=False)
    render_paths(day,X,M,C)
    V=pd.read_csv(ROOT/f'tables/{day}-operator-residuals.csv');bad=(V.form=='monotone_magnitude_decay')&(V.disposition=='undefined')
    V.loc[bad,['observed','residual']]=np.nan;save(V,f'{day}-operator-residuals.csv')
    L=pd.read_csv(ROOT/f'tables/{day}-life-measurements.csv');L.loc[L.disposition=='undefined_anchor_direction','life_seconds']=np.nan;save(L,f'{day}-life-measurements.csv')
    Z=pd.read_csv(ROOT/f'tables/{day}-part2-figure-reconciliation.csv');Z=Z[Z.figure.str.contains('-structure-')]
    render_operators(day,C,V,L,Z.to_dict('records'))
    print(day,'repaired unavailable residual rows',int(bad.sum()),flush=True)
