import datetime as dt

import databento_dbn as dbn
import pytest
import zstandard as zstd

from research.kalshi.frankie_boss.operations.stage_block_sources import count_records


def fixture(records):
    metadata = dbn.Metadata(dataset='GLBX.MDP3', start=1, stype_in=dbn.SType.RAW_SYMBOL,
                            stype_out=dbn.SType.INSTRUMENT_ID, schema=dbn.Schema.MBO)
    return zstd.ZstdCompressor().compress(metadata.encode()+b''.join(bytes(r) for r in records))


def record(ts, flags=128, instrument=1):
    return dbn.MBOMsg(publisher_id=1, instrument_id=instrument, ts_event=ts, order_id=1,
                      price=1, size=1, action=dbn.Action.ADD, side=dbn.Side.BID, ts_recv=ts, flags=flags)


def test_installed_dbn_decoder_counts_every_record_and_preserves_seams(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'databento', None)
    halt=int(dt.datetime(2021,10,3,21,tzinfo=dt.timezone.utc).timestamp()*1e9)
    assert count_records(fixture([record(halt-2,0),record(halt-1),record(halt,0,2)]),'20211003') == dict(
        mbo_records=3,before_halt=2,after_halt=1,first_ts_recv_ns=halt-2,last_ts_recv_ns=halt,
        instruments=2,f_last_groups=1,last_record_f_last=False,halt_boundary_f_last=True)


def test_empty_or_truncated_source_is_refused():
    with pytest.raises(ValueError):count_records(fixture([]),'20211003')
    with pytest.raises(ValueError):count_records(fixture([record(1)])[:-4],'20211003')
