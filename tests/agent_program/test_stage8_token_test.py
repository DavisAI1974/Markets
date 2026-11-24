"""Stage 8 checks: the token test (tools/token_test). No model call is made by any check here; there is no key.

Real records only. The one real per-call Granite record on file is a committed critic-spool folder of the first
real run on the Frankie branch (`origin/frankie-tip`); it is read with `git show` into a scratch folder. Checks that
need a record that does not exist (a box-job folder, a replay result) are skipped with that reason, never fed made-up data.
"""

from __future__ import annotations

import base64
import datetime as dt
from decimal import Decimal as D
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.token_test import arms, baseline, prices, replay, report

REPO = Path(__file__).resolve().parents[2]
SKILL_SHARED = Path("/tmp/claude-0/bundled-skills/2.1.331/e844ae32faa79e8f2f117b39bb77b32e/claude-api/shared")
MARKETS_DATA = Path("/home/user/markets-data")
SPOOL = ("research/kalshi/frankie_boss/sunday_20260915_package/FB/actual-feedback-run/execution/cycle-00/"
         "critic-spool/5f6d6b901ad0177075e3f4a90bbd9c3dd9b4cd91fb49fe743730a67bbf77b359")


@pytest.fixture(scope="module")
def real_spool(tmp_path_factory):
    root = tmp_path_factory.mktemp("receipts") / "critic-spool" / "5f6d6b90"
    root.mkdir(parents=True)
    for name in ("dispatch.json", "request.json", "outcome.json"):
        r = subprocess.run(["git", "-C", str(REPO), "show", f"origin/frankie-tip:{SPOOL}/{name}"], capture_output=True)
        if r.returncode:
            pytest.skip("the ref origin/frankie-tip (with the committed critic-spool record) is not in this checkout")
        (root / name).write_bytes(r.stdout)
    return root.parent.parent


# ---- baseline ---------------------------------------------------------------------------------------------
def test_no_receipt_gives_empty_list_and_reason(tmp_path):
    got = baseline.read_calls(tmp_path / "nope", "2026-09-15")
    assert list(got) == [] and "does not exist" in got.reason
    (tmp_path / "empty").mkdir()
    got = baseline.read_calls(tmp_path / "empty", "2026-09-15")
    assert list(got) == [] and "no Granite job record" in got.reason


def test_trade_day_boundaries():
    # 18:00 ET belongs to the NEXT named date, 17:00 to 17:59 is the halt, before 17:00 is the same date
    et = baseline.ET
    f = lambda h, m=0, d=15: baseline.trade_day_of(dt.datetime(2026, 9, d, h, m, tzinfo=et).timestamp())
    assert f(18) == ("day", "2026-09-16") and f(17, 59) == ("halt", None) and f(16, 59) == ("day", "2026-09-15")
    assert f(0) == ("day", "2026-09-15")
    # 2026-09-18 is a Friday: 18:00 on Friday to 18:00 on Sunday belongs to no trade day, never to a Saturday
    assert dt.date(2026, 9, 18).weekday() == 4
    assert f(16, 59, 18) == ("day", "2026-09-18") and f(17, 30, 18) == ("outside", None) and f(18, 0, 18) == ("outside", None)
    assert f(0, 0, 19) == ("outside", None) and f(12, 0, 19) == ("outside", None) and f(23, 59, 19) == ("outside", None)
    assert f(0, 0, 20) == ("outside", None) and f(17, 59, 20) == ("outside", None)
    assert f(18, 0, 20) == ("day", "2026-09-21") and dt.date(2026, 9, 21).weekday() == 0     # Sunday 18:00 is trade day Monday
    assert f(17, 30, 17) == ("halt", None)                                                   # Thursday halt kept


def test_real_marker_and_the_real_trade_day_boundaries_of_the_plan(real_spool):
    c = baseline.read_calls(real_spool, "2026-09-15")[0]
    assert baseline.trade_day_of(float(c["time_marker"])) == ("day", "2026-09-15")
    if not (MARKETS_DATA / "graph").exists():
        pytest.skip("no markets-data checkout with the graph: the real boundaries of the four trade days cannot be read")
    from tools.kgraph.store import GraphStore
    days = GraphStore(str(MARKETS_DATA)).nodes("TradeDay")
    assert {n["attrs"]["date"] for n in days} >= {"2023-10-02", "2023-10-03", "2023-10-17", "2023-10-18"}
    for n in days:
        a = n["attrs"]
        start, end = a["start_ns"] // 10**9, a["end_ns"] // 10**9
        assert baseline.trade_day_of(start) == ("day", a["date"])
        assert baseline.trade_day_of(end - 1) == ("day", a["date"])
        assert baseline.trade_day_of(end) == ("halt", None)
        before = baseline.trade_day_of(start - 1)
        assert before == (("outside", None) if a["date"] == "2023-10-02" else ("halt", None)), (a["date"], before)


def test_real_critic_spool_record_matches_its_files(real_spool):
    d = next(real_spool.glob("critic-spool/*"))
    calls = baseline.read_calls(real_spool, "2026-09-15")
    assert len(calls) == 1
    c = calls[0]
    outcome = json.loads((d / "outcome.json").read_bytes())
    body = json.loads(base64.b64decode(outcome["body_base64"]))
    dispatch = json.loads((d / "dispatch.json").read_bytes())
    assert c["writer"] == "critic_spool"
    assert c["input_tokens"] == body["usage"]["prompt_tokens"] == 92428
    assert c["output_tokens"] == body["usage"]["completion_tokens"] == 119
    assert c["call_id"] == dispatch["binding"]["job_id"] and c["conversation_id"] == dispatch["binding"]["attempt_id"]
    assert c["provider_created_at"] == body["created"] and c["trade_day"] == "2026-09-15"
    assert c["estimated_input_tokens"] == dispatch["admission"]["input_tokens"]
    assert set(c["not_recorded"]) == {"started_by", "purpose", "wall_clock_s", "started_at"}
    assert baseline.load_output(c) == body["choices"][0]["message"]["content"]
    assert baseline.load_prompt(c) == json.loads((d / "request.json").read_bytes())["messages"][0]["content"]
    # a different trade day lists it apart, never drops it
    other = baseline.read_calls(real_spool, "2026-09-16")
    assert len(other) == 0 and len(other.other_days) == 1
    strict = baseline.read_calls(real_spool, "2026-09-15", strict_start=True)
    assert len(strict) == 0 and len(strict.no_start_time) == 1


def test_every_folder_is_in_exactly_one_list(real_spool, tmp_path):
    """The real record's parent folder: every sub-folder is in exactly one returned list. Then the same real folder
    with its request.json cut short (the real bytes, cut): it is listed under `unreadable`, not passed over."""
    def partition(root):
        got = baseline.read_calls(root, "2026-09-15")
        lists = {"calls": list(got), "no_start_time": got.no_start_time, "halt": got.halt, "other_days": got.other_days,
                 "outside": got.outside_any_trade_day}
        where = {}
        for name, items in lists.items():
            for c in items:
                where.setdefault(c["job_path"], []).append(name)
        for name, items in (("unreadable", got.unreadable), ("not_a_granite_record", got.not_a_granite_record)):
            for c in items:
                where.setdefault(c["path"], []).append(name)
        return got, where
    got, where = partition(real_spool)
    leaves = {str(d) for d in real_spool.rglob("*") if d.is_dir() and not any(x.is_dir() for x in d.iterdir())}
    assert leaves and set(where) == leaves and all(len(v) == 1 for v in where.values())
    cut = tmp_path / "cut"
    shutil.copytree(real_spool / "critic-spool", cut / "critic-spool")
    req = next((cut / "critic-spool").glob("*/request.json"))
    req.write_bytes(req.read_bytes()[:200])
    got, where = partition(cut)
    assert len(got) == 0 and len(got.unreadable) == 1
    assert got.unreadable[0]["path"] == str(req.parent) and "request.json" in got.unreadable[0]["reason"]
    assert where == {str(req.parent): ["unreadable"]}


def test_box_job_reader_on_a_real_record():
    pytest.skip("no box-job folder (boss-jobs/<id>/) is committed in either checkout or on origin/frankie-tip; "
                "the box reader is written from S:2494-2576 and has not been run on a real record")


# ---- prices -----------------------------------------------------------------------------------------------
def test_worked_figures_of_the_proven_packet():
    n = 92427
    assert prices.cost(prices.SONNET, {"input_tokens": n})["total_exact"] in ("0.184854", "0.18485400")
    assert prices.cost(prices.HAIKU, {"input_tokens": n})["total_exact"] == "0.0092427"
    assert prices.cost(prices.SONNET, {"cache_read_input_tokens": n})["total_exact"] == "0.0092427"
    half = prices.cost(prices.SONNET, {"input_tokens": n}, batch=True)
    assert D(half["total_exact"]) == D("0.092427") and half["batch_factor"] == "0.5"
    assert "92427 x 2.00 / 1,000,000" in prices.cost(prices.SONNET, {"input_tokens": n})["lines"][0]["arithmetic"]
    # cache write is 1.25 x input; Haiku above 100,000 prompt tokens uses the higher tier
    assert prices.cost(prices.SONNET, {"cache_creation_input_tokens": 1_000_000})["total_exact"] == "2.5000"
    assert prices.cost(prices.HAIKU, {"input_tokens": 100001})["tier_prompt_tokens_up_to"] is None


def test_prices_table_against_the_text_of_the_bundled_skill_files():
    """The figures are read out of the TEXT of the claude-api skill files bundled with Claude Code 2.1.331, not out of
    the table that is being checked."""
    models = SKILL_SHARED / "models.md"
    if not models.exists():
        pytest.skip(f"the bundled claude-api skill files are not present here ({SKILL_SHARED}); prices not compared")
    text = models.read_text(encoding="utf-8")
    son = next(l for l in text.splitlines() if l.startswith("- **Claude Sonnet 5.5**"))
    hai = next(l for l in text.splitlines() if l.startswith("- **Claude Haiku 5.5**"))
    m = re.search(r"\(\$(\d+(?:\.\d+)?) / \$(\d+(?:\.\d+)?) per MTok\).*?cache reads at \$(\d+(?:\.\d+)?)", son)
    assert m, "the Sonnet 5.5 line of shared/models.md has a different wording now"
    t = prices.PRICES["models"][prices.SONNET]["tiers"]
    assert len(t) == 1 and (D(t[0]["input"]), D(t[0]["output"]), D(t[0]["cache_read"])) == tuple(D(x) for x in m.groups())
    h = re.search(r"at \$(\d+(?:\.\d+)?) / \$(\d+(?:\.\d+)?) per MTok when the prompt is (\d+)K tokens or fewer and "
                  r"\$(\d+(?:\.\d+)?) / \$(\d+(?:\.\d+)?) above", hai)
    assert h, "the Haiku 5.5 line of shared/models.md has a different wording now"
    lo, hi = prices.PRICES["models"][prices.HAIKU]["tiers"]
    assert (D(lo["input"]), D(lo["output"]), lo["prompt_tokens_up_to"], D(hi["input"]), D(hi["output"])) == \
        (D(h.group(1)), D(h.group(2)), int(h.group(3)) * 1000, D(h.group(4)), D(h.group(5)))
    caching = (SKILL_SHARED / "prompt-caching.md").read_text(encoding="utf-8")
    assert "1.25\u00d7 for 5-minute TTL" in caching and D(prices.PRICES["cache_write_multiplier"]["value"]) == D("1.25")
    assert "~0.1\u00d7 base input" in caching and D(prices.PRICES["cache_read_multiplier_when_no_figure"]["value"]) == D("0.1")
    assert "50% off **every token in the request" in (SKILL_SHARED / "cost-optimization.md").read_text(encoding="utf-8")
    assert D(prices.PRICES["batch_multiplier"]["value"]) == D("0.5")


# ---- arms -------------------------------------------------------------------------------------------------
def test_routing_tables_cover_the_purposes_granite_names():
    names = {"read-0001": "read-part", "read-0001-retry": "read-part", "read-0002-a": "read-part",
             "merge-1-final": "merge-notes", "merge-2-0003": "merge-notes",
             "granite-self-assessment": "self-assessment",
             "staged-0123456789abcdef-" + "a" * 24: "classroom-staged-part"}
    for name, fam in names.items():
        assert arms.purpose_family({"purpose": name, "writer": "box_job"}) == fam
        assert fam in arms.ROUTING
    assert arms.purpose_family({"purpose": None, "writer": "critic_spool"}) == arms.CRITIC_FAMILY
    assert set(arms.ROUTING) == {f for _, f in arms.PURPOSE_FAMILIES} | {arms.CRITIC_FAMILY}
    # a name outside the table is reported, treated as reasoning and urgent, never guessed
    r = arms.route({"purpose": "write-analysis", "writer": "box_job"})
    assert not r["in_table"] and r["kind"] == "reasoning" and r["urgent"] and r["note"] == "purpose not in the table"


def test_arms_on_the_real_call(real_spool):
    calls = list(baseline.read_calls(real_spool, "2026-09-15"))
    built = arms.build_arms(calls)
    assert built["requests"]["A"][0]["model"] == prices.SONNET and built["requests"]["B"][0]["model"] == prices.SONNET
    p = built["requests"]["A"][0]["params"]
    assert "temperature" not in p and "thinking" not in p and p["output_config"] == {"effort": "medium"}
    assert built["requests"]["A"][0]["send"] == "beta_fallback" and built["requests"]["A"][0]["fallbacks"] == "default"
    assert baseline.load_prompt(calls[0]) == p["messages"][0]["content"][0]["text"]
    for a in "CDE":
        assert "no context_fn" in built["not_built"][a] and a not in built["requests"]
    # with a function: the context is the function's, a conversation of one call gets no breakpoint,
    # and the urgent critic is not batched
    ctx = lambda c: baseline.load_prompt(c)[:3000]
    b2 = arms.build_arms(calls, context_fn=ctx)
    assert b2["requests"]["C"][0]["params"]["messages"][0]["content"][0]["text"] == ctx(calls[0])
    assert b2["requests"]["D"][0]["cache"] is False and "one call" in b2["requests"]["D"][0]["no_breakpoint_because"]
    assert b2["requests"]["E"] == [] and "urgent" in b2["set_apart"]["E"][0]["reason"]


def test_arm_d_prefix_is_common_to_the_conversation_and_arm_b_routes_by_kind(real_spool):
    # the context text is the real critic prompt (first 3000 characters, whole lines); only the last line differs by call
    real = baseline.load_prompt(baseline.read_calls(real_spool, "2026-09-15")[0])[:3000]
    stable = real[:real.rindex("\n") + 1]
    calls = [{"call_id": f"id{i}", "conversation_id": "c1", "purpose": f"read-000{i}", "writer": "box_job"} for i in (1, 2)]
    ctx = {c["call_id"]: stable + f"ask {c['call_id']}\n" for c in calls}
    built = arms.build_arms(calls, ("C", "D", "E"), context_fn=lambda c: ctx[c["call_id"]])
    for r, c in zip(built["requests"]["D"], calls):
        blocks = r["params"]["messages"][0]["content"]
        assert blocks[0]["text"] == stable and blocks[0]["cache_control"] == {"type": "ephemeral"}
        assert blocks[1]["text"] == f"ask {c['call_id']}\n" and "cache_control" not in blocks[1]
        assert r["model"] == prices.HAIKU          # reading call
    assert len(built["requests"]["E"]) == 2 and built["requests"]["E"][0]["send"] == "batch"
    assert built["requests"]["E"][0]["fallbacks"] is None and built["requests"]["E"][0]["betas"] is None


# ---- replay -----------------------------------------------------------------------------------------------
def _no_client(monkeypatch):
    import anthropic

    def boom(*a, **k):
        raise AssertionError("a client was made")
    monkeypatch.setattr(anthropic, "Anthropic", boom)


def test_plan_on_empty_folder_says_no_call_and_makes_no_client(tmp_path, monkeypatch):
    _no_client(monkeypatch)
    out = tmp_path / "plan.json"
    doc = replay.plan(tmp_path / "none", "2026-09-15", max_model_calls=5, budget_tokens=1000, out=out)
    assert doc["granite_calls_found"] == 0 and "no Granite call was found" in doc["note"]
    assert json.loads(out.read_text())["sends_nothing"] is True
    assert doc["budget"]["max_model_calls"] == 5
    with pytest.raises(replay.Refused):
        replay.go(doc, "greg said go", out_dir=tmp_path / "o")      # nothing to send: refused, still no client


def test_plan_makes_no_client_even_with_a_key_in_the_environment(real_spool, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key-placeholder-never-valid")
    _no_client(monkeypatch)
    out = tmp_path / "p.json"
    doc = replay.plan(real_spool, "2026-09-15", ("A", "B"), max_model_calls=2, budget_tokens=10**7, out=out)
    assert doc["token_count"]["A"] == ["estimate at 4 characters a token"] and doc["sends_nothing"] is True
    assert replay.main(["plan", "--receipts", str(real_spool), "--trade-day", "2026-09-15", "--arms", "A,B",
                        "--max-model-calls", "2", "--budget-tokens", str(10**7), "--out", str(tmp_path / "p2.json")]) == 0


def test_count_needs_gregs_words_and_sends_only_then(real_spool, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key-placeholder-never-valid")
    _no_client(monkeypatch)
    doc = replay.plan(real_spool, "2026-09-15", ("A",), max_model_calls=1, budget_tokens=10**7)
    for words in (None, "", "  "):
        with pytest.raises(replay.Refused, match="Greg's go"):
            replay.count(doc, words, out=tmp_path / "c.json")
    assert not (tmp_path / "c.json").exists()
    # with his words and a client handed in: the counts are the client's, the words are recorded, the plan given is unchanged
    est = doc["requests"]["A"][0]["input_tokens_planned"]
    # the stand-in answers with the figure Granite's own receipt recorded for this same prompt, not an invented one
    real = baseline.read_calls(real_spool, "2026-09-15")[0]["input_tokens"]
    assert real != est
    seen = []
    client = SimpleNamespace(messages=SimpleNamespace(count_tokens=lambda **k: (seen.append(k), SimpleNamespace(input_tokens=real))[1]))
    done = replay.count(doc, "his words", client=client, out=tmp_path / "c.json")
    assert len(seen) == 1 and done["requests"]["A"][0]["input_tokens_planned"] == real
    assert done["requests"]["A"][0]["input_tokens_how"] == "count_tokens" and done["greg_go"] == "his words"
    assert doc["requests"]["A"][0]["input_tokens_planned"] == est and doc["greg_go"] is None
    assert json.loads((tmp_path / "c.json").read_text())["counted_on_greg_go"] == "his words"


def test_budget_is_the_callers_and_includes_the_output_reserve(real_spool, tmp_path):
    with pytest.raises(replay.Refused, match="over max_model_calls 1"):
        replay.plan(real_spool, "2026-09-15", ("A", "B"), max_model_calls=1, budget_tokens=10**7, out=tmp_path / "p.json")
    ok = replay.plan(real_spool, "2026-09-15", ("A", "B"), max_model_calls=2, budget_tokens=10**7)
    pl = ok["planned"]
    assert pl["model_calls"] == 2 and pl["output_reserved_tokens"] == 2 * 16000
    # input alone fits, input plus the reserved output does not: refused, naming the figure
    inp = pl["input_tokens"]
    with pytest.raises(replay.Refused, match=rf"{inp} plus output reserved 32000 = {inp + 32000} are over max_tokens {inp + 1}"):
        replay.plan(real_spool, "2026-09-15", ("A", "B"), max_model_calls=2, budget_tokens=inp + 1, out=tmp_path / "p.json")
    assert not (tmp_path / "p.json").exists()
    # the plan's budget is required on the command line
    with pytest.raises(SystemExit):
        replay.main(["plan", "--receipts", str(real_spool), "--trade-day", "2026-09-15", "--budget-tokens", "5", "--out", "x"])


def test_go_refuses_without_greg_go_and_plan_over_budget(real_spool, tmp_path, monkeypatch):
    _no_client(monkeypatch)
    doc = replay.plan(real_spool, "2026-09-15", ("A", "B"), max_model_calls=2, budget_tokens=10**7, out=tmp_path / "p.json")
    assert doc["granite_calls_found"] == 1 and doc["planned"]["model_calls"] == 2
    assert set(doc["budget"]) == set(replay.BUDGET_FIELDS) and doc["fits_budget"] is True
    for words in (None, "", "   "):
        with pytest.raises(replay.Refused, match="Greg's go"):
            replay.go(doc, words, out_dir=tmp_path / "o")
    over = json.loads(json.dumps(doc))
    over["budget"]["max_tokens"] = 10
    with pytest.raises(replay.Refused, match="over max_tokens 10"):
        replay.go(over, "his words", out_dir=tmp_path / "o")
    (tmp_path / "over.json").write_text(json.dumps(over))
    assert replay.main(["go", "--plan", str(tmp_path / "over.json"), "--out-dir", str(tmp_path / "o")]) == 2


def _fake_message(stop_reason, details=None):
    u = SimpleNamespace(input_tokens=None, output_tokens=None, cache_creation_input_tokens=None, cache_read_input_tokens=None)
    return SimpleNamespace(usage=u, model="claude-sonnet-5-5", stop_reason=stop_reason, stop_details=details, content=[])


def test_go_records_greg_go_a_refusal_and_figures_not_carried(real_spool, tmp_path):
    """Shape of the recording code with API-shaped stand-ins for the client; no figure is invented (the usage
    fields the stand-in does not carry are None and stay None on the line)."""
    doc = replay.plan(real_spool, "2026-09-15", ("A",), max_model_calls=1, budget_tokens=10**7)
    est = doc["requests"]["A"][0]["input_tokens_planned"]
    msg = _fake_message("refusal", {"category": "a-category", "explanation": "an-explanation"})
    client = SimpleNamespace(
        messages=SimpleNamespace(count_tokens=lambda **k: SimpleNamespace(input_tokens=est)),
        beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **k: msg)))
    res = replay.go(doc, "his words", out_dir=tmp_path / "o", client=client)
    lines = [json.loads(x) for x in Path(res["per_call_lines"]).read_text().splitlines()]
    assert lines[0]["record"] == "head" and lines[0]["greg_go"] == "his words"
    l = lines[1]
    assert l["stop_reason"] == "refusal" and l["stop_details"] == {"category": "a-category", "explanation": "an-explanation"}
    assert l["output"] is None and "refusal" in l["output_not_given_because"] and l["granite_position"] == 1
    assert all(l[k] is None for k in prices.USAGE_FIELDS) and l["cost"]["total"] is None
    receipt = json.loads(Path(res["receipt"]).read_text())
    assert receipt["greg_go"] == "his words" and res["unresolved"] == []
    # the report keeps the row, leaves the point out, and says so
    out = report.report(report.read_lines(res["per_call_lines"]), tmp_path / "r")
    assert out["table_rows"] == 1 and out["rows_with_no_figure_per_arm"] == {"A": 1}
    assert out["points_plotted_per_arm"]["per_call"] == {"A": 0}


def test_batch_results_that_are_not_succeeded_are_recorded_with_their_reason(real_spool, tmp_path):
    doc = replay.plan(real_spool, "2026-09-15", ("A",), max_model_calls=1, budget_tokens=10**7)
    r = dict(doc["requests"]["A"][0], arm="E")
    got = []
    state = {"calls": 0, "tokens": 0, "t0": __import__("time").time(), "stopped": None, "unmatched": []}
    err = SimpleNamespace(type="error", request_id="req-shape", error=SimpleNamespace(type="invalid_request_error", message="a-reason"))
    results = [SimpleNamespace(custom_id="E-" + r["call_id"][:60], result=SimpleNamespace(type="errored", error=err)),
               SimpleNamespace(custom_id="E-not-a-request", result=SimpleNamespace(type="expired"))]
    est = r["input_tokens_planned"]
    client = SimpleNamespace(messages=SimpleNamespace(
        count_tokens=lambda **k: SimpleNamespace(input_tokens=est),
        batches=SimpleNamespace(create=lambda requests: SimpleNamespace(id="b", processing_status="ended"),
                                results=lambda bid: iter(results))))
    r["input_tokens_how"] = "count_tokens"
    replay._run_batch(client, [r], lambda *a: got.append(("ok", a)), lambda arm, req, res, wall: got.append(("failed", res.result.type, res.result.error.error.message)),
                      state, doc["budget"], lambda x: x["input_tokens_planned"])
    assert got == [("failed", "errored", "a-reason")] and state["unmatched"] == [{"custom_id": "E-not-a-request", "result_type": "expired"}]
    # a batch whose whole reserve passes the budget is not created
    state2 = {"calls": 0, "tokens": 0, "t0": __import__("time").time(), "stopped": None, "unmatched": []}
    tight = dict(doc["budget"], max_tokens=est + 1)
    client.messages.batches.create = lambda requests: (_ for _ in ()).throw(AssertionError("batch created"))
    replay._run_batch(client, [r], None, None, state2, tight, lambda x: x["input_tokens_planned"])
    assert "output reserved" in state2["stopped"]


def test_nothing_sends_at_import_or_in_plan():
    src = Path(replay.__file__).read_text()
    plan_src = src[src.index("def plan("):src.index("def _baseline_apart(")]
    for needle in (".messages.create", ".batches.create", "Anthropic(", "count_tokens(r, client", "_client("):
        assert needle not in plan_src


# ---- report -----------------------------------------------------------------------------------------------
def test_report_with_no_line_writes_nothing(tmp_path):
    res = report.report([], tmp_path / "r")
    assert res["written"] is False and "nothing to plot" in res["reason"] and not (tmp_path / "r").exists()


def test_report_reconciles_rows_and_points_on_the_real_call_figures(real_spool, tmp_path):
    """Shape check of the report code on the real Granite figures of the one real call (arm label 'granite-record',
    its own usage, nothing made up). The record carries no cache figures: those cells are empty, not 0."""
    c = baseline.read_calls(real_spool, "2026-09-15")[0]
    line = {"arm": "granite-record", "call_id": c["call_id"], "input_tokens": c["input_tokens"],
            "output_tokens": c["output_tokens"], "cost": {}}
    res = report.report([line], tmp_path / "r")
    assert res["written"] and res["table_rows"] == 1 and res["points_plotted_per_arm"]["per_call"] == {"granite-record": 1}
    assert res["rows_with_no_figure_per_arm"] == {"granite-record": 0}
    rows = [json.loads(x) for x in (tmp_path / "r" / "token-test-table.jsonl").read_text().splitlines()]
    assert rows[0]["total_tokens"] == rows[0]["cumulative_tokens"] == 92428 + 119
    assert rows[0]["cache_creation_input_tokens"] is None and rows[0]["figures_not_recorded"] == [
        "cache_creation_input_tokens", "cache_read_input_tokens"]
    assert rows[0]["cost_usd"] is None
    assert "granite_position" in (tmp_path / "r" / "token-test-table.csv").read_text().splitlines()[0]
    assert (tmp_path / "r" / "token-test-tokens-cumulative.png").stat().st_size > 0
    # the same call is at the same place for every arm; a row with no usage figure is a row, not a point
    nofig = {"arm": "other", "call_id": c["call_id"], "output_tokens": c["output_tokens"]}
    two = report.report([line, nofig], tmp_path / "r2")
    assert two["table_rows"] == 2 and two["rows_with_no_figure_per_arm"] == {"granite-record": 0, "other": 1}
    assert two["points_plotted_per_arm"]["cumulative"] == {"granite-record": 1, "other": 0}
    rows2 = [json.loads(x) for x in (tmp_path / "r2" / "token-test-table.jsonl").read_text().splitlines()]
    assert rows2[0]["granite_position"] == rows2[1]["granite_position"] == 1
    assert rows2[1]["total_tokens"] is None and rows2[1]["cumulative_tokens"] is None
    s = report.running_sums([line, nofig])
    assert s["calls"] == 2 and s["calls_with_no_figure"] == 1 and s["last"]["output_tokens"] == 2 * 119
    assert s["last"]["cache_read_input_tokens"] is None and s["last"]["cost_usd"] is None


def test_report_raises_and_writes_nothing_when_counts_differ(tmp_path, monkeypatch):
    real = report._figures

    def short(rows):
        figs, plotted = real(rows)
        plotted["per_call"] = {a: n - 1 for a, n in plotted["per_call"].items()}
        return figs, plotted
    monkeypatch.setattr(report, "_figures", short)
    with pytest.raises(report.ReportMismatch):
        report.report([{"arm": "x", "call_id": "k", "input_tokens": 1, "output_tokens": 1}], tmp_path / "r")
    assert not (tmp_path / "r").exists()


def test_replay_result_report():
    pytest.skip("no replay of any arm has been run (it needs Greg's go): there is no real per-arm call line to report on")
