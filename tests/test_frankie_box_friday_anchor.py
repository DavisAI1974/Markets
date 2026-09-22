"""The Friday anchor script (Greg, 2026-09-22): read-only, pinned to the archive's Friday object, the halt is 21:00Z."""
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_friday_anchor.sh'


def test_the_script_pins_the_friday_object_and_the_halt_and_never_overwrites_or_deletes():
    text = SCRIPT.read_text(encoding='utf-8')
    assert "KEY_SUFFIX = 'native/20211001_20211101/glbx-mdp3-20211001.mbo.dbn.zst'" in text
    assert "WANT_BYTES, WANT_SHA = 25628861, 'e6b4ec01bd9b34d57cb22c770b5d49c756e7f41a658f081823d923004a0121b2'" in text
    assert 'HALT = datetime(2021, 10, 1, 21, 0, tzinfo=timezone.utc)' in text
    assert int(datetime(2021, 10, 1, 21, 0, tzinfo=timezone.utc).timestamp()) == 1633122000     # Friday 17:00 EDT
    assert 'not overwritten (move it aside with a receipt first)' in text and "rm -f \"$ROOT/tmp/anchor-map.json\"" in text
    assert 'os.remove' not in text and 'unlink' not in text and 'shutil.rmtree' not in text
    assert "str(rec.action) != 'T'" in text and 'rec.ts_recv < HALT_NS' in text          # a trade, before the halt
    assert 'MAP_URL' in text and 'boto3' not in text                                     # the box reads S3 only through the presigned map
    assert 'nothing averaged' in text
