"""Stage 3, the proposer: checks on real records only (see test_stage3_ratchet.py). Nothing here runs the
engine: no paper run, no trial of the platform."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.kgraph import ingest_agent_runs as iar
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, data_root


@pytest.fixture(scope="module")
def root():
    return data_root()


def scratch_store(root, tmp_path):
    g = tmp_path / "graph"
    if (root / "graph").exists():
        shutil.copytree(root / "graph", g)
    return GraphStore(root, graph_dir=g), g


def test_run_47_two_lines_load_as_two_revisions(root, tmp_path):
    lines = [json.loads(l) for l in (root / iar.RUNS_FILE).read_text().splitlines() if l.strip()]
    twice = [l for l in lines if l["run"] == 47]
    if len(twice) < 2 or not any("corrects" in l for l in twice):
        pytest.skip("this checkout has no corrected run 47")
    store, g = scratch_store(root, tmp_path)
    iar.agent_runs(store)
    hist = GraphStore(root, graph_dir=g).history("run:0047")
    assert [h["rev"] for h in hist] == [1, 2]
    assert "corrects" not in hist[0]["attrs"] and "corrects" in hist[1]["attrs"]
    assert hist[1]["attrs"]["line_start"] > hist[0]["attrs"]["line_start"]


def test_same_run_number_without_corrects_or_across_sessions_is_still_refused(root, tmp_path):
    src = tmp_path / "data"
    f = src / iar.RUNS_FILE
    f.parent.mkdir(parents=True)
    shutil.copy(root / "MANIFEST.json", src / "MANIFEST.json")   # makes it a checkout the store accepts
    real = [json.loads(l) for l in (root / iar.RUNS_FILE).read_text().splitlines() if l.strip()]
    base = next(l for l in real if l["run"] == 46)       # a real line, only edited to be repeated
    def write(second):
        f.write_text(json.dumps(base) + "\n" + json.dumps(second) + "\n")
        for a in (["init", "-q"], ["add", "-A"],
                  ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"]):
            subprocess.run(["git", "-C", str(src), *a], check=True, capture_output=True)
    store = GraphStore(src, graph_dir=tmp_path / "g1")
    write(dict(base))                                           # no corrects
    with pytest.raises(ValueError, match="both say run 46"):
        iar.agent_runs(store)
    store = GraphStore(src, graph_dir=tmp_path / "g2")
    write(dict(base, corrects="x", session="another"))          # corrects, other session
    with pytest.raises(ValueError, match="both say run 46"):
        iar.agent_runs(store)


# ---- the proposer and the ready check, on the real plan of the platform -------------------------------
import yaml

from tools.exp_dag import ExpDag
from tools.kgraph import grounding
from tools.ratchet import program as prog
from tools.ratchet import ready as ready_mod
from tools.ratchet.loop import ProposalFailed, ReplayCommits, main as loop_main, run_loop
from tools.ratchet.proposer import MailboxProposer, dump_plan

PLATFORM = Path("/home/user/paper-trading-platform")
PLAN = "paper_platform/execution_plans/loop-trial.json"
# Real claims of the real graph. The first has no mark on it; the second a check marks "revise" today.
CLAIM_PLAIN, CLAIM_REVISE = "claim:70038adffed2", "claim:e760a503259a"
# prints one count read from the plan file itself; starts no engine and touches no tape
COUNT_CMD = ("python3 -c \"import json;d=json.load(open('" + PLAN + "'));"
             "print(json.dumps({'figures':{'rules_in_plan':len(d['rules'])}}))\"")


@pytest.fixture(scope="module")
def graph(root, tmp_path_factory):
    g = tmp_path_factory.mktemp("graph") / "graph"
    shutil.copytree(root / "graph", g)
    return g


@pytest.fixture()
def clone(tmp_path):
    if not PLATFORM.exists() or subprocess.run(["git", "-C", str(PLATFORM), "cat-file", "-e", f"HEAD:{PLAN}"]).returncode:
        pytest.skip("no paper-trading-platform checkout holding loop-trial.json")
    dest = tmp_path / "platform"
    subprocess.run(["git", "clone", "-q", str(PLATFORM), str(dest)], check=True)
    return dest


def sh(cwd, *args):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def control(clone, **over):
    d = {
        "loop": "plan-trials", "repo": str(clone), "mutable": [PLAN], "protected": [],
        "metric": {"name": "rules_in_plan", "direction": None, "unit": "rules"},
        "figures": [{"name": "rules_in_plan", "unit": "rules", "parse": {"kind": "json", "key": "figures.rules_in_plan"}}],
        "run": {"command": COUNT_CMD, "cwd": ".", "timeout_s": 60, "env": {}},
        "budget": {k: None for k in prog.BUDGET_KEYS},
        "crash": {"max_consecutive_crashes": 3}, "keep": "strictly_better",
        "stop": {"after_trials": None, "after_trials_without_a_keep": None},
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    return d


def write_program(tmp_path, clone, **over):
    p = tmp_path / "program.md"
    p.write_text("---\n" + yaml.safe_dump(control(clone, **over)) + "---\nnotes\n")
    return p


def answer(mailbox, n, change=None, rests_on=(CLAIM_PLAIN,), inference=None, usage=None, stop=False, hypothesis="h"):
    d = mailbox / f"trial-{n}"
    d.mkdir(parents=True, exist_ok=True)
    if stop:
        (d / "answer.json").write_text(json.dumps({"stop": True, "reason": "nothing more"}))
        return
    (d / "answer.json").write_text(json.dumps(
        {"hypothesis": hypothesis, "change": change, "rests_on": list(rests_on), "inference": inference}))
    if usage is not False:
        (d / "usage.json").write_text(json.dumps(
            usage or {"agent_run": f"run:{900 + n:04d}", "model_calls": 1, "tokens": 10, "tool_calls": None,
                      "sub_agents": 0}))


GIVE_BACK = {"path": ["exit", "give_back_fraction"], "value": "0.25"}


def mailbox_loop(tmp_path, clone, root, graph, mailbox, *, timeout_s=0.5, **over):
    program = prog.load(write_program(tmp_path, clone, **over))
    px = MailboxProposer(mailbox, program, data_root=root, graph_dir=graph, context_budget=3000,
                         timeout_s=timeout_s, poll_s=0.05)
    rep = run_loop(program, px, scratch=tmp_path / "scratch", data_root=root, exp_dir=tmp_path / "experiments")
    return rep, ExpDag(root, exp_dir=tmp_path / "experiments")


def test_the_plan_file_round_trips_byte_for_byte():
    raw = subprocess.run(["git", "-C", str(PLATFORM), "show", f"HEAD:{PLAN}"], capture_output=True).stdout
    if not raw:
        pytest.skip("no loop-trial.json in the platform checkout")
    assert dump_plan(json.loads(raw)).encode() == raw


def test_one_value_is_applied_and_every_earlier_trial_is_in_the_next_brief(tmp_path, root, graph, clone):
    mb = tmp_path / "mb"
    answer(mb, 1, GIVE_BACK, rests_on=[CLAIM_PLAIN, CLAIM_REVISE], hypothesis="first change")
    answer(mb, 2, {"path": ["rules", "CL01", "contracts"], "value": 2}, rests_on=[], inference="no claim names it",
           hypothesis="second change")
    answer(mb, 3, stop=True)
    rep, dag = mailbox_loop(tmp_path, clone, root, graph, mb)
    t0, t1, t2 = rep["trials"]
    assert rep["recorded"] == rep["trials"] and rep["stopped_because"] == "the proposer has nothing more to try"
    for t, (a, b) in ((t1, ("0.2", "0.25")), (t2, (1, 2))):
        c = dag.latest()[t]["change"]["commit"]
        stat = sh(clone, "git", "diff", "--numstat", c + "~1", c).split()
        assert stat[:2] == ["1", "1"] and stat[2] == PLAN          # one line out, one line in: one value
    # the proposal, with each claim's grounding decision, is in the trial's record
    prop = dag.latest()[t1]["environment"]["proposal"]
    assert prop["path"] == ["exit", "give_back_fraction"] and prop["old"] == "0.2" and prop["new"] == "0.25"
    assert [g["claim"] for g in prop["grounding"]] == [CLAIM_PLAIN, CLAIM_REVISE]
    assert prop["grounding"][1]["decision"] == "revise" and prop["grounding"][1]["reason"]   # reported, not a refusal
    assert json.loads((mb / "trial-1" / "applied.json").read_text()) == prop
    assert dag.latest()[t2]["environment"]["proposal"]["inference"] == "no claim names it"
    assert "proposal" not in dag.latest()[t0]["environment"]
    # the brief of trial 2 holds trial 0 and trial 1 as lines of their own, and claim ids
    brief = (mb / "trial-2" / "brief.md").read_text()
    lines = [l for l in brief.splitlines() if l.startswith("- trial ")]
    assert len(lines) == 2 and lines[0].startswith("- trial 0:") and lines[1].startswith("- trial 1:")
    assert "hypothesis: first change" in lines[1] and "rules_in_plan=32" in lines[1] and "status recorded" in lines[1]
    assert "Claim ids in the text above: claim:" in brief
    assert "No figure is chosen for keeping or reverting" in brief and "not scored" in brief
    assert "counts of what each trial wrote, not results" in brief
    assert '"give_back_fraction":"0.25"' in brief                    # the plan as it stands after trial 1
    for word in ("average", "mean ", "ranking of", "best "):
        assert word not in brief.split("## Session context")[0].lower().replace("averaged", "").replace("ranked", "")


@pytest.mark.parametrize("change,rests_on,inference,reason", [
    ({"path": ["rules", "CL01", "open"], "value": {"style": "post", "offset_ticks": 1}}, [CLAIM_PLAIN], None, "one value"),
    ({"path": ["rules", "CL01", "open"], "value": "post"}, [CLAIM_PLAIN], None, "group of values"),
    ({"path": ["instrument", "lot_size"], "value": "2"}, [CLAIM_PLAIN], None, "outside `exit`"),
    ({"path": ["rules", "ZZ99", "contracts"], "value": 2}, [CLAIM_PLAIN], None, "not in the plan"),
    ({"path": ["exit", "give_back_fraction"], "value": "0.2"}, [CLAIM_PLAIN], None, "no change"),
    ({"path": ["exit", "give_back_fraction"], "value": 0.25}, [CLAIM_PLAIN], None, "where the present value"),
    (GIVE_BACK, ["claim:000000000000"], None, "is not a claim of the graph"),
    (GIVE_BACK, [], None, "no source"),
    (GIVE_BACK, [], "  ", "no source"),
])
def test_a_proposal_that_breaks_a_rule_is_refused_with_its_reason(tmp_path, root, graph, clone, change, rests_on, inference, reason):
    mb = tmp_path / "mb"
    answer(mb, 1, change, rests_on=rests_on, inference=inference, hypothesis="a try")
    program = prog.load(write_program(tmp_path, clone))
    px = MailboxProposer(mb, program, data_root=root, graph_dir=graph, timeout_s=0.5, poll_s=0.05)
    with pytest.raises(ProposalFailed, match=reason) as e:
        px(clone, 1, [])
    assert e.value.hypothesis == "a try"
    assert sh(clone, "git", "status", "--porcelain") == ""             # nothing was changed
    assert not (mb / "trial-1" / "applied.json").exists()


def test_a_missing_usage_file_is_a_recorded_crash_and_the_loop_goes_on(tmp_path, root, graph, clone):
    mb = tmp_path / "mb"
    answer(mb, 1, GIVE_BACK, usage=False)
    answer(mb, 2, {"path": ["rules", "CL01", "contracts"], "value": 2})
    answer(mb, 3, stop=True)
    rep, dag = mailbox_loop(tmp_path, clone, root, graph, mb, timeout_s=0.3)
    t0, t1, t2 = rep["trials"]
    assert rep["crashed"] == [t1] and rep["recorded"] == [t0, t2]
    assert "usage.json is missing" in dag.latest()[t1]["note"]
    assert rep["stopped_because"] == "the proposer has nothing more to try"
    assert sh(clone, "git", "show", f"refs/ratchet/plan-trials/trial-2:{PLAN}").count('"contracts": 2') == 1


def test_usage_reaches_the_report_and_stops_the_loop_at_max_tokens(tmp_path, root, graph, clone):
    mb = tmp_path / "mb"
    answer(mb, 1, GIVE_BACK, usage={"agent_run": "run:0901", "model_calls": 2, "tokens": 60, "tool_calls": None, "sub_agents": 1})
    answer(mb, 2, {"path": ["rules", "CL01", "contracts"], "value": 2})
    budget = {k: None for k in prog.BUDGET_KEYS}
    budget["max_tokens"] = 50
    rep, dag = mailbox_loop(tmp_path, clone, root, graph, mb, budget=budget)
    assert len(rep["trials"]) == 2 and not (mb / "trial-2").exists()
    assert rep["stopped_because"] == "budget exhausted: max_tokens (50) used, as the proposer reported"
    u = rep["budget_used"]
    assert (u["tokens"], u["model_calls"], u["sub_agents"], u["tool_calls"]) == (60, 2, 1, "not reported")
    assert dag.latest()[rep["trials"][1]]["agent_run"] == "run:0901"


def test_replay_still_works_and_states_no_proposal(tmp_path, root, clone):
    base, docs_only = "048acb0", "bc301ca"
    if subprocess.run(["git", "-C", str(clone), "cat-file", "-e", docs_only]).returncode:
        pytest.skip("the real commits of the replay check are not in this checkout")
    sh(clone, "git", "checkout", "-q", base)
    p = write_program(tmp_path, clone, mutable=["tasty/**"],
                      run={"command": "python3 -c \"import json;print(json.dumps({'figures':{'rules_in_plan':1}}))\""})
    rep = run_loop(p, ReplayCommits(clone, [docs_only]), scratch=tmp_path / "scratch", data_root=root,
                   exp_dir=tmp_path / "experiments")
    dag = ExpDag(root, exp_dir=tmp_path / "experiments")
    assert len(rep["trials"]) == 2 and rep["recorded"] == rep["trials"]
    assert all("proposal" not in dag.latest()[t]["environment"] for t in rep["trials"])


def test_exactly_one_of_replay_and_mailbox_is_required(tmp_path, clone):
    p = str(write_program(tmp_path, clone))
    for extra in ([], ["--replay", "x", "--mailbox", str(tmp_path / "m")]):
        with pytest.raises(SystemExit) as e:
            loop_main(["--program", p, "--scratch", str(tmp_path / "s"), *extra])
        assert e.value.code == 2


# ---- the ready check ----------------------------------------------------------------------------------
def test_ready_check_on_a_good_control_file_and_it_never_runs_the_command(tmp_path, clone):
    left = tmp_path / "left-behind"
    cmd = f"touch {left} && " + COUNT_CMD
    out = ready_mod.check(write_program(tmp_path, clone, run={"command": cmd}))
    assert out["ready"] is True and out["not_ready"] == []
    assert not left.exists()                                           # the command was not run
    assert out["head"] == sh(clone, "git", "rev-parse", "HEAD")
    names = [e["name"] for e in out["entries"]]
    assert {"budget", "metric", "engine runs the budget allows", "guard reports a protected path"} <= set(names)
    assert out["hand_off"] == "this command starts nothing; starting the loop needs Greg's go"
    assert next(e for e in out["entries"] if e["name"] == "budget")["found"]["max_tokens"] == "not declared"
    assert "none is kept or reverted" in next(e for e in out["entries"] if e["name"] == "metric")["found"]["meaning"]


def test_ready_check_reports_a_shallow_repository(tmp_path, clone):
    shallow = tmp_path / "shallow"
    sh(tmp_path, "git", "clone", "-q", "--depth", "1", f"file://{clone}", str(shallow))
    out = ready_mod.check(write_program(tmp_path, shallow))
    assert out["ready"] is False and "repository is complete (not shallow)" in out["not_ready"]


def test_ready_check_reports_a_missing_mutable_file_and_an_unset_variable(tmp_path, clone, monkeypatch):
    monkeypatch.delenv("NO_SUCH_VARIABLE_FOR_THE_CHECK", raising=False)
    out = ready_mod.check(write_program(tmp_path, clone, mutable=["paper_platform/execution_plans/not-there.json"],
                                        run={"command": COUNT_CMD + " --data $NO_SUCH_VARIABLE_FOR_THE_CHECK"}))
    assert out["ready"] is False
    assert "mutable file paper_platform/execution_plans/not-there.json" in out["not_ready"]
    assert "variable NO_SUCH_VARIABLE_FOR_THE_CHECK" in out["not_ready"]


def test_ready_check_reads_the_manifest_of_the_stored_tape_by_name_and_size(tmp_path, root, clone):
    cmd = COUNT_CMD + " --trade-day 2023-10-03"
    out = ready_mod.check(write_program(tmp_path, clone, run={"command": cmd}), data=root)
    tape = {e["name"]: e for e in out["entries"] if e["name"].startswith("tape file")}
    assert sorted(tape) == [f"tape file of UTC clock day 2023-10-0{d}" for d in (1, 2, 3)]
    assert all(e["ready"] and e["found"]["on_disk_bytes"] == e["found"]["manifest_bytes"] for e in tape.values())
    cmd = COUNT_CMD + " --trade-day 2023-10-04"                          # no file of 2023-10-04 is stored
    out = ready_mod.check(write_program(tmp_path, clone, run={"command": cmd}), data=root)
    assert "tape file of UTC clock day 2023-10-04" in out["not_ready"]
