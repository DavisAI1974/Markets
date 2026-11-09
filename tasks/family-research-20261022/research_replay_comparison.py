"""Apply the retained October 18 dipole/stack methods to sealed replay dates.

Run one date per process. The module bindings below supply date-specific inputs
and output directories to the unchanged historical calculations, never producers.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

import pandas as pd

NS = 10**9
HERE = Path(__file__).resolve().parent
SOURCE_REV = '2f12d6d47'
OLD_CANDIDATES = 'tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz'


def candidate_inputs(records, groups):
    operands = {r['candidate_id']: r for r in records if r['emitting_section'] == 'candidate'}
    episodes = [r for r in records if r['emitting_section'] == 'episode' and 'birth_recv_ns' in r]
    seconds = {r['second']: r for r in records if r['emitting_section'] == 'flow_substrate'}

    def window(end):
        b = sum(seconds.get(s, {}).get('buy_volume', 0) for s in range(end-19, end+1))
        a = sum(seconds.get(s, {}).get('sell_volume', 0) for s in range(end-19, end+1))
        return dict(buy_lots=b, sell_lots=a, classified_lots=b+a, roll20=(b-a)/(b+a) if b+a else None)

    result = []
    for e in episodes:
        ident = e['candidate_id']
        if ident not in operands:
            raise ValueError(f'missing original operands: {ident}')
        stamp = e['frankie_emission']
        if stamp.get('phase') == 'FINALIZE' and stamp['group_index'] is None:
            result.append(dict(candidate_id=ident,recognition_group=None,
                               input_disposition='finalize_only_no_live_recognition',
                               birth_to_emission_flow_state='unavailable_finalize_only',
                               original_episode=e,recorded_operands=operands[ident]))
            continue
        g = groups[stamp['group_index']]
        if (g['group_ordinal'], g['close_cursor'], g['receive_ns']) != (
                stamp['group_index'], stamp['input_cursor'], stamp['ts_recv_ns']):
            raise ValueError(f'Native recognition/group mismatch: {ident}')
        birth = e['birth_recv_ns']//NS
        last = stamp['ts_recv_ns']//NS-1
        b, w = window(birth), window(last)
        bv, v = b['roll20'], w['roll20']
        state = ('undefined_at_emission' if v is None else 'no_reconstructed_birth_direction'
                 if not bv else 'balanced_at_emission' if not v else
                 'same_direction_at_emission' if bv*v > 0 else 'opposite_direction_at_emission')
        result.append(dict(candidate_id=ident, birth_second=birth,
                           available_second=e['recognized_recv_ns']//NS,
                           recognition_group=g['group_ordinal'], recognition_cursor=g['close_cursor'],
                           recognition_receive_ns=g['receive_ns'], last_closed_second=last,
                           birth_window=b, last_closed_window=w,
                           recorded_operands=operands[ident], birth_to_emission_flow_state=state))
    if len({r['candidate_id'] for r in result}) != len(result) or len(result) != len(operands):
        raise ValueError('candidate/recognition population does not reconcile')
    return result


def main(day, mechanisms=False, prebirth_only=False):
    import flow_book_discovery as fb
    import research_atlas as atlas
    import research_atlas_dipole as dipole
    import research_atlas_stack as stack
    import research_atlas_timing as timing
    import research_atlas_prebirth as prebirth

    target = HERE/'replay-comparison'/day
    out = target/'research-atlas-v2'
    out.mkdir(parents=True, exist_ok=True)
    (out/'sources').mkdir(exist_ok=True)
    (target/'flow-book-discovery-v1').mkdir(exist_ok=True)
    old_rows = fb.rows
    if day == '20231018':
        group_path = fb.GROUPS
        groups = old_rows(group_path)
        candidates = old_rows(OLD_CANDIDATES)
        source_revision = fb.REV
        group_digest = hashlib.sha256(fb.blob(group_path)).hexdigest()
    else:
        group_path = f'tasks/family-research-20261022/replay-artifacts/{day}/standalone-inputs/groups.jsonl.gz'
        payload = subprocess.check_output(['git','show',f'{SOURCE_REV}:{group_path}'])
        receipt = json.loads(subprocess.check_output(['git','show',f'{SOURCE_REV}:{group_path.rsplit("/",1)[0]}/receipt.json']))
        group_digest = hashlib.sha256(payload).hexdigest()
        assert group_digest == receipt['groups_file']['sha256']
        groups = list(map(json.loads,gzip.decompress(payload).splitlines()))
        assert len(groups) == receipt['counts']['groups']
        source = HERE/'replay-comparison/sources'/f'research-comparison-{day}'
        raw = (source/'native-research-records.jsonl.gz').read_bytes()
        extraction = json.loads((source/'source-receipt.json').read_text())
        assert hashlib.sha256(raw).hexdigest() == extraction['output_sha256']
        records = list(map(json.loads,gzip.decompress(raw).splitlines()))
        candidates = candidate_inputs(records, groups)
        assert len(candidates) == sum(r['candidates_emitted'] for r in extraction['candidate_detection'])
        (target/'candidate-inputs.jsonl.gz').write_bytes(gzip.compress(
            ''.join(json.dumps(r)+'\n' for r in candidates).encode(),mtime=0))
        source_revision = SOURCE_REV

    all_candidates = candidates
    candidates = [c for c in candidates if c['recognition_group'] is not None]
    midnight = int(datetime.strptime(day,'%Y%m%d').replace(tzinfo=timezone.utc).timestamp())
    start = midnight if day in ('20231002','20231017') else midnight-7200
    end = midnight+21*3600
    atlas.OPEN, atlas.CLOSE = start*NS, end*NS

    def date_rows(path):
        if path == group_path:return groups
        if path == OLD_CANDIDATES:return candidates
        raise ValueError(f'Unexpected historical input request: {path}')

    # Single-process bindings prevent silent fallback to October 18 data.
    for module in (fb, atlas, dipole, stack, timing, prebirth):
        module.rows = date_rows
        module.GROUPS = group_path
    atlas.OUT = out
    fb.OUT = target/'flow-book-discovery-v1'
    for module in (dipole, stack):
        module.OUT = out
        module.HERE = target
    dipole.OPEN, dipole.CLOSE = atlas.OPEN, atlas.CLOSE
    timing.OUT = out
    prebirth.OUT = out
    prebirth.OPEN, prebirth.CLOSE = atlas.OPEN, atlas.CLOSE
    births=[(c['candidate_id'],c['birth_second']*NS if 'birth_second' in c else
             c['original_episode']['birth_recv_ns']) for c in all_candidates]
    prebirth.main({'dipole_birth':births})
    method_path=out/'prebirth-method.json'
    method=json.loads(method_path.read_text())
    method.update(source_revision=source_revision,source_groups=group_path,source_family=None,
                  populations=['dipole_birth'],trade_date=day,
                  population_note='All recorded births, including finalization-only rows; retrospective alignment, not live recognition.')
    method['limitations']=[s for s in method['limitations'] if 'One discovery date' not in s]
    method_path.write_text(json.dumps(method,indent=2)+'\n')
    if prebirth_only:return
    fb.dipole_followup(fb.load_groups())
    dipole.main()
    stack.main()
    # Replace historical descriptive metadata, not calculated observations.
    for name in ('dipole-application-method.json','stack-method.json'):
        path = out/name
        method = json.loads(path.read_text())
        method.update(source_revision=source_revision, source_groups=group_path, trade_date=day,
                      scope='partial UTC snapshot through halt' if day in ('20231002','20231017') else 'full session',
                      candidates=len(candidates),all_recorded_candidates=len(all_candidates),
                      unavailable_finalize_only=len(all_candidates)-len(candidates))
        if 'populations' in method:method['populations']['dipoles']=len(candidates)
        key = 'limits'
        method[key] = [s for s in method[key] if '863' not in s and 'One selected October 18' not in s]
        method[key].append('Each date is discovery; same model and folds, separately fitted. All hypotheses retained for paper comparison.')
        path.write_text(json.dumps(method,indent=2)+'\n')

    summary = dict(day=day, source_revision=source_revision, groups=len(groups),
                   groups_sha256=group_digest, candidates=len(all_candidates), live_recognitions=len(candidates),
                   unavailable_finalize_only=len(all_candidates)-len(candidates),
                   recognition_states=dict(Counter(c['birth_to_emission_flow_state'] for c in all_candidates)),
                   scope='partial' if day in ('20231002','20231017') else 'full',
                   open_ns=atlas.OPEN, close_ns=atlas.CLOSE)
    if mechanisms:
        import databento as db
        def raw_records():
            sources = [(day,0)] if summary['scope']=='partial' else [
                (str(int(day)-1), -808453 if day=='20231003' else -841601),
                (day, 4889 if day=='20231003' else 17375)]
            close_by_cursor={g['close_cursor']:g for g in groups}
            verified=0
            for raw_day, offset in sources:
                path=f'data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_{raw_day}.dbn.zst'
                data=subprocess.check_output(['git','show',f'{atlas.TAPE_REV}:{path}'])
                for index,record in enumerate(db.DBNStore.from_bytes(data)):
                    cursor=index+offset
                    if cursor>groups[-1]['close_cursor']:
                        assert verified==len(groups)
                        summary['raw_group_closes_verified']=verified
                        return
                    if cursor in close_by_cursor:
                        assert int(record.ts_recv)==close_by_cursor[cursor]['receive_ns']
                        assert int(record.flags)&128
                        verified+=1
                    if cursor>=0:yield cursor,record,raw_day,index
            assert verified==len(groups)
            summary['raw_group_closes_verified']=verified
        atlas.raw_records = raw_records
        matrix=atlas.group_matrix(groups)
        events,outcomes=atlas.mechanism_inventory(groups,matrix)
        timing.main()
        for name in ('mechanism-method.json','observation-method.json'):
            path=out/name
            method=json.loads(path.read_text())
            method.update(trade_date=day,source_groups_revision=source_revision,source_groups_sha256=group_digest)
            path.write_text(json.dumps(method,indent=2)+'\n')
        summary['resting_events']=len(events)
        summary['resting_endings']=events.end_kind.value_counts().to_dict()
        summary['resting_visible_at_start']=int(events.visible_at_start_close.sum())
        # Exact earliest favorable, contrary and flat order paths at 20 seconds.
        examples=[]
        v=outcomes[(outcomes.anchor=='start_close')&(outcomes.horizon_s==20)&(outcomes.disposition=='available')]
        actions=pd.read_csv(out/'aggression-to-rest-actions.csv.gz')
        for label,mask in [('continuation',v.direction_oriented_change>0),('reversal',v.direction_oriented_change<0),('flat',v.direction_oriented_change==0)]:
            selected=v[mask].merge(events[events.visible_at_start_close],on='event_id').sort_values('known_by_ns').head(1)
            if len(selected):
                row=selected.iloc[0].to_dict()
                row.update(label=label,actions=actions[actions.event_id==row['event_id']].head(30).to_dict('records'))
                examples.append(row)
        (out/'order-examples.json').write_text(json.dumps(examples,indent=2)+'\n')
    (target/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('day',choices=['20231002','20231003','20231017','20231018'])
    parser.add_argument('--mechanisms',action='store_true')
    parser.add_argument('--prebirth-only',action='store_true')
    args=parser.parse_args()
    main(args.day,args.mechanisms,args.prebirth_only)
