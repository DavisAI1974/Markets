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


DEFAULT_FEEDS = [
    {
        "source": "CoinDesk",
        "source_quality": "TRUSTED_MEDIA",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    },
    {
        "source": "Cointelegraph",
        "source_quality": "TRUSTED_MEDIA",
        "url": "https://cointelegraph.com/rss",
    },
    {
        "source": "Ethereum Foundation Blog",
        "source_quality": "PROTOCOL_PRIMARY",
        "url": "https://blog.ethereum.org/feed.xml",
    },
]

BTC_TERMS = re.compile(r"\b(bitcoin|btc|satoshi|lightning network)\b", re.I)
ETH_TERMS = re.compile(r"\b(ethereum|ether|eth\b|staking|validator|mainnet|evm|defi)\b", re.I)
BEARISH_TERMS = re.compile(
    r"\b(hack|exploit|lawsuit|charged|probe|outflow|selloff|drop|falls|bearish|"
    r"liquidation|security|outage|ban|delay|risk|warning|crackdown)\b",
    re.I,
)
BULLISH_TERMS = re.compile(
    r"\b(approval|inflow|surge|rally|launch|rollout|adoption|upgrade|record|"
    r"accumulation|buy|bullish|partnership|integrat|support|etf)\b",
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
    assets = []
    if BTC_TERMS.search(text):
        assets.append("BTC")
    if ETH_TERMS.search(text):
        assets.append("ETH")
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
    category = "UNKNOWN"
    lowered = text.lower()
    if "etf" in lowered or "inflow" in lowered or "outflow" in lowered:
        category = "ETF"
    elif "hack" in lowered or "exploit" in lowered or "security" in lowered:
        category = "SECURITY"
    elif "sec" in lowered or "cftc" in lowered or "lawsuit" in lowered or "regulation" in lowered:
        category = "REGULATORY"
    elif "upgrade" in lowered or "mainnet" in lowered or "validator" in lowered:
        category = "PROTOCOL"
    elif "exchange" in lowered or "coinbase" in lowered or "binance" in lowered or "kraken" in lowered:
        category = "EXCHANGE"
    elif "fed" in lowered or "cpi" in lowered or "treasury" in lowered or "rates" in lowered:
        category = "MACRO"
    confidence = 0.55 if assets else 0.25
    if bias in {"BULLISH", "BEARISH"}:
        confidence += 0.1
    trade_starter_candidate = category in {"SECURITY", "REGULATORY"} and bias in {"BULLISH", "BEARISH"}
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
