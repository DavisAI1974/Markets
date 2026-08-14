#!/usr/bin/env python3
"""M-13 S126: recover the three stale Frankie stores without inventing replacement feeds.

This wrapper reuses the existing builders and the sanctioned Markets S3 door:

  1. restore the current private substrate from S3;
  2. merge strictly-pre-print storage-consensus evidence recovered from point-in-time
     GitHub Actions collector logs;
  3. extend the existing MOS cycle and freeze-risk stores with their existing builders;
  4. push only through platform_sync.py;
  5. D47-read every pushed source file back from S3 and require byte-identical SHA256;
  6. run a suffixed g24 rehearsal through canonical stage_group.py and require state-health
     hard == 0 plus all three M-13 blocks non-empty on every configured day.

No Frankie settings, schema, inputs, specialist roles, spawn.py, or signal methodology are changed.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RENDER_DIR = HERE / "renders" / "ng_refine_s95"
EVIDENCE_PATH = HERE / "data_records" / "storage_consensus_forward_s126.json"
STORAGE_PATH = REPO / "data" / "storage_consensus" / "storage_consensus.json"
EIA_PATH = REPO / "data" / "eia_surprise.json"
MOS_CYCLE_DIR = REPO / "data" / "weather" / "mos_cycle"
MOS_CYCLE_PATH = MOS_CYCLE_DIR / "mos_cycle_index.json"
FREEZE_DIR = REPO / "data" / "weather" / "mos_freeze"
FREEZE_PATH = FREEZE_DIR / "freeze_risk_index.json"

BUCKET = "bento-568968024170-us-east-2-an"
REGION = "us-east-2"
REHEARSAL_SUFFIX = "_m13check"

PUSHES = (
    ("consensus/", STORAGE_PATH.parent),
    ("weather/mos_cycle/", MOS_CYCLE_DIR),
    ("weather/mos_freeze/", FREEZE_DIR),
)


class M13InvariantError(RuntimeError):
    pass


def _log(msg: str) -> None:
    print(f"[m13] {msg}", flush=True)


def _parse_utc(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def validate_evidence_rows(rows: Iterable[dict], through: str | None = None) -> list[dict]:
    """Validate and return release-sorted blind-safe evidence, optionally truncated at through."""
    cutoff = dt.date.fromisoformat(through) if through else None
    seen: set[str] = set()
    out: list[dict] = []
    for raw in rows:
        row = dict(raw)
        rel = str(row.get("release_date") or "")
        try:
            rel_d = dt.date.fromisoformat(rel)
        except ValueError as exc:
            raise M13InvariantError(f"bad release_date {rel!r}") from exc
        if rel in seen:
            raise M13InvariantError(f"duplicate storage evidence for {rel}")
        seen.add(rel)
        if rel_d.weekday() != 3:
            raise M13InvariantError(f"{rel}: normal M-13 evidence release is not Thursday")
        observed = _parse_utc(str(row.get("observed_at_utc") or ""))
        printed = _parse_utc(str(row.get("print_datetime_utc") or ""))
        if observed >= printed:
            raise M13InvariantError(
                f"{rel}: BLIND WALL evidence observed {observed.isoformat()} "
                f"at/after print {printed.isoformat()}"
            )
        val = row.get("consensus_bcf")
        if not isinstance(val, (int, float)):
            raise M13InvariantError(f"{rel}: consensus_bcf is not numeric: {val!r}")
        if not row.get("workflow_run_id") or not row.get("workflow_job_id"):
            raise M13InvariantError(f"{rel}: missing point-in-time workflow provenance")
        if cutoff is None or rel_d <= cutoff:
            out.append(row)
    out.sort(key=lambda r: r["release_date"])
    if not out:
        raise M13InvariantError("no legal storage-consensus evidence remains after cutoff")
    return out


def _estimate_from_evidence(row: dict) -> dict:
    return {
        "source": row["source"],
        "value_bcf": float(row["consensus_bcf"]),
        "pre_print": True,
        "snapshot_utc": row["observed_at_utc"],
        "snapshot_url": row["evidence_url"],
        "workflow_run_id": int(row["workflow_run_id"]),
        "workflow_job_id": int(row["workflow_job_id"]),
        "previous_bcf": (
            float(row["previous_bcf"]) if isinstance(row.get("previous_bcf"), (int, float)) else None
        ),
        "provenance_note": (
            "Point-in-time collector log; observation timestamp is strictly before the EIA print. "
            "Recovered for M-13 S126 because durable consensus.jsonl updates forecast values in place."
        ),
    }


def _new_report(row: dict, actuals: dict[str, float | None]) -> dict:
    release = dt.date.fromisoformat(row["release_date"])
    value = float(row["consensus_bcf"])
    return {
        "for_report_date": (release - dt.timedelta(days=6)).isoformat(),
        "print_date": release.isoformat(),
        "print_dow": "Thu",
        "print_time_et": "10:30",
        "print_datetime_utc": row["print_datetime_utc"],
        "print_schedule_note": (
            "Normal Thursday 10:30 ET EIA natural-gas storage print; consensus provenance "
            "recovered from a strictly pre-print forward collector log (M-13 S126)."
        ),
        "nominal_release_date": release.isoformat(),
        "consensus_chg_bcf": value,
        "source": row["source"],
        "consensus_pre_print_bcf": value,
        "consensus_pre_print_snapshot_utc": row["observed_at_utc"],
        "n_estimates": 1,
        "range_low_bcf": None,
        "range_high_bcf": None,
        "house_disagreement_bcf": None,
        "estimates": [_estimate_from_evidence(row)],
        "actual_current_vintage_bcf": actuals.get(release.isoformat()),
        "actual_as_printed_bcf": None,
        "actual_as_printed_source": None,
    }


def merge_storage_consensus(
    store: dict,
    evidence_rows: Iterable[dict],
    actuals: dict[str, float | None] | None = None,
) -> tuple[dict, list[str]]:
    """Add forward pre-print evidence without overwriting a conflicting archived house value."""
    if not isinstance(store, dict) or not isinstance(store.get("reports"), list):
        raise M13InvariantError("storage consensus baseline must contain a reports list")
    actuals = actuals or {}
    merged = copy.deepcopy(store)
    reports = merged["reports"]
    by_print = {str(r.get("print_date")): r for r in reports}
    notes: list[str] = []

    for row in evidence_rows:
        rel = row["release_date"]
        val = float(row["consensus_bcf"])
        rec = by_print.get(rel)
        if rec is None:
            rec = _new_report(row, actuals)
            reports.append(rec)
            by_print[rel] = rec
            notes.append(f"{rel}: appended legal forward consensus {val:+g} Bcf")
            continue

        estimates = rec.setdefault("estimates", [])
        duplicate = any(
            e.get("workflow_run_id") == int(row["workflow_run_id"])
            and e.get("workflow_job_id") == int(row["workflow_job_id"])
            for e in estimates
        )
        if not duplicate:
            estimates.append(_estimate_from_evidence(row))

        headline = rec.get("consensus_chg_bcf")
        if headline is None:
            rec["consensus_chg_bcf"] = val
            rec["source"] = row["source"]
            notes.append(f"{rel}: filled missing headline consensus with legal pre-print {val:+g} Bcf")
        elif abs(float(headline) - val) > 1e-9:
            notes.append(
                f"{rel}: preserved existing archived headline {float(headline):+g} Bcf; "
                f"carried forward collector {val:+g} Bcf side-by-side"
            )

        pre = rec.get("consensus_pre_print_bcf")
        if pre is None:
            rec["consensus_pre_print_bcf"] = val
            rec["consensus_pre_print_snapshot_utc"] = row["observed_at_utc"]
        elif abs(float(pre) - val) > 1e-9:
            notes.append(
                f"{rel}: preserved existing strictly-pre-print value {float(pre):+g} Bcf; "
                f"collector evidence remains in estimates"
            )

        if rec.get("n_estimates") is None:
            rec["n_estimates"] = sum(
                isinstance(e.get("value_bcf"), (int, float)) for e in estimates
            )
        vals = [float(e["value_bcf"]) for e in estimates if isinstance(e.get("value_bcf"), (int, float))]
        if rec.get("house_disagreement_bcf") is None and len(vals) >= 2:
            rec["house_disagreement_bcf"] = round(max(vals) - min(vals), 3)

        if actuals.get(rel) is not None:
            rec["actual_current_vintage_bcf"] = actuals[rel]

    reports.sort(key=lambda r: str(r.get("print_date")))
    dates = [str(r.get("print_date")) for r in reports]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise M13InvariantError("storage reports are not unique and strictly print-date ordered")
    return merged, notes


def _load_eia_actuals(path: Path = EIA_PATH) -> dict[str, float | None]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    ng = raw.get("KXNATGASD") or {}
    return {str(k): v.get("actual") for k, v in ng.items() if isinstance(v, dict)}


def _atomic_json_write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def recover_storage_consensus(through: str) -> list[dict]:
    if not STORAGE_PATH.exists():
        raise M13InvariantError(
            f"{STORAGE_PATH} missing after substrate restore; refusing to synthesize a replacement history"
        )
    evidence_doc = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    rows = validate_evidence_rows(evidence_doc.get("rows") or [], through)
    max_evidence = max(dt.date.fromisoformat(r["release_date"]) for r in rows)
    if dt.date.fromisoformat(through) > max_evidence:
        raise M13InvariantError(
            f"--through {through} exceeds latest blind-safe evidence {max_evidence}; "
            "collect a newer pre-print vintage instead of extrapolating"
        )
    store = json.loads(STORAGE_PATH.read_text(encoding="utf-8"))
    merged, notes = merge_storage_consensus(store, rows, _load_eia_actuals())
    _atomic_json_write(STORAGE_PATH, merged)
    for note in notes:
        _log(f"storage {note}")
    subprocess.run([sys.executable, str(HERE / "storage_consensus.py"), "--selftest"], check=True)
    return rows


def _ymd_to_iso(ymd: str) -> str:
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"


def refresh_weather_stores(build_start: str, through: str) -> None:
    """Extend existing public MOS inputs and run the two existing derived-store builders."""
    fetch_start_d = dt.date.fromisoformat(build_start) - dt.timedelta(days=2)
    through_d = dt.date.fromisoformat(through)
    fetch_end_d = through_d + dt.timedelta(days=8)
    build_end_d = through_d + dt.timedelta(days=1)
    fetch_start, fetch_end = fetch_start_d.isoformat(), fetch_end_d.isoformat()
    build_end = build_end_d.isoformat()

    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import nws_temp_feed as nws

    _log(
        f"refreshing demand MOS raw {fetch_start}..{fetch_end} "
        f"({len(nws.STATION_WEIGHTS_RAW)} metros x {len(nws.MOS_MODEL_ORDER)} models)"
    )
    for station in nws.STATION_WEIGHTS_RAW:
        for model in nws.MOS_MODEL_ORDER:
            rows = nws.load_mos_cached(station, model, fetch_start, fetch_end, refresh=False)
            if not rows:
                raise M13InvariantError(f"MOS raw refresh returned zero rows for {station}/{model}")

    import mos_cycle_feed as mos_cycle
    mos_cycle._RUNS_CACHE.clear()
    mos_cycle.build(build_start, build_end)

    import freeze_risk_feed as freeze
    _log(f"refreshing producing-basin MOS raw {fetch_start}..{fetch_end}")
    freeze.pull(fetch_start, fetch_end)
    freeze._RUNS_CACHE.clear()
    freeze.build(build_start, build_end)


def validate_local_coverage(gid: str, evidence_rows: Iterable[dict]) -> dict:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import group_config as gc

    days = list(gc.GROUPS[gid]["days"])
    cycle = json.loads(MOS_CYCLE_PATH.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))

    for ymd in days:
        iso = _ymd_to_iso(ymd)
        c = cycle.get(iso)
        if not isinstance(c, dict) or not isinstance(c.get("weekday_open"), dict):
            raise M13InvariantError(f"weather_forecast_cycle missing weekday_open on {ymd}")
        h0 = (c["weekday_open"].get("horizons") or [{}])[0]
        if h0.get("gw_hdd") is None or h0.get("gw_cdd") is None:
            raise M13InvariantError(f"weather_forecast_cycle D+0 null on {ymd}: {h0}")

        f = freeze.get(iso)
        if not isinstance(f, dict) or not isinstance(f.get("weekday_open"), dict):
            raise M13InvariantError(f"freeze_risk missing weekday_open on {ymd}")
        basins = f["weekday_open"].get("basins") or {}
        if not basins:
            raise M13InvariantError(f"freeze_risk has no basins on {ymd}")
        for station, basin in basins.items():
            h = basin.get("horizons") or []
            if not h or h[0].get("tmin_f") is None:
                raise M13InvariantError(f"freeze_risk {station} D+0 null on {ymd}")

    import storage_consensus as sc
    sc._CACHE = {"store": None, "surprise": None}
    for ymd in days:
        iso = _ymd_to_iso(ymd)
        view = sc.storage_consensus_asof(iso)
        if not isinstance(view, dict):
            raise M13InvariantError(f"storage_consensus empty on {ymd}")
        nxt, last = view.get("next_print"), view.get("last_print")
        if not isinstance(nxt, dict) or nxt.get("consensus_chg_bcf") is None:
            raise M13InvariantError(f"storage_consensus next_print consensus missing on {ymd}")
        if not isinstance(last, dict) or last.get("consensus_chg_bcf") is None:
            raise M13InvariantError(f"storage_consensus last_print consensus missing on {ymd}")

    raw_store = json.loads(STORAGE_PATH.read_text(encoding="utf-8"))
    by_print = {r.get("print_date"): r for r in raw_store.get("reports", [])}
    for ev in evidence_rows:
        rec = by_print.get(ev["release_date"])
        if rec is None:
            raise M13InvariantError(f"recovered storage report {ev['release_date']} missing")
        found = any(
            e.get("pre_print") is True
            and e.get("workflow_run_id") == int(ev["workflow_run_id"])
            and e.get("workflow_job_id") == int(ev["workflow_job_id"])
            and e.get("value_bcf") == float(ev["consensus_bcf"])
            and e.get("snapshot_utc") == ev["observed_at_utc"]
            for e in rec.get("estimates", [])
        )
        if not found:
            raise M13InvariantError(
                f"{ev['release_date']}: exact point-in-time pre-print evidence not carried in store"
            )

    return {
        "gid": gid,
        "days": len(days),
        "weather_forecast_cycle": "PASS",
        "freeze_risk": "PASS",
        "storage_consensus": "PASS",
    }


def _source_files(src: Path) -> list[tuple[Path, str]]:
    if src.is_file():
        return [(src, src.name)]
    files: list[tuple[Path, str]] = []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src).as_posix()
        if rel == "manifest.json":
            continue
        files.append((path, rel))
    if not files:
        raise M13InvariantError(f"nothing to push/read back under {src}")
    return files


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_s3_readback(prefix: str, src: Path, s3) -> dict:
    """D47: remote GET every pushed source file and require exact byte equality by SHA256."""
    local = _source_files(src)
    for path, rel in local:
        local_bytes = path.read_bytes()
        try:
            remote_bytes = s3.get_object(Bucket=BUCKET, Key=prefix + rel)["Body"].read()
        except Exception as exc:
            raise M13InvariantError(f"D47 missing/unreadable s3://{BUCKET}/{prefix}{rel}: {exc}") from exc
        if _sha256(local_bytes) != _sha256(remote_bytes):
            raise M13InvariantError(f"D47 SHA256 mismatch for {prefix}{rel}")

    try:
        manifest = json.loads(
            s3.get_object(Bucket=BUCKET, Key=prefix + "manifest.json")["Body"].read()
        )
    except Exception as exc:
        raise M13InvariantError(f"D47 manifest unreadable for {prefix}: {exc}") from exc
    local_rels = sorted(rel for _, rel in local)
    if sorted(manifest.get("files") or []) != local_rels:
        raise M13InvariantError(
            f"D47 manifest file list mismatch for {prefix}: "
            f"remote={sorted(manifest.get('files') or [])} local={local_rels}"
        )
    if manifest.get("object_count") != len(local_rels):
        raise M13InvariantError(
            f"D47 manifest object_count {manifest.get('object_count')} != {len(local_rels)} for {prefix}"
        )
    return {"prefix": prefix, "files": len(local_rels), "sha256_readback": "PASS"}


def push_and_read_back() -> list[dict]:
    for prefix, src in PUSHES:
        subprocess.run(
            [
                sys.executable,
                str(HERE / "platform_sync.py"),
                "push",
                "--prefix",
                prefix,
                "--src",
                str(src),
                "--execute",
                "--note",
                "M-13 S126 current-store recovery; existing builders; blind-safe storage vintages",
            ],
            check=True,
        )
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import creds
    s3 = creds.aws_client("s3", REGION)
    return [verify_s3_readback(prefix, src, s3) for prefix, src in PUSHES]


def validate_rehearsal_state(gid: str) -> dict:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import group_config as gc
    import state_health

    state_path = RENDER_DIR / f"grp{gid[1:]}_state{REHEARSAL_SUFFIX}.json"
    if not state_path.exists():
        raise M13InvariantError(f"rehearsal state missing: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    audit = state_health.audit(state)
    if audit.get("hard"):
        raise M13InvariantError(f"rehearsal state-health hard failures: {audit['hard']}")

    blocks = ("storage_consensus", "weather_forecast_cycle", "freeze_risk")
    for ymd in gc.GROUPS[gid]["days"]:
        rec = state.get(ymd)
        if not isinstance(rec, dict):
            raise M13InvariantError(f"rehearsal state missing day {ymd}")
        for block in blocks:
            value = rec.get(block)
            if value is None or value == {} or value == []:
                raise M13InvariantError(f"rehearsal {ymd}: {block} empty")
    return {"gid": gid, "state_health_hard": 0, "m13_blocks": "PASS", "state": str(state_path)}


def run(gid: str, through: str, execute: bool) -> dict:
    if not execute:
        raise M13InvariantError(
            "refusing to mutate the S3 data plane without --execute; this wrapper is fail-closed"
        )
    os.chdir(REPO)
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import group_config as gc

    if gid not in gc.GROUPS:
        raise M13InvariantError(f"unknown group {gid}")
    group_dates = [dt.date(int(d[:4]), int(d[4:6]), int(d[6:])) for d in gc.GROUPS[gid]["days"]]
    through_d = dt.date.fromisoformat(through)
    if through_d < max(group_dates):
        raise M13InvariantError(
            f"--through {through} ends before {gid}'s last day {max(group_dates)}"
        )
    build_start = min(group_dates).isoformat()

    _log("restoring existing private substrate (no group stage yet)")
    subprocess.run([sys.executable, str(HERE / "restore_substrate.py")], check=True)

    evidence = recover_storage_consensus(through)
    refresh_weather_stores(build_start, through)
    local = validate_local_coverage(gid, evidence)
    _log(f"local coverage gate PASS: {local}")

    readback = push_and_read_back()
    _log(f"D47 remote read-back PASS: {readback}")

    _log(f"running canonical suffixed rehearsal stage for {gid}")
    subprocess.run(
        [
            sys.executable,
            str(HERE / "stage_group.py"),
            gid,
            "--suffix",
            REHEARSAL_SUFFIX,
        ],
        check=True,
    )
    rehearsal = validate_rehearsal_state(gid)
    result = {
        "gid": gid,
        "through": through,
        "evidence_rows": len(evidence),
        "local": local,
        "readback": readback,
        "rehearsal": rehearsal,
    }
    print(
        f"PASS: M-13 {gid} stores rebuilt, S3 SHA256 read-back verified, "
        f"staged state health hard=0",
        flush=True,
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="M-13 S126 stale-store recovery")
    ap.add_argument("gid", nargs="?", default="g24")
    ap.add_argument("--through", default="2026-08-13")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    try:
        run(args.gid, args.through, args.execute)
    except (M13InvariantError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: M-13 recovery stopped: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
