#!/usr/bin/env python3
"""Rerunnable proof that the live clock adapter equals the frozen blind inputs."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from ng_exhaustion_live_clock import AggressorRoll20Feed, FrozenPreFamilyClassifier, _fill_curve
from ng_exhaustion_runway_clock import ExhaustionRunwayClock


def run(records_path: Path, family_path: Path, state_path: Path) -> dict:
    rows=json.loads(records_path.read_text())
    if len(rows)!=1711: raise RuntimeError(f"expected 1711 frozen blind records, got {len(rows)}")
    family=FrozenPreFamilyClassifier.load(family_path)
    clock=ExhaustionRunwayClock.from_classifier_path(state_path)
    family_bad=0; window_bad=0; a_bad=0; samples=0; max_error=0.0; a_n=0
    for row in rows:
        got_family=family.classify(row['dipole_roll20_oriented_t_minus60_to_plus60'][:61]).family
        family_bad += got_family != row['family']
        feed=AggressorRoll20Feed()
        for i,(b,s) in enumerate(zip(row['aggressor_buy_volume_t_minus60_to_plus60'],row['aggressor_sell_volume_t_minus60_to_plus60'])):
            feed.ingest_volume(i-60,buy_volume=0.0 if b is None else float(b),sell_volume=0.0 if s is None else float(s))
        raw=_fill_curve(feed.raw_series(0,60)); pol=int(row['dipole_polarity']); live=[pol*x for x in raw]
        expected=[float(x) for x in row['dipole_roll20_oriented_t_minus60_to_plus60'][60:]]
        err=max(abs(a-b) for a,b in zip(live,expected)); samples += len(live); max_error=max(max_error,err)
        window_bad += err != 0.0
        if row['family']=='A':
            a_n += 1
            out=clock.update(event_id=row['blind_id'],session_id=row['day'],t0=row['t0_second_utc'],family='A',elapsed_s=60.0,
                             a_t0_to_plus60=live,data_flags={'event_clock':True,'a_classifier_window':True,'microstructure':False})
            a_bad += out['post_state'] != row['frozen_post_state_assignment']['label']
            if out['future_price_accessed'] is not False: raise RuntimeError('future-price invariant failed')
    result={'schema':'markets.ng_exhaustion.live_clock_batch_proof.v1','status':'PASS' if not (family_bad or window_bad or a_bad or max_error) else 'FAIL',
            'records':len(rows),'pre_family_classifier_sha256':family.artifact_sha256,'family_assignment_mismatches':family_bad,
            'live_roll20_samples_checked':samples,'live_roll20_bad_records':window_bad,'live_roll20_max_abs_error':max_error,
            'a_records':a_n,'a_poststate_mismatches':a_bad,'future_price_accessed_by_clock':False,
            'event_detection_scope':'external causal t0 marker; not part of runway clock V0','permanent_frankie_mutated':False}
    if result['status']!='PASS': raise RuntimeError(json.dumps(result,sort_keys=True))
    return result


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--records',required=True); ap.add_argument('--family-classifier',required=True); ap.add_argument('--poststate-classifier',required=True); ap.add_argument('--out'); a=ap.parse_args()
    result=run(Path(a.records),Path(a.family_classifier),Path(a.poststate_classifier)); text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if a.out: Path(a.out).write_text(text)
    print(text,end=''); return 0
if __name__=='__main__': raise SystemExit(main())
