import json
from functools import cache
from pathlib import Path


@cache
def markets():
    folder = Path(__file__).with_name("markets")
    return {p.stem: json.loads(p.read_text(encoding="utf8")) for p in sorted(folder.glob("*.json"))}


def replay_market(key):
    market = markets()[key]
    if market["adapter"] != "nymex-ng":
        raise ValueError("the selected market needs its own tape and trading-session adapter")
    return market
