"""Readable per-instance cards from the checked saved observations and forecasts."""
import gzip,json,pathlib

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/sqlite-triage/20261022/families/instance-market-review-20261023'
CARDS=OUT/'cases';CARDS.mkdir(exist_ok=True)
MODELS=[('ridge100','Linear ridge'),('evotrees_depth3','Shallow trees'),('evotrees_depth5','Deeper trees'),('evotrees_mae','Median-loss trees'),('neural_tree','NeuralTree'),('residual_mlp','Residual MLP'),('tabm_ensemble','TabM'),('evotrees_q10','Lower quantile'),('evotrees_q90','Upper quantile')]

def number(v):
    if v is None or v=='':return 'unavailable'
    return f'{float(v):.6f}'

index=['# Individual family event records','',
       'Every retained first-family event appears in chronological order. These cards separate the strict pre-event observations and frozen held-out model forecasts from the subsequently observed endpoints. They are individual records, not completed causal explanations or executed trades.','',
       'Start with the [detailed instance 375 replay](instance-375-review.md). Its [next matching instance 391](cases/0391.md) is part of the same wider episode, with different subsequent price behavior. The [50 matching contexts](candidate-flow-transition-instances.csv) are a case-finding inventory, not independent signal validation.','',
       '| Instance | First observed UTC | Family | Recorded main and quantile forecasts |','|---:|---|---|---:|']
n=0
with gzip.open(OUT/'individual-instance-records.jsonl.gz','rt',encoding='utf-8') as stream:
    for line in stream:
        r=json.loads(line);n+=1;inst=r['instance'];measure={x['feature']:x for x in r['measurements']}
        forecasts={(x['outcome'],x['horizon_s'],x['model']):x for x in r['forecasts']}
        lines=[f'# Instance {inst} individual market record','',
               f"Family `{r['family_id']}` · instrument `{r['instrument_id']}` · first observed **{r['start_utc']}**.",'',
               f"[Previous instance]({inst-1:04d}.md)" if inst>1 else 'First chronological instance',
               f"[Next instance]({inst+1:04d}.md)" if inst<749 else 'Last chronological instance','',
               '## Strict pre-event observations','',
               f"Decision cutoff `{r['decision_cutoff_ns']}` receive nanoseconds; cursor cap `{r['cursor_cap']}`. Eligible completed-group source `{r['pre_source_ordinal']}` was known by `{r['pre_known_by_ns']}`, cursor `{r['pre_input_cursor']}`. The family group itself is excluded.",'',
               '| Measurement | Recorded value |','|---|---:|']
        for key,label in [('root.best_bid','Best bid'),('root.best_ask','Best ask'),('root.mid','Midquote'),('root.spread','Spread'),('root.bid_depth_full','Full bid size'),('root.ask_depth_full','Full ask size'),('root.depth_imbalance_n','Producer depth_n imbalance'),('root.depth_imbalance_full','Full-book imbalance')]:
            lines.append(f"| {label} | {number(measure.get(key,{}).get('value'))} |")
        lines+=['','| Pre-event rolling window | Buy-aggressor quantity | Sell-aggressor quantity |','|---:|---:|---:|']
        for h in [1,5,20,60,300]:
            buy=measure.get(f'root.activity.{h}.trade_buy_aggressor_qty',{}).get('value');sell=measure.get(f'root.activity.{h}.trade_sell_aggressor_qty',{}).get('value')
            lines.append(f'| {h} s | {number(buy)} | {number(sell)} |')
        lines+=['','These windows overlap. Values are the recorded quantities at the decision boundary; they do not identify the exact instant each pressure condition first became observable. Raw missingness/reasons and other contemporaneous measurements remain in the linked per-instance JSON and measurement ledger.','',
                '## Frozen forecasts and subsequently observed outcomes','']
        if not forecasts:
            lines+=['No saved held-out forecasts exist for this sample. The instance remains in the inventory; no in-sample or synthetic forecast is substituted.','']
        else:
            for outcome,title,horizons in [('mid_price_change','Signed endpoint midquote change',[1,5,20,60,120,300,600,1800,3600]),('absolute_mid_price_change','Absolute endpoint midquote change',[1,5,20,60,120,300,600,1800,3600]),('first_observed_family_within_h','Occurrence of any first-observed family for the instrument',[120,300,600])]:
                lines += ['### '+title,'', '| Perspective | '+' | '.join(f'{h} s' for h in horizons)+' |','|---|'+'---:|'*len(horizons)]
                observed=[]
                for h in horizons:
                    rows=[v for (o,hh,m),v in forecasts.items() if o==outcome and hh==h]
                    assert not rows or max(x['observed'] for x in rows)-min(x['observed'] for x in rows)<1e-12
                    observed.append(number(rows[0]['observed']) if rows else 'unavailable')
                lines.append('| **Observed later** | '+' | '.join(observed)+' |')
                for model,label in MODELS:
                    if not any((outcome,h,model) in forecasts for h in horizons):continue
                    values=[number(forecasts.get((outcome,h,model),{}).get('prediction')) for h in horizons]
                    lines.append('| '+label+' | '+' | '.join(values)+' |')
                lines.append('')
            folds=sorted({x['fold'] for x in r['forecasts']})
            lines+=['Recorded held-out fold(s): '+', '.join(map(str,folds))+'. Original training chronology, family purge and embargo remain unchanged. Observed endpoints are hindsight labels, not predictors. A missing horizon remains unavailable. Quantile forecasts describe separate tails rather than competing point estimates. Negative magnitude forecasts are preserved as invalid outputs, without clipping.','']
        lines+=['## Source and interpretation boundaries','',
                '[Chronological index](../chronological-instance-index.csv) · [All pre-event forecasts and removal refits](../all-pre-event-forecasts.csv.gz) · [Individual JSON records](../individual-instance-records.jsonl.gz) · [Pre-event measurements](../pre-event-measurements.csv.gz) · [Clock receipts](../pre-event-clock-receipts.csv)','',
                'This is a first-observed structural family event, not a demonstrated original order birth, causal intervention or filled trade. Averages can provide context; an entry condition requires instance-specific timing, confirmation and invalidation evidence. Semantic coverage remains NOT_PASSED and neural repeatability/domain caveats remain unresolved.','',
                '[Full consecutive replay and verified ladders for this instance](../instance-375-review.md).' if inst==375 else 'No dedicated complete consecutive book replay has been generated for this instance. Some nearby events overlap the saved window centered on instance 375; the card itself contains context observations and horizon endpoints, not an invented continuous path.']
        (CARDS/f'{inst:04d}.md').write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
        index.append(f"| [{inst}](cases/{inst:04d}.md) | {r['start_utc']} | `{r['family_id']}` | {len(forecasts)} |")
assert n==749
(OUT/'instance-by-instance.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
print(f'Wrote {n} separate instance cards and chronological navigation')
