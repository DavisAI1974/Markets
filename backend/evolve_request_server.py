"""
Small request-capture API for the private Evolve tab.

It is intentionally separate from api_server.py so phone prompt capture stays
responsive even when the market poller is busy scanning live data.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EVOLVE_REQUESTS_PATH = os.path.join(REPO_ROOT, "backend_evolve_requests.jsonl")

app = FastAPI(title="markets-watch-evolve-requests")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class EvolveRequestBody(BaseModel):
    prompt: str
    mode: str = "codebase"
    source: str = "evolve_tab"


def _load_requests(limit: int = 20) -> list[dict[str, Any]]:
    if not os.path.exists(EVOLVE_REQUESTS_PATH):
        return []
    requests: list[dict[str, Any]] = []
    try:
        with open(EVOLVE_REQUESTS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    requests.append(json.loads(line))
    except Exception as e:
        print(f"[evolve-request] load error: {e}", flush=True)
        return []
    requests.reverse()
    return requests[:limit]


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "evolve-requests"}


@app.get("/api/evolve-requests")
async def get_evolve_requests(limit: int = 20):
    return {"requests": _load_requests(max(1, min(limit, 100)))}


@app.post("/api/evolve-request")
async def post_evolve_request(body: EvolveRequestBody):
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="prompt is too long")
    record = {
        "id": f"EVREQ-{uuid.uuid4().hex[:8].upper()}",
        "ts_utc": time.time(),
        "prompt": prompt,
        "mode": body.mode,
        "source": body.source,
        "status": "new",
    }
    try:
        with open(EVOLVE_REQUESTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[evolve-request] persist error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="could not save request")
    return {"ok": True, "request": record}
