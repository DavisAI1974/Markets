from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oracle_runtime_preflight import verify_oracle_runtime_paths


if __name__ == "__main__":
    verify_oracle_runtime_paths()
    print("oracle runtime paths ok")
