"""Stage 3: the ratchet loop harness, checked on the real history of claude/tasty-runner.

No made-up change and no made-up figure. The loop works on a local clone of
/home/user/paper-trading-platform (never on that checkout) and replays real commits of its branch. The
figure is an engineering count: the number of checks that pass in the repository's own suite
(`python3 -m pytest tests/tasty_runner -q`, about 2 s a run). Never a trade figure.

Expected values come from outside the harness: git itself (ids, refs, files of a commit) and the counts
written in the record (the handoff of 2026-11-24 W: 26 checks pass at 0772834; the decisions file, twentieth
session: 17 pass at 13ddfa9). The first base commit 048acb0 follows 13ddfa9 by two commits that only touch
tasty/RUNNING_LIST.md (asserted below with git), so the record's 17 stands for it.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools.exp_dag import ExpDag
from tools.ratchet import program as prog
from tools.ratchet.loop import ReplayCommits, run_loop

from .realrecords import data_root

PLATFORM = Path("/home/user/paper-trading-platform")
TEMPLATE = Path(__file__).resolve().parents[2] / "tools/ratchet/PROGRAM_TEMPLATE.md"
BASE = "048acb0"                   # two docs-only commits after 13ddfa9 (17 checks pass at 13ddfa9, per the record)
C_CODE, C_DOCS, C_FIX = "7a74dce", "bc301ca", "ef58c85"   # code and tests; list only; a fix to the order path
RECORD_FINAL = 26                  # handoff W: 26 checks pass at 0772834, whose tests/ and tasty/paper equal ef58c85
RECORD_BASE = 17                   # decisions file, twentieth session: 17 pass at 13ddfa9


def sh(cwd, *args):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture(scope="module")
def root():
    r = data_root()
    if not PLATFORM.exists():
        pytest.skip("no local paper-trading-platform checkout")
    return r


@pytest.fixture()
def clone(tmp_path, root):
    dest = tmp_path / "platform"
    sh(tmp_path, "git", "clone", "-q", str(PLATFORM), str(dest))
    sh(dest, "git", "checkout", "-q", BASE)
    return dest


def control(clone, **over):
    d = {
        "loop": "tasty-checks",
        "repo": str(clone),
        "mutable": ["tasty/**", "tests/tasty_runner/**"],
        "protected": [],
        "metric": {"name": "checks_passed", "direction": "higher", "unit": "checks"},
        "figures": [{"name": "checks_passed", "unit": "checks",
                     "parse": {"kind": "regex", "pattern": r"(\d+) passed", "group": 1}}],
        "run": {"command": "python3 -m pytest tests/tasty_runner -q -p no:cacheprovider",
                "cwd": ".", "timeout_s": 120, "env": {}},
        "budget": {k: None for k in prog.BUDGET_KEYS},
        "crash": {"max_consecutive_crashes": 2},
        "keep": "strictly_better",
        "stop": {"after_trials": None, "after_trials_without_a_keep": None},
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    return d


def go(tmp_path, root, clone, commits, **over):
    text = "---\n" + yaml.safe_dump(control(clone, **over)) + "---\nnotes\n"
    p = tmp_path / "program.md"
    p.write_text(text)
    dag_dir = tmp_path / "experiments"
    rep = run_loop(p, ReplayCommits(clone, commits), scratch=tmp_path / "scratch", data_root=root,
                   exp_dir=dag_dir)
    return rep, ExpDag(root, exp_dir=dag_dir)


def full(clone, c):
    return sh(clone, "git", "rev-parse", c)


def files_of(clone, commit):
    return sorted(sh(clone, "git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit).split())


def trial(dag, tid):
    return dag.latest()[tid]


# ---- the keep-if-better loop on real commits ------------------------------------------------------
def test_the_base_follows_the_record_commit_by_docs_only_commits(clone):
    changed = sh(clone, "git", "diff", "--name-only", "13ddfa9", BASE).split()
    assert changed == ["tasty/RUNNING_LIST.md"]


def test_keep_and_revert_on_real_commits(tmp_path, root, clone):
    base_commit = sh(clone, "git", "rev-parse", "HEAD")
    rep, dag = go(tmp_path, root, clone, [C_CODE, C_DOCS, C_FIX])
    t0, t1, t2, t3 = rep["trials"]
    assert len(rep["trials"]) == 4
    assert rep["kept"] == [t0, t1, t3] and rep["reverted"] == [t2] and rep["crashed"] == []
    assert rep["best"] == t3 and rep["unresolved"] == []
    assert rep["stopped_because"] == "the proposer has nothing more to try"
    fig = lambda t: {m["name"]: m["value"] for m in trial(dag, t)["metrics"]}
    assert fig(t0)["checks_passed"] == RECORD_BASE          # the record's count, not the harness's
    assert fig(t1)["checks_passed"] > RECORD_BASE           # real code and tests were added
    assert fig(t2)["checks_passed"] == fig(t1)["checks_passed"]     # a docs-only commit: not better
    assert fig(t3)["checks_passed"] == RECORD_FINAL         # handoff W
    # every trial is in the record with its commit, figures, status, parent and loop
    assert len(dag.latest()) == 4
    commits = {t: trial(dag, t)["change"]["commit"] for t in rep["trials"]}
    assert commits[t0] == base_commit
    assert trial(dag, t0)["parent"] is None
    assert trial(dag, t1)["parent"] == t0
    assert trial(dag, t2)["parent"] == t1
    assert trial(dag, t3)["parent"] == t1                    # based on the last KEPT trial, not the reverted one
    assert [trial(dag, t)["status"] for t in rep["trials"]] == ["kept", "kept", "reverted", "kept"]
    assert all(trial(dag, t)["loop"] == "tasty-checks" for t in rep["trials"])
    assert all(trial(dag, t)["written_by"].startswith("code:tools.ratchet.loop@") for t in rep["trials"])
    assert re.search(r"figure checks_passed was 25, the best kept is 25 \(trial 1", trial(dag, t2)["note"])
    # each trial's commit holds what the real commit changed (git's own file list)
    for t, src in ((t1, C_CODE), (t2, C_DOCS), (t3, C_FIX)):
        assert files_of(clone, commits[t]) == files_of(clone, src)
    # the reverted trial's commit is still there by its ref, and the branch is on the last kept commit
    assert sh(clone, "git", "rev-parse", "refs/ratchet/tasty-checks/trial-2") == commits[t2]
    assert sh(clone, "git", "rev-parse", "ratchet/tasty-checks") == commits[t3]
    r = subprocess.run(["git", "merge-base", "--is-ancestor", commits[t2], "ratchet/tasty-checks"],
                       cwd=clone)
    assert r.returncode == 1                                 # the reverted change is not on the branch
    assert sh(clone, "git", "log", "-1", "--format=%an|%s", commits[t2]).startswith("ratchet loop|replay of " + C_DOCS)
    # the user's own working tree and branch were not touched
    assert sh(clone, "git", "rev-parse", "HEAD") == base_commit
    assert sh(clone, "git", "status", "--porcelain") == ""
    assert (tmp_path / "scratch/tasty-checks/logs/trial-2.log").exists()
    assert rep["budget_used"]["model_calls"] == "not reported"
    assert rep["budget_used"]["trials"] == 3 and rep["budget_used"]["graph_writes"] == 4


def test_a_protected_file_is_a_crash_undone_and_escalated(tmp_path, root, clone):
    protected = "tests/tasty_runner/test_runner_offline.py"
    assert protected in files_of(clone, C_CODE)              # a real commit changes it (git's list)
    rep, dag = go(tmp_path, root, clone, [C_CODE, C_FIX], protected=[protected],
                  escalate_file=str(tmp_path / "esc.json"))
    t0, t1 = rep["trials"]
    assert rep["crashed"] == [t1] and rep["kept"] == [t0]
    assert trial(dag, t1)["status"] == "crash" and trial(dag, t1)["note"] == f"touched {protected}"
    assert trial(dag, t1)["metrics"] == []                   # it was not run: no figure is claimed
    assert [e["condition"] for e in rep["escalations"]] == ["a protected file was touched"]
    assert rep["stopped_because"].startswith("escalated: a protected file was touched")
    assert rep["unresolved"] == [full(clone, C_FIX)]
    assert json.loads((tmp_path / "esc.json").read_text())["escalations"] == rep["escalations"]
    # undone: the branch is back on trial 0, and the offending commit is kept under its ref
    t0c = trial(dag, t0)["change"]["commit"]
    assert sh(clone, "git", "rev-parse", "ratchet/tasty-checks") == t0c
    assert sh(clone, "git", "rev-parse", "refs/ratchet/tasty-checks/trial-1") == trial(dag, t1)["change"]["commit"]
    assert protected in files_of(clone, trial(dag, t1)["change"]["commit"])


def test_a_file_outside_mutable_is_a_crash_too(tmp_path, root, clone):
    rep, dag = go(tmp_path, root, clone, [C_CODE], mutable=["tests/**"])
    t = trial(dag, rep["trials"][1])
    assert t["status"] == "crash" and t["note"].startswith("touched tasty/paper/")
    assert rep["escalations"] == []                          # only a protected file escalates


def test_no_figure_chosen_records_every_trial_and_reverts_nothing(tmp_path, root, clone):
    rep, dag = go(tmp_path, root, clone, [C_CODE, C_DOCS, C_FIX],
                  metric={"name": "checks_passed", "direction": None, "unit": "checks"})
    assert rep["recorded"] == rep["trials"] and len(rep["trials"]) == 4
    assert rep["kept"] == [] and rep["reverted"] == [] and rep["crashed"] == [] and rep["best"] is None
    ids = rep["trials"]
    assert [trial(dag, t)["status"] for t in ids] == ["recorded"] * 4
    assert [trial(dag, t)["parent"] for t in ids] == [None, ids[0], ids[1], ids[2]]
    # nothing was undone: the branch carries all three real commits
    tip = trial(dag, ids[3])["change"]["commit"]
    assert sh(clone, "git", "rev-parse", "ratchet/tasty-checks") == tip
    assert [m["value"] for m in trial(dag, ids[3])["metrics"]] == [RECORD_FINAL]


def test_budget_stop_names_the_unresolved_commits(tmp_path, root, clone):
    budget = {k: None for k in prog.BUDGET_KEYS}
    budget["max_trials"] = 2
    rep, dag = go(tmp_path, root, clone, [C_CODE, C_DOCS, C_FIX], budget=budget)
    assert len(rep["trials"]) == 3                           # the baseline and two proposed trials
    assert rep["unresolved"] == [full(clone, C_FIX)]
    assert rep["stopped_because"].startswith("budget exhausted: max_trials (2)")
    assert [e["condition"] for e in rep["escalations"]] == ["budget exhausted"]
    assert rep["budget_used"]["trials"] == 2


def test_after_trials_without_a_keep_is_a_plain_stop(tmp_path, root, clone):
    rep, dag = go(tmp_path, root, clone, [C_CODE, C_DOCS, C_FIX],
                  stop={"after_trials": None, "after_trials_without_a_keep": 1})
    assert rep["stopped_because"].startswith("stop.after_trials_without_a_keep")
    assert rep["unresolved"] == [full(clone, C_FIX)] and rep["escalations"] == []


def test_an_unreadable_figure_is_a_crash_with_its_reason(tmp_path, root, clone):
    figs = [{"name": "checks_passed", "parse": {"kind": "regex", "pattern": r"(\d+) never_printed"}}]
    rep, dag = go(tmp_path, root, clone, [C_CODE], figures=figs)
    t = trial(dag, rep["trials"][0])
    assert t["status"] == "crash" and "could not parse figure checks_passed" in t["note"]
    assert rep["stopped_because"].startswith("baseline run crashed")


def test_a_timeout_is_a_crash(tmp_path, root, clone):
    rep, dag = go(tmp_path, root, clone, [C_CODE],
                  run={"command": "python3 -c 'import time; time.sleep(30)'", "timeout_s": 1})
    assert "timeout after 1" in trial(dag, rep["trials"][0])["note"]


# ---- the control file ------------------------------------------------------------------------------
def template_text():
    return TEMPLATE.read_text()


def test_the_template_loads_with_every_field():
    p = prog.parse(template_text())
    assert p.loop == "tasty-checks-count" and p.metric_direction == "higher"
    assert p.budget["max_trials"] == 5 and p.keep == "strictly_better"
    assert p.figures[0].pattern == r"(\d+) passed"


@pytest.mark.parametrize("line,field", [
    (r"^  max_trials:.*\n", "budget.max_trials"),
    (r"^protected:.*\n(?:  .*\n)+", "protected"),
    (r"^crash:.*\n(?:  .*\n)+", "crash"),
])
def test_a_missing_field_is_refused_and_named(line, field):
    text = re.sub(line, "", template_text(), count=1, flags=re.M)
    assert text != template_text()
    with pytest.raises(prog.ProgramError) as e:
        prog.parse(text)
    assert field in str(e.value) and "missing" in str(e.value)


def test_an_unknown_field_is_refused_and_named():
    text = template_text().replace("  timeout_s: 120", "  timeout_s: 120\n  retries_forever: true", 1)
    with pytest.raises(prog.ProgramError) as e:
        prog.parse(text)
    assert "run.retries_forever" in str(e.value) and "unknown" in str(e.value)
    text = template_text().replace("keep: strictly_better", "keep: strictly_better\nrank: yes", 1)
    with pytest.raises(prog.ProgramError) as e:
        prog.parse(text)
    assert "rank: unknown field" in str(e.value)


# ---- the command line --------------------------------------------------------------------------------
def test_command_line(tmp_path, root, clone):
    (tmp_path / "program.md").write_text("---\n" + yaml.safe_dump(control(clone)) + "---\n")
    r = subprocess.run([sys.executable, "-m", "tools.ratchet.loop", "--program", str(tmp_path / "program.md"),
                        "--replay", C_CODE, "--scratch", str(tmp_path / "s"), "--data", str(root),
                        "--exp-dir", str(tmp_path / "exp")],
                       cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert len(rep["trials"]) == 2 and rep["kept"] == rep["trials"]
    assert len(ExpDag(root, exp_dir=tmp_path / "exp").latest()) == 2


# ---- the guard and the report (review of 2026-11-24: F10.1 to F10.4) ---------------------------------------
class WithExtra:
    """A proposer that applies a real commit (ReplayCommits) and then does one more thing to the worktree."""

    def __init__(self, inner, extra=None, raises_first=None):
        self.inner, self.extra, self.raises_first, self.calls = inner, extra, raises_first, 0

    def unresolved(self):
        return self.inner.unresolved()

    def __call__(self, wt, n, history):
        self.calls += 1
        if self.raises_first and self.calls == 1:
            raise self.raises_first
        got = self.inner(wt, n, history)
        if got and self.extra and self.calls == 1:
            self.extra(Path(wt))
        return got


def run_with(tmp_path, root, clone, proposer, **over):
    text = "---\n" + yaml.safe_dump(control(clone, **over)) + "---\nnotes\n"
    p = tmp_path / "program.md"
    p.write_text(text)
    rep = run_loop(p, proposer, scratch=tmp_path / "scratch", data_root=root, exp_dir=tmp_path / "experiments")
    return rep, ExpDag(root, exp_dir=tmp_path / "experiments"), tmp_path / "scratch/tasty-checks/worktree"


def test_a_new_ignored_file_is_a_change_outside_mutable_and_is_cleaned_between_trials(tmp_path, root, clone):
    """F10.1. The platform's .gitignore ignores .venv/: a file a proposer writes there is read by the run command
    like any other, so the trial is not run (crash, "touched <file>") and the file is gone for the next trial."""
    def write_ignored(wt):
        (wt / ".venv").mkdir(exist_ok=True)
        (wt / ".venv" / "settings.txt").write_text("a file git ignores\n")
    assert sh(clone, "git", "check-ignore", ".venv/settings.txt") == ".venv/settings.txt"
    rep, dag, wt = run_with(tmp_path, root, clone, WithExtra(ReplayCommits(clone, [C_CODE, C_DOCS]), write_ignored))
    t0, t1, t2 = rep["trials"]
    assert trial(dag, t1)["status"] == "crash" and ".venv/settings.txt" in trial(dag, t1)["note"]
    assert trial(dag, t1)["note"].startswith("touched ") and trial(dag, t1)["metrics"] == []     # not run
    assert not (wt / ".venv" / "settings.txt").exists()                  # cleaned, ignored files too
    assert trial(dag, t2)["status"] == "reverted" and trial(dag, t2)["metrics"]   # the next trial ran, clean
    assert sh(wt, "git", "status", "--porcelain", "--ignored") == ""


def test_a_proposer_that_raises_is_a_recorded_crash_and_the_loop_goes_on(tmp_path, root, clone):
    """F10.3. Any exception from a proposer ends that trial as a crash with its text; the worktree is back on
    the last kept commit; the loop's report is returned."""
    rep, dag, wt = run_with(tmp_path, root, clone,
                            WithExtra(ReplayCommits(clone, [C_CODE]), raises_first=RuntimeError("the model went away")))
    t0, t1, t2 = rep["trials"]
    assert trial(dag, t1)["status"] == "crash" and "RuntimeError: the model went away" in trial(dag, t1)["note"]
    assert trial(dag, t2)["status"] == "kept" and rep["stopped_because"] == "the proposer has nothing more to try"
    assert sh(wt, "git", "status", "--porcelain") == ""


def test_the_report_is_returned_and_written_when_the_loop_itself_fails(tmp_path, root, clone):
    """F10.3: a proposer that hands back something the loop cannot use (no hypothesis) is not a proposer
    failure: the loop stops, says so, the worktree is put back, and the report is written to escalate_file."""
    class Bad:
        def __call__(self, wt, n, history):
            return {"agent_run": None}
    rep, dag, wt = run_with(tmp_path, root, clone, Bad(), escalate_file=str(tmp_path / "esc.json"))
    assert rep["stopped_because"].startswith("the loop itself stopped: KeyError")
    assert [e["condition"] for e in rep["escalations"]] == ["the loop stopped on an exception"]
    assert json.loads((tmp_path / "esc.json").read_text())["stopped_because"] == rep["stopped_because"]
    assert rep["trials"] and sh(wt, "git", "status", "--porcelain") == ""


def test_a_crashed_trial_keeps_every_attempt_and_the_figures_that_were_parsed(tmp_path, root, clone):
    """F10.4. environment.attempts is a list: one entry an attempt (exit code, timed out, what was parsed)."""
    budget = {k: None for k in prog.BUDGET_KEYS}
    budget["max_retries"] = 2
    run = {"command": "python3 -c 'import sys; print(\"7 passed\"); sys.exit(3)'", "env": {"RATCHET_CHECK": "ratchet-secret-value"}}
    rep, dag, _ = run_with(tmp_path, root, clone, ReplayCommits(clone, [C_CODE]), budget=budget, run=run)
    t = trial(dag, rep["trials"][0])
    assert t["status"] == "crash"
    env = t["environment"] if isinstance(t["environment"], dict) else json.loads(t["environment"])
    assert [a["exit_code"] for a in env["attempts"]] == [3, 3, 3] and [a["timed_out"] for a in env["attempts"]] == [False] * 3
    assert all(a["parsed"] == {"checks_passed": 7} for a in env["attempts"])
    assert [m["value"] for m in t["metrics"]] == [7]                     # the figure that was parsed is kept
    assert all(f"attempt {i}" in t["note"] for i in (1, 2, 3))           # the note of EVERY attempt
    # F10.2: the command and the NAMES of the environment variables are in the record, never their values
    assert env["run_command"] == run["command"] and env["env_names"] == ["RATCHET_CHECK"]
    assert "ratchet-secret-value" not in json.dumps(env)


def test_the_limit_of_the_guard_is_written_in_the_loop_and_in_the_control_file_template():
    from tools.ratchet import loop
    for text in (loop.__doc__, template_text()):
        assert "does not cover what the run command" in " ".join(text.lower().split()) or \
               "not what the run command" in " ".join(text.lower().split())
    assert "only read and print" in " ".join(loop.__doc__.split()) and "only read and print" in template_text()
