"""The sealed-absence proof (F-23): the sealed object set, and the scan that proves it absent.

**The one genuinely new function of the S121 search.** `native_layer_crosswalk` consumes
`FRANKIE_SEALED_ABSENCE_PROOF_V1` (`all_absent`, `tokens_checked`, `receipt_sha256`) and
nothing produced it, so the nine sealed layers read SEALED_UNPROVEN on every crosswalk. The
pre-traversal gate (`corrected_a_arm_execution_gate.validate_rt_surface_inventory`) proves the
RT surface inventory DECLARES them sealed; nothing proved that what actually reaches the
principal - the prompt, the knowledge he is handed, the paths he is pointed at - names none
of them.

**The forbidden set is DERIVED, never typed.** Three classes:

- `SEALED_LAYER_ID`: every layer of the registry's `SEALED_FOR_A_SCOPE` groups (the validator
  pins them equal to `SEALED_LAYER_IDS`).
- `SECTION_K_PATH`: every source-inventory bullet `classify_inventory` classifies SEALED and
  that names a path (section K, the October Step-1 answer material).
- `STEP1_IDENTIFIER`: the Step-1 product identifiers read OUT OF those section-K files -
  the module-level string constants of the `.py` files and the string values of the `.json`
  files that carry `STEP1` - plus the Step-1 S3 result prefix, a constant here whose source
  (the Step-1 launch workflow) is checked by test.

**The scan is `brain_view.context_leak`'s shape**: exact, case-sensitive substring search of
every token over every named surface, every hit recorded with the surface and the token's
DIGEST (never the token in clear - the proof travels beside the prompt), and a hard failure
naming the surface. Case-sensitive on purpose: the KEEP corpus names `STEP1` in file names
(`NG_EXHAUSTION_CHAIN_STEP1_ORIGINAL_FILE_MAP_20260820.md`) and those are knowledge, not
the answer.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    canonical_bytes,
    canonical_hash,
    load_registry,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_knowledge_delivery import (
    MANIFEST_PATH,
    REPO_ROOT,
    SEALED,
    SPEC_PATH,
    ClassifiedPath,
    classify_inventory,
)

PROOF_SCHEMA = "FRANKIE_SEALED_ABSENCE_PROOF_V1"
SET_SCHEMA = "FRANKIE_SEALED_OBJECT_SET_V1"
SEALED_POLICY = "SEALED_FOR_A_SCOPE"
STEP1_S3_PREFIX = "nymex/ng_mbo_5y_v0/step1_census/"
"""The Step-1 result prefix on S3. Its source is the Step-1 launch workflow
(`STEP1_LAUNCH_WORKFLOW`), which the test suite reads to confirm this constant verbatim."""
STEP1_LAUNCH_WORKFLOW = ".github/workflows/ng_exhaustion_mbo_5y_step1_launch_20260822.yml"
MIN_IDENTIFIER_LENGTH = 12
"""Shorter than this and a Step-1 string would match prose; every derived identifier is longer."""
MAX_HITS_PER_TOKEN_PER_SURFACE = 5
_CONSTANT_RE = re.compile(r'^([A-Z][A-Z0-9_]*)\s*=\s*"([^"\n]+)"', re.MULTILINE)
_STEP1_RE = re.compile(r"STEP1")


class SealedAbsenceError(ValueError):
    """A sealed token is present where the principal would see it, or the proof is vacuous."""


def _json_strings(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, Mapping):
        for item in value.values():
            out |= _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            out |= _json_strings(item)
    elif isinstance(value, str):
        out.add(value)
    return out


def step1_identifiers(section_k_paths: Sequence[str], *, repo_root: Path | str = REPO_ROOT) -> list[str]:
    """Step-1 product identifiers read out of the section-K files themselves."""
    root = Path(repo_root)
    found: set[str] = {STEP1_S3_PREFIX}
    for relative in section_k_paths:
        path = root / relative
        if not path.is_file():
            continue
        if path.suffix == ".py":
            text = path.read_text(encoding="utf-8", errors="replace")
            for name, value in _CONSTANT_RE.findall(text):
                if _STEP1_RE.search(value) and len(value) >= MIN_IDENTIFIER_LENGTH:
                    found.add(value)
        elif path.suffix == ".json":
            try:
                body = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for value in _json_strings(body):
                if _STEP1_RE.search(value) and len(value) >= MIN_IDENTIFIER_LENGTH and " " not in value:
                    found.add(value)
    return sorted(found)


def sealed_object_set(
    registry: Mapping[str, Any] | None = None,
    inventory: Sequence[ClassifiedPath] | None = None,
    *,
    repo_root: Path | str = REPO_ROOT,
) -> dict[str, Any]:
    """The tokens that must be ABSENT from everything the principal is handed. Derived."""
    active = load_registry() if registry is None else registry
    rows = classify_inventory(repo_root) if inventory is None else list(inventory)
    layer_ids = sorted(
        entry["layer_id"] for group in active["groups"] if group["policy"] == SEALED_POLICY for entry in group["entries"]
    )
    k_paths = sorted(row.path for row in rows if row.classification == SEALED and row.path)
    identifiers = step1_identifiers(k_paths, repo_root=repo_root)
    tokens = sorted(set(layer_ids) | set(k_paths) | set(identifiers))
    if not tokens:
        raise SealedAbsenceError("the sealed object set is empty; a proof over nothing proves nothing")
    return {
        "schema": SET_SCHEMA,
        "registry_sha256": active["registry_sha256"],
        "by_class": {
            "SEALED_LAYER_ID": layer_ids,
            "SECTION_K_PATH": k_paths,
            "STEP1_IDENTIFIER": identifiers,
        },
        "tokens": tokens,
        "token_count": len(tokens),
        "sealed_set_sha256": hashlib.sha256(canonical_bytes(tokens)).hexdigest(),
    }


def _delivery_surface(delivery_receipt: Mapping[str, Any]) -> str:
    """Every path-like string a delivery receipt points the principal at, one per line."""
    parts: list[str] = []
    for key in ("run_prefix", "bucket", "out_dir"):
        value = delivery_receipt.get(key)
        if isinstance(value, str):
            parts.append(value)
    ledgers = delivery_receipt.get("ledgers")
    if isinstance(ledgers, Mapping):
        for name, entry in ledgers.items():
            parts.append(str(name))
            if isinstance(entry, Mapping):
                for field in ("local_path", "object", "file"):
                    if isinstance(entry.get(field), str):
                        parts.append(entry[field])
    objects = delivery_receipt.get("objects")
    if isinstance(objects, Mapping):
        for name, entry in objects.items():
            parts.append(str(name))
            if isinstance(entry, Mapping):
                for field in ("key", "local_path", "object"):
                    if isinstance(entry.get(field), str):
                        parts.append(entry[field])
    return "\n".join(parts)


def surfaces_from_delivery(
    *,
    knowledge_receipt: Mapping[str, Any],
    model_visible_context: bytes,
    delivery_receipt: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """The surfaces beyond the prompt: the bundle he reads, the knowledge paths, the delivered paths."""
    knowledge_paths: list[str] = [
        str(knowledge_receipt.get("manifest_path", MANIFEST_PATH)),
        str(knowledge_receipt.get("spec_path", SPEC_PATH)),
    ]
    knowledge_paths.extend(str(a["path"]) for a in knowledge_receipt.get("artifacts", []))
    for row in knowledge_receipt.get("layers", []):
        knowledge_paths.extend(str(f["path"]) for f in row.get("files", []))
        knowledge_paths.extend(str(m) for m in row.get("missing", []))
    surfaces = {
        "knowledge_bundle": bytes(model_visible_context).decode("utf-8", errors="replace"),
        "knowledge_paths": "\n".join(knowledge_paths),
    }
    if delivery_receipt is not None:
        surfaces["delivered_paths"] = _delivery_surface(delivery_receipt)
    return surfaces


def prove_sealed_absent(
    sealed: Mapping[str, Any], surfaces: Mapping[str, str | bytes], *, hard: bool = True
) -> dict[str, Any]:
    """Scan every surface for every sealed token; the four-key proof the crosswalk consumes.

    `hard=True` (the default, and the gate's setting) raises on the first surface with a hit,
    naming the surface and the offending token in the error - the error is not the prompt.
    `hard=False` returns the proof with `all_absent` false and the hits digested, which the
    crosswalk reads as SEALED_UNPROVEN.
    """
    tokens = list(sealed.get("tokens") or [])
    if not tokens:
        raise SealedAbsenceError("no sealed token to prove absent; the sealed object set is empty")
    if not surfaces:
        raise SealedAbsenceError("no surface to scan; a proof over no surface is vacuous")
    classes: dict[str, str] = {}
    for token_class, members in (sealed.get("by_class") or {}).items():
        for member in members:
            classes.setdefault(member, token_class)
    hits: list[dict[str, Any]] = []
    scanned: dict[str, dict[str, Any]] = {}
    clear: list[str] = []
    for surface, raw in surfaces.items():
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        scanned[surface] = {"bytes": len(text.encode("utf-8")), "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        for token in tokens:
            index = text.find(token)
            count = 0
            while index >= 0 and count < MAX_HITS_PER_TOKEN_PER_SURFACE:
                hits.append({
                    "surface": surface,
                    "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    "token_class": classes.get(token, "UNCLASSIFIED"),
                    "offset": index,
                })
                clear.append(f"{surface}: {token!r} at offset {index}")
                count += 1
                index = text.find(token, index + 1)
    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "all_absent": not hits,
        "tokens_checked": len(tokens),
        "sealed_set_sha256": sealed.get("sealed_set_sha256"),
        "token_digests": [hashlib.sha256(token.encode("utf-8")).hexdigest() for token in tokens],
        "surfaces_scanned": scanned,
        "hits": hits,
        "receipt_sha256": "",
    }
    proof["receipt_sha256"] = canonical_hash(proof, omit="receipt_sha256")
    if hits and hard:
        raise SealedAbsenceError(
            f"sealed token present in what the principal would receive ({len(hits)} hit(s)): "
            + "; ".join(clear[:8])
        )
    return proof
