"""creds.py - credential resolution, OUTSIDE the repo (S113, Greg: "no more scratchpad. It's in the sop").

D33 forbids the next session's runnables living in session scratchpad; D34 says git = code and
records, S3 = data. A credential is NEITHER - it must never be in git and must not sit in a
scratchpad directory that dies with the session. So it lives outside the repo tree entirely.

RESOLUTION ORDER, first hit wins:
  0. MARKETS_<NAME> in the process environment (S115) - set ONCE in the Claude Code environment
                                configuration, injected into every fresh container automatically.
                                The prefix exists because the harness injects proxy-injected
                                PLACEHOLDERS under the bare AWS names; a prefixed name can never
                                collide with them. This is what ends the per-session paste.
  1. the process environment (works for CI, cron and one-off overrides; placeholders ignored)
  2. ~/.config/markets/env      chmod 600, outside the repo, the standard location
  3. <repo>/scratchpad/aws.env  LEGACY - still read so nothing breaks mid-migration, but it WARNS,
                                because that path is exactly what this module exists to end.
  4. AWS SSM Parameter Store    non-bootstrap keys only (S114) - needs the AWS pair to be
                                resolvable by 0-3 first.
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


def _from_env(name):
    """Process-environment resolution: MARKETS_<NAME> first (S115, un-shadowable by the
    container's placeholder injection because the name never collides), then the bare name
    with placeholders filtered out."""
    v = os.environ.get("MARKETS_" + name)
    if v and not _is_placeholder(v):
        return v.strip()
    v = os.environ.get(name)
    if v and not _is_placeholder(v):
        return v
    return None


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
    v = _from_env(name)               # MARKETS_-prefixed first; placeholder stubs are NOT credentials
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
    # S115: pass the RESOLVED pair explicitly when we have one - from MARKETS_ env vars, the env
    # file, or legacy. This makes a fresh container with only environment-config vars work with
    # zero setup (no ~/.aws/credentials write needed), and it is immune to the placeholder trap
    # by construction.
    ak = get("AWS_ACCESS_KEY_ID", required=False)
    sk = get("AWS_SECRET_ACCESS_KEY", required=False)
    if ak and sk:
        return boto3.client(service, region_name=region,
                            aws_access_key_id=ak, aws_secret_access_key=sk)
    for k in _AWS_VARS:
        if _is_placeholder(os.environ.get(k)):
            os.environ.pop(k, None)
    return boto3.client(service, region_name=region)


def status():
    """EFFECTIVE resolution per key, by NAME only - never a value.

    S115: the old display reported file presence, not what get() can actually resolve - so a
    fresh container printed ABSENT for keys the SSM fallback would have fetched on first ask,
    and every session opened with a false 'no keys' alarm. This walks the same order get()
    uses, and for SSM-eligible keys with nothing local it PROBES SSM and says retrievable.
    """
    names = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "DATABENTO_API_KEY", "EIA_API_KEY")
    aws_ok = bool(get("AWS_ACCESS_KEY_ID", required=False) and
                  get("AWS_SECRET_ACCESS_KEY", required=False))
    for n in names:
        if os.environ.get("MARKETS_" + n) and not _is_placeholder(os.environ.get("MARKETS_" + n)):
            src = "MARKETS_ env (environment config)"
        elif os.environ.get(n) and not _is_placeholder(os.environ.get(n)):
            src = "env"
        elif _from_file(HOME_ENV, n):
            src = "~/.config/markets/env"
        elif _from_file(LEGACY, n):
            src = "LEGACY scratchpad (move it - D33/D34)"
        elif n not in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY") and aws_ok:
            try:
                aws_client("ssm", os.environ.get("AWS_REGION") or "us-east-2").get_parameter(
                    Name=f"{SSM_PREFIX}/{n}", WithDecryption=True)
                src = "SSM (retrievable on first ask)"
            except Exception:
                src = "ABSENT (not local, not in SSM)"
        else:
            src = "ABSENT"
        note = ""
        if _is_placeholder(os.environ.get(n)):
            note = "  [container placeholder in env: ignored]"
        print(f"  {n:<24} {src}{note}")
    print(f"  {'(aws fallback)':<24} ~/.aws/credentials "
          f"{'present' if os.path.exists(os.path.expanduser('~/.aws/credentials')) else 'absent'}"
          f"  - use creds.aws_client(), not bare boto3.client()")


def sync_ssm():
    """Push the non-bootstrap keys to SSM SecureString, then VERIFY BY READ-BACK (D47).

    Run after Greg pastes a fresh set, and after any rotation. The AWS pair is deliberately NOT
    pushed - it is the bootstrap that reads SSM in the first place.
    """
    ssm = aws_client("ssm", os.environ.get("AWS_REGION") or "us-east-2")
    ok = True
    # OPENAI_API_KEY joined the set at S118: the durable box fetches it from here to build
    # /etc/markets/tunnel.env, so the value never travels in an SSM RunShellScript command line
    # (those are retained in command history and CloudTrail - a second place to leak a key).
    for name in ("DATABENTO_API_KEY", "EIA_API_KEY", "OPENAI_API_KEY"):
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
