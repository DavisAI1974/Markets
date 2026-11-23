"""Manual Actions entry point. Replay only. Any interruption closes the quote-only run."""

import argparse
import base64
from collections import deque
from datetime import date
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit

import requests
from .api import wire
from .session import Session
from root.calendar import trade_day_bounds


def notify(reason, run):
    response = requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.environ["PUSHOVER_APP_TOKEN"],
            "user": os.environ["PUSHOVER_USER_KEY"],
            "message": f"NG paper run {run}: {reason}",
        },
        timeout=5,
    )
    if not response.ok:
        raise RuntimeError("phone notice delivery failed")


class Publication:
    """Publish on a dedicated run branch. Stage only the run directory; keep credentials in memory."""

    def __init__(self, session, url):
        self.s = session
        self.url = url
        self.last_push = time.monotonic()
        self.sent = 0
        self.http = requests.Session()
        self.http.headers["Authorization"] = "Bearer " + os.environ["PAPER_RELAY_TOKEN"]
        token = base64.b64encode(("x-access-token:" + os.environ["MARKETS_DATA_TOKEN"]).encode()).decode()
        self.env = dict(
            os.environ,
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
            GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + token,
            GIT_TERMINAL_PROMPT="0",
        )
        self.branch = "paper-runs/" + session.run

    def command(self, *args):
        proc = subprocess.run(
            ["git", "-C", str(self.s.data_root), *args],
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=25,
        )
        if proc.returncode:
            raise RuntimeError("markets-data git " + args[0] + " failed")

    def push(self):
        s = self.s
        path = s.folder.relative_to(s.data_root).as_posix()
        with s.lock:
            if not s.receives.closed:
                s.receives.flush()
            self.command("add", "--", path)
        self.command(
            "-c",
            "user.name=NG Paper Recorder",
            "-c",
            "user.email=paper@users.noreply.github.com",
            "commit",
            "--allow-empty",
            "-qm",
            "Append paper events [skip ci]",
            "--",
            path,
        )
        self.command("push", "origin", "HEAD:refs/heads/" + self.branch)
        self.last_push = time.monotonic()

    def send(self, event):
        response = self.http.post(
            self.url + "/ingest", json=self.packet(event), timeout=8, allow_redirects=False
        )
        if response.status_code == 409:
            target = response.json().get("detail")
            if (
                isinstance(target, dict)
                and type(target.get("next")) is int
                and 0 <= target["next"] < event["sequence"]
            ):
                with (self.s.folder / "events.jsonl").open(encoding="utf8") as f:
                    for line in f:
                        old = json.loads(line)
                        if target["next"] <= old["sequence"] <= event["sequence"]:
                            self.post_again(old)
                return
        if response.status_code != 200:
            raise RuntimeError("Render event delivery failed")

    def packet(self, event):
        status = self.s.status()
        status["events"] = event["sequence"] + 1
        status["status"] = (
            event["reason"] if event["kind"] == "status" and event["reason"] != "started" else "active"
        )
        return {"event": wire(event), "status": status}

    def post_again(self, event):
        response = self.http.post(
            self.url + "/ingest", json=self.packet(event), timeout=8, allow_redirects=False
        )
        if response.status_code != 200:
            raise RuntimeError("Render journal recovery failed")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--trade-day", type=date.fromisoformat, required=True)
    p.add_argument("--market", default="nymex-ng")
    p.add_argument("--message-budget", type=int, required=True)
    p.add_argument("--event-budget", type=int, required=True)
    p.add_argument("--greg-go", action="store_true")
    args = p.parse_args()
    if not args.greg_go:
        p.error("Greg must start this run")
    url = os.environ["PAPER_RELAY_URL"].rstrip("/")
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname or urlsplit(url).username:
        p.error("Render must use an HTTPS URL")
    for key in ("PUSHOVER_APP_TOKEN", "PUSHOVER_USER_KEY", "PAPER_RELAY_TOKEN", "MARKETS_DATA_TOKEN"):
        if not os.environ.get(key):
            p.error("required run credential missing: " + key)
    s = pub = None
    finished = threading.Event()
    alert_sent = threading.Event()
    why = "failure"
    try:
        requests.get(url + "/health", timeout=90).raise_for_status()
        s = Session(
            args.data,
            args.trade_day,
            message_budget=args.message_budget,
            output_budget=args.event_budget,
            market_key=args.market,
        )
        pub = Publication(s, url)
        pending = deque()
        s.on_event = pending.append
        with (s.folder / "events.jsonl").open(encoding="utf8") as f:
            pending.extend(json.loads(row) for row in f)
        stopped = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stopped.set())
        opens, halts = trade_day_bounds(args.trade_day)
        base = None
        indices = ((f, i) for f in s.feed.week for i in range(len(f.records)))

        def guard():
            while not finished.wait(0.1):
                reason = s.due()
                if reason:
                    s.stop(reason)
                    try:
                        notify(reason, s.run)
                        alert_sent.set()
                    except requests.RequestException:
                        pass
                    return

        watcher = threading.Thread(target=guard, daemon=True)
        watcher.start()

        def deliver():
            while pending:
                event = pending.popleft()
                pub.send(event)
                if event["kind"] == "paper order":
                    pub.push()
            if time.monotonic() - pub.last_push >= 60:
                pub.push()

        while s.state == "active":
            if stopped.is_set():
                why = "run stopped"
                break
            if s.due():
                why = s.due()
                break
            deliver()
            # Peek at the next raw receive time without exposing it to any strategy.
            # The scheduler paces delivery; only step() admits that record into the engine.
            next_row = next(indices, None)
            if next_row:
                f, i = next_row
                r = f.records[i]
                if i >= f.vendor_snapshot and opens <= int(r["ts_event"]) < halts:
                    if base is None:
                        base = time.monotonic_ns() - int(r["ts_recv"])
                    until = base + int(r["ts_recv"])
                    while time.monotonic_ns() < until and not stopped.is_set() and not s.due():
                        stopped.wait(min(0.25, max(0, (until - time.monotonic_ns()) / 1e9)))
                        if time.monotonic() - pub.last_push >= 60:
                            pub.push()
            if stopped.is_set() or s.due():
                continue
            s.step(s.cursor)
        if s.state != "active":
            why = s.state
    finally:
        # Attempt the phone, local receipt, relay and final push independently on failure.
        finished.set()
        if "watcher" in locals():
            watcher.join()
        errors = []
        if s is not None:
            try:
                s.stop(why)
            except Exception:
                errors.append("close")
        try:
            if not alert_sent.is_set():
                notify(why, s.run if s else "preflight")
        except Exception:
            errors.append("phone")
        if pub is not None:
            try:
                deliver()
            except Exception:
                errors.append("relay")
            try:
                pub.push()
            except Exception:
                errors.append("git")
        if errors:
            try:
                notify("failure during final delivery", s.run if s else "preflight")
            except Exception:
                pass
            raise RuntimeError("final delivery failed: " + ", ".join(errors))


if __name__ == "__main__":
    main()
