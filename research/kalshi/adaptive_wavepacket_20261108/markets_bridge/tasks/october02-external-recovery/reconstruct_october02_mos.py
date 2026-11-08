"""Reconstruct October 2 target-day MOS values, with archive clocks still held."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PIN = "db96f24f3260bf0d70c763b297c2ba9b84f571a6"
PINNED_FEED = "research/kalshi/nws_temp_feed.py"
FEED_SHA256 = "53a0f09853524962e2fb7ad487ec8317d1e77fb19632e149ffddd03ae0722d63"
EVIDENCE = ROOT / "october02-normalized-evidence.jsonl.gz"
TARGET_DAY = date(2023, 10, 2)
RECORDING_ZONE = ZoneInfo("America/Chicago")
SOURCE_ID = "manifest:1d4a6eebd6f7982b6978bfda412c041e23e8dce989971ea792ffd24733ab9104"


def target_date(stamp):
    return datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc).astimezone(RECORDING_ZONE).date()


def main():
    feed = subprocess.check_output(["git", "show", f"{PIN}:{PINNED_FEED}"])
    if hashlib.sha256(feed).hexdigest() != FEED_SHA256:
        raise ValueError("Unreviewed MOS station weights")
    namespace = {"__name__": "_historical_nws_feed", "__file__": PINNED_FEED}
    exec(compile(feed, PINNED_FEED, "exec"), namespace)
    weights = namespace["station_weights"]()
    min_obs = namespace["MOS_MIN_OBS"]
    observations = defaultdict(dict)
    pinned_forecasts = []
    with gzip.open(EVIDENCE, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["point_name"] == "mos.gw_by_cycle":
                if any(w["source_id"] == SOURCE_ID for w in row["occurrences"]):
                    pinned_forecasts.append(row)
            elif row["point_name"] == "mos.raw" and row["states"]["tmp_f"] == "PRESENT":
                scope = row["scope"]
                key = (scope["model"], row["observation"]["runtime_utc"], scope["station"], row["available_ns"])
                values = observations[key].setdefault(scope["valid_utc"], {})
                values.setdefault(row["numeric"]["tmp_f"], set()).add(row["normalized_sha256"])

    forecasts = defaultdict(dict)
    conflicts = []
    horizons = [TARGET_DAY + timedelta(days=index) for index in range(9)]
    for (model, runtime, station, available), forecast in observations.items():
        if station not in weights:
            continue
        if model not in min_obs:
            raise ValueError(f"Unknown model {model}")
        for target in horizons:
            hours = {valid: alternatives for valid, alternatives in forecast.items() if target_date(valid) == target}
            if any(len(values) > 1 for values in hours.values()):
                conflicts.append([model, runtime, station, target.isoformat()])
                continue
            if len(hours) < min_obs[model]:
                continue
            temps = [next(iter(versions)) for versions in hours.values()]
            mean = (min(temps) + max(temps)) / 2
            hashes = sorted(set().union(*(set().union(*versions.values()) for versions in hours.values())))
            forecasts[(model, runtime, available, target)][station] = (max(0, 65 - mean), max(0, mean - 65), hashes)

    aggregates = {}
    for (model, runtime, available, target), stations in forecasts.items():
        weight = sum(weights[s] for s in stations)
        if not weight:
            continue
        aggregates[(model, runtime, available, target)] = dict(
            model=model, runtime_utc=runtime, catalog_modeled_available_ns=available, target_day=target.isoformat(),
            target_offset_days=(target - TARGET_DAY).days, gw_hdd=round(sum(weights[s] * v[0] for s, v in stations.items()) / weight, 3),
            gw_cdd=round(sum(weights[s] * v[1] for s, v in stations.items()) / weight, 3),
            coverage=round(weight, 4), n_metros=len(stations),
            metros_missing=sorted(set(weights) - stations.keys()), source_rows=sorted(set().union(*(v[2] for v in stations.values()))),
        )
    comparisons = []
    for row in pinned_forecasts:
        key = (row["scope"]["model"], row["observation"]["runtime_utc"], row["available_ns"],
               date.fromisoformat(row["scope"]["target_day"]))
        actual = aggregates.get(key)
        fields = ("gw_hdd", "gw_cdd", "coverage", "n_metros")
        comparison = {
            "archive_sha256": row["normalized_sha256"], "target_day": key[-1].isoformat(),
            "differences": ({f: [row["numeric"][f], actual[f]] for f in fields if row["numeric"][f] != actual[f]}
                            if actual is not None else None),
        }
        comparisons.append(comparison)
    selected = [value for key, value in sorted(aggregates.items()) if key[-1] <= horizons[-2]]
    disagreements = defaultdict(list)
    for (model, runtime, available, target), gfs in forecasts.items():
        if model != "GFS" or target > horizons[-2]:
            continue
        nam = forecasts.get(("NAM", runtime, available, target), {})
        common = sorted(gfs.keys() & nam.keys())
        weight = sum(weights[s] for s in common)
        if not weight:
            continue
        spread = sum(weights[s] * (gfs[s][0] - nam[s][0]) for s in common) / weight
        disagreements[(runtime, available)].append({
            "target_day": target.isoformat(), "target_offset_days": (target - TARGET_DAY).days,
            "spread_gw_hdd": round(spread, 3), "common_metros": common,
        })
    by_cycle = []
    for (runtime, available), values in sorted(disagreements.items()):
        values = sorted(values, key=lambda r: r["target_day"])
        top = max(values, key=lambda r: abs(r["spread_gw_hdd"]))
        by_cycle.append(dict(runtime_utc=runtime, catalog_modeled_available_ns=available,
                             max_abs_spread_gw_hdd=abs(top["spread_gw_hdd"]), max_at_target=top["target_day"],
                             spreads=values))
    report = {
        "trade_date": TARGET_DAY.isoformat(), "status": "HELD_MODELED_DISSEMINATION_CLOCK",
        "feed_sha256": FEED_SHA256, "forecast_rows": selected, "disagreement_cycles": by_cycle,
        "overlapping_other_day_forecast_checks": comparisons, "conflicting_station_target_cycles": conflicts,
        "clock_limit": "The pinned archive uses runtime plus 4.5 hours. No original dissemination timestamp was recovered.",
    }
    (ROOT / "october02-mos-reconstruction.json").write_text(json.dumps(report, separators=(",", ":")) + "\n",
                                                          encoding="utf-8")
    print("Forecast rows:", len(selected), "disagreement cycles:", len(by_cycle),
          "archive comparisons:", len(comparisons), "matches:", sum(r["differences"] == {} for r in comparisons),
          "station/target conflicts:", len(conflicts))


if __name__ == "__main__":
    main()
