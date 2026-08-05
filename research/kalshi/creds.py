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


# THE CONTAINER LIES ABOUT AWS. Claude Code cloud containers inject PLACEHOLDER values
# (AWS_ACCESS_KEY_ID=proxy-injected) that sit FIRST in boto3's resolution order and therefore
# override ~/.aws/credentials. That cost S100 an hour and the documented workaround has been to
# remember `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY` on every command. A resolution
# order that reads the environment first - which this module does - walks straight into it and
# hands back "proxy-injected" as though it were a key: present, well-formed, wrong. Handle it
# HERE so no caller has to remember anything.
PLACEHOLDERS = ("proxy-injected",)
_AWS_VARS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")


def _is_placeholder(v):
    return bool(v) and v.strip().lower().startswith(PLACEHOLDERS)


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
    if _is_placeholder(v):
        v = None                      # the container's injected stub is NOT a credential
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


def aws_client(service, region):
    """A boto3 client that survives the container's injected placeholders.

    Strips the stub AWS vars from this process so boto3 falls through to ~/.aws/credentials,
    which is where the real pair lives. This replaces the `env -u AWS_ACCESS_KEY_ID
    -u AWS_SECRET_ACCESS_KEY python ...` incantation - a rule you have to remember is a rule
    that eventually gets forgotten, and the failure it produces (InvalidClientTokenId on a
    known-good key) looks like a dead key rather than a shadowed one.
    """
    import boto3
    for k in _AWS_VARS:
        if _is_placeholder(os.environ.get(k)):
            os.environ.pop(k, None)
    return boto3.client(service, region_name=region)


def status():
    """Which secrets are resolvable, by NAME only - never a value."""
    for n in ("EIA_API_KEY", "AWS_ACCESS_KEY_ID", "DATABENTO_API_KEY"):
        src = ("CONTAINER PLACEHOLDER (ignored)" if _is_placeholder(os.environ.get(n)) else
               "env" if os.environ.get(n) else
               "~/.config/markets/env" if _from_file(HOME_ENV, n) else
               "LEGACY scratchpad" if _from_file(LEGACY, n) else "ABSENT")
        print(f"  {n:<22} {src}")
    print(f"  {'(aws fallback)':<22} ~/.aws/credentials "
          f"{'present' if os.path.exists(os.path.expanduser('~/.aws/credentials')) else 'ABSENT'}"
          f"  - use creds.aws_client(), not bare boto3.client()")


if __name__ == "__main__":
    status()
