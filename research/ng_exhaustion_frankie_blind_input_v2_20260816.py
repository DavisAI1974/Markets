#!/usr/bin/env python3
"""Key-safe wrapper for the frozen NG exhaustion blind-input builder.

The base builder already redacts target-day values. This wrapper additionally replaces
any dictionary KEY containing a target-day token so the serialized served brain cannot
retain a target date in structural metadata. It changes no data, family, split, or outcome wall.
"""
from __future__ import annotations
from collections import OrderedDict
import sys
import ng_exhaustion_frankie_blind_input_20260816 as base


def key_safe_redact(obj, toks, counter):
    if isinstance(obj, dict):
        out = OrderedDict()
        for k, v in obj.items():
            if any(t in str(k) for t in toks):
                counter[0] += 1
                rk = f"[REDACTED_TARGET_DAY_KEY_{counter[0]}]"
                out[rk] = "[REDACTED_TARGET_DAY]"
            else:
                out[k] = key_safe_redact(v, toks, counter)
        return out
    if isinstance(obj, list):
        return [key_safe_redact(v, toks, counter) for v in obj]
    if isinstance(obj, str) and any(t in obj for t in toks):
        counter[0] += 1
        return "[REDACTED_TARGET_DAY]"
    return obj


base.redact = key_safe_redact

if __name__ == "__main__":
    base.main(sys.argv[1:])
