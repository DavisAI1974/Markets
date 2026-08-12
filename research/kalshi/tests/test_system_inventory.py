import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("system_inventory", HERE / "system_inventory.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_system_inventory_selftest():
    assert MOD.selftest() == 0


def test_closed_history_is_never_dropped():
    reg = MOD._load(MOD.OPEN_ITEMS)
    out = MOD.render()
    closed = [i for i in reg["items"] if i.get("status") in {"DONE", "SUPERSEDED", "BLOCKED"}]
    assert closed
    missing = [i["id"] for i in closed if str(i["id"]) not in out]
    assert missing == []


def test_inventory_carries_major_families():
    out = MOD.render().lower()
    for name in (
        "market microstructure / databento",
        "weather / ensembles",
        "storage / eia gas balance",
        "power / generator stack",
        "lng / pipelines",
        "options / volatility",
        "storage infrastructure / s3 / restore",
        "model / generator infrastructure",
    ):
        assert name in out


def test_spawn_is_inventory_only_not_a_write_target():
    source = (HERE / "system_inventory.py").read_text(encoding="utf-8")
    assert "research/kalshi/spawn.py" in source
    assert "open(\"research/kalshi/spawn.py\"" not in source
    assert "open('research/kalshi/spawn.py'" not in source
