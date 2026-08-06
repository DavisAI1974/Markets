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


SSM_PREFIX = "/markets"          # SecureString home for non-bootstrap keys (S114)


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
    # S114: DURABLE FALLBACK - AWS SSM Parameter Store, SecureString, in our own account.
    #
    # THE PROBLEM IT SOLVES. `~/.config/markets/env` is the canonical home and is chmod 600 outside
    # the repo, which is right - but it lives in an EPHEMERAL CONTAINER and does not survive the
    # session. Secrets can never go into git (CLAUDE.md: the full secret is NEVER written in this
    # repo - it is/was public, and AWS kills keys it finds on GitHub). So before S114 every key had
    # to be re-pasted by hand every session, all four of them.
    #
    # WHAT IS AND IS NOT STORED HERE, and the distinction is the whole design: the AWS PAIR is the
    # BOOTSTRAP and cannot live here - you need it to read SSM at all. Everything else can, so
    # DATABENTO_API_KEY and EIA_API_KEY are pulled automatically once the AWS pair is present.
    # That takes the per-session paste from four values to two.
    #
    # Rotation is unaffected: these are the same keys, in the same account, and D1 still says they
    # do not rotate during the walk. `python creds.py --sync-ssm` re-pushes after a rotation.
    if name not in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        try:
            _ssm = aws_client("ssm", os.environ.get("AWS_REGION") or "us-east-2")
            v = _ssm.get_parameter(Name=f"{SSM_PREFIX}/{name}",
                                   WithDecryption=True)["Parameter"]["Value"]
            if v:
                print(f"[creds] {name} retrieved from SSM {SSM_PREFIX}/{name} (SecureString). "
                      f"Write it to {HOME_ENV} to avoid the round trip.")
                return v
        except Exception:
            pass                      # SSM unreachable or param absent - fall through to the error
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


def sync_ssm():
    """Push the non-bootstrap keys to SSM SecureString, then VERIFY BY READ-BACK (D47).

    Run after Greg pastes a fresh set, and after any rotation. The AWS pair is deliberately NOT
    pushed - it is the bootstrap that reads SSM in the first place.
    """
    ssm = aws_client("ssm", os.environ.get("AWS_REGION") or "us-east-2")
    ok = True
    for name in ("DATABENTO_API_KEY", "EIA_API_KEY"):
        v = get(name, required=False)
        if not v:
            print("  SKIP %s - not resolvable locally, nothing to push" % name)
            continue
        ssm.put_parameter(Name="%s/%s" % (SSM_PREFIX, name), Value=v, Type="SecureString",
                          Overwrite=True,
                          Description="DavisAI Markets session credential. Never echo. See KEYS.md.")
        back = ssm.get_parameter(Name="%s/%s" % (SSM_PREFIX, name),
                                 WithDecryption=True)["Parameter"]["Value"]
        good = back == v
        ok = ok and good
        print("  %s/%-24s pushed, read-back matches: %s" % (SSM_PREFIX, name, good))
    print("SYNC OK" if ok else "SYNC FAILED - a value did not survive the round trip")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys as _s
    if "--sync-ssm" in _s.argv:
        _s.exit(sync_ssm())
    status()
