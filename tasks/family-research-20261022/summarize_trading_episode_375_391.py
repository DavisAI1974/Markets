"""Audit episode timing, lifecycle descriptions and rich saved context subsets."""
import csv
import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/sqlite-triage/20261022/families'
OUT = BASE / 'trading-episode-375-391'
CASES = {375:(1697634552081390598,303655),391:(1697634840878613141,319232)}
CLOCKS = ['source_ordinal','input_cursor','event_ns','receive_ns','known_by_ns']
q = pd.read_csv(BASE/'timestamped-mbo-window-v1/consecutive_quote_books.csv.gz',dtype={k:'int64' for k in CLOCKS})
qi = q.set_index('source_ordinal')


def save(rows, name):
    frame = rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    kw={'compression':{'method':'gzip','mtime':0}} if name.endswith('.gz') else {}
    frame.to_csv(OUT/name,index=False,**kw)


def point(ix,t):
    if ix is None:
        return None
    return {k:int(q.at[ix,k]) for k in CLOCKS}|{'relative_ns':int(q.at[ix,'known_by_ns'])-t,'mid':float(q.at[ix,'mid'])}


metrics=[]
for case,(t,cap) in CASES.items():
    pre=q[(q.known_by_ns<t)&(q.input_cursor<=cap)].iloc[-1].mid
    w=q[q.known_by_ns.between(t,t+300_000_000_000)]
    short=w[w.known_by_ns<=t+5_000_000_000]
    ix=short.mid.idxmin();low=short.mid.min();post=w.loc[ix:]
    record={'case_reference':case,'baseline':float(pre),
            'definition':'descriptive observed quote lifecycle; 5s local-low window and 300s follow-up chosen for this comparison, not validated trade segmentation',
            'first5s_low':point(ix,t),'first5s_downward_excursion':float(low-pre),
            '300s_min':point(w.mid.idxmin(),t),'300s_max':point(w.mid.idxmax(),t)}
    for key,price in [('half_recovery_after_low',low+(pre-low)/2),('baseline_recovery_after_low',pre),('above_baseline_by001',pre+.001)]:
        candidates=post[post.mid>=price-1e-12]
        record[key]=point(None if candidates.empty else candidates.index[0],t)
    metrics.append(record)
(OUT/'lifecycle-descriptions.json').write_text(json.dumps(metrics,indent=2)+'\n')

ledger=[]
facts=[
    (375,233365,'offer_growth_before_first_lower_quote','At fixed ask 3.156 size 8 to 13; bid 3.155 remains size5/2orders',233368,'597967ns before first lower-mid update; not an execution/causal identification'),
    (375,233366,'more_offer_growth_before_first_lower_quote','Ask3.156 size17/7orders; bid3.155 still5/2',233368,'455174ns before first lower-mid update; operational latency unmodeled'),
    (375,233368,'first_lower_quote_in_final_local_burst','Bid3.155 absent; bid3.154 ask3.156 midpoint3.1550',233368,'same-group price confirmation; no pre-move lead'),
    (375,233425,'strict_pre_reference','Bid3.152 size7/5orders; ask3.154 size25/14orders; 1s buy0 sell24',233426,'already 0.0025 below midpoint3.1555 preceding final burst; not pre-birth of that burst'),
    (391,244892,'pre_gap_bid_reappearance','Bid3.139 reappears size1/1order front_age0.000025977s',244934,'also a price recovery after prior decline; subsequent sharp drop falsifies sufficiency as exhaustion signal'),
    (391,244900,'second_pre_gap_bid_reappearance','Bid3.139 reappears again size1/1order',244934,'refresh observable before next drop; not proof that it will hold'),
    (391,244933,'strict_pre_reference','Bid3.139 size4/4orders; ask3.140 size3/3orders; 1s buy6 sell26',244934,'25.495931ms snapshot age at strict cutoff; future sharp drop remains unseen'),
    (391,244934,'sharp_gap_and_concentrated_offer','Bid3.136 ask3.137 midpoint3.1365; ask150 in1order; 1s buy6 sell76',244934,'known only at group close; offer age does not backdate availability; rolling-flow differences not interval executions'),
    (391,244969,'first5s_low_hindsight','Midpoint3.1355, 0.0040 below strict-pre',244969,'current low observable; its status as future 5s minimum is hindsight'),
    (391,245009,'post_drop_bid_reappearance','Bid3.136 reappears size6/1order front_age0.000041020s',245219,'after initial low; 172893878ns before ask3.137 disappears, but recovery already started'),
    (391,245213,'recovering_displayed_bid','Bid3.136 size23/9orders; ask3.137 size47/2orders',245219,'14494396ns before offer disappears; no fill/cancel split, no FIFO survival claim'),
    (391,245219,'offer_disappearance','Ask3.137 absent; best ask3.138; midpoint3.1370',245219,'price confirmation at this clock; disappearance is not identified execution'),
    (391,245220,'half_recovery','Midpoint3.1375; half of initial 0.0040 decline recovered',245220,'description of current price response; not known before initial decline'),
    (391,245460,'baseline_recovery','Midpoint3.1395 returns to strict-pre baseline',245460,'first return after chosen low; later persistence/end not known'),
    (375,235704,'baseline_recovery','Midpoint3.1530 returns to strict-pre baseline',235704,'counterevidence to uninterrupted momentum; later renewed decline remains separate evidence'),
]
for case,ordinal,kind,fact,ref,qualification in facts:
    t,cap=CASES[case]
    row={k:int(qi.at[ordinal,k]) for k in CLOCKS if k!='source_ordinal'}
    row.update(case_reference=case,source_ordinal=ordinal,relative_known_by_ns=row['known_by_ns']-t,
               comparison_move_ordinal=ref,comparison_move_known_by_ns=int(qi.at[ref,'known_by_ns']),
               lead_to_comparison_move_ns=int(qi.at[ref,'known_by_ns'])-row['known_by_ns'],
               strict_pre_cutoff_ns=t-1,strict_pre_cursor_cap=cap,
               eligible_before_family_reference=(row['known_by_ns']<=t-1 and row['input_cursor']<=cap),
               observation=kind,fact=fact,qualification=qualification,
               counterevidence='391 refresh preceded another drop; 375 later recovered baseline; both have later declines',
               candidate_falsification='Observed next loss of fixed-price support, renewed lower offers or failed recovery contradicts a sustained-hold hypothesis',
               source='consecutive_quote_books plus nearby-queues-and-fixed-prices; rolling flow from saved context',
               model_consumption='only original sample forecasts saved; no model at every ledger timestamp',
               operational_executability='not simulated; no processing/fill/fee/slippage claim')
    ledger.append(row)
save(ledger,'availability-evidence-ledger.csv')

for f in ['external_asof.csv.gz','features.csv.gz','group_measurements.csv.gz']:
    with gzip.open(BASE/'descriptive-v1'/f,'rt',newline='') as h:
        rows=[r for r in csv.DictReader(h) if r['sample_id'].split(':')[0] in ['375','391']]
    save(rows,'episode-'+f)
with (OUT/'saved-context-clock-receipts.csv').open(newline='') as h:
    cutoffs={r['sample_id']:int(r['cutoff_ns']) for r in csv.DictReader(h) if r['lag_s']=='0'}
with gzip.open(OUT/'episode-external_asof.csv.gz','rt',newline='') as h:
    external=list(csv.DictReader(h))
assert all(int(r['published_ns'])<=cutoffs[r['sample_id']] for r in external if r['published_ns'])

pred=pd.read_csv(OUT/'original-all-model-forecasts.csv.gz',dtype=str,keep_default_na=False)
matches=0
for case,(t,cap) in CASES.items():
    p=pred[pred.instance.eq(str(case))]
    assert p.cutoff_ns.eq(str(t-1)).all() and p.cursor_cap.eq(str(cap)).all()
    source=pd.read_csv(BASE/f'instance-market-review-20261023/instance-{case}-all-model-forecasts.csv',dtype=str,keep_default_na=False)
    pd.testing.assert_frame_equal(p.reset_index(drop=True),source.reset_index(drop=True))
    for horizon in [1,5,20,60,120,300]+([600] if case==375 else []):
        eligible=q[q.known_by_ns<=t+horizon*1_000_000_000];ix=eligible.index[-1]
        base=q[(q.known_by_ns<t)&(q.input_cursor<=cap)].mid.iloc[-1]
        observed=p[p.outcome.eq('mid_price_change')&p.horizon_s.eq(str(horizon))].observed.astype(float)
        assert len(observed)>0 and (observed-(q.at[ix,'mid']-base)).abs().max()<1e-12
        matches+=1

# Audit the saved CSV text itself, guarding against accidental clock float coercion.
for filename in ['checkpoints.csv','touch-queue-checkpoints.csv','availability-evidence-ledger.csv','price-step-timeline.csv']:
    with (OUT/filename).open(newline='') as h:
        for row in csv.DictReader(h):
            if row.get('source_ordinal','')=='': continue
            ordinal=int(row['source_ordinal'])
            for k in CLOCKS:
                assert row[k]==str(int(qi.at[ordinal,k]) if k!='source_ordinal' else ordinal),(filename,k,row[k])

receipt=json.loads((OUT/'verification-receipt.json').read_text())
receipt.update(saved_csv_clock_strings_match_integer_source=True,original_case_forecasts_unchanged=True,
               matched_quote_label_endpoints=matches,external_publication_cutoffs_checked=len(external),
               lifecycle_definitions='5s local low and 300s followup are retrospective descriptions, not trade entries/exits',
               richer_source_coverage='15899 native/root context rows plus complete selected descriptive and second-group projections; not full 1.15million-column semantic certification')
(OUT/'verification-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Lifecycle, availability, exact CSV clocks, frozen forecasts and external cutoffs verified')
