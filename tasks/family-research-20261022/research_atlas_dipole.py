"""Apply the existing information-dipole operator to retained October observations."""
import hashlib
import subprocess
import types
import numpy as np
import pandas as pd
from flow_book_discovery import REV, NS, HERE, GROUPS, rows
from research_atlas import OUT, OPEN, CLOSE, group_matrix, rolling_flow, save, dump


def flow_change_reason(buy, sell, expired_buy, expired_sell):
    fresh = buy + sell > 0
    expired = expired_buy + expired_sell > 0
    return ('fresh_and_expiry' if expired else 'fresh_only') if fresh else (
        'expiry_only' if expired else 'no_classified_change')


def half_activity(buy, sell):
    mid = len(buy)//2
    early = sum(buy[:mid])+sum(sell[:mid]) > 0
    late = sum(buy[mid:])+sum(sell[mid:]) > 0
    return 'both_active' if early and late else 'early_empty' if late else 'late_empty' if early else 'both_empty'


def main():
    raw = subprocess.check_output(['git','show',f'{REV}:odcore/info_dipole.py'])
    operator = types.ModuleType('retained_info_dipole')
    exec(compile(raw, 'pinned:odcore/info_dipole.py', 'exec'), operator.__dict__)
    (OUT/'sources/info_dipole_pinned.py').write_bytes(raw)
    groups=rows(GROUPS); matrix=group_matrix(groups)
    seconds=np.arange(OPEN//NS,CLOSE//NS,dtype=np.int64)
    buy,sell,unknown=(np.zeros(len(seconds)) for _ in range(3))
    for i,g in enumerate(groups):
        if not OPEN<=g['receive_ns']<CLOSE:continue
        k=g['receive_ns']//NS-seconds[0]
        for p in g['prints']:
            valid=i>0 and matrix[i-1,7] and matrix[i,7] and matrix[i-1,8]==matrix[i,8]
            delta=2*p['price_raw']-matrix[i-1,2] if valid else 0
            (buy if delta>0 else sell if delta<0 else unknown)[k]+=p['size']
    day=pd.DataFrame(dict(second=seconds,buy=buy,sell=sell,unknown=unknown,**rolling_flow(buy,sell)))
    save('dipole-completed-group-flow.csv.gz',day)
    seconds = day.second.to_numpy(dtype=np.int64)
    buy, sell = day.buy.to_numpy(), day.sell.to_numpy()
    candidates = rows('tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz')
    result, paths, events = [], [], []
    for c in candidates:
        birth, end = c['birth_second'], c['last_closed_second']
        # Birth labels are retrospective alignment only. No polarity is passed to the operator.
        anchors = [(f'prebirth_{lead}s',birth-lead-1,(birth-lead)*NS) for lead in (1,5,20,60)]
        anchors += [('recognition',end,c['recognition_receive_ns'])]
        for stage,second,decision in anchors:
            j = int(np.searchsorted(seconds,second))
            valid = j>=19 and j<len(seconds) and seconds[j]==second and seconds[j]-seconds[j-19]==19
            r = dict(candidate_id=c['candidate_id'],stage=stage,decision_ns=decision,
                     source_last_second=second,source_bin_closed_by_ns=(second+1)*NS,
                     input_disposition='available' if valid else 'boundary')
            if valid:
                b,s = buy[j-19:j+1],sell[j-19:j+1]
                feats = operator.signed_flow_features(b,s)
                r.update(buy_lots=int(sum(b)),sell_lots=int(sum(s)),
                         half_activity=half_activity(b,s),operator_defined=feats is not None)
                if feats is not None:r.update(feats)
                # Preserve original operator output, including its zero-valued empty half,
                # and attach activity flags rather than calling missing flow balance.
                if stage=='recognition':
                    w=c['last_closed_window']
                    r.update(saved_action_buy_lots=w.get('buy_lots',0),saved_action_sell_lots=w.get('sell_lots',0),
                             matches_saved_action_operands=(r['buy_lots']==w.get('buy_lots',0) and r['sell_lots']==w.get('sell_lots',0)))
                    assert r['source_bin_closed_by_ns']<=decision
            result.append(r)
        subset=day[(day.second>birth)&(day.second<=end)]
        counts=dict(weakening_seconds=0,undefined_after_defined_seconds=0,
                    weakening_expiry_only=0,weakening_fresh_only=0,weakening_fresh_and_expiry=0)
        for i in subset.index:
            if i<20:continue
            before,after=day.iloc[i-1].ratio,day.iloc[i].ratio
            weakening=np.isfinite(before) and np.isfinite(after) and abs(after)<abs(before)
            vanished=np.isfinite(before) and not np.isfinite(after)
            if not (weakening or vanished):continue
            reason=flow_change_reason(buy[i],sell[i],buy[i-20],sell[i-20])
            counts['weakening_seconds']+=int(weakening)
            counts['undefined_after_defined_seconds']+=int(vanished)
            if weakening:counts['weakening_'+reason]+=1
            paths.append(dict(candidate_id=c['candidate_id'],second=int(seconds[i]),
                              bin_closed_by_ns=int(seconds[i]+1)*NS,recognition_ns=c['recognition_receive_ns'],
                              transition='weakening' if weakening else 'became_undefined',reason=reason,
                              before_ratio=before,after_ratio=after,buy_lots=buy[i],sell_lots=sell[i],
                              expired_buy_lots=buy[i-20],expired_sell_lots=sell[i-20]))
        events.append(dict(candidate_id=c['candidate_id'],birth_second=birth,
                           recognition_ns=c['recognition_receive_ns'],
                           recognition_delay_s=(c['recognition_receive_ns']-birth*NS)/NS,
                           recognition_flow_state=c['birth_to_emission_flow_state'],**counts))
    features=pd.DataFrame(result); event_frame=pd.DataFrame(events)
    save('dipole-operator-observations.csv.gz',features)
    save('dipole-weakening-path.csv.gz',paths)
    save('dipole-weakening-events.csv',event_frame)
    outcome=pd.read_csv(HERE/'flow-book-discovery-v1/dipole-after-recognition.csv.gz')
    joined=outcome.merge(event_frame,on='candidate_id',validate='many_to_one',suffixes=('','_audit'))
    joined['weakening_mechanism']=np.where(joined.weakening_seconds.eq(0),'no_defined_weakening',
        np.where(joined.weakening_seconds.eq(joined.weakening_expiry_only),'expiry_only',
        np.where(joined.weakening_expiry_only.eq(0),'fresh_involved','mixed_path')))
    save('dipole-weakening-outcomes.csv.gz',joined)
    summary=[]
    for keys,g in joined.groupby(['weakening_mechanism','flow_state','horizon_s']):
        v=g[g.disposition.eq('available')]
        aligned=v.change*v.birth_polarity
        summary.append(dict(zip(['weakening_mechanism','flow_state','horizon_s'],keys),
                            n=len(g),available=len(v),same=int((aligned>0).sum()),
                            opposite=int((aligned<0).sum()),flat=int((aligned==0).sum())))
    save('dipole-weakening-summary.csv',summary)
    dump('dipole-application-method.json',dict(source_revision=REV,
         operator='odcore/info_dipole.py:signed_flow_features',operator_sha256=hashlib.sha256(raw).hexdigest(),
         populations={'dipoles':863,'observation_rows':len(features)},
         window_seconds=20,prebirth_leads_s=[1,5,20,60],
         application='Existing portable information-dipole operator applied unchanged; no revalidation of NG applicability.',
         flow_definition='Print price compared with the preceding valid completed-group midpoint; classified volume assigned to containing group close second. Unknown volume is retained separately. Companion observation lens, not the saved action-quote detector substrate.',
         clocks='Prebirth bins end by the strict decision cutoff; recognition uses the last closed bin in the saved candidate. Bin availability is an accounting boundary, not an upstream emission timestamp.',
         limits=['No crypto per-cell deployment thresholds imported.',
                 'Empty halves are explicitly flagged; C_signed uses original EPS regularization and is not a probability.',
                 'Birth-aligned paths are retrospective explanations; later birth polarity is outcome annotation only.',
                 'Overlapping dipoles can share weakening seconds. Report both event counts and unique seconds.',
                 'No A/B/C lineage mapping is asserted for these 863 reconstructed candidates; frozen runway classifier requires its original event contract.',
                 'Prebirth lead samples are descriptive comparisons, not a replacement for continuous NG timing.']))
    print(features.groupby(['stage','half_activity'],dropna=False).size().to_string())
    print(event_frame.drop(columns=['candidate_id','birth_second','recognition_ns','recognition_flow_state']).describe().to_string())


if __name__=='__main__':main()
