"""The principal's OUTPUT ledgers: the required set is derived above a protected baseline.

Frankie receives every record of every field for the day as a causal stream in `ts_recv_ns`
order and computes every calculation-contract section himself (D81). What he writes is
produced sequentially as the stream advances and is never rewritten - the feed inventory,
section 15: *"These outputs are part of the experimental data and must remain append-only"*,
and the registry group `append_only_outputs` (`proof_mode: APPEND_ONLY_HASH_CHAIN`,
`activation_stage: SEQUENTIAL_AS_PRODUCED`). This module is the schema and the validator for
that output surface. Staging calls it; it edits nothing staging owns.

**THE REQUIRED SET IS DERIVED AT VALIDATION TIME, WITH THE CURRENT EIGHTEEN AS ITS FLOOR.**
The protected baseline is the actual section identities 4.0, 4.0b and 4.1 through 4.16,
not a scalar count that a replacement heading could satisfy. Every later `### 4.x` heading
automatically grows the required set. So the set is:

- every layer id of the loaded registry's `append_only_outputs` group, read from the
  registry object handed in - never typed here;
- one ledger per `### 4.x` heading of the calculation contract, read from the contract TEXT
  handed in (`contract_section_<id>`, including the protected baseline); adding a heading
  adds a required ledger with no edit here, while deleting a baseline heading is refused;
- the mission's section 9a raw-MBO classification (`raw_mbo_classification`); and
- the knowledge-verification record (`knowledge_verification`), one verdict per delivered
  lesson.

A bundle missing any one of them is a refused spawn. The floor is expressed as section
identities, not an integer count, so deleting 4.0b and adding 4.17 cannot silently pass.

**THE SHAPE.** Every ledger is an `AppendOnlyLedger`: entries carry a monotone `sequence`, a
nondecreasing `cutoff_recv_ns` (the F_LAST `ts_recv_ns` after which the entry was written -
contract section 2: the first lawful knowledge time for a completed group is its F_LAST
receive time), a `body`, and a hash chain `entry_hash = sha256(prev_hash + canonical(entry))`
from `sha256(b"")`, the convention `native_causal_stream` uses for delivery receipts. An
edited entry breaks its own hash, a reordered one breaks its sequence, a moved one breaks the
cutoff order. An `OutputBundle` holds one run's ledgers bound to `registry_sha256` and
`contract_sha256`; `write_bundle` puts one JSON per ledger beside `RECEIPT.json` and refuses
any rewrite that is not a pure extension; `load_bundle` re-verifies every chain against the
receipt. `validate_output_bundle` derives the required set, refuses any missing ledger by
name, verifies every chain, applies the per-ledger rules and the cross-ledger ones, and
returns the receipt; `validate_output_bundle_dir` is the form staging calls.

**THE RULES THE LEDGERS ENFORCE**, each from a ruling in `DROP_IN_S121.md` item zero:
timings are derived on the registry's named causal clocks and written as `{clock,
observed_ns}` - a fixed ladder label names no clock and is refused (ruling 5, one helper,
`clock_reading`); the state movie carries the book and the FIFO state and the delta per
cutoff (ruling 3); a helper invocation is a tool call inside a role with a persona and is
refused if it carries lane, cpu, parallel or output-artifact keys (ruling 6, D63/D64); the
outputs are append-only experimental data (feed inventory 15); the principal runs as an
AGENT SESSION, so API-shaped invocation receipts are refused (D70); no body names a desktop
or session-local path (D34); and the 9a classification advises and never drops - a bundle
where every field is LOAD_BEARING is valid (D60, D76).

Run `python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_principal_outputs validate
--dir <outputs dir>` to print the receipt or `REFUSED: <why>`. `--arm` defaults to
`CANONICAL_ARM` (A_MEMORY - the one arm, D86; equivalent to `--arm A_MEMORY` spelled out);
A_CLEAN is accepted only as the inert record it is, and a bundle for another arm is refused
by name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    ALLOWED_ARMS,
    REGISTRY_PATH,
    SHA256_RE,
    canonical_bytes,
    canonical_hash,
    load_registry,
)

#: THE ONE ARM (D86; Greg, S122: "we aren't running clean anymore only memory"). Every
#: default, example and fixture names it; nothing is built, defaulted or exemplified for
#: A_CLEAN, which stays in `ALLOWED_ARMS` as an inert record until its removal is discussed
#: (D60, F-28). Staging re-exports this so the two modules cannot drift.
CANONICAL_ARM = "A_MEMORY"
assert CANONICAL_ARM in ALLOWED_ARMS

APPEND_ONLY_OUTPUTS_GROUP = "append_only_outputs"
SECTION_LEDGER_PREFIX = "contract_section_"
RAW_MBO_CLASSIFICATION_LEDGER = "raw_mbo_classification"
KNOWLEDGE_VERIFICATION_LEDGER = "knowledge_verification"

#: `### 4.0`, `### 4.0b`, `### 4.16` - the section id is the token after the marks.
CONTRACT_SECTION_HEADING_RE = re.compile(r"^### (4\.[0-9]+[a-z]?)\b", re.MULTILINE)
#: Greg, S124: eighteen is the floor. Identities enforce the real baseline; a bare count
#: would let deleting 4.0b and adding 4.17 pass. Extra headings remain automatically required.
MINIMUM_CONTRACT_SECTION_IDS = (
    "4.0", "4.0b", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7",
    "4.8", "4.9", "4.10", "4.11", "4.12", "4.13", "4.14", "4.15", "4.16",
)


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
    missing_baseline = [section for section in MINIMUM_CONTRACT_SECTION_IDS if section not in ids]
    if missing_baseline:
        raise PrincipalOutputError(
            f"calculation contract is below the protected baseline; missing {missing_baseline}"
        )
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
# Abstentions, weak findings, negatives, sparse and inconclusive cases
# --------------------------------------------------------------------------------------

NEGATIVE_LEDGER = "output_negative_sparse_inconclusive_ledger"
#: Feed inventory section 15's own wording of what this ledger holds.
NEGATIVE_KINDS = ("ABSTENTION", "WEAK", "NEGATIVE", "SPARSE", "INCONCLUSIVE")


def _v_negative(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    for entry in entries:
        where = f"{NEGATIVE_LEDGER}[{entry['sequence']}]"
        body = entry["body"]
        _choice(body, "kind", NEGATIVE_KINDS, where)
        _mapping(body, "stratum", where)
        numerator = _int(body, "numerator", where)
        denominator = _int(body, "denominator", where)
        if numerator < 0 or denominator < 0 or numerator > denominator:
            _fail(where, f"numerator {numerator} / denominator {denominator} is not a population count")
        _text(body, "statement", where)


# --------------------------------------------------------------------------------------
# Knowledge retrieval receipts
# --------------------------------------------------------------------------------------

KNOWLEDGE_RECEIPTS = "output_knowledge_retrieval_receipts"
#: The dispositions `native_frankie_knowledge_registry.bind_principal_knowledge_use` accepts.
RETRIEVAL_DISPOSITIONS = ("INSPECTED", "UNINSPECTED")


def _v_knowledge_receipts(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    for entry in entries:
        where = f"{KNOWLEDGE_RECEIPTS}[{entry['sequence']}]"
        body, cutoff = entry["body"], entry["cutoff_recv_ns"]
        receipt_id = _text(body, "receipt_id", where)
        if receipt_id in ctx.receipt_cutoffs:
            _fail(where, f"receipt_id {receipt_id!r} repeats")
        _text(body, "layer_id", where)
        _sha(body, "sha256", where)
        _choice(body, "disposition", RETRIEVAL_DISPOSITIONS, where)
        ctx.receipt_cutoffs[receipt_id] = cutoff


# --------------------------------------------------------------------------------------
# Provider invocation and response receipts: an agent session, never an API
# --------------------------------------------------------------------------------------

INVOCATION_RECEIPTS = "output_provider_invocation_response_receipts"
INVOCATION_MECHANISM = "AGENT_SESSION"
#: Mission section 10 (D70): the fields an API gate demanded and a session run cannot supply.
API_SHAPED_KEYS = frozenset(
    {
        "provider",
        "requested_model",
        "served_model",
        "principal_invocation_id",
        "usage",
        "input_tokens",
        "output_tokens",
        "api_key",
        "endpoint",
        "http_status",
    }
)


def _v_invocations(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    for entry in entries:
        where = f"{INVOCATION_RECEIPTS}[{entry['sequence']}]"
        body = entry["body"]
        api_keys = sorted(API_SHAPED_KEYS & set(body))
        if api_keys:
            _fail(
                where,
                f"receipt carries API-shaped fields {api_keys}; the principal runs as an AGENT "
                "SESSION over committed files and no provider API is called (mission section 10, "
                "D70) - a gate demanding these would reject a correct session run",
            )
        if body.get("mechanism") != INVOCATION_MECHANISM:
            _fail(where, f"mechanism must be {INVOCATION_MECHANISM!r}, got {body.get('mechanism')!r}")
        _text(body, "session_id", where)
        _text(body, "model_identity_as_reported_by_session", where)
        request = _sha(body, "request_sha256", where)
        response = _sha(body, "response_sha256", where)
        if request == response:
            _fail(where, "request and response hash identically; a run that returned its own input produced no findings")


# --------------------------------------------------------------------------------------
# Answer-wall access receipts: empty, or the run is invalid
# --------------------------------------------------------------------------------------

ANSWER_WALL_RECEIPTS = "output_answer_wall_access_receipts"


def _v_answer_wall(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    if entries:
        _fail(
            ANSWER_WALL_RECEIPTS,
            f"{len(entries)} answer-wall access receipt(s) present; any access to the answer wall "
            "invalidates the run - a valid run's ledger is EMPTY with its reason stated",
        )


# --------------------------------------------------------------------------------------
# Source, state, manifest, code and run hashes: START and END
# --------------------------------------------------------------------------------------

RUN_HASHES = "output_source_state_manifest_code_model_run_hashes"
HASH_PHASES = ("START", "END")
RUN_HASH_KEYS = (
    "mission_sha256",
    "contract_sha256",
    "knowledge_manifest_sha256",
    "source_manifest_sha256",
    "code_sha256",
    "state_sha256",
)
#: Only the state may move during a run.
RUN_HASH_INVARIANT_KEYS = tuple(key for key in RUN_HASH_KEYS if key != "state_sha256")


def _v_run_hashes(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    phases = [entry["body"].get("phase") for entry in entries]
    if phases != list(HASH_PHASES):
        _fail(RUN_HASHES, f"written exactly twice, START then END; got phases {phases}")
    for entry in entries:
        where = f"{RUN_HASHES}[{entry['sequence']}]"
        body = entry["body"]
        for key in RUN_HASH_KEYS:
            _sha(body, key, where)
        if body.get("run_id") != ctx.bundle.get("run_id"):
            _fail(where, f"run_id {body.get('run_id')!r} is not the bundle's {ctx.bundle.get('run_id')!r}")
        if body["contract_sha256"] != ctx.bundle.get("contract_sha256"):
            _fail(where, "contract_sha256 is not the contract this bundle is bound to")
        if "model_identity" in body:
            _text(body, "model_identity", where)
    start, end = entries[0]["body"], entries[1]["body"]
    for key in RUN_HASH_INVARIANT_KEYS + ("model_identity",):
        if start.get(key) != end.get(key):
            _fail(f"{RUN_HASHES}[1]", f"{key} changed between START and END; only the state may move during a run")


# --------------------------------------------------------------------------------------
# One ledger per calculation-contract section
# --------------------------------------------------------------------------------------

NULL_RESULT = "NULL_RESULT"
#: Contract section 3: resolved, censored, or still-open.
STRATUM_STATUSES = ("RESOLVED", "CENSORED", "OPEN")
#: Contract section 3's nine declarations every average must carry, as keys: (1) numerator and
#: formula; (2) population and denominator; (3) source day and role; (4) family, subfamily and
#: cluster version; (5) side or mirror orientation; (6) session, phase and continuity segment;
#: (7) causal clock and cutoff; (8) status; (9) missingness and inclusion rules.
STRATUM_REQUIRED_KEYS = (
    "numerator",
    "formula",
    "population",
    "denominator",
    "source_day",
    "source_role",
    "family",
    "subfamily",
    "cluster_version",
    "side_or_mirror_orientation",
    "session",
    "phase",
    "continuity_segment",
    "causal_clock",
    "cutoff_recv_ns",
    "status",
    "missingness_rule",
    "inclusion_rule",
)


def _v_average(average: Any, cutoff: int, where: str, ctx: ValidationContext) -> None:
    if not isinstance(average, Mapping):
        _fail(where, "an average is a mapping: value and strata")
    value = average.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(where, f"`value` must be a number, got {value!r}")
    strata = _mapping(average, "strata", where)
    missing = [key for key in STRATUM_REQUIRED_KEYS if key not in strata]
    if missing:
        _fail(where, f"strata omit {missing}; no average is quoted without its nine declarations (contract section 3, mission section 7)")
    _choice(strata, "status", STRATUM_STATUSES, where)
    if strata["causal_clock"] not in ctx.clock_ids:
        _fail(where, f"causal_clock {strata['causal_clock']!r} is not one of the registry's causal clocks {list(ctx.clock_ids)}")
    if strata["cutoff_recv_ns"] != cutoff:
        _fail(where, f"strata cutoff_recv_ns {strata['cutoff_recv_ns']!r} must be this entry's cutoff {cutoff}")
    if _int(strata, "denominator", where) < 0:
        _fail(where, "denominator must be non-negative")


def _section_rule(section: str) -> Any:
    ledger_id = section_ledger_id(section)

    def validate(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
        for entry in entries:
            where = f"{ledger_id}[{entry['sequence']}]"
            body, cutoff = entry["body"], entry["cutoff_recv_ns"]
            if body.get("section") != section:
                _fail(where, f"section must be {section!r}, got {body.get('section')!r}")
            members = _int_list(body, "member_group_indices", where)
            if not members:
                if body.get("result") != NULL_RESULT:
                    _fail(where, f"an entry rests on exact member groups (`member_group_indices` is empty) or states result {NULL_RESULT!r} with its population; absence is a result, silence is not")
                population = _mapping(body, "population", where)
                _int(population, "denominator", f"{where}.population")
                _text(population, "description", f"{where}.population")
            averages = body.get("averages", [])
            if not isinstance(averages, list):
                _fail(where, "`averages` must be a list when given")
            for index, average in enumerate(averages):
                _v_average(average, cutoff, f"{where}.averages[{index}]", ctx)

    return validate


# --------------------------------------------------------------------------------------
# Mission section 9a: the raw-MBO retention judgement
# --------------------------------------------------------------------------------------

RAW_MBO_CLASSES = (
    "LOAD_BEARING",
    "RETAINED_UNREAD",
    "DEGENERATE_ON_THIS_SLICE",
    "REDUNDANT",
    "CANNOT_JUDGE",
)
#: Mission 9a: RETAINED_UNREAD says whether that is a wiring defect or a genuine spare.
RETAINED_UNREAD_CAUSES = ("WIRING_DEFECT", "GENUINE_SPARE")
DROP_WORDS = frozenset({"DROP", "DROPPED", "REMOVE", "REMOVED", "DELETE", "DELETED"})


def _v_raw_mbo(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    for entry in entries:
        where = f"{RAW_MBO_CLASSIFICATION_LEDGER}[{entry['sequence']}]"
        body = entry["body"]
        _text(body, "field_or_group", where)
        classification = _choice(body, "classification", RAW_MBO_CLASSES, where)
        _text(body, "evidence", where)
        action = body.get("action")
        if isinstance(action, str) and action.strip().upper() in DROP_WORDS:
            _fail(where, "an output advises and never drops; removal is Greg's decision after discussion (mission 9a, D60)")
        if classification == "LOAD_BEARING":
            if not _list(body, "read_by_sections", where):
                _fail(where, "LOAD_BEARING names the section(s) whose reading changes conclusions")
        elif classification == "RETAINED_UNREAD":
            _choice(body, "cause", RETAINED_UNREAD_CAUSES, where)
        elif classification == "DEGENERATE_ON_THIS_SLICE":
            if "single_value" not in body or not isinstance(body.get("expected_on_other_days"), bool):
                _fail(where, "DEGENERATE_ON_THIS_SLICE states the single value and whether it is expected to hold on other days")
        elif classification == "REDUNDANT":
            _text(body, "derivation", where)
        else:
            _text(body, "reason", where)


# --------------------------------------------------------------------------------------
# Knowledge verification: one verdict per delivered lesson
# --------------------------------------------------------------------------------------

KNOWLEDGE_VERDICTS = ("VERIFIED", "UNVERIFIED", "REFUTED")


def _v_knowledge_verification(entries: Sequence[Mapping[str, Any]], ctx: ValidationContext) -> None:
    for entry in entries:
        where = f"{KNOWLEDGE_VERIFICATION_LEDGER}[{entry['sequence']}]"
        body, cutoff = entry["body"], entry["cutoff_recv_ns"]
        _text(body, "lesson_id", where)
        _text(body, "layer_id", where)
        cited = _sha(body, "knowledge_receipt_sha256", where)
        if ctx.knowledge_receipt_sha256 is not None and cited != ctx.knowledge_receipt_sha256:
            _fail(where, f"knowledge_receipt_sha256 {cited} does not cite the knowledge-delivery receipt {ctx.knowledge_receipt_sha256} this run was validated against")
        verdict = _choice(body, "verdict", KNOWLEDGE_VERDICTS, where)
        if verdict == "UNVERIFIED":
            _text(body, "reason", where)
            continue
        evidence = _mapping(body, "evidence", where)
        ew = f"{where}.evidence"
        if not _int_list(evidence, "member_group_indices", ew):
            _fail(ew, "a verdict rests on exact member groups; `member_group_indices` is empty")
        evidence_cutoff = _int(evidence, "cutoff_recv_ns", ew)
        if evidence_cutoff > cutoff:
            _fail(ew, f"evidence cutoff {evidence_cutoff} is after the entry's cutoff {cutoff}")


# --------------------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------------------

LEDGER_RULES: dict[str, Any] = {
    STATE_MOVIE: _v_state_movie,
    REASONING_MOVIE: _v_reasoning_movie,
    PROBABILITY_MOVIE: _v_probability_movie,
    CANDIDATE_DISCOVERIES: _v_candidates,
    FIRST_LOCKS: _v_locks,
    NEGATIVE_LEDGER: _v_negative,
    KNOWLEDGE_RECEIPTS: _v_knowledge_receipts,
    INVOCATION_RECEIPTS: _v_invocations,
    ANSWER_WALL_RECEIPTS: _v_answer_wall,
    RUN_HASHES: _v_run_hashes,
    RAW_MBO_CLASSIFICATION_LEDGER: _v_raw_mbo,
    KNOWLEDGE_VERIFICATION_LEDGER: _v_knowledge_verification,
}


def _rule_for(ledger_id: str) -> Any:
    if ledger_id in LEDGER_RULES:
        return LEDGER_RULES[ledger_id]
    if ledger_id.startswith(SECTION_LEDGER_PREFIX):
        return _section_rule(ledger_id[len(SECTION_LEDGER_PREFIX):])
    return None


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


# --------------------------------------------------------------------------------------
# D34: no artifact names a desktop or session-local path
# --------------------------------------------------------------------------------------

D34_RULE = (
    "D34 (Greg, S112): there is nothing local - no artifact may name a desktop or "
    "session-local path; write it repo-relative"
)
#: A drive-letter path, an absolute home/user/root/temp path, or a tilde path. Case matters:
#: `Users` is the desktop spelling; a repo-relative `research/home/...` is not matched.
DESKTOP_PATH_RE = re.compile(
    r"(?:(?<![A-Za-z0-9_])[A-Za-z]:[\\/]|(?<![\w./-])/(?:home|Users|root|tmp)/|(?<![\w])~/)"
)


def refuse_desktop_paths(value: Any, *, where: str) -> None:
    if isinstance(value, str):
        if DESKTOP_PATH_RE.search(value):
            raise PrincipalOutputError(f"{where}: {value!r} names a desktop or session-local path. {D34_RULE}")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            refuse_desktop_paths(child, where=f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            refuse_desktop_paths(child, where=f"{where}[{index}]")


# --------------------------------------------------------------------------------------
# The whole bundle
# --------------------------------------------------------------------------------------

CONTRACT_PATH = REGISTRY_PATH.parent / "frankie_native_raw_mbo_calculation_contract_20260828.md"

#: A valid run always writes into these. Every contract-section ledger is one too - absence
#: there is a NULL_RESULT entry, never an empty ledger - and knowledge_verification is one
#: whenever a knowledge-delivery receipt is known, because delivered lessons exist to verify.
MUST_HAVE_ENTRIES = frozenset(
    {STATE_MOVIE, REASONING_MOVIE, INVOCATION_RECEIPTS, RUN_HASHES, RAW_MBO_CLASSIFICATION_LEDGER}
)
#: Cross-ledger references fix this much of the order: receipts before the movie that cites
#: them, probabilities before the locks that bind them. Everything else follows in bundle order.
VALIDATE_FIRST = (KNOWLEDGE_RECEIPTS, PROBABILITY_MOVIE)


def _must_have_entries(ledger_id: str, knowledge_receipt_sha256: str | None) -> bool:
    if ledger_id in MUST_HAVE_ENTRIES or ledger_id.startswith(SECTION_LEDGER_PREFIX):
        return True
    return ledger_id == KNOWLEDGE_VERIFICATION_LEDGER and knowledge_receipt_sha256 is not None


def validate_output_bundle(
    bundle: OutputBundle | Mapping[str, Any],
    *,
    registry: Mapping[str, Any],
    contract_text: str,
    knowledge_receipt_sha256: str | None = None,
    delivery_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    """Every required ledger present, every chain intact, every rule met - or refuse.

    The required set is derived here from `registry` and `contract_text`; a bundle missing
    any one ledger is refused naming every missing id. When `knowledge_receipt_sha256` is
    given every knowledge-verification verdict must cite it; when `delivery_receipt_sha256`
    is given the bundle must cite it, because the outputs were produced against that delivery.
    Returns the bundle receipt (its `missing_ledger_ids` is empty by construction).
    """
    body = _as_mapping(bundle)
    if body.get("schema") != OUTPUT_BUNDLE_SCHEMA:
        raise PrincipalOutputError(f"bundle schema is {body.get('schema')!r}, expected {OUTPUT_BUNDLE_SCHEMA!r}")
    if body.get("arm") not in ALLOWED_ARMS or body.get("role") not in ALLOWED_ROLES:
        raise PrincipalOutputError("bundle names an unknown arm or role")
    _require_text(body.get("run_id"), "bundle run_id")
    declared_registry = _require_sha(registry.get("registry_sha256"), "registry.registry_sha256")
    if body.get("registry_sha256") != declared_registry:
        raise PrincipalOutputError(
            f"bundle was written against registry {body.get('registry_sha256')!r}, not the registry "
            f"{declared_registry} it is validated against"
        )
    expected_contract = contract_sha256_of(contract_text)
    if body.get("contract_sha256") != expected_contract:
        raise PrincipalOutputError(
            f"bundle was written against calculation contract {body.get('contract_sha256')!r}, not the "
            f"contract {expected_contract} it is validated against"
        )
    if delivery_receipt_sha256 is not None:
        _require_sha(delivery_receipt_sha256, "delivery_receipt_sha256")
        if body.get("delivery_receipt_sha256") != delivery_receipt_sha256:
            raise PrincipalOutputError(
                f"the run delivered its ledgers under delivery receipt {delivery_receipt_sha256} and the "
                f"bundle cites {body.get('delivery_receipt_sha256')!r}; outputs are produced against the "
                "delivery they were given"
            )
    if knowledge_receipt_sha256 is not None:
        _require_sha(knowledge_receipt_sha256, "knowledge_receipt_sha256")
        cited = body.get("knowledge_receipt_sha256")
        if cited is not None and cited != knowledge_receipt_sha256:
            raise PrincipalOutputError(
                f"bundle cites knowledge-delivery receipt {cited}, not the run's {knowledge_receipt_sha256}"
            )

    required = required_ledger_ids(registry, contract_text)
    ledgers = body.get("ledgers")
    if not isinstance(ledgers, Mapping):
        raise PrincipalOutputError("bundle carries no ledgers mapping")
    missing = [lid for lid in required if lid not in ledgers]
    if missing:
        raise PrincipalOutputError(
            f"{len(missing)} of {len(required)} required output ledger(s) absent: {missing}; a bundle "
            "missing any one required ledger is a refused spawn - there is no floor below the full "
            "count (DROP_IN_S121 ruling 4)"
        )

    ctx = ValidationContext(registry=registry, bundle=body)
    ctx.knowledge_receipt_sha256 = knowledge_receipt_sha256
    entries_by: dict[str, list[Mapping[str, Any]]] = {}
    for ledger_id, ledger in ledgers.items():
        entries = verify_chain(ledger_id, ledger)
        reason = ledger.get("empty_reason")
        if not entries:
            if _must_have_entries(ledger_id, knowledge_receipt_sha256):
                raise PrincipalOutputError(
                    f"{ledger_id}: no entries; a valid run always writes into this ledger"
                    + (" (absence is a NULL_RESULT entry, never an empty ledger)" if ledger_id.startswith(SECTION_LEDGER_PREFIX) else "")
                )
            if reason is None:
                raise PrincipalOutputError(f"{ledger_id}: empty without a stated empty_reason")
        elif reason is not None:
            raise PrincipalOutputError(f"{ledger_id}: carries {len(entries)} entries and an empty_reason")
        for entry in entries:
            refuse_desktop_paths(entry["body"], where=f"{ledger_id}[{entry['sequence']}]")
        entries_by[ledger_id] = entries

    order = [*VALIDATE_FIRST, *(lid for lid in ledgers if lid not in VALIDATE_FIRST)]
    for ledger_id in order:
        if ledger_id in entries_by:
            validate_ledger_entries(ledger_id, entries_by[ledger_id], ctx)

    all_cutoffs = {entry["cutoff_recv_ns"] for entries in entries_by.values() for entry in entries}
    turns = {entry["cutoff_recv_ns"] for entry in entries_by[INVOCATION_RECEIPTS]}
    uncovered = sorted(all_cutoffs - turns)
    if uncovered:
        raise PrincipalOutputError(
            f"{INVOCATION_RECEIPTS}: no session turn receipt at cutoff(s) {uncovered}, yet outputs were "
            "written there; every cutoff that produced an output was a turn"
        )
    hashes = entries_by[RUN_HASHES]
    if hashes[0]["cutoff_recv_ns"] > min(all_cutoffs) or hashes[-1]["cutoff_recv_ns"] < max(all_cutoffs):
        raise PrincipalOutputError(
            f"{RUN_HASHES}: START must be at or before the first output cutoff and END at or after the last"
        )
    return bundle_receipt(body, required_ledger_ids=required)


def validate_output_bundle_dir(
    out_dir: Path | str,
    *,
    registry: Mapping[str, Any],
    contract_text: str,
    knowledge_receipt_sha256: str | None = None,
    delivery_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    """The staging form: load what the principal wrote, re-verifying every chain, then validate."""
    return validate_output_bundle(
        load_bundle(out_dir),
        registry=registry,
        contract_text=contract_text,
        knowledge_receipt_sha256=knowledge_receipt_sha256,
        delivery_receipt_sha256=delivery_receipt_sha256,
    )


def ledger_entries(bundle: OutputBundle | Mapping[str, Any], ledger_id: str) -> list[Mapping[str, Any]]:
    """The chain-verified entries of one ledger of a bundle, in sequence order.

    For staging's handoff builder (S121 slice 4), which reads a ledger's head entry and the
    candidate roster off a VALIDATED bundle. A ledger the bundle does not carry is refused by
    name rather than read as empty: absence and emptiness are different facts.
    """
    body = _as_mapping(bundle)
    ledgers = body.get("ledgers")
    if not isinstance(ledgers, Mapping) or ledger_id not in ledgers:
        raise PrincipalOutputError(f"bundle carries no ledger {ledger_id!r}")
    return verify_chain(ledger_id, ledgers[ledger_id])


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m research.kalshi.frankie_raw_mbo_benchmark.native_principal_outputs",
        description="Validate a principal output bundle: print its receipt, or REFUSED and why.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate a written bundle directory")
    validate.add_argument("--dir", required=True, help="directory holding ledgers/ and RECEIPT.json")
    validate.add_argument(
        "--arm", default=CANONICAL_ARM, choices=sorted(ALLOWED_ARMS),
        help=f"the arm the bundle must belong to (default {CANONICAL_ARM}, the one arm - D86; "
             "A_CLEAN is accepted only as an inert record)",
    )
    validate.add_argument("--registry", default=str(REGISTRY_PATH), help="ingestion-layer registry JSON")
    validate.add_argument("--contract", default=str(CONTRACT_PATH), help="calculation contract markdown")
    validate.add_argument("--knowledge-receipt-sha256", default=None, help="the knowledge-delivery receipt every verdict must cite")
    validate.add_argument("--delivery-receipt-sha256", default=None, help="the ledger-delivery receipt the bundle must cite")
    args = parser.parse_args(argv)
    try:
        registry = load_registry(Path(args.registry))
        contract_text = Path(args.contract).read_text(encoding="utf-8")
        bundle = load_bundle(args.dir)
        if bundle.get("arm") != args.arm:
            raise PrincipalOutputError(f"bundle arm {bundle.get('arm')!r} is not the requested arm {args.arm!r}")
        receipt = validate_output_bundle(
            bundle,
            registry=registry,
            contract_text=contract_text,
            knowledge_receipt_sha256=args.knowledge_receipt_sha256,
            delivery_receipt_sha256=args.delivery_receipt_sha256,
        )
    except (PrincipalOutputError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
