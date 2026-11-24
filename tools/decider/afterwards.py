"""What happened after each decision: the after-the-fact layer, joined to each opening signal of a paper run.

  python3 -m tools.decider.afterwards --journal <events.jsonl> | (--data <markets-data> --run <run id>)
        [--decisions <decisions.jsonl>] [--quotes <quotes.jsonl>] [--prints <prints.jsonl>] --out <afterwards.jsonl>
  python3 -m tools.decider.afterwards brief --afterwards <afterwards.jsonl> --budget <tokens> --out <brief section>

One line for each opening signal of the journal, in journal order. Nothing in the file may be given to a decider at
the instant it decides; it is for learning after the fact (Greg, 2026-11-24). The first line of the file is a header
that says so; every other line carries `known_only_afterwards: true`.

One signal can have several trades under it: the rule's own (trade id = the signal's) and the trades the engine
opens beside it (trade id `<signal's>/<rule>`). Each (rule, trade id) is its own entry in `trades`, with its own
rows and its own figures, worked out exactly as `paper_platform.trial.trade_lines` works them (read, not imported).

Files that are given:
  quotes.jsonl  one line per change of the best bid / best ask, in time order: a time under `received_ns`,
                `tape_received_ns` or `received`, and `bid` and `ask` (tape price units, either may be null).
  prints.jsonl  one line per print, in time order, with a time under one of those keys.
Each side is read by itself. Nothing is made from the bid and the ask together. No total, no average, no ranking,
no word that judges. No fee, no fill assumption. No model is called; the tape is not read; no engine is run.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from pathlib import Path

from tools.kgraph import signal_packet as sp

HEADER_TEXT = ("Nothing in this file may be given to a decider at the instant it decides; it is for learning after "
               "the fact. Each line joins one opening signal of a paper run to what came after it: the decision, the "
               "trade's own later rows, the trade's own result where it holds no contract, and what the market did "
               "after. Each decision and each trade is its own line, in the tape's own price units. Nothing is added "
               "up across lines.")
TIME_KEYS = ("received_ns", "tape_received_ns", "received")
ROW_KINDS = ("paper order", "fill", "order status")
ROW_FIELDS = ("kind", "sequence", "rule", "trade_id", "action", "reason", "side", "order_side", "quantity",
              "fill_price", "bid", "ask", "trade_data", "administrative_reason", "administrative_flatten",
              "exit_policy", "open_profit", "highest_open_profit", "order_status", "execution_event",
              "remaining_quantity", "liquidity", "order_id", "fill_id")


def _base(trade_id):
    return trade_id.split("/")[0]


def _time(row):
    for k in TIME_KEYS:
        if row.get(k) is not None:
            return row[k]
    return None


def _row_time(row):
    return row.get("fill_received_ns") if row.get("kind") == "fill" and row.get("fill_received_ns") is not None \
        else row.get("received")


def read_series(path, what):
    """(lines, times) of a quotes or prints file; refuses a line with no time and a series out of time order."""
    lines, times = [], []
    for n, text in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
        if not text.strip():
            continue
        row = json.loads(text)
        t = _time(row)
        if not isinstance(t, int):
            raise ValueError(f"{what} line {n}: no time under {TIME_KEYS}")
        if times and t < times[-1]:
            raise ValueError(f"{what} line {n}: not in time order")
        lines.append(row)
        times.append(t)
    return lines, times


def _decisions(path):
    out = {}
    if path:
        for text in Path(path).read_text(encoding="utf-8").splitlines():
            if text.strip():
                row = json.loads(text)
                out.setdefault(row["sequence"], row)   # one line a question; the first is kept, none dropped from the file
    return out


def trade_entries(rows, base_id):
    """One entry for each (rule, trade id) under the signal's trade id, with its rows, as trial.trade_lines works it."""
    trades = {}
    for row in rows:
        if row["kind"] not in ROW_KINDS or not row.get("trade_id") or _base(row["trade_id"]) != base_id:
            continue
        key = row["rule"], row["trade_id"]
        t = trades.setdefault(key, dict(rule=key[0], trade_id=key[1], side=None, rows=[], fills=[], held=0,
                                        price_sum=0, administrative_close=False, close_reason=None))
        t["rows"].append({k: row[k] for k in ROW_FIELDS if k in row} | {"received": _row_time(row)})
        if row["kind"] == "paper order":
            if row.get("action") != "open":
                t["close_reason"] = row.get("reason")
        elif row["kind"] == "fill":
            q, p = int(row["quantity"]), int(row["fill_price"])
            signed = q if row["side"] == "buy" else -q
            if not t["fills"]:
                t["side"] = row["side"]
            t["held"] += signed
            t["price_sum"] -= signed * p
            t["administrative_close"] = t["administrative_close"] or (
                row.get("action") != "open" and row.get("trade_data") is False)
            t["fills"].append(dict(sequence=row["sequence"], action=row["action"], side=row["side"], quantity=q,
                                   fill_price=p, bid=row.get("bid"), ask=row.get("ask"), received=_row_time(row),
                                   trade_data=row.get("trade_data", True)))
    out = []
    for t in trades.values():
        flat = t["held"] == 0 and len(t["fills"]) > 1
        closing = [f for f in t["fills"] if f["action"] != "open"]
        out.append(dict(
            rule=t["rule"], trade_id=t["trade_id"], side=t["side"], opened=bool(t["fills"]),
            contracts_held_at_end=t["held"] if t["fills"] else None,
            own_result_price_units=t["price_sum"] if flat else None,
            closed_by_an_administrative_fill=t["administrative_close"],
            close_reason=t["close_reason"], last_closing_fill=closing[-1] if closing else None,
            fills=t["fills"], rows=t["rows"],
            open_profit_values=[{"sequence": r["sequence"], "received": r["received"], "action": r.get("action"),
                                 "open_profit": r.get("open_profit"), "highest_open_profit": r.get("highest_open_profit")}
                                for r in t["rows"] if "open_profit" in r or "highest_open_profit" in r]))
    return out


def _at_or_before(times, t):
    i = bisect.bisect_right(times, t) - 1
    return i if i >= 0 else None


def _quote_at(quotes, times, t):
    if t is None:
        return None
    i = _at_or_before(times, t)
    return None if i is None else {"index": i, "time": times[i], "bid": quotes[i].get("bid"), "ask": quotes[i].get("ask")}


def market_after(quotes, times, t0, close_t, fill_t):
    start = bisect.bisect_left(times, t0)
    best = {}
    for name, side, want in (("highest_bid", "bid", 1), ("lowest_bid", "bid", -1),
                             ("highest_ask", "ask", 1), ("lowest_ask", "ask", -1)):
        hit = None
        for i in range(start, len(quotes)):
            v = quotes[i].get(side)
            if isinstance(v, (int, float)) and (hit is None or (v - hit["price"]) * want > 0):
                hit = {"price": v, "first_reached_ns": times[i], "index": i}
        best[name] = hit
    last = len(quotes) - 1
    return dict(first_quote_index_at_or_after_signal=start if start < len(quotes) else None, **best,
                at_rule_close_signal=_quote_at(quotes, times, close_t),
                at_own_last_closing_fill=_quote_at(quotes, times, fill_t),
                at_last_line_of_series={"index": last, "time": times[last], "bid": quotes[last].get("bid"),
                                        "ask": quotes[last].get("ask")} if quotes else None)


def build_lines(rows, decisions=None, quotes=None, prints=None):
    decided = _decisions(decisions) if isinstance(decisions, (str, Path)) else (decisions or {})
    answers = {}
    for r in rows:
        if r["kind"] == "answer" and r.get("asked_at_sequence") is not None:
            answers.setdefault(r["asked_at_sequence"], r)
    out = []
    for s in rows:
        if s["kind"] != "signal" or s.get("action") != "open":
            continue
        tid, seq = s["trade_id"], s["sequence"]
        d, a = decided.get(seq), answers.get(seq)
        src = d or a
        decision = {"action": src.get("action") if src else None, "why": src.get("why") if src else None,
                    "by": src.get("by") if src else None,
                    "source": "decisions.jsonl" if d else ("journal answer row" if a else None)}
        closes = [r for r in rows if r["kind"] == "signal" and r.get("action") in ("close", "exit")
                  and r.get("trade_id") == tid]
        fmt = lambda r: {"sequence": r["sequence"], "received": r["received"], "reason": r.get("reason"),
                         "bid": r.get("bid"), "ask": r.get("ask"), "trade_data": r.get("trade_data", True)}
        rule_close = next((r for r in closes if r.get("trade_data") is not False), None)
        others = [fmt(r) | {"action": r["action"]} for r in rows if r["kind"] == "signal" and r["sequence"] != seq
                  and r.get("trade_id") == tid and r.get("action") not in ("close", "exit")]
        trades = sorted(trade_entries(rows, tid), key=lambda t: (t["trade_id"] != tid, t["rule"] != s["rule"]))
        own = next((t for t in trades if t["trade_id"] == tid and t["rule"] == s["rule"]), None)
        opened = any(t["opened"] for t in trades)
        line = {"known_only_afterwards": True, "sequence": seq, "rule": s["rule"], "side": s.get("side"), "trade_id": tid,
                "tape_received_ns": s["received"], "bid": s.get("bid"), "ask": s.get("ask"), "decision": decision,
                "journal_answer": {k: a.get(k) for k in ("action", "by", "why", "applied")} if a else None,
                "trade_opened": opened,
                "rule_close_signal": fmt(rule_close) if rule_close else None,
                "close_signals_as_journaled": [fmt(r) for r in closes],
                "other_signal_rows_of_the_trade": others, "trades": trades}
        if own and own["opened"]:
            line["own_result_price_units"] = own["own_result_price_units"]
            line["contracts_held_at_end"] = own["contracts_held_at_end"]
            line["closed_by_an_administrative_fill"] = own["closed_by_an_administrative_fill"]
        elif opened:
            line["own_result_note"] = ("the signal's own rule has no fill under the signal's trade id; the trades "
                                       "opened beside it are in `trades`, each with its own result")
        else:
            line["own_result_note"] = "no result: this trade was never opened, so it has no fills of its own"
        if quotes is None:
            line["market_series_kept"] = False
        else:
            ql, qt = quotes
            fill_t = own["last_closing_fill"]["received"] if own and own["last_closing_fill"] else None
            line["market_series_kept"] = True
            line["market_after"] = market_after(ql, qt, s["received"], rule_close["received"] if rule_close else None, fill_t)
        if prints is not None:
            pl, pt = prints
            i = bisect.bisect_left(pt, s["received"])
            line["first_print_index_at_or_after_signal"] = i if i < len(pl) else None
        out.append(line)
    return out


def write_lines(path, header, lines):
    with Path(path).open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(header, sort_keys=True) + "\n")
        for l in lines:
            f.write(json.dumps(l, sort_keys=True) + "\n")


# ---- the brief section ------------------------------------------------------------------------------------

def _ext(x):
    return "none" if not x else f"{x['price']} at {x['first_reached_ns']}"


def _q(x):
    return "none" if not x else f"bid {x['bid']} ask {x['ask']} at {x['time']}"


def brief_line(l):
    parts = []
    for t in l.get("trades", []):
        if t["opened"]:
            r = t["own_result_price_units"] if t["own_result_price_units"] is not None else \
                f"none (holds {t['contracts_held_at_end']})"
            parts.append(f"{t['rule']} {r}" + (" (administrative close, not trade data)"
                                                if t["closed_by_an_administrative_fill"] else ""))
    own = "; ".join(parts) if parts else "never opened"
    text = (f"sequence {l['sequence']} rule {l['rule']} side {l['side']} decision {l['decision']['action']} "
            f"own result per trade: {own}")
    m = l.get("market_after")
    if m:
        text += (f"; bid highest {_ext(m['highest_bid'])}, lowest {_ext(m['lowest_bid'])}; ask highest "
                 f"{_ext(m['highest_ask'])}, lowest {_ext(m['lowest_ask'])}; at the rule's close signal "
                 f"{_q(m['at_rule_close_signal'])}; at the last closing fill {_q(m['at_own_last_closing_fill'])}; "
                 f"at the last line of the series {_q(m['at_last_line_of_series'])}")
    else:
        text += "; the market series was not kept"
    return text


def make_brief(path, budget):
    lines = [json.loads(t) for t in Path(path).read_text(encoding="utf-8").splitlines() if t.strip()][1:]
    head = ("What happened after each decision (for writing the next decider; known only afterwards, never for a "
            "decision at its own instant). Each decision is its own line, oldest first, prices in the tape's own "
            "units, bid and ask each by itself.")
    cost = lambda t: (len(t) + 1 + 3) // 4
    foot = lambda shown: f"Shown: {shown} of {len(lines)} decisions, oldest first; every line is in {path}."
    used, shown = cost(head) + cost(foot(len(lines))), []
    for l in lines:
        t = brief_line(l)
        if used + cost(t) > budget:
            break
        used += cost(t)
        shown.append(t)
    return "\n".join([head, *shown, foot(len(shown))]) + "\n"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "brief":
        ap = argparse.ArgumentParser(prog="afterwards brief")
        ap.add_argument("--afterwards", required=True)
        ap.add_argument("--budget", type=int, required=True, help="tokens")
        ap.add_argument("--out", required=True)
        a = ap.parse_args(argv[1:])
        Path(a.out).write_text(make_brief(a.afterwards, a.budget), encoding="utf-8")
        return 0
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--journal")
    ap.add_argument("--data")
    ap.add_argument("--run")
    ap.add_argument("--decisions")
    ap.add_argument("--quotes")
    ap.add_argument("--prints")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if bool(a.journal) == bool(a.run and a.data):
        ap.error("give --journal, or --data with --run, one of the two")
    rows = sp.journal_from_file(a.journal) if a.journal else sp.journal_from_branch(a.data, a.run)
    lines = build_lines(rows, a.decisions, read_series(a.quotes, "quotes") if a.quotes else None,
                        read_series(a.prints, "prints") if a.prints else None)
    header = {"header": True, "known_only_afterwards": True, "text": HEADER_TEXT, "run": rows[0].get("run") if rows else None,
              "opening_signals": len(lines), "market_series_kept": bool(a.quotes), "prints_kept": bool(a.prints),
              "decisions_file_given": bool(a.decisions)}
    write_lines(a.out, header, lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
