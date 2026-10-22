"""Export actual consecutive completed MBO books around one retained family.

Read only exact indexed native records; no sampling, interpolation or tick fill.
"""
import csv
import gzip
import hashlib
import json
import os
import pathlib
import sqlite3
import struct


def main():
    b=pathlib.Path(os.environ.get('FAMILY_RESEARCH_DIR','/opt/frankie-box/work/family-research-20261022'))
    out=b/'timestamped-mbo-window-v1';out.mkdir(exist_ok=True)
    assert not (out/'window_receipt.json').exists(), 'do not overwrite an exported window'
    db=sqlite3.connect(f'file:{b}/alignment.sqlite?mode=ro',uri=True);db.row_factory=sqlite3.Row
    # Predeclared median chronological family, not selected by a favorable response.
    family=dict(db.execute('SELECT f.*,g.instrument_id FROM family_start f JOIN group_event g USING(source_ordinal) ORDER BY start_recv_ns LIMIT 1 OFFSET 374').fetchone())
    lo,hi=family['start_recv_ns']-120_000_000_000,family['start_recv_ns']+600_000_000_000
    rows=[dict(r) for r in db.execute('SELECT * FROM group_event WHERE instrument_id=? AND recv_ns BETWEEN ? AND ? ORDER BY recv_ns,input_cursor,source_ordinal',(family['instrument_id'],lo,hi))]
    pin=dict(db.execute("SELECT * FROM source_registry WHERE name='native.member'").fetchone())
    quote_names=['family_id','instrument_id','family_start_recv_ns','source_ordinal','input_cursor','event_ns','receive_ns','known_by_ns','relative_receive_ns','best_bid','best_ask','spread','mid','bid_depth_n','ask_depth_n','bid_depth_full','ask_depth_full','bid_level_n','ask_level_n','source_offset','source_length','source_row_sha256']
    level_names=['family_id','instrument_id','source_ordinal','input_cursor','event_ns','receive_ns','known_by_ns','relative_receive_ns','side','rank','price','price_raw','size','order_count','front_order_size','front_order_age_s','queue_age_median_s','queue_age_p90_s','largest_order_share']
    level_count=0;bytes_read=0
    with open(pin['path'],'rb') as source,open(pin['offset_index'],'rb') as ix, \
         gzip.open(out/'consecutive_quote_books.csv.gz','wt',newline='') as quotes, \
         gzip.open(out/'consecutive_bid_ask_levels.csv.gz','wt',newline='') as levels:
        header=json.loads(ix.readline());head=ix.tell();assert header['byteorder']=='little'
        qw=csv.DictWriter(quotes,fieldnames=quote_names);qw.writeheader()
        lw=csv.DictWriter(levels,fieldnames=level_names);lw.writeheader()
        for r in rows:
            ordinal=r['source_ordinal'];ix.seek(head+8*ordinal);start,end=struct.unpack('<QQ',ix.read(16));source.seek(start);raw=source.read(end-start)
            assert len(raw)==end-start;bytes_read+=len(raw);j=json.loads(raw);em=j['frankie_emission']
            assert em['input_cursor']==r['input_cursor'] and em['ts_recv_ns']==r['recv_ns'] and j['instrument_id']==r['instrument_id']
            assert j['ts_event_ns']==r['event_ns'] and j['ts_recv_ns']==r['recv_ns']
            book=j['book'];full=j['book_full']
            common=dict(family_id=family['family_id'],instrument_id=r['instrument_id'],source_ordinal=ordinal,input_cursor=r['input_cursor'],event_ns=r['event_ns'],receive_ns=r['recv_ns'],known_by_ns=em['ts_recv_ns'],relative_receive_ns=r['recv_ns']-family['start_recv_ns'])
            q=dict(common,family_start_recv_ns=family['start_recv_ns'],source_offset=start,source_length=end-start,source_row_sha256=hashlib.sha256(raw).hexdigest(),bid_level_n=len(full['bid_levels_full']),ask_level_n=len(full['ask_levels_full']))
            for key in ['best_bid','best_ask','spread','mid','bid_depth_n','ask_depth_n','bid_depth_full','ask_depth_full']:q[key]=book.get(key)
            qw.writerow(q)
            for side,name in [('B','bid_levels_full'),('A','ask_levels_full')]:
                for rank,level in enumerate(full[name],1):
                    assert abs(level['price']-level['price_raw']/1e9)<1e-10
                    row=dict(common,side=side,rank=rank)
                    for key in level_names:
                        if key in level:row[key]=level[key]
                    lw.writerow(row);level_count+=1
    receipt={'status':'completed','family_selection':'375th of 749 chronological first-observed families, chosen without outcomes',
        'family':family,'window_start_ns':lo,'window_end_ns':hi,'window_seconds':[-120,600],
        'book_updates':len(rows),'bid_ask_level_rows':level_count,'source_bytes_read':bytes_read,
        'timestamp_unit':'integer nanoseconds','clock_meanings':'exchange event, local receive and completed-group known-by clocks separately retained; input cursor orders ties',
        'measurement':'actual full native MBO book at every retained same-instrument completed group in the window; not daily aggregates',
        'boundaries':'group-close states after F_LAST, not partial intra-group states; no global forward-fill, interpolation, synthetic levels or post-session prices',
        'use':'inspect descriptive timing of price/depth/queue changes around this family; one window cannot identify causal market influence',
        'model_relation':'new explicit export of already pinned source; no new numerical matrix values or labels, no model restart required',
        'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()} for p in out.glob('*.csv.gz')}}
    (out/'window_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))


if __name__=='__main__':main()
