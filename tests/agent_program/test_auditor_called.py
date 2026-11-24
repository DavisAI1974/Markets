"""Ticket 03b: every run of the other agents has an auditor's report with its own row.

Real records only: the run record, the auditor's reports and TICKET_RUNS.json of a markets-data checkout,
as they stand and as they were at named commits (read with git, no checkout). Every check above the last
section rests on real lines only; the last section says exactly what it changes in a real line.
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


def _agent(d):
    return d.get("agent_type") or (str(d.get("role", "")).lower().split() or [""])[0].strip(",.;:()")


def _expected(lines):
    """From the lines only: (all runs, auditor runs, cleared, record_only). A run is an auditor's run by its
    NEWEST line; what it names is the union over its lines; a name counts when one of its lines has an
    audit_report with a commit."""
    runs = {d["run"] for d in lines}
    newest = {d["run"]: d for d in lines}          # later lines overwrite: the newest line of each run
    auditors = {r for r, d in newest.items() if _agent(d) == AUDITOR}
    reported = {d["run"] for d in lines if d.get("audit_report", {}).get("commit")}
    says = {}       # run -> one entry per clearing auditor run: does that auditor list it as record-only?
    for a in sorted(auditors & reported):
        mine = [d for d in lines if d["run"] == a]
        names = {n for d in mine for n in d.get("audits", [])}
        rec = {n for d in mine for n in d.get("record_only", [])}
        for n in names:
            says.setdefault(n, []).append(n in rec)
    cleared = set(says)
    # record-only only when EVERY auditor that clears the run lists it as record-only
    rec_only = {n for n, v in says.items() if all(v)}
    return runs, auditors, cleared, rec_only


def _no_report(lines):
    """Auditor runs (by newest line) none of whose lines names an audit_report with a commit."""
    _, auditors, _, _ = _expected(lines)
    reported = {d["run"] for d in lines if d.get("audit_report", {}).get("commit")}
    return auditors - reported


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
    assert set(rep.auditors) == auditors
    assert set(rep.record_only) == (cleared & rec_only) - auditors
    assert set(rep.with_row) == (cleared - rec_only) - auditors
    assert set(rep.not_audited) == runs - auditors - cleared
    assert set(rep.no_report) == _no_report(_lines(root))


def test_real_record_as_it_stands_names_no_run_whose_row_is_missing():
    # every number an auditor line names has its row in the report that line names: independent check
    root = data_root()
    for d in _lines(root):
        if "audit_report" in d and d["audit_report"].get("commit"):
            ar = d["audit_report"]
            text = _git_show(root, ar["commit"], ar["path"])
            assert all(_tokens_have_row(text, n) for n in d["audits"]), d["run"]
    assert ac.analyse(root).notes == {}


def test_at_9bfef60_runs_118_119_121_are_not_audited_and_auditor_runs_are_111_116_120():
    root = data_root()
    _git_show(root, "9bfef60", RUNS)
    rep = ac.analyse(root, at="9bfef60")
    assert max(rep.lines) == 121
    assert set(rep.not_audited) == {118, 119, 121}
    assert set(rep.auditors) == {111, 116, 120} and rep.no_report == []
    assert ac.main(["--data", str(root), "--at", "9bfef60"]) == 1


def test_at_d75eff9_runs_118_119_121_have_their_own_row_and_run_125_is_not_audited():
    root = data_root()
    rep = ac.analyse(root, at="d75eff9")
    assert {118, 119, 121} <= set(rep.with_row) and 125 in rep.not_audited
    assert not {118, 119, 121} & set(rep.not_audited)


def test_run_107_has_its_own_row_and_run_50_is_audited_from_the_record_alone():
    rep = ac.analyse(data_root(), at="9bfef60")
    assert 107 in rep.with_row and 107 not in rep.record_only
    assert 50 in rep.record_only and 50 not in rep.with_row


def test_whole_token_run_11_is_not_run_110():
    root = data_root()
    a116 = _git_show(root, "932f38f", f"{PAPER}/audits-20261124/AUDIT_RUN_116.md")
    assert re.search(r"^## Run 110 ", a116, re.M) and not re.search(r"^## Run 11\b", a116, re.M)
    assert ac.has_row(a116, 110) and not ac.has_row(a116, 11)
    assert not ac.has_row(a116, 1)
    # real lines, read with git: a row of the first report and a heading of the second
    a111 = _git_show(root, "1f27fc7", f"{PAPER}/audits-20261124/AUDIT_RUN_111.md")
    row = next(x for x in a111.splitlines() if x.startswith("L113 r107 reviewer |"))
    head = next(x for x in a116.splitlines() if x.startswith("## Run 110 (builder,"))
    assert ac.has_row(row, 107) and not ac.has_row(row, 10) and not ac.has_row(row, 1)
    assert ac.has_row(head, 110) and not ac.has_row(head, 11) and not ac.has_row(head, 1)


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
    assert rep.no_report == [111]


def test_command_at_1f27fc7_exits_1_and_says_run_111_names_no_report(capsys):
    root = data_root()
    _git_show(root, "1f27fc7", RUNS)
    assert ac.main(["--data", str(root), "--at", "1f27fc7"]) == 1
    out = capsys.readouterr().out
    sec4 = out.split("(4) THE AUDITOR'S OWN RUNS")[1].split("(5)")[0]
    assert re.search(r"^run 111 \|.*names no report", sec4, re.M)


def test_an_auditor_run_is_so_by_its_newest_line_and_no_report_follows_the_record():
    # the record as it stands and at fixed commits: the auditor runs and the no-report runs follow the lines
    root = data_root()
    for at in (None, "9bfef60", "c0d4ff1", "2a2d229", "1f27fc7", "d75eff9"):
        lines = _lines(root, at)
        rep = ac.analyse(root, at=at)
        assert set(rep.auditors) == _expected(lines)[1], at
        assert set(rep.no_report) == _no_report(lines), at
    assert ac.analyse(root, at="c0d4ff1").no_report == [111, 116, 120]


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


def test_command_on_the_real_record_prints_the_lists_and_exits_as_the_record_says(capsys):
    root = data_root()
    lines = _lines(root)
    unaudited = _unaudited_now(root)
    code = ac.main(["--data", str(root)])
    out = capsys.readouterr().out
    assert code == (1 if unaudited or _no_report(lines) else 0)
    assert out.splitlines()[0] == f"data: {root}"
    for head in ("(1) NOT AUDITED", "(2) AUDITED FROM THE RECORD ALONE", "(3) OUTSIDE THE ROSTER",
                 "(4) THE AUDITOR'S OWN RUNS"):
        assert head in out
    section1 = out.split("(2) AUDITED FROM THE RECORD ALONE")[0]
    assert sorted(int(x) for x in re.findall(r"^run (\d+) \|", section1, re.M)) == sorted(unaudited)
    auditors = _expected(lines)[1]
    assert not any(re.search(rf"^run {n} \|", section1, re.M) for n in auditors)
    for n in sorted(unaudited)[:1]:
        # the limit told and the figure reached, as the run's own plan file and newest line hold them
        line_n = re.search(rf"^run {n} \|.*$", section1, re.M).group(0)
        plan_file = root / PAPER / "run-plans" / f"run-{n:04d}.json"
        if plan_file.exists():
            assert f"max_tokens={json.loads(plan_file.read_text())['max_tokens']}" in line_n
        newest = [d for d in lines if d["run"] == n][-1]
        assert f"tool_calls={newest['tool_calls']}" in line_n and newest["model"] in line_n
    if any(str(d.get("role", "")).startswith("main session") for d in lines):
        assert "main session" in out
    assert re.search(r"^COUNTS runs=\d+ not_audited=%d " % len(unaudited), out, re.M)
    sec4 = out.split("(4) THE AUDITOR'S OWN RUNS")[1].split("(5)")[0]
    for n in _no_report(lines):
        assert re.search(rf"^run {n} \|.*names no report", sec4, re.M)


def test_every_ticket_as_the_record_stands_exits_as_its_runs_stand(capsys):
    root = data_root()
    tix = _ticket_runs(root)
    runs, auditors, cleared, _ = _expected(_lines(root))
    unaudited = runs - auditors - cleared
    for tid, listed in tix.items():
        if tid == "note":
            continue
        bad = {n for n in listed if n not in runs or n in unaudited or n in _no_report(_lines(root))}
        code = ac.main(["--data", str(root), "--ticket", tid])
        out = capsys.readouterr().out
        assert code == (1 if bad else 0), tid
        assert all(re.search(rf"^run {n} \|", out, re.M) for n in listed)
        for n in bad:
            assert f"run {n}" in out and ("NOT AUDITED" in out or "names no report" in out)


def test_tickets_03b_and_02_at_9cea759_and_03b_at_c0d4ff1(capsys):
    root = data_root()
    tix = json.loads(_git_show(root, "9cea759", f"{PAPER}/tickets-44-20261124/TICKET_RUNS.json"))
    assert tix["03b"] == [111, 116, 120, 121] and 118 in tix["02"]
    runs, auditors, cleared, _ = _expected(_lines(root, "9cea759"))
    for tid in ("03b", "02"):
        bad = {n for n in tix[tid] if n not in runs or n in (runs - auditors - cleared)
               or n in _no_report(_lines(root, "9cea759"))}
        code = ac.main(["--data", str(root), "--at", "9cea759", "--ticket", tid])
        capsys.readouterr()
        assert code == (1 if bad else 0), tid
    old = json.loads(_git_show(root, "c0d4ff1", f"{PAPER}/tickets-44-20261124/TICKET_RUNS.json"))
    assert old["03b"] == [111, 116, 120]
    # EXPECTATION CHANGED (second read, point 4): 111, 116 and 120 named no report there, and an auditor's run
    # that names no report fails its ticket ("the auditor's report for each of its runs is kept in git")
    assert ac.main(["--data", str(root), "--at", "c0d4ff1", "--ticket", "03b"]) == 1
    out = capsys.readouterr().out
    assert all(re.search(rf"^run {n} \|.*names no report", out, re.M) for n in (111, 116, 120))


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
        # EXPECTATION CHANGED (second read, point 4): an auditor's run that names no report also fails its ticket
        bad = {n for n in listed if n not in runs or n in (runs - auditors - cleared) or n in _no_report(lines)}
        assert ac.main(["--data", str(root), "--at", at, "--ticket", tid]) == (1 if bad else 0), tid
        capsys.readouterr()


# ---- a row is a line that STARTS with the run; a plan with no line in the record is listed ----

def test_an_indented_mention_inside_another_runs_block_is_not_a_row_in_audit_run_120():
    root = data_root()
    text = _git_show(root, "3317d7e", f"{PAPER}/audits-20261124/AUDIT_RUN_120.md")
    lines = text.splitlines()
    # facts read from the real report: headings for 114, 115 and 117 only
    assert [x for x in lines if re.match(r"^#+ +[Rr]un \d+", x)] == [
        x for x in lines if x.startswith(("## Run 114 ", "## Run 115 ", "## Run 117 "))]
    for n in (114, 115, 117):
        assert ac.has_row(text, n), n
    for n in (107, 109, 110, 112, 113):
        assert not ac.has_row(text, n), n
    # the two real indented prose lines, alone
    l71, l120 = lines[70], lines[119]
    assert l71.startswith("   Run 110 has no harness total") and l120.startswith("   Run 107 was a re-read")
    assert not ac.has_row(l71, 110) and not ac.has_row(l120, 107)


def test_the_other_reports_have_exactly_the_rows_they_hold():
    root = data_root()
    a116 = _git_show(root, "932f38f", f"{PAPER}/audits-20261124/AUDIT_RUN_116.md")
    assert [n for n in range(100, 121) if ac.has_row(a116, n)] == [110, 112, 113]
    a111 = _git_show(root, "1f27fc7", f"{PAPER}/audits-20261124/AUDIT_RUN_111.md")
    assert all(ac.has_row(a111, n) for n in range(1, 110))
    assert all(re.search(rf"^L\d+ r{n} ", a111, re.M) for n in range(1, 110))


# ---- --data is used or refused, never another checkout; the first line names what was read ----

def test_data_on_a_folder_with_no_run_record_is_refused_and_names_the_folder(tmp_path, capsys, monkeypatch):
    root = data_root()
    monkeypatch.setenv("MARKETS_DATA", str(root))         # a real checkout is within reach; it must not be read
    assert ac.main(["--data", str(tmp_path)]) == 2
    cap = capsys.readouterr()
    assert str(tmp_path) in cap.err and "agent-runs.jsonl" in cap.err
    assert "COUNTS" not in cap.out and "NOT AUDITED" not in cap.out
    assert ac.main(["--data", str(tmp_path), "--ticket", "03b"]) == 2
    assert str(tmp_path) in capsys.readouterr().err


def test_first_line_names_the_folder_and_with_at_the_commit(capsys):
    root = data_root()
    _git_show(root, "2a2d229", RUNS)
    ac.main(["--data", str(root), "--at", "2a2d229"])
    assert capsys.readouterr().out.splitlines()[0] == f"data: {root} at 2a2d229"
    ac.main(["--data", str(root), "--at", "9cea759", "--ticket", "03b"])
    assert capsys.readouterr().out.splitlines()[0] == f"data: {root} at 9cea759"


def test_plans_with_no_line_in_the_record_are_listed_exactly(capsys):
    root = data_root()
    recorded = {d["run"] for d in _lines(root)}
    planned = {int(p.stem.split("-")[1]) for p in (root / PAPER / "run-plans").glob("run-*.json")}
    expect = sorted(planned - recorded)
    rep = ac.analyse(root)
    assert rep.planned_no_line == expect
    ac.main(["--data", str(root)])
    out = capsys.readouterr().out
    sec = out.split("(5) A PLAN FILE AND NO LINE IN THE RECORD")[1]
    assert "in flight" in sec.splitlines()[0]
    assert [int(x) for x in re.findall(r"^run (\d+) \|", sec.split("COUNTS")[0], re.M)] == expect
    if not expect:
        return
    plan = json.loads((root / PAPER / "run-plans" / f"run-{expect[0]:04d}.json").read_text())
    assert plan["agent"] in sec and f"max_tool_calls={plan['max_tool_calls']}" in sec
    assert plan["task"].split()[0] in sec


def test_plans_with_no_line_at_b96fc54_read_the_folder_as_it_was():
    root = data_root()
    at = "b96fc54"
    r = subprocess.run(["git", "-C", str(root), "ls-tree", "--name-only", f"{at}:{PAPER}/run-plans/"],
                       capture_output=True, text=True)
    if r.returncode:
        pytest.skip("no run-plans folder at b96fc54")
    planned = {int(re.search(r"run-(\d+)\.json", x).group(1)) for x in r.stdout.split()}
    recorded = {d["run"] for d in _lines(root, at)}
    assert ac.analyse(root, at=at).planned_no_line == sorted(planned - recorded)


# ---- the second read: reports are the auditor's own; heading of list (3); a missing commit ----

def test_on_the_real_record_every_auditors_report_is_its_own_by_its_first_line():
    root = data_root()
    seen = 0
    for d in _lines(root):
        ar = d.get("audit_report") or {}
        if _agent(d) == AUDITOR and ar.get("commit"):
            first = _git_show(root, ar["commit"], ar["path"]).splitlines()[0]
            assert re.match(rf"# Performance auditor run {d['run']}[ (]", first), (d["run"], first)
            seen += 1
    assert seen >= 4
    assert ac.analyse(root).no_report == sorted(_no_report(_lines(root)))


def test_list_3_heading_says_a_general_agent_handed_a_roles_file_is_listed_with_its_role(capsys):
    root = data_root()
    ac.main(["--data", str(root), "--at", "9bfef60"])
    out = capsys.readouterr().out
    assert "a general agent handed a role's file is listed here, with its role" in out.split("(4)")[0].split("(3)")[1].splitlines()[0]


def test_an_at_that_is_not_a_commit_of_that_repository_says_so(capsys):
    root = data_root()
    assert ac.main(["--data", str(root), "--at", "0123abc"]) == 2
    err = capsys.readouterr().err
    assert "0123abc" in err and "not in that repository" in err and str(root) in err


def test_first_line_after_the_number_may_be_a_space_paren_colon_or_the_end_only():
    root = data_root()
    r = _report_of(root, 133)
    first = _git_show(root, r["commit"], r["path"]).splitlines()[0]       # the real first line of run 133's report
    assert first.startswith("# Performance auditor run 133 (")
    stem = first.split(" (")[0]
    assert ac.first_line_problem(first, 133) is None
    assert ac.first_line_problem(stem, 133) is None and ac.first_line_problem(stem + ": x", 133) is None
    assert ac.first_line_problem(stem + " x", 133) is None
    assert ac.first_line_problem(first, 13) == ac.ANOTHER
    assert ac.first_line_problem(stem + "4", 133) != None
    assert "does not begin with" in ac.first_line_problem("\ufeff" + first, 133)
    assert "does not begin with" in ac.first_line_problem(" " + first, 133)


def test_an_at_that_is_not_a_commit_without_data_is_refused_too(capsys, monkeypatch):
    root = data_root()
    monkeypatch.setenv("MARKETS_DATA", str(root))
    assert ac.main(["--at", "0123abc"]) == 2
    err = capsys.readouterr().err
    assert "0123abc" in err and "not in that repository" in err


def test_first_line_with_the_right_number_and_a_tab_full_stop_or_hyphen_says_what_is_so():
    root = data_root()
    r = _report_of(root, 133)
    first = _git_show(root, r["commit"], r["path"]).splitlines()[0]       # the real first line of run 133's report
    stem = first.split(" (")[0]
    for ch in ("\t", ".", "-"):
        problem = ac.first_line_problem(stem + ch + "x", 133)
        assert f"after `# Performance auditor run 133` its first line holds {ch!r}, where a space, `(`, `:` or the end of the line is expected" == problem
    assert "does not begin with" in ac.first_line_problem(" " + first, 133)


def test_list_4_prints_each_distinct_report_once_run_124_at_7c3d2af(capsys):
    # run 124's first line names its report with no commit, its second names it at a commit: two distinct entries
    root = data_root()
    _git_show(root, "7c3d2af", RUNS)
    lines124 = [d for d in _lines(root, "7c3d2af") if d["run"] == 124]
    assert len({(d["audit_report"]["path"], d["audit_report"].get("commit")) for d in lines124 if "audit_report" in d}) == 2
    ac.main(["--data", str(root), "--at", "7c3d2af"])
    row = re.search(r"^run 124 \|.*$", capsys.readouterr().out.split("(4)")[1], re.M).group(0)
    assert row.count("AUDIT_RUN_124.md@") == 2
    assert row.count("AUDIT_RUN_124.md@None (no commit named)") == 1 and row.count("(its own)") == 1


# ======================================================================================================
# CASES THE REAL RECORD DOES NOT HOLD: each is the real record at a named commit, cut or with real lines
# re-appended, copied to a scratch folder, with exactly the field(s) named in the case's own comment
# changed. Nothing here is a real run. How: `git clone --shared --no-checkout` of the markets-data checkout under tmp_path, with
# the record file written over it (and, for a case that is run with --ticket, a TICKET_RUNS.json that
# `_scratch(tickets=...)` writes: {"03b": [run]}, naming the run the case is about); chosen because the code reads every report with git from the folder
# given to --data, and a shared clone holds every real report commit. The real checkout is never written.
# ======================================================================================================

def _report_of(root, run):
    """The `audit_report` (path and commit) of the run's newest line that names one, read from the record
    AT f1e3be4, not from the checkout as it stands."""
    got = [d["audit_report"] for d in _lines(root, "f1e3be4") if d["run"] == run and d.get("audit_report", {}).get("commit")]
    assert got, f"run {run} names no report at f1e3be4"
    return got[-1]


def _scratch(tmp_path, root, lines, tickets=None):
    dest = tmp_path / "copy"
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(root), str(dest)], check=True)
    f = dest / RUNS
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps(d) + "\n" for d in lines), encoding="utf-8")
    if tickets:
        t = dest / PAPER / "tickets-44-20261124" / "TICKET_RUNS.json"
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(json.dumps(tickets), encoding="utf-8")
    return dest


def _newest(lines, run):
    return [d for d in lines if d["run"] == run][-1]


def test_case_m1_an_auditor_run_whose_newest_line_says_builder_is_checked_like_a_builder(tmp_path, capsys):
    # CHANGED: run 120's newest real line re-appended with agent_type and role = "builder"
    root = data_root()
    base = _lines(root, "d75eff9")
    line = dict(_newest(base, 120), agent_type="builder", role="builder")
    lines = base + [line]
    copy = _scratch(tmp_path, root, lines)
    rep = ac.analyse(copy)
    others = {n for a in (111, 116, 124) for d in base if d["run"] == a for n in d.get("audits", [])}
    named_by_120 = {n for d in base if d["run"] == 120 for n in d.get("audits", [])}
    assert 120 not in rep.auditors and 120 in rep.not_audited      # nobody else names 120
    assert (named_by_120 - others) and (named_by_120 - others) <= set(rep.not_audited)
    assert ac.main(["--data", str(copy)]) == 1
    out = capsys.readouterr().out
    assert ("run 120 was an auditor's run by an earlier line and is not by its newest: "
            "the audits it named are not counted") in out
    assert re.search(r"^run 120 \| builder \|", out.split("(2) AUDITED")[0], re.M)


def test_case_m2_a_run_that_names_no_report_fails_the_command_though_every_other_run_is_audited(tmp_path, capsys):
    # CHANGED: nothing in a line. The record is cut to runs up to 109, run 111's two real lines (the first
    # names audits 1 to 109 and no report; the newest names the report) and run 116's FIRST real line,
    # which names no report. Expected from the rule: exit 1 only because run 116 names no report.
    root = data_root()
    base = _lines(root, "d75eff9")
    first116 = [d for d in base if d["run"] == 116][0]
    assert "audit_report" not in first116
    lines = [d for d in base if d["run"] <= 109] + [d for d in base if d["run"] == 111] + [first116]
    copy = _scratch(tmp_path, root, lines)
    rep = ac.analyse(copy)
    assert rep.not_audited == [] and rep.no_report == [116]
    assert ac.main(["--data", str(copy)]) == 1
    assert re.search(r"^run 116 \|.*names no report", capsys.readouterr().out, re.M)


def test_case_m4_and_m5_a_name_without_a_row_in_the_report_clears_nothing(tmp_path, capsys):
    # CHANGED: run 116's newest real line, audits = its own + [118, 50]. Its real report has no row for 118
    # or 50. 118 is unaudited at 9bfef60 and stays so, with the note. 50 is record-only for run 111 and stays
    # record-only (116 does not clear it). No real report holds a row for a run another report holds, so
    # the half "a second auditor whose report DOES hold a row for 50" cannot be built from real reports.
    root = data_root()
    base = _lines(root, "9bfef60")
    l116 = _newest(base, 116)
    assert not ac.has_row(_git_show(root, l116["audit_report"]["commit"], l116["audit_report"]["path"]), 118)
    copy = _scratch(tmp_path, root, base + [dict(l116, audits=list(l116["audits"]) + [118, 50])])
    rep = ac.analyse(copy)
    assert 118 in rep.not_audited and "no row for run 118" in rep.notes[118]
    assert 50 in rep.record_only and 50 not in rep.with_row
    # EXPECTATION CHANGED (fourth read, point 2): a note is kept only for a run left NOT audited; 50 is audited
    assert 50 not in rep.notes


def test_case_g2b_a_report_that_is_another_auditors_is_no_report_of_its_own(tmp_path, capsys):
    # CHANGED: run 121's newest real line (a builder's) at 9bfef60 gets agent_type and role = the auditor's
    # type, audit_report = run 133's real report (path and commit, read at f1e3be4), audits = [118]
    root = data_root()
    base = _lines(root, "9bfef60")
    line = dict(_newest(base, 121), agent_type=AUDITOR, role=AUDITOR, audit_report=_report_of(root, 133), audits=[118])
    copy = _scratch(tmp_path, root, base + [line])
    rep = ac.analyse(copy)
    assert 121 in rep.no_report and 118 in rep.not_audited
    assert "another run's" in rep.notes[118]
    assert ac.main(["--data", str(copy)]) == 1
    assert re.search(r"^run 121 \|.*names no report.*the report it names is another run's",
                     capsys.readouterr().out, re.M)


@pytest.mark.parametrize("run, report_of", [(13, 133), (11, 111)])
def test_case_n3_a_report_whose_first_line_holds_the_number_inside_a_longer_one_is_not_that_runs_own(
        tmp_path, capsys, run, report_of):
    # CHANGED: a real line of run 13 (or 11) at 9bfef60, agent_type and role = the auditor's type and
    # audit_report = run 133's (or 111's) real report as the record held it at f1e3be4. "13" is inside "133".
    root = data_root()
    base = _lines(root, "9bfef60")
    line = dict(_newest(base, run), agent_type=AUDITOR, role=AUDITOR, audit_report=_report_of(root, report_of))
    copy = _scratch(tmp_path, root, base + [line])
    rep = ac.analyse(copy)
    assert run in rep.no_report and "another run's" in rep.no_report_why[run]
    assert ac.main(["--data", str(copy)]) == 1
    assert re.search(rf"^run {run} \|.*names no report.*another run's, not counted", capsys.readouterr().out, re.M)


def test_case_a_report_that_cannot_be_read_at_its_commit_is_no_report_and_fails_plain_and_ticket(tmp_path, capsys):
    # CHANGED: both real lines of run 120 at 9bfef60 replaced by its newest line, audit_report.commit = 0000000
    root = data_root()
    base = _lines(root, "9bfef60")
    new = _newest(base, 120)
    new = dict(new, audit_report=dict(new["audit_report"], commit="0000000"))
    copy = _scratch(tmp_path, root, [d for d in base if d["run"] != 120] + [new], tickets={"03b": [120]})
    rep = ac.analyse(copy)
    assert 120 in rep.no_report and "not readable at 0000000" in rep.no_report_why[120]
    assert ac.main(["--data", str(copy)]) == 1
    out = capsys.readouterr().out
    assert re.search(r"^run 120 \|.*names no report.*not readable at 0000000", out, re.M)
    assert ac.main(["--data", str(copy), "--ticket", "03b"]) == 1
    assert "names no report" in capsys.readouterr().out


def test_case_each_named_run_gets_the_reason_true_of_it_and_list_4_marks_each_report(tmp_path, capsys):
    # CHANGED: run 116's newest real line at 9bfef60 re-appended with audit_report = run 111's real report
    # (read at f1e3be4) and audits extended by 50 and 118
    root = data_root()
    base = _lines(root, "9bfef60")
    l116 = _newest(base, 116)
    line = dict(l116, audit_report=_report_of(root, 111), audits=list(l116["audits"]) + [50, 118])
    copy = _scratch(tmp_path, root, base + [line])
    rep = ac.analyse(copy)
    assert 116 not in rep.no_report                       # its own report is readable
    assert 118 in rep.not_audited and "its own report has no row for run 118" in rep.notes[118]
    assert "another run's" not in rep.notes[118]
    assert ac.main(["--data", str(copy)]) == 1
    out116 = re.search(r"^run 116 \|.*$", capsys.readouterr().out.split("(4)")[1], re.M).group(0)
    assert "AUDIT_RUN_116.md@" in out116 and "(its own)" in out116 and "(another run's, not counted)" in out116


