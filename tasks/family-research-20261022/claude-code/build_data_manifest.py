"""Build data-manifest.json: every pinned data input this work reads, with its hash, its current pin in the
Markets repository, and its path in the markets-data repository.

Tiers: tape (Databento NG MBO UTC-day members), export (standalone group exports, sealed decisions, the
October 18 candidate inputs and ledgers), archive (ROOT frame spools: too large for any git repository,
listed with their published part counts and spool hashes so they can be moved to S3 and verified there).
Hashes come from the tape MANIFEST.json, the export receipts, and sha256 of the committed blobs. The
markets-data path keeps today's relative path so no loader has to rename anything.
"""

import hashlib
import io
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TAPE_COMMIT = "1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202"
PREFIX_COMMIT = "603c4defcb28fbf66cb6afc8d7728b1d7b1ed268"
FR = "tasks/family-research-20261022"
RET = "research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/retained/october18-standalone-inputs"


def git_show(commit, path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{path}"])


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    entries = []
    # tape members: the four originals pinned at the tape commit, the two prefix members at the data commit
    for commit in (TAPE_COMMIT, PREFIX_COMMIT):
        man = json.loads(git_show(commit, "data/nymex_mbo/ng_v0_oct2023/MANIFEST.json"))
        for f in man["files"]:
            rel = f"data/nymex_mbo/ng_v0_oct2023/{f['file']}"
            if any(e["path"] == rel for e in entries):
                continue
            entries.append(dict(tier="tape", path=rel, bytes=f["bytes"], sha256=f["sha256"], markets_commit=commit, records=f["records"],
                                utc_day=f["day"], markets_data_path=rel, note="Databento GLBX.MDP3 NG.v.0 continuous mbo, one UTC day"))
    entries.append(dict(tier="tape", path="data/nymex_mbo/ng_v0_oct2023/MANIFEST.json", bytes=None, sha256=None, markets_commit=PREFIX_COMMIT,
                        markets_data_path="data/nymex_mbo/ng_v0_oct2023/MANIFEST.json", note="Databento pull manifest (six members)"))
    # exports and decisions from receipts
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).decode().strip()
    for day in ("20231002", "20231003", "20231017"):
        for kind, fname, key in (("standalone-inputs", "groups.jsonl.gz", "groups_file"), ("standalone-decisions", "decisions.jsonl.gz", "output")):
            rec_path = f"{FR}/replay-artifacts/{day}/{kind}/receipt.json"
            rec = json.loads(git_show(head, rec_path))
            rel = f"{FR}/replay-artifacts/{day}/{kind}/{fname}"
            entries.append(dict(tier="export", path=rel, bytes=rec[key]["bytes"], sha256=rec[key]["sha256"], markets_commit=head, session=day,
                                receipt=rec_path, markets_data_path=rel, scope=rec.get("scope") or rec.get("summary", {}).get("scope") or "full session"))
            entries.append(dict(tier="export", path=rec_path, bytes=None, sha256=sha(git_show(head, rec_path)), markets_commit=head, session=day,
                                markets_data_path=rec_path, note="receipt"))
    rec = json.loads(git_show(head, f"{RET}/receipt.json"))
    entries.append(dict(tier="export", path=f"{RET}/groups.jsonl.gz", bytes=rec["groups_file"]["bytes"], sha256=rec["groups_file"]["sha256"], markets_commit=head,
                        session="20231018", receipt=f"{RET}/receipt.json", markets_data_path=f"{FR}/replay-artifacts/20231018/standalone-inputs/groups.jsonl.gz",
                        note="October 18 export; relocated under replay-artifacts/20231018 in markets-data so the four sessions share one layout"))
    entries.append(dict(tier="export", path=f"{RET}/receipt.json", bytes=None, sha256=sha(git_show(head, f"{RET}/receipt.json")), markets_commit=head, session="20231018",
                        markets_data_path=f"{FR}/replay-artifacts/20231018/standalone-inputs/receipt.json", note="receipt"))
    for fname, note in (("october18-candidate-inputs.jsonl.gz", "863 archived dipole recognitions reconstructed (b5f28bd)"),
                        ("october18-candidate-input-summary.json", "summary of the above"),
                        ("october18-size-one-mechanisms.jsonl.gz", "1,012 size-one episodes, 13:07 to 13:19 UTC window"),
                        ("october18-touch-print-decisions.jsonl.gz", "sealed touch-print decisions, October 18"),
                        ("october18-large-quote-moves.jsonl.gz", "Codex large quote moves")):
        b = git_show(head, f"{FR}/{fname}")
        entries.append(dict(tier="export", path=f"{FR}/{fname}", bytes=len(b), sha256=sha(b), markets_commit=head, session="20231018",
                            markets_data_path=f"{FR}/replay-artifacts/20231018/{fname}", note=note))
    # archives: listed, not moved by git
    for day in ("20231002", "20231003", "20231017"):
        src = json.loads(git_show(head, f"{FR}/replay-artifacts/{day}/root-frames/source.json"))
        sums = git_show(head, f"{FR}/replay-artifacts/{day}/root-frames/SHA256SUMS").decode().splitlines()
        entries.append(dict(tier="archive", path=f"{FR}/replay-artifacts/{day}/root-frames/", bytes_uncompressed=src["bytes"], spool_sha256=src["sha256"], rows=src["count"],
                            parts=len(sums), parts_listing=f"{FR}/replay-artifacts/{day}/root-frames/SHA256SUMS", markets_commit=head, session=day,
                            markets_data_path=None, target="s3://bento-568968024170-us-east-2-an/root-frames/" + day + "/",
                            note="ROOT frame spool split into sub-100 MB parts; not for any git repository; verify parts against SHA256SUMS after the move"))
    out = dict(schema="markets.data_manifest.v1", built_from_markets_commit=head, tape_commit=TAPE_COMMIT, prefix_commit=PREFIX_COMMIT,
               data_repository="DavisAI1974/markets-data (to be created)", entries=entries,
               totals={t: dict(files=sum(1 for e in entries if e["tier"] == t), bytes=sum(e.get("bytes") or 0 for e in entries if e["tier"] == t)) for t in ("tape", "export")},
               archive_total_uncompressed_bytes=sum(e["bytes_uncompressed"] for e in entries if e["tier"] == "archive"))
    (HERE / "data-manifest.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["totals"]), "archive uncompressed", out["archive_total_uncompressed_bytes"], "entries", len(entries))


if __name__ == "__main__":
    main()
