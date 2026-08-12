"""Repo paths and canonical credential access for the dashboard read plane.

Credential resolution belongs to ``research/kalshi/creds.py``. The dashboard must not grow an
independent source order: that module handles MARKETS_-prefixed environment variables, ordinary
process environment variables with container placeholders rejected, ``~/.config/markets/env``,
the legacy migration path, and the shared AWS-credentials fallback used by ``aws_client``.

Secrets never enter dashboard responses, logs, HTML, or browser state.
"""
from __future__ import annotations

import importlib.util
import os
from types import ModuleType

HERE = os.path.dirname(os.path.abspath(__file__))
DASHBOARD = os.path.dirname(HERE)
REPO = os.path.dirname(DASHBOARD)
DATA = os.path.join(REPO, "data")
KALSHI_RESEARCH = os.path.join(REPO, "research", "kalshi")
BRAIN_PATH = os.path.join(KALSHI_RESEARCH, "knowledge", "ng_brain.json")
CREDS_PATH = os.path.join(KALSHI_RESEARCH, "creds.py")
SHARED_AWS_CREDENTIALS = os.path.expanduser("~/.aws/credentials")
BUCKET = "bento-568968024170-us-east-2-an"
REGION = "us-east-2"

_creds_module: ModuleType | None = None


def _canonical_creds() -> ModuleType:
    """Load the signal core's credential module without relying on a generic ``creds`` import."""
    global _creds_module
    if _creds_module is not None:
        return _creds_module
    spec = importlib.util.spec_from_file_location("markets_canonical_creds", CREDS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical credential resolver: {CREDS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _creds_module = module
    return module


def _looks_real(key_id: str | None, secret: str | None) -> bool:
    """Defence in depth after canonical resolution; placeholder values are never credentials."""
    if not key_id or not secret:
        return False
    if key_id.lower().startswith("proxy-") or secret.lower().startswith("proxy-"):
        return False
    return key_id.startswith(("AKIA", "ASIA")) and len(secret) >= 30


def resolve_aws_creds() -> dict | None:
    """Return an explicit AWS pair resolved by ``research/kalshi/creds.py``, or ``None``.

    The returned mapping is for server-side boto clients only. It is never serialized.
    ``~/.aws/credentials`` remains a fallback inside the canonical module's ``aws_client`` and
    is reported separately by :func:`aws_credential_status` rather than re-parsed here.
    """
    resolver = _canonical_creds()
    key_id = resolver.get("AWS_ACCESS_KEY_ID", required=False)
    secret = resolver.get("AWS_SECRET_ACCESS_KEY", required=False)
    if not _looks_real(key_id, secret):
        return None
    return {"aws_access_key_id": key_id, "aws_secret_access_key": secret}


def aws_credential_status() -> dict:
    """Safe source-level status. Never returns a key, path contents, or secret value."""
    explicit = resolve_aws_creds()
    shared_present = os.path.isfile(SHARED_AWS_CREDENTIALS)
    return {
        "resolved": explicit is not None,
        "source": "research/kalshi/creds.py" if explicit is not None else None,
        "shared_credentials_present": shared_present,
        "note": (
            None if explicit is not None else
            "AWS pair not resolved by research/kalshi/creds.py. Set MARKETS_AWS_ACCESS_KEY_ID "
            "and MARKETS_AWS_SECRET_ACCESS_KEY in the server environment, or write the bare "
            "names to ~/.config/markets/env with chmod 600. The canonical aws_client also "
            "supports ~/.aws/credentials when present."
        ),
    }


def s3_client():
    """Canonical explicit-credential S3 client, or ``None`` when no source is available."""
    status = aws_credential_status()
    if not status["resolved"] and not status["shared_credentials_present"]:
        return None
    return _canonical_creds().aws_client("s3", REGION)
