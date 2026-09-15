# Final committed package verification

**PASS: newly assembled final-v3 package reconciles with the exact committed artifacts.**

Target commit: `35982ac7d42b546446038866299c23ca4fc50edc`. Package: `E:\Codex\Frankie-BOSS-20260915\bootstrap-jobs-final-v3`.

Bounded local artifact reconciliation only. No database, tokenizer, model, tests, cloud or account actions. No repository edits. Only this small E-drive report is written. Earlier audits and package versions were not rerun.

## Exact exported bytes

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `granite_runpod.py` | 14397 | `684893ce7089e784dcf0c0dd5329cef3cc486df4fb99646458d678615c45bf5a` |
| `granite_runpod_proxy.py` | 13596 | `2bb4b331a3a5b01c01b8bc964dc5da0b753a4e94d7dc8f463663671eb680deac` |
| `granite_runpod_jobs.py` | 10132 | `7c1e5ae64310b53e7735b0cdd43504759236c39b90ebd2ea1e48e0579875582d` |
| `granite_startup.py` | 9533 | `bb92602455c66ad4a44aefbe2d3794a75b3cb5e983408df74303ae3cf9bbfc2b` |
| `granite_run_artifacts.py` | 15983 | `8a1e07529fd4b88456e689cfc0525ebe0f07b3d4552ce74ae0c6c22e4f701b0e` |
| `granite_artifacts_manifest.json` | 1864 | `adf5304a845900b4395c2593c5d270ae727867cc9a164132510acb95d5a3091a` |
| `granite_image_identity.json` | 1285 | `f0f619cb1ed40cbd797631ad60a3c77033d9659066ab9dee729a4a7e3e413b5e` |
| `granite_runpod_progress.py` | 10233 | `baf8213087b6880189aec0afcc4a04dc69a8655c964cded90d8bfdafb7659864` |

All eight files in both committed-lf and files were compared directly against raw git-show bytes and matched exactly. Python exports contain no CRLF. Both rosters have no extra files; files additionally contains exactly runpod_bundle.json.

## Manifest and launch identities

The bundle is canonical JSON with exactly the expected schema and ordered eight-member roster. Every row size/hash agrees with Git bytes, package receipt and runtime configuration. The bundle hash agrees with package, runtime, assembly and staging-marker pins. Source commit pins all agree. The runtime raw-file hash agrees with the assembly receipt. The bundle self-witness is external; there is no circular embedded self-hash.

The supervisor command is byte-for-byte identical to reconstruction using only committed preexec_code, supervisor_metadata_code and bootstrap_command function definitions. These selected functions only generate strings. No repository/backend module or generated command was imported or executed. The parsed generated source uses open_ended=True and zero bootstrap alarm, not a 60-second alarm.

The auxiliary preexec command digest also reconciles. It uses the committed package() builder row-key order path,size,sha256. The persisted canonical JSON rows have path,sha256,size ordering; naively using that parsed order produces a different string digest. Reconstructing the actual committed builder order gives the recorded 5f0e9c1473deba5d9af80b6569a0758b138d85b3e39a9e7d42a64f7a76bf5b54. This is a explained serialization-order distinction, not changed executable file bytes. The active supervisor command itself matches independently.

## Authoritative host and checkout

Authoritative configuration read: C:/Users/A/Documents/Codex/2026-09-15/continue-from-c-users-a-documents/work/actual-host-configuration.json. Its code pin equals the target commit, repository path equals the inspected checkout, service context is 131072, context encoding is stacked_v1, transport is jobs_v1, and output budget is remaining_context. All applicable runtime-configuration fields agree.

HEAD equals the target commit and tracked status is clean. Untracked files are explicitly outside that clean-status claim. The external reviewed host at C:/Users/A/Documents/Codex/2026-09-15/continue-from-c-users-a-documents/work/run_actual_sunday.py is raw-byte identical to the working copy and retains its reviewed SHA256. CRLF-to-LF normalization produces exactly the committed host blob; the raw digest difference is fully explained by line endings.

## Measured identities

```json
{
  "bundle_bytes": 1040,
  "bundle_sha256": "67affdb2de76a3cb36f17d326b223b148c0c363794f727421bd38a5470afea39",
  "commit": "35982ac7d42b546446038866299c23ca4fc50edc",
  "committed_crlf_count": 0,
  "committed_host_lf_sha256": "5953f19c3881b0e2e15a5e0f7a32205c645b360e4f9c4bda89180f3afae80c76",
  "external_crlf_count": 386,
  "external_host_raw_sha256": "761eecae29297184b55cadb1ee5a4310ff19de9901d40e19a4f50e0d9a5a8ce0",
  "file_count": 8,
  "host_configuration_sha256": "611f68c44ea5cbf383734d1b497cdb67f917f6cf6aad4af356caa1641e34377f",
  "preexec_command_sha256": "5f0e9c1473deba5d9af80b6569a0758b138d85b3e39a9e7d42a64f7a76bf5b54",
  "runtime_configuration_raw_sha256": "18bc9b57a04eec349b52bd611bf09112354d41658463c963cb8bd1a101c47a8a",
  "supervisor_command_sha256": "391963397aed83cba895b0bc2e996b4d73d81887bfc93197f2e674256c12dbfd",
  "total_exported_bytes": 77023,
  "tracked_clean": true
}
```

## Limits

This proves newly assembled local package identities and pure command construction. It does not prove source completion, live readiness, remote upload/execution, loaded model/tokenizer identity, completed inference/learning, or cloud cleanup. No successful tests were repeated. Public staging marker metadata was inspected without encryption or staging actions.
