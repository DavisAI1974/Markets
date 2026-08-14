"""
consensus_poll.py — accrue forward STREET CONSENSUS (forecast) + ACTUAL for the
scheduled releases our Kalshi contracts key on. This is the SURPRISE axis
(surprise = actual - forecast) the coupling/bucketing work needs, and it is only
obtainable FORWARD (there is no free historical consensus archive), so we start
accruing now and let it build.

Source: the free ForexFactory weekly economic-calendar JSON (faireconomy mirror).
Verified live to carry `forecast`/`previous`/`actual` for USD "Crude Oil
Inventories", "Natural Gas Storage", CPI, Non-Farm Employment, FOMC, PCE, etc.

Cadence: run at least twice around each release week — once BEFORE releases to
capture `forecast`, once AFTER to capture `actual`. Idempotent: keyed by
(title, date); re-polls fill in `actual` and refresh. Stdlib-only (runs in GHA
with no pip, like kalshi_collector.py).

S128: preserve `forecast_history` with an observed-at timestamp. The old store
kept only the latest forecast plus first/last poll times, which meant a later
forecast revision could not safely be served back at an earlier blind cutoff.
History is append-only by changed forecast value. Existing legacy rows are
seeded conservatively at their LAST poll time, never their first poll time, so
we do not back-date a value whose earlier vintage is unknown.

Usage:
    python research/kalshi/consensus_poll.py                       # poll + merge
    python research/kalshi/consensus_poll.py --out data/kalshi/consensus.jsonl
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FEED = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# ForexFactory event title (substring, lowercased) -> Kalshi series it bears on.
# Keep this the surprise->contract map; mirrors news_ingest CONTRACT_KEYWORDS intent.
TITLE_TO_SERIES = {
    "crude oil inventories": ["KXWTI", "KXBRENTD"],
    "natural gas storage": ["KXNATGASD"],
    "cpi m/m": ["KXCPIYOY", "KXCPICOREA"],
    "cpi y/y": ["KXCPIYOY"],
    "core cpi": ["KXCPICOREA"],
    "core pce": ["PCECORE"],
    "pce price": ["PCECORE"],
    "non-farm employment": ["KXUSNFP"],
    "nonfarm": ["KXUSNFP"],
    "unemployment rate": ["KXUSNFP"],
    "federal funds rate": ["KXFEDHIKE", "KXEFFR", "RATECUTS"],
    "fomc statement": ["KXFEDHIKE"],
    "fomc": ["KXFEDHIKE"],
}


def _series_for(title: str) -> list[str]:
    t = (title or "").lower()
    hit: list[str] = []
    for key, series in TITLE_TO_SERIES.items():
        if key in t:
            for s in series:
                if s not in hit:
                    hit.append(s)
    return hit


def fetch_feed(url: str = FEED, timeout: float = 20.0) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


def load_store(path: Path) -> dict[str, dict]:
    """keyed by f'{title}|{date}' -> record (JSONL, one row per key)."""
    store: dict[str, dict] = {}
    if not path.exists():
        return store
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        store[f"{r.get('title')}|{r.get('date')}"] = r
    return store


def _forecast_history(prev: dict | None, forecast, now: str) -> list[dict]:
    """Append-only changed-value snapshots; never back-date a legacy value."""
    history = [dict(x) for x in ((prev or {}).get("forecast_history") or []) if isinstance(x, dict)]
    if not history and prev and prev.get("forecast") not in (None, ""):
        # Conservative migration: last_polled_at is the latest time we can PROVE this stored
        # value existed. first_polled_at would incorrectly imply the final/revised forecast was
        # already known on the first poll.
        observed = prev.get("last_polled_at")
        if observed:
            history.append({"forecast": prev.get("forecast"), "observed_at": observed,
                            "migration": "legacy_value_seeded_at_last_poll"})
    if forecast in (None, ""):
        return history
    if not history or history[-1].get("forecast") != forecast:
        history.append({"forecast": forecast, "observed_at": now})
    return history


def main() -> None:
    p = argparse.ArgumentParser(description="Poll + accrue forward release consensus/actual")
    p.add_argument("--out", default="data/kalshi/consensus.jsonl")
    p.add_argument("--all", action="store_true", help="keep every event, not just mapped-to-a-series ones")
    args = p.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    store = load_store(out)

    events = fetch_feed()
    now = datetime.now(timezone.utc).isoformat()
    n_new = n_upd = n_actual = 0
    for e in events:
        title = e.get("title", "")
        series = _series_for(title)
        if not series and not args.all:
            continue
        key = f"{title}|{e.get('date')}"
        prev = store.get(key)
        forecast = e.get("forecast") or None
        rec = {
            "title": title,
            "country": e.get("country"),
            "date": e.get("date"),
            "impact": e.get("impact"),
            "forecast": forecast,
            "forecast_history": _forecast_history(prev, forecast, now),
            "previous": e.get("previous") or None,
            "actual": e.get("actual") or None,
            "series": series,
            "first_polled_at": (prev or {}).get("first_polled_at", now),
            "last_polled_at": now,
        }
        if prev is None:
            n_new += 1
        else:
            if rec["actual"] and not prev.get("actual"):
                n_actual += 1
            if rec != {**prev, "last_polled_at": now}:
                n_upd += 1
        store[key] = rec

    # rewrite the JSONL sorted by date
    rows = sorted(store.values(), key=lambda r: (r.get("date") or "", r.get("title") or ""))
    out.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))
    mapped = sum(1 for r in rows if r.get("series"))
    print(f"[consensus] polled {len(events)} events -> store {len(rows)} rows "
          f"({mapped} mapped to a series); new={n_new} updated={n_upd} newly-actual={n_actual}")
    # show the release-relevant rows this poll
    for r in rows:
        if r.get("series"):
            print(f"  {r['date']}  {r['title']:<26} fc={str(r['forecast']):>7} "
                  f"prev={str(r['previous']):>7} actual={str(r['actual']):>7} -> {','.join(r['series'])}")


if __name__ == "__main__":
    main()
