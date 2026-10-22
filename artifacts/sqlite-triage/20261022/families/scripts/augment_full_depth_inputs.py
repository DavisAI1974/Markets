"""Extract omitted full-depth measurements using only the 6265 pinned offsets.

No source reconstruction, directory scan, row forward fill or source-null repair.
The same context receipt supplies instrument, cutoff, source age and cursor.
"""
import collections
import csv
import hashlib
import json
import math
import os
import pathlib
import sqlite3
import statistics
import struct

LEVEL_FIELDS = ('price', 'size', 'order_count', 'front_order_size', 'front_order_age_s',
                'largest_order_share', 'queue_age_median_s', 'queue_age_p90_s')


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def measurements(j):
    out = {}
    for side in ('bid_levels', 'ask_levels'):
        full = j['book_full'][side + '_full']
        top = j['book'][side]
        assert len(full)>=len(top) and all(
            all(a.get(k)==z.get(k) for k in (*LEVEL_FIELDS, 'price_raw', 'side'))
            for a,z in zip(top,full)), 'full/top scalar book prefix disagreement'
        assert all((full[i]['price'] >= full[i+1]['price'] if side=='bid_levels' else
                    full[i]['price'] <= full[i+1]['price']) for i in range(len(full)-1))
        for rank, level in enumerate(full, 1):
            assert abs(level['price'] - level['price_raw']/1e9) < 1e-10
            prefix = f'native.book.{side}.rank{rank}.'
            # Existing top-N scalar measurements already live in v2.
            if rank > len(top):
                for key in LEVEL_FIELDS:
                    out[prefix + key] = level.get(key) if number(level.get(key)) else None
            queue = level.get('fifo_queue')
            if queue is None:
                out[prefix+'fifo_size_hhi'] = None
                out[prefix+'fifo_size_weighted_age_s'] = None
                continue
            assert len(queue) == level['order_count']
            assert sum(q['size'] for q in queue) == level['size']
            ahead = 0
            for q in queue:
                assert q['volume_ahead'] == ahead
                ahead += q['size']
            total = level['size']
            out[prefix+'fifo_size_hhi'] = sum((q['size']/total)**2 for q in queue) if total>0 else None
            out[prefix+'fifo_size_weighted_age_s'] = (sum(q['size']*q['priority_age_s'] for q in queue)/total
                if total>0 and all(number(q.get('priority_age_s')) for q in queue) else None)
        # Price distances retain the exact validated price unit, not rounded regime prices.
        if full:
            out[f'native.book.{side}.full_price_span'] = abs(full[0]['price']-full[-1]['price'])
    out['native.ts_in_delta_ns'] = j.get('ts_in_delta_ns') if number(j.get('ts_in_delta_ns')) else None
    gaps = j.get('within_group_receive_gaps_ns')
    valid = gaps is not None and all(number(v) for v in gaps)
    for label, fn in [('mean', statistics.mean), ('minimum', min), ('maximum', max), ('sum', sum)]:
        out[f'native.receive_gaps.{label}_ns'] = fn(gaps) if valid and gaps else None
    out['native.receive_gaps.observed_count'] = len(gaps) if valid else None
    out['native.receive_gaps.nonzero_count'] = sum(v!=0 for v in gaps) if valid else None
    return out


def main():
    base = pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR', '/opt/frankie-box/work/family-research-20261022'))
    dest = base/'joint-inputs-v3'; dest.mkdir(exist_ok=True)
    assert not (dest/'full_depth_values.jsonl').exists(), 'refuse overwriting completed extraction'
    db = sqlite3.connect(f'file:{base}/alignment.sqlite?mode=ro', uri=True); db.row_factory=sqlite3.Row
    pin = dict(db.execute("SELECT * FROM source_registry WHERE name='native.member'").fetchone())
    contexts = list(csv.DictReader((base/'descriptive-v1/group_context_receipts.csv').open()))
    samples = {r['sample_id']: r for r in csv.DictReader((base/'joint-inputs-v2/model_sample_master.csv').open())}
    grouped = collections.defaultdict(list)
    for c in contexts: grouped[int(c['source_ordinal'])].append(c)
    names=set(); finite=collections.Counter(); null=collections.Counter(); maxrank=collections.Counter()
    anchor_reasons=collections.Counter(); rows=0; byte_count=0
    with open(pin['path'],'rb') as source, open(pin['offset_index'],'rb') as ix, \
         (dest/'full_depth_values.jsonl').open('w') as output, \
         (dest/'full_depth_source_receipts.jsonl').open('w') as receipt:
        header=json.loads(ix.readline()); head=ix.tell(); assert header['byteorder']=='little'
        for n,(ordinal,cs) in enumerate(sorted(grouped.items()),1):
            ix.seek(head+ordinal*8); lo,hi=struct.unpack('<QQ',ix.read(16)); source.seek(lo); raw=source.read(hi-lo)
            assert len(raw)==hi-lo; byte_count+=len(raw); j=json.loads(raw)
            known=int(j['frankie_emission']['ts_recv_ns']); cursor=int(j['frankie_emission']['input_cursor'])
            for c in cs:
                assert int(c['known_by_ns'])==known and int(c['input_cursor'])==cursor
                assert known<=int(c['cutoff_ns']) and cursor<=int(samples[c['sample_id']]['cursor_cap'])
                assert int(j['instrument_id'])==int(samples[c['sample_id']]['instrument_id'])
            values=measurements(j); names.update(values); rows+=len(values)
            for key,value in values.items():
                (finite if number(value) else null)[key]+=1
            for side in ('bid_levels','ask_levels'): maxrank[side]=max(maxrank[side],len(j['book_full'][side+'_full']))
            for anchor,a in j['activity_since'].items():
                if a.get('elapsed_recv_ns') is None: anchor_reasons[(anchor,str(a.get('anchor_basis')),str(a.get('anchor_recv_ns')))]+=1
            output.write(json.dumps({'source_ordinal':ordinal,'values':values},separators=(',',':'),allow_nan=False)+'\n')
            receipt.write(json.dumps({'source_ordinal':ordinal,'source_offset':lo,'source_length':hi-lo,
                'row_sha256':hashlib.sha256(raw).hexdigest(),'source_path':pin['path'],'known_by_ns':known,
                'input_cursor':cursor,'instrument_id':j['instrument_id'],'context_n':len(cs)})+'\n')
            if n%1000==0: print(f'full-depth indexed records {n}/{len(grouped)}',flush=True)
    with (dest/'additional_feature_registry.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['feature','finite_unique_source_records','null_unique_source_records'])
        w.writerows((name,finite[name],null[name]) for name in sorted(names))
    report={'status':'completed','unique_source_records':len(grouped),'contexts':len(contexts),'source_bytes_read':byte_count,
        'measurement_cells':rows,'feature_names':len(names),'max_rank':dict(maxrank),'source_unit_prefix_queue_and_asof_checks':'all passed',
        'missing_receive_anchor_counts':{'|'.join(k):v for k,v in sorted(anchor_reasons.items())},
        'limits':['No source-null, undefined flow side, absent completed step, pre-publication or session edge backfill.',
            'FIFO order sizes, volume ahead and priority ages summarized; order IDs, absolute priority clocks and sequences remain provenance.',
            'All observed deeper levels retained separately by side and rank; nonexistent levels remain missing, not zero.',
            'Rounded book_regime/ladder prices remain excluded; native prices verified by price_raw/1e9.',
            'One retained day; no new independent-day data found.']}
    (dest/'additional_source_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__': main()
