"""The loop on the decider program: replay_questions, trial_with_decider --dry, MailboxFileProposer, the control file.

Real records only: the journal of run 0f33fec4... from its record branch (git show into a scratch folder), the real
graph, the real starting program and contract file in a scratch repository. No engine, no tape, no model; no trial, session or loop
is run on the stored tape. The only command run through the loop prints a count of lines of a file.
markets-data is only read.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from tools.decider import replay_questions, trial_with_decider
from tools.exp_dag import ExpDag
from tools.kgraph import signal_packet as sp
from tools.kgraph.store import GraphStore, markets_data_root
from tools.ratchet import program as prog
from tools.ratchet.file_proposer import MailboxFileProposer, source_problem
from tools.ratchet.loop import ProposalFailed, guard, run_loop

from .realrecords import data_root

REPO = Path(__file__).resolve().parents[2]
R0 = "0f33fec49f8c4905b6c212912077d439"
PLATFORM = Path("/home/user/paper-trading-platform")
PROGRAMS = REPO / "tools" / "decider" / "programs"
LOOP_FILE = "tools/decider/programs/loop_decider.py"
CONTROL = REPO / "tools" / "ratchet" / "programs" / "platform_decider.md"
LIMIT = None                                       # all of the run's 217 opening signals, in order
CLAIM_PLAIN = "claim:70038adffed2"                # a real claim of the real graph
PRINT_CMD = ("python3 -c \"import json;print(json.dumps({'figures':{'program_lines':"
             f"len(open('{LOOP_FILE}').readlines())}}}}))\"")


@pytest.fixture(scope="module")
def root():
    return data_root()


@pytest.fixture(scope="module")
def journal(root, tmp_path_factory):
    r = subprocess.run(["git", "-C", str(root), "show", f"origin/paper-runs/{R0}:paper-trading/{R0}/events.jsonl"],
                       capture_output=True)
    if r.returncode:
        pytest.skip(f"no record branch for {R0} in {root}")
    p = tmp_path_factory.mktemp("journal") / "events.jsonl"
    p.write_bytes(r.stdout)
    return p


@pytest.fixture(scope="module")
def graph(root, tmp_path_factory):
    g = tmp_path_factory.mktemp("graph") / "graph"
    shutil.copytree(root / "graph", g)
    return g


def replay(root, journal, tmp_path, program, limit=LIMIT):
    out = tmp_path / "out"
    a = replay_questions.argparse.Namespace(data=str(root), run=None, journal=str(journal), platform=str(PLATFORM),
                                            budget=3000, program=str(program), mailbox_only=False, out=str(out),
                                            from_sequence=None, limit=limit, graph_dir=None, poll_s=0.05, timeout_s=5)
    return out, replay_questions.run(a)


# ---- piece 1: replay_questions ---------------------------------------------------------------------------
@pytest.mark.skipif(not PLATFORM.exists(), reason="no platform checkout")
@pytest.mark.parametrize("name,action", [("skip_all.py", "skip"), ("loop_decider.py", "take")])
def test_replay_over_real_signals_one_line_a_signal_and_the_counts_add_up(root, journal, tmp_path, name, action):
    out, c = replay(root, journal, tmp_path, PROGRAMS / name)
    lines = [json.loads(l) for l in (out / "decisions.jsonl").read_text().splitlines()]
    opens = sp.open_sequences(sp.journal_from_file(journal))
    assert len(opens) == 217
    assert [l["sequence"] for l in lines] == opens                  # one line a signal, in order
    assert c["signals_asked"] == c["answered"] == len(opens)
    assert c["take"] + c["skip"] == c["answered"]
    assert c["skip_answered_by_this_code"] == sum(l["answered_by"] == "this code" for l in lines)
    assert sum(c["skip_answered_by_this_code_reasons"].values()) == c["skip_answered_by_this_code"]
    assert c["packets_refused_by_the_leak_check"] == 0
    assert (c["take"] if action == "take" else c["skip"]) == len(opens)
    sizes = {l["sequence"]: l["packet_tokens_estimated_chars_div_4"] for l in lines}
    assert c["smallest_packet_tokens"] == min(sizes.values()) and sizes[c["smallest_packet_sequence"]] == c["smallest_packet_tokens"]
    assert c["largest_packet_tokens"] == max(sizes.values()) and sizes[c["largest_packet_sequence"]] == c["largest_packet_tokens"]
    assert c["packet_tokens_total_chars_div_4"] == sum(sizes.values())
    assert c["brief_tokens_total_chars_div_4"] > c["packet_tokens_total_chars_div_4"] > 0
    assert "NOT A TRIAL" in c["what_this_is_not"]
    print("\n", name, json.dumps(c, sort_keys=True))


@pytest.mark.skipif(not PLATFORM.exists(), reason="no platform checkout")
def test_replay_main_prints_the_counts_as_its_last_line(root, journal, tmp_path, capsys):
    rc = replay_questions.main(["--data", str(root), "--journal", str(journal), "--platform", str(PLATFORM),
                                "--budget", "3000", "--program", str(PROGRAMS / "skip_all.py"),
                                "--out", str(tmp_path / "o"), "--limit", "3"])
    last = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0 and last["signals_asked"] == 3 and "NOT A TRIAL" in last["what_this_is_not"]


# ---- piece 2: trial_with_decider --dry -------------------------------------------------------------------
def test_dry_prints_the_two_commands_and_starts_nothing(root, tmp_path, monkeypatch, capsys):
    if not PLATFORM.exists():
        pytest.skip("no platform checkout")
    plan = PLATFORM / "paper_platform" / "execution_plans" / "loop-trial.json"
    if not plan.exists():
        pytest.skip("no loop-trial.json")
    mailboxes = lambda: sorted(p.name for p in Path(tempfile.gettempdir()).glob("decider-mailbox-*"))
    before = mailboxes()

    real_popen, started = subprocess.Popen, []

    def only_the_shallow_read(argv, *a, **k):
        # the one process --dry may run is git's read of whether the platform checkout is shallow
        started.append(list(argv))
        assert argv[0] == "git" and argv[-1] == "--is-shallow-repository", f"--dry started {argv}"
        return real_popen(argv, *a, **k)
    monkeypatch.setattr(subprocess, "Popen", only_the_shallow_read)
    keep = tmp_path / "keep"
    rc = trial_with_decider.main(["--program", str(PROGRAMS / LOOP_FILE.split("/")[-1]), "--platform", str(PLATFORM),
                                  "--data", str(root), "--trade-day", "2023-10-02", "--plan", str(plan),
                                  "--from-minute", "30", "--minutes", "30", "--budget", "3000", "--keep", str(keep),
                                  "--dry"])
    out = capsys.readouterr().out.splitlines()
    doc = json.loads(out[-1])
    assert rc == 0 and doc["dry"] is True and doc["started"] == "nothing"
    assert any(l.startswith("door ") and "tools.decider.serve" in l and "--program" in l for l in out)
    assert any(l.startswith("trial ") and "paper_platform.trial" in l and "--decider-mailbox" in l for l in out)
    assert all(c["ok"] for c in doc["checks"]) and any("tape file of UTC clock day" in c["check"] for c in doc["checks"])
    assert len(started) == 1 and mailboxes() == before and not keep.exists()                       # no mailbox, no kept folder


def test_dry_reports_a_program_without_decide(root, tmp_path, capsys):
    bad = tmp_path / "p.py"
    bad.write_text("def other(packet):\n    return 1\n")
    rc = trial_with_decider.main(["--program", str(bad), "--platform", str(PLATFORM), "--data", str(root),
                                  "--trade-day", "2023-10-02", "--plan", str(tmp_path / "none.json"),
                                  "--from-minute", "30", "--minutes", "30", "--budget", "3000", "--dry"])
    doc = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert rc == 1 and [c["check"] for c in doc["checks"] if not c["ok"]][:2] == [
        "the program file compiles and defines decide", "the plan file exists"]


# ---- piece 3: MailboxFileProposer ------------------------------------------------------------------------
@pytest.fixture()
def clone(tmp_path):
    """A scratch repository holding the real starting program and the real contract file at their own paths, as
    committed here (a full clone of this checkout would copy gigabytes of working files for every check)."""
    dest = tmp_path / "markets"
    for rel in (LOOP_FILE, "tools/decider/programs/README.md"):
        out = subprocess.run(["git", "-C", str(REPO), "show", f"HEAD:{rel}"], capture_output=True)
        if out.returncode:
            pytest.skip(f"{rel} is not committed here")
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_bytes(out.stdout)
    git = lambda *a: subprocess.run(["git", "-C", str(dest), "-c", "user.name=check", "-c", "user.email=check@localhost",
                                     "-c", "commit.gpgsign=false", *a], check=True, capture_output=True)
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "the real files as committed")
    return dest


def control(clone, **over):
    d = {"loop": "decider-trials", "repo": str(clone), "mutable": [LOOP_FILE], "protected": ["tests/**"],
         "proposer": {"kind": "file"},
         "metric": {"name": "program_lines", "direction": None, "unit": "lines"},
         "figures": [{"name": "program_lines", "unit": "lines", "parse": {"kind": "json", "key": "figures.program_lines"}}],
         "run": {"command": PRINT_CMD, "cwd": ".", "timeout_s": 60, "env": {}},
         "budget": {k: None for k in prog.BUDGET_KEYS},
         "crash": {"max_consecutive_crashes": 3}, "keep": "strictly_better",
         "stop": {"after_trials": None, "after_trials_without_a_keep": None}}
    d.update(over)
    return d


def load(tmp_path, clone, **over):
    p = tmp_path / "program.md"
    p.write_text("---\n" + yaml.safe_dump(control(clone, **over)) + "---\nnotes\n")
    return prog.load(p)


VALID = '''def decide(packet):
    # INFERENCE: a check's own program, not a rule of the platform
    return {"action": "take", "why": "a change for the check", "rests_on": [packet["lines"][0]["source"]]}
'''


def answer(mb, n, source=VALID, hypothesis="a try", rests_on=(CLAIM_PLAIN,), inference=None, usage=True, stop=False):
    d = mb / f"trial-{n}"
    d.mkdir(parents=True, exist_ok=True)
    if stop:
        (d / "answer.json").write_text(json.dumps({"stop": True, "reason": "nothing more"}))
        return
    if source is not None:
        (d / "proposed.py").write_text(source)
    (d / "answer.json").write_text(json.dumps({"hypothesis": hypothesis, "rests_on": list(rests_on), "inference": inference}))
    if usage:
        (d / "usage.json").write_text(json.dumps({"agent_run": f"run:{900 + n:04d}", "model_calls": 1, "tokens": 10,
                                                  "tool_calls": None, "sub_agents": 0}))


def proposer(mb, program, root, graph, timeout_s=0.5):
    return MailboxFileProposer(mb, program, data_root=root, graph_dir=graph, context_budget=3000,
                               timeout_s=timeout_s, poll_s=0.05)


def test_the_brief_holds_the_present_file_the_contract_and_every_earlier_trial(tmp_path, root, graph, clone):
    mb = tmp_path / "mb"
    answer(mb, 1, hypothesis="first change")
    answer(mb, 2, stop=True)
    program = load(tmp_path, clone)
    assert program.proposer_kind == "file"
    rep = run_loop(program, proposer(mb, program, root, graph), scratch=tmp_path / "scratch", data_root=root,
                   exp_dir=tmp_path / "experiments")
    dag = ExpDag(root, exp_dir=tmp_path / "experiments")
    t0, t1 = rep["trials"]
    assert rep["recorded"] == [t0, t1] and rep["stopped_because"] == "the proposer has nothing more to try"
    present = PRESENT
    b1 = (mb / "trial-1" / "brief.md").read_text()
    assert present.rstrip("\n") in b1 and "decide(packet: dict)" in b1 and "Standard library only" in b1
    assert "marked INFERENCE" in b1 or "marked INFERENCE" in b1.replace("is marked", "marked")
    assert "(none yet)" not in b1 and "- trial 0:" in b1                        # trial 0 is already a line of its own
    b2 = (mb / "trial-2" / "brief.md").read_text()
    lines = [l for l in b2.splitlines() if l.startswith("- trial ")]
    assert len(lines) == 2 and lines[1].startswith("- trial 1:") and "hypothesis: first change" in lines[1]
    assert "program_lines=" in lines[1] and VALID.rstrip("\n") in b2             # the file as it now stands
    assert "counts of what each trial wrote, not results" in b2 and "Claim ids in the text above: claim:" in b2
    # the file was applied, applied.json holds the diff, and the proposal is in the trial's record
    ap = json.loads((mb / "trial-1" / "applied.json").read_text())
    assert ap["old_sha256"] != ap["new_sha256"] and "+++ b/" + LOOP_FILE in ap["diff"] and "-    return" in ap["diff"]
    assert ap["rests_on"] == [CLAIM_PLAIN] and ap["grounding"][0]["claim"] == CLAIM_PLAIN
    env = dag.latest()[t1]["environment"]
    assert env["proposal"] == ap and "proposal" not in dag.latest()[t0]["environment"]
    c = dag.latest()[t1]["change"]["commit"]
    assert subprocess.run(["git", "-C", str(clone), "show", f"{c}:{LOOP_FILE}"], capture_output=True, text=True).stdout == VALID


PRESENT = (REPO / LOOP_FILE).read_text() if (REPO / LOOP_FILE).exists() else ""


@pytest.mark.parametrize("source,reason", [
    ("def decide(packet:\n    return 1\n", "does not compile"),
    ("def other(packet):\n    return 1\n", "defines no `decide`"),
    (PRESENT, "byte-identical"),
    ("import os\n\ndef decide(packet):\n    return 1\n", "not allowed"),
    ("import numpy\n\ndef decide(packet):\n    return 1\n", "not allowed"),
    ("def decide(packet):\n    return open('x').read()\n", "'open'"),
    ("def decide(packet):\n    return eval('1')\n", "'eval'"),
    ("from pathlib import Path\n\ndef decide(packet):\n    return 1\n", "not allowed"),
])
def test_a_file_that_breaks_a_rule_is_refused_with_its_reason(tmp_path, root, graph, clone, source, reason):
    # the check itself (the brief, which reads the graph, is exercised by the checks around this one)
    mb = tmp_path / "mb"
    answer(mb, 1, source)
    program = load(tmp_path, clone)
    px = proposer(mb, program, root, graph)
    ans = json.loads((mb / "trial-1" / "answer.json").read_text())
    with pytest.raises(ProposalFailed, match=reason) as e:
        px._apply_file(PRESENT, clone / LOOP_FILE, mb / "trial-1" / "proposed.py", ans, "a try")
    assert e.value.hypothesis == "a try"
    assert (clone / LOOP_FILE).read_text() == PRESENT                      # nothing was changed
    assert not (mb / "trial-1" / "applied.json").exists()


@pytest.mark.parametrize("kw,reason", [
    (dict(rests_on=[], inference=None), "no source"),
    (dict(rests_on=["claim:000000000000"]), "is not a claim of the graph"),
])
def test_a_proposal_without_a_source_or_with_an_unknown_claim_is_refused(tmp_path, root, graph, clone, kw, reason):
    mb = tmp_path / "mb"
    answer(mb, 1, **kw)
    program = load(tmp_path, clone)
    ans = json.loads((mb / "trial-1" / "answer.json").read_text())
    with pytest.raises(ProposalFailed, match=reason):
        proposer(mb, program, root, graph)._apply_file(PRESENT, clone / LOOP_FILE, mb / "trial-1" / "proposed.py", ans, "a try")
    assert (clone / LOOP_FILE).read_text() == PRESENT


def test_source_problem_accepts_a_plain_program():
    assert source_problem(VALID, PRESENT) is None


def test_a_refused_file_is_a_recorded_crash_through_the_loop(tmp_path, root, graph, clone):
    mb = tmp_path / "mb"
    answer(mb, 1, "import os\n\ndef decide(packet):\n    return 1\n")
    answer(mb, 2, stop=True)
    program = load(tmp_path, clone)
    rep = run_loop(program, proposer(mb, program, root, graph), scratch=tmp_path / "scratch", data_root=root,
                   exp_dir=tmp_path / "experiments")
    t0, t1 = rep["trials"]
    assert rep["crashed"] == [t1] and rep["recorded"] == [t0]
    assert "not allowed" in ExpDag(root, exp_dir=tmp_path / "experiments").latest()[t1]["note"]


# ---- piece 4: the control file ---------------------------------------------------------------------------
def test_platform_decider_loads_and_the_guard_splits_mutable_from_protected():
    p = prog.load(CONTROL)
    assert p.loop == "platform-decider" and p.proposer_kind == "file" and p.metric_direction is None
    assert p.mutable == [LOOP_FILE] and len(p.figures) == 11
    assert guard(p, [LOOP_FILE]) == ([], [])                               # the one mutable file: nothing
    for f in ("tools/decider/serve.py", "tools/ratchet/loop.py", "tools/decider/programs/skip_all.py", "root/book.py",
              "tests/agent_program/test_decider_loop.py", "CLAUDE.md"):
        assert guard(p, [f]) == ([f], []), f
    assert guard(p, ["tools/decider/programs/new_file.py"]) == ([], ["tools/decider/programs/new_file.py"])


def test_an_existing_control_file_still_loads_with_the_default_proposer():
    p = prog.load(REPO / "tools" / "ratchet" / "programs" / "platform_exit.md")
    assert p.proposer_kind == "plan"
