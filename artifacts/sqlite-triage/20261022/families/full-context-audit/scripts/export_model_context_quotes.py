"""Export exact bid/ask context for every retained sample/lag, without new IO scans."""
import collections
import csv
import gzip
import json
import os
import pathlib


def main():
    base=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=base/'timestamped-model-context-v4';out.mkdir(exist_ok=True)
    target=out/'aligned_context_bid_ask.csv.gz';assert not target.exists()
    books={};checks=collections.Counter()
    with gzip.open(base/'full-context-audit/indexed-payloads/native.member.jsonl.gz','rt') as f:
        for line in f:
            wrapper=json.loads(line);r=wrapper['row'];full=r['book_full'];book=r['book'];em=r['frankie_emission']
            q=dict(source_ordinal=wrapper['source_ordinal'],input_cursor=em['input_cursor'],instrument_id=r['instrument_id'],
                event_ns=r['ts_event_ns'],receive_ns=r['ts_recv_ns'],known_by_ns=em['ts_recv_ns'],
                source_offset=wrapper['source_offset'],source_length=wrapper['source_length'],source_row_sha256=wrapper['row_sha256'])
            assert q['receive_ns']==q['known_by_ns']
            for side in ['bid','ask']:
                levels=full[side+'_levels_full']
                depth=sum(level['size'] for level in levels);orders=sum(level['order_count'] for level in levels)
                assert depth==full[side+'_depth_full']
                assert orders==full[side+'_order_count_full']
                assert len(levels)==full[side+'_price_level_count_full']
                best=levels[0]['price_raw']/1e9 if levels else None
                assert best==book['best_'+side],('touch_alias',side,best,book['best_'+side])
                for level in levels:assert abs(level['price']-level['price_raw']/1e9)<1e-10
                q['best_'+side]=best;q['best_'+side+'_raw']=levels[0]['price_raw'] if levels else None
                q[side+'_depth_full']=depth;q[side+'_orders_full']=orders;q[side+'_levels_full']=len(levels)
                q[side+'_depth_top10']=sum(level['size'] for level in levels[:10])
                checks['full_depth_conservation_checks']+=1;checks['touch_alias_checks']+=1
            bid=q['best_bid'];ask=q['best_ask'];two=bid is not None and ask is not None
            q['spread_raw']=q['best_ask_raw']-q['best_bid_raw'] if two else None
            q['spread']=q['spread_raw']/1e9 if two else None
            q['mid']=(q['best_ask_raw']+q['best_bid_raw'])/(2e9) if two else None
            q['quote_state']='TWO_SIDED_CROSSED' if two and ask<bid else 'TWO_SIDED_LOCKED' if two and ask==bid else 'TWO_SIDED' if two else 'ONE_SIDED' if bid is not None or ask is not None else 'EMPTY'
            checks[q['quote_state']]+=1
            # Preserve source-provided midpoint separately, including one-sided conventions.
            q['source_mid']=book.get('mid');q['source_spread']=book.get('spread')
            books[wrapper['source_ordinal']]=q
    samples={r['sample_id']:r for r in csv.DictReader((base/'joint-inputs-v3/model_sample_master.csv').open())}
    contexts=list(csv.DictReader((base/'descriptive-v1/group_context_receipts.csv').open()))
    fields=['sample_id','lag_s','family_id','cutoff_ns','cursor_cap','book_age_ns',*next(iter(books.values())).keys()]
    with gzip.open(target,'wt',newline='',compresslevel=1) as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in contexts:
            q=books[int(c['source_ordinal'])];s=samples[c['sample_id']];cutoff=int(c['cutoff_ns']);cap=int(s['cursor_cap'])
            assert q['known_by_ns']==int(c['known_by_ns'])<=cutoff
            assert q['input_cursor']==int(c['input_cursor'])<=cap
            assert q['instrument_id']==int(s['instrument_id'])
            w.writerow(dict(sample_id=c['sample_id'],lag_s=c['lag_s'],family_id=s['family_id'],cutoff_ns=cutoff,cursor_cap=cap,
                book_age_ns=cutoff-q['known_by_ns'],**q))
    receipt=dict(schema='TIMESTAMPED_ALL_MODEL_CONTEXT_QUOTES_V1',status='complete',coverage_gate='NOT_PASSED',
        unique_native_records=len(books),aligned_contexts=len(contexts),families=len({s['family_id'] for s in samples.values()}),checks=dict(checks),
        clocks='Exact integer event, receive, completed-group known-by, cutoff and cursor cap remain separate; age is cutoff minus known-by.',
        limitations=['Complete observed group snapshots only; this does not establish continuous FIFO survival or partial intra-group states.',
          'Crossed, locked, one-sided and empty states are retained explicitly. No synthetic quote or trade fill is made.',
          'This exports all retained model contexts; the existing consecutive-window export remains a separately scoped object.',
          'No v4 matrix or fit is asserted.'])
    (out/'context_quote_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
