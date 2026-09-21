# Chat 6 scratchpad, committed whole (Greg, 2026-09-21: "You have to commit and push everything that is on your scratchpad or we'll lose it")

Every file the chat-6 container's scratchpad held, copied here byte for byte, except the entries below, each named with
its reason. Nothing in this directory is run by anything; it is the record. Greg's standing rule from here on: the
scratchpad is not used at all (D34, "there is nothing local"); the build plan (`PLAN_CYCLE0_BEDROCK_20260921.md`, BR-0)
puts the producers checkout inside the repo as a gitignored worktree.

## What is here and where it came from
- `edit_turn.py`, `edit_ship_fixes.py`, `edit_review_fixes.py`: the edit scripts that applied, respectively, the
  correction-turn plumbing (commit 28c98d70 and neighbours), the /ship security and test-engineer fixes and the
  code-reviewer fixes (both in 4416e6ac). Already applied; kept as the record of exactly what changed and why.
- `probe_*.py`, `conftest_probe.py`: read-only probes used during the ship review and the reading-endpoint work
  (identity of the classroom module across loads, the writing gate, the codecs, the GPU/HF reach of the serverless
  config, script contracts). `probe_codecs.py` line 98 sets a PLACEHOLDER AWS key (`AKIAEXAMPLEEXAMPLE00`, secret `x*40`)
  for an offline test; it is not a credential.
- `notorch/torch.py`: the one-line stub that hides torch (`PYTHONPATH=<this dir>`) so the box suites run the shim branch
  CI exercises. Use: `PYTHONPATH=research/kalshi/frankie_boss/records/chat6_scratchpad_20260921/notorch python -m pytest ...`.
- `cycle-00-docs/`: the seven-file delivery Greg asked for (README, analysis, merged notes, derivation digest,
  accounting and ledgers, the two zips) assembled from `origin/root/cycle-00-response`; 48 of its 50 files are
  byte-identical to that branch, the two zips are bundles of them.
- `brain-dry/frozen-learned-structure/`: the dry run of `frankie_box_brain.write_frozen_entry` (59 of 60 files identical
  to the committed frozen entry; `MANIFEST.json` differs by the dry run's timestamp and paths).
- `response-00.json`, `analysis-00.md`, `host-attestation.json`, `host-session-record.json`: cycle 0's first response
  files, identical to `origin/root/cycle-00-response`.
- `critic.json`: the native critic's result for cycle 0 as fetched from the host run (the zero-hypotheses finding,
  handoff 22:xxZ).
- `prompt_text.txt`, `snapshot_text.txt`: the rendered request prompt and the codec snapshot text used to measure the
  read (chat 5's stacking work, referenced by the handoff 13:5xZ).
- `stripped.txt`: a GitHub Actions run log with secrets masked by GitHub (`***`); scanned, no credential inside; the
  base64 on line 270 is a chat completion body from the reading endpoint's verification job.
- `runpod_installer.sh`: RunPod's CLI installer script as downloaded (it failed through the proxy; the handoff records
  the GitHub-release path that worked).
- `work-probe/serverless-reading-endpoint.json`: a unit-test artifact with a fake endpoint id.

## Not copied, with the reason
- `producers/` (175 MB): a git worktree of commit 2ebb8ce8 on `origin/ccode/frankie-receiver-feed-20260916`, already
  in the remote; the build plan's BR-0 checks it out inside the repo. Nothing of it is unique to the scratchpad.
- `ci313/`, `civenv/`, `pylib/` (76 MB): Python virtual environments and pip installs (pytest, pyyaml, coverage,
  yamllint, actionlint's python deps); reproducible from the CI workflows' pip lines.
- `actionlint`, `actionlint.tgz`, `runpodctl-2.14.0` (21 MB): downloaded release binaries (actionlint 1.7.x, runpodctl
  2.14.0); reproducible from their GitHub releases.
- `__pycache__/`, `.coverage`, `.resp_tree.txt`, `.head_tree.txt`: caches and the two listing files made to compare this
  directory against git.
