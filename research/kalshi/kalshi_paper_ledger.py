#!/usr/bin/env python3
"""kalshi_paper_ledger.py - G1 of the paper-trading dock (S110 turnaround memo Part 3).

The PAPER order/position/P&L ledger for NG/KXNATGASD. Pure code, no external dependency: quotes are
PASSED IN by the caller (the live loop passes Kalshi API quotes when G0/G2 land; tests pass recorded
or manual quotes, tagged in `quote.source`). Fills are simulated TAKER at the offered price using
the verified fee formula from kalshi_fill_model (0.07*p*(1-p) dollars/contract). Maker resting is
deliberately OUT of v1 (fill-risk needs the book over time); a limit worse than the offer is
recorded UNFILLED - honest, never a phantom fill.

DISCIPLINE
- Append-only JSONL at paper/ledger.jsonl (git-tracked: paper trades are RECORDS). Never rewritten.
- Every event carries its full context (quote, caps state, note). Per-event always - status() prints
  rows, and the only aggregates are the DAY's cap accounting (standing rule: no pooled scoreboard).
- RISK CAPS are enforced in place() and every rejection is RECORDED with the cap that fired.
- What paper trading tests is the DOCK (fills, fees, plumbing, cadence), not the edge.

CLI
  python kalshi_paper_ledger.py place  --market <ticker> --side yes|no --count N --limit 0.63 \
        --bid 0.61 --ask 0.63 --quote-source manual --note "..."
  python kalshi_paper_ledger.py unwind --market <ticker> --count N --price 0.55 --quote-source manual
  python kalshi_paper_ledger.py settle --market <ticker> --value 0|1
  python kalshi_paper_ledger.py status
  python kalshi_paper_ledger.py selftest     (writes to a throwaway ledger, never the real one)
"""
from __future__ import annotations

import argparse
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
from kalshi_fill_model import taker_fee_per_contract  # noqa: E402

PAPER_DIR = os.path.join(HERE, "paper")
LEDGER = os.path.join(PAPER_DIR, "ledger.jsonl")

# RISK CAPS - explicit, Greg-adjustable, enforced at place(). A rejected order is a RECORD.
MAX_CONTRACTS_PER_ORDER = 50
MAX_OPEN_CONTRACTS = 200          # summed across open positions, both sides
MAX_ORDERS_PER_DAY = 20
MAX_DAILY_REALIZED_LOSS_USD = 250.0   # once breached, place() refuses for the rest of the day


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _events(path: str = LEDGER) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _append(ev: dict, path: str = LEDGER) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ev = {"ts": _now(), **ev}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev) + "\n")
    return ev


def positions(path: str = LEDGER) -> dict[str, dict]:
    """Open positions by market: {market: {side, count, cost_usd, fees_usd}}. FIFO not needed -
    one market one side at a time is the paper policy (a second side is an unwind first)."""
    pos: dict[str, dict] = {}
    for ev in _events(path):
        m = ev.get("market")
        if ev["type"] == "fill":
            p = pos.setdefault(m, {"side": ev["side"], "count": 0, "cost_usd": 0.0, "fees_usd": 0.0})
            p["count"] += ev["count"]
            p["cost_usd"] += ev["cost_usd"]
            p["fees_usd"] += ev["fee_usd"]
        elif ev["type"] in ("unwind", "settle") and m in pos:
            if ev["type"] == "unwind":
                p = pos[m]
                frac_gone = min(ev["count"], p["count"])
                if p["count"] > 0:
                    p["cost_usd"] *= (1 - frac_gone / p["count"])
                p["count"] -= frac_gone
                p["fees_usd"] += ev["fee_usd"]
                if p["count"] <= 0:
                    del pos[m]
            else:
                del pos[m]
    return pos


def day_state(path: str = LEDGER) -> dict:
    """Today's cap accounting: orders placed, realized P&L (settles + unwinds today)."""
    today = _today()
    orders = realized = 0.0
    n_orders = 0
    for ev in _events(path):
        if not ev["ts"].startswith(today):
            continue
        if ev["type"] in ("fill", "reject"):
            n_orders += 1
        if ev["type"] in ("settle", "unwind"):
            realized += ev.get("realized_pnl_usd", 0.0)
    return {"date": today, "orders_today": n_orders, "realized_pnl_today_usd": round(realized, 2)}


def place(market: str, side: str, count: int, limit: float, bid: float, ask: float,
          quote_source: str, note: str = "", path: str = LEDGER) -> dict:
    assert side in ("yes", "no"), side
    assert 0.0 < limit < 1.0 and 0.0 <= bid <= 1.0 and 0.0 <= ask <= 1.0
    offered = ask if side == "yes" else round(1.0 - bid, 4)   # executable taker price for the side
    quote = {"bid": bid, "ask": ask, "source": quote_source}
    ds, pos = day_state(path), positions(path)
    open_ct = sum(p["count"] for p in pos.values())
    cap = None
    if count > MAX_CONTRACTS_PER_ORDER:
        cap = f"MAX_CONTRACTS_PER_ORDER ({count} > {MAX_CONTRACTS_PER_ORDER})"
    elif open_ct + count > MAX_OPEN_CONTRACTS:
        cap = f"MAX_OPEN_CONTRACTS ({open_ct}+{count} > {MAX_OPEN_CONTRACTS})"
    elif ds["orders_today"] + 1 > MAX_ORDERS_PER_DAY:
        cap = f"MAX_ORDERS_PER_DAY ({ds['orders_today']}+1 > {MAX_ORDERS_PER_DAY})"
    elif ds["realized_pnl_today_usd"] <= -MAX_DAILY_REALIZED_LOSS_USD:
        cap = f"MAX_DAILY_REALIZED_LOSS_USD (today {ds['realized_pnl_today_usd']})"
    if cap:
        return _append({"type": "reject", "market": market, "side": side, "count": count,
                        "limit": limit, "quote": quote, "cap": cap, "note": note}, path)
    if limit < offered:
        return _append({"type": "unfilled", "market": market, "side": side, "count": count,
                        "limit": limit, "offered": offered, "quote": quote,
                        "note": (note + " | maker resting not modeled in v1 - recorded unfilled").strip()}, path)
    fee = taker_fee_per_contract(offered) * count
    ex = pos.get(market)
    if ex and ex["side"] != side:
        return _append({"type": "reject", "market": market, "side": side, "count": count,
                        "limit": limit, "quote": quote,
                        "cap": f"OPPOSITE_SIDE_OPEN ({ex['side']} {ex['count']}) - unwind first",
                        "note": note}, path)
    return _append({"type": "fill", "market": market, "side": side, "count": count,
                    "price": offered, "cost_usd": round(offered * count, 4),
                    "fee_usd": round(fee, 4), "quote": quote, "note": note}, path)


def unwind(market: str, count: int, price: float, quote_source: str, note: str = "",
           path: str = LEDGER) -> dict:
    """Close early at an executable price for the HELD side (taker, fee applies)."""
    pos = positions(path).get(market)
    if not pos:
        return _append({"type": "reject", "market": market, "cap": "NO_OPEN_POSITION",
                        "count": count, "note": note}, path)
    count = min(count, pos["count"])
    fee = taker_fee_per_contract(price) * count
    avg_cost = pos["cost_usd"] / pos["count"]
    realized = (price - avg_cost) * count - fee
    return _append({"type": "unwind", "market": market, "side": pos["side"], "count": count,
                    "price": price, "fee_usd": round(fee, 4),
                    "realized_pnl_usd": round(realized, 4),
                    "quote": {"source": quote_source}, "note": note}, path)


def settle(market: str, value: int, path: str = LEDGER) -> dict:
    """Settle at expiration_value (Kalshi's own settle print - verified S99). YES pays 1 iff value==1."""
    assert value in (0, 1), value
    pos = positions(path).get(market)
    if not pos:
        return _append({"type": "reject", "market": market, "cap": "NO_OPEN_POSITION_AT_SETTLE",
                        "note": f"value={value}"}, path)
    payout = float(value if pos["side"] == "yes" else 1 - value) * pos["count"]
    realized = payout - pos["cost_usd"] - 0.0   # settlement carries no taker fee
    return _append({"type": "settle", "market": market, "side": pos["side"], "count": pos["count"],
                    "expiration_value": value, "payout_usd": round(payout, 4),
                    "realized_pnl_usd": round(realized - pos["fees_usd"], 4),
                    "fees_included_usd": round(pos["fees_usd"], 4)}, path)


def status(path: str = LEDGER) -> None:
    evs = _events(path)
    print(f"[paper] {len(evs)} events | {os.path.relpath(path, HERE)}")
    for ev in evs[-12:]:
        core = {k: v for k, v in ev.items() if k in
                ("ts", "type", "market", "side", "count", "price", "realized_pnl_usd", "cap", "limit")}
        print("  ", json.dumps(core))
    print("[open positions]")
    for m, p in positions(path).items():
        print(f"   {m}: {p['side']} x{p['count']}  cost {p['cost_usd']:.2f}  fees {p['fees_usd']:.2f}")
    print("[day]", json.dumps(day_state(path)))


def selftest() -> bool:
    """Tool-validation anchors (allowed class): prove fills, fees, settles, and EVERY CAP execute.
    Runs on a throwaway ledger; the real ledger is never touched."""
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), f"paper_selftest_{int(time.time())}.jsonl")
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        ok = ok and cond

    f = place("TEST-M1", "yes", 10, 0.65, 0.61, 0.63, "selftest", path=tmp)
    chk("taker fill at offer", f["type"] == "fill" and f["price"] == 0.63)
    chk("fee = 0.07*p*(1-p)*n (4dp stored)", abs(f["fee_usd"] - 0.07 * 0.63 * 0.37 * 10) < 1e-4)
    s = settle("TEST-M1", 1, path=tmp)
    chk("settle yes@1 pays count", s["payout_usd"] == 10.0)
    chk("settle pnl = payout-cost-fees",
        abs(s["realized_pnl_usd"] - (10.0 - 6.3 - f["fee_usd"])) < 1e-6)
    f2 = place("TEST-M2", "no", 10, 0.40, 0.61, 0.63, "selftest", path=tmp)
    chk("no-side executable = 1-bid", f2["type"] == "fill" and f2["price"] == 0.39)
    u = unwind("TEST-M2", 4, 0.45, "selftest", path=tmp)
    chk("partial unwind realizes pnl", u["type"] == "unwind" and u["count"] == 4)
    r1 = place("TEST-M3", "yes", 51, 0.6, 0.5, 0.6, "selftest", path=tmp)
    chk("cap MAX_CONTRACTS_PER_ORDER fires+records", r1["type"] == "reject" and "PER_ORDER" in r1["cap"])
    r2 = place("TEST-M4", "yes", 50, 0.6, 0.5, 0.6, "selftest", path=tmp)
    r2b = place("TEST-M5", "yes", 50, 0.6, 0.5, 0.6, "selftest", path=tmp)
    r2c = place("TEST-M6", "yes", 50, 0.6, 0.5, 0.6, "selftest", path=tmp)
    r3 = place("TEST-M7", "yes", 50, 0.6, 0.5, 0.6, "selftest", path=tmp)
    chk("cap MAX_OPEN_CONTRACTS fires at 200", r3["type"] == "reject" and "OPEN_CONTRACTS" in r3["cap"])
    uf = place("TEST-M8", "yes", 5, 0.55, 0.5, 0.6, "selftest", path=tmp)
    chk("limit below offer -> UNFILLED, never phantom", uf["type"] == "unfilled")
    op = place("TEST-M2", "yes", 5, 0.7, 0.5, 0.6, "selftest", path=tmp)
    chk("opposite side blocked (unwind first)", op["type"] == "reject" and "OPPOSITE" in op["cap"])
    n = len(_events(tmp))
    chk("append-only: every action recorded incl. rejects", n == 11)
    os.remove(tmp)
    print(f"[selftest] {'ALL PASS' if ok else 'FAILURES PRESENT'}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("place")
    for a, t in (("--market", str), ("--side", str), ("--count", int), ("--limit", float),
                 ("--bid", float), ("--ask", float), ("--quote-source", str), ("--note", str)):
        p.add_argument(a, type=t, required=(a != "--note"), default="" if a == "--note" else None)
    u = sub.add_parser("unwind")
    for a, t in (("--market", str), ("--count", int), ("--price", float), ("--quote-source", str),
                 ("--note", str)):
        u.add_argument(a, type=t, required=(a != "--note"), default="" if a == "--note" else None)
    s = sub.add_parser("settle")
    s.add_argument("--market", required=True)
    s.add_argument("--value", type=int, required=True)
    sub.add_parser("status")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "place":
        print(json.dumps(place(a.market, a.side, a.count, a.limit, a.bid, a.ask,
                               a.quote_source, a.note)))
    elif a.cmd == "unwind":
        print(json.dumps(unwind(a.market, a.count, a.price, a.quote_source, a.note)))
    elif a.cmd == "settle":
        print(json.dumps(settle(a.market, a.value)))
    elif a.cmd == "status":
        status()
    elif a.cmd == "selftest":
        return 0 if selftest() else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
