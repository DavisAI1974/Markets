"""The packet for one opening signal of a paper run: what an answerer is given, from the graph and from the
run's own journal AS IT STOOD BEFORE that signal.

  python3 -m tools.kgraph.signal_packet --data <markets-data> (--run <run id> [--at <commit>] |
        --journal <events.jsonl> [--start <start.json>]) --sequence <journal sequence of an opening signal>
        --budget <tokens> [--platform <paper-trading-platform checkout>] [--graph-dir D] [--json]
  python3 -m tools.kgraph.signal_packet ... --all-opens --out <file>      one line a signal, nothing else
  build(journal_rows, sequence, budget, *, store, platform_dir) -> {"text", "tokens_estimated", "lines",
        "cut", "not_in_packet", "moment_ns", "sha256", ...}

The journal comes from one of two places by one small reader (`journal_from_branch`, `journal_from_file`):
a run's record branch at a commit (default the tip), or a local `events.jsonl` as it stands (a trial keeps its
journal there). Everything after the reader sees only rows. Rows at or after the signal's own sequence are
dropped before anything is read from them, so a file that already holds later rows gives the same packet.
Tokens are counted at 4 characters a token as `context.py` and `packet.py` count them.

THE ONE RULE (extends `packet.py`'s): every line in a packet has a KNOWN-AT time, and it is no later than the
signal's own tape receive time (`received`, ns). A thing with no known-at time is not in a packet.
  IN, with why it is known:
   - the signal itself: its own row, decided on the tape message received at the moment.
   - the rule: id, version commit and `specification` text of `paper_platform/rules/<rule>.json` as committed
     at the row's `rule_commit`. This is the ONE line whose known-at is not a tape time: the rule is fixed
     before the run starts and is the engine's input from its first message, as it would be before a live
     day. Its basis is "fixed before the run began", and `leakage_check` verifies the commit's date is
     earlier than the wall time the run's first journal row was recorded.
   - the earlier rows of this run (signal, paper order, fill), each its own line, newest first, each known at
     its own tape receive time (a fill: its `fill_received_ns`); once for the signal's rule and, separately,
     for the other rules (so the two sections together are every rule, no line twice).
   - the trades of this run already closed before the moment (net contracts back to zero over fills with a
     lower sequence), each its own line with its own fills' prices: no sum, no average, no count of wins.
   - the dipole events of the trade day made known before the moment, through `packet.py`'s own functions
     and its SHOWN allow-list.
  OUT, each named in the packet's foot with its count:
   - every other run of the same tape (they hold this stretch's future);
   - every Peak (the graph holds the time of a peak's high, not when it became known);
   - every Claim whose known-at (its `knowledge_time`, else `said_on`: the date its source file was written)
     is later than the moment, or is missing. On the 2023 tape that is every claim today; on a live day the
     claims made before that day would come in by the same rule;
   - the trials of the experiment record made on this tape;
   - `open_profit` and `highest_open_profit`: ingest_platform leaves them out of the graph, and this
     packet shows no row's value; later rows are never read;
   - rows with a lower sequence whose known-at is later than the moment (a count; none is expected).
Row fields shown are an allow-list per row kind (ROW_FIELDS); prices are the journal's own stored integers,
bid and ask side by side, no mid, no cost, nothing scored.

`leakage_check(packet)` verifies a built packet: the text is what its lines and frame render to, every
line's known-at is at or before the moment, every journal line's sequence is below the signal's, no line
comes from another run, every dipole line is that event's own allowed cell, the budget holds. With the
journal rows (and the store) passed in, each journal line is also compared with its row.
WHAT IT CANNOT SEE: whether a stored value was itself worked out with later ticks (that is checked where the
value is made, in the platform and in ROOT), and that the rule texts were written with these four trade days
already seen (the rule commits are dated 2026-11, the tape is 2023-10).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from . import packet as dp
from .store import GraphStore

PATH_NAME = "signal_v1"
NS = 10**9
ET = ZoneInfo("America/New_York")
SECTIONS = ("signal", "rule", "same_rule", "trades", "dipoles", "other_rules")
VARIABLE = ("same_rule", "trades", "dipoles", "other_rules")
HEADINGS = {
    "signal": "THE SIGNAL:",
    "rule": "THE RULE (fixed before the run began):",
    "same_rule": "EARLIER ROWS OF THIS RUN FOR THIS RULE, NEWEST FIRST:",
    "trades": "TRADES OF THIS RUN CLOSED BEFORE THE MOMENT, NEWEST FIRST:",
    "dipoles": "DIPOLE EVENTS OF THE TRADE DAY MADE KNOWN BEFORE THE MOMENT, NEWEST FIRST:",
    "other_rules": "EARLIER ROWS OF THIS RUN FOR THE OTHER RULES, NEWEST FIRST:",
}
ROW_FIELDS = {
    "signal": ("rule", "action", "side", "reason", "conditions", "trade_id", "bid", "ask", "received"),
    "paper order": ("rule", "action", "order_side", "quantity", "placement", "limit_price", "trade_id",
                    "order_id", "bid", "ask", "received"),
    "fill": ("rule", "action", "side", "quantity", "fill_price", "liquidity", "trade_id", "fill_id",
             "bid", "ask", "fill_received_ns"),
}
LEFT_OUT = ("open_profit", "highest_open_profit")


# ---- the journal, from one of two places ------------------------------------------------------------------

def journal_from_branch(data, run: str, at: str | None = None, ref: str | None = None) -> list[dict]:
    from . import live
    root = GraphStore(data).data_root
    commit = live.resolve_commit(root, run, at=at, ref=ref)
    return live.read_at(root, run, commit)["rows"]


def journal_from_file(path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


# ---- small helpers -------------------------------------------------------------------------------------

def trade_day_of(ns: int) -> str:
    """The trade day an instant belongs to: 18:00 ET the evening before to 17:00 ET on the named date.
    The halt hour (17:00 to 18:00 ET) belongs to neither; it is given to the next trade day here and the
    packet never sees it (no signal is placed in it)."""
    t = dt.datetime.fromtimestamp(ns / NS, ET)
    return (t.date() + dt.timedelta(days=1 if t.hour >= 17 else 0)).isoformat()


def known_at(row: dict):
    if row["kind"] == "fill":
        return row.get("fill_received_ns", row.get("received"))
    return row.get("received")


def _fmt(row: dict, fields) -> str:
    def one(v):
        return json.dumps(v, sort_keys=True, ensure_ascii=False) if isinstance(v, (dict, list)) else v
    return "; ".join(f"{k}={one(row[k])}" for k in fields if k in row and row[k] is not None)


def row_line(row: dict, run: str) -> dict:
    seq, kind = row["sequence"], row["kind"]
    if kind == "paper order":
        src = f"porder:{row['order_id']}"
    elif kind == "fill":
        src = f"pfill:{run}:{seq}"
    else:
        src = f"journal#{seq}"
    text = f"{src} | seq={seq}; kind={kind}; {_fmt(row, ROW_FIELDS[kind])}"
    return {"section": None, "text": text, "source": src, "sequence": seq, "run": row["run"],
            "known_at_ns": known_at(row), "basis": "tape receive time", "row_kind": kind}


def _git_show(repo, commit, path):
    r = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"], capture_output=True)
    return r.stdout.decode("utf-8") if r.returncode == 0 else None


def rule_line(rule: str, commit: str, platform_dir, first_recorded_ns: int):
    """(line or None, reason when None)."""
    if not platform_dir:
        return None, "no paper-trading-platform checkout was given"
    raw = _git_show(platform_dir, commit, f"paper_platform/rules/{rule}.json")
    if raw is None:
        return None, f"{rule} is not in {commit[:10]} of {platform_dir}"
    spec = json.loads(raw).get("specification")
    if not spec:
        return None, f"{rule} at {commit[:10]} has no specification text"
    date = subprocess.run(["git", "-C", str(platform_dir), "log", "-1", "--format=%cI", commit],
                          capture_output=True, text=True).stdout.strip()
    committed_ns = int(dt.datetime.fromisoformat(date).timestamp() * NS)
    src = f"rule:{rule}@{commit[:10]}"
    text = f"{src} | rule={rule}; version_commit={commit}; specification={json.dumps(spec, ensure_ascii=False)}"
    return {"section": "rule", "text": text, "source": src, "sequence": None, "run": None,
            "known_at_ns": None, "basis": "fixed before the run began", "committed_ns": committed_ns,
            "committed_at": date, "run_first_recorded_ns": first_recorded_ns}, None


# ---- per-store caches (a store does not change while packets are built from it) ----------------------------

_CACHE: dict = {}


def _cached(store, key, fn):
    k = (id(store), key)
    if k not in _CACHE or _CACHE[k][0] is not store:     # the store is held, so its id is not reused
        _CACHE[k] = (store, fn())
    return _CACHE[k][1]


def _day_dipoles(store, day):
    def make():
        of_day = [n for n in store.nodes("DipoleEvent") if n["attrs"]["trade_day"] == day]
        return of_day, dp._before_by_birth(of_day)
    return _cached(store, ("dipoles", day), make)


def _order_runs(store):
    """run id -> {trade days of its orders, orders, fills}: from the graph."""
    def make():
        out = {}
        for typ, key in (("Order", "orders"), ("Fill", "fills")):
            for n in store.nodes(typ):
                a = n["attrs"]
                o = out.setdefault(a["run"], {"days": set(), "orders": 0, "fills": 0})
                o[key] += 1
                if a.get("received") is not None:
                    o["days"].add(trade_day_of(a["received"]))
        return out
    return _cached(store, "runs", make)


def _claim_known_ns(store):
    def make():
        out = []
        for c in store.nodes("Claim"):
            raw = c["attrs"].get("knowledge_time") or c["attrs"].get("said_on")
            try:
                out.append(int(dt.datetime.fromisoformat(str(raw)).replace(tzinfo=dt.timezone.utc).timestamp() * NS))
            except (TypeError, ValueError):
                out.append(None)
        return out
    return _cached(store, "claims", make)


def _trials(store):
    def make():
        from tools.exp_dag import ExpDag
        return ExpDag(store.data_root).log()
    return _cached(store, "trials", make)


def _peaks_of(store, day):
    return _cached(store, ("peaks", day), lambda: sum(1 for n in store.nodes("Peak") if n["attrs"].get("trade_day") == day))


# ---- build ----------------------------------------------------------------------------------------------

def _digits(n):  # a number's width, for the reserved size of the foot
    return len(str(n))


def build(journal_rows, sequence, budget, *, store, platform_dir=None, trials=None) -> dict:
    budget_chars = budget * dp.CHARS_PER_TOKEN
    prior = [r for r in journal_rows if r["sequence"] < sequence]          # nothing at or after is read
    sig = next((r for r in journal_rows if r["sequence"] == sequence), None)
    if sig is None or sig["kind"] != "signal" or sig.get("action") != "open":
        raise ValueError(f"journal sequence {sequence} is not an opening signal")
    moment, run, rule = sig["received"], sig["run"], sig["rule"]
    day = trade_day_of(moment)
    first_recorded = min((r["recorded_ns"] for r in prior + [sig] if r.get("recorded_ns") is not None), default=None)

    lines = {s: [] for s in SECTIONS}
    sl = row_line(sig, run)
    sl.update(section="signal")
    lines["signal"].append(sl)
    rl, why_no_rule = (None, "the signal row names no rule_commit")
    if sig.get("rule_commit") and first_recorded is not None:
        rl, why_no_rule = rule_line(rule, sig["rule_commit"], platform_dir, first_recorded)
    if rl:
        lines["rule"].append(rl)

    known, later_known = [], []
    for r in prior:
        if r["kind"] not in ROW_FIELDS:
            continue
        k = known_at(r)
        (known if k is not None and k <= moment else later_known).append(r)
    open_profit_rows = sum(1 for r in prior if any(x in r for x in LEFT_OUT))
    cand = {"same_rule": [], "other_rules": []}
    for r in sorted(known, key=lambda r: (known_at(r), r["sequence"]), reverse=True):
        ln = row_line(r, run)
        sec = "same_rule" if r.get("rule") == rule else "other_rules"
        ln["section"] = sec
        cand[sec].append(ln)
    # closed trades
    trades = {}
    for r in sorted(known, key=lambda r: r["sequence"]):
        if r["kind"] == "fill" and r.get("trade_id"):
            trades.setdefault((r["rule"], r["trade_id"]), []).append(r)
    closed = []
    for (trule, tid), fills in trades.items():
        held = sum(int(f["quantity"]) if f["side"] == "buy" else -int(f["quantity"]) for f in fills)
        if held == 0:
            ka = max(known_at(f) for f in fills)
            body = "; ".join(f"fill#{f['sequence']} {f['action']} {f['side']} qty={f['quantity']} "
                             f"fill_price={f['fill_price']} bid={f.get('bid')} ask={f.get('ask')} at={known_at(f)}"
                             for f in fills)
            src = "journal#" + ",".join(str(f["sequence"]) for f in fills)
            closed.append({"section": "trades", "source": src, "sequence": max(f["sequence"] for f in fills),
                           "sequences": [f["sequence"] for f in fills], "run": run, "known_at_ns": ka,
                           "basis": "tape receive time", "row_kind": "trade",
                           "text": f"{src} | trade rule={trule}; trade_id={tid} | {body}"})
    closed.sort(key=lambda l: (l["known_at_ns"], l["sequence"]), reverse=True)
    cand["trades"] = closed
    # dipoles of the trade day, through packet.py's own functions
    of_day, before = _day_dipoles(store, day)
    earlier = [n for n in of_day if dp._known_ns(n) < moment and dp._birth_ns(n) + dp.NS_PER_SECOND <= moment]
    earlier.sort(key=lambda n: (dp._known_ns(n), n["id"]), reverse=True)
    cand["dipoles"] = [{"section": "dipoles", "source": n["id"], "sequence": None, "run": None,
                        "known_at_ns": dp._known_ns(n), "basis": "native known second",
                        "row_kind": "dipole", "text": dp._line(n, before, moment)} for n in earlier]
    columns = sorted({c for n in of_day for c in n["attrs"]["pinned"]})
    held = [c for c in columns if c in dp.HELD_BACK]
    after = [c for c in columns if c in dp.AFTERWARDS]
    unplaced = [c for c in columns if c not in dp.SHOWN and c not in dp.HELD_BACK and c not in dp.AFTERWARDS]
    n_later_dipoles = len([n for n in of_day if n not in earlier])

    runs = _order_runs(store)
    others = {r: v for r, v in runs.items() if r != run and day in v["days"]}
    claim_ns = _claim_known_ns(store)
    claims_out = sum(1 for k in claim_ns if k is None or k > moment)
    claims_in = len(claim_ns) - claims_out
    tl = trials if trials is not None else _trials(store)
    on_tape = sum(1 for t in tl if (t.get("environment") or {}).get("trade_day") == day)
    no_day = sum(1 for t in tl if not (t.get("environment") or {}).get("trade_day"))

    def foot(cut: dict) -> list[str]:
        out = ["NOT IN THIS PACKET:"]
        out.append("- cut for want of budget (the oldest first): " + ", ".join(f"{k} {cut[k]}" for k in VARIABLE) + ".")
        if not rl:
            out.append(f"- the rule's text: {why_no_rule}.")
        out.append(f"- every other run of the same tape: {len(others)} runs hold "
                   f"{sum(v['orders'] for v in others.values())} orders and {sum(v['fills'] for v in others.values())} "
                   "fills of this stretch, which may hold its future.")
        out.append(f"- peaks: {_peaks_of(store, day)} of this trade day; the graph does not hold the time a peak "
                   "became known.")
        out.append(f"- claims: {claims_out} are out (their source files were written after the moment, or the date "
                   f"is not known); {claims_in} are known by the moment; none is shown (claims are not a section "
                   "of this packet yet).")
        out.append(f"- trials of the experiment record on this tape: {on_tape} name this trade day, "
                   f"{no_day} name none; none is shown.")
        out.append(f"- open_profit and highest_open_profit: on {open_profit_rows} earlier rows and shown on none; "
                   "later rows are not read.")
        out.append(f"- rows of lower sequence known after the moment: {len(later_known)}.")
        out.append(f"- dipole events made known at or after the moment: {n_later_dipoles}.")
        out.append("- held back until Greg says which reading governs: " + ", ".join(held) + ".")
        out.append("- what happened afterwards, the answer key: " + ", ".join(after) + ".")
        if unplaced:
            out.append("- columns nobody has placed yet, hidden until someone does: " + ", ".join(unplaced) + ".")
        return out

    head = [f"PACKET {PATH_NAME} | run {run} | signal sequence {sequence} | rule {rule} | trade day {day} | "
            f"moment {moment} ns (tape receive time of the signal). Each line: source | fields. "
            "Every line was known at or before the moment."]
    fixed = list(head)
    for s in ("signal", "rule"):
        fixed += [HEADINGS[s]] + [l["text"] for l in lines[s]]
    for s in VARIABLE:
        fixed.append(HEADINGS[s])
    fixed += foot({k: len(cand[k]) for k in VARIABLE})
    left = budget_chars - len("\n".join(fixed)) - 2
    if left < 0:
        raise ValueError(f"budget {budget} tokens is below the fixed part of the packet ({-left} characters short)")
    cut = {}
    for i, s in enumerate(VARIABLE):
        share = left // (len(VARIABLE) - i)
        used = 0
        for ln in cand[s]:
            if used + len(ln["text"]) + 1 > share:
                break
            lines[s].append(ln)
            used += len(ln["text"]) + 1
        cut[s] = len(cand[s]) - len(lines[s])
        left -= used
    pk = {"path": PATH_NAME, "run": run, "sequence": sequence, "rule": rule, "trade_day": day,
          "moment_ns": moment, "budget_tokens": budget, "head": head, "lines": [l for s in SECTIONS for l in lines[s]],
          "foot": foot(cut), "cut": cut,
          "lines_in": {s: len(lines[s]) for s in SECTIONS}}
    pk["text"] = render(pk)
    pk["tokens_estimated"] = dp.estimate_tokens(pk["text"])
    pk["sha256"] = hashlib.sha256(pk["text"].encode("utf-8")).hexdigest()
    pk["not_in_packet"] = pk["foot"]
    return pk


def render(pk: dict) -> str:
    out = list(pk["head"])
    for s in SECTIONS:
        out.append(HEADINGS[s])
        out += [l["text"] for l in pk["lines"] if l["section"] == s]
    return "\n".join(out + pk["foot"]) + "\n"


# ---- the check ------------------------------------------------------------------------------------------

def leakage_check(pk: dict, *, store=None, journal_rows=None) -> list[str]:
    """Every breach of the rule in a built packet, one line each; empty when there is none."""
    out, moment, seq, run = [], pk["moment_ns"], pk["sequence"], pk["run"]
    if pk["text"] != render(pk):
        out.append("the packet's text is not what its lines and foot render to")
    by_seq = {r["sequence"]: r for r in (journal_rows or [])}
    for ln in pk["lines"]:
        who = ln.get("source")
        sec = ln.get("section")
        if sec not in SECTIONS:
            out.append(f"{who}: section {sec!r} is not one of the packet's")
            continue
        if ln.get("basis") == "fixed before the run began":
            if sec != "rule":
                out.append(f"{who}: only the rule line may be known before the run began")
            elif not (ln.get("committed_ns") is not None and ln.get("run_first_recorded_ns") is not None
                      and ln["committed_ns"] < ln["run_first_recorded_ns"]):
                out.append(f"{who}: the rule's commit ({ln.get('committed_at')}) is not before the run began")
            continue
        k = ln.get("known_at_ns")
        if k is None:
            out.append(f"{who}: no known-at time")
        elif sec == "signal":
            if k != moment:
                out.append(f"{who}: the signal's own known-at {k} is not the moment {moment}")
        elif k > moment:
            out.append(f"{who}: known at {k}, after the moment {moment}")
        if sec == "dipoles":
            if store is not None:
                node = store.node(who)
                if node is None:
                    out.append(f"{who} is a dipole line and not in the graph")
                    continue
                if dp._known_ns(node) >= moment:
                    out.append(f"{who}: made known at {dp._known_ns(node)}, not before the moment {moment}")
                if dp._birth_ns(node) + dp.NS_PER_SECOND > moment:
                    out.append(f"{who}: its birth second had not ended at the moment")
                if node["attrs"]["trade_day"] != pk["trade_day"]:
                    out.append(f"{who}: of trade day {node['attrs']['trade_day']}, not {pk['trade_day']}")
                of_day, before = _day_dipoles(store, pk["trade_day"])
                pinned = node["attrs"]["pinned"]
                for pair in ln["text"].split(" | ", 1)[1].split("; "):
                    col, eq, value = pair.partition("=")
                    if not eq or col not in dp.SHOWN:
                        out.append(f"{who}: {col!r} is not a column that may be shown")
                    elif col not in pinned or value != f"{pinned[col]}":
                        out.append(f"{who}: {col}={value} is not that event's stored cell")
                    elif col == dp.GAP_COLUMN and not dp._gap_is_known(node, before, moment):
                        out.append(f"{who}: {col} shown and the dipole before it was not yet known")
            continue
        if sec == "rule":
            continue
        # a journal line
        if ln.get("run") != run:
            out.append(f"{who}: from run {ln.get('run')}, not {run}")
        if sec != "signal":
            seqs = ln.get("sequences") or [ln.get("sequence")]
            for s in seqs:
                if s is None or s >= seq:
                    out.append(f"{who}: journal sequence {s} is not below the signal's {seq}")
        elif ln.get("sequence") != seq:
            out.append(f"{who}: the signal line is sequence {ln.get('sequence')}, not {seq}")
        if who and who.startswith(("porder:", "pfill:")) and run not in who:
            out.append(f"{who}: its id does not name this run")
        if by_seq and ln.get("row_kind") in ROW_FIELDS:
            row = by_seq.get(ln["sequence"])
            if row is None:
                out.append(f"{who}: no such row in the journal")
            else:
                want = row_line(row, run)
                if want["text"] != ln["text"] or want["known_at_ns"] != k:
                    out.append(f"{who}: the line is not its journal row's allowed fields")
    if dp.estimate_tokens(pk["text"]) > pk["budget_tokens"] or pk["tokens_estimated"] != dp.estimate_tokens(pk["text"]):
        out.append(f"the packet is {dp.estimate_tokens(pk['text'])} estimated tokens, budget {pk['budget_tokens']}")
    return out


# ---- the command ------------------------------------------------------------------------------------------

def open_sequences(rows):
    return [r["sequence"] for r in rows if r["kind"] == "signal" and r.get("action") == "open"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--graph-dir")
    ap.add_argument("--platform")
    ap.add_argument("--run")
    ap.add_argument("--at")
    ap.add_argument("--ref")
    ap.add_argument("--journal")
    ap.add_argument("--start")
    ap.add_argument("--sequence", type=int)
    ap.add_argument("--budget", type=int, required=True, help="tokens")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all-opens", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if bool(a.run) == bool(a.journal):
        ap.error("give --run (the record branch) or --journal (a local events.jsonl), one of the two")
    if a.all_opens == (a.sequence is not None):
        ap.error("give --sequence, or --all-opens (with --out), one of the two")
    if a.all_opens and not a.out:
        ap.error("--all-opens writes to --out")
    store = GraphStore(a.data, graph_dir=a.graph_dir)
    platform = a.platform or str(store.data_root.parent / "paper-trading-platform")
    rows = journal_from_file(a.journal) if a.journal else journal_from_branch(store.data_root, a.run, a.at, a.ref)
    if a.start:
        start = json.loads(Path(a.start).read_text(encoding="utf-8"))
        if rows and start.get("run") != rows[0]["run"]:
            ap.error("start.json is of another run than the journal")
    seqs = open_sequences(rows) if a.all_opens else [a.sequence]
    out_lines, rc = [], 0
    for s in seqs:
        p = build(rows, s, a.budget, store=store, platform_dir=platform)
        br = leakage_check(p, store=store, journal_rows=rows)
        if a.all_opens:
            out_lines.append(json.dumps({"sequence": s, "rule": p["rule"], "tokens_estimated": p["tokens_estimated"],
                                         "lines_in": len(p["lines"]), "lines_cut": sum(p["cut"].values()),
                                         "leakage_breaches": len(br)}, sort_keys=True))
            continue
        if br:
            print("\n".join(br), file=sys.stderr)
            return 1
        if a.json:
            print(json.dumps({"sequence": s, "tokens_estimated": p["tokens_estimated"], "lines_in": len(p["lines"]),
                              "cut": p["cut"], "sha256": p["sha256"], "leakage_breaches": 0}, sort_keys=True))
        else:
            sys.stdout.write(p["text"])
    if a.all_opens:
        Path(a.out).write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
