"""Bind the three approved discovery spans to the verified Git DBN members."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .verify_ng_book_replay import TAPE_PIN, read_member, tape_blob


DAYS = ("20231002", "20231003", "20231017")
SCOPES = {
    "20231002": (808_453, 600_291),
    "20231003": (879_830, 653_912),
    "20231017": (841_601, 635_170),
}
HALT_HOUR = 21


def inspect(day, spec):
    start = int(datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()) * 10**9
    halt = start + HALT_HOUR * 3600 * 10**9
    end = start + 24 * 3600 * 10**9
    count = before = groups = before_groups = 0
    last_before_flags = last_flags = 0
    previous = None
    instruments = set()
    for record in read_member(spec):
        receive = int(record.ts_recv)
        flags = int(record.flags)
        if not start <= receive < end or (previous is not None and previous > receive):
            raise ValueError(f"{day} has a record outside its ordered UTC scope")
        if previous is None:
            first = receive
            if record.action.value != "R" or not flags & 32:
                raise ValueError(f"{day} lacks its opening snapshot reset")
        instruments.add(int(record.instrument_id))
        count += 1
        groups += bool(flags & 128)
        if receive < halt:
            before += 1
            before_groups += bool(flags & 128)
            last_before_flags = flags
        last_flags, previous = flags, receive
    if (count != spec["records"] or not 0 < before < count or len(instruments) != 1
            or not last_before_flags & 128 or not last_flags & 128):
        raise ValueError(f"{day} count, instrument or closed-group boundary failed")
    return dict(member_key=spec["file"], day_utc=day, mbo_records=count, before_halt=before,
                after_halt=count - before, f_last_groups=groups, f_last_before_halt=before_groups,
                first_ts_recv_ns=first, last_ts_recv_ns=previous, instruments=len(instruments),
                halt_boundary_f_last=True, last_record_f_last=True)


def build(day, specs, sessions):
    full_open = day == "20231003"
    member_days = ("20231002", day) if full_open else (day,)
    head = sessions[day]
    partial = dict(member_key=head["member_key"], partition_mbo_records=head["mbo_records"],
                   take=head["before_halt"], reason="Keep the records before the 21:00 UTC halt boundary.")
    tails = []
    groups = head["f_last_before_halt"]
    if full_open:
        prior = sessions[member_days[0]]
        groups += prior["f_last_groups"] - prior["f_last_before_halt"]
        tails.append(dict(member_key=prior["member_key"], partition_mbo_records=prior["mbo_records"],
                          skip=prior["before_halt"], take=prior["after_halt"],
                          reason="Include the previous UTC member's tail for this trading date."))
    counts = [entry["take"] for entry in (*tails, partial)]
    if (sum(counts), groups) != SCOPES[day]:
        raise ValueError(f"{day} disagrees with the verified replay scope")
    sources = [dict(member_index=index, member_key=specs[key]["file"], sha256=specs[key]["sha256"],
                    size_bytes=specs[key]["bytes"], mbo_records=take)
               for index, (key, take) in enumerate(zip(member_days, counts, strict=True))]
    manifest = dict(
        schema="BOSS_BLOCK_SOURCE_MANIFEST_V1", block=day, trading_day=day,
        role="DISCOVERY_DATA", source_kind="NATIVE_DBN_MBO", causal_clock="ts_recv_ns",
        bucket=None, prefix=None, tape_git_commit=TAPE_PIN, halt_utc_hour=HALT_HOUR,
        sampled=False, canonical_source_rewritten=False,
        member_seams_close_groups=True, halt_boundaries_close_groups=True,
        opening_scope="PREVIOUS_UTC_TAIL" if full_open else "MIDNIGHT_UTC_SNAPSHOT_PARTIAL_TRADING_DATE",
        sources=sources, sessions=[sessions[key] for key in member_days],
        partial_members=[partial], tail_members=tails,
        total_mbo_records=sum(counts), completed_groups=groups,
    )
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    manifest["manifest_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Existing empty destination directory")
    output = parser.parse_args().output
    by_file = {x["file"]: x for x in json.loads(tape_blob("MANIFEST.json"))["files"]}
    specs = {day: by_file[f"NG_v0_mbo_{day}.dbn.zst"] for day in DAYS}
    with ThreadPoolExecutor(max_workers=3) as pool:
        receipts = pool.map(inspect, DAYS, (specs[day] for day in DAYS))
        sessions = dict(zip(DAYS, receipts, strict=True))
    for day in DAYS:
        manifest = build(day, specs, sessions)
        with (output / f"BLOCK_{day}_SOURCE_MANIFEST.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(day, manifest["total_mbo_records"], manifest["completed_groups"], manifest["manifest_hash"])


if __name__ == "__main__":
    main()
