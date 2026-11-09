from common import *
C,rs=candidates('20231018');G=groups('20231018');X=pd.read_csv(ROOT/'tables/20231018-paths.csv.gz');R=pd.read_csv(ROOT/'tables/20231018-figure-reconciliation.csv')
assert ((R.rows_in==R.points_plotted+R.endpoint_points_in_companion+R.rows_excluded)).all()
checks=[]
for r in rs:
 pre=G.iloc[np.searchsorted(G.receive_ns,r['birth_second']*S-1,side='right')-1]
 rec=G.iloc[np.searchsorted(G.receive_ns,r['recognition_receive_ns'],side='right')-1]
 checks.append(all([pre.bid_raw==r['prebirth_quote']['bid'][0],pre.ask_raw==r['prebirth_quote']['ask'][0],pre.bid_size==r['prebirth_quote']['bid'][1],pre.ask_size==r['prebirth_quote']['ask'][1],rec.bid_raw==r['recognition_bid'][0],rec.ask_raw==r['recognition_ask'][0],rec.receive_ns==r['recognition_receive_ns']]))
assert all(checks)
print('Endpoint quote/source checks',len(checks),'of',len(rs),'figure panels',len(R))
print(pd.read_csv(ROOT/'tables/20231018-path-members.csv').groupby(['kind','orientation','move_orientation']).size().to_string())
