"""Publish a sealed RunPod ROOT frame archive to Git in bounded batches."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

BRANCH = "refs/heads/codex/ng-shadow-discovery-20261108"
REPOSITORY = "https://github.com/DavisAI1974/Markets.git"
DESTINATION = "tasks/family-research-20261022/replay-artifacts"
PORTS = {"20231002": "34955", "20231003": "31686", "20231017": "31620"}
PART = re.compile(r"([0-9a-f]{64})  (frames\.jsonl\.zst\.part-[0-9]{6})")
BATCH_PARTS = 8


def git(repo, *args, env=None, data=None):
    return subprocess.check_output(["git", "-C", str(repo), *args], env=env, input=data)


def fetch_head(repo, ref):
    git(repo, "fetch", "--quiet", "--depth=1", "--filter=blob:none", "--no-tags", "origin", ref)
    return git(repo, "rev-parse", "FETCH_HEAD").decode().strip()


def staging_parent(repo, ref):
    lookup = git(repo, "ls-remote", "origin", ref)
    return fetch_head(repo, ref if lookup else BRANCH)


def tree(repo, revision, folder):
    listing = git(repo, "ls-tree", "-r", revision, "--", folder).decode()
    return {path: header.split()[2] for header, path in
            (line.split("\t", 1) for line in listing.splitlines())}


def publish(repo, ref, folder, files, index, message):
    env = dict(os.environ, GIT_INDEX_FILE=str(index), GIT_NO_REPLACE_OBJECTS="1")
    for _ in range(4):
        parent = staging_parent(repo, ref)
        previous = tree(repo, parent, folder)
        changed = {path: oid for path, oid in files.items() if previous.get(path) != oid}
        if any(path in previous for path in changed):
            raise ValueError("publication would replace an existing archive part")
        if not changed:
            return parent
        git(repo, "read-tree", parent, env=env)
        entries = "".join(f"100644 {oid}\t{path}\n" for path, oid in changed.items())
        git(repo, "update-index", "--add", "--index-info", env=env, data=entries.encode())
        root = git(repo, "write-tree", "--missing-ok", env=env).decode().strip()
        commit = git(repo, "commit-tree", root, "-p", parent, "-m", message).decode().strip()
        result = subprocess.run(["git", "-C", str(repo), "push", "--porcelain", "origin", f"{commit}:{ref}"],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            if any(word in result.stdout for word in ("fetch first", "non-fast-forward", "cannot lock ref")):
                continue
            raise RuntimeError(result.stdout)
        remote = fetch_head(repo, ref)
        published = tree(repo, remote, folder)
        if any(published.get(path) != oid for path, oid in files.items()):
            raise RuntimeError(f"published tree differs at {remote}")
        print(f"{remote} published {len(changed)} archive files", flush=True)
        return remote
    raise RuntimeError(f"{ref} advanced during each of four push attempts")


def archive_ssh(day):
    return ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            "-p", PORTS[day], "root@38.80.152.147"]


def part_blob(repo, ssh, remote, local, expected, existing):
    if existing:
        payload = git(repo, "cat-file", "blob", existing)
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError(f"published bytes differ for {remote}")
        return existing
    with local.open("wb") as output:
        subprocess.run([*ssh, "cat", "--", remote], stdout=output, check=True)
    with local.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
            raise ValueError(f"download differs for {remote}")
    return git(repo, "hash-object", "-w", "--no-filters", str(local)).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("day", choices=PORTS)
    parser.add_argument("bare_repository", type=Path)
    args = parser.parse_args()
    repo, day = args.bare_repository.resolve(), args.day
    if git(repo, "remote", "get-url", "origin").decode().strip() != REPOSITORY:
        raise ValueError("unexpected Git remote")
    ssh = archive_ssh(day)
    remote = f"/opt/frankie-box/work/git-publication/{day}/root-frames"
    folder = f"{DESTINATION}/{day}/root-frames"
    staging = f"refs/heads/codex/replay-archive-{day}"
    sums = subprocess.check_output([*ssh, "cat", "--", f"{remote}/SHA256SUMS"])
    source = subprocess.check_output([*ssh, "cat", "--", f"{remote}/source.json"])
    parts = [PART.fullmatch(line) for line in sums.decode().splitlines()]
    if not parts or any(part is None for part in parts):
        raise ValueError("malformed or empty archive checksum list")
    inventory = [part.groups() for part in parts]
    if [name for _, name in inventory] != [f"frames.jsonl.zst.part-{i:06d}" for i in range(len(inventory))]:
        raise ValueError("archive parts are incomplete or out of order")
    with tempfile.TemporaryDirectory(prefix=f"publish-{day}-", dir=repo.parent) as work:
        temporary = Path(work)
        index = temporary / "index"
        current = tree(repo, staging_parent(repo, staging), folder)
        if f"{folder}/SHA256SUMS" in current and f"{folder}/source.json" in current:
            same = (git(repo, "cat-file", "blob", current[f"{folder}/SHA256SUMS"]) == sums and
                    git(repo, "cat-file", "blob", current[f"{folder}/source.json"]) == source)
            if same and all(f"{folder}/{name}" in current for _, name in inventory):
                remote_commit = publish(
                    repo, BRANCH, folder, current, index, f"data: publish the sealed {day} ROOT frame archive [skip ci]",
                )
                print(f"COMPLETE {day} {len(inventory)} parts {remote_commit}", flush=True)
                return
            raise ValueError("existing final manifest differs from the sealed archive")
        verified = {}
        for first in range(0, len(inventory), BATCH_PARTS):
            batch = {}
            for digest, name in inventory[first:first+BATCH_PARTS]:
                path = f"{folder}/{name}"
                batch[path] = part_blob(repo, ssh, f"{remote}/{name}", temporary / "part", digest, current.get(path))
            publish(repo, staging, folder, batch, index, f"data: save {day} ROOT frame archive parts {first:06d} onward [skip ci]")
            verified.update(batch)
        for name, payload in (("SHA256SUMS", sums), ("source.json", source)):
            verified[f"{folder}/{name}"] = git(repo, "hash-object", "-w", "--stdin", data=payload).decode().strip()
        publish(repo, staging, folder, verified, index, f"data: seal the {day} ROOT frame archive in Git [skip ci]")
        remote_commit = publish(
            repo, BRANCH, folder, verified, index, f"data: publish the sealed {day} ROOT frame archive [skip ci]",
        )
        print(f"COMPLETE {day} {len(inventory)} parts {remote_commit}", flush=True)


if __name__ == "__main__":
    main()
