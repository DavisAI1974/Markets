"""ROOT `tape`: reads the raw order-tape files of a trade week in order, every record, and says what each one is.

Specification: SPEC-root.md (approved by Greg, 2026-11-16), part `tape`. Inputs: the raw MBO files of
markets-data `data/nymex_mbo/ng_v0_oct2023/`, one per UTC clock day, each checked against its MANIFEST.json
fingerprint before it is read, and its record count checked against the manifest's independent count.

What each record is (checked on the seven files held, 2026-11-16):
- The week's first file (its Sunday) opens with the exchange's clear, unflagged, then the re-listed orders. The vendor
  flags those re-listed orders as a snapshot, but they are the exchange's Sunday start-up (Greg's ruling): ticks, with
  their flags kept on the row.
- Every later file opens with the vendor's own restatement of the book: a flagged clear and flagged adds, received
  exactly at the file's start. They are not exchange messages at that moment, so they are not ticks: they go to the
  snapshot table and are never applied to the book.
- Everything else is a tick, in tape order.
Anything that does not fit this is refused with the file named.

    python3 -m root.run check-week 20231002
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from root.calendar import (OPEN_EASTERN, HALT_EASTERN, STARTUP, TRADE_DAY, clock_days_needed, eastern, label,
                           to_ns, week_sunday)

TICK = 'tick'
VENDOR_SNAPSHOT = 'vendor snapshot'
CLEAR = b'R'                                       # the action code of a clear, as the tape writes it


def flag_bits() -> dict:
    """The vendor's named flag bits (databento_dbn), never written as numbers here."""
    import databento_dbn as dbn
    return {name: getattr(dbn, name) for name in ('F_LAST', 'F_TOB', 'F_SNAPSHOT', 'F_MBP', 'F_BAD_TS_RECV',
                                                  'F_MAYBE_BAD_BOOK', 'F_PUBLISHER_SPECIFIC')}


def record_fields() -> list[str]:
    """Every field of an MBO record, as the vendor defines it."""
    import databento_dbn as dbn
    return list(dbn.MBOMsg._ordered_fields)


class TapeFolder:
    """The raw tape folder with its manifest. A file is read only after its fingerprint and count are checked."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        manifest = json.loads((self.folder / 'MANIFEST.json').read_text())
        self.by_day = {dt.date.fromisoformat(f['day']): f for f in manifest['files']}

    def entry(self, day: dt.date) -> dict:
        if day not in self.by_day:
            raise FileNotFoundError(f'no raw tape file for UTC clock day {day} in {self.folder} (MANIFEST.json); '
                                    f'the week cannot be read without it')
        return self.by_day[day]

    def read(self, day: dt.date):
        """(manifest entry, every record as a structured array, contract mappings) for one UTC clock day."""
        import databento as db
        entry = self.entry(day)
        path = self.folder / entry['file']
        if not path.is_file():
            raise FileNotFoundError(f'{entry["file"]} is in MANIFEST.json but not in {self.folder}')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError(f'{entry["file"]} differs from its fingerprint in MANIFEST.json; refusing to read it')
        store = db.DBNStore.from_bytes(raw)
        records = store.to_ndarray()
        if len(records) != entry['records']:
            raise ValueError(f'{entry["file"]} holds {len(records)} records; MANIFEST.json counted {entry["records"]}')
        return entry, records, store.metadata.mappings


def classify(records, first_of_week: bool, name: str) -> int:
    """The number of leading records that are the vendor's restatement (0 in the week's first file). Refuses, naming
    the file, when the file does not open as the held tape does or when a flagged record appears later on."""
    snap = flag_bits()['F_SNAPSHOT']
    flagged = (records['flags'] & snap) != 0
    if not len(records):
        raise ValueError(f'{name} holds no records')
    if first_of_week:
        if flagged[0] or records['action'][0] != CLEAR:
            raise ValueError(f'{name}: the week\'s first file does not open with the exchange\'s unflagged clear')
        start, lead = 1, 0
    else:
        if not flagged[0] or records['action'][0] != CLEAR:
            raise ValueError(f'{name}: a later file does not open with the vendor\'s flagged clear (its restatement)')
        start = 0
    run = start
    while run < len(records) and flagged[run]:
        run += 1
    if flagged[run:].any():
        raise ValueError(f'{name}: a flagged record appears after the opening block, at record {run + int(flagged[run:].argmax()) + 1}')
    return 0 if first_of_week else run


@dataclass
class WeekFile:
    day: dt.date
    name: str
    sha256: str
    records: object
    vendor_snapshot: int
    instrument_ids: list = field(default_factory=list)
    mappings: dict = field(default_factory=dict)


def read_week(folder: Path, trade_day: dt.date) -> list[WeekFile]:
    """Every raw file a trade day needs, from its week's Sunday, in order. Refuses a missing file, a changed
    fingerprint, a wrong count, a file that does not open as expected, or more than one contract in the week."""
    tape = TapeFolder(folder)
    days = clock_days_needed(trade_day)
    if days[0] != week_sunday(trade_day):
        raise ValueError(f'the week of {trade_day} does not start at its Sunday')
    out = []
    for k, day in enumerate(days):
        entry, records, mappings = tape.read(day)
        lead = classify(records, k == 0, entry['file'])
        ids = sorted(set(records['instrument_id'].tolist()))
        out.append(WeekFile(day, entry['file'], entry['sha256'], records, lead, ids, mappings))
    contracts = {i for f in out for i in f.instrument_ids}
    if len(contracts) != 1:
        raise ValueError(f'the week of {trade_day} holds more than one contract: {sorted(contracts)}')
    return out


def ticks(week: list[WeekFile]):
    """(file index, record index, record, kind) for every record of the week, in tape order. One pass, forward only."""
    for f_index, f in enumerate(week):
        for r_index in range(len(f.records)):
            kind = VENDOR_SNAPSHOT if r_index < f.vendor_snapshot else TICK
            yield f_index, r_index, f.records[r_index], kind


def written_or_not(trade_day: dt.date, exchange_ns: int) -> str:
    """For one trade day's box: 'written' (the trade day, the stretch before and after it, and the Sunday start-up
    when it is the week's first trade day), 'warm-up' (earlier in the week: run through the book only) or 'shelved'
    (after the stretch that follows it: belongs to a later trade day)."""
    before_from = to_ns(eastern(trade_day - dt.timedelta(days=1), HALT_EASTERN))
    after_to = to_ns(eastern(trade_day, OPEN_EASTERN))
    tag, _ = label(exchange_ns)
    if exchange_ns >= after_to:
        return 'shelved'
    if before_from <= exchange_ns:
        return 'written'
    if tag == STARTUP and trade_day - dt.timedelta(days=1) == week_sunday(trade_day):
        return 'written'
    return 'warm-up'


def check_week(folder: Path, trade_day: dt.date) -> dict:
    """The check-week receipt: files, fingerprints, independent counts, what each record is, and every count by
    action, flag and label. Nothing is applied to a book here."""
    import time
    started = time.monotonic()
    week = read_week(folder, trade_day)
    bits = flag_bits()
    files = []
    for f in week:
        rec = f.records
        tick_part = rec[f.vendor_snapshot:]
        labels = collections.Counter()
        box = collections.Counter()
        for t in tick_part['ts_event'].tolist():
            tag, day = label(t)
            labels[f'{tag} {day}' if day else tag] += 1
            box[written_or_not(trade_day, t)] += 1
        files.append(dict(
            file=f.name, utc_clock_day=f.day.isoformat(), sha256=f.sha256, records=len(rec),
            vendor_snapshot_records=f.vendor_snapshot, ticks=len(tick_part),
            vendor_snapshot_actions={k.decode(): v for k, v in collections.Counter(rec['action'][:f.vendor_snapshot].tolist()).items()},
            tick_actions={k.decode(): v for k, v in sorted(collections.Counter(tick_part['action'].tolist()).items())},
            tick_flags={name: int(((tick_part['flags'] & bit) != 0).sum()) for name, bit in bits.items()},
            ticks_by_label=dict(sorted(labels.items())), ticks_for_this_box=dict(sorted(box.items())),
            instrument_ids=f.instrument_ids,
            mappings={k: [dict(start_date=str(m['start_date']), end_date=str(m['end_date']), symbol=m['symbol'])
                          for m in v] for k, v in f.mappings.items()},
            fields=list(rec.dtype.names)))
    for f in files:
        assert f['records'] == f['vendor_snapshot_records'] + f['ticks']
    return dict(what='ROOT tape: check-week (files, fingerprints, counts, what each record is)',
                specification='SPEC-root.md (approved 2026-11-16), part tape', trade_day=trade_day.isoformat(),
                week_sunday=week_sunday(trade_day).isoformat(), files=files,
                contract_instrument_id=week[0].instrument_ids[0], record_fields=record_fields(),
                never_exercised=['a later file that does not open with a flagged clear',
                                 'a first file that does not open with an unflagged clear',
                                 'a flagged record after the opening block', 'more than one contract in a week'],
                seconds=round(time.monotonic() - started, 1))


# ---------------------------------------------------------------- the only way into a calculation (Greg, 2026-11-16)
BUILT_TRADE_DAYS = frozenset(dt.date(2023, 10, d) for d in (2, 3, 17, 18))


def calculation_eligible(exchange_ns: int, built=BUILT_TRADE_DAYS) -> bool:
    """True only for a tick inside one of the four built trade days (6 pm to 5 pm Eastern). Greg: "none of the hours
    outside of the 4 trade days are used in our calculations." The 5 pm to 6 pm stretches and the Sunday start-up keep
    their marked rows but are never calculated on; warm-up and shelved ticks only build the book."""
    tag, day = label(exchange_ns)
    return tag == TRADE_DAY and day in built


def for_calculations(week: list[WeekFile], built=BUILT_TRADE_DAYS):
    """The ONE gate through which any calculation receives ticks. Yields (file index, record index, record) for
    calculation-eligible ticks only. A calculation must never iterate `ticks()` or the raw files itself."""
    for f_index, r_index, record, kind in ticks(week):
        if kind == TICK and calculation_eligible(int(record['ts_event']), built):
            yield f_index, r_index, record


def columns(records) -> dict:
    """Every field of a block of records as plain lists (one pass over a file is far faster on lists)."""
    return {name: records[name].tolist() for name in records.dtype.names}
