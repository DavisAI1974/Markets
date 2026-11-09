"""Apply the supplied primer to retained evidence; no producer rerun."""
import numpy as np
import pandas as pd
from flow_book_discovery import HERE, NS, GROUPS, rows
from research_atlas import OUT, group_matrix, save, dump


def next_changes(a):
    result = np.full(len(a),-1,dtype=np.int64)
    for j in range(len(a)-2,-1,-1):
        if not a[j,7] or not a[j+1,7] or a[j,8] != a[j+1,8]:
            continue
        result[j] = j+1 if a[j,2] != a[j+1,2] else result[j+1]
    return result


def main(family=None, sensitivity_populations=None):
    a = group_matrix(rows(GROUPS))
    nexts = next_changes(a)
    if family is None:
        family = pd.read_csv(HERE/'flow-book-discovery-v1/opportunities.csv.gz',dtype={'anchor_ns':str})
    events = pd.read_csv(OUT/'aggression-to-rest-events.csv')
    anchors = [('family_prebirth',str(r.instance),int(r.anchor_ns)-1,int(r.pre_group))
               for r in family.itertuples() if pd.notna(r.pre_group)]
    anchors += [('aggression_to_rest',r.event_id,int(r.start_known_by_ns),int(r.start_group)) for r in events.itertuples()]
    records = []
    for population,ident,t,j in anchors:
        g = a[j]; spread = int(g[4]-g[3])
        imbalance = (g[5]-g[6])/(g[5]+g[6]) if g[5]+g[6] else np.nan
        regime = 'one_tick' if spread==1_000_000 else 'wider' if spread>1_000_000 else 'locked_or_other'
        windows = {'1ms':1_000_000,'5ms':5_000_000,'25ms':25_000_000,
                   '100ms':100_000_000,'250ms':250_000_000,'500ms':500_000_000,
                   '1s':NS,'5s':5*NS,'20s':20*NS}
        for horizon in ('next_change',*windows):
            k = int(nexts[j]) if horizon=='next_change' else int(np.searchsorted(a[:,0],t+windows[horizon],side='right'))-1
            valid = k>=0 and a[j,7] and a[k,7] and a[j,8]==a[k,8]
            if horizon=='next_change':valid = valid and a[k,0]>t
            else: valid = valid and t+windows[horizon]<=a[-1,0]
            change = (int(a[k,2])-int(g[2]))/(2*NS) if valid else None
            records.append(dict(population=population,case_id=ident,decision_ns=t,source_group=j,
                                source_cursor=int(g[1]),source_known_by_ns=int(g[0]),spread_raw=spread,
                                regime=regime,touch_imbalance=imbalance,
                                touch_sign='bid_heavy' if imbalance>0 else 'ask_heavy' if imbalance<0 else 'balanced',
                                horizon=horizon,disposition='available' if valid else 'boundary_or_no_later_change',
                                endpoint_group=k if valid else None,
                                elapsed_ns=int(a[k,0])-t if valid else None,
                                change=change))
    frame = pd.DataFrame(records)
    # Nullable coordinates are written from integers, without float conversion.
    for col in ('endpoint_group','elapsed_ns'):
        frame[col]=[str(r[col]) if r[col] is not None else '' for r in records]
    save('primer-spread-event-outcomes.csv.gz',frame)
    summary=[]
    for keys,g in frame.groupby(['population','regime','touch_sign','horizon']):
        v=g[g.disposition.eq('available')]
        summary.append(dict(zip(['population','regime','touch_sign','horizon'],keys),
                            n=len(g),available=len(v),up=int((v.change>0).sum()),
                            down=int((v.change<0).sum()),flat=int((v.change==0).sum()),
                            mean_change=v.change.mean(),
                            median_elapsed_ms=pd.to_numeric(v.elapsed_ns).median()/1e6))
    save('primer-spread-event-summary.csv',summary)
    pairs=pd.read_csv(OUT/'prebirth-matched-pairs.csv.gz')
    cases=pd.read_csv(OUT/'prebirth-cases.csv.gz',dtype={'quote_age_ns':str})
    sensitivities=[]
    for population,feature in (sensitivity_populations if sensitivity_populations is not None else [('family_start','total1'),('dipole_birth','displayed_lots')]):
        controls=pd.read_csv(OUT/f'prebirth-{population}-control-grid.csv.gz')
        for lead in (1,5,20,60):
            p=pairs[pairs.population.eq(population)&pairs.feature.eq(feature)&pairs.lead_s.eq(lead)].copy()
            c=cases[cases.population.eq(population)&cases.lead_s.eq(lead)]
            p=p.merge(c[['case_id','quote_age_ns']],on='case_id',validate='one_to_one')
            p=p.merge(controls[['decision_ns','quote_age_ns']],left_on='control_decision_ns',right_on='decision_ns',suffixes=('_case','_control'),validate='many_to_one')
            p['quote_age_ns_case']=pd.to_numeric(p.quote_age_ns_case)
            for label,g in [('all_matched',p),('both_quotes_at_most_1s',p[(p.quote_age_ns_case<=NS)&(p.quote_age_ns_control<=NS)])]:
                sensitivity=dict(population=population,feature=feature,lead_s=lead,scope=label,
                                 pairs=len(g),unique_controls=g.control_decision_ns.nunique(),
                                 mean_difference=g.difference.mean(),
                                 equal_control_weight_mean_difference=g.groupby('control_decision_ns').difference.mean().mean(),
                                 median_case_quote_age_ms=g.quote_age_ns_case.median()/1e6,
                                 median_control_quote_age_ms=g.quote_age_ns_control.median()/1e6)
                sensitivities.append(sensitivity)
    save('primer-prebirth-sensitivity.csv',sensitivities)
    dump('primer-application-method.json',dict(
        reference='User PDF SHA256 3a59306ef16814a525b85f08550a2f73cff63602cbbf6422693011c335f7e4dc',
        scope='October 18 retained evidence; all other dates remain discovery and await comparable final tables.',
        next_change='First different completed-group midpoint within same valid segment. Family decision is birth minus one nanosecond with the saved strict-pre quote; the birth group may be the next change. Remainder reference is initial completed-group close.',
        spread='Existing NG tick convention: raw 1000000 = 0.001; one tick versus wider, with other states retained separately.',
        sensitivity='Reweight each reused control equally, and separately require both case/control quote ages at most one second. Fixed diagnostic, not optimized threshold.',
        native_response_grid='Retain response horizons 1/5/25/100/250/500 ms and 1/5/20 s at native completed groups. This is descriptive response measurement, not a substitute for the established NG look-ahead calculation or a transfer revalidation.',
        limitations=['Selected populations, overlapping outcomes and variable event waits; no fitted predictor or out-of-sample claim.',
                     'Family prebirth selection is retrospective; a birth-group move cannot be credited to a trade after family recognition.',
                     'Comparison changes both target and denominator; available and flat counts retained.',
                     'Quote-age and reuse checks do not remove all matching/selection confounding.']))
    print(pd.DataFrame(sensitivities).to_string(index=False))


if __name__=='__main__':main()
