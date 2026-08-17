# Frankie 1 freeze

The immutable parent baseline is commit `03d03c3ec5de9274ccb26b15ee51e9355624f316`
from `chatgpt/ng-exhaustion-chain-full-history-phase1-20260817`.

`freeze_manifest.json` pins 166 parent runtime, brain/lens, specialist, schema, workflow,
deployment, and test files with SHA-256 and Git blob identities. In particular:

- `research/kalshi/spawn.py` SHA-256:
  `a9bdad63c71f05a2897ffd10d4ca5ac56bfe1030b92db139668254ee68361e6c`
- `research/kalshi/spawn.py` Git blob:
  `2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e`

`origin.verify_freeze()` hashes the current files and fails closed on a missing or changed byte.
`origin.assert_descendant_write_path()` rejects trader state paths outside this descendant package.
Neither trader imports a Frankie 1 runtime module; the only parent boundary is a detached JSON copy
adapted by `ReadOnlyForecastAdapter`.
