"""Where the pinned producers live for the box tests (plan BR-0, Greg 2026-09-21: no scratchpad; the checkout is an
in-repo gitignored worktree). `producers_root()` honours FRANKIE_BOX_PRODUCERS, else `<repo>/.producers-2ebb8ce8`.
`require_producers()` FAILS when the variable names a path that is absent (a misconfigured CI is a failure, not a
skip) and SKIPS with the reason only when the variable is unset and the default worktree is not there."""
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LINEAGE = 'ccode/frankie-receiver-feed-20260916'
PIN = '2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134'
DEFAULT_ROOT = REPO / f'.producers-{PIN[:8]}'
DRIVER = 'research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py'
DRIVER_SHA256 = '67996f3e1da9f6584bcca888eefe015c3b31508b9451335a76e2f49bfd7a8762'   # pinned in frankie_box_stage_producers.sh
CHECKOUT_SCRIPT = REPO / 'deploy' / 'aws' / 'box' / 'producers_checkout.sh'


def producers_root():
    value = os.environ.get('FRANKIE_BOX_PRODUCERS')
    return Path(value) if value else DEFAULT_ROOT


def require_producers():
    root = producers_root()
    if (root / DRIVER).is_file():
        return root
    hint = f'run: bash {CHECKOUT_SCRIPT.relative_to(REPO)}'
    if os.environ.get('FRANKIE_BOX_PRODUCERS'):
        pytest.fail(f'FRANKIE_BOX_PRODUCERS={root} is set but the producers checkout is absent there; {hint}')
    pytest.skip(f'producers checkout absent at {root} (FRANKIE_BOX_PRODUCERS unset); {hint}')
