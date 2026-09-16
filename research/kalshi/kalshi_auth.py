#!/usr/bin/env python3
"""kalshi_auth.py - the Kalshi signed-request client (G0 closure, S110). CLASSIC + margin lanes.

Auth scheme (docs, verified S110): RSA-PSS SHA256 over  <timestamp_ms><METHOD><path>  with headers
KALSHI-ACCESS-KEY (key UUID) / KALSHI-ACCESS-SIGNATURE (base64) / KALSHI-ACCESS-TIMESTAMP (ms).
One RSA pair serves REST and FIX. Keys live in scratchpad/kalshi.env (never in git, never in chat):
    KALSHI_DEMO_KEY_ID=<uuid>
    KALSHI_DEMO_KEY_PEM=<path to .key PEM>

Usage:
    python kalshi_auth.py smoke              (signed GET /portfolio/balance on the CLASSIC DEMO)
    from kalshi_auth import signed_request   (the dock's client primitive)
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_CANDIDATES = (os.path.join(HERE, "..", "..", "scratchpad", "kalshi.env"),
                  os.path.join(HERE, "scratchpad", "kalshi.env"))
DEMO_BASE = "https://external-api.demo.kalshi.co"
PROD_BASE = "https://api.elections.kalshi.com"


def load_env() -> dict:
    for p in ENV_CANDIDATES:
        if os.path.exists(p):
            out = {}
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
            out["_env_path"] = p
            return out
    raise SystemExit("kalshi.env not found in scratchpad - G0 keys not provisioned")


def _sign(pem_path: str, msg: str) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    key = serialization.load_pem_private_key(open(pem_path, "rb").read(), password=None)
    sig = key.sign(msg.encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                             salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    return base64.b64encode(sig).decode()


def signed_request(method: str, path: str, body: dict | None = None, demo: bool = True) -> dict:
    """path INCLUDES /trade-api/v2... (the signed string is ts+METHOD+path, no query)."""
    env = load_env()
    kid, pem = env.get("KALSHI_DEMO_KEY_ID"), env.get("KALSHI_DEMO_KEY_PEM")
    if not kid or not pem or not os.path.exists(pem):
        raise SystemExit("kalshi.env incomplete (id or pem path missing)")
    ts = str(int(time.time() * 1000))
    base_path = path.split("?")[0]
    headers = {"KALSHI-ACCESS-KEY": kid,
               "KALSHI-ACCESS-SIGNATURE": _sign(pem, ts + method.upper() + base_path),
               "KALSHI-ACCESS-TIMESTAMP": ts,
               "User-Agent": "davisai-dock", "Content-Type": "application/json"}
    url = (DEMO_BASE if demo else PROD_BASE) + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return {"status": r.status, "body": json.loads(r.read().decode() or "{}")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode()[:400]}


def smoke() -> int:
    r = signed_request("GET", "/trade-api/v2/portfolio/balance", demo=True)
    print(f"[kalshi_auth smoke] DEMO signed GET /portfolio/balance -> HTTP {r['status']}")
    print(" ", json.dumps(r["body"])[:300])
    ok = r["status"] == 200
    print(f"[kalshi_auth smoke] {'PASS - G0 CLOSED: authenticated demo access live' if ok else 'FAIL - check key id / pem / clock'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(smoke() if (len(sys.argv) > 1 and sys.argv[1] == "smoke") or len(sys.argv) == 1 else 0)
