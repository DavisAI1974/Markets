"""aws/run_discovery_s3.py — S3-driven coeff-discovery job for AWS (Batch/Fargate or EC2).

Reads 1-second bins from S3, runs the SAME in-container pipeline that's validated locally
(_build_alt_winner_labels -> _run_alt_coeffs, the DETERMINISTIC cs100_v2 decoder tier, S39),
and writes the coeff index back to S3. This is also the off-git storage answer (S37): bins
live in S3, not git.

Pure numpy + boto3 — no GPU, no torch, no E:\refrag. GPU is only for FNO training (train_fno/).

Env (all optional except bucket):
  S3_BUCKET        (required) e.g. davisai-markets
  S3_BINS_PREFIX   default "realbins"   -> s3://<bucket>/<prefix>/<coin>_<venue>_bins.json[.gz]
  S3_OUT_PREFIX    default "coeffs"      -> s3://<bucket>/<prefix>/alt_coeff_index.json.gz
  CELLS            default "doge:DOGE,xrp:XRP,sol:SOL" (coin:ASSET, comma list)
  VENUE            default "bybit_perp"
  CAP              default "100"
  SIDES            default "buy,sell"

Local run for testing (no S3): set NO_S3=1 and it uses ./realbins + ./_alt_labels in place.
"""
from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUCKET = os.environ.get("S3_BUCKET")
BINS_PREFIX = os.environ.get("S3_BINS_PREFIX", "realbins")
OUT_PREFIX = os.environ.get("S3_OUT_PREFIX", "coeffs")
CELLS = os.environ.get("CELLS", "doge:DOGE,xrp:XRP,sol:SOL")
VENUE = os.environ.get("VENUE", "bybit_perp")
CAP = os.environ.get("CAP", "100")
SIDES = os.environ.get("SIDES", "buy,sell")
NO_S3 = os.environ.get("NO_S3") == "1"

REAL = Path("realbins"); LABELS = Path("_alt_labels"); COEFFS = LABELS / "coeffs"


def _s3():
    import boto3
    return boto3.client("s3")


def pull_bins(coin: str):
    """Download <coin>_<venue>_bins.json[.gz] from S3 into realbins/ (gunzip if needed)."""
    REAL.mkdir(exist_ok=True)
    base = f"{coin}_{VENUE}_bins.json"
    dst = REAL / base
    if NO_S3:
        if dst.exists():
            return True
        print(f"[s3] NO_S3 and {dst} missing", flush=True); return False
    s3 = _s3()
    for key in (f"{BINS_PREFIX}/{base}.gz", f"{BINS_PREFIX}/{base}"):
        try:
            tmp = REAL / (base + (".gz" if key.endswith(".gz") else ""))
            s3.download_file(BUCKET, key, str(tmp))
            if key.endswith(".gz"):
                with gzip.open(tmp, "rb") as fi, open(dst, "wb") as fo:
                    shutil.copyfileobj(fi, fo)
                tmp.unlink()
            print(f"[s3] pulled {key}", flush=True); return True
        except Exception:
            continue
    print(f"[s3] no bins for {coin} under s3://{BUCKET}/{BINS_PREFIX}/", flush=True)
    return False


def main() -> int:
    if not NO_S3 and not BUCKET:
        print("S3_BUCKET required (or set NO_S3=1)", flush=True); return 2
    cells = [c.strip() for c in CELLS.split(",") if c.strip()]
    coins = [c.split(":")[0] for c in cells]
    assets = {c.split(":")[0]: c.split(":")[1] for c in cells}

    for coin in coins:
        if not pull_bins(coin):
            continue
        subprocess.run([sys.executable, "_build_alt_winner_labels.py",
                        "--bins-path", str(REAL / f"{coin}_{VENUE}_bins.json"),
                        "--asset", assets[coin], "--venue", VENUE, "--sides", SIDES],
                       check=True)

    subprocess.run([sys.executable, "_run_alt_coeffs.py", "--cap", CAP], check=True)

    out = COEFFS / "alt_coeff_index.json.gz"
    if not out.exists():
        print("[done] no coeff index produced", flush=True); return 1
    if NO_S3:
        print(f"[done] {out} ({out.stat().st_size} bytes) — NO_S3, left local", flush=True)
        return 0
    key = f"{OUT_PREFIX}/alt_coeff_index.json.gz"
    _s3().upload_file(str(out), BUCKET, key)
    print(f"[done] uploaded s3://{BUCKET}/{key}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
