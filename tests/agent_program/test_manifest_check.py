"""Checks of the manifest check (tools/kgraph/manifest_check.py), through its public command.

Real cases read the real history of a markets-data checkout (set MARKETS_DATA). Expected values are
literals read with `git show --stat`, `git diff --name-status`, `git ls-tree -l` and `sha256sum`,
not with the command's own git calls. The cases the real history does not hold are in ONE separated
section at the foot of this file.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess

import pytest

from tests.agent_program.realrecords import PAPER
from tools.kgraph.manifest_check import main
from tools.kgraph.store import markets_data_root


def _root():
    try:
        root = markets_data_root()
    except FileNotFoundError as e:
        pytest.skip(f"no markets-data checkout: {e}")
    return root


def _needs(root, *commits):
    for c in commits:
        r = subprocess.run(["git", "-C", str(root), "cat-file", "-e", c + "^{commit}"], capture_output=True)
        if r.returncode:
            pytest.skip(f"this markets-data checkout does not hold commit {c}")


def _run(capsys, data, rng):
    code = main(["--data", str(data), "--range", rng])
    return code, capsys.readouterr().out.splitlines()


def _counts(lines):
    last = lines[-1]
    assert last.startswith("COUNTS ")
    return dict(kv.split("=") for kv in last.split()[1:])


# ---- real cases ----

def test_d70527a_five_run_plans_added_no_manifest_holds_them(capsys):
    # markets-data d70527a (`git show --stat`): added run-0157.json .. run-0161.json under PAPER/run-plans/;
    # `git diff --name-status d70527a^ d70527a` shows 5 A lines and nothing else; none of the 14 manifests at
    # d70527a names any of them (grep of each manifest at d70527a: 0 hits).
    root = _root()
    _needs(root, "d70527a")
    code, out = _run(capsys, root, "d70527a^..d70527a")
    assert code == 0
    c = _counts(out)
    assert (c["added"], c["with_entry"], c["no_entry"], c["gone_at_B"]) == ("5", "0", "5", "0")
    assert c["manifests_read"] == "13" and c["manifests_shape_not_read"] == "1"
    assert "manifest paper-rules/20261109/machine/PAPER_UNIVERSE_MANIFEST.json: its shape was not read" in out
    for n in range(157, 162):
        p = f"{PAPER}/run-plans/run-{n:04d}.json"
        rows = [ln for ln in out if ln.startswith(p + " |")]
        assert len(rows) == 1
        assert "exists at B" in rows[0] and "no manifest holds an entry for it" in rows[0]


def test_42614ca_first_load_experiments_files_have_entries(capsys):
    # markets-data 42614ca ("graph and experiments: the first load"), parent 624710b. `git diff --name-status`
    # shows A for experiments/MANIFEST.json, frankie_exp_dag.sqlite, trials.jsonl and graph/MANIFEST.json,
    # graph/edges/DERIVED_FROM.jsonl, graph/nodes/{AgentRun,Commit,Source}.jsonl = 8 added.
    # `git ls-tree -l`: trials.jsonl 52408 bytes, sha256 f924686d...; sqlite 77824 bytes, sha256 9074acf3...;
    # both equal their experiments/MANIFEST.json entries; DERIVED_FROM.jsonl 5171 bytes, sha256 711e9e0b..., equal
    # to its graph/MANIFEST.json entry. The two MANIFEST.json files are held by no manifest (not self-listed).
    root = _root()
    _needs(root, "42614ca", "624710b")
    code, out = _run(capsys, root, "624710b..42614ca")
    assert code == 0
    c = _counts(out)
    assert c["added"] == "8" and c["with_entry"] == "6" and c["no_entry"] == "2" and c["gone_at_B"] == "0"
    # manifest files at 42614ca (`git ls-tree -r --name-only 42614ca`, basename holding "manifest", ending .json): 8,
    # all read; two of them (data/nymex_mbo/ng_v0_oct2023, data/outside/ng_oct2023) carry no path key (see below)
    assert c["manifests_read"] == "8" and c["manifests_shape_not_read"] == "0"
    assert c["manifests_with_entries_not_read"] == "2" and c["under_a_folder_entry"] == "0"
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")]
    assert len(row) == 1
    assert "bytes at B 52408" in row[0]
    assert "experiments/MANIFEST.json: bytes equal, sha256 equal" in row[0]
    row = [ln for ln in out if ln.startswith("experiments/frankie_exp_dag.sqlite |")]
    assert "bytes at B 77824" in row[0] and "experiments/MANIFEST.json: bytes equal, sha256 equal" in row[0]
    row = [ln for ln in out if ln.startswith("graph/edges/DERIVED_FROM.jsonl |")]
    assert "bytes at B 5171" in row[0] and "graph/MANIFEST.json: bytes equal, sha256 equal" in row[0]
    for p in ("experiments/MANIFEST.json", "graph/MANIFEST.json"):
        row = [ln for ln in out if ln.startswith(p + " |")]
        assert len(row) == 1 and "no manifest holds an entry for it" in row[0]


def test_bad_range_exits_2_with_a_sentence(capsys):
    root = _root()
    code, out = _run(capsys, root, "0000000..1111111")
    assert code == 2
    assert len(out) == 1 and "cannot read the range" in out[0]


def test_bad_checkout_exits_2_with_a_sentence(capsys, tmp_path):
    code, out = _run(capsys, tmp_path, "a..b")
    assert code == 2
    assert len(out) == 1 and "cannot read the checkout" in out[0]


def test_output_gives_no_verdict_words(capsys):
    # the words, in any letter case, on the three real ranges (none of the three outputs holds one: read with grep -ci)
    root = _root()
    for rng, ends in (("624710b..42614ca", ("42614ca", "624710b")), ("557a3b0..ec7af4b", ("557a3b0", "ec7af4b")),
                      ("2fab819..a8a6738", ("2fab819", "a8a6738"))):
        _needs(root, *ends)
        code, out = _run(capsys, root, rng)
        assert code == 0
        assert re.search(r"pass|fail|error|wrong", " ".join(out), re.IGNORECASE) is None, rng


def test_carry_forward_file_is_found_by_its_path_relative_to_the_manifests_folder(capsys):
    # markets-data db095e0: carry-forward/20261109/FILE_MANIFEST.json holds {'path': 'FINDINGS_REGISTER.json',
    # 'bytes': 19808, 'sha256': '9e641327...383c'}; `git ls-tree -l db095e0` gives the file 19808 bytes and
    # `git show db095e0:carry-forward/20261109/FINDINGS_REGISTER.json | sha256sum` gives 9e641327...383c.
    # The file was added in 2fab819..a8a6738 (`git diff --name-status --diff-filter=A 2fab819 a8a6738`).
    root = _root()
    _needs(root, "2fab819", "a8a6738")
    code, out = _run(capsys, root, "2fab819..a8a6738")
    assert code == 0
    row = [ln for ln in out if ln.startswith("carry-forward/20261109/FINDINGS_REGISTER.json |")]
    assert len(row) == 1
    assert "bytes at B 19808" in row[0]
    assert ("carry-forward/20261109/FILE_MANIFEST.json: bytes equal, sha256 equal "
            "(path relative to the manifest's folder)") in row[0]
    assert "no manifest holds an entry for it" not in row[0]
    c = _counts(out)
    # 26 added (`git diff --name-status --diff-filter=A`); 25 are the 25 entries of FILE_MANIFEST.json (reviewer run 174:
    # "25 of 25"), the 26th is FILE_MANIFEST.json itself
    assert c["added"] == "26" and c["with_entry"] == "25" and c["no_entry"] == "1"
    row = [ln for ln in out if ln.startswith("carry-forward/20261109/FILE_MANIFEST.json |")]
    assert len(row) == 1 and "no manifest holds an entry for it" in row[0]


def test_entries_in_the_root_manifest_match_as_written(capsys):
    # markets-data 42614ca: experiments/MANIFEST.json holds the path "experiments/trials.jsonl" (git show)
    root = _root()
    _needs(root, "42614ca", "624710b")
    _, out = _run(capsys, root, "624710b..42614ca")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "experiments/MANIFEST.json: bytes equal, sha256 equal (path as written)" in row


def test_db095e0_entries_without_a_path_key_are_named(capsys):
    # `git show db095e0:data/nymex_mbo/ng_v0_oct2023/MANIFEST.json`: "files" holds 7 entries, each keyed "file", none "path";
    # `git show db095e0:data/outside/ng_oct2023/MANIFEST.json`: 142 entries, each keyed "address", none "path".
    # Reviewer run 174, same commit: also SOURCE_MANIFEST.json under claude-independent-research-20261113 (239 of 239)
    # and paper-rules/20261109/recovery/model_source_audit/SOURCE_MANIFEST.json (10 of 15): 4 manifests.
    root = _root()
    _needs(root, "557a3b0", "db095e0")
    code, out = _run(capsys, root, "557a3b0..db095e0")
    assert code == 0
    assert _counts(out)["manifests_with_entries_not_read"] == "4"
    for name, n, key in (("data/nymex_mbo/ng_v0_oct2023/MANIFEST.json", 7, "file"),
                         ("data/outside/ng_oct2023/MANIFEST.json", 142, "address")):
        line = [ln for ln in out if ln.startswith(f"manifest {name}: ")]
        assert len(line) == 1
        assert f": {n} of {n} entries carry neither" in line[0]
        keys = line[0].split("the keys those entries carry: ")[1].split(";")[0].split(", ")
        assert key in keys and "path" not in keys and "markets_data_path" not in keys
    # nothing is guessed from those keys: the files named by them are not matched
    assert _counts(out)["with_entry"] == "0"


def test_b_with_a_different_set_of_manifest_files_than_head(capsys):
    # markets-data 44c015a is before 42614ca, the newest commit to add a manifest (`git log --diff-filter=A --format=%h
    # -- '*MANIFEST*.json' '*manifest*.json'`). `git ls-tree -r --name-only 44c015a`: 16 files whose basename holds
    # "manifest" and ends .json; the checkout's HEAD ec7af4b holds 14. The command's own split of the 16: 15 read, 1 not.
    root = _root()
    _needs(root, "44c015a", "44c015a^")
    code, out = _run(capsys, root, "44c015a^..44c015a")
    assert code == 0
    c = _counts(out)
    assert c["manifests_read"] == "15" and c["manifests_shape_not_read"] == "1"
    assert ("manifest tasks/family-research-20261022/research-union-current/field-rebuild-20261113/"
            "ORIGINAL_FULL_POPULATION_MANIFEST.json: its shape was not read") in out


def test_a_renamed_file_is_listed_under_its_new_path(capsys):
    # markets-data 44c015a: `git diff -M --name-status 44c015a^ 44c015a` shows 16 R lines, one of them
    # R050 field-rebuild-20261113/book_records/20231017-5.jsonl.gz -> trade-day-rebuild-20261116/book_records/20231017-5.jsonl.gz;
    # `git ls-tree -l 44c015a` gives the new path 7779723 bytes; the old path is not in the tree at 44c015a.
    # `git diff --no-renames --diff-filter=A --name-only 44c015a^ 44c015a | wc -l` = 34.
    root = _root()
    _needs(root, "44c015a", "44c015a^")
    code, out = _run(capsys, root, "44c015a^..44c015a")
    base = "tasks/family-research-20261022/research-union-current/"
    new = base + "trade-day-rebuild-20261116/book_records/20231017-5.jsonl.gz"
    old = base + "field-rebuild-20261113/book_records/20231017-5.jsonl.gz"
    assert code == 0 and _counts(out)["added"] == "34"
    row = [ln for ln in out if ln.startswith(new + " |")]
    assert len(row) == 1 and "exists at B | bytes at B 7779723" in row[0]
    assert not [ln for ln in out if ln.startswith(old + " |")]


def test_graph_manifest_entries_still_match_as_written_where_the_joined_path_does_not_exist(capsys):
    # markets-data 7bdf323: `git show 7bdf323:graph/MANIFEST.json` holds 26 entries in "files", each "path" a string
    # written from the root ("graph/edges/..." and so on); `git ls-tree -r 7bdf323 --name-only | grep '^graph/graph/'`
    # gives nothing, so the joined reading names no file and the as-written reading is the one that counts.
    root = _root()
    _needs(root, "7bdf323", "624710b")
    code, out = _run(capsys, root, "624710b..7bdf323")
    assert code == 0
    rows = [ln for ln in out if "graph/MANIFEST.json: " in ln and "(path as written)" in ln and ln.startswith("graph/")]
    assert len(rows) == 26
    assert not [ln for ln in out if "names the same path in another folder" in ln and "graph/MANIFEST.json" in ln]


# ---- CASES THE REAL HISTORY DOES NOT HOLD ----
# Each is a real file's text with exactly the named thing changed, committed into a scratch git repo
# (tmp_path, never markets-data). Real texts come from markets-data 42614ca.

def _git(repo, *a, text=True, inp=None):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=text, input=inp, check=True)
    return r.stdout


def _scratch(tmp_path, root, manifest_text, extra_commit=None):
    """Commit 1: nothing but a README. Commit 2: real trials.jsonl and the (changed) manifest."""
    repo = tmp_path / "scratch"
    (repo / "experiments").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "x@example.invalid")
    _git(repo, "config", "user.name", "x")
    (repo / "README.md").write_text("scratch\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    trials = subprocess.run(["git", "-C", str(root), "show", "42614ca:experiments/trials.jsonl"],
                            capture_output=True, check=True).stdout
    (repo / "experiments" / "trials.jsonl").write_bytes(trials)
    (repo / "experiments" / "MANIFEST.json").write_text(manifest_text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add")
    if extra_commit:
        extra_commit(repo)
    return repo


def _real_manifest(root):
    _needs(root, "42614ca")
    return _git(root, "show", "42614ca:experiments/MANIFEST.json")


def test_changed_sha256_is_named_as_not_equal(capsys, tmp_path):
    # change: the sha256 of the experiments/trials.jsonl entry, first character f -> 0
    root = _root()
    text = _real_manifest(root)
    assert "f924686d" in text
    repo = _scratch(tmp_path, root, text.replace("f924686d", "0924686d", 1))
    code, out = _run(capsys, repo, "HEAD~1..HEAD")
    assert code == 0
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "experiments/MANIFEST.json: bytes equal, sha256 not equal" in row


def test_changed_bytes_is_named_as_not_equal(capsys, tmp_path):
    # change: the bytes of the experiments/trials.jsonl entry, 52408 -> 52409
    root = _root()
    text = _real_manifest(root)
    repo = _scratch(tmp_path, root, text.replace("52408", "52409", 1))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "experiments/MANIFEST.json: bytes not equal, sha256 equal" in row


def test_manifest_of_unknown_shape_is_named_not_skipped(capsys, tmp_path):
    # change: the key "files" renamed "rows", so the manifest holds no list under "entries" or "files"
    root = _root()
    text = _real_manifest(root)
    assert '"files"' in text
    repo = _scratch(tmp_path, root, text.replace('"files"', '"rows"', 1))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    assert "manifest experiments/MANIFEST.json: its shape was not read" in out
    c = _counts(out)
    assert c["manifests_shape_not_read"] == "1" and c["manifests_read"] == "0"
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "no manifest holds an entry for it" in row


def test_entry_without_bytes_or_sha_is_compared_only_where_it_carries_them(capsys, tmp_path):
    # change: the entry's "bytes" and "sha256" keys removed (the entry keeps path and source)
    root = _root()
    m = json.loads(_real_manifest(root))
    for k in ("bytes", "sha256"):
        del m["files"][0][k]
    repo = _scratch(tmp_path, root, json.dumps(m, indent=1))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "experiments/MANIFEST.json: bytes not in entry, sha256 not in entry" in row


def test_file_removed_after_being_added_is_counted_gone_at_B(capsys, tmp_path):
    # change: a third commit deletes experiments/trials.jsonl; range covers both commits
    root = _root()
    text = _real_manifest(root)

    def rm(repo):
        _git(repo, "rm", "-q", "experiments/trials.jsonl")
        _git(repo, "commit", "-q", "-m", "remove")

    repo = _scratch(tmp_path, root, text, rm)
    _, out = _run(capsys, repo, "HEAD~2..HEAD")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "gone at B" in row
    assert _counts(out)["gone_at_B"] == "1"


def _manifest_with(root, old, new):
    text = _real_manifest(root)
    assert text.count(old) == 1
    return text.replace(old, new, 1)


TRIALS_PATH = '"path": "experiments/trials.jsonl"'


def test_leading_dot_slash_is_dropped_before_matching(capsys, tmp_path):
    # change: the trials.jsonl entry's path "experiments/trials.jsonl" -> "./experiments/trials.jsonl" (nothing else)
    root = _root()
    repo = _scratch(tmp_path, root, _manifest_with(root, TRIALS_PATH, '"path": "./experiments/trials.jsonl"'))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "experiments/MANIFEST.json: bytes equal, sha256 equal (path as written)" in row


def test_path_relative_to_the_manifests_folder_in_a_scratch_folder(capsys, tmp_path):
    # change: the trials.jsonl entry's path "experiments/trials.jsonl" -> "trials.jsonl" (nothing else)
    root = _root()
    repo = _scratch(tmp_path, root, _manifest_with(root, TRIALS_PATH, '"path": "trials.jsonl"'))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert ("experiments/MANIFEST.json: bytes equal, sha256 equal (path relative to the manifest's folder)") in row


def test_entry_naming_a_folder_is_not_an_entry_for_a_file(capsys, tmp_path):
    # change: the trials.jsonl entry's path "experiments/trials.jsonl" -> "experiments/" (nothing else). Both files
    # added in the scratch range (trials.jsonl, MANIFEST.json) are under experiments/.
    root = _root()
    repo = _scratch(tmp_path, root, _manifest_with(root, TRIALS_PATH, '"path": "experiments/"'))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    for p in ("experiments/trials.jsonl", "experiments/MANIFEST.json"):
        row = [ln for ln in out if ln.startswith(p + " |")][0]
        assert "experiments/MANIFEST.json: this manifest names its folder in an entry (path as written)" in row
        assert "bytes equal" not in row and "no manifest holds an entry" not in row
    c = _counts(out)
    assert (c["added"], c["with_entry"], c["no_entry"], c["under_a_folder_entry"]) == ("2", "0", "0", "2")


def test_entry_with_no_path_key_is_named_and_its_key_not_read(capsys, tmp_path):
    # change: the trials.jsonl entry's key "path" -> "file" (value, other keys and the second entry unchanged)
    root = _root()
    repo = _scratch(tmp_path, root, _manifest_with(root, TRIALS_PATH, '"file": "experiments/trials.jsonl"'))
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    line = [ln for ln in out if ln.startswith("manifest experiments/MANIFEST.json: ")]
    assert len(line) == 1
    assert ": 1 of 2 entries carry neither" in line[0]
    assert "the keys those entries carry: bytes, file, sha256, source;" in line[0]
    row = [ln for ln in out if ln.startswith("experiments/trials.jsonl |")][0]
    assert "no manifest holds an entry for it" in row
    c = _counts(out)
    assert c["manifests_with_entries_not_read"] == "1" and c["manifests_read"] == "1"


def test_a_read_that_failed_is_not_a_file_that_is_gone(capsys, tmp_path):
    # change: after the commit, the loose object file of the experiments/trials.jsonl blob is deleted from the scratch
    # repo's .git/objects, so `git ls-tree` still lists the path and `git show HEAD:experiments/trials.jsonl` fails
    root = _root()
    repo = _scratch(tmp_path, root, _real_manifest(root))
    sha = _git(repo, "rev-parse", "HEAD:experiments/trials.jsonl").strip()
    obj = repo / ".git" / "objects" / sha[:2] / sha[2:]
    assert obj.is_file()
    os.chmod(obj, stat.S_IWRITE | stat.S_IREAD)
    obj.unlink()
    code, out = _run(capsys, repo, "HEAD~1..HEAD")
    assert code == 2
    assert "cannot read experiments/trials.jsonl at" in out[-1] and "could not be read" in out[-1]
    assert len([ln for ln in out if ln.startswith("cannot read")]) == 1
    assert not any(ln.startswith("COUNTS") for ln in out)


def test_when_both_readings_name_a_file_the_entry_means_the_one_in_the_manifests_folder(capsys, tmp_path):
    # markets-data 7bdf323: paper-rules/20261109/FILE_MANIFEST.json holds {"path": "tasks/plan.md", "bytes": 3284, ...};
    # `git cat-file -s` gives tasks/plan.md 3283 bytes and paper-rules/20261109/tasks/plan.md 3284 bytes.
    # change: the text of that manifest is committed unchanged into a scratch repo, with the real tasks/plan.md and the
    # real paper-rules/20261109/tasks/plan.md, both added in the one commit (the real root file came in a root commit)
    root = _root()
    _needs(root, "7bdf323")
    repo = tmp_path / "scratch"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "x@example.invalid")
    _git(repo, "config", "user.name", "x")
    (repo / "README.md").write_text("scratch\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    for src, dst in (("tasks/plan.md", "tasks/plan.md"),
                     ("paper-rules/20261109/tasks/plan.md", "paper-rules/20261109/tasks/plan.md"),
                     ("paper-rules/20261109/FILE_MANIFEST.json", "paper-rules/20261109/FILE_MANIFEST.json")):
        blob = subprocess.run(["git", "-C", str(root), "show", f"7bdf323:{src}"], capture_output=True, check=True).stdout
        (repo / dst).parent.mkdir(parents=True, exist_ok=True)
        (repo / dst).write_bytes(blob)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add")
    _, out = _run(capsys, repo, "HEAD~1..HEAD")
    nested = [ln for ln in out if ln.startswith("paper-rules/20261109/tasks/plan.md |")][0]
    assert "bytes at B 3284" in nested
    assert "paper-rules/20261109/FILE_MANIFEST.json: bytes equal, sha256 equal (path relative to the manifest's folder)" in nested
    top = [ln for ln in out if ln.startswith("tasks/plan.md |")][0]
    assert "bytes at B 3283" in top
    assert "bytes equal" not in top and "bytes not equal" not in top
    assert "names the same path in another folder" in top
    assert "paper-rules/20261109/FILE_MANIFEST.json" in top and "paper-rules/20261109/tasks/plan.md" in top
    assert "not counted as its entry" in top
    c = _counts(out)
    assert (c["added"], c["with_entry"], c["no_entry"]) == ("3", "1", "2")
