"""Immutable, complete research sources shared by principal and scientific teacher.

Source content is never parsed, normalized, summarized, or promoted here. Catalog
metadata is separate from frozen Memory A. Reading receipts attest byte delivery
and completed host-retained calls, not comprehension or scientific validity.
The host must obtain provider_job and retained prompt/response bytes from its own
invocation records; model-authored attestations are not an authority source.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

CATALOG_SCHEMA = "FRANKIE_SHARED_KNOWLEDGE_CATALOG_V1"
SNAPSHOT_SCHEMA = "FRANKIE_SHARED_KNOWLEDGE_SNAPSHOT_V1"
DESCRIPTOR_SCHEMA = "FRANKIE_SHARED_KNOWLEDGE_DESCRIPTOR_V1"
READING_SCHEMA = "FRANKIE_STAGED_READING_RECEIPT_V1"
ROLES = frozenset(("principal", "scientific_teacher"))
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
_PRIVATE_PATH = re.compile(r"teacher[-_]key|classroom[-_]audit", re.I)


class KnowledgeIncomplete(ValueError):
    """All missing/mismatched sources; no complete snapshot was published."""
    def __init__(self, deficiencies):
        self.deficiencies = tuple(deficiencies)
        super().__init__("shared knowledge incomplete: " +
                         "; ".join(d["source_id"] + ": " + d["reason"] for d in deficiencies))


@dataclass(frozen=True)
class Snapshot:
    directory: Path
    snapshot_hash: str
    catalog: dict

    @property
    def sources(self):
        # Do not expose the stored mutable catalog through this convenience view.
        return tuple(json.loads(_canonical(self.catalog))["sources"])


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _hash(value):
    return _sha(_canonical(value))


def _digest(value, label):
    if type(value) is not str or not _SHA.fullmatch(value):
        raise ValueError(label + " must be a full lowercase SHA-256")
    return value


def _text(value, label):
    if type(value) is not str or not value.strip():
        raise ValueError(label + " must be nonempty text")
    return value


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(label + " must be an integer >= " + str(minimum))
    return value


def _catalog(value):
    if type(value) is not dict or value.get("schema") != CATALOG_SCHEMA:
        raise ValueError("shared knowledge catalog schema differs")
    _text(value.get("version"), "catalog version")
    sources = value.get("sources")
    if type(sources) is not list or not sources:
        raise ValueError("shared knowledge catalog requires all source entries")
    ids = set()
    for entry in sources:
        if type(entry) is not dict:
            raise ValueError("shared source entry must be an object")
        source_id = entry.get("id")
        if type(source_id) is not str or not _ID.fullmatch(source_id) or source_id in ids:
            raise ValueError("shared source id invalid or duplicated")
        ids.add(source_id)
        path = _text(entry.get("path"), "source path")
        parsed = PurePosixPath(path)
        if (parsed.is_absolute() or ".." in parsed.parts or "\\" in path
                or ":" in path or parsed.as_posix() != path):
            raise ValueError("shared source path must be a normalized repository-relative path")
        if entry.get("access") != "SHARED_RESEARCH" or _PRIVATE_PATH.search(path):
            raise ValueError("shared research cannot include a private teacher key or audit source")
        _text(entry.get("revision"), "source revision")
        _digest(entry.get("sha256"), "source digest")
        _integer(entry.get("bytes"), "source bytes")
        _text(entry.get("status"), "source status")
        _text(entry.get("explanation"), "source explanation")
        if entry.get("required") is not True:
            raise ValueError("every catalog source is required; missing knowledge cannot be hidden")
        if type(entry.get("provenance")) is not dict or not entry["provenance"]:
            raise ValueError("source provenance required")
        supersedes = entry.get("supersedes")
        if type(supersedes) is not list or any(type(s) is not str or not s for s in supersedes):
            raise ValueError("source supersession references must be a list of identifiers")
        if source_id in supersedes or len(set(supersedes)) != len(supersedes):
            raise ValueError("source supersession references cannot self-reference or repeat")
    # Preserve all additional review annotations and historical relationships.
    return json.loads(_canonical(value))


def _real_path(path):
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ValueError("shared knowledge symlink path refused")
    return path


def _read_regular(path):
    path = _real_path(path)
    if not path.is_file():
        raise ValueError("shared knowledge source or manifest is absent: " + str(path))
    return path.read_bytes()


def _raw(entry, data):
    if type(data) is not bytes:
        raise ValueError("source resolver must return exact bytes")
    if len(data) != entry["bytes"] or _sha(data) != entry["sha256"]:
        raise ValueError("source size or full digest differs")
    # The snapshot is a full-text research corpus; invalid UTF-8 must not turn into replacement characters.
    data.decode("utf-8", errors="strict")
    return data


def _body(catalog):
    return dict(schema=SNAPSHOT_SCHEMA, catalog=catalog)


def _put(path, raw):
    """Exclusive immutable write; an interrupted identical publication can resume."""
    path = _real_path(path)
    if path.exists():
        if _read_regular(path) != raw:
            raise ValueError("immutable snapshot path already carries different bytes")
        return
    try:
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if _read_regular(path) != raw:
            raise ValueError("concurrent snapshot publication differs")


def build_snapshot(catalog, resolve_source, destination):
    """Resolve every source before publishing MANIFEST.json.

    resolve_source(entry) returns exact bytes, including for a verified alias.
    Sources are content-addressed; source IDs and all review metadata remain in
    the manifest. A changed catalog requires a different destination.
    """
    catalog = _catalog(catalog)
    body = _body(catalog)
    expected_hash = _hash(body)
    directory = _real_path(destination)
    manifest_path = directory / "MANIFEST.json"
    if manifest_path.exists():
        return load_snapshot(directory, expected_hash)
    resolved, deficiencies = {}, []
    for entry in catalog["sources"]:
        try:
            data = _raw(entry, resolve_source(json.loads(_canonical(entry))))
            resolved[entry["sha256"]] = data
        except Exception as error:
            reason = str(error) if isinstance(error, (ValueError, UnicodeError)) else (
                "source resolution failed (" + type(error).__name__ + ")")
            deficiencies.append(dict(source_id=entry["id"], path=entry["path"], reason=reason))
    if deficiencies:
        raise KnowledgeIncomplete(deficiencies)
    directory.mkdir(parents=True, exist_ok=True)
    source_dir = _real_path(directory / "sources")
    source_dir.mkdir(exist_ok=True)
    for digest, raw in resolved.items():
        _put(source_dir / digest, raw)
    _put(manifest_path, _canonical(dict(body, snapshot_hash=expected_hash)))
    return load_snapshot(directory, expected_hash)


def load_snapshot(directory, expected_snapshot_hash):
    """Rehash manifest and every source; a receipt or path alone is insufficient."""
    _digest(expected_snapshot_hash, "snapshot hash")
    directory = _real_path(directory)
    raw = _read_regular(directory / "MANIFEST.json")
    try:
        saved = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ValueError("shared snapshot manifest unreadable") from error
    if (type(saved) is not dict or set(saved) != {"schema", "catalog", "snapshot_hash"}
            or saved.get("schema") != SNAPSHOT_SCHEMA):
        raise ValueError("shared snapshot manifest schema differs")
    catalog = _catalog(saved["catalog"])
    if (saved["snapshot_hash"] != expected_snapshot_hash
            or _hash(_body(catalog)) != expected_snapshot_hash
            or _canonical(saved) != raw):
        raise ValueError("shared snapshot identity or manifest bytes differ")
    source_dir = _real_path(directory / "sources")
    expected = {entry["sha256"] for entry in catalog["sources"]}
    if not source_dir.is_dir() or {p.name for p in source_dir.iterdir()} != expected:
        raise ValueError("shared snapshot source inventory differs")
    for entry in catalog["sources"]:
        _raw(entry, _read_regular(source_dir / entry["sha256"]))
    return Snapshot(directory, expected_snapshot_hash, catalog)


def _checked(snapshot):
    if not isinstance(snapshot, Snapshot):
        raise ValueError("verified shared knowledge Snapshot required")
    # Recheck disk against the immutable external hash, not the caller's mutable dict.
    return load_snapshot(snapshot.directory, snapshot.snapshot_hash)



def _descriptor(catalog, snapshot_hash):
    return dict(schema=DESCRIPTOR_SCHEMA, snapshot_hash=snapshot_hash,
                catalog_hash=_hash(catalog), catalog=catalog,
                sources=[dict(source_id=e["id"], sha256=e["sha256"], bytes=e["bytes"])
                         for e in catalog["sources"]])


def descriptor(snapshot):
    """Portable complete catalog and source roster, verified from immutable disk."""
    snapshot = _checked(snapshot)
    return _descriptor(snapshot.catalog, snapshot.snapshot_hash)


def validate_descriptor(value):
    """Validate the complete descriptor without filesystem access."""
    if type(value) is not dict or value.get("schema") != DESCRIPTOR_SCHEMA:
        raise ValueError("shared knowledge descriptor schema differs")
    catalog = _catalog(value.get("catalog"))
    expected = _descriptor(catalog, _hash(_body(catalog)))
    if value != expected:
        raise ValueError("shared knowledge descriptor identity or source roster differs")
    return json.loads(_canonical(expected))


def read_source(snapshot, source_id, byte_start=0, byte_count=16384):
    """Read an exact UTF-8 byte range; continue at next_byte_start until eof.

    byte_count is a maximum. End is rounded down to a UTF-8 boundary. If even one
    code point cannot fit, or start splits a code point, refuse without skipping.
    """
    snapshot = _checked(snapshot)
    entry = next((s for s in snapshot.sources if s["id"] == source_id), None)
    if entry is None:
        raise ValueError("shared source id is absent")
    start = _integer(byte_start, "source byte_start")
    count = _integer(byte_count, "source byte_count", 1)
    data = _read_regular(snapshot.directory / "sources" / entry["sha256"])
    if start > len(data):
        raise ValueError("source byte_start exceeds source")
    try:
        data[:start].decode("utf-8", errors="strict")
    except UnicodeError as error:
        raise ValueError("source start is not a UTF-8 boundary") from error
    end = min(len(data), start + count)
    while end > start:
        try:
            content = data[start:end].decode("utf-8", errors="strict")
            break
        except UnicodeDecodeError:
            end -= 1
    else:
        if start != len(data):
            raise ValueError("source byte_count cannot hold one UTF-8 code point")
        content = ""
    piece = data[start:end]
    return dict(source_id=source_id, start=start, end=end, next_byte_start=end,
                eof=end == len(data), source_sha256=entry["sha256"],
                chunk_sha256=_sha(piece), content=content, bytes=len(piece))


def _witnessed(value, label):
    if type(value) is not dict:
        raise ValueError(label + " retained content and witness required")
    content = value.get("content")
    if type(content) is str:
        raw = content.encode("utf-8")
    elif type(content) is bytes:
        raw = content
        raw.decode("utf-8", errors="strict")
    else:
        raise ValueError(label + " retained raw content required")
    if (type(value.get("bytes")) is not int or value["bytes"] != len(raw)
            or value.get("sha256") != _sha(raw)):
        raise ValueError(label + " retained content witness differs")
    return raw


def validate_reading(snapshot, receipt, role, request_hash, *, additional_sources=(),
                     expected_phase="shared_knowledge"):
    """Validate both full source coverage and host-retained call evidence.

    Compatible with FRANKIE_STAGED_READING_RECEIPT_V1. The staging validator owns
    plan validation; this boundary independently verifies source hashes/ranges,
    exact bytes at prompt source_offset, response acknowledgements, and provider
    job bindings. Supply retained content from actual host job records, never
    declarations authored by the model. A valid result is not comprehension.
    """
    snapshot = _checked(snapshot)
    if role not in ROLES:
        raise ValueError("shared knowledge reader role differs")
    _digest(request_hash, "reading request hash")
    if type(receipt) is not dict or receipt.get("schema") != READING_SCHEMA:
        raise ValueError("shared reading receipt schema differs")
    binding = receipt.get("binding")
    if (type(binding) is not dict or binding.get("role") != role
            or binding.get("phase") != _text(expected_phase, "reading phase")
            or binding.get("request_hash") != request_hash
            or binding.get("snapshot_hash") != snapshot.snapshot_hash):
        raise ValueError("shared reading binding differs")
    _text(binding.get("model_identity"), "reading model identity")
    _digest(receipt.get("plan_hash"), "reading plan hash")
    parts = receipt.get("parts")
    if type(parts) is not list or not parts:
        raise ValueError("shared reading parts required")
    sources = {e["id"]: e for e in snapshot.sources}
    data = {sid: _read_regular(snapshot.directory / "sources" / e["sha256"])
            for sid, e in sources.items()}

    for source in additional_sources:
        if type(source) is not dict:
            raise ValueError("additional reading source must be an object")
        sid = source.get("source_id", source.get("id"))
        if type(sid) is not str or not _ID.fullmatch(sid) or sid in sources:
            raise ValueError("additional source identifier invalid or duplicate")
        raw = source.get("content")
        if type(raw) is str:
            raw = raw.encode("utf-8")
        if type(raw) is not bytes:
            raise ValueError("additional source exact retained content required")
        raw.decode("utf-8", errors="strict")
        digest = _sha(raw)
        if (("sha256" in source and source["sha256"] != digest)
                or ("bytes" in source and (type(source["bytes"]) is not int
                                          or source["bytes"] != len(raw)))):
            raise ValueError("additional source retained witness differs")
        sources[sid] = dict(id=sid, sha256=digest, bytes=len(raw))
        data[sid] = raw
    coverage = {sid: [] for sid in sources}
    seen, jobs = set(), set()
    for part in parts:
        if type(part) is not dict:
            raise ValueError("shared reading part must be an object")
        part_id = _text(part.get("part_id"), "reading part id")
        if part_id in seen:
            raise ValueError("duplicate shared reading part")
        seen.add(part_id)
        sid = part.get("source_id")
        if sid not in sources:
            raise ValueError("reading source absent from snapshot")
        start = _integer(part.get("start"), "reading start")
        end = _integer(part.get("end"), "reading end")
        if not 0 <= start <= end <= len(data[sid]) or (start == end and data[sid]):
            raise ValueError("reading source range invalid")
        chunk = data[sid][start:end]
        try:
            data[sid][:start].decode("utf-8", errors="strict")
            chunk.decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise ValueError("reading range splits UTF-8") from error
        ack = dict(part_id=part_id, source_id=sid, start=start, end=end,
                   source_sha256=sources[sid]["sha256"], chunk_sha256=_sha(chunk))
        if any(part.get(k) != v for k, v in ack.items()) or part.get("ack") != ack:
            raise ValueError("reading source acknowledgement differs")
        prompt = _witnessed(part.get("prompt"), "reading prompt")
        response = _witnessed(part.get("response"), "reading response")
        offset = _integer(part.get("source_offset"), "prompt source offset")
        if offset > len(prompt) or prompt[offset:offset + len(chunk)] != chunk:
            raise ValueError("reading prompt does not contain the exact source bytes at source_offset")
        try:
            answer = json.loads(response)
        except (ValueError, UnicodeError) as error:
            raise ValueError("reading response acknowledgement must be structured JSON") from error
        if type(answer) is not dict or answer.get("ack") != ack:
            raise ValueError("reading ack is absent from the retained response")
        _text(answer.get("assessment"), "reading assessment")
        job = part.get("provider_job")
        if (type(job) is not dict or job.get("status") != "completed"
                or job.get("role") != role or job.get("request_hash") != request_hash
                or job.get("prompt_sha256") != _sha(prompt)
                or job.get("response_sha256") != _sha(response)):
            raise ValueError("retained provider job binding differs or call incomplete")
        job_id = _text(job.get("id"), "provider job id")
        if job_id in jobs:
            raise ValueError("provider job reused for different reading parts")
        jobs.add(job_id)
        coverage[sid].append((start, end))
    for sid, spans in coverage.items():
        if not spans:
            raise ValueError("shared reading source omitted: " + sid)
        cursor = 0
        for start, end in sorted(spans):
            if start != cursor:
                raise ValueError("shared reading source coverage has a gap or overlap: " + sid)
            cursor = end
        if cursor != len(data[sid]) or (not data[sid] and len(spans) != 1):
            raise ValueError("shared reading source coverage incomplete: " + sid)
    return dict(schema="FRANKIE_SHARED_KNOWLEDGE_COVERAGE_V1", status="complete",
                role=role, request_hash=request_hash, snapshot_hash=snapshot.snapshot_hash,
                plan_hash=receipt["plan_hash"], source_ids=list(sources), parts=len(parts),
                bytes=sum(len(raw) for raw in data.values()),
                meaning="All source bytes delivered in completed role-specific calls; not proof of comprehension.")
