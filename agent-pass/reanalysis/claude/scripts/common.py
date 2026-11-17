"""Shared paths and helpers for the Claude Code independent reanalysis (frozen inputs only)."""
import os, pathlib, json, gzip
EV = pathlib.Path(os.environ.get("REANALYSIS_EVIDENCE", "/tmp/claude-0/-home-user-Markets/9d08bbd8-e004-5d31-9253-a2d3c0d0bcc4/scratchpad/evidence"))
OUT = pathlib.Path(os.environ.get("REANALYSIS_OUT", str(pathlib.Path(__file__).resolve().parents[1] / "tables")))
OUT.mkdir(parents=True, exist_ok=True)
DAYS = ["20231002", "20231003", "20231017", "20231018"]
TAG = {"20231002": "oct02", "20231003": "oct03", "20231017": "oct17", "20231018": "oct18"}
FR = "tasks/family-research-20261022"
NATIVE = EV / "native" / FR / "native-dipole/20261108-33693e180/agent-pass/tables"
WHOLE = EV / "whole" / FR / "whole-lifecycles/run-42573465249-1"
EVENTS = EV / "events" / FR / "combined-events/run-42571551209-1"
FAMILY = EV / "family" / FR / "family-replication/run-42566535537-1"
CONT = EV / "continuous" / FR / "four-day-extensions/run-42563528655-1"
TIER1 = EV / "tier1" / FR / "claude-code-pins/precision-fix-42592319662-1"
ROWCLOCK = EV / "rowclock" / FR / "all-row-clock-pins/run-42584823565-1"
LIFECYCLE = EV / "lifecycle" / FR / "lifecycle-data-links/run-42583801329-1"
CCODE = EV / "ccode" / FR / "claude-code"
SUITE = EV / "suite" / FR / "claude-pass-3day"
TICK_RAW = 1_000_000  # NG tick 0.001 in 1e-9 price_raw units

def jsonl(path):
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)

def qdesc(s):
    import numpy as np
    s = s.dropna()
    if len(s) == 0:
        return dict(n=0)
    return dict(n=int(len(s)), min=float(s.min()), p10=float(s.quantile(.1)), p25=float(s.quantile(.25)), p50=float(s.median()),
                p75=float(s.quantile(.75)), p90=float(s.quantile(.9)), max=float(s.max()))

def sign_counts(s):
    s = s.dropna()
    return dict(n=int(len(s)), up=int((s > 0).sum()), flat=int((s == 0).sum()), down=int((s < 0).sum()))
