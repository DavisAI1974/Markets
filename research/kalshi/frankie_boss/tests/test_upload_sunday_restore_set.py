"""Guard for the multipart TLS-flag race: the restore-set uploader must never share one client across transfer threads."""
import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[1] / 'operations' / 'upload_sunday_restore_set.py'
    spec = importlib.util.spec_from_file_location('upload_sunday_restore_set', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_transfer_config_is_single_threaded():
    config = _module().transfer_config()
    assert config.max_concurrency == 1
    assert config.multipart_chunksize == 64 * 1024 * 1024


def test_mirror_key_maps_both_roots():
    m = _module()
    assert m.mirror_key('E:/Codex/Frankie-BOSS-20260915/actual-prefixes/prefix-01.sqlite') == 'FB/actual-prefixes/prefix-01.sqlite'
    assert m.mirror_key('C:/Users/A/Documents/Codex/x/y.json') == 'C_Codex/x/y.json'
