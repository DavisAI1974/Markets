# Frankie pre-launch audit — 2026-09-16

**Verdict: HOLD. The retained evidence checks below pass; no single current launch tree/configuration combines the required recovery, classroom and receiver behavior. This audit does not clear a result-bearing launch.**

Greg requested the September 14 full-evidence audit again, then a handoff for Claude to take over the box. He narrowed the work to audit and handoff. No model invocation, training, Pod restart, EC2 start/stop, new workflow or scientific implementation was performed.

## Exact scope and identities

Recovered plan from Codex task `Review Frankie BOSS handoffs`, September 14 (`01a0a0b8-b0d9-7083-a899-47be57ad58a5`): preserve every row/field, original numeric/type semantics, partial and failed records, causal cutoffs, restart state and physical integrity; trace retained evidence into computation and principal delivery; preserve agent attribution. Extended it to compact-source/reducer/cache changes, mandatory Dipole classroom, output documents and Memory A carry.

Audited Git identities:

| Surface | Branch | Exact SHA |
|---|---|---|
| Classroom/recovery composition and feed-wiring continuation | `chatgpt/frankie-feed-output-memory-wiring-20260916` | `d152dd82a3f8a639f51a8585c0fc65c547270d39` |
| Current recovery/compact-source/ingestion work | `ccode/frankie-lawful-recovery-review-20260915` | `34301ac081016a1e750bd99303267e27941aeb9e` |
| Corrected receiver, memory carry and two required documents | `ccode/frankie-receiver-feed-20260916` | `2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134` |
| Scientific comparison ancestor | lawful failed-run lineage | `050c5056c3657a954d6a3ee17f3a216999930768` |

Read the actual trees and local checkouts; documentation tips were treated as historical until checked. Audit deliverables live on a separate documentation branch. Neither the recovery nor receiver implementation branch was changed.

## Retained evidence verification

**Fresh full physical journal audit passed:** 114,054 entries, 57,027 INPUT records and 57,027 APPLIED records, every exact typed raw-record pair matched. Full compact journal SHA/size was unchanged before/after: `19603159548b1e443a3565f8c999543981c43c23c80fd511c11e760f633b260f`, 569,667,584 bytes. Terminal head `d8de0394367b66ea034d2553c3dd45fb7b1ae2b3c92724f8817627118f173500`; independently retained terminal checkpoint SHA `750dbb3c63ab672614323dca0dd7f363847ea78aa8a489d0f0b84afe8f00bcf7`. No sampling. Read/verification took 671.56 seconds using the reader's three available worker CPUs.

**Fresh delivered-ledger physical hashes passed:** all three complete files matched the original delivery receipt: member ledger 10,756,276,521 bytes, lifecycle/runway ledger 300,309,453 bytes, legacy observable rows 29,329,182 bytes. All hashes and byte counts are retained in `evidence/delivery-ledger-physical-audit.json`.

The journal verification covers every retained compact envelope, block hash, ordered seam, journal terminal identity and exact typed INPUT/APPLIED raw-record pair. It checks physical SHA/size before and after the read. It does not establish model understanding, re-decode the original DBN with historical binaries, or prove all 19 future principal attachments.

The receiver physically loaded the retained Sunday principal bundle and re-verified its chains: **30 historical ledgers**. Their required set is the contract that existed when that run was filed. They are not represented as satisfying today's 32-ledger contract.

`carry_run_into_memory --check --all` passed on receiver `2ebb8ce8`: seed matches generated v2 (82 entries), mission pin matches, generated knowledge sources include 63 KEEP and three own-run artifacts, registry rebind matches, and the retained Sunday run is carried with the explicit historical verdict `RECEIPT_AND_CHAINS_VERIFIED_FILED_UNDER_PRIOR_REGISTRY_OR_CONTRACT`. The two new documents are honestly marked not filed because the run predates their contract.

Re-rendered the retained Sunday A_MEMORY delivery against the current receiver's crosswalk tool, including its historical output receipt and retained sealed-absence proof:

| Measure | Result |
|---|---:|
| Registered / applicable | 99 / 98 |
| Applicable inputs | 77 |
| Delivered | 75 |
| Principal-stamped | 1 |
| Degenerate proof, same subject | 1 |
| Carrier mismatches / no producer | 0 / 0 |
| Sealed proven / unproven | 9 / 0 |
| Registry output layers filed / pending | 10 / 0 |
| Shadow layers disabled by policy | 2 |

Tool gate passed; crosswalk SHA `a5cc72274a74baed831479d150aaee69eb441966e8217511f8d9f60f083bcac8`. The gate accepts principal-stamped/degenerate statuses; it does not eliminate the independent-proof finding below. The sealed proof here is the retained cycle-0 proof, not a new scan of a future integrated prompt.

Restoration manifest hash coverage passed **27/27**, no missing/conflicting pins. The bulk addendum pins CRLF manifest SHA `c8b2e0f5d4a7ef26844dccd5819f82bd5141c0b05ef1e60c6c6e52e69f25cf41`. Git's LF form hashes to `8e41e4676abbc3a198f4769950e376ecc4ec10c0b9aa54c117b46681b0e29708`. Converting only line endings reproduces the exact pinned CRLF SHA and passes the original audit. This is a deployment-byte requirement, not a content defect. This coverage check validates manifest/addendum pin consistency; it is not a fresh full read of all 27 remote bulk objects.

## Findings requiring Claude's resolution

1. **Required — no final integrated tree.** Recovery `34301ac` lacks the classroom modules and uses the base principal adapter. The continuation `d152dd8` contains the explicit classroom composition but its recovery parent predates the latest recovery work. Comparing two good branches separately cannot clear the combined launch. Reconcile them in isolation and retain current compact-source/reducer/migration behavior and mandatory classroom behavior.
2. **Required — actual retained launch pins are stale.** `E:/Codex/Frankie-BOSS-20260915/sunday-launch-20260915/actual-host-final-configuration.json` pins BOSS `050c5056`, receiver `342f57288d8fbc52a9143c16e7d5dba9d90469cf`, and completion ref `codex/full-frankie-boss-connection-20260915`. The current receiver adds required `what_he_learned` and `in_his_own_words`, growing outputs from 30 to 32, plus the preparation output-bundle gate. Preserve old config as historical evidence; produce a fresh independently reviewed config for the new run.
3. **Required — compact-source launch can select the old host.** `operations/run_actual_sunday_compact_source.py` loads `host_runtime.repository`, subclasses that checkout's `ActualHost`, and substitutes it into its main. Its source/prefix audit mode performs no model step. Do not treat that mode as proof that result-bearing execution selects the integrated classroom adapter. On recovery's current tree the base host/adapter remains the production route. Verify composition on the final tree and reject missing classroom package/adapter before dispatch.
4. **Required — sealed/output admission is not end-to-end wired on the BOSS boundary inspected.** `frankie_principal_adapter.py:222` prepares receiver output; `_request` at line 339 checks witnesses but does not call sealed-absence proof; `recover` at line 418 does not demand the current principal's 32-ledger output bundle. Existing options/manual receipts are insufficient. New receiver preparation also needs explicit `--principal-artifact` and `--outputs-dir`, or the declared historical `--without-output-bundle` policy. Do not silently exempt a new run.
5. **Required — independent Memory A proof remains unresolved.** The actual historical delivery crosswalk still reports `DEGENERATE_PROOF_SAME_AS_SUBJECT` for one prior-package proof. Successful current carry checks prove the corrected seed/files are generated consistently; they do not establish an independent witness over the seed served to a new session. Preserve frozen pre-Sunday memory for the comparison; newer carry is a distinct identity.
6. **Required — authority map omits new stores.** The inspected `AUTHORITY_MAP.json` has no declared classroom-audit or principal-artifact ownership. Declare semantic writers/readers and hash/admission boundaries before the final composition audit. Keep teacher key and full grade outside the model-facing principal directory.
7. **Required verification — science-byte claims need exceptions stated.** Compared the reviewed science list against `050c5056`; two files differ: `c15_journal.py` (typed pack fast path) and `prepared_context_cache.py` (reader-owned `stored_tail`, compact compatibility). Do not claim all science files are byte-identical. Focused equivalence/cache checks pass; these changes need their correct code/runtime identity. Other files in the enumerated teacher/model/normalizer/packet/refrag comparison list have no Git diff.
8. **Reported remote blocker — restored receiver worktree has no parent repository.** The later host restoration record says `RECEIVER_HEAD` was empty because its parent Git repository was not included in the restore set. The disposable benchmark did not require it, but the principal path's strict `_code()` does. Claude must restore/verify the intended receiver Git checkout at the exact expected path and commit before preparing a principal request. This is from the completed host session record, not a fresh read of the stopped host.

No field/row loss was observed in the completed retained-journal checks. The listed launch issues prevent a claim that the latest combined pipeline delivers everything into the intended sessions.

## Focused verification

| Tree | Checks | Result |
|---|---|---|
| `d152dd8` | source conformance, journal reader, compact journal/source, causal records, principal/runtime boundary, classroom reconciliation/final review/integration | 99 passed, 25.44 s |
| receiver `2ebb8ce8` | output ledgers, sealed absence, layer crosswalk, seed carry, required documents, carry automation | 246 passed, 44.56 s |
| recovery `34301ac` | reduction equivalence, prepared cache, compact-source host, retained migration | 21 passed, 24.51 s |

These are separate tree-specific suites, not a single final integrated suite. Early collection attempts lacked sparse `research/refrag` or the repository's standalone module search paths; dependencies/search paths were corrected and the final invocations passed. No passing suite was repeated afterward. No full suite, inference, native-step benchmark or result-bearing run was performed.

The older independent source-verification GitHub run `34958705448` is cancelled at verification. Its successful transfer/setup is not a passed verification. Later reducer completion evidence is recorded in the existing recovery handoff (`34962256086`); it was not substituted for this audit's fresh physical read. Greg's standing instruction is no new workflow until the build is complete and he requests one.

## Live infrastructure and limits

Live Runpod read: migrated Pod `ycf4v6lmave6xw`, RUNNING, one `NVIDIA L40S`, 32 vCPUs, tool cost field 1.09. Old Pod `jvs75m56w8f73q` EXITED. No infrastructure mutation was performed. Running status alone is not an application-health/inference check.

Live EC2 status via the existing helper: `i-0e90ee6110ef609aa`, STOPPED, `r7i.4xlarge`, `us-east-2`, `KeepRunning=false`, profile `Ssm`. The helper's cumulative-cost estimate is not a billing receipt. Remote restored-file bytes and current remote tool versions were not re-read because the host is stopped; Claude owns that takeover verification.

Read `CLAUDE_HANDOFF.md` for navigation and next actions. Keep launch closed until the exact integrated tree/config, full per-cycle admission and remote restoration checks are reconciled.
