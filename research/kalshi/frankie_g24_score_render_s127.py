#!/usr/bin/env python3
"""Score and render the fully-frozen ChatGPT-operated Frankie g24 blind run.

Outcome access is deliberately delayed until ALL ten blind day artifacts exist and validate under
S121. This script never writes or edits a blind forecast. It reads the realized g24 artifact only
after the full freeze gate passes, then emits a score JSON and one post-reveal comparison PNG.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import group_config as gc
import frankie_s121_curve_restore as s121

HERE = Path(__file__).resolve().parent
RENDERS = HERE / "renders" / "ng_refine_s95"
FORECASTS = HERE / "forecasts"
GID = "g24"
NAMESPACE = "frankie_g24_s127_chatgpt"
MULT = 10000.0
ET = ZoneInfo("America/New_York")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def forecast_path(day: str, owner: str) -> Path:
    return FORECASTS / NAMESPACE / f"grp24_{owner}_{day}.json"


def freeze_gate() -> list[dict]:
    """Validate every blind artifact before outcome access begins."""
    rows = []
    owners = gc.owner_map(GID)
    for day in gc.GROUPS[GID]["days"]:
        owner = owners[day]
        path = forecast_path(day, owner)
        if not path.is_file():
            raise RuntimeError(f"BLIND_GROUP_INCOMPLETE: missing {path.relative_to(HERE)}")
        payload = read_json(path)
        s121.validate_day(payload, GID, day, owner)
        rows.append(payload)
    if len(rows) != 10:
        raise RuntimeError(f"BLIND_GROUP_INCOMPLETE: expected 10 validated days, got {len(rows)}")
    return rows


def score(forecasts: list[dict]) -> dict:
    # OUTCOME ACCESS STARTS HERE, after the full blind freeze gate above.
    actual = read_json(RENDERS / "g24_actual.json")
    old = read_json(FORECASTS / "grp24.json")
    actual_by_day = {str(r["date"]): r for r in actual["days"]}
    old_by_day = {str(r["date"]): r for r in old["days"]}

    events = []
    for p in forecasts:
        day = str(p["date"]).replace("-", "")
        a = actual_by_day[day]
        oldrow = old_by_day.get(day, {})
        guess = float(p["guessed_net_usd"])
        aval = float(a["day_move_usd"])
        old_guess = float(oldrow.get("guess_day_move_usd", oldrow.get("guessed_net_usd", 0)) or 0)
        direction_ok = ((guess > 0) == (aval > 0)) if aval != 0 else guess == 0
        old_direction_ok = ((old_guess > 0) == (aval > 0)) if aval != 0 else old_guess == 0
        events.append({
            "day": day,
            "owner": p["specialist"],
            "disposition": str(p.get("disposition", "CALL")).upper(),
            "confidence": str(p.get("confidence", "")).lower(),
            "frankie_guess_usd": guess,
            "frankie_gap_usd": float(p.get("overnight_gap_usd", 0) or 0),
            "actual_day_move_usd": aval,
            "actual_gap_usd": float(a.get("gap_usd", 0) or 0),
            "frankie_error_usd": guess - aval,
            "frankie_abs_error_usd": abs(guess - aval),
            "frankie_direction_ok": direction_ok,
            "old_blind_guess_usd": old_guess,
            "old_blind_abs_error_usd": abs(old_guess - aval),
            "old_blind_direction_ok": old_direction_ok,
        })

    calls = [r for r in events if r["disposition"] == "CALL"]
    abstains = [r for r in events if r["disposition"] == "ABSTAIN"]
    n = len(events)
    mae = sum(r["frankie_abs_error_usd"] for r in events) / n
    rmse = math.sqrt(sum(r["frankie_error_usd"] ** 2 for r in events) / n)
    report = {
        "schema_version": "s127.score.1",
        "group": GID,
        "namespace": NAMESPACE,
        "blind_frozen_before_reveal": True,
        "n": n,
        "metrics": {
            "frankie_mae_usd": round(mae, 1),
            "frankie_median_abs_error_usd": sorted(r["frankie_abs_error_usd"] for r in events)[n // 2 - 1:n // 2 + 1],
            "frankie_rmse_usd": round(rmse, 1),
            "frankie_direction_hits_all_p50": sum(bool(r["frankie_direction_ok"]) for r in events),
            "frankie_total_p50_days": n,
            "call_count": len(calls),
            "call_direction_hits": sum(bool(r["frankie_direction_ok"]) for r in calls),
            "call_mae_usd": round(sum(r["frankie_abs_error_usd"] for r in calls) / len(calls), 1),
            "abstain_count": len(abstains),
            "abstain_p50_mae_usd": round(sum(r["frankie_abs_error_usd"] for r in abstains) / len(abstains), 1),
            "frankie_block_sum_guess_usd": round(sum(r["frankie_guess_usd"] for r in events), 1),
            "actual_block_sum_usd": round(sum(r["actual_day_move_usd"] for r in events), 1),
            "old_blind_mae_usd": float(old.get("mean_abs_err_usd", 0)),
            "old_blind_direction_hits": int(old.get("dir_hits", 0)),
            "old_blind_n": int(old.get("n", 0)),
            "frankie_minus_old_mae_usd": round(mae - float(old.get("mean_abs_err_usd", 0)), 1),
        },
        "events": events,
    }
    return report


def session_pos(raw) -> float:
    if isinstance(raw, str):
        hh, mm = raw.split(":")
        h = int(hh) + int(mm) / 60.0
        if raw == "24:00":
            return 24.0
    else:
        h = float(raw)
        if abs(h - 24.0) < 1e-12:
            return 24.0
    return h - 20.0 if h >= 20.0 else h + 4.0


def render(forecasts: list[dict], score_report: dict) -> Path:
    actual = read_json(RENDERS / "g24_actual.json")
    anchor = float(actual["anchor"])
    seam = str(actual.get("seam") or "")
    seam_offset = float(actual.get("seam_offset", 0) or 0)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    cont = actual["continuous"]
    ax_x = [datetime.fromtimestamp(float(t), tz=ZoneInfo("UTC")).astimezone(ET) for t, _ in cont]
    ax_y = [float(px) for _, px in cont]

    fx: list[datetime] = []
    fy: list[float] = []
    running_cum = 0.0
    disposition_by_day = {}
    for p in forecasts:
        day = str(p["date"]).replace("-", "")
        disposition_by_day[day] = str(p.get("disposition", "CALL")).upper()
        y, m, d = int(day[:4]), int(day[4:6]), int(day[6:])
        start = datetime(y, m, d, 20, 0, tzinfo=ET) - timedelta(days=1)
        gap = float(p.get("overnight_gap_usd", 0) or 0)
        open_cum = running_cum + gap
        roll = seam_offset if seam and day >= seam else 0.0
        for raw_t, cum in p["path_p50_curve"]:
            pos = session_pos(raw_t)
            fx.append(start + timedelta(hours=pos))
            fy.append(anchor + (open_cum + float(cum)) / MULT + roll)
        running_cum += float(p["guessed_net_usd"])
        # break forecast line between sessions
        fx.append(start + timedelta(hours=24, seconds=1))
        fy.append(float("nan"))

    fig, ax = plt.subplots(figsize=(18, 6))
    ax.plot(ax_x, ax_y, lw=0.9, label="actual RT (real traded price)")
    ax.plot(fx, fy, lw=1.7, ls="--", label="Frankie S127 blind p50")
    ax.axhline(anchor, lw=0.7, ls=":", alpha=0.7)

    ymax = max(max(ax_y), max(v for v in fy if not math.isnan(v)))
    for row in actual["days"]:
        day = str(row["date"])
        y, m, d = int(day[:4]), int(day[4:6]), int(day[6:])
        mark = datetime(y, m, d, 12, 0, tzinfo=ET)
        score_row = next(r for r in score_report["events"] if r["day"] == day)
        label = f"{day[4:6]}-{day[6:]} {score_row['owner']} {score_row['disposition']}\nF {score_row['frankie_guess_usd']:+.0f} / A {score_row['actual_day_move_usd']:+.0f}"
        ax.text(mark, ymax, label, fontsize=7, va="top", ha="center", rotation=0)
    if seam:
        y, m, d = int(seam[:4]), int(seam[4:6]), int(seam[6:])
        seam_dt = datetime(y, m, d, 0, 0, tzinfo=ET)
        ax.axvline(seam_dt, lw=1.0, ls="-.", alpha=0.8)
        ax.text(seam_dt, min(ax_y), " Q26→U26 scoring seam", fontsize=8, va="bottom")

    met = score_report["metrics"]
    ax.set_title(
        "Frankie S127 g24 — ChatGPT-operated blind forecast vs actual RT\n"
        f"MAE ${met['frankie_mae_usd']:.0f} | p50 dir {met['frankie_direction_hits_all_p50']}/{met['frankie_total_p50_days']} | "
        f"CALL dir {met['call_direction_hits']}/{met['call_count']} | old blind MAE ${met['old_blind_mae_usd']:.0f}, dir {met['old_blind_direction_hits']}/{met['old_blind_n']}"
    )
    ax.set_ylabel("NG price")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d", tz=ET))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1, tz=ET))
    ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    out = RENDERS / "g24_frankie_s127_chatgpt_render.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> int:
    forecasts = freeze_gate()
    report = score(forecasts)
    score_path = RENDERS / "g24_frankie_s127_chatgpt_score.json"
    score_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    render_path = render(forecasts, report)
    print(json.dumps({
        "blind_frozen_before_reveal": True,
        "score": str(score_path.relative_to(HERE)),
        "render": str(render_path.relative_to(HERE)),
        "metrics": report["metrics"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
