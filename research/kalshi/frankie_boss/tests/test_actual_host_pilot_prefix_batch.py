"""Requested pilot prefix admission keeps source verification intact."""
import pytest
from types import SimpleNamespace
from research.kalshi.frankie_boss.operations import run_actual_sunday as host_module

@pytest.mark.parametrize('limit,index,scheduled,count', [(19,1,19,2),(2,2,19,2),(2,1,18,2),(2,1,19,1)])
def test_partial_prefix_manifest_cannot_cover_unrequested_or_missing_cycles(monkeypatch,limit,index,scheduled,count):
    host=object.__new__(host_module.ActualHost)
    host.host={'context_encoding':'stacked_v1','prefix_manifest':{}}
    host.cycle_limit=limit
    manifest={'schema':'FRANKIE_SUNDAY_PREFIX_BATCH_V1','prefixes':2,'scheduled_cycles':scheduled,
        'source_records':57027,'witnesses':[{}]*count}
    monkeypatch.setattr(host_module,'verified_json',lambda witness: manifest)
    with pytest.raises(ValueError,match='covering the requested cycles'):
        host.encoding_options({'cycle_index':index})

def test_pilot_manifest_enters_existing_snapshot_verification(monkeypatch):
    host=object.__new__(host_module.ActualHost)
    host.host={'context_encoding':'stacked_v1','prefix_manifest':{'which':'manifest'}}
    host.cycle_limit=2
    manifest={'schema':'FRANKIE_SUNDAY_PREFIX_BATCH_V1','prefixes':2,'scheduled_cycles':19,
        'source_records':57027,'witnesses':[{}, {'which':'snapshot'}]}
    def read(witness):
        if witness==host.host['prefix_manifest']:return manifest
        assert witness==manifest['witnesses'][1]
        raise ValueError('snapshot verifier still authoritative')
    monkeypatch.setattr(host_module,'verified_json',read)
    with pytest.raises(ValueError,match='snapshot verifier'):
        host.encoding_options({'cycle_index':1})
