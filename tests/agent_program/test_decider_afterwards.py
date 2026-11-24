"""tools/decider/afterwards.py on the real journal of run 0f33fec4... (events.jsonl from its record branch, `git show`
into a scratch folder). No engine, no model, no tape.

There is NO real quotes.jsonl yet (nothing has been run with the market series kept). The quotes part is checked on a
short series BUILT FROM THE JOURNAL'S OWN ROWS: the bid and the ask that the real journal rows carry, in time order.
Real values, a thin series; no price is invented. Its expected figures are worked out here by a plain loop.
"""

import json
import subprocess

import pytest

from tools.decider import afterwards as aw
from tools.kgraph import signal_packet as sp
from tools.kgraph.store import markets_data_root

R0 = "0f33fec49f8c4905b6c212912077d439"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    try:
        root = markets_data_root()
    except FileNotFoundError as e:
        pytest.skip(f"no markets-data checkout: {e}")
    r = subprocess.run(["git", "-C", str(root), "show", f"origin/paper-runs/{R0}:paper-trading/{R0}/events.jsonl"],
                       capture_output=True)
    if r.returncode:
        pytest.skip(f"no record branch for {R0} in {root}")
    d = tmp_path_factory.mktemp("aw")
    journal = d / "events.jsonl"
    journal.write_bytes(r.stdout)
    rows = sp.journal_from_file(journal)
    qrows = sorted((x for x in rows if x.get("bid") is not None and x.get("ask") is not None
                    and isinstance(x.get("received"), int)), key=lambda x: (x["received"], x["sequence"]))
    quotes = d / "quotes.jsonl"
    quotes.write_text("".join(json.dumps({"received_ns": x["received"], "bid": x["bid"], "ask": x["ask"],
                                          "journal_sequence": x["sequence"]}) + "\n" for x in qrows))
    out = d / "afterwards.jsonl"
    aw.main(["--journal", str(journal), "--quotes", str(quotes), "--out", str(out)])
    plain = d / "plain.jsonl"
    aw.main(["--journal", str(journal), "--out", str(plain)])
    lines = [json.loads(t) for t in out.read_text().splitlines()]
    return dict(rows=rows, d=d, journal=journal, quotes=quotes, qrows=qrows, out=out, plain=plain,
                header=lines[0], lines=lines[1:])


def test_header_and_one_line_for_each_opening_signal(world):
    assert "may be given to a decider at the instant it decides" in world["header"]["text"]
    opens = sp.open_sequences(world["rows"])
    assert len(opens) == 217
    assert [l["sequence"] for l in world["lines"]] == opens
    assert all(l["known_only_afterwards"] is True for l in world["lines"])


def test_own_result_equals_trade_lines_rule(world):
    """Expected value from the journal's fills: what they sold for less what they bought for, for a trade that holds
    nothing at the end after more than one fill (trial.trade_lines)."""
    rows, checked = world["rows"], 0
    for l in world["lines"]:
        for t in l["trades"]:
            fills = [r for r in rows if r["kind"] == "fill" and r["trade_id"] == t["trade_id"] and r["rule"] == t["rule"]]
            sold = sum(int(f["quantity"]) * int(f["fill_price"]) for f in fills if f["side"] == "sell")
            bought = sum(int(f["quantity"]) * int(f["fill_price"]) for f in fills if f["side"] == "buy")
            held = sum(int(f["quantity"]) * (1 if f["side"] == "buy" else -1) for f in fills)
            if held == 0 and len(fills) > 1:
                assert t["own_result_price_units"] == sold - bought
                checked += 1
            else:
                assert t["own_result_price_units"] is None
        own = next((t for t in l["trades"] if t["trade_id"] == l["trade_id"] and t["rule"] == l["rule"] and t["opened"]), None)
        assert l["trade_opened"] and any(t["opened"] for t in l["trades"])
        if own:
            assert l["own_result_price_units"] == own["own_result_price_units"]
        else:
            assert "own_result_price_units" not in l and "own_result_note" in l
    assert checked > 200


def test_administrative_close_carried_as_not_trade_data(world):
    rows = world["rows"]
    admin = [t for l in world["lines"] for t in l["trades"] if t["closed_by_an_administrative_fill"]]
    assert admin
    for t in admin:
        closing = [f for f in t["fills"] if f["action"] != "open"]
        assert closing and closing[-1]["trade_data"] is False
        assert t["last_closing_fill"]["trade_data"] is False
    n = sum(1 for r in rows if r["kind"] == "fill" and r["action"] != "open" and r.get("trade_data") is False)
    assert n == sum(1 for t in admin for f in t["fills"] if f["action"] != "open" and f["trade_data"] is False)


def test_rule_close_signal_joined_to_trade_id(world):
    rows = world["rows"]
    for l in world["lines"]:
        want = [r["sequence"] for r in rows if r["kind"] == "signal" and r["action"] in ("close", "exit")
                and r["trade_id"] == l["trade_id"]]
        assert [c["sequence"] for c in l["close_signals_as_journaled"]] == want
        if l["rule_close_signal"]:
            assert l["rule_close_signal"]["sequence"] in want and l["rule_close_signal"]["trade_data"] is not False
    assert sum(1 for l in world["lines"] if l["rule_close_signal"]) > 200


def test_open_profit_values_are_the_journals_own(world):
    rows = world["rows"]
    want = sum(1 for r in rows if "open_profit" in r or "highest_open_profit" in r)
    got = sum(len(t["open_profit_values"]) for l in world["lines"] for t in l["trades"])
    assert got == want == 325


def test_quotes_part_on_a_series_from_the_journals_rows(world):
    q = world["qrows"]
    for l in world["lines"][:: max(1, len(world["lines"]) // 25)]:
        m, t0 = l["market_after"], l["tape_received_ns"]
        first = next((i for i, x in enumerate(q) if x["received"] >= t0), None)
        assert m["first_quote_index_at_or_after_signal"] == first
        for name, side, want in (("highest_bid", "bid", 1), ("lowest_bid", "bid", -1),
                                 ("highest_ask", "ask", 1), ("lowest_ask", "ask", -1)):
            best = None
            for x in q[first:]:
                if best is None or (x[side] - best[0]) * want > 0:
                    best = (x[side], x["received"])
            assert (m[name]["price"], m[name]["first_reached_ns"]) == best
        assert m["at_last_line_of_series"]["bid"] == q[-1]["bid"] and m["at_last_line_of_series"]["index"] == len(q) - 1
        rc = l["rule_close_signal"]
        if rc:
            i = max(j for j, x in enumerate(q) if x["received"] <= rc["received"])
            assert m["at_rule_close_signal"]["index"] == i
    assert not any(k in json.dumps(world["lines"][0]).lower() for k in ("\"mid", "spread"))


def test_without_the_series_the_keys_are_absent_and_say_so(world):
    plain = [json.loads(t) for t in world["plain"].read_text().splitlines()][1:]
    assert len(plain) == 217
    for l in plain:
        assert l["market_series_kept"] is False and "market_after" not in l


def test_skipped_trade_has_no_result_and_says_so(world):
    """The engine journals no fills for a skipped signal; here the real rows of one signal are cut to its signal row."""
    s = next(r for r in world["rows"] if r["kind"] == "signal" and r["action"] == "open")
    ans = {"sequence": s["sequence"], "action": "skip", "why": "a reason", "by": "someone"}
    (line,) = aw.build_lines([s], {s["sequence"]: ans})
    assert line["trade_opened"] is False and "own_result_price_units" not in line and "never opened" in line["own_result_note"]
    assert line["decision"]["action"] == "skip" and line["decision"]["source"] == "decisions.jsonl"


def test_brief_one_line_a_decision_and_nothing_added(world):
    out = world["d"] / "brief.md"
    aw.main(["brief", "--afterwards", str(world["out"]), "--budget", "1000000", "--rests-on-none", "the journal of run 0f33fec4 was made with no decider plugged in and bears on no registered claim", "--out", str(out)])
    text = out.read_text().splitlines()
    body = [t for t in text if t.startswith("sequence ")]
    assert len(body) == 217 and len(text) == 217 + 2
    assert [int(t.split()[1]) for t in body] == [l["sequence"] for l in world["lines"]]
    low = out.read_text().lower()
    for word in ("total", "average", "mean", "win", "loss", "good", "bad", "best", "worst", "rank"):
        assert word not in low.replace("lowest", "").replace("highest", "")


def test_brief_budget_shows_the_head_and_names_the_rest(world):
    out = world["d"] / "brief_small.md"
    aw.main(["brief", "--afterwards", str(world["out"]), "--budget", "600", "--rests-on-none", "the journal of run 0f33fec4 was made with no decider plugged in and bears on no registered claim", "--out", str(out)])
    text = out.read_text().splitlines()
    body = [t for t in text if t.startswith("sequence ")]
    assert 0 < len(body) < 217
    assert [int(t.split()[1]) for t in body] == [l["sequence"] for l in world["lines"]][: len(body)]
    assert f"Shown: {len(body)} of 217" in text[-1] and str(world["out"]) in text[-1]
