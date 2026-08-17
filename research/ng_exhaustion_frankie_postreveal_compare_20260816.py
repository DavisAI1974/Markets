#!/usr/bin/env python3
"""Legal post-freeze reveal/scoring for Frankie's NG exhaustion blind curves.

This script may be run only after the immutable blind prediction freeze commit exists.
It verifies the frozen shards, maps them back to the reconstructed holdout blind records,
then opens the held-out actual MBP10 price paths and retrospective ZigZag outcomes.
It never refits or changes the frozen A classifier or any Frankie/brain/schema rule.
"""
from __future__ import annotations

import gzip, hashlib, html, json, math, sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from ng_dipole_runway_audit import load_day, zigzag_legs

TICK = 0.001
FREEZE_COMMIT = '0f26c125548c801037bb3084d23b1b5d974ae0eb'
FREEZE_DIR = Path('research/blind_freeze/ng_exhaustion_20260816')
FREEZE_MANIFEST = FREEZE_DIR / 'FRANKIE_NG_EXHAUSTION_BLIND_PREDICTION_FREEZE_MANIFEST_20260816.json'
BLIND_RECORDS = Path('ng_frankie_blind_records.json')
OUT = Path('research/blind_reveal/ng_exhaustion_20260816')
SCALES = ('3t','5t','8t','13t')
THRESH = {'3t':3,'5t':5,'8t':8,'13t':13}
GROUPS = ('A-persistent','A-fast-collapse','B','C')


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def finite(x):
    return math.isfinite(float(x))


def median(xs):
    a=[float(x) for x in xs if x is not None and finite(x)]
    return float(np.median(a)) if a else None


def mean(xs):
    a=[float(x) for x in xs if x is not None and finite(x)]
    return float(np.mean(a)) if a else None


def rate(xs):
    a=[bool(x) for x in xs if x is not None]
    return float(np.mean(a)) if a else None


def corr(x,y):
    x=np.asarray(x,float); y=np.asarray(y,float)
    m=np.isfinite(x)&np.isfinite(y)
    if m.sum()<5: return None
    x=x[m]; y=y[m]
    if np.std(x)<1e-12 or np.std(y)<1e-12: return None
    return float(np.corrcoef(x,y)[0,1])


def containing_or_near(legs,t0):
    inside=[x for x in legs if x['start']<=t0<=x['end']]
    if inside: return min(inside,key=lambda x:x['end']-x['start'])
    if not legs: return None
    x=min(legs,key=lambda y:abs(y['start']-t0))
    return x if abs(x['start']-t0)<=15 else None


def read_predictions():
    man=json.loads(FREEZE_MANIFEST.read_text())
    if man.get('status')!='FROZEN_BLIND_PREDICTIONS_PENDING_REVEAL':
        raise SystemExit('freeze manifest status is not pending reveal')
    if man.get('prediction_n')!=1711 or man.get('outcome_accessed_before_freeze') is not False:
        raise SystemExit('freeze manifest prediction/outcome invariant failed')
    if man.get('single_best_curve_only') is not True or man.get('uncertainty_bands') is not False:
        raise SystemExit('single-best-curve invariant failed')
    preds=[]
    for name,meta in sorted(man['shards'].items()):
        path=FREEZE_DIR/name
        raw=path.read_bytes()
        if sha256_bytes(raw)!=meta['sha256']:
            raise SystemExit(f'frozen shard hash drift: {name}')
        data=gzip.decompress(raw)
        if sha256_bytes(data)!=meta['uncompressed_sha256']:
            raise SystemExit(f'frozen shard uncompressed hash drift: {name}')
        rows=[json.loads(x) for x in data.decode().splitlines() if x.strip()]
        if len(rows)!=meta['records']:
            raise SystemExit(f'frozen shard record count drift: {name}')
        preds.extend(rows)
    if len(preds)!=1711 or len({p['blind_id'] for p in preds})!=1711:
        raise SystemExit('frozen prediction coverage drift')
    for p in preds:
        if p.get('outcome_accessed') is not False:
            raise SystemExit('a frozen prediction says outcome_accessed != false')
        if any(any(str(k).lower().startswith(('p25','p50','p75')) for k in n) for n in p['best_price_curve']):
            raise SystemExit('probability band field found in frozen single-best curve')
    return man,preds


def pred_group(p):
    if p['family']=='A': return p['post_state']
    return p['family']


def pred_at(p,sec):
    xs=np.asarray([n['seconds_from_t0'] for n in p['best_price_curve']],float)
    ys=np.asarray([n['forecast_price'] for n in p['best_price_curve']],float)
    return float(np.interp(float(sec),xs,ys))


def sign_tick(px,anchor,min_tick=.5):
    d=(float(px)-float(anchor))/TICK
    if d>min_tick: return 1
    if d<-min_tick: return -1
    return 0


def early_pred_turn(p,max_sec=300):
    nodes=p['best_price_curve']
    if len(nodes)<3: return None,None
    ys=np.asarray([n['forecast_price'] for n in nodes],float)
    xs=np.asarray([n['seconds_from_t0'] for n in nodes],float)
    dy=np.diff(ys)
    s=[]
    for v in dy:
        if abs(v)<0.25*TICK: s.append(0)
        else: s.append(1 if v>0 else -1)
    last=0
    for i,sg in enumerate(s):
        if sg==0: continue
        if last and sg!=last:
            t=int(xs[i])
            return (t,last) if t<=max_sec else (None,None)
        last=sg
    return None,None


def actual_early_extreme(day,t0,initial_sign,max_sec=300):
    hi=min(86399,t0+max_sec)
    if hi<=t0 or initial_sign not in (-1,1): return None
    a=np.asarray(day.price[t0:hi+1],float)
    if not len(a) or not finite(a[0]): return None
    disp=initial_sign*(a-a[0])
    disp[~np.isfinite(disp)]=-np.inf
    j=int(np.argmax(disp))
    return j if np.isfinite(disp[j]) else None


def curve_metrics(p,day):
    anchor=float(p['price_anchor']); t0=int(p['t0_second_utc']); horizon=int(p['best_price_curve'][-1]['seconds_from_t0'])
    horizon=max(1,min(horizon,86399-t0))
    step=max(1,int(math.ceil(horizon/900)))
    grid=np.arange(0,horizon+1,step,dtype=int)
    if grid[-1]!=horizon: grid=np.r_[grid,horizon]
    actual=np.asarray([day.price[t0+int(s)] for s in grid],float)
    px=np.asarray([pred_at(p,int(s)) for s in grid],float)
    m=np.isfinite(actual)&np.isfinite(px)
    if m.sum()<2:
        return {'curve_horizon_s':horizon,'curve_rmse_ticks':None,'curve_mae_ticks':None,'curve_corr':None,'path_sign_agreement':None,'pred_peak_ticks':None,'actual_peak_ticks':None,'terminal_error_ticks':None}
    ae=(px[m]-actual[m])/TICK
    pred_disp=(px[m]-anchor)/TICK; act_disp=(actual[m]-anchor)/TICK
    sig=(np.abs(pred_disp)>=.5)&(np.abs(act_disp)>=.5)
    sign_agree=float(np.mean(np.sign(pred_disp[sig])==np.sign(act_disp[sig]))) if sig.any() else None
    turn_t,initial_sign=early_pred_turn(p)
    actual_turn=actual_early_extreme(day,t0,initial_sign) if turn_t is not None else None
    return {
      'curve_horizon_s':horizon,
      'curve_rmse_ticks':float(np.sqrt(np.mean(ae*ae))),
      'curve_mae_ticks':float(np.mean(np.abs(ae))),
      'curve_corr':corr(pred_disp,act_disp),
      'path_sign_agreement':sign_agree,
      'pred_peak_ticks':float(np.max(np.abs(pred_disp))),
      'actual_peak_ticks':float(np.max(np.abs(act_disp))),
      'terminal_error_ticks':float((px[m][-1]-actual[m][-1])/TICK),
      'pred_early_turn_s':turn_t,
      'actual_early_extreme_s':actual_turn,
      'early_turn_abs_error_s':(abs(turn_t-actual_turn) if turn_t is not None and actual_turn is not None else None),
    }


def leg_metrics(p,day,leg_cache):
    t0=int(p['t0_second_utc']); anchor=float(p['price_anchor']); pol=int(p['_dipole_polarity'])
    out={}
    for scale in SCALES:
        L=containing_or_near(leg_cache[THRESH[scale]],t0)
        pred_dur=int(p['predicted_duration_s'][scale])
        pred_px=pred_at(p,pred_dur); pred_dir=sign_tick(pred_px,anchor)
        if L is None:
            out[scale]={'actual_leg':None,'predicted_duration_s':pred_dur,'predicted_direction':pred_dir}
            continue
        actual_dir=int(L['dir'])
        out[scale]={
          'actual_leg':{'start_offset_s':int(L['start'])-t0,'end_offset_s':int(L['end'])-t0,'duration_s':int(L['duration']),'direction':actual_dir,'ticks':float(L['ticks'])},
          'predicted_duration_s':pred_dur,
          'duration_abs_error_s':abs(pred_dur-int(L['duration'])),
          'predicted_direction':pred_dir,
          'prediction_direction_hit':(pred_dir==actual_dir if pred_dir else None),
          'actual_alignment_with_dipole':actual_dir==pol,
        }
    return out


def downsample_actual(day,t0,horizon,n=300):
    horizon=max(1,min(int(horizon),86399-t0))
    xs=np.unique(np.rint(np.linspace(0,horizon,min(n,horizon+1))).astype(int))
    ys=[day.price[t0+int(s)] for s in xs]
    return [(int(s),float(y)) for s,y in zip(xs,ys) if finite(y)]


def svg_poly(points,x0,y0,w,h,xmax,ymin,ymax):
    if not points or xmax<=0 or ymax<=ymin: return ''
    out=[]
    for x,y in points:
        sx=x0+w*(float(x)/xmax)
        sy=y0+h*(1-(float(y)-ymin)/(ymax-ymin))
        out.append(f'{sx:.1f},{sy:.1f}')
    return ' '.join(out)


def write_html_gallery(day,metrics,day_obj):
    cards=[]
    for m in metrics:
        p=m['_prediction']; t0=int(p['t0_second_utc']); anchor=float(p['price_anchor']); horizon=int(m['curve_horizon_s'])
        act=[(s,(px-anchor)/TICK) for s,px in downsample_actual(day_obj,t0,horizon,260)]
        pred=[(int(n['seconds_from_t0']),(float(n['forecast_price'])-anchor)/TICK) for n in p['best_price_curve'] if int(n['seconds_from_t0'])<=horizon]
        vals=[y for _,y in act+pred] or [0]
        ymin=min(vals)-1; ymax=max(vals)+1
        if ymax-ymin<4: ymin-=2; ymax+=2
        W,H=560,230; x0,y0,w,h=46,18,494,172
        ap=svg_poly(act,x0,y0,w,h,horizon,ymin,ymax); pp=svg_poly(pred,x0,y0,w,h,horizon,ymin,ymax)
        title=f"{html.escape(p['blind_id'])} | {pred_group(p)} | t0={t0} | anchor={anchor:.3f}"
        info=f"RMSE={m['curve_rmse_ticks']:.2f}t" if m.get('curve_rmse_ticks') is not None else 'RMSE=n/a'
        c=f'''<div class="card"><div class="ttl">{title}</div><svg viewBox="0 0 {W} {H}" role="img">
<line x1="{x0}" y1="{y0+h}" x2="{x0+w}" y2="{y0+h}" stroke="#aaa"/><line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0+h}" stroke="#aaa"/>
<polyline points="{ap}" fill="none" stroke="#111" stroke-width="1.3"/><polyline points="{pp}" fill="none" stroke="#1f77b4" stroke-width="2.0" stroke-dasharray="5 3"/>
<text x="{x0}" y="{H-12}" font-size="11">0s</text><text x="{x0+w-35}" y="{H-12}" font-size="11">{horizon}s</text>
<text x="{x0+4}" y="{y0+12}" font-size="10">{ymax:.1f}t</text><text x="{x0+4}" y="{y0+h-4}" font-size="10">{ymin:.1f}t</text>
</svg><div class="meta">Actual solid black; Frankie dashed blue. {info}; corr={m.get('curve_corr') if m.get('curve_corr') is not None else 'n/a'}</div></div>'''
        cards.append(c)
    doc=f'''<!doctype html><meta charset="utf-8"><title>Frankie vs actual {day}</title><style>
body{{font-family:Arial,sans-serif;margin:16px;background:#fafafa}}h1{{font-size:22px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(560px,1fr));gap:12px}}.card{{background:white;border:1px solid #ddd;padding:8px}}.ttl{{font-weight:700;font-size:13px}}.meta{{font-size:11px;color:#444}}svg{{width:100%;height:auto}}
</style><h1>Frankie blind forecast vs held-out actual — {day}</h1><p>Each chart is event-relative ticks from the legal t0 price anchor. Actual is solid black; Frankie's frozen single-best curve is dashed blue.</p><div class="grid">{''.join(cards)}</div>'''
    (OUT/f'frankie_vs_actual_all_{day}.html').write_text(doc,encoding='utf-8')


def group_summary(rows,group):
    rr=[r for r in rows if r['group']==group]
    return {
      'n':len(rr),
      'median_curve_rmse_ticks':median(r['curve_rmse_ticks'] for r in rr),
      'median_curve_mae_ticks':median(r['curve_mae_ticks'] for r in rr),
      'median_curve_corr':median(r['curve_corr'] for r in rr),
      'mean_path_sign_agreement':mean(r['path_sign_agreement'] for r in rr),
      'median_pred_peak_ticks':median(r['pred_peak_ticks'] for r in rr),
      'median_actual_peak_ticks':median(r['actual_peak_ticks'] for r in rr),
      'median_early_turn_abs_error_s':median(r.get('early_turn_abs_error_s') for r in rr),
    }


def scale_summary(rows,group,scale):
    rr=[]
    for r in rows:
        if r['group']!=group: continue
        x=r['legs'][scale]
        if x.get('actual_leg') is not None: rr.append(x)
    return {
      'n':len(rr),
      'predicted_duration_median_s':median(x['predicted_duration_s'] for x in rr),
      'actual_duration_median_s':median(x['actual_leg']['duration_s'] for x in rr),
      'duration_mae_median_s':median(x.get('duration_abs_error_s') for x in rr),
      'predicted_direction_coverage':(sum(x.get('predicted_direction',0)!=0 for x in rr)/len(rr) if rr else None),
      'prediction_direction_hit_rate':rate(x.get('prediction_direction_hit') for x in rr),
      'actual_alignment_with_dipole_rate':rate(x.get('actual_alignment_with_dipole') for x in rr),
      'actual_leg_ticks_median':median(x['actual_leg']['ticks'] for x in rr),
    }


def make_group_curves(rows,days):
    fig,axs=plt.subplots(2,2,figsize=(14,9),constrained_layout=True)
    for ax,g in zip(axs.flat,GROUPS):
        rr=[r for r in rows if r['group']==g]
        if not rr: continue
        h=int(median(r['curve_horizon_s'] for r in rr) or 1)
        h=max(60,h)
        grid=np.unique(np.rint(np.linspace(0,h,240)).astype(int))
        preds=[]; acts=[]
        for r in rr:
            p=r['_prediction']; d=days[p['day']]; t0=int(p['t0_second_utc']); a=float(p['price_anchor'])
            maxh=min(int(p['best_price_curve'][-1]['seconds_from_t0']),86399-t0)
            if grid[-1]>maxh: continue
            preds.append([(pred_at(p,int(s))-a)/TICK for s in grid])
            acts.append([(d.price[t0+int(s)]-a)/TICK for s in grid])
        if preds and acts:
            pm=np.nanmedian(np.asarray(preds,float),axis=0); am=np.nanmedian(np.asarray(acts,float),axis=0)
            ax.plot(grid,am,label='Held-out actual median',linewidth=2)
            ax.plot(grid,pm,label='Frankie frozen forecast median',linewidth=2,linestyle='--')
        ax.axhline(0,linewidth=.8)
        ax.set_title(f'{g} (n={len(rr)})')
        ax.set_xlabel('seconds from t0'); ax.set_ylabel('ticks from t0 anchor'); ax.legend(fontsize=8)
    fig.suptitle('Frankie blind single-best curves vs held-out actual — group medians',fontsize=15)
    fig.savefig(OUT/'frankie_vs_actual_group_curves.png',dpi=170); plt.close(fig)


def choose_examples(rows):
    picked=[]
    for g in GROUPS:
        rr=[r for r in rows if r['group']==g and r.get('curve_rmse_ticks') is not None]
        rr=sorted(rr,key=lambda r:r['curve_rmse_ticks'])
        if not rr: continue
        picked.extend([(g,'best',rr[0]),(g,'median',rr[len(rr)//2]),(g,'worst',rr[-1])])
    return picked


def make_examples(rows,days):
    ex=choose_examples(rows)
    fig,axs=plt.subplots(3,4,figsize=(18,11),constrained_layout=True)
    for ax,item in zip(axs.flat,ex):
        g,label,r=item; p=r['_prediction']; d=days[p['day']]; t0=int(p['t0_second_utc']); h=int(r['curve_horizon_s'])
        step=max(1,int(math.ceil(h/600))); x=np.arange(0,h+1,step,dtype=int); actual=np.asarray([d.price[t0+int(s)] for s in x],float)
        pn=p['best_price_curve']; xp=[n['seconds_from_t0'] for n in pn]; yp=[n['forecast_price'] for n in pn]
        ax.plot(x,actual,label='actual',linewidth=1.3); ax.plot(xp,yp,label='Frankie',linewidth=2,linestyle='--')
        ax.set_title(f"{g} {label}\n{p['day']} {p['blind_id']} RMSE={r['curve_rmse_ticks']:.1f}t",fontsize=9)
        ax.set_xlabel('seconds from t0'); ax.set_ylabel('price'); ax.legend(fontsize=7)
    for ax in axs.flat[len(ex):]: ax.axis('off')
    fig.suptitle('Frankie blind forecast vs held-out actual — best / median / worst curve fit by group',fontsize=15)
    fig.savefig(OUT/'frankie_vs_actual_examples.png',dpi=160); plt.close(fig)


def make_summary_figure(summary):
    fig,axs=plt.subplots(2,2,figsize=(14,10),constrained_layout=True)
    ax=axs[0,0]; x=np.arange(len(SCALES)); w=.35
    pf=[summary['duration_by_group_scale']['A-persistent'][s]['actual_duration_median_s'] for s in SCALES]
    ff=[summary['duration_by_group_scale']['A-fast-collapse'][s]['actual_duration_median_s'] for s in SCALES]
    ax.bar(x-w/2,pf,w,label='A-persistent actual'); ax.bar(x+w/2,ff,w,label='A-fast-collapse actual')
    ax.set_xticks(x,SCALES); ax.set_ylabel('median actual leg duration (s)'); ax.set_title('Held-out A runway split'); ax.legend(fontsize=8)

    ax=axs[0,1]
    for g in ('B','C'):
        vals=[summary['duration_by_group_scale'][g][s]['actual_alignment_with_dipole_rate'] for s in SCALES]
        ax.plot(SCALES,vals,marker='o',label=f'{g} held-out')
    ax.set_ylim(0,1); ax.set_ylabel('actual alignment with dipole'); ax.set_title('Held-out B locality / C scale transition'); ax.legend(fontsize=8)

    ax=axs[1,0]; gs=list(GROUPS); vals=[summary['by_group'][g]['median_curve_rmse_ticks'] for g in gs]
    ax.bar(gs,vals); ax.set_ylabel('median curve RMSE (ticks)'); ax.set_title('Full-curve forecast error'); ax.tick_params(axis='x',rotation=20)

    ax=axs[1,1]; bins=summary['microstructure']['support_bins']; labels=list(bins); vals=[bins[k]['8t_actual_alignment_rate'] for k in labels]; ns=[bins[k]['n'] for k in labels]
    ax.bar(labels,[0 if v is None else v for v in vals]); ax.set_ylim(0,1); ax.set_ylabel('8t actual alignment with dipole'); ax.set_title('Frozen legal microstructure support vs held-out 8t')
    for i,(v,n) in enumerate(zip(vals,ns)):
        if v is not None: ax.text(i,v+.02,f'n={n}',ha='center',fontsize=8)
    fig.suptitle('Frankie NG exhaustion blind post-reveal summary',fontsize=15)
    fig.savefig(OUT/'frankie_postreveal_summary.png',dpi=170); plt.close(fig)


def main(paths):
    OUT.mkdir(parents=True,exist_ok=True)
    freeze,preds=read_predictions()
    blind=json.loads(BLIND_RECORDS.read_text())
    bmap={r['blind_id']:r for r in blind}
    if len(bmap)!=1711 or set(bmap)!={p['blind_id'] for p in preds}:
        raise SystemExit('reconstructed holdout blind-id set does not exactly match frozen predictions')
    for p in preds:
        b=bmap[p['blind_id']]
        if p['family']!=b['family'] or p['day']!=b['day'] or int(p['t0_second_utc'])!=int(b['t0_second_utc']): raise SystemExit('blind identity mapping drift')
        if abs(float(p['price_anchor'])-float(b['causal_price_anchor']['value']))>1e-12: raise SystemExit('t0 anchor drift')
        if p['family']=='A' and p['post_state']!=b['frozen_post_state_assignment']['label']: raise SystemExit('frozen A classifier assignment drift')
        p['_dipole_polarity']=int(b['dipole_polarity'])

    days={}
    for path in paths:
        d=load_day(path); days[d.day]=d
    if set(days)!={'20250717','20250923','20250930','20251001'}: raise SystemExit('actual day set drift')
    legs={day:{th:zigzag_legs(obj.price,th) for th in THRESH.values()} for day,obj in days.items()}

    rows=[]
    byday=defaultdict(list)
    event_dump=[]
    for p in preds:
        d=days[p['day']]
        cm=curve_metrics(p,d); lm=leg_metrics(p,d,legs[p['day']]); g=pred_group(p)
        r={'blind_id':p['blind_id'],'day':p['day'],'family':p['family'],'group':g,'post_state':p['post_state'],'t0_second_utc':p['t0_second_utc'],'price_anchor':p['price_anchor'],'dipole_polarity':p['_dipole_polarity'],'microstructure_support':p['microstructure_read']['oriented_support_score'],'microstructure_class':p['microstructure_read']['classification'],'legs':lm,**cm,'_prediction':p}
        rows.append(r); byday[p['day']].append(r)
        event_dump.append({k:v for k,v in r.items() if k!='_prediction'})

    raw=''.join(json.dumps(x,separators=(',',':'),sort_keys=True)+'\n' for x in event_dump).encode()
    (OUT/'postreveal_event_metrics.jsonl.gz').write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))

    by_group={g:group_summary(rows,g) for g in GROUPS}
    duration={g:{s:scale_summary(rows,g,s) for s in SCALES} for g in GROUPS}
    a_order={}
    for s in SCALES:
        p=duration['A-persistent'][s]['actual_duration_median_s']; f=duration['A-fast-collapse'][s]['actual_duration_median_s']
        days_pass={}
        for day in sorted(days):
            pp=[r['legs'][s]['actual_leg']['duration_s'] for r in rows if r['group']=='A-persistent' and r['day']==day and r['legs'][s].get('actual_leg')]
            ff=[r['legs'][s]['actual_leg']['duration_s'] for r in rows if r['group']=='A-fast-collapse' and r['day']==day and r['legs'][s].get('actual_leg')]
            mp=median(pp); mf=median(ff); days_pass[day]={'persistent_median_s':mp,'fast_median_s':mf,'persistent_gt_fast':(mp>mf if mp is not None and mf is not None else None)}
        a_order[s]={'persistent_median_s':p,'fast_median_s':f,'persistent_gt_fast':(p>f if p is not None and f is not None else None),'by_day':days_pass,'days_pass':sum(v['persistent_gt_fast'] is True for v in days_pass.values())}

    micro={}
    bins={'opposite':(-2,-.15),'mixed':(-.15,.15),'same_side':(.15,2)}
    for name,(lo,hi) in bins.items():
        rr=[r for r in rows if lo<=r['microstructure_support']<hi]
        micro[name]={'n':len(rr),'8t_actual_alignment_rate':rate(r['legs']['8t'].get('actual_alignment_with_dipole') for r in rr if r['legs']['8t'].get('actual_leg')),'median_curve_rmse_ticks':median(r['curve_rmse_ticks'] for r in rr),'median_8t_duration_s':median(r['legs']['8t']['actual_leg']['duration_s'] for r in rr if r['legs']['8t'].get('actual_leg'))}

    worst=sorted([r for r in rows if r.get('curve_rmse_ticks') is not None],key=lambda x:x['curve_rmse_ticks'],reverse=True)[:20]
    worst_out=[{'blind_id':r['blind_id'],'day':r['day'],'group':r['group'],'rmse_ticks':r['curve_rmse_ticks'],'corr':r['curve_corr'],'path_sign_agreement':r['path_sign_agreement'],'support':r['microstructure_support']} for r in worst]
    highA=[r for r in rows if r['family']=='A']
    a8_wrong=sum(r['legs']['8t'].get('prediction_direction_hit') is False for r in highA if r['legs']['8t'].get('actual_leg'))
    a5_wrong=sum(r['legs']['5t'].get('prediction_direction_hit') is False for r in highA if r['legs']['5t'].get('actual_leg'))

    summary={
      'status':'POSTREVEAL_COMPLETE_NO_RETUNING',
      'prediction_freeze_commit':FREEZE_COMMIT,
      'prediction_n':1711,
      'freeze_verified_before_actual_reveal':True,
      'frozen_a_classifier_sha256':freeze['frozen_a_classifier_sha256'],
      'a_classifier_refit_after_reveal':False,
      'frankie_brain_or_schema_mutated':False,
      'overall':{'median_curve_rmse_ticks':median(r['curve_rmse_ticks'] for r in rows),'median_curve_mae_ticks':median(r['curve_mae_ticks'] for r in rows),'median_curve_corr':median(r['curve_corr'] for r in rows),'mean_path_sign_agreement':mean(r['path_sign_agreement'] for r in rows),'median_pred_peak_ticks':median(r['pred_peak_ticks'] for r in rows),'median_actual_peak_ticks':median(r['actual_peak_ticks'] for r in rows)},
      'by_group':by_group,
      'duration_by_group_scale':duration,
      'a_state_runway_ordering':a_order,
      'b_locality_alignment':{s:duration['B'][s]['actual_alignment_with_dipole_rate'] for s in SCALES},
      'c_scale_transition_alignment':{s:duration['C'][s]['actual_alignment_with_dipole_rate'] for s in SCALES},
      'microstructure':{'support_bins':micro},
      'high_confidence_A_direction_failures':{'5t_wrong':a5_wrong,'8t_wrong':a8_wrong,'A_n':len(highA)},
      'worst_curve_failures':worst_out,
      'definitions':{
        'curve_rmse_ticks':'RMSE between piecewise-linear frozen forecast curve and 1s ffilled held-out actual price, sampled on an adaptive <=900-point grid through the forecast terminal horizon',
        'actual_leg_duration':'retrospective ZigZag pivot-to-pivot duration using the same 3/5/8/13 tick reversal definitions as reveal',
        'actual_alignment_with_dipole':'actual ZigZag leg direction equals frozen t0 dipole polarity',
        'prediction_direction_hit':'forecast displacement sign at its frozen scale-duration landmark equals actual attached ZigZag leg direction'
      }
    }
    (OUT/'FRANKIE_NG_EXHAUSTION_POSTREVEAL_METRICS_20260816.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')

    for day,rr in sorted(byday.items()): write_html_gallery(day,rr,days[day])
    make_group_curves(rows,days); make_examples(rows,days); make_summary_figure(summary)

    lines=['# Frankie NG Exhaustion Blind — Post-Reveal Analysis Scaffold','',f"Status: {summary['status']}",f"Frozen prediction commit: `{FREEZE_COMMIT}`",f"Predictions scored: {summary['prediction_n']}",'','## Core holdout checks']
    for s in SCALES:
        q=a_order[s]; lines.append(f"- A {s}: persistent median {q['persistent_median_s']}s vs fast {q['fast_median_s']}s; persistent>fast={q['persistent_gt_fast']}; day-level passes={q['days_pass']}/4.")
    lines+=['','## B locality / C transition']
    lines.append('- B alignment by scale: '+', '.join(f"{s}={summary['b_locality_alignment'][s]:.3f}" if summary['b_locality_alignment'][s] is not None else f'{s}=n/a' for s in SCALES))
    lines.append('- C alignment by scale: '+', '.join(f"{s}={summary['c_scale_transition_alignment'][s]:.3f}" if summary['c_scale_transition_alignment'][s] is not None else f'{s}=n/a' for s in SCALES))
    lines+=['','## Curve fit',f"- Overall median RMSE: {summary['overall']['median_curve_rmse_ticks']:.3f} ticks.",f"- Overall median curve correlation: {summary['overall']['median_curve_corr'] if summary['overall']['median_curve_corr'] is not None else 'n/a'}.",f"- Overall mean path-sign agreement: {summary['overall']['mean_path_sign_agreement'] if summary['overall']['mean_path_sign_agreement'] is not None else 'n/a'}.",'','No classifier, brain, schema, family definition, or forecast was retuned after reveal.']
    (OUT/'FRANKIE_NG_EXHAUSTION_POSTREVEAL_ANALYSIS_SCAFFOLD_20260816.md').write_text('\n'.join(lines)+'\n')

    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__':
    main(sys.argv[1:])
