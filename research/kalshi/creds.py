"""creds.py - credential resolution, OUTSIDE the repo (S113, Greg: "no more scratchpad. It's in the sop").

D33 forbids the next session's runnables living in session scratchpad; D34 says git = code and
records, S3 = data. A credential is NEITHER - it must never be in git and must not sit in a
scratchpad directory that dies with the session. So it lives outside the repo tree entirely.

RESOLUTION ORDER, first hit wins:
  1. the process environment (works for CI, cron and one-off overrides)
  2. ~/.config/markets/env      chmod 600, outside the repo, the standard location
  3. <repo>/scratchpad/aws.env  LEGACY - still read so nothing breaks mid-migration, but it WARNS,
                                because that path is exactly what this module exists to end.
Never logs, prints or returns a value into an artifact. Callers get the string or a clear error.
"""
import os

HOME_ENV = os.path.expanduser("~/.config/markets/env")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY = os.path.join(_ROOT, "scratchpad", "aws.env")


def _from_file(path, name):
    if not os.path.exists(path):
        return None
    for line in open(path):
        if line.startswith(name + "="):
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    return None


def get(name, required=True):
    v = os.environ.get(name)
    if v:
        return v
    v = _from_file(HOME_ENV, name)
    if v:
        return v
    v = _from_file(LEGACY, name)
    if v:
        print(f"[creds] WARNING: {name} came from {LEGACY} - a scratchpad path. "
              f"Move it to {HOME_ENV} (chmod 600). See D33/D34.")
        return v
    if required:
        raise RuntimeError(
            f"{name} not found. Set it in the environment or write it to {HOME_ENV} "
            f"(chmod 600, outside the repo - never in git, never in scratchpad).")
    return None


def status():
    """Which secrets are resolvable, by NAME only - never a value."""
    for n in ("EIA_API_KEY", "AWS_ACCESS_KEY_ID", "DATABENTO_API_KEY"):
        src = ("env" if os.environ.get(n) else
               "~/.config/markets/env" if _from_file(HOME_ENV, n) else
               "LEGACY scratchpad" if _from_file(LEGACY, n) else "ABSENT")
        print(f"  {n:<22} {src}")


if __name__ == "__main__":
    status()
