"""Repair Tier 1 annotation precision only; no market analysis or suite rerun."""
import copy, csv, gzip, hashlib, importlib.util, json, pathlib, re, subprocess, sys, tempfile, urllib.request

M = "DavisAI1974/Markets"
D = "DavisAI1974/markets-data"
FIX = "418462afeaf0f14aa8129f6f4d02c3867d772fd0"
SUITE = "3d0b06aa29781d5e39cc3eb45c6d09e174f195a2"
OLD_DATA = "c01caaf4f327e8fdff21e4e8b9c5153aba8604a8"
OLD_PACKET_REV = "5347fb95a760de8732c1b27d6fb0536a85a2628e"
OLD_PACKET = "tasks/family-research-20261022/shared-reanalysis-inputs/run-42588327774-1"
BASE = "tasks/family-research-20261022"
PIN = BASE + "/claude-code-pins"
CODE = BASE + "/claude-code"
REG = "artifacts/sqlite-triage/20261022/families/full-context-audit/canonical-99-registry.json"
READS = []

def fetch(repo, rev, path):
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{rev}/{path}", timeout=180) as response:
        data = response.read()
    READS.append(dict(repository=repo, revision=rev, path=path, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    return data

def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

def repair(out):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for path in (CODE + "/pin_tier1_rows_to_99.py", CODE + "/pin_rows_to_99.py", CODE + "/data-manifest.json", REG):
            dest = root / path; dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(fetch(M, FIX, path))
        for day in ("20231002", "20231003", "20231017", "20231018"):
            for name in ("t1_family_master_flags.csv", "t1_receipt.json"):
                path = f"{BASE}/claude-pass-3day/tables/{day}/{name}"
                dest = root / path; dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(fetch(M, SUITE, path))
        spec = importlib.util.spec_from_file_location("tier1_precision", root / CODE / "pin_tier1_rows_to_99.py")
        module = importlib.util.module_from_spec(spec)
        saved = sys.argv
        sys.argv = [str(root / CODE / "pin_tier1_rows_to_99.py"), str(root), str(out)]
        try:
            spec.loader.exec_module(module)
        finally:
            sys.argv = saved
        # Regression reproducer: the old float-first parser loses this exact clock and its 1 ns boundary.
        ns = 1696204800032777277
        assert int(float(str(ns))) != ns
        assert module.num(str(ns)) == ns and type(module.num(str(ns))) is int
        assert module.num(str(ns - 1)) == ns - 1
        assert module.num("-9007199254740993") == -9007199254740993
        assert module.num("1.25") == 1.25 and module.num("True") is True
        assert module.num("") is None and module.num("family") == "family"
        module.main()
        checks = []
        for tag, day in module.P.DAY.items():
            name = f"ninety-nine-pins-tier1-{tag}.jsonl.gz"
            old_path = root / name; old_path.write_bytes(fetch(D, OLD_DATA, PIN + "/" + name))
            source = root / f"{BASE}/claude-pass-3day/tables/{day}/t1_family_master_flags.csv"
            n = pins = corrected = 0
            with source.open(newline="") as raw_file, gzip.open(old_path, "rt") as old_file, gzip.open(out / name, "rt") as new_file:
                for ordinal, raw in enumerate(csv.DictReader(raw_file)):
                    old = json.loads(next(old_file)); new = json.loads(next(new_file))
                    assert new["ordinal"] == old["ordinal"] == ordinal
                    assert new["ids"] == old["ids"] and new["sources"] == old["sources"]
                    assert new["session"] == old["session"] and new["file"] == old["file"]
                    expected = {k: module.num(v) for k, v in raw.items()}
                    assert new["row"] == expected
                    for key, value in expected.items():
                        if key.endswith("_ns") and value is not None:
                            assert type(value) is int and value == int(raw[key])
                            assert new["clocks"][key] == value
                            corrected += old["row"][key] != value
                        else:
                            assert new["row"][key] == old["row"][key], (tag, ordinal, key)
                    start, cutoff, ref = (int(raw[k]) for k in ("start_recv_ns", "cutoff_ns", "ref_recv_ns"))
                    assert start - cutoff == 1 and ref <= cutoff
                    assert new["clocks"]["start_utc_ns"] == module.P.utc_ns(start)
                    assert new["clocks"]["cutoff_utc"] == module.P.utc_ns(cutoff)
                    assert new["clocks"]["ref_recv_utc"] == module.P.utc_ns(ref)
                    assert len(old["pins"]) == len(new["pins"])
                    for before, after in zip(old["pins"], new["pins"]):
                        assert before["field"] == after["field"] and before["layers"] == after["layers"]
                        assert before["clock_kind"] == after["clock_kind"]
                        assert after["value"] == expected[after["field"]]
                        kind = after["clock_kind"]
                        if kind == "known_by_cutoff_ns": exact = cutoff
                        elif kind == "known_by_receive_ns": exact = ref
                        elif kind == "receive_ns": exact = start
                        elif kind.startswith("outcome_window_start_plus_"):
                            exact = start + int(re.search(r"plus_(\d+)s", kind).group(1)) * module.NS
                        else: raise AssertionError(kind)
                        assert type(after["clock_ns"]) is int and after["clock_ns"] == exact
                        assert after["clock_epoch_s"] == exact // module.NS
                        assert after["clock_utc"] == module.P.utc_ns(exact)
                        pins += 1
                    n += 1
                assert old_file.read() == "" and new_file.read() == ""
            checks.append(dict(session=tag,rows=n,pins=pins,corrected_integer_clock_values=corrected,
                               all_source_rows_and_pins_verified=True,non_clock_values_unchanged=True))
        summary = json.loads((out / "ninety-nine-pins-tier1-summary.json").read_text())
        assert sum(c["rows"] for c in checks) == 3215
        entries = []
        for path in sorted(out.iterdir()):
            data = path.read_bytes()
            entries.append(dict(path=path.as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                                supersedes=dict(repository=D,revision=OLD_DATA,path=PIN + "/" + path.name)))
        write(out / "VERIFICATION.json",dict(status="PASS",analysis_authorized=False,code_revision=FIX,
              suite_revision=SUITE,checks=checks,total_rows=sum(c["rows"] for c in checks),
              total_pins=sum(c["pins"] for c in checks),sources=READS,files=entries))
        print(json.dumps(checks))

def refresh(pins_path, pins_revision, out):
    out = pathlib.Path(out)
    names = ("CANONICAL_INPUTS.json","SUMMARY.json","DEFINITION_CHECK.json","DUPLICATE_ALIASES.json",
             "ANNOTATION_OVERLAPS.json","UNAVAILABLE_REFERENCES.json","SOURCES.json")
    files = {name:json.loads(fetch(D,OLD_PACKET_REV,OLD_PACKET+"/"+name)) for name in names}
    verified = json.loads((pathlib.Path(pins_path)/"VERIFICATION.json").read_text())
    packet = files["CANONICAL_INPUTS.json"]
    replacements = {entry["supersedes"]["path"]:entry for entry in verified["files"]}
    replaced = []
    for group in packet["active_inputs"]:
        variants = [group["canonical"]] + group["aliases"]
        matches = [v for v in variants if v["repository"] == D and v["path"] in replacements]
        if not matches: continue
        old_group = copy.deepcopy(group)
        entry = replacements[matches[0]["path"]]
        current = dict(repository=D, revision=pins_revision, path=entry["path"], bytes=entry["bytes"],
                       sha256=entry["sha256"],collection="tier1_precision_corrected",
                       role=matches[0]["role"],checksum_evidence="measured; every source row and pin verified",
                       day=matches[0].get("day"),clock_status="exact integer clocks verified against original CSV")
        group.update(content_id="sha256:"+entry["sha256"],sha256=entry["sha256"],bytes=entry["bytes"],
                     canonical=current,aliases=[],clock_attachments=[])
        group["supersedes"] = variants
        group["correction_reason"] = "float-first CSV parsing rounded nanosecond timestamps; corrected from original integer text"
        replaced.append(dict(old_content_id=old_group["content_id"],new_content_id=group["content_id"],
                             superseded_coordinates=variants,replacement=current))
    assert len(replaced) == 5
    tier = next(g["canonical"] for g in packet["active_inputs"] if g["canonical"]["path"].endswith("ninety-nine-pins-tier1-summary.json"))
    packet["definitions"]["tier1_pin_summary"] = tier
    files["DEFINITION_CHECK.json"]["tier1_pin_summary"] = tier
    by_old = {x["old_content_id"]:x for x in replaced}
    files["DUPLICATE_ALIASES.json"] = [x for x in files["DUPLICATE_ALIASES.json"] if x["content_id"] not in by_old]
    for item in files["ANNOTATION_OVERLAPS.json"]:
        if item["content_id"] in by_old:
            replacement = by_old[item["content_id"]]
            item["content_id"] = replacement["new_content_id"]
            item["source"] = replacement["replacement"]
            item["exact_row_aliases_verified"] = True
            item["treatment"] = "join annotation to original Tier 1 CSV by session + source row ordinal + family_id + instance; never count embedded rows separately"
    aliases = sum(len(g["aliases"]) for g in packet["active_inputs"])
    for obj in (packet, files["SUMMARY.json"]):
        obj["source_coordinates"] = len(packet["active_inputs"]) + aliases
        obj["duplicate_file_aliases_removed"] = aliases
        obj["duplicate_groups"] = sum(bool(g["aliases"]) for g in packet["active_inputs"])
        obj["analysis_authorized"] = False
        obj["evidence_frozen"] = False
        obj["precision_correction"] = dict(repository=D,revision=pins_revision,
            verification_path=pins_path+"/VERIFICATION.json",replacement_count=len(replaced),
            scope="four Tier 1 ledgers and their summary only; final-suite preparation is otherwise unchanged")
    files["SOURCES.json"] += verified["sources"]
    files["PRECISION_CORRECTION.json"] = dict(status="PASS",replacements=replaced,
        verification=packet["precision_correction"],original_packet=dict(repository=D,revision=OLD_PACKET_REV,path=OLD_PACKET))
    for name, obj in files.items(): write(out/name,obj)

if __name__ == "__main__":
    if sys.argv[1] == "repair": repair(sys.argv[2])
    elif sys.argv[1] == "refresh": refresh(*sys.argv[2:])
    else: raise SystemExit("repair OUTPUT or refresh PINS_PATH PINS_REV OUTPUT")
