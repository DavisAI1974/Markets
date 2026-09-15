import json
import threading
import pytest
from research.kalshi.frankie_boss import full_run_progress as module


def test_latest_snapshot_sharing_failure_keeps_durable_progress(tmp_path, monkeypatch):
    probe=module.RunProbe(tmp_path,'sharing-seam',emit=lambda _:None)
    def denied(*args):
        error=PermissionError(13,'private path')
        error.winerror=32
        raise error
    monkeypatch.setattr(module.os,'replace',denied)
    probe.advance('causal_delivery',completed=26000,total=57027,unit='records')
    probe.check_health()
    rows=[json.loads(row) for row in (tmp_path/'progress.jsonl').read_text().splitlines()]
    assert rows[0]['completed']==26000
    assert rows[-1]['diagnostic_error']==dict(error_type='PermissionError',errno=13,winerror=32,phase='latest_snapshot')
    assert 'private path' not in (tmp_path/'progress.jsonl').read_text()


def test_background_failure_retains_safe_root_cause(tmp_path,monkeypatch):
    probe=module.RunProbe(tmp_path,'error-seam',emit=lambda _:None,interval=.001)
    def fail():raise OSError(28,'secret location')
    monkeypatch.setattr(probe,'sample',fail)
    worker=threading.Thread(target=probe._heartbeat);worker.start();worker.join(1)
    with pytest.raises(RuntimeError,match='diagnostic persistence') as failure:probe.check_health()
    assert isinstance(failure.value.__cause__,OSError)
    assert probe._heartbeat_error['errno']==28
    saved=json.loads((tmp_path/'diagnostic-failure.json').read_text())
    assert saved['error']['errno']==28 and saved['error']['phase']=='heartbeat'
    assert 'secret location' not in (tmp_path/'diagnostic-failure.json').read_text()
