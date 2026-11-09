"""Tie conditional dipole counts to exact original messages and verify all closes."""
import gzip
import json
from pathlib import Path
import subprocess

import databento as db
import pandas as pd

from flow_book_discovery import REV,GROUPS
from research_replay_comparison import SOURCE_REV
from research_atlas import TAPE_REV

BASE=Path(__file__).resolve().parent/'replay-comparison'


def main(day):
    root=BASE/day;out=root/'research-atlas-v2'
    revision=REV if day=='20231018' else SOURCE_REV
    path=GROUPS if day=='20231018' else f'tasks/family-research-20261022/replay-artifacts/{day}/standalone-inputs/groups.jsonl.gz'
    groups=list(map(json.loads,gzip.decompress(subprocess.check_output(['git','show',f'{revision}:{path}'])).splitlines()))
    features=pd.read_csv(out/'stack-features.csv.gz',dtype={'decision_ns':str})
    outcomes=pd.read_csv(root/'flow-book-discovery-v1/dipole-after-recognition.csv.gz')
    selected=features[(features.dipole_state=='weakening')&(features.book_vs_flow=='aligned')].merge(
        outcomes[(outcomes.horizon_s==20)&(outcomes.disposition=='available')],on='candidate_id')
    selected['oriented']=selected.change*selected.imb_level
    examples=[]
    targets=set()
    for label,mask in [('with_flow',selected.oriented>0),('against_flow',selected.oriented<0),('flat',selected.change==0)]:
        row=selected[mask].sort_values('decision_ns').head(1)
        if not len(row):continue
        r={k:None if pd.isna(v) else v for k,v in row.iloc[0].to_dict().items()}
        gi=int(r['source_group'])
        # Strictly following group; the recognition group is already a feature input.
        later=next((g for g in groups[gi+1:] if g['prints']),None)
        e=dict(label=label,candidate=r,recognition_group=groups[gi],first_later_print_group=later)
        examples.append(e)
        targets.add(gi)
        if later:targets.add(later['group_ordinal'])
    starts={groups[i]['first_cursor']:i for i in targets}
    close_by_cursor={g['close_cursor']:g for g in groups}
    sources=[(day,0)] if day in ('20231002','20231017') else [
        (str(int(day)-1),-808453 if day=='20231003' else -841601),
        (day,4889 if day=='20231003' else 17375)]
    messages={i:[] for i in targets};active=None;verified=0
    for raw_day,offset in sources:
        raw=subprocess.check_output(['git','show',f'{TAPE_REV}:data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{raw_day}.dbn.zst'])
        for index,record in enumerate(db.DBNStore.from_bytes(raw)):
            cursor=index+offset
            if cursor>groups[-1]['close_cursor']:break
            if cursor in starts:active=starts[cursor]
            if active is not None:
                messages[active].append(dict(cursor=cursor,raw_day=raw_day,raw_index=index,
                    receive_ns=int(record.ts_recv),order_id=int(record.order_id),action=str(record.action),
                    side=str(record.side),price_raw=int(record.price),size=int(record.size),flags=int(record.flags)))
            if cursor in close_by_cursor:
                g=close_by_cursor[cursor]
                assert int(record.ts_recv)==g['receive_ns'] and int(record.flags)&128
                verified+=1
                active=None
    assert verified==len(groups)
    for e in examples:
        for name in ('recognition_group','first_later_print_group'):
            g=e[name]
            e[name+'_messages']=messages[g['group_ordinal']] if g else []
    payload=dict(day=day,raw_tape_revision=TAPE_REV,verified_group_closes=verified,
                 selection='Earliest weakening + aligned-book recognition with/against/flat 20-second midpoint outcome; retrospective examples, not prevalence estimates.',
                 examples=examples)
    (out/'conditional-order-examples.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
    summary=json.loads((root/'summary.json').read_text());summary['raw_group_closes_verified']=verified
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(day,'verified',verified,'closes;',len(examples),'conditional order examples')


if __name__=='__main__':
    import sys
    main(sys.argv[1])
