"""Append-only on-disk retention for the exact ledgers. Nothing is dropped; it moves.

**Why this exists.** The exact member ledger, the lifecycle ledger and the D60 legacy rows
were held in RAM for the whole run and written out only at the end. Measured on the launch
path: peak RSS grows linearly at ~18-22 MiB per thousand F_LAST groups, which extrapolates to
**79-93 GiB over the roster's 4,256,603 groups** - against a box with 61.8 GiB. The rows are
48%, 29% and 23% of that.

**This is not a D60 drop and the distinction is the whole point.** Greg's rule is that a row
reaching our code is USED, or RETAINED and counted, or REFUSED loudly - and *"i don't care
about memory. restore every piece... he has to see everything."* Every row is still retained,
still counted, still complete, still in emission order. It lives on disk instead of in a
Python list. Memory was never what made retention meaningful.

**What it fixes on the way past.** Nothing verified the in-RAM lists either: the gate for
exact members beneath every summary reads `member_rows_written`, a COUNTER, and would have
passed just as happily if the list had been empty. A counter that agrees with nothing is the
failure shape this tree keeps meeting - present, typed, in range and wrong. A sink reconciles
its own file against that counter and REFUSES on mismatch, so streamed retention is strictly
better evidenced than the in-RAM retention it replaces, not merely cheaper.

**What it must not change, and is built not to change.** No calculator reads these ledgers.
`note_member_row` and `note_lifecycle_row` bump a counter and append; every stratum, measure
and summary comes from the calculators, which observed the row BEFORE it was retained. So a
sink changes where a copy lands and nothing that was measured. That is a claim, so it is
proved by a differential rather than asserted - see `test_native_row_sink_differential.py`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator, Mapping


KEY_SAMPLE_EVERY = 97
"""Sample one row in this many for per-FIELD byte estimates. Section totals stay exact.

A prime, so a sampler stepping through rows emitted in a repeating per-group pattern cannot
lock onto one position in that cycle and measure the same kind of row every time. With a
round number and a group that emits, say, ten rows, every sample would be the same row of the
group and the estimate would describe one tenth of the data while looking like all of it.
"""


class RowSinkError(RuntimeError):
    """A ledger could not be retained, or could not be reconciled against its counter."""


class RowSink:
    """One exact ledger, streamed to JSONL in emission order, hashed as it goes.

    JSON Lines rather than one array so a partial file after a crash is still readable to its
    last complete row, and so a reader never has to hold the whole ledger to see any of it -
    which is the property the in-RAM version lacked.
    """

    def __init__(self, path: Path | str, *, ledger: str) -> None:
        self.path = Path(path)
        self.ledger = ledger
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8")
        self._digest = hashlib.sha256()
        self._rows = 0
        self._bytes = 0
        self._closed = False
        self._bytes_by_section: dict[str, int] = {}
        self._rows_by_section: dict[str, int] = {}
        self._key_bytes: dict[str, int] = {}
        self._key_sampled_rows = 0

    @property
    def rows_written(self) -> int:
        return self._rows

    def write(self, row: Mapping[str, Any]) -> None:
        if self._closed:
            raise RowSinkError(f"{self.ledger} sink is closed; a row arrived after finalize")
        # sort_keys so a row's bytes depend on its CONTENT and not on dict insertion order:
        # two runs that retained the same rows must produce the same file hash, or the hash
        # is not evidence of anything.
        line = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        encoded = line.encode("utf-8")
        self._handle.write(line)
        self._digest.update(encoded)
        self._rows += 1
        self._bytes += len(encoded)

        # WHICH CALCULATION IS THE SIZE? A total tells you the run is too big and nothing
        # about what to do next. This attributes every byte to the section that emitted it,
        # exactly, at the cost of one dict lookup per row - so "which of the sixteen is
        # expensive" is a table rather than an opinion, and any decision to drop something
        # starts from what it actually costs.
        section = str(row.get("emitting_section") or row.get("section") or self.ledger)
        self._bytes_by_section[section] = self._bytes_by_section.get(section, 0) + len(encoded)
        self._rows_by_section[section] = self._rows_by_section.get(section, 0) + 1
        self._sample_keys(row)

    def _sample_keys(self, row: Mapping[str, Any]) -> None:
        """Per-FIELD bytes, sampled, because the expensive thing is usually one field.

        A section total says 4.x is large; it does not say the weight is one nested book
        snapshot. This measures each top-level key, which is what a drop decision is actually
        about - and D60 makes that a decision to bring to Greg with a number attached rather
        than one to take quietly.

        SAMPLED, and the rate is published beside the figures. Encoding every key of every row
        costs a serialization per key per row, which is affordable on a 57,000-record day and
        is not on a two-million-record one. An estimate labelled an estimate is honest; the
        same number labelled exact is the failure this package keeps finding.
        """
        if self._rows % KEY_SAMPLE_EVERY:
            return
        self._key_sampled_rows += 1
        for key, value in row.items():
            try:
                width = len(
                    json.dumps({key: value}, sort_keys=True, separators=(",", ":"),
                               allow_nan=False).encode("utf-8")
                )
            except (TypeError, ValueError):
                continue
            self._key_bytes[key] = self._key_bytes.get(key, 0) + width

    def close(self) -> dict[str, Any]:
        if not self._closed:
            self._handle.flush()
            self._handle.close()
            self._closed = True
        return self.receipt()

    def receipt(self) -> dict[str, Any]:
        return {
            "ledger": self.ledger,
            "path": str(self.path),
            "row_count": self._rows,
            "bytes": self._bytes,
            "sha256": self._digest.hexdigest(),
            "format": "JSONL_UTF8_SORTED_KEYS",
            "retention": "STREAMED",
            # EXACT. Every byte written is attributed, so these sum to `bytes`, and a test
            # asserts that they do - an attribution that does not add up to the total is a
            # plausible table rather than a measurement.
            "bytes_by_section": dict(sorted(self._bytes_by_section.items())),
            "rows_by_section": dict(sorted(self._rows_by_section.items())),
            # SAMPLED, and labelled so at the point of use. Scaled to the whole ledger by the
            # sample rate; the raw sampled figures and the row count behind them travel with
            # it so the estimate can be checked rather than taken.
            "field_bytes_estimated": {
                "sample_every_nth_row": KEY_SAMPLE_EVERY,
                "rows_sampled": self._key_sampled_rows,
                "basis": "sum of len(json({key: value})) over sampled rows, scaled by the rate",
                "bytes_by_field": {
                    key: value * KEY_SAMPLE_EVERY
                    for key, value in sorted(
                        self._key_bytes.items(), key=lambda item: -item[1]
                    )
                },
            },
        }

    def reconcile(self, expected_rows: int) -> dict[str, Any]:
        """The check the in-RAM version never had. A counter alone attests nothing.

        Verified from the FILE, not from this object's own tally - an internal counter
        agreeing with itself would prove only that the code is self-consistent, which is
        exactly what a silently failed write leaves intact.
        """
        receipt = self.close()
        on_disk = sum(1 for _ in self.path.open("r", encoding="utf-8"))
        if on_disk != self._rows or on_disk != expected_rows:
            raise RowSinkError(
                f"{self.ledger} retention mismatch: {expected_rows} counted, "
                f"{self._rows} offered, {on_disk} on disk at {self.path}"
            )
        receipt["reconciled_against_counter"] = expected_rows
        receipt["rows_read_back_from_disk"] = on_disk
        return receipt

    def read_back(self) -> Iterator[dict[str, Any]]:
        """Every retained row, in emission order. The proof that nothing was lost."""
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


class LedgerSinks:
    """The three exact ledgers a run retains, opened together or not at all.

    Supplied as one object rather than three arguments so a caller cannot stream two ledgers
    and silently keep the third in RAM - which would look like it worked and would still
    carry the memory term that made this necessary.
    """

    MEMBER = "exact_member_ledger"
    LIFECYCLE = "exact_lifecycle_and_runway_ledger"
    LEGACY = "legacy_observable_rows"

    def __init__(self, out_dir: Path | str) -> None:
        out_dir = Path(out_dir)
        self.member = RowSink(out_dir / "exact_member_rows.jsonl", ledger=self.MEMBER)
        self.lifecycle = RowSink(out_dir / "exact_lifecycle_rows.jsonl", ledger=self.LIFECYCLE)
        self.legacy = RowSink(out_dir / "legacy_observable_rows.jsonl", ledger=self.LEGACY)

    def reconcile_all(self, *, member: int, lifecycle: int, legacy: int) -> dict[str, Any]:
        return {
            self.MEMBER: self.member.reconcile(member),
            self.LIFECYCLE: self.lifecycle.reconcile(lifecycle),
            self.LEGACY: self.legacy.reconcile(legacy),
        }
