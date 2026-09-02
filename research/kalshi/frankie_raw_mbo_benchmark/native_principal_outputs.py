"""The principal's OUTPUT ledgers: the required set is derived, never counted in advance.

Frankie receives every record of every field for the day as a causal stream in `ts_recv_ns`
order and computes every calculation-contract section himself (D81). What he writes is
produced sequentially as the stream advances and is never rewritten - the feed inventory,
section 15: *"These outputs are part of the experimental data and must remain append-only"*,
and the registry group `append_only_outputs` (`proof_mode: APPEND_ONLY_HASH_CHAIN`,
`activation_stage: SEQUENTIAL_AS_PRODUCED`). This module is the schema and the validator for
that output surface. Staging calls it; it edits nothing staging owns.

**THE REQUIRED SET IS DERIVED AT VALIDATION TIME, AND THERE IS NO FLOOR BELOW IT.** Greg
(DROP_IN_S121, ruling 4): *"don't take any historical number like that as a valid number
that we should follow"*; *"not 10 as the floor. if it's supposed to have 30, the floor is
28. 10 is how 20 get silently dropped."* So the set is:

- every layer id of the loaded registry's `append_only_outputs` group, read from the
  registry object handed in - never typed here;
- one ledger per `### 4.x` heading of the calculation contract, read from the contract TEXT
  handed in (`contract_section_<id>`, including 4.0 and 4.0b); adding a heading adds a
  required ledger with no edit here;
- the mission's section 9a raw-MBO classification (`raw_mbo_classification`); and
- the knowledge-verification record (`knowledge_verification`), one verdict per delivered
  lesson.

A bundle missing any one of them is a refused spawn. No constant in this module names a
count, and `tests/test_native_principal_outputs.py` asserts that by reading the module's
own AST.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    ALLOWED_ARMS,
    SHA256_RE,
    canonical_bytes,
    canonical_hash,
)

APPEND_ONLY_OUTPUTS_GROUP = "append_only_outputs"
SECTION_LEDGER_PREFIX = "contract_section_"
RAW_MBO_CLASSIFICATION_LEDGER = "raw_mbo_classification"
KNOWLEDGE_VERIFICATION_LEDGER = "knowledge_verification"

#: `### 4.0`, `### 4.0b`, `### 4.16` - the section id is the token after the marks.
CONTRACT_SECTION_HEADING_RE = re.compile(r"^### (4\.[0-9]+[a-z]?)\b", re.MULTILINE)


class PrincipalOutputError(ValueError):
    """An output ledger could not be written lawfully, or a bundle could not be trusted."""


def _group(registry: Mapping[str, Any], group_id: str) -> Mapping[str, Any]:
    groups = registry.get("groups") if isinstance(registry, Mapping) else None
    if not isinstance(groups, list):
        raise PrincipalOutputError("registry carries no `groups` list")
    for group in groups:
        if isinstance(group, Mapping) and group.get("group_id") == group_id:
            return group
    raise PrincipalOutputError(f"registry has no {group_id!r} group")


def _layer_ids(registry: Mapping[str, Any], group_id: str) -> tuple[str, ...]:
    entries = _group(registry, group_id).get("entries")
    if not isinstance(entries, list) or not entries:
        raise PrincipalOutputError(f"registry group {group_id!r} has no entries")
    ids = tuple(str(entry["layer_id"]) for entry in entries)
    if len(set(ids)) != len(ids):
        raise PrincipalOutputError(f"registry group {group_id!r} repeats a layer id")
    return ids


def registry_output_layer_ids(registry: Mapping[str, Any]) -> tuple[str, ...]:
    """The output layers of the LOADED registry's `append_only_outputs` group, in order."""
    return _layer_ids(registry, APPEND_ONLY_OUTPUTS_GROUP)


def contract_section_ids(contract_text: str) -> tuple[str, ...]:
    """Every `### 4.x` heading of the calculation contract, in document order.

    Read at validation time so that adding a section to the contract adds a required ledger
    with no edit here. A text with no such heading is not a calculation contract.
    """
    ids = tuple(CONTRACT_SECTION_HEADING_RE.findall(contract_text))
    if not ids:
        raise PrincipalOutputError("contract text carries no `### 4.x` section headings")
    if len(set(ids)) != len(ids):
        raise PrincipalOutputError("contract text repeats a `### 4.x` section heading")
    return ids


def section_ledger_id(section: str) -> str:
    return f"{SECTION_LEDGER_PREFIX}{section}"


def required_ledger_ids(registry: Mapping[str, Any], contract_text: str) -> tuple[str, ...]:
    """Registry outputs + one per contract section + 9a classification + knowledge verification.

    Derived from the two objects handed in. Nothing here knows how many that is.
    """
    return (
        registry_output_layer_ids(registry)
        + tuple(section_ledger_id(section) for section in contract_section_ids(contract_text))
        + (RAW_MBO_CLASSIFICATION_LEDGER, KNOWLEDGE_VERIFICATION_LEDGER)
    )


# --------------------------------------------------------------------------------------
# The append-only ledger
# --------------------------------------------------------------------------------------

OUTPUT_BUNDLE_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_V1"
OUTPUT_RECEIPT_SCHEMA = "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_OUTPUTS_RECEIPT_V1"
#: Feed inventory section 10 (D64): exactly two roles. The same pair `native_staging` allows;
#: declared here rather than imported so staging can import this module without a cycle.
ALLOWED_ROLES = frozenset({"REAL_TIME_FRANKIE", "FORECASTER_FRANKIE"})
RECEIPT_FILENAME = "RECEIPT.json"
LEDGERS_DIRNAME = "ledgers"

GENESIS_PREV_HASH = hashlib.sha256(b"").hexdigest()
"""The first entry of every ledger chains from the hash of nothing - the convention
`native_causal_stream.GENESIS_PREVIOUS_RECEIPT_SHA256` uses for delivery receipts."""

ENTRY_KEYS = frozenset({"ledger_id", "sequence", "cutoff_recv_ns", "body", "prev_hash", "entry_hash"})
LEDGER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")


def entry_hash(prev_hash: str, entry_without_hash: Mapping[str, Any]) -> str:
    """`sha256(prev_hash + canonical(entry))`, the entry canonicalised WITHOUT `entry_hash`."""
    body = {k: v for k, v in entry_without_hash.items() if k != "entry_hash"}
    return hashlib.sha256(prev_hash.encode("ascii") + canonical_bytes(body)).hexdigest()


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise PrincipalOutputError(f"{label} must be a lowercase SHA-256, got {value!r}")
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrincipalOutputError(f"{label} must be a non-empty string")
    return value


class AppendOnlyLedger:
    """One output ledger. `append` is the only write; nothing edits, reorders or removes."""

    def __init__(self, ledger_id: str, *, empty_reason: str | None = None) -> None:
        if not isinstance(ledger_id, str) or LEDGER_ID_RE.fullmatch(ledger_id) is None:
            raise PrincipalOutputError(f"ledger_id {ledger_id!r} is not a plain identifier")
        self.ledger_id = ledger_id
        self.empty_reason = empty_reason
        self._entries: list[dict[str, Any]] = []

    @property
    def entries(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._entries)

    @property
    def head_hash(self) -> str:
        return self._entries[-1]["entry_hash"] if self._entries else GENESIS_PREV_HASH

    def append(self, cutoff_recv_ns: int, body: Mapping[str, Any]) -> dict[str, Any]:
        """Write one entry after the stream has reached `cutoff_recv_ns` (the F_LAST
        `ts_recv_ns` of the last group the entry may lawfully know). Never before."""
        if not _is_int(cutoff_recv_ns) or cutoff_recv_ns < 0:
            raise PrincipalOutputError(
                f"{self.ledger_id}: cutoff_recv_ns must be a non-negative int nanosecond reading, "
                f"got {cutoff_recv_ns!r}"
            )
        if self._entries and cutoff_recv_ns < self._entries[-1]["cutoff_recv_ns"]:
            raise PrincipalOutputError(
                f"{self.ledger_id}: cutoff {cutoff_recv_ns} is earlier than the previous entry's "
                f"{self._entries[-1]['cutoff_recv_ns']}; an output is written after the stream "
                "reaches its cutoff and never before"
            )
        if not isinstance(body, Mapping):
            raise PrincipalOutputError(f"{self.ledger_id}: entry body must be a mapping")
        entry: dict[str, Any] = {
            "ledger_id": self.ledger_id,
            "sequence": len(self._entries),
            "cutoff_recv_ns": cutoff_recv_ns,
            "body": json.loads(canonical_bytes(body)),
            "prev_hash": self.head_hash,
        }
        entry["entry_hash"] = entry_hash(entry["prev_hash"], entry)
        self._entries.append(entry)
        return dict(entry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "empty_reason": self.empty_reason,
            "entries": [dict(e) for e in self._entries],
            "head_hash": self.head_hash,
        }


def verify_chain(ledger_id: str, ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Recompute every hash from genesis; refuse an edit, a reorder, a gap, a regression."""
    if not isinstance(ledger, Mapping) or ledger.get("ledger_id") != ledger_id:
        raise PrincipalOutputError(
            f"ledger filed under {ledger_id!r} declares ledger_id "
            f"{ledger.get('ledger_id') if isinstance(ledger, Mapping) else None!r}"
        )
    reason = ledger.get("empty_reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise PrincipalOutputError(f"{ledger_id}: empty_reason must be null or a non-empty string")
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise PrincipalOutputError(f"{ledger_id}: entries must be a list")
    prev = GENESIS_PREV_HASH
    last_cutoff: int | None = None
    for index, entry in enumerate(entries):
        where = f"{ledger_id}[{index}]"
        if not isinstance(entry, Mapping) or set(entry) != ENTRY_KEYS:
            raise PrincipalOutputError(f"{where}: entry keys must be exactly {sorted(ENTRY_KEYS)}")
        if entry["ledger_id"] != ledger_id:
            raise PrincipalOutputError(f"{where}: entry names ledger {entry['ledger_id']!r}")
        if entry["sequence"] != index:
            raise PrincipalOutputError(
                f"{where}: sequence is {entry['sequence']!r}, expected {index}; the ledger has "
                "a gap or a reorder in its sequence"
            )
        cutoff = entry["cutoff_recv_ns"]
        if not _is_int(cutoff):
            raise PrincipalOutputError(f"{where}: cutoff_recv_ns must be an int")
        if last_cutoff is not None and cutoff < last_cutoff:
            raise PrincipalOutputError(
                f"{where}: cutoff {cutoff} is earlier than the previous entry's {last_cutoff}; "
                "the ledger is out of causal order"
            )
        last_cutoff = cutoff
        if entry["prev_hash"] != prev:
            raise PrincipalOutputError(f"{where}: prev_hash does not chain to the previous entry")
        if not isinstance(entry["body"], Mapping):
            raise PrincipalOutputError(f"{where}: body must be a mapping")
        expected = entry_hash(prev, entry)
        if entry["entry_hash"] != expected:
            raise PrincipalOutputError(
                f"{where}: entry_hash does not match its content; the entry was edited after it "
                "was written, and an output is never rewritten"
            )
        prev = expected
    if ledger.get("head_hash") != prev:
        raise PrincipalOutputError(
            f"{ledger_id}: head_hash {ledger.get('head_hash')!r} disagrees with the chain's head {prev}"
        )
    return entries


# --------------------------------------------------------------------------------------
# The bundle: every ledger of one run, bound to the registry and contract it ran against
# --------------------------------------------------------------------------------------


def contract_sha256_of(contract_text: str) -> str:
    """The contract's identity is the sha256 of its UTF-8 bytes - the committed file's hash."""
    return hashlib.sha256(contract_text.encode("utf-8")).hexdigest()


class OutputBundle:
    """Every ledger a run writes, under one run identity."""

    def __init__(
        self,
        *,
        run_id: str,
        arm: str,
        role: str,
        registry: Mapping[str, Any],
        contract_text: str,
        delivery_receipt_sha256: str | None = None,
        knowledge_receipt_sha256: str | None = None,
    ) -> None:
        if arm not in ALLOWED_ARMS:
            raise PrincipalOutputError(f"unknown arm {arm!r}; expected one of {sorted(ALLOWED_ARMS)}")
        if role not in ALLOWED_ROLES:
            raise PrincipalOutputError(f"unknown role {role!r}; expected one of {sorted(ALLOWED_ROLES)}")
        self.run_id = _require_text(run_id, "run_id")
        self.arm = arm
        self.role = role
        self.registry_sha256 = _require_sha(registry.get("registry_sha256"), "registry.registry_sha256")
        self.contract_sha256 = contract_sha256_of(contract_text)
        self.contract_sections = contract_section_ids(contract_text)
        self.required_ledger_ids = required_ledger_ids(registry, contract_text)
        self.delivery_receipt_sha256 = (
            None if delivery_receipt_sha256 is None
            else _require_sha(delivery_receipt_sha256, "delivery_receipt_sha256")
        )
        self.knowledge_receipt_sha256 = (
            None if knowledge_receipt_sha256 is None
            else _require_sha(knowledge_receipt_sha256, "knowledge_receipt_sha256")
        )
        self._ledgers: dict[str, AppendOnlyLedger] = {}

    def ledger(self, ledger_id: str, *, empty_reason: str | None = None) -> AppendOnlyLedger:
        if ledger_id not in self._ledgers:
            self._ledgers[ledger_id] = AppendOnlyLedger(ledger_id, empty_reason=empty_reason)
        elif empty_reason is not None:
            self._ledgers[ledger_id].empty_reason = empty_reason
        return self._ledgers[ledger_id]

    @property
    def ledgers(self) -> Mapping[str, AppendOnlyLedger]:
        return dict(self._ledgers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OUTPUT_BUNDLE_SCHEMA,
            "run_id": self.run_id,
            "arm": self.arm,
            "role": self.role,
            "registry_sha256": self.registry_sha256,
            "contract_sha256": self.contract_sha256,
            "delivery_receipt_sha256": self.delivery_receipt_sha256,
            "knowledge_receipt_sha256": self.knowledge_receipt_sha256,
            "ledgers": {lid: ledger.to_dict() for lid, ledger in self._ledgers.items()},
        }

    def receipt(self) -> dict[str, Any]:
        return bundle_receipt(self)


def _as_mapping(bundle: OutputBundle | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(bundle, OutputBundle):
        return bundle.to_dict()
    if not isinstance(bundle, Mapping):
        raise PrincipalOutputError("bundle must be an OutputBundle or a mapping")
    return bundle


def bundle_receipt(
    bundle: OutputBundle | Mapping[str, Any],
    required_ledger_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """What was written, per ledger, and what the required set still lacks.

    `ledgers` maps ledger_id -> {entry_count, head_hash}; `missing_ledger_ids` must be empty
    for the bundle to be valid. Other personas duck-type `ledgers` and `receipt_sha256`.
    """
    if required_ledger_ids is None:
        if not isinstance(bundle, OutputBundle):
            raise PrincipalOutputError(
                "a receipt over a plain mapping needs required_ledger_ids stated; derive them with "
                "required_ledger_ids(registry, contract_text)"
            )
        required_ledger_ids = bundle.required_ledger_ids
    body = _as_mapping(bundle)
    ledgers = body.get("ledgers")
    if not isinstance(ledgers, Mapping):
        raise PrincipalOutputError("bundle carries no ledgers mapping")
    per_ledger = {
        lid: {"entry_count": len(ledger["entries"]), "head_hash": ledger["head_hash"]}
        for lid, ledger in ledgers.items()
    }
    receipt: dict[str, Any] = {
        "schema": OUTPUT_RECEIPT_SCHEMA,
        "run_id": body.get("run_id"),
        "arm": body.get("arm"),
        "role": body.get("role"),
        "registry_sha256": body.get("registry_sha256"),
        "contract_sha256": body.get("contract_sha256"),
        "delivery_receipt_sha256": body.get("delivery_receipt_sha256"),
        "knowledge_receipt_sha256": body.get("knowledge_receipt_sha256"),
        "ledgers": per_ledger,
        "required_ledger_ids": list(required_ledger_ids),
        "missing_ledger_ids": [lid for lid in required_ledger_ids if lid not in ledgers],
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = canonical_hash(receipt, omit="receipt_sha256")
    return receipt


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _ledger_path(root: Path, ledger_id: str) -> Path:
    return root / LEDGERS_DIRNAME / f"{ledger_id}.json"


def write_bundle(bundle: OutputBundle, out_dir: Path | str) -> dict[str, Any]:
    """One JSON per ledger under `ledgers/`, plus `RECEIPT.json`. Returns the receipt.

    Written so the principal can call it after every cutoff during his session: a rewrite is
    allowed only when every ledger already on disk is a PREFIX of what is being written and no
    ledger on disk disappears. Anything else is a rewrite of an output, and is refused.
    """
    root = Path(out_dir)
    ledgers_dir = root / LEDGERS_DIRNAME
    ledgers_dir.mkdir(parents=True, exist_ok=True)
    on_disk = {path.stem for path in ledgers_dir.glob("*.json")}
    vanished = sorted(on_disk - set(bundle.ledgers))
    if vanished:
        raise PrincipalOutputError(
            f"ledger(s) {vanished} are on disk and absent from the bundle being written; an output "
            "is never rewritten and never removed"
        )
    for ledger_id, ledger in bundle.ledgers.items():
        path = _ledger_path(root, ledger_id)
        if path.exists():
            existing = verify_chain(ledger_id, json.loads(path.read_text(encoding="utf-8")))
            written = [e["entry_hash"] for e in existing]
            now = [e["entry_hash"] for e in ledger.entries]
            if now[: len(written)] != written:
                raise PrincipalOutputError(
                    f"{ledger_id}: the ledger on disk is not a prefix of the ledger being written; "
                    "an output is never rewritten, only extended"
                )
        path.write_text(_dump(ledger.to_dict()), encoding="utf-8")
    receipt = bundle.receipt()
    (root / RECEIPT_FILENAME).write_text(_dump(receipt), encoding="utf-8")
    return receipt


def load_bundle(out_dir: Path | str) -> dict[str, Any]:
    """Read a written bundle back, re-verifying every chain against the receipt, or refuse."""
    root = Path(out_dir)
    receipt_path = root / RECEIPT_FILENAME
    if not receipt_path.exists():
        raise PrincipalOutputError(f"no {RECEIPT_FILENAME} under {root}; nothing was written here")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, Mapping) or receipt.get("schema") != OUTPUT_RECEIPT_SCHEMA:
        raise PrincipalOutputError(f"{RECEIPT_FILENAME} is not a {OUTPUT_RECEIPT_SCHEMA}")
    if receipt.get("receipt_sha256") != canonical_hash(receipt, omit="receipt_sha256"):
        raise PrincipalOutputError(f"{RECEIPT_FILENAME}: receipt_sha256 does not match its content")
    vouched = receipt.get("ledgers")
    if not isinstance(vouched, Mapping):
        raise PrincipalOutputError(f"{RECEIPT_FILENAME}: carries no ledgers mapping")
    ledgers_dir = root / LEDGERS_DIRNAME
    on_disk = {path.stem for path in ledgers_dir.glob("*.json")} if ledgers_dir.exists() else set()
    unvouched = sorted(on_disk - set(vouched))
    if unvouched:
        raise PrincipalOutputError(f"ledger file(s) {unvouched} are on disk and the receipt does not vouch for them")
    ledgers: dict[str, Any] = {}
    for ledger_id, summary in vouched.items():
        path = _ledger_path(root, ledger_id)
        if not path.exists():
            raise PrincipalOutputError(f"{ledger_id}: the receipt vouches for it and no ledger file exists")
        ledger = json.loads(path.read_text(encoding="utf-8"))
        entries = verify_chain(ledger_id, ledger)
        if len(entries) != summary.get("entry_count") or ledger["head_hash"] != summary.get("head_hash"):
            raise PrincipalOutputError(
                f"{ledger_id}: the file's entry_count/head_hash ({len(entries)}, {ledger['head_hash']}) "
                f"disagree with the receipt's ({summary.get('entry_count')}, {summary.get('head_hash')})"
            )
        ledgers[ledger_id] = ledger
    return {
        "schema": OUTPUT_BUNDLE_SCHEMA,
        "run_id": receipt.get("run_id"),
        "arm": receipt.get("arm"),
        "role": receipt.get("role"),
        "registry_sha256": receipt.get("registry_sha256"),
        "contract_sha256": receipt.get("contract_sha256"),
        "delivery_receipt_sha256": receipt.get("delivery_receipt_sha256"),
        "knowledge_receipt_sha256": receipt.get("knowledge_receipt_sha256"),
        "ledgers": ledgers,
    }
