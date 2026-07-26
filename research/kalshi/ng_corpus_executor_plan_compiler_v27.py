#!/usr/bin/env python3
"""Public stable-plan compiler for attribution-authorized readiness v32."""
from __future__ import annotations

import ng_corpus_executor_plan_compiler_v27_core as _core
import ng_corpus_executor_plan_compiler_v27_impl as _impl

for _module in (_core, _impl):
    for _name in dir(_module):
        if not _name.startswith("__"):
            globals()[_name] = getattr(_module, _name)

if __name__ == "__main__":
    raise SystemExit(main())
