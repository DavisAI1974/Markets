"""Spread already spawned ROOT readers that inherited the coordinator CPU."""

import argparse
import json
import os
import signal
import time
from pathlib import Path

BASE = Path("/opt/frankie-box")
TRADE_DATES = ("20231002", "20231003", "20231017")


def cpu_affinity(pid):
    return os.sched_getaffinity(pid)


def spread(parent, plan):
    consumer = plan["consumer_cpu"]
    lanes = plan["worker_cpus"]
    children = Path(f"/proc/{parent}/task/{parent}/children").read_text().split()
    workers = []
    for child in children:
        try:
            args = Path(f"/proc/{child}/cmdline").read_bytes()
        except FileNotFoundError:
            continue
        if b"from multiprocessing.spawn import spawn_main" in args:
            workers.append(int(child))
    for pid, cpu in zip(workers, lanes):
        try:
            if cpu_affinity(pid) != {consumer}:
                continue
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            continue
        try:
            signal.pidfd_send_signal(fd, signal.SIGSTOP)
            try:
                for _ in range(30):
                    status = Path(f"/proc/{pid}/status").read_text().splitlines()
                    if any(line.startswith("State:\tT") for line in status):
                        if cpu_affinity(pid) == {consumer}:
                            os.sched_setaffinity(pid, {cpu})
                            print(f"worker {pid}: startup CPU {cpu}", flush=True)
                        break
                    time.sleep(0.005)
            finally:
                signal.pidfd_send_signal(fd, signal.SIGCONT)
        except (FileNotFoundError, ProcessLookupError):
            continue
        finally:
            os.close(fd)
    return len(workers) >= plan["effective"]


def watch(day):
    control = BASE / "replay-control" / day
    root = BASE / "work/experiment-roots" / f"ng-replay-{day}"
    while True:
        stage = (control / "status").read_text().strip().split(" ", 1)[1]
        if stage.startswith("failed") or stage == "producer-handoff-sealed":
            return
        if stage == "root-native":
            try:
                progress = json.loads((root / "progress.json").read_bytes())
                parent = progress["pid"]
                args = Path(f"/proc/{parent}/cmdline").read_bytes()
                if b"frankie_box_experiment_root.py" in args and f"\0{day}\0".encode() in args:
                    if progress["stage"] == "source-journal-records":
                        if spread(parent, progress["reader_workers"]):
                            return
                    elif "reader_workers" in progress:
                        return
            except (FileNotFoundError, KeyError, ProcessLookupError, json.JSONDecodeError):
                pass
        time.sleep(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("day", choices=TRADE_DATES)
    watch(parser.parse_args().day)
