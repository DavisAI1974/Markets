"""Atomic, source-bound local snapshots. No live scheduler integration."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from .core import _digest, LocalityError

def seal_snapshot(path:str|Path, payload:dict, *, source_identity:str,
                  contract_identity:str)->str:
    target=Path(path)
    if not source_identity or not contract_identity:
        raise LocalityError("source and contract identities required")
    if target.exists(): raise LocalityError("refusing to overwrite snapshot")
    wrapper={"schema":1,"source_identity":source_identity,
             "contract_identity":contract_identity,"payload":payload}
    try:
        wrapper["sha256"]=_digest(wrapper)
        data=json.dumps(wrapper,sort_keys=True,allow_nan=False).encode("utf-8")
    except ValueError as exc:
        # E-13: a NaN/inf payload is a contract refusal, not a bare serializer error.
        raise LocalityError("snapshot payload must be finite JSON (no NaN/inf)") from exc
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".locality-",dir=str(target.parent))
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if target.exists(): raise LocalityError("snapshot collision")
        # Hard-link publication is no-clobber; the temp file remains local to same filesystem.
        os.link(tmp,target)
        dirfd=os.open(target.parent,os.O_RDONLY)
        try: os.fsync(dirfd)
        finally: os.close(dirfd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return wrapper["sha256"]

def load_snapshot(path:str|Path,*,source_identity:str,contract_identity:str)->dict:
    # E-13: distinct, cause-preserving failures so the operator can tell them apart.
    try:
        text=Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LocalityError("missing snapshot") from exc
    except PermissionError as exc:
        raise LocalityError("unreadable snapshot: permission denied") from exc
    except OSError as exc:
        raise LocalityError("unreadable snapshot") from exc
    try:
        raw=json.loads(text)
    except ValueError as exc:
        raise LocalityError("torn or corrupt snapshot JSON") from exc
    if not isinstance(raw,dict) or raw.get("schema")!=1:
        raise LocalityError("unsupported snapshot")
    digest=raw.get("sha256")
    if not isinstance(digest,str) or digest!=_digest({k:v for k,v in raw.items() if k!="sha256"}):
        raise LocalityError("tampered snapshot")
    if raw.get("source_identity")!=source_identity or raw.get("contract_identity")!=contract_identity:
        raise LocalityError("incompatible snapshot identities")
    return raw["payload"]
