"""Ticket 03b: every run of the other agents has an auditor's report with its own row.

Real records only: the run record, the auditor's reports and TICKET_RUNS.json of a markets-data checkout,
as they stand and as they were at named commits (read with git, no checkout). No made-up run line.
Expected values are derived below from the record's auditor lines in a few independent lines, never by
calling the code under test.
"""

from __future__ import annotations

import json
import re
import subprocess

import pytest

from tests.agent_program.realrecords import PAPER, data_root
from tools.kgraph import auditor_called as ac

RUNS = f"{PAPER}/agent-runs.jsonl"
AUDITOR = "frankie-performance-auditor"


def _git_show(root, commit, path):
    r = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"], capture_output=True, text=True)
    if r.returncode:
        pytest.skip(f"markets-data checkout has no {commit}:{path} (shallow clone?)")
    return r.stdout


def _lines(root, at=None):
    text = _git_show(root, at, RUNS) if at else (root / RUNS).read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def _expected(lines):
    """From the auditor lines only: (all runs, auditor runs, cleared, record_only)."""
    runs = {d["run"] for d in lines}
    auditors = {d["run"] for d in lines if "audits" in d}
    cleared, rec_only = set(), set()
    reported = {d["run"] for d in lines if d.get("audit_report", {}).get("commit")}
    for d in lines:
        if "audits" in d and d["run"] in reported:
            cleared |= set(d["audits"])
            rec_only |= set(d.get("record_only", []))
    return runs, auditors, cleared, rec_only


def _tokens_have_row(text, n):
    """Independent few lines: a line that has the token 'rN' or the two tokens 'run' 'N'."""
    for ln in text.splitlines():
        t = re.split(r"[^A-Za-z0-9]+", ln)
        if f"r{n}" in t or any(a.lower() == "run" and b == str(n) for a, b in zip(t, t[1:])):
            return True
    return False


def test_real_record_as_it_stands_each_run_in_exactly_one_place():
    root = data_root()
    runs, auditors, cleared, rec_only = _expected(_lines(root))
    rep = ac.analyse(root)
    places = [set(rep.with_row), set(rep.record_only), set(rep.not_audited), set(rep.auditors)]
    assert sum(len(p) for p in places) == len(set().union(*places)) == len(runs)
    assert set().union(*places) == runs
    assert set(rep.auditors) == auditors == {111, 116, 120}
    assert set(rep.record_only) == (cleared & rec_only) - auditors
    assert set(rep.with_row) == (cleared - rec_only) - auditors
    assert set(rep.not_audited) == runs - auditors - cleared
    assert 119 in rep.not_audited and 120 not in rep.not_audited


def test_real_record_as_it_stands_names_no_run_whose_row_is_missing():
    # every number an auditor line names has its row in the report that line names: independent check
    root = data_root()
    for d in _lines(root):
        if "audit_report" in d and d["audit_report"].get("commit"):
            ar = d["audit_report"]
            text = _git_show(root, ar["commit"], ar["path"])
            assert all(_tokens_have_row(text, n) for n in d["audits"]), d["run"]
    assert ac.analyse(root).notes == {}


def test_run_107_has_its_own_row_and_run_50_is_audited_from_the_record_alone():
    rep = ac.analyse(data_root())
    assert 107 in rep.with_row and 107 not in rep.record_only
    assert 50 in rep.record_only and 50 not in rep.with_row


def test_whole_token_run_11_is_not_run_110():
    root = data_root()
    a116 = _git_show(root, "932f38f", f"{PAPER}/audits-20261124/AUDIT_RUN_116.md")
    assert re.search(r"^## Run 110 ", a116, re.M) and not re.search(r"^## Run 11\b", a116, re.M)
    assert ac.has_row(a116, 110) and not ac.has_row(a116, 11)
    assert not ac.has_row(a116, 1) and not ac.has_row("see r110 and run 110", 11)
    assert ac.has_row("L113 r107 reviewer | x", 107) and not ac.has_row("L113 r107 reviewer | x", 10)


def test_at_2a2d229_run_117_is_not_audited():
    # run 117's line had been added and no auditor named it
    root = data_root()
    rep = ac.analyse(root, at="2a2d229")
    assert 117 in rep.not_audited
    assert ac.main(["--data", str(root), "--at", "2a2d229"]) == 1


def test_at_2a2d229_an_auditor_line_with_no_audit_report_clears_nothing():
    # REAL CASE: at 2a2d229 the lines of runs 111 and 116 carry `audits` but no `audit_report`
    # (the plan expected 110, 112, 113 to be cleared here; its own rule 2 says they are not)
    root = data_root()
    lines = _lines(root, "2a2d229")
    assert [d["run"] for d in lines if "audits" in d and "audit_report" not in d] == [111, 116]
    rep = ac.analyse(root, at="2a2d229")
    assert {110, 112, 113} <= set(rep.not_audited)
    assert all("audit_report" in rep.notes[n] for n in (110, 112, 113))


def test_at_932f38f_report_exists_but_the_line_that_names_it_comes_later():
    root = data_root()
    assert "audit_report" not in [d for d in _lines(root, "932f38f") if d["run"] == 116][0]
    rep = ac.analyse(root, at="932f38f")
    assert {110, 112, 113} <= set(rep.not_audited)


def test_at_1f27fc7_run_111_names_1_to_109_without_a_report_so_none_is_cleared():
    root = data_root()
    rep = ac.analyse(root, at="1f27fc7")
    assert set(range(1, 110)) <= set(rep.not_audited)
    assert rep.with_row == [] and rep.record_only == []


def test_at_3317d7e_report_named_without_a_commit_clears_nothing():
    root = data_root()
    d = [x for x in _lines(root, "3317d7e") if x["run"] == 120][0]
    assert "audit_report" in d and "commit" not in d["audit_report"]
    rep = ac.analyse(root, at="3317d7e")
    assert {114, 115, 117} <= set(rep.not_audited)
    assert all("commit" in rep.notes[n] for n in (114, 115, 117))


# ---- the command: printed lists, exit codes, --ticket ----

def _ticket_runs(root):
    return json.loads((root / PAPER / "tickets-44-20261124" / "TICKET_RUNS.json").read_text())


def _unaudited_now(root):
    runs, auditors, cleared, _ = _expected(_lines(root))
    return runs - auditors - cleared


def test_command_on_the_real_record_prints_the_four_lists_and_fails_while_one_run_is_unaudited(capsys):
    root = data_root()
    unaudited = _unaudited_now(root)
    code = ac.main(["--data", str(root)])
    out = capsys.readouterr().out
    assert code == (1 if unaudited else 0) == 1
    for head in ("(1) NOT AUDITED", "(2) AUDITED FROM THE RECORD ALONE", "(3) OUTSIDE THE ROSTER",
                 "(4) THE AUDITOR'S OWN RUNS"):
        assert head in out
    section1 = out.split("(2) AUDITED FROM THE RECORD ALONE")[0]
    assert all(re.search(rf"^run {n} \|", section1, re.M) for n in unaudited)
    assert "run 119 |" in section1 and "run 120 |" not in section1
    # the limit told and the figure reached, as the run's own plan file and newest line hold them
    line119 = re.search(r"^run 119 \|.*$", section1, re.M).group(0)
    plan = json.loads((root / PAPER / "run-plans" / "run-0119.json").read_text())
    assert f"max_tokens={plan['max_tokens']}" in line119
    newest = [d for d in _lines(root) if d["run"] == 119][-1]
    assert f"tool_calls={newest['tool_calls']}" in line119 and newest["model"] in line119
    # an auditor's own runs are never in list (1); outside-roster runs carry their role
    assert "run 111 |" not in section1
    assert "main session" in out
    assert re.search(r"^COUNTS runs=\d+ not_audited=%d " % len(unaudited), out, re.M)


def test_ticket_03b_and_02_follow_the_record_and_01_fails_on_its_unaudited_run(capsys):
    root = data_root()
    tix, unaudited = _ticket_runs(root), _unaudited_now(root)
    for tid in ("03b", "02", "01"):
        bad = unaudited & set(tix[tid])
        code = ac.main(["--data", str(root), "--ticket", tid])
        out = capsys.readouterr().out
        assert code == (1 if bad else 0), tid
        assert all(re.search(rf"^run {n} \|", out, re.M) for n in tix[tid])
        for n in bad:
            assert f"run {n}" in out and "NOT AUDITED" in out
    assert not (unaudited & set(tix["03b"])) and not (unaudited & set(tix["02"]))
    assert 119 in tix["01"] and 119 in unaudited


def test_ticket_with_no_entry_exits_1_and_says_why(capsys):
    root = data_root()
    assert "99" not in _ticket_runs(root)
    assert ac.main(["--data", str(root), "--ticket", "99"]) == 1
    assert "no entry" in capsys.readouterr().out


def test_ticket_at_a_commit_reads_the_file_and_the_record_as_they_were(capsys):
    root = data_root()
    at = "b96fc54"  # the first commit that holds TICKET_RUNS.json
    tix = json.loads(_git_show(root, at, f"{PAPER}/tickets-44-20261124/TICKET_RUNS.json"))
    lines = _lines(root, at)
    runs, auditors, cleared, _ = _expected(lines)
    for tid, listed in tix.items():
        if tid == "note":
            continue
        bad = {n for n in listed if n not in runs or n in (runs - auditors - cleared)}
        assert ac.main(["--data", str(root), "--at", at, "--ticket", tid]) == (1 if bad else 0), tid
        capsys.readouterr()
