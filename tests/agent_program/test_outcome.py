"""Ticket 04 of the 44: who may see an outcome, and when.

Real things only. The claims are the real claim files of PAPER/claims-20261124/decider_v1 (registered by run:0002, a
real builder run); the reviewers are the real runs run:0003 and run:0005; the outcome-bearing record handed over is
the real journal (events.jsonl) of the feed-only live run 20261124T011440Z, tracked in markets-data. The one case the
real record does not hold (a second revision of a claim) is in ONE separated section at the foot of this file, as a COPY
of a real claim file with exactly one thing changed, said in a `# change:` comment there.
The challenge files are this test's own text about the real claim. Every write goes to a scratch copy of the graph made
for each check (`w`); markets-data is only read. EVERY CHECK STANDS ALONE: none reads what another wrote; each builds the
state it needs (register, challenge, release) through the helpers below, on its own scratch copy, so the checks pass in
any order and one failing never turns the others into errors.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.kgraph import defend, outcome
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, data_root

PROPOSER, REVIEWER, REVIEWER2 = "run:0002", "run:0003", "run:0005"
R0 = "0f33fec49f8c4905b6c212912077d439"
# a real record tracked in markets-data (the journal of a feed-only live run); the commit is the one that last changed it
JOURNAL = f"{PAPER}/live-runs/feed-only-20261124T011440Z/events.jsonl"
CLAIMS = f"{PAPER}/claims-20261124/decider_v1"
PLATFORM = Path("/home/user/paper-trading-platform")
MARKETS = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def world():
    """The real record, read once: nothing is written through this."""
    root = data_root()
    p = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%H", "--", JOURNAL], capture_output=True, text=True)
    commit = p.stdout.strip()
    if not commit:
        pytest.skip(f"{JOURNAL} is not tracked in {root}")
    raw = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{JOURNAL}"], capture_output=True).stdout
    return {"root": root, "commit": commit, "raw": raw, "spec": f"markets-data:{JOURNAL}@{commit}"}


@pytest.fixture()
def w(world, tmp_path):
    """One scratch copy of the graph for ONE check (markets-data is only read)."""
    g = tmp_path / "graph"
    shutil.copytree(world["root"] / "graph", g)
    (tmp_path / "f").mkdir()
    out = dict(world, graph=g, tmp=tmp_path / "f", n=0)
    for run in (PROPOSER, REVIEWER, REVIEWER2):
        if not fresh(out).node(run):
            pytest.skip(f"{run} is not in this graph")
    return out


def fresh(w):
    return GraphStore(w["root"], graph_dir=w["graph"])


def reg(w, name, edit=None):
    src = w["root"] / CLAIMS / f"{name}.json"
    if edit:
        d = json.loads(src.read_text())
        edit(d)
        w["n"] += 1
        src = w["tmp"] / f"{name}-{w['n']}.json"
        src.write_text(json.dumps(d))
    return defend.register(fresh(w), src, PROPOSER)["claim"]


def chal(w, cid, run):
    s = fresh(w)
    w["n"] += 1
    b, f = w["tmp"] / f"b{w['n']}.md", w["tmp"] / f"c{w['n']}.json"
    b.write_text(defend.brief(s, cid), encoding="utf-8")
    f.write_text(json.dumps({
        "alternatives": ["the program reads differently than the condition says"],
        "falsifiers": [{"observation": "a line of the program that does the opposite", "record": "the program file"}],
        "distinguishing_observation": "the line of the program the condition is about",
        "what_was_checked": ["the artifact in the brief"], "what_was_observed": ["the lines named stand in the file"],
        "what_remains_open": ["how it behaves on the tape"], "objections": ["none beyond what remains open"],
        "saw_proposer_reasoning": False, "what_i_opened": ["the brief only"]}), encoding="utf-8")
    return defend.challenge(s, cid, f, run, b)["evaluation"]


def rel(w, cid, run, out, *extra):
    return outcome.main(["release", "--claim", cid, "--run", run, "--record", w["spec"], "--out", str(out),
                         "--data", str(w["root"]), "--graph-dir", str(w["graph"]), *extra])


def challenged(w, name="condition-1", run=REVIEWER):
    """A real claim registered, then challenged by `run`: (claim id, challenge id)."""
    cid = reg(w, name)
    return cid, chal(w, cid, run)


def dmain(w, verb, cid, *extra):
    return defend.main([verb, "--claim", cid, "--data", str(w["root"]), "--graph-dir", str(w["graph"]), *extra])


def test_refused_before_any_challenge_and_the_refusal_is_kept(w):
    cid = reg(w, "condition-1")
    assert defend.challenges_of(fresh(w), cid) == []           # the real graph holds none for this claim
    ok, why = outcome.may_see_outcome(fresh(w), cid, REVIEWER)
    assert ok is False and cid in why and "revision 1" in why
    out = w["tmp"] / "out0"
    assert rel(w, cid, REVIEWER, out) == 2 and not out.exists()
    s = fresh(w)
    kept = [t for t in s.nodes("Task") if t["attrs"].get("verb") == "outcome" and t["attrs"].get("claim") == cid]
    assert len(kept) == 1 and kept[0]["attrs"]["run"] == REVIEWER and kept[0]["attrs"]["state"] == "blocked"
    assert outcome.releases_of(s, cid) == []                    # a refusal is not a release


def test_released_after_the_runs_own_challenge(w):
    cid, ev1 = challenged(w)
    assert outcome.may_see_outcome(fresh(w), cid, REVIEWER)[0] is True
    out = w["tmp"] / "out1"
    assert rel(w, cid, REVIEWER, out) == 0
    assert (out / "markets-data" / JOURNAL).read_bytes() == w["raw"]
    (r,) = outcome.releases_of(fresh(w), cid)
    a = r["attrs"]
    assert r["type"] == "Task" and a["state"] == "done" and a["text"] == \
        f"outcome records handed to {REVIEWER} for {cid} revision 1"
    import hashlib
    assert a["records"] == [{"repo": "markets-data", "path": JOURNAL, "commit": w["commit"],
                             "sha256": hashlib.sha256(w["raw"]).hexdigest(), "bytes": len(w["raw"])}]
    assert a["claim"] == cid and a["claim_revision"] == 1 and a["run"] == REVIEWER and a["challenges"] == [ev1]
    assert a["released_at"]
    s = fresh(w)
    assert any(e["src"] == r["id"] and e["dst"] == cid for e in s.edges("MENTIONS"))
    assert any(e["src"] == REVIEWER and e["dst"] == r["id"] for e in s.edges("PRODUCED"))


def test_a_second_reviewer_needs_its_own_challenge_the_proposer_needs_any(w):
    cid, _ = challenged(w)
    assert rel(w, cid, REVIEWER, w["tmp"] / "out1") == 0
    assert rel(w, cid, REVIEWER2, w["tmp"] / "out2") == 2 and not (w["tmp"] / "out2").exists()
    assert outcome.may_see_outcome(fresh(w), cid, REVIEWER2)[0] is False
    assert rel(w, cid, PROPOSER, w["tmp"] / "out3") == 0
    assert outcome.may_see_outcome(fresh(w), cid)[0] is True    # no run named: one challenge on record is enough
    assert [r["attrs"]["run"] for r in outcome.releases_of(fresh(w), cid)] == [REVIEWER, PROPOSER]


def test_releases_lists_everyone_but_shows_paths_only_to_a_run_that_passes(w, capsys):
    cid, _ = challenged(w)
    assert rel(w, cid, REVIEWER, w["tmp"] / "out1") == 0 and rel(w, cid, PROPOSER, w["tmp"] / "out3") == 0
    capsys.readouterr()
    base = ["releases", "--claim", cid, "--data", str(w["root"]), "--graph-dir", str(w["graph"])]
    for extra in (["--run", REVIEWER2], []):
        assert outcome.main(base + extra) == 0
        t = capsys.readouterr().out
        assert REVIEWER in t and PROPOSER in t and JOURNAL not in t and w["commit"] not in t
    assert outcome.main(base + ["--run", REVIEWER]) == 0
    t = capsys.readouterr().out
    assert JOURNAL in t and w["commit"] in t and REVIEWER in t


# ---- ticket 04, the reviewer's point 4: `outcome release` --------------------------------------------------------
def test_out_inside_a_data_checkout_is_refused_naming_the_checkout(w, capsys):
    cid, _ = challenged(w)
    cases = [("markets-data", w["root"] / "handed-over-here"), ("Markets", MARKETS / "handed-over-here")]
    if PLATFORM.exists():
        cases.append(("paper-trading-platform", PLATFORM / "handed-over-here"))
    for name, out in cases:
        capsys.readouterr()
        assert rel(w, cid, REVIEWER, out) == 2
        err = capsys.readouterr().err
        assert "refused" in err and f"inside the {name} checkout" in err and str(out) in err
        assert not out.exists()
    assert outcome.releases_of(fresh(w), cid) == []             # nothing was handed over
    assert rel(w, cid, REVIEWER, w["tmp"] / "outside") == 0     # a folder outside every checkout is fine


def test_a_second_release_of_the_same_revision_to_the_same_run_writes_nothing(w, capsys):
    cid, _ = challenged(w)
    assert rel(w, cid, REVIEWER, w["tmp"] / "out1") == 0
    (first,) = outcome.releases_of(fresh(w), cid)
    tasks = sum(1 for _ in fresh(w).nodes("Task"))
    capsys.readouterr()
    again = w["tmp"] / "out-again"
    assert rel(w, cid, REVIEWER, again) == 0                    # said, not refused
    said = capsys.readouterr().out
    assert "already on record" in said and first["id"] in said
    assert not again.exists()                                   # nothing handed over a second time
    assert [r["id"] for r in outcome.releases_of(fresh(w), cid)] == [first["id"]]
    assert sum(1 for _ in fresh(w).nodes("Task")) == tasks      # no second release Task, no refusal Task


# ---- part B: what the brief says, who may `show`, and the flag on a challenge --------------------------------
def test_the_brief_says_only_that_an_outcome_was_or_was_not_seen(w):
    cid, _ = challenged(w)
    assert rel(w, cid, REVIEWER, w["tmp"] / "out1") == 0
    seen = reg(w, "condition-2")        # a real claim file whose proposer states an outcome WAS seen
    what = json.loads((w["root"] / CLAIMS / "condition-2.json").read_text())["outcome_visibility"]["what"]
    s = fresh(w)
    b = defend.brief(s, seen)
    assert "proposer states that an outcome had been seen before registration" in b
    assert "the reviewer is not given what was seen" in b
    assert what[:60] not in b and "registered after an outcome was seen" not in b
    unseen = reg(w, "inference-1")
    if not json.loads((w["root"] / CLAIMS / "inference-1.json").read_text())["outcome_visibility"]["outcome_seen"]:
        assert "had not been seen" in defend.brief(s, unseen)
    assert JOURNAL not in defend.brief(s, cid)         # no released record path is in the brief of the released claim
    assert what[:60] in defend.show(s, seen, PROPOSER)  # the proposer's side keeps the whole sentence


def test_show_refuses_a_reviewer_without_its_own_challenge(w, capsys):
    cid = reg(w, "condition-2")
    assert dmain(w, "show", cid, "--run", REVIEWER2) == 2
    capsys.readouterr()
    kept = [t for t in fresh(w).nodes("Task") if t["attrs"].get("verb") == "show" and t["attrs"].get("claim") == cid]
    assert len(kept) == 1 and kept[0]["attrs"]["run"] == REVIEWER2
    assert dmain(w, "show", cid, "--run", PROPOSER) == 0           # the proposer needs no challenge to read its own side
    assert "mechanism" in capsys.readouterr().out
    chal(w, cid, REVIEWER)
    assert dmain(w, "show", cid, "--run", REVIEWER) == 0
    assert "mechanism" in capsys.readouterr().out
    assert dmain(w, "show", cid, "--run", REVIEWER2) == 2           # still no challenge of its own


def test_show_needs_a_run_and_prints_nothing_of_the_claim_without_one(w, capsys):
    cid = reg(w, "condition-2")
    d = json.loads((w["root"] / CLAIMS / "condition-2.json").read_text())
    capsys.readouterr()
    assert dmain(w, "show", cid) == 2
    got = capsys.readouterr()
    assert got.out == ""                                   # nothing of the claim on the output
    assert d["outcome_visibility"]["what"][:60] not in got.err and d["mechanism"][:60] not in got.err
    assert "a run must be named" in got.err and "--run" in got.err
    kept = [t for t in fresh(w).nodes("Task") if t["attrs"].get("verb") == "show" and t["attrs"].get("claim") == cid]
    assert len(kept) == 1 and kept[0]["attrs"]["state"] == "blocked"      # the refusal is kept, as every refusal is


# ---- part C: the code that hands records over today goes through the rule -------------------------------------
from tools.decider import afterwards as aw          # noqa: E402
from tools.exp_dag import ExpDag                     # noqa: E402
from tools.kgraph.signal_packet import journal_from_file     # noqa: E402,F401
from tools.ratchet.loop import TRIAL_ID_FILE, run_loop     # noqa: E402
from .test_decider_loop import (CLAIM_PLAIN, LOOP_FILE, PRINT_CMD, REPO, VALID, answer, clone, load,   # noqa: E402,F401
                                proposer)                                             # (clone is a fixture)

UNREGISTERED = "claim:70038adffed2"        # a real claim of the graph that was never registered with `defend register`


def _rows(cid3):
    """History rows in loop.py's own shape. The figure is the real line count of the real program file; the hypotheses
    and the note are this test's own words."""
    lines = len((REPO / LOOP_FILE).read_text().splitlines())
    row = lambda n, rests: {"n": n, "id": f"trial:{n}", "commit": "x", "status": "recorded", "figures": {"program_lines": lines},
                            "note": f"NOTE-{n}", "hypothesis": f"HYPOTHESIS-{n}", "parent": None, "runtime_s": 1.0, **rests}
    old = row(2, {})
    return [row(0, {"rests_on": [cid3]}), row(1, {"rests_on": [UNREGISTERED]}), old]


def _keep_folders(w, keep, ids):
    """Real copies of one real journal, one folder each; `ids` maps a folder name to the trial id the loop wrote in it
    (None = a folder the loop did not tag)."""
    for name, tid in ids.items():
        (keep / name).mkdir(parents=True)
        (keep / name / "events.jsonl").write_bytes(w["raw"])
        if tid:
            (keep / name / TRIAL_ID_FILE).write_text(json.dumps({"id": tid}) + "\n")


def test_the_file_proposer_holds_a_trial_that_rests_on_an_unchallenged_claim(w, tmp_path, clone):
    cid3 = reg(w, "inference-2")
    keep = tmp_path / "keep"
    _keep_folders(w, keep, {"r0": "trial:0", "r1": "trial:1", "r2": "trial:2"})     # one folder a trial
    program = load(tmp_path, clone, run={"command": PRINT_CMD + f" --keep {keep}", "cwd": ".", "timeout_s": 60, "env": {}})
    p = proposer(tmp_path / "mb", program, w["root"], w["graph"])
    hist = _rows(cid3)
    text, _ = p.brief("def decide(packet):\n    return 1\n", hist, 3, clone)
    line = lambda t, n: next(l for l in t.splitlines() if l.startswith(f"- trial {n}:"))
    held = line(text, 0)
    assert held.startswith("- trial 0: held: ") and cid3 in held and "revision 1" in held
    for k in ("HYPOTHESIS-0", "NOTE-0", "program_lines=", "status"):
        assert k not in held
    assert "HYPOTHESIS-1" in line(text, 1) and "program_lines=" in line(text, 1)
    assert "not a registered claim: no rule applies" in line(text, 1) and UNREGISTERED in line(text, 1)
    assert "HYPOTHESIS-2" in line(text, 2) and "no record of what it rested on" in line(text, 2)
    kept = p.kept_records(hist)
    assert len(kept) == 3 and "trial 0" in kept[0] and "held" in kept[0] and str(keep / "r0") not in kept[0]
    assert cid3 in kept[0] and all(str(keep / f"r{i}") in kept[i] for i in (1, 2))
    chal(w, cid3, REVIEWER)             # the challenge is on record: the trial prints as before
    p = proposer(tmp_path / "mb", program, w["root"], w["graph"])
    text, _ = p.brief("def decide(packet):\n    return 1\n", hist, 3, clone)
    assert "HYPOTHESIS-0" in line(text, 0) and "held" not in line(text, 0) and "program_lines=" in line(text, 0)
    assert all(str(keep / f"r{i}") in k for i, k in enumerate(p.kept_records(hist)))
    assert p.held({"n": 9, "rests_on": []}) == [] and p.held({"n": 9}) == []


def test_a_held_trials_folder_is_tied_by_its_trial_id_not_by_order(w, tmp_path, clone):
    """The shape the reviewer described: trial 1 left NO folder (a refused proposal), trial 2 rests on an unchallenged
    claim and left the second folder. By order that folder would be taken for trial 1's and its path printed."""
    cid3 = reg(w, "inference-2")
    keep = tmp_path / "keep"
    _keep_folders(w, keep, {"r-a": "trial:0", "r-b": "trial:2", "r-c": None, "r-d": "trial:not-a-row"})
    program = load(tmp_path, clone, run={"command": PRINT_CMD + f" --keep {keep}", "cwd": ".", "timeout_s": 60, "env": {}})
    p = proposer(tmp_path / "mb", program, w["root"], w["graph"])
    rows = _rows(cid3)
    hist = [dict(rows[2], n=0, id="trial:0", rests_on=[]),
            dict(rows[1], n=1, id="trial:1", rests_on=[], status="crash"),    # the refused one: no folder at all
            dict(rows[0], n=2, id="trial:2", rests_on=[cid3])]                # the held one
    kept = p.kept_records(hist)
    assert len(kept) == 4
    assert str(keep / "r-a") in kept[0] and "trial 0" in kept[0]
    assert "trial 2" in kept[1] and "held" in kept[1] and cid3 in kept[1]
    assert "not matched to a trial" in kept[2] and "carries no trial id" in kept[2]
    assert "not matched to a trial" in kept[3] and "trial:not-a-row" in kept[3]
    text, _ = p.brief("def decide(packet):\n    return 1\n", hist, 3, clone)
    for held_or_unmatched in ("r-b", "r-c", "r-d"):         # no later brief holds the path of any of the three
        assert str(keep / held_or_unmatched) not in text and held_or_unmatched not in text
    assert str(keep / "r-a") in text


def _loop_with_keep(w, tmp_path, clone, answers, cid_for_trial_2=None):
    """The real loop, the real file proposer: trial 1 is refused (a program that names open), trial 2 is a change that
    runs and leaves a folder, trial 3 stops. Returns (report, dag, keep folder, mailbox, histories seen by the proposer)."""
    keep, mb = tmp_path / "keep", tmp_path / "mb"
    cmd = ("python3 -c \"import json,os,sys;os.makedirs(os.path.join(sys.argv[2],'r'+str(os.getpid())));"
           "print(json.dumps({'figures':{'program_lines':1}}))\" --keep " + str(keep))
    answer(mb, 1, source="def decide(packet):\n    return open('x')\n", hypothesis="a refused try", rests_on=(CLAIM_PLAIN,))
    answer(mb, 2, hypothesis="a try that runs", rests_on=(cid_for_trial_2 or CLAIM_PLAIN,))
    answer(mb, 3, stop=True)
    program = load(tmp_path, clone, run={"command": cmd, "cwd": ".", "timeout_s": 60, "env": {}})
    inner, seen = proposer(mb, program, w["root"], w["graph"]), []

    class Spy:
        def __call__(self, wt, n, history):
            seen.append([dict(h) for h in history])
            return inner(wt, n, history)

        def unresolved(self):
            return inner.unresolved() if hasattr(inner, "unresolved") else []
    rep = run_loop(program, Spy(), scratch=tmp_path / "scratch", data_root=w["root"], exp_dir=tmp_path / "experiments")
    return rep, ExpDag(w["root"], exp_dir=tmp_path / "experiments"), keep, mb, seen, inner


def test_the_loop_writes_the_trial_id_into_the_folder_so_a_held_trial_stays_held(w, tmp_path, clone):
    cid3 = reg(w, "inference-2")                    # registered, no independent challenge: a trial resting on it is held
    rep, dag, keep, mb, seen, p = _loop_with_keep(w, tmp_path, clone, None, cid_for_trial_2=cid3)
    t0, t1, t2 = rep["trials"]
    assert dag.latest()[t1]["status"] == "crash"                      # refused: no folder came of it
    folders = sorted(keep.iterdir())
    assert len(folders) == 2                                          # the baseline's and trial 2's, none for trial 1
    ids = {json.loads((f / TRIAL_ID_FILE).read_text())["id"] for f in folders}
    assert ids == {t0, t2}
    held_folder = next(f for f in folders if json.loads((f / TRIAL_ID_FILE).read_text())["id"] == t2)
    brief = (mb / "trial-3" / "brief.md").read_text()
    assert held_folder.name not in brief and "held" in brief and cid3 in brief
    base_folder = next(f for f in folders if f != held_folder)
    assert str(base_folder) in brief


def test_a_refused_proposal_keeps_its_rests_on_on_its_row(w, tmp_path, clone):
    rep, dag, keep, mb, seen, p = _loop_with_keep(w, tmp_path, clone, None)
    rows = {h["n"]: h for h in seen[-1]}
    assert rows[1]["status"] == "crash" and "names" in rows[1]["note"] or "open" in rows[1]["note"]
    assert rows[1]["rests_on"] == [CLAIM_PLAIN]           # the claim the refused hand-in said it rested on, not dropped
    assert rows[2]["rests_on"] == [CLAIM_PLAIN]           # a proposal that ran keeps its own as before


def test_afterwards_brief_goes_through_the_rule(w, tmp_path, capsys):
    cid = reg(w, "inference-3")
    journal = tmp_path / "events.jsonl"
    journal.write_bytes(w["raw"])             # the real feed-only journal; it may hold few or no decision lines
    after = tmp_path / "afterwards.jsonl"
    assert aw.main(["--journal", str(journal), "--out", str(after)]) == 0
    base = ["brief", "--afterwards", str(after), "--budget", "100000", "--data", str(w["root"]), "--graph-dir", str(w["graph"])]
    out = tmp_path / "b1.md"
    assert aw.main(base + ["--out", str(out), "--claim", cid]) == 2 and not out.exists()
    assert cid in capsys.readouterr().err
    chal(w, cid, REVIEWER)
    assert aw.main(base + ["--out", str(out), "--claim", cid]) == 0 and out.exists()
    assert cid in out.read_text().splitlines()[0]
    why = "the journal bears on no registered claim, it was made with no decider plugged in"
    out2 = tmp_path / "b2.md"
    assert aw.main(base + ["--out", str(out2), "--rests-on-none", why, "--run", PROPOSER]) == 0
    assert why in out2.read_text().splitlines()[0]
    out3 = tmp_path / "b3.md"
    assert aw.main(base + ["--out", str(out3)]) == 2 and not out3.exists()
    assert aw.main(base + ["--out", str(out3), "--claim", cid, "--rests-on-none", why, "--run", PROPOSER]) == 2 and not out3.exists()


def _afterwards(w, tmp_path):
    journal = tmp_path / "events.jsonl"
    journal.write_bytes(w["raw"])
    after = tmp_path / "afterwards.jsonl"
    assert aw.main(["--journal", str(journal), "--out", str(after)]) == 0
    return ["brief", "--afterwards", str(after), "--budget", "100000", "--data", str(w["root"]), "--graph-dir", str(w["graph"])]


def test_the_rests_on_none_reason_is_one_task_in_the_graph(w, tmp_path):
    base = _afterwards(w, tmp_path)
    why = "the journal bears on no registered claim, it was made with no decider plugged in"
    out = tmp_path / "b.md"
    before = {t["id"] for t in fresh(w).nodes("Task")}
    assert aw.main(base + ["--out", str(out), "--rests-on-none", why, "--run", PROPOSER]) == 0
    new = [t for t in fresh(w).nodes("Task") if t["id"] not in before]
    assert len(new) == 1                                           # ONE Task node, nothing else
    a = new[0]["attrs"]
    assert a["rests_on_none"] == why and a["run"] == PROPOSER and a["brief_path"] == str(out.resolve())
    assert a["state"] == "done" and a["afterwards_brief"] is True
    assert any(e["src"] == PROPOSER and e["dst"] == new[0]["id"] for e in fresh(w).edges("PRODUCED"))
    out.unlink()                                                   # the reason outlives the brief file
    assert why in {t["attrs"].get("rests_on_none") for t in fresh(w).nodes("Task")}


def test_rests_on_none_without_a_run_is_refused_and_the_refusal_is_kept(w, tmp_path, capsys):
    base = _afterwards(w, tmp_path)
    out = tmp_path / "b.md"
    capsys.readouterr()
    assert aw.main(base + ["--out", str(out), "--rests-on-none", "a reason given with no run"]) == 2
    assert "--run" in capsys.readouterr().err and not out.exists()
    kept = [t for t in fresh(w).nodes("Task") if t["attrs"].get("verb") == "afterwards-brief"]
    assert len(kept) == 1 and kept[0]["attrs"]["state"] == "blocked" and kept[0]["attrs"]["rests_on_none"] == "a reason given with no run"
    assert not [t for t in fresh(w).nodes("Task") if t["attrs"].get("afterwards_brief")]      # and no done Task


def test_neither_or_both_of_claim_and_rests_on_none_is_refused_and_kept(w, tmp_path):
    base = _afterwards(w, tmp_path)
    cid = reg(w, "inference-3")
    out = tmp_path / "b.md"
    assert aw.main(base + ["--out", str(out)]) == 2 and not out.exists()
    assert aw.main(base + ["--out", str(out), "--claim", cid, "--rests-on-none", "why", "--run", PROPOSER]) == 2 and not out.exists()
    kept = [t for t in fresh(w).nodes("Task") if t["attrs"].get("verb") == "afterwards-brief"]
    assert len(kept) == 2 and all(t["attrs"]["state"] == "blocked" for t in kept)
    assert sorted(len(t["attrs"]["claims"]) for t in kept) == [0, 1]


# ================================================================================================================
# CASES THE REAL RECORD DOES NOT HOLD (the one separated section). The graph holds no second revision of a claim.
# The record used is the real claim file of condition-1 with exactly one thing changed:
# change: its `scope` sentence is lengthened by " (revision two of the file)"; nothing else in the file is changed,
#         and it is registered by the same real run (run:0002) so the graph holds revision 2 of the real claim.
# The claim says nothing about the market; the change only makes a second revision exist.
# ================================================================================================================
def revise(w, cid):
    assert reg(w, "condition-1", lambda d: d.update(scope=d["scope"] + " (revision two of the file)")) == cid
    assert fresh(w).node(cid)["rev"] == 2


def test_a_new_revision_needs_a_new_challenge(w):
    cid, ev1 = challenged(w)
    assert rel(w, cid, REVIEWER, w["tmp"] / "out1") == 0
    revise(w, cid)
    for run in (REVIEWER, None):
        ok, why = outcome.may_see_outcome(fresh(w), cid, run)
        assert ok is False and "revision 2" in why
    assert rel(w, cid, REVIEWER, w["tmp"] / "out4") == 2 and not (w["tmp"] / "out4").exists()
    assert outcome.may_see_outcome(fresh(w), cid, PROPOSER)[0] is False
    chal(w, cid, REVIEWER)
    assert outcome.may_see_outcome(fresh(w), cid, REVIEWER)[0] is True
    assert outcome.may_see_outcome(fresh(w), cid, REVIEWER2)[0] is False


def test_a_challenge_records_whether_an_outcome_was_on_record_before_it(w, capsys):
    cid, ev1 = challenged(w)
    assert rel(w, cid, REVIEWER, w["tmp"] / "out1") == 0
    revise(w, cid)
    ev2 = chal(w, cid, REVIEWER)
    s = fresh(w)
    flag = lambda ev: s.node(ev)["attrs"]["outcome_on_record_before_challenge"]
    assert flag(ev1) is False          # run:0003 challenged revision 1 before any release to it
    assert flag(ev2) is True           # it challenged revision 2 after the release under revision 1
    ev3 = chal(w, cid, REVIEWER2)
    assert fresh(w).node(ev3)["attrs"]["outcome_on_record_before_challenge"] is False   # nothing was ever released to run:0005
    again = chal(w, cid, REVIEWER)          # the same challenge again is the same id: the flag of the first is kept
    assert again == ev2 and fresh(w).node(again)["attrs"]["outcome_on_record_before_challenge"] is True
    capsys.readouterr()
    assert dmain(w, "show", cid, "--run", REVIEWER) == 0
    out = capsys.readouterr().out
    assert out.count("outcome_on_record_before_challenge: ") == 3


def test_a_release_lists_the_challenges_of_the_released_revision_only(w):
    cid, ev1 = challenged(w)
    revise(w, cid)
    ev2 = chal(w, cid, REVIEWER)
    assert ev1 != ev2
    assert rel(w, cid, REVIEWER, w["tmp"] / "out2") == 0
    (r,) = outcome.releases_of(fresh(w), cid)
    assert r["attrs"]["claim_revision"] == 2
    assert r["attrs"]["challenges"] == [ev2] and ev1 not in r["attrs"]["challenges"]
