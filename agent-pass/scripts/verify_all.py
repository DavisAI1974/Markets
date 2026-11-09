"""Cross-artifact reconciliation and provenance checks; never a scientific acceptance gate."""
from common import *
DAYS=['20231002','20231003','20231017','20231018']
results=[]
for day in DAYS:
 C,rs=candidates(day);G=groups(day);M=pd.read_csv(ROOT/f'tables/{day}-path-members.csv',dtype={'anchor_ns':'int64','recognition_ns':'Int64'})
 X=pd.read_csv(ROOT/f'tables/{day}-paths.csv.gz',dtype={'cut_ns':'int64'},low_memory=False)
 assert C.candidate_id.nunique()==len(C)
 assert (M.kind=='candidate').sum()==C.recognition_ns.notna().sum()
 assert len(X)==M.path_rows.sum()
 assert not X.duplicated(['candidate_id','kind','relative_s']).any()
 assert X.groupby(['candidate_id','kind']).relative_s.min().eq(-60).all()
 # Every control inherits exactly the case duration and matching regime; independently check source activity buckets.
 grid=np.arange((G.receive_ns.iloc[0]//S+61)*S,(G.receive_ns.iloc[-1]//S-200)*S,S,dtype=np.int64)-1
 gr=G.receive_ns.to_numpy();ix=np.searchsorted(gr,grid,'right')-1
 ref=G.iloc[ix].copy();ref['age']=(grid-gr[ix])/S;ref['regime']=np.rint((ref.ask_raw-ref.bid_raw)/1e6).clip(0,3)
 cum=np.r_[0,np.cumsum(G.prints.to_numpy())]
 def activity(cuts):return cum[np.searchsorted(gr,cuts,'right')]-cum[np.searchsorted(gr,cuts-60*S,'right')]
 ref['activity']=activity(grid);ref=ref[ref.good&(ref.regime>0)&(ref.age<60)]
 edges={reg:np.quantile(z.activity,[.2,.4,.6,.8]) for reg,z in ref.groupby('regime')}
 metadata=[]
 for m in M.itertuples():
  p=G.iloc[np.searchsorted(gr,m.anchor_ns-1,'right')-1];reg=min(3,round((p.ask_raw-p.bid_raw)/1e6));act=activity(np.array([m.anchor_ns-1]))[0];bucket=np.searchsorted(edges[reg],act,'right')
  assert reg==m.regime and bucket==m.activity_bucket
  metadata.append(dict(candidate_id=m.candidate_id,kind=m.kind,anchor_ns=str(m.anchor_ns),actual_activity=act,actual_regime=reg,actual_activity_bucket=bucket))
 save(pd.DataFrame(metadata),f'{day}-matching-audit.csv')
 J=pd.read_csv(ROOT/f'tables/{day}-detector-all-comparisons.csv',dtype={'recovered_recognition_ns':str});J=J[J.variant=='native_action'].set_index('candidate_id')
 live=0
 for r in rs:
  if r.get('recognition_receive_ns') is not None:
   assert str(r['recognition_receive_ns'])==J.loc[r['candidate_id'],'recovered_recognition_ns'],r['candidate_id'];live+=1
  else:assert pd.isna(J.loc[r['candidate_id'],'recovered_recognition_ns'])
 for col in ['baseline','magnitude','prominence','threshold','observations_behind_threshold','searched_span_seconds']:
  assert np.allclose(J[col+'_recorded'],J[col+'_recovered'],rtol=0,atol=1e-12)
 panels=0
 for f in (ROOT/'tables').glob(f'{day}-*figure-reconciliation.csv'):
  Z=pd.read_csv(f);extra=Z.endpoint_points_in_companion.fillna(0) if 'endpoint_points_in_companion' in Z else 0
  assert (Z.rows_in==Z.points_plotted+Z.rows_excluded+extra).all(),f
  panels+=len(Z)
 L=pd.read_csv(ROOT/f'tables/{day}-life-measurements.csv');assert len(L)==len(M)
 assert (L.finite_adjacent_pairs==L.magnitude_increases+L.magnitude_decreases+L.magnitude_unchanged).all()
 assert L[L.disposition=='undefined_anchor_direction'].life_seconds.isna().all()
 P=pd.read_csv(ROOT/f'tables/{day}-life-paths.csv.gz');assert np.allclose(P.net_recurrence_residual,0,rtol=0,atol=1e-12)
 results.append(dict(day=day,candidates=len(C),exact_live_recognition_clocks=live,finalization_only=len(C)-live,path_rows=len(X),matched_path_anchors_checked=len(M),figure_panels=panels,life_transition_rows=len(P)))
print(pd.DataFrame(results).to_string(index=False));save(pd.DataFrame(results),'verification-summary.csv')
