"""Canonicalize Kalshi market rules and find duplicated contingent claims.

Purpose
-------
Support the Novel Edge Lab's highest-ranked structural candidate: the same economic
outcome fragmented across daily, weekly, or monthly wrappers. This module is deliberately
conservative:

- `strict_hash` preserves normalized complete rule text plus settlement identity fields.
  Only strict-hash groups are eligible for an exact-payoff review.
- `semantic_hash` uses extracted fields and is a NEAR-MATCH discovery aid only.
- executable pair output is GROSS BEFORE FEES and never labeled arbitrage automatically.
- missing source, field, clock, inequality, or strike information is surfaced as a warning.

The scanner accepts a JSON list of market objects or an object containing `markets`.
It does not call Kalshi, hold credentials, or route orders.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


SPACE_RE = re.compile(r"\s+")
TICKER_STRIKE_RE = re.compile(r"-T(-?\d+(?:\.\d+)?)$", re.I)
MONEY_STRIKE_RE = re.compile(
    r"(?:above|greater than|at or above|below|less than|at or below)\s+\$?(-?\d+(?:\.\d+)?)",
    re.I,
)
KNOWN_SOURCE_PATTERNS = [
    ("pyth", re.compile(r"\bpyth\b", re.I)),
    ("trading_economics", re.compile(r"\btrading\s+economics\b", re.I)),
    ("ice", re.compile(r"\bintercontinental\s+exchange\b|\bice\b", re.I)),
    ("cme", re.compile(r"\bchicago\s+mercantile\s+exchange\b|\bcme\b|\bnymex\b", re.I)),
    ("eia", re.compile(r"\bu\.?s\.?\s+energy\s+information\s+administration\b|\beia\b", re.I)),
    ("nws", re.compile(r"\bnational\s+weather\s+service\b|\bnws\b", re.I)),
]
KNOWN_INSTRUMENT_RE = re.compile(
    r"\b(?:NG|CL|GC|SI|HG|BZ)[FGHJKMNQUVXZ]\d{1,2}\b|\bNGD[A-Z]\d{1,2}\b|"
    r"\bXAU(?:/USD)?\b|\bXAG(?:/USD)?\b|\bWTI\b|\bBRENT\b",
    re.I,
)


@dataclass(frozen=True)
class CanonicalMarket:
    ticker: str
    event_ticker: str | None
    series_ticker: str | None
    title: str | None
    strike: float | None
    close_time_utc: str | None
    source: str | None
    source_instrument: str | None
    measured_field: str | None
    inequality: str | None
    normalized_rules: str
    strict_hash: str
    semantic_hash: str
    warnings: tuple[str, ...]
    yes_ask_dollars: float | None
    no_ask_dollars: float | None


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _text(value)).lower()
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\bp\.?m\.?\b", "pm", text)
    text = re.sub(r"\ba\.?m\.?\b", "am", text)
    text = re.sub(r"\beastern\s+daylight\s+time\b", "america/new_york", text)
    text = re.sub(r"\beastern\s+standard\s+time\b", "america/new_york", text)
    text = re.sub(r"\beastern\s+time\b|\bet\b", "america/new_york", text)
    text = re.sub(r"\bcoordinated\s+universal\s+time\b|\butc\b", "utc", text)
    text = SPACE_RE.sub(" ", text).strip()
    return text


def _first(market: dict, names: Iterable[str]) -> Any:
    for name in names:
        value = market.get(name)
        if value is not None and value != "":
            return value
    return None


def _parse_float(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _strike(market: dict, ticker: str, title: str, rules: str) -> float | None:
    direct = _first(market, ("floor_strike", "cap_strike", "strike", "functional_strike"))
    parsed = _parse_float(direct)
    if parsed is not None:
        return parsed
    match = TICKER_STRIKE_RE.search(ticker)
    if match:
        return float(match.group(1))
    match = MONEY_STRIKE_RE.search(f"{title} {rules}")
    return float(match.group(1)) if match else None


def _iso_utc(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return normalize_text(text)
    if parsed.tzinfo is None:
        return parsed.isoformat(timespec="seconds")
    return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _close_time(market: dict) -> str | None:
    return _iso_utc(_first(market, (
        "close_time", "expected_expiration_time", "expiration_time", "determination_time",
        "settlement_time", "latest_expiration_time",
    )))


def _source(market: dict, rules: str) -> str | None:
    direct = _first(market, ("settlement_source", "verification_source", "source", "oracle"))
    if direct is not None:
        return normalize_text(direct)
    for label, pattern in KNOWN_SOURCE_PATTERNS:
        if pattern.search(rules):
            return label
    return None


def _source_instrument(market: dict, rules: str) -> str | None:
    direct = _first(market, (
        "settlement_symbol", "source_symbol", "underlying", "underlying_ticker",
        "settlement_instrument", "instrument",
    ))
    if direct is not None:
        return normalize_text(direct).upper()
    match = KNOWN_INSTRUMENT_RE.search(rules)
    return match.group(0).upper() if match else None


def _measured_field(market: dict, rules: str) -> str | None:
    direct = _first(market, ("settlement_field", "measured_field", "price_field", "candle_field"))
    if direct is not None:
        return normalize_text(direct)
    checks = [
        ("official_settlement", r"official\s+(?:daily\s+)?settlement|settlement\s+price"),
        ("one_minute_close", r"one[- ]minute.*\bclose\b|1[- ]minute.*\bclose\b"),
        ("close", r"\bclosing\s+price\b|\bclose\b"),
        ("open", r"\bopening\s+price\b|\bopen\b"),
        ("high", r"\bdaily\s+high\b|\bhighest\b|\bhigh\b"),
        ("low", r"\bdaily\s+low\b|\blowest\b|\blow\b"),
        ("vwap", r"\bvwap\b|volume[- ]weighted"),
    ]
    for label, pattern in checks:
        if re.search(pattern, rules, re.I):
            return label
    return None


def _inequality(market: dict, title: str, rules: str) -> str | None:
    direct = _first(market, ("comparison", "inequality", "strike_type"))
    if direct is not None:
        return normalize_text(direct)
    text = f"{title} {rules}"
    checks = [
        ("ge", r"\bat\s+or\s+above\b|\bgreater\s+than\s+or\s+equal\b|\bnot\s+less\s+than\b"),
        ("gt", r"\babove\b|\bgreater\s+than\b|\bexceed(?:s|ed)?\b"),
        ("le", r"\bat\s+or\s+below\b|\bless\s+than\s+or\s+equal\b|\bnot\s+greater\s+than\b"),
        ("lt", r"\bbelow\b|\bless\s+than\b"),
        ("between", r"\bbetween\b|\brange\b"),
    ]
    for label, pattern in checks:
        if re.search(pattern, text, re.I):
            return label
    return None


def _price_dollars(market: dict, side: str) -> float | None:
    dollar_keys = (f"{side}_ask_dollars", f"{side}_price_dollars")
    for key in dollar_keys:
        value = _parse_float(market.get(key))
        if value is not None:
            return value
    for key in (f"{side}_ask", f"{side}_price"):
        value = _parse_float(market.get(key))
        if value is not None:
            return value / 100.0 if value > 1.0 else value
    return None


def _hash(obj: dict) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonicalize_market(market: dict) -> CanonicalMarket:
    ticker = _text(_first(market, ("ticker", "market_ticker"))).strip()
    event_ticker = _first(market, ("event_ticker", "event"))
    series_ticker = _first(market, ("series_ticker", "series"))
    title = _first(market, ("title", "subtitle", "market_title"))
    rules_raw = _first(market, ("rules_primary", "rules", "settlement_rules", "rule_text"))
    normalized_rules = normalize_text(rules_raw)
    title_text = _text(title)
    strike = _strike(market, ticker, title_text, normalized_rules)
    close_time = _close_time(market)
    source = _source(market, normalized_rules)
    source_instrument = _source_instrument(market, normalized_rules)
    measured_field = _measured_field(market, normalized_rules)
    inequality = _inequality(market, title_text, normalized_rules)

    warnings = []
    for label, value in (
        ("ticker", ticker), ("rules", normalized_rules), ("strike", strike),
        ("close_time", close_time), ("source", source),
        ("source_instrument", source_instrument), ("measured_field", measured_field),
        ("inequality", inequality),
    ):
        if value is None or value == "":
            warnings.append(f"missing_{label}")

    strict_identity = {
        "strike": strike,
        "close_time_utc": close_time,
        "source": source,
        "source_instrument": source_instrument,
        "measured_field": measured_field,
        "inequality": inequality,
        "normalized_rules": normalized_rules,
    }
    semantic_identity = {
        "strike": strike,
        "close_time_utc": close_time,
        "source": source,
        "source_instrument": source_instrument,
        "measured_field": measured_field,
        "inequality": inequality,
    }
    return CanonicalMarket(
        ticker=ticker,
        event_ticker=_text(event_ticker).strip() or None,
        series_ticker=_text(series_ticker).strip() or None,
        title=title_text.strip() or None,
        strike=strike,
        close_time_utc=close_time,
        source=source,
        source_instrument=source_instrument,
        measured_field=measured_field,
        inequality=inequality,
        normalized_rules=normalized_rules,
        strict_hash=_hash(strict_identity),
        semantic_hash=_hash(semantic_identity),
        warnings=tuple(warnings),
        yes_ask_dollars=_price_dollars(market, "yes"),
        no_ask_dollars=_price_dollars(market, "no"),
    )


def _group(markets: list[CanonicalMarket], attr: str) -> list[list[CanonicalMarket]]:
    groups: dict[str, list[CanonicalMarket]] = {}
    for market in markets:
        groups.setdefault(getattr(market, attr), []).append(market)
    return [sorted(group, key=lambda m: m.ticker) for group in groups.values() if len(group) > 1]


def _gross_lock_pairs(group: list[CanonicalMarket]) -> list[dict]:
    out = []
    for i, a in enumerate(group):
        for b in group[i + 1:]:
            for yes_market, no_market in ((a, b), (b, a)):
                if yes_market.yes_ask_dollars is None or no_market.no_ask_dollars is None:
                    continue
                gross_cost = yes_market.yes_ask_dollars + no_market.no_ask_dollars
                out.append({
                    "buy_yes": yes_market.ticker,
                    "buy_no": no_market.ticker,
                    "gross_cost_dollars": round(gross_cost, 6),
                    "gross_locked_margin_before_fees": round(1.0 - gross_cost, 6),
                    "positive_before_fees": gross_cost < 1.0,
                    "warning": "gross only; subtract fees, slippage, legging risk, and rule-dispute risk",
                })
    return sorted(out, key=lambda x: x["gross_locked_margin_before_fees"], reverse=True)


def scan(markets_raw: list[dict]) -> dict:
    canonical = [canonicalize_market(m) for m in markets_raw]
    canonical = [m for m in canonical if m.ticker]
    strict_groups = _group(canonical, "strict_hash")
    semantic_groups_all = _group(canonical, "semantic_hash")
    semantic_groups = [
        group for group in semantic_groups_all
        if len({market.strict_hash for market in group}) > 1
    ]

    exact = []
    gross_pairs = []
    for group in strict_groups:
        pairs = _gross_lock_pairs(group)
        gross_pairs.extend(pairs)
        exact.append({
            "strict_hash": group[0].strict_hash,
            "tickers": [m.ticker for m in group],
            "series": sorted({m.series_ticker for m in group if m.series_ticker}),
            "strike": group[0].strike,
            "close_time_utc": group[0].close_time_utc,
            "source": group[0].source,
            "source_instrument": group[0].source_instrument,
            "measured_field": group[0].measured_field,
            "inequality": group[0].inequality,
            "gross_pair_count": len(pairs),
            "review_status": "EXACT_NORMALIZED_RULE_MATCH_REQUIRES_HUMAN_RULE_REVIEW",
        })

    near = []
    for group in semantic_groups:
        near.append({
            "semantic_hash": group[0].semantic_hash,
            "tickers": [m.ticker for m in group],
            "strict_hashes": sorted({m.strict_hash for m in group}),
            "differences": "same extracted settlement identity; normalized full rule text differs",
            "review_status": "NEAR_MATCH_ONLY_NOT_ARBITRAGE_ELIGIBLE",
        })

    warning_counts: dict[str, int] = {}
    for market in canonical:
        for warning in market.warnings:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1

    return {
        "schema_version": "1.0",
        "authority": "READ_ONLY",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "input_markets": len(markets_raw),
            "canonical_markets": len(canonical),
            "exact_normalized_rule_groups": len(exact),
            "semantic_near_match_groups": len(near),
            "gross_pair_checks": len(gross_pairs),
            "positive_gross_pairs_before_fees": sum(1 for p in gross_pairs if p["positive_before_fees"]),
        },
        "exact_groups": exact,
        "semantic_near_matches": near,
        "gross_pair_checks": gross_pairs,
        "warning_counts": warning_counts,
        "markets": [asdict(m) for m in canonical],
        "doctrine": [
            "Only strict normalized-rule groups enter exact-payoff review.",
            "Semantic groups are discovery aids and cannot support an arbitrage label.",
            "Positive gross margin is before fees, slippage, legging, disputes, and execution failure.",
            "Human review of complete current rules remains mandatory before any order intent.",
        ],
    }


def _load_markets(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("markets"), list):
        return payload["markets"]
    raise ValueError("input must be a market list or an object containing a `markets` list")


def selftest() -> None:
    common_rule = (
        "The market resolves Yes if the one-minute close of NGDQ6 from Pyth at 5:00 pm "
        "Eastern Time is above 3.50."
    )
    markets = [
        {
            "ticker": "KXNATGASD-26AUG0617-T3.50", "series_ticker": "KXNATGASD",
            "title": "Natural gas above $3.50", "rules_primary": common_rule,
            "close_time": "2026-08-06T17:00:00-04:00", "yes_ask": 42, "no_ask": 60,
        },
        {
            "ticker": "KXNATGASW-26AUG0617-T3.50", "series_ticker": "KXNATGASW",
            "title": "Natural gas weekly above $3.50", "rules_primary": common_rule,
            "close_time": "2026-08-06T21:00:00Z", "yes_ask_dollars": "0.39", "no_ask": 63,
        },
        {
            "ticker": "KXNATGASX-26AUG0617-T3.50", "series_ticker": "KXNATGASX",
            "title": "Natural gas above $3.50", "rules_primary": common_rule.replace("Pyth", "ICE"),
            "close_time": "2026-08-06T21:00:00Z", "yes_ask": 40, "no_ask": 62,
        },
    ]
    result = scan(markets)
    assert result["summary"]["exact_normalized_rule_groups"] == 1
    assert result["exact_groups"][0]["tickers"] == [
        "KXNATGASD-26AUG0617-T3.50", "KXNATGASW-26AUG0617-T3.50"
    ]
    assert any(pair["positive_before_fees"] for pair in result["gross_pair_checks"])
    assert result["summary"]["semantic_near_match_groups"] == 0
    assert all(m["source"] in {"pyth", "ice"} for m in result["markets"])
    print("kalshi_rule_canonicalizer selftest: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="JSON market list or object containing `markets`")
    parser.add_argument("--out", default="data/novel/kalshi_rule_scan.json")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not args.input:
        parser.error("input is required unless --selftest is used")
    result = scan(_load_markets(Path(args.input)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
