"""Export October 2 external evidence from the hash-verified scoped history catalog.

Run from the repository root with the restored scoped_history.sqlite path.
The report keeps recovered values separate from archived candidates and controls.
"""
import argparse
from collections import Counter
from datetime import date, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

DEST = Path(__file__).resolve().parent
START = 1696204800000000000
HALT = 1696280400000000000
MARKET_OPEN = 1696197600000000000
HOUR = 3600 * 10**9
CATALOG_SHA = "74bc6de27a97f7f074957d36d64481d8bbe3e6ef6c0b9873cc42a1c015f6117a"
ARCHIVE_SHA = "2e6808cf2e1ca07e89ae3260d237d81327418dd28a1710c81ba7f0b733b656b0"
CFTC_SHA = "f69db3a12ee75bcc40a44e24dfffcf359fcd9fa0e6eebf78d25700ee28ebf7db"
CFTC_LATEST = "https://www.cftc.gov/sites/default/files/files/dea/cotarchives/2023/futures/nat_gas_lf092623.htm"
CFTC_PRIOR = "https://www.cftc.gov/sites/default/files/files/dea/cotarchives/2023/futures/nat_gas_lf091923.htm"
EIA = "https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2023/09_28/"
CME = "https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf"
POINTS = {
    1: ("cot.023651",),
    2: ("mos.gw_by_cycle", "mos.raw"),
    3: ("cot.023651",),
    4: ("cot.023651",),
    5: ("eia930.hourly", "eia930.us48"),
    6: ("calendar.sessions_since_prompt_expiry",),
    7: ("eia930.hourly", "eia930.us48"),
    8: ("cot.023391", "cot.023392", "cot.0233AG", "cot.0233AH"),
    9: ("mos.disagreement_by_cycle", "mos.raw"),
    10: ("weather.gw_daily", "weather.obs_hourly"),
    11: ("storage.weekly",),
    12: ("storage.estimate", "storage.estimate_captures"),
    13: ("curve.definitions", "curve.statistics", "curve.trades", "curve.settled_shape", "curve.traded_shape"),
}
JSON_COLUMNS = ("observation", "numeric", "states", "categories", "provenance")


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def independent_cot():
    path = DEST / "cftc-disaggregated-futures-only-through-2023-09-26.json"
    if digest(path) != CFTC_SHA:
        raise ValueError("Unreviewed CFTC response")
    rows = json.loads(path.read_bytes())
    result = {}
    report = date(2023, 9, 26)
    for code, printed in {"023651": (182449, 238657, 1142377), "023391": (240094, 127537, 6591753)}.items():
        selected = [
            (date.fromisoformat(r["report_date_as_yyyy_mm_dd"][:10]),
             int(r["m_money_positions_long_all"]), int(r["m_money_positions_short_all"]), int(r["open_interest_all"]))
            for r in rows if r["cftc_contract_market_code"] == code
        ]
        if len(selected) != 157 or selected != sorted(set(selected)) or len({r[0] for r in selected}) != 157:
            raise ValueError(f"Incomplete or ambiguous CFTC window for {code}")
        if selected[-1] != (report, *printed):
            raise ValueError(f"Latest CFTC API row differs from original printed report for {code}")
        _, long, short, interest = selected[-1]
        net = long - short
        _, previous_long, previous_short, _ = selected[-2]
        numbers = dict(managed_money_long=long, managed_money_short=short, open_interest=interest,
                       managed_money_net=net, managed_money_net_chg_wow=net - (previous_long - previous_short))
        for label, days in (("1y", 365), ("3y", 1095)):
            window = [lng - sht for when, lng, sht, _ in selected if when >= report - timedelta(days=days)]
            rank = 100 * sum(1 if value < net else 0.5 if value == net else 0 for value in window) / len(window)
            numbers[f"managed_money_net_pctile_{label}"] = round(rank, 2)
            numbers[f"pctile_{label}_n_obs"] = len(window)
        result["cot." + code] = numbers
    return result


def candidate_role(point):
    if point.startswith("calendar."):
        return "OTHER_DATE_CONTEXT"
    if point.startswith("eia930."):
        return "HELD_REVISED_VINTAGE_AND_NOMINAL_CLOCK"
    if point.startswith(("mos.", "weather.")):
        return "HELD_ARCHIVE_CLOCK_OR_TARGET_SCOPE"
    if point.startswith("curve."):
        return "HELD_FULL_CURVE_SOURCE_AND_CAUSAL_COMPONENT_CHECK"
    if point.startswith("cot."):
        return "CFTC_HISTORICAL_EVIDENCE"
    return "SEPARATE_STORAGE_VINTAGE_EVIDENCE"


def selection_start(point):
    if point.startswith(("cot.", "storage.", "calendar.")):
        return 0
    if point.startswith("eia930."):
        return MARKET_OPEN - 8 * 24 * HOUR
    if point.startswith(("mos.", "weather.")):
        return MARKET_OPEN - 72 * HOUR
    return START


def export_candidates(db, cot):
    counters, source_uses, cftc_checks = Counter(), Counter(), Counter()
    sources = {
        r["source_id"]: dict(source_day=r["day"], sha256=r["sha256"], role=r["role"],
                            metadata=json.loads(r["metadata_json"]))
        for r in db.execute("SELECT source_id,day,sha256,role,metadata_json FROM source_file")
    }
    ids = sorted({table for names in POINTS.values() for table in names})
    output = DEST / "october02-normalized-evidence.jsonl.gz"
    with output.open("wb") as out, gzip.GzipFile(fileobj=out, filename="", mode="wb", mtime=0) as compressed:
        for scope in db.execute("SELECT * FROM scope ORDER BY point_name,scope_id"):
            point = scope["point_name"]
            if point not in ids:
                raise ValueError(f"Unreviewed catalog scope: {point}")
            scope_info = json.loads(scope["scope_json"])
            if point.startswith("calendar."):
                continue
            rows = db.execute(
                """SELECT * FROM normalized_variant INDEXED BY normalized_scope_time
                   WHERE scope_id=? AND available_ns>=? AND available_ns<?
                   ORDER BY available_ns, normalized_sha256""",
                (scope["scope_id"], selection_start(point), HALT),
            )
            for row in rows:
                entry = {k: row[k] for k in ("normalized_sha256", "point_name", "scope_id", "observation_id",
                                             "available_ns", "event_ns", "source_published_ns", "clock_rule")}
                entry.update({k: json.loads(row[k + "_json"]) for k in JSON_COLUMNS})
                if row["event_ns"] is not None and row["event_ns"] > row["available_ns"]:
                    raise ValueError(f"Future event at {row['normalized_sha256']}")
                witnesses = db.execute(
                    """SELECT source_id, source_ordinal, raw_row_sha256 FROM provenance
                       INDEXED BY provenance_normalized WHERE normalized_sha256=?
                       ORDER BY source_id,source_ordinal""", (row["normalized_sha256"],),
                )
                occurrences = []
                for witness in witnesses:
                    source = sources[witness["source_id"]]
                    meta = source["metadata"]["point_metadata"][point]
                    occurrences.append({
                        **dict(witness), "source_day": source["source_day"],
                        "source_sha256": source["sha256"], "vintage": meta.get("vintage"),
                    })
                    source_uses[witness["source_id"]] += 1
                if not occurrences:
                    raise ValueError(f"Unlinked normalized variant: {row['normalized_sha256']}")
                entry.update(scope=scope_info, occurrences=occurrences, disposition=candidate_role(point))
                if point in cot and entry["observation"]["report_date"] == "2023-09-26":
                    if any(entry["numeric"].get(k) != value for k, value in cot[point].items()):
                        raise ValueError(f"CFTC source mismatch for {point}")
                    if entry["available_ns"] != 1696015800000000000:
                        raise ValueError(f"Unexpected CFTC publication for {point}")
                    cftc_checks[point] += 1
                counters[point] += 1
                compressed.write(json.dumps(entry, separators=(",", ":"), allow_nan=False).encode() + b"\n")
    if set(cftc_checks) != set(cot):
        raise ValueError("Missing retained CFTC matches")
    return output, counters, source_uses, cftc_checks


def build_report(output, counters, source_uses, cftc_checks, cot):
    status = {
        1: "RECOVERED_CFTC",
        2: "RECONSTRUCTED_HELD_MODELED_DISSEMINATION_CLOCK",
        3: "RECOVERED_CFTC",
        4: "RECOVERED_CFTC",
        5: "HELD_FIRST_PUBLICATION_VINTAGE",
        6: "RECOVERED_CONTROL",
        7: "HELD_FIRST_PUBLICATION_VINTAGE",
        8: "RECOVERED_ICE_LD1",
        9: "RECONSTRUCTED_HELD_MODELED_DISSEMINATION_CLOCK",
        10: "HELD_ARCHIVE_PUBLICATION_CLOCK",
        11: "RECOVERED_EIA_AS_REPORTED",
        12: "RECOVERED_EIA_THE_DESK_VARIANT",
        13: "PARTIAL_NGX3_TRADES_VERIFIED_FULL_CURVE_HELD",
    }
    selected = {
        1: {"value": cot["cot.023651"]["managed_money_net_pctile_1y"], "units": "percentile_0_to_100"},
        3: {"value": cot["cot.023651"]["managed_money_net_chg_wow"], "units": "contracts"},
        4: {"value": cot["cot.023651"]["managed_money_net_pctile_3y"], "units": "percentile_0_to_100"},
        6: {"value": 3, "units": "CME_business_sessions", "last_prompt": "NGV23", "expiry": "2023-09-27",
            "available_ns": 1696269600000000000, "role": "calendar_control", "source": CME,
            "definition_commit": "db96f24f3260bf0d70c763b297c2ba9b84f571a6",
            "calendar_definition_blob": "06fa0ad2c73695da5311102ecc057a91afb8db66",
            "builder_definition_blob": "11e3d1436fb46bcd5a97cb433b73f8409a4c233d"},
        8: {"value": cot["cot.023391"]["managed_money_net_pctile_1y"], "units": "percentile_0_to_100"},
        11: {"week_ending": "2023-09-22", "level_bcf": 3359, "weekly_chg_bcf": 90, "vs_5yr_bcf": 189,
             "five_yr_avg_bcf": 3170, "year_ago_bcf": 2962, "source": EIA},
        12: {"week_ending": "2023-09-22", "print_date": "2023-09-28", "estimate_bcf": 90, "actual_bcf": 90,
             "surprise_bcf": 0, "estimate_range_bcf": [84, 102], "estimate_vintage": "The Desk median reported by EIA",
             "source": EIA},
    }
    for point in (1, 3, 4, 8):
        selected[point].update(report_date="2023-09-26", source=CFTC_LATEST, available_ns=1696015800000000000)
    for point in (11, 12):
        selected[point].update(available_ns=1695960000000000000,
                               availability_basis="Conservative end of the EIA update's dated release day in New York")
    return {
        "trade_date": "2023-10-02", "available_market_start_ns": START, "halt_exclusive_ns": HALT,
        "coverage_gate": "NOT_PASSED",
        "archive_sha256": ARCHIVE_SHA, "catalog_sha256": CATALOG_SHA,
        "candidate_file": output.name, "candidate_file_sha256": digest(output),
        "candidate_count": sum(counters.values()), "candidate_counts_by_table": dict(counters),
        "source_occurrence_counts": dict(source_uses),
        "cftc_independent_response_sha256": CFTC_SHA, "cftc_original_prior_print": CFTC_PRIOR,
        "cftc_independent_values": cot, "cftc_retained_variants_matched": dict(cftc_checks),
        "curve_ng_x3_check": "october02-ngx3-curve-trades-crosscheck.json",
        "mos_reconstruction": "october02-mos-reconstruction.json",
        "cftc_percentile_vintage_limit": "Independent calculation from official historical report rows. The as-first-published vintage of every constituent report has not been separately checked.",
        "points": [{"id": point, "original_tables": tables, "status": status[point],
                    "available_reconstruction": selected.get(point)} for point, tables in POINTS.items()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()
    if digest(args.catalog) != CATALOG_SHA:
        raise ValueError("Unreviewed scoped history catalog")
    cot = independent_cot()
    with sqlite3.connect(args.catalog.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA cache_size=-524288")
        output, counts, source_uses, checks = export_candidates(db, cot)
    report = build_report(output, counts, source_uses, checks, cot)
    (DEST / "october02-external-recovery.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {report['candidate_count']:,} archive variants and reviewed all {len(POINTS)} points", flush=True)


if __name__ == "__main__":
    main()
