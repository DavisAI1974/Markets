"""The packet for one opening signal of a paper run: what an answerer is given, from the graph and from the
run's own journal AS IT STOOD BEFORE that signal.

  python3 -m tools.kgraph.signal_packet --data <markets-data> (--run <run id> [--at <commit>] |
        --journal <events.jsonl> [--start <start.json>]) --sequence <journal sequence of an opening signal>
        --budget <tokens> [--platform <paper-trading-platform checkout>] [--graph-dir D] [--json]
  python3 -m tools.kgraph.signal_packet ... --all-opens --out <file>      one line a signal, nothing else
  build(journal_rows, sequence, budget, *, store, platform_dir, question=None) -> {"text", "tokens_estimated",
        "lines", "cut", "not_in_packet", "moment_ns", "sha256", ...}

WITH A QUESTION (the platform's own question.json for this signal, Greg 2026-11-24: "all of data depth back in"):
the packet also holds `state` (the question's state, whole and unchanged), `flow_lines` (the question's `lines`: the
dipole and exhaustion lines, each value and width in seconds; named flow_lines because `lines` is the packet's own list
of text lines) and `exchange_ns`, and its text gains two sections BEFORE the signal's: "the data at the signal" and
"the two lines at this run's earlier signals". Every `state:` line is known at the signal's own tick; every `q:` line
at its own earlier tape time. The real shape of a real state is not known until one pass of the tape has been taken:
everything here reads the shape the platform's code and its own checks describe, and a name that is not there is
counted in the foot, never made up. Without a question the packet is exactly what it was.

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

# The two sections a question adds, in the order they stand in the text (before the signal's own).
QUESTION_SECTIONS = ("data_at_signal", "earlier_q", "state_layers")
HEADINGS["data_at_signal"] = ("THE DATA AT THE SIGNAL (the engine's own values at the signal's tick; prices and sizes are the "
                     "tape's integer units as stored; nothing derived):")
HEADINGS["earlier_q"] = "THE TWO LINES AT THIS RUN'S EARLIER SIGNALS, NEWEST FIRST:"
HEADINGS["state_layers"] = ("THE REST OF THE STATE, LAYER BY LAYER (each layer: its name, how many lines it holds in all, "
                            "its head; the whole of every layer is in state.json beside this brief):")
# ENGINEERING CHOICE, not a finding: the part of the room left for the variable sections (after the fixed head, signal,
# rule and foot) that the two question sections may use between them. The rest goes to the journal's sections.
STATE_SHARE = 0.5
ROW_CHARS = 400          # a state row longer than this is split into its parts; a scalar longer is cut and says so
LEG_NAMES = ("leg_number", "direction", "first_trade_position", "start_price", "furthest_price", "steps")
LEFT_OUT_NAMES_SHOWN = 20


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



# ---- the data at the signal (only when a question is given) --------------------------------------------------

def _v(x):
    """A value as given, in one piece of text."""
    return "null" if x is None else json.dumps(x, sort_keys=True, ensure_ascii=False)


def _g(d, *path):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def state_sha256(state) -> str:
    """The platform's own digest of a state: canonical JSON, sorted keys, no spaces (session.py `_ask_decider`)."""
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _flow_text(name, question, state):
    """One flow line as given: its value and width from the question's `lines`, else from the tick; the bought and
    sold sizes behind it from the inputs' own flow when the state has them."""
    ln = _g(question, "lines", name)
    tick = _g(state, "inputs", "tick") or {}
    flow = _g(state, "inputs", "strategy_inputs", name) or {}
    if isinstance(ln, dict):
        value, width = ln.get("value"), ln.get("width_s")
    else:
        value = tick.get(name) if isinstance(tick, dict) else None
        w = flow.get("width") if isinstance(flow, dict) else None
        width = w // NS if isinstance(w, int) else None
    parts = [f"value={'empty' if value is None else _v(value)}", f"width_s={_v(width)}"]
    size = flow.get("size") if isinstance(flow, dict) else None
    if isinstance(size, list) and len(size) == 2:
        parts += [f"bought={_v(size[0])}", f"sold={_v(size[1])}"]
    return f"{name}; " + "; ".join(parts)


def _fact_name(i, fact, taken):
    base = f"{fact.get('quote')}:{fact.get('fact')}".replace(" ", "_") if isinstance(fact, dict) and (
        fact.get("quote") is not None or fact.get("fact") is not None) else f"no_name_{i}"
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base}#{n}"
    taken.add(name)
    return name


def state_lines(question, moment):
    """(lines in priority order, {"book_bid": n, "book_ask": n, "left_out": [...]}) from a question's state."""
    state = question.get("state")
    out = []

    def add(src, body):
        out.append({"section": "data_at_signal", "text": f"{src} | {body}", "source": src, "sequence": None, "run": None,
                    "known_at_ns": moment, "basis": "the signal's own tick", "row_kind": "state"})
    tick = _g(state, "inputs", "tick") or {}
    tick = tick if isinstance(tick, dict) else {}
    add("state:dipole", _flow_text("dipole", question, state))
    add("state:exhaustion", _flow_text("exhaustion", question, state))
    add("state:tick", "; ".join(f"{k}={_v(tick.get(k))}" for k in ("bid", "ask", "trade", "price", "aggressor",
                                                                     "settlement") if k in tick))
    add("state:before", "; ".join(f"{k}={_v(tick.get(k))}" for k in ("dipole_before", "exhaustion_before",
                                                                      "exhaustion_prior_read") if k in tick))
    taken = set()
    for i, fact in enumerate(tick.get("quote_facts") or []):
        body = "; ".join(f"{k}={_v(v)}" for k, v in sorted(fact.items())) if isinstance(fact, dict) else _v(fact)
        add(f"state:fact:{_fact_name(i, fact, taken)}", body)
    leg = tick.get("leg")
    if isinstance(leg, list) and len(leg) == len(LEG_NAMES):
        add("state:leg", "; ".join(f"{n}={_v(x)}" for n, x in zip(LEG_NAMES, leg)))
    elif "leg" in tick:
        add("state:leg", f"leg={_v(leg)}")
    book = state.get("book") if isinstance(state, dict) else None
    sides = {s: (book.get(s) if isinstance(book, dict) and isinstance(book.get(s), list) else []) for s in ("bid", "ask")}
    for level in range(max(len(sides["bid"]), len(sides["ask"]))):
        for s in ("bid", "ask"):
            if level < len(sides[s]):
                lv = sides[s][level]
                lv = lv if isinstance(lv, dict) else {}
                add(f"state:book:{s}:{level + 1}", f"side={s}; level={level + 1}; price={_v(lv.get('price'))}; "
                    f"size={_v(lv.get('size'))}; orders={_v(lv.get('orders'))}")
    left = state.get("left_out") if isinstance(state, dict) and isinstance(state.get("left_out"), list) else []
    return out, {"book_bid": len(sides["bid"]), "book_ask": len(sides["ask"]), "book_given": book is not None,
                 "left_out": [x.get("name") if isinstance(x, dict) else x for x in left]}


def state_layer_list(state):
    """[(layer name, value)] by the state's own top-level and second-level keys, so a layer the platform adds later
    is passed through and listed without a change here. A top-level dict whose values are all dicts or lists is
    split by its second-level keys; anything else is one layer."""
    out = []
    for k1, v in state.items():
        if isinstance(v, dict) and v and all(isinstance(x, (dict, list)) for x in v.values()):
            out += [(f"{k1}.{k2}", x) for k2, x in v.items()]
        else:
            out.append((k1, v))
    return out


def _leaves(v, path=""):
    """(path, value) rows of a layer: scalars, and any list or dict short enough to read as one row; a longer one is
    split into its parts. Lazy, so a count never holds the rows."""
    if isinstance(v, (dict, list)) and v:
        if len(json.dumps(v, sort_keys=True, ensure_ascii=False)) <= ROW_CHARS:
            yield path, v
        elif isinstance(v, dict):
            for k, x in v.items():
                yield from _leaves(x, f"{path}.{k}" if path else str(k))
        else:
            for i, x in enumerate(v):
                yield from _leaves(x, f"{path}[{i}]")
    else:
        yield path, v


def state_row_id(layer, path):
    return f"state.{layer}/{path}"


def state_row_text(layer, path, value):
    t = json.dumps(value, sort_keys=True, ensure_ascii=False)
    if len(t) > ROW_CHARS:
        t = t[:ROW_CHARS] + f"... ({len(t) - ROW_CHARS} more characters, whole in state.json)"
    return f"{state_row_id(layer, path)} | {t}"


def resolve_state_id(state, id_):
    """True when `id_` (state.<layer>/<path>) names a row that is in the state."""
    import re
    if not isinstance(id_, str) or not id_.startswith("state.") or "/" not in id_ or not isinstance(state, dict):
        return False
    layer, _, path = id_[6:].partition("/")
    cur = state
    for k in layer.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return False
        cur = cur[k]
    for m in re.finditer(r"\.?([^.\[\]]+)|\[(\d+)\]", path):
        if m.group(2) is not None:
            i = int(m.group(2))
            if not isinstance(cur, list) or i >= len(cur):
                return False
            cur = cur[i]
        else:
            if not isinstance(cur, dict) or m.group(1) not in cur:
                return False
            cur = cur[m.group(1)]
    return True


def state_layer_of(state, id_):
    """The layer name an id of a state row belongs to, or None."""
    if resolve_state_id(state, id_):
        return id_[6:].partition("/")[0]
    return None


class PacketIds:
    """Every id a decision may name: the explicit rows of every layer, shown in the text or not, and every row of the
    state by its address. `in` asks the whole packet, not the text."""

    def __init__(self, layer_of: dict, state=None):
        self.layer_of, self.state = dict(layer_of), state

    def __contains__(self, id_):
        return id_ in self.layer_of or resolve_state_id(self.state, id_)

    def layer(self, id_):
        return self.layer_of.get(id_) or state_layer_of(self.state, id_)


def layer_of_map(pk) -> dict:
    """id -> layer name for every explicit row of a built packet (text lines and the layers' whole rows)."""
    out = {l["source"]: l.get("layer") or l["section"] for l in pk["lines"]}
    for name, lay in (pk.get("layers") or {}).items():
        for r in lay.get("rows", []):
            out.setdefault(r["source"], name)
    return out


PLANE_FILE_REASONS = (
    ("peaks-by-place", "built on Peaks: Peaks stay out (the graph holds the time of a peak's high, not when it became known)"),
    ("old-defs-on-peaks", "built on Peaks: Peaks stay out (the time a peak became known is not held)"),
    ("peak-lives", "built on Peaks: Peaks stay out (the time a peak became known is not held)"),
    ("flow-60s-before-and-after", "holds the flow AFTER each event, an AFTERWARDS column (what happened after)"),
)


def planes_named(store, day, platform_dir):
    """Every stored layer of the trade day that this packet does not hold, each with its reason: [(layer, rows, reason)].
    Nothing is read from a file; the graph's CalcOutput nodes, the file names under markets-data and the READS of the
    rule texts are listed. Where a layer's rows have a time it cannot be verified here, no time is guessed."""
    out, calcs, columns = [], set(), set()
    for n in store.nodes("CalcOutput"):
        a = n["attrs"]
        if a.get("trade_day") != day:
            continue
        calcs.add(a["calc"])
        columns |= set(a.get("columns") or [])
        out.append((f"calc-{a['calc']}", (a.get("receipt") or {}).get("rows"),
                    f"stored per tick (every row carries its tick's position and time); its parquet parts are on branch "
                    f"{a.get('branch')} of markets-data, which is not in the checkout: not read, no row placed"))
    ymd = day.replace("-", "")
    root = Path(store.data_root)
    for f in sorted(root.glob(f"tasks/**/research-union-current/**/*{ymd}*.parquet")):
        why = next((r for k, r in PLANE_FILE_REASONS if f.name.startswith(k)), None) or \
            "a research file of the trade day whose rows carry no known-at time this packet can verify: not read, no time guessed"
        out.append((f.name, None, why))
    if platform_dir:
        import re
        reads = set()
        for f in sorted(Path(platform_dir).glob("paper_platform/rules/*.json")):
            try:
                spec = json.loads(f.read_text(encoding="utf-8")).get("specification", "")
            except (OSError, ValueError):
                continue
            for line in spec.split("\n"):
                if line.lstrip().startswith("- READS"):
                    reads |= set(re.findall(r"`([^`]+)`", line))
        have = {n for n, _, _ in out}
        for name in sorted(reads):
            base = name[5:].split("-facts")[0] if name.startswith("calc-") else name
            if name in have or base in calcs or f"calc-{base}" in have:
                continue
            if name in columns or name in ("exhaustion_20s", "dipole_60s"):
                out.append((name, None, "a column of calc-research_columns (stored per tick, parquet not in the checkout): not read"))
            else:
                out.append((name, None, "named in a rule text's READS; no file of this trade day is in the graph or the checkout"))
    return out


def q_line(row: dict) -> dict:
    """One earlier question row of the run: the two lines it carried, known at its own tape time."""
    seq = row.get("signal_sequence")
    lines = row.get("lines") if isinstance(row.get("lines"), dict) else None

    def one(name):
        ln = lines.get(name) if lines else None
        return "not given" if not isinstance(ln, dict) else ("empty" if ln.get("value") is None else _v(ln["value"]))
    src = f"q:{seq}"
    return {"section": "earlier_q", "source": src, "sequence": seq, "run": row.get("run"),
            "known_at_ns": row.get("received"), "basis": "tape receive time", "row_kind": "question",
            "text": f"{src} | rule={row.get('rule')}; side={row.get('side')}; dipole={one('dipole')}; "
                    f"exhaustion={one('exhaustion')}"}


# ---- build ----------------------------------------------------------------------------------------------

def _digits(n):  # a number's width, for the reserved size of the foot
    return len(str(n))


def build(journal_rows, sequence, budget, *, store, platform_dir=None, trials=None, question=None) -> dict:
    budget_chars = budget * dp.CHARS_PER_TOKEN
    prior = [r for r in journal_rows if r["sequence"] < sequence]          # nothing at or after is read
    sig = next((r for r in journal_rows if r["sequence"] == sequence), None)
    if sig is None or sig["kind"] != "signal" or sig.get("action") != "open":
        raise ValueError(f"journal sequence {sequence} is not an opening signal")
    moment, run, rule = sig["received"], sig["run"], sig["rule"]
    day = trade_day_of(moment)
    first_recorded = min((r["recorded_ns"] for r in prior + [sig] if r.get("recorded_ns") is not None), default=None)

    sections = (QUESTION_SECTIONS + SECTIONS) if question is not None else SECTIONS
    variable = (QUESTION_SECTIONS + VARIABLE) if question is not None else VARIABLE
    lines = {s: [] for s in sections}
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
    q_meta, q_later, slayers, planes = None, 0, [], []
    if question is not None:
        st = question.get("state")
        cand["data_at_signal"], q_meta = state_lines(question, moment) if isinstance(st, dict) else ([], None)
        cand["earlier_q"] = []
        for r in sorted((r for r in prior if r["kind"] == "question"), key=lambda r: (r.get("received") or 0,
                                                                                  r["sequence"]), reverse=True):
            if r.get("received") is not None and r["received"] <= moment and r.get("signal_sequence") is not None \
                    and r["signal_sequence"] < sequence:
                cand["earlier_q"].append(q_line(r))
            else:
                q_later += 1
        if isinstance(st, dict):
            for name, value in state_layer_list(st):
                slayers.append({"name": f"state.{name}", "key": name, "value": value,
                                "count": sum(1 for _ in _leaves(value))})
        planes = planes_named(store, day, platform_dir)
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
        out.append("- cut for want of budget (the oldest first): " + ", ".join(f"{k} {cut[k]}" for k in variable) + ".")
        if question is not None:
            if q_meta is None:
                out.append("- the data at the signal: the question carried no state, so none is shown; the "
                           "platform said: " + _v(question.get("state_left_out")) + ".")
            else:
                shown = [l["source"] for l in lines["data_at_signal"]]
                nb = {s: sum(1 for x in shown if x.startswith(f"state:book:{s}:")) for s in ("bid", "ask")}
                out.append(f"- book levels not shown in the text (cut for want of budget): bid "
                           f"{cut.get('book_bid', q_meta['book_bid'] - nb['bid'])} of {q_meta['book_bid']}, ask "
                           f"{cut.get('book_ask', q_meta['book_ask'] - nb['ask'])} of {q_meta['book_ask']}; all of them, "
                           "with the queue at each level, are in state.json"
                           + ("." if q_meta["book_given"] else "; the platform gave no book at this tick."))
                names = [str(n) for n in q_meta["left_out"]]
                out.append(f"- named by the platform as left out of the state ({len(names)}): "
                           + ", ".join(names[:LEFT_OUT_NAMES_SHOWN])
                           + (f" and {len(names) - LEFT_OUT_NAMES_SHOWN} more" if len(names) > LEFT_OUT_NAMES_SHOWN else "")
                           + ".")
            parts = []
            for s in sections:
                if s == "state_layers":
                    continue
                n = len(cand[s]) if s in cand else len(lines[s])
                parts.append(f"{s} {n - cut.get(s, 0)} of {n}")
            out.append("- layers held whole in layers.json (lines shown here of lines in all): " + ", ".join(parts)
                       + ". The state's own layers are listed above with their counts; their whole is in state.json.")
            out.append(f"- earlier question rows of this run with no usable time or later than the moment: {q_later}.")
            groups = {}
            for name, rows, why in planes:
                groups.setdefault(why, []).append(f"{name}" + (f" ({rows} rows)" if rows else ""))
            out.append(f"- ROOT's stored planes of trade day {day}: none is placed in this packet, each for the reason "
                       "given and none read:")
            for why, names in groups.items():
                out.append(f"  - {why}: " + ", ".join(names) + ".")
            out.append("- from the planes, never in a packet whatever the file: AFTERWARDS columns (what happened after "
                       "an event) and the HELD_BACK columns named below, and every Peak (counted above).")
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
    for s in variable:
        fixed.append(HEADINGS[s])
    layered = question is not None
    forced = {}
    if layered:
        # no layer is reduced to nothing: the first line of each (the dipole and the exhaustion line of the data at
        # the signal) are in the text before any share is given out
        for s in variable:
            if s != "state_layers" and cand[s]:
                forced[s] = 2 if s == "data_at_signal" else 1
                lines[s] += cand[s][:forced[s]]
                fixed += [l["text"] for l in lines[s]]
        gens = []
        for L in slayers:
            known = {"known_at_ns": moment, "basis": "the signal's own tick", "row_kind": "state",
                     "sequence": None, "run": None, "section": "state_layers", "layer": L["name"]}
            hdr = dict(known, source=f"layer:{L['name']}",
                       text=f"layer:{L['name']} | {L['count']} lines in all; the head is shown here and the whole is in "
                            f"state.json under {' > '.join(L['key'].split('.'))}")
            it = _leaves(L["value"])
            first = next(it, None)
            lines["state_layers"].append(hdr)
            fixed.append(hdr["text"])
            rows = []
            if first is not None:
                ln = dict(known, source=state_row_id(L["key"], first[0]),
                          text=state_row_text(L["key"], first[0], first[1]))
                lines["state_layers"].append(ln)
                fixed.append(ln["text"])
            gens.append((L, it, known))
    full = {k: len(cand[k]) for k in variable if k != "state_layers"}
    full["state_layers"] = sum(max(L["count"] - 1, 0) for L in slayers)
    if q_meta is not None:
        full.update(book_bid=q_meta["book_bid"], book_ask=q_meta["book_ask"])
    fixed += foot(full)
    left = budget_chars - len("\n".join(fixed)) - 2
    if left < 0:
        raise ValueError(f"budget {budget} tokens is below the fixed part of the packet ({-left} characters short)")
    cut = {}

    def fill(s, share):
        used = 0
        for ln in cand[s][len(lines[s]):]:
            if used + len(ln["text"]) + 1 > share:
                break
            lines[s].append(ln)
            used += len(ln["text"]) + 1
        cut[s] = len(cand[s]) - len(lines[s])
        return used

    def fill_state_layers(share):
        used, shown_rows = 0, 0
        for i, (L, it, known) in enumerate(gens):
            mine = (share - used) // (len(gens) - i)
            got = 0
            for path, value in it:
                ln = dict(known, source=state_row_id(L["key"], path), text=state_row_text(L["key"], path, value))
                if got + len(ln["text"]) + 1 > mine:
                    break
                lines["state_layers"].append(ln)
                got += len(ln["text"]) + 1
            used += got
        shown = sum(1 for l in lines["state_layers"] if not l["source"].startswith("layer:"))
        cut["state_layers"] = sum(L["count"] for L in slayers) - shown
        return used
    if layered:
        room = int(left * STATE_SHARE)
        for i, s in enumerate(QUESTION_SECTIONS):
            used = fill_state_layers(room // (len(QUESTION_SECTIONS) - i)) if s == "state_layers" else \
                fill(s, room // (len(QUESTION_SECTIONS) - i))
            room -= used
            left -= used
        if q_meta is not None:
            for s in ("bid", "ask"):
                cut[f"book_{s}"] = q_meta[f"book_{s}"] - sum(1 for l in lines["data_at_signal"]
                                                              if l["source"].startswith(f"state:book:{s}:"))
    for i, s in enumerate(VARIABLE):
        left -= fill(s, left // (len(VARIABLE) - i))
    if layered:     # each state layer's head stands under its own header
        order = {L["name"]: i for i, L in enumerate(slayers)}
        lines["state_layers"].sort(key=lambda l: order[l["layer"]])
    pk = {"path": PATH_NAME, "run": run, "sequence": sequence, "rule": rule, "trade_day": day,
          "moment_ns": moment, "budget_tokens": budget, "head": head, "lines": [l for s in sections for l in lines[s]],
          "foot": foot(cut), "cut": cut,
          "lines_in": {s: len(lines[s]) for s in sections}}
    if question is not None:
        state = question.get("state")
        pk["sections"] = list(sections)
        pk["state"], pk["flow_lines"], pk["exchange_ns"] = state, question.get("lines"), question.get("exchange_ns")
        layers = {}
        for s in sections:
            if s == "state_layers":
                continue
            rows = cand[s] if s in cand else lines[s]
            layers[s] = {"count": len(rows), "in_text": len(lines[s]), "where": "layers.json", "rows": rows}
        for L in slayers:
            shown = sum(1 for l in lines["state_layers"] if l.get("layer") == L["name"] and not l["source"].startswith("layer:"))
            layers[L["name"]] = {"count": L["count"], "in_text": shown, "where": "state.json"}
        pk["layers"] = layers
        pk["planes_not_placed"] = [{"layer": n, "rows": r, "reason": w} for n, r, w in planes]
        pk["question_state"] = {"sequence": question.get("sequence"), "tape_received_ns": question.get("tape_received_ns"),
                                "state_known_at_tape_ns": _g(state, "known_at_tape_ns"),
                                "state_sha256": None if state is None else state_sha256(state)}
    pk["text"] = render(pk)
    pk["tokens_estimated"] = dp.estimate_tokens(pk["text"])
    pk["sha256"] = hashlib.sha256(pk["text"].encode("utf-8")).hexdigest()
    pk["not_in_packet"] = pk["foot"]
    return pk


def render(pk: dict) -> str:
    out = list(pk["head"])
    for s in pk.get("sections", SECTIONS):
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
    allowed = pk.get("sections", SECTIONS)
    qs = pk.get("question_state")
    if qs is not None:
        for what, t in (("the state's known_at_tape_ns", qs.get("state_known_at_tape_ns")),
                        ("the question's tape_received_ns", qs.get("tape_received_ns"))):
            if qs.get("state_sha256") is None and what.startswith("the state"):
                continue
            if t != moment:
                out.append(f"{what} is {t}, not the signal's moment {moment}: the state is from another tick "
                           f"(state known at {qs.get('state_known_at_tape_ns')}, question received at "
                           f"{qs.get('tape_received_ns')}, signal at {moment})")
        if qs.get("sequence") != seq:
            out.append(f"the question is sequence {qs.get('sequence')}, not the signal's {seq}")
    for name, lay in (pk.get("layers") or {}).items():
        if lay.get("where") not in ("layers.json", "state.json"):
            out.append(f"layer {name}: no place is named for the rest of it")
        if lay.get("in_text", 0) > lay.get("count", 0):
            out.append(f"layer {name}: more lines in the text than it holds")
    seen = {(l.get("section"), l.get("source")) for l in pk["lines"]}
    every = list(pk["lines"]) + [r for lay in (pk.get("layers") or {}).values() for r in lay.get("rows", [])
                                 if (r.get("section"), r.get("source")) not in seen]
    by_q = {r.get("signal_sequence"): r for r in (journal_rows or []) if r.get("kind") == "question"}
    for ln in every:
        who = ln.get("source")
        sec = ln.get("section")
        if sec not in allowed:
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
        if sec in ("data_at_signal", "state_layers"):
            if k != moment:
                out.append(f"{who}: a line of the state is known at {k}, not the signal's own tick {moment}")
            continue
        if sec == "earlier_q":
            if ln.get("sequence") is None or ln["sequence"] >= seq:
                out.append(f"{who}: the earlier signal {ln.get('sequence')} is not below the signal's {seq}")
            row = by_q.get(ln.get("sequence"))
            if journal_rows and row is not None and (q_line(row)["text"] != ln["text"] or row.get("received") != k):
                out.append(f"{who}: the line is not its journal question row's lines")
            continue
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
