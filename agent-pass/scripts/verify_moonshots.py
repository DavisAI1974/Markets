"""M1/M2 denominator checks, exact clock availability and raw-case lineage."""
from common import *
checks=[]
for day in ['20231002','20231003','20231017','20231018']:
    C,_=candidates(day);M=pd.read_csv(ROOT/f'tables/{day}-path-members.csv')
    E=pd.read_csv(ROOT/f'tables/{day}-detector-free-events.csv.gz',dtype={'receive_ns':'int64','raw_receive_ns':'Int64'})
    O=pd.read_csv(ROOT/f'tables/{day}-moonshot-summary.csv');F=pd.read_csv(ROOT/f'tables/{day}-first-footprint-events.csv');P=pd.read_csv(ROOT/f'tables/{day}-lag-footprints.csv');N=pd.read_csv(ROOT/f'tables/{day}-detector-free-nearest.csv')
    assert len(P)==len(M);assert len(F)==14*len(M);assert len(N)==3*len(C)
    assert not F.duplicated(['candidate_id','kind','event']).any()
    absent=F.disposition=='absent_within_lag'
    assert F.loc[absent,'first_s'].isna().all() and F.loc[absent,'groups'].eq(0).all()
    joined=F.merge(M[['candidate_id','kind','lag_s']],on=['candidate_id','kind'],validate='many_to_one')
    assert (joined.loc[~absent,'first_s']>=0).all()
    assert (joined.loc[~absent,'first_s']<=joined.loc[~absent,'lag_s']+1e-9).all()
    for row in O.itertuples():
        assert row.births==len(C)==row.birth_seconds_with_event+row.birth_seconds_without_event
        assert row.events==len(E[E.definition==row.definition])==row.events_in_birth_seconds+row.events_outside_birth_seconds
    Z=pd.read_csv(ROOT/f'tables/{day}-part3-figure-reconciliation.csv');assert (Z.rows_in==Z.points_plotted+Z.rows_excluded).all()
    cases=pd.read_csv(ROOT/f'tables/{day}-detector-free-cases.csv');raw=pd.read_csv(ROOT/f'tables/{day}-detector-free-case-records.csv.gz');assert cases.raw_records.sum()==len(raw)
    checks.append(dict(day=day,births=len(C),live_paths=int((M.kind=='candidate').sum()),paired_path_members=len(P),first_event_rows=len(F),definition_event_rows=len(E),nearest_event_rows=len(N),figure_panels=len(Z),case_records=len(raw)))
save(pd.DataFrame(checks),'moonshot-verification.csv');print(pd.DataFrame(checks).to_string(index=False))
