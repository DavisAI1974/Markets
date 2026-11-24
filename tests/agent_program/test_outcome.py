"""Ticket 04 of the 44: who may see an outcome, and when.

Real things only. The claims are the real claim files of PAPER/claims-20261124/decider_v1 (registered by run:0002, a
real builder run); the reviewers are the real runs run:0003 and run:0005; the outcome-bearing record handed over is
the real journal (events.jsonl) of the feed-only live run 20261124T011440Z, tracked in markets-data. One revision check uses a COPY
of a real claim file with its scope sentence lengthened (a copy made here; the claim says nothing about the market).
The challenge files are this test's own text about the real claim. Every write goes to a scratch copy of the graph,
made once for the module; markets-data is only read. The checks run in file order: each builds on the graph the one
before left (a claim is challenged, then released, then revised).
"""

import json
import shutil
import subprocess

import pytest

from tools.kgraph import defend, outcome
from tools.kgraph.store import GraphStore

from .realrecords import PAPER, data_root

PROPOSER, REVIEWER, REVIEWER2 = "run:0002", "run:0003", "run:0005"
R0 = "0f33fec49f8c4905b6c212912077d439"
# a real record tracked in markets-data (the journal of a feed-only live run); the commit is the one that last changed it
JOURNAL = f"{PAPER}/live-runs/feed-only-20261124T011440Z/events.jsonl"
CLAIMS = f"{PAPER}/claims-20261124/decider_v1"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = data_root()
    p = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%H", "--", JOURNAL], capture_output=True, text=True)
    commit = p.stdout.strip()
    if not commit:
        pytest.skip(f"{JOURNAL} is not tracked in {root}")
    raw = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{JOURNAL}"], capture_output=True).stdout
    g = tmp_path_factory.mktemp("g") / "graph"
    shutil.copytree(root / "graph", g)
    w = {"root": root, "graph": g, "tmp": tmp_path_factory.mktemp("f"), "commit": commit, "raw": raw,
         "spec": f"markets-data:{JOURNAL}@{commit}", "n": 0}
    for run in (PROPOSER, REVIEWER, REVIEWER2):
        if not fresh(w).node(run):
            pytest.skip(f"{run} is not in this graph")
    return w


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


S = {}


def test_refused_before_any_challenge_and_the_refusal_is_kept(world):
    w = world
    cid = S["cid"] = reg(w, "condition-1")
    assert defend.challenges_of(fresh(w), cid) == []           # the real graph holds none for this claim
    ok, why = outcome.may_see_outcome(fresh(w), cid, REVIEWER)
    assert ok is False and cid in why and "revision 1" in why
    out = w["tmp"] / "out0"
    assert rel(w, cid, REVIEWER, out) == 2 and not out.exists()
    s = fresh(w)
    kept = [t for t in s.nodes("Task") if t["attrs"].get("verb") == "outcome" and t["attrs"].get("claim") == cid]
    assert len(kept) == 1 and kept[0]["attrs"]["run"] == REVIEWER and kept[0]["attrs"]["state"] == "blocked"
    assert outcome.releases_of(s, cid) == []                    # a refusal is not a release


def test_released_after_the_runs_own_challenge(world):
    w, cid = world, S["cid"]
    S["ev1"] = chal(w, cid, REVIEWER)
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
    assert a["claim"] == cid and a["claim_revision"] == 1 and a["run"] == REVIEWER and a["challenges"] == [S["ev1"]]
    assert a["released_at"]
    s = fresh(w)
    assert any(e["src"] == r["id"] and e["dst"] == cid for e in s.edges("MENTIONS"))
    assert any(e["src"] == REVIEWER and e["dst"] == r["id"] for e in s.edges("PRODUCED"))


def test_a_second_reviewer_needs_its_own_challenge_the_proposer_needs_any(world):
    w, cid = world, S["cid"]
    assert rel(w, cid, REVIEWER2, w["tmp"] / "out2") == 2 and not (w["tmp"] / "out2").exists()
    assert outcome.may_see_outcome(fresh(w), cid, REVIEWER2)[0] is False
    assert rel(w, cid, PROPOSER, w["tmp"] / "out3") == 0
    assert outcome.may_see_outcome(fresh(w), cid)[0] is True    # no run named: one challenge on record is enough
    assert [r["attrs"]["run"] for r in outcome.releases_of(fresh(w), cid)] == [REVIEWER, PROPOSER]


def test_a_new_revision_needs_a_new_challenge(world):
    w, cid = world, S["cid"]
    assert reg(w, "condition-1", lambda d: d.update(scope=d["scope"] + " (revision two of the file)")) == cid
    assert fresh(w).node(cid)["rev"] == 2
    for run in (REVIEWER, None):
        ok, why = outcome.may_see_outcome(fresh(w), cid, run)
        assert ok is False and "revision 2" in why
    assert rel(w, cid, REVIEWER, w["tmp"] / "out4") == 2 and not (w["tmp"] / "out4").exists()
    assert outcome.may_see_outcome(fresh(w), cid, PROPOSER)[0] is False
    S["ev2"] = chal(w, cid, REVIEWER)
    assert outcome.may_see_outcome(fresh(w), cid, REVIEWER)[0] is True
    assert outcome.may_see_outcome(fresh(w), cid, REVIEWER2)[0] is False


def test_releases_lists_everyone_but_shows_paths_only_to_a_run_that_passes(world, capsys):
    w, cid = world, S["cid"]
    base = ["releases", "--claim", cid, "--data", str(w["root"]), "--graph-dir", str(w["graph"])]
    for extra in (["--run", REVIEWER2], []):
        assert outcome.main(base + extra) == 0
        t = capsys.readouterr().out
        assert REVIEWER in t and PROPOSER in t and JOURNAL not in t and w["commit"] not in t
    assert outcome.main(base + ["--run", REVIEWER]) == 0
    t = capsys.readouterr().out
    assert JOURNAL in t and w["commit"] in t and REVIEWER in t


# ---- part B: what the brief says, who may `show`, and the flag on a challenge --------------------------------
def dmain(w, verb, cid, *extra):
    return defend.main([verb, "--claim", cid, "--data", str(w["root"]), "--graph-dir", str(w["graph"]), *extra])


def test_the_brief_says_only_that_an_outcome_was_or_was_not_seen(world):
    w = world
    seen = S["cid2"] = reg(w, "condition-2")        # a real claim file whose proposer states an outcome WAS seen
    what = json.loads((w["root"] / CLAIMS / "condition-2.json").read_text())["outcome_visibility"]["what"]
    s = fresh(w)
    b = defend.brief(s, seen)
    assert "proposer states that an outcome had been seen before registration" in b
    assert "the reviewer is not given what was seen" in b
    assert what[:60] not in b and "registered after an outcome was seen" not in b
    unseen = reg(w, "inference-1")
    if not json.loads((w["root"] / CLAIMS / "inference-1.json").read_text())["outcome_visibility"]["outcome_seen"]:
        assert "had not been seen" in defend.brief(s, unseen)
    assert JOURNAL not in defend.brief(s, S["cid"])         # no released record path is in the brief of the released claim
    assert what[:60] in defend.show(s, seen)                 # the proposer's side keeps the whole sentence


def test_show_refuses_a_reviewer_without_its_own_challenge(world, capsys):
    w, cid = world, S["cid2"]
    assert dmain(w, "show", cid, "--run", REVIEWER2) == 2
    capsys.readouterr()
    kept = [t for t in fresh(w).nodes("Task") if t["attrs"].get("verb") == "show" and t["attrs"].get("claim") == cid]
    assert len(kept) == 1 and kept[0]["attrs"]["run"] == REVIEWER2
    assert dmain(w, "show", cid, "--run", PROPOSER) == 0           # the proposer needs no challenge to read its own side
    assert "mechanism" in capsys.readouterr().out
    assert dmain(w, "show", cid) == 0
    assert "no run was named" in capsys.readouterr().out.splitlines()[0]
    chal(w, cid, REVIEWER)
    assert dmain(w, "show", cid, "--run", REVIEWER) == 0
    assert "mechanism" in capsys.readouterr().out
    assert dmain(w, "show", cid, "--run", REVIEWER2) == 2           # still no challenge of its own


def test_a_challenge_records_whether_an_outcome_was_on_record_before_it(world, capsys):
    w, cid = world, S["cid"]
    s = fresh(w)
    flag = lambda ev: s.node(ev)["attrs"]["outcome_on_record_before_challenge"]
    assert flag(S["ev1"]) is False          # run:0003 challenged revision 1 before any release to it
    assert flag(S["ev2"]) is True           # it challenged revision 2 after the release under revision 1
    ev3 = chal(w, cid, REVIEWER2)
    assert fresh(w).node(ev3)["attrs"]["outcome_on_record_before_challenge"] is False   # nothing was ever released to run:0005
    again = chal(w, cid, REVIEWER)          # the same challenge again is the same id: the flag of the first is kept
    assert again == S["ev2"] and fresh(w).node(again)["attrs"]["outcome_on_record_before_challenge"] is True
    assert dmain(w, "show", cid, "--run", REVIEWER) == 0
    out = capsys.readouterr().out
    assert out.count("outcome_on_record_before_challenge: ") == 3


# ---- part C: the code that hands records over today goes through the rule -------------------------------------
from tools.decider import afterwards as aw          # noqa: E402
from tools.kgraph.signal_packet import journal_from_file     # noqa: E402,F401
from .test_decider_loop import LOOP_FILE, PRINT_CMD, REPO, clone, load, proposer   # noqa: E402,F401  (clone is a fixture)

UNREGISTERED = "claim:70038adffed2"        # a real claim of the graph that was never registered with `defend register`


def _rows(w, cid):
    """History rows in loop.py's own shape. The figure is the real line count of the real program file; the hypotheses
    and the note are this test's own words."""
    lines = len((REPO / LOOP_FILE).read_text().splitlines())
    row = lambda n, rests: {"n": n, "id": f"trial:{n}", "commit": w["commit"], "status": "recorded", "figures": {"program_lines": lines},
                            "note": f"NOTE-{n}", "hypothesis": f"HYPOTHESIS-{n}", "parent": None, "runtime_s": 1.0, **rests}
    old = row(2, {})
    return [row(0, {"rests_on": [S["cid3"]]}), row(1, {"rests_on": [UNREGISTERED]}), old]


def test_the_file_proposer_holds_a_trial_that_rests_on_an_unchallenged_claim(world, tmp_path, clone):
    w = world
    S["cid3"] = reg(w, "inference-2")
    keep = tmp_path / "keep"
    for i in (0, 1, 2):                      # real copies of one real journal, one folder a trial, in order
        (keep / f"r{i}").mkdir(parents=True)
        (keep / f"r{i}" / "events.jsonl").write_bytes(w["raw"])
    program = load(tmp_path, clone, run={"command": PRINT_CMD + f" --keep {keep}", "cwd": ".", "timeout_s": 60, "env": {}})
    p = proposer(tmp_path / "mb", program, w["root"], w["graph"])
    hist = _rows(w, S["cid3"])
    text, _ = p.brief("def decide(packet):\n    return 1\n", hist, 3, clone)
    line = lambda t, n: next(l for l in t.splitlines() if l.startswith(f"- trial {n}:"))
    held = line(text, 0)
    assert held.startswith("- trial 0: held: ") and S["cid3"] in held and "revision 1" in held
    for k in ("HYPOTHESIS-0", "NOTE-0", "program_lines=", "status"):
        assert k not in held
    assert "HYPOTHESIS-1" in line(text, 1) and "program_lines=" in line(text, 1)
    assert "not a registered claim: no rule applies" in line(text, 1) and UNREGISTERED in line(text, 1)
    assert "HYPOTHESIS-2" in line(text, 2) and "no record of what it rested on" in line(text, 2)
    kept = p.kept_records(hist)
    assert len(kept) == 3 and "trial 0" in kept[0] and "held" in kept[0] and str(keep / "r0") not in kept[0]
    assert S["cid3"] in kept[0] and all(str(keep / f"r{i}") in kept[i] for i in (1, 2))
    chal(w, S["cid3"], REVIEWER)             # the challenge is on record: the trial prints as before
    p = proposer(tmp_path / "mb", program, w["root"], w["graph"])
    text, _ = p.brief("def decide(packet):\n    return 1\n", hist, 3, clone)
    assert "HYPOTHESIS-0" in line(text, 0) and "held" not in line(text, 0) and "program_lines=" in line(text, 0)
    assert all(str(keep / f"r{i}") in k for i, k in enumerate(p.kept_records(hist)))
    assert p.held({"n": 9, "rests_on": []}) == [] and p.held({"n": 9}) == []


def test_afterwards_brief_goes_through_the_rule(world, tmp_path, capsys):
    w = world
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
    assert aw.main(base + ["--out", str(out2), "--rests-on-none", why]) == 0
    assert why in out2.read_text().splitlines()[0]
    out3 = tmp_path / "b3.md"
    assert aw.main(base + ["--out", str(out3)]) == 2 and not out3.exists()
    assert aw.main(base + ["--out", str(out3), "--claim", cid, "--rests-on-none", why]) == 2 and not out3.exists()
