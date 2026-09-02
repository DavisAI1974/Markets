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


# --------------------------------------------------------------------------------------
# The timing rule: one helper, reused by every ledger
# --------------------------------------------------------------------------------------

CAUSAL_CLOCKS_GROUP = "causal_clocks"
#: The clock every ledger's `cutoff_recv_ns` is on: the F_LAST `ts_recv_ns` the causal stream
#: orders by. Named here as a registry layer id and checked against the registry at validation.
RECEIVE_CLOCK_ID = "clock_receive_time"
TIMING_RULE = (
    "TIMING RULE (Greg, S120; DROP_IN_S121 ruling 5 - no hardcoded windows or horizons): a "
    "timing or clock reading is derived on a named causal clock and written as "
    "{clock, observed_ns}, with clock one of the registry's causal_clocks layer ids and "
    "observed_ns an int; a fixed ladder label such as 'H+60' or '300s', or a bare number, "
    "names no clock and is refused"
)
#: The timing vocabulary the rule names. A key whose last token (after a unit suffix) is one of
#: these carries a timing and must be a clock reading.
TIMING_WORDS = frozenset({"lead", "horizon", "elapsed", "age", "runway"})
UNIT_TOKENS = frozenset({"ns", "us", "ms", "s", "sec", "secs", "seconds"})
#: Verbatim member-row material inside a state frame. The hash-locked adapter's own level fields
#: (`front_order_age_s`, `priority_age_s`) live here, computed at the frame's receive-clock
#: cutoff; D61 wraps that adapter and never renames its fields, so the scan skips exactly these.
MEMBER_ROW_VERBATIM_KEYS = frozenset({"book", "fifo_state"})


def registry_clock_ids(registry: Mapping[str, Any]) -> tuple[str, ...]:
    """The registry's named causal clocks, as layer ids, in registry order."""
    return _layer_ids(registry, CAUSAL_CLOCKS_GROUP)


def clock_reading(value: Any, *, clock_ids: Sequence[str], where: str) -> tuple[str, int]:
    """Validate one `{clock, observed_ns}` reading, or refuse it naming the rule."""
    if not isinstance(value, Mapping) or "clock" not in value or "observed_ns" not in value:
        raise PrincipalOutputError(f"{where}: {value!r} is not a clock reading. {TIMING_RULE}")
    clock = value["clock"]
    if clock not in clock_ids:
        raise PrincipalOutputError(
            f"{where}: clock {clock!r} is not one of the registry's causal clocks {list(clock_ids)}. "
            f"{TIMING_RULE}"
        )
    observed = value["observed_ns"]
    if not _is_int(observed):
        raise PrincipalOutputError(f"{where}: observed_ns {observed!r} is not an int. {TIMING_RULE}")
    return clock, observed


def _is_timing_key(key: str) -> bool:
    tokens = [token for token in key.lower().split("_") if token]
    if tokens and tokens[-1] in UNIT_TOKENS:
        tokens = tokens[:-1]
    return bool(tokens) and tokens[-1] in TIMING_WORDS


def refuse_clockless_timings(value: Any, *, clock_ids: Sequence[str], where: str) -> None:
    """Walk a body; every value under a timing key must be a clock reading (or a list of them,
    or null for an absent timing). Skips the two verbatim member-row subtrees, nothing else."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in MEMBER_ROW_VERBATIM_KEYS:
                continue
            sub = f"{where}.{key}"
            if isinstance(key, str) and _is_timing_key(key):
                if child is None:
                    continue
                for item in child if isinstance(child, list) else [child]:
                    clock_reading(item, clock_ids=clock_ids, where=sub)
            else:
                refuse_clockless_timings(child, clock_ids=clock_ids, where=sub)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            refuse_clockless_timings(child, clock_ids=clock_ids, where=f"{where}[{index}]")


# --------------------------------------------------------------------------------------
# Per-ledger validation: shared helpers and context
# --------------------------------------------------------------------------------------


def _fail(where: str, message: str) -> None:
    raise PrincipalOutputError(f"{where}: {message}")


def _text(body: Mapping[str, Any], key: str, where: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail(where, f"`{key}` must be a non-empty string")
    return value  # type: ignore[return-value]


def _sha(body: Mapping[str, Any], key: str, where: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        _fail(where, f"`{key}` must be a lowercase SHA-256")
    return value  # type: ignore[return-value]


def _int(body: Mapping[str, Any], key: str, where: str) -> int:
    value = body.get(key)
    if not _is_int(value):
        _fail(where, f"`{key}` must be an int")
    return value  # type: ignore[return-value]


def _choice(body: Mapping[str, Any], key: str, allowed: Sequence[str], where: str) -> str:
    value = body.get(key)
    if value not in allowed:
        _fail(where, f"`{key}` must be one of {list(allowed)}, got {value!r}")
    return value  # type: ignore[return-value]


def _list(body: Mapping[str, Any], key: str, where: str) -> list[Any]:
    value = body.get(key)
    if not isinstance(value, list):
        _fail(where, f"`{key}` must be a list")
    return value  # type: ignore[return-value]


def _mapping(body: Mapping[str, Any], key: str, where: str) -> Mapping[str, Any]:
    value = body.get(key)
    if not isinstance(value, Mapping):
        _fail(where, f"`{key}` must be a mapping")
    return value  # type: ignore[return-value]


def _int_list(body: Mapping[str, Any], key: str, where: str) -> list[int]:
    values = _list(body, key, where)
    if any(not _is_int(v) or v < 0 for v in values):
        _fail(where, f"`{key}` must be a list of non-negative int group indices")
    return values


class ValidationContext:
    """What the per-ledger rules may look at across ledgers, plus the registry's clocks."""

    def __init__(self, *, registry: Mapping[str, Any], bundle: Mapping[str, Any]) -> None:
        self.registry = registry
        self.bundle = bundle
        self.clock_ids = registry_clock_ids(registry)
        if RECEIVE_CLOCK_ID not in self.clock_ids:
            raise PrincipalOutputError(
                f"the registry names no {RECEIVE_CLOCK_ID!r} clock, and every ledger cutoff is on it"
            )
        self.knowledge_receipt_sha256: str | None = None
        self.receipt_cutoffs: dict[str, int] = {}
        self.probability_entry_cutoffs: dict[str, int] = {}
        self.first_locks: dict[str, int] = {}
        self.locks = 0
        self.no_locks = 0

    def reading(self, value: Any, where: str) -> tuple[str, int]:
        return clock_reading(value, clock_ids=self.clock_ids, where=where)


# --------------------------------------------------------------------------------------
# The state and state-delta movie
# --------------------------------------------------------------------------------------

STATE_MOVIE = "output_state_and_state_delta_movie"
#: V4 proposal section 3: per channel, missingness distinguishes at minimum these, and a true
#: numerical zero is its own state.
CHANNEL_STATUSES = (
    "OBSERVED",
    "PAST_CARRY",
    "STALE",
    "MISSING",
    "STRUCTURALLY_NOT_YET_KNOWN",
    "NOT_APPLICABLE",
    "TRUE_ZERO",
)
STATUSES_WITHOUT_VALUE = frozenset({"MISSING", "STRUCTURALLY_NOT_YET_KNOWN", "NOT_APPLICABLE"})
CARRIED_STATUSES = frozenset({"PAST_CARRY", "STALE"})
#: The member row's `book` (V4 `book_snapshot`): top of book, the depth levels and full depth.
BOOK_REQUIRED_KEYS = ("best_bid", "best_ask", "spread", "bid_levels", "ask_levels", "bid_depth_full", "ask_depth_full")
LEVEL_REQUIRED_KEYS = ("price_raw", "size", "order_count")
#: The member row's `book_full[...].fifo_queue[...]` identity fields (V4 `_level`).
FIFO_IDENTITY_KEYS = ("order_id", "priority_recv_ns", "priority_sequence", "size", "volume_ahead")
FIFO_STATE_BASIS = (
    "TOUCH_FIFO_IDENTITIES_PLUS_FULL_BOOK_SHA256: the fifo_queue identities at the bid and ask "
    "touch, because queue-position and priority questions read the front of the queue, plus the "
    "sha256 of the complete book_full snapshot with its level and order counts, because that "
    "proves the whole FIFO state at this cutoff without carrying every level in every frame - "
    "the full book_full stays on the member row"
)


def fifo_state_from_book_full(book_full: Mapping[str, Any]) -> dict[str, Any]:
    """Build a frame's `fifo_state` from a member row's `book_full`, both ways at once."""
    bids = book_full.get("bid_levels_full", book_full.get("bid_levels")) or []
    asks = book_full.get("ask_levels_full", book_full.get("ask_levels")) or []

    def touch(levels: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
        if not levels:
            return None
        level = levels[0]
        return {
            "price_raw": level["price_raw"],
            "fifo_queue": [{key: order[key] for key in FIFO_IDENTITY_KEYS} for order in level.get("fifo_queue", [])],
        }

    return {
        "basis": FIFO_STATE_BASIS,
        "book_full_sha256": hashlib.sha256(canonical_bytes(book_full)).hexdigest(),
        "level_count": len(bids) + len(asks),
        "order_count": sum(int(level["order_count"]) for level in list(bids) + list(asks)),
        "touch": {"bid": touch(bids), "ask": touch(asks)},
    }


def _v_book(body: Mapping[str, Any], where: str) -> None:
    book = _mapping(body, "book", where)
    missing = [key for key in BOOK_REQUIRED_KEYS if key not in book]
    if missing:
        _fail(where, f"`book` omits {missing}; the frame carries the book as on the member row")
    for side in ("bid_levels", "ask_levels"):
        levels = _list(book, side, f"{where}.book")
        for index, level in enumerate(levels):
            if not isinstance(level, Mapping) or any(key not in level for key in LEVEL_REQUIRED_KEYS):
                _fail(where, f"`book.{side}[{index}]` must carry {list(LEVEL_REQUIRED_KEYS)} as on the member row")


def _v_fifo_state(body: Mapping[str, Any], where: str) -> None:
    fifo = _mapping(body, "fifo_state", where)
    fw = f"{where}.fifo_state"
    _text(fifo, "basis", fw)
    _sha(fifo, "book_full_sha256", fw)
    _int(fifo, "order_count", fw)
    _int(fifo, "level_count", fw)
    touch = _mapping(fifo, "touch", fw)
    for side in ("bid", "ask"):
        if side not in touch:
            _fail(fw, f"`touch` must state the {side} side (a mapping, or null for an empty side)")
        level = touch[side]
        if level is None:
            continue
        if not isinstance(level, Mapping):
            _fail(fw, f"`touch.{side}` must be a mapping or null")
        _int(level, "price_raw", f"{fw}.touch.{side}")
        for index, order in enumerate(_list(level, "fifo_queue", f"{fw}.touch.{side}")):
            if not isinstance(order, Mapping) or any(key not in order for key in FIFO_IDENTITY_KEYS):
                _fail(fw, f"`touch.{side}.fifo_queue[{index}]` must carry the FIFO identities {list(FIFO_IDENTITY_KEYS)}")


def _v_state_movie(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    previous_cutoff: int | None = None
    for entry in entries:
        where = f"{STATE_MOVIE}[{entry['sequence']}]"
        body, cutoff = entry["body"], entry["cutoff_recv_ns"]
        channels = _mapping(body, "channels", where)
        if not channels:
            _fail(where, "a frame with no channels is not a state")
        missing: list[str] = []
        for name, channel in channels.items():
            cw = f"{where}.channels.{name}"
            if not isinstance(channel, Mapping):
                _fail(cw, "a channel is a mapping with a status")
            status = _choice(channel, "status", CHANNEL_STATUSES, cw)
            if status == "MISSING":
                missing.append(name)
            if status not in STATUSES_WITHOUT_VALUE and "value" not in channel:
                _fail(cw, f"status {status} carries no value")
            if status == "TRUE_ZERO":
                value = channel["value"]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value != 0:
                    _fail(cw, f"TRUE_ZERO is a numerical zero, got {value!r}")
            if status in CARRIED_STATUSES:
                source = _int(channel, "source_recv_ns", cw)
                if source > cutoff:
                    _fail(cw, f"carried source_recv_ns {source} is after the cutoff {cutoff}")
                clock, age = ctx.reading(channel.get("age"), f"{cw}.age")
                if clock == RECEIVE_CLOCK_ID and age != cutoff - source:
                    _fail(cw, f"age {age} on the receive clock must be cutoff - source = {cutoff - source}")
        declared = _list(body, "missing_channels", where)
        if sorted(declared) != sorted(missing):
            _fail(where, f"missing_channels {sorted(declared)} does not name the MISSING channels {sorted(missing)}")
        _v_book(body, where)
        _v_fifo_state(body, where)
        delta = _mapping(body, "delta", where)
        if "previous_cutoff_recv_ns" not in delta or delta["previous_cutoff_recv_ns"] != previous_cutoff:
            _fail(
                f"{where}.delta",
                f"previous_cutoff_recv_ns {delta.get('previous_cutoff_recv_ns')!r} must be the previous "
                f"frame's cutoff {previous_cutoff!r} (null on the first frame)",
            )
        _mapping(delta, "channels", f"{where}.delta")
        _mapping(delta, "book", f"{where}.delta")
        previous_cutoff = cutoff


# --------------------------------------------------------------------------------------
# The reasoning movie: helper invocations are tool calls inside a role, never lanes
# --------------------------------------------------------------------------------------

REASONING_MOVIE = "output_frankie_reasoning_movie"
#: Feed inventory section 10 (D63/D64): a helper has no lane, no CPU affinity, no output
#: artifact of its own and nothing waits on it in parallel.
HELPER_LANE_KEYS = frozenset({"lane", "cpu", "cpu_affinity", "parallel", "output_artifact"})


def _v_reasoning_movie(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    role = ctx.bundle.get("role")
    for entry in entries:
        where = f"{REASONING_MOVIE}[{entry['sequence']}]"
        body, cutoff = entry["body"], entry["cutoff_recv_ns"]
        if body.get("role") != role:
            _fail(where, f"role must be the bundle's role {role!r}, got {body.get('role')!r}")
        _text(body, "reasoning", where)
        for index, record in enumerate(_list(body, "helper_invocations", where)):
            hw = f"{where}.helper_invocations[{index}]"
            if not isinstance(record, Mapping):
                _fail(hw, "a helper invocation is a mapping: persona, question, answer_sha256")
            lane_keys = sorted(HELPER_LANE_KEYS & set(record))
            if lane_keys:
                _fail(
                    hw,
                    f"carries {lane_keys}; a helper is a tool invocation inside a role with a "
                    "selectable persona, never a parallel lane (D63/D64)",
                )
            _text(record, "persona", hw)
            _text(record, "question", hw)
            _sha(record, "answer_sha256", hw)
        for receipt_id in _list(body, "knowledge_retrievals", where):
            if receipt_id not in ctx.receipt_cutoffs:
                _fail(where, f"knowledge retrieval {receipt_id!r} has no receipt in the knowledge-retrieval ledger")
            if ctx.receipt_cutoffs[receipt_id] > cutoff:
                _fail(where, f"knowledge retrieval {receipt_id!r} is receipted after this cutoff")


# --------------------------------------------------------------------------------------
# The probability movie
# --------------------------------------------------------------------------------------

PROBABILITY_MOVIE = "output_probability_movie"
#: V4 proposal section 10: first-lock, no-reliable-lock, no-lock, wrong-lock, late and censored.
LOCK_STATES = ("FIRST_LOCK", "NO_RELIABLE_LOCK", "NO_LOCK", "WRONG_LOCK", "LATE", "CENSORED")
PROBABILITY_SUM_TOLERANCE = 1e-6


def _v_probability_movie(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    for entry in entries:
        where = f"{PROBABILITY_MOVIE}[{entry['sequence']}]"
        body, cutoff = entry["body"], entry["cutoff_recv_ns"]
        for key in ("instance_id", "snapshot_id", "head", "view", "lock_rule_revision"):
            _text(body, key, where)
        _choice(body, "lock_state", LOCK_STATES, where)
        probabilities = _mapping(body, "probabilities", where)
        if not probabilities:
            _fail(where, "probabilities must not be empty")
        total = 0.0
        for label, value in probabilities.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
                _fail(where, f"probability {label!r} = {value!r} is not a number in [0, 1]")
            total += float(value)
        partition = body.get("partition", True)
        if not isinstance(partition, bool):
            _fail(where, "`partition` must be a bool when given")
        if partition:
            if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
                _fail(where, f"probabilities sum to {total}, not 1; a head whose outcomes do not partition says `partition: false` with a reason")
        else:
            _text(body, "not_a_partition_reason", where)
        clock, evaluated = ctx.reading(body.get("evaluation"), f"{where}.evaluation")
        if clock == RECEIVE_CLOCK_ID and evaluated > cutoff:
            _fail(where, f"evaluation {evaluated} is after the cutoff {cutoff} it was written at")
        ctx.probability_entry_cutoffs[entry["entry_hash"]] = cutoff


# --------------------------------------------------------------------------------------
# Candidate discoveries
# --------------------------------------------------------------------------------------

CANDIDATE_DISCOVERIES = "output_candidate_discoveries"
#: Contract section 2: PRIOR (before birth, positive lead), T0 (at birth), H+N (after).
RECOGNITION_LABELS = ("PRIOR", "T0", "H+N")


def _v_recognition(body: Mapping[str, Any], where: str, ctx: ValidationContext) -> None:
    recognition = _mapping(body, "recognition", where)
    rw = f"{where}.recognition"
    label = _choice(recognition, "label", RECOGNITION_LABELS, rw)
    _clock, lead = ctx.reading(recognition.get("lead"), f"{rw}.lead")
    # `lead = reference - observed`, as native_clocks.RecognitionLabel: positive before birth.
    if label == "PRIOR" and lead <= 0:
        _fail(rw, f"a PRIOR recognition precedes its reference; lead {lead} is not positive")
    if label == "T0" and lead != 0:
        _fail(rw, f"a T0 recognition coincides with its reference; lead {lead} is not zero")
    if label == "H+N" and lead >= 0:
        _fail(rw, f"an H+N recognition follows its reference; lead {lead} is not negative")


def _v_candidates(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    for entry in entries:
        where = f"{CANDIDATE_DISCOVERIES}[{entry['sequence']}]"
        body, cutoff = entry["body"], entry["cutoff_recv_ns"]
        _text(body, "candidate_id", where)
        _text(body, "family_id", where)
        if not _int_list(body, "member_group_indices", where):
            _fail(where, "a discovery names the exact member groups beneath it; `member_group_indices` is empty")
        _text(body, "falsifier", where)
        available = _int(body, "first_lawful_availability_ns", where)
        if available > cutoff:
            _fail(where, f"first_lawful_availability_ns {available} is after the cutoff {cutoff}; not lawfully known when written")
        _v_recognition(body, where, ctx)


# --------------------------------------------------------------------------------------
# First locks and no-locks
# --------------------------------------------------------------------------------------

FIRST_LOCKS = "output_first_locks_and_no_locks"
LOCK_LEDGER_STATES = ("FIRST_LOCK", "NO_LOCK", "NO_RELIABLE_LOCK")


def _v_locks(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    for entry in entries:
        where = f"{FIRST_LOCKS}[{entry['sequence']}]"
        body, cutoff = entry["body"], entry["cutoff_recv_ns"]
        candidate = _text(body, "candidate_id", where)
        state = _choice(body, "lock_state", LOCK_LEDGER_STATES, where)
        _text(body, "lock_rule_revision", where)
        if state == "FIRST_LOCK":
            if candidate in ctx.first_locks:
                _fail(where, f"candidate {candidate!r} already holds a FIRST_LOCK at cutoff {ctx.first_locks[candidate]}; a later call cannot replace an earlier exact signal")
            reference = _sha(body, "probability_entry_hash", where)
            if reference not in ctx.probability_entry_cutoffs:
                _fail(where, "probability_entry_hash names no entry of the probability movie")
            if ctx.probability_entry_cutoffs[reference] > cutoff:
                _fail(where, "the referenced probability entry was written after this lock")
            clock, locked_at = ctx.reading(body.get("lock_at"), f"{where}.lock_at")
            if clock == RECEIVE_CLOCK_ID and locked_at != cutoff:
                _fail(where, f"lock_at {locked_at} is not the cutoff {cutoff} it was written at; a lock is stamped when it is called and never moved earlier")
            ctx.first_locks[candidate] = cutoff
            ctx.locks += 1
        else:
            _text(body, "reason", where)
            if candidate in ctx.first_locks:
                _fail(where, f"candidate {candidate!r} is already first-locked; a lock is never withdrawn")
            ctx.no_locks += 1


# --------------------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------------------

LEDGER_RULES: dict[str, Any] = {
    STATE_MOVIE: _v_state_movie,
    REASONING_MOVIE: _v_reasoning_movie,
    PROBABILITY_MOVIE: _v_probability_movie,
    CANDIDATE_DISCOVERIES: _v_candidates,
    FIRST_LOCKS: _v_locks,
}


def _rule_for(ledger_id: str) -> Any:
    return LEDGER_RULES.get(ledger_id)


def validate_ledger_entries(
    ledger_id: str, entries: Sequence[Mapping[str, Any]], ctx: ValidationContext
) -> None:
    """The timing rule over every entry of every ledger, then the ledger's own rule if any.

    A ledger with no rule of its own (a registry output layer added after this module) still
    gets its chain verified and the timing rule applied; nothing is dropped for lacking a rule.
    """
    for entry in entries:
        refuse_clockless_timings(entry["body"], clock_ids=ctx.clock_ids, where=f"{ledger_id}[{entry['sequence']}]")
    rule = _rule_for(ledger_id)
    if rule is not None:
        rule(entries, ctx)
