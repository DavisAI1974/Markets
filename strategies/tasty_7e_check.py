#!/usr/bin/env python3
"""Stage 7e: a ONE-TIME CHECK of tastytrade, not a trading runner.

Question 1: does the SANDBOX list and accept natural gas futures (and their options),
            and does a natural gas future order fill there?
Question 2: what does the PRODUCTION quote stream (DXLink) send for natural gas:
            which event types, every field name and value, which time fields.

Sub-commands (run one at a time):
  sandbox-lookup   token, accounts, products, NG futures, NG option chain
  sandbox-order    dry-run, and with --submit a real sandbox order and its polling
  prod-stream      production READ-ONLY market data: futures lookup, quote token, DXLink stream

Everything seen is written append-only as JSONL into --out (a markets-data folder,
never inside the Markets repo), plus a receipt. Credentials come only from environment
variables and are never printed or written. Counts only: no averages, no statistics.
"""
import argparse
import asyncio
import datetime
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

USER_AGENT = "davisai-paper/0.1"
# The ONLY place a host is named. Every REST request is built from this table.
BASES = {
    "sandbox": "https://api.cert.tastyworks.com",
    "prod": "https://api.tastyworks.com",
}
CRED_NAMES = {
    "sandbox": ("TASTY_SANDBOX_CLIENT_ID", "TASTY_SANDBOX_CLIENT_SECRET", "TASTY_SANDBOX_REFRESH_TOKEN"),
    "prod": ("TASTY_PROD_CLIENT_ID", "TASTY_PROD_CLIENT_SECRET", "TASTY_PROD_REFRESH_TOKEN"),
}
SECRET_WORDS = ("token", "secret", "authorization", "password", "cookie")   # key contains one of these
SECRET_KEYS = {"client_id", "id_token"}                                   # or equals one of these
TERMINAL = {"filled", "cancelled", "expired", "rejected", "removed", "partially removed"}
EVENT_TYPES = ["Quote", "Trade", "TradeETH", "TimeAndSale", "Summary", "Profile", "Order"]
HTTP_TIMEOUT_SECONDS = 30   # transport limit for one HTTP call (our choice, see receipt)
MAX_ATTEMPTS = 4            # for 429 and 5xx, never for an order submit
BACKOFF_RULE = "sleep 2**attempt seconds plus uniform(0,1) seconds, between attempts"
KEEPALIVE_SECONDS = 30      # the documented interval
# 0 = the server does not group events over a period: we ask for every event as it occurs
AGGREGATION_PERIOD = 0
NO_TYPE = "<no type>"
LEARN_FLOOR = 8             # shortest string learned as a secret from a response (credentials: any length)
SETUP_VERSION = "0.1-DXF-JS/0.3.0"
KEEPALIVE_TIMEOUT = 60      # keepaliveTimeout and acceptKeepaliveTimeout in SETUP
FEED_CHANNEL = 3
DATA_FORMAT = "FULL"
START_DATE_RULE = "previous day in US Eastern time (America/New_York), yyyy-mm-dd"

SECRETS = set()   # every secret string this run knows; scrubbed out of everything written or printed


class StepStop(Exception):
    """This step cannot go on; what was seen is already recorded."""


class Uncertain(Exception):
    """A request may or may not have reached the server."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # never follow a redirect: a 3xx is recorded and stops the step
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


# ---------------------------------------------------------------- secrets

def is_secret_key(k):
    n = str(k).lower().replace("-", "_")
    return n in SECRET_KEYS or any(w in n for w in SECRET_WORDS)


def add_secret(s):
    if isinstance(s, str) and len(s) >= LEARN_FLOOR:
        SECRETS.add(s)


def learn_secrets(x):
    """Every string value under a secret-looking key becomes a known secret."""
    if isinstance(x, dict):
        for k, v in x.items():
            if is_secret_key(k) and isinstance(v, str):
                add_secret(v)      # learned from a response: the 8-character floor applies
            learn_secrets(v)
    elif isinstance(x, list):
        for v in x:
            learn_secrets(v)


def scrub(text):
    """Replace every known secret string (and its JSON-escaped form) by <redacted>."""
    text = str(text)
    # the server may write "/" as "\/": match that form too, and the JSON-escaped form of each
    base = set(SECRETS) | {x.replace("/", "\\/") for x in SECRETS}
    # one level of JSON escaping (as the server writes it), with and without non-ASCII escaped, and the
    # second level (as raw server text looks once our own line is written around it)
    once = {json.dumps(x)[1:-1] for x in base} | {json.dumps(x, ensure_ascii=False)[1:-1] for x in base}
    forms = base | once | {json.dumps(x)[1:-1] for x in once}
    for s in sorted(forms, key=len, reverse=True):
        text = text.replace(s, "<redacted>")
    return text


def redact(x):
    """Copy of x with the value of every secret-looking key replaced by <redacted>."""
    if isinstance(x, dict):
        return {k: ("<redacted>" if is_secret_key(k) else redact(v)) for k, v in x.items()}
    if isinstance(x, list):
        return [redact(v) for v in x]
    return x


def say(text):
    print(scrub(text))


def dget(x, *keys):
    """x[k1][k2]... where any level that is not an object gives None."""
    for k in keys:
        if not isinstance(x, dict):
            return None
        x = x.get(k)
    return x


# ---------------------------------------------------------------- small helpers

def stamp(ns):
    """UTC time to the nanosecond, safe in a file name."""
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime(ns // 10**9)) + f"{ns % 10**9:09d}Z"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_commit():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        return subprocess.run(["git", "-C", here, "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def read_creds(env):
    """Credentials from the environment only. Names a missing variable, never a value."""
    missing = [n for n in CRED_NAMES[env] if not os.environ.get(n)]
    if missing:
        sys.exit("missing environment variable(s): " + ", ".join(missing))
    cid, secret, refresh = (os.environ[n] for n in CRED_NAMES[env])
    SECRETS.update((cid, secret, refresh))   # known secrets, whatever their length
    return {"client_id": cid, "client_secret": secret, "refresh_token": refresh}


def check_out_dir(out):
    """Refuse a folder inside the Markets repo (or inside the repo this file lives in)."""
    real = os.path.realpath(out)
    here = os.path.dirname(os.path.abspath(__file__))
    banned = [os.path.realpath("/home/user/Markets")]
    try:
        top = subprocess.run(["git", "-C", here, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, check=True).stdout.strip()
        banned.append(os.path.realpath(top))
    except (OSError, subprocess.CalledProcessError):
        pass
    for b in banned:
        if os.path.commonpath([real, b]) == b:
            sys.exit(f"--out must not be inside the Markets repo ({b})")
    return real


# ---------------------------------------------------------------- files: ALL writing goes through here

def new_file(ctx, name):
    """Create a file (exclusive: never rewrites one) and track it at creation."""
    path = os.path.join(ctx["out"], name)
    f = open(path, "xb")
    ctx["files"].append(path)
    return f


def write_text_file(ctx, name, text):
    f = new_file(ctx, name)
    with f:
        f.write(scrub(text).encode())


class Recorder:
    """Append-only JSONL file; one line per request, response, note or stream message.
    Every line is scrubbed of known secrets here, so nothing can bypass it."""

    def __init__(self, ctx, name):
        self.f = new_file(ctx, name)

    def write(self, **fields):
        line = scrub(json.dumps(fields, separators=(",", ":"), default=str))
        self.f.write(line.encode() + b"\n")
        self.f.flush()

    def note(self, text):
        self.write(t_ns=time.time_ns(), kind="note", text=text)

    def close(self):
        self.f.close()


# ---------------------------------------------------------------- REST

def prod_guard(method, path):
    """Every production request goes through here. Production is MARKET DATA ONLY:
    GET only (plus the one token POST), and never a path with /orders."""
    if method == "POST" and path == "/oauth/token":
        return
    if method != "GET":
        raise RuntimeError(f"production guard: {method} {path} refused (GET only)")
    if "/orders" in path:
        raise RuntimeError(f"production guard: {path} refused (no /orders on production)")


def http(ctx, method, path, body=None, retry=True, auth=True):
    """One REST call with recording, backoff on 429/5xx (retry=True only), and one re-mint on 401
    (retry=True only). With retry=False (an order submit) nothing is ever sent twice: a network
    failure, a 401 or a 5xx raises Uncertain. Raises StepStop on any other non-2xx."""
    env = ctx["env"]
    if env == "prod":
        prod_guard(method, path)
    base = BASES[env]
    host = base.split("//", 1)[1]
    attempts = MAX_ATTEMPTS if retry else 1
    attempt, reminted = 0, False
    while True:
        attempt += 1
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        if auth and ctx.get("token"):
            headers["Authorization"] = "Bearer " + ctx["token"]
        ctx["rec"].write(t_ns=time.time_ns(), kind="request", host=host, method=method, path=path,
                         attempt=attempt, headers=redact(headers), body=redact(body))
        status, text, hdrs, failure = None, "", {}, None
        try:
            req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
            with OPENER.open(req, timeout=HTTP_TIMEOUT_SECONDS) as r:
                status, text, hdrs = r.status, r.read().decode("utf-8", "replace"), dict(r.headers.items())
        except urllib.error.HTTPError as e:
            status, text, hdrs = e.code, e.read().decode("utf-8", "replace"), dict(e.headers.items())
        except OSError as e:   # timeouts, resets, DNS
            failure = f"{type(e).__name__}: {e}"
        t_ns = time.time_ns()
        try:
            obj = json.loads(text) if text else None
        except ValueError:
            obj = None
        learn_secrets(obj)   # before anything is written: the new access token must be scrubbed too
        if failure:
            ctx["rec"].write(t_ns=t_ns, kind="response", host=host, method=method, path=path,
                             attempt=attempt, status=None, error=failure)
        else:
            rec = dict(t_ns=t_ns, kind="response", host=host, method=method, path=path,
                       attempt=attempt, status=status, headers=redact(hdrs), body_text=scrub(text))
            if obj is not None:
                rec["body"] = redact(obj)
            ctx["rec"].write(**rec)
        if status == 401 and retry and auth and not reminted and path != "/oauth/token":
            reminted = True       # token expired: mint once and send the same request again
            attempt -= 1
            mint(ctx)
            continue
        if status is not None and 200 <= status < 300:
            return status, obj
        again = failure is not None or status == 429 or status >= 500
        if retry and again and attempt < attempts:
            time.sleep(2 ** attempt + random.uniform(0, 1))   # backoff with jitter
            continue
        if not retry and (failure or status == 401 or status >= 500):
            raise Uncertain(failure or f"HTTP {status}")
        raise StepStop(f"{method} {path}: " + (failure or f"HTTP {status}"))


def mint(ctx):
    """Mint a fresh 15-minute access token from the refresh token."""
    ctx["token"] = None
    body = {"grant_type": "refresh_token", **ctx["creds"]}
    if ctx["env"] == "prod":
        body["scope"] = "read"   # the production token can only read
    _, obj = http(ctx, "POST", "/oauth/token", body, auth=False)
    if not obj or "access_token" not in obj:
        raise StepStop("token response had no access_token")
    add_secret(obj["access_token"])
    ctx["token"] = obj["access_token"]


def try_call(ctx, method, path, **kw):
    """A step that may fail without ending the run: the failure is recorded and printed."""
    try:
        status, obj = http(ctx, method, path, **kw)
        say(f"  {method} {path} -> {status}")
        return obj
    except (StepStop, Uncertain) as e:
        ctx["failed"].append({"step": f"{method} {path}", "note": scrub(str(e))})
        say(f"  step stopped: {e}")
        return None


# ---------------------------------------------------------------- sandbox-lookup

def cmd_sandbox_lookup(ctx, args):
    mint(ctx)
    for path in ("/customers/me/accounts", "/instruments/future-products",
                 "/instruments/futures?product-code[]=NG", "/futures-option-chains/NG"):
        try_call(ctx, "GET", path)


# ---------------------------------------------------------------- sandbox-order

def has_identifier(x, ext):
    """True if any order object in x has external-identifier equal to ext."""
    if isinstance(x, dict):
        return x.get("external-identifier") == ext or any(has_identifier(v, ext) for v in x.values())
    if isinstance(x, list):
        return any(has_identifier(v, ext) for v in x)
    return False


def check_uncertain_submit(ctx, acct, ext, max_pages):
    """After an uncertain submit: look in the live orders and in the orders since the previous day
    (US Eastern), page by page (each page recorded) until the identifier is found, a page is empty,
    the response's own pagination says no more pages, or max_pages is reached.
    Outcomes: found / not found / not found within N pages / could not check."""
    prev = (datetime.datetime.now(ZoneInfo("America/New_York")) - datetime.timedelta(days=1)).date().isoformat()
    result = {}
    for label, base, sep in (("live", f"/accounts/{acct}/orders/live", "?"),
                             ("since_previous_day_et", f"/accounts/{acct}/orders?start-date={prev}", "&")):
        outcome, more = "not found", False
        for page in range(max_pages):
            obj = try_call(ctx, "GET", base + (f"{sep}page-offset={page}" if page else ""))
            if obj is None:
                outcome = "could not check"
                break
            if has_identifier(obj, ext):
                outcome = "found"
                break
            pag = dget(obj, "pagination")
            total = dget(pag, "total-pages")
            more = bool(dget(obj, "data", "items")) and isinstance(total, int) and page + 1 < total
            if not more:    # empty page, or the response says there are no more (or says nothing)
                break
        else:
            more = True
        if outcome == "not found" and more:
            outcome = f"not found within {max_pages} pages"
        result[label] = outcome
    ctx["rec"].note(f"uncertain submit, external-identifier {ext}: {json.dumps(result)}")
    say(f"  uncertain submit; external-identifier check: {json.dumps(result)}")


def final_records(ctx, acct):
    try_call(ctx, "GET", f"/accounts/{acct}/positions")
    try_call(ctx, "GET", f"/accounts/{acct}/orders/live")


def cmd_sandbox_order(ctx, args):
    mint(ctx)
    acct = args.account
    leg = {"instrument-type": "Future", "symbol": args.symbol, "action": args.action,
           "quantity": args.quantity}
    body = {"time-in-force": args.time_in_force, "order-type": args.order_type}
    if args.gtc_date:
        body["gtc-date"] = args.gtc_date
    if args.order_type == "Limit":
        body["price"] = args.price   # exactly as given, as a string: no rounding, no tick change
        # the docs: buying is a Debit, selling is a Credit
        body["price-effect"] = "Debit" if args.action == "Buy" else "Credit"
    body["legs"] = [leg]

    _, obj = http(ctx, "POST", f"/accounts/{acct}/orders/dry-run", body)
    found = {}
    for where, src in (("top", obj), ("data", dget(obj, "data"))):
        for key in ("errors", "warnings"):
            if dget(src, key):
                found[f"{where}.{key}"] = src[key]
    if found:
        ctx["rec"].note("dry-run returned errors or warnings (a warning means the order would be rejected): "
                        "nothing submitted. " + json.dumps(found))
        raise StepStop("dry-run returned errors or warnings: " + ", ".join(found))
    if not args.submit:
        say("  dry-run clean; no --submit: nothing was submitted")
        return

    ext = f"davisai-{stamp(time.time_ns())}-{args.symbol.lstrip('/')}"
    submit_body = dict(body, **{"external-identifier": ext})
    try:
        _, obj = http(ctx, "POST", f"/accounts/{acct}/orders", submit_body, retry=False)
    except Uncertain as e:
        # never resubmit, on any outcome but a clean 2xx
        ctx["rec"].note(f"submit result uncertain ({e}); NOT resubmitting; checking for our external-identifier")
        check_uncertain_submit(ctx, acct, ext, args.max_pages)
        raise StepStop("uncertain submit") from e
    oid = dget(obj, "data", "order", "id")
    if oid is None:
        # a 2xx without the id where we look: as uncertain as a timeout. No guessing another key.
        ctx["rec"].note("submit response has no data.order.id where the code looks for it; the whole "
                        "response is recorded above; checking for our external-identifier; not polling")
        check_uncertain_submit(ctx, acct, ext, args.max_pages)
        final_records(ctx, acct)
        raise StepStop("submit response had no data.order.id")
    say(f"  submitted order id {oid}")

    status = None
    try:
        for i in range(args.poll_count):
            if i:
                time.sleep(args.poll_seconds)
            try:
                _, o = http(ctx, "GET", f"/accounts/{acct}/orders/{oid}")
            except StepStop as e:      # a failed poll is recorded; go on to the next
                ctx["failed"].append({"step": f"poll {i + 1}", "note": scrub(str(e))})
                ctx["rec"].note(f"poll {i + 1} failed: {e}")
                say(f"  poll {i + 1} failed: {e}")
                continue
            status = dget(o, "data", "status")
            say(f"  poll {i + 1}: status {status}")
            if str(status).lower() in TERMINAL:
                break
    finally:
        if str(status).lower() not in TERMINAL and args.cancel_if_open:
            ctx["rec"].note("order not known to be terminal after the last poll: cancelling (--cancel-if-open)")
            try_call(ctx, "DELETE", f"/accounts/{acct}/orders/{oid}")
            try_call(ctx, "GET", f"/accounts/{acct}/orders/{oid}")
        final_records(ctx, acct)


# ---------------------------------------------------------------- prod-stream

def is_time_field(n):
    n = n.lower()
    return "time" in n or "sequence" in n or "nanos" in n


def is_side_field(n):
    n = n.lower()
    return "side" in n or "aggressor" in n


def is_order_id_field(n):
    # index, id, orderId, marketMaker, mmid, or a camelCase name ending in a separate word Id / ID
    return n.lower() in ("index", "id", "orderid", "marketmaker", "mmid") or re.search(r"(?<=[a-z0-9])(Id|ID)$", n) is not None


def pick(ev, test):
    return {k: v for k, v in ev.items() if test(k)}


def summarize(stats):
    out = {}
    for typ, s in sorted(stats["events"].items()):
        e = {"events": s["count"], "field_names": sorted(s["fields"]),
             "time_fields_first": pick(s["first"], is_time_field),
             "time_fields_last": pick(s["last"], is_time_field),
             "side_fields_first": pick(s["first"], is_side_field)}
        if typ == "Order":
            e["order_id_fields_first"] = pick(s["first"], is_order_id_field)
        out[typ] = e
    note = None
    if stats["undecoded"]:
        note = ("some FEED_DATA items could not be decoded (neither object form nor COMPACT with the "
                "field lists FEED_CONFIG gave); the raw frames are in the JSONL")
    return {"messages_received": stats["n"], "messages_by_type": dict(sorted(stats["types"].items())),
            "feed_config_data_format": stats["format"], "feed_configs_as_received": stats["feed_configs"],
            "feed_data_items_not_decoded": stats["undecoded"], "undecoded_note": note,
            "events_by_event_type": out}


def add_event(stats, ev):
    typ = str(ev["eventType"]) if ev.get("eventType") is not None else "<no eventType>"
    s = stats["events"].setdefault(typ, {"count": 0, "fields": set(), "first": ev, "last": ev})
    s["count"] += 1
    s["fields"].update(ev.keys())
    s["last"] = ev


def decode_compact(stats, data):
    """COMPACT FEED_DATA: [label, rows, label, rows ...]; fields come from FEED_CONFIG eventFields."""
    i = 0
    while i < len(data):
        label = data[i]
        rows = data[i + 1] if i + 1 < len(data) else None
        i += 2
        fields = stats["compact_fields"].get(label) if isinstance(label, str) else None
        if not fields or not isinstance(rows, list) or not rows:
            stats["undecoded"] += 1
            continue
        if all(isinstance(r, list) for r in rows):
            chunks = rows
        elif len(rows) % len(fields) == 0:
            chunks = [rows[j:j + len(fields)] for j in range(0, len(rows), len(fields))]
        else:
            stats["undecoded"] += 1
            continue
        for c in chunks:
            if len(c) != len(fields):
                stats["undecoded"] += 1
            else:
                add_event(stats, dict(zip(fields, c)))


def add_stats(stats, msg):
    typ = msg.get("type") if isinstance(msg.get("type"), str) else NO_TYPE
    stats["types"][typ] = stats["types"].get(typ, 0) + 1
    if typ == "FEED_CONFIG":
        stats["feed_configs"].append(msg)      # every FEED_CONFIG is kept, as received
        if msg.get("dataFormat") is not None:
            stats["format"] = msg.get("dataFormat")
        ef = msg.get("eventFields")
        if isinstance(ef, dict):               # merge event type by event type; none given = no change
            stats["compact_fields"].update(ef)
    if typ != "FEED_DATA" or not isinstance(msg.get("data"), list):
        return
    data = msg["data"]
    if data and all(isinstance(x, dict) for x in data):
        for ev in data:
            add_event(stats, ev)
    elif data and stats["format"] == "COMPACT":
        decode_compact(stats, data)
    else:
        stats["undecoded"] += len(data) or 1


async def stream(ctx, url, token, symbols, max_messages, seconds, stats):
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed
    rec = ctx["rec"]
    host = url.split("/")[2]
    # the --seconds clock starts here, before the connection is made
    st = {"next_ka": time.monotonic() + KEEPALIVE_SECONDS, "auth_sent": False,
          "deadline": time.monotonic() + seconds if seconds else None}

    # ping_interval=None: no extra traffic of ours; DXLink has its own KEEPALIVE
    async with connect(url, user_agent_header=USER_AGENT, ping_interval=None, max_size=None) as ws:
        async def send(msg):
            t = time.time_ns()
            await ws.send(json.dumps(msg))
            rec.write(t_ns=t, kind="sent", host=host, body=redact(msg))

        async def recv_record():
            """Next message (recorded), or None once the stop condition is reached."""
            while True:
                now = time.monotonic()
                if (max_messages and stats["n"] >= max_messages) or (st["deadline"] and now >= st["deadline"]):
                    return None
                if now >= st["next_ka"]:
                    await send({"type": "KEEPALIVE", "channel": 0})
                    st["next_ka"] = now + KEEPALIVE_SECONDS
                wait = st["next_ka"] - now
                if st["deadline"]:
                    wait = min(wait, st["deadline"] - now)
                try:
                    raw = await asyncio.wait_for(ws.recv(), max(wait, 0.01))
                except asyncio.TimeoutError:
                    continue
                except ConnectionClosed as e:
                    raise StepStop(f"connection closed by server: {e}") from e
                t = time.time_ns()   # taken when the websocket library hands the frame over
                stats["n"] += 1
                try:
                    msg = json.loads(raw)
                except ValueError:
                    msg = {}
                learn_secrets(msg)   # a secret first seen in a frame is learned before the frame is written
                rec.write(t_ns=t, kind="received", host=host, msg_no=stats["n"], raw=scrub(raw))
                if not isinstance(msg, dict):
                    msg = {}
                add_stats(stats, msg)
                if st["auth_sent"] and msg.get("type") == "AUTH_STATE" and msg.get("state") == "UNAUTHORIZED":
                    raise StepStop("AUTH_STATE UNAUTHORIZED after our AUTH was sent")
                return msg

        async def wait_for(test, what):
            while True:
                msg = await recv_record()
                if msg is None:
                    raise StepStop(f"stop condition reached before {what}")
                if msg.get("type") == "ERROR":
                    raise StepStop(f"server sent ERROR before {what} (see the record)")
                if test(msg):
                    return msg

        await send({"type": "SETUP", "channel": 0, "version": SETUP_VERSION,
                    "keepaliveTimeout": KEEPALIVE_TIMEOUT, "acceptKeepaliveTimeout": KEEPALIVE_TIMEOUT})
        await wait_for(lambda m: m.get("type") == "AUTH_STATE", "AUTH_STATE")
        await send({"type": "AUTH", "channel": 0, "token": token})
        st["auth_sent"] = True
        await wait_for(lambda m: m.get("type") == "AUTH_STATE" and m.get("state") == "AUTHORIZED", "AUTHORIZED")
        await send({"type": "CHANNEL_REQUEST", "channel": FEED_CHANNEL, "service": "FEED", "parameters": {"contract": "AUTO"}})
        await wait_for(lambda m: m.get("type") == "CHANNEL_OPENED" and m.get("channel") == FEED_CHANNEL, "CHANNEL_OPENED")
        await send({"type": "FEED_SETUP", "channel": FEED_CHANNEL, "acceptAggregationPeriod": AGGREGATION_PERIOD,
                    "acceptDataFormat": DATA_FORMAT})
        await wait_for(lambda m: m.get("type") == "FEED_CONFIG", "FEED_CONFIG")
        await send({"type": "FEED_SUBSCRIPTION", "channel": FEED_CHANNEL, "reset": True,
                    "add": [{"type": t, "symbol": s} for s in symbols for t in EVENT_TYPES]})
        while await recv_record() is not None:
            pass
    # leaving the block closes the socket; nothing more is sent


def cmd_prod_stream(ctx, args):
    mint(ctx)
    obj = try_call(ctx, "GET", "/instruments/futures?product-code[]=NG")
    items = dget(obj, "data", "items")
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            say(f"  {item.get('symbol')}  streamer-symbol={item.get('streamer-symbol')}")
    if not args.streamer_symbol:
        ctx["rec"].note("no --streamer-symbol given: lookup only, stream not opened")
        say("  no --streamer-symbol given: choose one above and run again; stream not opened")
        return
    _, q = http(ctx, "GET", "/api-quote-tokens")
    d = dget(q, "data") if isinstance(dget(q, "data"), dict) else {}
    url = d.get("dxlink-url")
    if not d.get("token") or not url:
        raise StepStop("quote token response had no token or dxlink-url")
    add_secret(d["token"])
    parts = urllib.parse.urlparse(url)
    ctx["rec"].note(f"dxlink-url scheme {parts.scheme}, host {parts.netloc}")
    if parts.scheme != "wss":
        raise StepStop(f"dxlink-url scheme is {parts.scheme!r}, not wss: refusing to send the quote token")
    ctx["stats"] = {"n": 0, "types": {}, "events": {}, "undecoded": 0, "format": None, "compact_fields": {},
                    "feed_configs": []}
    asyncio.run(stream(ctx, url, d["token"], args.streamer_symbol, args.messages, args.seconds, ctx["stats"]))
    say(f"  messages received: {ctx['stats']['n']}")


# ---------------------------------------------------------------- main

ASKED = {
    "sandbox-lookup": "Does the sandbox list natural gas futures and their options (accounts, products, NG futures, NG option chain)?",
    "sandbox-order": "Does a natural gas future order get accepted and fill in the sandbox (dry-run, and with --submit the order and its polling)?",
    "prod-stream": "What event types, field names, values and time fields does the production DXLink feed send for the chosen natural gas streamer symbols?",
}


def pos_int(s):
    v = int(s)
    if v < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return v


def nonneg_float(s):
    v = float(s)
    if v < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return v


def pos_float(s):
    v = float(s)
    if v <= 0:
        raise argparse.ArgumentTypeError("must be more than 0")
    return v


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", required=True, help="folder to write into (a markets-data checkout; not inside the Markets repo)")

    sub.add_parser("sandbox-lookup", parents=[common], help="sandbox: accounts, futures products, NG futures, NG option chain")

    o = sub.add_parser("sandbox-order", parents=[common], help="sandbox: dry-run, and with --submit a real sandbox order")
    o.add_argument("--account", required=True, help="sandbox account number")
    o.add_argument("--symbol", required=True, help="futures symbol chosen from the lookup output, e.g. /NGF7")
    o.add_argument("--action", required=True, choices=["Buy", "Sell"])
    o.add_argument("--order-type", required=True, choices=["Market", "Limit"])
    o.add_argument("--price", help="Limit only; sent exactly as given")
    o.add_argument("--time-in-force", required=True, help="the doc says Day, GTC and GTD exist; sent exactly as given")
    o.add_argument("--gtc-date", help="yyyy-mm-dd; required with GTD, refused otherwise")
    o.add_argument("--quantity", required=True, type=pos_int)
    o.add_argument("--max-pages", type=pos_int, help="pages to follow when looking for our order after an uncertain submit, 1 or more (required with --submit)")
    o.add_argument("--submit", action="store_true", help="actually submit (without it only the dry-run is made)")
    o.add_argument("--poll-count", type=pos_int, help="number of polls, 1 or more (required with --submit)")
    o.add_argument("--poll-seconds", type=nonneg_float, help="seconds between polls, 0 or more (required with --submit)")
    o.add_argument("--cancel-if-open", action="store_true", help="after the last poll, cancel the order if not known to be terminal")

    p = sub.add_parser("prod-stream", parents=[common], help="production READ-ONLY: futures lookup, quote token, DXLink stream")
    p.add_argument("--streamer-symbol", action="append",
                   help="DXLink symbol to subscribe (repeatable). Without it only the futures lookup is made and the stream is not opened")
    p.add_argument("--messages", type=pos_int, help="stop after this many received messages (handshake messages included)")
    p.add_argument("--seconds", type=pos_float, help="stop this long after the clock starts, which is BEFORE the connection is made (connect and handshake included)")
    return ap, o, p


def finish(ctx, args, start_ns, stopped):
    """Summary (if the stream ran) then the receipt. Always runs; a failure here goes into the receipt."""
    problems = []
    try:
        if ctx["rec"] is not None:
            ctx["rec"].close()
    except Exception as e:
        problems.append(f"closing record: {e}")
    if ctx.get("stats") is not None:
        try:
            write_text_file(ctx, f"prod-stream-{ctx['stamp']}-summary.json",
                            json.dumps(summarize(ctx["stats"]), indent=2, sort_keys=True) + "\n")
        except Exception as e:
            problems.append(f"summary not written: {type(e).__name__}: {e}")
    files = []
    for f in ctx["files"]:
        try:
            files.append({"path": f, "bytes": os.path.getsize(f), "sha256": sha256_file(f)})
        except OSError as e:
            files.append({"path": f, "error": str(e)})
    commit = code_commit()
    receipt = {
        "sub_command": args.cmd, "arguments": vars(args), "asked": ASKED[args.cmd],
        "stopped_by": scrub(stopped), "failed_steps": ctx["failed"], "problems_writing_outputs": problems,
        "run_start_utc_ns": start_ns, "code_commit": commit,
        "code_file_sha256": sha256_file(os.path.abspath(__file__)),
        "constants_used": {"http_timeout_seconds": HTTP_TIMEOUT_SECONDS, "max_attempts": MAX_ATTEMPTS,
                           "backoff_rule": BACKOFF_RULE, "user_agent": USER_AGENT,
                           "accept_aggregation_period": AGGREGATION_PERIOD,
                           "keepalive_seconds": KEEPALIVE_SECONDS,
                           "setup_version": SETUP_VERSION, "keepaliveTimeout": KEEPALIVE_TIMEOUT,
                           "acceptKeepaliveTimeout": KEEPALIVE_TIMEOUT, "feed_channel": FEED_CHANNEL,
                           "acceptDataFormat": DATA_FORMAT, "event_types_asked_for": EVENT_TYPES,
                           "terminal_statuses": sorted(TERMINAL),
                           "secret_length_floors": {"learned_from_responses": LEARN_FLOOR,
                                                    "credentials": "none (any length)"},
                           "start_date_rule": START_DATE_RULE},
        "receive_time_note": "t_ns on a received stream message is time.time_ns() taken when the "
                             "websocket library hands the frame to our code",
        "files": files}
    rname = f"{args.cmd}-{ctx['stamp']}-receipt.json"
    write_text_file(ctx, rname, json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n")
    rpath = os.path.join(ctx["out"], rname)
    files.append({"path": rpath, "bytes": os.path.getsize(rpath), "sha256": sha256_file(rpath)})
    say("MANIFEST lines for the main session:")
    for e in files:
        if "sha256" in e:
            say(json.dumps({"path": e["path"], "bytes": e["bytes"], "sha256": e["sha256"],
                            "source": f"strategies/tasty_7e_check.py {args.cmd} @ {commit}"}))


def main():
    ap, o, p = build_parser()
    args = ap.parse_args()
    if args.cmd == "sandbox-order":
        if args.order_type == "Limit" and args.price is None:
            o.error("--price is required for a Limit order")
        if args.order_type == "Market" and args.price is not None:
            o.error("--price is only for a Limit order")
        if args.time_in_force.lower() == "gtd" and not args.gtc_date:
            o.error("--gtc-date is required when --time-in-force is GTD")
        if args.gtc_date and args.time_in_force.lower() != "gtd":
            o.error("--gtc-date is only for --time-in-force GTD")
        if args.gtc_date and not (re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.gtc_date) and _valid_date(args.gtc_date)):
            o.error("--gtc-date must be a real date as yyyy-mm-dd")
        if args.submit and (args.poll_count is None or args.poll_seconds is None or args.max_pages is None):
            o.error("--submit requires --poll-count, --poll-seconds and --max-pages")
    if args.cmd == "prod-stream" and args.streamer_symbol and not (args.messages or args.seconds):
        p.error("with --streamer-symbol, one of --messages or --seconds is required")

    out = check_out_dir(args.out)
    env = "prod" if args.cmd == "prod-stream" else "sandbox"
    creds = read_creds(env)            # stops here, naming a missing variable, before any file exists
    os.makedirs(out, exist_ok=True)

    start_ns = time.time_ns()
    ctx = {"env": env, "creds": creds, "token": None, "out": out, "stamp": stamp(start_ns),
           "files": [], "rec": None, "failed": []}
    fn = {"sandbox-lookup": cmd_sandbox_lookup, "sandbox-order": cmd_sandbox_order, "prod-stream": cmd_prod_stream}[args.cmd]
    stopped, code = "completed", 0
    try:
        ctx["rec"] = Recorder(ctx, f"{args.cmd}-{ctx['stamp']}.jsonl")
        fn(ctx, args)
        if ctx["failed"]:
            stopped = "completed with failed steps"
    except BaseException as e:    # everything, including Ctrl-C: the receipt is always attempted
        stopped = f"{type(e).__name__}: {e}"
        code = 130 if isinstance(e, KeyboardInterrupt) else 1
        say(f"STOPPED: {stopped}")
        try:
            ctx["rec"].note(f"run stopped: {scrub(stopped)}")
        except Exception:
            pass
    finally:
        try:
            finish(ctx, args, start_ns, stopped)
        except Exception as e:     # one scrubbed line, no traceback
            say(f"receipt not written: {type(e).__name__} (path {out}/{args.cmd}-{ctx['stamp']}-receipt.json)")
            code = code or 1
    return code


def _valid_date(s):
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    sys.exit(main())
