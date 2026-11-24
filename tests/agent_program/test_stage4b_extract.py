"""Stage 4b, the model part: what a reader returned becomes claims only where its quote stands in the
file. Checked on the real read of handoff X kept in markets-data graph/reads/ and on the real file."""

import json
import re
import subprocess

import pytest

from tools.kgraph import extract, ingest_agent_runs, schema
from tools.kgraph.store import GraphStore

from .realrecords import WORK, data_root

READ = "graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json"
HANDOFF = f"{WORK}/NEXT_SESSION_HANDOFF_20261124X.md"
RUN = "run:0018"
READ_W = "graph/reads/run-0021-NEXT_SESSION_HANDOFF_20261124W.json"


@pytest.fixture()
def loaded(tmp_path):
    root = data_root()
    if not (root / READ).exists():
        pytest.skip(f"{READ} is not in this markets-data checkout")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)                       # the reader's own run must be in the graph
    dirs = extract.repo_dirs(root, None, None)
    result = json.loads((root / READ).read_text(encoding="utf-8"))
    return store, dirs, result


def _words(s):
    return re.findall(r"\w+", s)


def _stands(claim, lines):
    """Counted here by a route of the check's own: a quote of 6 words or more, and its words, as whole
    words in a row, inside its lines (the words joined by single spaces and searched with the spaces round
    them, so it can never start or end inside a word)."""
    span = " " + " ".join(_words(" ".join(lines[claim["line_start"] - 1:claim["line_end"]]))) + " "
    return len(claim["quote"].split()) >= 6 and " " + " ".join(_words(claim["quote"])) + " " in span


def test_every_returned_claim_is_written_or_kept_as_thrown_out(loaded):
    store, dirs, result = loaded
    lines = (store.data_root / HANDOFF).read_text(encoding="utf-8").splitlines()
    returned = [c for p in result["pieces"] for c in p["claims"]]
    standing = [c for c in returned if _stands(c, lines)]
    report = extract.load_result(store, dirs, result, RUN)
    claims = store.nodes("Claim")
    assert report["claims_written"] == len(claims) == len(standing)
    assert report["thrown_out"] == len(returned) - len(standing)
    assert len([t for t in store.nodes("Task") if t["attrs"]["state"] == "blocked"]) == report["thrown_out"]
    # each claim is tied to the handoff by a SUPPORTS link and to the run that read it
    sid = "src:markets-data:" + HANDOFF
    assert {e["dst"] for e in store.edges("SUPPORTS")} == {c["id"] for c in claims}
    assert all(e["src"] == sid for e in store.edges("SUPPORTS"))
    assert {e["dst"] for e in store.edges("PRODUCED") if e["src"] == RUN} >= {c["id"] for c in claims}
    for c in claims:
        a = c["attrs"]
        assert _stands(a, lines) and a["source"] == sid and a["extracted_by"] == RUN and len(a["source_commit"]) == 40
    # Greg's own words are kept as his
    greg = [c["attrs"] for c in claims if "finish building everything for the agents" in c["attrs"]["quote"]]
    assert len(greg) == 1 and greg[0]["said_by"] == "Greg" and greg[0]["statement_kind"] == "decision"
    assert store.check_all() == []
    again = extract.load_result(store, dirs, result, RUN)      # a second load adds nothing
    assert len(store.nodes("Claim")) == len(claims) and again["claims_written"] == len(claims)
    assert all(len(store.history(c["id"])) == 1 for c in claims)


def test_a_claim_whose_quote_is_not_in_the_file_is_not_believed(loaded):
    """Real words only: nothing is invented to make a claim fail. Claims really read from handoff W are
    set against handoff X, which does not hold their words, and a real claim of X against other lines of X."""
    store, dirs, result = loaded
    if not (store.data_root / READ_W).exists():
        pytest.skip(f"{READ_W} is not in this markets-data checkout")
    lines = (store.data_root / HANDOFF).read_text(encoding="utf-8").splitlines()
    whole = " ".join(" ".join(lines).split())
    of_w = json.loads((store.data_root / READ_W).read_text(encoding="utf-8"))["pieces"][0]["claims"]
    real = result["pieces"][0]["claims"][0]
    not_these_words = next(c for c in of_w if c["line_end"] <= len(lines) and " ".join(c["quote"].split()) not in whole)
    wrong_lines = {**real, "line_start": 60, "line_end": 60}                           # real quote of X, other lines of X
    outside = next(c for c in of_w if c["line_start"] > len(lines))                    # lines the piece does not have
    bad = {"pieces": [{"piece": result["pieces"][0]["piece"], "claims": [real, not_these_words, wrong_lines, outside]}]}
    report = extract.load_result(store, dirs, bad, RUN)
    assert report["claims_written"] == 1 and report["thrown_out"] == 3
    kept = [t["attrs"] for t in store.nodes("Task") if t["attrs"]["state"] == "blocked"]
    assert len(kept) == 3 and all(k["returned"] in (not_these_words, wrong_lines, outside) for k in kept)
    assert sorted(bool(re.search("word for word|outside the piece", k["reason"])) for k in kept) == [True] * 3


def test_a_read_needs_its_run_and_the_file_as_it_was_cut(loaded):
    store, dirs, result = loaded
    with pytest.raises(schema.Refused, match="not an AgentRun"):
        extract.load_result(store, dirs, result, "run:9999")
    stale = json.loads(json.dumps(result))
    stale["pieces"][0]["piece"] = re.sub(r"@[0-9a-f]{10}#", "@0000000000#", stale["pieces"][0]["piece"])
    with pytest.raises(schema.Refused, match="does not have"):          # a commit that never was
        extract.load_result(store, dirs, stale, RUN)
    assert store.nodes("Claim") == []


def test_a_read_of_a_file_that_has_since_grown_is_checked_against_the_file_as_it_was_read(tmp_path):
    """The decisions file is added to all the time. A read cut at an earlier commit still loads: each
    quote is checked against the file as it stood at that commit, and each claim says which."""
    root = data_root()
    rel = "graph/reads/run-0022-ROOT_GAMEPLAN_DECISIONS_L5853-L6152.json"
    if not (root / rel).exists():
        pytest.skip(f"{rel} is not in this markets-data checkout")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    result = json.loads((root / rel).read_text(encoding="utf-8"))
    cut = re.search(r"@([0-9a-f]{10})#", result["pieces"][0]["piece"]).group(1)
    path = f"{WORK}/root-redesign-20261116/ROOT_GAMEPLAN_DECISIONS.md"
    now = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%H", "--", path],
                         capture_output=True, text=True, check=True).stdout.strip()
    if now.startswith(cut):
        pytest.skip("the decisions file has not changed since this read was made")
    then = subprocess.run(["git", "-C", str(root), "show", f"{cut}:{path}"], capture_output=True, text=True, check=True).stdout.splitlines()
    returned = [c for p in result["pieces"] for c in p["claims"]]
    stood = [c for c in returned
             if _stands(c, then)]
    report = extract.load_result(store, dirs, result, "run:0022")
    claims = store.nodes("Claim")
    assert report["claims_written"] == len(claims) == len(stood)
    assert {c["attrs"]["source_commit"][:10] for c in claims} == {cut}                  # each says which wording it was read from
    assert store.node(claims[0]["attrs"]["source"])["attrs"]["commit"] == now          # the file's own line says where it stands now


def test_coverage_says_which_documents_are_read_and_which_are_not(loaded):
    store, dirs, result = loaded
    extract.load_result(store, dirs, result, RUN)
    out = extract.coverage(store, dirs)
    docs = {(d["repo"], d["path"]): d for d in out["documents"]}
    assert docs[("markets-data", HANDOFF)]["state"] == "done"
    w = docs[("markets-data", f"{WORK}/NEXT_SESSION_HANDOFF_20261124W.md")]
    assert w["state"] == "not_extracted" and w["claims"] == 0
    tasks = {t["id"]: t["attrs"] for t in store.nodes("Task") if t["id"].startswith("task:extract:")}
    assert len(tasks) == len([d for d in out["documents"] if d["state"] in ("done", "open", "not_extracted")])
    assert out["read"] == 1 and out["not_read"] == len(tasks) - 1          # nothing is passed over in silence
    assert tasks[f"task:extract:markets-data:{HANDOFF}"]["claims"] == len(store.nodes("Claim"))


def test_the_brief_numbers_every_line_and_cuts_only_at_entries():
    root = data_root()
    store = GraphStore(root)
    dirs = extract.repo_dirs(root, None, None)
    brief, listing = extract.build_brief(store, dirs, [f"markets-data:{HANDOFF}"])
    lines = (root / HANDOFF).read_text(encoding="utf-8").splitlines()
    assert len(listing) == 1 and (listing[0]["first"], listing[0]["last"]) == (1, len(lines))
    assert all(f"{n}| {lines[n - 1]}" in brief for n in (1, 7, len(lines)))
    big = (root / WORK / "root-redesign-20261116/ROOT_GAMEPLAN_DECISIONS.md").read_text(encoding="utf-8").splitlines()
    cut = extract.pieces(big)
    assert cut[0][0] == 1 and cut[-1][1] == len(big)
    assert all(a2 == b1 + 1 for (_, b1), (a2, _) in zip(cut, cut[1:]))      # no line lost, none read twice
    assert all(big[a - 1].startswith(("#", "- ")) for a, _ in cut[1:])       # a cut never falls inside an entry


# ---- the loader's fixes (review tickets F5.1 to F5.6) -----------------------------------------------------
# Only real returns and real lines are used. Where a case is built, it is built by setting two real things
# against each other (a real claim's quote with another real claim's text; a piece of real file text), and
# the comment says so.
from tools.kgraph.store import sha as _sha

ALL_READS = ("graph/reads/run-0018-NEXT_SESSION_HANDOFF_20261124X.json",)


def _real_lines(store):
    return (store.data_root / HANDOFF).read_text(encoding="utf-8").splitlines()


def test_a_quote_of_fewer_than_six_words_is_thrown_out_and_kept(loaded):
    """Real returns of the read of handoff X whose quote has fewer than 6 words."""
    store, dirs, result = loaded
    short = [c for p in result["pieces"] for c in p["claims"] if len(c["quote"].split()) < 6]
    if not short:
        pytest.skip("no claim of the real read of handoff X has a quote under 6 words")
    report = extract.load_result(store, dirs, result, RUN)
    kept = [t["attrs"]["returned"] for t in store.nodes("Task") if t["attrs"]["state"] == "blocked"]
    assert all(c in kept for c in short)
    assert all(extract.check_claim(c, _real_lines(store), 1, 119) for c in short)


def test_a_quote_that_starts_or_ends_inside_a_word_is_not_found(loaded):
    """A piece of real file text cut from the middle of a word to the middle of another (the handoff's own
    line), is not on the lines: the old test (a substring) let it through."""
    store, dirs, result = loaded
    lines = _real_lines(store)
    n = next(i for i, l in enumerate(lines, 1) if len(l.split()) >= 9 and l.lstrip().startswith("-"))
    line = lines[n - 1]
    words = line.split()
    start = line.index(words[1]) + 1                                 # one letter into the second word
    end = line.index(words[8]) + len(words[8]) - 1                   # one letter short of the ninth word's end
    cut = line[start:end]
    assert cut in line and len(cut.split()) >= 6
    c = {"line_start": n, "line_end": n, "quote": cut, "text": "x", "statement_kind": "state", "inference": False}
    assert "word for word" in extract.check_claim(c, lines, 1, len(lines))
    whole = {**c, "quote": " ".join(words[1:8])}                      # the same real words, whole
    assert extract.check_claim(whole, lines, 1, len(lines)) is None


def test_the_lines_of_a_claim_are_the_smallest_run_that_holds_the_quote(loaded):
    store, dirs, result = loaded
    extract.load_result(store, dirs, result, RUN)
    lines = _real_lines(store)
    ret = {_sha([c["quote"]]): c for p in result["pieces"] for c in p["claims"]}
    wider = 0
    for n in store.nodes("Claim"):
        a = n["attrs"]
        r = ret[_sha([a["quote"]])]
        assert a["lines_as_returned"] == [r["line_start"], r["line_end"]]
        assert a["lines_as_returned"][0] <= a["line_start"] <= a["line_end"] <= a["lines_as_returned"][1]
        assert _stands(a, lines)
        if a["line_end"] > a["line_start"]:       # one line less at either end and the quote is no longer there
            assert not _stands({**a, "line_start": a["line_start"] + 1}, lines)
            assert not _stands({**a, "line_end": a["line_end"] - 1}, lines)
        wider += a["lines_as_returned"] != [a["line_start"], a["line_end"]]
    link = next(e for e in store.edges("SUPPORTS"))
    assert link["attrs"]["line_start"] == store.node(link["dst"])["attrs"]["line_start"]


def test_a_different_wording_of_the_same_quote_is_a_second_claim_beside_the_first(loaded):
    """Built from two real returns on the same lines of handoff X: the first as the reader gave it, and the
    second reader's TEXT put on the first's QUOTE (the same words carrying another wording)."""
    store, dirs, result = loaded
    lines = _real_lines(store)
    claims = [c for p in result["pieces"] for c in p["claims"] if extract.check_claim(c, lines, 1, len(lines)) is None]
    by = {}
    for c in claims:
        by.setdefault((c["line_start"], c["line_end"]), []).append(c)
    pair = next((v for v in by.values() if len(v) > 1 and v[0]["text"] != v[1]["text"]), None)
    if pair is None:
        pytest.skip("the real read holds no two claims on the same lines")
    first, other = pair[0], pair[1]
    beside = {**first, "text": other["text"], "statement_kind": other["statement_kind"], "said_by": other["said_by"]}
    piece = result["pieces"][0]["piece"]
    sid = "src:markets-data:" + HANDOFF
    extract.load_result(store, dirs, {"pieces": [{"piece": piece, "claims": [first]}]}, RUN)
    plain = extract.claim_id(sid, first["quote"])
    before = store.node(plain)
    rep = extract.load_result(store, dirs, {"pieces": [{"piece": piece, "claims": [beside]}]}, RUN)
    assert rep["per_piece"][0]["second_claims_on_the_same_quote"] == 1
    assert store.node(plain)["rev"] == 1 and store.node(plain)["attrs"] == before["attrs"]      # the first is untouched
    twin = extract.claim_id_beside(sid, first["quote"], other["text"], other["statement_kind"], other["said_by"])
    assert store.node(twin)["attrs"]["text"] == other["text"] and store.node(twin)["rev"] == 1
    # both returned in ONE piece: neither overwrites the other
    s2 = GraphStore(store.data_root, graph_dir=store.dir.parent / "graph2")
    ingest_agent_runs.agent_runs(s2)
    rep = extract.load_result(s2, dirs, {"pieces": [{"piece": piece, "claims": [first, beside, first]}]}, RUN)
    assert {plain, twin} <= {n["id"] for n in s2.nodes("Claim")}
    assert s2.node(plain)["attrs"]["text"] == first["text"] and s2.node(twin)["attrs"]["text"] == other["text"]
    assert rep["per_piece"][0]["identical_returns_in_one_piece"] == 1      # the same return twice is said, not silent
    assert all(len(s2.history(i)) == 1 for i in (plain, twin))


def test_an_answer_with_a_piece_that_is_refused_writes_nothing_and_a_missing_piece_is_a_task(loaded, tmp_path):
    store, dirs, result = loaded
    good = result["pieces"][0]
    stale = {"piece": re.sub(r"@[0-9a-f]{10}#", "@0000000000#", good["piece"]), "claims": []}
    with pytest.raises(schema.Refused, match="does not have"):
        extract.load_result(store, dirs, {"pieces": [good, stale]}, RUN)      # the good piece comes FIRST
    assert store.nodes("Claim") == [] and store.nodes("Task") == []
    with pytest.raises(schema.Refused, match="no usable id"):
        extract.load_result(store, dirs, {"pieces": [good, {"piece": "nonsense", "claims": []}]}, RUN)
    assert store.nodes("Claim") == [] and store.nodes("Task") == []
    # `prompt` writes the list of pieces beside the brief; `load --pieces` makes a Task for each piece left out
    out = tmp_path / "brief.txt"
    gd = str(store.dir)
    assert extract.main(["--data", str(store.data_root), "--graph-dir", gd, "prompt", "--doc", f"markets-data:{HANDOFF}", "--out", str(out)]) == 0
    listed = json.loads((tmp_path / "brief.txt.pieces.json").read_text(encoding="utf-8"))
    assert [l["piece"] for l in listed] == [good["piece"]] and "source" not in listed[0]
    other_read = store.data_root / READ_W
    if not other_read.exists():
        pytest.skip(f"{READ_W} is not in this markets-data checkout")
    w_piece = json.loads(other_read.read_text(encoding="utf-8"))["pieces"][0]["piece"]
    m = re.fullmatch(r"src:([^:@]+):(.+)@[0-9a-f]{10}#L(\d+)-L(\d+)", w_piece)
    listed.append({"piece": w_piece, "repo": m.group(1), "path": m.group(2), "first": int(m.group(3)), "last": int(m.group(4)),
                   "source_id": w_piece.split("@")[0]})
    (tmp_path / "pieces.json").write_text(json.dumps(listed), encoding="utf-8")
    rep = extract.load_result(store, dirs, result, RUN, listed)
    assert rep["pieces_left_out_by_the_answer"] == 1
    left = [t for t in store.nodes("Task") if t["id"].startswith("task:piece-not-returned:")]
    assert len(left) == 1 and left[0]["attrs"]["state"] == "open" and left[0]["attrs"]["piece"] == w_piece
    assert extract.load_result(store, dirs, result, RUN, listed)["pieces_left_out_by_the_answer"] == 1
    assert len([t for t in store.nodes("Task") if t["id"].startswith("task:piece-not-returned:")]) == 1   # not twice
    assert store.check_all() == []


def _independent_marks(claim_attrs, lines):
    """What the two marks should say, by the check's own plainer route: digit runs on the entry, and the
    three words on the claim's lines and the two above."""
    a = claim_attrs
    n = a["line_start"]
    first = n
    while first > 1 and not re.match(r"(#|- |\d+[.)] |\s*\|)", lines[first - 1]):
        first -= 1
    end = n
    while end < len(lines) and not re.match(r"(#|- |\d+[.)] |\s*\|)", lines[end]):
        end += 1
    entry = "\n".join(lines[first - 1:end]).replace(",", "").lower()
    figs = [f for f in re.findall(r"\d[\d,.]*\d|\d", a["text"]) if f.replace(",", "").rstrip(".").lower() not in entry]
    near = " ".join(lines[max(0, n - 3):a["line_end"]])
    unnamed = a["said_by"] == "Greg" and not re.search(r"\b(Greg|his|he)\b", near, re.I)
    return figs, unnamed


def lines_of_entry(lines, n):
    first = n
    while first > 1 and not re.match(r"(#|- |\d+[.)] |\s*\|)", lines[first - 1]):
        first -= 1
    end = n
    while end < len(lines) and not re.match(r"(#|- |\d+[.)] |\s*\|)", lines[end]):
        end += 1
    return lines[first - 1:end]


def test_a_figure_not_on_the_claims_entry_and_a_greg_not_named_on_his_lines_are_marked_not_dropped(tmp_path):
    root = data_root()
    reads = sorted((root / "graph/reads").glob("run-*.json"))
    if not reads:
        pytest.skip("no real reads in this markets-data checkout")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    for f in reads:
        extract.load_result(store, dirs, json.loads(f.read_text(encoding="utf-8")), "run:" + f.name.split("-")[1])
    evals = store.nodes("Evaluation")
    marked = {}
    for e in evals:
        tgt = next(l["dst"] for l in store.edges("EVALUATES") if l["src"] == e["id"])
        marked.setdefault(tgt, {})[e["attrs"]["rubric"]] = e["attrs"]
    assert {e["attrs"]["rubric"] for e in evals} <= {extract.RUBRIC_TEXT, extract.RUBRIC_SAID_BY}
    assert extract.RUBRIC_TEXT == "text against its lines v1: every figure in a claim's text stands on the lines of its own entry"
    assert extract.RUBRIC_SAID_BY == "said by v1: a claim given as Greg's has his name on its lines or the two lines above"
    cache, seen_fig, seen_greg = {}, 0, 0
    for c in store.nodes("Claim"):
        a = c["attrs"]
        key = (a["source"], a["source_commit"])
        if key not in cache:
            repo, rel = re.fullmatch(r"src:([^:@]+):(.+)", a["source"]).groups()
            cache[key] = extract.git_text(dirs[repo], a["source_commit"], rel).splitlines()
        figs, unnamed = _independent_marks(a, cache[key])
        mine = marked.get(c["id"], {})
        if figs:                                         # a figure the plain route finds missing is marked
            assert extract.RUBRIC_TEXT in mine, (c["id"], figs)
        if extract.RUBRIC_TEXT in mine:
            seen_fig += 1
            named = mine[extract.RUBRIC_TEXT]["what_was_observed"][0].split(": ", 1)[1].split(", ")
            entry_text = "\n".join(lines_of_entry(cache[key], a["line_start"])).replace(",", "").lower()
            toks = {t.strip(".") for t in re.findall(r"[\w.]+", entry_text)}
            assert named and all(f.replace(",", "") not in toks for f in named), (c["id"], named)
        assert (extract.RUBRIC_SAID_BY in mine) == unnamed, c["id"]
        seen_greg += unnamed
        assert store.node(c["id"]) is not None            # a marked claim is still there, unchanged
    assert seen_fig + seen_greg > 0
    again = extract.recheck(store, dirs)                  # nothing twice
    assert again["marks_written"] == 0 and again["already_marked"] == len(evals)


def test_recheck_marks_the_claims_already_in_a_graph_and_writes_nothing_twice(tmp_path, monkeypatch):
    root = data_root()
    f = root / READ
    if not f.exists():
        pytest.skip(f"{READ} is not in this markets-data checkout")
    store = GraphStore(root, graph_dir=tmp_path / "graph")
    ingest_agent_runs.agent_runs(store)
    dirs = extract.repo_dirs(root, None, None)
    monkeypatch.setattr(extract, "_mark", lambda *a, **k: 0)      # claims as they stood before the marks existed
    extract.load_result(store, dirs, json.loads(f.read_text(encoding="utf-8")), RUN)
    monkeypatch.undo()
    assert store.nodes("Evaluation") == []
    first = extract.recheck(store, dirs)
    n = len(store.nodes("Evaluation"))
    assert first["marks_written"] == n and first["claims"] == len(store.nodes("Claim"))
    assert n > 0                                                 # the real claim of X L32 and others stand on Claude's words
    second = extract.recheck(store, dirs)
    assert second["marks_written"] == 0 and len(store.nodes("Evaluation")) == n
    assert store.check_all() == []
    assert extract.main(["--data", str(root), "--graph-dir", str(store.dir), "recheck"]) == 0
