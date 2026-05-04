"""
push.py — Web Push subscription store + notification sender.

Friends subscribe via the frontend (service worker registers a push
subscription with VAPID public key, sends to /api/push/subscribe).
Backend stores subscriptions in push_subscriptions.jsonl. On each new
high-confidence signal, push handler sends a notification to all subs.

VAPID keys: generate once via `python -m backend.push --generate-keys`,
put VAPID_PRIVATE_KEY in env, copy VAPID_PUBLIC_KEY into the frontend
service worker.

For real deployment: install pywebpush. The handler does best-effort send
and logs failures; expired subscriptions are pruned automatically.

Without pywebpush installed (sandbox), the subscribe endpoint still works
- subscriptions are persisted - but the actual push send is a no-op so
the dev environment doesn't crash.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import asdict, dataclass


SUBS_PATH = os.environ.get("MARKETS_WATCH_PUSH_SUBS",
                            os.path.join(os.path.dirname(__file__), "..", "push_subscriptions.jsonl"))
VAPID_PUBLIC = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CONTACT = os.environ.get("VAPID_CONTACT_EMAIL", "mailto:admin@example.com")


@dataclass
class PushSubscription:
    endpoint: str
    keys_p256dh: str
    keys_auth: str
    user_agent: str = ""
    registered_utc: float = 0.0


def _load_subs() -> list[PushSubscription]:
    subs: list[PushSubscription] = []
    if not os.path.exists(SUBS_PATH):
        return subs
    try:
        with open(SUBS_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                subs.append(PushSubscription(**{
                    k: v for k, v in d.items()
                    if k in PushSubscription.__dataclass_fields__
                }))
    except Exception as e:
        print(f"[push] could not load subs: {e}", flush=True)
    return subs


def _save_subs(subs: list[PushSubscription]):
    tmp = SUBS_PATH + ".tmp"
    with open(tmp, "w") as f:
        for s in subs:
            f.write(json.dumps(asdict(s)) + "\n")
    os.replace(tmp, SUBS_PATH)


_subs_cache: list[PushSubscription] | None = None


def get_subs() -> list[PushSubscription]:
    global _subs_cache
    if _subs_cache is None:
        _subs_cache = _load_subs()
    return _subs_cache


def add_sub(sub: PushSubscription) -> int:
    subs = get_subs()
    if any(s.endpoint == sub.endpoint for s in subs):
        return len(subs)   # already registered
    sub.registered_utc = time.time()
    subs.append(sub)
    _save_subs(subs)
    return len(subs)


def remove_sub(endpoint: str) -> bool:
    subs = get_subs()
    n_before = len(subs)
    subs[:] = [s for s in subs if s.endpoint != endpoint]
    _save_subs(subs)
    return len(subs) < n_before


def send_to_all(payload: dict) -> dict:
    """Send a push notification to every subscribed client.

    Returns {sent: int, failed: int, expired_pruned: int}.
    """
    if not VAPID_PRIVATE:
        return {"sent": 0, "failed": 0, "expired_pruned": 0,
                "note": "VAPID_PRIVATE_KEY not set; push disabled"}
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return {"sent": 0, "failed": 0, "expired_pruned": 0,
                "note": "pywebpush not installed; push disabled"}

    sent = failed = pruned = 0
    expired_endpoints: list[str] = []
    for s in list(get_subs()):
        try:
            webpush(
                subscription_info={
                    "endpoint": s.endpoint,
                    "keys": {"p256dh": s.keys_p256dh, "auth": s.keys_auth},
                },
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE,
                vapid_claims={"sub": VAPID_CONTACT},
            )
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", 0)
            if status in (404, 410):
                expired_endpoints.append(s.endpoint)
            else:
                failed += 1
                print(f"[push] webpush error: {e}", flush=True)
        except Exception as e:
            failed += 1
            print(f"[push] unexpected error: {e}", flush=True)
    for ep in expired_endpoints:
        remove_sub(ep)
        pruned += 1
    return {"sent": sent, "failed": failed, "expired_pruned": pruned}


def generate_vapid_keypair() -> dict:
    """Generate a VAPID-compliant ECDSA P-256 keypair (urlsafe-b64-encoded).
    Run once: `python -m backend.push --generate-keys`."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return {"error": "install cryptography: pip install cryptography"}

    priv = ec.generate_private_key(ec.SECP256R1())
    priv_bytes = priv.private_numbers().private_value.to_bytes(32, "big")
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return {
        "private_b64u": base64.urlsafe_b64encode(priv_bytes).rstrip(b"=").decode(),
        "public_b64u": base64.urlsafe_b64encode(pub).rstrip(b"=").decode(),
        "instructions": [
            "1. Set VAPID_PRIVATE_KEY to the value of private_b64u in your backend env.",
            "2. Set VAPID_PUBLIC_KEY to the same value (the frontend uses public_b64u).",
            "3. Replace the placeholder applicationServerKey in service-worker.js push subscribe with public_b64u.",
            "4. Set VAPID_CONTACT_EMAIL to a real mailto: address you control.",
        ],
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--generate-keys", action="store_true")
    args = p.parse_args()
    if args.generate_keys:
        out = generate_vapid_keypair()
        print(json.dumps(out, indent=2))
