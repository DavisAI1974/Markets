from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


# S78 Kalshi repoint: macro / energy / weather feeds (was CoinDesk/Cointelegraph/ETH).
# PRIMARY = government release source. Reachability from this environment noted inline;
# BLS blocks datacenter IPs (403 even with a browser UA) -> kept for box-side/other-IP
# runs, skipped gracefully here. The news-coupling thread targets the EIA-energy,
# Fed/CPI-macro, and NHC-hurricane contracts; the daily-high-temp city contracts are
# served by the OD-weather thread, not by RSS news.
DEFAULT_FEEDS = [
    {"source": "EIA Today in Energy", "source_quality": "PRIMARY",
     "url": "https://www.eia.gov/rss/todayinenergy.xml"},          # live (200)
    {"source": "EIA Press", "source_quality": "PRIMARY",
     "url": "https://www.eia.gov/rss/press_rss.xml"},              # live (200)
    {"source": "Federal Reserve Press (all)", "source_quality": "PRIMARY",
     "url": "https://www.federalreserve.gov/feeds/press_all.xml"}, # live (200)
    {"source": "Federal Reserve Monetary", "source_quality": "PRIMARY",
     "url": "https://www.federalreserve.gov/feeds/press_monetary.xml"},  # live (200)
    {"source": "NOAA NHC Atlantic", "source_quality": "PRIMARY",
     "url": "https://www.nhc.noaa.gov/index-at.xml"},              # live (200) hurricanes
    {"source": "BLS Employment Situation", "source_quality": "PRIMARY",
     "url": "https://www.bls.gov/feed/empsit.rss"},                # 403 from datacenter IPs
    {"source": "BLS CPI", "source_quality": "PRIMARY",
     "url": "https://www.bls.gov/feed/cpi.rss"},                   # 403 from datacenter IPs
]

# Contract-keyword map (was BTC_TERMS/ETH_TERMS). Each Kalshi series -> a regex; a news
# item that matches tags that series in `assets`. EXTEND with Greg's domain edge (esp.
# energy contracts once added to the collector watchlist). Downstream (coupling) is
# unchanged: `assets` now holds Kalshi series tickers instead of BTC/ETH.
CONTRACT_KEYWORDS: dict[str, "re.Pattern[str]"] = {
    # --- macro scheduled prints (clean news->outcome causal events) ---
    "KXUSNFP":    re.compile(r"\b(nonfarm|payroll|jobs report|employment situation|jobless|labor market)\b", re.I),
    "KXCPIYOY":   re.compile(r"\b(cpi|consumer price|inflation)\b", re.I),
    "KXCPICOREA": re.compile(r"\bcore (cpi|inflation)\b", re.I),
    "PCECORE":    re.compile(r"\b(pce|core pce|personal consumption expenditure)\b", re.I),
    "KXFEDHIKE":  re.compile(r"\b(fomc|federal reserve|fed\b|powell|rate (hike|decision|increase))\b", re.I),
    "RATECUTS":   re.compile(r"\b(rate cut|fed cut|easing|dovish)\b", re.I),
    "KXEFFR":     re.compile(r"\b(fed funds|effr|federal funds rate)\b", re.I),
    # --- energy price contracts (EIA feed; Greg's domain edge) ---
    "KXWTI":      re.compile(r"\b(wti|west texas|crude|oil price|petroleum|opec|barrel|rig count)\b", re.I),
    "KXBRENTD":   re.compile(r"\b(brent|crude|oil price|opec|barrel)\b", re.I),
    "KXNATGASD":  re.compile(r"\b(natural gas|nat gas|natgas|henry hub|gas storage|lng)\b", re.I),
    "KXAAAGASD":  re.compile(r"\b(gasoline|gas price|pump price|retail gas)\b", re.I),
    # --- hurricanes / tropical (NHC feed) ---
    "KXTROPSTORM": re.compile(r"\b(tropical storm|tropical depression|named storm|hurricane|cyclone)\b", re.I),
    # --- weather daily-high cities: mostly OD-driven, tagged only on heat-wave macro news ---
    "KXHIGHNY":   re.compile(r"\b(new york|nyc|central park)\b", re.I),
    "KXHIGHCHI":  re.compile(r"\bchicago\b", re.I),
    "KXHIGHTPHX": re.compile(r"\bphoenix\b", re.I),
    # TODO(greg): add EIA energy contracts (crude/natgas storage, gasoline) once on the watchlist.
}

BEARISH_TERMS = re.compile(
    r"\b(hotter|higher|rose|rise|jump|surge|accelerat|beat|hawkish|above forecast|"
    r"tighten|hike|elevated|sticky|shortfall|draw|deficit|storm|warning|risk)\b",
    re.I,
)
BULLISH_TERMS = re.compile(
    r"\b(cooler|lower|fell|drop|ease|eased|slow|decelerat|miss|dovish|below forecast|"
    r"cut|soft|cooling|surplus|build|glut|calm|clear)\b",
    re.I,
)
NUMERIC_SIZE_TERMS = re.compile(r"(\$?\d+(?:\.\d+)?\s?(?:billion|million|bn|m|%|bps|bp))", re.I)
FOLLOWUP_TERMS = re.compile(r"\b(update|recap|follow-up|reaction|after|amid|continues|latest)\b", re.I)


def nlp_features(title: str, summary: str) -> dict[str, Any]:
    text = f"{title} {summary}"
    bearish = len(BEARISH_TERMS.findall(text))
    bullish = len(BULLISH_TERMS.findall(text))
    magnitude = max(-75, min(75, (bullish - bearish) * 10))
    if NUMERIC_SIZE_TERMS.search(text):
        magnitude *= 1.25
    return {
        "is_followup": bool(FOLLOWUP_TERMS.search(text)),
        "has_numeric_size": bool(NUMERIC_SIZE_TERMS.search(text)),
        "magnitude_bps_hint": int(round(magnitude)),
    }


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _parse_dt(text: str) -> datetime | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
    except Exception:
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _text_of(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _link_of(node: ET.Element) -> str:
    link = _text_of(node, ["link"])
    if link:
        return link
    for child in node:
        if child.tag.endswith("link") and child.attrib.get("href"):
            return child.attrib["href"].strip()
    return ""


def _fetch(url: str, timeout_s: float) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MarketsWatchNewsIngest/0.1 (+daily research)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read()


def _iter_feed_items(xml_bytes: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    out = []
    for item in items:
        title = _text_of(item, ["title", "{http://www.w3.org/2005/Atom}title"])
        summary = _text_of(item, [
            "description",
            "summary",
            "{http://www.w3.org/2005/Atom}summary",
            "{http://www.w3.org/2005/Atom}content",
        ])
        published = _text_of(item, [
            "pubDate",
            "published",
            "updated",
            "{http://www.w3.org/2005/Atom}published",
            "{http://www.w3.org/2005/Atom}updated",
        ])
        out.append({
            "title": _strip_html(title),
            "summary": _strip_html(summary),
            "url": _link_of(item),
            "published_at": published,
        })
    return out


def classify_item(title: str, summary: str) -> dict[str, Any]:
    text = f"{title} {summary}"
    # `assets` now holds the Kalshi series ticker(s) the item bears on (contract map).
    assets = [series for series, rx in CONTRACT_KEYWORDS.items() if rx.search(text)]
    bearish = len(BEARISH_TERMS.findall(text))
    bullish = len(BULLISH_TERMS.findall(text))
    if bullish > bearish:
        bias = "BULLISH"
    elif bearish > bullish:
        bias = "BEARISH"
    elif bullish or bearish:
        bias = "MIXED"
    else:
        bias = "UNKNOWN"
    # Macro/energy/weather categories (was crypto ETF/SECURITY/PROTOCOL/EXCHANGE).
    category = "UNKNOWN"
    lowered = text.lower()
    if any(k in lowered for k in ("crude", "petroleum", "natural gas", "gasoline", "opec", "barrel", "storage", "inventory", "energy")):
        category = "ENERGY"
    elif any(k in lowered for k in ("cpi", "pce", "inflation", "price index")):
        category = "INFLATION"
    elif any(k in lowered for k in ("payroll", "employment", "unemployment", "jobless", "labor")):
        category = "JOBS"
    elif any(k in lowered for k in ("fomc", "federal reserve", "powell", "rate cut", "rate hike", "fed funds", "monetary")):
        category = "MONETARY"
    elif any(k in lowered for k in ("hurricane", "tropical storm", "cyclone", "landfall")):
        category = "HURRICANE"
    elif any(k in lowered for k in ("temperature", "heat wave", "heatwave", "record high", "forecast")):
        category = "WEATHER"
    confidence = 0.55 if assets else 0.25
    if bias in {"BULLISH", "BEARISH"}:
        confidence += 0.1
    # Scheduled prints + storm warnings are the shock events that gate new entries.
    trade_starter_candidate = category in {"INFLATION", "JOBS", "MONETARY", "ENERGY", "HURRICANE"} and bias in {"BULLISH", "BEARISH"}
    starter_actions = []
    if trade_starter_candidate:
        starter_actions.append("PAUSE_NEW_ENTRIES")
        if bias == "BEARISH":
            starter_actions.extend(["EXIT_LONGS_IF_UNCONFIRMED", "ALLOW_HEDGE_SHORT", "START_SHORT_IF_CONFIRMED"])
        elif bias == "BULLISH":
            starter_actions.extend(["EXIT_SHORTS_IF_UNCONFIRMED", "ALLOW_HEDGE_LONG", "START_LONG_IF_CONFIRMED"])
    features = nlp_features(title, summary)
    if features["has_numeric_size"]:
        confidence += 0.05
    if features["is_followup"]:
        confidence -= 0.05
    return {
        "assets": assets,
        "directional_bias": bias,
        "category": category,
        "confidence": min(1.0, confidence),
        "impact": 0.5 if assets else 0.2,
        "trade_starter_candidate": trade_starter_candidate,
        "starter_actions": starter_actions,
        "nlp_features": features,
    }


def event_id_for(source: str, url: str, title: str) -> str:
    key = f"{source}|{url}|{title}".encode("utf-8", errors="ignore")
    return hashlib.sha1(key).hexdigest()[:16]


def load_seen(path: Path) -> set[str]:
    seen = set()
    if not path.exists():
        return seen
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("event_id"):
                seen.add(str(row["event_id"]))
            if row.get("dedupe_key"):
                seen.add(str(row["dedupe_key"]))
    return seen


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="news_events.jsonl")
    p.add_argument("--raw-output", default="news_raw_ingest.jsonl")
    p.add_argument("--feeds", default="", help="Optional JSON file of feed objects.")
    p.add_argument("--lookback-hours", type=float, default=36.0)
    p.add_argument("--timeout-s", type=float, default=12.0)
    p.add_argument("--include-unknown-assets", action="store_true")
    args = p.parse_args()

    feeds = DEFAULT_FEEDS
    if args.feeds:
        with open(args.feeds, encoding="utf-8") as f:
            feeds = json.load(f)

    out_path = Path(args.output)
    raw_path = Path(args.raw_output)
    seen = load_seen(out_path)
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - args.lookback_hours * 3600.0
    new_events = 0
    raw_items = 0

    with out_path.open("a", encoding="utf-8") as out_f, raw_path.open("a", encoding="utf-8") as raw_f:
        for feed in feeds:
            source = str(feed["source"])
            url = str(feed["url"])
            quality = str(feed.get("source_quality") or "TRUSTED_MEDIA").upper()
            try:
                items = _iter_feed_items(_fetch(url, args.timeout_s))
            except Exception as e:
                print(f"[news-ingest] fetch failed {source}: {e}", flush=True)
                continue
            for item in items:
                raw_items += 1
                published_dt = _parse_dt(item.get("published_at", "")) or now
                raw_record = {
                    "source": source,
                    "source_quality": quality,
                    "feed_url": url,
                    "retrieved_at": now.isoformat(),
                    **item,
                    "published_at_iso": published_dt.isoformat(),
                }
                raw_f.write(json.dumps(raw_record, ensure_ascii=True) + "\n")
                if published_dt.timestamp() < cutoff:
                    continue
                title = item.get("title", "")
                summary = item.get("summary", "")
                classified = classify_item(title, summary)
                if not classified["assets"] and not args.include_unknown_assets:
                    continue
                eid = event_id_for(source, item.get("url", ""), title)
                dedupe = hashlib.sha1((item.get("url", "") or title).encode("utf-8", errors="ignore")).hexdigest()[:16]
                if eid in seen or dedupe in seen:
                    continue
                seen.add(eid)
                seen.add(dedupe)
                event = {
                    "event_id": eid,
                    "published_at": published_dt.isoformat(),
                    "first_seen_at": now.isoformat(),
                    "source": source,
                    "source_quality": quality,
                    "url": item.get("url", ""),
                    "title": title,
                    "assets": classified["assets"],
                    "category": classified["category"],
                    "directional_bias": classified["directional_bias"],
                    "confidence": classified["confidence"],
                    "impact": classified["impact"],
                    "summary": summary[:500],
                    "dedupe_key": dedupe,
                    "classifier": "keyword_v0+nlp_v1",
                    "nlp_features": classified["nlp_features"],
                    "trade_starter_candidate": classified["trade_starter_candidate"],
                    "starter_actions": classified["starter_actions"],
                }
                out_f.write(json.dumps(event, ensure_ascii=True) + "\n")
                new_events += 1

    print(f"[news-ingest] raw_items={raw_items} new_events={new_events} output={out_path}")


if __name__ == "__main__":
    main()
