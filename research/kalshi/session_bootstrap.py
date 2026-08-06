"""session_bootstrap.py - one command to take a fresh container from empty to ready (S108).

WHY. data/ is gitignored and dies with the container; so does the scratchpad; and the credentials are
deliberately never committed. So every session starts by pasting keys and then running four commands
from the drop-in box, in the right order, with the right env-var suppression. That ritual has opened
three sessions in a row and gone wrong twice.

This collapses it to one command. It does NOT store keys anywhere new and it never prints them.

    python research/kalshi/session_bootstrap.py --aws-id AKIA... --aws-secret ... --bento db-...
    AWS_ID=... AWS_SECRET=... BENTO_KEY=... python research/kalshi/session_bootstrap.py
    python research/kalshi/session_bootstrap.py --verify-only      # no key writes, just check + report

What it does, in order:
  1. writes ~/.aws/credentials, scratchpad/aws.env, scratchpad/bento.env  (chmod 600, outside the repo
     tree for the first, gitignored for the others)
  2. verifies the pair via STS, printing ONLY pass/fail and the account tail
  3. restores the data plane from S3 and rebuilds vol_regime
  4. runs the completeness gate and prints each group's verdict

THE ENV-VAR TRAP (S100, cost an hour). Claude Code containers inject PLACEHOLDER AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY values that OVERRIDE ~/.aws/credentials in boto3's precedence, so a known-good key
returns InvalidClientTokenId. Every AWS call below is made with those two names stripped from the
environment. If STS ever fails on a key you trust, suspect this first, not the key.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRATCH = os.path.join(REPO, "scratchpad")
AWS_DIR = os.path.expanduser("~/.aws")
REGION = "us-east-2"


def _clean_env():
    """The container's placeholder creds must not survive into a boto3 call."""
    e = dict(os.environ)
    e.pop("AWS_ACCESS_KEY_ID", None)
    e.pop("AWS_SECRET_ACCESS_KEY", None)
    e.pop("AWS_SESSION_TOKEN", None)
    return e


def _write(path, body, label):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, 0o600)
    print(f"[bootstrap] wrote {label} (chmod 600)")


def write_keys(aws_id, aws_secret, bento):
    if aws_id and aws_secret:
        _write(os.path.join(AWS_DIR, "credentials"),
               f"[default]\naws_access_key_id = {aws_id}\n"
               f"aws_secret_access_key = {aws_secret}\nregion = {REGION}\n",
               "~/.aws/credentials")
        _write(os.path.join(SCRATCH, "aws.env"),
               f"AWS_ACCESS_KEY_ID={aws_id}\nAWS_SECRET_ACCESS_KEY={aws_secret}\n"
               f"AWS_DEFAULT_REGION={REGION}\n",
               "scratchpad/aws.env")
    if bento:
        _write(os.path.join(SCRATCH, "bento.env"), f"DATABENTO_API_KEY={bento}\n", "scratchpad/bento.env")


def verify_sts():
    """Pass/fail and the account TAIL only. Never the key, never the full account id."""
    code = ("import boto3;i=boto3.client('sts','%s').get_caller_identity();"
            "print('ACCOUNT_TAIL', i['Account'][-4:])" % REGION)
    r = subprocess.run([sys.executable, "-c", code], env=_clean_env(),
                       capture_output=True, text=True)
    if r.returncode == 0 and "ACCOUNT_TAIL" in r.stdout:
        print(f"[bootstrap] STS OK - account ...{r.stdout.split()[-1]}")
        return True
    err = (r.stderr or "").strip().splitlines()
    print(f"[bootstrap] STS FAILED: {err[-1] if err else 'unknown'}")
    print("[bootstrap]   if the key is known-good, suspect the placeholder env-var override FIRST")
    return False


def run(label, argv):
    print(f"\n[bootstrap] {label} ...")
    r = subprocess.run(argv, env=_clean_env(), cwd=REPO)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="Take a fresh container from empty to ready")
    ap.add_argument("--aws-id", default=os.environ.get("AWS_ID"))
    ap.add_argument("--aws-secret", default=os.environ.get("AWS_SECRET"))
    ap.add_argument("--bento", default=os.environ.get("BENTO_KEY"))
    ap.add_argument("--verify-only", action="store_true",
                    help="do not write keys; just verify and report what is present")
    ap.add_argument("--skip-restore", action="store_true", help="verify keys, do not pull from S3")
    a = ap.parse_args()

    if not a.verify_only:
        if not (a.aws_id and a.aws_secret):
            print("[bootstrap] no AWS pair supplied.\n"
                  "  Pass --aws-id/--aws-secret, or set AWS_ID/AWS_SECRET, or use --verify-only.\n"
                  "  Keys are NEVER committed and do NOT survive a session - this is expected, not a bug.")
            return 2
        write_keys(a.aws_id, a.aws_secret, a.bento)

    have = os.path.exists(os.path.join(AWS_DIR, "credentials"))
    print(f"[bootstrap] ~/.aws/credentials present: {have}")
    print(f"[bootstrap] scratchpad/bento.env present: {os.path.exists(os.path.join(SCRATCH, 'bento.env'))}")
    if not have:
        print("[bootstrap] NOT READY - no credentials. Staging, restore and S3 access will all fail.")
        return 2
    if not verify_sts():
        return 2

    if not a.skip_restore:
        if not run("restoring the data plane (S3 + vol_regime rebuild)",
                   [sys.executable, os.path.join(HERE, "restore_substrate.py")]):
            print("[bootstrap] restore reported a problem - VERIFY BEFORE STAGING")

    print("\n[bootstrap] completeness gate:")
    subprocess.run([sys.executable, os.path.join(HERE, "state_health.py")], env=_clean_env(), cwd=REPO)
    print("\n[bootstrap] done. A group staged at S108 or later runs BOTH rounds with no data/ at all;")
    print("[bootstrap] the data plane is needed for STAGING and for pre-S108 groups' round-2 handoff.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
