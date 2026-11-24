"""Stage 8 checks: the token test (tools/token_test). No model call is made by any check here; there is no key.

Real records only. The one real per-call Granite record on file is a committed critic-spool folder of the first
real run on the Frankie branch (`origin/frankie-tip`); it is read with `git show` into a scratch folder. Checks that
need a record that does not exist (a box-job folder, a replay result) are skipped with that reason, never fed made-up data.
"""

from __future__ import annotations

import base64
from decimal import Decimal as D
import json
import subprocess
from pathlib import Path

import pytest

from tools.token_test import arms, baseline, prices, replay, report

REPO = Path(__file__).resolve().parents[2]
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
    import datetime as dt
    et = baseline.ET
    f = lambda h, m=0: baseline.trade_day_of(dt.datetime(2026, 9, 15, h, m, tzinfo=et).timestamp())
    assert f(18) == ("day", "2026-09-16") and f(17, 59) == ("halt", None) and f(16, 59) == ("day", "2026-09-15")
    assert f(0) == ("day", "2026-09-15")


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
def test_plan_on_empty_folder_says_no_call_and_makes_no_client(tmp_path, monkeypatch):
    import anthropic

    def boom(*a, **k):
        raise AssertionError("a client was made")
    monkeypatch.setattr(anthropic, "Anthropic", boom)
    out = tmp_path / "plan.json"
    doc = replay.plan(tmp_path / "none", "2026-09-15", budget_tokens=1000, out=out)
    assert doc["granite_calls_found"] == 0 and "no Granite call was found" in doc["note"]
    assert json.loads(out.read_text())["sends_nothing"] is True
    with pytest.raises(replay.Refused):
        replay.go(doc, "greg said go", out_dir=tmp_path / "o")      # nothing to send: refused, still no client


def test_go_refuses_without_greg_go_and_plan_over_budget(real_spool, tmp_path):
    doc = replay.plan(real_spool, "2026-09-15", ("A", "B"), budget_tokens=10, out=tmp_path / "p.json")
    assert doc["granite_calls_found"] == 1 and doc["planned"]["model_calls"] == 2
    assert doc["token_count"]["A"] == ["estimate at 4 characters a token"]
    assert set(doc["budget"]) == set(replay.BUDGET_FIELDS) and doc["fits_budget"] is False
    for words in (None, "", "   "):
        with pytest.raises(replay.Refused, match="Greg's go"):
            replay.go(doc, words, out_dir=tmp_path / "o")
    with pytest.raises(replay.Refused, match="over max_tokens"):
        replay.go(doc, "his words", out_dir=tmp_path / "o")
    assert replay.main(["go", "--plan", str(tmp_path / "p.json"), "--out-dir", str(tmp_path / "o")]) == 2


def test_nothing_sends_at_import_or_in_plan():
    src = Path(replay.__file__).read_text()
    plan_src = src[src.index("def plan("):src.index("def _write(")]
    for needle in (".messages.create", ".batches.create", "Anthropic("):
        assert needle not in plan_src


# ---- report -----------------------------------------------------------------------------------------------
def test_report_with_no_line_writes_nothing(tmp_path):
    res = report.report([], tmp_path / "r")
    assert res["written"] is False and "nothing to plot" in res["reason"] and not (tmp_path / "r").exists()


def test_report_reconciles_rows_and_points_on_the_real_call_figures(real_spool, tmp_path):
    """Shape check of the report code on the real Granite figures of the one real call (arm label 'granite-record',
    its own usage, nothing made up). A replay result does not exist, so the arms' own report is not checked."""
    c = baseline.read_calls(real_spool, "2026-09-15")[0]
    line = {"arm": "granite-record", "call_id": c["call_id"], "input_tokens": c["input_tokens"],
            "output_tokens": c["output_tokens"], "cost": {}}
    res = report.report([line], tmp_path / "r")
    assert res["written"] and res["table_rows"] == 1 and res["points_plotted_per_arm"]["per_call"] == {"granite-record": 1}
    rows = [json.loads(x) for x in (tmp_path / "r" / "token-test-table.jsonl").read_text().splitlines()]
    assert rows[0]["total_tokens"] == rows[0]["cumulative_tokens"] == 92428 + 119
    assert (tmp_path / "r" / "token-test-tokens-cumulative.png").stat().st_size > 0


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
