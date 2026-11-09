"""Independent reconciliation and provenance checks for additive shape descriptions."""
from common import *
P=pd.read_csv(ROOT/'tables/shape_forms-observations.csv',float_precision='round_trip')
M=pd.read_csv(ROOT/'tables/shape_forms-models.csv',float_precision='round_trip')
G=pd.read_csv(ROOT/'tables/shape_forms-fit-grid.csv',float_precision='round_trip')
R=pd.read_csv(ROOT/'tables/shape_forms-residuals.csv.gz',float_precision='round_trip')
assert len(P)==5085 and P.recognition_minus_event_s.notna().sum()==5079
assert not P.duplicated(['day','definition','candidate_id']).any()
for (day,definition),q in P.groupby(['day','definition']):
    source=pd.read_csv(ROOT/f'tables/{day}-detector-free-nearest.csv',float_precision='round_trip')
    source=source[(source.orientation=='SAME')&(source.definition==definition)].set_index('candidate_id')
    assert len(source)==len(q)
    assert np.allclose(q.recognition_minus_event_s,source.loc[q.candidate_id,'recognition_advantage_s'],rtol=0,atol=0,equal_nan=True)
    defined=q[q['rank'].notna()].sort_values('rank')
    assert np.array_equal(defined['rank'],np.arange(len(defined)))
    assert (np.diff(defined.recognition_minus_event_s)>=0).all()
    assert np.allclose(q.adjacent_gap_s,q.recognition_minus_event_s.diff(),rtol=0,atol=0,equal_nan=True)
    assert np.allclose(q.gap_change_s,q.recognition_minus_event_s.diff().diff(),rtol=0,atol=0,equal_nan=True)
assert len(M)==192
for m in M.itertuples():
    search=G[(G.source_day==m.source_day)&(G.definition==m.definition)&(G.section==m.section)&(G.form==m.form)&(G.status=='fitted')]
    if m.status=='fitted':assert m.total_absolute_residual==search.total_absolute_residual.min()
    else:assert len(search)==0
    q=R[R.model_id==m.model_id];valid=q.predicted_s.notna();x=q.loc[valid,'rank'].to_numpy();a,b=m.a,m.b
    if m.form=='line':pred=a+b*x
    elif m.form=='logarithm':pred=a+b*np.log(x+m.shift)
    elif m.form=='shifted_reciprocal':pred=a+b/(x+m.shift)
    else:pred=a+b*np.exp(-x/m.shift)
    assert np.allclose(q.loc[valid,'predicted_s'],pred,rtol=0,atol=1e-9)
    assert np.allclose(q.loc[valid,'residual_s'],pred-q.loc[valid,'observed_s'],rtol=0,atol=1e-9)
    inside=valid&q['rank'].between(m.rank_min,m.rank_max)
    assert (q.domain.eq('within_source_rank_domain')==inside).all()
    assert (q.domain.eq('out_of_source_rank_domain')==(valid&~inside)).all()
    own=q[(q.target_day==m.source_day)&(q.target_definition==m.definition)]
    if m.status=='fitted':assert np.isclose(own.residual_s.abs().sum(),m.total_absolute_residual,rtol=0,atol=1e-7)
    for day in [20231002,20231003,20231017,20231018]:
      for definition in q.target_definition.unique():
        expected=P[(P.day==day)&(P.definition==definition)]
        if m.section!='full':expected=expected[expected.section==m.section]
        actual=q[(q.target_day==day)&(q.target_definition==definition)]
        assert set(actual.candidate_id)==set(expected.candidate_id)
Q=pd.read_csv(ROOT/'tables/shape_forms-environment-pairs.csv',dtype={k:'Int64' for k in ['anchor_ns','paired_end_ns','first_event_ns','recognition_minus_event_ns']},float_precision='round_trip')
assert len(Q)==len(P)*3 and not Q.duplicated(['day','definition','candidate_id','kind']).any()
valid=Q.recognition_minus_event_ns.notna()
assert (Q.loc[valid,'recognition_minus_event_ns']==Q.loc[valid,'paired_end_ns']-Q.loc[valid,'first_event_ns']).all()
assert np.allclose(Q.loc[valid,'recognition_minus_event_s'],Q.loc[valid,'recognition_minus_event_ns'].astype(float)/S,rtol=0,atol=0)
c=Q[Q.kind=='candidate'].merge(P[['day','definition','candidate_id','recognition_minus_event_s']],on=['day','definition','candidate_id'],suffixes=('_environment','_original'),validate='one_to_one')
assert np.allclose(c.recognition_minus_event_s_environment,c.recognition_minus_event_s_original,rtol=0,atol=0,equal_nan=True)
for day,q in Q.groupby('day'):
    events=pd.read_csv(ROOT/f'tables/{day}-detector-free-events.csv.gz',usecols=['definition','receive_ns'])
    audit=pd.read_csv(ROOT/f'tables/{day}-matching-audit.csv')
    joined=q[q.actual_spread_bucket.notna()].merge(audit,on=['candidate_id','kind'],validate='many_to_one')
    assert np.array_equal(joined.actual_spread_bucket,joined.actual_regime)
    assert np.array_equal(joined.actual_activity_bucket_x,joined.actual_activity_bucket_y)
    assert np.array_equal(joined.trailing_60s_activity,joined.actual_activity)
    for definition,z in q.groupby('definition'):
        times=np.sort(events.loc[events.definition==definition,'receive_ns'].unique())
        for r in z[z.anchor_ns.notna()].itertuples():
            ix=np.searchsorted(times,int(r.anchor_ns),'left')
            if ix==len(times):assert pd.isna(r.first_event_ns)
            else:
                assert int(r.first_event_ns)==times[ix]
                assert times[ix]>=int(r.anchor_ns) and (ix==0 or times[ix-1]<int(r.anchor_ns))
K=pd.read_csv(ROOT/'tables/shape_forms-markers.csv',float_precision='round_trip')
assert len(K)==len(P)
for _,q in K.groupby(['day','definition']):
    gaps=q.adjacent_gap_s.to_numpy();maximum=np.zeros(len(q),dtype=bool);minimum=maximum.copy()
    for i in range(1,len(q)-1):
        a,b,c=gaps[i-1:i+2]
        if np.isfinite([a,b,c]).all():
            maximum[i]=b>=a and b>=c and (b>a or b>c)
            minimum[i]=b<=a and b<=c and (b<a or b<c)
    assert np.array_equal(maximum,q.local_gap_maximum)
    assert np.array_equal(minimum,q.local_gap_minimum)
D=pd.read_csv(ROOT/'tables/shape_forms-environment-contrasts.csv',float_precision='round_trip')
assert len(D)==2*len(P)
assert np.allclose(D.control_minus_candidate_lead_s,D.control_lead_s-D.candidate_lead_s,rtol=0,atol=0,equal_nan=True)
checks=dict(observation_rows=len(P),defined_observations=int(P.recognition_minus_event_s.notna().sum()),fit_models=len(M),fit_grid_rows=len(G),residual_rows=len(R),unavailable_residuals=int(R.residual_s.isna().sum()),outside_source_rank_domain=int(R.domain.eq('out_of_source_rank_domain').sum()),environment_rows=len(Q),paired_control_contrasts=len(D))
import scipy
source_inputs=[]
for day in [20231002,20231003,20231017,20231018]:
    for suffix in ['candidate-operands.csv','path-members.csv','matching-audit.csv','lag-footprints.csv','detector-free-events.csv.gz','detector-free-nearest.csv']:
        p=ROOT/f'tables/{day}-{suffix}'
        source_inputs.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
receipt=dict(**checks,versions=dict(scipy=scipy.__version__,numpy=np.__version__,pandas=pd.__version__),source_inputs=source_inputs)
(ROOT/'shape_forms-verification-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(checks))
