"""Repo paths + AWS credential resolution for the dashboard's READ-ONLY data plane.

Credential doctrine (CLAUDE.md "AWS KEY"): the cloud container injects PLACEHOLDER
AWS_* env vars that override ~/.aws/credentials in boto3's default chain. We therefore
NEVER rely on the default chain: credentials are read explicitly from (in order)
scratchpad/aws.env, then ~/.aws/credentials, and passed to boto3 directly. Placeholder
values (anything starting with 'proxy-') are rejected. Secrets never leave this process.
"""
from __future__ import annotations

import configparser
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DASHBOARD = os.path.dirname(HERE)
REPO = os.path.dirname(DASHBOARD)
DATA = os.path.join(REPO, "data")
KALSHI_RESEARCH = os.path.join(REPO, "research", "kalshi")
BRAIN_PATH = os.path.join(KALSHI_RESEARCH, "knowledge", "ng_brain.json")
AWS_ENV = os.path.join(REPO, "scratchpad", "aws.env")
BUCKET = "bento-568968024170-us-east-2-an"
REGION = "us-east-2"


def _looks_real(key_id: str | None, secret: str | None) -> bool:
    if not key_id or not secret:
        return False
    if key_id.startswith("proxy-") or secret.startswith("proxy-"):
        return False
    return key_id.startswith("AKIA") and len(secret) >= 30


def resolve_aws_creds() -> dict | None:
    """Return {'aws_access_key_id':..., 'aws_secret_access_key':...} or None. Explicit
    sources only; the container's placeholder env vars are deliberately ignored."""
    if os.path.exists(AWS_ENV):
        kv = {}
        for line in open(AWS_ENV):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
        kid = kv.get("AWS_ACCESS_KEY_ID")
        sec = kv.get("AWS_SECRET_ACCESS_KEY")
        if _looks_real(kid, sec):
            return {"aws_access_key_id": kid, "aws_secret_access_key": sec}
    cred_file = os.path.expanduser("~/.aws/credentials")
    if os.path.exists(cred_file):
        cp = configparser.ConfigParser()
        cp.read(cred_file)
        for section in cp.sections():
            kid = cp[section].get("aws_access_key_id")
            sec = cp[section].get("aws_secret_access_key")
            if _looks_real(kid, sec):
                return {"aws_access_key_id": kid, "aws_secret_access_key": sec}
    return None


def s3_client():
    """Explicit-credential S3 client, or None when no real credentials are resolvable."""
    creds = resolve_aws_creds()
    if creds is None:
        return None
    import boto3
    return boto3.client("s3", region_name=REGION, **creds)
